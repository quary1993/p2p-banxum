from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import Model, Sum

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.money import (
    Money,
    MoneyError,
    allocate_by_weights,
    normalize_currency,
)
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    BorrowerRepaymentEventType,
    InvestorRepaymentDistributionLine,
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
REPAYMENT_ALLOWED_LOAN_STATUSES = {LOAN_STATUS_FUNDED, LOAN_STATUS_LATE}
STATUS_SCAN_LOAN_STATUSES = {LOAN_STATUS_FUNDED, LOAN_STATUS_LATE}
LATE_THRESHOLD_DAYS = 5
DEFAULT_THRESHOLD_DAYS = 16


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
class RecordBorrowerRepaymentResult:
    repayment_event: BorrowerRepaymentEvent
    distribution_lines: list[InvestorRepaymentDistributionLine]


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
class ScanLoanServicingStatusesResult:
    as_of_date: date
    changes: list[LoanServicingStatusChange]


def _ledger_services() -> Any:
    return import_module("backend.apps.ledger.services")


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


def _locked_repayable_loan(loan_id: str) -> Model:
    loan_model = apps.get_model("loans", "Loan")
    loan = cast(
        Model | None,
        loan_model.objects.select_for_update()
        .select_related("borrower", "currency")
        .filter(id=loan_id)
        .first(),
    )
    if loan is None:
        raise ServicingValidationError("Loan does not exist.")
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
    aggregate = BorrowerRepaymentEvent.objects.filter(installment=installment).aggregate(
        principal=Sum("principal_applied_minor"),
        interest=Sum("interest_applied_minor"),
    )
    return int(aggregate["principal"] or 0), int(aggregate["interest"] or 0)


def _first_outstanding_installment_status(
    loan: Model,
    *,
    as_of_date: date,
) -> tuple[str, int, int, Model | None]:
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
        outstanding = remaining_principal + remaining_interest
        if outstanding <= 0:
            continue
        days_past_due = max(0, (as_of_date - installment.due_date).days)
        if days_past_due >= DEFAULT_THRESHOLD_DAYS:
            return LOAN_STATUS_DEFAULTED, days_past_due, outstanding, cast(Model, installment)
        if days_past_due >= LATE_THRESHOLD_DAYS:
            return LOAN_STATUS_LATE, days_past_due, outstanding, cast(Model, installment)
        return LOAN_STATUS_FUNDED, days_past_due, outstanding, cast(Model, installment)
    return LOAN_STATUS_FUNDED, 0, 0, None


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
    if str(loan_ref.status) != LOAN_STATUS_LATE:
        return None
    new_status, days_past_due, outstanding, installment = _first_outstanding_installment_status(
        loan,
        as_of_date=as_of_date,
    )
    if new_status == LOAN_STATUS_DEFAULTED:
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
    if amount_minor > expected_due:
        raise ServicingValidationError(
            "Repayment exceeds the next due installment; early and multi-installment "
            "repayments are handled in a later servicing slice."
        )
    if amount_minor < expected_due and not command.warning_acknowledged:
        raise ServicingValidationError(
            "Repayment differs from the next due installment; warning acknowledgement is required."
        )

    interest_applied = min(amount_minor, remaining_interest)
    principal_applied = amount_minor - interest_applied
    event_type = (
        BorrowerRepaymentEventType.REGULAR_INSTALLMENT
        if amount_minor == expected_due
        else BorrowerRepaymentEventType.PARTIAL_INSTALLMENT
    )
    holdings = _active_holdings_for_loan(loan)
    distribution_plan = _distribution_plan(
        holdings=holdings,
        principal_minor=principal_applied,
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
        "distribution_line_count": len(distribution_lines),
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
