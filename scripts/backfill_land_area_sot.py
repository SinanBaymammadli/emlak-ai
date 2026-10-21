"""
Backfill land_area_sot for land listings that are missing it.

For land listings the bina.az GraphQL API returns the area in sot via
area{value} (the same field used for m² in other categories). Since Oct 6
parse_es_node was storing that value in area_m2 instead of land_area_sot.
This script copies area_m2 → land_area_sot for all affected land listings.

Safe to re-run: only rewrites files that have at least one update.

Usage:
    python3 scripts/backfill_land_area_sot.py
    python3 scripts/backfill_land_area_sot.py --dry-run
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DRY_RUN = "--dry-run" in sys.argv


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


def main() -> None:
    files = sorted(DATA_DIR.glob("land_sale_*.json"))
    total_updated = 0
    files_written = 0

    for path in files:
        listings = _json_loads(path.read_text(encoding="utf-8"))
        updated = 0
        for l in listings:
            if l.get("land_area_sot") is None and l.get("area_m2") is not None:
                l["land_area_sot"] = l["area_m2"]
                l["area_m2"] = None
                updated += 1
        if updated:
            total_updated += updated
            print(f"  {path.name}: {updated} updated")
            if not DRY_RUN:
                output = _json_dumps(listings)
                output = output.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
                path.write_text(output, encoding="utf-8")
                files_written += 1

    print(f"\nTotal: {total_updated} listings updated across {files_written} files" if not DRY_RUN
          else f"\nDry run: would update {total_updated} listings")


if __name__ == "__main__":
    main()
