"""IP of Webby-Soft SRL. Audit S4-2: atomic rate counters and the account-wide sign-in limits.

Every counter is "count first, then compare": the increment is one atomic cache operation
(Redis ``INCR``), so requests that arrive at the same moment get different counts and exactly
``limit`` of them pass. A read followed by a separate write would let a burst through.

Account-wide limits count failures for one account from every IP address together, so many
addresses cannot share out a guessing attack. They are keyed by the typed email (a hash), also
when no such account exists: the answers never tell whether the account exists. So that other
people's failures cannot lock the owner out (audit A-47), a browser that already signed in to
the account (its ``banxum_device`` cookie, known only to that browser) is not held by the
account-wide password limit; its own limits per (email, IP) and per IP stay.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

HOUR = 60 * 60
DAY = 24 * HOUR


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def take_cooldown(key: str, seconds: int) -> bool:
    """Start a cooldown. False when one is already running (atomic: set if absent)."""
    if seconds <= 0:
        return True
    return bool(cache.add(key, True, timeout=seconds))


def _bucket_key(key: str, seconds: int, now: int) -> str:
    return f"{key}:{now // seconds}"


def take_window(key: str, seconds: int, limit: int, *, now: int | None = None) -> int | None:
    """Count one event in the fixed window. None when it is within the limit, else the seconds
    until the window ends."""
    moment = int(time.time()) if now is None else now
    bucket = _bucket_key(key, seconds, moment)
    cache.add(bucket, 0, timeout=seconds + 5)
    try:
        count = int(cache.incr(bucket))
    except ValueError:
        # The key expired between the two calls: this event is the first of a new window.
        cache.set(bucket, 1, timeout=seconds + 5)
        count = 1
    if count <= limit:
        return None
    return seconds - (moment % seconds)


def window_count(key: str, seconds: int, *, now: int | None = None) -> int:
    moment = int(time.time()) if now is None else now
    return int(cache.get(_bucket_key(key, seconds, moment), 0))


@dataclass(frozen=True, slots=True)
class FailureLimit:
    """Failures of one subject per hour and per day, counted atomically."""

    scope: str
    hourly: int
    daily: int

    def _keys(self, subject: str) -> tuple[tuple[str, int, int], ...]:
        base = f"throttle:{self.scope}:{_digest(subject)}"
        return ((f"{base}:hour", HOUR, self.hourly), (f"{base}:day", DAY, self.daily))

    def retry_after(self, subject: str) -> int | None:
        """Seconds to wait when the subject is at a limit, else None. Counts nothing."""
        now = int(time.time())
        waits = [
            seconds - (now % seconds)
            for key, seconds, limit in self._keys(subject)
            if limit > 0 and window_count(key, seconds, now=now) >= limit
        ]
        return max(waits) if waits else None

    def record_failure(self, subject: str) -> None:
        now = int(time.time())
        for key, seconds, limit in self._keys(subject):
            if limit > 0:
                take_window(key, seconds, limit, now=now)


def account_subject(email: str) -> str:
    return str(email or "").strip().lower()


def sign_in_account_failures() -> FailureLimit:
    """Wrong passwords for one investor account, from all addresses together."""
    return FailureLimit(
        scope="sign_in_account_failures",
        hourly=int(settings.AUTH_SIGN_IN_ACCOUNT_FAILURES_HOURLY),
        daily=int(settings.AUTH_SIGN_IN_ACCOUNT_FAILURES_DAILY),
    )


def admin_login_account_failures() -> FailureLimit:
    """Wrong passwords for one admin account, from all addresses together."""
    return FailureLimit(
        scope="admin_login_account_failures",
        hourly=int(settings.AUTH_SIGN_IN_ACCOUNT_FAILURES_HOURLY),
        daily=int(settings.AUTH_SIGN_IN_ACCOUNT_FAILURES_DAILY),
    )


def factor_account_failures() -> FailureLimit:
    """Wrong second-factor codes (SMS, app, recovery code) for one account."""
    return FailureLimit(
        scope="factor_account_failures",
        hourly=int(settings.AUTH_FACTOR_ACCOUNT_FAILURES_HOURLY),
        daily=int(settings.AUTH_FACTOR_ACCOUNT_FAILURES_DAILY),
    )
