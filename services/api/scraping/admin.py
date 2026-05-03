from django.contrib import admin, messages
from django.db.models import Q, QuerySet
from django.http import HttpRequest

from scraping.models import DeadListing, Listing, ListingUrl, ScrapeRun
from scraping.services import DeadListingPromotionError, promote_dead_listing


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


_PROMOTION_READY_Q = (
    Q(bag_id__isnull=False) & ~Q(bag_id__exact="") & ~Q(title__exact="") & ~Q(price__exact="") & ~Q(city__exact="")
)


class PromotionReadyFilter(admin.SimpleListFilter):
    title = "promotion ready"
    parameter_name = "promotion_ready"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(_PROMOTION_READY_Q)
        if self.value() == "no":
            return queryset.exclude(_PROMOTION_READY_Q)
        return queryset


@admin.register(DeadListing)
class DeadListingAdmin(admin.ModelAdmin):
    change_form_template = "admin/scraping/deadlisting/change_form.html"
    list_display = (
        "id",
        "promotion_ready",
        "website",
        "reason",
        "city",
        "street",
        "house_number",
        "postcode",
        "bag_id",
        "scraped_at",
    )
    list_filter = (PromotionReadyFilter, "website", "reason", "city")
    search_fields = ("title", "detail_url", "street", "postcode", "bag_id")
    ordering = ("-scraped_at",)
    readonly_fields = ("created_at", "updated_at")
    actions = ("promote_action",)

    @admin.display(boolean=True, description="Ready", ordering="bag_id")
    def promotion_ready(self, obj: DeadListing) -> bool:
        return obj.is_promotion_ready

    def render_change_form(self, request, context, *args, **kwargs):
        obj: DeadListing | None = context.get("original")
        if obj is not None:
            context["promotion_ready"] = obj.is_promotion_ready
            context["promotion_missing_fields"] = obj.missing_promotion_fields
        return super().render_change_form(request, context, *args, **kwargs)

    @admin.action(description="Promote to Listing")
    def promote_action(self, request: HttpRequest, queryset: QuerySet[DeadListing]) -> None:
        promoted: list[int] = []
        skipped: list[int] = []
        failed: list[tuple[int, str]] = []

        for dead in queryset:
            if not dead.is_promotion_ready:
                skipped.append(dead.pk)
                continue
            try:
                promote_dead_listing(dead)
                promoted.append(dead.pk)
            except DeadListingPromotionError as exc:
                failed.append((dead.pk, str(exc)))

        summary = f"Promoted {len(promoted)}, skipped {len(skipped)} (not ready), failed {len(failed)}."
        level = messages.SUCCESS if not skipped and not failed else messages.WARNING
        self.message_user(request, summary, level=level)
        for pk, reason in failed:
            self.message_user(request, f"DeadListing {pk}: {reason}", level=messages.ERROR)


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
