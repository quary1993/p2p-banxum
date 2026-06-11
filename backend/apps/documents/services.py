from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import textwrap
from dataclasses import dataclass
from typing import Any, cast

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max, Model
from django.utils import timezone

from backend.apps.documents.models import (
    DocumentAcceptanceEvidence,
    DocumentArtifactOutputFormat,
    DocumentArtifactPurpose,
    DocumentCategory,
    DocumentEvent,
    DocumentEventType,
    DocumentRenderedArtifact,
    DocumentTemplate,
    DocumentTemplateVersion,
    DocumentTemplateVersionStatus,
)
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
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
MAX_CHECKBOX_LABELS = 20
MAX_CHECKBOX_LABEL_LENGTH = 500
MAX_ACCEPTANCE_JSON_BYTES = 65_536
ACCEPTANCE_FINGERPRINT_METADATA_KEY = "request_fingerprint"
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)*)\s*}}")
TEMPLATE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"
PDF_CONTENT_TYPE = "application/pdf"
TEXT_CONTENT_ENCODING = "text"
BASE64_CONTENT_ENCODING = "base64"
DOCUMENT_ARTIFACT_RENDERER_VERSION = "document-artifact-renderer-v1"
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
CSV_FORMULA_LEADING_CHARS = ("\t", "\r", "\n")


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


