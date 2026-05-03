import re

# Permissive base: street (lazy), space, number, optional trailing tokens.
# The trailing `rest` is parsed by `_split_suffix` into huisletter +
# huisnummertoevoeging — one regex can't disambiguate them cleanly because
# BAG treats them as two separate columns and titles like "Klaterweg 9 R A59"
# carry both.
_BASE_RE = re.compile(r"^\s*(?P<street>.+?)\s+(?P<number>\d+)\s*(?P<rest>.*?)\s*$")

# Dutch postcode: 4 digits + 2 uppercase letters, optional space.
_POSTCODE_RE = re.compile(r"\b(\d{4})\s?([A-Z]{2})\b")


def parse_dutch_address(text: str | None) -> tuple[str | None, int | None, str | None, str | None]:
    """Parse 'Klaterweg 9 R A59' → ('Klaterweg', 9, 'R', 'A59')."""
    if not text:
        return None, None, None, None
    match = _BASE_RE.match(text)
    if not match:
        return None, None, None, None
    street = match.group("street").strip()
    number = int(match.group("number"))
    huisletter, huisnummertoevoeging = _split_suffix(match.group("rest"))
    return street, number, huisletter, huisnummertoevoeging


def _split_suffix(rest: str) -> tuple[str | None, str | None]:
    # First token is the huisletter only when it's a single alphabetic character.
    # Anything longer or numeric collapses into huisnummertoevoeging — that
    # keeps "bis" and "12-3" working and still lets "R A59" split cleanly.
    tokens = [token for token in re.split(r"[-\s]+", rest.strip()) if token]
    if not tokens:
        return None, None
    if len(tokens[0]) == 1 and tokens[0].isalpha():
        remaining = " ".join(tokens[1:]) if len(tokens) > 1 else None
        return tokens[0], remaining
    return None, " ".join(tokens)


def parse_dutch_postcode(text: str | None) -> str | None:
    """Extract a Dutch postcode from text, normalised to 'NNNNAA' form (BAG canonical)."""
    if not text:
        return None
    match = _POSTCODE_RE.search(text)
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"
