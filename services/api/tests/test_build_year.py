import pytest

from scraping.parsing import parse_build_year


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1973", 1973),
        ("1920-1940", 1920),  # range -> start year
        ("Bouwjaar 1998", 1998),
        ("circa 2001, gerenoveerd 2015", 2001),  # first match wins
        (None, None),
        ("", None),
        ("onbekend", None),
        ("jaren 30", None),  # no 4-digit run
    ],
)
def test_parse_build_year(value, expected):
    assert parse_build_year(value) == expected
