import pytest

from scraping.api import _parse_price_eur


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("€ 350.000 k.k.", 350_000),
        ("€ 1.250.000 v.o.n.", 1_250_000),
        ("€\xa0535.000 k.k.", 535_000),
        ("€ 1.250,50", 1_250),
        ("€ 425.000", 425_000),
        ("", None),
        ("Prijs op aanvraag", None),
    ],
)
def test_parse_price_eur(raw: str, expected: int | None) -> None:
    assert _parse_price_eur(raw) == expected
