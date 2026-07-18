from datetime import datetime

import pytest
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.template.loader import render_to_string


@pytest.mark.django_db
def test_default_site_is_huismus():
    site = Site.objects.get(pk=1)
    assert site.name == "Huismus"
    assert site.domain == "huismusapp.com"


def test_email_logo_url_is_absolute():
    from scraping.context_processors import email_branding

    ctx = email_branding(request=None)
    url = ctx["email_logo_url"]
    assert url.startswith("http")
    assert "email/huismus-logo" in url


@pytest.mark.django_db
def test_base_email_renders_to_html_doc():
    html = render_to_string(
        "account/email/base_email.html",
        {"current_site": Site.objects.get(pk=1), "email_logo_url": "https://x/logo.png"},
    )
    assert "<html" in html.lower()
    assert "Huismus" in html
    assert "prefers-color-scheme" in html  # dark mode present


@pytest.mark.django_db
def test_password_changed_message_renders():
    html = render_to_string(
        "account/email/password_changed_message.html",
        {
            "current_site": Site.objects.get(pk=1),
            "email_logo_url": "https://x/logo.png",
            "ip": "203.0.113.5",
            "user_agent": "Mozilla/5.0",
            "timestamp": datetime(2026, 7, 18, 14, 32),
        },
    )
    assert "<html" in html.lower()
    assert "Your password was changed" in html
    assert "203.0.113.5" in html
    assert "Mozilla/5.0" in html
    assert "18 Jul 2026, 14:32" in html
    assert "Secure your account" in html


@pytest.mark.django_db
def test_email_changed_message_renders():
    html = render_to_string(
        "account/email/email_changed_message.html",
        {
            "current_site": Site.objects.get(pk=1),
            "email_logo_url": "https://x/logo.png",
            "from_email": "old@example.com",
            "to_email": "new@example.com",
            "ip": "203.0.113.5",
            "user_agent": "Mozilla/5.0",
            "timestamp": datetime(2026, 7, 18, 14, 32),
        },
    )
    assert "<html" in html.lower()
    assert "Your email was changed" in html
    assert "old@example.com" in html
    assert "new@example.com" in html
    assert "203.0.113.5" in html


@pytest.mark.django_db
def test_email_deleted_message_renders():
    html = render_to_string(
        "account/email/email_deleted_message.html",
        {
            "current_site": Site.objects.get(pk=1),
            "email_logo_url": "https://x/logo.png",
            "deleted_email": "removed@example.com",
            "ip": "203.0.113.5",
            "user_agent": "Mozilla/5.0",
            "timestamp": datetime(2026, 7, 18, 14, 32),
        },
    )
    assert "<html" in html.lower()
    assert "An email address was removed" in html
    assert "removed@example.com" in html
    assert "203.0.113.5" in html


@pytest.mark.django_db
def test_email_confirm_message_renders():
    html = render_to_string(
        "account/email/email_confirm_message.html",
        {
            "current_site": Site.objects.get(pk=1),
            "email_logo_url": "https://x/logo.png",
        },
    )
    assert "<html" in html.lower()
    assert "You're all set" in html
    assert "Open Huismus" in html


@pytest.mark.django_db
def test_account_already_exists_message_renders():
    html = render_to_string(
        "account/email/account_already_exists_message.html",
        {
            "current_site": Site.objects.get(pk=1),
            "email_logo_url": "https://x/logo.png",
            "email": "x@example.com",
            "password_reset_url": "https://huismusapp.com/reset/abc",
        },
    )
    assert "<html" in html.lower()
    assert "You already have an account" in html
    assert "https://huismusapp.com/reset/abc" in html


@pytest.mark.django_db
def test_email_previews_command_writes_files(tmp_path):
    call_command("email_previews", out_dir=str(tmp_path), lang="en")

    preview = tmp_path / "email_confirmation_signup.en.html"
    assert preview.exists()
    assert "<html" in preview.read_text(encoding="utf-8").lower()
