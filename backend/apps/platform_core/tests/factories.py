from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Any, TypedDict

# The PIN every test investor gets from these helpers (ACC-DEC-009). Not weak.
TEST_SENSITIVE_ACTION_PIN = "482916"
_TEST_PIN_HASH: dict[str, str] = {}


@dataclass(frozen=True, slots=True)
class SensitiveActionTestCode:
    code_id: str
    raw_code: str
    pin: str = TEST_SENSITIVE_ACTION_PIN


class SensitiveActionCodePayload(TypedDict):
    sensitive_action_code_id: str
    sensitive_action_code: str
    pin: str


def _cheap_test_pin_hash(pin: str) -> str:
    """A real Django PBKDF2 hash with few iterations, so tests stay fast.

    check_password() reads the iteration count from the hash itself.
    """

    if pin not in _TEST_PIN_HASH:
        hashers: Any = import_module("django.contrib.auth.hashers")
        _TEST_PIN_HASH[pin] = hashers.PBKDF2PasswordHasher().encode(
            pin, hashers.PBKDF2PasswordHasher().salt(), iterations=1000
        )
    return _TEST_PIN_HASH[pin]


def give_test_pin(user: Any, pin: str = TEST_SENSITIVE_ACTION_PIN) -> str:
    """Give a test investor a PIN (once); returns the PIN to send with sensitive actions."""

    accounts_models: Any = import_module("backend.apps.accounts_auth.models")
    timezone: Any = import_module("django.utils.timezone")
    now = timezone.now()
    accounts_models.SensitiveActionPin.objects.get_or_create(
        user_id=user.pk,
        defaults={"pin_hash": _cheap_test_pin_hash(pin), "set_at": now, "changed_at": now},
    )
    return pin


def issue_sensitive_action_test_code(user: Any, action: str) -> SensitiveActionTestCode:
    """An email code for the action; the user also gets the test PIN if it has none."""

    accounts_models: Any = import_module("backend.apps.accounts_auth.models")
    accounts_services: Any = import_module("backend.apps.accounts_auth.services")

    pin = give_test_pin(user)
    result = accounts_services.issue_sensitive_action_code(
        accounts_services.SensitiveActionCodeCommand(
            user=user,
            action=accounts_models.SensitiveAction(action),
        )
    )
    return SensitiveActionTestCode(
        code_id=str(result.code_record.id),
        raw_code=result.raw_code,
        pin=pin,
    )


def assert_pin_guards_sensitive_action(
    post: Callable[[dict[str, str]], Any],
    user: Any,
    action: str,
    *,
    success_status: int,
) -> Any:
    """Run the PIN checks of one sensitive endpoint (ACC-DEC-009) and return the success.

    ``post`` sends the endpoint's full request with the given code and PIN fields.
    No PIN yet answers 409 ``pin_required``, a wrong PIN 400 ``pin_invalid``; neither
    touches the email code, which then works with the right PIN.
    """

    accounts_models: Any = import_module("backend.apps.accounts_auth.models")
    accounts_models.SensitiveActionPin.objects.filter(user_id=user.pk).delete()
    code = issue_sensitive_action_test_code(user, action)
    accounts_models.SensitiveActionPin.objects.filter(user_id=user.pk).delete()
    fields = {
        "sensitive_action_code_id": code.code_id,
        "sensitive_action_code": code.raw_code,
    }

    required = post({**fields, "pin": TEST_SENSITIVE_ACTION_PIN})
    assert required.status_code == 409, required.content
    assert required.json()["code"] == "pin_required"

    give_test_pin(user)
    wrong_pin = "999990" if TEST_SENSITIVE_ACTION_PIN != "999990" else "999991"
    invalid = post({**fields, "pin": wrong_pin})
    assert invalid.status_code == 400, invalid.content
    assert invalid.json()["code"] == "pin_invalid"
    assert invalid.json()["attempts_left"] == 4

    code_record = accounts_models.SensitiveActionCode.objects.get(id=code.code_id)
    assert code_record.consumed_at is None
    assert code_record.attempts == 0

    success = post({**fields, "pin": TEST_SENSITIVE_ACTION_PIN})
    assert success.status_code == success_status, success.content
    code_record.refresh_from_db()
    assert code_record.consumed_at is not None
    return success


def sensitive_action_test_payload(user: Any, action: str) -> SensitiveActionCodePayload:
    """The request fields of a sensitive action: email code and PIN."""

    code = issue_sensitive_action_test_code(user, action)
    return {
        "sensitive_action_code_id": code.code_id,
        "sensitive_action_code": code.raw_code,
        "pin": code.pin,
    }
