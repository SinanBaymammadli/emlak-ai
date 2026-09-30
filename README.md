# emlak-ai

Baku real estate intelligence: daily scraper for all bina.az listing categories with full historical price and availability tracking.

## What it does

- Scrapes all bina.az categories (apartments, houses, land, commercial, office — sale and rental)
- Stores every listing in SQLite with a complete price history (every price change recorded)
- Marks listings as `deleted_at` when they disappear from the site, keeping full history
- Exports per-category JSON files for the frontend dashboard

## Output data files

After each scrape run, `data/` contains one JSON file per category:

| File | Contents |
|------|----------|
| `data/apartment_sale.json` | Apartment sale listings |
| `data/apartment_rental.json` | Apartment rental listings |
| `data/house_sale.json` | House/villa sale listings |
| `data/house_rental.json` | House/villa rental listings |
| `data/land_sale.json` | Land plot sale listings |
| `data/commercial_sale.json` | Commercial property sale listings |
| `data/commercial_rental.json` | Commercial property rental listings |
| `data/office_rental.json` | Office rental listings |

Each listing looks like:

```json
{
  "id": "6153043",
  "category": "apartment",
  "deal_type": "sale",
  "price": 80000,
  "location": "Nərimanov r., Bakı",
  "rooms": "3 otaqlı",
  "area_m2": 75.0,
  "land_area_sot": null,
  "lat": 40.4093,
  "lng": 49.8671,
  "has_repair": true,
  "photo_url": "https://bina.azstatic.com/uploads/big/...",
  "url": "https://bina.az/items/6153043",
  "first_seen_at": "2026-09-30T06:00:00+00:00",
  "last_seen_at": "2026-09-30T06:00:00+00:00",
  "deleted_at": null,
  "price_history": [
    {"price": 85000, "date": "2026-09-15T06:00:00+00:00"},
    {"price": 80000, "date": "2026-09-28T06:00:00+00:00"}
  ]
}
```

`deleted_at` is `null` for active listings. When a listing disappears from bina.az it gets a timestamp but stays in the file so historical data is never lost.

## Run locally

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download the Camoufox browser (once)
python -m camoufox fetch

# Copy env config (Telegram optional — not used yet)
cp .env.example .env

# Run the scraper — opens a visible browser window
python -m scraper.main
```

The scraper opens a real browser window (not headless) to avoid Cloudflare bot detection, same approach as the binaaz reference project.

## Scheduling

The workflow (`.github/workflows/scrape.yml`) is triggered only via `workflow_dispatch` — no built-in cron. GitHub's native cron is unreliable (can skip runs silently), so use an external service to call the GitHub API on a schedule.

### Setting up an external cron trigger

**Option 1 — cron-job.org (free)**
1. Create a free account at [cron-job.org](https://cron-job.org)
2. Create a new cron job with:
   - **URL:** `https://api.github.com/repos/YOUR_USERNAME/emlak-ai/actions/workflows/scrape.yml/dispatches`
   - **Method:** POST
   - **Headers:**
     ```
     Authorization: Bearer YOUR_GITHUB_PAT
     Accept: application/vnd.github+json
     Content-Type: application/json
     ```
   - **Body:** `{"ref":"main"}`
   - **Schedule:** daily at your preferred time

**Option 2 — EasyCron / Pipedream / similar**
Same approach — HTTP POST to the GitHub Actions dispatch API endpoint above.

**Creating a GitHub Personal Access Token (PAT)**
1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Scope it to this repo only with **Actions: Read and Write** permission
3. Paste the token as the `Bearer` value in your cron service

**Trigger manually anytime:**
GitHub → Actions → Scrape bina.az → Run workflow

## Project structure

```
scraper/
  categories.py   — all 8 bina.az search URLs (category + deal_type + URL)
  parser.py       — pure text parsing: price, location, rooms, area, land area
  browser.py      — Camoufox browser automation: load, scroll, extract cards, GraphQL
  main.py         — entry point: scrape all categories, update JSON files
data/
  apartment_sale.json
  apartment_rental.json
  house_sale.json
  house_rental.json
  land_sale.json
  commercial_sale.json
  commercial_rental.json
  office_rental.json
.github/workflows/
  scrape.yml      — workflow_dispatch only (triggered by external cron)
```

## How historical tracking works

1. First time a listing is seen → inserted with `first_seen_at = now`, first `price_history` record written
2. Same listing seen again, same price → only `last_seen_at` updated
3. Same listing seen again, price changed → `price` updated, new `price_history` record appended
4. Listing no longer returned by bina.az → `deleted_at` set to now (listing stays in DB and JSON)
5. Listing reappears later → `deleted_at` cleared, treated as active again
