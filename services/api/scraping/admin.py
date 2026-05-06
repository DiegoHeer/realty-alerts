from django.contrib import admin

from scraping.models import Listing, Residence, ScrapeRun


class ListingInline(admin.TabularInline):
    model = Listing
    extra = 0
    readonly_fields = ("url", "website", "first_seen_at")
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
        "last_scraped_at",
    )
    list_filter = ("current_status", "city")
    search_fields = ("title", "street", "postcode", "bag_id")
    ordering = ("-last_scraped_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (ListingInline,)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("id", "url", "website", "residence", "first_seen_at")
    list_filter = ("website",)
    search_fields = ("url",)
    ordering = ("-first_seen_at",)
    readonly_fields = ("first_seen_at",)


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "website",
        "status",
        "started_at",
        "finished_at",
        "listings_found",
        "new_residences_count",
        "new_listings_count",
        "duration_seconds",
    )
    list_filter = ("website", "status")
    ordering = ("-started_at",)
