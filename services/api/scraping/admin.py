import httpx
from django.contrib import admin, messages
from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from django.http import HttpResponseRedirect
from django.urls import path, reverse

from scraping.resolvers import BagLookupFailure, ChainedResolver, create_resolver
from scraping.services import cbs
from scraping.resolvers.types import AddressQuery
from scraping.models import (
    BagStatus,
    City,
    DetailScrapeRun,
    District,
    Listing,
    ListScrapeRun,
    Neighborhood,
    Residence,
)
from scraping.tasks import (
    _dispatch_detail_scrapes,
    enrich_building_details,
    enrich_location,
    enrich_soil_status,
    enrich_zoning,
    fetch_city_geo_shape,
    fetch_city_stats,
    fetch_district_geo_shape,
    fetch_district_stats,
    fetch_neighbourhood_geo_shape,
    fetch_neighbourhood_stats,
)
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


@admin.action(description="Enrich location (PDOK)")
def enrich_location_action(modeladmin, request, queryset):
    count = 0
    for residence in queryset:
        enrich_location.delay(residence.pk)
        count += 1
    modeladmin.message_user(
        request,
        f"Dispatched location enrichment for {count} residence(s).",
        messages.SUCCESS,
    )


@admin.action(description="Enrich building details (EP-Online)")
def enrich_building_details_action(modeladmin, request, queryset):
    count = 0
    for residence in queryset:
        enrich_building_details.delay(residence.pk)
        count += 1
    modeladmin.message_user(
        request,
        f"Dispatched building details enrichment for {count} residence(s).",
        messages.SUCCESS,
    )


@admin.action(description="Enrich zoning (Bestemmingsplan)")
def enrich_zoning_action(modeladmin, request, queryset):
    count = 0
    for residence in queryset:
        enrich_zoning.delay(residence.pk)
        count += 1
    modeladmin.message_user(
        request,
        f"Dispatched zoning enrichment for {count} residence(s).",
        messages.SUCCESS,
    )


