"""IP of Webby-Soft SRL. Signed-in devices, sign-in history and new-device alerts (U33-DEC-25).

- Every sign-in of a known account is recorded (time, device, approximate place, method,
  result) and kept after the session ends, for ``security.sign_in_history_retention_days``.
- Every signed-in browser has a ``UserSession``. The investor can end one session or all
  other sessions; the middleware signs an ended session out on its next request, so the
  access really ends.
- A sign-in from a device not seen before sends a security email, independent of
  marketing consent. The first recorded sign-in of an account sends nothing.

The device comes from the browser's user agent; the place is the country a trusted edge
proxy gives in ``SIGN_IN_COUNTRY_HEADER`` (IP location is not GPS). The IP address is kept
only as a keyed hash.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import logout
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from backend.apps.accounts_auth import geoip
from backend.apps.accounts_auth.models import (
    SessionEndReason,
    SignInEvent,
    SignInResult,
    User,
    UserSession,
)
from backend.apps.platform_core.api.request_meta import client_ip
from backend.apps.platform_core.domain.access import actor_ref_for_user
from backend.apps.platform_core.domain.time import to_business_time
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message
from backend.apps.platform_core.services.ip_privacy import keyed_ip_hash

SESSION_RECORD_KEY = "banxum_user_session_id"
ACTIVITY_WRITE_INTERVAL = timedelta(minutes=5)
DEFAULT_RETENTION_DAYS = 365
HISTORY_LIMIT = 50
_COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")
# Codes some proxies use for "unknown" or Tor; they are not a place.
_NOT_A_COUNTRY = frozenset({"XX", "T1", "A1", "A2", "O1", "EU", "AP"})

_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
)


def wall_clock() -> datetime:
    # Real time on purpose, like the session lifetime: the QA clock must not age sessions.
    return timezone.now()


def describe_user_agent(user_agent: str) -> tuple[str, str]:
    """``("Chrome on macOS", "desktop")`` from a user agent; ``("Unknown device", "")``."""
    browser = next((name for marker, name in _BROWSERS if marker in user_agent), "")
    system = next((name for marker, name in _SYSTEMS if marker in user_agent), "")
    if not browser and not system:
        return "Unknown device", ""
    kind = "mobile" if system in {"iPhone", "Android"} or "Mobile" in user_agent else "desktop"
    if system == "iPad":
        kind = "tablet"
    if browser and system:
        return f"{browser} on {system}", kind
    return browser or system, kind


def request_country(request: HttpRequest | None) -> str:
    header = str(getattr(settings, "SIGN_IN_COUNTRY_HEADER", "") or "").strip()
    if request is None or not header:
        return ""
    meta_key = "HTTP_" + header.upper().replace("-", "_")
    value = str(request.META.get(meta_key, "") or "").strip().upper()
    if not _COUNTRY_PATTERN.match(value) or value in _NOT_A_COUNTRY:
        return ""
    return value


def ip_hash(ip_address: str | None) -> str:
    """The keyed hash every authentication record stores in place of the IP (audit S4-1)."""
    return keyed_ip_hash(ip_address)


# Audit G-03: a random value in a long-lived, HTTP-only cookie names the browser, so a second
# computer with the same browser and system is still a new device. Only its keyed hash is
# stored. It is a security cookie: no tracking, no use outside sign-in alerts.
DEVICE_COOKIE_NAME = "banxum_device"
DEVICE_COOKIE_MAX_AGE_SECONDS = 2 * 365 * 24 * 60 * 60
NEW_DEVICE_TOKEN_ATTRIBUTE = "_banxum_new_device_token"
_DEVICE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


def device_hash(token: str) -> str:
    if not token:
        return ""
    pepper = hashlib.sha256(f"{settings.SECRET_KEY}:accounts-device:v1".encode()).digest()
    return hmac.new(pepper, token.encode("utf-8"), hashlib.sha256).hexdigest()


def device_token_for_request(request: HttpRequest) -> str:
    """The browser's device value; a new one is made (and set by the middleware) if missing."""
    token = str(request.COOKIES.get(DEVICE_COOKIE_NAME, "") or "")
    if _DEVICE_TOKEN_PATTERN.fullmatch(token):
        return token
    token = secrets.token_urlsafe(32)
    setattr(request, NEW_DEVICE_TOKEN_ATTRIBUTE, token)
    return token


def set_device_cookie(request: HttpRequest, response: Any) -> None:
    """Called by the middleware: store a device value made during this request."""
    token = getattr(request, NEW_DEVICE_TOKEN_ATTRIBUTE, None)
    if not token:
        return
    response.set_cookie(
        DEVICE_COOKIE_NAME,
        token,
        max_age=DEVICE_COOKIE_MAX_AGE_SECONDS,
        secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        httponly=True,
        samesite="Lax",
    )


