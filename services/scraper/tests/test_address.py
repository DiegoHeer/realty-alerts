import pytest

from scraper.address import parse_dutch_address, parse_dutch_postcode


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hoofdstraat 12", ("Hoofdstraat", 12, None)),
        ("Hoofdstraat 12A", ("Hoofdstraat", 12, "A")),
        ("Hoofdstraat 12 A", ("Hoofdstraat", 12, "A")),
        ("Hoofdstraat 12-A", ("Hoofdstraat", 12, "A")),
        ("Hoofdstraat 12bis", ("Hoofdstraat", 12, "bis")),
        ("Hoofdstraat 12-bis", ("Hoofdstraat", 12, "bis")),
        ("Hoofdstraat 12-3", ("Hoofdstraat", 12, "3")),
        ("Van der Heijdenstraat 12", ("Van der Heijdenstraat", 12, None)),
        ("2e Constantijn Huygensstraat 5", ("2e Constantijn Huygensstraat", 5, None)),
        ("Vigohof 19", ("Vigohof", 19, None)),
        ("Smaragdhorst 100", ("Smaragdhorst", 100, None)),
        ("Delftlaan 265", ("Delftlaan", 265, None)),
        ("  Hoofdstraat 12A  ", ("Hoofdstraat", 12, "A")),
    ],
)
def test_parse_dutch_address(text: str, expected: tuple[str | None, int | None, str | None]) -> None:
    assert parse_dutch_address(text) == expected


@pytest.mark.parametrize("text", ["", None, "no number", "Just a street"])
def test_parse_dutch_address_unparseable(text: str | None) -> None:
    assert parse_dutch_address(text) == (None, None, None)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3067 ZV Rotterdam (Oosterflank)", "3067ZV"),
        ("2024 CB Haarlem", "2024CB"),
        ("3067ZV Rotterdam", "3067ZV"),
        ("Living at 1234 AB Amsterdam", "1234AB"),
    ],
)
def test_parse_dutch_postcode(text: str, expected: str) -> None:
    assert parse_dutch_postcode(text) == expected


@pytest.mark.parametrize("text", ["", None, "Rotterdam", "1234"])
def test_parse_dutch_postcode_missing(text: str | None) -> None:
    assert parse_dutch_postcode(text) is None
