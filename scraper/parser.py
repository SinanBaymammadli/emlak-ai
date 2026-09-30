import re


def _clean_lines(text: str) -> list[str]:
    return [l.strip().replace("\xa0", " ") for l in text.splitlines() if l.strip()]


def _parse_price(raw: str) -> int | None:
    # Strip rental suffix before extracting digits
    raw = re.sub(r"/ay.*", "", raw, flags=re.IGNORECASE)
    digits = re.sub(r"\D", "", raw)
    return int(digits) if digits else None


def parse_card_text(text: str) -> dict:
    """Parse apartment/house card innerText. Returns price, location, rooms, area_m2."""
    lines = _clean_lines(text)
    while lines and not re.search(r"\d", lines[0]):
        lines.pop(0)

    price = _parse_price(lines[0]) if lines else None
    location = lines[1] if len(lines) > 1 else ""
    rooms = area_m2 = ""
    for line in lines[2:]:
        if "otaqlı" in line and not rooms:
            rooms = line
        elif "m²" in line and not area_m2:
            area_m2 = line
    return {"price": price, "location": location, "rooms": rooms, "area_m2": area_m2}


def parse_land_card_text(text: str) -> dict:
    """Parse land (torpaq) card innerText. Returns price, location, land_area_sot."""
    lines = _clean_lines(text)
    while lines and not re.search(r"\d", lines[0]):
        lines.pop(0)

    price = _parse_price(lines[0]) if lines else None
    location = lines[1] if len(lines) > 1 else ""
    land_area_sot = None
    for line in lines[2:]:
        if "sot" in line:
            try:
                land_area_sot = float(re.sub(r"[^\d.,]", "", line).replace(",", "."))
            except ValueError:
                pass
            break
    return {"price": price, "location": location, "land_area_sot": land_area_sot}


def parse_commercial_card_text(text: str) -> dict:
    """Parse commercial/office card innerText. Returns price, location, area_m2."""
    lines = _clean_lines(text)
    while lines and not re.search(r"\d", lines[0]):
        lines.pop(0)

    price = _parse_price(lines[0]) if lines else None
    location = lines[1] if len(lines) > 1 else ""
    area_m2 = ""
    for line in lines[2:]:
        if "m²" in line and not area_m2:
            area_m2 = line
    return {"price": price, "location": location, "area_m2": area_m2}


PARSERS = {
    "apartment": parse_card_text,
    "house": parse_card_text,
    "land": parse_land_card_text,
    "commercial": parse_commercial_card_text,
    "office": parse_commercial_card_text,
}
