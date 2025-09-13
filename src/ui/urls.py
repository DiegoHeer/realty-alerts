from django.urls import path

from ui.views import (
    RealtyQueryListView,
    RealtyQueryDetailView,
    HomeView,
    RealtyResultsListView,
    query_toggle,
    create_query,
    validate_ntfy_topic,
    archive_result,
    check_query_name,
    check_query_url,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("queries/list", RealtyQueryListView.as_view(), name="realty-query-list"),
    path("queries/create", create_query, name="realty-query-create"),
    path("queries/<int:pk>", RealtyQueryDetailView.as_view(), name="realty-query-detail"),
    path("queries/<int:pk>/toggle", query_toggle, name="realty-query-toggle"),
    path("queries/<int:pk>/results/", RealtyResultsListView.as_view(), name="realty-result-list"),
    path("test/ntfy-topic", validate_ntfy_topic, name="validate-ntfy-topic"),
    path("results/<int:pk>/delete", archive_result, name="realty-result-delete"),
    path("queries/create/check-query-name", check_query_name, name="check-query-name"),
    path("queries/create/check-query-url", check_query_url, name="check-query-url"),
]
