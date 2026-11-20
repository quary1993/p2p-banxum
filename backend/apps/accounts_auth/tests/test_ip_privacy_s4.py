"""IP of Webby-Soft SRL. Audit S4-1 (Q06): authentication records never store an IP address."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest
from django.apps import apps
from django.db import connection, models
from django.test import Client

from backend.apps.accounts_auth.models import (
    EmailLoginToken,
    LoginChallenge,
    PasswordResetToken,
    PhoneVerificationChallenge,
    RegistrationTermsAcceptance,
    SensitiveAction,
    SensitiveActionCode,
    SignInEvent,
    User,
)
from backend.apps.accounts_auth.tests.signin_helpers import (
    give_password,
    give_sms_factor,
    sign_in,
)
from backend.apps.platform_core.services.ip_privacy import (
    ACCOUNT_IP_PURPOSE,
    PUBLIC_IP_PURPOSE,
    keyed_ip_hash,
)

ADDRESS = "203.0.113.77"
PASSWORD = "quiet harbour lantern 47"


def test_the_hash_is_keyed_stable_and_separate_per_purpose(settings: Any) -> None:
    first = keyed_ip_hash(ADDRESS)
    assert len(first) == 64 and ADDRESS not in first
    assert (
        first == keyed_ip_hash(f" {ADDRESS} ") == keyed_ip_hash(ADDRESS, purpose=ACCOUNT_IP_PURPOSE)
    )
    assert first != keyed_ip_hash(ADDRESS, purpose=PUBLIC_IP_PURPOSE)
    assert keyed_ip_hash("") == keyed_ip_hash(None) == ""
    # The sign-in history and the public forms use the same service.
    sessions: Any = import_module("backend.apps.accounts_auth.security_sessions")
    forms: Any = import_module("backend.apps.communications.public_forms")
    assert sessions.ip_hash(ADDRESS) == first
    assert forms.public_ip_hash(ADDRESS) == keyed_ip_hash(ADDRESS, purpose=PUBLIC_IP_PURPOSE)
    settings.SECRET_KEY = "another-key"
    assert keyed_ip_hash(ADDRESS) != first


def test_no_authentication_model_has_an_ip_address_column() -> None:
    """Every model of accounts_auth: no IP address field type, and every column whose name
    speaks of an IP is a hash column."""
    for model in apps.get_app_config("accounts_auth").get_models():
        for field in model._meta.get_fields():
            if not isinstance(field, models.Field):
                continue
            assert not isinstance(field, models.GenericIPAddressField), (model, field.name)
            if "ip" in field.name.split("_"):
                assert field.name.endswith("ip_hash"), (model.__name__, field.name)


@pytest.mark.django_db
def test_a_full_sign_in_and_code_flow_stores_no_raw_address(client: Client) -> None:
    """Registration terms, phone codes, sign-in challenges, operation codes, password reset and
    the sign-in history: every row written with a client address holds only the keyed hash."""
    services: Any = import_module("backend.apps.accounts_auth.services")
    two_factor: Any = import_module("backend.apps.accounts_auth.two_factor")
    user = User.objects.create_user(
        email="ip-privacy@example.test",
        full_name="Ip Privacy",
        account_type="natural_person_lender",
        status="active",
    )
    give_password(user, PASSWORD)
    give_sms_factor(user)
    RegistrationTermsAcceptance.objects.create(
        user=user, terms_version="v1", terms_hash="h", ip_hash=keyed_ip_hash(ADDRESS)
    )
    # A full sign-in through the API from the address: challenge, SMS code, sign-in history.
    signed_in = sign_in(client, user, password=PASSWORD, REMOTE_ADDR=ADDRESS)
    assert signed_in.status_code == 200
    services.issue_sensitive_action_code(
        services.SensitiveActionCodeCommand(
            user=user,
            action=SensitiveAction.WITHDRAWAL,
            operation={"amount_minor": 100, "currency": "CHF", "iban": "CH5604835012345678009"},
            ip_address=ADDRESS,
        )
    )
    two_factor.request_password_reset(email=user.email, ip_address=ADDRESS)
    expected = keyed_ip_hash(ADDRESS)
    assert (
        LoginChallenge.objects.filter(user=user).latest("created_at").requested_ip_hash == expected
    )
    assert (
        PhoneVerificationChallenge.objects.filter(user=user).latest("created_at").requested_ip_hash
        == expected
    )
    assert SensitiveActionCode.objects.get(user=user).requested_ip_hash == expected
    assert PasswordResetToken.objects.get(user=user).requested_ip_hash == expected
    assert EmailLoginToken._meta.get_field("requested_ip_hash").max_length == 64
    assert SignInEvent.objects.filter(ip_hash=expected).exists()

    # No table of the app holds the address in any column.
    with connection.cursor() as cursor:
        for model in apps.get_app_config("accounts_auth").get_models():
            table = model._meta.db_table
            cursor.execute(f'SELECT * FROM "{table}"')  # noqa: S608 - table names from the models
            for row in cursor.fetchall():
                assert ADDRESS not in " ".join(str(value) for value in row), table


@pytest.mark.django_db
def test_migration_hashes_the_stored_addresses() -> None:
    """The data step of migration 0016 uses the same keyed hash as the service."""
    migration: Any = import_module("backend.apps.accounts_auth.migrations.0016_ip_hashes_only")
    assert migration._keyed_hash(ADDRESS) == keyed_ip_hash(ADDRESS)
    assert {raw for _model, raw, _hashed in migration.COLUMNS} == {
        "ip_address",
        "requested_ip",
        "consumed_ip",
        "confirmed_ip",
    }
    assert len(migration.COLUMNS) == 9
