"""IP of Webby-Soft SRL. 18.5: which second factor an account has (no other imports, so both the
registration services and the sign-in services can use it).

- "app": an active authenticator app (it wins: D-1, the app replaces the PIN and the SMS code).
- "sms": a verified phone number.
- "": no factor yet (registration not finished; no financial access).
"""

from __future__ import annotations

from typing import Any

from backend.apps.accounts_auth.models import AuthenticatorApp

FACTOR_APP = "app"
FACTOR_SMS = "sms"


def active_authenticator(user: Any) -> AuthenticatorApp | None:
    if getattr(user, "pk", None) is None:
        return None
    return (
        AuthenticatorApp.objects.filter(
            user_id=user.pk, confirmed_at__isnull=False, disabled_at__isnull=True
        )
        .order_by("-confirmed_at")
        .first()
    )


def factor_kind(user: Any) -> str:
    if getattr(user, "pk", None) is None:
        return ""
    if AuthenticatorApp.objects.filter(
        user_id=user.pk, confirmed_at__isnull=False, disabled_at__isnull=True
    ).exists():
        return FACTOR_APP
    if getattr(user, "phone_verified_at", None) is not None and bool(
        getattr(user, "phone_number", None)
    ):
        return FACTOR_SMS
    return ""
