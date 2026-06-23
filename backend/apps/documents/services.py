from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import textwrap
import uuid
from dataclasses import dataclass
from typing import Any, cast

from django.apps import apps
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
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    record_domain_event,
)


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
DOCUMENT_ARTIFACT_RENDERER_VERSION = "document-artifact-renderer-v2"
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
CSV_FORMULA_LEADING_CHARS = ("\t", "\r", "\n")
DOCUMENT_ACCEPTANCE_EMAIL_TOPIC = "email.document_acceptance_pdf"


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
        "holding": {
            "description": "Holding fields when the primary order has closed into a holding."
        },
        "assignment": {"description": "Claim assignment and assignor fields."},
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


def _format_minor_units_for_document(amount_minor: int, currency: str) -> str:
    sign = "-" if amount_minor < 0 else ""
    absolute = abs(amount_minor)
    major, minor = divmod(absolute, 100)
    return f"{sign}{major:,}.{minor:02d}".replace(",", "'")


def _format_bps_percent_for_document(bps: int) -> str:
    whole, fractional = divmod(int(bps), 100)
    return f"{whole}.{fractional:02d}"


def _display_choice(instance: Model, field_name: str) -> str:
    display = getattr(instance, f"get_{field_name}_display", None)
    if callable(display):
        return str(display())
    return str(getattr(instance, field_name, ""))


def _primary_order_context_snapshot(*, context_type: str, context_id: str) -> dict[str, Any]:
    if context_type != "primary_order":
        return {}
    try:
        order_id = uuid.UUID(str(context_id))
    except ValueError:
        return {}
    order_model = apps.get_model("marketplace_primary", "PrimaryInvestmentOrder")
    installment_model = apps.get_model("loans", "LoanInstallment")
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    order = (
        order_model.objects.select_related("loan", "loan__borrower", "currency")
        .filter(id=order_id)
        .first()
    )
    if order is None:
        return {}
    order_ref = cast(Any, order)
    loan = cast(Model, order_ref.loan)
    loan_ref = cast(Any, loan)
    borrower = cast(Model, loan_ref.borrower)
    borrower_ref = cast(Any, borrower)
    currency = str(order_ref.currency_id)
    effective_amount_minor = int(
        order_ref.allocated_amount_minor or order_ref.requested_amount_minor
    )
    maturity_installment = (
        installment_model.objects.filter(
            loan_id=loan_ref.id,
            schedule_version=loan_ref.schedule_version,
        )
        .order_by("-due_date")
        .first()
    )
    holding = (
        holding_model.objects.filter(source_primary_order_id=order_ref.id)
        .order_by("created_at", "id")
        .first()
    )
    holding_id = str(cast(Any, holding).id) if holding is not None else "Assigned at funding close"
    collateral_description = str(getattr(loan, "collateral_description", "") or "").strip()
    collateral_security = collateral_description or _display_choice(loan, "collateral_type")
    if not collateral_security:
        collateral_security = "As described in the Project Summary"
    confirmation_datetime = order_ref.allocated_at or order_ref.created_at
    return {
        "lender": {
            "id": str(order_ref.investor_user_id),
        },
        "order": {
            "id": str(order_ref.id),
            "agreement_no": f"PIO-{str(order_ref.id)[:8].upper()}",
            "confirmation_datetime": confirmation_datetime.isoformat(),
            "amount": _format_minor_units_for_document(effective_amount_minor, currency),
            "claim_price": _format_minor_units_for_document(effective_amount_minor, currency),
            "currency": currency,
            "requested_amount_minor": int(order_ref.requested_amount_minor),
            "allocated_amount_minor": int(order_ref.allocated_amount_minor),
            "status": str(order_ref.status),
        },
        "loan": {
            "id": str(loan_ref.id),
            "title": str(loan_ref.title),
            "agreement_no": f"LOAN-{str(loan_ref.id)[:8].upper()}",
            "interest_rate_percent": _format_bps_percent_for_document(
                int(loan_ref.interest_rate_bps)
            ),
            "maturity_date": (
                cast(Any, maturity_installment).due_date.isoformat()
                if maturity_installment is not None
                else ""
            ),
            "repayment_type": _display_choice(loan, "repayment_type"),
            "collateral_security": collateral_security,
            "buyback_obligation": "No",
            "currency": currency,
        },
        "borrower": {
            "id": str(borrower_ref.id),
            "legal_name": str(borrower_ref.legal_name),
        },
        "holding": {
            "id": holding_id,
        },
        "assignment": {
            "assignor_name": str(settings.LEGAL_OPERATOR_NAME),
        },
    }


