from __future__ import annotations

from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.communications"
    verbose_name = "Communications"
