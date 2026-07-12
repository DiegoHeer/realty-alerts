from django.db.models import F, OuterRef, QuerySet, Subquery

from scraping.models import Listing, Residence

# Best-effort cover photo: freshest listing (any bag_status) with an image.
# nulls_last mirrors Residence._freshest_resolved_listing and reconciliation.
COVER_IMAGE = Subquery(
    Listing.objects.filter(residence=OuterRef("pk"))
    .exclude(image_url__isnull=True)
    .exclude(image_url="")
    .order_by(F("list_scraped_at").desc(nulls_last=True))
    .values("image_url")[:1]
)


def residence_summary_qs() -> QuerySet[Residence]:
    return Residence.objects.annotate(cover_image_url=COVER_IMAGE)
