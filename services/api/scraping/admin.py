from django.contrib import admin

from scraping.models import Listing, ScrapeRun


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("id", "website", "city", "street", "house_number", "postcode", "price", "status", "scraped_at")
    list_filter = ("website", "status", "city")
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
        "listings_new",
        "duration_seconds",
    )
    list_filter = ("website", "status")
    ordering = ("-started_at",)
