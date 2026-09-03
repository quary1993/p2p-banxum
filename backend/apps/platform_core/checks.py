from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_qa_dev_mode_not_enabled_in_production(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    if bool(getattr(settings, "IS_PRODUCTION", False)) and bool(
        getattr(settings, "QA_DEV_MODE_ALLOWED", False)
    ):
        return [
            Error(
                "QA_DEV_MODE_ALLOWED must be false in production.",
                id="platform_core.E001",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_scheduled_jobs_actor_configured(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    if str(getattr(settings, "ENVIRONMENT", "local")) in {"local", "test"}:
        return []
    if str(getattr(settings, "SCHEDULED_JOBS_ACTOR_EMAIL", "")).strip():
        return []
    return [
        Error(
            "SCHEDULED_JOBS_ACTOR_EMAIL is required outside local/test environments.",
            hint=(
                "Set it to a dedicated active admin account before running automated "
                "funding, ageing, servicing, or reconciliation jobs."
            ),
            id="platform_core.E002",
        )
    ]
