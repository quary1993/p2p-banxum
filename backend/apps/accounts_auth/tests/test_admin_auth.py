from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth.hashers import make_password
from django.test import Client, override_settings
from django.utils import timezone

from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    AuthenticatorApp,
    SensitiveAction,
    SensitiveActionCode,
    User,
)
from backend.apps.accounts_auth.services import (
    AdminAuthorizationError,
    AdminLoginInvalidCredentialsError,
    CreateAdminUserCommand,
    DuplicateEmailError,
    InvalidPasswordError,
    SuperadminBootstrapError,
    bootstrap_env_superadmin,
    create_admin_user,
    delivery_secret_for_sensitive_action_code,
)
from backend.apps.accounts_auth.tests.signin_helpers import (
    admin_sign_in,
    app_code,
    enrollment_code,
    give_authenticator,
)
from backend.apps.accounts_auth.two_factor import (
    TwoFactorError,
    complete_admin_enrollment,
    complete_admin_sign_in,
    reset_admin_authenticator,
    start_admin_sign_in,
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
def test_first_admin_sign_in_sets_up_the_app_with_the_email_code(
    admin_user: User,
    django_capture_on_commit_callbacks: Any,
) -> None:
    """18.5: admins sign in with the password and an authenticator app. The first time, the
    email code proves the mailbox and the first app code proves the new app."""
    with django_capture_on_commit_callbacks(execute=True):
        step = start_admin_sign_in(email=admin_user.email, password="AdminPass123!")

    assert step.status == "enrollment_required"
    assert step.enrollment is not None
    code_record = SensitiveActionCode.objects.get(id=step.code_id)
    assert code_record.action == SensitiveAction.ADMIN_LOGIN
    outbox_message = OutboxMessage.objects.get(
        topic="email.sensitive_action_code_requested",
        idempotency_key=f"sensitive-action-code:{code_record.id}",
    )
    assert "code" not in outbox_message.payload
    EmailDeliveryRecord = apps.get_model("communications", "EmailDeliveryRecord")
    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox_message)
    assert delivery.status == "sent"
    assert delivery.template_key == "auth.admin_login.code.v1"
    email_code = delivery_secret_for_sensitive_action_code(code_record)
    secret = step.enrollment["secret"]

    # A wrong app code leaves the email code usable.
    with pytest.raises(TwoFactorError):
        complete_admin_enrollment(
            code_id=step.code_id,
            email_code=email_code,
            enrollment_id=step.enrollment["enrollment_id"],
            code="000000" if enrollment_code(secret) != "000000" else "111111",
        )
    assert SensitiveActionCode.objects.get(id=code_record.id).consumed_at is None

    authenticated = complete_admin_enrollment(
        code_id=step.code_id,
        email_code=email_code,
        enrollment_id=step.enrollment["enrollment_id"],
        code=enrollment_code(secret),
    )

    assert authenticated.id == admin_user.id
    assert SensitiveActionCode.objects.get(id=code_record.id).consumed_at is not None
    assert AuthenticatorApp.objects.filter(
        user=admin_user, confirmed_at__isnull=False, disabled_at__isnull=True
    ).exists()
    assert AuditEvent.objects.filter(
        action="auth.admin_login_completed",
        target_id=str(admin_user.id),
    ).exists()

    # Next time: password, then the app code; no email code.
    codes_before = SensitiveActionCode.objects.count()
    second = start_admin_sign_in(email=admin_user.email, password="AdminPass123!")
    assert second.status == "factor_required"
    assert SensitiveActionCode.objects.count() == codes_before
    assert complete_admin_sign_in(challenge_id=second.challenge_id, code=app_code(admin_user))


@pytest.mark.django_db
def test_admin_setup_email_exhaustion_is_not_an_account_or_app_lock(admin_user: User) -> None:
    step = start_admin_sign_in(email=admin_user.email, password="AdminPass123!")
    assert step.enrollment
    record = SensitiveActionCode.objects.get(pk=step.code_id)
    actual = delivery_secret_for_sensitive_action_code(record)
    wrong = "000000" if actual != "000000" else "111111"
    for attempt in range(1, record.max_attempts + 1):
        with pytest.raises(TwoFactorError) as exc:
            complete_admin_enrollment(
                code_id=step.code_id,
                email_code=wrong,
                enrollment_id=step.enrollment["enrollment_id"],
                code=enrollment_code(step.enrollment["secret"]),
            )
        assert exc.value.code == (
            "enrollment_email_exhausted" if attempt == record.max_attempts else "email_code_invalid"
        )
    admin_user.refresh_from_db()
    assert admin_user.can_login
    app = AuthenticatorApp.objects.get(pk=step.enrollment["enrollment_id"])
    assert app.confirmed_at is None and app.locked_until is None


