"""IP of Webby-Soft SRL. U33-DEC-25: signed-in devices, sign-in history and new-device alerts."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from backend.apps.accounts_auth.models import (
    AccountAccessReason,
    AccountStatus,
    AccountType,
    SignInEvent,
    User,
    UserSession,
)
from backend.apps.accounts_auth.security_sessions import (
    DEVICE_COOKIE_NAME,
    describe_user_agent,
    purge_account_security_history,
)
from backend.apps.accounts_auth.services import (
    ChangeAccountAccessCommand,
    MagicLinkRequestCommand,
    change_account_access,
    issue_magic_link,
)
from backend.apps.platform_core.models import OutboxMessage

MAC_CHROME = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
IPHONE_SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
WINDOWS_FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0"


@pytest.fixture
def investor(db: None) -> User:
    return User.objects.create_user(
        email="devices@example.test",
        full_name="Device Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    )


def _sign_in(user: User, user_agent: str, client: Client | None = None, **headers: Any) -> Client:
    """A sign-in from a browser: a new one by default, or the given one (same device cookie)."""
    client = client or Client(HTTP_USER_AGENT=user_agent)
    link = issue_magic_link(MagicLinkRequestCommand(email=user.email))
    response = client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": link.raw_token},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 200, response.content
    return client


def test_the_device_is_read_from_the_user_agent() -> None:
    assert describe_user_agent(MAC_CHROME) == ("Chrome on macOS", "desktop")
    assert describe_user_agent(IPHONE_SAFARI) == ("Safari on iPhone", "mobile")
    assert describe_user_agent(WINDOWS_FIREFOX) == ("Firefox on Windows", "desktop")
    assert describe_user_agent("") == ("Unknown device", "")


@pytest.mark.django_db
@override_settings(SIGN_IN_COUNTRY_HEADER="CF-IPCountry")
def test_sign_in_records_the_session_and_the_history(investor: User) -> None:
    client = _sign_in(investor, MAC_CHROME, HTTP_CF_IPCOUNTRY="CH")

    sessions = client.get("/api/v1/auth/sessions/").json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["device_label"] == "Chrome on macOS"
    assert sessions[0]["country_code"] == "CH"
    assert sessions[0]["method"] == "email_link"
    assert sessions[0]["current"] is True

    history = client.get("/api/v1/auth/sign-in-history/").json()
    assert history["retention_days"] == 365
    [event] = history["events"]
    assert (event["device_label"], event["country_code"], event["method"], event["result"]) == (
        "Chrome on macOS",
        "CH",
        "email_link",
        "signed_in",
    )


@pytest.mark.django_db
def test_ending_another_session_really_signs_that_browser_out(investor: User) -> None:
    laptop = _sign_in(investor, MAC_CHROME)
    phone = _sign_in(investor, IPHONE_SAFARI)
    sessions = laptop.get("/api/v1/auth/sessions/").json()["sessions"]
    assert [row["current"] for row in sessions] == [True, False]
    phone_session = sessions[1]["id"]

    assert laptop.post(f"/api/v1/auth/sessions/{phone_session}/revoke/").status_code == 204
    revoked = phone.get("/api/v1/auth/me/")
    assert revoked.status_code == 401
    assert revoked.json()["code"] == "session_expired"
    assert "signed out from another device" in revoked.json()["detail"]
    assert phone.get("/api/v1/auth/me/").status_code in {401, 403}
    assert UserSession.objects.get(id=phone_session).end_reason == "revoked"
    # The laptop stays signed in, and its own session cannot be "revoked" from here.
    assert laptop.get("/api/v1/auth/me/").status_code == 200
    current = laptop.get("/api/v1/auth/sessions/").json()["sessions"][0]["id"]
    assert laptop.post(f"/api/v1/auth/sessions/{current}/revoke/").status_code == 404


@pytest.mark.django_db
def test_sign_out_everywhere_else_and_sign_out_here(investor: User) -> None:
    laptop = _sign_in(investor, MAC_CHROME)
    phone = _sign_in(investor, IPHONE_SAFARI)
    tablet = _sign_in(investor, WINDOWS_FIREFOX)

    ended = laptop.post("/api/v1/auth/sessions/revoke-others/").json()
    assert ended == {"sessions_ended": 2}
    assert phone.get("/api/v1/auth/me/").status_code == 401
    assert tablet.get("/api/v1/auth/me/").status_code == 401
    assert len(laptop.get("/api/v1/auth/sessions/").json()["sessions"]) == 1

    assert laptop.post("/api/v1/auth/logout/").status_code == 204
    assert UserSession.objects.filter(ended_at__isnull=True).count() == 0
    assert UserSession.objects.filter(end_reason="logout").count() == 1
    # The history stays after the sessions end.
    assert SignInEvent.objects.filter(user=investor, result="signed_in").count() == 3


@pytest.mark.django_db
def test_a_new_device_sends_a_security_email_but_the_first_sign_in_does_not(
    investor: User,
) -> None:
    alerts = OutboxMessage.objects.filter(topic="email.security_new_sign_in")
    mac = _sign_in(investor, MAC_CHROME)
    assert not alerts.exists()
    _sign_in(investor, MAC_CHROME, client=mac)
    assert not alerts.exists()
    _sign_in(investor, IPHONE_SAFARI)
    [alert] = alerts
    assert alert.payload["user_id"] == str(investor.pk)
    assert alert.payload["email"] == investor.email
    assert ["Device", "Safari on iPhone"] in alert.payload["data_rows"]
    assert "sign out the other devices" in alert.payload["body_text"]


@pytest.mark.django_db
def test_a_refused_sign_in_of_a_blocked_account_is_in_its_history(investor: User) -> None:
    admin = User.objects.create_user(
        email="devices-admin@example.test",
        password="AdminPass123!",
        full_name="Ops",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )
    link = issue_magic_link(MagicLinkRequestCommand(email=investor.email))
    change_account_access(
        ChangeAccountAccessCommand(
            actor=admin,
            user_id=str(investor.id),
            new_status=AccountStatus.RESTRICTED,
            reason_code=AccountAccessReason.COMPLIANCE_HOLD,
            note="Review.",
        )
    )
    response = Client(HTTP_USER_AGENT=WINDOWS_FIREFOX).post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": link.raw_token},
        content_type="application/json",
    )
    assert response.status_code == 403
    event = SignInEvent.objects.get(user=investor)
    assert (event.result, event.device_label) == ("blocked", "Firefox on Windows")
    assert not UserSession.objects.filter(user=investor).exists()


@pytest.mark.django_db
def test_retention_deletes_old_history_and_ended_sessions(investor: User) -> None:
    client = _sign_in(investor, MAC_CHROME)
    client.post("/api/v1/auth/logout/")
    old = timezone.now() - timedelta(days=400)
    SignInEvent.objects.update(occurred_at=old)
    UserSession.objects.update(ended_at=old)
    _sign_in(investor, IPHONE_SAFARI)

    result = purge_account_security_history(as_of=timezone.now())

    assert result == {"sign_in_events_deleted": 1, "sessions_deleted": 1}
    assert SignInEvent.objects.filter(user=investor).count() == 1
    assert UserSession.objects.filter(user=investor).count() == 1


@pytest.mark.django_db
def test_a_second_computer_with_the_same_browser_is_a_new_device(investor: User) -> None:
    """Audit G-03: the device cookie, not the browser label, tells devices apart."""
    alerts = OutboxMessage.objects.filter(topic="email.security_new_sign_in")
    office = _sign_in(investor, MAC_CHROME)
    cookie = office.cookies[DEVICE_COOKIE_NAME]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
    assert len(cookie.value) >= 32

    _sign_in(investor, MAC_CHROME, client=office)
    assert not alerts.exists()
    # Same browser and system, other computer: no device cookie yet.
    _sign_in(investor, MAC_CHROME)

    [alert] = alerts
    assert ["Device", "Chrome on macOS"] in alert.payload["data_rows"]
    # Only the keyed hash of the cookie is stored.
    stored = set(SignInEvent.objects.filter(user=investor).values_list("device_hash", flat=True))
    assert cookie.value not in stored
    assert len(stored) == 2


@pytest.mark.django_db
def test_sign_ins_from_before_the_device_cookie_still_count_as_known(investor: User) -> None:
    """The cookie's arrival raises no alert for a browser already seen without it."""
    _sign_in(investor, MAC_CHROME)
    SignInEvent.objects.filter(user=investor).update(device_hash="")
    alerts = OutboxMessage.objects.filter(topic="email.security_new_sign_in")

    _sign_in(investor, MAC_CHROME)

    assert not alerts.exists()
