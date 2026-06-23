from __future__ import annotations

import base64
import datetime as dt
import html
from typing import Any, cast
from zipfile import ZipFile

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.documents.legal_import import (
    extract_lender_user_agreement_template,
    extract_project_investment_confirmation_template,
)
from backend.apps.documents.models import (
    DocumentAcceptanceEvidence,
    DocumentCategory,
    DocumentEvent,
    DocumentRenderedArtifact,
    DocumentTemplateVersion,
    DocumentTemplateVersionStatus,
)
from backend.apps.documents.services import (
    AcceptDocumentTermsCommand,
    CreateDocumentTemplateVersionCommand,
    DocumentAuthorizationError,
    DocumentValidationError,
    PublishDocumentTemplateVersionCommand,
    RenderDocumentAcceptanceArtifactCommand,
    accept_document_terms,
    create_document_template_version,
    get_current_document_template,
    publish_document_template_version,
    render_document_acceptance_artifact,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation

AGREEMENT_CHECKBOX_LABEL = (
    "I have read, understood and accept the General Terms and Conditions / "
    "User Agreement, including its integral annexes"
)
INVESTMENT_CONFIRMATION_CHECKBOX_LABEL = (
    "I confirm this investment and accept the Project Investment Confirmation "
    "and Claim Assignment Agreement."
)


@pytest.fixture
def superadmin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_superuser(
            email="docs-superadmin@example.test",
            password="AdminPass123!",
            full_name="Docs Superadmin",
        ),
    )


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="docs-admin@example.test",
            password="AdminPass123!",
            full_name="Docs Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="docs-investor@example.test",
            full_name="Docs Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


def _approve_financial_access(investor: Model) -> None:
    now = timezone.now()
    cast(Any, investor).phone_verified_at = now
    investor.save(update_fields=["phone_verified_at"])
    kyc_case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    kyc_case_model.objects.update_or_create(
        user_id=investor.pk,
        defaults={
            "subject_reference": f"user:{investor.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{investor.pk}",
            "status": "approved",
            "decision_at": now,
        },
    )


def _template_command(
    superadmin_user: Model,
    *,
    category: str = DocumentCategory.PRIMARY_MARKET_INVESTMENT,
    title: str = "Primary Investment Terms",
    body: str = "Hello {{user.full_name}}, invest in {{loan.title}} on {{platform.name}}.",
    publish_now: bool = True,
) -> CreateDocumentTemplateVersionCommand:
    return CreateDocumentTemplateVersionCommand(
        actor=superadmin_user,
        category=category,
        name="Primary investment template",
        title=title,
        body=body,
        checkbox_labels=[
            "I accept the investment terms.",
            "I understand that P2P lending involves risk.",
        ],
        publish_now=publish_now,
        legal_review_reference="legal-review-placeholder",
    )


