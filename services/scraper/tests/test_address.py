import pytest

from scraper.address import parse_dutch_address, parse_dutch_postcode


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hoofdstraat 12", ("Hoofdstraat", 12, None, None)),
        ("Hoofdstraat 12A", ("Hoofdstraat", 12, "A", None)),
        ("Hoofdstraat 12 A", ("Hoofdstraat", 12, "A", None)),
        ("Hoofdstraat 12-A", ("Hoofdstraat", 12, "A", None)),
        ("Hoofdstraat 12bis", ("Hoofdstraat", 12, None, "bis")),
        ("Hoofdstraat 12-bis", ("Hoofdstraat", 12, None, "bis")),
        ("Hoofdstraat 12-3", ("Hoofdstraat", 12, None, "3")),
        ("Klaterweg 9 R A59", ("Klaterweg", 9, "R", "A59")),
        ("Parkweg 2 302", ("Parkweg", 2, None, "302")),
        ("Van der Heijdenstraat 12", ("Van der Heijdenstraat", 12, None, None)),
        ("2e Constantijn Huygensstraat 5", ("2e Constantijn Huygensstraat", 5, None, None)),
        ("Vigohof 19", ("Vigohof", 19, None, None)),
        ("Smaragdhorst 100", ("Smaragdhorst", 100, None, None)),
        ("Delftlaan 265", ("Delftlaan", 265, None, None)),
        ("  Hoofdstraat 12A  ", ("Hoofdstraat", 12, "A", None)),
    ],
)
def test_parse_dutch_address(text: str, expected: tuple[str | None, int | None, str | None, str | None]) -> None:
    assert parse_dutch_address(text) == expected


@pytest.mark.parametrize("text", ["", None, "no number", "Just a street"])
def test_parse_dutch_address_unparseable(text: str | None) -> None:
    assert parse_dutch_address(text) == (None, None, None, None)


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
