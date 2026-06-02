from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import Max, Model
from django.utils import timezone

from backend.apps.documents.models import (
    DocumentAcceptanceEvidence,
    DocumentCategory,
    DocumentEvent,
    DocumentEventType,
    DocumentTemplate,
    DocumentTemplateVersion,
    DocumentTemplateVersionStatus,
)
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_lender_actor,
    is_superadmin_actor,
    user_can_access_financial_features,
)
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class DocumentsError(ValueError):
    pass


class DocumentAuthorizationError(DocumentsError):
    pass


class DocumentValidationError(DocumentsError):
    pass


DEFAULT_TEMPLATE_KEY = "default"
SUPPORTED_LANGUAGES = frozenset({"en"})
MAX_IDEMPOTENCY_KEY_LENGTH = 160
ACCEPTANCE_FINGERPRINT_METADATA_KEY = "request_fingerprint"
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)*)\s*}}")
TEMPLATE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")


DEFAULT_VARIABLE_SCOPES: dict[str, dict[str, Any]] = {
    DocumentCategory.REGISTRATION: {
        "user": {"description": "Registering user/account fields."},
        "platform": {"description": "Platform brand and configuration fields."},
        "operator": {"description": "Legal operator fields."},
        "balance": {"description": "Balance ageing, withdrawal, penalty, and FX rules."},
        "support": {"description": "Support contact fields."},
    },
    DocumentCategory.PRIMARY_MARKET_INVESTMENT: {
        "user": {"description": "Authenticated investor fields."},
        "lender": {"description": "Lender account fields."},
        "loan": {"description": "Loan/project fields."},
        "borrower": {"description": "Borrower disclosure fields."},
        "order": {"description": "Primary investment order fields."},
        "documents": {"description": "Generated document package fields."},
        "payment": {"description": "Balance/deposit/payment instruction fields."},
        "platform": {"description": "Platform brand fields."},
        "operator": {"description": "Legal operator fields."},
        "risk": {"description": "Risk acknowledgement/disclosure fields."},
    },
    DocumentCategory.SECONDARY_MARKET_PURCHASE: {
        "user": {"description": "Authenticated buyer fields."},
        "buyer": {"description": "Secondary-market buyer fields."},
        "seller": {"description": "Secondary-market seller fields."},
        "loan": {"description": "Loan/project fields."},
        "holding": {"description": "Transferred holding fields."},
        "listing": {"description": "Secondary-market listing fields."},
        "fees": {"description": "Maker/taker fee fields."},
        "documents": {"description": "Generated document package fields."},
        "platform": {"description": "Platform brand fields."},
        "operator": {"description": "Legal operator fields."},
    },
    DocumentCategory.SECONDARY_MARKET_LISTING: {
        "user": {"description": "Authenticated seller fields."},
        "seller": {"description": "Secondary-market seller fields."},
        "loan": {"description": "Loan/project fields."},
        "holding": {"description": "Listed holding fields."},
        "listing": {"description": "Secondary-market listing fields."},
        "platform": {"description": "Platform brand fields."},
        "operator": {"description": "Legal operator fields."},
        "risk": {"description": "Non-standard listing disclosure fields."},
    },
}


@dataclass(frozen=True, slots=True)
class CreateDocumentTemplateVersionCommand:
    actor: Model
    category: str
    name: str
    title: str
    body: str
    checkbox_labels: list[str]
    template_key: str = DEFAULT_TEMPLATE_KEY
    language: str = "en"
    description: str = ""
    variable_schema: dict[str, Any] | None = None
    publish_now: bool = False
    legal_review_reference: str = ""
    metadata: dict[str, Any] | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class PublishDocumentTemplateVersionCommand:
    actor: Model
    template_version_id: str
    legal_review_reference: str = ""
    metadata: dict[str, Any] | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class AcceptDocumentTermsCommand:
    actor: Model
    category: str
    accepted_checkbox_labels: list[str]
    context_type: str
    context_id: str
    template_key: str = DEFAULT_TEMPLATE_KEY
    language: str = "en"
    expected_template_version_id: str | None = None
    data_snapshot: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str = ""
    idempotency_key: str | None = None
    metadata: dict[str, Any] | None = None


