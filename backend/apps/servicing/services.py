from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model, Sum

from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.money import (
    Money,
    MoneyError,
    allocate_by_weights,
    normalize_currency,
)
from backend.apps.platform_core.domain.time import business_timezone, now_utc
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    record_domain_event,
)
from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    BorrowerRepaymentEventType,
    InvestorLossRecognitionLine,
    InvestorRecoveryDistributionLine,
    InvestorRepaymentDistributionLine,
    LoanRecoveryEvent,
    LoanRiskNote,
    LoanRiskNoteType,
    LoanRiskNoteVisibility,
    LoanWriteOffEvent,
)


class ServicingError(ValueError):
    pass


class ServicingAuthorizationError(ServicingError):
    pass


class ServicingValidationError(ServicingError):
    pass


MAX_IDEMPOTENCY_KEY_LENGTH = 160
REQUEST_FINGERPRINT_METADATA_KEY = "request_fingerprint"
LOAN_STATUS_FUNDED = "funded"
LOAN_STATUS_LATE = "late"
LOAN_STATUS_DEFAULTED = "defaulted"
LOAN_STATUS_REPAID = "repaid"
LOAN_STATUS_WRITTEN_OFF = "written_off"
REPAYMENT_ALLOWED_LOAN_STATUSES = {LOAN_STATUS_FUNDED, LOAN_STATUS_LATE}
STATUS_SCAN_LOAN_STATUSES = {LOAN_STATUS_FUNDED, LOAN_STATUS_LATE}
RECOVERY_ALLOWED_LOAN_STATUSES = {LOAN_STATUS_DEFAULTED}
LATE_THRESHOLD_DAYS = 5
DEFAULT_THRESHOLD_DAYS = 16
PUBLIC_NOTE_LOAN_STATUSES = {
    LOAN_STATUS_FUNDED,
    LOAN_STATUS_LATE,
    LOAN_STATUS_DEFAULTED,
    LOAN_STATUS_REPAID,
    LOAN_STATUS_WRITTEN_OFF,
}


def _investor_email_for_user_id(investor_user_id: str) -> str:
    user_model = apps.get_model("accounts_auth", "User")
    user = user_model.objects.filter(id=investor_user_id).only("email").first()
    return str(getattr(user, "email", "")).strip().lower() if user is not None else ""


def _enqueue_investor_email(
    *,
    investor_user_id: str,
    topic: str,
    subject: str,
    body_text: str,
    template_key: str,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> None:
    email = _investor_email_for_user_id(investor_user_id)
    if not email:
        return
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=idempotency_key,
            topic=topic,
            payload={
                "user_id": investor_user_id,
                "email": email,
                "subject": subject,
                "body_text": body_text,
                "template_key": template_key,
                "metadata": metadata,
            },
        )
    )


@dataclass(frozen=True, slots=True)
class RecordBorrowerRepaymentCommand:
    actor: Model
    loan_id: str
    amount_minor: int
    booking_date: date
    value_date: date
    collection_account_identifier: str
    payer_name: str
    payer_account_identifier: str = ""
    bank_reference: str = ""
    payment_reference: str = ""
    evidence_reference: str = ""
    admin_notes: str = ""
    warning_acknowledged: bool = False
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class ServicingDistributionPlanLine:
    holding: Model
    investor_user_id: str
    principal_minor: int
    interest_minor: int
    amount_minor: int
    current_principal_before_minor: int
    current_principal_after_minor: int


@dataclass(frozen=True, slots=True)
class RecoveryDistributionPlanLine:
    holding: Model
    investor_user_id: str
    principal_minor: int
    contractual_interest_minor: int
    default_interest_minor: int
    penalties_minor: int
    other_costs_minor: int
    amount_minor: int
    current_principal_before_minor: int
    current_principal_after_minor: int


@dataclass(frozen=True, slots=True)
class LossRecognitionPlanLine:
    holding: Model
    investor_user_id: str
    principal_loss_minor: int
    contractual_interest_loss_minor: int
    default_interest_loss_minor: int
    fees_loss_minor: int
    penalties_loss_minor: int
    total_loss_minor: int
    current_principal_before_minor: int
    current_principal_after_minor: int


@dataclass(frozen=True, slots=True)
class RecordBorrowerRepaymentResult:
    repayment_event: BorrowerRepaymentEvent
    distribution_lines: list[InvestorRepaymentDistributionLine]


@dataclass(frozen=True, slots=True)
class RecordLoanRecoveryPaymentCommand:
    actor: Model
    loan_id: str
    gross_recovered_minor: int
    externally_deducted_costs_minor: int
    third_party_costs_from_received_minor: int
    recovery_fee_applied: bool
    recovery_fee_bps: int
    principal_recovered_minor: int
    contractual_interest_recovered_minor: int
    default_interest_recovered_minor: int
    penalties_recovered_minor: int
    other_costs_recovered_minor: int
    booking_date: date
    value_date: date
    collection_account_identifier: str
    payer_name: str
    payer_account_identifier: str = ""
    bank_reference: str = ""
    payment_reference: str = ""
    evidence_reference: str = ""
    notes: str = ""
    recovery_waterfall_config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class RecordLoanRecoveryPaymentResult:
    recovery_event: LoanRecoveryEvent
    distribution_lines: list[InvestorRecoveryDistributionLine]


@dataclass(frozen=True, slots=True)
class ScanLoanServicingStatusesCommand:
    actor: Model
    as_of_date: date
    loan_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LoanServicingStatusChange:
    loan_id: str
    previous_status: str
    new_status: str
    days_past_due: int
    outstanding_minor: int
    triggering_installment_id: str
    triggering_due_date: date | None


@dataclass(frozen=True, slots=True)
class LoanServicingStatusSnapshot:
    loan_id: str
    status: str
    days_past_due: int
    outstanding_minor: int
    triggering_installment_id: str
    triggering_due_date: date | None


@dataclass(frozen=True, slots=True)
class ScanLoanServicingStatusesResult:
    as_of_date: date
    changes: list[LoanServicingStatusChange]


@dataclass(frozen=True, slots=True)
class AddLoanRiskNoteCommand:
    actor: Model
    loan_id: str
    visibility: str
    note_type: str
    body: str
    idempotency_key: str
    title: str = ""
    evidence_reference: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RecordLoanWriteOffCommand:
    actor: Model
    loan_id: str
    written_off_principal_minor: int
    reason: str
    idempotency_key: str
    written_off_contractual_interest_minor: int = 0
    written_off_default_interest_minor: int = 0
    written_off_fees_minor: int = 0
    written_off_penalties_minor: int = 0
    notes: str = ""
    evidence_reference: str = ""
    metadata: dict[str, Any] | None = None


def _ledger_services() -> Any:
    return import_module("backend.apps.ledger.services")


def _schedule_domain() -> Any:
    return import_module("backend.apps.loans.domain.schedules")


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise ServicingAuthorizationError("Only an active admin can manage servicing.")


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ServicingValidationError(f"{label} is required.")
    return cleaned


