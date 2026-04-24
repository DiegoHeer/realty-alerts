from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_price_cents(price_str: str) -> int | None:
    """Extract numeric value from Dutch price strings like '€ 350.000 k.k.' or '€ 1.250'."""
    cleaned = price_str.replace("€", "").replace("k.k.", "").replace("v.o.n.", "").replace(" ", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return None
