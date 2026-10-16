"""Fixed-window counters in the cache, shared by modules that guard anonymous endpoints.

This is the cache-window pattern of the auth throttles (``accounts_auth/api/throttles.py``)
as a module-neutral helper: one counter per (scope, rule, identifier, window), created
with ``cache.add`` and raised with ``cache.incr``. Identifiers that name a person, an
address or an IP are hashed before they reach the cache.

Callers check first (``window_wait_seconds``) and count afterwards
(``record_window_hits``), so an endpoint can decide which requests use up a budget, for
example only accepted form submissions.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from dataclasses import dataclass

from django.core.cache import cache


@dataclass(frozen=True, slots=True)
class WindowRule:
    name: str
    seconds: int
    limit: int


@dataclass(frozen=True, slots=True)
class WindowLimit:
    """One rule applied to one identifier, for example ``ip:<hash>`` or ``global``."""

    identifier: str
    rule: WindowRule


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def current_epoch_seconds() -> int:
    """Wall-clock seconds; a function so tests can pin the window."""

    return int(time.time())


def _window_key(scope: str, limit: WindowLimit, now: int) -> str:
    bucket = now // max(limit.rule.seconds, 1)
    return f"throttle:{scope}:window:{limit.rule.name}:{limit.identifier}:{bucket}"


def window_wait_seconds(scope: str, limits: Sequence[WindowLimit]) -> int | None:
    """Seconds until the longest exhausted window resets, or None while all have room."""

    now = current_epoch_seconds()
    wait: int | None = None
    for limit in limits:
        seconds = max(limit.rule.seconds, 1)
        count = int(cache.get(_window_key(scope, limit, now), 0) or 0)
        if count >= limit.rule.limit:
            remaining = seconds - (now % seconds)
            wait = remaining if wait is None else max(wait, remaining)
    return wait


def record_window_hits(scope: str, limits: Sequence[WindowLimit]) -> None:
    """Count one hit in every window of ``limits``."""

    now = current_epoch_seconds()
    for limit in limits:
        key = _window_key(scope, limit, now)
        timeout = max(limit.rule.seconds, 1) + 5
        cache.add(key, 0, timeout=timeout)
        try:
            cache.incr(key)
        except ValueError:
            # The key expired between add and incr.
            cache.set(key, 1, timeout=timeout)