def _clean_idempotency_key(value: str) -> str:
    key = _clean_required(value, "Idempotency key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ServicingValidationError(
            f"Idempotency key cannot exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )
    return key


def _stable_json_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _enabled_currency(currency_code: str) -> Currency:
    try:
        code = normalize_currency(currency_code)
    except MoneyError as exc:
        raise ServicingValidationError(str(exc)) from exc
    currency = Currency.objects.filter(code=code, is_enabled=True).first()
    if currency is None:
        raise ServicingValidationError(f"Currency is not enabled: {code}")
    return currency


def _validate_money(amount_minor: int, currency_code: str, label: str) -> int:
    try:
        Money(amount_minor, currency_code)
    except MoneyError as exc:
        raise ServicingValidationError(str(exc)) from exc
    if amount_minor <= 0:
        raise ServicingValidationError(f"{label} must be positive.")
    return amount_minor


def _validate_positive_minor_amount(amount_minor: int, label: str) -> int:
    if type(amount_minor) is not int:
        raise ServicingValidationError(f"{label} must be an integer minor-unit amount.")
    if amount_minor <= 0:
        raise ServicingValidationError(f"{label} must be positive.")
    return amount_minor


def _validate_nonnegative_minor_amount(amount_minor: int, label: str) -> int:
    if type(amount_minor) is not int:
        raise ServicingValidationError(f"{label} must be an integer minor-unit amount.")
    if amount_minor < 0:
        raise ServicingValidationError(f"{label} cannot be negative.")
    return amount_minor


def _fee_from_bps(base_minor: int, bps: int) -> int:
    if type(bps) is not int:
        raise ServicingValidationError("Recovery fee bps must be an integer.")
    if bps < 0:
        raise ServicingValidationError("Recovery fee bps cannot be negative.")
    return int(
        (Decimal(base_minor) * Decimal(bps) / Decimal(10_000)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _loan_model() -> Any:
    return apps.get_model("loans", "Loan")


def _loan_event_model() -> Any:
    return apps.get_model("loans", "LoanEvent")


def _locked_loan(loan_id: str) -> Model:
    loan = cast(
        Model | None,
        _loan_model().objects.select_for_update()
        .select_related("borrower", "currency")
        .filter(id=loan_id)
        .first(),
    )
    if loan is None:
        raise ServicingValidationError("Loan does not exist.")
    return loan


def _received_at_from_value_date(value_date: date) -> datetime:
    return datetime.combine(value_date, time.min, tzinfo=business_timezone())


def _request_fingerprint(
    command: RecordBorrowerRepaymentCommand,
    *,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "amount_minor": amount_minor,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "payer_name": command.payer_name.strip(),
            "payer_account_identifier": command.payer_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "admin_notes": command.admin_notes.strip(),
            "warning_acknowledged": command.warning_acknowledged,
            "idempotency_key": idempotency_key,
        }
    )


def _existing_repayment_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> RecordBorrowerRepaymentResult | None:
    existing = BorrowerRepaymentEvent.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise ServicingValidationError(
            "Idempotency key was already used for a different repayment request."
        )
    return RecordBorrowerRepaymentResult(
        repayment_event=existing,
        distribution_lines=list(existing.distribution_lines.select_related("holding")),
    )


def _recovery_payment_fingerprint(
    command: RecordLoanRecoveryPaymentCommand,
    *,
    gross_recovered_minor: int,
    externally_deducted_costs_minor: int,
    net_received_minor: int,
    third_party_costs_from_received_minor: int,
    recovery_fee_base_minor: int,
    recovery_fee_minor: int,
    net_available_for_distribution_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "gross_recovered_minor": gross_recovered_minor,
            "externally_deducted_costs_minor": externally_deducted_costs_minor,
            "net_received_minor": net_received_minor,
            "third_party_costs_from_received_minor": third_party_costs_from_received_minor,
            "recovery_fee_applied": command.recovery_fee_applied,
            "recovery_fee_bps": command.recovery_fee_bps,
            "recovery_fee_base_minor": recovery_fee_base_minor,
            "recovery_fee_minor": recovery_fee_minor,
            "net_available_for_distribution_minor": net_available_for_distribution_minor,
            "principal_recovered_minor": command.principal_recovered_minor,
            "contractual_interest_recovered_minor": (
                command.contractual_interest_recovered_minor
            ),
            "default_interest_recovered_minor": command.default_interest_recovered_minor,
            "penalties_recovered_minor": command.penalties_recovered_minor,
            "other_costs_recovered_minor": command.other_costs_recovered_minor,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "payer_name": command.payer_name.strip(),
            "payer_account_identifier": command.payer_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "notes": command.notes.strip(),
            "recovery_waterfall_config": command.recovery_waterfall_config or {},
            "metadata": command.metadata or {},
            "idempotency_key": idempotency_key,
        }
    )


def _existing_recovery_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> RecordLoanRecoveryPaymentResult | None:
    existing = LoanRecoveryEvent.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise ServicingValidationError(
            "Idempotency key was already used for a different recovery payment request."
        )
    return RecordLoanRecoveryPaymentResult(
        recovery_event=existing,
        distribution_lines=list(existing.distribution_lines.select_related("holding")),
    )


def _risk_note_fingerprint(
    command: AddLoanRiskNoteCommand,
    *,
    visibility: str,
    note_type: str,
    title: str,
    body: str,
    evidence_reference: str,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "visibility": visibility,
            "note_type": note_type,
            "title": title,
            "body": body,
            "evidence_reference": evidence_reference,
            "metadata": command.metadata or {},
            "idempotency_key": idempotency_key,
        }
    )


def _existing_risk_note_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> LoanRiskNote | None:
    existing = LoanRiskNote.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise ServicingValidationError(
            "Idempotency key was already used for a different risk-note request."
        )
    return cast(LoanRiskNote, existing)


def _write_off_fingerprint(
    command: RecordLoanWriteOffCommand,
    *,
    currency_code: str,
    principal_minor: int,
    contractual_interest_minor: int,
    default_interest_minor: int,
    fees_minor: int,
    penalties_minor: int,
    total_minor: int,
    reason: str,
    notes: str,
    evidence_reference: str,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "currency": currency_code,
            "written_off_principal_minor": principal_minor,
            "written_off_contractual_interest_minor": contractual_interest_minor,
            "written_off_default_interest_minor": default_interest_minor,
            "written_off_fees_minor": fees_minor,
            "written_off_penalties_minor": penalties_minor,
            "total_written_off_minor": total_minor,
            "reason": reason,
            "notes": notes,
            "evidence_reference": evidence_reference,
            "metadata": command.metadata or {},
            "idempotency_key": idempotency_key,
        }
    )


def _existing_write_off_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> LoanWriteOffEvent | None:
    existing = LoanWriteOffEvent.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise ServicingValidationError(
            "Idempotency key was already used for a different write-off request."
        )
    return cast(LoanWriteOffEvent, existing)


def _locked_repayable_loan(loan_id: str) -> Model:
    loan = _locked_loan(loan_id)
    loan_ref = cast(Any, loan)
    status = str(loan_ref.status)
    if status == LOAN_STATUS_DEFAULTED:
        raise ServicingValidationError(
            "Defaulted loans must be handled through the recovery workflow."
        )
    if status not in REPAYMENT_ALLOWED_LOAN_STATUSES:
        raise ServicingValidationError("Loan must be funded or late before borrower repayment.")
    if not bool(getattr(loan_ref.borrower, "can_transact", False)):
        raise ServicingValidationError(
            "Borrower KYB must be approved and free of compliance hold."
        )
    return loan


def _installment_paid_totals(installment: Model) -> tuple[int, int]:
    installment_ref = cast(Any, installment)
    aggregate = BorrowerRepaymentEvent.objects.filter(
        loan_id=installment_ref.loan_id,
        installment__installment_number=installment_ref.installment_number,
    ).aggregate(
        principal=Sum("principal_applied_minor"),
        interest=Sum("interest_applied_minor"),
    )
    return int(aggregate["principal"] or 0), int(aggregate["interest"] or 0)


def _first_outstanding_installment_status(
    loan: Model,
    *,
    as_of_date: date,
    lock_installments: bool = True,
) -> tuple[str, int, int, Model | None]:
    loan_ref = cast(Any, loan)
    installment_model = apps.get_model("loans", "LoanInstallment")
    installments = installment_model.objects.filter(
        loan=loan,
        schedule_version=loan_ref.schedule_version,
    ).order_by("due_date", "installment_number", "id")
    if lock_installments:
        installments = installments.select_for_update()
    for installment in installments:
        principal_paid, interest_paid = _installment_paid_totals(cast(Model, installment))
        remaining_principal = int(installment.principal_minor) - principal_paid
        remaining_interest = int(installment.interest_minor) - interest_paid
        if remaining_principal < 0 or remaining_interest < 0:
            raise ServicingValidationError("Installment payment totals exceed scheduled amounts.")
        outstanding = remaining_principal + remaining_interest
        if outstanding <= 0:
            continue
        days_past_due = max(0, (as_of_date - installment.due_date).days)
        if days_past_due >= DEFAULT_THRESHOLD_DAYS:
            return LOAN_STATUS_DEFAULTED, days_past_due, outstanding, cast(Model, installment)
        if days_past_due >= LATE_THRESHOLD_DAYS:
            return LOAN_STATUS_LATE, days_past_due, outstanding, cast(Model, installment)
        return LOAN_STATUS_FUNDED, days_past_due, outstanding, cast(Model, installment)
    return LOAN_STATUS_REPAID, 0, 0, None


def get_loan_servicing_status_snapshot(
    *,
    loan: Model,
    as_of_date: date,
) -> LoanServicingStatusSnapshot:
    status, days_past_due, outstanding, installment = _first_outstanding_installment_status(
        loan,
        as_of_date=as_of_date,
        lock_installments=False,
    )
    installment_ref = cast(Any, installment) if installment is not None else None
    return LoanServicingStatusSnapshot(
        loan_id=str(cast(Any, loan).pk),
        status=status,
        days_past_due=days_past_due,
        outstanding_minor=outstanding,
        triggering_installment_id=str(installment_ref.pk) if installment_ref is not None else "",
        triggering_due_date=cast(date, installment_ref.due_date)
        if installment_ref is not None
        else None,
    )


def _record_loan_servicing_status_change(
    *,
    loan: Model,
    actor: Model,
    new_status: str,
    as_of_date: date,
    days_past_due: int,
    outstanding_minor: int,
    triggering_installment: Model | None,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> LoanServicingStatusChange | None:
    loan_ref = cast(Any, loan)
    previous_status = str(loan_ref.status)
    if previous_status == new_status:
        return None
    loan_ref.status = new_status
    loan_ref.updated_by_admin_id = actor.pk
    loan.save(update_fields=["status", "updated_by_admin_id", "updated_at"])
    triggering_installment_id = (
        str(cast(Any, triggering_installment).id) if triggering_installment is not None else ""
    )
    triggering_due_date = (
        cast(date, cast(Any, triggering_installment).due_date)
        if triggering_installment is not None
        else None
    )
    event_metadata = {
        "previous_status": previous_status,
        "new_status": new_status,
        "as_of_date": as_of_date.isoformat(),
        "days_past_due": days_past_due,
        "outstanding_minor": outstanding_minor,
        "triggering_installment_id": triggering_installment_id,
        "triggering_due_date": triggering_due_date.isoformat()
        if triggering_due_date is not None
        else "",
        "reason": reason,
        **(metadata or {}),
    }
    event_model = apps.get_model("loans", "LoanEvent")
    event_model.objects.create(
        loan=loan,
        event_type="servicing_status_changed",
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        previous_status=previous_status,
        new_status=new_status,
        note=f"Loan servicing status changed to {new_status}.",
        metadata=event_metadata,
    )
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.servicing_status_changed",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanServicingStatusChanged",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=event_metadata,
            idempotency_key=(
                f"loan:{loan_ref.id}:servicing-status:"
                f"{new_status}:{as_of_date.isoformat()}"
            ),
        )
    )
    return LoanServicingStatusChange(
        loan_id=str(loan_ref.id),
        previous_status=previous_status,
        new_status=new_status,
        days_past_due=days_past_due,
        outstanding_minor=outstanding_minor,
        triggering_installment_id=triggering_installment_id,
        triggering_due_date=triggering_due_date,
    )


