from datetime import UTC, datetime

from django.utils import timezone

from scraping.models import BagStatus, Listing, ListingStatus, Residence
from scraping.parsing import parse_build_year

# Ordering for "most-advanced" status rollup. SOLD beats SALE_PENDING beats NEW —
# once any portal marks the property gone, we treat the residence as gone.
_STATUS_ORDER = {
    ListingStatus.NEW: 0,
    ListingStatus.SALE_PENDING: 1,
    ListingStatus.SOLD: 2,
}


def reconcile_residence(residence: Residence) -> None:
    """Recompute Residence's stored aggregates from its resolved Listings.

    Run this after every Listing create/update that affects price, status, or
    list_scraped_at. Idempotent: safe to call multiple times for the same residence."""
    resolved = list(Listing.objects.filter(residence=residence, bag_status=BagStatus.RESOLVED))
    if not resolved:
        return

    prices = [listing.price_eur for listing in resolved if listing.price_eur is not None]
    new_price_eur = min(prices) if prices else None
    new_status = max((listing.status for listing in resolved), key=lambda s: _STATUS_ORDER[ListingStatus(s)])
    scraped_ats = [listing.list_scraped_at for listing in resolved if listing.list_scraped_at is not None]
    new_last_scraped_at = max(scraped_ats) if scraped_ats else None

    update_fields: list[str] = []
    if residence.current_price_eur != new_price_eur:
        residence.current_price_eur = new_price_eur
        update_fields.append("current_price_eur")
    if residence.current_status != new_status:
        residence.current_status = new_status
        residence.status_changed_at = timezone.now()
        update_fields.extend(("current_status", "status_changed_at"))
    if residence.last_scraped_at != new_last_scraped_at:
        residence.last_scraped_at = new_last_scraped_at
        update_fields.append("last_scraped_at")

    _reconcile_building_and_construction(residence, resolved, update_fields)
    _reconcile_listing_attributes(residence, resolved, update_fields)

    if update_fields:
        residence.save(update_fields=update_fields)


def _reconcile_building_and_construction(
    residence: Residence, resolved: list[Listing], update_fields: list[str]
) -> None:
    _min_ts = datetime.min.replace(tzinfo=UTC)
    by_freshness = sorted(resolved, key=lambda listing: listing.list_scraped_at or _min_ts, reverse=True)

    if freshest_ct := next((listing for listing in by_freshness if listing.construction_type), None):
        new_construction_type = freshest_ct.construction_type
    else:
        new_construction_type = None
    if residence.construction_type != new_construction_type:
        residence.construction_type = new_construction_type
        update_fields.append("construction_type")

    if residence.building_type is None:
        if freshest_bt := next((listing for listing in by_freshness if listing.building_type), None):
            residence.building_type = freshest_bt.building_type
            update_fields.append("building_type")


def _reconcile_listing_attributes(
    residence: Residence, resolved: list[Listing], update_fields: list[str]
) -> None:
    """Denormalize the freshest resolved Listing's display attributes onto the
    Residence as a coherent set — the same listing that drives title/image_url.
    Values are always refreshed; a null on the freshest listing yields a null
    here (never borrowed from an older listing)."""
    _min_ts = datetime.min.replace(tzinfo=UTC)
    freshest = max(resolved, key=lambda listing: listing.list_scraped_at or _min_ts)
    new_values = {
        "bedroom_count": freshest.bedroom_count,
        "bathroom_count": freshest.bathroom_count,
        "surface_area_m2": freshest.surface_area_m2,
        "build_year": parse_build_year(freshest.construction_period),
    }
    for field, value in new_values.items():
        if getattr(residence, field) != value:
            setattr(residence, field, value)
            update_fields.append(field)
