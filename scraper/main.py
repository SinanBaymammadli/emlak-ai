"""
Entry point: scrape today's bina.az listings → persist to per-category JSON files.

Each JSON file is both the persistent store and the output. On every run:
  1. Load existing JSON (if any) into memory keyed by listing ID
  2. Scrape fresh listings from bina.az, stopping once past today's listings
  3. Upsert only listings updated today: new listings added, price changes appended
     to price_history, listings no longer on site get deleted_at set
  4. Save back to JSON — all listings including deleted ones are kept
"""
import asyncio
import json
import os
try:
    import orjson as _orjson
    def _json_loads(s): return _orjson.loads(s)
    def _json_dumps(obj): return _orjson.dumps(obj, option=_orjson.OPT_INDENT_2 | _orjson.OPT_NON_STR_KEYS).decode()
except ImportError:
    def _json_loads(s): return json.loads(s)
    def _json_dumps(obj): return json.dumps(obj, ensure_ascii=False, indent=2)
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

from scraper.browser import (
    extract_cards,
    fetch_item_graphql,
    load_category_page,
    open_browser,
    scroll_and_extract,
)
from scraper.categories import CATEGORIES
from scraper.parser import PARSERS

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
# Set SCRAPE_LIMIT=20 to test with first N listings per category (skips full scroll)
SCRAPE_LIMIT = int(os.getenv("SCRAPE_LIMIT", "0")) or None
# How many categories to scrape simultaneously (each gets its own browser)
CONCURRENCY = int(os.getenv("SCRAPER_CONCURRENCY", str(len(CATEGORIES))))


def _is_recent(text: str) -> bool:
    t = text.lower()
    return "bugün" in t or "bu gün" in t or "dünən" in t


def make_recent_stop_check(threshold: int = 20):
    """Stop scrolling once the last `threshold` cards contain no today/yesterday listings,
    but only after we've seen at least one recent listing (avoids stopping before
    recent listings have even loaded)."""
    def check(all_cards: list[dict]) -> bool:
        if len(all_cards) < threshold:
            return False
        if not any(_is_recent(c["text"]) for c in all_cards):
            return False
        tail = all_cards[-threshold:]
        if not any(_is_recent(c["text"]) for c in tail):
            print(f"  no recent listings in last {threshold} cards → stopping")
            return True
        return False
    return check


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


def _file_stem(category: str, deal_type: str) -> str:
    return f"{category}_{deal_type}"


def load_existing(category: str, deal_type: str) -> dict[str, dict]:
    path = DATA_DIR / f"{_file_stem(category, deal_type)}.json"
    if not path.exists():
        return {}
    listings = _json_loads(path.read_text(encoding="utf-8"))
    return {l["id"]: l for l in listings}