def _acceptance_data_snapshot(
    actor: Model,
    raw_snapshot: dict[str, Any],
    *,
    category: DocumentCategory,
    context_type: str,
    context_id: str,
) -> dict[str, Any]:
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
    if category == DocumentCategory.PRIMARY_MARKET_INVESTMENT:
        authoritative = _deep_merge(
            authoritative,
            _primary_order_context_snapshot(context_type=context_type, context_id=context_id),
        )
    # Authoritative user/platform/operator values are set server-side so generated documents
    # cannot be made to evidence a forged brand, operator, accepting party, or transaction
    # details when the context is a primary-market order known to the platform.
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


PDF_PAGE_WIDTH = 612.0
PDF_PAGE_HEIGHT = 842.0
PDF_MARGIN_X = 42.0
PDF_MARGIN_TOP = 38.0
PDF_MARGIN_BOTTOM = 44.0
PDF_CONTENT_WIDTH = PDF_PAGE_WIDTH - (PDF_MARGIN_X * 2)
PDF_PRIMARY = (47, 107, 79)
PDF_PRIMARY_DARK = (27, 33, 29)
PDF_MUTED = (112, 122, 112)
PDF_RULE = (218, 211, 198)
PDF_TABLE_HEADER_FILL = (233, 229, 217)
PDF_TABLE_ALT_FILL = (252, 251, 247)
PDF_NOTE_FILL = (246, 236, 210)
PDF_INFO_FILL = (227, 237, 244)
PDF_BODY_BOTTOM = PDF_MARGIN_BOTTOM + 28


def _pdf_number(value: float) -> str:
    formatted = f"{value:.3f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _pdf_color(color: tuple[int, int, int]) -> str:
    return " ".join(_pdf_number(channel / 255) for channel in color)


class _PdfDocumentCanvas:
    def __init__(self) -> None:
        self.pages: list[list[str]] = [[]]

    @property
    def current(self) -> list[str]:
        return self.pages[-1]

    def new_page(self) -> None:
        self.pages.append([])

    def text(
        self,
        *,
        x: float,
        y: float,
        text: str,
        size: float = 8.3,
        font: str = "F1",
        color: tuple[int, int, int] = PDF_PRIMARY_DARK,
    ) -> None:
        self.current.append(
            "BT "
            f"/{font} {_pdf_number(size)} Tf "
            f"{_pdf_color(color)} rg "
            f"{_pdf_number(x)} {_pdf_number(y)} Td "
            f"({_pdf_escape(text)}) Tj ET"
        )

    def rect(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: tuple[int, int, int] | None = None,
        stroke: tuple[int, int, int] | None = None,
        line_width: float = 0.6,
    ) -> None:
        commands = ["q"]
        if fill:
            commands.append(f"{_pdf_color(fill)} rg")
        if stroke:
            commands.append(f"{_pdf_color(stroke)} RG {_pdf_number(line_width)} w")
        commands.append(
            f"{_pdf_number(x)} {_pdf_number(y)} {_pdf_number(width)} {_pdf_number(height)} re"
        )
        if fill and stroke:
            commands.append("B")
        elif fill:
            commands.append("f")
        else:
            commands.append("S")
        commands.append("Q")
        self.current.append(" ".join(commands))

    def line(
        self,
        *,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: tuple[int, int, int] = PDF_RULE,
        line_width: float = 0.45,
    ) -> None:
        self.current.append(
            "q "
            f"{_pdf_color(color)} RG {_pdf_number(line_width)} w "
            f"{_pdf_number(x1)} {_pdf_number(y1)} m "
            f"{_pdf_number(x2)} {_pdf_number(y2)} l S Q"
        )


