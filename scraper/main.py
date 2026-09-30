"""
Entry point: scrape all bina.az categories → persist to per-category JSON files.

Each JSON file is both the persistent store and the output. On every run:
  1. Load existing JSON (if any) into memory keyed by listing ID
  2. Scrape fresh listings from bina.az
  3. Upsert in memory: new listings added, price changes appended to price_history,
     listings no longer on site get deleted_at set
  4. Save back to JSON — all listings including deleted ones are kept
"""
import asyncio
import json
import os
import urllib.request
from datetime import datetime, timezone
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
from scraper.parser import PARSERS

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
# Set SCRAPE_LIMIT=20 to test with first N listings per category (skips full scroll)
SCRAPE_LIMIT = int(os.getenv("SCRAPE_LIMIT", "0")) or None


def telegram_notify(text: str) -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        print(f"  Telegram notify failed: {exc}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_existing(category: str, deal_type: str) -> dict[str, dict]:
    path = DATA_DIR / f"{category}_{deal_type}.json"
    if not path.exists():
        return {}
    listings = json.loads(path.read_text(encoding="utf-8"))
    return {l["id"]: l for l in listings}


def save_listings(category: str, deal_type: str, listings: dict[str, dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{category}_{deal_type}.json"
    # Active listings first (deleted_at is None), then deleted; both sorted newest first
    sorted_listings = sorted(
        listings.values(),
        key=lambda l: (l["deleted_at"] is not None, l.get("last_seen_at", "")),
        reverse=False,
    )
    path.write_text(
        json.dumps(sorted_listings, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def upsert(
    existing: dict[str, dict], listing: dict, category: str, deal_type: str
) -> str:
    """Update existing dict in-place. Returns 'new', 'updated', or 'unchanged'."""
    now = _now()
    item_id = listing["id"]

    if item_id not in existing:
        existing[item_id] = {
            **listing,
            "category": category,
            "deal_type": deal_type,
            "url": f"https://bina.az/items/{item_id}",
            "first_seen_at": now,
            "last_seen_at": now,
            "deleted_at": None,
            "price_history": (
                [{"price": listing["price"], "date": now}]
                if listing.get("price") is not None
                else []
            ),
        }
        return "new"

    record = existing[item_id]

    # Resurrect listing if it was previously deleted
    if record.get("deleted_at"):
        record["deleted_at"] = None

    old_price = record.get("price")
    new_price = listing.get("price")

    if new_price != old_price:
        record.update({**listing, "last_seen_at": now})
        if new_price is not None:
            record.setdefault("price_history", []).append(
                {"price": new_price, "date": now}
            )
        return "updated"

    record["last_seen_at"] = now
    return "unchanged"


def mark_deleted(existing: dict[str, dict], seen_ids: set[str]) -> int:
    now = _now()
    count = 0
    for item_id, record in existing.items():
        if item_id not in seen_ids and record.get("deleted_at") is None:
            record["deleted_at"] = now
            count += 1
    return count


async def scrape_category(page, cfg: dict) -> None:
    category = cfg["category"]
    deal_type = cfg["deal_type"]
    url = cfg["url"]

    print(f"\n→ {category} / {deal_type}")

    existing = load_existing(category, deal_type)

    total = await load_category_page(page, url)
    print(f"  total on site: {total}")
    if SCRAPE_LIMIT:
        print(f"  limit={SCRAPE_LIMIT} (test mode — skipping full scroll)")
    else:
        await scroll_load_all(page)
    raw_cards = await extract_cards(page)
    if SCRAPE_LIMIT:
        raw_cards = raw_cards[:SCRAPE_LIMIT]
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
        if gql.get("area_m2_gql") and not listing.get("area_m2"):
            listing["area_m2"] = gql["area_m2_gql"]
        if gql.get("land_area_sot") and not listing.get("land_area_sot"):
            listing["land_area_sot"] = gql["land_area_sot"]

        result = upsert(existing, listing, category, deal_type)
        counts[result] += 1

    deleted = mark_deleted(existing, seen_ids)
    save_listings(category, deal_type, existing)

    print(
        f"  new={counts['new']} updated={counts['updated']} "
        f"unchanged={counts['unchanged']} deleted={deleted} "
        f"→ saved {len(existing)} total"
    )


async def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    errors: list[str] = []

    try:
        async with open_browser(headless=False) as browser:
            page = await browser.new_page()
            for cfg in CATEGORIES:
                try:
                    await scrape_category(page, cfg)
                except Exception as exc:
                    msg = f"{cfg['category']}/{cfg['deal_type']}: {exc}"
                    print(f"  ERROR {msg}")
                    errors.append(msg)
                    continue
    except Exception as exc:
        telegram_notify(f"❌ <b>emlak-ai scrape failed</b>\n{exc}")
        raise

    # Build summary for Telegram
    lines = ["✅ <b>emlak-ai scrape complete</b>"]
    for f in sorted(DATA_DIR.glob("*.json")):
        try:
            listings = json.loads(f.read_text(encoding="utf-8"))
            active = sum(1 for l in listings if l.get("deleted_at") is None)
            lines.append(f"  {f.stem}: {active} active")
        except Exception:
            pass
    if errors:
        lines.append("\n⚠️ Errors:")
        lines.extend(f"  • {e}" for e in errors)

    telegram_notify("\n".join(lines))
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
