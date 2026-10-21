"""
Backfill land_area_sot for land listings that are missing it (broken since Oct 6
when the GraphQL migration stopped returning landArea from the item detail API).

Strategy per listing:
  1. Try fetch_item_graphql — fast, no page load needed.
  2. If still null, fetch the listing page HTML and extract "X sot" from the DOM.

Safe to re-run: only rewrites files that have at least one update.

Usage:
    python3 scripts/backfill_land_area_sot.py
    python3 scripts/backfill_land_area_sot.py --dry-run   # print counts, no writes
"""
import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scraper.browser import fetch_item_graphql, open_browser, warmup

DATA_DIR = ROOT / "data"
DRY_RUN = "--dry-run" in sys.argv
GQL_BATCH = 20
PAGE_BATCH = 5  # concurrent page fetches for HTML fallback


def _json_loads(s):
    try:
        import orjson
        return orjson.loads(s)
    except ImportError:
        return json.loads(s)


def _json_dumps(obj):
    try:
        import orjson
        return orjson.dumps(obj, option=orjson.OPT_NON_STR_KEYS).decode()
    except ImportError:
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def load_affected() -> tuple[dict[str, dict], dict[str, str]]:
    """Returns {id: listing} and {id: filename} for active land_sale listings missing sot."""
    listings: dict[str, dict] = {}
    file_map: dict[str, str] = {}
    for path in sorted(DATA_DIR.glob("land_sale_*.json")):
        for l in _json_loads(path.read_text(encoding="utf-8")):
            listings[l["id"]] = l
            file_map[l["id"]] = path.name

    affected_ids = {
        lid for lid, l in listings.items()
        if l.get("land_area_sot") is None and not l.get("deleted_at")
    }
    return {lid: listings[lid] for lid in affected_ids}, {lid: file_map[lid] for lid in affected_ids}


async def fetch_sot_from_page(page, url: str) -> float | None:
    """Fetch listing page and extract land area in sot from page text."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        text = await page.evaluate("() => document.body.innerText")
        for line in text.splitlines():
            line = line.strip()
            if "sot" in line.lower():
                m = re.search(r"([\d.,]+)\s*sot", line, re.IGNORECASE)
                if m:
                    return float(m.group(1).replace(",", "."))
    except Exception as e:
        print(f"  page fetch failed for {url}: {e}")
    return None


async def main() -> None:
    affected, file_map = load_affected()
    print(f"Affected listings: {len(affected)}")
    if not affected:
        print("Nothing to backfill.")
        return

    if DRY_RUN:
        print("Dry run — no writes.")
        return

    resolved: dict[str, float] = {}  # id → sot value

    async with open_browser(headless=True) as browser:
        page = await browser.new_page()
        await warmup(page)

        # ── Pass 1: GraphQL item detail ───────────────────────────────────────
        ids = list(affected)
        print(f"\nPass 1: GraphQL detail for {len(ids)} listings…")
        for i in range(0, len(ids), GQL_BATCH):
            batch = ids[i:i + GQL_BATCH]
            print(f"  {min(i + GQL_BATCH, len(ids))}/{len(ids)}", end="\r", flush=True)
            results = await asyncio.gather(*[fetch_item_graphql(page, lid) for lid in batch])
            for lid, gql in zip(batch, results):
                sot = (gql or {}).get("land_area_sot")
                if sot is not None:
                    resolved[lid] = sot
        print(f"\n  resolved via GraphQL: {len(resolved)}")

        # ── Pass 2: HTML page fallback for remaining ──────────────────────────
        remaining = [lid for lid in ids if lid not in resolved]
        print(f"\nPass 2: HTML page fetch for {len(remaining)} listings…")
        sem = asyncio.Semaphore(PAGE_BATCH)

        async def fetch_one(lid: str) -> tuple[str, float | None]:
            async with sem:
                url = affected[lid]["url"]
                sot = await fetch_sot_from_page(page, url)
                return lid, sot

        tasks = [fetch_one(lid) for lid in remaining]
        for done, coro in enumerate(asyncio.as_completed(tasks), 1):
            lid, sot = await coro
            print(f"  {done}/{len(remaining)}", end="\r", flush=True)
            if sot is not None:
                resolved[lid] = sot

        print(f"\n  resolved via HTML: {len(resolved) - (len(ids) - len(remaining))}")

    print(f"\nTotal resolved: {len(resolved)}/{len(affected)}")
    if not resolved:
        print("Nothing to write.")
        return

    # ── Write back to source files ────────────────────────────────────────────
    by_file: dict[str, list[str]] = defaultdict(list)
    for lid in resolved:
        by_file[file_map[lid]].append(lid)

    for filename, lids in by_file.items():
        path = DATA_DIR / filename
        listings = _json_loads(path.read_text(encoding="utf-8"))
        by_id = {l["id"]: l for l in listings}
        for lid in lids:
            by_id[lid]["land_area_sot"] = resolved[lid]
        output = _json_dumps(list(by_id.values()))
        output = output.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        path.write_text(output, encoding="utf-8")
        print(f"  wrote {filename} ({len(lids)} updated)")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
