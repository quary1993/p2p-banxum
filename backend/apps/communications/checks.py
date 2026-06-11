from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_email_provider_config(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    if str(settings.ENVIRONMENT).lower() == "local":
        return []

    errors: list[Error] = []
    provider = str(settings.COMMUNICATIONS_EMAIL_PROVIDER).strip().lower()
    if provider != "sendgrid":
        errors.append(
            Error(
                "COMMUNICATIONS_EMAIL_PROVIDER must be sendgrid outside local development.",
                id="communications.E001",
            )
        )
    if not str(settings.SENDGRID_API_KEY).strip():
        errors.append(
            Error(
                "SENDGRID_API_KEY must be configured outside local development.",
                id="communications.E002",
            )
        )
    if not str(settings.SENDGRID_FROM_EMAIL).strip():
        errors.append(
            Error(
                "SENDGRID_FROM_EMAIL must be configured outside local development.",
                id="communications.E003",
            )
        )
    if int(settings.SENDGRID_TIMEOUT_SECONDS) <= 0:
        errors.append(
            Error(
                "SENDGRID_TIMEOUT_SECONDS must be positive.",
                id="communications.E004",
            )
        )
    return errors
