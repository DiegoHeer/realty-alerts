from django.contrib import admin

from ui.models import RealtyQuery, RealtyResult


@admin.register(RealtyQuery)
class RealtyQueryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "created_at",
        "cron_schedule",
        "website",
    )

    search_fields = ("name", "ntfy_topic", "query_url")
    readonly_fields = ("website", "notification_url")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "ntfy_topic",
                    "cron_schedule",
                    "query_url",
                    "max_listing_page_number",
                )
            },
        ),
        (
            "Computed Fields",
            {
                "fields": ("website", "notification_url"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(RealtyResult)
class RealtyResultAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "created_at",
        "updated_at",
        "price",
        "query",
    )
    list_filter = (
        "query",
        "status",
    )
    search_fields = ("title", "price", "query__name")
    list_select_related = ("query",)