def _write_minimal_docx(path: Any, blocks: list[str]) -> None:
    paragraphs = "\n".join(
        (
            '<w:p><w:r><w:t xml:space="preserve">'
            f"{html.escape(block)}"
            "</w:t></w:r></w:p>"
        )
        for block in blocks
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body>"
        "</w:document>"
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def _accepted_primary_document(
    *,
    superadmin_user: Model,
    investor: Model,
    idempotency_key: str = "accept-primary-render",
    body: str = (
        "Lender {{user.full_name}} invests in {{loan.title}} through {{platform.name}}. "
        "Operator: {{operator.name}}."
    ),
    loan_title: str = "Zurich Bakery Expansion",
) -> DocumentAcceptanceEvidence:
    _approve_financial_access(investor)
    version = create_document_template_version(
        _template_command(
            superadmin_user,
            body=body,
        )
    )
    return accept_document_terms(
        AcceptDocumentTermsCommand(
            actor=investor,
            category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            expected_template_version_id=str(version.id),
            accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
            context_type="primary_order",
            context_id="order-render",
            data_snapshot={"loan": {"title": loan_title}},
            idempotency_key=idempotency_key,
        )
    )


def _create_primary_order_context(*, investor: Model, admin_user: Model) -> Model:
    currency_model = apps.get_model("platform_core", "Currency")
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    loan_model = apps.get_model("loans", "Loan")
    installment_model = apps.get_model("loans", "LoanInstallment")
    order_model = apps.get_model("marketplace_primary", "PrimaryInvestmentOrder")
    currency_model.objects.get_or_create(
        code="CHF",
        defaults={"name": "Swiss Franc", "minor_units": 2, "is_enabled": True},
    )
    borrower = borrower_model.objects.create(
        legal_name="Server Owned Borrower AG",
        year_founded=2018,
        entity_type="swiss_company",
        kyb_status="approved",
        country="CH",
        created_by_admin_id=admin_user.pk,
    )
    loan = loan_model.objects.create(
        borrower=borrower,
        status="published",
        title="Server Owned Project",
        investor_summary="Server owned summary.",
        purpose="working_capital",
        purpose_description="Working capital.",
        principal_minor=100_000_00,
        currency_id="CHF",
        interest_rate_bps=950,
        term_months=12,
        repayment_type="bullet_periodic_interest",
        funding_deadline=dt.date(2026, 7, 20),
        first_payment_date=dt.date(2026, 8, 20),
        collateral_type="real_estate",
        collateral_value_minor=150_000_00,
        collateral_description="First-ranking real estate pledge.",
        risk_rating="A",
        created_by_admin_id=admin_user.pk,
    )
    installment_model.objects.create(
        loan=loan,
        schedule_version=1,
        installment_number=1,
        due_date=dt.date(2027, 6, 20),
        principal_minor=100_000_00,
        interest_minor=9_500_00,
        total_minor=109_500_00,
    )
    return cast(
        Model,
        order_model.objects.create(
            loan=loan,
            investor_user_id=investor.pk,
            requested_amount_minor=2_500_00,
            allocated_amount_minor=0,
            currency_id="CHF",
            created_by_user_id=investor.pk,
            idempotency_key="docs-primary-order-context",
        ),
    )


@pytest.mark.django_db
def test_lender_user_agreement_docx_import_extracts_body_and_checkbox(tmp_path: Any) -> None:
    docx_path = tmp_path / "agreement.docx"
    _write_minimal_docx(
        docx_path,
        [
            "GARANTA FINANZGRUPPE AG",
            "General Terms and Conditions / User Agreement for Lenders",
            "Version: 0.4\nEffective date: [to be completed]",
            "Document Structure and One-Click Acceptance",
            "Recommended clickwrap acceptance wording",
            "The platform should display the following text.",
            f"“{AGREEMENT_CHECKBOX_LABEL}”",
            "Acceptance evidence to be retained by the platform",
            "For each acceptance, store a non-editable PDF/snapshot.",
            "Main Agreement",
            "1. Parties and Scope",
            "Fee item [to confirm]",
        ],
    )

    imported = extract_lender_user_agreement_template(
        docx_path=docx_path,
        effective_date="2026-07-01",
    )

    assert "Main Agreement" in imported.body
    assert "Effective date: 2026-07-01" in imported.body
    assert "Recommended clickwrap acceptance wording" not in imported.body
    assert imported.checkbox_label.startswith("I have read, understood")
    assert imported.unresolved_placeholders == ("[to confirm]",)


@pytest.mark.django_db
def test_project_investment_confirmation_import_maps_dynamic_fields(tmp_path: Any) -> None:
    docx_path = tmp_path / "investment-confirmation.docx"
    _write_minimal_docx(
        docx_path,
        [
            "GARANTA FINANZGRUPPE AG",
            "Project Investment Confirmation and Claim Assignment Agreement",
            "Version: 0.4 | Effective date: [to be completed] | Draft for legal review",
            "Recommended confirmation text",
            f"Table:\n{INVESTMENT_CONFIRMATION_CHECKBOX_LABEL}",
            "Part I - Basic Terms and Conditions",
            (
                "Table:\n"
                "No. | Field | Dynamic value\n"
                "1 | Agreement No. | [AGREEMENT_NO]\n"
                "2 | Project ID / Project name | [PROJECT_ID] / [PROJECT_NAME]\n"
                "3 | Borrower | [BORROWER_NAME] / [BORROWER_ID]\n"
                "4 | Investment / Claim Amount | [AMOUNT] [CURRENCY]\n"
                "5 | Interest rate | [INTEREST_RATE]% p.a.\n"
                "6 | Collateral / security | "
                "[none / as described in the Project Summary / as per Collateral Documents]"
            ),
            "Part II - General Assignment Terms and Conditions",
            "1. Relationship with the User Agreement and Project documents",
            "The transaction is accepted electronically.",
        ],
    )

    imported = extract_project_investment_confirmation_template(
        docx_path=docx_path,
        effective_date="2026-07-01",
    )

    assert "Effective date: 2026-07-01" in imported.body
    assert "Recommended confirmation text" not in imported.body
    assert "{{order.agreement_no}}" in imported.body
    assert "{{loan.title}}" in imported.body
    assert "{{borrower.legal_name}}" in imported.body
    assert "{{loan.collateral_security}}" in imported.body
    assert imported.checkbox_label == INVESTMENT_CONFIRMATION_CHECKBOX_LABEL
    assert imported.unresolved_placeholders == ()


@pytest.mark.django_db
def test_import_lender_user_agreement_command_publishes_registration_template(
    superadmin_user: Model,
    tmp_path: Any,
) -> None:
    docx_path = tmp_path / "agreement.docx"
    _write_minimal_docx(
        docx_path,
        [
            "GARANTA FINANZGRUPPE AG",
            "General Terms and Conditions / User Agreement for Lenders",
            "Version: 0.4\nEffective date: [to be completed]",
            "Document Structure and One-Click Acceptance",
            "Recommended clickwrap acceptance wording",
            "The platform should display the following text.",
            f"“{AGREEMENT_CHECKBOX_LABEL}”",
            "Acceptance evidence to be retained by the platform",
            "For each acceptance, store a non-editable PDF/snapshot.",
            "Main Agreement",
            "1. Parties and Scope",
            "Final legal text.",
        ],
    )

    call_command(
        "import_lender_user_agreement",
        str(docx_path),
        "--effective-date",
        "2026-07-01",
        "--superadmin-email",
        cast(Any, superadmin_user).email,
        "--legal-review-reference",
        "advisor-approved-test",
        "--publish",
    )

    current = get_current_document_template(category=DocumentCategory.REGISTRATION)
    assert current.status == DocumentTemplateVersionStatus.PUBLISHED
    assert current.template.template_key == "default"
    assert current.legal_review_reference == "advisor-approved-test"
    assert current.metadata["source_docx_sha256"]
    assert current.metadata["effective_date"] == "2026-07-01"
    assert "Recommended clickwrap" in current.metadata["skipped_instruction_text"]
    assert "Final legal text." in current.body


@pytest.mark.django_db
def test_import_project_investment_confirmation_command_publishes_primary_template(
    superadmin_user: Model,
    tmp_path: Any,
) -> None:
    docx_path = tmp_path / "investment-confirmation.docx"
    _write_minimal_docx(
        docx_path,
        [
            "GARANTA FINANZGRUPPE AG",
            "Project Investment Confirmation and Claim Assignment Agreement",
            "Version: 0.4 | Effective date: [to be completed] | Draft for legal review",
            "Recommended confirmation text",
            f"Table:\n{INVESTMENT_CONFIRMATION_CHECKBOX_LABEL}",
            "Part I - Basic Terms and Conditions",
            "Table:\nNo. | Field | Dynamic value\n1 | Agreement No. | [AGREEMENT_NO]",
            "Part II - General Assignment Terms and Conditions",
            "1. Relationship with the User Agreement and Project documents",
            "Final investment confirmation text.",
        ],
    )

    call_command(
        "import_project_investment_confirmation",
        str(docx_path),
        "--effective-date",
        "2026-07-01",
        "--superadmin-email",
        cast(Any, superadmin_user).email,
        "--legal-review-reference",
        "advisor-approved-test",
        "--publish",
    )

    current = get_current_document_template(category=DocumentCategory.PRIMARY_MARKET_INVESTMENT)
    assert current.status == DocumentTemplateVersionStatus.PUBLISHED
    assert current.template.template_key == "default"
    assert current.legal_review_reference == "advisor-approved-test"
    assert current.checkbox_labels == [INVESTMENT_CONFIRMATION_CHECKBOX_LABEL]
    assert current.metadata["generation_context"] == "one_acceptance_per_primary_investment_order"
    assert "{{order.agreement_no}}" in current.body


@pytest.mark.django_db
def test_superadmin_creates_published_template_and_current_lookup(superadmin_user: Model) -> None:
    version = create_document_template_version(_template_command(superadmin_user))
    current = get_current_document_template(category=DocumentCategory.PRIMARY_MARKET_INVESTMENT)

    assert version.status == DocumentTemplateVersionStatus.PUBLISHED
    assert version.published_at is not None
    assert current.id == version.id
    assert version.template.current_published_version_id == version.id
    assert len(version.content_hash) == 64
    assert "user" in version.variable_schema
    assert AuditEvent.objects.filter(
        action="document.template_version_published",
        target_id=str(version.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="DocumentTemplateVersionPublished",
        aggregate_id=str(version.id),
    ).exists()


@pytest.mark.django_db
def test_admin_cannot_manage_document_templates(admin_user: Model) -> None:
    with pytest.raises(DocumentAuthorizationError):
        create_document_template_version(_template_command(admin_user))


@pytest.mark.django_db
def test_template_validation_rejects_unknown_variable_scope(superadmin_user: Model) -> None:
    with pytest.raises(DocumentValidationError, match="unsupported variable"):
        create_document_template_version(
            _template_command(
                superadmin_user,
                body="This uses {{unknown.field}}.",
            )
        )


@pytest.mark.django_db
def test_publish_draft_creates_immutable_published_copy(superadmin_user: Model) -> None:
    draft = create_document_template_version(
        _template_command(superadmin_user, publish_now=False)
    )
    published = publish_document_template_version(
        PublishDocumentTemplateVersionCommand(
            actor=superadmin_user,
            template_version_id=str(draft.id),
            legal_review_reference="approved-offline",
        )
    )

    assert draft.status == DocumentTemplateVersionStatus.DRAFT
    assert published.id != draft.id
    assert published.status == DocumentTemplateVersionStatus.PUBLISHED
    assert published.source_version_id == draft.id
    assert published.version_number == 2
    assert published.content_hash == draft.content_hash
    assert published.template.current_published_version_id == published.id


@pytest.mark.django_db
def test_publish_draft_twice_returns_existing_current_clone(superadmin_user: Model) -> None:
    draft = create_document_template_version(
        _template_command(superadmin_user, publish_now=False)
    )
    first_publish = publish_document_template_version(
        PublishDocumentTemplateVersionCommand(
            actor=superadmin_user,
            template_version_id=str(draft.id),
        )
    )
    second_publish = publish_document_template_version(
        PublishDocumentTemplateVersionCommand(
            actor=superadmin_user,
            template_version_id=str(draft.id),
        )
    )

    assert second_publish.id == first_publish.id
    assert (
        DocumentTemplateVersion.objects.filter(
            template=draft.template,
            source_version_id=draft.id,
            status=DocumentTemplateVersionStatus.PUBLISHED,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_acceptance_uses_server_owned_current_hash(
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    version = create_document_template_version(_template_command(superadmin_user))

    acceptance = accept_document_terms(
        AcceptDocumentTermsCommand(
            actor=investor,
            category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            expected_template_version_id=str(version.id),
            accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
            context_type="primary_order",
            context_id="order-1",
            data_snapshot={"loan": {"id": "loan-1", "amount_minor": 100_000}},
            idempotency_key="accept-primary-order-1",
        )
    )
    idempotent = accept_document_terms(
        AcceptDocumentTermsCommand(
            actor=investor,
            category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            expected_template_version_id=str(version.id),
            accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
            context_type="primary_order",
            context_id="order-1",
            data_snapshot={"loan": {"id": "loan-1", "amount_minor": 100_000}},
            idempotency_key="accept-primary-order-1",
        )
    )

    assert acceptance.template_hash == version.content_hash
    assert acceptance.template_version_number == version.version_number
    assert acceptance.accepted_checkbox_labels == version.checkbox_labels
    assert idempotent.id == acceptance.id
    assert DocumentAcceptanceEvidence.objects.count() == 1
    assert DocumentEvent.objects.filter(event_type="accepted").count() == 1
    assert DomainEvent.objects.filter(
        event_type="DocumentAccepted",
        aggregate_id=str(acceptance.id),
    ).exists()


@pytest.mark.django_db
def test_acceptance_rejects_stale_template_version(
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    old_version = create_document_template_version(_template_command(superadmin_user))
    new_version = create_document_template_version(
        _template_command(
            superadmin_user,
            title="Primary Investment Terms Updated",
            body="Updated {{user.full_name}} {{loan.title}}.",
        )
    )

    with pytest.raises(DocumentValidationError, match="not current"):
        accept_document_terms(
            AcceptDocumentTermsCommand(
                actor=investor,
                category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
                expected_template_version_id=str(old_version.id),
                accepted_checkbox_labels=list(cast(list[str], new_version.checkbox_labels)),
                context_type="primary_order",
                context_id="order-2",
                idempotency_key="accept-stale",
            )
        )


@pytest.mark.django_db
def test_acceptance_rejects_missing_required_checkbox(
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    version = create_document_template_version(_template_command(superadmin_user))
    labels = list(cast(list[str], version.checkbox_labels))

    with pytest.raises(DocumentValidationError, match="All required checkbox"):
        accept_document_terms(
            AcceptDocumentTermsCommand(
                actor=investor,
                category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
                expected_template_version_id=str(version.id),
                accepted_checkbox_labels=labels[:1],
                context_type="primary_order",
                context_id="order-missing-label",
                idempotency_key="accept-missing-label",
            )
        )


@pytest.mark.django_db
def test_acceptance_idempotency_mismatch_is_rejected(
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    version = create_document_template_version(_template_command(superadmin_user))
    labels = list(cast(list[str], version.checkbox_labels))
    accept_document_terms(
        AcceptDocumentTermsCommand(
            actor=investor,
            category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            accepted_checkbox_labels=labels,
            context_type="primary_order",
            context_id="order-3",
            idempotency_key="accept-mismatch",
        )
    )

    with pytest.raises(DocumentValidationError, match="different acceptance"):
        accept_document_terms(
            AcceptDocumentTermsCommand(
                actor=investor,
                category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
                accepted_checkbox_labels=labels,
                context_type="primary_order",
                context_id="different-order",
                idempotency_key="accept-mismatch",
            )
        )


@pytest.mark.django_db
def test_acceptance_rejects_oversized_payload(
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    version = create_document_template_version(_template_command(superadmin_user))

    with pytest.raises(DocumentValidationError, match="Data snapshot"):
        accept_document_terms(
            AcceptDocumentTermsCommand(
                actor=investor,
                category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
                accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
                context_type="primary_order",
                context_id="order-large-snapshot",
                data_snapshot={"oversized": "x" * 70_000},
                idempotency_key="accept-large-snapshot",
            )
        )


@pytest.mark.django_db
def test_primary_acceptance_requires_financial_access(
    superadmin_user: Model,
    investor: Model,
) -> None:
    version = create_document_template_version(_template_command(superadmin_user))

    with pytest.raises(DocumentAuthorizationError):
        accept_document_terms(
            AcceptDocumentTermsCommand(
                actor=investor,
                category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
                accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
                context_type="primary_order",
                context_id="order-4",
                idempotency_key="accept-no-kyc",
            )
        )


@pytest.mark.django_db
def test_registration_acceptance_requires_lender_actor(
    superadmin_user: Model,
    admin_user: Model,
    investor: Model,
) -> None:
    version = create_document_template_version(
        _template_command(
            superadmin_user,
            category=DocumentCategory.REGISTRATION,
            title="Registration Terms",
            body="Hello {{user.full_name}}, welcome to {{platform.name}}.",
        )
    )

    with pytest.raises(DocumentAuthorizationError):
        accept_document_terms(
            AcceptDocumentTermsCommand(
                actor=admin_user,
                category=DocumentCategory.REGISTRATION,
                accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
                context_type="registration",
                context_id=str(admin_user.pk),
                idempotency_key="registration-admin-denied",
            )
        )

    acceptance = accept_document_terms(
        AcceptDocumentTermsCommand(
            actor=investor,
            category=DocumentCategory.REGISTRATION,
            accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
            context_type="registration",
            context_id=str(investor.pk),
            idempotency_key="registration-investor-ok",
        )
    )

    assert acceptance.category == DocumentCategory.REGISTRATION


@pytest.mark.django_db
def test_document_template_and_acceptance_api(
    client: Client,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    client.force_login(cast(Any, superadmin_user))
    create_response = client.post(
        "/api/v1/documents/admin/templates/versions/",
        data={
            "category": DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            "name": "Primary investment template",
            "title": "Primary Investment Terms",
            "body": "Hello {{user.full_name}}, invest in {{loan.title}}.",
            "checkbox_labels": [
                "I accept the investment terms.",
                "I understand that P2P lending involves risk.",
            ],
            "publish_now": True,
            "legal_review_reference": "approved-offline",
        },
        content_type="application/json",
    )
    client.logout()
    current_response = client.get(
        "/api/v1/documents/templates/current/",
        data={"category": DocumentCategory.PRIMARY_MARKET_INVESTMENT},
    )
    current_payload = current_response.json()
    client.force_login(cast(Any, investor))
    acceptance_response = client.post(
        "/api/v1/documents/acceptances/",
        data={
            "category": DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            "expected_template_version_id": current_payload["id"],
            "accepted_checkbox_labels": current_payload["checkbox_labels"],
            "context_type": "primary_order",
            "context_id": "api-order-1",
            "data_snapshot": {"loan": {"id": "loan-api"}},
            "idempotency_key": "api-accept-primary-order-1",
        },
        content_type="application/json",
    )

    assert create_response.status_code == 201
    assert current_response.status_code == 200
    assert current_payload["content_hash"] == create_response.json()["content_hash"]
    assert current_payload["category"] == DocumentCategory.PRIMARY_MARKET_INVESTMENT
    assert current_payload["template_key"] == "default"
    assert current_payload["language"] == "en"
    assert "created_by_superadmin_id" not in current_payload
    assert "legal_review_reference" not in current_payload
    assert "metadata" not in current_payload
    assert acceptance_response.status_code == 201
    assert acceptance_response.json()["template_hash"] == current_payload["content_hash"]


@pytest.mark.django_db
def test_admin_template_version_list_searches_server_side(
    client: Client,
    superadmin_user: Model,
) -> None:
    create_document_template_version(
        _template_command(
            superadmin_user,
            title="Primary Investment Terms",
            publish_now=False,
        )
    )
    create_document_template_version(
        _template_command(
            superadmin_user,
            title="Secondary Buyer Terms",
            publish_now=False,
        )
    )
    client.force_login(cast(Any, superadmin_user))

    response = client.get(
        "/api/v1/documents/admin/templates/versions/",
        data={
            "category": DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            "q": "secondary",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [row["title"] for row in payload] == ["Secondary Buyer Terms"]


@pytest.mark.django_db
def test_acceptance_snapshot_includes_server_owned_brand_operator_and_user(
    superadmin_user: Model,
    investor: Model,
) -> None:
    acceptance = _accepted_primary_document(
        superadmin_user=superadmin_user,
        investor=investor,
        idempotency_key="accept-server-owned-snapshot",
    )

    assert acceptance.data_snapshot["platform"]["name"] == "BANXUM"
    assert acceptance.data_snapshot["operator"]["name"] == "Garanta Finanzgruppe AG"
    assert acceptance.data_snapshot["user"]["id"] == str(investor.pk)
    assert acceptance.data_snapshot["user"]["email"] == "docs-investor@example.test"
    assert acceptance.data_snapshot["user"]["full_name"] == "Docs Investor"


@pytest.mark.django_db
def test_primary_investment_acceptance_snapshot_uses_server_owned_order_context(
    superadmin_user: Model,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    order = _create_primary_order_context(investor=investor, admin_user=admin_user)
    version = create_document_template_version(
        _template_command(
            superadmin_user,
            title="Project Investment Confirmation",
            body=(
                "Agreement {{order.agreement_no}}\n\n"
                "Table:\n"
                "Field | Value\n"
                "Project | {{loan.id}} / {{loan.title}}\n"
                "Borrower | {{borrower.legal_name}} / {{borrower.id}}\n"
                "Amount | {{order.amount}} {{order.currency}}\n"
                "Lender | {{lender.id}}\n"
                "Holding | {{holding.id}}\n"
                "Assignor | {{assignment.assignor_name}}"
            ),
        )
    )

    acceptance = accept_document_terms(
        AcceptDocumentTermsCommand(
            actor=investor,
            category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            expected_template_version_id=str(version.id),
            accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
            context_type="primary_order",
            context_id=str(cast(Any, order).id),
            data_snapshot={
                "loan": {"title": "Forged Loan"},
                "borrower": {"legal_name": "Forged Borrower"},
                "order": {"amount": "999'999.00", "currency": "EUR"},
            },
            idempotency_key="accept-server-owned-primary-order",
        )
    )

    assert acceptance.data_snapshot["loan"]["title"] == "Server Owned Project"
    assert acceptance.data_snapshot["borrower"]["legal_name"] == "Server Owned Borrower AG"
    assert acceptance.data_snapshot["order"]["amount"] == "2'500.00"
    assert acceptance.data_snapshot["order"]["currency"] == "CHF"
    assert acceptance.data_snapshot["holding"]["id"] == "Assigned at funding close"

    artifact = render_document_acceptance_artifact(
        RenderDocumentAcceptanceArtifactCommand(
            actor=investor,
            acceptance_id=str(acceptance.id),
            output_format="pdf",
        )
    )
    pdf_bytes = base64.b64decode(artifact.content.encode("ascii"))
    assert b"Server Owned Project" in pdf_bytes
    assert b"Forged Loan" not in pdf_bytes


@pytest.mark.django_db
def test_render_acceptance_pdf_is_template_driven_and_records_artifact(
    superadmin_user: Model,
    investor: Model,
) -> None:
    acceptance = _accepted_primary_document(
        superadmin_user=superadmin_user,
        investor=investor,
        idempotency_key="accept-render-pdf",
    )

    artifact = render_document_acceptance_artifact(
        RenderDocumentAcceptanceArtifactCommand(
            actor=investor,
            acceptance_id=str(acceptance.id),
            output_format="pdf",
        )
    )
    rerendered = render_document_acceptance_artifact(
        RenderDocumentAcceptanceArtifactCommand(
            actor=investor,
            acceptance_id=str(acceptance.id),
            output_format="pdf",
        )
    )
    pdf_bytes = base64.b64decode(artifact.content.encode("ascii"))

    assert artifact.content_type == "application/pdf"
    assert artifact.content_encoding == "base64"
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert artifact.content_sha256 == rerendered.content_sha256
    assert artifact.manifest["source_of_truth"] == "template_version_and_acceptance_snapshot"
    assert artifact.manifest["legal_content_status"] == (
        "template_content_must_be_approved_before_production_use"
    )
    assert artifact.manifest["renderer_version"] == "document-artifact-renderer-v2"
    assert b"Table of contents" in pdf_bytes
    assert b"BANXUM accepted-document artifact" in pdf_bytes
    assert DocumentRenderedArtifact.objects.filter(
        acceptance=acceptance,
        content_sha256=artifact.content_sha256,
    ).count() == 2
    assert DocumentEvent.objects.filter(event_type="artifact_rendered").count() == 2
    assert DomainEvent.objects.filter(event_type="DocumentArtifactRendered").count() == 2
    assert AuditEvent.objects.filter(action="document.artifact_rendered").count() == 2


@pytest.mark.django_db
def test_render_acceptance_csv_neutralizes_formula_cells(
    superadmin_user: Model,
    investor: Model,
) -> None:
    acceptance = _accepted_primary_document(
        superadmin_user=superadmin_user,
        investor=investor,
        idempotency_key="accept-render-csv",
        body="{{loan.title}}",
        loan_title="=HYPERLINK(\"https://evil.example\")",
    )

    artifact = render_document_acceptance_artifact(
        RenderDocumentAcceptanceArtifactCommand(
            actor=investor,
            acceptance_id=str(acceptance.id),
            output_format="csv",
        )
    )

    assert artifact.content_type == "text/csv; charset=utf-8"
    assert "rendered_body" in artifact.content
    assert "'=HYPERLINK" in artifact.content


@pytest.mark.django_db
def test_render_acceptance_rejects_missing_template_variable(
    superadmin_user: Model,
    investor: Model,
) -> None:
    acceptance = _accepted_primary_document(
        superadmin_user=superadmin_user,
        investor=investor,
        idempotency_key="accept-render-missing-variable",
        body="Missing {{loan.not_present}}.",
    )

    with pytest.raises(DocumentValidationError, match="loan.not_present"):
        render_document_acceptance_artifact(
            RenderDocumentAcceptanceArtifactCommand(
                actor=investor,
                acceptance_id=str(acceptance.id),
                output_format="pdf",
            )
        )


@pytest.mark.django_db
def test_render_acceptance_is_owner_or_admin_scoped(
    superadmin_user: Model,
    admin_user: Model,
    investor: Model,
) -> None:
    acceptance = _accepted_primary_document(
        superadmin_user=superadmin_user,
        investor=investor,
        idempotency_key="accept-render-owner-scoped",
    )
    user_model: Any = get_user_model()
    other = cast(
        Model,
        user_model.objects.create_user(
            email="other-docs-investor@example.test",
            full_name="Other Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )

    with pytest.raises(DocumentAuthorizationError):
        render_document_acceptance_artifact(
            RenderDocumentAcceptanceArtifactCommand(
                actor=other,
                acceptance_id=str(acceptance.id),
                output_format="pdf",
            )
        )

    admin_artifact = render_document_acceptance_artifact(
        RenderDocumentAcceptanceArtifactCommand(
            actor=admin_user,
            acceptance_id=str(acceptance.id),
            output_format="csv",
            purpose="admin_download",
        )
    )
    assert admin_artifact.rendered_artifact.purpose == "admin_download"


@pytest.mark.django_db
def test_document_acceptance_artifact_api(
    client: Client,
    superadmin_user: Model,
    investor: Model,
) -> None:
    acceptance = _accepted_primary_document(
        superadmin_user=superadmin_user,
        investor=investor,
        idempotency_key="accept-render-api",
    )
    client.force_login(cast(Any, investor))

    response = client.post(
        f"/api/v1/documents/acceptances/{acceptance.id}/artifact/",
        data={"output_format": "pdf"},
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] == "application/pdf"
    assert payload["content_encoding"] == "base64"
    assert payload["content_sha256"] == payload["manifest"]["content_sha256"]
    assert DocumentRenderedArtifact.objects.filter(id=payload["rendered_artifact_id"]).exists()


@pytest.mark.django_db
def test_document_acceptance_api_rejects_missing_required_checkbox(
    client: Client,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    version = create_document_template_version(_template_command(superadmin_user))
    labels = list(cast(list[str], version.checkbox_labels))
    client.force_login(cast(Any, investor))

    response = client.post(
        "/api/v1/documents/acceptances/",
        data={
            "category": DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            "expected_template_version_id": str(version.id),
            "accepted_checkbox_labels": labels[:1],
            "context_type": "primary_order",
            "context_id": "api-order-missing-label",
            "idempotency_key": "api-accept-missing-label",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert DocumentAcceptanceEvidence.objects.count() == 0


@pytest.mark.django_db
def test_document_append_only_records_have_app_and_db_guards(
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    version = create_document_template_version(_template_command(superadmin_user))
    acceptance = accept_document_terms(
        AcceptDocumentTermsCommand(
            actor=investor,
            category=DocumentCategory.PRIMARY_MARKET_INVESTMENT,
            accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
            context_type="primary_order",
            context_id="order-append-only",
            data_snapshot={"loan": {"title": "Append-only test loan"}},
            idempotency_key="accept-append-only",
        )
    )
    event = DocumentEvent.objects.get(event_type="accepted")
    artifact = render_document_acceptance_artifact(
        RenderDocumentAcceptanceArtifactCommand(
            actor=investor,
            acceptance_id=str(acceptance.id),
            output_format="pdf",
        )
    ).rendered_artifact
    guarded_records = [
        (version, DocumentTemplateVersion, "documents_documenttemplateversion"),
        (acceptance, DocumentAcceptanceEvidence, "documents_documentacceptanceevidence"),
        (artifact, DocumentRenderedArtifact, "documents_documentrenderedartifact"),
        (event, DocumentEvent, "documents_documentevent"),
    ]

    for record, model, table in guarded_records:
        record_id = record.pk
        db_record_id = record_id.hex
        with pytest.raises(AppendOnlyViolation):
            record.save()
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).update(id=record_id)
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).delete()

        with pytest.raises(DatabaseError) as update_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {table} SET id = %s WHERE id = %s",
                    [db_record_id, db_record_id],
                )
        assert "append-only" in str(update_error.value)

        with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE id = %s", [db_record_id])
        assert "append-only" in str(delete_error.value)
