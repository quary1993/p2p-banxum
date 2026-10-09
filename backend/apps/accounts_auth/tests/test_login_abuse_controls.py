"""Login abuse controls: lockout, enumeration, timing, link reuse and login CSRF.

Audit 2026-10-09: A-47 (third parties could lock a named investor or admin out),
A-57 (admin email timing), SECCODE-15 / SECURITY-04 (older links stayed valid, login
endpoints accepted cross-site posts).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.cache import cache
from django.test import Client

from backend.apps.accounts_auth.api.throttles import AdminLoginStartThrottle
from backend.apps.accounts_auth.models import AccountStatus, AccountType, EmailLoginToken, User
from backend.apps.accounts_auth.services import (
    AdminLoginInvalidCredentialsError,
    AdminLoginStartCommand,
    InvalidOrExpiredTokenError,
    MagicLinkConsumeCommand,
    MagicLinkRequestCommand,
    MagicLinkSuppressedError,
    _magic_link_backoff_seconds,
    _magic_link_send_history_key,
    consume_magic_link,
    delivery_secret_for_magic_link,
    issue_magic_link,
    start_admin_login,
)

ADMIN_PASSWORD = "Correct-Horse-Battery-42"


@pytest.fixture
def investor() -> User:
    return User.objects.create_user(
        email="victim@example.test",
        full_name="Victim Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    )


@pytest.fixture
def admin_user() -> User:
    return User.objects.create_user(
        email="ops-admin@example.test",
        password=ADMIN_PASSWORD,
        full_name="Ops Admin",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )


def _request_link(client: Client, email: str, ip: str) -> Any:
    return client.post(
        "/api/v1/auth/magic-link/request/",
        data={"email": email},
        content_type="application/json",
        REMOTE_ADDR=ip,
    )


def _admin_start(client: Client, email: str, password: str, ip: str, **extra: Any) -> Any:
    return client.post(
        "/api/v1/auth/admin/login/start/",
        data={"email": email, "password": password},
        content_type="application/json",
        REMOTE_ADDR=ip,
        **extra,
    )


def _latest_link(user: User) -> str:
    token = EmailLoginToken.objects.filter(user=user).order_by("-expires_at").first()
    assert token is not None
    return delivery_secret_for_magic_link(token)


@pytest.mark.django_db
def test_requests_from_other_ips_cannot_lock_an_investor_out(
    client: Client,
    investor: User,
) -> None:
    # Before the fix every request counted in one per-email bucket: 5 requests from
    # anywhere gave the owner 429 for up to an hour.
    for index in range(8):
        assert _request_link(client, investor.email, f"203.0.113.{index + 1}").status_code == 202

    own_request = _request_link(client, investor.email, "198.51.100.77")

    assert own_request.status_code == 202
    # The newest link in the owner's inbox signs them in.
    response = client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": _latest_link(investor)},
        content_type="application/json",
        REMOTE_ADDR="198.51.100.77",
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_one_ip_is_still_limited_for_one_address(client: Client, investor: User) -> None:
    assert _request_link(client, investor.email, "203.0.113.5").status_code == 202
    assert _request_link(client, investor.email, "203.0.113.5").status_code == 429


@pytest.mark.django_db
def test_a_flood_of_requests_sends_one_email_while_the_last_link_is_unused(
    client: Client,
    investor: User,
) -> None:
    for index in range(6):
        _request_link(client, investor.email, f"203.0.113.{index + 20}")

    assert EmailLoginToken.objects.filter(user=investor).count() == 1


@pytest.mark.django_db
def test_magic_link_backoff_grows_and_stays_below_link_lifetime(settings: Any) -> None:
    settings.AUTH_MAGIC_LINK_EMAIL_BACKOFF_SECONDS = 60
    settings.AUTH_MAGIC_LINK_EMAIL_MAX_BACKOFF_SECONDS = 3600
    ttl = timedelta(minutes=15)

    waits = [_magic_link_backoff_seconds(sent_last_hour=count, ttl=ttl) for count in range(6)]

    assert waits == [0.0, 60.0, 120.0, 240.0, 480.0, 840.0]


@pytest.mark.django_db
def test_new_link_after_backoff_supersedes_the_older_one(investor: User) -> None:
    first = issue_magic_link(MagicLinkRequestCommand(email=investor.email))
    with pytest.raises(MagicLinkSuppressedError):
        issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    # Pretend the last send was long ago.
    cache.set(_magic_link_send_history_key(investor), [0.0], timeout=60)
    second = issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    first.login_token.refresh_from_db()
    assert first.login_token.superseded_at is not None
    with pytest.raises(InvalidOrExpiredTokenError):
        consume_magic_link(MagicLinkConsumeCommand(raw_token=first.raw_token))
    assert consume_magic_link(MagicLinkConsumeCommand(raw_token=second.raw_token)).id == investor.id


@pytest.mark.django_db
def test_used_link_does_not_hold_back_the_next_one(investor: User) -> None:
    first = issue_magic_link(MagicLinkRequestCommand(email=investor.email))
    consume_magic_link(MagicLinkConsumeCommand(raw_token=first.raw_token))

    second = issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    assert second.raw_token != first.raw_token


@pytest.mark.django_db
def test_failed_admin_passwords_from_other_ips_do_not_lock_the_admin_out(
    client: Client,
    admin_user: User,
) -> None:
    # Before the fix 20 wrong passwords for the admin email, from any IPs, blocked the
    # admin's correct password for up to an hour.
    for index in range(25):
        response = _admin_start(client, admin_user.email, "wrong-password", f"203.0.113.{index}")
        assert response.status_code == 400

    own = _admin_start(client, admin_user.email, ADMIN_PASSWORD, "198.51.100.8")

    assert own.status_code == 202


@pytest.mark.django_db
def test_failed_admin_passwords_back_off_per_email_and_ip(
    client: Client,
    admin_user: User,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.AUTH_ADMIN_LOGIN_FREE_FAILURES = 3
    settings.AUTH_ADMIN_LOGIN_BACKOFF_BASE_SECONDS = 30
    # Isolate the failure backoff from the per-request cooldown.
    monkeypatch.setattr(AdminLoginStartThrottle, "cooldown_rules", ())

    for _ in range(4):
        assert _admin_start(client, admin_user.email, "wrong", "203.0.113.9").status_code == 400

    blocked = _admin_start(client, admin_user.email, ADMIN_PASSWORD, "203.0.113.9")
    assert blocked.status_code == 429
    assert 0 < blocked.json()["retry_after_seconds"] <= 31
    assert blocked["Retry-After"]
    # The same admin from another IP is not affected.
    assert _admin_start(client, admin_user.email, ADMIN_PASSWORD, "198.51.100.9").status_code == 202


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["unknown", "investor", "admin"])
def test_admin_login_runs_the_password_hasher_for_every_email(
    target: str,
    investor: User,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Audit A-57: only admin emails ran the hasher (~0.4 s vs ~0.015 s).
    calls: list[str] = []
    original_encode = PBKDF2PasswordHasher.encode

    def counting_encode(self: PBKDF2PasswordHasher, *args: Any, **kwargs: Any) -> str:
        calls.append("encode")
        return original_encode(self, *args, **kwargs)

    monkeypatch.setattr(PBKDF2PasswordHasher, "encode", counting_encode)
    email = {
        "unknown": "nobody@example.test",
        "investor": investor.email,
        "admin": admin_user.email,
    }[target]

    with pytest.raises(AdminLoginInvalidCredentialsError):
        start_admin_login(AdminLoginStartCommand(email=email, password="wrong-password"))

    assert len(calls) == 1


@pytest.mark.django_db
def test_login_endpoints_refuse_cross_site_posts(client: Client, investor: User) -> None:
    issued = issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    cross_site = client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": issued.raw_token},
        content_type="application/json",
        HTTP_ORIGIN="https://evil.example",
    )
    null_origin = client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": issued.raw_token},
        content_type="application/json",
        HTTP_ORIGIN="null",
    )
    fetch_metadata = client.post(
        "/api/v1/auth/admin/login/start/",
        data={"email": "x@example.test", "password": "x"},
        content_type="application/json",
        HTTP_SEC_FETCH_SITE="cross-site",
    )

    assert cross_site.status_code == 403
    assert null_origin.status_code == 403
    assert fetch_metadata.status_code == 403
    assert "sessionid" not in cross_site.cookies
    issued.login_token.refresh_from_db()
    assert issued.login_token.used_at is None

    same_site = client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": issued.raw_token},
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )
    assert same_site.status_code == 200
