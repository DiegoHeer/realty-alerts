from django import forms
from django.contrib.auth.models import User
from django.http import HttpRequest


class SignupForm(forms.Form):
    """Custom signup form wired via ``ACCOUNT_SIGNUP_FORM_CLASS``.

    allauth composes this into ``BaseSignupForm`` (and the headless
    ``SignupInput``) through multiple inheritance, so the ``name`` field
    becomes a required field on the headless signup request. ``signup`` is the
    hook allauth invokes after the user is created.
    """

    name = forms.CharField(max_length=150)

    def signup(self, request: HttpRequest, user: User) -> None:
        user.first_name = self.cleaned_data["name"]
        user.save(update_fields=["first_name"])