@pytest.mark.django_db
def test_admin_reset_retires_unfinished_setup_and_allows_fresh_setup(
    admin_user: User, superadmin: User
) -> None:
    admin_user.phone_number = "+41790000001"
    admin_user.phone_verified_at = timezone.now()
    admin_user.save(update_fields=["phone_number", "phone_verified_at"])
    old = start_admin_sign_in(email=admin_user.email, password="AdminPass123!")
    assert old.enrollment
    reset_admin_authenticator(actor=superadmin, admin_user_id=str(admin_user.pk))
    assert AuthenticatorApp.objects.get(pk=old.enrollment["enrollment_id"]).disabled_at is not None
    assert SensitiveActionCode.objects.get(pk=old.code_id).superseded_at is not None
    new = start_admin_sign_in(email=admin_user.email, password="AdminPass123!")
    assert new.status == "enrollment_required" and new.enrollment
    assert new.enrollment["secret"] != old.enrollment["secret"]
    assert new.code_id != old.code_id
    authenticated = complete_admin_enrollment(
        code_id=new.code_id,
        email_code=delivery_secret_for_sensitive_action_code(
            SensitiveActionCode.objects.get(pk=new.code_id)
        ),
        enrollment_id=new.enrollment["enrollment_id"],
        code=enrollment_code(new.enrollment["secret"]),
    )
    assert authenticated.pk == admin_user.pk


@pytest.mark.django_db
def test_admin_login_rejects_invalid_password(admin_user: User) -> None:
    with pytest.raises(AdminLoginInvalidCredentialsError):
        start_admin_sign_in(email=admin_user.email, password="wrong-password")

    assert AuditEvent.objects.filter(
        action="auth.admin_login_failed",
        target_id=str(admin_user.id),
    ).exists()
    assert SensitiveActionCode.objects.count() == 0


@pytest.mark.django_db
def test_admin_login_api_logs_in_session(client: Client, admin_user: User) -> None:
    give_authenticator(admin_user)

    confirm_response = admin_sign_in(client, admin_user, "AdminPass123!")

    assert confirm_response.json()["user"]["email"] == admin_user.email
    me_response = client.get("/api/v1/auth/me/")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == admin_user.email

    logout_response = client.post("/api/v1/auth/logout/")
    assert logout_response.status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
def test_a_wrong_admin_app_code_signs_nobody_in(client: Client, admin_user: User) -> None:
    give_authenticator(admin_user)
    start = client.post(
        "/api/v1/auth/admin/login/start/",
        data={"email": admin_user.email, "password": "AdminPass123!"},
        content_type="application/json",
    )
    assert start.json()["status"] == "factor_required"
    right = app_code(admin_user)
    wrong = "000000" if right != "000000" else "111111"

    response = client.post(
        "/api/v1/auth/admin/login/confirm/",
        data={"challenge_id": start.json()["challenge_id"], "code": wrong},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert client.get("/api/v1/auth/me/").status_code == 403


@pytest.mark.django_db
def test_a_super_admin_resets_another_admins_app(
    client: Client, superadmin: User, admin_user: User
) -> None:
    give_authenticator(admin_user)
    other = Client()
    admin_sign_in(other, admin_user, "AdminPass123!")
    client.force_login(superadmin)

    response = client.post(f"/api/v1/auth/admin/users/{admin_user.id}/authenticator/reset/")

    assert response.status_code == 200
    assert not AuthenticatorApp.objects.filter(user=admin_user, disabled_at__isnull=True).exists()
    assert other.get("/api/v1/auth/me/").status_code == 401
    # The next sign-in sets up a new app with an email code.
    assert start_admin_sign_in(email=admin_user.email, password="AdminPass123!").status == (
        "enrollment_required"
    )
    # Audit S4-6 (D3): the admin is told at once, by email and by a task in the console.
    [notice] = OutboxMessage.objects.filter(
        topic="email.security_change", payload__user_id=str(admin_user.pk)
    )
    payload = notice.payload
    assert payload["email"] == admin_user.email
    assert payload["template_key"] == "security.admin_authenticator_reset.v1"
    assert superadmin.email in payload["body_text"] and "This was not me" in payload["body_text"]
    assert ["Reset by", f"{superadmin.full_name} ({superadmin.email})"] in payload["data_rows"]
    assert any(row[0] == "Time" and "Europe/Zurich" in row[1] for row in payload["data_rows"])
    assert any(row[0] == "Contact" and "@" in row[1] for row in payload["data_rows"])
    # No secret, code or link is in the notice.
    text = str(payload).lower()
    for forbidden in ("otpauth", "secret=", "action_url", "delivery_secret", "token"):
        assert forbidden not in text
    reset = AuditEvent.objects.get(action="auth.admin_authenticator_reset")
    assert notice.idempotency_key == f"security:admin-authenticator-reset:{reset.pk}"
    task = apps.get_model("admin_ops", "AdminTask").objects.get(
        related_object_type="AdminAuthenticatorReset"
    )
    assert (str(task.assigned_admin_id), task.status, task.priority) == (
        str(admin_user.pk),
        "open",
        "high",
    )
    assert "This was not me" in task.notes
    # Nobody resets their own app.
    own = client.post(f"/api/v1/auth/admin/users/{superadmin.id}/authenticator/reset/")
    assert own.status_code == 403
    assert OutboxMessage.objects.filter(topic="email.security_change").count() == 1


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
@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("Short-Pass1", "at least 12 characters"),
        ("password1234", "too common"),
        # Audit S4-5: the same upper bound as for investors.
        ("x" * 129, "at most 128 characters"),
    ],
)
def test_admin_passwords_need_twelve_characters_and_no_common_password(
    superadmin: User,
    password: str,
    reason: str,
) -> None:
    # Audit SECCODE-17: Django's defaults allowed 8 characters.
    with pytest.raises(InvalidPasswordError, match=reason):
        create_admin_user(
            CreateAdminUserCommand(
                actor=superadmin,
                email="ops-admin@example.test",
                password=password,
                full_name="Ops Admin",
            )
        )


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


