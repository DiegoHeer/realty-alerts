from django.contrib import admin

from scraping.models import DeadListing, Listing, ListingUrl, ScrapeRun


class ListingUrlInline(admin.TabularInline):
    model = ListingUrl
    extra = 0
    readonly_fields = ("url", "website", "first_seen_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bag_id",
        "city",
        "street",
        "house_number",
        "postcode",
        "price",
        "status",
        "scraped_at",
    )
    list_filter = ("status", "city")
    search_fields = ("title", "street", "postcode", "bag_id")
    ordering = ("-scraped_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (ListingUrlInline,)


@admin.register(ListingUrl)
class ListingUrlAdmin(admin.ModelAdmin):
    list_display = ("id", "url", "website", "listing", "first_seen_at")
    list_filter = ("website",)
    search_fields = ("url",)
    ordering = ("-first_seen_at",)
    readonly_fields = ("first_seen_at",)


@admin.register(DeadListing)
class DeadListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "website",
        "reason",
        "city",
        "street",
        "house_number",
        "postcode",
        "scraped_at",
    )
    list_filter = ("website", "reason", "city")
    search_fields = ("title", "detail_url", "street", "postcode")
    ordering = ("-scraped_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "website",
        "status",
        "started_at",
        "finished_at",
        "listings_found",
        "new_properties_count",
        "new_listing_urls_count",
        "duration_seconds",
    )
    list_filter = ("website", "status")
    ordering = ("-started_at",)
