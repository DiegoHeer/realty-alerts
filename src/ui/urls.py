from django.urls import path

from ui.views import RealtyQueryListView, RealtyQueryDetailView, HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("query-list/", RealtyQueryListView.as_view(), name="realty-query-list"),
    path("query/<int:pk>", RealtyQueryDetailView.as_view(), name="realty-query-detail"),
]
