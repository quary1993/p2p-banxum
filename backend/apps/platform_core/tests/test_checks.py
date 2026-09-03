from __future__ import annotations

from typing import Any

from django.core.checks import run_checks


def _error_ids() -> set[str]:
    return {
        message.id
        for message in run_checks(include_deployment_checks=True)
        if message.id is not None
    }


def test_platform_checks_are_registered(settings: Any) -> None:
    settings.ENVIRONMENT = "production"
    settings.IS_PRODUCTION = True
    settings.QA_DEV_MODE_ALLOWED = True
    settings.SCHEDULED_JOBS_ACTOR_EMAIL = ""

    assert {"platform_core.E001", "platform_core.E002"} <= _error_ids()


def test_scheduler_actor_check_accepts_nonempty_configuration(settings: Any) -> None:
    settings.ENVIRONMENT = "staging"
    settings.IS_PRODUCTION = False
    settings.QA_DEV_MODE_ALLOWED = False
    settings.SCHEDULED_JOBS_ACTOR_EMAIL = "scheduler@banxum.example"

    assert "platform_core.E002" not in _error_ids()