@pytest.mark.django_db
def test_admin_creation_uses_the_one_password_policy(
    superadmin: User, settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit S4-5: no forced mix of character types, the breach check, and the same behavior
    when the breach service cannot be reached (the common list still applies; logged)."""
    import hashlib
    import urllib.error
    import urllib.request

    from backend.apps.accounts_auth import passwords

    def create(email: str, password: str) -> User:
        return create_admin_user(
            CreateAdminUserCommand(
                actor=superadmin, email=email, password=password, full_name="Ops Admin"
            )
        )

    # A long numeric password that is in no list is valid: no composition rule.
    numeric = create("numeric-admin@example.test", "730194862517")
    assert numeric.check_password("730194862517") and numeric.password_changed_at is not None

    settings.AUTH_PASSWORD_BREACH_CHECK_ENABLED = True
    breached = "violet-orchard-ladder-31"
    digest = hashlib.sha1(breached.encode()).hexdigest().upper()  # noqa: S324 - test of HIBP

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return f"{digest[5:]}:42".encode()

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: _Response())
    with pytest.raises(InvalidPasswordError, match="known data breaches"):
        create("breached-admin@example.test", breached)
    assert not User.objects.filter(email="breached-admin@example.test").exists()

    def offline(request: Any, timeout: float) -> Any:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    with pytest.raises(InvalidPasswordError, match="too common"):
        create("common-admin@example.test", "password1234")
    assert create("offline-admin@example.test", breached).check_password(breached)
    assert passwords.MIN_LENGTH == 12 and passwords.MAX_LENGTH == 128


@pytest.mark.django_db
def test_django_password_paths_use_the_same_policy(settings: Any) -> None:
    """Audit S4-5: AUTH_PASSWORD_VALIDATORS holds only the platform validator."""
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    assert [item["NAME"] for item in settings.AUTH_PASSWORD_VALIDATORS] == [
        "backend.apps.accounts_auth.passwords.PlatformPasswordValidator"
    ]
    validate_password("730194862517")
    for bad in ("Short-Pass1", "x" * 129, "password1234"):
        with pytest.raises(ValidationError):
            validate_password(bad)


@pytest.mark.django_db
def test_admin_create_api_refuses_a_password_outside_the_length_bounds(
    client: Client, superadmin: User
) -> None:
    client.force_login(superadmin)
    for password in ("Short-Pass1", "x" * 129):
        response = client.post(
            "/api/v1/auth/admin/users/",
            data={"email": "len-admin@example.test", "password": password, "full_name": "Len"},
            content_type="application/json",
        )
        assert response.status_code == 400, response.json()
    assert not User.objects.filter(email="len-admin@example.test").exists()
