from __future__ import annotations

from django.apps import AppConfig


class HoldingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.holdings"
    verbose_name = "Investor holdings"
