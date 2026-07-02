import dataclasses
from typing import cast

from allauth.headless.adapter import DefaultHeadlessAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import User


class HeadlessAdapter(DefaultHeadlessAdapter):
    """Headless adapter that adds ``name`` to the serialized user object.

    Overriding ``get_user_dataclass`` (the OpenAPI-backing schema) and
    ``user_as_dataclass`` is the documented way to surface a custom field in
    the user payload returned by the login/session/signup responses. ``name``
    mirrors the Django ``User.first_name`` set at signup.
    """

    def get_user_dataclass(self):
        base = super().get_user_dataclass()
        fields = [(f.name, f.type, dataclasses.field(metadata=dict(f.metadata))) for f in dataclasses.fields(base)]
        fields.append(
            (
                "name",
                str | None,
                dataclasses.field(
                    default=None,
                    metadata={"description": "The user's display name.", "example": "Ada Lovelace"},
                ),
            )
        )
        return dataclasses.make_dataclass("User", fields)

    def user_as_dataclass(self, user: AbstractBaseUser):
        dc = super().user_as_dataclass(user)
        dc.name = cast(User, user).first_name or None
        return dc


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Store the provider's full display name on ``User.first_name``.

    Google's ``extract_common_fields`` maps ``first_name`` to the *given* name
    only, while the email/password signup path stores the full name there (see
    ``SignupForm``). Promoting the provider's full ``name`` keeps the ``name``
    surfaced by ``HeadlessAdapter`` consistent across both sign-in methods.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        full_name = sociallogin.account.extra_data.get("name")
        if not full_name:
            full_name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p).strip()
        if full_name:
            user.first_name = full_name
            user.last_name = ""
        return cast(User, user)
