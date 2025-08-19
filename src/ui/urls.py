from django.urls import path

from ui.views import RealtyQueryListView

urlpatterns = [
    path("", RealtyQueryListView.as_view(), name="realty-query-list"),
]
