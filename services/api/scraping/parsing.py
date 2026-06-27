import re


def parse_build_year(construction_period: str | None) -> int | None:
    """First 4-digit run in a free-form construction-period string (so a range
    like '1920-1940' yields the start year). None if absent or unparseable."""
    if not construction_period:
        return None
    match = re.search(r"\d{4}", construction_period)
    return int(match.group()) if match else None
