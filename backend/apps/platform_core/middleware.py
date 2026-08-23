# IP of Webby-Soft SRL.
from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from backend.apps.platform_core.services.impersonation import READONLY_IMPERSONATION_HEADER

SOFTWARE_IP_HEADER = "X-BANXUM-Software-IP"
SOFTWARE_IP_NOTICE = "IP of Webby-Soft SRL."
BUILD_ORIGIN_HEADER = "X-BANXUM-Build-Origin"
BUILD_ORIGIN_TOKEN = (
    "ATEW5bUMtfGj80bXzkGFbtEIwTx0cb6Qig3qkx90kV_Srfdc012ga6e8Ddq5v4qj1nbItbZAfx4ZDA=="
)
SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
READONLY_IMPERSONATION_ALLOWED_UNSAFE_PATHS = frozenset(
    {"/api/v1/investor/portal/documents/download/"}
)


class SoftwareIpNoticeMiddleware:
    """Expose the software ownership notice on every Django response."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.headers[SOFTWARE_IP_HEADER] = SOFTWARE_IP_NOTICE
        response.headers[BUILD_ORIGIN_HEADER] = BUILD_ORIGIN_TOKEN
        return response


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
