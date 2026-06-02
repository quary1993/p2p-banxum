from __future__ import annotations

from typing import Any

from backend.apps.platform_core.domain.actors import ActorRef

ADMIN_ACCOUNT_TYPES = frozenset({"admin", "superadmin"})
SUPERADMIN_ACCOUNT_TYPES = frozenset({"superadmin"})
BLOCKING_ACCOUNT_STATUSES = frozenset({"restricted", "locked", "closed"})


def account_type_of(user: Any) -> str:
    return str(getattr(user, "account_type", ""))


def account_status_of(user: Any) -> str:
    return str(getattr(user, "status", ""))


def has_admin_role(user: Any) -> bool:
    return bool(getattr(user, "is_staff", False)) and account_type_of(user) in ADMIN_ACCOUNT_TYPES


def has_superadmin_role(user: Any) -> bool:
    return (
        bool(getattr(user, "is_staff", False))
        and bool(getattr(user, "is_superuser", False))
        and account_type_of(user) in SUPERADMIN_ACCOUNT_TYPES
    )


def is_blocking_account_status(status: Any) -> bool:
    return str(status) in BLOCKING_ACCOUNT_STATUSES


def is_admin_actor(user: Any) -> bool:
    return (
        bool(getattr(user, "is_active", False))
        and has_admin_role(user)
        and not is_blocking_account_status(account_status_of(user))
    )


def is_superadmin_actor(user: Any) -> bool:
    return (
        bool(getattr(user, "is_active", False))
        and has_superadmin_role(user)
        and not is_blocking_account_status(account_status_of(user))
    )


def actor_ref_for_user(user: Any) -> ActorRef:
    account_type = account_type_of(user)
    if account_type == "superadmin":
        return ActorRef("superadmin", str(getattr(user, "pk", getattr(user, "id", ""))))
    if account_type == "admin":
        return ActorRef("admin", str(getattr(user, "pk", getattr(user, "id", ""))))
    return ActorRef("investor", str(getattr(user, "pk", getattr(user, "id", ""))))