def _request_ip(request: HttpRequest) -> str:
    return client_ip(request) or ""


def retention_days() -> int:
    value = get_platform_setting_value(
        "security.sign_in_history_retention_days", DEFAULT_RETENTION_DAYS
    )
    if type(value) is int and 30 <= value <= 3650:
        return value
    return DEFAULT_RETENTION_DAYS


def session_is_open(record: UserSession, *, now: datetime) -> bool:
    """Not ended, and younger than the absolute session lifetime."""
    if record.ended_at is not None:
        return False
    max_age = int(settings.AUTH_SESSION_MAX_AGE_SECONDS)
    started: datetime = record.created_at
    return bool(started + timedelta(seconds=max_age) > now)


def record_sign_in(
    *,
    user: User,
    method: str,
    result: str,
    user_agent: str,
    ip_address: str = "",
    country_code: str = "",
    device_token: str = "",
) -> SignInEvent:
    label, kind = describe_user_agent(user_agent)
    # Q06: the local IP database gives the approximate city (and the country when the proxy
    # header does not).
    city, geo_country = geoip.lookup(ip_address)
    country_code = country_code or geo_country
    digest = device_hash(device_token)
    new_device = False
    if result == SignInResult.SIGNED_IN:
        earlier = SignInEvent.objects.filter(user=user, result=SignInResult.SIGNED_IN)
        if earlier.exists():
            known = bool(digest) and earlier.filter(device_hash=digest).exists()
            # Sign-ins recorded before the device cookie have no device value: their browser
            # label still counts as known, so the new cookie itself raises no alert.
            known = known or earlier.filter(device_hash="", device_label=label).exists()
            new_device = not known
    event = SignInEvent.objects.create(
        user=user,
        method=method,
        result=result,
        device_label=label,
        device_kind=kind,
        device_hash=digest,
        country_code=country_code,
        city=city,
        ip_hash=ip_hash(ip_address),
        new_device=new_device,
        occurred_at=wall_clock(),
    )
    if new_device:
        _enqueue_new_device_alert(user=user, event=event)
    return event


def _enqueue_new_device_alert(*, user: User, event: SignInEvent) -> None:
    brand = str(getattr(settings, "PLATFORM_BRAND_NAME", "") or "BANXUM")
    when = to_business_time(event.occurred_at).strftime("%d.%m.%Y %H:%M")
    rows = [["Device", event.device_label], ["Time", f"{when} (Swiss time)"]]
    place = geoip.place_label(event.city, event.country_code)
    if place:
        rows.append(["Approximate place", place])
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"security:new-sign-in:{event.id}",
            topic="email.security_new_sign_in",
            payload={
                "user_id": str(user.pk),
                "email": str(user.email),
                "subject": f"New sign-in to your {brand} account",
                "notice_label": "Security",
                "headline": "New sign-in",
                "status_label": "New device",
                "status_tone": "warning",
                "body_text": (
                    f"Your {brand} account was signed in from a device we have not seen "
                    "before.\n\nIf this was you, you do not need to do anything. If it was "
                    "not you, sign out the other devices in Profile & Settings, Security, "
                    "and contact support."
                ),
                "data_rows": rows,
                "template_key": "security.new_sign_in.v1",
                "metadata": {"sign_in_event_id": str(event.id), "navigation_target": "none"},
            },
        )
    )


@transaction.atomic
def start_tracked_session(request: HttpRequest, user: User, *, method: str) -> UserSession:
    """Record the sign-in and the new session; called right after Django's login()."""
    user_agent = str(request.META.get("HTTP_USER_AGENT", "") or "")[:500]
    country = request_country(request)
    now = wall_clock()
    previous_id = request.session.get(SESSION_RECORD_KEY)
    if previous_id:
        UserSession.objects.filter(id=previous_id, user=user, ended_at__isnull=True).update(
            ended_at=now, end_reason=SessionEndReason.REPLACED
        )
    event = record_sign_in(
        user=user,
        method=method,
        result=SignInResult.SIGNED_IN,
        user_agent=user_agent,
        ip_address=_request_ip(request),
        country_code=country,
        device_token=device_token_for_request(request),
    )
    label, kind = describe_user_agent(user_agent)
    record = UserSession.objects.create(
        user=user,
        method=method,
        device_label=label,
        device_kind=kind,
        country_code=event.country_code,
        city=event.city,
        ip_hash=ip_hash(_request_ip(request)),
        last_activity_at=now,
    )
    request.session[SESSION_RECORD_KEY] = str(record.id)
    return record


def _lazy_record(request: HttpRequest, user: User, *, now: datetime) -> UserSession:
    """A session started before this tracking existed (or by a test login) gets a record."""
    label, kind = describe_user_agent(str(request.META.get("HTTP_USER_AGENT", "") or ""))
    record = UserSession.objects.create(
        user=user,
        device_label=label,
        device_kind=kind,
        country_code=request_country(request),
        ip_hash=ip_hash(_request_ip(request)),
        last_activity_at=now,
    )
    request.session[SESSION_RECORD_KEY] = str(record.id)
    return record


