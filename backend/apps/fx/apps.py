from __future__ import annotations

from django.apps import AppConfig


class FxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.fx"
    verbose_name = "FX"
