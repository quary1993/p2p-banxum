from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Model, Sum

from backend.apps.ledger.models import (
    BalanceLotSourceType,
    BalanceLotStatus,
    BankOperation,
    BankOperationStatus,
    BankOperationType,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorPayoutInstructionStatus,
    InvestorWithdrawalRequest,
    InvestorWithdrawalRequestStatus,
    LedgerAccount,
    LedgerAccountType,
    LedgerDirection,
    LedgerJournalEntry,
    LedgerPosting,
    LedgerPostingSide,
    ReconciliationSnapshot,
)
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
    is_lender_actor,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.money import Money, MoneyError, normalize_currency
from backend.apps.platform_core.domain.time import (
    business_date,
    business_timezone,
    calendar_day_difference,
    now_utc,
    to_business_time,
)
from backend.apps.platform_core.models import Currency, DomainEvent
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class LedgerError(ValueError):
    pass


class LedgerAuthorizationError(LedgerError):
    pass


class LedgerValidationError(LedgerError):
    pass


INVESTMENT_DEADLINE_DAYS = 30
WITHDRAWAL_DEADLINE_DAYS = 60
BALANCE_AGEING_REMINDER_DAYS = (25, 46, 53, 58, 59, 60)
MAX_IDEMPOTENCY_KEY_LENGTH = 160
REQUEST_FINGERPRINT_METADATA_KEY = "request_fingerprint"
CANCELLATION_FINGERPRINT_METADATA_KEY = "cancellation_request_fingerprint"
CANCELLATION_IDEMPOTENCY_METADATA_KEY = "cancellation_idempotency_key"
INVESTMENT_RESERVATION_FINGERPRINT_METADATA_KEY = "investment_reservation_fingerprint"
INVESTMENT_RELEASE_FINGERPRINT_METADATA_KEY = "investment_release_fingerprint"
PRIMARY_LOAN_CLOSE_FINGERPRINT_METADATA_KEY = "primary_loan_close_fingerprint"
FX_EXCHANGE_FINGERPRINT_METADATA_KEY = "fx_exchange_fingerprint"


@dataclass(frozen=True, slots=True)
class PostingCommand:
    account: LedgerAccount
    side: str
    amount_minor: int
    memo: str = ""


@dataclass(frozen=True, slots=True)
class PostJournalEntryCommand:
    actor: Model
    event_type: str
    direction: str
    currency: str
    gross_amount_minor: int
    net_amount_minor: int
    booking_date: date
    value_date: date
    effective_at: datetime
    received_at: datetime
    source_type: str
    source_id: str
    idempotency_key: str
    postings: list[PostingCommand]
    lender_user_id: str | None = None
    borrower_id: str | None = None
    loan_id: str | None = None
    bank_operation: BankOperation | None = None
    bank_reference: str = ""
    evidence_reference: str = ""
    tax_metadata: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    reversal_of: LedgerJournalEntry | None = None


@dataclass(frozen=True, slots=True)
class DeclareLenderDepositCommand:
    actor: Model
    investor_user_id: str
    amount_minor: int
    currency: str
    booking_date: date
    value_date: date
    collection_account_identifier: str
    payer_name: str
    payer_account_identifier: str = ""
    bank_reference: str = ""
    payment_reference: str = ""
    evidence_reference: str = ""
    notes: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class LenderDepositResult:
    bank_operation: BankOperation
    journal_entry: LedgerJournalEntry
    balance_lot: InvestorBalanceLot


@dataclass(frozen=True, slots=True)
class RegisterInvestorPayoutInstructionCommand:
    actor: Model
    investor_user_id: str
    currency: str
    destination_iban: str
    destination_account_name: str
    is_verified_usable: bool = True
    notes: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RequestInvestorWithdrawalCommand:
    actor: Model
    amount_minor: int
    currency: str
    destination_iban: str
    destination_account_name: str = ""
    notes: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class FinalizeInvestorWithdrawalCommand:
    actor: Model
    withdrawal_request_id: str
    booking_date: date
    value_date: date
    collection_account_identifier: str
    bank_reference: str = ""
    payment_reference: str = ""
    evidence_reference: str = ""
    admin_notes: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class FinalizeBorrowerDisbursementCommand:
    actor: Model
    loan_id: str
    borrower_id: str
    amount_minor: int
    currency: str
    booking_date: date
    value_date: date
    collection_account_identifier: str
    payee_name: str
    payee_account_identifier: str
    bank_reference: str = ""
    payment_reference: str = ""
    evidence_reference: str = ""
    admin_notes: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class InvestorBalanceCreditLineCommand:
    investor_user_id: str
    amount_minor: int
    principal_minor: int = 0
    interest_minor: int = 0
    fee_minor: int = 0
    holding_id: str = ""
    installment_id: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class DeclareBorrowerRepaymentDistributionCommand:
    actor: Model
    loan_id: str
    borrower_id: str
    amount_minor: int
    currency: str
    booking_date: date
    value_date: date
    collection_account_identifier: str
    payer_name: str
    source_type: str
    source_id: str
    distribution_lines: list[InvestorBalanceCreditLineCommand]
    payer_account_identifier: str = ""
    bank_reference: str = ""
    payment_reference: str = ""
    evidence_reference: str = ""
    admin_notes: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class CancelInvestorWithdrawalCommand:
    actor: Model
    withdrawal_request_id: str
    reason: str
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class InvestorWithdrawalFinalizeResult:
    withdrawal_request: InvestorWithdrawalRequest
    bank_operation: BankOperation
    journal_entry: LedgerJournalEntry


@dataclass(frozen=True, slots=True)
class BorrowerDisbursementFinalizeResult:
    bank_operation: BankOperation
    journal_entry: LedgerJournalEntry


@dataclass(frozen=True, slots=True)
class InvestorBalanceCreditResult:
    line_index: int
    investor_user_id: str
    amount_minor: int
    balance_lot: InvestorBalanceLot


@dataclass(frozen=True, slots=True)
class BorrowerRepaymentDistributionResult:
    bank_operation: BankOperation
    journal_entry: LedgerJournalEntry
    balance_credits: list[InvestorBalanceCreditResult]


@dataclass(frozen=True, slots=True)
class InvestorWithdrawalCancelResult:
    withdrawal_request: InvestorWithdrawalRequest
    journal_entry: LedgerJournalEntry


@dataclass(frozen=True, slots=True)
class BalanceAgeingReminderDue:
    lot_id: str
    investor_user_id: str
    currency: str
    amount_minor: int
    day: int
    withdrawal_deadline_at: datetime


@dataclass(frozen=True, slots=True)
class BalanceAgeingPenaltyModeTransition:
    lot_id: str
    investor_user_id: str
    currency: str
    amount_minor: int
    days_overdue: int


@dataclass(frozen=True, slots=True)
class BalanceAgeingForcedWithdrawalCandidate:
    investor_user_id: str
    currency: str
    amount_minor: int
    lot_ids: list[str]
    payout_instruction_id: str


@dataclass(frozen=True, slots=True)
class BalanceAgeingScanResult:
    as_of: datetime
    reminders_due: list[BalanceAgeingReminderDue]
    forced_withdrawal_candidates: list[BalanceAgeingForcedWithdrawalCandidate]
    forced_withdrawal_requests: list[InvestorWithdrawalRequest]
    penalty_mode_transitions: list[BalanceAgeingPenaltyModeTransition]
    skipped_lot_ids: list[str]


@dataclass(frozen=True, slots=True)
class RunBalanceAgeingScanCommand:
    actor: Model
    as_of: datetime | None = None
    currency: str | None = None
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class BalanceSummary:
    investor_user_id: str
    currency: str
    total_available_minor: int
    investable_minor: int
    withdraw_only_minor: int
    overdue_minor: int
    frozen_minor: int
    penalty_mode_minor: int


@dataclass(frozen=True, slots=True)
class BalanceConsumptionPlanLine:
    lot_id: str
    amount_minor: int
    investment_deadline_at: datetime
    withdrawal_deadline_at: datetime


@dataclass(frozen=True, slots=True)
class ReserveInvestmentBalanceCommand:
    actor: Model
    investor_user_id: str
    loan_id: str
    amount_minor: int
    currency: str
    loan_funding_deadline: date
    source_type: str
    source_id: str
    idempotency_key: str
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class InvestmentBalanceReservationResult:
    journal_entry: LedgerJournalEntry
    lot_allocations: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ReleaseInvestmentBalanceReservationCommand:
    actor: Model
    investor_user_id: str
    loan_id: str
    amount_minor: int
    currency: str
    source_type: str
    source_id: str
    reservation_journal_entry_id: str
    lot_allocations: list[dict[str, Any]]
    reason: str
    idempotency_key: str
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class InvestmentBalanceReleaseResult:
    journal_entry: LedgerJournalEntry


@dataclass(frozen=True, slots=True)
class ClosePrimaryLoanFundingCommand:
    actor: Model
    loan_id: str
    borrower_id: str
    accepted_principal_minor: int
    borrower_success_fee_bps: int
    currency: str
    source_type: str
    source_id: str
    idempotency_key: str
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExecuteInvestorFxExchangeLedgerCommand:
    actor: Model
    investor_user_id: str
    source_currency: str
    target_currency: str
    source_amount_minor: int
    gross_target_amount_minor: int
    target_amount_minor: int
    fee_minor: int
    source_type: str
    source_id: str
    idempotency_key: str
    as_of: datetime | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ClosePrimaryLoanFundingResult:
    journal_entry: LedgerJournalEntry
    borrower_success_fee_minor: int
    borrower_disbursement_payable_minor: int


@dataclass(frozen=True, slots=True)
class InvestorFxExchangeLedgerResult:
    source_journal_entry: LedgerJournalEntry
    target_journal_entry: LedgerJournalEntry
    target_balance_lot: InvestorBalanceLot
    source_lot_allocations: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class InvestorBalanceIntegrityBreak:
    investor_user_id: str
    currency: str
    lot_available_minor: int
    liability_posting_minor: int
    difference_minor: int


@dataclass(frozen=True, slots=True)
class CreateReconciliationSnapshotCommand:
    actor: Model
    currency: str
    as_of_date: date
    bank_stated_balance_minor: int
    pending_exception_balance_minor: int = 0
    notes: str = ""
    metadata: dict[str, Any] | None = None


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise LedgerAuthorizationError("Only an active admin can manage ledger operations.")


def _locked_funded_loan_for_disbursement(
    *,
    loan_id: str,
    borrower_id: str,
    currency_code: str,
) -> Model:
    loan_model = apps.get_model("loans", "Loan")
    loan = cast(
        Model | None,
        loan_model.objects.select_for_update()
        .select_related("borrower")
        .filter(id=loan_id)
        .first(),
    )
    if loan is None:
        raise LedgerValidationError("Loan does not exist.")
    if str(getattr(loan, "status", "")) != "funded":
        raise LedgerValidationError("Loan must be funded before borrower disbursement.")
    if str(getattr(loan, "currency_id", "")) != currency_code:
        raise LedgerValidationError("Loan currency must match borrower disbursement currency.")
    loan_borrower_id = str(getattr(loan, "borrower_id", ""))
    if str(borrower_id) != loan_borrower_id:
        raise LedgerValidationError("Borrower does not match loan.")
    loan_ref = cast(Any, loan)
    borrower = cast(Model, loan_ref.borrower)
    if not bool(getattr(borrower, "can_transact", False)):
        raise LedgerValidationError(
            "Borrower KYB must be approved and free of compliance hold."
        )
    return loan


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise LedgerValidationError(f"{label} is required.")
    return cleaned