@dataclass(frozen=True, slots=True)
class _DocumentTocEntry:
    title: str
    page_number: int
    level: int


def _pdf_wrap_text(
    text: str,
    *,
    width: float = PDF_CONTENT_WIDTH,
    font_size: float = 8.3,
    max_lines: int | None = None,
) -> list[str]:
    capacity = max(12, int(width / (font_size * 0.49)))
    lines = textwrap.wrap(
        " ".join(str(text).split()),
        width=capacity,
        break_long_words=True,
        replace_whitespace=True,
    ) or [""]
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        lines[-1] = last[: max(1, capacity - 3)].rstrip() + "..."
    return lines


def _pdf_page_header(
    canvas: _PdfDocumentCanvas,
    *,
    document_title: str,
    compact: bool = False,
) -> float:
    y = PDF_PAGE_HEIGHT - PDF_MARGIN_TOP
    canvas.rect(x=PDF_MARGIN_X, y=y - 23, width=23, height=23, fill=PDF_PRIMARY)
    canvas.text(
        x=PDF_MARGIN_X + 7.1,
        y=y - 16.1,
        text="B",
        size=13.2,
        font="F2",
        color=(255, 255, 255),
    )
    canvas.text(
        x=PDF_MARGIN_X + 32,
        y=y - 7.5,
        text=str(settings.PLATFORM_BRAND_NAME),
        size=11.8,
        font="F2",
    )
    canvas.text(
        x=PDF_MARGIN_X + 32,
        y=y - 20.5,
        text=f"by {settings.LEGAL_OPERATOR_NAME}",
        size=6.8,
        color=PDF_MUTED,
    )
    heading = document_title if len(document_title) <= 64 else f"{document_title[:61]}..."
    canvas.text(
        x=PDF_PAGE_WIDTH - PDF_MARGIN_X - 254,
        y=y - 8.5,
        text=heading,
        size=7.2 if compact else 8.2,
        font="F2",
        color=PDF_PRIMARY,
    )
    canvas.line(x1=PDF_MARGIN_X, y1=y - 32, x2=PDF_PAGE_WIDTH - PDF_MARGIN_X, y2=y - 32)
    return y - (49 if compact else 56)


def _pdf_footer(
    canvas: _PdfDocumentCanvas,
    *,
    page_number: int,
    page_count: int,
    acceptance_id: str,
) -> None:
    footer_y = 23.0
    canvas.line(
        x1=PDF_MARGIN_X,
        y1=footer_y + 14,
        x2=PDF_PAGE_WIDTH - PDF_MARGIN_X,
        y2=footer_y + 14,
    )
    canvas.text(
        x=PDF_MARGIN_X,
        y=footer_y,
        text=f"BANXUM accepted-document artifact. Acceptance {acceptance_id}.",
        size=6.3,
        color=PDF_MUTED,
    )
    canvas.text(
        x=PDF_PAGE_WIDTH - PDF_MARGIN_X - 66,
        y=footer_y,
        text=f"Page {page_number} of {page_count}",
        size=6.3,
        color=PDF_MUTED,
    )


def _pdf_ensure_space(
    canvas: _PdfDocumentCanvas,
    *,
    y: float,
    required_height: float,
    document_title: str,
) -> float:
    if y - required_height >= PDF_BODY_BOTTOM:
        return y
    canvas.new_page()
    return _pdf_page_header(canvas, document_title=document_title, compact=True)


