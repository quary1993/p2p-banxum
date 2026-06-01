from __future__ import annotations

from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.loans"
    verbose_name = "Loans"