def _clean_idempotency_key(value: str) -> str:
    key = _clean_required(value, "Idempotency key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise LedgerValidationError(
            f"Idempotency key cannot exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )
    return key


def _clean_iban(value: str) -> str:
    iban = "".join(value.upper().split())
    if len(iban) < 15 or len(iban) > 34:
        raise LedgerValidationError("Destination IBAN must be between 15 and 34 characters.")
    if not iban[:2].isalpha() or not iban[2:].isalnum():
        raise LedgerValidationError("Destination IBAN must look like a valid IBAN.")
    return iban


def _derived_idempotency_key(namespace: str, source_key: str) -> str:
    key = f"{namespace}:{source_key}"
    if len(key) <= MAX_IDEMPOTENCY_KEY_LENGTH:
        return key
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def _enabled_currency(currency_code: str) -> Currency:
    try:
        code = normalize_currency(currency_code)
    except MoneyError as exc:
        raise LedgerValidationError(str(exc)) from exc
    currency = Currency.objects.filter(code=code, is_enabled=True).first()
    if currency is None:
        raise LedgerValidationError(f"Currency is not enabled: {code}")
    return currency


def _validate_money(amount_minor: int, currency_code: str, label: str) -> int:
    try:
        Money(amount_minor, currency_code)
    except MoneyError as exc:
        raise LedgerValidationError(str(exc)) from exc
    if amount_minor <= 0:
        raise LedgerValidationError(f"{label} must be positive.")
    return amount_minor


def _validate_nonnegative_money(amount_minor: int, currency_code: str, label: str) -> int:
    try:
        Money(amount_minor, currency_code)
    except MoneyError as exc:
        raise LedgerValidationError(str(exc)) from exc
    if amount_minor < 0:
        raise LedgerValidationError(f"{label} cannot be negative.")
    return amount_minor


def _stable_json_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _metadata_without_reserved(metadata: dict[str, Any] | None) -> dict[str, Any]:
    cleaned = dict(metadata or {})
    cleaned.pop(REQUEST_FINGERPRINT_METADATA_KEY, None)
    return cleaned


def _assert_fingerprint_matches(
    *,
    stored_metadata: dict[str, Any],
    expected_fingerprint: str | None,
) -> None:
    if expected_fingerprint is None:
        return
    stored_fingerprint = stored_metadata.get(REQUEST_FINGERPRINT_METADATA_KEY)
    if stored_fingerprint is None:
        return
    if stored_fingerprint != expected_fingerprint:
        raise LedgerValidationError("Idempotency key was already used for a different request.")


def _ledger_direction(value: str) -> LedgerDirection:
    try:
        return LedgerDirection(value)
    except ValueError as exc:
        raise LedgerValidationError(f"Invalid ledger direction: {value}") from exc


def _posting_side(value: str) -> LedgerPostingSide:
    try:
        return LedgerPostingSide(value)
    except ValueError as exc:
        raise LedgerValidationError(f"Invalid posting side: {value}") from exc


def _bank_operation_type(value: str) -> BankOperationType:
    try:
        return BankOperationType(value)
    except ValueError as exc:
        raise LedgerValidationError(f"Invalid bank operation type: {value}") from exc


def _account_code(
    *,
    account_type: str,
    currency_code: str,
    owner_type: str = "",
    owner_id: str = "",
) -> str:
    owner_part = f":{owner_type}:{owner_id}" if owner_type and owner_id else ""
    return f"{account_type}:{currency_code}{owner_part}"


def get_or_create_ledger_account(
    *,
    account_type: str,
    currency: Currency,
    owner_type: str = "",
    owner_id: str = "",
    name: str = "",
) -> LedgerAccount:
    try:
        parsed_type = LedgerAccountType(account_type)
    except ValueError as exc:
        raise LedgerValidationError(f"Invalid ledger account type: {account_type}") from exc
    code = _account_code(
        account_type=parsed_type,
        currency_code=currency.code,
        owner_type=owner_type,
        owner_id=owner_id,
    )
    account, _ = LedgerAccount.objects.get_or_create(
        code=code,
        defaults={
            "name": name or code.replace(":", " "),
            "account_type": parsed_type,
            "currency": currency,
            "owner_type": owner_type,
            "owner_id": owner_id,
        },
    )
    return account


def _investor_for_id(investor_user_id: str) -> Model:
    user_model = get_user_model()
    investor = cast(Model | None, user_model.objects.filter(id=investor_user_id).first())
    if investor is None:
        raise LedgerValidationError("Investor account does not exist.")
    if not is_lender_actor(investor):
        raise LedgerValidationError("Investor account must be an active lender account.")
    return investor


def _lender_account_for_id(investor_user_id: str) -> Model:
    user_model = get_user_model()
    investor = cast(Model | None, user_model.objects.filter(id=investor_user_id).first())
    if investor is None:
        raise LedgerValidationError("Investor account does not exist.")
    account_type = str(getattr(investor, "account_type", ""))
    if account_type not in {"natural_person_lender", "legal_entity_lender_representative"}:
        raise LedgerValidationError("Account must be a lender account.")
    return investor


def _received_at_from_value_date(value_date: date) -> datetime:
    return datetime.combine(value_date, time.min, tzinfo=business_timezone())


def _lot_deadlines(received_at: datetime) -> tuple[datetime, datetime]:
    business_received_at = to_business_time(received_at)
    investment_deadline_at = business_received_at + timedelta(days=INVESTMENT_DEADLINE_DAYS)
    withdrawal_deadline_at = business_received_at + timedelta(days=WITHDRAWAL_DEADLINE_DAYS)
    return investment_deadline_at, withdrawal_deadline_at


def _validate_lot_conservation_values(
    *,
    original_amount_minor: int,
    available_amount_minor: int,
    invested_amount_minor: int = 0,
    converted_amount_minor: int = 0,
    withdrawn_amount_minor: int = 0,
    penalized_amount_minor: int = 0,
    currency_code: str,
) -> None:
    amounts = {
        "Original amount": original_amount_minor,
        "Available amount": available_amount_minor,
        "Invested amount": invested_amount_minor,
        "Converted amount": converted_amount_minor,
        "Withdrawn amount": withdrawn_amount_minor,
        "Penalized amount": penalized_amount_minor,
    }
    for label, amount in amounts.items():
        _validate_nonnegative_money(amount, currency_code, label)
    consumed_total = (
        available_amount_minor
        + invested_amount_minor
        + converted_amount_minor
        + withdrawn_amount_minor
        + penalized_amount_minor
    )
    if consumed_total != original_amount_minor:
        raise LedgerValidationError("Balance-lot amounts must conserve the original amount.")


def _validate_lot_conservation(lot: InvestorBalanceLot) -> None:
    _validate_lot_conservation_values(
        original_amount_minor=lot.original_amount_minor,
        available_amount_minor=lot.available_amount_minor,
        invested_amount_minor=lot.invested_amount_minor,
        converted_amount_minor=lot.converted_amount_minor,
        withdrawn_amount_minor=lot.withdrawn_amount_minor,
        penalized_amount_minor=lot.penalized_amount_minor,
        currency_code=lot.currency_id,
    )


def _validate_postings(
    *,
    postings: list[PostingCommand],
    currency: Currency,
) -> tuple[int, int]:
    if len(postings) < 2:
        raise LedgerValidationError("A journal entry requires at least two postings.")
    debit_total = 0
    credit_total = 0
    sides_by_account: dict[str, set[LedgerPostingSide]] = {}
    for posting in postings:
        if posting.account.currency_id != currency.code:
            raise LedgerValidationError("Posting account currency must match journal currency.")
        amount = _validate_money(posting.amount_minor, currency.code, "Posting amount")
        side = _posting_side(posting.side)
        account_sides = sides_by_account.setdefault(str(posting.account.pk), set())
        account_sides.add(side)
        if len(account_sides) > 1:
            raise LedgerValidationError(
                "A ledger account cannot appear on both sides of one journal entry."
            )
        if side == LedgerPostingSide.DEBIT:
            debit_total += amount
        else:
            credit_total += amount
    if debit_total != credit_total:
        raise LedgerValidationError("Ledger postings must balance debit and credit totals.")
    return debit_total, credit_total


def _validate_received_at_matches_value_date(*, received_at: datetime, value_date: date) -> None:
    if to_business_time(received_at).date() != value_date:
        raise LedgerValidationError("Received timestamp must match the journal value date.")


def _journal_request_fingerprint(
    command: PostJournalEntryCommand,
    *,
    currency_code: str,
    idempotency_key: str,
) -> str:
    actor_ref = actor_ref_for_user(command.actor)
    metadata = _metadata_without_reserved(command.metadata)
    return _stable_json_fingerprint(
        {
            "actor_type": actor_ref.actor_type,
            "actor_id": actor_ref.actor_id,
            "event_type": command.event_type.strip(),
            "direction": command.direction,
            "currency": currency_code,
            "gross_amount_minor": command.gross_amount_minor,
            "net_amount_minor": command.net_amount_minor,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "effective_at": command.effective_at.isoformat(),
            "received_at": command.received_at.isoformat(),
            "source_type": command.source_type.strip(),
            "source_id": command.source_id.strip(),
            "lender_user_id": str(command.lender_user_id or ""),
            "borrower_id": str(command.borrower_id or ""),
            "loan_id": str(command.loan_id or ""),
            "bank_operation_id": str(command.bank_operation.pk if command.bank_operation else ""),
            "bank_reference": command.bank_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "tax_metadata": command.tax_metadata or {},
            "metadata": metadata,
            "reversal_of_id": str(command.reversal_of.pk if command.reversal_of else ""),
            "idempotency_key": idempotency_key,
            "postings": [
                {
                    "account_id": str(posting.account.pk),
                    "side": posting.side,
                    "amount_minor": posting.amount_minor,
                    "memo": posting.memo.strip(),
                }
                for posting in command.postings
            ],
        }
    )


def _deposit_request_fingerprint(
    command: DeclareLenderDepositCommand,
    *,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "investor_user_id": str(command.investor_user_id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "payer_name": command.payer_name.strip(),
            "payer_account_identifier": command.payer_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "notes": command.notes.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _withdrawal_request_fingerprint(
    command: RequestInvestorWithdrawalCommand,
    *,
    actor_id: str,
    currency_code: str,
    amount_minor: int,
    destination_iban: str,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "actor_id": actor_id,
            "amount_minor": amount_minor,
            "currency": currency_code,
            "destination_iban": destination_iban,
            "destination_account_name": command.destination_account_name.strip(),
            "notes": command.notes.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _withdrawal_finalization_fingerprint(
    command: FinalizeInvestorWithdrawalCommand,
    *,
    withdrawal_request: InvestorWithdrawalRequest,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "withdrawal_request_id": str(withdrawal_request.id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "admin_notes": command.admin_notes.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _borrower_disbursement_finalization_fingerprint(
    command: FinalizeBorrowerDisbursementCommand,
    *,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "borrower_id": str(command.borrower_id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "payee_name": command.payee_name.strip(),
            "payee_account_identifier": command.payee_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "admin_notes": command.admin_notes.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _borrower_repayment_distribution_fingerprint(
    command: DeclareBorrowerRepaymentDistributionCommand,
    *,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "borrower_id": str(command.borrower_id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "payer_name": command.payer_name.strip(),
            "payer_account_identifier": command.payer_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "admin_notes": command.admin_notes.strip(),
            "source_type": command.source_type.strip(),
            "source_id": command.source_id.strip(),
            "idempotency_key": idempotency_key,
            "distribution_lines": [
                {
                    "investor_user_id": str(line.investor_user_id),
                    "amount_minor": line.amount_minor,
                    "principal_minor": line.principal_minor,
                    "interest_minor": line.interest_minor,
                    "fee_minor": line.fee_minor,
                    "holding_id": str(line.holding_id),
                    "installment_id": str(line.installment_id),
                    "metadata": line.metadata or {},
                }
                for line in command.distribution_lines
            ],
        }
    )


def _withdrawal_cancellation_fingerprint(
    command: CancelInvestorWithdrawalCommand,
    *,
    withdrawal_request: InvestorWithdrawalRequest,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "withdrawal_request_id": str(withdrawal_request.id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "reason": command.reason.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _existing_journal_entry_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str | None = None,
) -> LedgerJournalEntry | None:
    existing = LedgerJournalEntry.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    _assert_fingerprint_matches(
        stored_metadata=cast(dict[str, Any], existing.metadata),
        expected_fingerprint=expected_fingerprint,
    )
    return cast(LedgerJournalEntry, existing)


@transaction.atomic
def post_journal_entry(command: PostJournalEntryCommand) -> LedgerJournalEntry:
    currency = _enabled_currency(command.currency)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    request_fingerprint = _journal_request_fingerprint(
        command,
        currency_code=currency.code,
        idempotency_key=idempotency_key,
    )
    existing = _existing_journal_entry_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    _clean_required(command.event_type, "Event type")
    _clean_required(command.source_type, "Source type")
    _clean_required(command.source_id, "Source id")
    _ledger_direction(command.direction)
    _validate_money(command.gross_amount_minor, currency.code, "Gross amount")
    _validate_nonnegative_money(command.net_amount_minor, currency.code, "Net amount")
    if command.net_amount_minor > command.gross_amount_minor:
        raise LedgerValidationError("Net amount cannot exceed gross amount.")
    _validate_received_at_matches_value_date(
        received_at=command.received_at,
        value_date=command.value_date,
    )
    _validate_postings(postings=command.postings, currency=currency)
    actor_ref = actor_ref_for_user(command.actor)
    metadata = _metadata_without_reserved(command.metadata)
    metadata[REQUEST_FINGERPRINT_METADATA_KEY] = request_fingerprint
    try:
        with transaction.atomic():
            journal_entry = cast(
                LedgerJournalEntry,
                LedgerJournalEntry.objects.create(
                    event_type=command.event_type.strip(),
                    direction=command.direction,
                    booking_date=command.booking_date,
                    value_date=command.value_date,
                    effective_at=command.effective_at,
                    received_at=command.received_at,
                    currency=currency,
                    gross_amount_minor=command.gross_amount_minor,
                    net_amount_minor=command.net_amount_minor,
                    source_type=command.source_type.strip(),
                    source_id=command.source_id.strip(),
                    lender_user_id=command.lender_user_id,
                    borrower_id=command.borrower_id,
                    loan_id=command.loan_id,
                    bank_operation=command.bank_operation,
                    bank_reference=command.bank_reference.strip(),
                    evidence_reference=command.evidence_reference.strip(),
                    actor_type=actor_ref.actor_type,
                    actor_id=actor_ref.actor_id,
                    tax_metadata=command.tax_metadata or {},
                    metadata=metadata,
                    reversal_of=command.reversal_of,
                    idempotency_key=idempotency_key,
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_journal_entry_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    LedgerPosting.objects.bulk_create(
        [
            LedgerPosting(
                journal_entry=journal_entry,
                account=posting.account,
                side=posting.side,
                amount_minor=posting.amount_minor,
                currency=currency,
                memo=posting.memo.strip(),
            )
            for posting in command.postings
        ]
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.journal_entry_posted",
            target_type="LedgerJournalEntry",
            target_id=str(journal_entry.id),
            metadata={
                "event_type": journal_entry.event_type,
                "currency": currency.code,
                "gross_amount_minor": journal_entry.gross_amount_minor,
                "source_type": journal_entry.source_type,
                "source_id": journal_entry.source_id,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LedgerJournalEntryPosted",
            aggregate_type="LedgerJournalEntry",
            aggregate_id=str(journal_entry.id),
            payload={
                "event_type": journal_entry.event_type,
                "currency": currency.code,
                "gross_amount_minor": journal_entry.gross_amount_minor,
                "source_type": journal_entry.source_type,
                "source_id": journal_entry.source_id,
            },
            idempotency_key=f"ledger:{journal_entry.id}:posted",
        )
    )
    return journal_entry


def _existing_lender_deposit_result(
    idempotency_key: str,
    *,
    expected_fingerprint: str | None = None,
) -> LenderDepositResult | None:
    existing_operation = BankOperation.objects.filter(idempotency_key=idempotency_key).first()
    if existing_operation is None:
        return None
    _assert_fingerprint_matches(
        stored_metadata=cast(dict[str, Any], existing_operation.metadata),
        expected_fingerprint=expected_fingerprint,
    )
    existing_journal = existing_operation.journal_entries.first()
    if existing_journal is None:
        raise LedgerValidationError("Existing bank operation has no journal entry.")
    existing_lot = existing_journal.balance_lots.first()
    if existing_lot is None:
        raise LedgerValidationError("Existing lender deposit has no balance lot.")
    return LenderDepositResult(
        cast(BankOperation, existing_operation),
        cast(LedgerJournalEntry, existing_journal),
        cast(InvestorBalanceLot, existing_lot),
    )


@transaction.atomic
def register_investor_payout_instruction(
    command: RegisterInvestorPayoutInstructionCommand,
) -> InvestorPayoutInstruction:
    _require_admin_actor(command.actor)
    investor = _lender_account_for_id(command.investor_user_id)
    currency = _enabled_currency(command.currency)
    destination_iban = _clean_iban(command.destination_iban)
    account_name = _clean_required(command.destination_account_name, "Destination account name")
    verified_at = now_utc() if command.is_verified_usable else None

    InvestorPayoutInstruction.objects.select_for_update().filter(
        investor_user_id=investor.pk,
        currency=currency,
        status=InvestorPayoutInstructionStatus.ACTIVE,
    ).update(status=InvestorPayoutInstructionStatus.DISABLED)
    instruction = InvestorPayoutInstruction.objects.create(
        investor_user_id=investor.pk,
        currency=currency,
        destination_iban=destination_iban,
        destination_account_name=account_name,
        is_verified_usable=command.is_verified_usable,
        verified_by_admin_id=command.actor.pk if command.is_verified_usable else None,
        verified_at=verified_at,
        created_by_admin_id=command.actor.pk,
        notes=command.notes.strip(),
        metadata=command.metadata or {},
    )
    actor_ref = actor_ref_for_user(command.actor)
    event_metadata = {
        "investor_user_id": str(investor.pk),
        "currency": currency.code,
        "instruction_id": str(instruction.id),
        "is_verified_usable": instruction.is_verified_usable,
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.investor_payout_instruction_registered",
            target_type="InvestorPayoutInstruction",
            target_id=str(instruction.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="InvestorPayoutInstructionRegistered",
            aggregate_type="InvestorPayoutInstruction",
            aggregate_id=str(instruction.id),
            payload=event_metadata,
            idempotency_key=f"payout-instruction:{instruction.id}:registered",
        )
    )
    return instruction


@transaction.atomic
def declare_lender_deposit(command: DeclareLenderDepositCommand) -> LenderDepositResult:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    currency = _enabled_currency(command.currency)
    amount_minor = _validate_money(command.amount_minor, currency.code, "Deposit amount")
    request_fingerprint = _deposit_request_fingerprint(
        command,
        currency_code=currency.code,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing_result = _existing_lender_deposit_result(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing_result is not None:
        return existing_result

    investor = _investor_for_id(command.investor_user_id)
    collection_account_identifier = _clean_required(
        command.collection_account_identifier,
        "Collection account identifier",
    )
    received_at = _received_at_from_value_date(command.value_date)
    confirmed_at = now_utc()
    bank_operation_metadata = {
        "matched_investor_email": str(getattr(investor, "email", "")),
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
    }
    try:
        with transaction.atomic():
            bank_operation = BankOperation.objects.create(
                operation_type=_bank_operation_type(BankOperationType.LENDER_DEPOSIT),
                status=BankOperationStatus.RECONCILED,
                amount_minor=amount_minor,
                currency=currency,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=collection_account_identifier,
                payer_name=command.payer_name.strip(),
                payer_account_identifier=command.payer_account_identifier.strip(),
                payee_name="Garanta Finanzgruppe AG",
                payee_account_identifier=collection_account_identifier,
                bank_reference=command.bank_reference.strip(),
                payment_reference=command.payment_reference.strip(),
                linked_object_type="investor",
                linked_object_id=str(investor.pk),
                evidence_reference=command.evidence_reference.strip(),
                confirmed_by_admin_id=command.actor.pk,
                confirmed_at=confirmed_at,
                notes=command.notes.strip(),
                metadata=bank_operation_metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_lender_deposit_result(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    collection_cash_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
        name=f"{currency.code} collection cash",
    )
    investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=str(investor.pk),
        name=f"{currency.code} investor balance liability {investor.pk}",
    )
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="lender_deposit_reconciled",
            direction=LedgerDirection.IN,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=command.booking_date,
            value_date=command.value_date,
            effective_at=confirmed_at,
            received_at=received_at,
            source_type="bank_operation",
            source_id=str(bank_operation.id),
            lender_user_id=str(investor.pk),
            bank_operation=bank_operation,
            bank_reference=command.bank_reference,
            evidence_reference=command.evidence_reference,
            idempotency_key=_derived_idempotency_key("ledger", idempotency_key),
            postings=[
                PostingCommand(
                    account=collection_cash_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Cash received into collection account",
                ),
                PostingCommand(
                    account=investor_liability_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Investor balance liability credited",
                ),
            ],
            metadata={
                "bank_operation_type": BankOperationType.LENDER_DEPOSIT,
                "payment_reference": command.payment_reference.strip(),
            },
        )
    )
    investment_deadline_at, withdrawal_deadline_at = _lot_deadlines(received_at)
    _validate_lot_conservation_values(
        original_amount_minor=amount_minor,
        available_amount_minor=amount_minor,
        currency_code=currency.code,
    )
    balance_lot = InvestorBalanceLot.objects.create(
        investor_user_id=investor.pk,
        currency=currency,
        source_journal_entry=journal_entry,
        source_type=BalanceLotSourceType.DEPOSIT,
        source_id=str(bank_operation.id),
        received_at=received_at,
        investment_deadline_at=investment_deadline_at,
        withdrawal_deadline_at=withdrawal_deadline_at,
        original_amount_minor=amount_minor,
        available_amount_minor=amount_minor,
        lineage=[{"source_type": "bank_operation", "source_id": str(bank_operation.id)}],
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.lender_deposit_declared",
            target_type="BankOperation",
            target_id=str(bank_operation.id),
            metadata={
                "investor_user_id": str(investor.pk),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "balance_lot_id": str(balance_lot.id),
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LenderDepositDeclared",
            aggregate_type="BankOperation",
            aggregate_id=str(bank_operation.id),
            payload={
                "investor_user_id": str(investor.pk),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "balance_lot_id": str(balance_lot.id),
                "journal_entry_id": str(journal_entry.id),
            },
            idempotency_key=f"bank-operation:{bank_operation.id}:lender-deposit-declared",
        )
    )
    return LenderDepositResult(bank_operation, journal_entry, balance_lot)


def _existing_withdrawal_request_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str | None = None,
) -> InvestorWithdrawalRequest | None:
    existing = InvestorWithdrawalRequest.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    _assert_fingerprint_matches(
        stored_metadata=cast(dict[str, Any], existing.metadata),
        expected_fingerprint=expected_fingerprint,
    )
    return existing


def _existing_withdrawal_finalization_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str | None = None,
) -> InvestorWithdrawalFinalizeResult | None:
    bank_operation = BankOperation.objects.filter(idempotency_key=idempotency_key).first()
    if bank_operation is None:
        return None
    _assert_fingerprint_matches(
        stored_metadata=cast(dict[str, Any], bank_operation.metadata),
        expected_fingerprint=expected_fingerprint,
    )
    withdrawal_request = bank_operation.withdrawal_requests.first()
    if withdrawal_request is None:
        raise LedgerValidationError("Existing withdrawal bank operation has no request.")
    journal_entry = bank_operation.journal_entries.first()
    if journal_entry is None:
        raise LedgerValidationError("Existing withdrawal bank operation has no journal entry.")
    return InvestorWithdrawalFinalizeResult(
        withdrawal_request,
        cast(BankOperation, bank_operation),
        cast(LedgerJournalEntry, journal_entry),
    )


def _existing_borrower_disbursement_finalization_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str | None = None,
) -> BorrowerDisbursementFinalizeResult | None:
    bank_operation = BankOperation.objects.filter(idempotency_key=idempotency_key).first()
    if bank_operation is None:
        return None
    _assert_fingerprint_matches(
        stored_metadata=cast(dict[str, Any], bank_operation.metadata),
        expected_fingerprint=expected_fingerprint,
    )
    journal_entry = bank_operation.journal_entries.first()
    if journal_entry is None:
        raise LedgerValidationError(
            "Existing borrower disbursement bank operation has no journal entry."
        )
    return BorrowerDisbursementFinalizeResult(
        cast(BankOperation, bank_operation),
        cast(LedgerJournalEntry, journal_entry),
    )


def _existing_borrower_repayment_distribution_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str | None = None,
) -> BorrowerRepaymentDistributionResult | None:
    bank_operation = BankOperation.objects.filter(idempotency_key=idempotency_key).first()
    if bank_operation is None:
        return None
    _assert_fingerprint_matches(
        stored_metadata=cast(dict[str, Any], bank_operation.metadata),
        expected_fingerprint=expected_fingerprint,
    )
    journal_entry = bank_operation.journal_entries.first()
    if journal_entry is None:
        raise LedgerValidationError(
            "Existing borrower repayment bank operation has no journal entry."
        )
    credits: list[InvestorBalanceCreditResult] = []
    for index, lot in enumerate(journal_entry.balance_lots.order_by("created_at", "id")):
        credits.append(
            InvestorBalanceCreditResult(
                line_index=index,
                investor_user_id=str(lot.investor_user_id),
                amount_minor=lot.original_amount_minor,
                balance_lot=cast(InvestorBalanceLot, lot),
            )
        )
    return BorrowerRepaymentDistributionResult(
        cast(BankOperation, bank_operation),
        cast(LedgerJournalEntry, journal_entry),
        credits,
    )


def _withdrawal_lots_for_update(
    *,
    investor_user_id: str,
    currency: Currency,
) -> list[InvestorBalanceLot]:
    return list(
        InvestorBalanceLot.objects.select_for_update()
        .filter(
            investor_user_id=investor_user_id,
            currency=currency,
            status__in=[BalanceLotStatus.AVAILABLE, BalanceLotStatus.PENALTY_MODE],
            available_amount_minor__gt=0,
        )
        .order_by("received_at", "created_at", "id")
    )


def _consume_lots_for_withdrawal(
    *,
    lots: list[InvestorBalanceLot],
    amount_minor: int,
    currency_code: str,
) -> list[dict[str, Any]]:
    remaining = amount_minor
    allocations: list[dict[str, Any]] = []
    for lot in lots:
        _validate_lot_conservation(lot)
        if remaining <= 0:
            break
        amount = min(remaining, lot.available_amount_minor)
        if amount <= 0:
            continue
        status_before_withdrawal = str(lot.status)
        available_before_withdrawal = lot.available_amount_minor
        withdrawn_before_withdrawal = lot.withdrawn_amount_minor
        new_available = lot.available_amount_minor - amount
        new_withdrawn = lot.withdrawn_amount_minor + amount
        new_status = BalanceLotStatus.CONSUMED if new_available == 0 else lot.status
        _validate_lot_conservation_values(
            original_amount_minor=lot.original_amount_minor,
            available_amount_minor=new_available,
            invested_amount_minor=lot.invested_amount_minor,
            converted_amount_minor=lot.converted_amount_minor,
            withdrawn_amount_minor=new_withdrawn,
            penalized_amount_minor=lot.penalized_amount_minor,
            currency_code=currency_code,
        )
        lot.available_amount_minor = new_available
        lot.withdrawn_amount_minor = new_withdrawn
        lot.status = new_status
        lot.save(update_fields=["available_amount_minor", "withdrawn_amount_minor", "status"])
        allocations.append(
            {
                "lot_id": str(lot.id),
                "amount_minor": amount,
                "status_before_withdrawal": status_before_withdrawal,
                "available_before_withdrawal_minor": available_before_withdrawal,
                "withdrawn_before_withdrawal_minor": withdrawn_before_withdrawal,
                "received_at": lot.received_at.isoformat(),
                "investment_deadline_at": lot.investment_deadline_at.isoformat(),
                "withdrawal_deadline_at": lot.withdrawal_deadline_at.isoformat(),
                "source_type": lot.source_type,
                "source_id": lot.source_id,
            }
        )
        remaining -= amount

    if remaining > 0:
        raise LedgerValidationError("Insufficient withdrawable balance for the requested amount.")
    return allocations


def _restore_lots_from_withdrawal_allocations(
    *,
    withdrawal_request: InvestorWithdrawalRequest,
    currency: Currency,
) -> None:
    allocations = cast(list[dict[str, Any]], withdrawal_request.lot_allocations)
    if not allocations:
        raise LedgerValidationError("Withdrawal request has no lot allocations to restore.")
    lot_ids: list[str] = []
    for allocation in allocations:
        lot_id = str(allocation.get("lot_id", ""))
        if not lot_id:
            raise LedgerValidationError("Withdrawal allocation is missing a lot id.")
        lot_ids.append(lot_id)

    lots = {
        str(lot.id): lot
        for lot in InvestorBalanceLot.objects.select_for_update().filter(
            id__in=lot_ids,
            investor_user_id=withdrawal_request.investor_user_id,
            currency=currency,
        )
    }
    total_restored = 0
    for allocation in allocations:
        lot_id = str(allocation["lot_id"])
        lot = lots.get(lot_id)
        if lot is None:
            raise LedgerValidationError("Withdrawal allocation references an unavailable lot.")
        amount_value = allocation.get("amount_minor")
        if type(amount_value) is not int:
            raise LedgerValidationError("Withdrawal allocation amount must be integer minor units.")
        amount = _validate_money(amount_value, currency.code, "Withdrawal allocation amount")
        previous_status = str(
            allocation.get("status_before_withdrawal") or BalanceLotStatus.AVAILABLE
        )
        if previous_status not in {
            BalanceLotStatus.AVAILABLE.value,
            BalanceLotStatus.PENALTY_MODE.value,
        }:
            raise LedgerValidationError("Withdrawal allocation has an invalid previous lot status.")
        _validate_lot_conservation(lot)
        new_available = lot.available_amount_minor + amount
        new_withdrawn = lot.withdrawn_amount_minor - amount
        if new_withdrawn < 0:
            raise LedgerValidationError("Withdrawal allocation would over-restore a balance lot.")
        _validate_lot_conservation_values(
            original_amount_minor=lot.original_amount_minor,
            available_amount_minor=new_available,
            invested_amount_minor=lot.invested_amount_minor,
            converted_amount_minor=lot.converted_amount_minor,
            withdrawn_amount_minor=new_withdrawn,
            penalized_amount_minor=lot.penalized_amount_minor,
            currency_code=currency.code,
        )
        lot.available_amount_minor = new_available
        lot.withdrawn_amount_minor = new_withdrawn
        lot.status = previous_status
        lot.save(update_fields=["available_amount_minor", "withdrawn_amount_minor", "status"])
        total_restored += amount

    if total_restored != withdrawal_request.amount_minor:
        raise LedgerValidationError("Withdrawal allocations do not match the request amount.")


@transaction.atomic
def request_investor_withdrawal(
    command: RequestInvestorWithdrawalCommand,
) -> InvestorWithdrawalRequest:
    if not user_can_access_financial_features(command.actor):
        raise LedgerAuthorizationError("Investor account cannot access financial features.")
    investor_id = str(command.actor.pk)
    currency = _enabled_currency(command.currency)
    amount_minor = _validate_money(command.amount_minor, currency.code, "Withdrawal amount")
    destination_iban = _clean_iban(command.destination_iban)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    request_fingerprint = _withdrawal_request_fingerprint(
        command,
        actor_id=investor_id,
        currency_code=currency.code,
        amount_minor=amount_minor,
        destination_iban=destination_iban,
        idempotency_key=idempotency_key,
    )
    existing = _existing_withdrawal_request_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing

    requested_at = now_utc()
    value_date = to_business_time(requested_at).date()
    metadata = {REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint}
    try:
        with transaction.atomic():
            withdrawal_request = InvestorWithdrawalRequest.objects.create(
                investor_user_id=command.actor.pk,
                amount_minor=amount_minor,
                currency=currency,
                destination_iban=destination_iban,
                destination_account_name=command.destination_account_name.strip(),
                requested_by_user_id=command.actor.pk,
                requested_at=requested_at,
                notes=command.notes.strip(),
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_withdrawal_request_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    lots = _withdrawal_lots_for_update(investor_user_id=investor_id, currency=currency)
    allocations = _consume_lots_for_withdrawal(
        lots=lots,
        amount_minor=amount_minor,
        currency_code=currency.code,
    )
    investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=investor_id,
        name=f"{currency.code} investor balance liability {investor_id}",
    )
    withdrawal_payable_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.WITHDRAWAL_PAYABLE,
        currency=currency,
        owner_type="investor",
        owner_id=investor_id,
        name=f"{currency.code} withdrawal payable {investor_id}",
    )
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="investor_withdrawal_requested",
            direction=LedgerDirection.OUT,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=requested_at,
            received_at=requested_at,
            source_type="withdrawal_request",
            source_id=str(withdrawal_request.id),
            lender_user_id=investor_id,
            idempotency_key=_derived_idempotency_key("ledger-withdrawal-request", idempotency_key),
            postings=[
                PostingCommand(
                    account=investor_liability_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Investor balance liability reserved for withdrawal",
                ),
                PostingCommand(
                    account=withdrawal_payable_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Withdrawal payable created",
                ),
            ],
            metadata={"withdrawal_request_id": str(withdrawal_request.id)},
        )
    )
    withdrawal_request.request_journal_entry = journal_entry
    withdrawal_request.lot_allocations = allocations
    withdrawal_request.save(
        update_fields=["request_journal_entry", "lot_allocations", "updated_at"]
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.investor_withdrawal_requested",
            target_type="InvestorWithdrawalRequest",
            target_id=str(withdrawal_request.id),
            metadata={
                "investor_user_id": investor_id,
                "currency": currency.code,
                "amount_minor": amount_minor,
                "lot_allocations": allocations,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="InvestorWithdrawalRequested",
            aggregate_type="InvestorWithdrawalRequest",
            aggregate_id=str(withdrawal_request.id),
            payload={
                "investor_user_id": investor_id,
                "currency": currency.code,
                "amount_minor": amount_minor,
                "journal_entry_id": str(journal_entry.id),
            },
            idempotency_key=f"withdrawal-request:{withdrawal_request.id}:requested",
        )
    )
    return withdrawal_request


@transaction.atomic
def finalize_investor_withdrawal(
    command: FinalizeInvestorWithdrawalCommand,
) -> InvestorWithdrawalFinalizeResult:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    withdrawal_request = (
        InvestorWithdrawalRequest.objects.select_for_update()
        .filter(id=command.withdrawal_request_id)
        .first()
    )
    if withdrawal_request is None:
        raise LedgerValidationError("Withdrawal request does not exist.")
    amount_minor = _validate_money(
        withdrawal_request.amount_minor,
        withdrawal_request.currency_id,
        "Withdrawal amount",
    )
    request_fingerprint = _withdrawal_finalization_fingerprint(
        command,
        withdrawal_request=withdrawal_request,
        currency_code=withdrawal_request.currency_id,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_withdrawal_finalization_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    if withdrawal_request.status != InvestorWithdrawalRequestStatus.REQUESTED:
        if (
            withdrawal_request.status == InvestorWithdrawalRequestStatus.FINALIZED
            and withdrawal_request.bank_operation is not None
            and withdrawal_request.finalization_journal_entry is not None
        ):
            return InvestorWithdrawalFinalizeResult(
                withdrawal_request,
                withdrawal_request.bank_operation,
                withdrawal_request.finalization_journal_entry,
            )
        raise LedgerValidationError("Withdrawal request is not pending finalization.")

    currency = withdrawal_request.currency
    collection_account_identifier = _clean_required(
        command.collection_account_identifier,
        "Collection account identifier",
    )
    finalized_at = now_utc()
    bank_operation_metadata = {REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint}
    try:
        with transaction.atomic():
            bank_operation = BankOperation.objects.create(
                operation_type=_bank_operation_type(BankOperationType.LENDER_WITHDRAWAL),
                status=BankOperationStatus.RECONCILED,
                amount_minor=amount_minor,
                currency=currency,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=collection_account_identifier,
                payer_name="Garanta Finanzgruppe AG",
                payer_account_identifier=collection_account_identifier,
                payee_name=withdrawal_request.destination_account_name,
                payee_account_identifier=withdrawal_request.destination_iban,
                bank_reference=command.bank_reference.strip(),
                payment_reference=command.payment_reference.strip(),
                linked_object_type="withdrawal_request",
                linked_object_id=str(withdrawal_request.id),
                evidence_reference=command.evidence_reference.strip(),
                confirmed_by_admin_id=command.actor.pk,
                confirmed_at=finalized_at,
                notes=command.admin_notes.strip(),
                metadata=bank_operation_metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_withdrawal_finalization_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    collection_cash_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
        name=f"{currency.code} collection cash",
    )
    withdrawal_payable_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.WITHDRAWAL_PAYABLE,
        currency=currency,
        owner_type="investor",
        owner_id=str(withdrawal_request.investor_user_id),
        name=f"{currency.code} withdrawal payable {withdrawal_request.investor_user_id}",
    )
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="lender_withdrawal_finalized",
            direction=LedgerDirection.OUT,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=command.booking_date,
            value_date=command.value_date,
            effective_at=finalized_at,
            received_at=_received_at_from_value_date(command.value_date),
            source_type="bank_operation",
            source_id=str(bank_operation.id),
            lender_user_id=str(withdrawal_request.investor_user_id),
            bank_operation=bank_operation,
            bank_reference=command.bank_reference,
            evidence_reference=command.evidence_reference,
            idempotency_key=_derived_idempotency_key("ledger", idempotency_key),
            postings=[
                PostingCommand(
                    account=withdrawal_payable_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Withdrawal payable cleared",
                ),
                PostingCommand(
                    account=collection_cash_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Cash paid out from collection account",
                ),
            ],
            metadata={
                "bank_operation_type": BankOperationType.LENDER_WITHDRAWAL,
                "withdrawal_request_id": str(withdrawal_request.id),
            },
        )
    )
    withdrawal_request.status = InvestorWithdrawalRequestStatus.FINALIZED
    withdrawal_request.bank_operation = bank_operation
    withdrawal_request.finalization_journal_entry = journal_entry
    withdrawal_request.finalized_by_admin_id = command.actor.pk
    withdrawal_request.finalized_at = finalized_at
    withdrawal_request.bank_reference = command.bank_reference.strip()
    withdrawal_request.payment_reference = command.payment_reference.strip()
    withdrawal_request.evidence_reference = command.evidence_reference.strip()
    withdrawal_request.admin_notes = command.admin_notes.strip()
    withdrawal_request.save(
        update_fields=[
            "status",
            "bank_operation",
            "finalization_journal_entry",
            "finalized_by_admin_id",
            "finalized_at",
            "bank_reference",
            "payment_reference",
            "evidence_reference",
            "admin_notes",
            "updated_at",
        ]
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.investor_withdrawal_finalized",
            target_type="InvestorWithdrawalRequest",
            target_id=str(withdrawal_request.id),
            metadata={
                "investor_user_id": str(withdrawal_request.investor_user_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "bank_operation_id": str(bank_operation.id),
                "journal_entry_id": str(journal_entry.id),
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="InvestorWithdrawalFinalized",
            aggregate_type="InvestorWithdrawalRequest",
            aggregate_id=str(withdrawal_request.id),
            payload={
                "investor_user_id": str(withdrawal_request.investor_user_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "bank_operation_id": str(bank_operation.id),
                "journal_entry_id": str(journal_entry.id),
            },
            idempotency_key=f"withdrawal-request:{withdrawal_request.id}:finalized",
        )
    )
    return InvestorWithdrawalFinalizeResult(withdrawal_request, bank_operation, journal_entry)


@transaction.atomic
def finalize_borrower_disbursement(
    command: FinalizeBorrowerDisbursementCommand,
) -> BorrowerDisbursementFinalizeResult:
    _require_admin_actor(command.actor)
    currency = _enabled_currency(command.currency)
    amount_minor = _validate_money(command.amount_minor, currency.code, "Disbursement amount")
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    collection_account_identifier = _clean_required(
        command.collection_account_identifier,
        "Collection account identifier",
    )
    payee_name = _clean_required(command.payee_name, "Payee name")
    payee_account_identifier = _clean_required(
        command.payee_account_identifier,
        "Payee account identifier",
    )
    request_fingerprint = _borrower_disbursement_finalization_fingerprint(
        command,
        currency_code=currency.code,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_borrower_disbursement_finalization_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing

    _locked_funded_loan_for_disbursement(
        loan_id=str(command.loan_id),
        borrower_id=str(command.borrower_id),
        currency_code=currency.code,
    )
    borrower_disbursement_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.BORROWER_DISBURSEMENT_PAYABLE,
        currency=currency,
        owner_type="loan",
        owner_id=str(command.loan_id),
        name=f"{currency.code} borrower disbursement payable loan {command.loan_id}",
    )
    payable_balance = _credit_balance_for_account(borrower_disbursement_account)
    if payable_balance <= 0:
        raise LedgerValidationError("Loan has no borrower disbursement payable balance.")
    if amount_minor != payable_balance:
        raise LedgerValidationError(
            "Borrower disbursement amount must equal the outstanding payable balance."
        )
    collection_cash_balance = _account_group_balance_minor(
        currency=currency,
        account_type=LedgerAccountType.COLLECTION_CASH,
    )
    if collection_cash_balance < amount_minor:
        raise LedgerValidationError(
            "Collection cash balance is insufficient for borrower disbursement."
        )

    finalized_at = now_utc()
    bank_operation_metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "loan_id": str(command.loan_id),
        "borrower_id": str(command.borrower_id),
        "payable_balance_before_disbursement_minor": payable_balance,
    }
    try:
        with transaction.atomic():
            bank_operation = BankOperation.objects.create(
                operation_type=_bank_operation_type(
                    BankOperationType.BORROWER_LOAN_DISBURSEMENT
                ),
                status=BankOperationStatus.RECONCILED,
                amount_minor=amount_minor,
                currency=currency,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=collection_account_identifier,
                payer_name="Garanta Finanzgruppe AG",
                payer_account_identifier=collection_account_identifier,
                payee_name=payee_name,
                payee_account_identifier=payee_account_identifier,
                bank_reference=command.bank_reference.strip(),
                payment_reference=command.payment_reference.strip(),
                linked_object_type="loan",
                linked_object_id=str(command.loan_id),
                evidence_reference=command.evidence_reference.strip(),
                confirmed_by_admin_id=command.actor.pk,
                confirmed_at=finalized_at,
                notes=command.admin_notes.strip(),
                metadata=bank_operation_metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_borrower_disbursement_finalization_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    collection_cash_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
        name=f"{currency.code} collection cash",
    )
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="borrower_loan_disbursement_finalized",
            direction=LedgerDirection.OUT,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=command.booking_date,
            value_date=command.value_date,
            effective_at=finalized_at,
            received_at=_received_at_from_value_date(command.value_date),
            source_type="bank_operation",
            source_id=str(bank_operation.id),
            borrower_id=str(command.borrower_id),
            loan_id=str(command.loan_id),
            bank_operation=bank_operation,
            bank_reference=command.bank_reference,
            evidence_reference=command.evidence_reference,
            idempotency_key=_derived_idempotency_key("ledger", idempotency_key),
            postings=[
                PostingCommand(
                    account=borrower_disbursement_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Borrower disbursement payable cleared",
                ),
                PostingCommand(
                    account=collection_cash_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Cash paid to borrower from collection account",
                ),
            ],
            tax_metadata={
                "client_money_flow_minor": amount_minor,
            },
            metadata={
                "bank_operation_type": BankOperationType.BORROWER_LOAN_DISBURSEMENT,
                "loan_id": str(command.loan_id),
                "borrower_id": str(command.borrower_id),
                "payable_balance_before_disbursement_minor": payable_balance,
            },
        )
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.borrower_disbursement_finalized",
            target_type="BankOperation",
            target_id=str(bank_operation.id),
            metadata={
                "loan_id": str(command.loan_id),
                "borrower_id": str(command.borrower_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "journal_entry_id": str(journal_entry.id),
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BorrowerDisbursementFinalized",
            aggregate_type="BankOperation",
            aggregate_id=str(bank_operation.id),
            payload={
                "loan_id": str(command.loan_id),
                "borrower_id": str(command.borrower_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "journal_entry_id": str(journal_entry.id),
            },
            idempotency_key=f"bank-operation:{bank_operation.id}:borrower-disbursement-finalized",
        )
    )
    return BorrowerDisbursementFinalizeResult(bank_operation, journal_entry)


def _validated_balance_credit_lines(
    lines: list[InvestorBalanceCreditLineCommand],
    *,
    currency_code: str,
) -> list[InvestorBalanceCreditLineCommand]:
    if not lines:
        raise LedgerValidationError("At least one investor balance credit line is required.")
    validated: list[InvestorBalanceCreditLineCommand] = []
    for line in lines:
        _lender_account_for_id(line.investor_user_id)
        amount_minor = _validate_money(
            line.amount_minor,
            currency_code,
            "Distribution line amount",
        )
        principal_minor = _validate_nonnegative_money(
            line.principal_minor,
            currency_code,
            "Distribution line principal",
        )
        interest_minor = _validate_nonnegative_money(
            line.interest_minor,
            currency_code,
            "Distribution line interest",
        )
        fee_minor = _validate_nonnegative_money(
            line.fee_minor,
            currency_code,
            "Distribution line fee",
        )
        if principal_minor + interest_minor - fee_minor != amount_minor:
            raise LedgerValidationError(
                "Distribution line amount must equal principal plus interest minus fee."
            )
        validated.append(
            InvestorBalanceCreditLineCommand(
                investor_user_id=str(line.investor_user_id),
                amount_minor=amount_minor,
                principal_minor=principal_minor,
                interest_minor=interest_minor,
                fee_minor=fee_minor,
                holding_id=str(line.holding_id),
                installment_id=str(line.installment_id),
                metadata=line.metadata or {},
            )
        )
    return validated


@transaction.atomic
def declare_borrower_repayment_distribution(
    command: DeclareBorrowerRepaymentDistributionCommand,
) -> BorrowerRepaymentDistributionResult:
    _require_admin_actor(command.actor)
    currency = _enabled_currency(command.currency)
    amount_minor = _validate_money(command.amount_minor, currency.code, "Repayment amount")
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    source_type = _clean_required(command.source_type, "Source type")
    source_id = _clean_required(command.source_id, "Source id")
    collection_account_identifier = _clean_required(
        command.collection_account_identifier,
        "Collection account identifier",
    )
    payer_name = _clean_required(command.payer_name, "Payer name")
    distribution_lines = _validated_balance_credit_lines(
        command.distribution_lines,
        currency_code=currency.code,
    )
    if sum(line.amount_minor for line in distribution_lines) != amount_minor:
        raise LedgerValidationError(
            "Distribution line amounts must sum to the borrower repayment amount."
        )
    request_fingerprint = _borrower_repayment_distribution_fingerprint(
        DeclareBorrowerRepaymentDistributionCommand(
            actor=command.actor,
            loan_id=str(command.loan_id),
            borrower_id=str(command.borrower_id),
            amount_minor=amount_minor,
            currency=currency.code,
            booking_date=command.booking_date,
            value_date=command.value_date,
            collection_account_identifier=collection_account_identifier,
            payer_name=payer_name,
            source_type=source_type,
            source_id=source_id,
            distribution_lines=distribution_lines,
            payer_account_identifier=command.payer_account_identifier,
            bank_reference=command.bank_reference,
            payment_reference=command.payment_reference,
            evidence_reference=command.evidence_reference,
            admin_notes=command.admin_notes,
            idempotency_key=idempotency_key,
        ),
        currency_code=currency.code,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_borrower_repayment_distribution_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing

    confirmed_at = now_utc()
    bank_operation_metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "loan_id": str(command.loan_id),
        "borrower_id": str(command.borrower_id),
        "distribution_line_count": len(distribution_lines),
    }
    try:
        with transaction.atomic():
            bank_operation = BankOperation.objects.create(
                operation_type=_bank_operation_type(BankOperationType.BORROWER_REPAYMENT),
                status=BankOperationStatus.RECONCILED,
                amount_minor=amount_minor,
                currency=currency,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=collection_account_identifier,
                payer_name=payer_name,
                payer_account_identifier=command.payer_account_identifier.strip(),
                payee_name="Garanta Finanzgruppe AG",
                payee_account_identifier=collection_account_identifier,
                bank_reference=command.bank_reference.strip(),
                payment_reference=command.payment_reference.strip(),
                linked_object_type="loan",
                linked_object_id=str(command.loan_id),
                evidence_reference=command.evidence_reference.strip(),
                confirmed_by_admin_id=command.actor.pk,
                confirmed_at=confirmed_at,
                notes=command.admin_notes.strip(),
                metadata=bank_operation_metadata,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing_after_race = _existing_borrower_repayment_distribution_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    collection_cash_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
        name=f"{currency.code} collection cash",
    )
    postings = [
        PostingCommand(
            account=collection_cash_account,
            side=LedgerPostingSide.DEBIT,
            amount_minor=amount_minor,
            memo="Borrower repayment received into collection account",
        )
    ]
    for line in distribution_lines:
        investor_liability_account = get_or_create_ledger_account(
            account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
            currency=currency,
            owner_type="investor",
            owner_id=str(line.investor_user_id),
            name=f"{currency.code} investor balance liability {line.investor_user_id}",
        )
        postings.append(
            PostingCommand(
                account=investor_liability_account,
                side=LedgerPostingSide.CREDIT,
                amount_minor=line.amount_minor,
                memo="Borrower repayment distribution credited to investor balance",
            )
        )
    received_at = _received_at_from_value_date(command.value_date)
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="borrower_repayment_distributed",
            direction=LedgerDirection.IN,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=command.booking_date,
            value_date=command.value_date,
            effective_at=confirmed_at,
            received_at=received_at,
            source_type=source_type,
            source_id=source_id,
            borrower_id=str(command.borrower_id),
            loan_id=str(command.loan_id),
            bank_operation=bank_operation,
            bank_reference=command.bank_reference,
            evidence_reference=command.evidence_reference,
            idempotency_key=_derived_idempotency_key("ledger", idempotency_key),
            postings=postings,
            tax_metadata={
                "client_money_flow_minor": amount_minor,
                "principal_minor": sum(line.principal_minor for line in distribution_lines),
                "interest_minor": sum(line.interest_minor for line in distribution_lines),
            },
            metadata={
                "bank_operation_type": BankOperationType.BORROWER_REPAYMENT,
                "loan_id": str(command.loan_id),
                "borrower_id": str(command.borrower_id),
                "distribution_line_count": len(distribution_lines),
            },
        )
    )
    investment_deadline_at, withdrawal_deadline_at = _lot_deadlines(received_at)
    balance_credits: list[InvestorBalanceCreditResult] = []
    for index, line in enumerate(distribution_lines):
        _validate_lot_conservation_values(
            original_amount_minor=line.amount_minor,
            available_amount_minor=line.amount_minor,
            currency_code=currency.code,
        )
        balance_lot = InvestorBalanceLot.objects.create(
            investor_user_id=line.investor_user_id,
            currency=currency,
            source_journal_entry=journal_entry,
            source_type=BalanceLotSourceType.INSTALLMENT,
            source_id=f"{source_id}:{index}",
            received_at=received_at,
            investment_deadline_at=investment_deadline_at,
            withdrawal_deadline_at=withdrawal_deadline_at,
            original_amount_minor=line.amount_minor,
            available_amount_minor=line.amount_minor,
            lineage=[
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "line_index": index,
                    "loan_id": str(command.loan_id),
                    "holding_id": line.holding_id,
                    "installment_id": line.installment_id,
                    "principal_minor": line.principal_minor,
                    "interest_minor": line.interest_minor,
                    "fee_minor": line.fee_minor,
                    "metadata": line.metadata or {},
                }
            ],
        )
        balance_credits.append(
            InvestorBalanceCreditResult(
                line_index=index,
                investor_user_id=str(line.investor_user_id),
                amount_minor=line.amount_minor,
                balance_lot=balance_lot,
            )
        )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.borrower_repayment_distributed",
            target_type="BankOperation",
            target_id=str(bank_operation.id),
            metadata={
                "loan_id": str(command.loan_id),
                "borrower_id": str(command.borrower_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "journal_entry_id": str(journal_entry.id),
                "balance_lot_ids": [str(credit.balance_lot.id) for credit in balance_credits],
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BorrowerRepaymentDistributed",
            aggregate_type="BankOperation",
            aggregate_id=str(bank_operation.id),
            payload={
                "loan_id": str(command.loan_id),
                "borrower_id": str(command.borrower_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "journal_entry_id": str(journal_entry.id),
                "balance_lot_ids": [str(credit.balance_lot.id) for credit in balance_credits],
            },
            idempotency_key=f"bank-operation:{bank_operation.id}:borrower-repayment-distributed",
        )
    )
    return BorrowerRepaymentDistributionResult(
        bank_operation=bank_operation,
        journal_entry=journal_entry,
        balance_credits=balance_credits,
    )


@transaction.atomic
def cancel_investor_withdrawal(
    command: CancelInvestorWithdrawalCommand,
) -> InvestorWithdrawalCancelResult:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    withdrawal_request = (
        InvestorWithdrawalRequest.objects.select_for_update()
        .filter(id=command.withdrawal_request_id)
        .first()
    )
    if withdrawal_request is None:
        raise LedgerValidationError("Withdrawal request does not exist.")
    amount_minor = _validate_money(
        withdrawal_request.amount_minor,
        withdrawal_request.currency_id,
        "Withdrawal amount",
    )
    cancellation_fingerprint = _withdrawal_cancellation_fingerprint(
        command,
        withdrawal_request=withdrawal_request,
        currency_code=withdrawal_request.currency_id,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing_cancellation_key = cast(dict[str, Any], withdrawal_request.metadata).get(
        CANCELLATION_IDEMPOTENCY_METADATA_KEY
    )
    if withdrawal_request.status == InvestorWithdrawalRequestStatus.CANCELLED:
        if (
            withdrawal_request.cancellation_journal_entry is not None
            and existing_cancellation_key == idempotency_key
        ):
            stored_fingerprint = cast(dict[str, Any], withdrawal_request.metadata).get(
                CANCELLATION_FINGERPRINT_METADATA_KEY
            )
            if stored_fingerprint and stored_fingerprint != cancellation_fingerprint:
                raise LedgerValidationError(
                    "Idempotency key was already used for a different request."
                )
            return InvestorWithdrawalCancelResult(
                withdrawal_request,
                withdrawal_request.cancellation_journal_entry,
            )
        raise LedgerValidationError("Withdrawal request is not pending cancellation.")
    if withdrawal_request.status != InvestorWithdrawalRequestStatus.REQUESTED:
        raise LedgerValidationError("Only requested withdrawals can be cancelled.")
    if withdrawal_request.request_journal_entry is None:
        raise LedgerValidationError("Withdrawal request has no reservation journal entry.")

    currency = withdrawal_request.currency
    cancelled_at = now_utc()
    value_date = to_business_time(cancelled_at).date()
    _restore_lots_from_withdrawal_allocations(
        withdrawal_request=withdrawal_request,
        currency=currency,
    )
    investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=str(withdrawal_request.investor_user_id),
        name=f"{currency.code} investor balance liability {withdrawal_request.investor_user_id}",
    )
    withdrawal_payable_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.WITHDRAWAL_PAYABLE,
        currency=currency,
        owner_type="investor",
        owner_id=str(withdrawal_request.investor_user_id),
        name=f"{currency.code} withdrawal payable {withdrawal_request.investor_user_id}",
    )
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="investor_withdrawal_cancelled",
            direction=LedgerDirection.IN,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=cancelled_at,
            received_at=cancelled_at,
            source_type="withdrawal_request",
            source_id=str(withdrawal_request.id),
            lender_user_id=str(withdrawal_request.investor_user_id),
            idempotency_key=_derived_idempotency_key("ledger-withdrawal-cancel", idempotency_key),
            reversal_of=withdrawal_request.request_journal_entry,
            postings=[
                PostingCommand(
                    account=withdrawal_payable_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Withdrawal payable released",
                ),
                PostingCommand(
                    account=investor_liability_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Investor balance restored after withdrawal cancellation",
                ),
            ],
            metadata={
                "withdrawal_request_id": str(withdrawal_request.id),
                "cancellation_reason": command.reason.strip(),
            },
        )
    )
    metadata = dict(withdrawal_request.metadata)
    metadata[CANCELLATION_FINGERPRINT_METADATA_KEY] = cancellation_fingerprint
    metadata[CANCELLATION_IDEMPOTENCY_METADATA_KEY] = idempotency_key
    withdrawal_request.status = InvestorWithdrawalRequestStatus.CANCELLED
    withdrawal_request.cancellation_journal_entry = journal_entry
    withdrawal_request.cancelled_by_admin_id = command.actor.pk
    withdrawal_request.cancelled_at = cancelled_at
    withdrawal_request.cancellation_reason = command.reason.strip()
    withdrawal_request.metadata = metadata
    withdrawal_request.save(
        update_fields=[
            "status",
            "cancellation_journal_entry",
            "cancelled_by_admin_id",
            "cancelled_at",
            "cancellation_reason",
            "metadata",
            "updated_at",
        ]
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.investor_withdrawal_cancelled",
            target_type="InvestorWithdrawalRequest",
            target_id=str(withdrawal_request.id),
            metadata={
                "investor_user_id": str(withdrawal_request.investor_user_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "journal_entry_id": str(journal_entry.id),
                "reason": command.reason.strip(),
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="InvestorWithdrawalCancelled",
            aggregate_type="InvestorWithdrawalRequest",
            aggregate_id=str(withdrawal_request.id),
            payload={
                "investor_user_id": str(withdrawal_request.investor_user_id),
                "currency": currency.code,
                "amount_minor": amount_minor,
                "journal_entry_id": str(journal_entry.id),
                "reason": command.reason.strip(),
            },
            idempotency_key=f"withdrawal-request:{withdrawal_request.id}:cancelled",
        )
    )
    return InvestorWithdrawalCancelResult(withdrawal_request, journal_entry)


def _active_verified_payout_instruction(
    *,
    investor_user_id: str,
    currency: Currency,
) -> InvestorPayoutInstruction | None:
    return (
        InvestorPayoutInstruction.objects.filter(
            investor_user_id=investor_user_id,
            currency=currency,
            status=InvestorPayoutInstructionStatus.ACTIVE,
            is_verified_usable=True,
        )
        .order_by("-verified_at", "-created_at", "-id")
        .first()
    )


def _record_balance_ageing_reminder_due(
    *,
    actor: Model,
    lot: InvestorBalanceLot,
    day: int,
    as_of: datetime,
) -> bool:
    idempotency_key = _balance_ageing_reminder_idempotency_key(lot=lot, day=day)
    if _balance_ageing_reminder_already_recorded(lot=lot, day=day):
        return False
    payload = {
        "investor_user_id": str(lot.investor_user_id),
        "currency": lot.currency_id,
        "lot_id": str(lot.id),
        "amount_minor": lot.available_amount_minor,
        "day": day,
        "as_of": as_of.isoformat(),
        "withdrawal_deadline_at": lot.withdrawal_deadline_at.isoformat(),
    }
    record_domain_event(
        DomainEventCommand(
            event_type="BalanceAgeingReminderDue",
            aggregate_type="InvestorBalanceLot",
            aggregate_id=str(lot.id),
            payload=payload,
            idempotency_key=idempotency_key,
        )
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="ledger.balance_ageing_reminder_due",
            target_type="InvestorBalanceLot",
            target_id=str(lot.id),
            metadata=payload,
        )
    )
    return True


