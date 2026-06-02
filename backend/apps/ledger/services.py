from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, cast

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
)
from backend.apps.platform_core.domain.money import Money, MoneyError, normalize_currency
from backend.apps.platform_core.domain.time import business_timezone, now_utc, to_business_time
from backend.apps.platform_core.models import Currency
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
MAX_IDEMPOTENCY_KEY_LENGTH = 160
REQUEST_FINGERPRINT_METADATA_KEY = "request_fingerprint"


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
    withdrawn_amount_minor: int = 0,
    penalized_amount_minor: int = 0,
    currency_code: str,
) -> None:
    amounts = {
        "Original amount": original_amount_minor,
        "Available amount": available_amount_minor,
        "Invested amount": invested_amount_minor,
        "Withdrawn amount": withdrawn_amount_minor,
        "Penalized amount": penalized_amount_minor,
    }
    for label, amount in amounts.items():
        _validate_nonnegative_money(amount, currency_code, label)
    consumed_total = (
        available_amount_minor
        + invested_amount_minor
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
    lots = (
        InvestorBalanceLot.objects.filter(
            investor_user_id=investor_user_id,
            currency=currency_model,
            status=BalanceLotStatus.AVAILABLE,
            available_amount_minor__gt=0,
        )
        .order_by("received_at", "created_at", "id")
    )
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
    garanta_accrued = abs(
        _account_group_balance_minor(
            currency=currency,
            account_type=LedgerAccountType.GARANTA_ACCRUED_REVENUE,
        )
    )
    suspense = abs(
        _account_group_balance_minor(
            currency=currency,
            account_type=LedgerAccountType.SUSPENSE_UNMATCHED_CASH,
        )
    )
    collection_cash_balance = _account_group_balance_minor(
        currency=currency,
        account_type=LedgerAccountType.COLLECTION_CASH,
    )
    expected = investor_balance + garanta_accrued + suspense + pending_exception_balance
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
            "collection_cash_ledger_balance_minor": collection_cash_balance,
            "bank_to_collection_cash_difference_minor": bank_to_collection_cash_difference,
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
