import pytest
from django.contrib.sites.models import Site


@pytest.mark.django_db
def test_default_site_is_huismus():
    site = Site.objects.get(pk=1)
    assert site.name == "Huismus"
    assert site.domain == "huismusapp.com"
