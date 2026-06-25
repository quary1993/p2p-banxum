from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any

import pytest
from django.apps import apps
from django.test import Client
from django.utils import timezone

from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    EmailLoginToken,
    PhoneVerificationChallenge,
    PhoneVerificationStatus,
    RegistrationTermsAcceptance,
    User,
)
from backend.apps.accounts_auth.services import (
    DuplicateEmailError,
    InvalidTermsAcceptanceError,
    RegisterNaturalPersonCommand,
    register_natural_person_lender,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent, OutboxMessage

AGREEMENT_CHECKBOX_LABEL = (
    "I have read, understood and accept the General Terms and Conditions / "
    "User Agreement, including its integral annexes"
)


def _published_registration_document() -> Any:
    documents = import_module("backend.apps.documents.services")
    superadmin = User.objects.create_superuser(
        email="registration-docs-superadmin@example.test",
        password="AdminPass123!",
        full_name="Registration Docs Superadmin",
    )
    return documents.create_document_template_version(
        documents.CreateDocumentTemplateVersionCommand(
            actor=superadmin,
            category="registration",
            name="Garanta Lender User Agreement",
            title="General Terms and Conditions / User Agreement for Lenders",
            body="Agreement body for {{platform.name}} operated by {{operator.name}}.",
            checkbox_labels=[AGREEMENT_CHECKBOX_LABEL],
            publish_now=True,
            legal_review_reference="legal-approved-test",
        )
    )


@pytest.mark.django_db
def test_register_natural_person_lender_records_terms_and_events(settings: Any) -> None:
    user = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="Investor@Example.COM",
            full_name="Ada Investor",
            phone_number="+41790000000",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
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
        terms_version=settings.REGISTRATION_TERMS_VERSION,
        terms_hash=settings.REGISTRATION_TERMS_HASH,
    ).exists()
    assert AuditEvent.objects.filter(action="account.registered", target_id=str(user.id)).exists()
    assert DomainEvent.objects.filter(
        event_type="NaturalPersonLenderRegistered",
        aggregate_id=str(user.id),
    ).exists()


@pytest.mark.django_db
def test_register_natural_person_lender_accepts_current_registration_document(
    settings: Any,
) -> None:
    version = _published_registration_document()
    label = version.checkbox_labels[0]

    user = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="doc-investor@example.test",
            full_name="Doc Investor",
            phone_number="+41790000000",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
            registration_document_template_version_id=str(version.id),
            accepted_checkbox_labels=[label],
            document_idempotency_key="registration-doc-acceptance-test",
        )
    )

    terms = RegistrationTermsAcceptance.objects.get(user=user)
    acceptance = apps.get_model("documents", "DocumentAcceptanceEvidence").objects.get(
        user_id=user.id
    )
    assert terms.terms_version == f"document:{version.id}"
    assert terms.terms_hash == version.content_hash
    assert acceptance.template_version_id == version.id
    assert acceptance.accepted_checkbox_labels == [label]
    assert not OutboxMessage.objects.filter(
        topic="email.document_acceptance_pdf",
        payload__acceptance_id=str(acceptance.id),
    ).exists()


@pytest.mark.django_db
def test_register_requires_document_terms_when_registration_template_is_published(
    settings: Any,
) -> None:
    _published_registration_document()

    with pytest.raises(InvalidTermsAcceptanceError, match="agreement"):
        register_natural_person_lender(
            RegisterNaturalPersonCommand(
                email="missing-doc@example.test",
                full_name="Missing Doc Investor",
                phone_number="+41790000000",
                terms_version=settings.REGISTRATION_TERMS_VERSION,
                terms_hash=settings.REGISTRATION_TERMS_HASH,
            )
        )


@pytest.mark.django_db
def test_register_natural_person_lender_rejects_duplicate_email(settings: Any) -> None:
    user = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="investor@example.test",
            full_name="Ada Investor",
            phone_number="+41790000000",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
        )
    )
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])

    with pytest.raises(DuplicateEmailError):
        register_natural_person_lender(
            RegisterNaturalPersonCommand(
                email="investor@example.test",
                full_name="Ada Investor",
                phone_number="+41790000000",
                terms_version=settings.REGISTRATION_TERMS_VERSION,
                terms_hash=settings.REGISTRATION_TERMS_HASH,
            )
        )


