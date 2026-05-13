import httpx
import respx

from scraper.client import BackendClient
from scraper.enums import ListingStatus
from scraper.models import DetailListing

BASE_URL = "http://test-api"
API_KEY = "testkey"


@respx.mock
def test_submit_detail_result_patches_correct_endpoint():
    detail = DetailListing(
        price="€ 510.000,- k.k.",
        status=ListingStatus.NEW,
        surface_area_m2=95,
        bedroom_count=2,
        bathroom_count=1,
        room_count=3,
        construction_period="1991-2000",
        energy_label="A",
    )
    route = respx.patch(f"{BASE_URL}/internal/v1/listings/42/detail").mock(
        return_value=httpx.Response(200, json={})
    )

    client = BackendClient(base_url=BASE_URL, api_key=API_KEY)
    client.submit_detail_result(listing_id=42, detail=detail)

    assert route.called
    sent = route.calls.last.request
    import json
    body = json.loads(sent.content)
    assert body["price"] == "€ 510.000,- k.k."
    assert body["status"] == "new"
    assert body["surface_area_m2"] == 95
    assert body["bedroom_count"] == 2
    assert body["bathroom_count"] == 1
    assert body["room_count"] == 3
    assert body["construction_period"] == "1991-2000"
    assert body["energy_label"] == "A"


@respx.mock
def test_submit_detail_result_raises_on_non_2xx():
    detail = DetailListing(price="€ 100.000", status=ListingStatus.NEW)
    respx.patch(f"{BASE_URL}/internal/v1/listings/99/detail").mock(
        return_value=httpx.Response(404)
    )

    client = BackendClient(base_url=BASE_URL, api_key=API_KEY)

    import pytest
    with pytest.raises(httpx.HTTPStatusError):
        client.submit_detail_result(listing_id=99, detail=detail)
