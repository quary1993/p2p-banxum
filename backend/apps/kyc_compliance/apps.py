from __future__ import annotations

from django.apps import AppConfig


class KycComplianceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.kyc_compliance"
    verbose_name = "KYC and compliance"

    def ready(self) -> None:
        from backend.apps.kyc_compliance import checks  # noqa: F401
