_BASE = "items_view=list&sorting=bumped_at+desc"
_ROOMS = ["1", "2", "3", "4", "5%2B"]  # 5%2B = "5+" URL-encoded
_BUILDING_TYPES = ["yeni-tikili", "kohne-tikili"]
_KUPCA = [True, False]  # has_bill_of_sale


def _room_url(base_path: str, room: str, kupca: bool | None = None) -> str:
    url = f"{base_path}?{_BASE}&room_ids%5B%5D={room}"
    if kupca is not None:
        url += f"&has_bill_of_sale={'true' if kupca else 'false'}"
    return url


def _plain_url(base_path: str) -> str:
    return f"{base_path}?{_BASE}"


# Apartments split by: building type (yeni/kohne) × bill-of-sale (kupca/nokupca) × room count
# Houses split by room count only.
# After scraping, main.py merges sub-files into the final category file.
CATEGORIES = [
    # ── Apartments (sale) — yeni/kohne × kupca/nokupca × 5 rooms ─────────────
    *[
        {
            "category": "apartment",
            "deal_type": "sale",
            "building": btype.replace("-tikili", ""),
            "kupca": kupca,
            "room": room,
            "url": _room_url(f"https://bina.az/baki/alqi-satqi/menziller/{btype}", room, kupca),
        }
        for btype in _BUILDING_TYPES
        for kupca in _KUPCA
        for room in _ROOMS
    ],

    # ── Apartments (rental) — yeni/kohne × kupca/nokupca × 5 rooms ───────────
    *[
        {
            "category": "apartment",
            "deal_type": "rental",
            "building": btype.replace("-tikili", ""),
            "kupca": kupca,
            "room": room,
            "url": _room_url(f"https://bina.az/baki/kiraye/menziller/{btype}", room, kupca),
        }
        for btype in _BUILDING_TYPES
        for kupca in _KUPCA
        for room in _ROOMS
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