def _balance_ageing_reminder_idempotency_key(
    *,
    lot: InvestorBalanceLot,
    day: int,
) -> str:
    return f"balance-lot:{lot.id}:ageing-reminder-day:{day}"


def _balance_ageing_reminder_already_recorded(
    *,
    lot: InvestorBalanceLot,
    day: int,
) -> bool:
    return DomainEvent.objects.filter(
        idempotency_key=_balance_ageing_reminder_idempotency_key(lot=lot, day=day)
    ).exists()


def _unrecorded_balance_ageing_reminder_days(
    *,
    lot: InvestorBalanceLot,
    days_held: int,
) -> list[int]:
    return [
        threshold
        for threshold in BALANCE_AGEING_REMINDER_DAYS
        if threshold <= days_held
        and not _balance_ageing_reminder_already_recorded(lot=lot, day=threshold)
    ]


def _forced_withdrawal_request_fingerprint(
    *,
    actor_id: str,
    investor_user_id: str,
    currency_code: str,
    amount_minor: int,
    destination_iban: str,
    payout_instruction_id: str,
    lot_ids: list[str],
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "actor_id": actor_id,
            "investor_user_id": investor_user_id,
            "currency": currency_code,
            "amount_minor": amount_minor,
            "destination_iban": destination_iban,
            "payout_instruction_id": payout_instruction_id,
            "lot_ids": lot_ids,
            "idempotency_key": idempotency_key,
        }
    )


