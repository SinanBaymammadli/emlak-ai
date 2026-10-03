"""Send a single Telegram summary after all scrape jobs complete."""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
if not token or not chat_id:
    print("No Telegram credentials — skipping")
    raise SystemExit(0)

result = os.environ.get("SCRAPE_RESULT", "unknown")
icon = "✅" if result == "success" else "⚠️" if result == "failure" else "❓"

CATEGORIES = [
    "apartment_rental",
    "apartment_sale",
    "commercial_rental",
    "commercial_sale",
    "garage_rental",
    "garage_sale",
    "house_rental",
    "house_sale",
    "land_sale",
    "office_rental",
    "office_sale",
]

# Find the oldest scrape commit pushed today so we can diff against its parent
hashes = subprocess.check_output(
    ["git", "log", "--format=%H", "--grep=chore: scrape", "--since=midnight"],
    text=True,
).split()
base = (
    subprocess.check_output(
        ["git", "rev-parse", f"{hashes[-1]}^"], text=True
    ).strip()
    if hashes
    else None
)

def active_ids(listings):
    return {l["id"] for l in listings if l.get("deleted_at") is None}

lines = [f"{icon} <b>emlak-ai scrape complete</b> ({result})\n"]
for cat in CATEGORIES:
    f = Path("data") / f"{cat}.json"
    try:
        listings = json.loads(f.read_text(encoding="utf-8"))
        ids = active_ids(listings)
        total = len(ids)

        new_count = 0
        if base:
            try:
                old = subprocess.check_output(
                    ["git", "show", f"{base}:data/{f.name}"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                new_count = len(ids - active_ids(json.loads(old)))
            except subprocess.CalledProcessError:
                new_count = total  # file is new this run

        new_str = f"  <b>+{new_count} new</b>" if new_count else ""
        lines.append(f"  <b>{cat}</b>: {total} total{new_str}")
    except Exception:
        lines.append(f"  <b>{cat}</b>: ⚠️ error")

payload = json.dumps(
    {"chat_id": chat_id, "text": "\n".join(lines), "parse_mode": "HTML"}
).encode()
req = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data=payload,
    headers={"Content-Type": "application/json"},
)
try:
    urllib.request.urlopen(req, timeout=10)
    print("Telegram notification sent")
except Exception as exc:
    print(f"Telegram notify failed: {exc}")
