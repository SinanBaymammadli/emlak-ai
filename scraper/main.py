"""
Scraper entry point — uses bina.az GraphQL API exclusively.

Per run, for each category:
  1. Paginate itemsConnection (all listings, sorted by bumped_at desc)
  2. Upsert every listing — tracks price + field changes
  3. Fetch item(id) details (lat/lng, title, description, etc.) for new listings only
  4. Mark listings absent from the full page set as deleted
"""
import asyncio
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from scraper.browser import (
    _save_debug_snapshot,
    fetch_item_graphql,
    fetch_items_page,
    open_browser,
    warmup,
)
from scraper.categories import CATEGORIES

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
SCRAPE_LIMIT = int(os.getenv("SCRAPE_LIMIT", "0")) or None
CONCURRENCY = int(os.getenv("SCRAPER_CONCURRENCY", str(len(CATEGORIES))))

CATEGORY_IDS = {
    "apartment": "1",
    "house":     "5",
    "commercial":"10",
    "office":    "7",
    "garage":    "8",
    "land":      "9",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_stem(category: str, deal_type: str) -> str:
    return f"{category}_{deal_type}"


try:
    import orjson as _orjson
    def _json_loads(s): return _orjson.loads(s)
    def _json_dumps(obj): return _orjson.dumps(obj, option=_orjson.OPT_INDENT_2 | _orjson.OPT_NON_STR_KEYS).decode()
except ImportError:
    def _json_loads(s): return json.loads(s)
    def _json_dumps(obj): return json.dumps(obj, ensure_ascii=False, indent=2)


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


_DATED_GLOB = "_20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"


def load_existing(category: str, deal_type: str) -> tuple[dict[str, dict], dict[str, str]]:
    stem = _file_stem(category, deal_type)
    listings: dict[str, dict] = {}
    file_map: dict[str, str] = {}
    for path in sorted(DATA_DIR.glob(f"{stem}{_DATED_GLOB}")):
        for l in _json_loads(path.read_text(encoding="utf-8")):
            listings[l["id"]] = l
            file_map[l["id"]] = path.name
    return listings, file_map


def _update_manifest(stem: str, filenames: set[str]) -> None:
    manifest_path = DATA_DIR / "manifest.json"
    try:
        manifest = _json_loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    except Exception:
        manifest = {}
    existing_dates = set(manifest.get(stem, []))
    for name in filenames:
        # extract date from e.g. "apartment_sale_2026-10-06.json"
        suffix = name[len(stem) + 1:-5]  # strip "{stem}_" prefix and ".json" suffix
        if len(suffix) == 10:
            existing_dates.add(suffix)
    manifest[stem] = sorted(existing_dates)
    output = _json_dumps(manifest)
    manifest_path.write_text(output, encoding="utf-8")


def save_listings(
    category: str,
    deal_type: str,
    existing: dict[str, dict],
    file_map: dict[str, str],
    dirty_ids: set[str],
    today_filename: str,
) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    stem = _file_stem(category, deal_type)

    dirty_files = {file_map.get(id_, today_filename) for id_ in dirty_ids}
    if not dirty_files:
        return

    # group all listings by their source file
    by_file: dict[str, list] = defaultdict(list)
    for id_, listing in existing.items():
        by_file[file_map.get(id_, today_filename)].append(listing)

    for filename in dirty_files:
        path = DATA_DIR / filename
        sorted_listings = sorted(
            by_file.get(filename, []),
            key=lambda l: (l["deleted_at"] is not None, l.get("updated_at_site") or ""),
        )
        output = _json_dumps(sorted_listings)
        output = output.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        path.write_text(output, encoding="utf-8")

    _update_manifest(stem, dirty_files)


# ── ESItem parsing ────────────────────────────────────────────────────────────

def parse_es_node(node: dict, category: str, deal_type: str) -> dict:
    rooms = node.get("rooms")
    area = (node.get("area") or {}).get("value")
    floor_n = node.get("floor")
    floors_n = node.get("floors")
    loc = node.get("location") or {}
    return {
        "id": node["id"],
        "photo_url": (node.get("preview") or {}).get("f460x345"),
        "price": (node.get("price") or {}).get("total"),
        "location": loc.get("fullName") or loc.get("name") or "",
        "location_id": loc.get("id"),
        "location_name": loc.get("name"),
        "rooms": f"{rooms} otaqlı" if rooms else None,
        "area_m2": area,
        "floor": f"{floor_n}/{floors_n} mərtəbə" if floor_n and floors_n else None,
        "floor_number": floor_n,
        "is_agency": node.get("isBusiness"),
        "has_repair": node.get("hasRepair"),
        "has_bill_of_sale": node.get("hasBillOfSale"),
        "has_mortgage": node.get("hasMortgage"),
        "is_featured": node.get("isFeatured"),
        "updated_at_site": node.get("updatedAt"),
        "category": category,
        "deal_type": deal_type,
        "url": f"https://bina.az{node['path']}",
    }


# ── Upsert ────────────────────────────────────────────────────────────────────

# Fields refreshed on every scrape from itemsConnection
_ES_FIELDS = [
    "photo_url", "location", "location_id", "location_name",
    "rooms", "area_m2", "floor", "floor_number",
    "is_agency", "has_repair", "has_bill_of_sale", "has_mortgage",
    "is_featured", "updated_at_site",
]


def upsert(existing: dict[str, dict], listing: dict) -> str:
    """Upsert listing into existing dict. Returns 'new', 'updated', or 'unchanged'."""
    now = _now()
    item_id = listing["id"]

    if item_id not in existing:
        existing[item_id] = {
            **listing,
            "lat": None,
            "lng": None,
            "land_area_sot": None,
            "building_type": None,
            "title": None,
            "description": None,
            "deleted_at": None,
            "price_history": (
                [{"price": listing["price"], "date": now}]
                if listing.get("price") is not None else []
            ),
        }
        return "new"

    record = existing[item_id]

    if record.get("deleted_at"):
        record["deleted_at"] = None

    changed = False

    # Refresh fields from ESItem
    for field in _ES_FIELDS:
        new_val = listing.get(field)
        if new_val is not None and record.get(field) != new_val:
            record[field] = new_val
            changed = True

    # Price change tracking
    new_price = listing.get("price")
    if new_price is not None and new_price != record.get("price"):
        record["price"] = new_price
        record.setdefault("price_history", []).append({"price": new_price, "date": now})
        changed = True

    return "updated" if changed else "unchanged"


# ── Scrape category ───────────────────────────────────────────────────────────

async def scrape_category(page, cfg: dict) -> None:
    category = cfg["category"]
    deal_type = cfg["deal_type"]
    print(f"\n→ {category}/{deal_type}")

    existing, file_map = load_existing(category, deal_type)
    today_filename = f"{_file_stem(category, deal_type)}_{datetime.now(timezone.utc).date().isoformat()}.json"
    cat_id = CATEGORY_IDS[category]
    leased = deal_type == "rental"

    seen_ids: set[str] = set()
    new_ids: list[str] = []
    dirty_ids: set[str] = set()
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    cursor = None
    total_count = None
    page_num = 0
    all_pages_fetched = False

    while True:
        edges, next_cursor, has_next, total = await fetch_items_page(page, cat_id, leased, cursor)

        if total_count is None and total:
            total_count = total
            print(f"  total on site: {total_count}")

        if not edges:
            if page_num == 0:
                snap = await _save_debug_snapshot(page, f"blocked_{category}_{deal_type}")
                raise RuntimeError(
                    f"0 listings on first page — likely blocked. Snapshot: {snap}"
                )
            break

        for edge in edges:
            node = edge.get("node") or {}
            item_id = node.get("id")
            if not item_id:
                continue
            seen_ids.add(item_id)
            listing = parse_es_node(node, category, deal_type)
            result = upsert(existing, listing)
            counts[result] += 1
            if result == "new":
                new_ids.append(item_id)
                file_map[item_id] = today_filename
                dirty_ids.add(item_id)
            elif result == "updated":
                dirty_ids.add(item_id)

        page_num += 1
        total_str = f"/{total_count}" if total_count else ""
        print(
            f"  page {page_num}{total_str and f' ({len(seen_ids)}{total_str})'}"
            f"  new={counts['new']} updated={counts['updated']} unchanged={counts['unchanged']}",
            end="\r", flush=True,
        )

        if SCRAPE_LIMIT and len(seen_ids) >= SCRAPE_LIMIT:
            print()
            print(f"  limit={SCRAPE_LIMIT} reached")
            break

        if not has_next:
            all_pages_fetched = True
            break

        cursor = next_cursor

    print()  # end the \r line
    print(f"  pages={page_num}  seen={len(seen_ids)}")

    # Fetch full details for new listings (lat/lng, title, description, etc.)
    if new_ids:
        print(f"  fetching details for {len(new_ids)} new listings…")
        GQL_BATCH = 20
        for i in range(0, len(new_ids), GQL_BATCH):
            print(f"  details {i + GQL_BATCH}/{len(new_ids)}", end="\r", flush=True)
            batch = new_ids[i:i + GQL_BATCH]
            gql_results = await asyncio.gather(*[fetch_item_graphql(page, id_) for id_ in batch])
            for id_, gql in zip(batch, gql_results):
                if not gql or id_ not in existing:
                    continue
                r = existing[id_]
                for key, val in {
                    "lat": gql.get("lat"),
                    "lng": gql.get("lng"),
                    "land_area_sot": gql.get("land_area_sot"),
                    "building_type": gql.get("building_type"),
                    "title": gql.get("title"),
                    "description": gql.get("description"),
                }.items():
                    if val is not None:
                        r[key] = val
                if gql.get("area_m2_gql") and not r.get("area_m2"):
                    r["area_m2"] = gql["area_m2_gql"]

    # Deletion detection — only when we fetched every page
    if all_pages_fetched:
        deleted = 0
        for id_, record in existing.items():
            if id_ not in seen_ids and not record.get("deleted_at"):
                record["deleted_at"] = _now()
                dirty_ids.add(id_)
                deleted += 1
        if deleted:
            print(f"  marked {deleted} as deleted")

    save_listings(category, deal_type, existing, file_map, dirty_ids, today_filename)
    print(
        f"  new={counts['new']} updated={counts['updated']} "
        f"unchanged={counts['unchanged']} → saved {len(existing)} total"
    )


# ── Orchestration ─────────────────────────────────────────────────────────────

async def scrape_category_isolated(cfg: dict, sem: asyncio.Semaphore, errors: list) -> None:
    async with sem:
        try:
            async with open_browser(headless=True) as browser:
                page = await browser.new_page()
                await warmup(page)
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

    await asyncio.gather(
        *[scrape_category_isolated(cfg, sem, errors) for cfg in targets]
    )

    lines = ["✅ <b>emlak-ai scrape complete</b>"]
    manifest_path = DATA_DIR / "manifest.json"
    try:
        manifest = _json_loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    except Exception:
        manifest = {}
    for stem, dates in sorted(manifest.items()):
        total_active = 0
        for date_str in dates:
            path = DATA_DIR / f"{stem}_{date_str}.json"
            try:
                listings = _json_loads(path.read_text(encoding="utf-8"))
                total_active += sum(1 for l in listings if l.get("deleted_at") is None)
            except Exception:
                pass
        lines.append(f"  {stem}: {total_active} active")
    if errors:
        lines.append("\n⚠️ Errors:")
        lines.extend(f"  • {e}" for e in errors)

    telegram_notify("\n".join(lines))
    print("\nDone.")

    if errors:
        import sys
        sys.exit(1)


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
