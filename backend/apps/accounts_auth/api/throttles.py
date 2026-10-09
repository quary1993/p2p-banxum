from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from backend.apps.accounts_auth.api.request_meta import client_ip
from backend.apps.accounts_auth.models import User


@dataclass(frozen=True, slots=True)
class WindowRule:
    name: str
    seconds: int
    limit: int


@dataclass(frozen=True, slots=True)
class CooldownRule:
    name: str
    seconds: int


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_email(request: Request) -> str:
    email = request.data.get("email") if isinstance(request.data, dict) else None
    if isinstance(email, str) and email.strip():
        return email.strip().lower()
    return ""


def email_ip_identifier(request: Request, email: str | None = None) -> str:
    """One bucket per (email, client IP) pair.

    Abuse limits that name an email address are always paired with the caller's IP:
    requests from other IPs can never use up the real owner's budget, so nobody can
    lock a named investor or admin out of login (audit A-47).
    """

    address = (email if email is not None else _request_email(request)).strip().lower()
    ip_address = client_ip(request) or "unknown"
    return f"email-ip:{_hash_identifier(f'{address}|{ip_address}')}"


class AuthThrottle(BaseThrottle):
    scope = "auth"
    cooldown_rules: tuple[CooldownRule, ...] = ()
    window_rules: tuple[WindowRule, ...] = ()

    def __init__(self) -> None:
        self._wait: int | None = None

    def get_identifiers(self, request: Request) -> tuple[str, ...]:
        ip_address = client_ip(request) or "unknown"
        return (f"ip:{_hash_identifier(ip_address)}",)

    def allow_request(self, request: Request, view: APIView) -> bool:
        now = int(time.time())
        identifiers = self.get_identifiers(request)

        for identifier in identifiers:
            for rule in self.cooldown_rules:
                key = f"throttle:{self.scope}:cooldown:{rule.name}:{identifier}"
                if cache.get(key):
                    self._wait = rule.seconds
                    return False

            for window_rule in self.window_rules:
                bucket = now // window_rule.seconds
                key = f"throttle:{self.scope}:window:{window_rule.name}:{identifier}:{bucket}"
                count = int(cache.get(key, 0))
                if count >= window_rule.limit:
                    self._wait = window_rule.seconds - (now % window_rule.seconds)
                    return False

        for identifier in identifiers:
            for rule in self.cooldown_rules:
                key = f"throttle:{self.scope}:cooldown:{rule.name}:{identifier}"
                cache.set(key, True, timeout=rule.seconds)

            for window_rule in self.window_rules:
                bucket = now // window_rule.seconds
                key = f"throttle:{self.scope}:window:{window_rule.name}:{identifier}:{bucket}"
                cache.add(key, 0, timeout=window_rule.seconds + 5)
                cache.incr(key)

        return True

    def wait(self) -> int | None:
        return self._wait


class MagicLinkRequestThrottle(AuthThrottle):
    scope = "magic_link_request"
    cooldown_rules = (CooldownRule("cooldown", settings.AUTH_MAGIC_LINK_COOLDOWN_SECONDS),)
    window_rules = (
        WindowRule("hour", 60 * 60, settings.AUTH_MAGIC_LINK_HOURLY_LIMIT),
        WindowRule("day", 24 * 60 * 60, settings.AUTH_MAGIC_LINK_DAILY_LIMIT),
    )

    def get_identifiers(self, request: Request) -> tuple[str, ...]:
        identifiers = list(super().get_identifiers(request))
        if _request_email(request):
            identifiers.append(email_ip_identifier(request))
        return tuple(identifiers)


class NaturalPersonRegistrationThrottle(AuthThrottle):
    scope = "natural_person_registration"
    cooldown_rules = (CooldownRule("cooldown", settings.AUTH_REGISTRATION_COOLDOWN_SECONDS),)
    window_rules = (
        WindowRule("hour", 60 * 60, settings.AUTH_REGISTRATION_HOURLY_LIMIT),
        WindowRule("day", 24 * 60 * 60, settings.AUTH_REGISTRATION_DAILY_LIMIT),
    )


class AdminLoginStartThrottle(AuthThrottle):
    scope = "admin_login_start"
    cooldown_rules = (CooldownRule("cooldown", settings.AUTH_ADMIN_LOGIN_COOLDOWN_SECONDS),)
    window_rules = (
        WindowRule("hour", 60 * 60, settings.AUTH_ADMIN_LOGIN_HOURLY_LIMIT),
        WindowRule("day", 24 * 60 * 60, settings.AUTH_ADMIN_LOGIN_DAILY_LIMIT),
    )

    def get_identifiers(self, request: Request) -> tuple[str, ...]:
        identifiers = list(super().get_identifiers(request))
        if _request_email(request):
            identifiers.append(email_ip_identifier(request))
        return tuple(identifiers)


