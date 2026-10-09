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
    REGISTRATION_OUTCOME_CREATED,
    REGISTRATION_OUTCOME_EXISTING,
    REGISTRATION_OUTCOME_INCOMPLETE,
    AccountsAuthError,
    InvalidTermsAcceptanceError,
    PhoneAlreadyVerifiedError,
    PhoneVerificationRequestCommand,
    RegisterNaturalPersonCommand,
    register_natural_person_lender,
    request_phone_verification,
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


def _published_risk_disclosure(superadmin: User) -> Any:
    documents = import_module("backend.apps.documents.services")
    return documents.create_document_template_version(
        documents.CreateDocumentTemplateVersionCommand(
            actor=superadmin,
            category="risk_disclosure",
            name="Lender Risk Disclosure",
            title="P2P Lending Risk Disclosure",
            body="Risk disclosure for {{platform.name}} operated by {{operator.name}}.",
            checkbox_labels=["I acknowledge possible capital loss."],
            publish_now=True,
            legal_review_reference="risk-approved-test",
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
    ).user

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
    ).user

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
def test_registration_records_separate_server_versioned_risk_disclosure(settings: Any) -> None:
    agreement = _published_registration_document()
    superadmin = User.objects.get(email="registration-docs-superadmin@example.test")
    risk = _published_risk_disclosure(superadmin)

    user = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="risk-evidence@example.test",
            full_name="Risk Evidence Investor",
            phone_number="+41790000011",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
            registration_document_template_version_id=str(agreement.id),
            accepted_checkbox_labels=list(agreement.checkbox_labels),
            document_idempotency_key="registration-agreement-with-risk",
            risk_document_template_version_id=str(risk.id),
            accepted_risk_checkbox_labels=list(risk.checkbox_labels),
            risk_document_idempotency_key="registration-risk-evidence",
        )
    ).user

    evidence_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    evidence = evidence_model.objects.filter(user_id=user.id).order_by("category")
    assert list(evidence.values_list("category", flat=True)) == [
        "registration",
        "risk_disclosure",
    ]
    risk_evidence = evidence.get(category="risk_disclosure")
    assert risk_evidence.template_version_id == risk.id
    assert risk_evidence.context_type == "registration"
    assert risk_evidence.accepted_checkbox_labels == list(risk.checkbox_labels)


@pytest.mark.django_db
def test_registration_requires_risk_disclosure_when_published(settings: Any) -> None:
    agreement = _published_registration_document()
    superadmin = User.objects.get(email="registration-docs-superadmin@example.test")
    _published_risk_disclosure(superadmin)

    with pytest.raises(InvalidTermsAcceptanceError, match="risk disclosure"):
        register_natural_person_lender(
            RegisterNaturalPersonCommand(
                email="missing-risk@example.test",
                full_name="Missing Risk Investor",
                phone_number="+41790000012",
                terms_version=settings.REGISTRATION_TERMS_VERSION,
                terms_hash=settings.REGISTRATION_TERMS_HASH,
                registration_document_template_version_id=str(agreement.id),
                accepted_checkbox_labels=list(agreement.checkbox_labels),
                document_idempotency_key="registration-missing-risk",
            )
        )


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


def _registration_body(
    settings: Any,
    email: str,
    phone_number: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "email": email,
        "full_name": extra.pop("full_name", "Client Investor"),
        "phone_number": phone_number,
        "terms_version": settings.REGISTRATION_TERMS_VERSION,
        "terms_hash": settings.REGISTRATION_TERMS_HASH,
        "marketing_consent": extra.pop("marketing_consent", False),
        **extra,
    }


def _post_registration(client: Client, body: dict[str, Any], ip: str) -> Any:
    return client.post(
        "/api/v1/auth/register/natural-person/",
        data=body,
        content_type="application/json",
        REMOTE_ADDR=ip,
    )


@pytest.mark.django_db
def test_repeated_registration_never_changes_an_unfinished_account(settings: Any) -> None:
    # Audit A-50: an unauthenticated repeat registration rewrote name and phone.
    first = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="investor@example.test",
            full_name="Ada Investor",
            phone_number="+41790000000",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
            marketing_consent=False,
        )
    )
    assert first.outcome == REGISTRATION_OUTCOME_CREATED
    user = first.user
    challenge = PhoneVerificationChallenge.objects.create(
        user=user,
        phone_number="+41790000000",
        provider="mock",
        code_digest="digest",
        encrypted_code="secret",
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    repeated = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="Investor@Example.Test",
            full_name="Attacker Chosen",
            phone_number="+88216000000",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
            marketing_consent=True,
            ip_address="203.0.113.9",
        )
    )

    assert repeated.user.id == user.id
    assert repeated.outcome == REGISTRATION_OUTCOME_INCOMPLETE
    user.refresh_from_db()
    challenge.refresh_from_db()
    assert user.full_name == "Ada Investor"
    assert user.phone_number == "+41790000000"
    assert user.marketing_consent is False
    assert challenge.status == PhoneVerificationStatus.PENDING
    assert RegistrationTermsAcceptance.objects.filter(user=user).count() == 1
    audit = AuditEvent.objects.get(action="account.registration_repeated", target_id=str(user.id))
    assert audit.metadata["profile_changed"] is False
    assert audit.metadata["requested_ip"] == "203.0.113.9"


