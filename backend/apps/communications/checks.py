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
    if provider not in {"sendgrid", "twilio_email"}:
        errors.append(
            Error(
                "COMMUNICATIONS_EMAIL_PROVIDER must be sendgrid or twilio_email "
                "outside local development.",
                id="communications.E001",
            )
        )
    if provider == "sendgrid":
        if not str(settings.SENDGRID_API_KEY).strip():
            errors.append(
                Error(
                    "SENDGRID_API_KEY must be configured for the SendGrid provider.",
                    id="communications.E002",
                )
            )
        if not str(settings.SENDGRID_FROM_EMAIL).strip():
            errors.append(
                Error(
                    "SENDGRID_FROM_EMAIL must be configured for the SendGrid provider.",
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
    if provider == "twilio_email":
        if not str(settings.TWILIO_EMAIL_API_KEY_SID).strip():
            errors.append(
                Error(
                    "TWILIO_EMAIL_API_KEY_SID must be configured for the Twilio Email provider.",
                    id="communications.E005",
                )
            )
        if not str(settings.TWILIO_EMAIL_API_KEY_SECRET).strip():
            errors.append(
                Error(
                    "TWILIO_EMAIL_API_KEY_SECRET must be configured for the Twilio Email provider.",
                    id="communications.E006",
                )
            )
        if not str(settings.TWILIO_EMAIL_FROM_EMAIL).strip():
            errors.append(
                Error(
                    "TWILIO_EMAIL_FROM_EMAIL must be configured for the Twilio Email provider.",
                    id="communications.E007",
                )
            )
        if int(settings.TWILIO_EMAIL_TIMEOUT_SECONDS) <= 0:
            errors.append(
                Error(
                    "TWILIO_EMAIL_TIMEOUT_SECONDS must be positive.",
                    id="communications.E008",
                )
            )
    return errors
