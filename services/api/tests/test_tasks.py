import httpx
import pytest
import respx


def test_ping_returns_pong_under_eager_mode():
    from scraping.tasks import ping

    result = ping.delay()
    assert result.get(timeout=1) == "pong"


@respx.mock
def test_dispatch_scrape_posts_payload_and_returns_run_id(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"
    route = respx.post("http://webhook.test/scrape").mock(return_value=httpx.Response(200))

    run_id = dispatch_scrape.delay("funda", "run-abc").get(timeout=1)

    assert run_id == "run-abc"
    assert route.called
    body = route.calls.last.request.content.decode()
    assert '"website":"funda"' in body
    assert '"run_id":"run-abc"' in body


@respx.mock
def test_dispatch_scrape_generates_run_id_when_missing(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"
    respx.post("http://webhook.test/scrape").mock(return_value=httpx.Response(200))

    run_id = dispatch_scrape.delay("pararius").get(timeout=1)

    assert run_id and len(run_id) == 32  # uuid4 hex


def test_dispatch_scrape_short_circuits_when_url_unset(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = None

    # No respx mock — if the task attempted an HTTP call it would fail.
    run_id = dispatch_scrape.delay("funda", "run-skip").get(timeout=1)

    assert run_id == "run-skip"


def test_dispatch_scrape_rejects_unknown_website(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"

    with pytest.raises(ValueError):
        dispatch_scrape.delay("not-a-real-site").get(timeout=1)
