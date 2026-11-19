"""IP of Webby-Soft SRL. Test helpers for the 18.5 sign-in (password + second factor).

Codes come from the test providers: the mock SMS provider stores the code encrypted on the
phone challenge; an authenticator code is computed from the stored secret (RFC 6238).
No real personal data or real secrets.
"""

from __future__ import annotations

from typing import Any

from django.test import Client
from django.utils import timezone

from backend.apps.accounts_auth import totp
from backend.apps.accounts_auth.crypto import decrypt_delivery_secret, encrypt_delivery_secret
from backend.apps.accounts_auth.models import (
    AuthenticatorApp,
    EmailLoginToken,
    LoginChallenge,
    PhoneVerificationChallenge,
    SensitiveActionCode,
    User,
)
from backend.apps.accounts_auth.services import (
    delivery_secret_for_phone_verification,
    delivery_secret_for_sensitive_action_code,
)

TEST_PASSWORD = "quiet-harbour-lantern-47"


def give_password(user: User, password: str = TEST_PASSWORD) -> User:
    user.set_password(password)
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password", "password_changed_at"])
    return user


def give_sms_factor(user: User, phone_number: str = "+41790000123") -> User:
    if not user.phone_number:
        user.phone_number = phone_number
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_number", "phone_verified_at"])
    return user


def give_authenticator(user: User, secret: str | None = None) -> str:
    """An active authenticator app; returns its secret."""
    value = secret or totp.new_secret()
    AuthenticatorApp.objects.filter(user=user, disabled_at__isnull=True).update(
        disabled_at=timezone.now(), disabled_reason="test"
    )
    AuthenticatorApp.objects.create(
        user=user, encrypted_secret=encrypt_delivery_secret(value), confirmed_at=timezone.now()
    )
    return value


def confirm_email(user: User) -> None:
    """Record a used registration link (the email address is confirmed)."""
    EmailLoginToken.objects.create(
        user=user,
        email=user.email,
        token_digest=f"test-confirmed-{user.pk}",
        encrypted_token="",
        expires_at=timezone.now(),
        used_at=timezone.now(),
    )


def app_code(user: User) -> str:
    """A code the active app accepts now (a step after the last used one)."""
    app = AuthenticatorApp.objects.get(
        user=user, confirmed_at__isnull=False, disabled_at__isnull=True
    )
    secret = decrypt_delivery_secret(app.encrypted_secret)
    now_step = totp.current_step()
    step = max(now_step - 1, int(app.last_used_step) + 1)
    if step > now_step + 1:
        # Tests that sign in many times within one period: allow the next code again.
        AuthenticatorApp.objects.filter(pk=app.pk).update(last_used_step=0)
        step = now_step - 1
    return totp.code_at_step(secret, step)


def enrollment_code(secret: str) -> str:
    return totp.code_at_step(secret, totp.current_step())


def sms_code_for_challenge(challenge_id: str) -> str:
    challenge = LoginChallenge.objects.get(id=challenge_id)
    assert challenge.phone_challenge_id is not None
    phone = PhoneVerificationChallenge.objects.get(id=challenge.phone_challenge_id)
    return delivery_secret_for_phone_verification(phone)


def post_json(client: Client, path: str, data: dict[str, Any], **extra: Any) -> Any:
    return client.post(path, data=data, content_type="application/json", **extra)


def sign_in(
    client: Client,
    user: User,
    *,
    password: str = TEST_PASSWORD,
    trust_device: bool = False,
    **extra: Any,
) -> Any:
    """Sign an investor in through the API with its factor; returns the last response."""
    start = post_json(
        client, "/api/v1/auth/login/", {"email": user.email, "password": password}, **extra
    )
    assert start.status_code == 200, start.content
    body = start.json()
    if body["status"] != "factor_required":
        return start
    code = (
        app_code(user)
        if body["method"] == "app"
        else sms_code_for_challenge(body["challenge_id"])
    )
    verify = post_json(
        client,
        "/api/v1/auth/login/verify/",
        {"challenge_id": body["challenge_id"], "code": code, "trust_device": trust_device},
        **extra,
    )
    assert verify.status_code == 200, verify.content
    return verify


def ready_investor(user: User) -> User:
    """Password + SMS factor (the usual signed-in investor of these tests)."""
    give_password(user)
    give_sms_factor(user)
    return user


def admin_sign_in(client: Client, user: User, password: str, **extra: Any) -> Any:
    """Admin sign-in: password + app; the first time with the email code and a new app."""
    start = post_json(
        client,
        "/api/v1/auth/admin/login/start/",
        {"email": user.email, "password": password},
        **extra,
    )
    assert start.status_code == 202, start.content
    body = start.json()
    if body["status"] == "enrollment_required":
        code_record = SensitiveActionCode.objects.get(id=body["code_id"])
        confirm = post_json(
            client,
            "/api/v1/auth/admin/login/enroll/",
            {
                "code_id": body["code_id"],
                "email_code": delivery_secret_for_sensitive_action_code(code_record),
                "enrollment_id": body["enrollment_id"],
                "code": enrollment_code(body["secret"]),
            },
            **extra,
        )
    else:
        confirm = post_json(
            client,
            "/api/v1/auth/admin/login/confirm/",
            {"challenge_id": body["challenge_id"], "code": app_code(user)},
            **extra,
        )
    assert confirm.status_code == 200, confirm.content
    return confirm
