from __future__ import annotations

import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from backend.apps.accounts_auth.models import (
    AccountAccessEvent,
    AccountAccessReason,
    AccountStatus,
    AccountType,
    User,
)
from backend.apps.accounts_auth.services import (
    AccountAccessControlError,
    AdminAuthorizationError,
    ChangeAccountAccessCommand,
    change_account_access,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation


@pytest.fixture
def admin_user() -> User:
    return User.objects.create_user(
        email="admin@example.test",
        password="AdminPass123!",
        full_name="Admin User",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )


@pytest.fixture
def superadmin() -> User:
    return User.objects.create_user(
        email="superadmin@example.test",
        password="SuperAdminPass123!",
        full_name="Super Admin",
        account_type=AccountType.SUPERADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def investor() -> User:
    return User.objects.create_user(
        email="investor@example.test",
        full_name="Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    )


@pytest.mark.django_db
def test_admin_can_restrict_and_reactivate_investor_account(
    admin_user: User,
    investor: User,
) -> None:
    restricted = change_account_access(
        ChangeAccountAccessCommand(
            actor=admin_user,
            user_id=str(investor.id),
            new_status=AccountStatus.RESTRICTED,
            reason_code=AccountAccessReason.KYC_AML_REVIEW,
            note="PEP review pending.",
        )
    )

    investor.refresh_from_db()
    assert investor.status == AccountStatus.RESTRICTED
    assert investor.can_login is False
    assert restricted.previous_status == AccountStatus.ACTIVE
    assert restricted.new_status == AccountStatus.RESTRICTED
    assert AuditEvent.objects.filter(
        action="account.access_changed",
        target_id=str(investor.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="AccountAccessChanged",
        aggregate_id=str(investor.id),
    ).exists()

    reactivated = change_account_access(
        ChangeAccountAccessCommand(
            actor=admin_user,
            user_id=str(investor.id),
            new_status=AccountStatus.ACTIVE,
            reason_code=AccountAccessReason.ADMIN_CORRECTION,
            evidence_summary="Compliance released the hold.",
        )
    )

    investor.refresh_from_db()
    assert investor.status == AccountStatus.ACTIVE
    assert investor.can_login is True
    assert reactivated.previous_status == AccountStatus.RESTRICTED
    assert AccountAccessEvent.objects.count() == 2


@pytest.mark.django_db
def test_close_account_requires_clean_account_confirmation(
    admin_user: User,
    investor: User,
) -> None:
    with pytest.raises(AccountAccessControlError):
        change_account_access(
            ChangeAccountAccessCommand(
                actor=admin_user,
                user_id=str(investor.id),
                new_status=AccountStatus.CLOSED,
                reason_code=AccountAccessReason.ACCOUNT_CLOSURE,
                note="Support request.",
            )
        )

    event = change_account_access(
        ChangeAccountAccessCommand(
            actor=admin_user,
            user_id=str(investor.id),
            new_status=AccountStatus.CLOSED,
            reason_code=AccountAccessReason.ACCOUNT_CLOSURE,
            note="Support request.",
            clean_account_confirmed=True,
        )
    )

    investor.refresh_from_db()
    assert investor.status == AccountStatus.CLOSED
    assert investor.is_active is False
    assert investor.can_login is False
    assert event.clean_account_confirmed is True


@pytest.mark.django_db
def test_regular_admin_cannot_change_admin_account_access(
    admin_user: User,
    superadmin: User,
) -> None:
    with pytest.raises(AdminAuthorizationError):
        change_account_access(
            ChangeAccountAccessCommand(
                actor=admin_user,
                user_id=str(superadmin.id),
                new_status=AccountStatus.LOCKED,
                reason_code=AccountAccessReason.ADMIN_CORRECTION,
                note="Should not be allowed.",
            )
        )


@pytest.mark.django_db
def test_env_managed_superadmin_access_is_not_admin_mutable(superadmin: User) -> None:
    env_superadmin = User.objects.create_user(
        email="env-superadmin@example.test",
        password="SuperAdminPass123!",
        full_name="Env Super Admin",
        account_type=AccountType.SUPERADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
        is_superuser=True,
        is_env_managed_superadmin=True,
    )

    with pytest.raises(AccountAccessControlError):
        change_account_access(
            ChangeAccountAccessCommand(
                actor=superadmin,
                user_id=str(env_superadmin.id),
                new_status=AccountStatus.LOCKED,
                reason_code=AccountAccessReason.ADMIN_CORRECTION,
                note="Use env instead.",
            )
        )


@pytest.mark.django_db
def test_account_access_change_api(client: Client, admin_user: User, investor: User) -> None:
    client.force_login(admin_user)

    response = client.post(
        f"/api/v1/auth/admin/users/{investor.id}/access/",
        data={
            "new_status": AccountStatus.LOCKED,
            "reason_code": AccountAccessReason.COMPLIANCE_HOLD,
            "note": "Provider alert under review.",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["user"]["status"] == AccountStatus.LOCKED
    assert response.json()["event"]["reason_code"] == AccountAccessReason.COMPLIANCE_HOLD


@pytest.mark.django_db
def test_account_access_events_are_append_only(admin_user: User, investor: User) -> None:
    event = change_account_access(
        ChangeAccountAccessCommand(
            actor=admin_user,
            user_id=str(investor.id),
            new_status=AccountStatus.LOCKED,
            reason_code=AccountAccessReason.COMPLIANCE_HOLD,
            note="Provider alert under review.",
        )
    )

    event.note = "changed"
    with pytest.raises(AppendOnlyViolation):
        event.save()
    with pytest.raises(AppendOnlyViolation):
        AccountAccessEvent.objects.filter(id=event.id).update(note="changed")
    with pytest.raises(AppendOnlyViolation):
        AccountAccessEvent.objects.filter(id=event.id).delete()

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE accounts_auth_accountaccessevent SET note = %s WHERE id = %s",
                ["changed", event.id],
            )

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM accounts_auth_accountaccessevent WHERE id = %s",
                [event.id],
            )
