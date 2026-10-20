"""Migrate data files: merge price (int) + price_history into a single price array."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

total_files = 0
total_listings = 0
total_migrated = 0

for path in sorted(DATA_DIR.glob("*.json")):
    if path.name == "manifest.json":
        continue
    listings = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for l in listings:
        price = l.get("price")
        history = l.get("price_history")
        if isinstance(price, (int, float)):
            if history:
                l["price"] = history
            elif price is not None:
                l["price"] = [{"price": price, "date": "unknown"}]
            else:
                l["price"] = []
            changed = True
            total_migrated += 1
        if "price_history" in l:
            del l["price_history"]
            changed = True
        total_listings += 1
    if changed:
        path.write_text(
            json.dumps(listings, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        total_files += 1

print(f"Migrated {total_migrated} listings across {total_files} files ({total_listings} total)")