def _pdf_draw_wrapped_text(
    canvas: _PdfDocumentCanvas,
    *,
    y: float,
    text: str,
    document_title: str,
    x: float = PDF_MARGIN_X,
    width: float = PDF_CONTENT_WIDTH,
    size: float = 8.3,
    line_height: float = 11.1,
    font: str = "F1",
    color: tuple[int, int, int] = PDF_PRIMARY_DARK,
    before: float = 0,
    after: float = 7.0,
) -> float:
    lines = _pdf_wrap_text(text, width=width, font_size=size)
    y = _pdf_ensure_space(
        canvas,
        y=y - before,
        required_height=(len(lines) * line_height) + after,
        document_title=document_title,
    )
    current_y = y
    for line in lines:
        canvas.text(x=x, y=current_y, text=line, size=size, font=font, color=color)
        current_y -= line_height
    return current_y - after


def _table_rows_from_block(block: str) -> list[list[str]]:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines or lines[0].lower() != "table:":
        return []
    rows: list[list[str]] = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) > 1 and any(cells):
            rows.append(cells)
    if not rows:
        return []
    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows]


def _pdf_table_widths(column_count: int) -> list[float]:
    if column_count == 2:
        return [PDF_CONTENT_WIDTH * 0.23, PDF_CONTENT_WIDTH * 0.77]
    if column_count == 3:
        return [PDF_CONTENT_WIDTH * 0.23, PDF_CONTENT_WIDTH * 0.32, PDF_CONTENT_WIDTH * 0.45]
    if column_count == 4:
        return [
            PDF_CONTENT_WIDTH * 0.22,
            PDF_CONTENT_WIDTH * 0.20,
            PDF_CONTENT_WIDTH * 0.28,
            PDF_CONTENT_WIDTH * 0.30,
        ]
    if column_count == 5:
        return [
            PDF_CONTENT_WIDTH * 0.21,
            PDF_CONTENT_WIDTH * 0.15,
            PDF_CONTENT_WIDTH * 0.20,
            PDF_CONTENT_WIDTH * 0.25,
            PDF_CONTENT_WIDTH * 0.19,
        ]
    return [PDF_CONTENT_WIDTH / max(1, column_count)] * column_count


def _pdf_cell_lines(
    *,
    text: str,
    width: float,
    font_size: float,
) -> list[str]:
    return _pdf_wrap_text(text, width=max(10.0, width - 9.0), font_size=font_size)


def _pdf_draw_table_row(
    canvas: _PdfDocumentCanvas,
    *,
    y: float,
    row: list[str],
    widths: list[float],
    row_height: float,
    cell_lines: list[list[str]],
    header: bool,
    alternate: bool,
    font_size: float,
    line_height: float,
) -> None:
    fill = (
        PDF_TABLE_HEADER_FILL
        if header
        else (PDF_TABLE_ALT_FILL if alternate else (255, 255, 255))
    )
    canvas.rect(
        x=PDF_MARGIN_X,
        y=y - row_height,
        width=PDF_CONTENT_WIDTH,
        height=row_height,
        fill=fill,
        stroke=PDF_RULE,
        line_width=0.35,
    )
    current_x = PDF_MARGIN_X
    for index, (_cell, width, lines) in enumerate(zip(row, widths, cell_lines, strict=True)):
        if index > 0:
            canvas.line(
                x1=current_x,
                y1=y,
                x2=current_x,
                y2=y - row_height,
                color=PDF_RULE,
                line_width=0.3,
            )
        text_y = y - 11.0
        font = "F2" if header else "F1"
        color = PDF_PRIMARY if header else PDF_PRIMARY_DARK
        for line in lines:
            canvas.text(
                x=current_x + 4.5,
                y=text_y,
                text=line,
                size=font_size,
                font=font,
                color=color,
            )
            text_y -= line_height
        current_x += width


