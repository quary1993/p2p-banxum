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


def _is_local_environment() -> bool:
    return str(getattr(settings, "ENVIRONMENT", "local")).strip().lower() == "local"


@register(Tags.security, deploy=True)
def check_debug_off_outside_local(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    """Debug pages show settings and code; only local development may turn them on."""

    if _is_local_environment() or not bool(getattr(settings, "DEBUG", False)):
        return []
    return [
        Error(
            "DJANGO_DEBUG must be false outside local development.",
            hint="Remove DJANGO_DEBUG from the environment or set it to false.",
            id="platform_core.E003",
        )
    ]


@register(Tags.security, deploy=True)
def check_client_ip_source_behind_proxy(
    app_configs: object | None,
    **kwargs: Any,
) -> list[Error]:
    """Behind a proxy, client IPs need TRUSTED_PROXY_COUNT (audit A-48).

    With 0, every request seems to come from the proxy, so the per-IP login limits
    become platform-wide and one person can block login for everybody.
    """

    if _is_local_environment():
        return []
    behind_proxy = getattr(settings, "SECURE_PROXY_SSL_HEADER", None) is not None
    if not behind_proxy or int(getattr(settings, "TRUSTED_PROXY_COUNT", 0) or 0) > 0:
        return []
    return [
        Error(
            "TRUSTED_PROXY_COUNT must be set when Django runs behind a reverse proxy.",
            hint=(
                "Set it to the number of proxies that add X-Forwarded-For entries "
                "(Caddy -> nginx -> backend: 2)."
            ),
            id="platform_core.E004",
        )
    ]
