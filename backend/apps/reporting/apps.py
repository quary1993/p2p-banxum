from __future__ import annotations

from django.apps import AppConfig


class ReportingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.reporting"
    verbose_name = "Reporting"
