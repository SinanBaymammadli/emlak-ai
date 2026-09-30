from camoufox.async_api import AsyncCamoufox


def open_browser(headless: bool = False):
    return AsyncCamoufox(headless=headless)


async def load_category_page(page, url: str) -> int:
    """Navigate to bina.az homepage first (session warm-up), then to the search URL.
    Returns the total listing count shown on the page."""
    await page.goto("https://bina.az", wait_until="domcontentloaded", timeout=60_000)
    try:
        await page.wait_for_function(
            "() => document.title !== 'Just a moment...'", timeout=30_000
        )
    except Exception:
        pass
    await page.wait_for_timeout(3_000)

    await page.goto(url, wait_until="load", timeout=60_000)
    try:
        await page.wait_for_function(
            "() => document.title !== 'Just a moment...'", timeout=30_000
        )
    except Exception:
        pass
    await page.wait_for_timeout(3_000)

    total = await page.evaluate(r"""() => {
        const m = document.body.innerText.match(/\((\d+)\)/);
        // Remove footer so scroll stall detection triggers cleanly at last listing
        document.querySelectorAll('footer, .footer, #footer, .site-footer').forEach(el => el.remove());
        return m ? parseInt(m[1]) : 0;
    }""")
    return total


async def scroll_and_extract(page) -> list[dict]:
    """Scroll and extract cards incrementally, marking each with data-x to avoid duplicates.
    Returns the full list of extracted cards.
    """
    await page.set_viewport_size({"width": 1280, "height": 900})
    all_cards: list[dict] = []
    prev_total, stalls, last_pos = 0, 0, 0

    while stalls < 3:
        scroll_height = await page.evaluate("() => document.body.scrollHeight")
        pos = last_pos
        while pos < scroll_height:
            pos += 800
            await page.evaluate(f"window.scrollTo(0, {pos})")
            await page.wait_for_timeout(200)
        last_pos = pos
        await page.wait_for_timeout(1_500)

        total = await page.evaluate(
            "() => document.querySelectorAll('.item-card').length"
        )

        if total > prev_total:
            new_cards = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('.item-card:not([data-x])').forEach(card => {
                    const a = card.querySelector('a[href*="/items/"]');
                    if (!a) return;
                    const m = a.getAttribute('href').match(/\\/items\\/(\\d+)/);
                    if (!m) return;
                    const img = card.querySelector('img');
                    const photo_url = img ? (img.src || img.dataset.src || null) : null;
                    card.setAttribute('data-x', '1');
                    results.push({id: m[1], text: card.innerText.trim(), photo_url});
                });
                return results;
            }""")

            all_cards.extend(new_cards)
            print(f"  scroll: {total} loaded, {len(all_cards)} extracted")
            prev_total, stalls = total, 0
        else:
            stalls += 1

    return all_cards


async def extract_cards(page) -> list[dict]:
    """Extract all unprocessed listing cards (used for SCRAPE_LIMIT mode)."""
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1_000)
    return await page.evaluate("""() => {
        const seen = new Set(), results = [];
        document.querySelectorAll('.item-card').forEach(card => {
            const a = card.querySelector('a[href*="/items/"]');
            if (!a) return;
            const m = a.getAttribute('href').match(/\\/items\\/(\\d+)/);
            if (!m) return;
            if (seen.has(m[1])) return;
            seen.add(m[1]);
            const img = card.querySelector('img');
            const photo_url = img ? (img.src || img.dataset.src || null) : null;
            results.push({id: m[1], text: card.innerText.trim(), photo_url});
        });
        return results;
    }""")


async def fetch_item_graphql(page, item_id: str) -> dict:
    """Fetch listing details from bina.az GraphQL. Returns {} on any error or timeout."""
    try:
        data = await page.evaluate(
            """async (id) => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 15000);
            try {
                const r = await fetch('https://bina.az/graphql', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        operationName: 'GetItem',
                        variables: {id},
                        query: `query GetItem($id: ID!) {
                            item(id: $id) {
                                id latitude longitude
                                landArea { value }
                                area { value }
                                hasRepair
                                hasBillOfSale
                                hasMortgage
                                floor
                                updatedAt
                                isFeatured
                                title
                                description
                                category { id name slug }
                                location { id name }
                            }
                        }`
                    }),
                    signal: controller.signal
                });
                return r.json();
            } finally {
                clearTimeout(timer);
            }
        }""",
            item_id,
        )
        item = (data.get("data") or {}).get("item") or {}
        has_repair = item.get("hasRepair")
        return {
            "lat": item.get("latitude"),
            "lng": item.get("longitude"),
            "land_area_sot": (item.get("landArea") or {}).get("value"),
            "area_m2_gql": (item.get("area") or {}).get("value"),
            "has_repair": bool(has_repair) if has_repair is not None else None,
            "has_bill_of_sale": item.get("hasBillOfSale"),
            "has_mortgage": item.get("hasMortgage"),
            "floor_number": item.get("floor"),
            "updated_at_site": item.get("updatedAt"),
            "is_featured": item.get("isFeatured"),
            "title": item.get("title"),
            "description": item.get("description"),
            "building_type": (item.get("category") or {}).get("name"),
            "location_id": (item.get("location") or {}).get("id"),
            "location_name": (item.get("location") or {}).get("name"),
        }
    except Exception:
        return {}
