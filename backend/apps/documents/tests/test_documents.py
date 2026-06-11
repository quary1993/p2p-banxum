from __future__ import annotations

import base64
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

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
    assert artifact.manifest["renderer_version"] == "document-artifact-renderer-v1"
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
