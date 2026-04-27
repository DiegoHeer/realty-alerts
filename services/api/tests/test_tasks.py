def test_ping_returns_pong_under_eager_mode():
    from scraping.tasks import ping

    result = ping.delay()
    assert result.get(timeout=1) == "pong"
