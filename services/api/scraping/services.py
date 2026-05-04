from django.db import transaction

from scraping.api import _parse_price_eur
from scraping.models import DeadResidence, Listing, Residence

# Subset of api._COMPLEMENT_FIELDS — DeadResidence carries a strict subset of
# the Residence schema (no property_type / bedrooms / area_sqm).
_DEAD_RESIDENCE_COMPLEMENT_FIELDS = (
    "title",
    "street",
    "house_number",
    "house_letter",
    "house_number_suffix",
    "postcode",
    "image_url",
)


class DeadResidencePromotionError(ValueError):
    """Raised when a DeadResidence cannot be promoted into a Residence."""


def promote_dead_residence(dead: DeadResidence) -> Residence:
    """Promote a triaged DeadResidence into a real Residence and delete the dead row.

    Reuses an existing Residence when its `bag_id` matches (e.g. same property
    listed on a second portal). Refuses if `dead.detail_url` is already
    attached to a Residence under a *different* `bag_id` — that's a re-wiring
    operation that needs explicit operator action.
    """
    if not dead.is_promotion_ready:
        missing = ", ".join(dead.missing_promotion_fields)
        raise DeadResidencePromotionError(f"Not ready for promotion. Missing: {missing}")

    has_conflict = Listing.objects.filter(url=dead.detail_url).exclude(residence__bag_id=dead.bag_id).exists()
    if has_conflict:
        raise DeadResidencePromotionError(f"URL {dead.detail_url} is already attached to a different residence")

    with transaction.atomic():
        residence, created = Residence.objects.get_or_create(
            bag_id=dead.bag_id,
            defaults=_residence_defaults_from_dead(dead),
        )
        if not created:
            _complement_residence_from_dead(residence, dead)

        Listing.objects.get_or_create(
            url=dead.detail_url,
            defaults={"residence": residence, "website": dead.website},
        )
        dead.delete()

    return residence


def _residence_defaults_from_dead(dead: DeadResidence) -> dict:
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


def _complement_residence_from_dead(residence: Residence, dead: DeadResidence) -> None:
    # Promotion is manual triage — the dead row may be older than the matched
    # residence's last scrape. Only refresh price/scraped_at when newer, unlike
    # the scraper ingest path which always overwrites.
    if dead.scraped_at > residence.scraped_at:
        residence.scraped_at = dead.scraped_at
        residence.price = dead.price
        residence.price_eur = _parse_price_eur(dead.price)

    for field in _DEAD_RESIDENCE_COMPLEMENT_FIELDS:
        if getattr(residence, field) is None and (incoming := getattr(dead, field)) is not None:
            setattr(residence, field, incoming)
    residence.save()
