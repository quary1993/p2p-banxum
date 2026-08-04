from __future__ import annotations

from django.apps import AppConfig


class OriginatorClaimsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.originator_claims"
    verbose_name = "Loan Originator claims"
