import pytest
from django.contrib.sites.models import Site


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
