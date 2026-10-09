"""Absolute lifetime of authenticated investor and admin browser sessions.

A session is valid for ``AUTH_SESSION_MAX_AGE_SECONDS`` from login (absolute, not
sliding). The login moment is stored in the server-side session, so the limit is
enforced by the backend regardless of the cookie lifetime. Read-only superadmin
impersonation runs on the superadmin's own session and therefore ends with it.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, login
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from backend.apps.accounts_auth.models import User
from backend.apps.platform_core.domain.access import actor_ref_for_user
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event

SESSION_AUTHENTICATED_AT_KEY = "banxum_authenticated_at"
# Kept in the anonymous session that replaces an expired one, so every later API
# call from that browser keeps answering "session expired" until the next login.
SESSION_EXPIRED_AT_KEY = "banxum_session_expired_at"
SESSION_EXPIRED_CODE = "session_expired"
SESSION_EXPIRED_DETAIL = "Your session has expired. Please log in again."


def session_max_age_seconds() -> int:
    return int(settings.AUTH_SESSION_MAX_AGE_SECONDS)


def _wall_clock_seconds() -> int:
    # Real time on purpose: the QA simulated clock must not end or extend sessions.
    return int(timezone.now().timestamp())


def start_authenticated_session(request: HttpRequest, user: User) -> None:
    """Log the user in and start the absolute session lifetime clock."""
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.pop(SESSION_EXPIRED_AT_KEY, None)
    request.session[SESSION_AUTHENTICATED_AT_KEY] = _wall_clock_seconds()


def end_session_if_expired(request: HttpRequest) -> bool:
    """Log out an authenticated session older than the configured lifetime.

    Returns True when the request comes from an expired session: one ended now,
    or one ended earlier whose browser has not logged in again since. Sessions
    without a recorded login time (created before this policy or by test helpers)
    start their lifetime on first use.
    """
    session = getattr(request, "session", None)
    if session is None:
        return False
    if SESSION_KEY not in session:
        return SESSION_EXPIRED_AT_KEY in session
    now = _wall_clock_seconds()
    authenticated_at = session.get(SESSION_AUTHENTICATED_AT_KEY)
    if not isinstance(authenticated_at, int | float) or isinstance(authenticated_at, bool):
        session[SESSION_AUTHENTICATED_AT_KEY] = now
        return False
    if now - int(authenticated_at) < session_max_age_seconds():
        return False

    user: Any = getattr(request, "user", None)
    if isinstance(user, User):
        record_audit_event(
            AuditCommand(
                actor=actor_ref_for_user(user),
                action="auth.session_expired",
                target_type="User",
                target_id=str(user.pk),
                metadata={
                    "authenticated_at": int(authenticated_at),
                    "max_age_seconds": session_max_age_seconds(),
                },
            )
        )
    # Strip the authentication but keep the session key (unlike logout(), which
    # deletes the row): a parallel request still carrying this cookie must also
    # learn that the session expired instead of looking like a plain anonymous call.
    for key in (SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_AUTHENTICATED_AT_KEY):
        session.pop(key, None)
    session[SESSION_EXPIRED_AT_KEY] = now
    request.user = AnonymousUser()
    return True


def session_expired_response() -> JsonResponse:
    response = JsonResponse(
        {"detail": SESSION_EXPIRED_DETAIL, "code": SESSION_EXPIRED_CODE},
        status=401,
    )
    response["WWW-Authenticate"] = 'Session realm="api"'
    return response
