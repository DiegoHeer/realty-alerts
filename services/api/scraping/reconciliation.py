from django.utils import timezone

from scraping.models import BagStatus, Listing, ListingStatus, Residence

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
    scraped_at. Idempotent: safe to call multiple times for the same residence."""
    resolved = list(Listing.objects.filter(residence=residence, bag_status=BagStatus.RESOLVED))
    if not resolved:
        return

    prices = [listing.price_eur for listing in resolved if listing.price_eur is not None]
    new_price_eur = min(prices) if prices else None
    new_status = max((listing.status for listing in resolved), key=lambda s: _STATUS_ORDER[ListingStatus(s)])
    scraped_ats = [listing.scraped_at for listing in resolved if listing.scraped_at is not None]
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

    if update_fields:
        residence.save(update_fields=update_fields)