def _pdf_draw_table(
    canvas: _PdfDocumentCanvas,
    *,
    y: float,
    rows: list[list[str]],
    document_title: str,
) -> float:
    if not rows:
        return y
    column_count = max(len(row) for row in rows)
    rows = [row + [""] * (column_count - len(row)) for row in rows]
    widths = _pdf_table_widths(column_count)
    font_size = 6.6 if column_count >= 4 else 7.1
    line_height = 8.7 if column_count >= 4 else 9.4
    header_row = rows[0]

    y = _pdf_ensure_space(canvas, y=y - 2, required_height=42, document_title=document_title)
    for row_index, row in enumerate(rows):
        header = row_index == 0
        if row_index > 0 and y - 28 < PDF_BODY_BOTTOM:
            canvas.new_page()
            y = _pdf_page_header(canvas, document_title=document_title, compact=True)
            header_lines = [
                _pdf_cell_lines(text=cell, width=width, font_size=font_size)
                for cell, width in zip(header_row, widths, strict=True)
            ]
            header_height = max(21.0, max(len(lines) for lines in header_lines) * line_height + 9.0)
            _pdf_draw_table_row(
                canvas,
                y=y,
                row=header_row,
                widths=widths,
                row_height=header_height,
                cell_lines=header_lines,
                header=True,
                alternate=False,
                font_size=font_size,
                line_height=line_height,
            )
            y -= header_height
            header = False
        cell_lines = [
            _pdf_cell_lines(text=cell, width=width, font_size=font_size)
            for cell, width in zip(row, widths, strict=True)
        ]
        row_height = max(21.0, max(len(lines) for lines in cell_lines) * line_height + 9.0)
        y = _pdf_ensure_space(
            canvas,
            y=y,
            required_height=row_height,
            document_title=document_title,
        )
        _pdf_draw_table_row(
            canvas,
            y=y,
            row=row,
            widths=widths,
            row_height=row_height,
            cell_lines=cell_lines,
            header=header,
            alternate=row_index % 2 == 0,
            font_size=font_size,
            line_height=line_height,
        )
        y -= row_height
    return y - 12


def _document_heading_level(text: str) -> int | None:
    cleaned = " ".join(text.strip().split())
    if cleaned in {"Main Agreement", "Document Structure and One-Click Acceptance"}:
        return 1
    if re.match(r"^Annex\s+\d+\b", cleaned, flags=re.I):
        return 1
    if re.match(r"^\d{1,2}\.\s+\S", cleaned):
        return 2
    return None


def _pdf_draw_body_block(
    canvas: _PdfDocumentCanvas,
    *,
    y: float,
    block: str,
    document_title: str,
) -> tuple[float, int | None]:
    cleaned = block.strip()
    rows = _table_rows_from_block(cleaned)
    if rows:
        return _pdf_draw_table(canvas, y=y, rows=rows, document_title=document_title), None

    heading_level = _document_heading_level(cleaned)
    if heading_level == 1:
        y = _pdf_ensure_space(canvas, y=y - 4, required_height=35, document_title=document_title)
        canvas.text(x=PDF_MARGIN_X, y=y, text=cleaned, size=12.3, font="F2", color=PDF_PRIMARY)
        canvas.line(x1=PDF_MARGIN_X, y1=y - 7, x2=PDF_PAGE_WIDTH - PDF_MARGIN_X, y2=y - 7)
        return y - 23, heading_level
    if heading_level == 2:
        y = _pdf_ensure_space(canvas, y=y - 3, required_height=25, document_title=document_title)
        canvas.text(x=PDF_MARGIN_X, y=y, text=cleaned, size=10.2, font="F2", color=PDF_PRIMARY_DARK)
        return y - 17, heading_level
    if cleaned == str(settings.LEGAL_OPERATOR_NAME).upper():
        return (
            _pdf_draw_wrapped_text(
                canvas,
                y=y,
                text=cleaned,
                document_title=document_title,
                size=7.4,
                line_height=9.5,
                font="F2",
                color=PDF_PRIMARY,
                after=5,
            ),
            None,
        )
    if cleaned == document_title:
        return (
            _pdf_draw_wrapped_text(
                canvas,
                y=y,
                text=cleaned,
                document_title=document_title,
                size=14.2,
                line_height=16.0,
                font="F2",
                color=PDF_PRIMARY_DARK,
                after=8,
            ),
            None,
        )
    return (
        _pdf_draw_wrapped_text(
            canvas,
            y=y,
            text=cleaned,
            document_title=document_title,
        ),
        None,
    )


