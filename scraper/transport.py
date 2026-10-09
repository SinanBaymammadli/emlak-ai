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
"""
import bisect
import json
import math
from pathlib import Path

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


def load_and_build(data_dir: Path) -> tuple[list[dict], list[float]]:
    """Load transport stops and return (sorted_stops, lats) index."""
    stops = _load_stops(data_dir)
    if not stops:
        return [], []
    return build_index(stops)
