from django.urls import path

from ui.views import RealtyQueryListView, RealtyQueryDetailView, HomeView, RealtyResultsListView, query_toggle

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("queries/list", RealtyQueryListView.as_view(), name="realty-query-list"),
    path("queries/<int:pk>", RealtyQueryDetailView.as_view(), name="realty-query-detail"),
    path("queries/<int:pk>/toggle", query_toggle, name="realty-query-toggle"),
    path("queries/<int:pk>/results/", RealtyResultsListView.as_view(), name="realty-result-list"),
]