@admin.action(description="Enrich soil status (Bodemloket)")
def enrich_soil_status_action(modeladmin, request, queryset):
    count = 0
    for residence in queryset:
        enrich_soil_status.delay(residence.pk)
        count += 1
    modeladmin.message_user(
        request,
        f"Dispatched soil status enrichment for {count} residence(s).",
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
        "neighbourhood",
        "district",
        "building_type",
        "current_price_eur",
        "current_status",
        "listing_count",
        "last_scraped_at",
    )
    list_filter = ("current_status", "building_type", "city", "neighbourhood")
    # `title` lives on per-portal Listing now, so search joins through the
    # reverse FK rather than a Residence column.
    search_fields = ("listings__title", "street", "postcode", "bag_id")
    ordering = ("-last_scraped_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "building_type",
        "energy_label",
        "energy_label_valid_until",
        "zoning_designation",
        "zoning_fetched_at",
        "soil_wbb_count",
        "soil_fetched_at",
        "display_room_count",
        "display_bedroom_count",
        "display_bathroom_count",
        "display_surface_area_m2",
        "display_construction_period",
        "display_detail_scraped_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "bag_id",
                    "city",
                    "street",
                    "house_number",
                    "house_letter",
                    "house_number_suffix",
                    "postcode",
                    "latitude",
                    "longitude",
                    "neighbourhood",
                    "district",
                    "current_price_eur",
                    "current_status",
                    "last_scraped_at",
                    "status_changed_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
        (
            "Building Details (EP-Online)",
            {
                "fields": (
                    "building_type",
                    "energy_label",
                    "energy_label_valid_until",
                ),
            },
        ),
        (
            "Zoning (Bestemmingsplan)",
            {
                "fields": (
                    "zoning_designation",
                    "zoning_fetched_at",
                ),
            },
        ),
        (
            "Soil Status (Bodemloket)",
            {
                "fields": (
                    "soil_wbb_count",
                    "soil_fetched_at",
                ),
            },
        ),
        (
            "Listing Details (latest scrape)",
            {
                "fields": (
                    "display_room_count",
                    "display_bedroom_count",
                    "display_bathroom_count",
                    "display_surface_area_m2",
                    "display_construction_period",
                    "display_detail_scraped_at",
                ),
            },
        ),
    )
    inlines = (ListingInline,)
    actions = [
        scrape_residence_details,
        enrich_location_action,
        enrich_building_details_action,
        enrich_zoning_action,
        enrich_soil_status_action,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(listing_count=Count("listings"))

    @admin.display(description="Listings", ordering="listing_count")
    def listing_count(self, obj):
        return obj.listing_count

    def _get_freshest_listing(self, obj):
        cached = getattr(obj, "_freshest_listing_cache", None)
        if cached is not None:
            return cached
        listing = obj.listings.filter(detail_scraped_at__isnull=False).order_by("-detail_scraped_at").first()
        obj._freshest_listing_cache = listing or False
        return listing or False

    def _detail_field(self, obj, field_name):
        listing = self._get_freshest_listing(obj)
        if not listing:
            return "—"
        value = getattr(listing, field_name, None)
        return value if value not in (None, "") else "—"

    @admin.display(description="Rooms")
    def display_room_count(self, obj):
        return self._detail_field(obj, "room_count")

    @admin.display(description="Bedrooms")
    def display_bedroom_count(self, obj):
        return self._detail_field(obj, "bedroom_count")

    @admin.display(description="Bathrooms")
    def display_bathroom_count(self, obj):
        return self._detail_field(obj, "bathroom_count")

    @admin.display(description="Surface area (m²)")
    def display_surface_area_m2(self, obj):
        return self._detail_field(obj, "surface_area_m2")

    @admin.display(description="Construction period")
    def display_construction_period(self, obj):
        return self._detail_field(obj, "construction_period")

    @admin.display(description="Detail scraped at")
    def display_detail_scraped_at(self, obj):
        return self._detail_field(obj, "detail_scraped_at")


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


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "has_geometry", "has_stats", "geometry_fetched_at", "stats_fetched_at")
    search_fields = ("code", "name")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    actions = ["fetch_geo_shapes", "fetch_stats", "fetch_districts"]
    change_list_template = "admin/scraping/city/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("sync-cities/", self.admin_site.admin_view(self.sync_cities_view), name="scraping_city_sync"),
        ]
        return custom_urls + urls

    def sync_cities_view(self, request):
        try:
            cities_data = cbs.fetch_all_cities()
            count = 0
            for city_data in cities_data:
                City.objects.update_or_create(
                    code=city_data["code"],
                    defaults={"name": city_data["name"]},
                )
                count += 1
            messages.success(request, f"Synced {count} cities.")
        except Exception as exc:
            messages.error(request, f"Failed to sync cities: {exc}")
        return HttpResponseRedirect(reverse("admin:scraping_city_changelist"))

    @admin.action(description="Fetch geo shapes")
    def fetch_geo_shapes(self, request, queryset):
        count = 0
        for city in queryset:
            fetch_city_geo_shape.delay(city.pk)
            count += 1
        self.message_user(request, f"Dispatched geo shape fetch for {count} city/cities.", messages.SUCCESS)

    @admin.action(description="Fetch stats")
    def fetch_stats(self, request, queryset):
        count = 0
        for city in queryset:
            fetch_city_stats.delay(city.pk)
            count += 1
        self.message_user(request, f"Dispatched stats fetch for {count} city/cities.", messages.SUCCESS)

    @admin.action(description="Fetch districts")
    def fetch_districts(self, request, queryset):
        success, failures = 0, []
        for city in queryset:
            try:
                for d in cbs.fetch_districts_for_city(city.code):
                    District.objects.update_or_create(code=d["code"], defaults={"name": d["name"], "city": city})
                success += 1
            except Exception as exc:
                failures.append(f"{city.code} ({exc})")
        self._report(request, "districts", success, failures, "cities")

    @staticmethod
    def _report(request, entity, success, failures, level_name):
        msg = f"Fetched {entity} for {success} {level_name}."
        if failures:
            msg += f" Failed: {', '.join(failures)}."
            messages.warning(request, msg)
        else:
            messages.success(request, msg)

    @admin.display(boolean=True, description="Geo")
    def has_geometry(self, obj):
        return obj.geometry is not None

    @admin.display(boolean=True, description="Stats")
    def has_stats(self, obj):
        return obj.stats is not None


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "has_geometry", "has_stats", "geometry_fetched_at", "stats_fetched_at")
    list_filter = ("city",)
    search_fields = ("code", "name")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    actions = ["fetch_geo_shapes", "fetch_stats", "fetch_neighbourhoods"]

    @admin.action(description="Fetch geo shapes")
    def fetch_geo_shapes(self, request, queryset):
        count = 0
        for district in queryset:
            fetch_district_geo_shape.delay(district.pk)
            count += 1
        self.message_user(request, f"Dispatched geo shape fetch for {count} district(s).", messages.SUCCESS)

    @admin.action(description="Fetch stats")
    def fetch_stats(self, request, queryset):
        count = 0
        for district in queryset:
            fetch_district_stats.delay(district.pk)
            count += 1
        self.message_user(request, f"Dispatched stats fetch for {count} district(s).", messages.SUCCESS)

    @admin.action(description="Fetch neighbourhoods")
    def fetch_neighbourhoods(self, request, queryset):
        success, failures = 0, []
        for district in queryset:
            try:
                for n in cbs.fetch_neighbourhoods_for_district(district.code):
                    Neighborhood.objects.update_or_create(
                        code=n["code"],
                        defaults={"name": n["name"], "district": district, "city": district.city},
                    )
                success += 1
            except Exception as exc:
                failures.append(f"{district.code} ({exc})")
        self._report(request, "neighbourhoods", success, failures, "districts")

    @staticmethod
    def _report(request, entity, success, failures, level_name):
        msg = f"Fetched {entity} for {success} {level_name}."
        if failures:
            msg += f" Failed: {', '.join(failures)}."
            messages.warning(request, msg)
        else:
            messages.success(request, msg)

    @admin.display(boolean=True, description="Geo")
    def has_geometry(self, obj):
        return obj.geometry is not None

    @admin.display(boolean=True, description="Stats")
    def has_stats(self, obj):
        return obj.stats is not None


@admin.register(Neighborhood)
class NeighborhoodAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "city",
        "district",
        "has_geometry",
        "has_stats",
        "geometry_fetched_at",
        "stats_fetched_at",
    )
    list_filter = ("city",)
    search_fields = ("code", "name")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    actions = ["fetch_geo_shapes", "fetch_stats"]

    @admin.action(description="Fetch geo shapes")
    def fetch_geo_shapes(self, request, queryset):
        count = 0
        for neighbourhood in queryset:
            fetch_neighbourhood_geo_shape.delay(neighbourhood.pk)
            count += 1
        self.message_user(request, f"Dispatched geo shape fetch for {count} neighbourhood(s).", messages.SUCCESS)

    @admin.action(description="Fetch stats")
    def fetch_stats(self, request, queryset):
        count = 0
        for neighbourhood in queryset:
            fetch_neighbourhood_stats.delay(neighbourhood.pk)
            count += 1
        self.message_user(request, f"Dispatched stats fetch for {count} neighbourhood(s).", messages.SUCCESS)

    @admin.display(boolean=True, description="Geo")
    def has_geometry(self, obj):
        return obj.geometry is not None

    @admin.display(boolean=True, description="Stats")
    def has_stats(self, obj):
        return obj.stats is not None
