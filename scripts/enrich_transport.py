"""
Retroactively add transport proximity fields to all existing listings.
Safe to re-run: only rewrites files that contain listings with coords but no transport data.

Usage:
    python3 scripts/enrich_transport.py
    python3 scripts/enrich_transport.py --force   # re-enrich all listings with coords
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scraper.transport import build_index, enrich, _load_stops

DATA_DIR = ROOT / "data"
FORCE = "--force" in sys.argv


def main() -> None:
    stops = _load_stops(DATA_DIR)
    if not stops:
        print("ERROR: data/transport_stops.json not found. Run fetch_transport_stops.py first.")
        sys.exit(1)

    sorted_stops, lats = build_index(stops)
    print(f"Transport index: {len(sorted_stops)} stops")

    json_files = sorted(DATA_DIR.glob("*_20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"))
    total_enriched = 0
    total_skipped = 0
    files_written = 0

    for path in json_files:
        try:
            with open(path, encoding="utf-8") as f:
                listings = json.load(f)
        except Exception as e:
            print(f"  skip {path.name}: {e}")
            continue

        dirty = False
        for l in listings:
            if l.get("lat") is None or l.get("lng") is None:
                total_skipped += 1
                continue
            if not FORCE and l.get("walk_min_to_transport") is not None:
                total_skipped += 1
                continue
            enrich(l, sorted_stops, lats)
            total_enriched += 1
            dirty = True

        if dirty:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(listings, f, ensure_ascii=False, indent=2)
            files_written += 1
            print(f"  {path.name}: enriched {sum(1 for l in listings if l.get('walk_min_to_transport') is not None)} listings")

    print(f"\nDone. enriched={total_enriched}  skipped={total_skipped}  files_written={files_written}")


if __name__ == "__main__":
    main()
