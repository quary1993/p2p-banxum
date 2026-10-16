"""IP of Webby-Soft SRL. Investor PIN for sensitive actions (ACC-DEC-009)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.hashers import check_password
from django.test import Client
from django.test.utils import override_settings
from django.utils import timezone

from backend.apps.accounts_auth.api.throttles import PinThrottle, WindowRule
from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    PhoneVerificationChallenge,
    PhoneVerificationPurpose,
    PhoneVerificationStatus,
    SensitiveAction,
    SensitiveActionCode,
    SensitiveActionPin,
    User,
)
from backend.apps.accounts_auth.phone_providers import (
    PhoneVerificationCheckResult,
    PhoneVerificationStartResult,
)
from backend.apps.accounts_auth.pin_services import (
    ChangePinCommand,
    ConfirmPinResetCommand,
    PhoneCodeInvalidError,
    PinAlreadySetError,
    PinInvalidError,
    PinLockedError,
    PinMismatchError,
    PinNotAvailableError,
    PinPhoneVerificationRequiredError,
    PinResetUnavailableError,
    PinUnchangedError,
    PinWeakError,
    SetPinCommand,
    StartPinResetCommand,
    VerifyPinCommand,
    assign_known_qa_pin,
    change_pin,
    confirm_pin_reset,
    pin_status_for_user,
    pin_weakness,
    set_first_pin,
    start_pin_reset,
    verify_pin,
)
from backend.apps.accounts_auth.services import (
    InvalidOrExpiredCodeError,
    PhoneVerificationConfirmCommand,
    SensitiveActionCodeCommand,
    confirm_phone_verification,
    issue_sensitive_action_code,
)
from backend.apps.platform_core.models import AuditEvent, OutboxMessage
from backend.apps.platform_core.services.sensitive_actions import (
    SensitiveActionPinError,
    SensitiveActionVerificationCommand,
    SensitiveActionVerificationError,
    verify_sensitive_action_code,
)

PIN = "482916"
NEW_PIN = "730519"


def _user(
    email: str = "pin-investor@example.test",
    *,
    status: str = AccountStatus.ACTIVE,
    phone_verified: bool = True,
    account_type: str = AccountType.NATURAL_PERSON_LENDER,
) -> User:
    return User.objects.create_user(
        email=email,
        full_name="Pin Investor",
        account_type=account_type,
        status=status,
        phone_number="+41790000042",
        phone_verified_at=timezone.now() if phone_verified else None,
    )


def _code(user: User, action: SensitiveAction) -> tuple[str, str]:
    result = issue_sensitive_action_code(SensitiveActionCodeCommand(user=user, action=action))
    return str(result.code_record.id), result.raw_code


def _with_pin(user: User, pin: str = PIN) -> User:
    code_id, raw_code = _code(user, SensitiveAction.PIN_SETUP)
    set_first_pin(
        SetPinCommand(
            user=user,
            new_pin=pin,
            new_pin_confirmation=pin,
            sensitive_action_code_id=code_id,
            sensitive_action_code=raw_code,
        )
    )
    return user


def _verify(user: User, *, pin: str, code_id: str, raw_code: str) -> None:
    verify_sensitive_action_code(
        SensitiveActionVerificationCommand(
            actor=user,
            action=SensitiveAction.WITHDRAWAL,
            code_id=code_id,
            raw_code=raw_code,
            pin=pin,
        )
    )


def _record(user: User) -> SensitiveActionPin:
    return SensitiveActionPin.objects.get(user=user)


# ---- Hashing and rules ---------------------------------------------------------------------


@pytest.mark.django_db
def test_pin_is_stored_only_as_a_django_password_hash() -> None:
    user = _with_pin(_user())

    record = _record(user)
    assert record.pin_hash.startswith("pbkdf2_sha256$")
    assert PIN not in record.pin_hash
    assert check_password(PIN, record.pin_hash)
    assert record.set_at == record.changed_at
    assert record.failed_attempts == 0
    assert record.locked_until is None


@pytest.mark.parametrize(
    "pin",
    ["000000", "111111", "999999", "123456", "234567", "456789", "012345", "654321", "987654"],
)
def test_weak_pins_are_refused_with_a_clear_message(pin: str) -> None:
    reason = pin_weakness(pin)

    assert reason is not None
    assert "like" in reason


@pytest.mark.parametrize("pin", ["12345", "1234567", "12a456", "", " 48291"])
def test_a_pin_must_be_exactly_six_digits(pin: str) -> None:
    assert pin_weakness(pin) == "Your PIN must be exactly 6 digits."


@pytest.mark.parametrize("pin", [PIN, NEW_PIN, "246810", "102938", "112233", "123465"])
def test_ordinary_pins_are_accepted(pin: str) -> None:
    assert pin_weakness(pin) is None


@pytest.mark.django_db
def test_a_weak_or_mismatched_new_pin_is_refused_before_anything_is_stored() -> None:
    user = _user(status=AccountStatus.PENDING_KYC)

    with pytest.raises(PinWeakError):
        set_first_pin(SetPinCommand(user=user, new_pin="123456", new_pin_confirmation="123456"))
    with pytest.raises(PinMismatchError):
        set_first_pin(SetPinCommand(user=user, new_pin=PIN, new_pin_confirmation=NEW_PIN))
    assert not SensitiveActionPin.objects.exists()


# ---- First PIN -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_registration_pin_needs_no_email_code() -> None:
    user = _user(status=AccountStatus.PENDING_KYC)

    set_first_pin(SetPinCommand(user=user, new_pin=PIN, new_pin_confirmation=PIN))

    assert check_password(PIN, _record(user).pin_hash)
    event = AuditEvent.objects.get(action="auth.pin_set", target_id=str(user.id))
    assert event.metadata["source"] == "registration"
    assert pin_status_for_user(user).setup_requires_email_code is False


@pytest.mark.django_db
def test_registration_pin_needs_the_verified_phone_first() -> None:
    user = _user(status=AccountStatus.PENDING_KYC, phone_verified=False)

    with pytest.raises(PinPhoneVerificationRequiredError):
        set_first_pin(SetPinCommand(user=user, new_pin=PIN, new_pin_confirmation=PIN))


@pytest.mark.django_db
def test_first_pin_of_an_active_account_needs_a_fresh_pin_setup_email_code() -> None:
    user = _user()
    assert pin_status_for_user(user).setup_requires_email_code is True

    with pytest.raises(InvalidOrExpiredCodeError):
        set_first_pin(SetPinCommand(user=user, new_pin=PIN, new_pin_confirmation=PIN))
    withdrawal_code_id, withdrawal_code = _code(user, SensitiveAction.WITHDRAWAL)
    with pytest.raises(InvalidOrExpiredCodeError):
        set_first_pin(
            SetPinCommand(
                user=user,
                new_pin=PIN,
                new_pin_confirmation=PIN,
                sensitive_action_code_id=withdrawal_code_id,
                sensitive_action_code=withdrawal_code,
            )
        )
    assert not SensitiveActionPin.objects.filter(user=user).exists()

    _with_pin(user)

    assert check_password(PIN, _record(user).pin_hash)
    event = AuditEvent.objects.get(action="auth.pin_set", target_id=str(user.id))
    assert event.metadata["source"] == "pin_setup"


@pytest.mark.django_db
def test_a_second_first_pin_is_refused() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.PIN_SETUP)

    with pytest.raises(PinAlreadySetError):
        set_first_pin(
            SetPinCommand(
                user=user,
                new_pin=NEW_PIN,
                new_pin_confirmation=NEW_PIN,
                sensitive_action_code_id=code_id,
                sensitive_action_code=raw_code,
            )
        )
    assert check_password(PIN, _record(user).pin_hash)
    # The refusal comes before the email code is used.
    assert SensitiveActionCode.objects.get(id=code_id).consumed_at is None


@pytest.mark.django_db
def test_admins_have_no_pin() -> None:
    admin = User.objects.create_user(
        email="admin-pin@example.test",
        full_name="Admin",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )

    with pytest.raises(PinNotAvailableError):
        set_first_pin(SetPinCommand(user=admin, new_pin=PIN, new_pin_confirmation=PIN))


# ---- Central check: PIN lock -> PIN -> email code -------------------------------------------


@pytest.mark.django_db
def test_sensitive_action_without_a_pin_answers_pin_required_and_keeps_the_code() -> None:
    user = _user()
    code_id, raw_code = _code(user, SensitiveAction.WITHDRAWAL)

    with pytest.raises(SensitiveActionPinError) as error:
        _verify(user, pin=PIN, code_id=code_id, raw_code=raw_code)

    assert error.value.code == "pin_required"
    assert error.value.http_status == 409
    code = SensitiveActionCode.objects.get(id=code_id)
    assert code.consumed_at is None
    assert code.attempts == 0


@pytest.mark.django_db
def test_wrong_pin_with_the_right_code_does_not_use_up_the_code() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.WITHDRAWAL)

    with pytest.raises(SensitiveActionPinError) as error:
        _verify(user, pin="999990", code_id=code_id, raw_code=raw_code)

    assert error.value.code == "pin_invalid"
    assert error.value.http_status == 400
    assert error.value.extra == {"attempts_left": 4}
    assert "4 attempts left" in str(error.value)
    code = SensitiveActionCode.objects.get(id=code_id)
    assert code.consumed_at is None
    assert code.attempts == 0
    assert _record(user).failed_attempts == 1
    # The same email code still works with the right PIN.
    _verify(user, pin=PIN, code_id=code_id, raw_code=raw_code)
    assert SensitiveActionCode.objects.get(id=code_id).consumed_at is not None


@pytest.mark.django_db
def test_right_pin_with_a_wrong_code_resets_the_pin_count_and_counts_the_code_attempt() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.WITHDRAWAL)
    with pytest.raises(SensitiveActionPinError):
        _verify(user, pin="999990", code_id=code_id, raw_code=raw_code)
    assert _record(user).failed_attempts == 1

    wrong_code = "000000" if raw_code != "000000" else "111111"
    with pytest.raises(SensitiveActionVerificationError) as error:
        _verify(user, pin=PIN, code_id=code_id, raw_code=wrong_code)

    assert not isinstance(error.value, SensitiveActionPinError)
    assert _record(user).failed_attempts == 0
    assert SensitiveActionCode.objects.get(id=code_id).attempts == 1
    assert AuditEvent.objects.filter(action="auth.pin_verified", target_id=str(user.id)).exists()


@pytest.mark.django_db
def test_five_wrong_pins_lock_the_pin_for_thirty_minutes_with_audit_and_email() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.WITHDRAWAL)
    before = timezone.now()

    for attempt in range(1, 5):
        with pytest.raises(SensitiveActionPinError) as error:
            _verify(user, pin="999990", code_id=code_id, raw_code=raw_code)
        assert error.value.code == "pin_invalid"
        assert error.value.extra["attempts_left"] == 5 - attempt
    with pytest.raises(SensitiveActionPinError) as locked:
        _verify(user, pin="999990", code_id=code_id, raw_code=raw_code)

    assert locked.value.code == "pin_locked"
    assert locked.value.http_status == 423
    record = _record(user)
    assert record.locked_until is not None
    assert (
        before + timedelta(minutes=30)
        <= record.locked_until
        <= timezone.now() + timedelta(minutes=30)
    )
    assert locked.value.extra == {"locked_until": record.locked_until.isoformat()}
    lock_event = AuditEvent.objects.get(action="auth.pin_locked", target_id=str(user.id))
    assert lock_event.metadata["max_attempts"] == 5
    notice = OutboxMessage.objects.get(topic="email.pin_locked")
    assert notice.payload["email"] == user.email
    assert "Your PIN was locked after 5 wrong attempts" in notice.payload["body_text"]
    # The email code was never touched.
    assert SensitiveActionCode.objects.get(id=code_id).attempts == 0

    # Locked: even the right PIN is refused, without counting.
    with pytest.raises(SensitiveActionPinError) as still_locked:
        _verify(user, pin=PIN, code_id=code_id, raw_code=raw_code)
    assert still_locked.value.code == "pin_locked"
    assert OutboxMessage.objects.filter(topic="email.pin_locked").count() == 1

    # After the lock time the right PIN works again and the count starts from zero.
    SensitiveActionPin.objects.filter(user=user).update(
        locked_until=timezone.now() - timedelta(seconds=1)
    )
    assert pin_status_for_user(user).attempts_left == 5
    _verify(user, pin=PIN, code_id=code_id, raw_code=raw_code)
    assert _record(user).locked_until is None


@pytest.mark.django_db
@override_settings(AUTH_PIN_MAX_ATTEMPTS=2, AUTH_PIN_LOCK_SECONDS=120)
def test_pin_lock_limits_are_configurable() -> None:
    user = _with_pin(_user())

    with pytest.raises(PinInvalidError):
        verify_pin(VerifyPinCommand(user=user, pin="999990"))
    with pytest.raises(PinLockedError):
        verify_pin(VerifyPinCommand(user=user, pin="999990"))

    locked_until = _record(user).locked_until
    assert locked_until is not None
    assert locked_until <= timezone.now() + timedelta(seconds=120)
    assert locked_until > timezone.now() + timedelta(seconds=100)


@pytest.mark.django_db
def test_a_correct_pin_resets_the_wrong_attempt_count() -> None:
    user = _with_pin(_user())
    for _ in range(3):
        with pytest.raises(PinInvalidError):
            verify_pin(VerifyPinCommand(user=user, pin="999990"))

    verify_pin(VerifyPinCommand(user=user, pin=PIN))

    assert _record(user).failed_attempts == 0
    with pytest.raises(PinInvalidError) as error:
        verify_pin(VerifyPinCommand(user=user, pin="999990"))
    assert error.value.extra["attempts_left"] == 4


# ---- Change PIN ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_change_pin_needs_the_current_pin_an_email_code_and_the_new_pin_twice() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.PIN_CHANGE)

    with pytest.raises(PinInvalidError):
        change_pin(
            ChangePinCommand(
                user=user,
                pin="999990",
                new_pin=NEW_PIN,
                new_pin_confirmation=NEW_PIN,
                sensitive_action_code_id=code_id,
                sensitive_action_code=raw_code,
            )
        )
    assert SensitiveActionCode.objects.get(id=code_id).consumed_at is None
    with pytest.raises(PinUnchangedError):
        change_pin(
            ChangePinCommand(
                user=user,
                pin=PIN,
                new_pin=PIN,
                new_pin_confirmation=PIN,
                sensitive_action_code_id=code_id,
                sensitive_action_code=raw_code,
            )
        )
    with pytest.raises(PinMismatchError):
        change_pin(
            ChangePinCommand(
                user=user,
                pin=PIN,
                new_pin=NEW_PIN,
                new_pin_confirmation=PIN,
                sensitive_action_code_id=code_id,
                sensitive_action_code=raw_code,
            )
        )

    change_pin(
        ChangePinCommand(
            user=user,
            pin=PIN,
            new_pin=NEW_PIN,
            new_pin_confirmation=NEW_PIN,
            sensitive_action_code_id=code_id,
            sensitive_action_code=raw_code,
        )
    )

    record = _record(user)
    assert check_password(NEW_PIN, record.pin_hash)
    assert record.changed_at > record.set_at
    assert SensitiveActionCode.objects.get(id=code_id).consumed_at is not None
    assert AuditEvent.objects.filter(action="auth.pin_changed", target_id=str(user.id)).exists()
    notice = OutboxMessage.objects.get(topic="email.pin_changed")
    assert "Your BANXUM PIN was changed." in notice.payload["body_text"]
    assert "If this was not you, contact support" in notice.payload["body_text"]
    with pytest.raises(PinInvalidError):
        verify_pin(VerifyPinCommand(user=user, pin=PIN))
    verify_pin(VerifyPinCommand(user=user, pin=NEW_PIN))


@pytest.mark.django_db
def test_change_pin_with_a_wrong_email_code_keeps_the_old_pin() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.PIN_CHANGE)

    with pytest.raises(InvalidOrExpiredCodeError):
        change_pin(
            ChangePinCommand(
                user=user,
                pin=PIN,
                new_pin=NEW_PIN,
                new_pin_confirmation=NEW_PIN,
                sensitive_action_code_id=code_id,
                sensitive_action_code="000000" if raw_code != "000000" else "111111",
            )
        )

    assert check_password(PIN, _record(user).pin_hash)
    assert not OutboxMessage.objects.filter(topic="email.pin_changed").exists()


# ---- Forgot PIN ----------------------------------------------------------------------------


def _start_reset(user: User) -> tuple[str, str]:
    result = start_pin_reset(StartPinResetCommand(user=user))
    return str(result.challenge.id), result.raw_code


@pytest.mark.django_db
def test_forgot_pin_with_email_and_sms_codes_sets_a_new_pin_and_clears_the_lock() -> None:
    user = _with_pin(_user())
    SensitiveActionPin.objects.filter(user=user).update(
        locked_until=timezone.now() + timedelta(minutes=20)
    )
    code_id, raw_code = _code(user, SensitiveAction.PIN_RESET)
    challenge_id, sms_code = _start_reset(user)
    challenge = PhoneVerificationChallenge.objects.get(id=challenge_id)
    assert challenge.purpose == PhoneVerificationPurpose.PIN_RESET
    assert challenge.phone_number == user.phone_number
    assert OutboxMessage.objects.filter(
        topic="sms.phone_verification_requested", payload__purpose="pin_reset"
    ).exists()

    confirm_pin_reset(
        ConfirmPinResetCommand(
            user=user,
            phone_challenge_id=challenge_id,
            phone_code=sms_code,
            new_pin=NEW_PIN,
            new_pin_confirmation=NEW_PIN,
            sensitive_action_code_id=code_id,
            sensitive_action_code=raw_code,
        )
    )

    record = _record(user)
    assert check_password(NEW_PIN, record.pin_hash)
    assert record.locked_until is None
    assert record.failed_attempts == 0
    assert SensitiveActionCode.objects.get(id=code_id).consumed_at is not None
    assert (
        PhoneVerificationChallenge.objects.get(id=challenge_id).status
        == PhoneVerificationStatus.VERIFIED
    )
    reset_event = AuditEvent.objects.get(action="auth.pin_reset", target_id=str(user.id))
    assert reset_event.metadata["lock_cleared"] is True
    assert OutboxMessage.objects.filter(topic="email.pin_changed").count() == 1
    verify_pin(VerifyPinCommand(user=user, pin=NEW_PIN))


@pytest.mark.django_db
def test_forgot_pin_with_a_wrong_sms_code_keeps_the_email_code_usable() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.PIN_RESET)
    challenge_id, sms_code = _start_reset(user)
    wrong_sms = "000000" if sms_code != "000000" else "111111"

    with pytest.raises(PhoneCodeInvalidError):
        confirm_pin_reset(
            ConfirmPinResetCommand(
                user=user,
                phone_challenge_id=challenge_id,
                phone_code=wrong_sms,
                new_pin=NEW_PIN,
                new_pin_confirmation=NEW_PIN,
                sensitive_action_code_id=code_id,
                sensitive_action_code=raw_code,
            )
        )

    code = SensitiveActionCode.objects.get(id=code_id)
    assert code.consumed_at is None
    assert code.attempts == 0
    assert PhoneVerificationChallenge.objects.get(id=challenge_id).attempts == 1
    confirm_pin_reset(
        ConfirmPinResetCommand(
            user=user,
            phone_challenge_id=challenge_id,
            phone_code=sms_code,
            new_pin=NEW_PIN,
            new_pin_confirmation=NEW_PIN,
            sensitive_action_code_id=code_id,
            sensitive_action_code=raw_code,
        )
    )
    assert check_password(NEW_PIN, _record(user).pin_hash)


@pytest.mark.django_db
def test_forgot_pin_with_a_wrong_email_code_does_not_touch_the_sms_code() -> None:
    user = _with_pin(_user())
    code_id, raw_code = _code(user, SensitiveAction.PIN_RESET)
    challenge_id, sms_code = _start_reset(user)

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_pin_reset(
            ConfirmPinResetCommand(
                user=user,
                phone_challenge_id=challenge_id,
                phone_code=sms_code,
                new_pin=NEW_PIN,
                new_pin_confirmation=NEW_PIN,
                sensitive_action_code_id=code_id,
                sensitive_action_code="000000" if raw_code != "000000" else "111111",
            )
        )

    assert SensitiveActionCode.objects.get(id=code_id).attempts == 1
    challenge = PhoneVerificationChallenge.objects.get(id=challenge_id)
    assert challenge.attempts == 0
    assert challenge.status == PhoneVerificationStatus.PENDING
    assert check_password(PIN, _record(user).pin_hash)


@pytest.mark.django_db
def test_forgot_pin_needs_a_verified_phone() -> None:
    user = _user(phone_verified=False)

    with pytest.raises(PinResetUnavailableError):
        start_pin_reset(StartPinResetCommand(user=user))
    assert pin_status_for_user(user).reset_available is False


@pytest.mark.django_db
def test_a_pin_reset_sms_code_never_verifies_a_phone_number() -> None:
    user = _with_pin(_user())
    challenge_id, sms_code = _start_reset(user)

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(user=user, challenge_id=challenge_id, raw_code=sms_code)
        )


@pytest.mark.django_db
@override_settings(PHONE_VERIFICATION_PROVIDER="twilio_verify")
def test_forgot_pin_uses_twilio_verify_for_the_sms_code(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _with_pin(_user())
    checks: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "backend.apps.accounts_auth.pin_services.start_twilio_verify",
        lambda phone: PhoneVerificationStartResult(provider_reference="VE-1", provider_status="ok"),
    )

    def fake_check(phone: str, code: str) -> PhoneVerificationCheckResult:
        checks.append((phone, code))
        return PhoneVerificationCheckResult(approved=code == "135792", provider_status="approved")

    monkeypatch.setattr("backend.apps.accounts_auth.pin_services.check_twilio_verify", fake_check)
    code_id, raw_code = _code(user, SensitiveAction.PIN_RESET)
    result = start_pin_reset(StartPinResetCommand(user=user))
    assert result.raw_code == ""
    assert result.challenge.provider_reference == "VE-1"

    confirm_pin_reset(
        ConfirmPinResetCommand(
            user=user,
            phone_challenge_id=str(result.challenge.id),
            phone_code="135792",
            new_pin=NEW_PIN,
            new_pin_confirmation=NEW_PIN,
            sensitive_action_code_id=code_id,
            sensitive_action_code=raw_code,
        )
    )

    assert checks == [(user.phone_number, "135792")]
    assert check_password(NEW_PIN, _record(user).pin_hash)


# ---- QA seed helper ------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(ENVIRONMENT="test", IS_PRODUCTION=False)
def test_known_qa_pin_is_set_once_or_replaced_on_request() -> None:
    user = _user()

    assert assign_known_qa_pin(user, pin="246810", source="qa") is True
    assert assign_known_qa_pin(user, pin=NEW_PIN, source="qa") is False
    assert check_password("246810", _record(user).pin_hash)
    assert assign_known_qa_pin(user, pin=NEW_PIN, source="qa", replace=True) is True
    assert check_password(NEW_PIN, _record(user).pin_hash)


@pytest.mark.django_db
@override_settings(ENVIRONMENT="production", IS_PRODUCTION=True)
def test_known_qa_pin_is_refused_in_production() -> None:
    from backend.apps.accounts_auth.services import AccountsAuthError

    with pytest.raises(AccountsAuthError):
        assign_known_qa_pin(_user(), pin="246810", source="qa")


# ---- API -----------------------------------------------------------------------------------


def _client(user: User) -> Client:
    client = Client()
    client.force_login(user)
    return client


def _post(client: Client, path: str, payload: dict[str, Any] | None = None) -> Any:
    return client.post(path, data=payload or {}, content_type="application/json")


@pytest.mark.django_db
def test_me_and_status_tell_the_portal_whether_a_pin_exists_and_whether_it_is_locked() -> None:
    user = _user()
    client = _client(user)

    me = client.get("/api/v1/auth/me/").json()["user"]
    assert me["pin_set"] is False
    assert me["pin_locked_until"] is None
    status = client.get("/api/v1/auth/pin/status/").json()["pin"]
    assert status == {
        "pin_set": False,
        "locked_until": None,
        "attempts_left": 5,
        "max_attempts": 5,
        "setup_requires_email_code": True,
        "reset_available": True,
        "phone_last_digits": "42",
    }

    _with_pin(user)
    locked_until = timezone.now() + timedelta(minutes=10)
    SensitiveActionPin.objects.filter(user=user).update(locked_until=locked_until)

    me = client.get("/api/v1/auth/me/").json()["user"]
    assert me["pin_set"] is True
    assert me["pin_locked_until"] == locked_until.isoformat()
    assert client.get("/api/v1/auth/pin/status/").json()["pin"]["attempts_left"] == 0


@pytest.mark.django_db
def test_registration_pin_api_sets_the_pin_without_an_email_code() -> None:
    user = _user(status=AccountStatus.PENDING_KYC)
    client = _client(user)

    weak = _post(
        client, "/api/v1/auth/pin/set/", {"new_pin": "111111", "new_pin_confirmation": "111111"}
    )
    assert weak.status_code == 400
    assert weak.json()["code"] == "pin_weak"
    response = _post(client, "/api/v1/auth/pin/set/", {"new_pin": PIN, "new_pin_confirmation": PIN})

    assert response.status_code == 201
    assert response.json()["pin"]["pin_set"] is True
    again = _post(client, "/api/v1/auth/pin/set/", {"new_pin": PIN, "new_pin_confirmation": PIN})
    assert again.status_code == 409
    assert again.json()["code"] == "pin_already_set"


@pytest.mark.django_db
def test_kyc_cannot_start_before_the_registration_pin_step() -> None:
    user = _user(status=AccountStatus.PENDING_KYC)
    client = _client(user)

    refused = _post(client, "/api/v1/kyc/session/")
    assert refused.status_code == 409
    assert refused.json()["code"] == "pin_required"

    _post(client, "/api/v1/auth/pin/set/", {"new_pin": PIN, "new_pin_confirmation": PIN})
    assert _post(client, "/api/v1/kyc/session/").status_code == 202


@pytest.mark.django_db
def test_first_pin_api_of_an_active_account_needs_the_pin_setup_email_code() -> None:
    user = _user()
    client = _client(user)

    missing = _post(client, "/api/v1/auth/pin/set/", {"new_pin": PIN, "new_pin_confirmation": PIN})
    assert missing.status_code == 400
    assert missing.json()["code"] == "email_code_invalid"

    requested = _post(
        client, "/api/v1/auth/sensitive-action-code/request/", {"action": "pin_setup"}
    )
    assert requested.status_code == 202
    code = SensitiveActionCode.objects.get(id=requested.json()["code_id"])
    from backend.apps.accounts_auth.services import delivery_secret_for_sensitive_action_code

    response = _post(
        client,
        "/api/v1/auth/pin/set/",
        {
            "new_pin": PIN,
            "new_pin_confirmation": PIN,
            "sensitive_action_code_id": str(code.id),
            "sensitive_action_code": delivery_secret_for_sensitive_action_code(code),
        },
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_change_pin_api_reports_the_pin_errors_with_their_codes() -> None:
    user = _with_pin(_user())
    client = _client(user)
    code_id, raw_code = _code(user, SensitiveAction.PIN_CHANGE)
    payload = {
        "pin": "999990",
        "new_pin": NEW_PIN,
        "new_pin_confirmation": NEW_PIN,
        "sensitive_action_code_id": code_id,
        "sensitive_action_code": raw_code,
    }

    for attempts_left in (4, 3, 2, 1):
        response = _post(client, "/api/v1/auth/pin/change/", payload)
        assert response.status_code == 400
        assert response.json()["code"] == "pin_invalid"
        assert response.json()["attempts_left"] == attempts_left
    locked = _post(client, "/api/v1/auth/pin/change/", payload)
    assert locked.status_code == 423
    assert locked.json()["code"] == "pin_locked"
    assert locked.json()["locked_until"] == _record(user).locked_until.isoformat()  # type: ignore[union-attr]
    assert "Forgot PIN" in locked.json()["detail"]


@pytest.mark.django_db
def test_forgot_pin_api_flow() -> None:
    user = _with_pin(_user())
    client = _client(user)
    code_id, raw_code = _code(user, SensitiveAction.PIN_RESET)

    started = _post(client, "/api/v1/auth/pin/reset/start/")
    assert started.status_code == 202
    assert started.json()["phone_last_digits"] == "42"
    challenge = PhoneVerificationChallenge.objects.get(id=started.json()["phone_challenge_id"])
    from backend.apps.accounts_auth.services import delivery_secret_for_phone_verification

    sms_code = delivery_secret_for_phone_verification(challenge)
    wrong = _post(
        client,
        "/api/v1/auth/pin/reset/confirm/",
        {
            "sensitive_action_code_id": code_id,
            "sensitive_action_code": raw_code,
            "phone_challenge_id": str(challenge.id),
            "phone_code": "000000" if sms_code != "000000" else "111111",
            "new_pin": NEW_PIN,
            "new_pin_confirmation": NEW_PIN,
        },
    )
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "phone_code_invalid"
    response = _post(
        client,
        "/api/v1/auth/pin/reset/confirm/",
        {
            "sensitive_action_code_id": code_id,
            "sensitive_action_code": raw_code,
            "phone_challenge_id": str(challenge.id),
            "phone_code": sms_code,
            "new_pin": NEW_PIN,
            "new_pin_confirmation": NEW_PIN,
        },
    )
    assert response.status_code == 200
    assert response.json()["pin"]["pin_set"] is True
    assert check_password(NEW_PIN, _record(user).pin_hash)


@pytest.mark.django_db
def test_forgot_pin_sms_is_throttled_like_the_registration_sms() -> None:
    user = _with_pin(_user())
    client = _client(user)

    assert _post(client, "/api/v1/auth/pin/reset/start/").status_code == 202
    assert _post(client, "/api/v1/auth/pin/reset/start/").status_code == 429


@pytest.mark.django_db
def test_pin_endpoints_are_throttled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PinThrottle, "window_rules", (WindowRule("hour", 60 * 60, 2),))
    user = _user(status=AccountStatus.PENDING_KYC)
    client = _client(user)
    weak = {"new_pin": "111111", "new_pin_confirmation": "111111"}

    assert _post(client, "/api/v1/auth/pin/set/", weak).status_code == 400
    assert _post(client, "/api/v1/auth/pin/set/", weak).status_code == 400
    assert _post(client, "/api/v1/auth/pin/set/", weak).status_code == 429


@pytest.mark.django_db
def test_pin_endpoints_need_a_session() -> None:
    client = Client()

    assert client.get("/api/v1/auth/pin/status/").status_code in {401, 403}
    assert _post(client, "/api/v1/auth/pin/set/", {"new_pin": PIN}).status_code in {401, 403}


@pytest.mark.django_db
def test_the_pin_never_appears_in_responses_or_audit_metadata() -> None:
    user = _user(status=AccountStatus.PENDING_KYC)
    client = _client(user)

    response = _post(client, "/api/v1/auth/pin/set/", {"new_pin": PIN, "new_pin_confirmation": PIN})

    assert PIN not in response.content.decode()
    for event in AuditEvent.objects.filter(target_id=str(user.id)):
        assert PIN not in str(event.metadata)


@pytest.mark.django_db
def test_admin_login_has_no_pin() -> None:
    from backend.apps.accounts_auth.services import (
        AdminLoginConfirmCommand,
        AdminLoginStartCommand,
        confirm_admin_login,
        delivery_secret_for_sensitive_action_code,
        start_admin_login,
    )

    admin = User.objects.create_user(
        email="admin-no-pin@example.test",
        password="Correct-Horse-Battery-42",
        full_name="Admin",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )
    started = start_admin_login(
        AdminLoginStartCommand(email=admin.email, password="Correct-Horse-Battery-42")
    )

    user = confirm_admin_login(
        AdminLoginConfirmCommand(
            code_id=str(started.code_record.id),
            raw_code=delivery_secret_for_sensitive_action_code(started.code_record),
        )
    )

    assert user == admin
    assert not SensitiveActionPin.objects.exists()
    assert not AuditEvent.objects.filter(action__startswith="auth.pin_").exists()