def _refresh_loan_status_after_repayment(
    *,
    loan: Model,
    actor: Model,
    as_of_date: date,
    repayment_event_id: str,
) -> LoanServicingStatusChange | None:
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) not in {LOAN_STATUS_FUNDED, LOAN_STATUS_LATE}:
        return None
    new_status, days_past_due, outstanding, installment = _first_outstanding_installment_status(
        loan,
        as_of_date=as_of_date,
    )
    if new_status == LOAN_STATUS_DEFAULTED:
        # Repayment recording never escalates a loan into default; the status scanner owns that.
        return None
    return _record_loan_servicing_status_change(
        loan=loan,
        actor=actor,
        new_status=new_status,
        as_of_date=as_of_date,
        days_past_due=days_past_due,
        outstanding_minor=outstanding,
        triggering_installment=installment,
        reason="borrower_repayment",
        metadata={"repayment_event_id": repayment_event_id},
    )


def _next_due_installment(loan: Model) -> tuple[Model, int, int]:
    loan_ref = cast(Any, loan)
    installment_model = apps.get_model("loans", "LoanInstallment")
    installments = installment_model.objects.select_for_update().filter(
        loan=loan,
        schedule_version=loan_ref.schedule_version,
    ).order_by("due_date", "installment_number", "id")
    for installment in installments:
        principal_paid, interest_paid = _installment_paid_totals(cast(Model, installment))
        remaining_principal = int(installment.principal_minor) - principal_paid
        remaining_interest = int(installment.interest_minor) - interest_paid
        if remaining_principal < 0 or remaining_interest < 0:
            raise ServicingValidationError("Installment payment totals exceed scheduled amounts.")
        if remaining_principal + remaining_interest > 0:
            return cast(Model, installment), remaining_principal, remaining_interest
    raise ServicingValidationError("Loan has no outstanding scheduled installment.")


def _active_holdings_for_loan(loan: Model) -> list[Model]:
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    return list(
        holding_model.objects.select_for_update()
        .filter(
            loan=loan,
            status="active",
            current_principal_minor__gt=0,
        )
        .order_by("assignment_effective_at", "created_at", "id")
    )


def _distribution_plan(
    *,
    holdings: list[Model],
    principal_minor: int,
    interest_minor: int,
    currency_code: str,
) -> list[ServicingDistributionPlanLine]:
    if not holdings:
        raise ServicingValidationError("Loan has no active investor holdings.")
    weights = [int(cast(Any, holding).current_principal_minor) for holding in holdings]
    principal_parts = allocate_by_weights(Money(principal_minor, currency_code), weights)
    interest_parts = allocate_by_weights(Money(interest_minor, currency_code), weights)
    plan: list[ServicingDistributionPlanLine] = []
    for holding, principal_part, interest_part in zip(
        holdings,
        principal_parts,
        interest_parts,
        strict=True,
    ):
        holding_ref = cast(Any, holding)
        before = int(holding_ref.current_principal_minor)
        principal_amount = principal_part.amount_minor
        if principal_amount > before:
            raise ServicingValidationError("Distribution principal exceeds holding principal.")
        amount = principal_amount + interest_part.amount_minor
        if amount <= 0:
            continue
        plan.append(
            ServicingDistributionPlanLine(
                holding=holding,
                investor_user_id=str(holding_ref.investor_user_id),
                principal_minor=principal_amount,
                interest_minor=interest_part.amount_minor,
                amount_minor=amount,
                current_principal_before_minor=before,
                current_principal_after_minor=before - principal_amount,
            )
        )
    if sum(line.amount_minor for line in plan) != principal_minor + interest_minor:
        raise ServicingValidationError("Distribution plan does not reconcile to repayment amount.")
    return plan


def _recovery_distribution_plan(
    *,
    holdings: list[Model],
    principal_minor: int,
    contractual_interest_minor: int,
    default_interest_minor: int,
    penalties_minor: int,
    other_costs_minor: int,
    currency_code: str,
) -> list[RecoveryDistributionPlanLine]:
    if not holdings:
        raise ServicingValidationError("Loan has no active investor holdings.")
    weights = [int(cast(Any, holding).current_principal_minor) for holding in holdings]
    if principal_minor > sum(weights):
        raise ServicingValidationError("Recovered principal exceeds current holding principal.")

    category_allocations = {
        "principal": allocate_by_weights(Money(principal_minor, currency_code), weights),
        "contractual_interest": allocate_by_weights(
            Money(contractual_interest_minor, currency_code),
            weights,
        ),
        "default_interest": allocate_by_weights(
            Money(default_interest_minor, currency_code),
            weights,
        ),
        "penalties": allocate_by_weights(Money(penalties_minor, currency_code), weights),
        "other_costs": allocate_by_weights(Money(other_costs_minor, currency_code), weights),
    }
    plan: list[RecoveryDistributionPlanLine] = []
    for index, holding in enumerate(holdings):
        holding_ref = cast(Any, holding)
        before = int(holding_ref.current_principal_minor)
        principal_part = category_allocations["principal"][index].amount_minor
        contractual_interest_part = category_allocations["contractual_interest"][
            index
        ].amount_minor
        default_interest_part = category_allocations["default_interest"][index].amount_minor
        penalties_part = category_allocations["penalties"][index].amount_minor
        other_costs_part = category_allocations["other_costs"][index].amount_minor
        if principal_part > before:
            raise ServicingValidationError("Recovered principal exceeds holding principal.")
        amount = (
            principal_part
            + contractual_interest_part
            + default_interest_part
            + penalties_part
            + other_costs_part
        )
        if amount <= 0:
            continue
        plan.append(
            RecoveryDistributionPlanLine(
                holding=holding,
                investor_user_id=str(holding_ref.investor_user_id),
                principal_minor=principal_part,
                contractual_interest_minor=contractual_interest_part,
                default_interest_minor=default_interest_part,
                penalties_minor=penalties_part,
                other_costs_minor=other_costs_part,
                amount_minor=amount,
                current_principal_before_minor=before,
                current_principal_after_minor=before - principal_part,
            )
        )
    expected = (
        principal_minor
        + contractual_interest_minor
        + default_interest_minor
        + penalties_minor
        + other_costs_minor
    )
    if sum(line.amount_minor for line in plan) != expected:
        raise ServicingValidationError("Recovery distribution plan does not reconcile.")
    return plan


def _loss_recognition_plan(
    *,
    holdings: list[Model],
    principal_loss_minor: int,
    contractual_interest_loss_minor: int,
    default_interest_loss_minor: int,
    fees_loss_minor: int,
    penalties_loss_minor: int,
    currency_code: str,
) -> list[LossRecognitionPlanLine]:
    if not holdings:
        raise ServicingValidationError("Loan has no active investor holdings to loss-recognize.")
    weights = [int(cast(Any, holding).current_principal_minor) for holding in holdings]
    total_current_principal = sum(weights)
    if principal_loss_minor != total_current_principal:
        raise ServicingValidationError(
            "Written-off principal must equal the remaining active holding principal."
        )
    category_allocations = {
        "principal": allocate_by_weights(Money(principal_loss_minor, currency_code), weights),
        "contractual_interest": allocate_by_weights(
            Money(contractual_interest_loss_minor, currency_code),
            weights,
        ),
        "default_interest": allocate_by_weights(
            Money(default_interest_loss_minor, currency_code),
            weights,
        ),
        "fees": allocate_by_weights(Money(fees_loss_minor, currency_code), weights),
        "penalties": allocate_by_weights(Money(penalties_loss_minor, currency_code), weights),
    }
    plan: list[LossRecognitionPlanLine] = []
    for index, holding in enumerate(holdings):
        holding_ref = cast(Any, holding)
        before = int(holding_ref.current_principal_minor)
        principal_part = category_allocations["principal"][index].amount_minor
        contractual_interest_part = category_allocations["contractual_interest"][
            index
        ].amount_minor
        default_interest_part = category_allocations["default_interest"][index].amount_minor
        fees_part = category_allocations["fees"][index].amount_minor
        penalties_part = category_allocations["penalties"][index].amount_minor
        if principal_part != before:
            raise ServicingValidationError(
                "Written-off principal allocation must close every active holding."
            )
        total = (
            principal_part
            + contractual_interest_part
            + default_interest_part
            + fees_part
            + penalties_part
        )
        if total <= 0:
            continue
        plan.append(
            LossRecognitionPlanLine(
                holding=holding,
                investor_user_id=str(holding_ref.investor_user_id),
                principal_loss_minor=principal_part,
                contractual_interest_loss_minor=contractual_interest_part,
                default_interest_loss_minor=default_interest_part,
                fees_loss_minor=fees_part,
                penalties_loss_minor=penalties_part,
                total_loss_minor=total,
                current_principal_before_minor=before,
                current_principal_after_minor=0,
            )
        )
    if sum(line.principal_loss_minor for line in plan) != principal_loss_minor:
        raise ServicingValidationError("Loss principal allocation does not reconcile.")
    if sum(line.total_loss_minor for line in plan) != (
        principal_loss_minor
        + contractual_interest_loss_minor
        + default_interest_loss_minor
        + fees_loss_minor
        + penalties_loss_minor
    ):
        raise ServicingValidationError("Loss recognition plan does not reconcile.")
    return plan


