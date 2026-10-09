# emlak-ai

Baku real estate intelligence: daily scraper for all bina.az listing categories with full historical price and availability tracking.

## What it does

- Scrapes all 11 bina.az categories (apartments, houses, land, commercial, office, garage — sale and rental)
- Persists every listing as JSON with a complete `price_history` array (every price change recorded)
- Marks listings as `deleted_at` when they disappear from the site — keeps full history, nothing is ever deleted
- Sends a Telegram notification after each run (success summary or failure alert)

## Data files

Data is stored as incremental dated files — each scrape run appends only new listings to a new file rather than overwriting a single large file:

```
data/
  apartment_sale_2026-09-30.json   ← listings first seen on that date
  apartment_sale_2026-10-01.json
  apartment_sale_2026-10-06.json   ← today's new listings
  apartment_rental_2026-09-30.json
  ...
  manifest.json                    ← index of all dated files per category
```

Price changes and deletions are written back to whichever dated file the listing originally came from, so no separate state file is needed.

`manifest.json` maps each stem to a sorted list of available dates:

```json
{
  "apartment_sale": ["2026-09-30", "2026-10-01", "2026-10-06"],
  "apartment_rental": ["2026-09-30", "2026-10-01"]
}
```

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
  ],
  "walk_min_to_transport": 4.2,
  "nearest_transport_type": "bus",
  "nearest_transport_name": "88, 125, 176",
  "metro_walk_min": 11.3,
  "metro_station_name": "Nəriman Nərimanov",
  "stops_within_10min": 8
}
```

`deleted_at` is `null` for active listings. When a listing disappears from bina.az it gets a timestamp but stays in its dated file so no historical data is lost. Each run only the changed files (new listings file + any files containing updated/deleted records) are rewritten.

## Run locally

### Frontend

```bash
python3 serve.py
```

Opens `http://localhost:8000` in your browser automatically.

### Scraper

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download the Camoufox browser (once)
python3 -m camoufox fetch

# Copy and fill in env config
cp .env.example .env

# Run the full scraper — opens a visible browser window
python3 -m scraper.main

# Run a quick test with 20 listings per category
SCRAPE_LIMIT=20 python3 -m scraper.main
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

## Deal scoring

Each listing receives a score from 0–100 computed entirely in the browser. Higher is better.

### Components (all categories except garage)

| Component | Max pts | Notes |
|-----------|---------|-------|
| Price percentile (₼/m² or ₼/sot) | 32–62 | Lower price per m² vs same category/type = higher score |
| Transport proximity | 0–15 | Effective walk ≤4 min: +15 · ≤8 min: +10 · ≤14 min: +5 |
| Owner (not agency) | 0–18 | Full points if `is_agency = false` |
| Price dropped | 0–13 | Any reduction vs first recorded price |
| Building type | 0–18 | Yeni tikili (new build) bonus — apartments only |
| Çıxarış (deed) | 0–9 | Has bill of sale |

The theoretical max exceeds 100 in some combinations; the score is capped at 100.

**Transport score** uses a type-weighted effective walk time to avoid double-counting metro access:

```
effective_walk = walk_min_to_transport × type_factor
  metro → 0.7   (metro is worth more per minute than bus)
  train → 0.8
  bus   → 1.0
```

A metro station 5 min away → 3.5 effective min → +15 pts.
A bus stop 5 min away → 5 effective min → +10 pts.

Transport fields (`walk_min_to_transport`, `metro_walk_min`, `stops_within_10min`) are pre-computed at scrape time using straight-line haversine ÷ 70 m/min (≈ 4.2 km/h urban walking speed). Bus stops show served route numbers (e.g. `"88, 125, 176"`); metro/train show the station name.

### Garage scoring

Garages are scored on price percentile (65 pts), owner status (25 pts), and price drop (10 pts) only — transport is not relevant.

## Transport data

Public transport stop locations are stored in `data/transport_stops.json` (3,912 stops):

- **Bus** (3,834 stops) — from [ayna.gov.az](https://ayna.gov.az) official Baku transport API, enriched with route numbers via all 209 routes
- **Metro** (34 stations) — from OpenStreetMap
- **Train** (44 stations/halts) — from OpenStreetMap

### Refreshing transport data

```bash
# Re-fetch stop locations (bus, metro, train)
python3 scripts/fetch_transport_stops.py

# Re-fetch bus route numbers per stop (209 routes)
python3 scripts/fetch_bus_routes.py

# Re-enrich all listings with updated transport fields
python3 scripts/enrich_transport.py --force
```

## Project structure

```
scraper/
  categories.py   — 11 bina.az category definitions
  browser.py      — Camoufox automation: GraphQL pagination, item detail fetch
  transport.py    — transport proximity enrichment (haversine index + field writer)
  main.py         — entry point: scrape all categories, enrich, save, notify Telegram
scripts/
  fetch_transport_stops.py  — fetch bus/metro/train stop locations (ayna.gov.az + OSM)
  fetch_bus_routes.py       — fetch route numbers per bus stop (209 routes)
  enrich_transport.py       — retroactively add transport fields to existing listings
data/
  {stem}_{YYYY-MM-DD}.json  — incremental dated listing files (committed to git)
  manifest.json             — index of dated files per category stem
  transport_stops.json      — all public transport stop locations with route numbers
.github/workflows/
  scrape.yml      — workflow_dispatch triggered by external cron
```

## How historical tracking works

1. **New listing** → saved with `first_seen_at = now`, initial `price_history` entry created
2. **Same listing, same price** → only `last_seen_at` updated
3. **Same listing, price changed** → `price` updated, new entry appended to `price_history`
4. **Listing gone from site** → `deleted_at` set, listing stays in JSON
5. **Listing reappears** → `deleted_at` cleared, treated as active again
