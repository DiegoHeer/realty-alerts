from typing import Any

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage


def email_branding(request: Any) -> dict[str, str]:
    return {
        "email_logo_url": f"{settings.EMAIL_ASSET_BASE_URL}{staticfiles_storage.url('email/huismus-logo.png')}",
    }
