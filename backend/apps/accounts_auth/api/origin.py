from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpRequest
from django.utils.http import is_same_domain
from rest_framework.permissions import BasePermission
from rest_framework.request import Request


def _own_origin(request: HttpRequest) -> str:
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}"


def _trusted_origin(origin: str, request: HttpRequest) -> bool:
    if origin == _own_origin(request):
        return True
    parsed = urlsplit(origin)
    for trusted in getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or []:
        if origin == trusted:
            return True
        if "://*." in trusted:
            trusted_scheme, trusted_host = trusted.split("://", 1)
            if parsed.scheme == trusted_scheme and is_same_domain(
                parsed.netloc, trusted_host[1:]
            ):
                return True
    return False


def is_cross_site_request(request: HttpRequest) -> bool:
    """True when a browser sent this request from another site.

    Browsers always send ``Origin`` (or ``Sec-Fetch-Site``) on cross-site POSTs, so a
    missing header means a same-site page or a non-browser client.
    """

    origin = request.META.get("HTTP_ORIGIN")
    if origin is not None:
        return origin == "null" or not _trusted_origin(str(origin), request)
    if str(request.META.get("HTTP_SEC_FETCH_SITE", "")).lower() == "cross-site":
        return True
    referer = str(request.META.get("HTTP_REFERER", "") or "")
    if referer:
        parsed = urlsplit(referer)
        if parsed.scheme and parsed.netloc:
            return not _trusted_origin(f"{parsed.scheme}://{parsed.netloc}", request)
    return False


class SameSiteRequestOnly(BasePermission):
    """Refuse cross-site browser posts to the sign-in endpoints (login CSRF, SECURITY-04).

    These views run without session authentication, so DRF's CSRF check does not
    apply; without this an attacker page could sign a victim's browser in to the
    attacker's own account.
    """

    message = "Cross-site request refused."

    def has_permission(self, request: Request, view: Any) -> bool:
        return not is_cross_site_request(request._request)  # noqa: SLF001
