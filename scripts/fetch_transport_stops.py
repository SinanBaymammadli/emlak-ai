"""
Fetch all public transport stop locations for Baku and save to data/transport_stops.json.

Sources:
  bus   — map-api.ayna.gov.az (official Baku transport agency, no auth)
  metro — OpenStreetMap Overpass API
  train — OpenStreetMap Overpass API

Output format (one object per stop):
  {
    "id": <string>,        # "bus-1234", "metro-670199298", "train-12345"
    "type": "bus"|"metro"|"train",
    "lat": <float>,
    "lng": <float>,
    "name": <string|null>,
    "name_en": <string|null>,
    "name_ru": <string|null>,
    "code": <string|null>,   # bus stop code from ayna.gov.az
    "route_ref": <string|null>  # bus line numbers from OSM (metro/train only)
  }

Usage:
    python3 scripts/fetch_transport_stops.py
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

AYNA_BASE = "https://map-api.ayna.gov.az"
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OVERPASS_BBOX = "(40.2,49.5,40.65,50.4)"
OVERPASS_HEADERS = {
    "User-Agent": "emlak-ai/1.0 (Baku transport stop index)",
    "Content-Type": "application/x-www-form-urlencoded",
}
OUTPUT = Path(__file__).parent.parent / "data" / "transport_stops.json"


# ── helpers ───────────────────────────────────────────────────────────────────

def get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "emlak-ai/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def overpass_query(tag_filters: str | list[str], label: str, retries: int = 6) -> list[dict]:
    if isinstance(tag_filters, list):
        union = "".join(f"node{f}{OVERPASS_BBOX};" for f in tag_filters)
        query = f"[out:json][timeout:45]; ({union}); out body;"
    else:
        query = f"[out:json][timeout:45]; node{tag_filters}{OVERPASS_BBOX}; out body;"
    print(f"  fetching {label}...", end=" ", flush=True)
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err: Exception | None = None
    for attempt in range(retries):
        server = OVERPASS_SERVERS[attempt % len(OVERPASS_SERVERS)]
        try:
            req = urllib.request.Request(server, data=data, headers=OVERPASS_HEADERS)
            with urllib.request.urlopen(req, timeout=90) as r:
                result = json.load(r)
            elements = result["elements"]
            print(f"{len(elements)} found")
            return elements
        except Exception as e:
            last_err = e
            wait = 10 * (attempt + 1)
            print(f"\n    attempt {attempt + 1} failed ({e}), retrying in {wait}s...", end=" ", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"All Overpass attempts failed for {label}: {last_err}")


# ── bus stops — ayna.gov.az ───────────────────────────────────────────────────

def fetch_bus_stops() -> list[dict]:
    print("  probing total count...", end=" ", flush=True)
    page1 = get_json(f"{AYNA_BASE}/api/stop/getPagedList?page=1&pageSize=1")
    total = page1.get("totalCount") or page1.get("total") or page1.get("count")
    if total is None:
        # fall back to getAll endpoint
        print("using getAll fallback...")
        raw = get_json(f"{AYNA_BASE}/api/stop/getAll")
        if isinstance(raw, list):
            stops_raw = raw
        else:
            stops_raw = raw.get("data") or raw.get("items") or []
        print(f"  {len(stops_raw)} stops via getAll")
    else:
        print(f"total={total}, fetching in one page...")
        page_all = get_json(f"{AYNA_BASE}/api/stop/getPagedList?page=1&pageSize={total}")
        stops_raw = (
            page_all.get("data")
            or page_all.get("items")
            or page_all.get("list")
            or []
        )
        print(f"  {len(stops_raw)} stops fetched")

    stops = []
    for s in stops_raw:
        try:
            lat = float(str(s.get("latitude", "")).replace(",", "."))
            lng = float(str(s.get("longitude", "")).replace(",", "."))
        except (ValueError, TypeError):
            continue
        if not (39 < lat < 42 and 48 < lng < 52):
            continue
        stops.append({
            "id": f"bus-{s['id']}",
            "type": "bus",
            "lat": lat,
            "lng": lng,
            "name": s.get("name") or None,
            "name_en": None,
            "name_ru": None,
            "code": s.get("code") or None,
            "route_ref": None,
        })
    return stops


# ── metro & train — OpenStreetMap ─────────────────────────────────────────────

def fetch_metro_stops() -> list[dict]:
    nodes = overpass_query('["station"="subway"]', "metro stations")
    stops = []
    for el in nodes:
        tags = el.get("tags", {})
        stops.append({
            "id": f"metro-{el['id']}",
            "type": "metro",
            "lat": el["lat"],
            "lng": el["lon"],
            "name": tags.get("name") or tags.get("name:az") or None,
            "name_en": tags.get("name:en") or None,
            "name_ru": tags.get("name:ru") or None,
            "code": None,
            "route_ref": tags.get("route_ref") or None,
        })
    return stops


def fetch_train_stops() -> list[dict]:
    all_nodes = overpass_query(
        ['["railway"="station"]["station"!="subway"]', '["railway"="halt"]'],
        "train stations + halts",
    )
    stops = []
    seen: set[int] = set()
    for el in all_nodes:
        if el["id"] in seen:
            continue
        seen.add(el["id"])
        tags = el.get("tags", {})
        stops.append({
            "id": f"train-{el['id']}",
            "type": "train",
            "lat": el["lat"],
            "lng": el["lon"],
            "name": tags.get("name") or tags.get("name:az") or None,
            "name_en": tags.get("name:en") or None,
            "name_ru": tags.get("name:ru") or None,
            "code": None,
            "route_ref": tags.get("route_ref") or None,
        })
    return stops


# ── main ──────────────────────────────────────────────────────────────────────

def save(stops: list[dict]) -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stops, f, ensure_ascii=False, indent=2)


def main() -> None:
    print("Fetching Baku public transport stops...")

    print("\n[bus] ayna.gov.az")
    bus_stops = fetch_bus_stops()

    print("\n[metro] OpenStreetMap")
    time.sleep(2)
    metro_stops = fetch_metro_stops()

    # Save bus + metro immediately so we have something even if train fails
    save(bus_stops + metro_stops)
    print(f"  (partial save: {len(bus_stops)} bus + {len(metro_stops)} metro → {OUTPUT})")

    print("\n[train] OpenStreetMap")
    time.sleep(5)
    try:
        train_stops = fetch_train_stops()
    except RuntimeError as e:
        print(f"\n  WARNING: {e}")
        print("  Saving without train stops.")
        train_stops = []

    all_stops = bus_stops + metro_stops + train_stops
    save(all_stops)

    summary = {t: sum(1 for s in all_stops if s["type"] == t) for t in ("bus", "metro", "train")}
    print(f"\nTotal: {len(all_stops)}")
    for t, n in summary.items():
        print(f"  {t}: {n}")
    print(f"\nSaved → {OUTPUT}")


if __name__ == "__main__":
    main()