def _create_forced_withdrawal_request(
    *,
    actor: Model,
    investor_user_id: str,
    currency: Currency,
    amount_minor: int,
    payout_instruction: InvestorPayoutInstruction,
    lot_ids: list[str],
    as_of: datetime,
) -> InvestorWithdrawalRequest:
    amount_minor = _validate_money(amount_minor, currency.code, "Forced withdrawal amount")
    idempotency_key = _derived_idempotency_key(
        "forced-withdrawal",
        f"{investor_user_id}:{currency.code}:{business_date(as_of).isoformat()}:{':'.join(lot_ids)}",
    )
    destination_iban = _clean_iban(payout_instruction.destination_iban)
    request_fingerprint = _forced_withdrawal_request_fingerprint(
        actor_id=str(actor.pk),
        investor_user_id=investor_user_id,
        currency_code=currency.code,
        amount_minor=amount_minor,
        destination_iban=destination_iban,
        payout_instruction_id=str(payout_instruction.id),
        lot_ids=lot_ids,
        idempotency_key=idempotency_key,
    )
    existing = _existing_withdrawal_request_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "payout_instruction_id": str(payout_instruction.id),
        "forced_withdrawal_lot_ids": lot_ids,
        "generated_by": "balance_ageing_scan",
    }
    try:
        withdrawal_request = InvestorWithdrawalRequest.objects.create(
            investor_user_id=investor_user_id,
            amount_minor=amount_minor,
            currency=currency,
            destination_iban=destination_iban,
            destination_account_name=payout_instruction.destination_account_name,
            requested_by_user_id=actor.pk,
            requested_at=as_of,
            is_forced=True,
            notes=(
                "Forced withdrawal generated by balance ageing scan because the "
                "source balance reached the 60-day holding limit."
            ),
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except IntegrityError:
        existing_after_race = _existing_withdrawal_request_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    lots = _withdrawal_lots_for_update(investor_user_id=investor_user_id, currency=currency)
    allocations = _consume_lots_for_withdrawal(
        lots=lots,
        amount_minor=amount_minor,
        currency_code=currency.code,
    )
    investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=investor_user_id,
        name=f"{currency.code} investor balance liability {investor_user_id}",
    )
    withdrawal_payable_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.WITHDRAWAL_PAYABLE,
        currency=currency,
        owner_type="investor",
        owner_id=investor_user_id,
        name=f"{currency.code} withdrawal payable {investor_user_id}",
    )
    value_date = business_date(as_of)
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=actor,
            event_type="forced_withdrawal_requested",
            direction=LedgerDirection.OUT,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=as_of,
            received_at=as_of,
            source_type="withdrawal_request",
            source_id=str(withdrawal_request.id),
            lender_user_id=investor_user_id,
            idempotency_key=_derived_idempotency_key(
                "ledger-forced-withdrawal-request",
                idempotency_key,
            ),
            postings=[
                PostingCommand(
                    account=investor_liability_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Investor balance liability reserved for forced withdrawal",
                ),
                PostingCommand(
                    account=withdrawal_payable_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Forced withdrawal payable created",
                ),
            ],
            metadata={
                "withdrawal_request_id": str(withdrawal_request.id),
                "payout_instruction_id": str(payout_instruction.id),
            },
        )
    )
    withdrawal_request.request_journal_entry = journal_entry
    withdrawal_request.lot_allocations = allocations
    withdrawal_request.save(
        update_fields=["request_journal_entry", "lot_allocations", "updated_at"]
    )
    event_metadata = {
        "investor_user_id": investor_user_id,
        "currency": currency.code,
        "amount_minor": amount_minor,
        "withdrawal_request_id": str(withdrawal_request.id),
        "journal_entry_id": str(journal_entry.id),
        "payout_instruction_id": str(payout_instruction.id),
        "lot_allocations": allocations,
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="ledger.forced_withdrawal_requested",
            target_type="InvestorWithdrawalRequest",
            target_id=str(withdrawal_request.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="ForcedWithdrawalRequested",
            aggregate_type="InvestorWithdrawalRequest",
            aggregate_id=str(withdrawal_request.id),
            payload=event_metadata,
            idempotency_key=f"withdrawal-request:{withdrawal_request.id}:forced-requested",
        )
    )
    return withdrawal_request


