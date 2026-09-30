# Constants used by merge logic in main.py
_ROOMS = ["1", "2", "3", "4", "5%2B"]
_BUILDING_TYPES = ["yeni-tikili", "kohne-tikili"]
_KUPCA = [True, False]
_PRICE_BANDS = [("lo", None, 300_000), ("hi", 300_001, None)]
_PRICE_SPLIT_ROOMS = {"3"}

_BASE = "items_view=list&sorting=bumped_at+desc"
_AS = "https://bina.az/baki/alqi-satqi/menziller"
_AR = "https://bina.az/baki/kiraye/menziller"

CATEGORIES = [

    # ── Apartment sale — yeni tikili, kupca ───────────────────────────────────
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      True,
        "room":       "1",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=1&has_bill_of_sale=true",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      True,
        "room":       "2",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=2&has_bill_of_sale=true",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      True,
        "room":       "3",
        "price_band": "lo",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=true&price_to=300000",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      True,
        "room":       "3",
        "price_band": "hi",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=true&price_from=300001",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      True,
        "room":       "4",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=4&has_bill_of_sale=true",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      True,
        "room":       "5%2B",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=5%2B&has_bill_of_sale=true",
    },

    # ── Apartment sale — yeni tikili, nokupca ─────────────────────────────────
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      False,
        "room":       "1",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=1&has_bill_of_sale=false",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      False,
        "room":       "2",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=2&has_bill_of_sale=false",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      False,
        "room":       "3",
        "price_band": "lo",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=false&price_to=300000",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      False,
        "room":       "3",
        "price_band": "hi",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=false&price_from=300001",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      False,
        "room":       "4",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=4&has_bill_of_sale=false",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "yeni",
        "kupca":      False,
        "room":       "5%2B",
        "url":        f"{_AS}/yeni-tikili?{_BASE}&room_ids%5B%5D=5%2B&has_bill_of_sale=false",
    },

    # ── Apartment sale — kohne tikili, kupca ──────────────────────────────────
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      True,
        "room":       "1",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=1&has_bill_of_sale=true",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      True,
        "room":       "2",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=2&has_bill_of_sale=true",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      True,
        "room":       "3",
        "price_band": "lo",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=true&price_to=300000",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      True,
        "room":       "3",
        "price_band": "hi",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=true&price_from=300001",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      True,
        "room":       "4",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=4&has_bill_of_sale=true",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      True,
        "room":       "5%2B",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=5%2B&has_bill_of_sale=true",
    },

    # ── Apartment sale — kohne tikili, nokupca ────────────────────────────────
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      False,
        "room":       "1",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=1&has_bill_of_sale=false",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      False,
        "room":       "2",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=2&has_bill_of_sale=false",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      False,
        "room":       "3",
        "price_band": "lo",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=false&price_to=300000",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      False,
        "room":       "3",
        "price_band": "hi",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=3&has_bill_of_sale=false&price_from=300001",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      False,
        "room":       "4",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=4&has_bill_of_sale=false",
    },
    {
        "category":   "apartment",
        "deal_type":  "sale",
        "building":   "kohne",
        "kupca":      False,
        "room":       "5%2B",
        "url":        f"{_AS}/kohne-tikili?{_BASE}&room_ids%5B%5D=5%2B&has_bill_of_sale=false",
    },

    # ── Apartment rental — yeni tikili ────────────────────────────────────────
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "yeni",
        "room":      "1",
        "url":       f"{_AR}/yeni-tikili?{_BASE}&room_ids%5B%5D=1",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "yeni",
        "room":      "2",
        "url":       f"{_AR}/yeni-tikili?{_BASE}&room_ids%5B%5D=2",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "yeni",
        "room":      "3",
        "url":       f"{_AR}/yeni-tikili?{_BASE}&room_ids%5B%5D=3",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "yeni",
        "room":      "4",
        "url":       f"{_AR}/yeni-tikili?{_BASE}&room_ids%5B%5D=4",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "yeni",
        "room":      "5%2B",
        "url":       f"{_AR}/yeni-tikili?{_BASE}&room_ids%5B%5D=5%2B",
    },

    # ── Apartment rental — kohne tikili ───────────────────────────────────────
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "kohne",
        "room":      "1",
        "url":       f"{_AR}/kohne-tikili?{_BASE}&room_ids%5B%5D=1",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "kohne",
        "room":      "2",
        "url":       f"{_AR}/kohne-tikili?{_BASE}&room_ids%5B%5D=2",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "kohne",
        "room":      "3",
        "url":       f"{_AR}/kohne-tikili?{_BASE}&room_ids%5B%5D=3",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "kohne",
        "room":      "4",
        "url":       f"{_AR}/kohne-tikili?{_BASE}&room_ids%5B%5D=4",
    },
    {
        "category":  "apartment",
        "deal_type": "rental",
        "building":  "kohne",
        "room":      "5%2B",
        "url":       f"{_AR}/kohne-tikili?{_BASE}&room_ids%5B%5D=5%2B",
    },

    # ── House sale ────────────────────────────────────────────────────────────
    {
        "category":  "house",
        "deal_type": "sale",
        "room":      "1",
        "url":       f"https://bina.az/baki/alqi-satqi/heyet-evleri?{_BASE}&room_ids%5B%5D=1",
    },
    {
        "category":  "house",
        "deal_type": "sale",
        "room":      "2",
        "url":       f"https://bina.az/baki/alqi-satqi/heyet-evleri?{_BASE}&room_ids%5B%5D=2",
    },
    {
        "category":  "house",
        "deal_type": "sale",
        "room":      "3",
        "url":       f"https://bina.az/baki/alqi-satqi/heyet-evleri?{_BASE}&room_ids%5B%5D=3",
    },
    {
        "category":  "house",
        "deal_type": "sale",
        "room":      "4",
        "url":       f"https://bina.az/baki/alqi-satqi/heyet-evleri?{_BASE}&room_ids%5B%5D=4",
    },
    {
        "category":  "house",
        "deal_type": "sale",
        "room":      "5%2B",
        "url":       f"https://bina.az/baki/alqi-satqi/heyet-evleri?{_BASE}&room_ids%5B%5D=5%2B",
    },

    # ── House rental ──────────────────────────────────────────────────────────
    {
        "category":  "house",
        "deal_type": "rental",
        "room":      "1",
        "url":       f"https://bina.az/baki/kiraye/heyet-evleri?{_BASE}&room_ids%5B%5D=1",
    },
    {
        "category":  "house",
        "deal_type": "rental",
        "room":      "2",
        "url":       f"https://bina.az/baki/kiraye/heyet-evleri?{_BASE}&room_ids%5B%5D=2",
    },
    {
        "category":  "house",
        "deal_type": "rental",
        "room":      "3",
        "url":       f"https://bina.az/baki/kiraye/heyet-evleri?{_BASE}&room_ids%5B%5D=3",
    },
    {
        "category":  "house",
        "deal_type": "rental",
        "room":      "4",
        "url":       f"https://bina.az/baki/kiraye/heyet-evleri?{_BASE}&room_ids%5B%5D=4",
    },
    {
        "category":  "house",
        "deal_type": "rental",
        "room":      "5%2B",
        "url":       f"https://bina.az/baki/kiraye/heyet-evleri?{_BASE}&room_ids%5B%5D=5%2B",
    },

    # ── Other categories ──────────────────────────────────────────────────────
    {
        "category":  "land",
        "deal_type": "sale",
        "url":       f"https://bina.az/baki/alqi-satqi/torpaq?{_BASE}",
    },
    {
        "category":  "commercial",
        "deal_type": "sale",
        "url":       f"https://bina.az/baki/alqi-satqi/obyektler?{_BASE}",
    },
    {
        "category":  "commercial",
        "deal_type": "rental",
        "url":       f"https://bina.az/baki/kiraye/obyektler?{_BASE}",
    },
    {
        "category":  "office",
        "deal_type": "sale",
        "url":       f"https://bina.az/baki/alqi-satqi/ofisler?{_BASE}",
    },
    {
        "category":  "office",
        "deal_type": "rental",
        "url":       f"https://bina.az/baki/kiraye/ofisler?{_BASE}",
    },
    {
        "category":  "garage",
        "deal_type": "sale",
        "url":       f"https://bina.az/baki/alqi-satqi/qarajlar?{_BASE}",
    },
    {
        "category":  "garage",
        "deal_type": "rental",
        "url":       f"https://bina.az/baki/kiraye/qarajlar?{_BASE}",
    },
]

# Categories that require post-scrape merge of sub-files
MERGE_TARGETS = {
    ("apartment", "sale"),
    ("apartment", "rental"),
    ("house", "sale"),
    ("house", "rental"),
}