def _pdf_key_value_box(
    canvas: _PdfDocumentCanvas,
    *,
    x: float,
    y: float,
    width: float,
    title: str,
    items: list[tuple[str, str]],
) -> float:
    line_height = 12.0
    height = 28 + (len(items) * line_height)
    canvas.rect(
        x=x,
        y=y - height,
        width=width,
        height=height,
        fill=PDF_TABLE_ALT_FILL,
        stroke=PDF_RULE,
    )
    canvas.text(x=x + 10, y=y - 15, text=title, size=7.8, font="F2", color=PDF_PRIMARY)
    current_y = y - 31
    for label, value in items:
        canvas.text(x=x + 10, y=current_y, text=label, size=6.7, color=PDF_MUTED)
        for line_index, line in enumerate(
            _pdf_wrap_text(value, width=width - 116, font_size=6.8, max_lines=1)
        ):
            canvas.text(
                x=x + 96,
                y=current_y - (line_index * 8.5),
                text=line,
                size=6.8,
                font="F2",
                color=PDF_PRIMARY_DARK,
            )
        current_y -= line_height
    return y - height


def _render_acceptance_cover_page(
    canvas: _PdfDocumentCanvas,
    *,
    acceptance: DocumentAcceptanceEvidence,
    document_title: str,
) -> None:
    y = _pdf_page_header(canvas, document_title=document_title, compact=False)
    title_lines = _pdf_wrap_text(document_title, width=PDF_CONTENT_WIDTH, font_size=17.2)
    title_y = y
    for line in title_lines:
        canvas.text(x=PDF_MARGIN_X, y=title_y, text=line, size=17.2, font="F2")
        title_y -= 19.0
    canvas.text(
        x=PDF_MARGIN_X,
        y=title_y - 2,
        text="Accepted document evidence package",
        size=10.5,
        color=PDF_MUTED,
    )
    y = title_y - 35
    snapshot = acceptance.data_snapshot if isinstance(acceptance.data_snapshot, dict) else {}
    raw_user_snapshot = snapshot.get("user")
    user_snapshot: dict[str, Any] = raw_user_snapshot if isinstance(raw_user_snapshot, dict) else {}
    left_y = _pdf_key_value_box(
        canvas,
        x=PDF_MARGIN_X,
        y=y,
        width=(PDF_CONTENT_WIDTH - 14) / 2,
        title="Accepted by",
        items=[
            ("Name", str(user_snapshot.get("full_name") or "Unavailable")),
            ("Email", str(user_snapshot.get("email") or "Unavailable")),
            ("Account", str(user_snapshot.get("account_type") or "Unavailable")),
            ("Accepted", acceptance.accepted_at.isoformat()),
        ],
    )
    right_y = _pdf_key_value_box(
        canvas,
        x=PDF_MARGIN_X + ((PDF_CONTENT_WIDTH - 14) / 2) + 14,
        y=y,
        width=(PDF_CONTENT_WIDTH - 14) / 2,
        title="Evidence",
        items=[
            ("Acceptance", str(acceptance.id)),
            ("Category", acceptance.category),
            ("Version", str(acceptance.template_version_number)),
            ("Hash", acceptance.template_hash[:28] + "..."),
        ],
    )
    y = min(left_y, right_y) - 20
    canvas.rect(
        x=PDF_MARGIN_X,
        y=y - 86,
        width=PDF_CONTENT_WIDTH,
        height=86,
        fill=PDF_INFO_FILL,
        stroke=PDF_RULE,
    )
    canvas.text(x=PDF_MARGIN_X + 12, y=y - 17, text="Source of truth", size=8.4, font="F2")
    note = (
        "This PDF is generated from immutable BANXUM clickwrap evidence: the accepted template "
        "version, content hash, server-owned user/operator snapshot, accepted checkbox labels, "
        "context and timestamp. It is a presentation artifact; the recorded evidence remains "
        "authoritative."
    )
    text_y = y - 33
    for line in _pdf_wrap_text(note, width=PDF_CONTENT_WIDTH - 24, font_size=7.4):
        canvas.text(x=PDF_MARGIN_X + 12, y=text_y, text=line, size=7.4)
        text_y -= 9.8
    y -= 112
    canvas.text(
        x=PDF_MARGIN_X,
        y=y,
        text="Accepted checkboxes",
        size=9.0,
        font="F2",
        color=PDF_PRIMARY,
    )
    y -= 15
    for label in acceptance.accepted_checkbox_labels:
        y = _pdf_draw_wrapped_text(
            canvas,
            y=y,
            text=f"- {label}",
            document_title=document_title,
            x=PDF_MARGIN_X + 8,
            width=PDF_CONTENT_WIDTH - 8,
            size=7.6,
            line_height=10.0,
            after=4,
        )


