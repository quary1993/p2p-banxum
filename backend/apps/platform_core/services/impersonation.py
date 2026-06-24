from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core import signing
from django.db.models import Model

from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    has_admin_role,
    is_superadmin_actor,
)
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event

READONLY_IMPERSONATION_HEADER = "X-BANXUM-Impersonate"
READONLY_IMPERSONATION_SALT = "banxum.admin-readonly-impersonation.v1"
DEFAULT_TOKEN_MAX_AGE_SECONDS = 30 * 60


class ReadOnlyImpersonationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReadOnlyImpersonationContext:
    superadmin_user_id: str
    target_user_id: str
    target_email: str
    target_full_name: str


def _user_model() -> Any:
    return apps.get_model("accounts_auth", "User")


def _token_max_age_seconds() -> int:
    return int(
        getattr(
            settings,
            "ADMIN_READONLY_IMPERSONATION_TOKEN_MAX_AGE_SECONDS",
            DEFAULT_TOKEN_MAX_AGE_SECONDS,
        )
    )


def _target_payload(target: Model) -> dict[str, str]:
    return {
        "target_user_id": str(target.pk),
        "target_email": str(getattr(target, "email", "")),
        "target_full_name": str(getattr(target, "full_name", "")),
    }


def issue_readonly_impersonation_token(*, actor: Model, target_user_id: str) -> dict[str, Any]:
    if not is_superadmin_actor(actor):
        raise ReadOnlyImpersonationError(
            "Only an active superadmin can start read-only impersonation."
        )
    target = _user_model().objects.filter(id=target_user_id).first()
    if target is None:
        raise ReadOnlyImpersonationError("User was not found.")
    if has_admin_role(target):
        raise ReadOnlyImpersonationError("Admin and superadmin accounts cannot be impersonated.")
    payload = {
        "superadmin_user_id": str(actor.pk),
        **_target_payload(target),
    }
    token = signing.dumps(payload, salt=READONLY_IMPERSONATION_SALT, compress=True)
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="admin.readonly_impersonation_started",
            target_type="User",
            target_id=str(target.pk),
            metadata={
                "target_email": str(getattr(target, "email", "")),
                "target_full_name": str(getattr(target, "full_name", "")),
                "target_account_type": str(getattr(target, "account_type", "")),
                "token_max_age_seconds": _token_max_age_seconds(),
            },
        )
    )
    return {
        "token": token,
        "expires_in_seconds": _token_max_age_seconds(),
        **_target_payload(target),
    }


def resolve_readonly_impersonation(
    *, actor: Model, token: str
) -> tuple[Model, ReadOnlyImpersonationContext]:
    if not token:
        raise ReadOnlyImpersonationError("Missing read-only impersonation token.")
    if not is_superadmin_actor(actor):
        raise ReadOnlyImpersonationError(
            "Only an active superadmin can use read-only impersonation."
        )
    try:
        payload = signing.loads(
            token,
            salt=READONLY_IMPERSONATION_SALT,
            max_age=_token_max_age_seconds(),
        )
    except signing.BadSignature as exc:
        raise ReadOnlyImpersonationError(
            "Read-only impersonation token is invalid or expired."
        ) from exc
    if str(payload.get("superadmin_user_id", "")) != str(actor.pk):
        raise ReadOnlyImpersonationError(
            "Read-only impersonation token does not match this admin session."
        )
    target = _user_model().objects.filter(id=str(payload.get("target_user_id", ""))).first()
    if target is None:
        raise ReadOnlyImpersonationError("Read-only impersonation target was not found.")
    if has_admin_role(target):
        raise ReadOnlyImpersonationError("Admin and superadmin accounts cannot be impersonated.")
    context = ReadOnlyImpersonationContext(
        superadmin_user_id=str(actor.pk),
        target_user_id=str(target.pk),
        target_email=str(getattr(target, "email", "")),
        target_full_name=str(getattr(target, "full_name", "")),
    )
    return target, context
