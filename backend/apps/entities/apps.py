from __future__ import annotations

from django.apps import AppConfig


class EntitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.entities"
    verbose_name = "Entities"
