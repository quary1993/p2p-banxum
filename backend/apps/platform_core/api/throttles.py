"""DRF throttle base on the shared cache-window counters (see services.rate_limits)."""

from __future__ import annotations

from collections.abc import Sequence

from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from backend.apps.platform_core.api.request_meta import client_ip
from backend.apps.platform_core.services.rate_limits import (
    WindowLimit,
    hash_identifier,
    record_window_hits,
    window_wait_seconds,
)


def client_ip_identifier(request: Request) -> str:
    """Cache identifier of the caller's IP (hashed; see ``client_ip`` for proxy handling)."""

    return f"ip:{hash_identifier(client_ip(request) or 'unknown')}"


class CacheWindowThrottle(BaseThrottle):
    """Counts every request in fixed cache windows and refuses once a window is full."""

    scope = "api"

    def __init__(self) -> None:
        self._wait: int | None = None

    def limits(self, request: Request) -> Sequence[WindowLimit]:
        raise NotImplementedError

    def allow_request(self, request: Request, view: APIView) -> bool:
        limits = self.limits(request)
        wait = window_wait_seconds(self.scope, limits)
        if wait is not None:
            self._wait = wait
            return False
        record_window_hits(self.scope, limits)
        return True

    def wait(self) -> int | None:
        return self._wait
