from __future__ import annotations

import pytest
from django.test import Client

from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    RegistrationTermsAcceptance,
    User,
)
from backend.apps.accounts_auth.services import (
    DuplicateEmailError,
    RegisterNaturalPersonCommand,
    register_natural_person_lender,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent


@pytest.mark.django_db
def test_register_natural_person_lender_records_terms_and_events() -> None:
    user = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="Investor@Example.COM",
            full_name="Ada Investor",
            phone_number="+41790000000",
            terms_version="registration-v1",
            terms_hash="abc123",
            ip_address="127.0.0.1",
            user_agent="pytest",
            marketing_consent=True,
        )
    )

    assert user.email == "investor@example.com"
    assert user.account_type == AccountType.NATURAL_PERSON_LENDER
    assert user.status == AccountStatus.PENDING_KYC
    assert user.has_usable_password() is False
    assert user.marketing_consent is True
    assert RegistrationTermsAcceptance.objects.filter(
        user=user,
        terms_version="registration-v1",
        terms_hash="abc123",
    ).exists()
    assert AuditEvent.objects.filter(action="account.registered", target_id=str(user.id)).exists()
    assert DomainEvent.objects.filter(
        event_type="NaturalPersonLenderRegistered",
        aggregate_id=str(user.id),
    ).exists()


@pytest.mark.django_db
def test_register_natural_person_lender_rejects_duplicate_email() -> None:
    command = RegisterNaturalPersonCommand(
        email="investor@example.test",
        full_name="Ada Investor",
        phone_number="+41790000000",
        terms_version="registration-v1",
        terms_hash="abc123",
    )
    register_natural_person_lender(command)

    with pytest.raises(DuplicateEmailError):
        register_natural_person_lender(command)


@pytest.mark.django_db
def test_registration_api_creates_pending_kyc_account(client: Client) -> None:
    response = client.post(
        "/api/v1/auth/register/natural-person/",
        data={
            "email": "client@example.test",
            "full_name": "Client Investor",
            "phone_number": "+41790000001",
            "terms_version": "registration-v1",
            "terms_hash": "hash123",
            "marketing_consent": False,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "client@example.test"
    assert body["user"]["status"] == AccountStatus.PENDING_KYC
    assert User.objects.filter(email="client@example.test").exists()


@pytest.mark.django_db
def test_registration_api_returns_conflict_for_duplicate_email(client: Client) -> None:
    User.objects.create_user(
        email="client@example.test",
        full_name="Existing",
        account_type=AccountType.NATURAL_PERSON_LENDER,
    )

    response = client.post(
        "/api/v1/auth/register/natural-person/",
        data={
            "email": "client@example.test",
            "full_name": "Client Investor",
            "phone_number": "+41790000001",
            "terms_version": "registration-v1",
            "terms_hash": "hash123",
        },
        content_type="application/json",
    )

    assert response.status_code == 409
