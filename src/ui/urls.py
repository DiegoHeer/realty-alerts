from django.urls import path

from ui.views import RealtyQueryListView, RealtyQueryDetailView

urlpatterns = [
    path("", RealtyQueryListView.as_view(), name="realty-query-list"),
    path("<int:pk>", RealtyQueryDetailView.as_view(), name="realty-query-detail"),
]
