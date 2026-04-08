import pytest

from app.utils import parse_price_cents


@pytest.mark.parametrize(
    ("price_str", "expected"),
    [
        ("€ 350.000 k.k.", 350000),
        ("€ 1.250", 1250),
        ("€350.000", 350000),
        ("€ 2.500.000 k.k.", 2500000),
        ("€ 850 v.o.n.", 850),
    ],
)
def test_parse_dutch_prices(price_str: str, expected: int):
    assert parse_price_cents(price_str) == expected


def test_parse_unparseable_returns_none():
    assert parse_price_cents("Price on request") is None
    assert parse_price_cents("Prijs op aanvraag") is None
