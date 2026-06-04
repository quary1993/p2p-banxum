from __future__ import annotations

from django.urls import path

from backend.apps.reporting.api.views import ReportGenerateView

urlpatterns = [
    path("admin/reports/", ReportGenerateView.as_view(), name="reporting-report-generate"),
]
