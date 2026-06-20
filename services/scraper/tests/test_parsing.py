import pytest

from scraper.parsing import parse_building_type, parse_construction_type


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Funda values
        ("Eengezinswoning, tussenwoning", "terraced"),
        ("Eengezinswoning, hoekwoning", "corner"),
        ("Eengezinswoning, 2-onder-1-kapwoning", "semi_detached"),
        ("Villa, vrijstaande woning", "detached"),
        ("Galerijflat (appartement)", "apartment"),
        ("Portiekflat (appartement)", "apartment"),
        # Pararius values
        ("Tussenwoning (rijtjeshuis), Eengezinswoning", "terraced"),
        ("Galerijflat", "apartment"),
        ("Bovenwoning, Appartement", "apartment"),
        ("Vrijstaande woning, Eengezinswoning", "detached"),
        ("Halfvrijstaande woning, Eengezinswoning", "semi_detached"),
        ("Geschakelde woning, Eengezinswoning", "semi_detached"),
        ("2-onder-1-kapwoning, Eengezinswoning", "semi_detached"),
        ("Tussenverdieping, Appartement", "apartment"),
        # VastgoedNL values
        ("tussenwoning", "terraced"),
        ("hoekwoning", "corner"),
        ("vrijstaande woning", "detached"),
        ("2-onder-1-kapwoning", "semi_detached"),
        ("tussenverdieping", "apartment"),
        ("portiekflat", "apartment"),
        # Edge cases
        ("Benedenwoning", "apartment"),
        ("Maisonnette", "apartment"),
        ("twee-onder-één-kapwoning", "semi_detached"),
        ("Villa", "detached"),
    ],
)
def test_parse_building_type(raw, expected):
    assert parse_building_type(raw) == expected


def test_parse_building_type_unknown_returns_none():
    assert parse_building_type("woonboot") is None


def test_parse_building_type_empty_returns_none():
    assert parse_building_type("") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Bestaande bouw", "bestaande_bouw"),
        ("bestaande bouw", "bestaande_bouw"),
        ("Nieuwbouw", "nieuwbouw"),
        ("nieuwbouw", "nieuwbouw"),
        ("BESTAANDE BOUW", "bestaande_bouw"),
    ],
)
def test_parse_construction_type(raw, expected):
    assert parse_construction_type(raw) == expected


def test_parse_construction_type_unknown_returns_none():
    assert parse_construction_type("verbouwing") is None


def test_parse_construction_type_empty_returns_none():
    assert parse_construction_type("") is None
