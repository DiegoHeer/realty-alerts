from django.contrib import admin

from scraping.models import BagStatus, Listing, Residence, ScrapeRun


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
        "last_scraped_at",
    )
    list_filter = ("current_status", "city")
    # `title` lives on per-portal Listing now, so search joins through the
    # reverse FK rather than a Residence column.
    search_fields = ("listings__title", "street", "postcode", "bag_id")
    ordering = ("-last_scraped_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (ListingInline,)


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
            return queryset.filter(
                bag_status__in=(
                    BagStatus.PARSE_FAILED,
                    BagStatus.MISSING_ADDRESS,
                    BagStatus.BAG_NO_MATCH,
                    BagStatus.BAG_AMBIGUOUS,
                )
            )
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


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
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
