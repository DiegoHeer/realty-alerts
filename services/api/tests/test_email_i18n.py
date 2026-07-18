import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils import translation


def test_supported_languages_configured():
    codes = {code for code, _ in settings.LANGUAGES}
    assert codes == {"en", "nl", "pt"}


def test_locale_paths_configured():
    assert any(str(p).endswith("locale") for p in settings.LOCALE_PATHS)


def test_locale_middleware_installed():
    mw = settings.MIDDLEWARE
    assert "django.middleware.locale.LocaleMiddleware" in mw
    # Must sit after SessionMiddleware and before CommonMiddleware.
    assert (
        mw.index("django.contrib.sessions.middleware.SessionMiddleware")
        < mw.index("django.middleware.locale.LocaleMiddleware")
        < mw.index("django.middleware.common.CommonMiddleware")
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang,needle",
    [
        ("en", "Verify your email"),
        ("nl", "Verifieer je e-mailadres"),
        ("pt", "Verifique o seu e-mail"),
    ],
)
def test_verification_email_localized(lang, needle):
    # The signup verification copy ("Verify your email") lives in
    # email_confirmation_signup_message.html; the reconfirm-email template
    # email_confirmation_message.html carries the distinct "Confirm your
    # email address" copy split out in the task-8 copy change.
    with translation.override(lang):
        html = render_to_string(
            "account/email/email_confirmation_signup_message.html",
            {
                "code": "7F2K-9QD4",
                "current_site": Site.objects.get(pk=1),
                "email_logo_url": "https://x/logo.png",
            },
        )
    assert needle in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang,needle",
    [
        ("en", "Your password was changed"),
        ("nl", "Je wachtwoord is gewijzigd"),
        ("pt", "A sua palavra-passe foi alterada"),
    ],
)
def test_password_changed_notice_localized(lang, needle):
    # Security notice added in Task 11/12; msgids were extracted and
    # translated in Task 13. Exercises the H1 plus the facts-table labels
    # (When/Device/IP address) rendered via _facts.html.
    with translation.override(lang):
        html = render_to_string(
            "account/email/password_changed_message.html",
            {
                "ip": "203.0.113.7",
                "user_agent": "Safari on macOS",
                "timestamp": "2026-07-18 21:04 UTC",
                "current_site": Site.objects.get(pk=1),
                "email_logo_url": "https://x/logo.png",
            },
        )
    assert needle in html
