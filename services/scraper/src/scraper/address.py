import re

# Pattern: <street> <number><optional separator><optional suffix>
# - Street is lazy so the LAST number-like token wins as huisnummer.
# - Suffix accepts a letter group (optionally trailing digits, e.g. "A1"),
#   the literal "bis", or pure digits (e.g. "12-3" → number=12, suffix="3").
_ADDRESS_RE = re.compile(
    r"^\s*(?P<street>.+?)\s+(?P<number>\d+)"
    r"(?:[-\s]*(?P<suffix>bis|[A-Za-z]+\d*|\d+))?"
    r"\s*$",
    re.IGNORECASE,
)

# Dutch postcode: 4 digits + 2 uppercase letters, optional space.
_POSTCODE_RE = re.compile(r"\b(\d{4})\s?([A-Z]{2})\b")


def parse_dutch_address(text: str | None) -> tuple[str | None, int | None, str | None]:
    """Parse 'Hoofdstraat 12A' → ('Hoofdstraat', 12, 'A')."""
    if not text:
        return None, None, None
    match = _ADDRESS_RE.match(text)
    if not match:
        return None, None, None
    street = match.group("street").strip()
    number = int(match.group("number"))
    suffix_raw = match.group("suffix")
    suffix = suffix_raw.strip() if suffix_raw else None
    return street, number, suffix


def parse_dutch_postcode(text: str | None) -> str | None:
    """Extract a Dutch postcode from text, normalised to 'NNNN AA' form."""
    if not text:
        return None
    match = _POSTCODE_RE.search(text)
    if not match:
        return None
    return f"{match.group(1)} {match.group(2)}"
