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
try:
    import orjson as _orjson
    def _json_loads(s): return _orjson.loads(s)
    def _json_dumps(obj): return _orjson.dumps(obj, option=_orjson.OPT_INDENT_2 | _orjson.OPT_NON_STR_KEYS).decode()
except ImportError:
    def _json_loads(s): return json.loads(s)
    def _json_dumps(obj): return json.dumps(obj, ensure_ascii=False, indent=2)
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from scraper.browser import (
    extract_cards,
    fetch_item_graphql,
    load_category_page,
    open_browser,
    scroll_and_extract,
)
from scraper.categories import CATEGORIES, MERGE_TARGETS
from scraper.parser import PARSERS

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
# Set SCRAPE_LIMIT=20 to test with first N listings per category (skips full scroll)
SCRAPE_LIMIT = int(os.getenv("SCRAPE_LIMIT", "0")) or None
# How many categories to scrape simultaneously (each gets its own browser)
# Defaults to all categories at once; lower if machine runs out of RAM
CONCURRENCY = int(os.getenv("SCRAPER_CONCURRENCY", str(len(CATEGORIES))))


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


def _room_label(room: str) -> str:
    """Extract just the leading digit from a room string: '5%2B' → '5', '3' → '3'."""
    import re
    m = re.match(r"(\d+)", room)
    return m.group(1) if m else room


def _file_stem(category: str, deal_type: str, room: str | None = None, building: str | None = None, kupca: bool | None = None, price_band: str | None = None) -> str:
    parts = [category, deal_type]
    if building:
        parts.append(building)
    if kupca is True:
        parts.append("kupca")
    elif kupca is False:
        parts.append("nokupca")
    if room:
        parts.append(_room_label(room))
    if price_band:
        parts.append(price_band)
    return "_".join(parts)


def load_existing(category: str, deal_type: str, room: str | None = None, building: str | None = None, kupca: bool | None = None, price_band: str | None = None) -> dict[str, dict]:
    path = DATA_DIR / f"{_file_stem(category, deal_type, room, building, kupca, price_band)}.json"
    if not path.exists():
        return {}
    listings = _json_loads(path.read_text(encoding="utf-8"))
    return {l["id"]: l for l in listings}


def save_listings(category: str, deal_type: str, listings: dict[str, dict], room: str | None = None, building: str | None = None, kupca: bool | None = None, price_band: str | None = None) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{_file_stem(category, deal_type, room, building, kupca, price_band)}.json"
    sorted_listings = sorted(
        listings.values(),
        key=lambda l: (l["deleted_at"] is not None, l.get("updated_at_site", "")),
        reverse=False,
    )
    # Escape U+2028 / U+2029 — Python's json module leaves them unescaped but
    # they are invalid unescaped inside JSON strings per the spec.
    output = _json_dumps(sorted_listings)
    output = output.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    path.write_text(output, encoding="utf-8")


def merge_room_files(category: str, deal_type: str) -> None:
    """Merge all sub-files into the combined category file, deduped by listing ID."""
    from scraper.categories import _ROOMS, _BUILDING_TYPES, _KUPCA, _PRICE_BANDS, _PRICE_SPLIT_ROOMS
    merged: dict[str, dict] = {}

    buildings: list[str | None] = [None]
    kupca_list: list[bool | None] = [None]
    use_price_bands = False

    if category == "apartment":
        buildings = [b.replace("-tikili", "") for b in _BUILDING_TYPES]
        if deal_type == "sale":
            kupca_list = _KUPCA
            use_price_bands = True

    for building in buildings:
        for kupca in kupca_list:
            for room in _ROOMS:
                bands: list[str | None] = [b[0] for b in _PRICE_BANDS] if (use_price_bands and room in _PRICE_SPLIT_ROOMS) else [None]
                for price_band in bands:
                    path = DATA_DIR / f"{_file_stem(category, deal_type, room, building, kupca, price_band)}.json"
                    if not path.exists():
                        continue
                    for listing in _json_loads(path.read_text(encoding="utf-8")):
                        lid = listing["id"]
                        if lid not in merged or (listing.get("updated_at_site", "")) > (merged[lid].get("updated_at_site", "")):
                            merged[lid] = listing

    if merged:
        save_listings(category, deal_type, merged)
        active = sum(1 for l in merged.values() if not l.get("deleted_at"))
        print(f"  merged {len(merged)} listings ({active} active) → {category}_{deal_type}.json")


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

    # Resurrect listing if it was previously deleted
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


def make_stop_check(existing: dict[str, dict], parser, threshold: int = 50):
    """Returns a callback for scroll_and_extract that stops once the last
    `threshold` extracted cards are all known listings with unchanged prices.
    bina.az is sorted newest-first, so reaching this point means we've scrolled
    past all new/changed content.
    """
    def check(all_cards: list[dict]) -> bool:
        if len(all_cards) < threshold:
            return False
        tail = all_cards[-threshold:]
        known_unchanged = sum(
            1 for c in tail
            if (rec := existing.get(c["id"])) is not None
            and rec.get("price") == parser(c["text"]).get("price")
        )
        if known_unchanged >= threshold:
            print(f"  {threshold} consecutive known+unchanged → incremental stop")
            return True
        return False
    return check


