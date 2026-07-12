from django.conf import settings
from django.db import models


class UserPreferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences")
    search = models.JSONField(default=dict, blank=True)
    search_updated_at = models.DateTimeField(null=True, blank=True)
    notifications = models.JSONField(default=dict, blank=True)
    notifications_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Preferences<{self.user.pk}>"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    residence = models.ForeignKey("scraping.Residence", on_delete=models.CASCADE, related_name="+")
    liked_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "residence"], name="uniq_user_favorite")]
        indexes = [models.Index(fields=["user", "-liked_at"], name="fav_user_liked_idx")]

    def __str__(self) -> str:
        return f"Favorite<{self.user.pk}:{self.residence_id}>"  # ty: ignore[unresolved-attribute]


class ResidenceView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="residence_views")
    residence = models.ForeignKey("scraping.Residence", on_delete=models.CASCADE, related_name="+")
    viewed_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "residence"], name="uniq_user_residence_view")]
        indexes = [models.Index(fields=["user", "-viewed_at"], name="view_user_viewed_idx")]

    def __str__(self) -> str:
        return f"ResidenceView<{self.user.pk}:{self.residence_id}>"  # ty: ignore[unresolved-attribute]
