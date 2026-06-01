from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_didit_webhook_signature_config(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    if str(settings.ENVIRONMENT).lower() == "local":
        return []

    errors: list[Error] = []
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
