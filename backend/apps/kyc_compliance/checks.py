from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_didit_webhook_signature_config(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    environment = str(settings.ENVIRONMENT).lower()
    session_provider = str(settings.DIDIT_SESSION_PROVIDER).lower()
    if environment == "local":
        return []

    errors: list[Error] = []
    if session_provider != "api":
        errors.append(
            Error(
                "DIDIT_SESSION_PROVIDER must be api outside local development.",
                id="kyc_compliance.E003",
            )
        )
    if not str(settings.DIDIT_API_KEY):
        errors.append(
            Error(
                "DIDIT_API_KEY must be set outside local development.",
                id="kyc_compliance.E004",
            )
        )
    if str(settings.DIDIT_WORKFLOW_ID) == "didit-natural-person-lender-v1":
        errors.append(
            Error(
                "DIDIT_WORKFLOW_ID must be set to a real Didit workflow outside local development.",
                id="kyc_compliance.E005",
            )
        )
    if not str(settings.DIDIT_WEBHOOK_SECRET):
        errors.append(
            Error(
                "DIDIT_WEBHOOK_SECRET must be set outside local development.",
                id="kyc_compliance.E001",
            )
        )
    if not bool(settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE):
        errors.append(
            Error(
                "DIDIT_WEBHOOK_REQUIRE_SIGNATURE must be true outside local development.",
                id="kyc_compliance.E002",
            )
        )
    return errors
