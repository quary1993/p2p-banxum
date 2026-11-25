"""IP of Webby-Soft SRL. 18.5 sign-in and account security (U33-DEC-01, Q05, Q06, D1-D6, D-1)."""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import timedelta
from importlib import import_module
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from backend.apps.accounts_auth import factor_sms, geoip, passwords, totp, two_factor
from backend.apps.accounts_auth import services as accounts_services
from backend.apps.accounts_auth.crypto import digest_secret
from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    AssistedRecoveryCase,
    AuthenticatorApp,
    EmailLoginToken,
    LoginChallenge,
    PasswordResetToken,
    PhoneVerificationChallenge,
    RecoveryCode,
    SecurityRestriction,
    SensitiveAction,
    SensitiveActionCode,
    TrustedDevice,
    User,
    UserSession,
)
from backend.apps.accounts_auth.passwords import PasswordPolicyError, validate_new_password
from backend.apps.accounts_auth.tests.signin_helpers import (
    TEST_PASSWORD,
    app_code,
    confirm_email,
    enrollment_code,
    give_authenticator,
    post_json,
    ready_investor,
    sign_in,
    sms_code_for_challenge,
)
from backend.apps.platform_core.domain.access import (
    security_restriction_until,
    user_can_access_financial_features,
)
from backend.apps.platform_core.models import AuditEvent, OutboxMessage

NEW_PASSWORD = "silver-meadow-compass-58"


def _investor(email: str = "security@example.test", **extra: Any) -> User:
    return User.objects.create_user(
        email=email,
        full_name="Security Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=extra.pop("status", AccountStatus.ACTIVE),
        **extra,
    )


def _admin(email: str) -> User:
    return User.objects.create_user(
        email=email,
        password="Admin-Pass-Phrase-77",
        full_name="Support Admin",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )


STORED_NAME = "Anna Maria Müller-Keller"
STORED_BIRTH = "1984-05-17"


def _verified(user: User, *, name: str = STORED_NAME, birth: str = STORED_BIRTH) -> User:
    """An approved KYC case with the verified name and date of birth (the stored identity)."""
    from datetime import date

    from django.apps import apps

    apps.get_model("kyc_compliance", "KycVerificationCase").objects.update_or_create(
        user_id=user.pk,
        defaults={
            "subject_reference": f"user:{user.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{user.pk}",
            "status": "approved",
            "decision_at": timezone.now(),
            "verified_full_name": name,
            "verified_birth_date": date.fromisoformat(birth),
        },
    )
    return user


def _compliance(email: str) -> User:
    admin = _admin(email)
    admin.staff_roles = ["compliance"]
    admin.save(update_fields=["staff_roles"])
    return admin


def _didit_result(
    case: AssistedRecoveryCase,
    *,
    status: str = "approved",
    name: str = "MÜLLER-KELLER ANNA MARIA",
    birth: str = STORED_BIRTH,
    event: str = "recovery-result-1",
    session_id: str = "",
) -> None:
    """The provider's webhook for the recovery's identity check."""
    kyc: Any = import_module("backend.apps.kyc_compliance.services")
    kyc.process_didit_event(
        kyc.ProviderKycEventCommand(
            provider_event_id=event,
            provider_event_type="status.updated",
            provider_status=status,
            provider_session_id=session_id or case.identity_check_session_id,
            vendor_data=f"user:{case.user_id}",
            raw_payload={
                "id": event,
                "status": status,
                "decision": {"id_verifications": [{"full_name": name, "date_of_birth": birth}]},
            },
        )
    )


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


# ---- Password policy -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("short-pass1", "password_too_short"),
        ("x" * 129, "password_too_long"),
        ("password1234", "password_common"),
        ("someone@example.test", "password_is_email"),
    ],
)
def test_password_policy_refuses_short_long_common_and_email(password: str, code: str) -> None:
    with pytest.raises(PasswordPolicyError) as error:
        validate_new_password(password, email="someone@example.test")
    assert error.value.code == code


def test_a_long_passphrase_without_symbols_is_accepted() -> None:
    validate_new_password("quiet harbour lantern forty seven", email="someone@example.test")


