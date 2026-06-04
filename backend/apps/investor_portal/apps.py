from __future__ import annotations

from django.apps import AppConfig


class InvestorPortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.investor_portal"
    verbose_name = "Investor portal"