@dataclass(frozen=True, slots=True)
class RenderDocumentAcceptanceArtifactCommand:
    actor: Model
    acceptance_id: str
    output_format: str = DocumentArtifactOutputFormat.PDF
    purpose: str = DocumentArtifactPurpose.INVESTOR_DOWNLOAD
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RenderedDocumentArtifact:
    rendered_artifact: DocumentRenderedArtifact
    content_type: str
    filename: str
    content: str
    content_encoding: str
    content_sha256: str
    manifest: dict[str, Any]


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
    if len(labels) > MAX_CHECKBOX_LABELS:
        raise DocumentValidationError(f"At most {MAX_CHECKBOX_LABELS} checkbox labels are allowed.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if not isinstance(label, str):
            raise DocumentValidationError("Checkbox labels must be strings.")
        cleaned_label = _clean_required(label, "Checkbox label")
        if len(cleaned_label) > MAX_CHECKBOX_LABEL_LENGTH:
            raise DocumentValidationError(
                f"Checkbox labels must be at most {MAX_CHECKBOX_LABEL_LENGTH} characters."
            )
        if cleaned_label in seen:
            raise DocumentValidationError("Checkbox labels must be unique.")
        seen.add(cleaned_label)
        cleaned.append(cleaned_label)
    return cleaned


def _assert_json_payload_size(value: dict[str, Any], label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    if len(encoded) > MAX_ACCEPTANCE_JSON_BYTES:
        raise DocumentValidationError(
            f"{label} must not exceed {MAX_ACCEPTANCE_JSON_BYTES} bytes when serialized."
        )


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _acceptance_data_snapshot(actor: Model, raw_snapshot: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(raw_snapshot)
    authoritative = {
        "user": {
            "id": str(actor.pk),
            "email": str(getattr(actor, "email", "")),
            "full_name": str(getattr(actor, "full_name", "")),
            "account_type": _actor_account_type(actor),
        },
        "platform": {
            "name": settings.PLATFORM_BRAND_NAME,
            "base_url": settings.PUBLIC_APP_BASE_URL,
        },
        "operator": {
            "name": settings.LEGAL_OPERATOR_NAME,
        },
    }
    # Authoritative user/platform/operator values are set server-side so generated documents
    # cannot be made to evidence a forged brand, operator, or accepting party.
    return _deep_merge(snapshot, authoritative)


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


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


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


def _artifact_output_format(value: str) -> DocumentArtifactOutputFormat:
    try:
        return DocumentArtifactOutputFormat(value.strip().lower())
    except ValueError as exc:
        raise DocumentValidationError("Document artifacts can be rendered as pdf or csv.") from exc


def _artifact_purpose(value: str) -> DocumentArtifactPurpose:
    try:
        return DocumentArtifactPurpose(value.strip().lower())
    except ValueError as exc:
        raise DocumentValidationError("Unsupported document artifact purpose.") from exc


def _document_access_allowed(actor: Model, acceptance: DocumentAcceptanceEvidence) -> bool:
    if is_admin_actor(actor):
        return True
    return str(actor.pk) == str(acceptance.user_id) and is_lender_actor(actor)


def _resolve_path(context: dict[str, Any], path: str) -> Any:
    value: Any = context
    for segment in path.split("."):
        if isinstance(value, dict) and segment in value:
            value = value[segment]
            continue
        raise DocumentValidationError(f"Document template variable is missing: {path}")
    return value


def _render_template_text(*, body: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = _resolve_path(context, match.group(1))
        if value is None:
            return ""
        if isinstance(value, dict | list):
            return _stable_json(value)
        return str(value)

    return PLACEHOLDER_PATTERN.sub(replace, body)


def _csv_cell(value: Any) -> str | int:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return value
    if isinstance(value, dict | list):
        value = _stable_json(value)
    text = str(value)
    stripped = text.lstrip(" \t\r\n")
    if (
        text.startswith(CSV_FORMULA_LEADING_CHARS)
        or text.startswith(CSV_FORMULA_PREFIXES)
        or stripped.startswith(CSV_FORMULA_PREFIXES)
    ):
        return f"'{text}"
    return text


def _rows_to_csv(*, columns: list[str], rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_cell(row.get(column)) for column in columns})
    return buffer.getvalue()


def _content_sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _pdf_escape(text: str) -> str:
    ascii_text = text.encode("latin-1", errors="replace").decode("latin-1")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf_bytes(lines: list[str]) -> bytes:
    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(line, width=112) or [""])
    page_lines = [wrapped_lines[index : index + 62] for index in range(0, len(wrapped_lines), 62)]
    if not page_lines:
        page_lines = [["No document content."]]

    objects: dict[int, bytes] = {}
    page_object_ids: list[int] = []
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    next_id = 4
    for page_number, lines_for_page in enumerate(page_lines, start=1):
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        page_object_ids.append(page_id)
        text_commands = ["BT", "/F1 8 Tf", "10 TL", "36 800 Td"]
        for line in lines_for_page:
            text_commands.append(f"({_pdf_escape(line)}) Tj")
            text_commands.append("T*")
        text_commands.extend(["T*", f"(Page {page_number} of {len(page_lines)}) Tj", "ET"])
        content = "\n".join(text_commands).encode("latin-1", errors="replace")
        objects[content_id] = (
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream"
        )
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            + f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode(
                "ascii"
            )
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("ascii")
    ordered_ids = sorted(objects)
    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {0: 0}
    for object_id in ordered_ids:
        offsets[object_id] = buffer.tell()
        buffer.write(f"{object_id} 0 obj\n".encode("ascii"))
        buffer.write(objects[object_id])
        buffer.write(b"\nendobj\n")
    xref_offset = buffer.tell()
    max_id = max(ordered_ids)
    buffer.write(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for object_id in range(1, max_id + 1):
        offset = offsets.get(object_id, 0)
        status = "n" if object_id in offsets else "f"
        generation = "00000" if object_id in offsets else "65535"
        buffer.write(f"{offset:010d} {generation} {status} \n".encode("ascii"))
    buffer.write(
        f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return buffer.getvalue()


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip().lower()).strip("-")
    return (cleaned or "document")[:80]


def _artifact_manifest(
    *,
    acceptance: DocumentAcceptanceEvidence,
    rendered_body: str,
    output_format: str,
    content_type: str,
    filename: str,
    content_sha256: str,
    purpose: str,
) -> dict[str, Any]:
    return {
        "document_kind": "acceptance_evidence",
        "acceptance_id": str(acceptance.id),
        "user_id": str(acceptance.user_id),
        "category": acceptance.category,
        "template_id": str(acceptance.template_id),
        "template_version_id": str(acceptance.template_version_id),
        "template_version_number": acceptance.template_version_number,
        "template_hash": acceptance.template_hash,
        "context_type": acceptance.context_type,
        "context_id": acceptance.context_id,
        "accepted_at": acceptance.accepted_at.isoformat(),
        "output_format": output_format,
        "content_type": content_type,
        "filename": filename,
        "content_sha256": content_sha256,
        "purpose": purpose,
        "renderer_version": DOCUMENT_ARTIFACT_RENDERER_VERSION,
        "rendered_body_sha256": hashlib.sha256(rendered_body.encode("utf-8")).hexdigest(),
        "source_of_truth": "template_version_and_acceptance_snapshot",
        "legal_content_status": "template_content_must_be_approved_before_production_use",
    }


def _acceptance_render_context(acceptance: DocumentAcceptanceEvidence) -> dict[str, Any]:
    snapshot = dict(acceptance.data_snapshot or {})
    evidence = {
        "id": str(acceptance.id),
        "category": acceptance.category,
        "template_hash": acceptance.template_hash,
        "template_version_number": acceptance.template_version_number,
        "context_type": acceptance.context_type,
        "context_id": acceptance.context_id,
        "accepted_at": acceptance.accepted_at.isoformat(),
        "checkbox_labels": list(acceptance.accepted_checkbox_labels),
    }
    document = {
        "title": acceptance.template_version.title,
        "template_key": acceptance.template.template_key,
        "language": acceptance.template.language,
        "version_number": acceptance.template_version_number,
        "content_hash": acceptance.template_hash,
    }
    return _deep_merge(snapshot, {"acceptance": evidence, "document": document})


def _acceptance_rows(
    *,
    acceptance: DocumentAcceptanceEvidence,
    rendered_body: str,
) -> list[dict[str, Any]]:
    return [
        {"field": "document_title", "value": acceptance.template_version.title},
        {"field": "category", "value": acceptance.category},
        {"field": "template_key", "value": acceptance.template.template_key},
        {"field": "template_version_id", "value": str(acceptance.template_version_id)},
        {"field": "template_version_number", "value": acceptance.template_version_number},
        {"field": "template_hash", "value": acceptance.template_hash},
        {"field": "accepted_at", "value": acceptance.accepted_at.isoformat()},
        {"field": "context_type", "value": acceptance.context_type},
        {"field": "context_id", "value": acceptance.context_id},
        {
            "field": "accepted_checkbox_labels",
            "value": "; ".join(str(label) for label in acceptance.accepted_checkbox_labels),
        },
        {"field": "rendered_body", "value": rendered_body},
        {"field": "data_snapshot_json", "value": acceptance.data_snapshot},
    ]


def _acceptance_pdf_lines(
    *,
    acceptance: DocumentAcceptanceEvidence,
    rendered_body: str,
) -> list[str]:
    return [
        acceptance.template_version.title,
        "",
        *rendered_body.splitlines(),
        "",
        "Acceptance Evidence",
        f"Platform: {settings.PLATFORM_BRAND_NAME}",
        f"Operator: {settings.LEGAL_OPERATOR_NAME}",
        f"Acceptance ID: {acceptance.id}",
        f"User ID: {acceptance.user_id}",
        f"Category: {acceptance.category}",
        f"Context: {acceptance.context_type}:{acceptance.context_id}",
        f"Accepted at: {acceptance.accepted_at.isoformat()}",
        f"Template version ID: {acceptance.template_version_id}",
        f"Template version number: {acceptance.template_version_number}",
        f"Template hash: {acceptance.template_hash}",
        "Accepted checkboxes:",
        *[f"- {label}" for label in acceptance.accepted_checkbox_labels],
        "",
        "This artifact is regenerated from immutable BANXUM clickwrap evidence. "
        "The accepted template version, content hash, data snapshot, context, timestamp, "
        "IP/user-agent where available, and checkbox labels remain the source of truth.",
    ]


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
        current_version = cast(
            DocumentTemplateVersion | None,
            (
                DocumentTemplateVersion.objects.filter(
                    id=template.current_published_version_id
                ).first()
                if template.current_published_version_id
                else None
            ),
        )
        if (
            current_version is not None
            and current_version.status == DocumentTemplateVersionStatus.PUBLISHED
            and current_version.source_version_id == source_version.id
        ):
            return current_version
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
    raw_data_snapshot = command.data_snapshot or {}
    if not isinstance(raw_data_snapshot, dict):
        raise DocumentValidationError("Data snapshot must be an object.")
    _assert_json_payload_size(raw_data_snapshot, "Data snapshot")
    data_snapshot = _acceptance_data_snapshot(command.actor, raw_data_snapshot)
    _assert_json_payload_size(data_snapshot, "Data snapshot")
    if command.metadata is not None and not isinstance(command.metadata, dict):
        raise DocumentValidationError("Metadata must be an object.")
    _assert_json_payload_size(command.metadata or {}, "Metadata")
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


@transaction.atomic
def render_document_acceptance_artifact(
    command: RenderDocumentAcceptanceArtifactCommand,
) -> RenderedDocumentArtifact:
    output_format = _artifact_output_format(command.output_format)
    purpose = _artifact_purpose(command.purpose)
    if command.metadata is not None and not isinstance(command.metadata, dict):
        raise DocumentValidationError("Metadata must be an object.")
    acceptance = cast(
        DocumentAcceptanceEvidence | None,
        DocumentAcceptanceEvidence.objects.select_related("template", "template_version")
        .filter(id=command.acceptance_id)
        .first(),
    )
    if acceptance is None:
        raise DocumentValidationError("Document evidence was not found.")
    if not _document_access_allowed(command.actor, acceptance):
        raise DocumentAuthorizationError("Document evidence is not available to this account.")

    context = _acceptance_render_context(acceptance)
    rendered_body = _render_template_text(
        body=acceptance.template_version.body,
        context=context,
    )
    filename_base = _safe_filename(
        f"{acceptance.template_version.title}-{acceptance.context_type}-{acceptance.context_id}"
    )
    if output_format == DocumentArtifactOutputFormat.CSV:
        content = _rows_to_csv(
            columns=["field", "value"],
            rows=_acceptance_rows(acceptance=acceptance, rendered_body=rendered_body),
        )
        content_bytes = content.encode("utf-8")
        content_type = CSV_CONTENT_TYPE
        content_encoding = TEXT_CONTENT_ENCODING
        filename = f"{filename_base}.csv"
        encoded_content = content
    else:
        pdf_bytes = _simple_pdf_bytes(
            _acceptance_pdf_lines(acceptance=acceptance, rendered_body=rendered_body)
        )
        content_bytes = pdf_bytes
        content_type = PDF_CONTENT_TYPE
        content_encoding = BASE64_CONTENT_ENCODING
        filename = f"{filename_base}.pdf"
        encoded_content = base64.b64encode(pdf_bytes).decode("ascii")

    content_sha256 = _content_sha256_bytes(content_bytes)
    manifest = _artifact_manifest(
        acceptance=acceptance,
        rendered_body=rendered_body,
        output_format=output_format,
        content_type=content_type,
        filename=filename,
        content_sha256=content_sha256,
        purpose=purpose,
    )
    artifact = cast(
        DocumentRenderedArtifact,
        DocumentRenderedArtifact.objects.create(
            acceptance=acceptance,
            template=acceptance.template,
            template_version=acceptance.template_version,
            user_id=acceptance.user_id,
            actor_user_id=command.actor.pk,
            actor_account_type=_actor_account_type(command.actor),
            output_format=output_format,
            purpose=purpose,
            content_type=content_type,
            content_encoding=content_encoding,
            filename=filename,
            content_sha256=content_sha256,
            manifest=manifest,
            metadata=command.metadata or {},
        ),
    )
    event_metadata = {
        "acceptance_id": str(acceptance.id),
        "rendered_artifact_id": str(artifact.id),
        "user_id": str(acceptance.user_id),
        "category": acceptance.category,
        "template_version_id": str(acceptance.template_version_id),
        "context_type": acceptance.context_type,
        "context_id": acceptance.context_id,
        "output_format": output_format,
        "purpose": purpose,
        "content_sha256": content_sha256,
        "renderer_version": DOCUMENT_ARTIFACT_RENDERER_VERSION,
    }
    _record_document_event(
        template=acceptance.template,
        template_version=acceptance.template_version,
        category=acceptance.category,
        actor=command.actor,
        event_type=DocumentEventType.ARTIFACT_RENDERED,
        metadata=event_metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="document.artifact_rendered",
            target_type="DocumentRenderedArtifact",
            target_id=str(artifact.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="DocumentArtifactRendered",
            aggregate_type="DocumentRenderedArtifact",
            aggregate_id=str(artifact.id),
            payload=event_metadata,
        )
    )
    return RenderedDocumentArtifact(
        rendered_artifact=artifact,
        content_type=content_type,
        filename=filename,
        content=encoded_content,
        content_encoding=content_encoding,
        content_sha256=content_sha256,
        manifest=manifest,
    )
