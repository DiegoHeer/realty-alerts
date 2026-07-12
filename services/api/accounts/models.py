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
