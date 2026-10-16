"""IP of Webby-Soft SRL. API pieces shared by every sensitive investor action (ACC-DEC-009)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import serializers
from rest_framework.response import Response

from backend.apps.platform_core.services.sensitive_actions import SensitiveActionPinError

if TYPE_CHECKING:
    from django.utils.functional import _StrPromise

PIN_REGEX = r"^\d{6}$"
PIN_ERROR_MESSAGES: dict[str, str | _StrPromise] = {
    "invalid": "Enter your 6-digit PIN.",
    "required": "Enter your 6-digit PIN.",
    "blank": "Enter your 6-digit PIN.",
}


def sensitive_action_pin_field() -> serializers.RegexField:
    """The ``pin`` request field: the investor's 6 digits, never echoed back."""

    return serializers.RegexField(
        PIN_REGEX,
        write_only=True,
        trim_whitespace=True,
        error_messages=PIN_ERROR_MESSAGES,
    )


def sensitive_action_pin_error_response(exc: SensitiveActionPinError) -> Response:
    """400 ``pin_invalid``, 423 ``pin_locked`` or 409 ``pin_required``."""

    return Response(exc.payload(), status=exc.http_status)
