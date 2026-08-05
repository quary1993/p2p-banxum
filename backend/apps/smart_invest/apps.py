from __future__ import annotations

from django.apps import AppConfig


class SmartInvestConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.smart_invest"
    verbose_name = "Smart Invest"
