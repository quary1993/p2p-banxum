from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any
from uuid import UUID

from django.db.models import Model


class SensitiveActionVerificationError(ValueError):
    pass


WITHDRAWAL_ACTION = "withdrawal"
BANK_ACCOUNT_CHANGE_ACTION = "bank_account_change"
FX_ACTION = "fx"
PRIMARY_INVESTMENT_ACTION = "primary_investment"
SECONDARY_MARKET_LISTING_ACTION = "secondary_market_listing"
SECONDARY_MARKET_PURCHASE_ACTION = "secondary_market_purchase"


@dataclass(frozen=True, slots=True)
class SensitiveActionVerificationCommand:
    actor: Model
    action: str
    code_id: str
    raw_code: str
    ip_address: str | None = None
    user_agent: str = ""


def _normalized_code_id(code_id: str) -> str:
    raw = str(code_id).strip()
    if not raw:
        raise SensitiveActionVerificationError("Sensitive-action email code is required.")
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise SensitiveActionVerificationError(
            "Sensitive-action email code is invalid or expired."
        ) from exc


def _raw_code(raw_code: str) -> str:
    raw = str(raw_code).strip()
    if not raw:
        raise SensitiveActionVerificationError("Sensitive-action email code is required.")
    return raw


def verify_sensitive_action_code(command: SensitiveActionVerificationCommand) -> None:
    """Verify a fresh email code before starting an irreversible action.

    Call this outside rollbackable financial transactions. Wrong attempts must commit
    independently so the per-code brute-force limit cannot be erased by an outer
    transaction rollback.
    """
    accounts_services: Any = import_module("backend.apps.accounts_auth.services")
    try:
        accounts_services.consume_sensitive_action_code(
            accounts_services.SensitiveActionCodeConsumeCommand(
                code_id=_normalized_code_id(command.code_id),
                raw_code=_raw_code(command.raw_code),
                expected_user=command.actor,
                expected_action=command.action,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
    except Exception as exc:
        accounts_error = getattr(accounts_services, "AccountsAuthError", None)
        if accounts_error is not None and isinstance(exc, accounts_error):
            raise SensitiveActionVerificationError(str(exc)) from exc
        raise
