"""
One-time migration: split monolithic data/{stem}.json files into dated incremental files.

Each listing is placed in data/{stem}_{YYYY-MM-DD}.json based on its first price_history date.
Listings with no date fall back to "2026-01-01".

Run from project root:
    python scripts/migrate_to_dated.py

The original monolithic files are NOT deleted; verify results before removing them manually.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("data")

try:
    import orjson as _orjson
    def _loads(s): return _orjson.loads(s)
    def _dumps(obj): return _orjson.dumps(obj, option=_orjson.OPT_INDENT_2 | _orjson.OPT_NON_STR_KEYS).decode()
except ImportError:
    def _loads(s): return json.loads(s)
    def _dumps(obj): return json.dumps(obj, ensure_ascii=False, indent=2)

DATED_RE = re.compile(r"_20\d{2}-\d{2}-\d{2}\.json$")
FALLBACK_DATE = "2026-01-01"


def first_seen_date(listing: dict) -> str:
    history = listing.get("price_history") or []
    if history:
        date_str = (history[0].get("date") or "")[:10]
        if len(date_str) == 10:
            return date_str
    return FALLBACK_DATE


def sort_key(l):
    return (l["deleted_at"] is not None, l.get("updated_at_site") or "")


def main():
    if not DATA_DIR.exists():
        print(f"ERROR: {DATA_DIR} does not exist. Run from project root.")
        sys.exit(1)

    monolithic_files = [
        f for f in sorted(DATA_DIR.glob("*.json"))
        if f.name != "manifest.json" and not DATED_RE.search(f.name)
    ]

    if not monolithic_files:
        print("No monolithic files found. Already migrated?")
        return

    manifest: dict[str, list] = {}

    for src in monolithic_files:
        stem = src.stem
        print(f"\nMigrating {src.name} …")
        listings = _loads(src.read_text(encoding="utf-8"))
        if not isinstance(listings, list):
            print(f"  Skipping — not a list")
            continue

        by_date: dict[str, list] = defaultdict(list)
        for l in listings:
            by_date[first_seen_date(l)].append(l)

        written = 0
        dates_written: list[str] = []
        for date_str, group in sorted(by_date.items()):
            dest = DATA_DIR / f"{stem}_{date_str}.json"
            if dest.exists():
                print(f"  SKIP {dest.name} (already exists)")
                dates_written.append(date_str)
                continue
            sorted_group = sorted(group, key=sort_key)
            output = _dumps(sorted_group)
            output = output.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            dest.write_text(output, encoding="utf-8")
            print(f"  wrote {dest.name} ({len(group)} listings)")
            written += len(group)
            dates_written.append(date_str)

        manifest[stem] = sorted(set(dates_written))
        print(f"  total: {written} listings across {len(dates_written)} date files")

    # merge with existing manifest
    manifest_path = DATA_DIR / "manifest.json"
    existing_manifest: dict = {}
    if manifest_path.exists():
        try:
            existing_manifest = _loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    for stem, dates in manifest.items():
        merged = sorted(set(existing_manifest.get(stem, [])) | set(dates))
        existing_manifest[stem] = merged

    manifest_path.write_text(_dumps(existing_manifest), encoding="utf-8")
    print(f"\nWrote {manifest_path}")
    print("\nDone. Original monolithic files were NOT deleted.")
    print("Verify the dated files, then remove originals manually if satisfied.")


if __name__ == "__main__":
    main()
