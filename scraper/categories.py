_BASE = "items_view=list&sorting=bumped_at+desc"
_ROOMS = ["1", "2", "3", "4", "5%2B"]  # 5%2B = "5+" URL-encoded


def _room_url(base_path: str, room: str) -> str:
    return f"{base_path}?{_BASE}&room_ids%5B%5D={room}"


def _plain_url(base_path: str) -> str:
    return f"{base_path}?{_BASE}"


# Apartments and houses are split by room count to keep each scrape manageable.
# After scraping, main.py merges the room sub-files into the final category file.
CATEGORIES = [
    # ── Apartments (sale) — one entry per room count ──────────────────────────
    *[
        {
            "category": "apartment",
            "deal_type": "sale",
            "room": room,
            "url": _room_url("https://bina.az/baki/alqi-satqi/menziller", room),
        }
        for room in _ROOMS
    ],

    # ── Apartments (rental) — one entry per room count ────────────────────────
    *[
        {
            "category": "apartment",
            "deal_type": "rental",
            "room": room,
            "url": _room_url("https://bina.az/baki/kiraye/menziller", room),
        }
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

    # ── Other categories (no room split) ──────────────────────────────────────
    {"category": "land",       "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/torpaq")},
    {"category": "commercial", "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/obyektler")},
    {"category": "commercial", "deal_type": "rental", "url": _plain_url("https://bina.az/baki/kiraye/obyektler")},
    {"category": "office",     "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/ofisler")},
    {"category": "office",     "deal_type": "rental", "url": _plain_url("https://bina.az/baki/kiraye/ofisler")},
    {"category": "garage",     "deal_type": "sale",   "url": _plain_url("https://bina.az/baki/alqi-satqi/qarajlar")},
    {"category": "garage",     "deal_type": "rental", "url": _plain_url("https://bina.az/baki/kiraye/qarajlar")},
]

# Categories that require a post-scrape merge of room sub-files
MERGE_TARGETS = {
    ("apartment", "sale"),
    ("apartment", "rental"),
    ("house", "sale"),
    ("house", "rental"),
}
