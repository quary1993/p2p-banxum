"""Sign-in abuse controls: lockout, enumeration, timing, link reuse and login CSRF.

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
from backend.apps.accounts_auth.models import AccountStatus, AccountType, User
from backend.apps.accounts_auth.services import (
    AdminLoginInvalidCredentialsError,
    AdminLoginStartCommand,
    InvalidOrExpiredTokenError,
    MagicLinkConsumeCommand,
    MagicLinkRequestCommand,
    MagicLinkSuppressedError,
    _magic_link_backoff_seconds,
    _magic_link_send_history_key,
    check_admin_credentials,
    consume_magic_link,
    issue_magic_link,
)
from backend.apps.accounts_auth.tests.signin_helpers import (
    TEST_PASSWORD,
    admin_sign_in,
    ready_investor,
    sign_in,
)
from backend.apps.accounts_auth.two_factor import TwoFactorError, start_sign_in

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


def _sign_in(client: Client, email: str, password: str, ip: str) -> Any:
    return client.post(
        "/api/v1/auth/login/",
        data={"email": email, "password": password},
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


@pytest.mark.django_db
def test_failed_passwords_from_other_ips_do_not_lock_an_investor_out(
    client: Client,
    investor: User,
) -> None:
    """18.5: wrong passwords count per (email, IP), so third parties cannot block the owner."""
    ready_investor(investor)
    for index in range(12):
        response = _sign_in(client, investor.email, "wrong-password-1", f"203.0.113.{index + 1}")
        assert response.status_code == 400

    own = _sign_in(client, investor.email, TEST_PASSWORD, "198.51.100.77")

    assert own.status_code == 200
    assert own.json()["status"] == "factor_required"


@pytest.mark.django_db
def test_failed_investor_passwords_back_off_per_email_and_ip(
    client: Client,
    investor: User,
    settings: Any,
) -> None:
    ready_investor(investor)
    settings.AUTH_SIGN_IN_FREE_FAILURES = 3
    settings.AUTH_SIGN_IN_BACKOFF_BASE_SECONDS = 30

    for _ in range(4):
        wrong = _sign_in(client, investor.email, "wrong-password-1", "203.0.113.9")
        assert wrong.status_code == 400

    blocked = _sign_in(client, investor.email, TEST_PASSWORD, "203.0.113.9")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "sign_in_throttled"
    assert 0 < blocked.json()["retry_after_seconds"] <= 31
    assert _sign_in(client, investor.email, TEST_PASSWORD, "198.51.100.9").status_code == 200


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
    """Audit A-47 with audit S4-2: guesses from many addresses are counted together for the
    account and stop at the account limit, but the admin's own browser (its device cookie from
    an earlier sign-in) still signs in."""
    own = Client()
    admin_sign_in(own, admin_user, ADMIN_PASSWORD, REMOTE_ADDR="198.51.100.8")
    own.post("/api/v1/auth/logout/")

    statuses = [
        _admin_start(client, admin_user.email, "wrong-password", f"203.0.113.{index}").status_code
        for index in range(25)
    ]
    # 20 wrong passwords per hour for the account, whatever the address; then no more guesses.
    assert statuses == [400] * 20 + [429] * 5

    # A browser that never signed in to the account is held, also with the right password.
    stranger = _admin_start(Client(), admin_user.email, ADMIN_PASSWORD, "192.0.2.50")
    assert stranger.status_code == 429
    assert stranger.json()["code"] == "admin_login_throttled"
    # The admin's own browser is not, from a new address too.
    assert _admin_start(own, admin_user.email, ADMIN_PASSWORD, "198.51.100.99").status_code == 202


@pytest.mark.django_db
def test_wrong_investor_passwords_are_limited_per_account_across_addresses(
    investor: User,
) -> None:
    """Audit S4-2: an account-wide limit beside the per-address limits; the answer is the same
    for an email without an account; the owner's known browser is not locked out."""
    ready_investor(investor)
    own = Client()
    assert sign_in(own, investor, REMOTE_ADDR="198.51.100.8").status_code == 200
    own.post("/api/v1/auth/logout/")

    def attempts(email: str) -> list[int]:
        return [
            _sign_in(Client(), email, "a wrong password 1", f"203.0.113.{index}").status_code
            for index in range(23)
        ]

    known = attempts(investor.email)
    unknown = attempts("nobody@example.test")
    assert known == unknown == [400] * 20 + [429] * 3

    throttled = _sign_in(Client(), investor.email, TEST_PASSWORD, "192.0.2.50")
    ghost = _sign_in(Client(), "nobody@example.test", TEST_PASSWORD, "192.0.2.51")
    assert throttled.status_code == ghost.status_code == 429
    assert throttled.json()["code"] == ghost.json()["code"] == "sign_in_throttled"
    assert set(throttled.json()) == set(ghost.json())
    # The investor's own browser still reaches the second-factor step.
    again = _sign_in(own, investor.email, TEST_PASSWORD, "198.51.100.77")
    assert again.status_code == 200 and again.json()["status"] == "factor_required"
    # Another account is not affected.
    other = User.objects.create_user(
        email="other-victim@example.test",
        full_name="Other Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    )
    ready_investor(other)
    assert _sign_in(Client(), other.email, TEST_PASSWORD, "192.0.2.60").status_code == 200


def test_a_burst_of_requests_cannot_pass_a_limit_together() -> None:
    """Audit S4-2: the counters count first and compare after, in one atomic cache operation.
    40 requests released at the same moment: exactly the limit passes."""
    import threading

    from backend.apps.accounts_auth import rate_limits

    cache.clear()
    limit, callers = 7, 40
    barrier = threading.Barrier(callers)
    passed: list[bool] = []
    lock = threading.Lock()

    def call() -> None:
        barrier.wait()
        allowed = rate_limits.take_window("throttle:test:burst", 3600, limit, now=1_000_000) is None
        with lock:
            passed.append(allowed)

    threads = [threading.Thread(target=call) for _ in range(callers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert passed.count(True) == limit and len(passed) == callers

    # A cooldown: one of the simultaneous callers starts it.
    barrier = threading.Barrier(callers)
    started: list[bool] = []

    def cool() -> None:
        barrier.wait()
        value = rate_limits.take_cooldown("throttle:test:cooldown", 60)
        with lock:
            started.append(value)

    threads = [threading.Thread(target=cool) for _ in range(callers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert started.count(True) == 1


def test_the_request_throttle_counts_with_the_atomic_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit S4-2: the DRF throttle classes use the same counters (no read-then-write)."""
    from rest_framework.test import APIRequestFactory

    from backend.apps.accounts_auth.api import throttles

    cache.clear()
    monkeypatch.setattr(
        throttles.SignInVerifyThrottle,
        "window_rules",
        (throttles.WindowRule("hour", 3600, 3),),
    )

    def read_only(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the throttle must not read a counter and write it back")

    monkeypatch.setattr(cache, "get", read_only)
    request = APIRequestFactory().post("/api/v1/auth/login/verify/", REMOTE_ADDR="203.0.113.5")
    results = [
        throttles.SignInVerifyThrottle().allow_request(request, None)  # type: ignore[arg-type]
        for _ in range(5)
    ]
    assert results == [True, True, True, False, False]


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
        check_admin_credentials(AdminLoginStartCommand(email=email, password="wrong-password"))

    assert len(calls) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["unknown", "investor", "admin"])
def test_investor_sign_in_runs_the_password_hasher_for_every_email(
    target: str,
    investor: User,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """18.5: same work for unknown, investor and admin emails (no timing enumeration)."""
    ready_investor(investor)
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

    with pytest.raises(TwoFactorError) as error:
        start_sign_in(email=email, password="wrong-password-1")

    assert error.value.code == "invalid_credentials"
    assert len(calls) == 1


@pytest.mark.django_db
def test_login_endpoints_refuse_cross_site_posts(client: Client, investor: User) -> None:
    issued = issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    cross_site = client.post(
        "/api/v1/auth/register/confirm-email/",
        data={"token": issued.raw_token},
        content_type="application/json",
        HTTP_ORIGIN="https://evil.example",
    )
    null_origin = client.post(
        "/api/v1/auth/register/confirm-email/",
        data={"token": issued.raw_token},
        content_type="application/json",
        HTTP_ORIGIN="null",
    )
    investor_cross_site = client.post(
        "/api/v1/auth/login/",
        data={"email": "x@example.test", "password": "x"},
        content_type="application/json",
        HTTP_SEC_FETCH_SITE="cross-site",
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
    assert investor_cross_site.status_code == 403
    assert "sessionid" not in cross_site.cookies
    issued.login_token.refresh_from_db()
    assert issued.login_token.used_at is None

    same_site = client.post(
        "/api/v1/auth/register/confirm-email/",
        data={"token": issued.raw_token},
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )
    assert same_site.status_code == 200