def _actor_account_type(actor: Model) -> str:
    return str(getattr(actor, "account_type", ""))


def _require_superadmin_actor(actor: Model) -> None:
    if not is_superadmin_actor(actor):
        raise DocumentAuthorizationError("Only an active superadmin can manage templates.")


def _require_lender_acceptance_actor(actor: Model, category: DocumentCategory) -> None:
    if category == DocumentCategory.REGISTRATION:
        if not is_lender_actor(actor):
            raise DocumentAuthorizationError("Only an active lender can accept this document.")
        return
    if not user_can_access_financial_features(actor):
        raise DocumentAuthorizationError(
            "Investor must pass account, phone, and KYC/KYB gates before accepting this document."
        )


def _category(value: str) -> DocumentCategory:
    try:
        return DocumentCategory(value)
    except ValueError as exc:
        raise DocumentValidationError(f"Invalid document category: {value}") from exc


def _language(value: str) -> str:
    language = value.strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        raise DocumentValidationError("Only English document templates are supported at launch.")
    return language


def _template_key(value: str) -> str:
    key = value.strip().lower()
    if not TEMPLATE_KEY_PATTERN.fullmatch(key):
        raise DocumentValidationError(
            "Template key must start with a lowercase letter or digit and contain only "
            "lowercase letters, digits, underscore, dot, colon, or hyphen."
        )
    return key


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise DocumentValidationError(f"{label} is required.")
    return cleaned


