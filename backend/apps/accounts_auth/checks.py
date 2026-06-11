from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_phone_verification_provider_config(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    if str(settings.ENVIRONMENT).lower() == "local":
        return []

    errors: list[Error] = []
    provider = str(settings.PHONE_VERIFICATION_PROVIDER).strip().lower()
    if provider != "twilio_verify":
        errors.append(
            Error(
                "PHONE_VERIFICATION_PROVIDER must be twilio_verify outside local development.",
                id="accounts_auth.E001",
            )
        )
    has_account_auth = bool(
        str(settings.TWILIO_ACCOUNT_SID).strip()
        and str(settings.TWILIO_AUTH_TOKEN).strip()
    )
    has_api_key_auth = bool(
        str(settings.TWILIO_API_KEY_SID).strip()
        and str(settings.TWILIO_API_KEY_SECRET).strip()
    )
    if not has_account_auth and not has_api_key_auth:
        errors.append(
            Error(
                (
                    "Twilio credentials must be configured outside local development. "
                    "Set either TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN or "
                    "TWILIO_API_KEY_SID/TWILIO_API_KEY_SECRET."
                ),
                id="accounts_auth.E002",
            )
        )
    if not str(settings.TWILIO_VERIFY_SERVICE_SID).strip():
        errors.append(
            Error(
                "TWILIO_VERIFY_SERVICE_SID must be configured outside local development.",
                id="accounts_auth.E004",
            )
        )
    if int(settings.TWILIO_TIMEOUT_SECONDS) <= 0:
        errors.append(
            Error(
                "TWILIO_TIMEOUT_SECONDS must be positive.",
                id="accounts_auth.E005",
            )
        )
    return errors