@transaction.atomic
def run_balance_ageing_scan(command: RunBalanceAgeingScanCommand) -> BalanceAgeingScanResult:
    _require_admin_actor(command.actor)
    as_of = command.as_of or now_utc()
    to_business_time(as_of)
    currency = _enabled_currency(command.currency) if command.currency else None
    queryset = InvestorBalanceLot.objects.select_for_update().filter(
        available_amount_minor__gt=0,
        status__in=[BalanceLotStatus.AVAILABLE, BalanceLotStatus.PENALTY_MODE],
    )
    if currency is not None:
        queryset = queryset.filter(currency=currency)
    lots = list(
        queryset.select_related("currency").order_by(
            "investor_user_id", "currency", "received_at", "id"
        )
    )

    reminders_due: list[BalanceAgeingReminderDue] = []
    penalty_mode_transitions: list[BalanceAgeingPenaltyModeTransition] = []
    forced_withdrawal_candidates: list[BalanceAgeingForcedWithdrawalCandidate] = []
    forced_withdrawal_requests: list[InvestorWithdrawalRequest] = []
    skipped_lot_ids: list[str] = []
    overdue_by_investor_currency: dict[tuple[str, str], list[InvestorBalanceLot]] = {}

    for lot in lots:
        _validate_lot_conservation(lot)
        days_held = calendar_day_difference(lot.received_at, as_of)
        if lot.status == BalanceLotStatus.AVAILABLE:
            for reminder_day in _unrecorded_balance_ageing_reminder_days(
                lot=lot,
                days_held=days_held,
            ):
                reminder = BalanceAgeingReminderDue(
                    lot_id=str(lot.id),
                    investor_user_id=str(lot.investor_user_id),
                    currency=lot.currency_id,
                    amount_minor=lot.available_amount_minor,
                    day=reminder_day,
                    withdrawal_deadline_at=lot.withdrawal_deadline_at,
                )
                reminders_due.append(reminder)
                if not command.dry_run:
                    _record_balance_ageing_reminder_due(
                        actor=command.actor,
                        lot=lot,
                        day=reminder_day,
                        as_of=as_of,
                    )
        if business_date(as_of) >= business_date(lot.withdrawal_deadline_at):
            key = (str(lot.investor_user_id), lot.currency_id)
            overdue_by_investor_currency.setdefault(key, []).append(lot)

    for (investor_user_id, currency_code), overdue_lots in overdue_by_investor_currency.items():
        if not overdue_lots:
            continue
        overdue_currency = overdue_lots[0].currency
        payout_instruction = _active_verified_payout_instruction(
            investor_user_id=investor_user_id,
            currency=overdue_currency,
        )
        amount_minor = sum(lot.available_amount_minor for lot in overdue_lots)
        lot_ids = [str(lot.id) for lot in overdue_lots]
        if payout_instruction is not None:
            candidate = BalanceAgeingForcedWithdrawalCandidate(
                investor_user_id=investor_user_id,
                currency=currency_code,
                amount_minor=amount_minor,
                lot_ids=lot_ids,
                payout_instruction_id=str(payout_instruction.id),
            )
            forced_withdrawal_candidates.append(candidate)
            if not command.dry_run:
                forced_withdrawal_requests.append(
                    _create_forced_withdrawal_request(
                        actor=command.actor,
                        investor_user_id=investor_user_id,
                        currency=overdue_currency,
                        amount_minor=amount_minor,
                        payout_instruction=payout_instruction,
                        lot_ids=lot_ids,
                        as_of=as_of,
                    )
                )
            continue

        for lot in overdue_lots:
            if lot.status == BalanceLotStatus.PENALTY_MODE:
                skipped_lot_ids.append(str(lot.id))
                continue
            transition = BalanceAgeingPenaltyModeTransition(
                lot_id=str(lot.id),
                investor_user_id=str(lot.investor_user_id),
                currency=lot.currency_id,
                amount_minor=lot.available_amount_minor,
                days_overdue=max(0, calendar_day_difference(lot.withdrawal_deadline_at, as_of)),
            )
            penalty_mode_transitions.append(transition)
            if command.dry_run:
                continue
            lot.status = BalanceLotStatus.PENALTY_MODE
            lineage = list(cast(list[dict[str, Any]], lot.lineage))
            lineage.append(
                {
                    "event": "penalty_mode_enabled",
                    "as_of": as_of.isoformat(),
                    "penalty_bps_per_day": int(settings.BALANCE_PENALTY_BPS_PER_DAY),
                    "reason": "No verified usable payout instruction at 60-day holding limit.",
                }
            )
            lot.lineage = lineage
            lot.save(update_fields=["status", "lineage", "updated_at"])
            event_metadata = {
                "investor_user_id": str(lot.investor_user_id),
                "currency": lot.currency_id,
                "amount_minor": lot.available_amount_minor,
                "days_overdue": transition.days_overdue,
                "penalty_bps_per_day": int(settings.BALANCE_PENALTY_BPS_PER_DAY),
            }
            record_audit_event(
                AuditCommand(
                    actor=actor_ref_for_user(command.actor),
                    action="ledger.balance_penalty_mode_enabled",
                    target_type="InvestorBalanceLot",
                    target_id=str(lot.id),
                    metadata=event_metadata,
                )
            )
            record_domain_event(
                DomainEventCommand(
                    event_type="BalancePenaltyModeEnabled",
                    aggregate_type="InvestorBalanceLot",
                    aggregate_id=str(lot.id),
                    payload=event_metadata,
                    idempotency_key=f"balance-lot:{lot.id}:penalty-mode-enabled",
                )
            )

    return BalanceAgeingScanResult(
        as_of=as_of,
        reminders_due=reminders_due,
        forced_withdrawal_candidates=forced_withdrawal_candidates,
        forced_withdrawal_requests=forced_withdrawal_requests,
        penalty_mode_transitions=penalty_mode_transitions,
        skipped_lot_ids=skipped_lot_ids,
    )


