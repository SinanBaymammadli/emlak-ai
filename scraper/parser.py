import re

_RENTAL_PERIOD = re.compile(r"^/?(ay|gün|həftə|il)$", re.IGNORECASE)


def _clean_lines(text: str) -> list[str]:
    lines = [l.strip().replace("\xa0", " ") for l in text.splitlines() if l.strip()]
    # Remove standalone rental period tokens like "/ay" or "gün" that appear as
    # separate lines on rental cards — they would otherwise be mistaken for location.
    return [l for l in lines if not _RENTAL_PERIOD.match(l)]


def _parse_price(raw: str) -> int | None:
    # Strip rental suffix before extracting digits
    raw = re.sub(r"/ay.*", "", raw, flags=re.IGNORECASE)
    digits = re.sub(r"\D", "", raw)
    return int(digits) if digits else None


def parse_card_text(text: str) -> dict:
    """Parse apartment/house card innerText. Returns price, location, rooms, area_m2, floor, is_agency."""
    lines = _clean_lines(text)

    # Detect agency listing before stripping non-digit lines
    is_agency = any("agentlik" in l.lower() for l in lines if not re.search(r"\d", l))

    while lines and not re.search(r"\d", lines[0]):
        lines.pop(0)

    price = _parse_price(lines[0]) if lines else None
    location = lines[1] if len(lines) > 1 else ""
    rooms = area_m2 = floor = ""
    for line in lines[2:]:
        if "otaqlı" in line and not rooms:
            rooms = line
        elif "m²" in line and not area_m2:
            area_m2 = line
        elif "mərtəbə" in line and not floor:
            floor = line
    return {
        "price": price,
        "location": location,
        "rooms": rooms,
        "area_m2": area_m2,
        "floor": floor or None,
        "is_agency": is_agency,
    }


def parse_land_card_text(text: str) -> dict:
    """Parse land (torpaq) card innerText. Returns price, location, land_area_sot, is_agency."""
    lines = _clean_lines(text)
    is_agency = any("agentlik" in l.lower() for l in lines if not re.search(r"\d", l))
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
    return {
        "price": price,
        "location": location,
        "land_area_sot": land_area_sot,
        "floor": None,
        "is_agency": is_agency,
    }


def parse_commercial_card_text(text: str) -> dict:
    """Parse commercial/office card innerText. Returns price, location, area_m2, floor, is_agency."""
    lines = _clean_lines(text)
    is_agency = any("agentlik" in l.lower() for l in lines if not re.search(r"\d", l))
    while lines and not re.search(r"\d", lines[0]):
        lines.pop(0)

    price = _parse_price(lines[0]) if lines else None
    location = lines[1] if len(lines) > 1 else ""
    area_m2 = floor = ""
    for line in lines[2:]:
        if "m²" in line and not area_m2:
            area_m2 = line
        elif "mərtəbə" in line and not floor:
            floor = line
    return {
        "price": price,
        "location": location,
        "area_m2": area_m2,
        "floor": floor or None,
        "is_agency": is_agency,
    }


PARSERS = {
    "apartment": parse_card_text,
    "house": parse_card_text,
    "land": parse_land_card_text,
    "commercial": parse_commercial_card_text,
    "office": parse_commercial_card_text,
}
