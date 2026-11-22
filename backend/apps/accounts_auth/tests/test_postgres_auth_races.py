"""IP of Webby-Soft SRL. Audit S4-2 and S4-3: the races, with concurrent PostgreSQL transactions.

SQLite runs one writer at a time, so these tests are skipped there; they run in the PostgreSQL
hardening pack. Each test releases several threads at the same moment against one account.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from backend.apps.accounts_auth import factor_sms
from backend.apps.accounts_auth.models import (
    PhoneVerificationChallenge,
    SensitiveAction,
    SensitiveActionCode,
    User,
)
from backend.apps.accounts_auth.services import (
    PhoneVerificationThrottleError,
    SensitiveActionCodeCommand,
    SensitiveActionCodeThrottleError,
    issue_sensitive_action_code,
)

pytestmark = pytest.mark.django_db(transaction=True)

CALLERS = 8


def _require_postgres() -> None:
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL-only concurrency test.")


def _investor() -> User:
    return User.objects.create_user(
        email="race-investor@example.test",
        full_name="Race Investor",
        account_type="natural_person_lender",
        status="active",
        phone_number="+41790000321",
        phone_verified_at=timezone.now(),
    )


def _together(call: Any) -> list[Any]:
    """Run ``call(index)`` in CALLERS threads released at the same moment."""
    barrier = threading.Barrier(CALLERS)

    def run(index: int) -> Any:
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return call(index)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=CALLERS) as executor:
        return list(executor.map(run, range(CALLERS)))


def _operation(amount_minor: int) -> dict[str, object]:
    return {"amount_minor": amount_minor, "currency": "CHF", "iban": "CH5604835012345678009"}


def _issue(user_id: Any, amount_minor: int) -> str:
    try:
        issue_sensitive_action_code(
            SensitiveActionCodeCommand(
                user=User.objects.get(pk=user_id),
                action=SensitiveAction.WITHDRAWAL,
                operation=_operation(amount_minor),
            )
        )
    except SensitiveActionCodeThrottleError:
        return "throttled"
    return "issued"


def test_the_same_operation_at_the_same_moment_gets_one_code() -> None:
    """Audit S4-3: the cooldown holds for simultaneous requests with one fingerprint."""
    _require_postgres()
    user = _investor()
    results = _together(lambda _index: _issue(user.pk, 500_00))
    assert results.count("issued") == 1
    assert SensitiveActionCode.objects.filter(user=user).count() == 1


def test_changed_details_at_the_same_moment_leave_one_active_code_within_the_caps(
    settings: Any,
) -> None:
    """Audit S4-3: different fingerprints skip the cooldown, but each new code supersedes the
    older one and the hourly cap is never passed."""
    _require_postgres()
    settings.AUTH_SENSITIVE_CODE_HOURLY_LIMIT = 5
    user = _investor()
    results = _together(lambda index: _issue(user.pk, 100_00 + index))
    assert results.count("issued") == 5
    codes = SensitiveActionCode.objects.filter(user=user)
    assert codes.count() == 5
    assert codes.filter(consumed_at__isnull=True, superseded_at__isnull=True).count() == 1


def test_sms_codes_at_the_same_moment_stay_within_the_account_limit(settings: Any) -> None:
    """Audit S4-2: the account's row lock makes the SMS cooldown and limits exact."""
    _require_postgres()
    settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS = 0
    settings.AUTH_SMS_ACCOUNT_HOURLY_LIMIT = 3
    user = _investor()

    def send(_index: int) -> str:
        try:
            factor_sms.send_code(User.objects.get(pk=user.pk), purpose="sign_in")
        except PhoneVerificationThrottleError:
            return "throttled"
        return "sent"

    results = _together(send)
    assert results.count("sent") == 3
    assert PhoneVerificationChallenge.objects.filter(user=user).count() == 3
    # With the cooldown on, simultaneous requests send one SMS.
    PhoneVerificationChallenge.objects.filter(user=user).delete()
    settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS = 60
    assert _together(send).count("sent") == 1
