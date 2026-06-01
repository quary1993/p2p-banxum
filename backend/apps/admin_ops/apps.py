from __future__ import annotations

from django.apps import AppConfig


class AdminOpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.admin_ops"
    verbose_name = "Admin operations"
