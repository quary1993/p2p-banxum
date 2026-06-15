from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth.hashers import make_password
from django.test import Client, override_settings

from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    SensitiveAction,
    SensitiveActionCode,
    User,
)
from backend.apps.accounts_auth.services import (
    AdminAuthorizationError,
    AdminLoginConfirmCommand,
    AdminLoginInvalidCredentialsError,
    AdminLoginStartCommand,
    CreateAdminUserCommand,
    DuplicateEmailError,
    SuperadminBootstrapError,
    bootstrap_env_superadmin,
    confirm_admin_login,
    create_admin_user,
    delivery_secret_for_sensitive_action_code,
    start_admin_login,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent, OutboxMessage


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
def admin_user() -> User:
    return User.objects.create_user(
        email="admin@example.test",
        password="AdminPass123!",
        full_name="Admin User",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    )


@pytest.mark.django_db
def test_bootstrap_env_superadmin_creates_and_updates_env_managed_user(settings: Any) -> None:
    settings.GARANTA_SUPERADMIN_ENABLED = True
    settings.GARANTA_SUPERADMIN_EMAIL = "EnvSuperAdmin@Example.TEST"
    settings.GARANTA_SUPERADMIN_PASSWORD_HASH = make_password("FirstPass123!")
    settings.GARANTA_SUPERADMIN_FULL_NAME = "Env Superadmin"

    first = bootstrap_env_superadmin()

    assert first.action == "created"
    assert first.user is not None
    assert first.user.email == "envsuperadmin@example.test"
    assert first.user.check_password("FirstPass123!")
    assert first.user.account_type == AccountType.SUPERADMIN
    assert first.user.status == AccountStatus.ACTIVE
    assert first.user.is_env_managed_superadmin is True

    settings.GARANTA_SUPERADMIN_PASSWORD_HASH = make_password("SecondPass123!")
    second = bootstrap_env_superadmin()

    assert second.action == "updated"
    assert second.user is not None
    assert second.user.id == first.user.id
    assert second.user.check_password("SecondPass123!")
    assert AuditEvent.objects.filter(
        action="admin.env_superadmin_bootstrapped",
        target_id=str(second.user.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="EnvSuperadminBootstrapped",
        aggregate_id=str(second.user.id),
    ).exists()


@pytest.mark.django_db
def test_bootstrap_env_superadmin_disables_env_managed_user(settings: Any) -> None:
    user = User.objects.create_user(
        email="superadmin@example.test",
        password="SuperAdminPass123!",
        full_name="Env Superadmin",
        account_type=AccountType.SUPERADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
        is_superuser=True,
        is_env_managed_superadmin=True,
    )
    settings.GARANTA_SUPERADMIN_ENABLED = False

    result = bootstrap_env_superadmin()

    assert result.user is None
    assert result.disabled_user_ids == (str(user.id),)
    user.refresh_from_db()
    assert user.is_active is False
    assert user.status == AccountStatus.LOCKED


@pytest.mark.django_db
def test_bootstrap_env_superadmin_rejects_invalid_hash(settings: Any) -> None:
    settings.GARANTA_SUPERADMIN_ENABLED = True
    settings.GARANTA_SUPERADMIN_EMAIL = "superadmin@example.test"
    settings.GARANTA_SUPERADMIN_PASSWORD_HASH = "not-a-django-hash"

    with pytest.raises(SuperadminBootstrapError):
        bootstrap_env_superadmin()


@pytest.mark.django_db
def test_superadmin_can_create_admin_user(superadmin: User) -> None:
    user = create_admin_user(
        CreateAdminUserCommand(
            actor=superadmin,
            email="OpsAdmin@Example.TEST",
            password="OpsAdminPass123!",
            full_name="Ops Admin",
        )
    )

    assert user.email == "opsadmin@example.test"
    assert user.account_type == AccountType.ADMIN
    assert user.status == AccountStatus.ACTIVE
    assert user.is_staff is True
    assert user.is_superuser is False
    assert user.check_password("OpsAdminPass123!")
    assert AuditEvent.objects.filter(action="admin.user_created", target_id=str(user.id)).exists()
    assert DomainEvent.objects.filter(
        event_type="AdminUserCreated",
        aggregate_id=str(user.id),
    ).exists()

    with pytest.raises(DuplicateEmailError):
        create_admin_user(
            CreateAdminUserCommand(
                actor=superadmin,
                email="opsadmin@example.test",
                password="OpsAdminPass123!",
                full_name="Ops Admin",
            )
        )


@pytest.mark.django_db
def test_regular_admin_cannot_create_admin_user(admin_user: User) -> None:
    with pytest.raises(AdminAuthorizationError):
        create_admin_user(
            CreateAdminUserCommand(
                actor=admin_user,
                email="new-admin@example.test",
                password="OpsAdminPass123!",
                full_name="New Admin",
            )
        )


@pytest.mark.django_db
@override_settings(COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_admin_login_requires_password_then_email_code(
    admin_user: User,
    django_capture_on_commit_callbacks: Any,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        result = start_admin_login(
            AdminLoginStartCommand(email=admin_user.email, password="AdminPass123!")
        )

    assert result.code_record.user_id == admin_user.id
    assert result.code_record.action == SensitiveAction.ADMIN_LOGIN
    outbox_message = OutboxMessage.objects.get(
        topic="email.sensitive_action_code_requested",
        idempotency_key=f"sensitive-action-code:{result.code_record.id}",
    )
    assert "code" not in outbox_message.payload
    EmailDeliveryRecord = apps.get_model("communications", "EmailDeliveryRecord")
    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox_message)
    assert delivery.status == "sent"
    assert delivery.template_key == "auth.admin_login.code.v1"
    raw_code = delivery_secret_for_sensitive_action_code(result.code_record)

    authenticated = confirm_admin_login(
        AdminLoginConfirmCommand(
            code_id=str(result.code_record.id),
            raw_code=raw_code,
        )
    )

    assert authenticated.id == admin_user.id
    assert SensitiveActionCode.objects.get(id=result.code_record.id).consumed_at is not None
    assert AuditEvent.objects.filter(
        action="auth.admin_login_completed",
        target_id=str(admin_user.id),
    ).exists()


@pytest.mark.django_db
def test_admin_login_rejects_invalid_password(admin_user: User) -> None:
    with pytest.raises(AdminLoginInvalidCredentialsError):
        start_admin_login(
            AdminLoginStartCommand(email=admin_user.email, password="wrong-password")
        )

    assert AuditEvent.objects.filter(
        action="auth.admin_login_failed",
        target_id=str(admin_user.id),
    ).exists()
    assert SensitiveActionCode.objects.count() == 0


@pytest.mark.django_db
def test_admin_login_api_logs_in_session(client: Client, admin_user: User) -> None:
    start_response = client.post(
        "/api/v1/auth/admin/login/start/",
        data={"email": admin_user.email, "password": "AdminPass123!"},
        content_type="application/json",
    )

    assert start_response.status_code == 202
    code_record = SensitiveActionCode.objects.get(id=start_response.json()["code_id"])
    raw_code = delivery_secret_for_sensitive_action_code(code_record)

    confirm_response = client.post(
        "/api/v1/auth/admin/login/confirm/",
        data={"code_id": str(code_record.id), "code": raw_code},
        content_type="application/json",
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["user"]["email"] == admin_user.email

    me_response = client.get("/api/v1/auth/me/")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == admin_user.email

    logout_response = client.post("/api/v1/auth/logout/")
    assert logout_response.status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
def test_superadmin_create_admin_api(client: Client, superadmin: User) -> None:
    client.force_login(superadmin)

    response = client.post(
        "/api/v1/auth/admin/users/",
        data={
            "email": "ops-admin@example.test",
            "password": "OpsAdminPass123!",
            "full_name": "Ops Admin",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "ops-admin@example.test"
    assert User.objects.get(email="ops-admin@example.test").account_type == AccountType.ADMIN


@pytest.mark.django_db
def test_superadmin_create_admin_api_rejects_weak_password(
    client: Client,
    superadmin: User,
) -> None:
    client.force_login(superadmin)

    response = client.post(
        "/api/v1/auth/admin/users/",
        data={
            "email": "ops-admin@example.test",
            "password": "password",
            "full_name": "Ops Admin",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert User.objects.filter(email="ops-admin@example.test").exists() is False


@pytest.mark.django_db
def test_regular_admin_cannot_use_create_admin_api(client: Client, admin_user: User) -> None:
    client.force_login(admin_user)

    response = client.post(
        "/api/v1/auth/admin/users/",
        data={
            "email": "ops-admin@example.test",
            "password": "OpsAdminPass123!",
            "full_name": "Ops Admin",
        },
        content_type="application/json",
    )

    assert response.status_code == 403
