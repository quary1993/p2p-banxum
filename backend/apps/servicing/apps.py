from __future__ import annotations

from django.apps import AppConfig


class ServicingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.servicing"
    verbose_name = "Servicing"
