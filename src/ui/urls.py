from django.urls import path

from ui.views import index

urlpatterns = [
    path("", index, name="index"),
]