@pytest.mark.django_db
def test_repeated_registration_of_a_finished_account_is_not_an_error(settings: Any) -> None:
    user = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="investor@example.test",
            full_name="Ada Investor",
            phone_number="+41790000000",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
        )
    ).user
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])

    repeated = register_natural_person_lender(
        RegisterNaturalPersonCommand(
            email="investor@example.test",
            full_name="Someone Else",
            phone_number="+41790000001",
            terms_version=settings.REGISTRATION_TERMS_VERSION,
            terms_hash=settings.REGISTRATION_TERMS_HASH,
        )
    )

    assert repeated.outcome == REGISTRATION_OUTCOME_EXISTING
    user.refresh_from_db()
    assert user.full_name == "Ada Investor"
    assert user.phone_number == "+41790000000"


@pytest.mark.django_db
def test_registration_api_creates_pending_kyc_account(
    client: Client,
    settings: Any,
) -> None:
    response = _post_registration(
        client,
        _registration_body(settings, "client@example.test", "+41 79 000 00 01"),
        "198.51.100.1",
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "email_login_sent": True}
    user = User.objects.get(email="client@example.test")
    assert user.status == AccountStatus.PENDING_KYC
    assert user.phone_number == "+41790000001"
    token = EmailLoginToken.objects.get(user=user)
    outbox = OutboxMessage.objects.get(
        topic="email.magic_link_requested",
        idempotency_key=f"magic-link:{token.id}",
    )
    assert outbox.payload["purpose"] == "login"
    assert AuditEvent.objects.filter(
        action="auth.magic_link_requested",
        target_id=str(user.id),
    ).exists()


@pytest.mark.django_db
def test_registration_api_answers_new_and_existing_addresses_identically(
    client: Client,
    settings: Any,
) -> None:
    # Audit A-57 / SECURITY-02: 409 for an existing address enumerated every account.
    User.objects.create_user(
        email="active@example.test",
        full_name="Active Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
        phone_number="+41790000009",
        phone_verified_at=timezone.now(),
    )
    User.objects.create_user(
        email="unfinished@example.test",
        full_name="Unfinished Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
        phone_number="+41790000008",
    )
    User.objects.create_user(
        email="admin@example.test",
        full_name="Admin",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        password="CorrectHorse-Battery-42",
        is_staff=True,
    )

    responses = [
        _post_registration(
            client,
            _registration_body(settings, email, "+41790000001"),
            f"198.51.100.{index}",
        )
        for index, email in enumerate(
            [
                "new@example.test",
                "active@example.test",
                "unfinished@example.test",
                "ADMIN@example.test",
            ],
            start=10,
        )
    ]

    assert {response.status_code for response in responses} == {202}
    assert {response.content for response in responses} == {
        b'{"status":"accepted","email_login_sent":true}'
    }


@pytest.mark.django_db
def test_registration_api_emails_the_owner_instead_of_answering(
    client: Client,
    settings: Any,
) -> None:
    active = User.objects.create_user(
        email="active@example.test",
        full_name="Active Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
        phone_number="+41790000009",
        phone_verified_at=timezone.now(),
    )
    admin = User.objects.create_user(
        email="admin@example.test",
        full_name="Admin",
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        password="CorrectHorse-Battery-42",
        is_staff=True,
    )

    _post_registration(
        client, _registration_body(settings, "active@example.test", "+41790000001"), "198.51.100.20"
    )
    _post_registration(
        client, _registration_body(settings, "admin@example.test", "+41790000001"), "198.51.100.21"
    )

    link = OutboxMessage.objects.get(
        topic="email.magic_link_requested", payload__user_id=str(active.id)
    )
    assert link.payload["purpose"] == "existing_account"
    assert OutboxMessage.objects.filter(
        topic="email.account_exists_notice", payload__user_id=str(admin.id)
    ).count() == 1
    assert not EmailLoginToken.objects.filter(user=admin).exists()

    # The notice without a link is sent at most once an hour per account.
    _post_registration(
        client, _registration_body(settings, "admin@example.test", "+41790000001"), "198.51.100.22"
    )
    assert OutboxMessage.objects.filter(
        topic="email.account_exists_notice", payload__user_id=str(admin.id)
    ).count() == 1


