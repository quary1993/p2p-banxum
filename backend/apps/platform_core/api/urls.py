from __future__ import annotations

from django.urls import path

from backend.apps.platform_core.api.views import HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
]