def test_breached_password_is_refused_and_only_the_hash_prefix_leaves(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.AUTH_PASSWORD_BREACH_CHECK_ENABLED = True
    password = "violet-orchard-ladder-31"
    import hashlib

    digest = hashlib.sha1(password.encode()).hexdigest().upper()  # noqa: S324 - test of HIBP
    seen: list[str] = []

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return f"{digest[5:]}:42\r\nABCDEF0123456789ABCDEF0123456789ABC:0".encode()

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        seen.append(request.full_url)
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(PasswordPolicyError) as error:
        validate_new_password(password)

    assert error.value.code == "password_breached"
    assert seen == [passwords.HIBP_RANGE_URL + digest[:5]]


def test_an_unreachable_breach_service_does_not_block_and_is_logged(
    settings: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    settings.AUTH_PASSWORD_BREACH_CHECK_ENABLED = True

    def offline(request: Any, timeout: float) -> Any:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", offline)

    validate_new_password("violet-orchard-ladder-31")

    assert "password_breach_check_unavailable" in caplog.text


# ---- Authenticator codes (RFC 6238) --------------------------------------------------------


def test_totp_matches_the_rfc_6238_test_vectors() -> None:
    # RFC 6238 appendix B, SHA-1, secret "12345678901234567890", 6 digits.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.code_at_step(secret, 59 // 30) == "287082"
    assert totp.code_at_step(secret, 1111111109 // 30) == "081804"
    step = totp.verify(secret, "287082", now=59)
    assert step == 1
    # The same code is refused once used.
    assert totp.verify(secret, "287082", last_used_step=step, now=59) is None


@pytest.mark.django_db
def test_five_wrong_app_codes_lock_the_app_for_thirty_minutes() -> None:
    user = _investor()
    give_authenticator(user)
    wrong = _wrong(app_code(user))
    for left in (4, 3, 2, 1):
        with pytest.raises(two_factor.TwoFactorError) as error:
            two_factor.check_app_code(user, wrong, context="test")
        assert error.value.extra == {"attempts_left": left}
    with pytest.raises(two_factor.TwoFactorError) as locked:
        two_factor.check_app_code(user, wrong, context="test")
    assert locked.value.code == "authenticator_locked"
    assert locked.value.http_status == 423
    # Even the right code waits for the end of the lock.
    with pytest.raises(two_factor.TwoFactorError):
        two_factor.check_app_code(user, app_code(user), context="test")
    AuthenticatorApp.objects.filter(user=user).update(
        locked_until=timezone.now() - timedelta(seconds=1)
    )
    two_factor.check_app_code(user, app_code(user), context="test")


# ---- Sign-in -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_sms_sign_in_sends_a_code_and_records_the_method(client: Client) -> None:
    user = ready_investor(_investor())

    start = post_json(
        client, "/api/v1/auth/login/", {"email": user.email, "password": TEST_PASSWORD}
    )

    assert start.status_code == 200
    body = start.json()
    assert (body["status"], body["method"], body["phone_last_digits"]) == (
        "factor_required",
        "sms",
        "23",
    )
    assert body["user"] is None
    assert client.get("/api/v1/auth/me/").status_code == 403
    verify = post_json(
        client,
        "/api/v1/auth/login/verify/",
        {
            "challenge_id": body["challenge_id"],
            "code": sms_code_for_challenge(body["challenge_id"]),
        },
    )
    assert verify.status_code == 200
    me = client.get("/api/v1/auth/me/").json()["user"]
    assert me["second_factor"] == "sms"
    assert UserSession.objects.get(user=user).method == "password_sms"


@pytest.mark.django_db
def test_wrong_codes_end_the_step_after_five_attempts(client: Client) -> None:
    user = ready_investor(_investor())
    body = post_json(
        client, "/api/v1/auth/login/", {"email": user.email, "password": TEST_PASSWORD}
    ).json()
    wrong = _wrong(sms_code_for_challenge(body["challenge_id"]))
    statuses = [
        post_json(
            client,
            "/api/v1/auth/login/verify/",
            {"challenge_id": body["challenge_id"], "code": wrong},
        ).status_code
        for _ in range(6)
    ]

    assert statuses[0] == 400
    assert 429 in statuses
    assert client.get("/api/v1/auth/me/").status_code == 403
    assert LoginChallenge.objects.get(id=body["challenge_id"]).completed_at is None


@pytest.mark.django_db
def test_wrong_codes_are_limited_per_account_across_steps_and_addresses(settings: Any) -> None:
    """Audit S4-2: wrong recovery codes in several sign-in steps from several addresses count
    together for the account; at the limit also the right code waits."""
    settings.AUTH_FACTOR_ACCOUNT_FAILURES_HOURLY = 4
    user = ready_investor(_investor())
    codes = two_factor.issue_recovery_codes(user=user)

    def verify(index: int, recovery_code: str) -> Any:
        client = Client()
        address = f"203.0.113.{index}"
        body = post_json(
            client,
            "/api/v1/auth/login/",
            {"email": user.email, "password": TEST_PASSWORD},
            REMOTE_ADDR=address,
        ).json()
        return post_json(
            client,
            "/api/v1/auth/login/verify/",
            {"challenge_id": body["challenge_id"], "recovery_code": recovery_code},
            REMOTE_ADDR=address,
        )

    assert [verify(index, "AAAA-BBBB-CCCC").status_code for index in range(4)] == [400] * 4
    held = verify(9, codes[0])
    assert held.status_code == 429
    assert held.json()["code"] == "factor_attempts_account"
    assert held.json()["retry_after_seconds"] > 0
    # The recovery code was not used up by the refused step.
    assert two_factor.recovery_codes_remaining(user) == 10
    cache.clear()
    assert verify(10, codes[0]).status_code == 200


@pytest.mark.django_db
def test_sms_codes_are_limited_per_account_per_hour_and_day(
    settings: Any, row_locks_need_a_transaction: None
) -> None:
    """Audit S4-2: SMS codes of one account are counted for all purposes together, under the
    account's row lock; a pending code still works for a new step."""
    settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS = 0
    settings.AUTH_SMS_ACCOUNT_HOURLY_LIMIT = 3
    user = ready_investor(_investor())
    for purpose in ("sign_in", "security", "sign_in"):
        factor_sms.send_code(user, purpose=purpose, ip_address="203.0.113.5")
    with pytest.raises(accounts_services.PhoneVerificationThrottleError) as refused:
        factor_sms.send_code(user, purpose="security", ip_address="203.0.113.6")
    assert refused.value.account_limit is True
    assert "Too many SMS codes" in str(refused.value)
    assert PhoneVerificationChallenge.objects.filter(user=user).count() == 3
    # A sign-in step now reuses the code that is still pending; no fourth SMS.
    step = two_factor.start_sign_in(
        email=user.email, password=TEST_PASSWORD, trusted_token="", ip_address="203.0.113.7"
    )
    assert step.status == "factor_required"
    assert PhoneVerificationChallenge.objects.filter(user=user).count() == 3
    # The older codes leave the hour window: a new code is sent again (the day limit stays).
    PhoneVerificationChallenge.objects.filter(user=user).update(
        expires_at=timezone.now() - timedelta(minutes=55)
    )
    factor_sms.send_code(user, purpose="sign_in")
    settings.AUTH_SMS_ACCOUNT_DAILY_LIMIT = 4
    with pytest.raises(accounts_services.PhoneVerificationThrottleError):
        factor_sms.send_code(user, purpose="sign_in")


@pytest.mark.django_db
def test_an_app_user_signs_in_with_the_app_code(client: Client) -> None:
    user = ready_investor(_investor())
    give_authenticator(user)

    sign_in(client, user)

    assert UserSession.objects.get(user=user).method == "password_app"
    assert client.get("/api/v1/auth/me/").json()["user"]["second_factor"] == "app"


@pytest.mark.django_db
def test_a_recovery_code_signs_in_once_and_the_owner_is_told(client: Client) -> None:
    user = ready_investor(_investor())
    codes = two_factor.issue_recovery_codes(user=user)
    assert len(codes) == 10
    assert RecoveryCode.objects.filter(user=user).count() == 10
    assert codes[0] not in str(list(RecoveryCode.objects.values_list("code_digest", flat=True)))

    def use(code: str) -> Any:
        body = post_json(
            Client(), "/api/v1/auth/login/", {"email": user.email, "password": TEST_PASSWORD}
        ).json()
        return post_json(
            client,
            "/api/v1/auth/login/verify/",
            {"challenge_id": body["challenge_id"], "recovery_code": code.lower().replace("-", " ")},
        )

    assert use(codes[0]).status_code == 200
    assert UserSession.objects.filter(user=user, method="password_recovery_code").exists()
    assert use(codes[0]).status_code == 400
    assert two_factor.recovery_codes_remaining(user) == 9
    notice = OutboxMessage.objects.get(topic="email.security_change")
    assert "9 codes are left" in notice.payload["body_text"]


@pytest.mark.django_db
def test_a_remembered_browser_skips_the_code_for_thirty_days_but_not_the_password() -> None:
    user = ready_investor(_investor())
    browser = Client()
    sign_in(browser, user, trust_device=True)
    cookie = browser.cookies[two_factor.TRUSTED_COOKIE_NAME]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
    device = TrustedDevice.objects.get(user=user)
    assert device.token_digest != cookie.value
    assert (device.expires_at - timezone.now()).days in {29, 30}
    browser.post("/api/v1/auth/logout/")

    wrong_password = post_json(
        browser, "/api/v1/auth/login/", {"email": user.email, "password": "not-the-password-1"}
    )
    assert wrong_password.status_code == 400
    again = post_json(
        browser, "/api/v1/auth/login/", {"email": user.email, "password": TEST_PASSWORD}
    )
    assert again.json()["status"] == "signed_in"
    assert UserSession.objects.filter(method="password_trusted_device").count() == 1
    # Another browser still needs the code.
    other = post_json(
        Client(), "/api/v1/auth/login/", {"email": user.email, "password": TEST_PASSWORD}
    )
    assert other.json()["status"] == "factor_required"


@pytest.mark.django_db
def test_an_account_without_a_factor_must_confirm_its_email_then_set_up_a_factor(
    client: Client,
) -> None:
    user = _investor(status=AccountStatus.PENDING_KYC)
    user.set_password(TEST_PASSWORD)
    user.save(update_fields=["password"])

    unconfirmed = post_json(
        client, "/api/v1/auth/login/", {"email": user.email, "password": TEST_PASSWORD}
    )
    assert unconfirmed.status_code == 403
    assert unconfirmed.json()["code"] == "email_not_confirmed"
    assert EmailLoginToken.objects.filter(user=user, used_at__isnull=True).count() == 1

    confirm_email(user)
    signed_in = post_json(
        client, "/api/v1/auth/login/", {"email": user.email, "password": TEST_PASSWORD}
    )
    assert signed_in.json()["status"] == "enrollment_required"
    assert signed_in.json()["user"]["second_factor"] == ""
    assert user_can_access_financial_features(user) is False

    started = client.post("/api/v1/auth/security/authenticator/start/").json()
    assert started["otpauth_uri"].startswith("otpauth://totp/")
    confirmed = post_json(
        client,
        "/api/v1/auth/security/authenticator/confirm/",
        {"enrollment_id": started["enrollment_id"], "code": enrollment_code(started["secret"])},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["second_factor"] == "app"
    first_codes = post_json(client, "/api/v1/auth/security/recovery-codes/", {})
    assert first_codes.status_code == 200
    assert len(first_codes.json()["codes"]) == 10
    # A new set needs a fresh confirmation.
    again = post_json(client, "/api/v1/auth/security/recovery-codes/", {})
    assert again.status_code == 403
    assert again.json()["code"] == "security_confirmation_required"


# ---- Security changes while signed in ------------------------------------------------------


def _confirm(client: Client, user: User, password: str = TEST_PASSWORD) -> str:
    step = post_json(client, "/api/v1/auth/security/confirm/start/", {"password": password})
    assert step.status_code == 200, step.content
    body = step.json()
    code = (
        app_code(user) if body["method"] == "app" else sms_code_for_challenge(body["challenge_id"])
    )
    verified = post_json(
        client,
        "/api/v1/auth/security/confirm/verify/",
        {"challenge_id": body["challenge_id"], "code": code},
    )
    assert verified.status_code == 200, verified.content
    return str(verified.json()["confirmation_id"])


@pytest.mark.django_db
def test_changing_the_password_needs_password_and_factor_and_ends_other_sessions() -> None:
    user = ready_investor(_investor())
    phone = Client()
    sign_in(phone, user, trust_device=True)
    laptop = Client()
    sign_in(laptop, user)

    wrong = post_json(laptop, "/api/v1/auth/security/confirm/start/", {"password": "nope-nope-123"})
    assert wrong.status_code == 400
    confirmation = _confirm(laptop, user)
    weak = post_json(
        laptop,
        "/api/v1/auth/security/password/",
        {"new_password": "password1234", "confirmation_id": confirmation},
    )
    assert weak.status_code == 400
    assert weak.json()["code"] == "password_common"
    confirmation = _confirm(laptop, user)
    changed = post_json(
        laptop,
        "/api/v1/auth/security/password/",
        {"new_password": NEW_PASSWORD, "confirmation_id": confirmation},
    )

    assert changed.status_code == 200
    assert changed.json()["password_changed_at"] is not None
    assert laptop.get("/api/v1/auth/me/").status_code == 200
    # Signed out (the session record ended and the password hash changed).
    assert phone.get("/api/v1/auth/me/").status_code in {401, 403}
    assert not TrustedDevice.objects.filter(user=user, revoked_at__isnull=True).exists()
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert OutboxMessage.objects.filter(
        topic="email.security_change", payload__headline="Password changed"
    ).exists()
    # A confirmation works once.
    reused = post_json(
        laptop,
        "/api/v1/auth/security/password/",
        {"new_password": "another-long-phrase-90", "confirmation_id": confirmation},
    )
    assert reused.status_code == 403


@pytest.mark.django_db
def test_an_sms_investor_adds_the_app_and_the_pin_is_no_longer_asked() -> None:
    """D-1 (Vlad, 2026-11-19): the app replaces the PIN in operations and the SMS at sign-in."""
    user = ready_investor(_investor())
    client = Client()
    sign_in(client, user)
    started = client.post("/api/v1/auth/security/authenticator/start/").json()

    without_confirmation = post_json(
        client,
        "/api/v1/auth/security/authenticator/confirm/",
        {"enrollment_id": started["enrollment_id"], "code": enrollment_code(started["secret"])},
    )
    assert without_confirmation.status_code == 403
    confirmation = _confirm(client, user)
    enrolled = post_json(
        client,
        "/api/v1/auth/security/authenticator/confirm/",
        {
            "enrollment_id": started["enrollment_id"],
            "code": enrollment_code(started["secret"]),
            "confirmation_id": confirmation,
        },
    )

    assert enrolled.status_code == 200
    assert enrolled.json()["second_factor"] == "app"
    assert client.get("/api/v1/auth/pin/status/").json()["pin"]["second_factor"] == "app"
    assert OutboxMessage.objects.filter(
        topic="email.security_change", payload__headline="Authenticator app set up"
    ).exists()
    # The verified phone stays as contact data.
    user.refresh_from_db()
    assert user.phone_verified_at is not None


# ---- Forgotten password --------------------------------------------------------------------


@pytest.mark.django_db
def test_forgotten_password_needs_the_email_link_and_the_factor(client: Client) -> None:
    user = ready_investor(_investor())
    other = Client()
    sign_in(other, user)

    unknown = post_json(client, "/api/v1/auth/password/forgot/", {"email": "nobody@example.test"})
    assert unknown.status_code == 202
    raw = two_factor.request_password_reset(email=user.email)
    assert PasswordResetToken.objects.filter(user=user).count() == 1
    # Audit A-49: the link token is never in the outbox; only the provider gets it.
    outbox = OutboxMessage.objects.get(topic="email.password_reset")
    assert raw not in str(outbox.payload)
    comms: Any = import_module("backend.apps.communications.services")
    sent = comms.render_email_for_outbox_message(outbox)
    stored = comms.render_email_for_outbox_message(outbox, redact_secrets=True)
    assert f"/reset-password#token={raw}" in sent.body_html
    assert f"/reset-password#token={raw}" in sent.body_text
    assert raw not in stored.body_html + stored.body_text
    assert "[redacted]" in stored.body_text

    step = post_json(client, "/api/v1/auth/password/reset/start/", {"token": raw}).json()
    assert step["status"] == "factor_required"
    rejected = post_json(
        client,
        "/api/v1/auth/password/reset/complete/",
        {
            "token": raw,
            "new_password": user.email,
            "challenge_id": step["challenge_id"],
            "code": sms_code_for_challenge(step["challenge_id"]),
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "password_is_email"
    wrong = post_json(
        client,
        "/api/v1/auth/password/reset/complete/",
        {
            "token": raw,
            "new_password": NEW_PASSWORD,
            "challenge_id": step["challenge_id"],
            "code": _wrong(sms_code_for_challenge(step["challenge_id"])),
        },
    )
    assert wrong.status_code == 400
    done = post_json(
        client,
        "/api/v1/auth/password/reset/complete/",
        {
            "token": raw,
            "new_password": NEW_PASSWORD,
            "challenge_id": step["challenge_id"],
            "code": sms_code_for_challenge(step["challenge_id"]),
        },
    )

    assert done.status_code == 200
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert other.get("/api/v1/auth/me/").status_code in {401, 403}
    # The link works once.
    again = post_json(client, "/api/v1/auth/password/reset/start/", {"token": raw})
    assert again.status_code == 400
    assert again.json()["code"] == "reset_link_invalid"


@pytest.mark.django_db
def test_a_password_reset_stops_unfinished_operation_codes() -> None:
    user = ready_investor(_investor())
    from backend.apps.accounts_auth.services import (
        SensitiveActionCodeCommand,
        issue_sensitive_action_code,
    )

    pending = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=user,
            action=SensitiveAction.WITHDRAWAL,
            operation={"amount_minor": 100_00, "currency": "CHF", "iban": "CH5604835012345678009"},
        )
    ).code_record
    raw = two_factor.request_password_reset(email=user.email)
    step = two_factor.start_password_reset(raw_token=raw)

    two_factor.complete_password_reset(
        raw_token=raw,
        new_password=NEW_PASSWORD,
        challenge_id=step.challenge_id,
        code=sms_code_for_challenge(step.challenge_id),
    )

    assert SensitiveActionCode.objects.get(id=pending.id).superseded_at is not None


# ---- Assisted recovery ---------------------------------------------------------------------


@pytest.mark.django_db
def test_assisted_recovery_needs_two_people_a_notice_and_then_a_single_use_link() -> None:
    user = _verified(ready_investor(_investor()))
    give_authenticator(user)
    session = Client()
    sign_in(session, user)
    support = _compliance("support@example.test")
    approver = _admin("approver@example.test")

    case = two_factor.open_assisted_recovery(
        actor=support, user_id=str(user.pk), note="Lost phone."
    )
    # Audit S4-4: the recovery starts a new identity check and sends its link to the investor.
    assert case.identity_check_session_id and case.identity_check_count == 1
    link = OutboxMessage.objects.get(
        payload__template_key="security.assisted_recovery_identity_check.v1"
    )
    assert link.payload["email"] == user.email
    assert case.identity_check_session_id in link.payload["action_url"]
    _didit_result(case)
    case = two_factor.confirm_assisted_identity(
        actor=support, case_id=str(case.id), evidence="Checked by phone too."
    )
    assert (case.status, case.identity_check_outcome) == ("identity_confirmed", "match")
    assert len(case.identity_check_decision_digest) == 64
    assert case.identity_check_result["provider_session_id"] == case.identity_check_session_id
    # The case keeps the comparison's result, not the name or the date.
    assert STORED_BIRTH not in str(case.identity_check_result)
    assert "Anna" not in str(case.identity_check_result)
    with pytest.raises(two_factor.TwoFactorError) as same_person:
        two_factor.approve_assisted_recovery(actor=support, case_id=str(case.id))
    assert same_person.value.code == "second_person_required"

    case = two_factor.approve_assisted_recovery(actor=approver, case_id=str(case.id))

    assert case.status == "approved"
    assert session.get("/api/v1/auth/me/").status_code == 401
    assert not AuthenticatorApp.objects.filter(user=user, disabled_at__isnull=True).exists()
    notice = OutboxMessage.objects.get(payload__template_key="security.assisted_recovery_notice.v1")
    assert notice.payload["action_label"] == "This was not me"
    # Nothing before the 24 hours.
    assert two_factor.send_due_recovery_links() == []
    assert two_factor.send_due_recovery_links(as_of=timezone.now() + timedelta(hours=25)) == [
        str(case.id)
    ]
    PasswordResetToken.objects.filter(user=user, purpose="assisted_recovery").update(
        token_digest=digest_secret("known-test-link")
    )

    client = Client()
    done = post_json(
        client,
        "/api/v1/auth/account-recovery/complete/",
        {"token": "known-test-link", "new_password": NEW_PASSWORD},
    )

    assert done.status_code == 200
    assert done.json()["user"]["second_factor"] == ""
    assert AssistedRecoveryCase.objects.get(id=case.id).status == "completed"
    restriction = SecurityRestriction.objects.get(user=user)
    assert round((restriction.ends_at - restriction.starts_at).total_seconds() / 3600) == 72
    assert security_restriction_until(user) == restriction.ends_at
    again = post_json(
        Client(),
        "/api/v1/auth/account-recovery/complete/",
        {"token": "known-test-link", "new_password": NEW_PASSWORD},
    )
    assert again.status_code == 400


@pytest.mark.django_db
def test_this_was_not_me_stops_the_recovery_and_alerts_support() -> None:
    user = _verified(ready_investor(_investor()))
    support = _compliance("support@example.test")
    approver = _admin("approver@example.test")
    case = two_factor.open_assisted_recovery(actor=support, user_id=str(user.pk), note="Call.")
    _didit_result(case)
    two_factor.confirm_assisted_identity(actor=support, case_id=str(case.id))
    two_factor.approve_assisted_recovery(actor=approver, case_id=str(case.id))
    AssistedRecoveryCase.objects.filter(id=case.id).update(
        dispute_token_digest=digest_secret("known-dispute-link")
    )

    response = post_json(
        Client(), "/api/v1/auth/account-recovery/not-me/", {"token": "known-dispute-link"}
    )

    assert response.status_code == 200
    assert AssistedRecoveryCase.objects.get(id=case.id).status == "disputed"
    assert OutboxMessage.objects.filter(
        topic="email.operations_alert", payload__metadata__case_id=str(case.id)
    ).exists()
    assert two_factor.send_due_recovery_links(as_of=timezone.now() + timedelta(days=2)) == []


@pytest.mark.django_db
def test_at_most_three_assisted_recoveries_in_seven_days() -> None:
    user = _verified(ready_investor(_investor()))
    support = _admin("support@example.test")
    for _ in range(3):
        case = two_factor.open_assisted_recovery(actor=support, user_id=str(user.pk), note="x")
        AssistedRecoveryCase.objects.filter(id=case.id).update(status="cancelled")

    with pytest.raises(two_factor.TwoFactorError) as error:
        two_factor.open_assisted_recovery(actor=support, user_id=str(user.pk), note="x")

    assert error.value.code == "assisted_recovery_limit"
    assert AuditEvent.objects.filter(action="auth.assisted_recovery_opened").count() == 3


# ---- Audit S4-4: the identity of a recovery comes from the provider's result ------------------


def _open_recovery(email: str = "security@example.test") -> tuple[User, User, AssistedRecoveryCase]:
    user = _verified(ready_investor(_investor(email)))
    compliance = _compliance("compliance@example.test")
    case = two_factor.open_assisted_recovery(actor=compliance, user_id=str(user.pk), note="Call.")
    return user, compliance, case


def _confirm_code(actor: User, case: AssistedRecoveryCase, note: str = "") -> str:
    with pytest.raises(two_factor.TwoFactorError) as error:
        two_factor.confirm_assisted_identity(actor=actor, case_id=str(case.id), evidence=note)
    return error.value.code


@pytest.mark.django_db
def test_free_text_cannot_confirm_the_identity_of_a_recovery() -> None:
    """Pending: no provider result yet. A note such as "Didit session 123: match" is no proof."""
    _user, compliance, case = _open_recovery()
    assert _confirm_code(compliance, case, "Didit session 123: match.") == "identity_check_pending"
    case.refresh_from_db()
    assert (case.status, case.identity_check_outcome, case.identity_evidence) == (
        "requested",
        "",
        "",
    )
    # The approval needs the confirmed identity.
    with pytest.raises(two_factor.TwoFactorError):
        two_factor.approve_assisted_recovery(
            actor=_admin("approver@example.test"), case_id=str(case.id)
        )


@pytest.mark.django_db
def test_only_a_compliance_person_confirms_the_identity() -> None:
    _user, _compliance_person, case = _open_recovery()
    _didit_result(case)
    assert _confirm_code(_admin("support@example.test"), case) == "compliance_role_required"
    case.refresh_from_db()
    assert case.status == "requested"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("result", "code", "mismatches"),
    [
        ({"status": "declined"}, "identity_check_not_approved", []),
        ({"status": "in review"}, "identity_check_not_approved", []),
        ({"name": "Peter Example"}, "identity_check_mismatch", ["name"]),
        ({"name": "Anna Other"}, "identity_check_mismatch", ["name"]),
        ({"birth": "1984-05-18"}, "identity_check_mismatch", ["birth_date"]),
        (
            {"name": "", "birth": ""},
            "identity_check_mismatch",
            ["name_missing", "birth_date_missing"],
        ),
    ],
)
def test_a_rejected_or_different_identity_does_not_confirm_the_recovery(
    result: dict[str, str], code: str, mismatches: list[str]
) -> None:
    """Rejected and mismatch outcomes: refused, recorded on the case, and the KYC case of the
    real investor is not changed by somebody's failed check."""
    from django.apps import apps

    user, compliance, case = _open_recovery()
    _didit_result(case, **result)
    with pytest.raises(two_factor.TwoFactorError) as error:
        two_factor.confirm_assisted_identity(actor=compliance, case_id=str(case.id), evidence="ok")
    assert error.value.code == code
    assert error.value.extra["mismatches"] == mismatches
    case.refresh_from_db()
    assert case.status == "requested" and case.identity_confirmed_at is None
    assert case.identity_check_outcome == code.removeprefix("identity_check_")
    assert AuditEvent.objects.filter(action="auth.assisted_recovery_identity_check_failed").exists()
    kyc_case = apps.get_model("kyc_compliance", "KycVerificationCase").objects.get(user_id=user.pk)
    assert (kyc_case.status, kyc_case.verified_full_name) == ("approved", STORED_NAME)
    assert str(kyc_case.verified_birth_date) == STORED_BIRTH


@pytest.mark.django_db
def test_a_middle_name_left_out_on_the_new_document_still_matches() -> None:
    _user, compliance, case = _open_recovery()
    _didit_result(case, name="Anna Müller-Keller")
    case = two_factor.confirm_assisted_identity(actor=compliance, case_id=str(case.id))
    assert case.identity_check_outcome == "match"


@pytest.mark.django_db
def test_a_result_of_another_check_cannot_be_replayed_for_a_recovery() -> None:
    """Replay: only the check that this recovery started counts, and only once."""
    kyc: Any = import_module("backend.apps.kyc_compliance.recovery_checks")
    user, compliance, case = _open_recovery()
    other_user, _c, other_case = (
        _verified(ready_investor(_investor("other@example.test"))),
        None,
        None,
    )
    other_case = two_factor.open_assisted_recovery(
        actor=compliance, user_id=str(other_user.pk), note="Other."
    )
    # An approved result for the other recovery's session.
    _didit_result(other_case, event="other-result")
    # Pointing this recovery at the other session is refused by the provider-check lookup.
    AssistedRecoveryCase.objects.filter(id=case.id).update(
        identity_check_session_id=other_case.identity_check_session_id
    )
    assert _confirm_code(compliance, case) == "identity_check_missing"
    with pytest.raises(kyc.RecoveryCheckError):
        kyc.recovery_check_result(
            provider_session_id=other_case.identity_check_session_id, reference=str(case.id)
        )
    # The right recovery confirms once; a second confirmation is a wrong state.
    two_factor.confirm_assisted_identity(actor=compliance, case_id=str(other_case.id))
    assert _confirm_code(compliance, other_case) == "bad_state"
    assert user.pk != other_user.pk


@pytest.mark.django_db
def test_a_new_identity_check_can_be_sent_three_times_at_most() -> None:
    _user, compliance, case = _open_recovery()
    first = case.identity_check_session_id
    _didit_result(case, status="declined")
    assert _confirm_code(compliance, case) == "identity_check_not_approved"
    case = two_factor.restart_assisted_identity_check(actor=compliance, case_id=str(case.id))
    assert case.identity_check_session_id != first
    assert (case.identity_check_count, case.identity_check_outcome) == (2, "")
    # The old declined result does not count for the new check.
    assert _confirm_code(compliance, case) == "identity_check_pending"
    _didit_result(case, event="recovery-result-2")
    assert (
        two_factor.confirm_assisted_identity(actor=compliance, case_id=str(case.id)).status
        == "identity_confirmed"
    )
    other = _verified(ready_investor(_investor("limit@example.test")))
    second = two_factor.open_assisted_recovery(
        actor=compliance, user_id=str(other.pk), note="Call."
    )
    two_factor.restart_assisted_identity_check(actor=compliance, case_id=str(second.id))
    two_factor.restart_assisted_identity_check(actor=compliance, case_id=str(second.id))
    with pytest.raises(two_factor.TwoFactorError) as limit:
        two_factor.restart_assisted_identity_check(actor=compliance, case_id=str(second.id))
    assert limit.value.code == "identity_check_limit"
    assert (
        OutboxMessage.objects.filter(
            payload__template_key="security.assisted_recovery_identity_check.v1",
            payload__user_id=str(second.user_id),
        ).count()
        == 3
    )


@pytest.mark.django_db
def test_a_recovery_needs_a_stored_verified_identity() -> None:
    user = ready_investor(_investor())
    with pytest.raises(two_factor.TwoFactorError) as error:
        two_factor.open_assisted_recovery(
            actor=_admin("support@example.test"), user_id=str(user.pk), note="Call."
        )
    assert error.value.code == "identity_check_unavailable"
    assert not AssistedRecoveryCase.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_admin_api_confirms_from_the_provider_result_and_sends_a_new_check(client: Client) -> None:
    user, compliance, case = _open_recovery()
    client.force_login(compliance)
    base = f"/api/v1/auth/admin/account-recoveries/{case.id}"
    pending = post_json(client, f"{base}/confirm-identity/", {"evidence": "match, trust me"})
    assert pending.status_code == 400 and pending.json()["code"] == "identity_check_pending"
    again = post_json(client, f"{base}/identity-check/", {})
    assert again.status_code == 200 and again.json()["identity_check_count"] == 2
    case.refresh_from_db()
    _didit_result(case, name="Somebody Else")
    refused = post_json(client, f"{base}/confirm-identity/", {})
    assert refused.status_code == 400 and refused.json()["code"] == "identity_check_mismatch"
    assert refused.json()["mismatches"] == ["name"]
    listed = client.get("/api/v1/auth/admin/account-recoveries/").json()["results"][0]
    assert listed["identity_check_outcome"] == "mismatch"
    assert listed["identity_check_mismatches"] == ["name"]
    assert user.email == listed["user_email"]


# ---- Sign-in place (Q06, D6) ---------------------------------------------------------------


@pytest.mark.django_db
def test_the_sign_in_place_is_the_approximate_city(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(geoip, "lookup", lambda ip: ("Zurich", "CH"))
    user = ready_investor(_investor())
    client = Client()
    sign_in(client, user, REMOTE_ADDR="198.51.100.30")

    [session] = client.get("/api/v1/auth/sessions/").json()["sessions"]
    assert session["place"] == "Zurich, CH (approximate)"
    [event] = client.get("/api/v1/auth/sign-in-history/").json()["events"]
    assert event["place"] == "Zurich, CH (approximate)"


def test_private_addresses_are_never_looked_up() -> None:
    assert geoip.lookup("10.0.0.1") == ("", "")
    assert geoip.lookup("127.0.0.1") == ("", "")
    assert geoip.place_label("", "CH") == "CH (approximate)"
    assert geoip.place_label("", "") == ""