def track_session_activity(request: HttpRequest) -> bool:
    """Middleware hook. False when this browser's session was ended elsewhere (now logged out)."""
    user: Any = getattr(request, "user", None)
    session = getattr(request, "session", None)
    if session is None or not isinstance(user, User) or not user.is_authenticated:
        return True
    now = wall_clock()
    record_id = session.get(SESSION_RECORD_KEY)
    record = UserSession.objects.filter(id=record_id, user=user).first() if record_id else None
    if record is None:
        _lazy_record(request, user, now=now)
        return True
    if record.ended_at is not None:
        logout(request)
        return False
    if record.last_activity_at is None or now - record.last_activity_at >= ACTIVITY_WRITE_INTERVAL:
        UserSession.objects.filter(pk=record.pk).update(last_activity_at=now)
    return True


def end_current_session(request: HttpRequest, *, reason: str = SessionEndReason.LOGOUT) -> None:
    session = getattr(request, "session", None)
    record_id = session.get(SESSION_RECORD_KEY) if session is not None else None
    if record_id:
        UserSession.objects.filter(id=record_id, ended_at__isnull=True).update(
            ended_at=wall_clock(), end_reason=reason
        )


def _session_payload(record: UserSession, *, current_id: str) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "device_label": record.device_label or "Unknown device",
        "device_kind": record.device_kind,
        "country_code": record.country_code,
        "city": record.city,
        "place": geoip.place_label(record.city, record.country_code),
        "method": record.method,
        "started_at": record.created_at,
        "last_activity_at": record.last_activity_at or record.created_at,
        "current": str(record.id) == current_id,
    }


def list_open_sessions(user: User, *, current_id: str) -> list[dict[str, Any]]:
    now = wall_clock()
    rows = [
        record
        for record in UserSession.objects.filter(user=user, ended_at__isnull=True)
        if session_is_open(record, now=now)
    ]
    rows.sort(
        key=lambda record: (
            str(record.id) != current_id,
            -(record.last_activity_at or record.created_at).timestamp(),
        )
    )
    return [_session_payload(record, current_id=current_id) for record in rows]


def list_sign_in_history(user: User) -> list[dict[str, Any]]:
    since = wall_clock() - timedelta(days=retention_days())
    return [
        {
            "id": str(event.id),
            "occurred_at": event.occurred_at,
            "device_label": event.device_label or "Unknown device",
            "device_kind": event.device_kind,
            "country_code": event.country_code,
            "city": event.city,
            "place": geoip.place_label(event.city, event.country_code),
            "method": event.method,
            "result": event.result,
        }
        for event in SignInEvent.objects.filter(user=user, occurred_at__gte=since)[:HISTORY_LIMIT]
    ]


class SessionNotFoundError(LookupError):
    pass


@transaction.atomic
def revoke_session(user: User, *, session_id: str, current_id: str) -> None:
    if session_id == current_id:
        raise SessionNotFoundError("Use Sign out to end the session on this device.")
    updated = UserSession.objects.filter(id=session_id, user=user, ended_at__isnull=True).update(
        ended_at=wall_clock(), end_reason=SessionEndReason.REVOKED
    )
    if not updated:
        raise SessionNotFoundError("This session is no longer signed in.")
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(user),
            action="auth.session_revoked",
            target_type="UserSession",
            target_id=session_id,
        )
    )


@transaction.atomic
def revoke_other_sessions(user: User, *, current_id: str) -> int:
    others = UserSession.objects.filter(user=user, ended_at__isnull=True)
    if current_id:
        others = others.exclude(id=current_id)
    count = others.update(ended_at=wall_clock(), end_reason=SessionEndReason.REVOKED_OTHERS)
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(user),
            action="auth.other_sessions_revoked",
            target_type="User",
            target_id=str(user.pk),
            metadata={"sessions_ended": count},
        )
    )
    return int(count)


def purge_account_security_history(*, as_of: datetime) -> dict[str, int]:
    """Retention: delete sign-in events and ended or expired sessions past the period."""
    cutoff = as_of - timedelta(days=retention_days())
    events, _ = SignInEvent.objects.filter(occurred_at__lt=cutoff).delete()
    expired_before = cutoff - timedelta(seconds=int(settings.AUTH_SESSION_MAX_AGE_SECONDS))
    sessions, _ = UserSession.objects.filter(ended_at__lt=cutoff).delete()
    stale, _ = UserSession.objects.filter(
        ended_at__isnull=True, created_at__lt=expired_before
    ).delete()
    return {"sign_in_events_deleted": events, "sessions_deleted": sessions + stale}
