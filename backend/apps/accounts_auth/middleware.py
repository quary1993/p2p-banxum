from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from backend.apps.accounts_auth.session_lifetime import (
    end_session_if_expired,
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
