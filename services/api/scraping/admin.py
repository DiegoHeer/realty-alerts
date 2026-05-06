from django.contrib import admin, messages
from django.db.models import Q, QuerySet
from django.http import HttpRequest

from scraping.models import DeadResidence, Listing, Residence, ScrapeRun
from scraping.services import DeadResidencePromotionError, promote_dead_residence


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


@admin.register(DeadResidence)
class DeadResidenceAdmin(admin.ModelAdmin):
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
    def promotion_ready(self, obj: DeadResidence) -> bool:
        return obj.is_promotion_ready

    @admin.action(description="Promote to Residence")
    def promote_action(self, request: HttpRequest, queryset: QuerySet[DeadResidence]) -> None:
        promoted = 0
        skipped = 0
        failed = 0

        for dead in queryset:
            if not dead.is_promotion_ready:
                skipped += 1
                self.message_user(
                    request,
                    f"DeadResidence {dead.pk}: not ready — missing {', '.join(dead.missing_promotion_fields)}.",
                    level=messages.WARNING,
                )
                continue
            try:
                promote_dead_residence(dead)
                promoted += 1
            except DeadResidencePromotionError as exc:
                failed += 1
                self.message_user(request, f"DeadResidence {dead.pk}: {exc}", level=messages.ERROR)

        summary = f"Promoted {promoted}, skipped {skipped}, failed {failed}."
        level = messages.SUCCESS if not skipped and not failed else messages.WARNING
        self.message_user(request, summary, level=level)


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