def _render_acceptance_toc_page(
    canvas: _PdfDocumentCanvas,
    *,
    document_title: str,
    toc_entries: list[_DocumentTocEntry],
) -> None:
    canvas.new_page()
    y = _pdf_page_header(canvas, document_title=document_title, compact=False)
    canvas.text(x=PDF_MARGIN_X, y=y, text="Table of contents", size=17, font="F2")
    y -= 29
    if not toc_entries:
        canvas.text(
            x=PDF_MARGIN_X,
            y=y,
            text="No section headings detected.",
            size=8.2,
            color=PDF_MUTED,
        )
        return
    for entry in toc_entries[:42]:
        indent = 13.0 if entry.level > 1 else 0.0
        size = 7.6 if entry.level > 1 else 8.1
        font = "F1" if entry.level > 1 else "F2"
        title_lines = _pdf_wrap_text(
            entry.title,
            width=PDF_CONTENT_WIDTH - indent - 42,
            font_size=size,
            max_lines=1,
        )
        canvas.text(x=PDF_MARGIN_X + indent, y=y, text=title_lines[0], size=size, font=font)
        canvas.text(
            x=PDF_PAGE_WIDTH - PDF_MARGIN_X - 18,
            y=y,
            text=str(entry.page_number),
            size=size,
            font=font,
            color=PDF_MUTED,
        )
        y -= 13.0
        if y < PDF_BODY_BOTTOM + 15:
            canvas.text(
                x=PDF_MARGIN_X,
                y=y,
                text="Additional sub-sections continue in the document body.",
                size=7.1,
                color=PDF_MUTED,
            )
            break


def _render_acceptance_body_pages(
    *,
    acceptance: DocumentAcceptanceEvidence,
    rendered_body: str,
    document_title: str,
    page_offset: int,
) -> tuple[list[list[str]], list[_DocumentTocEntry]]:
    body_canvas = _PdfDocumentCanvas()
    y = _pdf_page_header(body_canvas, document_title=document_title, compact=True)
    toc_entries: list[_DocumentTocEntry] = []
    for raw_block in rendered_body.split("\n\n"):
        block = raw_block.strip()
        if not block:
            continue
        page_before = len(body_canvas.pages) + page_offset
        y, heading_level = _pdf_draw_body_block(
            body_canvas,
            y=y,
            block=block,
            document_title=document_title,
        )
        if heading_level is not None:
            toc_entries.append(
                _DocumentTocEntry(
                    title=" ".join(block.split()),
                    page_number=page_before,
                    level=heading_level,
                )
            )
    y = _pdf_ensure_space(body_canvas, y=y, required_height=150, document_title=document_title)
    canvas = body_canvas
    canvas.text(
        x=PDF_MARGIN_X,
        y=y,
        text="Acceptance evidence",
        size=12.0,
        font="F2",
        color=PDF_PRIMARY,
    )
    y -= 18
    evidence_rows = [
        ["Field", "Value"],
        ["Platform", str(settings.PLATFORM_BRAND_NAME)],
        ["Operator", str(settings.LEGAL_OPERATOR_NAME)],
        ["Acceptance ID", str(acceptance.id)],
        ["User ID", str(acceptance.user_id)],
        ["Context", f"{acceptance.context_type}:{acceptance.context_id}"],
        ["Accepted at", acceptance.accepted_at.isoformat()],
        ["Template version ID", str(acceptance.template_version_id)],
        ["Template hash", acceptance.template_hash],
        ["Renderer", DOCUMENT_ARTIFACT_RENDERER_VERSION],
    ]
    _pdf_draw_table(canvas, y=y, rows=evidence_rows, document_title=document_title)
    return body_canvas.pages, toc_entries


