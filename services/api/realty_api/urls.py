from django.contrib import admin
from django.urls import path

from scraping.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", api.urls),
]
