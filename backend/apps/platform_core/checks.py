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
