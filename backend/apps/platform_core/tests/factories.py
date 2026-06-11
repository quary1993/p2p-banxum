from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, TypedDict


@dataclass(frozen=True, slots=True)
class SensitiveActionTestCode:
    code_id: str
    raw_code: str


class SensitiveActionCodePayload(TypedDict):
    sensitive_action_code_id: str
    sensitive_action_code: str


def issue_sensitive_action_test_code(user: Any, action: str) -> SensitiveActionTestCode:
    accounts_models: Any = import_module("backend.apps.accounts_auth.models")
    accounts_services: Any = import_module("backend.apps.accounts_auth.services")

    result = accounts_services.issue_sensitive_action_code(
        accounts_services.SensitiveActionCodeCommand(
            user=user,
            action=accounts_models.SensitiveAction(action),
        )
    )
    return SensitiveActionTestCode(code_id=str(result.code_record.id), raw_code=result.raw_code)
