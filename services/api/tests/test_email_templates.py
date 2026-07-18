import pytest
from django.contrib.sites.models import Site
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
