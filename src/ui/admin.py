from django.contrib import admin

from ui.models import RealtyQuery, RealtyResult


@admin.register(RealtyQuery)
class RealtyQueryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "periodic_task_enabled",
        "created_at",
        "periodic_task",
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
                    "periodic_task",
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

    @admin.display(boolean=True, description="Task enabled")
    def periodic_task_enabled(self, object: RealtyQuery):
        return object.periodic_task.enabled

    periodic_task_enabled.admin_order_field = "periodic_task__enabled"


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
