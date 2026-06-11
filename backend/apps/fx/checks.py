from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_fx_provider_config(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    if str(settings.ENVIRONMENT).lower() == "local":
        return []

    errors: list[Error] = []
    provider = str(settings.FX_RATE_PROVIDER).strip().lower()
    if provider != "yahoo_finance":
        errors.append(
            Error(
                "FX_RATE_PROVIDER must be yahoo_finance outside local development.",
                id="fx.E001",
            )
        )
    if not str(settings.FX_YAHOO_CHART_URL).strip():
        errors.append(
            Error(
                "FX_YAHOO_CHART_URL must be configured outside local development.",
                id="fx.E002",
            )
        )
    if int(settings.FX_YAHOO_TIMEOUT_SECONDS) <= 0:
        errors.append(
            Error(
                "FX_YAHOO_TIMEOUT_SECONDS must be positive.",
                id="fx.E003",
            )
        )
    return errors
