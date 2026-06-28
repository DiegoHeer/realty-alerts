import pytest

from tests.factories import ResidenceFactory


@pytest.mark.django_db
class TestNeighbourhoodCodeFilter:
    endpoint = "/v1/residences"

    def _ids(self, client, query):
        body = client.get(f"{self.endpoint}?{query}").json()
        return {item["id"] for item in body}

    def test_filters_to_matching_code(self, client):
        a = ResidenceFactory(neighbourhood_code="BU03630000")
        ResidenceFactory(neighbourhood_code="BU03630001")
        assert self._ids(client, "neighbourhood_code=BU03630000") == {a.id}  # ty: ignore[unresolved-attribute]

    def test_repeated_param_or_combines(self, client):
        a = ResidenceFactory(neighbourhood_code="BU03630000")
        b = ResidenceFactory(neighbourhood_code="BU03630001")
        ResidenceFactory(neighbourhood_code="BU03630002")
        ids = self._ids(client, "neighbourhood_code=BU03630000&neighbourhood_code=BU03630001")
        assert ids == {a.id, b.id}  # ty: ignore[unresolved-attribute]

    def test_csv_fallback_or_combines(self, client):
        a = ResidenceFactory(neighbourhood_code="BU03630000")
        b = ResidenceFactory(neighbourhood_code="BU03630001")
        ids = self._ids(client, "neighbourhood_code=BU03630000,BU03630001")
        assert ids == {a.id, b.id}  # ty: ignore[unresolved-attribute]

    def test_null_code_excluded_when_filter_set(self, client):
        ResidenceFactory(neighbourhood_code=None)
        matching = ResidenceFactory(neighbourhood_code="BU03630000")
        assert self._ids(client, "neighbourhood_code=BU03630000") == {matching.id}  # ty: ignore[unresolved-attribute]

    def test_null_code_included_when_filter_absent(self, client):
        null_one = ResidenceFactory(neighbourhood_code=None)
        coded = ResidenceFactory(neighbourhood_code="BU03630000")
        ids = self._ids(client, "limit=100")
        assert {null_one.id, coded.id} <= ids  # ty: ignore[unresolved-attribute]
