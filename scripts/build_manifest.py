"""Regenerate data/manifest.json from the actual files on disk."""
import json
import re
from pathlib import Path

manifest: dict[str, list[str]] = {}
for p in sorted(Path("data").glob("*_20??-??-??*.json")):
    m = re.match(r"^(.+)_(20\d{2}-\d{2}-\d{2}(?:-\d{2})?)\.json$", p.name)
    if m:
        stem, date = m.group(1), m.group(2)
        manifest.setdefault(stem, [])
        if date not in manifest[stem]:
            manifest[stem].append(date)
for k in manifest:
    manifest[k] = sorted(manifest[k])
Path("data/manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
)
print(f"manifest.json updated: {len(manifest)} categories")
