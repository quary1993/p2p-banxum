from __future__ import annotations

from ipaddress import ip_address

from django.conf import settings
from django.http import HttpRequest
from rest_framework.request import Request


def trusted_proxy_count() -> int:
    """Number of reverse proxies in front of Django that append to X-Forwarded-For."""

    try:
        count = int(getattr(settings, "TRUSTED_PROXY_COUNT", 0) or 0)
    except (TypeError, ValueError):
        return 0
    return max(count, 0)


def _normalized_ip(value: str) -> str | None:
    candidate = value.strip()
    if candidate.startswith("[") and "]" in candidate:
        # "[2001:db8::1]:443" -> "2001:db8::1"
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:
        # "203.0.113.7:51234" -> "203.0.113.7"
        candidate = candidate.split(":", 1)[0]
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def client_ip(request: Request | HttpRequest) -> str | None:
    """The client address as seen by the outermost trusted proxy (audit A-48).

    Each trusted proxy appends the address it received the request from, so the
    client is the entry ``TRUSTED_PROXY_COUNT`` places from the right. Entries further
    left were sent by the client and are never used. When the header has fewer
    entries than expected (the request did not pass through every proxy), or
    ``TRUSTED_PROXY_COUNT`` is 0, the socket address is used.
    """

    remote_addr = request.META.get("REMOTE_ADDR")
    remote = str(remote_addr) if remote_addr else None
    hops = trusted_proxy_count()
    if hops == 0:
        return remote
    forwarded_for = str(request.META.get("HTTP_X_FORWARDED_FOR", "") or "")
    entries = [entry.strip() for entry in forwarded_for.split(",") if entry.strip()]
    if len(entries) < hops:
        return remote
    return _normalized_ip(entries[-hops]) or remote


def user_agent(request: Request | HttpRequest) -> str:
    return str(request.META.get("HTTP_USER_AGENT", ""))
