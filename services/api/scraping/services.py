from django.db import transaction

from scraping.api import _parse_price_eur
from scraping.models import DeadListing, Listing, ListingUrl

# Subset of api._COMPLEMENT_FIELDS — DeadListing carries a strict subset of the
# Listing schema (no property_type / bedrooms / area_sqm).
_DEAD_LISTING_COMPLEMENT_FIELDS = (
    "title",
    "street",
    "house_number",
    "house_letter",
    "house_number_suffix",
    "postcode",
    "image_url",
)


class DeadListingPromotionError(ValueError):
    """Raised when a DeadListing cannot be promoted into a Listing."""


def promote_dead_listing(dead: DeadListing) -> Listing:
    """Promote a triaged DeadListing into a real Listing and delete the dead row.

    Reuses an existing Listing when its `bag_id` matches (e.g. same property
    listed on a second portal). Refuses if `dead.detail_url` is already attached
    to a Listing under a *different* `bag_id` — that's a re-wiring operation
    that needs explicit operator action.
    """
    if not dead.is_promotion_ready:
        missing = ", ".join(dead.missing_promotion_fields)
        raise DeadListingPromotionError(f"Not ready for promotion. Missing: {missing}")

    has_conflict = (
        ListingUrl.objects.filter(url=dead.detail_url).exclude(listing__bag_id=dead.bag_id).exists()
    )
    if has_conflict:
        raise DeadListingPromotionError(
            f"URL {dead.detail_url} is already attached to a different listing"
        )

    with transaction.atomic():
        listing, created = Listing.objects.get_or_create(
            bag_id=dead.bag_id,
            defaults=_listing_defaults_from_dead(dead),
        )
        if not created:
            _complement_listing_from_dead(listing, dead)

        ListingUrl.objects.get_or_create(
            url=dead.detail_url,
            defaults={"listing": listing, "website": dead.website},
        )
        dead.delete()

    return listing


def _listing_defaults_from_dead(dead: DeadListing) -> dict:
    return {
        "title": dead.title,
        "price": dead.price,
        "price_eur": _parse_price_eur(dead.price),
        "city": dead.city,
        "street": dead.street,
        "house_number": dead.house_number,
        "house_letter": dead.house_letter,
        "house_number_suffix": dead.house_number_suffix,
        "postcode": dead.postcode,
        "image_url": dead.image_url,
        "scraped_at": dead.scraped_at,
    }


def _complement_listing_from_dead(listing: Listing, dead: DeadListing) -> None:
    # Promotion is manual triage — the dead row may be older than the matched
    # listing's last scrape. Only refresh price/scraped_at when newer, unlike
    # the scraper ingest path which always overwrites.
    if dead.scraped_at > listing.scraped_at:
        listing.scraped_at = dead.scraped_at
        listing.price = dead.price
        listing.price_eur = _parse_price_eur(dead.price)

    for field in _DEAD_LISTING_COMPLEMENT_FIELDS:
        if getattr(listing, field) is None and (incoming := getattr(dead, field)) is not None:
            setattr(listing, field, incoming)
    listing.save()
