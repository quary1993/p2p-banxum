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
                key = (
                    f"throttle:{self.scope}:window:{window_rule.name}:{identifier}:{bucket}"
                )
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
                key = (
                    f"throttle:{self.scope}:window:{window_rule.name}:{identifier}:{bucket}"
                )
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
        email = request.data.get("email") if isinstance(request.data, dict) else None
        if isinstance(email, str) and email:
            identifiers.append(f"email:{_hash_identifier(email.strip().lower())}")
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
        email = request.data.get("email") if isinstance(request.data, dict) else None
        if isinstance(email, str) and email:
            identifiers.append(f"email:{_hash_identifier(email.strip().lower())}")
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
