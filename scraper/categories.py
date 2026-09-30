_BASE = "items_view=list&sorting=bumped_at+desc"
_ROOMS = ["1", "2", "3", "4", "5%2B"]  # 5%2B = "5+" URL-encoded
_BUILDING_TYPES = ["yeni-tikili", "kohne-tikili"]
_KUPCA = [True, False]  # has_bill_of_sale
_PRICE_SPLIT_ROOMS = {"3"}  # rooms that get an extra price-range split
_PRICE_BANDS = [("lo", None, 300_000), ("hi", 300_001, None)]  # (label, min, max)


def _room_url(base_path: str, room: str, kupca: bool | None = None, price_band: tuple | None = None) -> str:
    url = f"{base_path}?{_BASE}&room_ids%5B%5D={room}"
    if kupca is not None:
        url += f"&has_bill_of_sale={'true' if kupca else 'false'}"
    if price_band:
        _, pmin, pmax = price_band
        if pmin is not None:
            url += f"&price_from={pmin}"
        if pmax is not None:
            url += f"&price_to={pmax}"
    return url


def _plain_url(base_path: str) -> str:
    return f"{base_path}?{_BASE}"


# Apartments split by: building type (yeni/kohne) × bill-of-sale (kupca/nokupca) × room count
# Houses split by room count only.
# After scraping, main.py merges sub-files into the final category file.
CATEGORIES = [
    # ── Apartments (sale) — yeni/kohne × kupca/nokupca × 5 rooms ─────────────
    # Rooms in _PRICE_SPLIT_ROOMS are further split by price band.
    *[
        {
            "category": "apartment",
            "deal_type": "sale",
            "building": btype.replace("-tikili", ""),
            "kupca": kupca,
            "room": room,
            "price_band": band[0] if room in _PRICE_SPLIT_ROOMS else None,
            "url": _room_url(
                f"https://bina.az/baki/alqi-satqi/menziller/{btype}",
                room, kupca,
                band if room in _PRICE_SPLIT_ROOMS else None,
            ),
        }
        for btype in _BUILDING_TYPES
        for kupca in _KUPCA
        for room in _ROOMS
        for band in (_PRICE_BANDS if room in _PRICE_SPLIT_ROOMS else [(None, None, None)])
    ],

    # ── Apartments (rental) — yeni/kohne × kupca/nokupca × 5 rooms ───────────
    *[
        {
            "category": "apartment",
            "deal_type": "rental",
            "building": btype.replace("-tikili", ""),
            "kupca": kupca,
            "room": room,
            "price_band": band[0] if room in _PRICE_SPLIT_ROOMS else None,
            "url": _room_url(
                f"https://bina.az/baki/kiraye/menziller/{btype}",
                room, kupca,
                band if room in _PRICE_SPLIT_ROOMS else None,
            ),
        }
        for btype in _BUILDING_TYPES
        for kupca in _KUPCA
        for room in _ROOMS
        for band in (_PRICE_BANDS if room in _PRICE_SPLIT_ROOMS else [(None, None, None)])
    ],

    # ── Houses (sale) — one entry per room count ──────────────────────────────
    *[
        {
            "category": "house",
            "deal_type": "sale",
            "room": room,
            "url": _room_url("https://bina.az/baki/alqi-satqi/heyet-evleri", room),
        }
        for room in _ROOMS
    ],

    # ── Houses (rental) — one entry per room count ────────────────────────────
    *[
        {
            "category": "house",
            "deal_type": "rental",
            "room": room,
            "url": _room_url("https://bina.az/baki/kiraye/heyet-evleri", room),
        }
        for room in _ROOMS
    ],

    # ── Other categories (no room/building split) ─────────────────────────────
    {"category": "land",       "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/torpaq")},
    {"category": "commercial", "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/obyektler")},
    {"category": "commercial", "deal_type": "rental", "url": _plain_url("https://bina.az/baki/kiraye/obyektler")},
    {"category": "office",     "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/ofisler")},
    {"category": "office",     "deal_type": "rental", "url": _plain_url("https://bina.az/baki/kiraye/ofisler")},
    {"category": "garage",     "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/qarajlar")},
    {"category": "garage",     "deal_type": "rental", "url": _plain_url("https://bina.az/baki/kiraye/qarajlar")},
]

# Categories that require a post-scrape merge of sub-files
MERGE_TARGETS = {
    ("apartment", "sale"),
    ("apartment", "rental"),
    ("house", "sale"),
    ("house", "rental"),
}
