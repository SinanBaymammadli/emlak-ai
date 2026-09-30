"""
Entry point: scrape all bina.az categories → persist to SQLite → export JSON.
"""
import asyncio
import json
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from scraper.browser import (
    extract_cards,
    fetch_item_graphql,
    load_category_page,
    open_browser,
    scroll_load_all,
)
from scraper.categories import CATEGORIES
from scraper.db import (
    finish_scrape_run,
    init_db,
    mark_deleted,
    start_scrape_run,
    upsert_listing,
)
from scraper.parser import PARSERS

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/emlak.db")
DATA_DIR = Path("data")


async def scrape_category(page, conn: sqlite3.Connection, cfg: dict) -> dict:
    category = cfg["category"]
    deal_type = cfg["deal_type"]
    url = cfg["url"]

    print(f"\n→ {category} / {deal_type}")
    run_id = start_scrape_run(conn, category, deal_type)

    try:
        total = await load_category_page(page, url)
        print(f"  total on site: {total}")
        await scroll_load_all(page)
        raw_cards = await extract_cards(page)
        print(f"  cards extracted: {len(raw_cards)}")

        parser = PARSERS.get(category, PARSERS["apartment"])
        seen_ids: set[str] = set()
        counts = {"new": 0, "updated": 0, "unchanged": 0}

        for card in raw_cards:
            item_id = card["id"]
            seen_ids.add(item_id)

            parsed = parser(card["text"])
            gql = await fetch_item_graphql(page, item_id)

            listing = {
                "id": item_id,
                "photo_url": card.get("photo_url"),
                **parsed,
                "lat": gql.get("lat"),
                "lng": gql.get("lng"),
                "has_repair": gql.get("has_repair"),
            }
            # GraphQL area overrides card text when available
            if gql.get("area_m2_gql") and not listing.get("area_m2"):
                listing["area_m2"] = gql["area_m2_gql"]
            if gql.get("land_area_sot") and not listing.get("land_area_sot"):
                listing["land_area_sot"] = gql["land_area_sot"]

            result = upsert_listing(conn, listing, category, deal_type)
            counts[result] += 1

        deleted = mark_deleted(conn, seen_ids, category, deal_type)
        finish_scrape_run(
            conn,
            run_id,
            found=len(raw_cards),
            new=counts["new"],
            updated=counts["updated"],
            deleted=deleted,
        )
        print(f"  new={counts['new']} updated={counts['updated']} deleted={deleted}")
        return counts

    except Exception as exc:
        conn.execute(
            "UPDATE scrape_runs SET status='error', finished_at=datetime('now') WHERE id=?",
            (run_id,),
        )
        conn.commit()
        print(f"  ERROR: {exc}")
        raise


def export_json(conn: sqlite3.Connection) -> None:
    """Export one JSON file per category+deal_type, with price_history embedded per listing.

    All listings are included (active and deleted). Deleted ones carry a non-null deleted_at.
    Output files: data/{category}_{deal_type}.json  e.g. data/apartment_sale.json
    """
    DATA_DIR.mkdir(exist_ok=True)

    listing_cols = [d[0] for d in conn.execute("SELECT * FROM listings LIMIT 0").description]

    # Build price history lookup: listing_id → sorted list of {price, date}
    history_lookup: dict[str, list[dict]] = {}
    for listing_id, price, observed_at in conn.execute(
        "SELECT listing_id, price, observed_at FROM price_history ORDER BY observed_at ASC"
    ):
        history_lookup.setdefault(listing_id, []).append(
            {"price": price, "date": observed_at}
        )

    # Group listings by category + deal_type
    groups: dict[str, list[dict]] = {}
    for row in conn.execute("SELECT * FROM listings ORDER BY last_seen_at DESC"):
        listing = dict(zip(listing_cols, row))
        listing["price_history"] = history_lookup.get(listing["id"], [])
        key = f"{listing['category']}_{listing['deal_type']}"
        groups.setdefault(key, []).append(listing)

    for key, listings in groups.items():
        path = DATA_DIR / f"{key}.json"
        path.write_text(json.dumps(listings, ensure_ascii=False, indent=2))
        active = sum(1 for l in listings if l["deleted_at"] is None)
        print(f"  Exported {active} active + {len(listings)-active} deleted → data/{key}.json")


async def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    async with open_browser(headless=False) as browser:
        page = await browser.new_page()
        for cfg in CATEGORIES:
            try:
                await scrape_category(page, conn, cfg)
            except Exception:
                print(f"  Skipping {cfg['category']}/{cfg['deal_type']} due to error")
                continue

    export_json(conn)
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
