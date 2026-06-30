"""Client-IP resolution for allauth rate limiting (prod policy).

prod.py sets ALLAUTH_TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP" because the
Cloudflare -> cloudflared -> Traefik chain rewrites X-Forwarded-For/X-Real-IP,
leaving CF-Connecting-IP as the only trustworthy client IP. These tests pin that
contract via override_settings (importing prod.py isn't viable in tests), guarding
against an allauth upgrade changing the trusted-header semantics.
"""

from allauth.account.adapter import get_adapter
from django.test import RequestFactory, override_settings


@override_settings(ALLAUTH_TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP")
def test_client_ip_comes_from_cloudflare_header():
    request = RequestFactory().get("/", HTTP_CF_CONNECTING_IP="203.0.113.7", REMOTE_ADDR="10.0.0.1")

    assert get_adapter().get_client_ip(request) == "203.0.113.7"


@override_settings(ALLAUTH_TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP")
def test_spoofed_forwarded_for_is_ignored_when_cf_header_trusted():
    request = RequestFactory().get(
        "/",
        HTTP_CF_CONNECTING_IP="203.0.113.7",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
        REMOTE_ADDR="10.0.0.1",
    )

    assert get_adapter().get_client_ip(request) == "203.0.113.7"
