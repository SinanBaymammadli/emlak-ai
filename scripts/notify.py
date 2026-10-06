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
icon = "✅" if result == "success" else "❌" if result == "failure" else "❓"

# Fetch per-job results from GitHub API to identify which categories failed
failed_categories: set[str] = set()
gh_token = os.environ.get("GITHUB_TOKEN")
run_id = os.environ.get("GITHUB_RUN_ID")
repo = os.environ.get("GITHUB_REPOSITORY")
if gh_token and run_id and repo:
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100",
            headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
        )
        jobs = json.loads(urllib.request.urlopen(req, timeout=10).read())
        for job in jobs.get("jobs", []):
            name = job.get("name", "")
            # Job names are "Scrape apartment_sale" etc.
            if name.startswith("Scrape ") and job.get("conclusion") == "failure":
                failed_categories.add(name.removeprefix("Scrape "))
    except Exception as exc:
        print(f"Could not fetch job results: {exc}")

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

def load_cat_listings(cat: str) -> list:
    manifest_path = Path("data") / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    dates = manifest.get(cat, [])
    listings = []
    for d in dates:
        p = Path("data") / f"{cat}_{d}.json"
        if p.exists():
            listings.extend(json.loads(p.read_text(encoding="utf-8")))
    return listings


lines = [f"{icon} <b>emlak-ai scrape complete</b> ({result})\n"]
for cat in CATEGORIES:
    try:
        listings = load_cat_listings(cat)
        ids = active_ids(listings)
        total = len(ids)

        new_count = 0
        if base:
            try:
                # count IDs in the today-dated file that weren't active at base
                from datetime import date as _date
                today_file = f"data/{cat}_{_date.today().isoformat()}.json"
                old_raw = subprocess.check_output(
                    ["git", "show", f"{base}:{today_file}"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                new_count = len(ids - active_ids(json.loads(old_raw)))
            except subprocess.CalledProcessError:
                # today's file is brand new — all its listings are new
                today_path = Path("data") / f"{cat}_{_date.today().isoformat()}.json"
                if today_path.exists():
                    new_count = len(active_ids(json.loads(today_path.read_text(encoding="utf-8"))))

        new_str = f"  <b>+{new_count} new</b>" if new_count else ""
        fail_str = "  ❌ <b>FAILED</b>" if cat in failed_categories else ""
        lines.append(f"  <b>{cat}</b>: {total} total{new_str}{fail_str}")
    except Exception as exc:
        print(f"  {cat} summary error: {exc}")
        fail_str = "  ❌ <b>FAILED</b>" if cat in failed_categories else ""
        lines.append(f"  <b>{cat}</b>: ⚠️ error{fail_str}")

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