def mark_deleted(existing: dict[str, dict], seen_ids: set[str], stale_days: int = 7) -> int:
    """Mark listings as deleted if not seen in this scrape AND not updated on bina.az
    for more than stale_days. This handles incremental scrapes where unseen IDs are
    simply listings we didn't reach (not necessarily removed from the site).
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=stale_days)).isoformat()
    count = 0
    for item_id, record in existing.items():
        if record.get("deleted_at") is not None:
            continue
        if item_id in seen_ids:
            continue
        # Only mark deleted if updated_at_site is older than cutoff (stale listing)
        updated = record.get("updated_at_site", "")
        if updated < cutoff:
            record["deleted_at"] = now.isoformat()
            count += 1
    return count


async def scrape_category(page, cfg: dict) -> None:
    category = cfg["category"]
    deal_type = cfg["deal_type"]
    url = cfg["url"]

    room = cfg.get("room")
    building = cfg.get("building")
    kupca = cfg.get("kupca")
    price_band = cfg.get("price_band")
    parts = [category, deal_type]
    if building: parts.append(building)
    if kupca is True: parts.append("kupca")
    elif kupca is False: parts.append("nokupca")
    if room: parts.append(f"{_room_label(room)}otaq")
    if price_band: parts.append(price_band)
    print(f"\n→ {'/'.join(parts)}")

    existing = load_existing(category, deal_type, room, building, kupca, price_band)

    total = await load_category_page(page, url)
    print(f"  total on site: {total}")
    if SCRAPE_LIMIT:
        print(f"  limit={SCRAPE_LIMIT} (test mode — skipping full scroll)")
        raw_cards = await extract_cards(page)
        raw_cards = raw_cards[:SCRAPE_LIMIT]
    else:
        # Use incremental stop when we have enough existing data (not a first-time full scrape)
        stop_fn = make_stop_check(existing, parser) if len(existing) >= 100 else None
        raw_cards = await scroll_and_extract(page, target=total, stop_check=stop_fn)
    print(f"  cards extracted: {len(raw_cards)}")

    parser = PARSERS.get(category, PARSERS["apartment"])
    seen_ids: set[str] = set()
    counts = {"new": 0, "updated": 0, "unchanged": 0}

    # Fetch all GraphQL data concurrently in batches of 20
    GQL_BATCH = 20
    gql_results: list[dict] = []
    for i in range(0, len(raw_cards), GQL_BATCH):
        batch = raw_cards[i:i + GQL_BATCH]
        batch_gql = await asyncio.gather(*[fetch_item_graphql(page, c["id"]) for c in batch])
        gql_results.extend(batch_gql)

    for card, gql in zip(raw_cards, gql_results):
        item_id = card["id"]
        seen_ids.add(item_id)

        parsed = parser(card["text"])
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

    deleted = mark_deleted(existing, seen_ids)
    save_listings(category, deal_type, existing, room, building, kupca, price_band)

    print(
        f"  new={counts['new']} updated={counts['updated']} "
        f"unchanged={counts['unchanged']} deleted={deleted} "
        f"→ saved {len(existing)} total"
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

    # Build summary for Telegram
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

    # Merge room sub-files into combined category files
    print("\nMerging room sub-files…")
    for category, deal_type in MERGE_TARGETS:
        merge_room_files(category, deal_type)

    telegram_notify("\n".join(lines))
    print("\nDone.")


if __name__ == "__main__":
    import sys

    def _cfg_key(c: dict) -> str:
        parts = [c["category"], c["deal_type"]]
        if c.get("building"): parts.append(c["building"])
        if c.get("kupca") is True: parts.append("kupca")
        elif c.get("kupca") is False: parts.append("nokupca")
        if c.get("room"): parts.append(_room_label(c["room"]))
        if c.get("price_band"): parts.append(c["price_band"])
        return "_".join(parts)

    if len(sys.argv) > 1:
        keys = set(sys.argv[1:])
        valid = {_cfg_key(c) for c in CATEGORIES} | {f"{c['category']}_{c['deal_type']}" for c in CATEGORIES}
        unknown = keys - valid
        if unknown:
            print(f"Unknown: {unknown}")
            print(f"Valid: {sorted(valid)}")
            sys.exit(1)
        # Match by full key (e.g. apartment_sale_1room) or base (e.g. apartment_sale → all rooms)
        selected = [c for c in CATEGORIES if _cfg_key(c) in keys or f"{c['category']}_{c['deal_type']}" in keys]
        asyncio.run(main(selected))
    else:
        asyncio.run(main())
