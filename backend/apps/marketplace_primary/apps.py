from __future__ import annotations

from django.apps import AppConfig


class MarketplacePrimaryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.marketplace_primary"
    verbose_name = "Primary marketplace"