def summarize_investor_balance(
    *,
    investor_user_id: str,
    currency: str,
    as_of: datetime | None = None,
) -> BalanceSummary:
    currency_model = _enabled_currency(currency)
    now_value = as_of or now_utc()
    lots = InvestorBalanceLot.objects.filter(
        investor_user_id=investor_user_id,
        currency=currency_model,
    )
    total_available = 0
    investable = 0
    withdraw_only = 0
    overdue = 0
    frozen = 0
    penalty_mode = 0
    for lot in lots:
        _validate_lot_conservation(lot)
        amount = lot.available_amount_minor
        if amount <= 0:
            continue
        if lot.status == BalanceLotStatus.FROZEN:
            total_available += amount
            frozen += amount
        elif lot.status == BalanceLotStatus.PENALTY_MODE:
            total_available += amount
            penalty_mode += amount
        elif lot.status == BalanceLotStatus.AVAILABLE:
            total_available += amount
            if now_value > lot.withdrawal_deadline_at:
                overdue += amount
            elif now_value > lot.investment_deadline_at:
                withdraw_only += amount
            else:
                investable += amount
    return BalanceSummary(
        investor_user_id=investor_user_id,
        currency=currency_model.code,
        total_available_minor=total_available,
        investable_minor=investable,
        withdraw_only_minor=withdraw_only,
        overdue_minor=overdue,
        frozen_minor=frozen,
        penalty_mode_minor=penalty_mode,
    )


def plan_investment_balance_consumption(
    *,
    investor_user_id: str,
    currency: str,
    amount_minor: int,
    loan_funding_deadline: date,
    as_of: datetime | None = None,
) -> list[BalanceConsumptionPlanLine]:
    currency_model = _enabled_currency(currency)
    _validate_money(amount_minor, currency_model.code, "Consumption amount")
    now_value = as_of or now_utc()
    remaining = amount_minor
    plan: list[BalanceConsumptionPlanLine] = []
    lots = InvestorBalanceLot.objects.filter(
        investor_user_id=investor_user_id,
        currency=currency_model,
        status=BalanceLotStatus.AVAILABLE,
        available_amount_minor__gt=0,
    ).order_by("received_at", "created_at", "id")
    for lot in lots:
        _validate_lot_conservation(lot)
        if now_value > lot.investment_deadline_at:
            continue
        investment_deadline_date = to_business_time(lot.investment_deadline_at).date()
        if loan_funding_deadline > investment_deadline_date:
            continue
        amount = min(remaining, lot.available_amount_minor)
        plan.append(
            BalanceConsumptionPlanLine(
                lot_id=str(lot.id),
                amount_minor=amount,
                investment_deadline_at=lot.investment_deadline_at,
                withdrawal_deadline_at=lot.withdrawal_deadline_at,
            )
        )
        remaining -= amount
        if remaining == 0:
            return plan
    raise LedgerValidationError("Insufficient eligible balance for the requested investment.")


def _investment_actor_for_id(actor: Model, investor_user_id: str) -> Model:
    investor = _lender_account_for_id(investor_user_id)
    if is_admin_actor(actor):
        return investor
    if str(actor.pk) != str(investor.pk):
        raise LedgerAuthorizationError("Investor can only reserve their own balance.")
    if not user_can_access_financial_features(actor):
        raise LedgerAuthorizationError("Investor account cannot access financial features.")
    return actor


