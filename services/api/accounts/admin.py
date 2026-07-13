from django.contrib import admin

from accounts.models import Favorite, ResidenceView, UserPreferences


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("user", "search_updated_at", "notifications_updated_at", "updated_at")
    search_fields = ("user__email", "user__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "residence", "liked_at", "created_at")
    search_fields = ("user__email", "user__username")
    readonly_fields = ("created_at",)


@admin.register(ResidenceView)
class ResidenceViewAdmin(admin.ModelAdmin):
    list_display = ("user", "residence", "viewed_at")
    search_fields = ("user__email", "user__username")