def _actor_has_loan_holding_history(actor: Model, loan_id: str) -> bool:
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    return bool(holding_model.objects.filter(loan_id=loan_id, investor_user_id=actor.pk).exists())


def _validate_visibility(value: str) -> str:
    cleaned = _clean_required(value, "Visibility")
    allowed = {choice.value for choice in LoanRiskNoteVisibility}
    if cleaned not in allowed:
        raise ServicingValidationError("Risk-note visibility is not valid.")
    return cleaned


def _validate_note_type(value: str) -> str:
    cleaned = _clean_required(value, "Note type")
    allowed = {choice.value for choice in LoanRiskNoteType}
    if cleaned not in allowed:
        raise ServicingValidationError("Risk-note type is not valid.")
    return cleaned


def list_admin_loan_risk_notes(
    *,
    actor: Model,
    loan_id: str,
    include_internal: bool = True,
    limit: int = 100,
) -> list[LoanRiskNote]:
    _require_admin_actor(actor)
    safe_limit = min(max(int(limit), 1), 250)
    query = LoanRiskNote.objects.select_related("loan", "loan__currency").filter(loan_id=loan_id)
    if not include_internal:
        query = query.filter(visibility=LoanRiskNoteVisibility.PUBLIC)
    return list(query.order_by("-occurred_at", "-id")[:safe_limit])


def list_public_loan_risk_notes(
    *,
    actor: Model,
    loan_id: str,
    limit: int = 100,
) -> list[LoanRiskNote]:
    if not is_admin_actor(actor):
        if not user_can_access_financial_features(actor):
            raise ServicingAuthorizationError("Investor account cannot view loan risk notes.")
        if not _actor_has_loan_holding_history(actor, loan_id):
            raise ServicingAuthorizationError(
                "Investor can only view public notes for loans they hold or previously held."
            )
    safe_limit = min(max(int(limit), 1), 250)
    return list(
        LoanRiskNote.objects.select_related("loan", "loan__currency")
        .filter(loan_id=loan_id, visibility=LoanRiskNoteVisibility.PUBLIC)
        .order_by("-occurred_at", "-id")[:safe_limit]
    )


def _record_holding_principal_update(
    *,
    holding: Model,
    actor: Model,
    repayment_event: BorrowerRepaymentEvent,
    principal_minor: int,
    before_minor: int,
    after_minor: int,
) -> None:
    if principal_minor <= 0:
        return
    holding_ref = cast(Any, holding)
    previous_status = str(holding_ref.status)
    holding_ref.current_principal_minor = after_minor
    if after_minor == 0:
        holding_ref.status = "closed"
    holding.save(update_fields=["current_principal_minor", "status", "updated_at"])
    event_model = apps.get_model("holdings", "InvestorLoanHoldingEvent")
    event_model.objects.create(
        holding=holding,
        loan_id=holding_ref.loan_id,
        investor_user_id=holding_ref.investor_user_id,
        event_type="closed" if after_minor == 0 else "principal_updated",
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        previous_status=previous_status,
        new_status=str(holding_ref.status),
        note="Borrower repayment principal distribution.",
        metadata={
            "repayment_event_id": str(repayment_event.id),
            "principal_repaid_minor": principal_minor,
            "current_principal_before_minor": before_minor,
            "current_principal_after_minor": after_minor,
        },
    )


def _record_recovery_holding_principal_update(
    *,
    holding: Model,
    actor: Model,
    recovery_event: LoanRecoveryEvent,
    principal_minor: int,
    before_minor: int,
    after_minor: int,
) -> None:
    if principal_minor <= 0:
        return
    holding_ref = cast(Any, holding)
    previous_status = str(holding_ref.status)
    holding_ref.current_principal_minor = after_minor
    if after_minor == 0:
        holding_ref.status = "closed"
    holding.save(update_fields=["current_principal_minor", "status", "updated_at"])
    event_model = apps.get_model("holdings", "InvestorLoanHoldingEvent")
    event_model.objects.create(
        holding=holding,
        loan_id=holding_ref.loan_id,
        investor_user_id=holding_ref.investor_user_id,
        event_type="closed" if after_minor == 0 else "principal_updated",
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        previous_status=previous_status,
        new_status=str(holding_ref.status),
        note="Recovery principal distribution.",
        metadata={
            "recovery_event_id": str(recovery_event.id),
            "principal_recovered_minor": principal_minor,
            "current_principal_before_minor": before_minor,
            "current_principal_after_minor": after_minor,
        },
    )


def _record_loss_holding_principal_update(
    *,
    holding: Model,
    actor: Model,
    write_off_event: LoanWriteOffEvent,
    principal_loss_minor: int,
    before_minor: int,
    after_minor: int,
) -> None:
    holding_ref = cast(Any, holding)
    previous_status = str(holding_ref.status)
    holding_ref.current_principal_minor = after_minor
    holding_ref.status = "closed" if after_minor == 0 else previous_status
    holding.save(update_fields=["current_principal_minor", "status", "updated_at"])
    event_model = apps.get_model("holdings", "InvestorLoanHoldingEvent")
    event_model.objects.create(
        holding=holding,
        loan_id=holding_ref.loan_id,
        investor_user_id=holding_ref.investor_user_id,
        event_type="closed" if after_minor == 0 else "principal_updated",
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        previous_status=previous_status,
        new_status=str(holding_ref.status),
        note="Final default loss recognition.",
        metadata={
            "write_off_event_id": str(write_off_event.id),
            "principal_loss_minor": principal_loss_minor,
            "current_principal_before_minor": before_minor,
            "current_principal_after_minor": after_minor,
        },
    )


def _remaining_schedule_first_due_date(loan: Model, current_installment: Model) -> date:
    loan_ref = cast(Any, loan)
    current_ref = cast(Any, current_installment)
    installment_model = apps.get_model("loans", "LoanInstallment")
    next_installment = installment_model.objects.filter(
        loan=loan,
        schedule_version=loan_ref.schedule_version,
        installment_number=int(current_ref.installment_number) + 1,
    ).first()
    if next_installment is not None:
        return cast(date, next_installment.due_date)
    schedules = _schedule_domain()
    return cast(date, schedules.add_months(cast(date, current_ref.due_date), 1))


def _remaining_schedule_rows_after_early_repayment(
    *,
    loan: Model,
    current_installment: Model,
    remaining_principal_minor: int,
    currency_code: str,
) -> list[Any]:
    if remaining_principal_minor <= 0:
        return []
    loan_ref = cast(Any, loan)
    current_number = int(cast(Any, current_installment).installment_number)
    remaining_term = int(loan_ref.term_months) - current_number
    if remaining_term <= 0:
        return []
    first_due_date = _remaining_schedule_first_due_date(loan, current_installment)
    schedules = _schedule_domain()
    repayment_type = str(loan_ref.repayment_type)
    if repayment_type == "equal_installments":
        rows = schedules.generate_equal_installment_schedule(
            principal_minor=remaining_principal_minor,
            currency=currency_code,
            term_months=remaining_term,
            annual_interest_bps=int(loan_ref.interest_rate_bps),
            first_due_date=first_due_date,
        )
    elif repayment_type == "amortizing_principal_interest":
        rows = schedules.generate_equal_principal_schedule(
            principal_minor=remaining_principal_minor,
            currency=currency_code,
            term_months=remaining_term,
            annual_interest_bps=int(loan_ref.interest_rate_bps),
            first_due_date=first_due_date,
        )
    elif repayment_type in {"bullet_periodic_interest", "interest_only_then_bullet"}:
        rows = schedules.generate_bullet_schedule(
            principal_minor=remaining_principal_minor,
            currency=currency_code,
            term_months=remaining_term,
            annual_interest_bps=int(loan_ref.interest_rate_bps),
            first_due_date=first_due_date,
        )
    elif repayment_type == "interest_only_then_amortizing":
        remaining_interest_only_months = max(
            0,
            int(loan_ref.interest_only_months) - current_number,
        )
        if 0 < remaining_interest_only_months < remaining_term:
            rows = schedules.generate_interest_only_then_amortizing_schedule(
                principal_minor=remaining_principal_minor,
                currency=currency_code,
                term_months=remaining_term,
                annual_interest_bps=int(loan_ref.interest_rate_bps),
                first_due_date=first_due_date,
                interest_only_months=remaining_interest_only_months,
            )
        else:
            rows = schedules.generate_equal_installment_schedule(
                principal_minor=remaining_principal_minor,
                currency=currency_code,
                term_months=remaining_term,
                annual_interest_bps=int(loan_ref.interest_rate_bps),
                first_due_date=first_due_date,
            )
    else:
        raise ServicingValidationError(
            "Early repayment schedule recalculation is not supported for this repayment type."
        )

    schedule_row_type = schedules.ScheduleInstallmentDraft
    return [
        schedule_row_type(
            installment_number=current_number + index,
            due_date=row.due_date,
            principal_minor=row.principal_minor,
            interest_minor=row.interest_minor,
            total_minor=row.total_minor,
            admin_overridden=False,
        )
        for index, row in enumerate(rows, start=1)
    ]


