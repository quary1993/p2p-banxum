from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from backend.apps.platform_core.services.impersonation import READONLY_IMPERSONATION_HEADER

SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
READONLY_IMPERSONATION_ALLOWED_UNSAFE_PATHS = frozenset(
    {"/api/v1/investor/portal/documents/download/"}
)


class RejectReadonlyImpersonationWritesMiddleware:
    """Make the support impersonation contract read-only at the HTTP boundary."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            request.path.startswith("/api/")
            and (request.method or "").upper() not in SAFE_HTTP_METHODS
            and request.path not in READONLY_IMPERSONATION_ALLOWED_UNSAFE_PATHS
            and request.headers.get(READONLY_IMPERSONATION_HEADER, "")
        ):
            return JsonResponse(
                {"detail": "Read-only impersonation cannot perform write actions."},
                status=403,
            )
        return self.get_response(request)