def _pdf_canvas_bytes(canvas: _PdfDocumentCanvas) -> bytes:
    objects: dict[int, bytes] = {}
    page_object_ids: list[int] = []
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"
    objects[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"

    next_id = 6
    for page_commands in canvas.pages:
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        page_object_ids.append(page_id)
        content = "\n".join(page_commands).encode("latin-1", errors="replace")
        objects[content_id] = (
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream"
        )
        objects[page_id] = (
            (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {int(PDF_PAGE_WIDTH)} {int(PDF_PAGE_HEIGHT)}] "
            ).encode("ascii")
            + (
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
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


def _acceptance_pdf_bytes(
    *,
    acceptance: DocumentAcceptanceEvidence,
    rendered_body: str,
) -> bytes:
    document_title = acceptance.template_version.title
    body_pages, toc_entries = _render_acceptance_body_pages(
        acceptance=acceptance,
        rendered_body=rendered_body,
        document_title=document_title,
        page_offset=2,
    )
    canvas = _PdfDocumentCanvas()
    _render_acceptance_cover_page(canvas, acceptance=acceptance, document_title=document_title)
    _render_acceptance_toc_page(canvas, document_title=document_title, toc_entries=toc_entries)
    canvas.pages.extend(body_pages)
    page_count = len(canvas.pages)
    for page_number in range(1, page_count + 1):
        _pdf_footer(
            canvas,
            page_number=page_number,
            page_count=page_count,
            acceptance_id=str(acceptance.id),
        )
    return _pdf_canvas_bytes(canvas)


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
    snapshot = acceptance.data_snapshot if isinstance(acceptance.data_snapshot, dict) else {}
    raw_user_snapshot = snapshot.get("user")
    user_snapshot: dict[str, Any] = raw_user_snapshot if isinstance(raw_user_snapshot, dict) else {}
    accepted_by = str(user_snapshot.get("full_name") or "").strip()
    accepted_email = str(user_snapshot.get("email") or "").strip()
    accepted_account_type = str(user_snapshot.get("account_type") or "").strip()
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
        f"Accepted by: {accepted_by or 'Unavailable'}",
        f"Accepted email: {accepted_email or 'Unavailable'}",
        f"Accepted account type: {accepted_account_type or 'Unavailable'}",
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


def _enqueue_acceptance_pdf_email(
    *,
    acceptance: DocumentAcceptanceEvidence,
    actor: Model,
) -> None:
    recipient_email = str(getattr(actor, "email", "") or "").strip().lower()
    if not recipient_email:
        return
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"document-acceptance:{acceptance.id}:email-pdf",
            topic=DOCUMENT_ACCEPTANCE_EMAIL_TOPIC,
            payload={
                "acceptance_id": str(acceptance.id),
                "user_id": str(acceptance.user_id),
                "email": recipient_email,
                "category": acceptance.category,
                "template_id": str(acceptance.template_id),
                "template_version_id": str(acceptance.template_version_id),
                "template_version_number": acceptance.template_version_number,
                "template_hash": acceptance.template_hash,
                "template_title": acceptance.template_version.title,
                "context_type": acceptance.context_type,
                "context_id": acceptance.context_id,
                "accepted_at": acceptance.accepted_at.isoformat(),
            },
        )
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
    data_snapshot = _acceptance_data_snapshot(
        command.actor,
        raw_data_snapshot,
        category=category,
        context_type=context_type,
        context_id=context_id,
    )
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
    _enqueue_acceptance_pdf_email(acceptance=acceptance, actor=command.actor)
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
        pdf_bytes = _acceptance_pdf_bytes(acceptance=acceptance, rendered_body=rendered_body)
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