@pytest.mark.django_db
def test_registration_api_does_not_overwrite_an_unfinished_account(
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

    response = _post_registration(
        client,
        _registration_body(
            settings,
            "client@example.test",
            "+88216000000",
            full_name="Attacker Chosen",
            marketing_consent=True,
        ),
        "203.0.113.50",
    )

    assert response.status_code == 202
    assert str(user.id) not in response.content.decode()
    user.refresh_from_db()
    assert user.full_name == "Existing"
    assert user.phone_number == "+41790000009"
    assert user.marketing_consent is False
    assert not RegistrationTermsAcceptance.objects.filter(user=user).exists()
    # The owner gets a sign-in link to continue; nobody else learns anything.
    assert EmailLoginToken.objects.filter(user=user).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "phone_number",
    ["12345", "+0123456789", "phone", "+41 79", "+1234567890123456"],
)
def test_registration_api_rejects_phone_numbers_that_are_not_e164(
    client: Client,
    settings: Any,
    phone_number: str,
) -> None:
    response = _post_registration(
        client,
        _registration_body(settings, "client@example.test", phone_number),
        "198.51.100.30",
    )

    assert response.status_code == 400
    assert "phone_number" in response.json()
    assert not User.objects.filter(email="client@example.test").exists()


@pytest.mark.django_db
def test_repeated_registrations_do_not_flood_the_owner_inbox(
    client: Client,
    settings: Any,
) -> None:
    body = _registration_body(settings, "client@example.test", "+41790000001")
    for index in range(5):
        response = _post_registration(client, body, f"198.51.100.{40 + index}")
        assert response.status_code == 202

    user = User.objects.get(email="client@example.test")
    # One link, still valid: later requests inside the backoff send nothing new.
    tokens = EmailLoginToken.objects.filter(user=user)
    assert tokens.count() == 1
    assert tokens.get().superseded_at is None
    assert AuditEvent.objects.filter(
        action="auth.magic_link_request_suppressed", target_id=str(user.id)
    ).count() == 4


@pytest.mark.django_db
def test_signed_in_owner_can_correct_an_unverified_phone_number(
    client: Client,
    settings: Any,
) -> None:
    from backend.apps.accounts_auth.services import MagicLinkRequestCommand, issue_magic_link

    user = User.objects.create_user(
        email="client@example.test",
        full_name="Existing",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
        phone_number="+41790000009",
    )
    issued = issue_magic_link(MagicLinkRequestCommand(email=user.email))
    assert client.post(
        "/api/v1/auth/magic-link/consume/",
        data={"token": issued.raw_token},
        content_type="application/json",
    ).status_code == 200

    response = client.post(
        "/api/v1/auth/phone/request/",
        data={"phone_number": "+41 79 111 22 33"},
        content_type="application/json",
    )

    assert response.status_code == 202
    user.refresh_from_db()
    assert user.phone_number == "+41791112233"
    challenge = PhoneVerificationChallenge.objects.get(id=response.json()["challenge_id"])
    assert challenge.phone_number == "+41791112233"
    assert AuditEvent.objects.filter(
        action="account.unverified_phone_number_changed", target_id=str(user.id)
    ).exists()

    # Once the phone is verified, the number no longer changes this way.
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])
    with pytest.raises(PhoneAlreadyVerifiedError):
        request_phone_verification(
            PhoneVerificationRequestCommand(user=user, phone_number="+41790000000")
        )
    user.refresh_from_db()
    assert user.phone_number == "+41791112233"


@pytest.mark.django_db
def test_phone_number_cannot_change_after_kyc_started(settings: Any) -> None:
    user = User.objects.create_user(
        email="client@example.test",
        full_name="Existing",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
        phone_number="+41790000009",
    )
    apps.get_model("kyc_compliance", "KycVerificationCase").objects.create(
        user=user,
        subject_reference=f"user:{user.id}",
        provider_environment="test",
        workflow_id="",
        vendor_data=f"user:{user.id}",
        status="pending",
    )

    with pytest.raises(AccountsAuthError, match="no longer be changed"):
        request_phone_verification(
            PhoneVerificationRequestCommand(user=user, phone_number="+41791112233")
        )
    user.refresh_from_db()
    assert user.phone_number == "+41790000009"


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

    assert first.status_code == 202
    assert second.status_code == 429
