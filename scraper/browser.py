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
        return m ? parseInt(m[1]) : 0;
    }""")
    return total


async def scroll_load_all(page) -> int:
    """Scroll viewport-by-viewport to trigger IntersectionObserver lazy loading.
    Continues from the last position so we never scroll back to the top mid-scrape.
    """
    await page.set_viewport_size({"width": 1280, "height": 900})
    prev, stalls, last_pos = 0, 0, 0
    while stalls < 3:
        scroll_height = await page.evaluate("() => document.body.scrollHeight")
        pos = last_pos
        while pos < scroll_height:
            pos += 800
            await page.evaluate(f"window.scrollTo(0, {pos})")
            await page.wait_for_timeout(200)
        last_pos = pos
        await page.wait_for_timeout(1_500)
        count = await page.evaluate(
            "() => document.querySelectorAll('.item-card').length"
        )
        if count > prev:
            print(f"  scroll: {count} cards")
            prev, stalls = count, 0
        else:
            stalls += 1
    return prev


async def extract_cards(page) -> list[dict]:
    """Extract all listing cards from the current page."""
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
    """Fetch lat, lng, area, hasRepair from bina.az GraphQL using the browser session."""
    try:
        data = await page.evaluate(
            """async (id) => {
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
                            floor
                            updatedAt
                            isFeatured
                            title
                            description
                            category { id name slug }
                            location { id name }
                        }
                    }`
                })
            });
            return r.json();
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
