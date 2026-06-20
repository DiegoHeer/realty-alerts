from loguru import logger

_BUILDING_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("tussenwoning", "terraced"),
    ("hoekwoning", "corner"),
    ("2-onder-1-kap", "semi_detached"),
    ("twee-onder-één-kap", "semi_detached"),
    ("halfvrijstaande", "semi_detached"),
    ("geschakelde", "semi_detached"),
    ("maisonnette", "apartment"),
    ("benedenwoning", "apartment"),
    ("bovenwoning", "apartment"),
    ("tussenverdieping", "apartment"),
    ("portiek", "apartment"),
    ("galerij", "apartment"),
    ("flat", "apartment"),
    ("appartement", "apartment"),
    ("vrijstaande woning", "detached"),
    ("vrijstaand", "detached"),
    ("villa", "detached"),
]


def parse_building_type(raw: str) -> str | None:
    if not raw:
        return None
    lowered = raw.strip().lower()
    for keyword, building_type in _BUILDING_TYPE_KEYWORDS:
        if keyword in lowered:
            return building_type
    logger.warning("Unknown building type: {!r}", raw)
    return None


def parse_construction_type(raw: str) -> str | None:
    if not raw:
        return None
    lowered = raw.strip().lower()
    if "bestaande bouw" in lowered:
        return "bestaande_bouw"
    if "nieuwbouw" in lowered:
        return "nieuwbouw"
    logger.warning("Unknown construction type: {!r}", raw)
    return None
