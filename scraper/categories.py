_BASE = "items_view=list&sorting=bumped_at+desc"

CATEGORIES = [
    {"category": "apartment", "deal_type": "sale",   "url": f"https://bina.az/baki/alqi-satqi/menziller?{_BASE}"},
    {"category": "apartment", "deal_type": "rental", "url": f"https://bina.az/baki/kiraye/menziller?{_BASE}"},
    {"category": "house",     "deal_type": "sale",   "url": f"https://bina.az/baki/alqi-satqi/heyet-evleri?{_BASE}"},
    {"category": "house",     "deal_type": "rental", "url": f"https://bina.az/baki/kiraye/heyet-evleri?{_BASE}"},
    {"category": "commercial","deal_type": "sale",   "url": f"https://bina.az/baki/alqi-satqi/obyektler?{_BASE}"},
    {"category": "commercial","deal_type": "rental", "url": f"https://bina.az/baki/kiraye/obyektler?{_BASE}"},
    {"category": "office",    "deal_type": "sale",   "url": f"https://bina.az/baki/alqi-satqi/ofisler?{_BASE}"},
    {"category": "office",    "deal_type": "rental", "url": f"https://bina.az/baki/kiraye/ofisler?{_BASE}"},
    {"category": "garage",    "deal_type": "sale",   "url": f"https://bina.az/baki/alqi-satqi/qarajlar?{_BASE}"},
    {"category": "garage",    "deal_type": "rental", "url": f"https://bina.az/baki/kiraye/qarajlar?{_BASE}"},
    {"category": "land",      "deal_type": "sale",   "url": f"https://bina.az/baki/alqi-satqi/torpaq?{_BASE}"},
]