def save_listings(category: str, deal_type: str, listings: dict[str, dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{_file_stem(category, deal_type)}.json"
    sorted_listings = sorted(
        listings.values(),
        key=lambda l: (l["deleted_at"] is not None, l.get("updated_at_site") or ""),
        reverse=False,
    )
    output = _json_dumps(sorted_listings)
    output = output.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    path.write_text(output, encoding="utf-8")


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
            "deleted_at": None,
            "price_history": (
                [{"price": listing["price"], "date": now}]
                if listing.get("price") is not None
                else []
            ),
        }
        return "new"

    record = existing[item_id]

    if record.get("deleted_at"):
        record["deleted_at"] = None

    old_price = record.get("price")
    new_price = listing.get("price")

    if new_price != old_price:
        record.update(listing)
        if new_price is not None:
            record.setdefault("price_history", []).append(
                {"price": new_price, "date": now}
            )
        return "updated"

    return "unchanged"



async def scrape_category(page, cfg: dict) -> None:
    category = cfg["category"]
    deal_type = cfg["deal_type"]
    url = cfg["url"]
    print(f"\n→ {category}/{deal_type}")

    existing = load_existing(category, deal_type)
    parser = PARSERS.get(category, PARSERS["apartment"])

    total = await load_category_page(page, url)
    print(f"  total on site: {total}")
    if SCRAPE_LIMIT:
        print(f"  limit={SCRAPE_LIMIT} (test mode — skipping full scroll)")
        raw_cards = await extract_cards(page)
        raw_cards = raw_cards[:SCRAPE_LIMIT]
    else:
        raw_cards = await scroll_and_extract(
            page, target=total, stop_check=make_recent_stop_check()
        )
    recent_cards = [c for c in raw_cards if _is_recent(c["text"])]
    print(f"  cards extracted: {len(raw_cards)}  recent: {len(recent_cards)}")

    # Split: new listings need GQL; known listings skip GQL unless price changed
    new_cards = [c for c in recent_cards if c["id"] not in existing]
    known_cards = [c for c in recent_cards if c["id"] in existing]
    price_changed_cards = [
        c for c in known_cards
        if parser(c["text"]).get("price") != existing[c["id"]].get("price")
    ]
    gql_cards = new_cards + price_changed_cards

    GQL_BATCH = 20
    gql_results: list[dict] = []
    for i in range(0, len(gql_cards), GQL_BATCH):
        batch = gql_cards[i:i + GQL_BATCH]
        batch_gql = await asyncio.gather(*[fetch_item_graphql(page, c["id"]) for c in batch])
        gql_results.extend(batch_gql)

    gql_map = {card["id"]: gql for card, gql in zip(gql_cards, gql_results)}
    counts = {"new": 0, "updated": 0, "unchanged": 0}

    for card in recent_cards:
        item_id = card["id"]
        parsed = parser(card["text"])
        gql = gql_map.get(item_id, {})
        listing = {
            "id": item_id,
            "photo_url": card.get("photo_url"),
            **parsed,
            "lat": gql.get("lat"),
            "lng": gql.get("lng"),
            "has_repair": gql.get("has_repair"),
            "has_bill_of_sale": gql.get("has_bill_of_sale"),
            "has_mortgage": gql.get("has_mortgage"),
            "floor_number": gql.get("floor_number"),
            "updated_at_site": gql.get("updated_at_site"),
            "is_featured": gql.get("is_featured"),
            "title": gql.get("title"),
            "description": gql.get("description"),
            "building_type": gql.get("building_type"),
            "location_id": gql.get("location_id"),
            "location_name": gql.get("location_name"),
        }
        if gql.get("area_m2_gql") and not listing.get("area_m2"):
            listing["area_m2"] = gql["area_m2_gql"]
        if gql.get("land_area_sot") and not listing.get("land_area_sot"):
            listing["land_area_sot"] = gql["land_area_sot"]

        result = upsert(existing, listing, category, deal_type)
        counts[result] += 1

    save_listings(category, deal_type, existing)

    print(
        f"  new={counts['new']} updated={counts['updated']} "
        f"unchanged={counts['unchanged']} → saved {len(existing)} total"
    )


async def scrape_category_isolated(cfg: dict, sem: asyncio.Semaphore, errors: list) -> None:
    """Open a dedicated browser for one category, scrape it, then close."""
    async with sem:
        try:
            async with open_browser(headless=False) as browser:
                page = await browser.new_page()
                await scrape_category(page, cfg)
        except Exception as exc:
            msg = f"{cfg['category']}/{cfg['deal_type']}: {exc}"
            print(f"  ERROR {msg}")
            errors.append(msg)


async def main(categories: list | None = None) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    errors: list[str] = []
    targets = categories or CATEGORIES

    print(f"Scraping {len(targets)} categories with concurrency={min(CONCURRENCY, len(targets))}")
    sem = asyncio.Semaphore(min(CONCURRENCY, len(targets)))

    try:
        await asyncio.gather(
            *[scrape_category_isolated(cfg, sem, errors) for cfg in targets]
        )
    except Exception as exc:
        telegram_notify(f"❌ <b>emlak-ai scrape failed</b>\n{exc}")
        raise

    lines = ["✅ <b>emlak-ai scrape complete</b>"]
    for f in sorted(DATA_DIR.glob("*.json")):
        try:
            listings = _json_loads(f.read_text(encoding="utf-8"))
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
    import sys

    def _cfg_key(c: dict) -> str:
        return f"{c['category']}_{c['deal_type']}"

    if len(sys.argv) > 1:
        keys = set(sys.argv[1:])
        valid = {_cfg_key(c) for c in CATEGORIES}
        unknown = keys - valid
        if unknown:
            print(f"Unknown: {unknown}")
            print(f"Valid: {sorted(valid)}")
            sys.exit(1)
        selected = [c for c in CATEGORIES if _cfg_key(c) in keys]
        asyncio.run(main(selected))
    else:
        asyncio.run(main())