def _recalculate_schedule_after_early_repayment(
    *,
    loan: Model,
    actor: Model,
    repayment_event: BorrowerRepaymentEvent,
    current_installment: Model,
    remaining_principal_minor: int,
    currency_code: str,
    future_principal_applied_minor: int,
) -> dict[str, Any]:
    if future_principal_applied_minor <= 0:
        return {}
    loan_ref = cast(Any, loan)
    installment_ref = cast(Any, current_installment)
    previous_schedule_version = int(loan_ref.schedule_version)
    next_schedule_version = previous_schedule_version + 1
    future_rows = _remaining_schedule_rows_after_early_repayment(
        loan=loan,
        current_installment=current_installment,
        remaining_principal_minor=remaining_principal_minor,
        currency_code=currency_code,
    )
    schedule_row_type = _schedule_domain().ScheduleInstallmentDraft
    current_row = schedule_row_type(
        installment_number=int(installment_ref.installment_number),
        due_date=cast(date, installment_ref.due_date),
        principal_minor=int(installment_ref.principal_minor),
        interest_minor=int(installment_ref.interest_minor),
        total_minor=int(installment_ref.total_minor),
        admin_overridden=bool(getattr(installment_ref, "admin_overridden", False)),
    )
    schedule_rows = [current_row, *future_rows]
    installment_model = apps.get_model("loans", "LoanInstallment")
    installment_model.objects.bulk_create(
        [
            installment_model(
                loan=loan,
                schedule_version=next_schedule_version,
                installment_number=row.installment_number,
                due_date=row.due_date,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                total_minor=row.total_minor,
                admin_overridden=row.admin_overridden,
                metadata={
                    "previous_schedule_version": previous_schedule_version,
                    "reason": "early_repayment",
                    "repayment_event_id": str(repayment_event.id),
                },
            )
            for row in schedule_rows
        ]
    )
    loan_ref.schedule_version = next_schedule_version
    # These totals describe the active schedule version. They are not lifetime
    # principal and are not a substitute for holding balances as outstanding principal.
    loan_ref.total_scheduled_principal_minor = sum(row.principal_minor for row in schedule_rows)
    loan_ref.total_scheduled_interest_minor = sum(row.interest_minor for row in schedule_rows)
    loan_ref.updated_by_admin_id = actor.pk
    loan.save(
        update_fields=[
            "schedule_version",
            "total_scheduled_principal_minor",
            "total_scheduled_interest_minor",
            "updated_by_admin_id",
            "updated_at",
        ]
    )
    metadata = {
        "previous_schedule_version": previous_schedule_version,
        "new_schedule_version": next_schedule_version,
        "future_principal_applied_minor": future_principal_applied_minor,
        "remaining_principal_minor": remaining_principal_minor,
        "repayment_event_id": str(repayment_event.id),
        "installment_count": len(schedule_rows),
        "future_installment_count": len(future_rows),
    }
    event_model = apps.get_model("loans", "LoanEvent")
    event_model.objects.create(
        loan=loan,
        event_type="schedule_generated",
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        previous_status=str(loan_ref.status),
        new_status=str(loan_ref.status),
        note="Schedule recalculated after early repayment.",
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.schedule_recalculated_after_early_repayment",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanScheduleRecalculated",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=metadata,
            idempotency_key=f"loan:{loan_ref.id}:schedule:{next_schedule_version}",
        )
    )
    return metadata


@transaction.atomic
def record_borrower_repayment(
    command: RecordBorrowerRepaymentCommand,
) -> RecordBorrowerRepaymentResult:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    amount_minor = _validate_positive_minor_amount(command.amount_minor, "Repayment amount")
    request_fingerprint = _request_fingerprint(
        command,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_repayment_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing

    loan = _locked_repayable_loan(command.loan_id)
    existing_after_lock = _existing_repayment_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing_after_lock is not None:
        return existing_after_lock

    loan_ref = cast(Any, loan)
    currency = _enabled_currency(str(loan_ref.currency_id))
    amount_minor = _validate_money(command.amount_minor, currency.code, "Repayment amount")
    if command.amount_minor != amount_minor:
        raise ServicingValidationError("Repayment amount changed during validation.")
    installment, remaining_principal, remaining_interest = _next_due_installment(loan)
    expected_due = remaining_principal + remaining_interest
    loan_status = str(loan_ref.status)
    future_principal_applied = 0
    if amount_minor > expected_due:
        if not command.warning_acknowledged:
            raise ServicingValidationError(
                "Repayment differs from the next due installment; "
                "warning acknowledgement is required."
            )
        if loan_status != LOAN_STATUS_FUNDED:
            raise ServicingValidationError(
                "Multiple-installment catch-up payments for late loans are handled in a "
                "later servicing slice."
            )
        future_principal_applied = amount_minor - expected_due
    if amount_minor < expected_due and not command.warning_acknowledged:
        raise ServicingValidationError(
            "Repayment differs from the next due installment; warning acknowledgement is required."
        )

    interest_applied = min(amount_minor, remaining_interest)
    principal_applied = min(remaining_principal, amount_minor - interest_applied)
    if future_principal_applied > 0:
        event_type = BorrowerRepaymentEventType.EARLY_REPAYMENT
    elif amount_minor == expected_due:
        event_type = BorrowerRepaymentEventType.REGULAR_INSTALLMENT
    else:
        event_type = BorrowerRepaymentEventType.PARTIAL_INSTALLMENT
    holdings = _active_holdings_for_loan(loan)
    total_holding_principal = sum(
        int(cast(Any, holding).current_principal_minor) for holding in holdings
    )
    max_future_principal = total_holding_principal - principal_applied
    if future_principal_applied > max_future_principal:
        raise ServicingValidationError(
            "Repayment exceeds outstanding loan principal after the current installment."
        )
    principal_for_distribution = principal_applied + future_principal_applied
    distribution_plan = _distribution_plan(
        holdings=holdings,
        principal_minor=principal_for_distribution,
        interest_minor=interest_applied,
        currency_code=currency.code,
    )
    event_id = uuid.uuid4()
    ledger = _ledger_services()
    try:
        ledger_result = ledger.declare_borrower_repayment_distribution(
            ledger.DeclareBorrowerRepaymentDistributionCommand(
                actor=command.actor,
                loan_id=str(loan_ref.id),
                borrower_id=str(loan_ref.borrower_id),
                amount_minor=amount_minor,
                currency=currency.code,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=command.collection_account_identifier,
                payer_name=command.payer_name,
                source_type="borrower_repayment_event",
                source_id=str(event_id),
                distribution_lines=[
                    ledger.InvestorBalanceCreditLineCommand(
                        investor_user_id=line.investor_user_id,
                        amount_minor=line.amount_minor,
                        principal_minor=line.principal_minor,
                        interest_minor=line.interest_minor,
                        holding_id=str(cast(Any, line.holding).id),
                        installment_id=str(cast(Any, installment).id),
                        metadata={
                            "current_principal_before_minor": (
                                line.current_principal_before_minor
                            ),
                            "current_principal_after_minor": line.current_principal_after_minor,
                        },
                    )
                    for line in distribution_plan
                ],
                payer_account_identifier=command.payer_account_identifier,
                bank_reference=command.bank_reference,
                payment_reference=command.payment_reference,
                evidence_reference=command.evidence_reference,
                admin_notes=command.admin_notes,
                idempotency_key=idempotency_key,
            )
        )
    except ledger.LedgerError as exc:
        raise ServicingValidationError(str(exc)) from exc

    received_at = _received_at_from_value_date(command.value_date)
    metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "installment_number": int(cast(Any, installment).installment_number),
        "future_principal_applied_minor": future_principal_applied,
        "ledger_journal_entry_id": str(ledger_result.journal_entry.id),
        "bank_operation_id": str(ledger_result.bank_operation.id),
    }
    try:
        with transaction.atomic():
            repayment_event = BorrowerRepaymentEvent.objects.create(
                id=event_id,
                loan=loan,
                installment=installment,
                event_type=event_type,
                amount_minor=amount_minor,
                currency=currency,
                booking_date=command.booking_date,
                value_date=command.value_date,
                received_at=received_at,
                expected_due_minor=expected_due,
                interest_applied_minor=interest_applied,
                principal_applied_minor=principal_applied,
                future_principal_applied_minor=future_principal_applied,
                remaining_installment_interest_minor=remaining_interest - interest_applied,
                remaining_installment_principal_minor=remaining_principal - principal_applied,
                warning_acknowledged=command.warning_acknowledged,
                bank_operation=ledger_result.bank_operation,
                journal_entry=ledger_result.journal_entry,
                created_by_admin_id=command.actor.pk,
                notes=command.admin_notes.strip(),
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_repayment_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    distribution_lines: list[InvestorRepaymentDistributionLine] = []
    credits_by_index = {credit.line_index: credit for credit in ledger_result.balance_credits}
    for index, plan_line in enumerate(distribution_plan):
        credit = credits_by_index[index]
        _record_holding_principal_update(
            holding=plan_line.holding,
            actor=command.actor,
            repayment_event=repayment_event,
            principal_minor=plan_line.principal_minor,
            before_minor=plan_line.current_principal_before_minor,
            after_minor=plan_line.current_principal_after_minor,
        )
        distribution_lines.append(
            InvestorRepaymentDistributionLine.objects.create(
                repayment_event=repayment_event,
                holding=plan_line.holding,
                investor_user_id=plan_line.investor_user_id,
                currency=currency,
                balance_lot=credit.balance_lot,
                amount_minor=plan_line.amount_minor,
                principal_minor=plan_line.principal_minor,
                interest_minor=plan_line.interest_minor,
                fee_minor=0,
                current_principal_before_minor=plan_line.current_principal_before_minor,
                current_principal_after_minor=plan_line.current_principal_after_minor,
                metadata={"line_index": index},
            )
        )
    for line in distribution_lines:
        _enqueue_investor_email(
            investor_user_id=str(line.investor_user_id),
            topic="email.repayment_distribution_credited",
            subject=f"{settings.PLATFORM_BRAND_NAME} repayment credited",
            body_text=(
                f"Your {settings.PLATFORM_BRAND_NAME} balance has been credited with "
                f"{line.amount_minor} minor units in {currency.code} for loan {loan_ref.title}.\n\n"
                f"Principal component: {line.principal_minor} minor units.\n"
                f"Interest component: {line.interest_minor} minor units.\n"
                f"Value date: {command.value_date.isoformat()}."
            ),
            template_key="servicing.repayment_distribution_credited.v1",
            idempotency_key=(
                f"email:repayment-distribution:{repayment_event.id}:{line.investor_user_id}"
            ),
            metadata={
                "repayment_event_id": str(repayment_event.id),
                "loan_id": str(loan_ref.id),
                "holding_id": str(line.holding_id),
                "balance_lot_id": str(line.balance_lot_id),
                "currency": currency.code,
                "amount_minor": line.amount_minor,
                "principal_minor": line.principal_minor,
                "interest_minor": line.interest_minor,
                "value_date": command.value_date.isoformat(),
            },
        )
    remaining_loan_principal = sum(line.current_principal_after_minor for line in distribution_plan)
    schedule_recalculation = _recalculate_schedule_after_early_repayment(
        loan=loan,
        actor=command.actor,
        repayment_event=repayment_event,
        current_installment=installment,
        remaining_principal_minor=remaining_loan_principal,
        currency_code=currency.code,
        future_principal_applied_minor=future_principal_applied,
    )
    status_change = _refresh_loan_status_after_repayment(
        loan=loan,
        actor=command.actor,
        as_of_date=command.value_date,
        repayment_event_id=str(repayment_event.id),
    )

    event_metadata = {
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "installment_id": str(cast(Any, installment).id),
        "currency": currency.code,
        "amount_minor": amount_minor,
        "interest_applied_minor": interest_applied,
        "principal_applied_minor": principal_applied,
        "future_principal_applied_minor": future_principal_applied,
        "distribution_line_count": len(distribution_lines),
        "schedule_recalculation": schedule_recalculation,
        "loan_status_change": {
            "previous_status": status_change.previous_status,
            "new_status": status_change.new_status,
        }
        if status_change is not None
        else {},
    }
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="servicing.borrower_repayment_recorded",
            target_type="BorrowerRepaymentEvent",
            target_id=str(repayment_event.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BorrowerRepaymentRecorded",
            aggregate_type="BorrowerRepaymentEvent",
            aggregate_id=str(repayment_event.id),
            payload=event_metadata,
            idempotency_key=f"borrower-repayment:{repayment_event.id}:recorded",
        )
    )
    return RecordBorrowerRepaymentResult(
        repayment_event=repayment_event,
        distribution_lines=distribution_lines,
    )


