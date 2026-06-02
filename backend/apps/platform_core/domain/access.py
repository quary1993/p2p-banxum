from __future__ import annotations

from typing import Any

from django.apps import apps

from backend.apps.platform_core.domain.actors import ActorRef

ADMIN_ACCOUNT_TYPES = frozenset({"admin", "superadmin"})
SUPERADMIN_ACCOUNT_TYPES = frozenset({"superadmin"})
LENDER_ACCOUNT_TYPES = frozenset(
    {"natural_person_lender", "legal_entity_lender_representative"}
)
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


def has_lender_role(user: Any) -> bool:
    return account_type_of(user) in LENDER_ACCOUNT_TYPES


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


def is_lender_actor(user: Any) -> bool:
    return (
        bool(getattr(user, "is_active", False))
        and has_lender_role(user)
        and not is_blocking_account_status(account_status_of(user))
    )


def user_kyc_status_value(user: Any) -> str:
    case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    case = case_model.objects.filter(user_id=getattr(user, "pk", None)).first()
    if case is None:
        return "not_started"
    return str(getattr(case, "status", "not_started"))


def user_can_access_financial_features(user: Any) -> bool:
    if not is_lender_actor(user):
        return False
    if getattr(user, "phone_verified_at", None) is None:
        return False
    if account_type_of(user) == "legal_entity_lender_representative":
        return True
    return user_kyc_status_value(user) == "approved"


def actor_ref_for_user(user: Any) -> ActorRef:
    account_type = account_type_of(user)
    if account_type == "superadmin":
        return ActorRef("superadmin", str(getattr(user, "pk", getattr(user, "id", ""))))
    if account_type == "admin":
        return ActorRef("admin", str(getattr(user, "pk", getattr(user, "id", ""))))
    return ActorRef("investor", str(getattr(user, "pk", getattr(user, "id", ""))))
