import datetime
import pathlib

from camoufox.async_api import AsyncCamoufox

_BLOCK_TITLES = {"just a moment", "attention required", "access denied", "403 forbidden", "captcha"}


def open_browser(headless: bool = False):
    return AsyncCamoufox(headless=headless)


def _is_blocked_title(title: str) -> bool:
    return any(k in title.lower() for k in _BLOCK_TITLES)


async def _save_debug_snapshot(page, label: str) -> str:
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    debug_dir = pathlib.Path("debug")
    debug_dir.mkdir(exist_ok=True)
    stem = debug_dir / f"{label}_{ts}"
    await page.screenshot(path=str(stem.with_suffix(".png")), full_page=False)
    stem.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
    return str(stem)


async def load_category_page(page, url: str) -> int:
    """Navigate to bina.az homepage first (session warm-up), then to the search URL.
    Returns the total listing count shown on the page.
    Raises RuntimeError if a bot-check / block page is detected."""
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

    title = await page.title()
    if _is_blocked_title(title):
        snap = await _save_debug_snapshot(page, "blocked")
        raise RuntimeError(f"Bot-check / block page detected (title={title!r}), snapshot: {snap}")

    total = await page.evaluate(r"""() => {
        const m = document.body.innerText.match(/\((\d+)\)/);
        // Remove vipped/featured block and footer so they don't pollute card extraction
        const vipped = document.getElementById('search-page-vipped');
        if (vipped) vipped.remove();
        document.querySelectorAll('footer, .footer, #footer, .site-footer').forEach(el => el.remove());
        return m ? parseInt(m[1]) : 0;
    }""")
    return total


async def scroll_and_extract(page, target: int = 0, stop_check=None) -> list[dict]:
    """Scroll and extract cards incrementally.

    Stops when:
    - len(extracted) >= target (the Elanlar count from the page header), OR
    - stop_check(all_cards) returns True (incremental mode: consecutive known listings)
    """
    await page.set_viewport_size({"width": 1280, "height": 900})
    all_cards: list[dict] = []
    last_pos = 0
    stalls = 0
    MAX_STALLS = 5  # safety exit: stop after 5 consecutive passes with no new cards

    while True:
        if target > 0 and len(all_cards) >= target:
            print(f"  reached target {target} → done ({len(all_cards)} extracted)")
            break

        scroll_height = await page.evaluate("() => document.body.scrollHeight")

        pos = last_pos
        while pos < scroll_height:
            pos += 800
            await page.evaluate(f"window.scrollTo(0, {pos})")
            await page.wait_for_timeout(150)
        last_pos = pos
        await page.wait_for_timeout(800)

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

        if new_cards:
            all_cards.extend(new_cards)
            stalls = 0
            print(f"  {len(all_cards)}/{target or '?'} extracted")

            if stop_check and stop_check(all_cards):
                break
        else:
            stalls += 1
            if stalls >= MAX_STALLS:
                print(f"  no new cards for {MAX_STALLS} passes → done ({len(all_cards)} extracted)")
                break

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


async def fetch_prices_batch(page, item_ids: list[str]) -> dict[str, int | None]:
    """Fetch prices for up to 300 listings in a single GraphQL request using aliases.
    Returns {id: price_or_None}."""
    if not item_ids:
        return {}
    alias_fields = " ".join(
        f'i{id}: item(id: "{id}") {{ price {{ total }} }}' for id in item_ids
    )
    try:
        data = await page.evaluate(
            """async (query) => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 30000);
            try {
                const r = await fetch('https://bina.az/graphql', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query }),
                    signal: controller.signal
                });
                return r.json();
            } finally { clearTimeout(timer); }
        }""",
            f"query {{ {alias_fields} }}",
        )
        result = data.get("data") or {}
        return {
            id: (result.get(f"i{id}") or {}).get("price", {}).get("total")
            for id in item_ids
        }
    except Exception:
        return {id: None for id in item_ids}


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