@transaction.atomic
def record_loan_recovery_payment(
    command: RecordLoanRecoveryPaymentCommand,
) -> RecordLoanRecoveryPaymentResult:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    gross_recovered_minor = _validate_positive_minor_amount(
        command.gross_recovered_minor,
        "Gross recovered amount",
    )
    externally_deducted_costs_minor = _validate_nonnegative_minor_amount(
        command.externally_deducted_costs_minor,
        "Externally deducted recovery costs",
    )
    third_party_costs_from_received_minor = _validate_nonnegative_minor_amount(
        command.third_party_costs_from_received_minor,
        "Third-party recovery costs from received funds",
    )
    principal_recovered_minor = _validate_nonnegative_minor_amount(
        command.principal_recovered_minor,
        "Recovered principal",
    )
    contractual_interest_recovered_minor = _validate_nonnegative_minor_amount(
        command.contractual_interest_recovered_minor,
        "Recovered contractual interest",
    )
    default_interest_recovered_minor = _validate_nonnegative_minor_amount(
        command.default_interest_recovered_minor,
        "Recovered default interest",
    )
    penalties_recovered_minor = _validate_nonnegative_minor_amount(
        command.penalties_recovered_minor,
        "Recovered penalties",
    )
    other_costs_recovered_minor = _validate_nonnegative_minor_amount(
        command.other_costs_recovered_minor,
        "Recovered other costs",
    )
    if externally_deducted_costs_minor >= gross_recovered_minor:
        raise ServicingValidationError(
            "Externally deducted costs must be lower than the gross recovered amount."
        )
    net_received_minor = gross_recovered_minor - externally_deducted_costs_minor
    recovery_fee_base_minor = net_received_minor - third_party_costs_from_received_minor
    if recovery_fee_base_minor <= 0:
        raise ServicingValidationError(
            "Recovery fee/cost base must leave funds available after third-party costs."
        )
    if command.recovery_fee_bps > 10_000:
        raise ServicingValidationError("Recovery fee bps cannot exceed 100%.")
    recovery_fee_minor = (
        _fee_from_bps(recovery_fee_base_minor, command.recovery_fee_bps)
        if command.recovery_fee_applied
        else 0
    )
    net_available_for_distribution_minor = (
        net_received_minor - third_party_costs_from_received_minor - recovery_fee_minor
    )
    if net_available_for_distribution_minor <= 0:
        raise ServicingValidationError("Recovery payment leaves no amount to distribute.")
    declared_distribution_minor = (
        principal_recovered_minor
        + contractual_interest_recovered_minor
        + default_interest_recovered_minor
        + penalties_recovered_minor
        + other_costs_recovered_minor
    )
    if declared_distribution_minor != net_available_for_distribution_minor:
        raise ServicingValidationError(
            "Recovery category split must equal the net amount available for distribution."
        )
    request_fingerprint = _recovery_payment_fingerprint(
        command,
        gross_recovered_minor=gross_recovered_minor,
        externally_deducted_costs_minor=externally_deducted_costs_minor,
        net_received_minor=net_received_minor,
        third_party_costs_from_received_minor=third_party_costs_from_received_minor,
        recovery_fee_base_minor=recovery_fee_base_minor,
        recovery_fee_minor=recovery_fee_minor,
        net_available_for_distribution_minor=net_available_for_distribution_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_recovery_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing

    loan = _locked_loan(command.loan_id)
    existing_after_lock = _existing_recovery_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing_after_lock is not None:
        return existing_after_lock
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) not in RECOVERY_ALLOWED_LOAN_STATUSES:
        raise ServicingValidationError(
            "Recovery payments can only be recorded for defaulted loans "
            "before final loss recognition."
        )
    currency = _enabled_currency(str(loan_ref.currency_id))
    for label, amount in [
        ("Gross recovered amount", gross_recovered_minor),
        ("Externally deducted recovery costs", externally_deducted_costs_minor),
        ("Net received amount", net_received_minor),
        ("Third-party recovery costs from received funds", third_party_costs_from_received_minor),
        ("Recovery fee base", recovery_fee_base_minor),
        ("Recovery fee amount", recovery_fee_minor),
        ("Net amount available for distribution", net_available_for_distribution_minor),
        ("Recovered principal", principal_recovered_minor),
        ("Recovered contractual interest", contractual_interest_recovered_minor),
        ("Recovered default interest", default_interest_recovered_minor),
        ("Recovered penalties", penalties_recovered_minor),
        ("Recovered other costs", other_costs_recovered_minor),
    ]:
        if amount > 0:
            _validate_money(amount, currency.code, label)
        else:
            _validate_nonnegative_minor_amount(amount, label)
    holdings = _active_holdings_for_loan(loan)
    distribution_plan = _recovery_distribution_plan(
        holdings=holdings,
        principal_minor=principal_recovered_minor,
        contractual_interest_minor=contractual_interest_recovered_minor,
        default_interest_minor=default_interest_recovered_minor,
        penalties_minor=penalties_recovered_minor,
        other_costs_minor=other_costs_recovered_minor,
        currency_code=currency.code,
    )
    event_id = uuid.uuid4()
    ledger = _ledger_services()
    try:
        ledger_result = ledger.declare_recovery_distribution(
            ledger.DeclareRecoveryDistributionCommand(
                actor=command.actor,
                loan_id=str(loan_ref.id),
                borrower_id=str(loan_ref.borrower_id),
                net_received_minor=net_received_minor,
                recovery_fee_minor=recovery_fee_minor,
                third_party_costs_from_received_minor=third_party_costs_from_received_minor,
                currency=currency.code,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=command.collection_account_identifier,
                payer_name=command.payer_name,
                source_type="loan_recovery_event",
                source_id=str(event_id),
                distribution_lines=[
                    ledger.InvestorRecoveryCreditLineCommand(
                        investor_user_id=line.investor_user_id,
                        amount_minor=line.amount_minor,
                        principal_minor=line.principal_minor,
                        contractual_interest_minor=line.contractual_interest_minor,
                        default_interest_minor=line.default_interest_minor,
                        penalties_minor=line.penalties_minor,
                        other_costs_minor=line.other_costs_minor,
                        holding_id=str(cast(Any, line.holding).id),
                        metadata={
                            "current_principal_before_minor": (
                                line.current_principal_before_minor
                            ),
                            "current_principal_after_minor": line.current_principal_after_minor,
                        },
                    )
                    for line in distribution_plan
                ],
                payer_account_identifier=command.payer_account_identifier,
                bank_reference=command.bank_reference,
                payment_reference=command.payment_reference,
                evidence_reference=command.evidence_reference,
                admin_notes=command.notes,
                idempotency_key=idempotency_key,
            )
        )
    except ledger.LedgerError as exc:
        raise ServicingValidationError(str(exc)) from exc

    received_at = _received_at_from_value_date(command.value_date)
    recovery_waterfall_config = {
        "version": "v1-default-admin-declared",
        "waterfall_order": [
            "external_recovery_legal_costs",
            "platform_approved_recovery_costs",
            "principal",
            "contractual_interest_until_default",
            "default_penalty_interest_after_default",
            "other_penalties_costs",
        ],
        "allocation_method": "pro_rata_by_current_principal",
        "rounding": "currency_minor_unit_half_up_largest_remainder",
        **(command.recovery_waterfall_config or {}),
    }
    metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "ledger_journal_entry_id": str(ledger_result.journal_entry.id),
        "bank_operation_id": str(ledger_result.bank_operation.id),
        "distribution_line_count": len(distribution_plan),
        "fee_base_policy": "net_received_after_third_party_costs_from_received",
        "metadata": command.metadata or {},
    }
    try:
        with transaction.atomic():
            recovery_event = LoanRecoveryEvent.objects.create(
                id=event_id,
                loan=loan,
                borrower_id=loan_ref.borrower_id,
                currency=currency,
                gross_recovered_minor=gross_recovered_minor,
                externally_deducted_costs_minor=externally_deducted_costs_minor,
                net_received_minor=net_received_minor,
                third_party_costs_from_received_minor=third_party_costs_from_received_minor,
                recovery_fee_applied=command.recovery_fee_applied,
                recovery_fee_bps=command.recovery_fee_bps,
                recovery_fee_base_minor=recovery_fee_base_minor,
                recovery_fee_minor=recovery_fee_minor,
                net_available_for_distribution_minor=net_available_for_distribution_minor,
                principal_recovered_minor=principal_recovered_minor,
                contractual_interest_recovered_minor=contractual_interest_recovered_minor,
                default_interest_recovered_minor=default_interest_recovered_minor,
                penalties_recovered_minor=penalties_recovered_minor,
                other_costs_recovered_minor=other_costs_recovered_minor,
                rounding_difference_minor=0,
                booking_date=command.booking_date,
                value_date=command.value_date,
                received_at=received_at,
                bank_operation=ledger_result.bank_operation,
                journal_entry=ledger_result.journal_entry,
                recovery_waterfall_config=recovery_waterfall_config,
                evidence_reference=command.evidence_reference.strip(),
                notes=command.notes.strip(),
                created_by_admin_id=command.actor.pk,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_recovery_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    distribution_lines: list[InvestorRecoveryDistributionLine] = []
    credits_by_index = {credit.line_index: credit for credit in ledger_result.balance_credits}
    for index, plan_line in enumerate(distribution_plan):
        credit = credits_by_index[index]
        _record_recovery_holding_principal_update(
            holding=plan_line.holding,
            actor=command.actor,
            recovery_event=recovery_event,
            principal_minor=plan_line.principal_minor,
            before_minor=plan_line.current_principal_before_minor,
            after_minor=plan_line.current_principal_after_minor,
        )
        distribution_lines.append(
            InvestorRecoveryDistributionLine.objects.create(
                recovery_event=recovery_event,
                holding=plan_line.holding,
                investor_user_id=plan_line.investor_user_id,
                currency=currency,
                balance_lot=credit.balance_lot,
                amount_minor=plan_line.amount_minor,
                principal_minor=plan_line.principal_minor,
                contractual_interest_minor=plan_line.contractual_interest_minor,
                default_interest_minor=plan_line.default_interest_minor,
                penalties_minor=plan_line.penalties_minor,
                other_costs_minor=plan_line.other_costs_minor,
                current_principal_before_minor=plan_line.current_principal_before_minor,
                current_principal_after_minor=plan_line.current_principal_after_minor,
                metadata={"line_index": index},
            )
        )
    for line in distribution_lines:
        _enqueue_investor_email(
            investor_user_id=str(line.investor_user_id),
            topic="email.recovery_distribution_credited",
            subject=f"{settings.PLATFORM_BRAND_NAME} recovery distribution credited",
            body_text=(
                f"Your {settings.PLATFORM_BRAND_NAME} balance has been credited with "
                f"{line.amount_minor} minor units in {currency.code} from a recovery payment "
                f"for loan {loan_ref.title}.\n\n"
                f"Principal recovered: {line.principal_minor} minor units.\n"
                f"Contractual interest recovered: {line.contractual_interest_minor} minor units.\n"
                f"Default/penalty interest recovered: {line.default_interest_minor} minor units.\n"
                f"Penalties and other costs recovered: "
                f"{line.penalties_minor + line.other_costs_minor} minor units.\n"
                f"Value date: {command.value_date.isoformat()}."
            ),
            template_key="servicing.recovery_distribution_credited.v1",
            idempotency_key=f"email:recovery-distribution:{recovery_event.id}:{line.investor_user_id}",
            metadata={
                "recovery_event_id": str(recovery_event.id),
                "loan_id": str(loan_ref.id),
                "holding_id": str(line.holding_id),
                "balance_lot_id": str(line.balance_lot_id),
                "currency": currency.code,
                "amount_minor": line.amount_minor,
                "principal_minor": line.principal_minor,
                "contractual_interest_minor": line.contractual_interest_minor,
                "default_interest_minor": line.default_interest_minor,
                "penalties_minor": line.penalties_minor,
                "other_costs_minor": line.other_costs_minor,
                "value_date": command.value_date.isoformat(),
            },
        )
    loan_event_model = _loan_event_model()
    loan_event_model.objects.create(
        loan=loan,
        event_type="recovery_recorded",
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        previous_status=str(loan_ref.status),
        new_status=str(loan_ref.status),
        note=command.notes.strip(),
        metadata={
            "recovery_event_id": str(recovery_event.id),
            "gross_recovered_minor": gross_recovered_minor,
            "net_received_minor": net_received_minor,
            "net_available_for_distribution_minor": net_available_for_distribution_minor,
            "recovery_fee_minor": recovery_fee_minor,
            "third_party_costs_from_received_minor": third_party_costs_from_received_minor,
        },
    )
    event_metadata = {
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "currency": currency.code,
        "gross_recovered_minor": gross_recovered_minor,
        "externally_deducted_costs_minor": externally_deducted_costs_minor,
        "net_received_minor": net_received_minor,
        "third_party_costs_from_received_minor": third_party_costs_from_received_minor,
        "recovery_fee_applied": command.recovery_fee_applied,
        "recovery_fee_bps": command.recovery_fee_bps,
        "recovery_fee_base_minor": recovery_fee_base_minor,
        "recovery_fee_minor": recovery_fee_minor,
        "net_available_for_distribution_minor": net_available_for_distribution_minor,
        "principal_recovered_minor": principal_recovered_minor,
        "contractual_interest_recovered_minor": contractual_interest_recovered_minor,
        "default_interest_recovered_minor": default_interest_recovered_minor,
        "penalties_recovered_minor": penalties_recovered_minor,
        "other_costs_recovered_minor": other_costs_recovered_minor,
        "distribution_line_count": len(distribution_lines),
        "journal_entry_id": str(ledger_result.journal_entry.id),
        "bank_operation_id": str(ledger_result.bank_operation.id),
    }
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="servicing.loan_recovery_recorded",
            target_type="LoanRecoveryEvent",
            target_id=str(recovery_event.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanRecoveryRecorded",
            aggregate_type="LoanRecoveryEvent",
            aggregate_id=str(recovery_event.id),
            payload=event_metadata,
            idempotency_key=f"loan-recovery:{recovery_event.id}:recorded",
        )
    )
    return RecordLoanRecoveryPaymentResult(
        recovery_event=recovery_event,
        distribution_lines=distribution_lines,
    )