@pytest.mark.django_db
def test_register_natural_person_lender_recovers_incomplete_registration(
    settings: Any,
) -> None:
    first_command = RegisterNaturalPersonCommand(
        email="investor@example.test",
        full_name="Ada Investor",
        phone_number="+41790000000",
        terms_version=settings.REGISTRATION_TERMS_VERSION,
        terms_hash=settings.REGISTRATION_TERMS_HASH,
        marketing_consent=False,
    )
    user = register_natural_person_lender(first_command)
    challenge = PhoneVerificationChallenge.objects.create(
        user=user,
        phone_number="+41790000000",
        provider="mock",
        code_digest="digest",
        encrypted_code="secret",
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    recovered = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="Investor@Example.Test",
            full_name="Ada Updated",
            phone_number="+41790000001",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
            marketing_consent=True,
        )
    )

    assert recovered.id == user.id
    recovered.refresh_from_db()
    challenge.refresh_from_db()
    assert recovered.full_name == "Ada Updated"
    assert recovered.phone_number == "+41790000001"
    assert recovered.marketing_consent is True
    assert recovered.status == AccountStatus.PENDING_KYC
    assert recovered.phone_verified_at is None
    assert challenge.status == PhoneVerificationStatus.SUPERSEDED
    assert RegistrationTermsAcceptance.objects.filter(user=recovered).count() == 2
    assert AuditEvent.objects.filter(
        action="account.registration_recovered",
        target_id=str(recovered.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="NaturalPersonLenderRegistrationRecovered",
        aggregate_id=str(recovered.id),
    ).exists()


@pytest.mark.django_db
def test_register_natural_person_lender_rejects_duplicate_after_kyc_started(
    settings: Any,
) -> None:
    user = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="investor@example.test",
            full_name="Ada Investor",
            phone_number="+41790000000",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
        )
    )
    case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    case_model.objects.create(
        user=user,
        subject_reference=f"user:{user.id}",
        provider_environment="test",
        workflow_id="",
        vendor_data=f"user:{user.id}",
        status="pending",
    )

    with pytest.raises(DuplicateEmailError):
        register_natural_person_lender(
            RegisterNaturalPersonCommand(
                email="investor@example.test",
                full_name="Ada Updated",
                phone_number="+41790000001",
                terms_version=settings.REGISTRATION_TERMS_VERSION,
                terms_hash=settings.REGISTRATION_TERMS_HASH,
            )
        )


@pytest.mark.django_db
def test_registration_api_creates_pending_kyc_account(
    client: Client,
    settings: Any,
) -> None:
    response = client.post(
        "/api/v1/auth/register/natural-person/",
        data={
            "email": "client@example.test",
            "full_name": "Client Investor",
            "phone_number": "+41790000001",
            "terms_version": settings.REGISTRATION_TERMS_VERSION,
            "terms_hash": settings.REGISTRATION_TERMS_HASH,
            "marketing_consent": False,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "client@example.test"
    assert body["user"]["status"] == AccountStatus.PENDING_KYC
    assert body["email_login_sent"] is True
    user = User.objects.get(email="client@example.test")
    token = EmailLoginToken.objects.get(user=user)
    assert OutboxMessage.objects.filter(
        topic="email.magic_link_requested",
        idempotency_key=f"magic-link:{token.id}",
    ).exists()
    assert AuditEvent.objects.filter(
        action="auth.magic_link_requested",
        target_id=str(user.id),
    ).exists()


@pytest.mark.django_db
def test_registration_api_returns_conflict_for_duplicate_email(
    client: Client,
    settings: Any,
) -> None:
    User.objects.create_user(
        email="client@example.test",
        full_name="Existing",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
        phone_number="+41790000009",
        phone_verified_at=timezone.now(),
    )

    response = client.post(
        "/api/v1/auth/register/natural-person/",
        data={
            "email": "client@example.test",
            "full_name": "Client Investor",
            "phone_number": "+41790000001",
            "terms_version": settings.REGISTRATION_TERMS_VERSION,
            "terms_hash": settings.REGISTRATION_TERMS_HASH,
        },
        content_type="application/json",
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_registration_api_recovers_incomplete_registration(
    client: Client,
    settings: Any,
) -> None:
    user = User.objects.create_user(
        email="client@example.test",
        full_name="Existing",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
        phone_number="+41790000009",
    )

    response = client.post(
        "/api/v1/auth/register/natural-person/",
        data={
            "email": "client@example.test",
            "full_name": "Client Investor",
            "phone_number": "+41790000001",
            "terms_version": settings.REGISTRATION_TERMS_VERSION,
            "terms_hash": settings.REGISTRATION_TERMS_HASH,
            "marketing_consent": True,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    user.refresh_from_db()
    body = response.json()
    assert body["user"]["id"] == str(user.id)
    assert body["user"]["full_name"] == "Client Investor"
    assert user.phone_number == "+41790000001"
    assert user.marketing_consent is True
    assert body["email_login_sent"] is True
    assert EmailLoginToken.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_registration_rejects_client_forged_terms_hash(settings: Any) -> None:
    with pytest.raises(InvalidTermsAcceptanceError):
        register_natural_person_lender(
            RegisterNaturalPersonCommand(
                email="investor@example.test",
                full_name="Ada Investor",
                phone_number="+41790000000",
                terms_version=settings.REGISTRATION_TERMS_VERSION,
                terms_hash="client-forged-hash",
            )
        )


@pytest.mark.django_db
def test_registration_api_throttles_repeated_ip_requests(
    client: Client,
    settings: Any,
) -> None:
    first = client.post(
        "/api/v1/auth/register/natural-person/",
        data={
            "email": "client-1@example.test",
            "full_name": "Client Investor",
            "phone_number": "+41790000001",
            "terms_version": settings.REGISTRATION_TERMS_VERSION,
            "terms_hash": settings.REGISTRATION_TERMS_HASH,
        },
        content_type="application/json",
    )
    second = client.post(
        "/api/v1/auth/register/natural-person/",
        data={
            "email": "client-2@example.test",
            "full_name": "Client Investor",
            "phone_number": "+41790000002",
            "terms_version": settings.REGISTRATION_TERMS_VERSION,
            "terms_hash": settings.REGISTRATION_TERMS_HASH,
        },
        content_type="application/json",
    )

    assert first.status_code == 201
    assert second.status_code == 429
