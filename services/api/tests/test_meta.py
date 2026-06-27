class TestMeta:
    endpoint = "/v1/meta"

    def test_returns_version_policy(self, client):
        response = client.get(self.endpoint)
        assert response.status_code == 200
        assert response.json() == {
            "current_api_version": 2,
            "min_supported_api_version": 1,
        }

    def test_reflects_settings(self, client, settings):
        settings.API_CURRENT_VERSION = 5
        settings.API_MIN_SUPPORTED_VERSION = 3
        body = client.get(self.endpoint).json()
        assert body == {"current_api_version": 5, "min_supported_api_version": 3}
