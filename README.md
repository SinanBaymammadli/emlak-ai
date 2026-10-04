# emlak-ai

Baku real estate intelligence: daily scraper for all bina.az listing categories with full historical price and availability tracking.

## What it does

- Scrapes all 11 bina.az categories (apartments, houses, land, commercial, office, garage — sale and rental)
- Persists every listing as JSON with a complete `price_history` array (every price change recorded)
- Marks listings as `deleted_at` when they disappear from the site — keeps full history, nothing is ever deleted
- Sends a Telegram notification after each run (success summary or failure alert)

## Data files

One JSON file per category in `data/`:

| File | Listings on site |
|------|-----------------|
| `data/apartment_sale.json` | ~55,000 |
| `data/apartment_rental.json` | ~23,000 |
| `data/house_sale.json` | ~11,000 |
| `data/house_rental.json` | ~2,800 |
| `data/land_sale.json` | ~4,200 |
| `data/commercial_sale.json` | ~2,400 |
| `data/commercial_rental.json` | ~2,700 |
| `data/office_sale.json` | ~110 |
| `data/office_rental.json` | ~1,500 |
| `data/garage_sale.json` | ~120 |
| `data/garage_rental.json` | ~45 |

Each listing record:

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

`deleted_at` is `null` for active listings. When a listing disappears from bina.az it gets a timestamp but stays in the file so no historical data is lost. Each run the file is loaded, diffed against fresh scrape results, and saved back.

## Run locally

### Frontend

```bash
python3 serve.py
```

Opens `http://localhost:8000` in your browser automatically.

### Scraper

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download the Camoufox browser (once)
python -m camoufox fetch

# Copy and fill in env config
cp .env.example .env

# Run the full scraper — opens a visible browser window
python -m scraper.main

# Run a quick test with 20 listings per category
SCRAPE_LIMIT=20 python -m scraper.main
```

The scraper opens a real (non-headless) browser window to avoid Cloudflare bot detection.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_TOKEN` | Yes (for notifications) | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes (for notifications) | Your chat or group ID |
| `SCRAPE_LIMIT` | No | Max listings per category (for testing). Leave empty for full scrape. |
| `DATA_DIR` | No | Output directory (default: `data/`) |

## Scheduling (GitHub Actions)

The workflow (`.github/workflows/scrape.yml`) uses `workflow_dispatch` only — no built-in GitHub cron, which is unreliable for private repos and can silently skip runs. Use an external service to trigger it on a schedule.

### Setting up an external cron trigger

**Option 1 — cron-job.org (free)**
1. Create a free account at [cron-job.org](https://cron-job.org)
2. Create a new cron job:
   - **URL:** `https://api.github.com/repos/SinanBaymammadli/emlak-ai/actions/workflows/scrape.yml/dispatches`
   - **Method:** `POST`
   - **Headers:**
     ```
     Authorization: Bearer YOUR_GITHUB_PAT
     Accept: application/vnd.github+json
     Content-Type: application/json
     ```
   - **Body:** `{"ref":"main"}`
   - **Schedule:** daily at your preferred time

**Option 2 — EasyCron / Pipedream / similar**
Same — HTTP POST to the dispatch URL above.

**Creating a GitHub PAT**
1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Scope to this repo only, permission: **Actions → Read and Write**
3. Use the token as the `Bearer` value

**Trigger manually:**
GitHub → Actions → Scrape bina.az → Run workflow

### Required repository secrets

Add under Settings → Secrets and variables → Actions:
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

## Project structure

```
scraper/
  categories.py   — 11 bina.az category URLs
  parser.py       — text parsing: price, location, rooms, area, land area
  browser.py      — Camoufox automation: page load, scroll, card extraction, GraphQL
  main.py         — entry point: scrape all categories, update JSON files, notify Telegram
data/
  *.json          — per-category listing files (committed to git, updated after each scrape)
.github/workflows/
  scrape.yml      — workflow_dispatch triggered by external cron
```

## How historical tracking works

1. **New listing** → saved with `first_seen_at = now`, initial `price_history` entry created
2. **Same listing, same price** → only `last_seen_at` updated
3. **Same listing, price changed** → `price` updated, new entry appended to `price_history`
4. **Listing gone from site** → `deleted_at` set, listing stays in JSON
5. **Listing reappears** → `deleted_at` cleared, treated as active again