@transaction.atomic
def scan_loan_servicing_statuses(
    command: ScanLoanServicingStatusesCommand,
) -> ScanLoanServicingStatusesResult:
    _require_admin_actor(command.actor)
    loan_model = apps.get_model("loans", "Loan")
    loans = loan_model.objects.select_for_update().filter(status__in=STATUS_SCAN_LOAN_STATUSES)
    if command.loan_ids:
        loans = loans.filter(id__in=[str(loan_id) for loan_id in command.loan_ids])
    changes: list[LoanServicingStatusChange] = []
    for loan in loans.order_by("id"):
        new_status, days_past_due, outstanding, installment = (
            _first_outstanding_installment_status(
                cast(Model, loan),
                as_of_date=command.as_of_date,
            )
        )
        change = _record_loan_servicing_status_change(
            loan=cast(Model, loan),
            actor=command.actor,
            new_status=new_status,
            as_of_date=command.as_of_date,
            days_past_due=days_past_due,
            outstanding_minor=outstanding,
            triggering_installment=installment,
            reason="servicing_status_scan",
        )
        if change is not None:
            changes.append(change)
    return ScanLoanServicingStatusesResult(as_of_date=command.as_of_date, changes=changes)


@transaction.atomic
def add_loan_risk_note(command: AddLoanRiskNoteCommand) -> LoanRiskNote:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    visibility = _validate_visibility(command.visibility)
    note_type = _validate_note_type(command.note_type)
    title = command.title.strip()
    body = _clean_required(command.body, "Risk note body")
    evidence_reference = command.evidence_reference.strip()
    if visibility == LoanRiskNoteVisibility.PUBLIC and note_type in {
        LoanRiskNoteType.INTERNAL_NOTE,
        LoanRiskNoteType.DOCUMENT_NOTE,
    }:
        raise ServicingValidationError("Internal/document notes cannot be marked public.")
    loan = _locked_loan(command.loan_id)
    loan_ref = cast(Any, loan)
    if visibility == LoanRiskNoteVisibility.PUBLIC and str(loan_ref.status) not in (
        PUBLIC_NOTE_LOAN_STATUSES
    ):
        raise ServicingValidationError("Public notes can only be added to active portfolio loans.")
    request_fingerprint = _risk_note_fingerprint(
        command,
        visibility=visibility,
        note_type=note_type,
        title=title,
        body=body,
        evidence_reference=evidence_reference,
        idempotency_key=idempotency_key,
    )
    existing = _existing_risk_note_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "loan_status": str(loan_ref.status),
        **(command.metadata or {}),
    }
    occurred_at = now_utc()
    try:
        with transaction.atomic():
            note = LoanRiskNote.objects.create(
                loan=loan,
                borrower_id=loan_ref.borrower_id,
                visibility=visibility,
                note_type=note_type,
                title=title,
                body=body,
                evidence_reference=evidence_reference,
                created_by_admin_id=command.actor.pk,
                occurred_at=occurred_at,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_risk_note_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    actor_ref = actor_ref_for_user(command.actor)
    event_metadata = {
        "risk_note_id": str(note.id),
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "visibility": visibility,
        "note_type": note_type,
        "title": title,
        "evidence_reference": evidence_reference,
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="servicing.loan_risk_note_added",
            target_type="LoanRiskNote",
            target_id=str(note.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanRiskNoteAdded",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=event_metadata,
            idempotency_key=f"loan-risk-note:{note.id}:added",
        )
    )
    return cast(LoanRiskNote, note)


@transaction.atomic
def record_loan_write_off(command: RecordLoanWriteOffCommand) -> LoanWriteOffEvent:
    """Record final default loss recognition and close remaining active holdings."""
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    principal_minor = _validate_nonnegative_minor_amount(
        command.written_off_principal_minor,
        "Written-off principal",
    )
    contractual_interest_minor = _validate_nonnegative_minor_amount(
        command.written_off_contractual_interest_minor,
        "Written-off contractual interest",
    )
    default_interest_minor = _validate_nonnegative_minor_amount(
        command.written_off_default_interest_minor,
        "Written-off default interest",
    )
    fees_minor = _validate_nonnegative_minor_amount(
        command.written_off_fees_minor,
        "Written-off fees",
    )
    penalties_minor = _validate_nonnegative_minor_amount(
        command.written_off_penalties_minor,
        "Written-off penalties",
    )
    total_minor = (
        principal_minor
        + contractual_interest_minor
        + default_interest_minor
        + fees_minor
        + penalties_minor
    )
    reason = _clean_required(command.reason, "Write-off reason")
    notes = command.notes.strip()
    evidence_reference = command.evidence_reference.strip()
    loan = _locked_loan(command.loan_id)
    loan_ref = cast(Any, loan)
    currency = _enabled_currency(str(loan_ref.currency_id))
    _validate_money(total_minor, currency.code, "Total written-off amount")
    request_fingerprint = _write_off_fingerprint(
        command,
        currency_code=currency.code,
        principal_minor=principal_minor,
        contractual_interest_minor=contractual_interest_minor,
        default_interest_minor=default_interest_minor,
        fees_minor=fees_minor,
        penalties_minor=penalties_minor,
        total_minor=total_minor,
        reason=reason,
        notes=notes,
        evidence_reference=evidence_reference,
        idempotency_key=idempotency_key,
    )
    existing = _existing_write_off_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    previous_status = str(loan_ref.status)
    if previous_status != LOAN_STATUS_DEFAULTED:
        raise ServicingValidationError("Only defaulted loans can be written off.")
    holdings = _active_holdings_for_loan(loan)
    loss_plan = _loss_recognition_plan(
        holdings=holdings,
        principal_loss_minor=principal_minor,
        contractual_interest_loss_minor=contractual_interest_minor,
        default_interest_loss_minor=default_interest_minor,
        fees_loss_minor=fees_minor,
        penalties_loss_minor=penalties_minor,
        currency_code=currency.code,
    )
    written_off_at = now_utc()
    metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "previous_loan_status": previous_status,
        "new_loan_status": LOAN_STATUS_WRITTEN_OFF,
        "loss_recognition_line_count": len(loss_plan),
        **(command.metadata or {}),
    }
    try:
        with transaction.atomic():
            write_off = LoanWriteOffEvent.objects.create(
                loan=loan,
                borrower_id=loan_ref.borrower_id,
                currency=currency,
                written_off_principal_minor=principal_minor,
                written_off_contractual_interest_minor=contractual_interest_minor,
                written_off_default_interest_minor=default_interest_minor,
                written_off_fees_minor=fees_minor,
                written_off_penalties_minor=penalties_minor,
                total_written_off_minor=total_minor,
                previous_loan_status=previous_status,
                new_loan_status=LOAN_STATUS_WRITTEN_OFF,
                reason=reason,
                notes=notes,
                evidence_reference=evidence_reference,
                written_off_at=written_off_at,
                created_by_admin_id=command.actor.pk,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_write_off_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    loss_lines: list[InvestorLossRecognitionLine] = []
    for index, line in enumerate(loss_plan):
        _record_loss_holding_principal_update(
            holding=line.holding,
            actor=command.actor,
            write_off_event=write_off,
            principal_loss_minor=line.principal_loss_minor,
            before_minor=line.current_principal_before_minor,
            after_minor=line.current_principal_after_minor,
        )
        loss_lines.append(
            InvestorLossRecognitionLine.objects.create(
                write_off_event=write_off,
                holding=line.holding,
                investor_user_id=line.investor_user_id,
                currency=currency,
                principal_loss_minor=line.principal_loss_minor,
                contractual_interest_loss_minor=line.contractual_interest_loss_minor,
                default_interest_loss_minor=line.default_interest_loss_minor,
                fees_loss_minor=line.fees_loss_minor,
                penalties_loss_minor=line.penalties_loss_minor,
                total_loss_minor=line.total_loss_minor,
                current_principal_before_minor=line.current_principal_before_minor,
                current_principal_after_minor=line.current_principal_after_minor,
                metadata={"line_index": index},
            )
        )
    loan_ref.status = LOAN_STATUS_WRITTEN_OFF
    loan_ref.updated_by_admin_id = command.actor.pk
    loan.save(update_fields=["status", "updated_by_admin_id", "updated_at"])
    event_metadata = {
        "write_off_event_id": str(write_off.id),
        "loan_id": str(loan_ref.id),
        "borrower_id": str(loan_ref.borrower_id),
        "currency": currency.code,
        "written_off_principal_minor": principal_minor,
        "written_off_contractual_interest_minor": contractual_interest_minor,
        "written_off_default_interest_minor": default_interest_minor,
        "written_off_fees_minor": fees_minor,
        "written_off_penalties_minor": penalties_minor,
        "total_written_off_minor": total_minor,
        "previous_status": previous_status,
        "new_status": LOAN_STATUS_WRITTEN_OFF,
        "reason": reason,
        "evidence_reference": evidence_reference,
        "loss_recognition_line_count": len(loss_lines),
    }
    _loan_event_model().objects.create(
        loan=loan,
        event_type="write_off_recorded",
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        previous_status=previous_status,
        new_status=LOAN_STATUS_WRITTEN_OFF,
        note=reason,
        metadata=event_metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="servicing.loan_write_off_recorded",
            target_type="LoanWriteOffEvent",
            target_id=str(write_off.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanWriteOffRecorded",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=event_metadata,
            idempotency_key=f"loan:{loan_ref.id}:write-off:{write_off.id}",
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanLossRecognized",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=event_metadata,
            idempotency_key=f"loan:{loan_ref.id}:loss-recognized:{write_off.id}",
        )
    )
    return cast(LoanWriteOffEvent, write_off)
