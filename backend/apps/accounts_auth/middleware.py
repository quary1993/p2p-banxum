from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from backend.apps.accounts_auth.security_sessions import set_device_cookie, track_session_activity
from backend.apps.accounts_auth.session_lifetime import (
    end_session_if_expired,
    session_ended_response,
    session_expired_response,
)


class SessionLifetimeMiddleware:
    """End authenticated sessions after their absolute lifetime.

    The expired session is logged out before the view runs, so the request is
    handled as anonymous: public and login endpoints keep working, and an API
    request that needed the session is answered with 401 ``session_expired``
    instead of a generic permission error. The browser keeps getting that answer
    until it logs in again or signs out.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        expired = end_session_if_expired(request)
        response = self.get_response(request)
        if expired and request.path.startswith("/api/") and response.status_code in {401, 403}:
            return session_expired_response()
        return response


class UserSessionMiddleware:
    """U33-DEC-25: keep each signed-in browser's last activity and enforce ended sessions.

    A session the investor ended from another device is signed out here, before the view
    runs; an API request that needed it gets 401 ``session_expired`` with its own text.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        still_open = track_session_activity(request)
        response = self.get_response(request)
        # A sign-in in this request may have given the browser its device value (audit G-03).
        set_device_cookie(request, response)
        if (
            not still_open
            and request.path.startswith("/api/")
            and response.status_code in {401, 403}
        ):
            return session_ended_response()
        return response
