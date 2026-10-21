"""Send a single Telegram summary after all scrape jobs complete,
plus individual notifications for new/price-changed listings that match filters."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.notification_filters import (
    check_and_notify,
    check_and_notify_price_change,
    load_filters,
)
from scraper import transport as _transport

token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")


def send_tg(text: str) -> None:
    if not token or not chat_id:
        print("No Telegram credentials — skipping")
        return
    payload = json.dumps(
        {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        print(f"Telegram notify failed: {exc}")


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

# Find the most recent scrape commit so we can diff against its parent (= state before this run).
# Using hashes[0] (newest today) means runs 2 and 3 only notify about *their* new findings.
hashes = subprocess.check_output(
    ["git", "log", "--format=%H", "--grep=chore: scrape", "--since=midnight"],
    text=True,
).split()
base = (
    subprocess.check_output(
        ["git", "rev-parse", f"{hashes[0]}^"], text=True
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


manifest_path = Path("data") / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

# ── Summary message ───────────────────────────────────────────────────────────

lines = [f"{icon} <b>emlak-ai scrape complete</b> ({result})\n"]
for cat in CATEGORIES:
    try:
        listings = load_cat_listings(cat)
        ids = active_ids(listings)
        total = len(ids)

        new_count = 0
        if base:
            base_ids: set[str] = set()
            for d in manifest.get(cat, []):
                try:
                    old_raw = subprocess.check_output(
                        ["git", "show", f"{base}:data/{cat}_{d}.json"],
                        text=True, stderr=subprocess.DEVNULL,
                    )
                    base_ids.update(
                        l["id"] for l in json.loads(old_raw) if not l.get("deleted_at")
                    )
                except subprocess.CalledProcessError:
                    pass
            new_count = len(ids - base_ids)

        new_str = f"  <b>+{new_count} new</b>" if new_count else ""
        fail_str = "  ❌ <b>FAILED</b>" if cat in failed_categories else ""
        lines.append(f"  <b>{cat}</b>: {total} total{new_str}{fail_str}")
    except Exception as exc:
        print(f"  {cat} summary error: {exc}")
        fail_str = "  ❌ <b>FAILED</b>" if cat in failed_categories else ""
        lines.append(f"  <b>{cat}</b>: ⚠️ error{fail_str}")

send_tg("\n".join(lines))
print("Telegram summary sent")

# ── Filter notifications ───────────────────────────────────────────────────────

if not base:
    print("No base commit found — skipping filter notifications")
    raise SystemExit(0)

filters = load_filters(Path("."))
if not filters:
    print("No filters defined — skipping filter notifications")
    raise SystemExit(0)

stops, lats = _transport.load_and_build(Path("data"))

matched_filter_indices: set[int] = set()

for cat in CATEGORIES:
    try:
        current_listings = load_cat_listings(cat)
        active = {l["id"]: l for l in current_listings if not l.get("deleted_at")}
        all_active = list(active.values())

        # Load base state for this category
        base_by_id: dict = {}
        for d in manifest.get(cat, []):
            filepath = f"data/{cat}_{d}.json"
            try:
                old_raw = subprocess.check_output(
                    ["git", "show", f"{base}:{filepath}"],
                    text=True, stderr=subprocess.DEVNULL,
                )
                for l in json.loads(old_raw):
                    base_by_id[l["id"]] = l
            except subprocess.CalledProcessError:
                pass

        # New listings
        for lid in set(active) - set(base_by_id):
            matched_filter_indices |= check_and_notify(active[lid], filters, send_tg, all_active, stops, lats)

        # Price-changed listings
        for lid, listing in active.items():
            base_l = base_by_id.get(lid)
            if not base_l:
                continue
            curr_arr = listing.get("price") or []
            base_arr = base_l.get("price") or []
            if not curr_arr or not base_arr:
                continue
            # Support both new format (list of dicts) and old int format during transition
            curr_price = curr_arr[-1]["price"] if isinstance(curr_arr[-1], dict) else curr_arr[-1]
            base_price = base_arr[-1]["price"] if isinstance(base_arr[-1], dict) else base_arr[-1]
            if curr_price != base_price:
                matched_filter_indices |= check_and_notify_price_change(listing, base_price, filters, send_tg, all_active, stops, lats)

    except Exception as exc:
        print(f"  {cat} filter notification error: {exc}")

for i, f in enumerate(filters):
    if i not in matched_filter_indices:
        name = f.get("name") or f"Filter {i + 1}"
        send_tg(f"🔕 <b>{name}</b>: no new or price-changed listings this run")

print("Filter notifications done")
