"""
Transport proximity enrichment for listings.

Adds to each listing:
  walk_min_to_transport  – float, walk minutes to nearest stop (any type)
  nearest_transport_type – "bus"|"metro"|"train"
  nearest_transport_name – string
  metro_walk_min         – float|null, walk minutes to nearest metro (null if >30)
  stops_within_10min     – int, count of all stops within 700 m (~10 min walk)

Uses straight-line haversine distance / 70 m·min⁻¹ (≈ 4.2 km/h, urban-corrected).
Builds a lat-sorted index so each listing only checks O(30) nearby candidates.

osrm_nearest_walk() provides accurate OSRM foot-routing times for notifications.
"""
import bisect
import json
import math
import time
import urllib.request
from pathlib import Path

_OSRM_URL = "https://routing.openstreetmap.de/routed-foot/route/v1/foot/{lng1},{lat1};{lng2},{lat2}?overview=false"

WALK_SPEED_M_PER_MIN = 70       # 4.2 km/h accounting for non-straight paths
RADIUS_10MIN_M       = 700      # metres ≈ 10 min walk
MAX_METRO_WALK_MIN   = 30       # beyond this we store null


def _load_stops(data_dir: Path) -> list[dict]:
    path = data_dir / "transport_stops.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_index(stops: list[dict]) -> tuple[list[dict], list[float]]:
    """Return stops sorted by latitude + parallel list of lat values for bisect."""
    sorted_stops = sorted(stops, key=lambda s: s["lat"])
    lats = [s["lat"] for s in sorted_stops]
    return sorted_stops, lats


def _approx_dist_m(lat1: float, lng1: float, lat2: float, lng2: float, cos_lat: float) -> float:
    dlat = (lat2 - lat1) * 111_000
    dlng = (lng2 - lng1) * 111_000 * cos_lat
    return math.sqrt(dlat * dlat + dlng * dlng)


def enrich(listing: dict, sorted_stops: list[dict], lats: list[float]) -> None:
    """Mutate listing in-place to add transport proximity fields."""
    lat = listing.get("lat")
    lng = listing.get("lng")
    if lat is None or lng is None:
        return

    # Search within ±0.018 degrees (~2 km) in latitude
    search_deg = 0.018
    lo = bisect.bisect_left(lats, lat - search_deg)
    hi = bisect.bisect_right(lats, lat + search_deg)
    cos_lat = math.cos(math.radians(lat))

    candidates = [
        s for s in sorted_stops[lo:hi]
        if abs(s["lng"] - lng) <= search_deg
    ]

    if not candidates:
        # Widen search to ±0.09 degrees (~10 km) as fallback
        search_deg = 0.09
        lo = bisect.bisect_left(lats, lat - search_deg)
        hi = bisect.bisect_right(lats, lat + search_deg)
        candidates = [
            s for s in sorted_stops[lo:hi]
            if abs(s["lng"] - lng) <= search_deg
        ]

    if not candidates:
        return

    # Compute distances
    scored = [
        (s, _approx_dist_m(lat, lng, s["lat"], s["lng"], cos_lat))
        for s in candidates
    ]

    nearest_s, nearest_dist = min(scored, key=lambda x: x[1])
    listing["walk_min_to_transport"] = round(nearest_dist / WALK_SPEED_M_PER_MIN, 1)
    listing["nearest_transport_type"] = nearest_s["type"]
    # buses: show route numbers; metro/train: show station name
    if nearest_s["type"] == "bus":
        listing["nearest_transport_name"] = nearest_s.get("route_ref") or nearest_s.get("name") or None
    else:
        listing["nearest_transport_name"] = nearest_s.get("name") or nearest_s.get("name_en") or None

    # Metro nearest
    metro = [(s, d) for s, d in scored if s["type"] == "metro"]
    if metro:
        ms, md = min(metro, key=lambda x: x[1])
        walk = round(md / WALK_SPEED_M_PER_MIN, 1)
        if walk <= MAX_METRO_WALK_MIN:
            listing["metro_walk_min"] = walk
            listing["metro_station_name"] = ms.get("name") or ms.get("name_en") or None
        else:
            listing["metro_walk_min"] = None
            listing["metro_station_name"] = None
    else:
        listing["metro_walk_min"] = None
        listing["metro_station_name"] = None

    # Stops within 10 min (~700 m)
    listing["stops_within_10min"] = sum(1 for _, d in scored if d <= RADIUS_10MIN_M)


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _osrm_walk(lat1: float, lng1: float, lat2: float, lng2: float) -> tuple[float | None, float | None]:
    url = _OSRM_URL.format(lat1=lat1, lng1=lng1, lat2=lat2, lng2=lng2)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.load(r)
            if data.get("code") == "Ok":
                route = data["routes"][0]
                return route["distance"], route["duration"]
            return None, None
        except Exception as exc:
            if attempt < 2:
                time.sleep(1)
            else:
                print(f"  OSRM error: {exc}")
    return None, None


def osrm_nearest_walk(
    lat: float, lng: float,
    sorted_stops: list[dict], lats: list[float],
    candidates: int = 3,
) -> dict | None:
    """
    Route to the nearest `candidates` stops via OSRM foot routing.
    Returns a dict with walk_min, transport_type, transport_name for the best stop,
    or None if OSRM is unavailable.
    """
    search_deg = 0.09
    lo = bisect.bisect_left(lats, lat - search_deg)
    hi = bisect.bisect_right(lats, lat + search_deg)
    nearby = [s for s in sorted_stops[lo:hi] if abs(s["lng"] - lng) <= search_deg]
    if not nearby:
        return None

    closest = sorted(nearby, key=lambda s: _haversine(lat, lng, s["lat"], s["lng"]))[:candidates]

    best_dur, best_stop = float("inf"), None
    for s in closest:
        _, dur_s = _osrm_walk(lat, lng, s["lat"], s["lng"])
        time.sleep(0.25)
        if dur_s is not None and dur_s < best_dur:
            best_dur, best_stop = dur_s, s

    if best_stop is None:
        return None

    if best_stop["type"] == "bus":
        name = best_stop.get("route_ref") or best_stop.get("name") or None
    else:
        name = best_stop.get("name") or best_stop.get("name_en") or None

    return {
        "walk_min": round(best_dur / 60, 1),
        "transport_type": best_stop["type"],
        "transport_name": name,
    }


def load_and_build(data_dir: Path) -> tuple[list[dict], list[float]]:
    """Load transport stops and return (sorted_stops, lats) index."""
    stops = _load_stops(data_dir)
    if not stops:
        return [], []
    return build_index(stops)
