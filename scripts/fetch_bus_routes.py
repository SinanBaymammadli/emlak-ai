"""
Fetch all 209 bus routes from ayna.gov.az and add route numbers (route_ref)
to each bus stop in data/transport_stops.json.

Usage:
    python3 scripts/fetch_bus_routes.py
"""
import json
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

AYNA_BASE = "https://map-api.ayna.gov.az"
OUTPUT = Path(__file__).parent.parent / "data" / "transport_stops.json"
HEADERS = {"User-Agent": "emlak-ai/1.0"}


def get_json(url: str) -> list | dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main() -> None:
    if not OUTPUT.exists():
        print("ERROR: data/transport_stops.json not found. Run fetch_transport_stops.py first.")
        return

    with open(OUTPUT, encoding="utf-8") as f:
        stops = json.load(f)

    print("Fetching bus route list…")
    bus_list = get_json(f"{AYNA_BASE}/api/bus/getBusList")
    print(f"  {len(bus_list)} routes")

    # stop_id (int) → set of bus number strings
    stop_lines: dict[int, set[str]] = defaultdict(set)

    for i, bus in enumerate(bus_list):
        bus_id = bus["id"]
        bus_num = bus["number"]
        print(f"  route {bus_num} ({i+1}/{len(bus_list)})…", end="\r", flush=True)
        try:
            detail = get_json(f"{AYNA_BASE}/api/bus/getBusById?id={bus_id}")
            for s in detail.get("stops", []):
                sid = s.get("stopId") or (s.get("stop") or {}).get("id")
                if sid:
                    stop_lines[sid].add(bus_num)
        except Exception as e:
            print(f"\n  WARNING: route {bus_num} failed: {e}")
        time.sleep(0.15)

    print(f"\nBuilt route map for {len(stop_lines)} stops")

    # Write route_ref back into transport_stops.json
    updated = 0
    for stop in stops:
        if stop["type"] != "bus":
            continue
        raw_id = stop["id"]  # "bus-1439"
        try:
            sid = int(raw_id.split("-", 1)[1])
        except (ValueError, IndexError):
            continue
        lines = stop_lines.get(sid)
        if lines:
            # Sort numerically where possible, then alphabetically
            def sort_key(n):
                try: return (0, int(n))
                except ValueError: return (1, n)
            stop["route_ref"] = ", ".join(sorted(lines, key=sort_key))
            updated += 1

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stops, f, ensure_ascii=False, indent=2)

    print(f"Updated route_ref for {updated} bus stops → {OUTPUT}")


if __name__ == "__main__":
    main()
