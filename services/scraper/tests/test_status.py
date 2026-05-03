import pytest
from bs4 import BeautifulSoup

from scraper.enums import ListingStatus
from scraper.status import detect_status


def _card(html: str):
    return BeautifulSoup(f"<div>{html}</div>", "html.parser").div


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        # Funda-style: status as bare text in the card root.
        ("<span>Nieuw</span> | Madeliefstraat 5 | 1706 AN Heerhugowaard | € 720.000 k.k.", ListingStatus.NEW),
        ("<span>Verkocht</span> | Madeliefstraat 5 | 1706 AN Heerhugowaard | € 720.000 k.k.", ListingStatus.SOLD),
        (
            "<span>Verkocht onder voorbehoud</span> | Madeliefstraat 5 | 1706 AN Heerhugowaard | € 720.000 k.k.",
            ListingStatus.SALE_PENDING,
        ),
        # Pararius-style: badge in a labelled span.
        ('<span class="listing-label listing-label--new">Nieuw</span>', ListingStatus.NEW),
        ('<span class="listing-label listing-label--sold">Verkocht</span>', ListingStatus.SOLD),
        # VastgoedNL-style: badge in a div.label.
        ('<div class="label">Nieuw</div>', ListingStatus.NEW),
        ('<div class="label">Verkocht</div>', ListingStatus.SOLD),
        ('<div class="label">Verkocht onder voorbehoud</div>', ListingStatus.SALE_PENDING),
        # No status text → default NEW (most cards on a search-results page).
        ("<span>Bergamotte 3</span> | 6846 HP Arnhem | € 695.000 k.k.", ListingStatus.NEW),
    ],
)
def test_detect_status_recognises_portal_badges(html: str, expected: ListingStatus) -> None:
    assert detect_status(_card(html)) == expected


def test_detect_status_prefers_sale_pending_over_sold() -> None:
    # The phrase "verkocht onder voorbehoud" contains "verkocht" — the longer
    # phrase must win so a sale-pending listing isn't downgraded to sold.
    card = _card('<div class="label">Verkocht onder voorbehoud</div>')
    assert detect_status(card) == ListingStatus.SALE_PENDING


def test_detect_status_ignores_substring_matches() -> None:
    # `nieuwbouw` (newly built) and arbitrary copy mentioning addresses
    # must not trigger SOLD via a partial `verkocht` match.
    card = _card("<span>Nieuwbouw te koop in Verkochtstraat 5</span>")
    # The street name `Verkochtstraat` contains `verkocht` as a substring but
    # is bounded by `straat`, so `\bverkocht\b` does NOT match.
    assert detect_status(card) == ListingStatus.NEW


def test_detect_status_is_case_insensitive() -> None:
    card = _card("<span>VERKOCHT</span>")
    assert detect_status(card) == ListingStatus.SOLD
