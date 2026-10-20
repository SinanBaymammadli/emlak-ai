"""Filter new listings against user-defined criteria and emit Telegram notifications."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scraper import transport as _transport

# ── Deal scoring (mirrors script.js computeScores) ────────────────────────────

_RENOVATION_COST_PER_M2 = 200
_TYPE_FACTOR = {"metro": 0.7, "train": 0.8, "bus": 1.0}


def _current_price(listing: dict) -> int | None:
    arr = listing.get("price") or []
    return arr[-1]["price"] if arr else None


def _pct_rank(vals: list, lower_is_better: bool) -> list:
    n = len(vals)
    valid = [(i, v) for i, v in enumerate(vals) if v is not None]
    out: list = [None] * n
    if len(valid) <= 1:
        for i, _ in valid:
            out[i] = 0.5
        return out
    valid.sort(key=lambda x: x[1])
    for rank, (i, _) in enumerate(valid):
        out[i] = rank / (len(valid) - 1)
    if lower_is_better:
        out = [1 - v if v is not None else None for v in out]
    return out


def compute_score(listing: dict, all_listings: list) -> int:
    cat = listing.get("category")
    dt = listing.get("deal_type")
    group = [l for l in all_listings
             if l.get("category") == cat and l.get("deal_type") == dt and not l.get("deleted_at")]
    if not group:
        group = [listing]
    try:
        gi = next(i for i, l in enumerate(group) if l["id"] == listing["id"])
    except StopIteration:
        group.append(listing)
        gi = len(group) - 1

    def _ppm2(l):
        a = l.get("area_m2")
        p = _current_price(l)
        if not p or not a or a <= 0:
            return None
        reno = _RENOVATION_COST_PER_M2 * a if l.get("has_repair") is False else 0
        return (p + reno) / a

    def _ppsot(l):
        p, s = _current_price(l), l.get("land_area_sot")
        return p / s if p and s and s > 0 else None

    ppm2_pct = _pct_rank([_ppm2(l) for l in group], True)
    ppsot_pct = _pct_rank([_ppsot(l) for l in group], True)

    is_sale = dt == "sale"
    owner_pts = 1.0 if listing.get("is_agency") is False else 0.0 if listing.get("is_agency") is True else 0.5
    h = listing.get("price") or []
    dropped = len(h) >= 2 and h[-1]["price"] < h[0]["price"]

    w_min = listing.get("walk_min_to_transport")
    transport_score = 0
    if w_min is not None:
        eff = w_min * _TYPE_FACTOR.get(listing.get("nearest_transport_type") or "", 1.0)
        if eff <= 4:
            transport_score = 15
        elif eff <= 8:
            transport_score = 10
        elif eff <= 14:
            transport_score = 5

    score = 0.0
    if cat == "apartment":
        if ppm2_pct[gi] is not None: score += 45 * ppm2_pct[gi]
        if listing.get("building_type") == "Yeni tikili": score += 18
        elif listing.get("building_type") == "Köhnə tikili": score += 5
        score += 13 * owner_pts
        if dropped: score += 9
        if is_sale and listing.get("has_bill_of_sale"): score += 5
        score += transport_score
    elif cat == "house":
        if ppm2_pct[gi] is not None: score += 32 * ppm2_pct[gi]
        if ppsot_pct[gi] is not None: score += 27 * ppsot_pct[gi]
        score += 13 * owner_pts
        if dropped: score += 13
        if is_sale and listing.get("has_bill_of_sale"): score += 5
        score += transport_score
    elif cat == "land":
        if ppsot_pct[gi] is not None: score += 62 * ppsot_pct[gi]
        elif ppm2_pct[gi] is not None: score += 62 * ppm2_pct[gi]
        score += 13 * owner_pts
        if dropped: score += 9
        if is_sale and listing.get("has_bill_of_sale"): score += 5
        score += transport_score
    elif cat in ("commercial", "office"):
        if ppm2_pct[gi] is not None: score += 50 * ppm2_pct[gi]
        score += 18 * owner_pts
        if dropped: score += 13
        if is_sale and listing.get("has_bill_of_sale"): score += 9
        score += transport_score
    elif cat == "garage":
        if ppm2_pct[gi] is not None: score += 65 * ppm2_pct[gi]
        score += 25 * owner_pts
        if dropped: score += 10

    return round(min(100, score))


def _rooms(listing: dict) -> int | None:
    raw = listing.get("rooms") or ""
    m = re.match(r"(\d+)", raw)
    return int(m.group(1)) if m else None


def matches(listing: dict, f: dict) -> bool:
    if "category" in f and listing.get("category") != f["category"]:
        return False
    if "deal_type" in f and listing.get("deal_type") != f["deal_type"]:
        return False

    price = _current_price(listing)
    if "price_min" in f and (price is None or price < f["price_min"]):
        return False
    if "price_max" in f and (price is None or price > f["price_max"]):
        return False

    rooms = _rooms(listing)
    if "rooms_min" in f and (rooms is None or rooms < f["rooms_min"]):
        return False
    if "rooms_max" in f and (rooms is None or rooms > f["rooms_max"]):
        return False

    area = listing.get("area_m2")
    if "area_min" in f and (area is None or area < f["area_min"]):
        return False
    if "area_max" in f and (area is None or area > f["area_max"]):
        return False

    floor = listing.get("floor_number")
    if "floor_min" in f and (floor is None or floor < f["floor_min"]):
        return False
    if "floor_max" in f and (floor is None or floor > f["floor_max"]):
        return False

    if "is_agency" in f and listing.get("is_agency") != f["is_agency"]:
        return False
    if "has_repair" in f and listing.get("has_repair") != f["has_repair"]:
        return False
    if "has_mortgage" in f and listing.get("has_mortgage") != f["has_mortgage"]:
        return False
    if "has_bill_of_sale" in f and listing.get("has_bill_of_sale") != f["has_bill_of_sale"]:
        return False

    land = listing.get("land_area_sot")
    if "land_area_sot_min" in f and (land is None or land < f["land_area_sot_min"]):
        return False
    if "land_area_sot_max" in f and (land is None or land > f["land_area_sot_max"]):
        return False

    metro = listing.get("metro_walk_min")
    if "metro_walk_max" in f and (metro is None or metro > f["metro_walk_max"]):
        return False

    transport = listing.get("walk_min_to_transport")
    if "transport_walk_max" in f and (transport is None or transport > f["transport_walk_max"]):
        return False

    keywords: list[str] | None = f.get("location_contains")
    if keywords:
        loc = (listing.get("location") or "").lower()
        if not any(kw.lower() in loc for kw in keywords):
            return False

    return True


def _unit_prices(listing: dict) -> str:
    parts = []
    price = _current_price(listing)
    area = listing.get("area_m2")
    if price and area:
        try:
            parts.append(f"{round(price / float(area)):,} AZN/m²")
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    sot = listing.get("land_area_sot")
    if price and sot:
        try:
            parts.append(f"{round(price / float(sot)):,} AZN/sot")
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    return " · ".join(parts)


def _repair_label(listing: dict) -> str:
    r = listing.get("has_repair")
    if r is True:
        return "✔ Təmirli"
    if r is False:
        return "✘ Təmirsiz"
    return ""


def _score_label(score: int | None) -> str:
    if score is None:
        return ""
    dot = "🟢" if score >= 65 else "🟡" if score >= 40 else "🔴"
    return f"{dot} Deal score: <b>{score}/100</b>"


def format_message(listing: dict, filter_name: str, score: int | None = None) -> str:
    parts = [listing["url"]]

    title = listing.get("title")
    parts.append(f'🏠 <b>{title or "Yeni elan"}</b>')

    price = _current_price(listing)
    if price is not None:
        deal = listing.get("deal_type", "")
        currency = "AZN/ay" if deal == "rental" else "AZN"
        parts.append(f'💰 {price:,} {currency}')

    details: list[str] = []
    if listing.get("rooms"):
        details.append(listing["rooms"])
    if listing.get("area_m2"):
        details.append(f'{listing["area_m2"]} m²')
    if listing.get("land_area_sot"):
        details.append(f'{listing["land_area_sot"]} sot')
    if listing.get("floor"):
        details.append(listing["floor"])
    if details:
        parts.append(" · ".join(details))

    location_parts: list[str] = []
    if listing.get("location"):
        location_parts.append(listing["location"])
    lat, lng = listing.get("lat"), listing.get("lng")
    if lat and lng:
        location_parts.append(f'<a href="https://maps.google.com/?q={lat},{lng}">Xəritədə aç</a>')
    if location_parts:
        parts.append(f'📍 {" · ".join(location_parts)}')

    metro = listing.get("metro_station_name")
    metro_min = listing.get("metro_walk_min")
    if metro and metro_min is not None:
        parts.append(f'🚇 {metro} ({metro_min:.0f} dəq)')

    bus_name = listing.get("_osrm_transport_name") or listing.get("nearest_transport_name")
    bus_min = listing.get("_osrm_walk_min") if "_osrm_walk_min" in listing else listing.get("walk_min_to_transport")
    transport_type = listing.get("_osrm_transport_type") or listing.get("nearest_transport_type", "bus")
    if bus_name and bus_min is not None:
        icon = "🚇" if transport_type == "metro" else "🚆" if transport_type == "train" else "🚌"
        parts.append(f'{icon} {bus_name} ({bus_min:.0f} dəq piyada)')

    flags: list[str] = []
    if listing.get("has_repair"):
        flags.append("təmirli")
    if listing.get("is_agency") is False:
        flags.append("sahibindən")
    if listing.get("has_mortgage"):
        flags.append("ipoteka")
    if flags:
        parts.append(" · ".join(flags))

    label = _score_label(score)
    if label:
        parts.append(label)

    return "\n".join(parts)


def format_price_change_message(listing: dict, old_price: int, score: int | None = None) -> str:
    new_price = _current_price(listing)
    diff = new_price - old_price
    arrow = "📈" if diff > 0 else "📉"
    sign = "+" if diff > 0 else ""
    deal = listing.get("deal_type", "")
    currency = "AZN/ay" if deal == "rental" else "AZN"

    land = f"{listing['land_area_sot']} sot" if listing.get("land_area_sot") else ""
    area = f"{listing['area_m2']} m²" if listing.get("area_m2") else ""
    detail = " · ".join(filter(None, [listing.get("location"), listing.get("rooms"), area, land]))
    lat, lng = listing.get("lat"), listing.get("lng")
    gmaps = f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else ""

    lines = [
        listing["url"],
        f'{arrow} <b>Price change: {old_price:,} → {new_price:,} {currency} ({sign}{diff:,})</b>',
        f'📍 {detail}',
    ]

    unit = _unit_prices(listing)
    if unit:
        lines.append(f'💰 {unit}')

    repair = _repair_label(listing)
    if repair:
        lines.append(f'🔧 {repair}')

    bus_name = listing.get("_osrm_transport_name") or listing.get("nearest_transport_name")
    bus_min = listing.get("_osrm_walk_min") if "_osrm_walk_min" in listing else listing.get("walk_min_to_transport")
    if bus_min is not None:
        bus_str = f" · {bus_name}" if bus_name else ""
        lines.append(f'🚶 {bus_min:.0f} dəq piyada{bus_str}')

    label = _score_label(score)
    if label:
        lines.append(label)

    if gmaps:
        lines.append(f'📌 <a href="{gmaps}">Google Maps</a>')

    return "\n".join(lines)


def load_filters(root: Path) -> list[dict]:
    path = root / "notification_filters.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [filters] could not load filters.json: {exc}")
        return []


def check_and_notify(
    listing: dict,
    filters: list[dict],
    notify_fn: Any,
    all_listings: list = (),
    transport_stops: list = (),
    transport_lats: list = (),
) -> None:
    for f in filters:
        if matches(listing, f):
            score = compute_score(listing, list(all_listings)) if all_listings else None
            # Use OSRM for accurate walk time if coordinates and stops are available
            if listing.get("lat") and listing.get("lng") and transport_stops:
                osrm = _transport.osrm_nearest_walk(
                    listing["lat"], listing["lng"], transport_stops, transport_lats
                )
                if osrm:
                    listing["_osrm_walk_min"] = osrm["walk_min"]
                    listing["_osrm_transport_type"] = osrm["transport_type"]
                    listing["_osrm_transport_name"] = osrm["transport_name"]
            msg = format_message(listing, f.get("name", ""), score)
            # Clean up temporary OSRM fields
            for key in ("_osrm_walk_min", "_osrm_transport_type", "_osrm_transport_name"):
                listing.pop(key, None)
            notify_fn(msg)


def check_and_notify_price_change(
    listing: dict,
    old_price: int,
    filters: list[dict],
    notify_fn: Any,
    all_listings: list = (),
    transport_stops: list = (),
    transport_lats: list = (),
) -> None:
    for f in filters:
        if matches(listing, f):
            score = compute_score(listing, list(all_listings)) if all_listings else None
            if listing.get("lat") and listing.get("lng") and transport_stops:
                osrm = _transport.osrm_nearest_walk(
                    listing["lat"], listing["lng"], transport_stops, transport_lats
                )
                if osrm:
                    listing["_osrm_walk_min"] = osrm["walk_min"]
                    listing["_osrm_transport_type"] = osrm["transport_type"]
                    listing["_osrm_transport_name"] = osrm["transport_name"]
            msg = format_price_change_message(listing, old_price, score)
            for key in ("_osrm_walk_min", "_osrm_transport_type", "_osrm_transport_name"):
                listing.pop(key, None)
            notify_fn(msg)
