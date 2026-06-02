from __future__ import annotations

from types import SimpleNamespace

from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    has_admin_role,
    has_superadmin_role,
    is_admin_actor,
    is_superadmin_actor,
)


def _user(
    *,
    account_type: str,
    status: str = "active",
    is_staff: bool = True,
    is_superuser: bool = False,
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="user-id",
        pk="user-id",
        account_type=account_type,
        status=status,
        is_staff=is_staff,
        is_superuser=is_superuser,
        is_active=is_active,
    )


def test_admin_actor_predicate_requires_active_staff_admin_not_blocked() -> None:
    assert is_admin_actor(_user(account_type="admin")) is True
    assert is_admin_actor(_user(account_type="superadmin", is_superuser=True)) is True

    assert is_admin_actor(_user(account_type="natural_person_lender", is_staff=False)) is False
    assert is_admin_actor(_user(account_type="admin", is_active=False)) is False
    assert is_admin_actor(_user(account_type="admin", is_staff=False)) is False
    assert is_admin_actor(_user(account_type="admin", status="restricted")) is False
    assert is_admin_actor(_user(account_type="admin", status="locked")) is False
    assert is_admin_actor(_user(account_type="admin", status="closed")) is False


def test_role_predicates_distinguish_role_from_active_access() -> None:
    restricted_superadmin = _user(
        account_type="superadmin",
        status="restricted",
        is_superuser=True,
    )

    assert has_admin_role(restricted_superadmin) is True
    assert has_superadmin_role(restricted_superadmin) is True
    assert is_admin_actor(restricted_superadmin) is False
    assert is_superadmin_actor(restricted_superadmin) is False


def test_actor_ref_for_user_maps_known_account_types() -> None:
    superadmin = _user(account_type="superadmin", is_superuser=True)

    assert actor_ref_for_user(superadmin).actor_type == "superadmin"
    assert actor_ref_for_user(_user(account_type="admin")).actor_type == "admin"
    assert (
        actor_ref_for_user(_user(account_type="natural_person_lender", is_staff=False)).actor_type
        == "investor"
    )