def _clean_context(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise DocumentValidationError(f"{label} is required.")
    if len(cleaned) > 128:
        raise DocumentValidationError(f"{label} must be at most 128 characters.")
    return cleaned


def _clean_checkbox_labels(labels: list[str]) -> list[str]:
    if not isinstance(labels, list) or not labels:
        raise DocumentValidationError("At least one checkbox label is required.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if not isinstance(label, str):
            raise DocumentValidationError("Checkbox labels must be strings.")
        cleaned_label = _clean_required(label, "Checkbox label")
        if cleaned_label in seen:
            raise DocumentValidationError("Checkbox labels must be unique.")
        seen.add(cleaned_label)
        cleaned.append(cleaned_label)
    return cleaned


def default_variable_schema(category: str) -> dict[str, Any]:
    document_category = _category(category)
    return dict(DEFAULT_VARIABLE_SCOPES[document_category])


def _variable_schema(category: DocumentCategory, value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return default_variable_schema(category)
    if not isinstance(value, dict) or not value:
        raise DocumentValidationError("Variable schema must be a non-empty object.")
    for key in value:
        if not isinstance(key, str) or not key.strip():
            raise DocumentValidationError("Variable scope names must be non-empty strings.")
    return value


def _validate_template_placeholders(body: str, variable_schema: dict[str, Any]) -> None:
    allowed_roots = set(variable_schema)
    unknown: set[str] = set()
    for match in PLACEHOLDER_PATTERN.finditer(body):
        root = match.group(1).split(".", 1)[0]
        if root not in allowed_roots:
            unknown.add(root)
    if unknown:
        unknown_text = ", ".join(sorted(unknown))
        raise DocumentValidationError(
            f"Template contains unsupported variable scope(s): {unknown_text}."
        )


def _stable_json_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _content_hash(
    *,
    category: str,
    template_key: str,
    language: str,
    title: str,
    body: str,
    checkbox_labels: list[str],
    variable_schema: dict[str, Any],
) -> str:
    return _stable_json_fingerprint(
        {
            "category": category,
            "template_key": template_key,
            "language": language,
            "title": title,
            "body": body,
            "checkbox_labels": checkbox_labels,
            "variable_schema": variable_schema,
        }
    )


def _next_version_number(template: DocumentTemplate) -> int:
    aggregate = template.versions.aggregate(max_version=Max("version_number"))
    max_version = aggregate["max_version"] or 0
    return int(max_version) + 1


def _record_document_event(
    *,
    template: DocumentTemplate | None,
    template_version: DocumentTemplateVersion | None,
    category: str,
    actor: Model,
    event_type: DocumentEventType,
    note: str = "",
    metadata: dict[str, Any] | None = None,
) -> DocumentEvent:
    return cast(
        DocumentEvent,
        DocumentEvent.objects.create(
            template=template,
            template_version=template_version,
            category=category,
            event_type=event_type,
            actor_user_id=actor.pk,
            actor_account_type=_actor_account_type(actor),
            note=note.strip(),
            metadata=metadata or {},
        ),
    )


@transaction.atomic
def create_document_template_version(
    command: CreateDocumentTemplateVersionCommand,
) -> DocumentTemplateVersion:
    _require_superadmin_actor(command.actor)
    category = _category(command.category)
    template_key = _template_key(command.template_key)
    language = _language(command.language)
    name = _clean_required(command.name, "Name")
    title = _clean_required(command.title, "Title")
    body = _clean_required(command.body, "Body")
    checkbox_labels = _clean_checkbox_labels(command.checkbox_labels)
    variable_schema = _variable_schema(category, command.variable_schema)
    _validate_template_placeholders(body, variable_schema)

    template, created = DocumentTemplate.objects.select_for_update().get_or_create(
        category=category,
        template_key=template_key,
        language=language,
        defaults={
            "name": name,
            "description": command.description.strip(),
            "created_by_superadmin_id": command.actor.pk,
            "updated_by_superadmin_id": command.actor.pk,
        },
    )
    if not created:
        template.name = name
        template.description = command.description.strip()
        template.updated_by_superadmin_id = command.actor.pk
        template.save(
            update_fields=["name", "description", "updated_by_superadmin_id", "updated_at"]
        )
    version_number = _next_version_number(template)
    status = (
        DocumentTemplateVersionStatus.PUBLISHED
        if command.publish_now
        else DocumentTemplateVersionStatus.DRAFT
    )
    published_at = timezone.now() if command.publish_now else None
    content_hash = _content_hash(
        category=category,
        template_key=template_key,
        language=language,
        title=title,
        body=body,
        checkbox_labels=checkbox_labels,
        variable_schema=variable_schema,
    )
    version = cast(
        DocumentTemplateVersion,
        DocumentTemplateVersion.objects.create(
            template=template,
            version_number=version_number,
            status=status,
            title=title,
            body=body,
            checkbox_labels=checkbox_labels,
            variable_schema=variable_schema,
            content_hash=content_hash,
            created_by_superadmin_id=command.actor.pk,
            published_at=published_at,
            legal_review_reference=command.legal_review_reference.strip(),
            metadata=command.metadata or {},
        ),
    )
    if command.publish_now:
        template.current_published_version = version
        template.updated_by_superadmin_id = command.actor.pk
        template.save(
            update_fields=[
                "current_published_version",
                "updated_by_superadmin_id",
                "updated_at",
            ]
        )

    actor_ref = actor_ref_for_user(command.actor)
    event_metadata = {
        "category": category,
        "template_id": str(template.id),
        "template_version_id": str(version.id),
        "template_key": template_key,
        "language": language,
        "version_number": version.version_number,
        "status": version.status,
        "content_hash": version.content_hash,
        "created_template": created,
    }
    event_type = (
        DocumentEventType.TEMPLATE_CREATED if created else DocumentEventType.VERSION_CREATED
    )
    _record_document_event(
        template=template,
        template_version=version,
        category=category,
        actor=command.actor,
        event_type=event_type,
        note=command.note,
        metadata=event_metadata,
    )
    if command.publish_now:
        _record_document_event(
            template=template,
            template_version=version,
            category=category,
            actor=command.actor,
            event_type=DocumentEventType.VERSION_PUBLISHED,
            note=command.note,
            metadata=event_metadata,
        )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="document.template_version_created",
            target_type="DocumentTemplateVersion",
            target_id=str(version.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="DocumentTemplateVersionCreated",
            aggregate_type="DocumentTemplateVersion",
            aggregate_id=str(version.id),
            payload=event_metadata,
            idempotency_key=f"document-template-version:{version.id}:created",
        )
    )
    if command.publish_now:
        record_audit_event(
            AuditCommand(
                actor=actor_ref,
                action="document.template_version_published",
                target_type="DocumentTemplateVersion",
                target_id=str(version.id),
                metadata=event_metadata,
            )
        )
        record_domain_event(
            DomainEventCommand(
                event_type="DocumentTemplateVersionPublished",
                aggregate_type="DocumentTemplateVersion",
                aggregate_id=str(version.id),
                payload=event_metadata,
                idempotency_key=f"document-template-version:{version.id}:published",
            )
        )
    return version


@transaction.atomic
def publish_document_template_version(
    command: PublishDocumentTemplateVersionCommand,
) -> DocumentTemplateVersion:
    _require_superadmin_actor(command.actor)
    source_version = cast(
        DocumentTemplateVersion | None,
        DocumentTemplateVersion.objects.select_related("template")
        .filter(id=command.template_version_id)
        .first(),
    )
    if source_version is None:
        raise DocumentValidationError("Template version does not exist.")
    template = source_version.template
    template = DocumentTemplate.objects.select_for_update().get(id=template.id)

    if (
        source_version.status == DocumentTemplateVersionStatus.PUBLISHED
        and template.current_published_version_id == source_version.id
    ):
        return source_version

    if source_version.status == DocumentTemplateVersionStatus.PUBLISHED:
        published_version = source_version
    else:
        published_version = cast(
            DocumentTemplateVersion,
            DocumentTemplateVersion.objects.create(
                template=template,
                version_number=_next_version_number(template),
                status=DocumentTemplateVersionStatus.PUBLISHED,
                title=source_version.title,
                body=source_version.body,
                checkbox_labels=source_version.checkbox_labels,
                variable_schema=source_version.variable_schema,
                content_hash=source_version.content_hash,
                created_by_superadmin_id=command.actor.pk,
                source_version_id=source_version.id,
                published_at=timezone.now(),
                legal_review_reference=(
                    command.legal_review_reference.strip()
                    or source_version.legal_review_reference
                ),
                metadata={**source_version.metadata, **(command.metadata or {})},
            ),
        )

    template.current_published_version = published_version
    template.updated_by_superadmin_id = command.actor.pk
    template.save(
        update_fields=[
            "current_published_version",
            "updated_by_superadmin_id",
            "updated_at",
        ]
    )
    event_metadata = {
        "category": template.category,
        "template_id": str(template.id),
        "template_version_id": str(published_version.id),
        "source_version_id": str(source_version.id),
        "template_key": template.template_key,
        "language": template.language,
        "version_number": published_version.version_number,
        "content_hash": published_version.content_hash,
    }
    _record_document_event(
        template=template,
        template_version=published_version,
        category=template.category,
        actor=command.actor,
        event_type=DocumentEventType.VERSION_PUBLISHED,
        note=command.note,
        metadata=event_metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="document.template_version_published",
            target_type="DocumentTemplateVersion",
            target_id=str(published_version.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="DocumentTemplateVersionPublished",
            aggregate_type="DocumentTemplateVersion",
            aggregate_id=str(published_version.id),
            payload=event_metadata,
            idempotency_key=f"document-template-version:{published_version.id}:published",
        )
    )
    return published_version


def get_current_document_template(
    *,
    category: str,
    template_key: str = DEFAULT_TEMPLATE_KEY,
    language: str = "en",
) -> DocumentTemplateVersion:
    document_category = _category(category)
    key = _template_key(template_key)
    lang = _language(language)
    template = (
        DocumentTemplate.objects.select_related("current_published_version")
        .filter(category=document_category, template_key=key, language=lang)
        .first()
    )
    if template is None or template.current_published_version is None:
        raise DocumentValidationError("No published template exists for this category.")
    return template.current_published_version


def _acceptance_fingerprint(
    *,
    actor: Model,
    template_version: DocumentTemplateVersion,
    category: str,
    context_type: str,
    context_id: str,
    accepted_checkbox_labels: list[str],
    data_snapshot: dict[str, Any],
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "actor_id": str(actor.pk),
            "template_version_id": str(template_version.id),
            "template_hash": template_version.content_hash,
            "category": category,
            "context_type": context_type,
            "context_id": context_id,
            "accepted_checkbox_labels": accepted_checkbox_labels,
            "data_snapshot": data_snapshot,
            "idempotency_key": idempotency_key,
        }
    )


def _existing_acceptance_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> DocumentAcceptanceEvidence | None:
    existing = cast(
        DocumentAcceptanceEvidence | None,
        DocumentAcceptanceEvidence.objects.filter(idempotency_key=idempotency_key).first(),
    )
    if existing is None:
        return None
    if existing.metadata.get(ACCEPTANCE_FINGERPRINT_METADATA_KEY) != expected_fingerprint:
        raise DocumentValidationError(
            "Idempotency key was already used for a different acceptance."
        )
    return existing


@transaction.atomic
def accept_document_terms(command: AcceptDocumentTermsCommand) -> DocumentAcceptanceEvidence:
    category = _category(command.category)
    _require_lender_acceptance_actor(command.actor, category)
    template_version = get_current_document_template(
        category=category,
        template_key=command.template_key,
        language=command.language,
    )
    if (
        command.expected_template_version_id is not None
        and str(template_version.id) != command.expected_template_version_id
    ):
        raise DocumentValidationError("Accepted template version is not current.")
    accepted_labels = _clean_checkbox_labels(command.accepted_checkbox_labels)
    required_labels = list(cast(list[str], template_version.checkbox_labels))
    missing = [label for label in required_labels if label not in accepted_labels]
    if missing:
        raise DocumentValidationError("All required checkbox labels must be accepted.")
    context_type = _clean_context(command.context_type, "Context type")
    context_id = _clean_context(command.context_id, "Context id")
    data_snapshot = command.data_snapshot or {}
    if not isinstance(data_snapshot, dict):
        raise DocumentValidationError("Data snapshot must be an object.")
    idempotency_key = (command.idempotency_key or "").strip()
    if not idempotency_key:
        raise DocumentValidationError("Idempotency key is required.")
    if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise DocumentValidationError("Idempotency key is too long.")
    fingerprint = _acceptance_fingerprint(
        actor=command.actor,
        template_version=template_version,
        category=category,
        context_type=context_type,
        context_id=context_id,
        accepted_checkbox_labels=accepted_labels,
        data_snapshot=data_snapshot,
        idempotency_key=idempotency_key,
    )
    existing = _existing_acceptance_for_idempotency(
        idempotency_key,
        expected_fingerprint=fingerprint,
    )
    if existing is not None:
        return existing
    metadata = {**(command.metadata or {}), ACCEPTANCE_FINGERPRINT_METADATA_KEY: fingerprint}
    try:
        acceptance = cast(
            DocumentAcceptanceEvidence,
            DocumentAcceptanceEvidence.objects.create(
                user_id=command.actor.pk,
                category=category,
                template=template_version.template,
                template_version=template_version,
                template_version_number=template_version.version_number,
                template_hash=template_version.content_hash,
                context_type=context_type,
                context_id=context_id,
                accepted_checkbox_labels=accepted_labels,
                data_snapshot=data_snapshot,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                idempotency_key=idempotency_key,
                metadata=metadata,
            ),
        )
    except IntegrityError:
        existing_after_race = _existing_acceptance_for_idempotency(
            idempotency_key,
            expected_fingerprint=fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    event_metadata = {
        "user_id": str(command.actor.pk),
        "category": category,
        "template_id": str(template_version.template_id),
        "template_version_id": str(template_version.id),
        "template_version_number": template_version.version_number,
        "template_hash": template_version.content_hash,
        "context_type": context_type,
        "context_id": context_id,
        "accepted_checkbox_count": len(accepted_labels),
    }
    _record_document_event(
        template=template_version.template,
        template_version=template_version,
        category=category,
        actor=command.actor,
        event_type=DocumentEventType.ACCEPTED,
        metadata=event_metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="document.accepted",
            target_type="DocumentAcceptanceEvidence",
            target_id=str(acceptance.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="DocumentAccepted",
            aggregate_type="DocumentAcceptanceEvidence",
            aggregate_id=str(acceptance.id),
            payload=event_metadata,
            idempotency_key=f"document-acceptance:{acceptance.id}:accepted",
        )
    )
    return acceptance
