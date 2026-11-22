from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any
from uuid import UUID

from django.db.models import Model

from backend.apps.platform_core.domain import operation_binding


class SensitiveActionVerificationError(ValueError):
    pass


class SensitiveActionPinError(SensitiveActionVerificationError):
    """The PIN check refused the action (ACC-DEC-009).

    Modules let this error pass instead of wrapping it in their own validation error,
    so the API can answer with its status and code: 400 ``pin_invalid`` (with
    ``attempts_left``), 423 ``pin_locked`` (with ``locked_until``) or 409
    ``pin_required`` (no PIN yet). The email code is untouched in every case.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        http_status: int,
        extra: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.extra = dict(extra or {})

    def payload(self) -> dict[str, object]:
        return {"detail": str(self), "code": self.code, **self.extra}


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
    # The second factor of the operation, checked before the email code: the 6-digit PIN, or
    # the authenticator app code when the investor has an active app (D-1: the app replaces
    # the PIN everywhere). The API field stays ``pin`` for both.
    pin: str = field(repr=False)
    ip_address: str | None = None
    user_agent: str = ""
    # 18.5: the operation details built from the module's own data (operation_binding). The
    # email code must have been requested for the same details.
    operation: Mapping[str, object] | None = None


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


def _expected_fingerprint(command: SensitiveActionVerificationCommand) -> str | None:
    if not operation_binding.is_bound_action(command.action):
        return None
    if not command.operation:
        raise SensitiveActionVerificationError("The operation details are missing.")
    try:
        return operation_binding.operation_fingerprint(command.action, command.operation)
    except operation_binding.OperationBindingError as exc:
        raise SensitiveActionVerificationError(str(exc)) from exc


def _verify_pin(command: SensitiveActionVerificationCommand) -> None:
    pin_services: Any = import_module("backend.apps.accounts_auth.pin_services")
    try:
        pin_services.verify_pin(
            pin_services.VerifyPinCommand(
                user=command.actor,
                pin=str(command.pin),
                action=command.action,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
    except pin_services.PinError as exc:
        raise SensitiveActionPinError(
            str(exc),
            code=str(exc.code),
            http_status=int(exc.http_status),
            extra=dict(exc.extra),
        ) from exc


def verify_sensitive_action_code(command: SensitiveActionVerificationCommand) -> None:
    """Verify the second factor and a fresh email code before starting an irreversible action.

    Order: operation details, second factor (PIN lock and PIN, or the authenticator app lock
    and code when the investor has an active app), email code. A wrong PIN or app code never
    uses up the email code, and it counts toward its lock even when the email code is right.
    The email code must have been requested for the same operation details (18.5).

    Call this outside rollbackable financial transactions. Wrong attempts must commit
    independently so the per-code and per-PIN limits cannot be erased by an outer
    transaction rollback.
    """
    code_id = _normalized_code_id(command.code_id)
    raw_code = _raw_code(command.raw_code)
    expected_fingerprint = _expected_fingerprint(command)
    two_factor: Any = import_module("backend.apps.accounts_auth.two_factor")
    if two_factor.factor_kind(command.actor) == two_factor.FACTOR_APP:
        try:
            two_factor.check_app_code(
                command.actor, str(command.pin), context=f"operation:{command.action}"
            )
        except two_factor.TwoFactorError as exc:
            raise SensitiveActionPinError(
                str(exc),
                code=str(exc.code),
                http_status=int(exc.http_status),
                extra=dict(exc.extra),
            ) from exc
    else:
        _verify_pin(command)

    accounts_services: Any = import_module("backend.apps.accounts_auth.services")
    try:
        accounts_services.consume_sensitive_action_code(
            accounts_services.SensitiveActionCodeConsumeCommand(
                code_id=code_id,
                raw_code=raw_code,
                expected_user=command.actor,
                expected_action=command.action,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                expected_operation_fingerprint=expected_fingerprint,
            )
        )
    except Exception as exc:
        accounts_error = getattr(accounts_services, "AccountsAuthError", None)
        if accounts_error is not None and isinstance(exc, accounts_error):
            raise SensitiveActionVerificationError(str(exc)) from exc
        raise
