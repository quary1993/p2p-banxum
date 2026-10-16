"""Abuse limits of the anonymous public-site endpoints (COMMS-DEC-009).

Fixed cache windows, the pattern of the auth throttles, through the shared platform_core
helper. Values come from settings (``PUBLIC_ENQUIRY_*`` and ``NEWSLETTER_*``).
"""

from __future__ import annotations

from collections.abc import Sequence

from django.conf import settings
from rest_framework.request import Request

from backend.apps.platform_core.api.throttles import CacheWindowThrottle, client_ip_identifier
from backend.apps.platform_core.services.rate_limits import (
    WindowLimit,
    WindowRule,
    hash_identifier,
)

TEN_MINUTES = 10 * 60
HOUR = 60 * 60
DAY = 24 * 60 * 60

PUBLIC_ENQUIRY_SCOPE = "public_enquiry"
NEWSLETTER_SUBSCRIBE_SCOPE = "newsletter_subscribe"
NEWSLETTER_CONFIRMATION_EMAIL_SCOPE = "newsletter_confirmation_email"
NEWSLETTER_CONFIRM_SCOPE = "newsletter_confirm"
NEWSLETTER_UNSUBSCRIBE_SCOPE = "newsletter_unsubscribe"
GLOBAL_IDENTIFIER = "global"


def public_enquiry_ip_limits(request: Request) -> list[WindowLimit]:
    identifier = client_ip_identifier(request)
    return [
        WindowLimit(
            identifier,
            WindowRule("10min", TEN_MINUTES, settings.PUBLIC_ENQUIRY_IP_10_MINUTE_LIMIT),
        ),
        WindowLimit(identifier, WindowRule("day", DAY, settings.PUBLIC_ENQUIRY_IP_DAILY_LIMIT)),
    ]


def public_enquiry_sender_limits(email: str) -> list[WindowLimit]:
    identifier = f"email:{hash_identifier(email.strip().lower())}"
    return [
        WindowLimit(
            identifier,
            WindowRule("sender-day", DAY, settings.PUBLIC_ENQUIRY_EMAIL_DAILY_LIMIT),
        )
    ]


def public_enquiry_global_limits() -> list[WindowLimit]:
    return [
        WindowLimit(
            GLOBAL_IDENTIFIER,
            WindowRule("global-day", DAY, settings.PUBLIC_ENQUIRY_GLOBAL_DAILY_LIMIT),
        )
    ]


def newsletter_confirmation_global_limits() -> list[WindowLimit]:
    return [
        WindowLimit(
            GLOBAL_IDENTIFIER,
            WindowRule("global-day", DAY, settings.NEWSLETTER_CONFIRMATION_GLOBAL_DAILY_LIMIT),
        )
    ]


class NewsletterSubscribeThrottle(CacheWindowThrottle):
    scope = NEWSLETTER_SUBSCRIBE_SCOPE

    def limits(self, request: Request) -> Sequence[WindowLimit]:
        identifier = client_ip_identifier(request)
        return (
            WindowLimit(
                identifier,
                WindowRule("hour", HOUR, settings.NEWSLETTER_SUBSCRIBE_IP_HOURLY_LIMIT),
            ),
            WindowLimit(
                identifier,
                WindowRule("day", DAY, settings.NEWSLETTER_SUBSCRIBE_IP_DAILY_LIMIT),
            ),
        )


class _NewsletterTokenThrottle(CacheWindowThrottle):
    def limits(self, request: Request) -> Sequence[WindowLimit]:
        return (
            WindowLimit(
                client_ip_identifier(request),
                WindowRule("hour", HOUR, settings.NEWSLETTER_TOKEN_IP_HOURLY_LIMIT),
            ),
        )


class NewsletterConfirmThrottle(_NewsletterTokenThrottle):
    scope = NEWSLETTER_CONFIRM_SCOPE


class NewsletterUnsubscribeThrottle(_NewsletterTokenThrottle):
    scope = NEWSLETTER_UNSUBSCRIBE_SCOPE
