import re

from bs4 import Tag

from scraper.enums import ListingStatus

# `verkocht onder voorbehoud` is checked first because it's a superstring of
# `verkocht`. Word-boundary on the bare `verkocht` keeps neighboring tokens
# (e.g. `nieuwbouw`, addresses) from triggering false matches.
_SALE_PENDING_PHRASE = "verkocht onder voorbehoud"
_SOLD_PATTERN = re.compile(r"\bverkocht\b")


def detect_status(card: Tag) -> ListingStatus:
    text = card.get_text(" ", strip=True).lower()
    if _SALE_PENDING_PHRASE in text:
        return ListingStatus.SALE_PENDING
    if _SOLD_PATTERN.search(text):
        return ListingStatus.SOLD
    return ListingStatus.NEW
