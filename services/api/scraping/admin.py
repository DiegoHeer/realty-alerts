import httpx
from django.contrib import admin, messages
from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from scraping.resolvers import BagLookupFailure, ChainedResolver, create_resolver
from scraping.resolvers.types import AddressQuery
from scraping.models import BagStatus, DetailScrapeRun, DetailScrapeRunStatus, Listing, ListScrapeRun, Residence
from scraping.tasks import dispatch_detail_scrape
from scraping.reconciliation import reconcile_residence

_FAILED_BAG_STATUSES = frozenset(
    {
        BagStatus.PARSE_FAILED,
        BagStatus.MISSING_ADDRESS,
        BagStatus.BAG_NO_MATCH,
        BagStatus.BAG_AMBIGUOUS,
    }
)

_FAILURE_TO_BAG_STATUS = {
    BagLookupFailure.MISSING_ADDRESS: BagStatus.MISSING_ADDRESS,
    BagLookupFailure.NO_MATCH: BagStatus.BAG_NO_MATCH,
    BagLookupFailure.AMBIGUOUS: BagStatus.BAG_AMBIGUOUS,
}

_FAILURE_MESSAGES = {
    BagLookupFailure.MISSING_ADDRESS: "still missing required address fields",
    BagLookupFailure.NO_MATCH: "BAG lookup found no match for the corrected address",
    BagLookupFailure.AMBIGUOUS: "BAG lookup still returned multiple ambiguous results",
}


def _promote_listing(listing: Listing, resolver: ChainedResolver) -> str | None:
    """Returns None on success, or an error message string on failure."""
    if listing.bag_status not in _FAILED_BAG_STATUSES:
        return f"skipped — bag_status is {listing.bag_status}, not a failed state"

    try:
        result = resolver.resolve(
            AddressQuery(
                postcode=listing.postcode,
                house_number=listing.house_number,
                house_letter=listing.house_letter,
                house_number_suffix=listing.house_number_suffix,
                street=listing.street,
                city=listing.city,
            )
        )
    except httpx.HTTPError as exc:
        return f"BAG API error — {exc}"

    if isinstance(result, BagLookupFailure):
        listing.bag_status = _FAILURE_TO_BAG_STATUS[result]
        listing.bag_failure_reason = f"BAG lookup: {result.value}"
        listing.save(update_fields=["bag_status", "bag_failure_reason"])
        return _FAILURE_MESSAGES[result]

    residence, _ = Residence.objects.get_or_create(
        bag_id=result.bag_id,
        defaults={
            "city": result.city,
            "street": result.street,
            "house_number": result.house_number,
            "house_letter": result.house_letter,
            "house_number_suffix": result.house_number_suffix,
            "postcode": result.postcode,
            "current_status": listing.status,
            "status_changed_at": timezone.now(),
            "last_scraped_at": listing.list_scraped_at,
        },
    )
    listing.residence = residence
    listing.bag_status = BagStatus.RESOLVED
    listing.bag_resolved_at = timezone.now()
    listing.bag_failure_reason = ""
    listing.save(update_fields=["residence", "bag_status", "bag_resolved_at", "bag_failure_reason"])
    reconcile_residence(residence)
    return None


@admin.action(description="Promote selected listings")
def promote_listings(modeladmin, request, queryset):
    succeeded = 0
    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        for listing in queryset:
            error = _promote_listing(listing, resolver)
            if error is None:
                succeeded += 1
            else:
                modeladmin.message_user(
                    request,
                    f"Listing {listing.pk} ({listing.url}): {error}",
                    messages.WARNING,
                )
    if succeeded:
        modeladmin.message_user(
            request,
            f"Successfully promoted {succeeded} listing(s).",
            messages.SUCCESS,
        )


def _dispatch_detail_scrapes(listings) -> int:
    dispatched = 0
    for listing in listings:
        run = DetailScrapeRun.objects.create(
            listing=listing,
            website=listing.website,
            status=DetailScrapeRunStatus.DISPATCHED,
        )
        dispatch_detail_scrape.delay(listing_id=listing.pk, detail_scrape_run_id=run.pk)
        dispatched += 1
    return dispatched


@admin.action(description="Scrape details for selected listings")
def scrape_details(modeladmin, request, queryset):
    dispatched = _dispatch_detail_scrapes(queryset)
    modeladmin.message_user(
        request,
        f"Dispatched detail scrape for {dispatched} listing(s).",
        messages.SUCCESS,
    )


@admin.action(description="Scrape details for selected residences")
def scrape_residence_details(modeladmin, request, queryset):
    listings = Listing.objects.filter(residence__in=queryset)
    dispatched = _dispatch_detail_scrapes(listings)
    modeladmin.message_user(
        request,
        f"Dispatched detail scrape for {dispatched} listing(s) across {queryset.count()} residence(s).",
        messages.SUCCESS,
    )


class ListingInline(admin.TabularInline):
    model = Listing
    extra = 0
    readonly_fields = ("url", "website", "bag_status", "first_seen_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Residence)
class ResidenceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bag_id",
        "city",
        "street",
        "house_number",
        "postcode",
        "current_price_eur",
        "current_status",
        "listing_count",
        "last_scraped_at",
    )
    list_filter = ("current_status", "city")
    # `title` lives on per-portal Listing now, so search joins through the
    # reverse FK rather than a Residence column.
    search_fields = ("listings__title", "street", "postcode", "bag_id")
    ordering = ("-last_scraped_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (ListingInline,)
    actions = [scrape_residence_details]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(listing_count=Count("listings"))

    @admin.display(description="Listings", ordering="listing_count")
    def listing_count(self, obj):
        return obj.listing_count


class BagStatusListFilter(admin.SimpleListFilter):
    title = "BAG status"
    parameter_name = "bag_status_group"

    def lookups(self, request, model_admin):
        return (
            ("resolved", "Resolved"),
            ("pending", "Pending"),
            ("failed", "Failed (any)"),
        )

    def queryset(self, request, queryset):
        if self.value() == "resolved":
            return queryset.filter(bag_status=BagStatus.RESOLVED)
        if self.value() == "pending":
            return queryset.filter(bag_status=BagStatus.PENDING)
        if self.value() == "failed":
            return queryset.filter(bag_status__in=_FAILED_BAG_STATUSES)
        return queryset


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "url",
        "website",
        "residence",
        "bag_status",
        "bag_resolved_at",
        "first_seen_at",
    )
    list_filter = (BagStatusListFilter, "website")
    search_fields = ("url", "title", "postcode", "street")
    ordering = ("-first_seen_at",)
    readonly_fields = ("first_seen_at",)
    actions = [promote_listings, scrape_details]


@admin.register(ListScrapeRun)
class ListScrapeRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "website",
        "status",
        "started_at",
        "finished_at",
        "listings_found",
        "new_listings_count",
        "duration_seconds",
    )
    list_filter = ("website", "status")
    ordering = ("-started_at",)


@admin.register(DetailScrapeRun)
class DetailScrapeRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "listing",
        "website",
        "status",
        "dispatched_at",
        "finished_at",
        "duration_seconds",
    )
    list_filter = ("website", "status")
    ordering = ("-dispatched_at",)
    readonly_fields = (
        "listing",
        "website",
        "status",
        "dispatched_at",
        "finished_at",
        "error_message",
        "duration_seconds",
    )
