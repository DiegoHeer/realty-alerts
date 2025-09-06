from http import HTTPStatus
import pytest
from django.urls import reverse

from ui.tests.factories import RealtyQueryFactory, RealtyResultFactory


@pytest.fixture
def query(db):
    return RealtyQueryFactory()


@pytest.fixture
def queries(db):
    return RealtyResultFactory.create_batch(15)


@pytest.fixture
def results(db, query):
    return RealtyResultFactory.create_batch(10, query=query)


@pytest.fixture
def realty_query_list_url():
    return reverse("realty-query-list")


@pytest.fixture
def realty_query_toggle_url(query):
    return reverse("realty-query-toggle", kwargs={"pk": query.pk})


@pytest.fixture
def detail_url(query):
    return reverse("realty-query-detail", kwargs={"pk": query.pk})


class TestRealtyQueryListView:
    def test_queryset_filters_by_name(self, client, realty_query_list_url, queries):
        response = client.get(realty_query_list_url, {"q": "Query 1"})

        object_list = response.context_data["queries"]
        assert all("Query 1" in obj.name for obj in object_list)

    def test_context_data_includes_new_results_count(self, client, realty_query_list_url, query, results):
        response = client.get(realty_query_list_url)

        queries = response.context_data["queries"]
        assert queries[0].new_results_count == 10

    def test_pagination(self, client, realty_query_list_url, queries):
        response = client.get(realty_query_list_url)

        page_obj = response.context_data["page_obj"]
        assert page_obj.paginator.num_pages == 2
        assert len(response.context_data["queries"]) == 10

    def test_post_toggles_periodic_task(self, client, realty_query_toggle_url, query):
        response = client.post(realty_query_toggle_url)

        assert response.status_code == HTTPStatus.OK
        assert len(response.templates) == 1
        assert response.templates[0].name == "ui/partials/query-toggle.html"

        query.refresh_from_db()
        assert query.periodic_task.enabled is False


class TestRealtyQueryDetailView:
    def test_get_detail_view_renders_query(self, client, detail_url, query):
        response = client.get(detail_url)

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["object"] == query

    def test_get_breadcrumbs_in_context(self, client, detail_url, query):
        response = client.get(detail_url)

        breadcrumbs = response.context_data["breadcrumbs"]
        assert breadcrumbs[0]["title"] == "Home"
        assert breadcrumbs[1]["title"] == query.name
        assert breadcrumbs[1]["url"].endswith(str(query.pk))

    def test_results_queryset_is_attached_to_context(self, client, detail_url, results):
        response = client.get(detail_url)

        # results are exposed as both object_list and results
        assert "results" in response.context_data
        assert list(response.context_data["results"]) == list(response.context_data["object_list"])
        assert len(response.context_data["results"]) == 5

    def test_results_queryset_filters_by_title(self, client, detail_url, query):
        matching = RealtyResultFactory(query=query, title="Lovely Penthouse", price="500000")
        RealtyResultFactory(query=query, title="Suburban House", price="250000")

        response = client.get(detail_url, {"q": "Penthouse"})
        results = response.context_data["results"]

        assert matching in results
        assert all("Penthouse" in r.title or "Penthouse" in str(r.price) for r in results)

    def test_results_queryset_filters_by_price(self, client, detail_url, query):
        matching = RealtyResultFactory(query=query, title="Modern Loft", price="750000")
        RealtyResultFactory(query=query, title="Countryside Cottage", price="250000")

        response = client.get(detail_url, {"q": "750000"})
        results = response.context_data["results"]

        assert matching in results
        assert all("750000" in str(r.price) or "750000" in r.title for r in results)

    def test_pagination_of_results(self, client, detail_url, results):
        response = client.get(detail_url)

        page_obj = response.context_data["page_obj"]
        assert page_obj.paginator.num_pages == 2
        assert len(response.context_data["results"]) == 5