def _reservation_request_fingerprint(
    command: ReserveInvestmentBalanceCommand,
    *,
    investor_user_id: str,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    actor_ref = actor_ref_for_user(command.actor)
    return _stable_json_fingerprint(
        {
            "actor_type": actor_ref.actor_type,
            "actor_id": actor_ref.actor_id,
            "investor_user_id": investor_user_id,
            "loan_id": str(command.loan_id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "loan_funding_deadline": command.loan_funding_deadline.isoformat(),
            "source_type": command.source_type.strip(),
            "source_id": command.source_id.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _release_request_fingerprint(
    command: ReleaseInvestmentBalanceReservationCommand,
    *,
    investor_user_id: str,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    actor_ref = actor_ref_for_user(command.actor)
    return _stable_json_fingerprint(
        {
            "actor_type": actor_ref.actor_type,
            "actor_id": actor_ref.actor_id,
            "investor_user_id": investor_user_id,
            "loan_id": str(command.loan_id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "source_type": command.source_type.strip(),
            "source_id": command.source_id.strip(),
            "reservation_journal_entry_id": str(command.reservation_journal_entry_id),
            "lot_allocations": command.lot_allocations,
            "reason": command.reason.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _primary_loan_close_request_fingerprint(
    command: ClosePrimaryLoanFundingCommand,
    *,
    currency_code: str,
    accepted_principal_minor: int,
    borrower_success_fee_minor: int,
    borrower_disbursement_payable_minor: int,
    idempotency_key: str,
) -> str:
    actor_ref = actor_ref_for_user(command.actor)
    return _stable_json_fingerprint(
        {
            "actor_type": actor_ref.actor_type,
            "actor_id": actor_ref.actor_id,
            "loan_id": str(command.loan_id),
            "borrower_id": str(command.borrower_id),
            "accepted_principal_minor": accepted_principal_minor,
            "borrower_success_fee_bps": command.borrower_success_fee_bps,
            "borrower_success_fee_minor": borrower_success_fee_minor,
            "borrower_disbursement_payable_minor": borrower_disbursement_payable_minor,
            "currency": currency_code,
            "source_type": command.source_type.strip(),
            "source_id": command.source_id.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _fx_exchange_request_fingerprint(
    command: ExecuteInvestorFxExchangeLedgerCommand,
    *,
    investor_user_id: str,
    source_currency_code: str,
    target_currency_code: str,
    source_amount_minor: int,
    gross_target_amount_minor: int,
    target_amount_minor: int,
    fee_minor: int,
    idempotency_key: str,
) -> str:
    actor_ref = actor_ref_for_user(command.actor)
    return _stable_json_fingerprint(
        {
            "actor_type": actor_ref.actor_type,
            "actor_id": actor_ref.actor_id,
            "investor_user_id": investor_user_id,
            "source_currency": source_currency_code,
            "target_currency": target_currency_code,
            "source_amount_minor": source_amount_minor,
            "gross_target_amount_minor": gross_target_amount_minor,
            "target_amount_minor": target_amount_minor,
            "fee_minor": fee_minor,
            "source_type": command.source_type.strip(),
            "source_id": command.source_id.strip(),
            "idempotency_key": idempotency_key,
            "metadata": command.metadata or {},
        }
    )


def _existing_investment_reservation(
    journal_idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> InvestmentBalanceReservationResult | None:
    existing = LedgerJournalEntry.objects.filter(idempotency_key=journal_idempotency_key).first()
    if existing is None:
        return None
    metadata = cast(dict[str, Any], existing.metadata)
    if metadata.get(INVESTMENT_RESERVATION_FINGERPRINT_METADATA_KEY) != expected_fingerprint:
        raise LedgerValidationError("Idempotency key was already used for a different request.")
    return InvestmentBalanceReservationResult(
        journal_entry=existing,
        lot_allocations=list(cast(list[dict[str, Any]], metadata.get("lot_allocations", []))),
    )


def _existing_investment_release(
    journal_idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> InvestmentBalanceReleaseResult | None:
    existing = LedgerJournalEntry.objects.filter(idempotency_key=journal_idempotency_key).first()
    if existing is None:
        return None
    metadata = cast(dict[str, Any], existing.metadata)
    if metadata.get(INVESTMENT_RELEASE_FINGERPRINT_METADATA_KEY) != expected_fingerprint:
        raise LedgerValidationError("Idempotency key was already used for a different request.")
    return InvestmentBalanceReleaseResult(journal_entry=existing)


def _existing_primary_loan_close(
    journal_idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> ClosePrimaryLoanFundingResult | None:
    existing = LedgerJournalEntry.objects.filter(idempotency_key=journal_idempotency_key).first()
    if existing is None:
        return None
    metadata = cast(dict[str, Any], existing.metadata)
    if metadata.get(PRIMARY_LOAN_CLOSE_FINGERPRINT_METADATA_KEY) != expected_fingerprint:
        raise LedgerValidationError("Idempotency key was already used for a different request.")
    return ClosePrimaryLoanFundingResult(
        journal_entry=existing,
        borrower_success_fee_minor=int(metadata.get("borrower_success_fee_minor", 0)),
        borrower_disbursement_payable_minor=int(
            metadata.get("borrower_disbursement_payable_minor", 0)
        ),
    )


def _existing_fx_exchange_ledger_result(
    source_journal_idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> InvestorFxExchangeLedgerResult | None:
    source_journal = LedgerJournalEntry.objects.filter(
        idempotency_key=source_journal_idempotency_key
    ).first()
    if source_journal is None:
        return None
    metadata = cast(dict[str, Any], source_journal.metadata)
    if metadata.get(FX_EXCHANGE_FINGERPRINT_METADATA_KEY) != expected_fingerprint:
        raise LedgerValidationError("Idempotency key was already used for a different request.")
    target_journal_id = str(metadata.get("target_journal_entry_id", ""))
    target_lot_id = str(metadata.get("target_balance_lot_id", ""))
    if not target_journal_id or not target_lot_id:
        raise LedgerValidationError("Existing FX source journal is missing target evidence.")
    target_journal = LedgerJournalEntry.objects.filter(id=target_journal_id).first()
    target_lot = InvestorBalanceLot.objects.filter(id=target_lot_id).first()
    if target_journal is None or target_lot is None:
        raise LedgerValidationError("Existing FX ledger evidence is incomplete.")
    return InvestorFxExchangeLedgerResult(
        source_journal_entry=cast(LedgerJournalEntry, source_journal),
        target_journal_entry=cast(LedgerJournalEntry, target_journal),
        target_balance_lot=target_lot,
        source_lot_allocations=list(
            cast(list[dict[str, Any]], metadata.get("source_lot_allocations", []))
        ),
    )


def _credit_balance_for_account(account: LedgerAccount) -> int:
    debit_total = (
        LedgerPosting.objects.filter(
            account=account,
            side=LedgerPostingSide.DEBIT,
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )
    credit_total = (
        LedgerPosting.objects.filter(
            account=account,
            side=LedgerPostingSide.CREDIT,
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )
    return int(credit_total) - int(debit_total)


def _investment_lots_for_update(
    *,
    investor_user_id: str,
    currency: Currency,
) -> list[InvestorBalanceLot]:
    return list(
        InvestorBalanceLot.objects.select_for_update()
        .filter(
            investor_user_id=investor_user_id,
            currency=currency,
            status=BalanceLotStatus.AVAILABLE,
            available_amount_minor__gt=0,
        )
        .order_by("received_at", "created_at", "id")
    )


def _fx_source_lots_for_update(
    *,
    investor_user_id: str,
    currency: Currency,
) -> list[InvestorBalanceLot]:
    return list(
        InvestorBalanceLot.objects.select_for_update()
        .filter(
            investor_user_id=investor_user_id,
            currency=currency,
            status=BalanceLotStatus.AVAILABLE,
            available_amount_minor__gt=0,
        )
        .order_by("received_at", "created_at", "id")
    )


def _consume_lots_for_fx(
    *,
    lots: list[InvestorBalanceLot],
    amount_minor: int,
    currency_code: str,
    as_of: datetime,
) -> list[dict[str, Any]]:
    remaining = amount_minor
    allocations: list[dict[str, Any]] = []
    for lot in lots:
        _validate_lot_conservation(lot)
        if remaining <= 0:
            break
        if as_of > lot.withdrawal_deadline_at:
            continue
        amount = min(remaining, lot.available_amount_minor)
        if amount <= 0:
            continue
        status_before_conversion = str(lot.status)
        available_before_conversion = lot.available_amount_minor
        converted_before_conversion = lot.converted_amount_minor
        new_available = lot.available_amount_minor - amount
        new_converted = lot.converted_amount_minor + amount
        new_status = BalanceLotStatus.CONSUMED if new_available == 0 else lot.status
        _validate_lot_conservation_values(
            original_amount_minor=lot.original_amount_minor,
            available_amount_minor=new_available,
            invested_amount_minor=lot.invested_amount_minor,
            converted_amount_minor=new_converted,
            withdrawn_amount_minor=lot.withdrawn_amount_minor,
            penalized_amount_minor=lot.penalized_amount_minor,
            currency_code=currency_code,
        )
        lot.available_amount_minor = new_available
        lot.converted_amount_minor = new_converted
        lot.status = new_status
        lot.save(update_fields=["available_amount_minor", "converted_amount_minor", "status"])
        allocations.append(
            {
                "lot_id": str(lot.id),
                "amount_minor": amount,
                "status_before_conversion": status_before_conversion,
                "available_before_conversion_minor": available_before_conversion,
                "converted_before_conversion_minor": converted_before_conversion,
                "received_at": lot.received_at.isoformat(),
                "investment_deadline_at": lot.investment_deadline_at.isoformat(),
                "withdrawal_deadline_at": lot.withdrawal_deadline_at.isoformat(),
                "source_type": lot.source_type,
                "source_id": lot.source_id,
            }
        )
        remaining -= amount
    if remaining > 0:
        raise LedgerValidationError("Insufficient eligible balance for the requested FX exchange.")
    return allocations


def _consume_lots_for_investment(
    *,
    lots: list[InvestorBalanceLot],
    amount_minor: int,
    currency_code: str,
    loan_funding_deadline: date,
    as_of: datetime,
) -> list[dict[str, Any]]:
    remaining = amount_minor
    allocations: list[dict[str, Any]] = []
    for lot in lots:
        _validate_lot_conservation(lot)
        if remaining <= 0:
            break
        if as_of > lot.investment_deadline_at:
            continue
        investment_deadline_date = to_business_time(lot.investment_deadline_at).date()
        if loan_funding_deadline > investment_deadline_date:
            continue
        amount = min(remaining, lot.available_amount_minor)
        if amount <= 0:
            continue
        status_before_investment = str(lot.status)
        available_before_investment = lot.available_amount_minor
        invested_before_investment = lot.invested_amount_minor
        new_available = lot.available_amount_minor - amount
        new_invested = lot.invested_amount_minor + amount
        new_status = BalanceLotStatus.CONSUMED if new_available == 0 else lot.status
        _validate_lot_conservation_values(
            original_amount_minor=lot.original_amount_minor,
            available_amount_minor=new_available,
            invested_amount_minor=new_invested,
            converted_amount_minor=lot.converted_amount_minor,
            withdrawn_amount_minor=lot.withdrawn_amount_minor,
            penalized_amount_minor=lot.penalized_amount_minor,
            currency_code=currency_code,
        )
        lot.available_amount_minor = new_available
        lot.invested_amount_minor = new_invested
        lot.status = new_status
        lot.save(update_fields=["available_amount_minor", "invested_amount_minor", "status"])
        allocations.append(
            {
                "lot_id": str(lot.id),
                "amount_minor": amount,
                "status_before_investment": status_before_investment,
                "available_before_investment_minor": available_before_investment,
                "invested_before_investment_minor": invested_before_investment,
                "received_at": lot.received_at.isoformat(),
                "investment_deadline_at": lot.investment_deadline_at.isoformat(),
                "withdrawal_deadline_at": lot.withdrawal_deadline_at.isoformat(),
                "source_type": lot.source_type,
                "source_id": lot.source_id,
            }
        )
        remaining -= amount
    if remaining > 0:
        raise LedgerValidationError("Insufficient eligible balance for the requested investment.")
    return allocations


def _restore_lots_from_investment_allocations(
    *,
    investor_user_id: str,
    currency: Currency,
    allocations: list[dict[str, Any]],
) -> int:
    if not allocations:
        raise LedgerValidationError("Investment reservation has no lot allocations to release.")
    lot_ids: list[str] = []
    for allocation in allocations:
        lot_id = str(allocation.get("lot_id", ""))
        if not lot_id:
            raise LedgerValidationError("Investment allocation is missing a lot id.")
        lot_ids.append(lot_id)
    lots = {
        str(lot.id): lot
        for lot in InvestorBalanceLot.objects.select_for_update().filter(
            id__in=lot_ids,
            investor_user_id=investor_user_id,
            currency=currency,
        )
    }
    total_released = 0
    for allocation in allocations:
        lot_id = str(allocation["lot_id"])
        lot = lots.get(lot_id)
        if lot is None:
            raise LedgerValidationError("Investment allocation references an unavailable lot.")
        amount_value = allocation.get("amount_minor")
        if type(amount_value) is not int:
            raise LedgerValidationError("Investment allocation amount must be integer minor units.")
        amount = _validate_money(amount_value, currency.code, "Investment allocation amount")
        previous_status = str(
            allocation.get("status_before_investment") or BalanceLotStatus.AVAILABLE
        )
        if previous_status != BalanceLotStatus.AVAILABLE:
            raise LedgerValidationError("Investment allocation has an invalid previous lot status.")
        _validate_lot_conservation(lot)
        new_available = lot.available_amount_minor + amount
        new_invested = lot.invested_amount_minor - amount
        if new_invested < 0:
            raise LedgerValidationError("Investment allocation would over-release a balance lot.")
        _validate_lot_conservation_values(
            original_amount_minor=lot.original_amount_minor,
            available_amount_minor=new_available,
            invested_amount_minor=new_invested,
            converted_amount_minor=lot.converted_amount_minor,
            withdrawn_amount_minor=lot.withdrawn_amount_minor,
            penalized_amount_minor=lot.penalized_amount_minor,
            currency_code=currency.code,
        )
        lot.available_amount_minor = new_available
        lot.invested_amount_minor = new_invested
        lot.status = previous_status
        lot.save(update_fields=["available_amount_minor", "invested_amount_minor", "status"])
        total_released += amount
    return total_released


@transaction.atomic
def reserve_investor_balance_for_investment(
    command: ReserveInvestmentBalanceCommand,
) -> InvestmentBalanceReservationResult:
    currency = _enabled_currency(command.currency)
    amount_minor = _validate_money(command.amount_minor, currency.code, "Investment amount")
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    source_type = _clean_required(command.source_type, "Source type")
    source_id = _clean_required(command.source_id, "Source id")
    investor = _investment_actor_for_id(command.actor, command.investor_user_id)
    investor_id = str(investor.pk)
    as_of = command.as_of or now_utc()
    value_date = business_date(as_of)
    journal_idempotency_key = _derived_idempotency_key(
        "ledger-investment-reserve",
        idempotency_key,
    )
    request_fingerprint = _reservation_request_fingerprint(
        command,
        investor_user_id=investor_id,
        currency_code=currency.code,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_investment_reservation(
        journal_idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing

    lots = _investment_lots_for_update(investor_user_id=investor_id, currency=currency)
    existing_after_locks = _existing_investment_reservation(
        journal_idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing_after_locks is not None:
        return existing_after_locks
    allocations = _consume_lots_for_investment(
        lots=lots,
        amount_minor=amount_minor,
        currency_code=currency.code,
        loan_funding_deadline=command.loan_funding_deadline,
        as_of=as_of,
    )
    investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=investor_id,
        name=f"{currency.code} investor balance liability {investor_id}",
    )
    loan_funding_escrow_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.LOAN_FUNDING_ESCROW,
        currency=currency,
        owner_type="loan",
        owner_id=str(command.loan_id),
        name=f"{currency.code} loan funding escrow {command.loan_id}",
    )
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="primary_investment_balance_reserved",
            direction=LedgerDirection.INTERNAL,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=as_of,
            received_at=as_of,
            source_type=source_type,
            source_id=source_id,
            lender_user_id=investor_id,
            loan_id=str(command.loan_id),
            idempotency_key=journal_idempotency_key,
            postings=[
                PostingCommand(
                    account=investor_liability_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Investor balance liability reserved for primary investment",
                ),
                PostingCommand(
                    account=loan_funding_escrow_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Loan funding escrow credited by primary investment",
                ),
            ],
            metadata={
                INVESTMENT_RESERVATION_FINGERPRINT_METADATA_KEY: request_fingerprint,
                "lot_allocations": allocations,
                "loan_funding_deadline": command.loan_funding_deadline.isoformat(),
            },
        )
    )
    return InvestmentBalanceReservationResult(
        journal_entry=journal_entry,
        lot_allocations=allocations,
    )


@transaction.atomic
def release_investor_balance_investment_reservation(
    command: ReleaseInvestmentBalanceReservationCommand,
) -> InvestmentBalanceReleaseResult:
    _require_admin_actor(command.actor)
    currency = _enabled_currency(command.currency)
    amount_minor = _validate_money(command.amount_minor, currency.code, "Investment release amount")
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    source_type = _clean_required(command.source_type, "Source type")
    source_id = _clean_required(command.source_id, "Source id")
    investor = _lender_account_for_id(command.investor_user_id)
    investor_id = str(investor.pk)
    reason = _clean_required(command.reason, "Release reason")
    as_of = command.as_of or now_utc()
    value_date = business_date(as_of)
    journal_idempotency_key = _derived_idempotency_key(
        "ledger-investment-release",
        idempotency_key,
    )
    request_fingerprint = _release_request_fingerprint(
        command,
        investor_user_id=investor_id,
        currency_code=currency.code,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_investment_release(
        journal_idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    reservation_journal = LedgerJournalEntry.objects.filter(
        id=command.reservation_journal_entry_id,
        lender_user_id=investor_id,
        loan_id=command.loan_id,
        currency=currency,
    ).first()
    if reservation_journal is None:
        raise LedgerValidationError("Investment reservation journal entry does not exist.")

    total_released = _restore_lots_from_investment_allocations(
        investor_user_id=investor_id,
        currency=currency,
        allocations=command.lot_allocations,
    )
    if total_released != amount_minor:
        raise LedgerValidationError("Released lot allocations do not match the release amount.")
    investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=investor_id,
        name=f"{currency.code} investor balance liability {investor_id}",
    )
    loan_funding_escrow_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.LOAN_FUNDING_ESCROW,
        currency=currency,
        owner_type="loan",
        owner_id=str(command.loan_id),
        name=f"{currency.code} loan funding escrow {command.loan_id}",
    )
    journal_entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="primary_investment_balance_released",
            direction=LedgerDirection.INTERNAL,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=as_of,
            received_at=as_of,
            source_type=source_type,
            source_id=source_id,
            lender_user_id=investor_id,
            loan_id=str(command.loan_id),
            idempotency_key=journal_idempotency_key,
            reversal_of=reservation_journal,
            postings=[
                PostingCommand(
                    account=loan_funding_escrow_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Loan funding escrow released",
                ),
                PostingCommand(
                    account=investor_liability_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Investor balance restored after primary investment release",
                ),
            ],
            metadata={
                INVESTMENT_RELEASE_FINGERPRINT_METADATA_KEY: request_fingerprint,
                "lot_allocations": command.lot_allocations,
                "release_reason": reason,
            },
        )
    )
    return InvestmentBalanceReleaseResult(journal_entry=journal_entry)


@transaction.atomic
def execute_investor_fx_exchange_ledger(
    command: ExecuteInvestorFxExchangeLedgerCommand,
) -> InvestorFxExchangeLedgerResult:
    source_currency = _enabled_currency(command.source_currency)
    target_currency = _enabled_currency(command.target_currency)
    if source_currency.code == target_currency.code:
        raise LedgerValidationError("FX source and target currencies must differ.")
    source_amount_minor = _validate_money(
        command.source_amount_minor,
        source_currency.code,
        "FX source amount",
    )
    gross_target_amount_minor = _validate_money(
        command.gross_target_amount_minor,
        target_currency.code,
        "FX gross target amount",
    )
    target_amount_minor = _validate_money(
        command.target_amount_minor,
        target_currency.code,
        "FX target amount",
    )
    fee_minor = _validate_nonnegative_money(
        command.fee_minor,
        target_currency.code,
        "FX fee",
    )
    if target_amount_minor + fee_minor != gross_target_amount_minor:
        raise LedgerValidationError("FX gross target amount must equal target amount plus fee.")
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    source_type = _clean_required(command.source_type, "Source type")
    source_id = _clean_required(command.source_id, "Source id")
    investor = _investment_actor_for_id(command.actor, command.investor_user_id)
    investor_id = str(investor.pk)
    as_of = command.as_of or now_utc()
    value_date = business_date(as_of)
    source_journal_key = _derived_idempotency_key("ledger-fx-source", idempotency_key)
    target_journal_key = _derived_idempotency_key("ledger-fx-target", idempotency_key)
    request_fingerprint = _fx_exchange_request_fingerprint(
        command,
        investor_user_id=investor_id,
        source_currency_code=source_currency.code,
        target_currency_code=target_currency.code,
        source_amount_minor=source_amount_minor,
        gross_target_amount_minor=gross_target_amount_minor,
        target_amount_minor=target_amount_minor,
        fee_minor=fee_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_fx_exchange_ledger_result(
        source_journal_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    if InvestorBalanceLot.objects.filter(
        investor_user_id=investor_id,
        status=BalanceLotStatus.PENALTY_MODE,
        available_amount_minor__gt=0,
    ).exists():
        raise LedgerValidationError(
            "Investor has overdue balance in penalty mode and cannot exchange currencies."
        )

    lots = _fx_source_lots_for_update(investor_user_id=investor_id, currency=source_currency)
    existing_after_locks = _existing_fx_exchange_ledger_result(
        source_journal_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing_after_locks is not None:
        return existing_after_locks
    source_allocations = _consume_lots_for_fx(
        lots=lots,
        amount_minor=source_amount_minor,
        currency_code=source_currency.code,
        as_of=as_of,
    )
    inherited_investment_deadline_at = max(
        datetime.fromisoformat(str(allocation["investment_deadline_at"]))
        for allocation in source_allocations
    )
    inherited_withdrawal_deadline_at = max(
        datetime.fromisoformat(str(allocation["withdrawal_deadline_at"]))
        for allocation in source_allocations
    )

    target_fx_clearing_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.FX_CLEARING,
        currency=target_currency,
        owner_type="fx",
        owner_id="platform",
        name=f"{target_currency.code} FX clearing",
    )
    target_investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=target_currency,
        owner_type="investor",
        owner_id=investor_id,
        name=f"{target_currency.code} investor balance liability {investor_id}",
    )
    target_postings = [
        PostingCommand(
            account=target_fx_clearing_account,
            side=LedgerPostingSide.DEBIT,
            amount_minor=gross_target_amount_minor,
            memo="FX target currency receivable created",
        ),
        PostingCommand(
            account=target_investor_liability_account,
            side=LedgerPostingSide.CREDIT,
            amount_minor=target_amount_minor,
            memo="FX target balance credited to investor",
        ),
    ]
    if fee_minor > 0:
        target_fee_revenue_account = get_or_create_ledger_account(
            account_type=LedgerAccountType.FX_FEE_REVENUE,
            currency=target_currency,
            owner_type="garanta",
            owner_id="platform",
            name=f"{target_currency.code} FX fee revenue",
        )
        target_postings.append(
            PostingCommand(
                account=target_fee_revenue_account,
                side=LedgerPostingSide.CREDIT,
                amount_minor=fee_minor,
                memo="FX platform fee revenue",
            )
        )
    target_journal = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="investor_fx_target_balance_credited",
            direction=LedgerDirection.INTERNAL,
            currency=target_currency.code,
            gross_amount_minor=gross_target_amount_minor,
            net_amount_minor=target_amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=as_of,
            received_at=as_of,
            source_type=source_type,
            source_id=source_id,
            lender_user_id=investor_id,
            idempotency_key=target_journal_key,
            postings=target_postings,
            tax_metadata={
                "client_money_flow_minor": target_amount_minor,
                "fx_fee_revenue_minor": fee_minor,
            },
            metadata={
                FX_EXCHANGE_FINGERPRINT_METADATA_KEY: request_fingerprint,
                "source_currency": source_currency.code,
                "source_amount_minor": source_amount_minor,
                "gross_target_amount_minor": gross_target_amount_minor,
                "target_amount_minor": target_amount_minor,
                "fee_minor": fee_minor,
            },
        )
    )
    _validate_lot_conservation_values(
        original_amount_minor=target_amount_minor,
        available_amount_minor=target_amount_minor,
        currency_code=target_currency.code,
    )
    target_lot = InvestorBalanceLot.objects.create(
        investor_user_id=investor_id,
        currency=target_currency,
        source_journal_entry=target_journal,
        source_type=BalanceLotSourceType.FX_PROCEEDS,
        source_id=source_id,
        received_at=as_of,
        investment_deadline_at=inherited_investment_deadline_at,
        withdrawal_deadline_at=inherited_withdrawal_deadline_at,
        original_amount_minor=target_amount_minor,
        available_amount_minor=target_amount_minor,
        lineage=[
            {
                "source_type": source_type,
                "source_id": source_id,
                "source_currency": source_currency.code,
                "target_currency": target_currency.code,
                "source_lot_allocations": source_allocations,
                "gross_target_amount_minor": gross_target_amount_minor,
                "target_amount_minor": target_amount_minor,
                "fee_minor": fee_minor,
                "inherited_investment_deadline_at": inherited_investment_deadline_at.isoformat(),
                "inherited_withdrawal_deadline_at": inherited_withdrawal_deadline_at.isoformat(),
                "metadata": command.metadata or {},
            }
        ],
    )

    source_investor_liability_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=source_currency,
        owner_type="investor",
        owner_id=investor_id,
        name=f"{source_currency.code} investor balance liability {investor_id}",
    )
    source_fx_clearing_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.FX_CLEARING,
        currency=source_currency,
        owner_type="fx",
        owner_id="platform",
        name=f"{source_currency.code} FX clearing",
    )
    source_journal = post_journal_entry(
        PostJournalEntryCommand(
            actor=command.actor,
            event_type="investor_fx_source_balance_converted",
            direction=LedgerDirection.INTERNAL,
            currency=source_currency.code,
            gross_amount_minor=source_amount_minor,
            net_amount_minor=source_amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=as_of,
            received_at=as_of,
            source_type=source_type,
            source_id=source_id,
            lender_user_id=investor_id,
            idempotency_key=source_journal_key,
            postings=[
                PostingCommand(
                    account=source_investor_liability_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=source_amount_minor,
                    memo="FX source balance debited from investor",
                ),
                PostingCommand(
                    account=source_fx_clearing_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=source_amount_minor,
                    memo="FX source currency clearing credited",
                ),
            ],
            tax_metadata={
                "client_money_flow_minor": source_amount_minor,
            },
            metadata={
                FX_EXCHANGE_FINGERPRINT_METADATA_KEY: request_fingerprint,
                "target_journal_entry_id": str(target_journal.id),
                "target_balance_lot_id": str(target_lot.id),
                "source_lot_allocations": source_allocations,
                "target_currency": target_currency.code,
                "gross_target_amount_minor": gross_target_amount_minor,
                "target_amount_minor": target_amount_minor,
                "fee_minor": fee_minor,
            },
        )
    )
    return InvestorFxExchangeLedgerResult(
        source_journal_entry=source_journal,
        target_journal_entry=target_journal,
        target_balance_lot=target_lot,
        source_lot_allocations=source_allocations,
    )


@transaction.atomic
def close_primary_loan_funding(
    command: ClosePrimaryLoanFundingCommand,
) -> ClosePrimaryLoanFundingResult:
    _require_admin_actor(command.actor)
    currency = _enabled_currency(command.currency)
    accepted_principal = _validate_money(
        command.accepted_principal_minor,
        currency.code,
        "Accepted funded principal",
    )
    if type(command.borrower_success_fee_bps) is not int:
        raise LedgerValidationError("Borrower success fee must be an integer bps value.")
    if command.borrower_success_fee_bps < 0 or command.borrower_success_fee_bps > 10_000:
        raise LedgerValidationError("Borrower success fee must be between 0 and 10,000 bps.")
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    source_type = _clean_required(command.source_type, "Source type")
    source_id = _clean_required(command.source_id, "Source id")
    as_of = command.as_of or now_utc()
    value_date = business_date(as_of)
    borrower_success_fee = int(
        (
            Decimal(accepted_principal)
            * Decimal(command.borrower_success_fee_bps)
            / Decimal(10_000)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    borrower_disbursement_payable = accepted_principal - borrower_success_fee
    if borrower_disbursement_payable < 0:
        raise LedgerValidationError("Borrower disbursement payable cannot be negative.")
    journal_idempotency_key = _derived_idempotency_key(
        "ledger-primary-loan-close",
        idempotency_key,
    )
    request_fingerprint = _primary_loan_close_request_fingerprint(
        command,
        currency_code=currency.code,
        accepted_principal_minor=accepted_principal,
        borrower_success_fee_minor=borrower_success_fee,
        borrower_disbursement_payable_minor=borrower_disbursement_payable,
        idempotency_key=idempotency_key,
    )
    existing = _existing_primary_loan_close(
        journal_idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing

    loan_funding_escrow_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.LOAN_FUNDING_ESCROW,
        currency=currency,
        owner_type="loan",
        owner_id=str(command.loan_id),
        name=f"{currency.code} loan funding escrow {command.loan_id}",
    )
    escrow_balance = _credit_balance_for_account(loan_funding_escrow_account)
    if escrow_balance < accepted_principal:
        raise LedgerValidationError("Loan funding escrow has insufficient balance to close.")
    borrower_disbursement_account = get_or_create_ledger_account(
        account_type=LedgerAccountType.BORROWER_DISBURSEMENT_PAYABLE,
        currency=currency,
        owner_type="loan",
        owner_id=str(command.loan_id),
        name=f"{currency.code} borrower disbursement payable loan {command.loan_id}",
    )
    postings = [
        PostingCommand(
            account=loan_funding_escrow_account,
            side=LedgerPostingSide.DEBIT,
            amount_minor=accepted_principal,
            memo="Loan funding escrow closed into borrower payable and platform revenue",
        )
    ]
    if borrower_disbursement_payable > 0:
        postings.append(
            PostingCommand(
                account=borrower_disbursement_account,
                side=LedgerPostingSide.CREDIT,
                amount_minor=borrower_disbursement_payable,
                memo="Borrower disbursement payable after success fee",
            )
        )
    if borrower_success_fee > 0:
        garanta_revenue_account = get_or_create_ledger_account(
            account_type=LedgerAccountType.GARANTA_ACCRUED_REVENUE,
            currency=currency,
            owner_type="garanta",
            owner_id="platform",
            name=f"{currency.code} Garanta accrued revenue",
        )
        postings.append(
            PostingCommand(
                account=garanta_revenue_account,
                side=LedgerPostingSide.CREDIT,
                amount_minor=borrower_success_fee,
                memo="Borrower success fee accrued at funding close",
            )
        )
    try:
        journal_entry = post_journal_entry(
            PostJournalEntryCommand(
                actor=command.actor,
                event_type="primary_loan_funding_closed",
                direction=LedgerDirection.INTERNAL,
                currency=currency.code,
                gross_amount_minor=accepted_principal,
                net_amount_minor=borrower_disbursement_payable,
                booking_date=value_date,
                value_date=value_date,
                effective_at=as_of,
                received_at=as_of,
                source_type=source_type,
                source_id=source_id,
                borrower_id=str(command.borrower_id),
                loan_id=str(command.loan_id),
                idempotency_key=journal_idempotency_key,
                postings=postings,
                tax_metadata={
                    "garanta_revenue_minor": borrower_success_fee,
                    "client_money_flow_minor": accepted_principal,
                },
                metadata={
                    PRIMARY_LOAN_CLOSE_FINGERPRINT_METADATA_KEY: request_fingerprint,
                    "borrower_success_fee_bps": command.borrower_success_fee_bps,
                    "borrower_success_fee_minor": borrower_success_fee,
                    "borrower_disbursement_payable_minor": borrower_disbursement_payable,
                    "escrow_balance_before_close_minor": escrow_balance,
                },
            )
        )
    except IntegrityError:
        existing_after_race = _existing_primary_loan_close(
            journal_idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    return ClosePrimaryLoanFundingResult(
        journal_entry=journal_entry,
        borrower_success_fee_minor=borrower_success_fee,
        borrower_disbursement_payable_minor=borrower_disbursement_payable,
    )


def investor_balance_liability_minor(*, currency: Currency) -> int:
    aggregate = InvestorBalanceLot.objects.filter(currency=currency).aggregate(
        total=Sum("available_amount_minor")
    )
    return int(aggregate["total"] or 0)


def investor_balance_liability_posting_minor(*, currency: Currency) -> int:
    account_ids = LedgerAccount.objects.filter(
        currency=currency,
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
    ).values_list("id", flat=True)
    debit_total = (
        LedgerPosting.objects.filter(
            account_id__in=account_ids,
            side=LedgerPostingSide.DEBIT,
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )
    credit_total = (
        LedgerPosting.objects.filter(
            account_id__in=account_ids,
            side=LedgerPostingSide.CREDIT,
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )
    return int(credit_total) - int(debit_total)


def investor_balance_integrity_breaks(
    *,
    currency: Currency,
) -> list[InvestorBalanceIntegrityBreak]:
    lot_totals: dict[str, int] = {}
    for lot in InvestorBalanceLot.objects.filter(currency=currency):
        _validate_lot_conservation(lot)
        investor_id = str(lot.investor_user_id)
        lot_totals[investor_id] = lot_totals.get(investor_id, 0) + lot.available_amount_minor

    posting_totals: dict[str, int] = {}
    postings = LedgerPosting.objects.filter(
        currency=currency,
        account__account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        account__owner_type="investor",
    ).select_related("account")
    for posting in postings:
        investor_id = posting.account.owner_id
        if not investor_id:
            continue
        signed_amount = posting.amount_minor
        if posting.side == LedgerPostingSide.DEBIT:
            signed_amount = -signed_amount
        posting_totals[investor_id] = posting_totals.get(investor_id, 0) + signed_amount

    breaks: list[InvestorBalanceIntegrityBreak] = []
    for investor_id in sorted(set(lot_totals) | set(posting_totals)):
        lot_total = lot_totals.get(investor_id, 0)
        posting_total = posting_totals.get(investor_id, 0)
        if lot_total != posting_total:
            breaks.append(
                InvestorBalanceIntegrityBreak(
                    investor_user_id=investor_id,
                    currency=currency.code,
                    lot_available_minor=lot_total,
                    liability_posting_minor=posting_total,
                    difference_minor=lot_total - posting_total,
                )
            )
    return breaks


def _account_group_balance_minor(
    *,
    currency: Currency,
    account_type: str,
) -> int:
    account_ids = LedgerAccount.objects.filter(
        currency=currency,
        account_type=account_type,
    ).values_list("id", flat=True)
    debit_total = (
        LedgerPosting.objects.filter(
            account_id__in=account_ids,
            side=LedgerPostingSide.DEBIT,
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )
    credit_total = (
        LedgerPosting.objects.filter(
            account_id__in=account_ids,
            side=LedgerPostingSide.CREDIT,
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )
    return int(debit_total) - int(credit_total)


def _credit_balance_minor(
    *,
    currency: Currency,
    account_type: str,
) -> int:
    return -_account_group_balance_minor(currency=currency, account_type=account_type)


@transaction.atomic
def create_reconciliation_snapshot(
    command: CreateReconciliationSnapshotCommand,
) -> ReconciliationSnapshot:
    _require_admin_actor(command.actor)
    currency = _enabled_currency(command.currency)
    bank_stated_balance = _validate_nonnegative_money(
        command.bank_stated_balance_minor,
        currency.code,
        "Bank-stated balance",
    )
    pending_exception_balance = _validate_nonnegative_money(
        command.pending_exception_balance_minor,
        currency.code,
        "Pending exception balance",
    )
    investor_balance = investor_balance_liability_minor(currency=currency)
    investor_posting_balance = investor_balance_liability_posting_minor(currency=currency)
    integrity_breaks = investor_balance_integrity_breaks(currency=currency)
    garanta_accrued = _credit_balance_minor(
        currency=currency,
        account_type=LedgerAccountType.GARANTA_ACCRUED_REVENUE,
    )
    suspense = _credit_balance_minor(
        currency=currency,
        account_type=LedgerAccountType.SUSPENSE_UNMATCHED_CASH,
    )
    withdrawal_payable = _credit_balance_minor(
        currency=currency,
        account_type=LedgerAccountType.WITHDRAWAL_PAYABLE,
    )
    borrower_disbursement_payable = _credit_balance_minor(
        currency=currency,
        account_type=LedgerAccountType.BORROWER_DISBURSEMENT_PAYABLE,
    )
    collection_cash_balance = _account_group_balance_minor(
        currency=currency,
        account_type=LedgerAccountType.COLLECTION_CASH,
    )
    account_sign_anomalies = [
        {"account_type": account_type, "credit_balance_minor": amount}
        for account_type, amount in [
            (LedgerAccountType.GARANTA_ACCRUED_REVENUE, garanta_accrued),
            (LedgerAccountType.SUSPENSE_UNMATCHED_CASH, suspense),
            (LedgerAccountType.WITHDRAWAL_PAYABLE, withdrawal_payable),
            (
                LedgerAccountType.BORROWER_DISBURSEMENT_PAYABLE,
                borrower_disbursement_payable,
            ),
        ]
        if amount < 0
    ]
    expected = (
        investor_balance
        + withdrawal_payable
        + borrower_disbursement_payable
        + garanta_accrued
        + suspense
        + pending_exception_balance
    )
    difference = bank_stated_balance - expected
    bank_to_collection_cash_difference = bank_stated_balance - collection_cash_balance
    metadata = dict(command.metadata or {})
    metadata.update(
        {
            "snapshot_semantics": (
                "current ledger state as of snapshot creation time; "
                "as_of_date is an admin-selected reconciliation label"
            ),
            "investor_balance_liability_posting_minor": investor_posting_balance,
            "withdrawal_payable_minor": withdrawal_payable,
            "borrower_disbursement_payable_minor": borrower_disbursement_payable,
            "collection_cash_ledger_balance_minor": collection_cash_balance,
            "bank_to_collection_cash_difference_minor": bank_to_collection_cash_difference,
            "account_sign_anomalies": account_sign_anomalies,
            "investor_balance_integrity_breaks": [
                {
                    "investor_user_id": item.investor_user_id,
                    "currency": item.currency,
                    "lot_available_minor": item.lot_available_minor,
                    "liability_posting_minor": item.liability_posting_minor,
                    "difference_minor": item.difference_minor,
                }
                for item in integrity_breaks
            ],
        }
    )
    snapshot = cast(
        ReconciliationSnapshot,
        ReconciliationSnapshot.objects.create(
            currency=currency,
            as_of_date=command.as_of_date,
            bank_stated_balance_minor=bank_stated_balance,
            investor_balance_liability_minor=investor_balance,
            garanta_accrued_revenue_minor=garanta_accrued,
            suspense_unmatched_cash_minor=suspense,
            pending_exception_balance_minor=pending_exception_balance,
            reconciliation_difference_minor=difference,
            created_by_admin_id=command.actor.pk,
            notes=command.notes.strip(),
            metadata=metadata,
        ),
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="ledger.reconciliation_snapshot_created",
            target_type="ReconciliationSnapshot",
            target_id=str(snapshot.id),
            metadata={
                "currency": currency.code,
                "as_of_date": command.as_of_date.isoformat(),
                "difference_minor": difference,
            },
        )
    )
    if difference != 0:
        record_domain_event(
            DomainEventCommand(
                event_type="LedgerReconciliationBreakDetected",
                aggregate_type="ReconciliationSnapshot",
                aggregate_id=str(snapshot.id),
                payload={
                    "currency": currency.code,
                    "as_of_date": command.as_of_date.isoformat(),
                    "difference_minor": difference,
                },
                idempotency_key=f"reconciliation:{snapshot.id}:break",
            )
        )
    if bank_to_collection_cash_difference != 0:
        record_domain_event(
            DomainEventCommand(
                event_type="LedgerCashLedgerMismatchDetected",
                aggregate_type="ReconciliationSnapshot",
                aggregate_id=str(snapshot.id),
                payload={
                    "currency": currency.code,
                    "as_of_date": command.as_of_date.isoformat(),
                    "difference_minor": bank_to_collection_cash_difference,
                },
                idempotency_key=f"reconciliation:{snapshot.id}:cash-ledger-mismatch",
            )
        )
    if integrity_breaks:
        record_domain_event(
            DomainEventCommand(
                event_type="LedgerInvestorBalanceIntegrityBreakDetected",
                aggregate_type="ReconciliationSnapshot",
                aggregate_id=str(snapshot.id),
                payload={
                    "currency": currency.code,
                    "as_of_date": command.as_of_date.isoformat(),
                    "breaks": metadata["investor_balance_integrity_breaks"],
                },
                idempotency_key=f"reconciliation:{snapshot.id}:investor-balance-integrity-break",
            )
        )
    return snapshot
