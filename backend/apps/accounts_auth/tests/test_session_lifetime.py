from __future__ import annotations

import pytest
from django.conf import settings
from django.test import Client, override_settings

from backend.apps.accounts_auth import session_lifetime
from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    User,
)
from backend.apps.accounts_auth.tests.signin_helpers import (
    TEST_PASSWORD,
    admin_sign_in,
    ready_investor,
    sign_in,
    sms_code_for_challenge,
)
from backend.apps.platform_core.models import AuditEvent
from backend.apps.platform_core.services.impersonation import (
    READONLY_IMPERSONATION_HEADER,
    issue_readonly_impersonation_token,
)

TWO_HOURS = 2 * 60 * 60


@pytest.fixture
def investor() -> User:
    return User.objects.create_user(
        email="investor@example.test",
        full_name="Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    )


@pytest.fixture
def admin_user() -> User:
    return User.objects.create_user(
        email="admin@example.test",
        password="AdminPass123!",
        full_name="Admin User",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )


@pytest.fixture
def superadmin() -> User:
    return User.objects.create_user(
        email="superadmin@example.test",
        password="SuperAdminPass123!",
        full_name="Super Admin",
        account_type=AccountType.SUPERADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
        is_superuser=True,
    )


class _Clock:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.offset = 0
        real = session_lifetime._wall_clock_seconds
        monkeypatch.setattr(
            session_lifetime,
            "_wall_clock_seconds",
            lambda: real() + self.offset,
        )


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    return _Clock(monkeypatch)


def _magic_link_login(client: Client, user: User) -> None:
    """18.5: password + SMS code (the name is kept from the email-link era)."""
    sign_in(client, ready_investor(user))


def _admin_login(client: Client, user: User, password: str) -> None:
    admin_sign_in(client, user, password)


def _assert_session_expired(response: object) -> None:
    assert getattr(response, "status_code", None) == 401
    assert response.json() == {  # type: ignore[attr-defined]
        "detail": "Your session has expired. Please log in again.",
        "code": "session_expired",
    }


@pytest.mark.django_db
def test_investor_session_expires_two_hours_after_login(
    client: Client,
    investor: User,
    clock: _Clock,
) -> None:
    _magic_link_login(client, investor)
    stamped_at = client.session[session_lifetime.SESSION_AUTHENTICATED_AT_KEY]
    assert isinstance(stamped_at, int)

    # Absolute, not sliding: activity during the window does not extend it.
    clock.offset = TWO_HOURS - 60
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert client.session[session_lifetime.SESSION_AUTHENTICATED_AT_KEY] == stamped_at

    clock.offset = TWO_HOURS
    _assert_session_expired(client.get("/api/v1/auth/me/"))
    assert AuditEvent.objects.filter(
        action="auth.session_expired",
        target_id=str(investor.id),
    ).exists()

    # The authenticated session is gone; the browser keeps being told why until
    # it logs in again or signs out.
    assert session_lifetime.SESSION_AUTHENTICATED_AT_KEY not in client.session
    _assert_session_expired(client.get("/api/v1/auth/me/"))
    assert client.post("/api/v1/auth/logout/").status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
def test_admin_session_expires_two_hours_after_login(
    client: Client,
    admin_user: User,
    clock: _Clock,
) -> None:
    _admin_login(client, admin_user, "AdminPass123!")
    assert client.get("/api/v1/admin-ops/dashboard/").status_code == 200

    clock.offset = TWO_HOURS + 1
    _assert_session_expired(client.get("/api/v1/admin-ops/dashboard/"))
    _assert_session_expired(client.get("/api/v1/auth/me/"))


@pytest.mark.django_db
def test_expired_session_does_not_block_public_and_login_endpoints(
    client: Client,
    investor: User,
    clock: _Clock,
) -> None:
    _magic_link_login(client, investor)
    clock.offset = TWO_HOURS

    # The sign-in step is open to an expired browser and signs the investor in again.
    response = client.post(
        "/api/v1/auth/login/",
        data={"email": investor.email, "password": TEST_PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == 200
    _assert_session_expired(client.get("/api/v1/auth/me/"))

    body = response.json()
    consumed = client.post(
        "/api/v1/auth/login/verify/",
        data={
            "challenge_id": body["challenge_id"],
            "code": sms_code_for_challenge(body["challenge_id"]),
        },
        content_type="application/json",
    )
    assert consumed.status_code == 200
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert session_lifetime.SESSION_EXPIRED_AT_KEY not in client.session


@pytest.mark.django_db
def test_logging_in_again_restarts_the_session_lifetime(
    client: Client,
    investor: User,
    clock: _Clock,
) -> None:
    _magic_link_login(client, investor)
    clock.offset = TWO_HOURS - 60
    _magic_link_login(client, investor)

    clock.offset = TWO_HOURS + 60
    assert client.get("/api/v1/auth/me/").status_code == 200


@pytest.mark.django_db
@override_settings(AUTH_SESSION_MAX_AGE_SECONDS=60)
def test_session_lifetime_follows_setting(
    client: Client,
    investor: User,
    clock: _Clock,
) -> None:
    _magic_link_login(client, investor)

    clock.offset = 59
    assert client.get("/api/v1/auth/me/").status_code == 200
    clock.offset = 60
    _assert_session_expired(client.get("/api/v1/auth/me/"))


@pytest.mark.django_db
def test_session_without_login_time_starts_its_lifetime_on_first_use(
    client: Client,
    investor: User,
    clock: _Clock,
) -> None:
    client.force_login(investor)
    assert session_lifetime.SESSION_AUTHENTICATED_AT_KEY not in client.session

    assert client.get("/api/v1/auth/me/").status_code == 200
    assert session_lifetime.SESSION_AUTHENTICATED_AT_KEY in client.session

    clock.offset = TWO_HOURS
    _assert_session_expired(client.get("/api/v1/auth/me/"))


@pytest.mark.django_db
def test_readonly_impersonation_ends_with_the_superadmin_session(
    client: Client,
    investor: User,
    superadmin: User,
    clock: _Clock,
) -> None:
    _admin_login(client, superadmin, "SuperAdminPass123!")
    token = issue_readonly_impersonation_token(actor=superadmin, target_user_id=str(investor.id))[
        "token"
    ]
    header = {f"HTTP_{READONLY_IMPERSONATION_HEADER.upper().replace('-', '_')}": token}
    assert client.get("/api/v1/kyc/status/", **header).status_code == 200

    clock.offset = TWO_HOURS
    _assert_session_expired(client.get("/api/v1/kyc/status/", **header))


@pytest.mark.django_db
def test_parallel_request_with_the_expired_cookie_also_learns_it_expired(
    client: Client,
    investor: User,
    clock: _Clock,
) -> None:
    _magic_link_login(client, investor)
    # A request sent at the same time still carries the cookie as it was before
    # the first expired response arrived.
    other_tab = Client()
    other_tab.cookies[settings.SESSION_COOKIE_NAME] = client.cookies[
        settings.SESSION_COOKIE_NAME
    ].value

    clock.offset = TWO_HOURS
    _assert_session_expired(client.get("/api/v1/auth/me/"))
    _assert_session_expired(other_tab.get("/api/v1/auth/me/"))