class AdminLoginConfirmThrottle(AuthThrottle):
    scope = "admin_login_confirm"
    window_rules = (
        WindowRule("hour", 60 * 60, settings.AUTH_ADMIN_LOGIN_CONFIRM_HOURLY_LIMIT),
        WindowRule("day", 24 * 60 * 60, settings.AUTH_ADMIN_LOGIN_CONFIRM_DAILY_LIMIT),
    )


class PhoneVerificationRequestThrottle(AuthThrottle):
    scope = "phone_verification_request"
    cooldown_rules = (CooldownRule("cooldown", settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS),)
    window_rules = (
        WindowRule("hour", 60 * 60, settings.AUTH_PHONE_VERIFICATION_HOURLY_LIMIT),
        WindowRule("day", 24 * 60 * 60, settings.AUTH_PHONE_VERIFICATION_DAILY_LIMIT),
    )

    def get_identifiers(self, request: Request) -> tuple[str, ...]:
        identifiers = list(super().get_identifiers(request))
        if isinstance(request.user, User):
            identifiers.append(f"user:{request.user.id}")
        return tuple(identifiers)


class PhoneVerificationConfirmThrottle(AuthThrottle):
    scope = "phone_verification_confirm"
    window_rules = (
        WindowRule("hour", 60 * 60, settings.AUTH_PHONE_VERIFICATION_CONFIRM_HOURLY_LIMIT),
        WindowRule("day", 24 * 60 * 60, settings.AUTH_PHONE_VERIFICATION_CONFIRM_DAILY_LIMIT),
    )

    def get_identifiers(self, request: Request) -> tuple[str, ...]:
        identifiers = list(super().get_identifiers(request))
        if isinstance(request.user, User):
            identifiers.append(f"user:{request.user.id}")
        return tuple(identifiers)


class FailureBackoff:
    """Exponential backoff after repeated failures for one identifier.

    Only failures count. The first ``free_failures`` failures cost nothing; each
    further failure doubles the wait from ``base_seconds`` up to ``max_seconds``.
    A success resets the count. Callers key it per (email, IP), so a third party's
    failures never delay the owner's own login.
    """

    def __init__(
        self,
        *,
        scope: str,
        free_failures: int,
        base_seconds: int,
        max_seconds: int,
        window_seconds: int = 24 * 60 * 60,
    ) -> None:
        self.scope = scope
        self.free_failures = max(free_failures, 0)
        self.base_seconds = max(base_seconds, 0)
        self.max_seconds = max(max_seconds, 0)
        self.window_seconds = max(window_seconds, 1)

    def _count_key(self, identifier: str) -> str:
        return f"throttle:{self.scope}:failures:{identifier}"

    def _until_key(self, identifier: str) -> str:
        return f"throttle:{self.scope}:blocked-until:{identifier}"

    def retry_after(self, identifier: str) -> int | None:
        blocked_until = cache.get(self._until_key(identifier))
        if blocked_until is None:
            return None
        remaining = int(float(blocked_until) - time.time()) + 1
        return remaining if remaining > 0 else None

    def record_failure(self, identifier: str) -> int:
        """Count one failure; return the wait it imposes (0 while still free)."""

        count_key = self._count_key(identifier)
        cache.add(count_key, 0, timeout=self.window_seconds)
        try:
            failures = int(cache.incr(count_key))
        except ValueError:
            cache.set(count_key, 1, timeout=self.window_seconds)
            failures = 1
        excess = failures - self.free_failures
        if excess <= 0 or self.base_seconds == 0:
            return 0
        wait = min(self.base_seconds * (1 << min(excess - 1, 20)), self.max_seconds)
        if wait > 0:
            cache.set(self._until_key(identifier), time.time() + wait, timeout=wait + 1)
        return wait

    def reset(self, identifier: str) -> None:
        cache.delete_many([self._count_key(identifier), self._until_key(identifier)])


def admin_login_failure_backoff() -> FailureBackoff:
    return FailureBackoff(
        scope="admin_login_password",
        free_failures=settings.AUTH_ADMIN_LOGIN_FREE_FAILURES,
        base_seconds=settings.AUTH_ADMIN_LOGIN_BACKOFF_BASE_SECONDS,
        max_seconds=settings.AUTH_ADMIN_LOGIN_BACKOFF_MAX_SECONDS,
    )
