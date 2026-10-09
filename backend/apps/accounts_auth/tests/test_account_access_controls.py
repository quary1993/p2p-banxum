from __future__ import annotations

from datetime import date
from importlib import import_module

import pytest
from django.apps import apps
from django.db import DatabaseError, connection, transaction
from django.test import Client

from backend.apps.accounts_auth.models import (
    AccountAccessEvent,
    AccountAccessReason,
    AccountStatus,
    AccountType,
    EmailLoginToken,
    User,
)
from backend.apps.accounts_auth.services import (
    AccountAccessControlError,
    AdminAuthorizationError,
    ChangeAccountAccessCommand,
    InvalidOrExpiredTokenError,
    MagicLinkRequestCommand,
    change_account_access,
    issue_magic_link,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent, OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.services.currencies import seed_launch_currencies


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
def test_close_account_rejects_unresolved_compliance_case(
    admin_user: User,
    investor: User,
) -> None:
    kyc_case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    kyc_case_model.objects.create(
        user=investor,
        subject_reference=f"user:{investor.id}",
        provider_environment="test",
        status="manual_review",
    )

    with pytest.raises(AccountAccessControlError, match="unresolved compliance review"):
        change_account_access(
            ChangeAccountAccessCommand(
                actor=admin_user,
                user_id=str(investor.id),
                new_status=AccountStatus.CLOSED,
                reason_code=AccountAccessReason.ACCOUNT_CLOSURE,
                note="Support request.",
                clean_account_confirmed=True,
            )
        )


@pytest.mark.django_db
def test_close_account_rejects_nonzero_investor_balance(
    admin_user: User,
    investor: User,
) -> None:
    ledger_services = import_module("backend.apps.ledger.services")

    seed_launch_currencies()
    ledger_services.declare_lender_deposit(
        ledger_services.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.id),
            amount_minor=100_00,
            currency="CHF",
            booking_date=date(2026, 7, 21),
            value_date=date(2026, 7, 21),
            collection_account_identifier="CH11GARANTATEST",
            payer_name=investor.full_name,
            payer_account_identifier="CH9300762011623852957",
            payment_reference=f"TEST-{investor.investor_reference}",
            idempotency_key="account-closure-balance-blocker",
        )
    )

    with pytest.raises(AccountAccessControlError, match="non-zero cash balance"):
        change_account_access(
            ChangeAccountAccessCommand(
                actor=admin_user,
                user_id=str(investor.id),
                new_status=AccountStatus.CLOSED,
                reason_code=AccountAccessReason.ACCOUNT_CLOSURE,
                note="Support request.",
                clean_account_confirmed=True,
            )
        )


@pytest.mark.django_db
def test_marketing_consent_api_is_persisted_and_audited(
    client: Client,
    investor: User,
) -> None:
    client.force_login(investor)

    response = client.patch(
        "/api/v1/auth/preferences/marketing/",
        data={"marketing_consent": True},
        content_type="application/json",
    )

    assert response.status_code == 200
    investor.refresh_from_db()
    assert investor.marketing_consent is True
    assert response.json()["user"]["marketing_consent"] is True
    assert AuditEvent.objects.filter(
        action="account.marketing_consent_changed",
        target_id=str(investor.id),
    ).exists()


@pytest.mark.django_db
def test_readonly_impersonation_header_blocks_all_unsafe_api_requests(
    client: Client,
    superadmin: User,
) -> None:
    client.force_login(superadmin)

    response = client.post(
        "/api/v1/auth/logout/",
        HTTP_X_BANXUM_IMPERSONATE="signed-readonly-context",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Read-only impersonation cannot perform write actions."
    assert client.get("/api/v1/auth/me/").status_code == 200


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


def _restrict(admin_user: User, investor: User, new_status: AccountStatus) -> None:
    change_account_access(
        ChangeAccountAccessCommand(
            actor=admin_user,
            user_id=str(investor.id),
            new_status=new_status,
            reason_code=AccountAccessReason.COMPLIANCE_HOLD,
            note="Compliance review.",
        )
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("new_status", "status_word"),
    [(AccountStatus.RESTRICTED, "restricted"), (AccountStatus.LOCKED, "locked")],
)
def test_blocked_account_login_request_emails_a_reason_without_revealing_it(
    client: Client,
    admin_user: User,
    investor: User,
    new_status: AccountStatus,
    status_word: str,
) -> None:
    _restrict(admin_user, investor, new_status)

    response = client.post(
        "/api/v1/auth/magic-link/request/",
        data={"email": investor.email},
        content_type="application/json",
    )

    # Same answer as for an unknown address, so account existence stays private.
    assert response.status_code == 202
    assert response.content == b""
    assert not EmailLoginToken.objects.filter(user=investor).exists()
    notice = OutboxMessage.objects.get(topic="email.account_login_blocked")
    assert notice.payload["email"] == investor.email
    assert notice.payload["subject"] == f"Your BANXUM account is {status_word}"
    assert f"currently {status_word}" in notice.payload["body_text"]
    assert "support@banxum.com" in notice.payload["body_text"]
    assert AuditEvent.objects.filter(
        action="auth.login_blocked_notice_requested",
        target_id=str(investor.id),
    ).exists()

    # Repeated requests within the hour reuse the same notice.
    with pytest.raises(InvalidOrExpiredTokenError):
        issue_magic_link(MagicLinkRequestCommand(email=investor.email))
    assert OutboxMessage.objects.filter(topic="email.account_login_blocked").count() == 1


@pytest.mark.django_db
def test_login_request_for_unknown_or_active_account_sends_no_blocked_notice(
    investor: User,
) -> None:
    with pytest.raises(InvalidOrExpiredTokenError):
        issue_magic_link(MagicLinkRequestCommand(email="missing@example.test"))
    issue_magic_link(MagicLinkRequestCommand(email=investor.email))

    assert not OutboxMessage.objects.filter(topic="email.account_login_blocked").exists()


@pytest.mark.django_db
def test_login_link_of_restricted_account_explains_the_restriction(
    client: Client,
    admin_user: User,
    investor: User,
) -> None:
    link = issue_magic_link(MagicLinkRequestCommand(email=investor.email))
    _restrict(admin_user, investor, AccountStatus.RESTRICTED)

    response = client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": link.raw_token},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Your account is restricted. Please contact support at support@banxum.com "
            "for further details."
        ),
        "code": "account_restricted",
    }
    assert client.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
def test_existing_session_of_restricted_account_reports_the_status(
    client: Client,
    admin_user: User,
    investor: User,
) -> None:
    client.force_login(investor)
    _restrict(admin_user, investor, AccountStatus.RESTRICTED)

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.json()["user"]["status"] == AccountStatus.RESTRICTED
