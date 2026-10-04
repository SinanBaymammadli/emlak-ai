import datetime
import pathlib

from camoufox.async_api import AsyncCamoufox


def open_browser(headless: bool = False):
    return AsyncCamoufox(headless=headless)


async def _save_debug_snapshot(page, label: str) -> str:
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    debug_dir = pathlib.Path("debug")
    debug_dir.mkdir(exist_ok=True)
    stem = debug_dir / f"{label}_{ts}"
    await page.screenshot(path=str(stem.with_suffix(".png")), full_page=False)
    stem.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
    return str(stem)


async def warmup(page) -> None:
    """Load bina.az homepage to establish a session and pass Cloudflare."""
    await page.goto("https://bina.az", wait_until="domcontentloaded", timeout=60_000)
    try:
        await page.wait_for_function(
            "() => document.title !== 'Just a moment...'", timeout=30_000
        )
    except Exception:
        pass
    await page.wait_for_timeout(3_000)


async def fetch_items_page(
    page, category_id: str, leased: bool, cursor: str | None
) -> tuple[list[dict], str | None, bool, int]:
    """Fetch one page of 25 listings via itemsConnection.
    Returns (edges, next_cursor, has_next_page, total_count)."""
    after = f', after: "{cursor}"' if cursor else ""
    query = f"""query {{
        itemsConnection(
            first: 25,
            filter: {{ cityId: "1", categoryId: "{category_id}", leased: {str(leased).lower()} }},
            sort: BUMPED_AT_DESC{after}
        ) {{
            totalCount
            pageInfo {{ hasNextPage endCursor }}
            edges {{
                node {{
                    id
                    price {{ total }}
                    rooms
                    area {{ value }}
                    floor floors
                    location {{ id name fullName }}
                    hasRepair hasBillOfSale hasMortgage
                    isBusiness isFeatured
                    updatedAt
                    preview {{ f460x345 }}
                    path
                }}
            }}
        }}
    }}"""
    try:
        data = await page.evaluate(
            """async (query) => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 20000);
            try {
                const r = await fetch('https://bina.az/graphql', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query }),
                    signal: controller.signal,
                });
                return r.json();
            } finally { clearTimeout(timer); }
        }""",
            query,
        )
        conn = (data.get("data") or {}).get("itemsConnection") or {}
        edges = conn.get("edges") or []
        page_info = conn.get("pageInfo") or {}
        return (
            edges,
            page_info.get("endCursor"),
            page_info.get("hasNextPage", False),
            conn.get("totalCount", 0),
        )
    except Exception:
        return [], None, False, 0


async def fetch_item_graphql(page, item_id: str) -> dict:
    """Fetch full listing details for a new listing. Returns {} on any error."""
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
