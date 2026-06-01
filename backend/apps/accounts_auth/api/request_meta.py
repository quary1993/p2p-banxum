from __future__ import annotations

from django.conf import settings
from rest_framework.request import Request


def client_ip(request: Request) -> str | None:
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return str(forwarded_for).split(",")[0].strip()

    remote_addr = request.META.get("REMOTE_ADDR")
    return str(remote_addr) if remote_addr else None


def user_agent(request: Request) -> str:
    return str(request.META.get("HTTP_USER_AGENT", ""))
