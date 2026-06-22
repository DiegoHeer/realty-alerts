from django.contrib import admin
from django.urls import include, path

from scraping.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("_allauth/", include("allauth.headless.urls")),
    path("", api.urls),
]
