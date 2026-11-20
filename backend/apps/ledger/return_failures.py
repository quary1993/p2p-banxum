"""IP of Webby-Soft SRL. 18.4: failed returns (Q02), compliance alerts and verification of a
return account from a deposit (Q02.5).

A failed return is a withdrawal or forced return that the receiving bank sent back. The team
records it once; the money goes back to the lots it came from, with their original age (no new
period, no penalty). The platform never retries by itself: the team sends again only to a
corrected or newly verified account. While a failure is open the investor gets a notice every day,
an admin task stays open, and compliance takes the case after a few days, or at once when the
money is at day 57 or later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Model

from backend.apps.ledger import notices as investor_notices
from backend.apps.ledger import services as ledger
from backend.apps.ledger.models import (
    BalanceLotStatus,
    BalanceReturnFailure,
    BalanceReturnFailureReason,
    BalanceReturnFailureResolution,
    BalanceReturnFailureStatus,
    BankOperation,
    BankOperationStatus,
    BankOperationType,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorPayoutInstructionStatus,
    InvestorWithdrawalRequest,
    InvestorWithdrawalRequestStatus,
    LedgerAccountType,
    LedgerDirection,
    LedgerPostingSide,
)
from backend.apps.platform_core.domain.access import actor_ref_for_user
from backend.apps.platform_core.domain.funding import (
    BALANCE_COMPLIANCE_ALERT_DAY,
    RETURN_FAILURE_COMPLIANCE_HOLDING_DAY,
    BalanceReturnSchedule,
    balance_holding_day,
    balance_return_is_due,
)
from backend.apps.platform_core.domain.money import format_amount_minor
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.selectors.settings import (
    compliance_alert_email,
    return_failure_compliance_after_days,
)
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.balance_schedule import BalanceScheduler
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    record_domain_event,
)
from backend.apps.platform_core.services.investor_notices import (
    InvestorNotice,
    brand,
    enqueue_investor_notice,
    masked_iban,
    notice_amount,
    notice_date,
)

# Causes on the investor's side: the failed account is revoked so nothing is sent to it again.
INVESTOR_ACCOUNT_REASONS = frozenset(
    {
        BalanceReturnFailureReason.ACCOUNT_CLOSED,
        BalanceReturnFailureReason.ACCOUNT_UNKNOWN,
        BalanceReturnFailureReason.NAME_MISMATCH,
        BalanceReturnFailureReason.ACCOUNT_BLOCKED,
    }
)
# Causes on the bank's side: the same account may be used again once the cause is cleared.
BANK_SIDE_REASONS = frozenset(
    {BalanceReturnFailureReason.BANK_RESTRICTION, BalanceReturnFailureReason.TECHNICAL}
)
INVESTOR_REASON_TEXT = {
    BalanceReturnFailureReason.ACCOUNT_CLOSED: "Your bank says the account is closed.",
    BalanceReturnFailureReason.ACCOUNT_UNKNOWN: "Your bank does not know this account number.",
    BalanceReturnFailureReason.NAME_MISMATCH: (
        "The account holder name does not match the account."
    ),
    BalanceReturnFailureReason.ACCOUNT_BLOCKED: (
        "Your bank says the account is blocked or restricted."
    ),
    BalanceReturnFailureReason.BANK_RESTRICTION: (
        "The receiving bank could not accept the transfer. This is not your fault."
    ),
    BalanceReturnFailureReason.TECHNICAL: (
        "The transfer came back because of a technical error. This is not your fault."
    ),
    BalanceReturnFailureReason.OTHER: "Your bank sent the transfer back.",
}
RETURN_FAILED_TOPIC = "email.balance_return_failed"
RETURN_FAILURE_TASK_TYPE = "BalanceReturnFailure"


def _admin_ops() -> Any:
    return import_module("backend.apps.admin_ops.services")


def open_failure_lot_ids(*, currency: Currency | None = None) -> set[str]:
    """Lots of open failed returns: the scan does not send them again by itself.

    Audit S3-2: a failed return stays open while its money is on the balance (a note cannot
    close it), so this block holds until the money leaves through a recorded withdrawal.
    """
    queryset = BalanceReturnFailure.objects.filter(status=BalanceReturnFailureStatus.OPEN)
    if currency is not None:
        queryset = queryset.filter(currency=currency)
    return {
        str(lot_id) for lot_ids in queryset.values_list("lot_ids", flat=True) for lot_id in lot_ids
    }


# --- Compliance alerts -----------------------------------------------------------------------


def _compliance_email() -> str:
    return compliance_alert_email(
        str(getattr(settings, "OPERATIONS_ALERT_EMAIL", "") or "hq@banxum.com")
    )


def raise_compliance_alert(
    *,
    actor: Model,
    related_object_type: str,
    related_object_id: str,
    title: str,
    notes: str,
    data_rows: list[list[str]],
    metadata: dict[str, Any],
) -> bool:
    """One compliance task and one email per object. True when the alert is new."""
    task, created = _admin_ops().ensure_related_admin_task(
        actor=actor,
        task_type="compliance_review",
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        title=title,
        priority="urgent",
        notes=notes,
    )
    if not created:
        return False
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"email:compliance:{related_object_type}:{related_object_id}",
            topic="email.compliance_alert",
            payload={
                "email": _compliance_email(),
                "subject": f"{settings.PLATFORM_BRAND_NAME} compliance: {title}",
                "notice_label": "Compliance alert",
                "headline": title,
                "status_label": "Urgent action",
                "status_tone": "danger",
                "body_text": notes,
                "template_key": "ops.compliance_alert.v1",
                "data_rows": [*data_rows, ["Admin task", str(task.id)]],
                "metadata": {**metadata, "admin_task_id": str(task.id)},
            },
        )
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="ledger.compliance_alert_raised",
            target_type=related_object_type,
            target_id=related_object_id,
            metadata={**metadata, "admin_task_id": str(task.id), "title": title},
        )
    )
    return True


def _investor_label(investor_user_id: str) -> str:
    user = get_user_model().objects.filter(id=investor_user_id).only("email", "full_name").first()
    if user is None:
        return investor_user_id
    return (
        str(getattr(user, "full_name", "")).strip()
        or str(getattr(user, "email", "")).strip()
        or investor_user_id
    )


def alert_lot_not_returned(
    *,
    actor: Model,
    lot: InvestorBalanceLot,
    schedule: BalanceReturnSchedule,
    as_of: datetime,
) -> bool:
    """Money at day 59 that is still on the balance (no return transfer made)."""
    day = schedule.holding_day(business_date(as_of))
    amount = format_amount_minor(lot.available_amount_minor, str(lot.currency_id))
    return raise_compliance_alert(
        actor=actor,
        related_object_type="BalanceLotReturnDeadline",
        related_object_id=str(lot.id),
        title=f"Money at day {day} not returned: {amount}",
        notes=(
            f"{amount} of {_investor_label(str(lot.investor_user_id))} is at day {day} after "
            f"its value date and is still on the balance. The 60-day limit is "
            f"{schedule.legal_limit_date.isoformat()}. Check why the return is not made (no "
            "usable bank account, a stopped request) and act before the limit."
        ),
        data_rows=[
            ["Investor", str(lot.investor_user_id)],
            ["Amount", amount],
            ["Holding day", str(day)],
            ["60-day limit", schedule.legal_limit_date.isoformat()],
        ],
        metadata={
            "lot_id": str(lot.id),
            "investor_user_id": str(lot.investor_user_id),
            "holding_day": day,
        },
    )


def _request_oldest_day(withdrawal_request: InvestorWithdrawalRequest, as_of: datetime) -> int:
    days = [
        balance_holding_day(
            withdrawal_deadline_at=datetime.fromisoformat(
                str(allocation["withdrawal_deadline_at"])
            ),
            as_of=as_of,
        )
        for allocation in cast(list[dict[str, Any]], withdrawal_request.lot_allocations or [])
        if allocation.get("withdrawal_deadline_at")
    ]
    return max(days, default=0)


def alert_late_return_request(
    *, actor: Model, withdrawal_request: InvestorWithdrawalRequest
) -> bool:
    """A return requested too late for the bank to debit by day 59 (a missed scan, cut-off)."""
    timing = dict(withdrawal_request.metadata or {}).get("return_timing")
    if not isinstance(timing, dict) or not timing.get("debit_after_latest_day"):
        return False
    amount = format_amount_minor(withdrawal_request.amount_minor, withdrawal_request.currency_id)
    return raise_compliance_alert(
        actor=actor,
        related_object_type="InvestorWithdrawalRequest",
        related_object_id=str(withdrawal_request.id),
        title=f"Return requested too late for day 59: {amount}",
        notes=(
            f"The return of {amount} was requested on {timing.get('order_day')}; with the "
            f"bank's processing time the debit comes on {timing.get('expected_debit_date')}, "
            f"after the planned latest debit day {timing.get('latest_debit_date')} (60-day "
            f"limit {timing.get('legal_limit_date')}). Send the transfer at once."
        ),
        data_rows=[
            ["Investor", str(withdrawal_request.investor_user_id)],
            ["Amount", amount],
            ["Expected debit", str(timing.get("expected_debit_date"))],
            ["60-day limit", str(timing.get("legal_limit_date"))],
        ],
        metadata={
            "withdrawal_request_id": str(withdrawal_request.id),
            "return_timing": timing,
        },
    )


def alert_return_requests_not_made(
    *, actor: Model, as_of: datetime, currency: Currency | None
) -> list[str]:
    """Forced returns not marked as made when their oldest money reaches day 59."""
    queryset = InvestorWithdrawalRequest.objects.filter(
        is_forced=True, status=InvestorWithdrawalRequestStatus.REQUESTED
    )
    if currency is not None:
        queryset = queryset.filter(currency=currency)
    alerts: list[str] = []
    for withdrawal_request in queryset.order_by("requested_at", "id"):
        day = _request_oldest_day(withdrawal_request, as_of)
        if day < BALANCE_COMPLIANCE_ALERT_DAY:
            continue
        amount = format_amount_minor(
            withdrawal_request.amount_minor, withdrawal_request.currency_id
        )
        if raise_compliance_alert(
            actor=actor,
            related_object_type="ForcedReturnNotMade",
            related_object_id=str(withdrawal_request.id),
            title=f"Return not marked as made at day {day}: {amount}",
            notes=(
                f"The forced return of {amount} to "
                f"{masked_iban(withdrawal_request.destination_iban)} is not marked as made, and "
                f"its money is at day {day}. The bank must debit "
                "Garanta's account within the 60 days. Make the transfer and record it, or "
                "explain the delay."
            ),
            data_rows=[
                ["Investor", str(withdrawal_request.investor_user_id)],
                ["Amount", amount],
                ["Holding day", str(day)],
            ],
            metadata={"withdrawal_request_id": str(withdrawal_request.id), "holding_day": day},
        ):
            alerts.append(f"ForcedReturnNotMade:{withdrawal_request.id}")
    return alerts


# --- Recording a returned transfer -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecordReturnedWithdrawalCommand:
    actor: Model
    withdrawal_request_id: str
    returned_value_date: date
    reason_code: str
    bank_reason_text: str = ""
    booking_date: date | None = None
    bank_reference: str = ""
    evidence_reference: str = ""
    collection_account_identifier: str = ""
    notes: str = ""
    idempotency_key: str = ""


def _reason(value: str) -> BalanceReturnFailureReason:
    try:
        return BalanceReturnFailureReason(value)
    except ValueError as exc:
        raise ledger.LedgerValidationError(
            "Choose the bank's reason for the returned transfer."
        ) from exc


@transaction.atomic
def record_returned_withdrawal(command: RecordReturnedWithdrawalCommand) -> BalanceReturnFailure:
    """The bank sent a withdrawal or return back: reconcile it once and open the failure."""
    ledger._require_admin_actor(command.actor)
    idempotency_key = ledger._clean_idempotency_key(command.idempotency_key)
    withdrawal_request = (
        InvestorWithdrawalRequest.objects.select_for_update()
        .select_related("currency", "bank_operation")
        .filter(id=command.withdrawal_request_id)
        .first()
    )
    if withdrawal_request is None:
        raise ledger.LedgerValidationError("Withdrawal request does not exist.")
    existing = BalanceReturnFailure.objects.filter(withdrawal_request=withdrawal_request).first()
    if existing is not None:
        if existing.metadata.get("idempotency_key") == idempotency_key:
            return existing
        raise ledger.LedgerConflictError(
            "The returned transfer of this withdrawal is already recorded. Nothing was changed.",
            code="withdrawal_return_already_recorded",
        )
    if withdrawal_request.status != InvestorWithdrawalRequestStatus.FINALIZED:
        raise ledger.LedgerConflictError(
            "Only a withdrawal that was sent can come back from the bank.",
            code="withdrawal_not_sent",
        )
    reason = _reason(command.reason_code)
    booking_date = command.booking_date or command.returned_value_date
    ledger._validate_bank_dates_not_in_future(
        booking_date=booking_date, value_date=command.returned_value_date
    )
    sent_value_date = (
        withdrawal_request.bank_operation.value_date if withdrawal_request.bank_operation else None
    )
    if sent_value_date is not None and command.returned_value_date < sent_value_date:
        raise ledger.LedgerValidationError(
            "The returned transfer cannot have a value date before the transfer was sent "
            f"({sent_value_date.isoformat()})."
        )
    currency = withdrawal_request.currency
    amount_minor = int(withdrawal_request.amount_minor)
    # The money comes back to the account it was sent from, unless the admin says otherwise.
    sent_from = (
        str(withdrawal_request.bank_operation.collection_account_identifier)
        if withdrawal_request.bank_operation
        else ""
    )
    collection_account_identifier = ledger._resolve_collection_account_identifier(
        currency_code=currency.code,
        supplied_identifier=command.collection_account_identifier or sent_from,
    )
    recorded_at = now_utc()
    bank_operation = BankOperation.objects.create(
        operation_type=BankOperationType.LENDER_WITHDRAWAL_RETURN,
        status=BankOperationStatus.RECONCILED,
        amount_minor=amount_minor,
        currency=currency,
        booking_date=booking_date,
        value_date=command.returned_value_date,
        collection_account_identifier=collection_account_identifier,
        payer_name=withdrawal_request.destination_account_name,
        payer_account_identifier=withdrawal_request.destination_iban,
        payee_name="Garanta Finanzgruppe AG",
        payee_account_identifier=collection_account_identifier,
        bank_reference=command.bank_reference.strip(),
        payment_reference="",
        linked_object_type="withdrawal_request",
        linked_object_id=str(withdrawal_request.id),
        evidence_reference=command.evidence_reference.strip(),
        confirmed_by_admin_id=command.actor.pk,
        confirmed_at=recorded_at,
        notes=command.notes.strip(),
        metadata={"reason_code": reason.value, "bank_reason_text": command.bank_reason_text},
        idempotency_key=ledger._derived_idempotency_key("withdrawal-return", idempotency_key),
    )
    ledger._restore_lots_from_withdrawal_allocations(
        withdrawal_request=withdrawal_request, currency=currency
    )
    investor_id = str(withdrawal_request.investor_user_id)
    collection_cash_account = ledger.get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
        name=f"{currency.code} collection cash",
    )
    investor_liability_account = ledger.get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=investor_id,
        name=f"{currency.code} investor balance liability {investor_id}",
    )
    journal_entry = ledger.post_journal_entry(
        ledger.PostJournalEntryCommand(
            actor=command.actor,
            event_type="lender_withdrawal_returned",
            direction=LedgerDirection.IN,
            currency=currency.code,
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=booking_date,
            value_date=command.returned_value_date,
            effective_at=recorded_at,
            received_at=ledger._received_at_from_value_date(command.returned_value_date),
            source_type="bank_operation",
            source_id=str(bank_operation.id),
            lender_user_id=investor_id,
            bank_operation=bank_operation,
            bank_reference=command.bank_reference,
            evidence_reference=command.evidence_reference,
            idempotency_key=ledger._derived_idempotency_key(
                "ledger-withdrawal-return", idempotency_key
            ),
            postings=[
                ledger.PostingCommand(
                    account=collection_cash_account,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount_minor,
                    memo="Returned transfer received back into the collection account",
                ),
                ledger.PostingCommand(
                    account=investor_liability_account,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount_minor,
                    memo="Investor balance restored after the bank sent the transfer back",
                ),
            ],
            metadata={
                "bank_operation_type": BankOperationType.LENDER_WITHDRAWAL_RETURN,
                "withdrawal_request_id": str(withdrawal_request.id),
                "reason_code": reason.value,
            },
        )
    )
    withdrawal_request.status = InvestorWithdrawalRequestStatus.RETURNED
    withdrawal_request.metadata = {
        **cast(dict[str, Any], withdrawal_request.metadata),
        "returned": {
            "bank_operation_id": str(bank_operation.id),
            "journal_entry_id": str(journal_entry.id),
            "reason_code": reason.value,
            "returned_value_date": command.returned_value_date.isoformat(),
            "recorded_by_admin_id": str(command.actor.pk),
        },
    }
    withdrawal_request.save(update_fields=["status", "metadata", "updated_at"])

    lot_ids = [
        str(allocation["lot_id"])
        for allocation in cast(list[dict[str, Any]], withdrawal_request.lot_allocations)
    ]
    failed_instruction = (
        InvestorPayoutInstruction.objects.filter(
            investor_user_id=withdrawal_request.investor_user_id,
            currency=currency,
            destination_iban=withdrawal_request.destination_iban,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    scheduler = BalanceScheduler()
    lots = list(InvestorBalanceLot.objects.filter(id__in=lot_ids))
    due_back = withdrawal_request.is_forced or any(
        balance_return_is_due(schedule=scheduler.schedule(lot), as_of=recorded_at) for lot in lots
    )
    failure = BalanceReturnFailure.objects.create(
        withdrawal_request=withdrawal_request,
        investor_user_id=withdrawal_request.investor_user_id,
        currency=currency,
        amount_minor=amount_minor,
        is_forced=bool(withdrawal_request.is_forced),
        reason_code=reason.value,
        bank_reason_text=command.bank_reason_text.strip(),
        returned_value_date=command.returned_value_date,
        return_bank_operation=bank_operation,
        return_journal_entry=journal_entry,
        failed_payout_instruction_id=failed_instruction.id if failed_instruction else None,
        failed_destination_iban=withdrawal_request.destination_iban,
        lot_ids=lot_ids,
        status=(
            BalanceReturnFailureStatus.OPEN if due_back else BalanceReturnFailureStatus.RESOLVED
        ),
        recorded_by_admin_id=command.actor.pk,
        recorded_at=recorded_at,
        last_notice_date=business_date(recorded_at),
        resolved_at=None if due_back else recorded_at,
        resolved_by_admin_id=None if due_back else command.actor.pk,
        resolution="" if due_back else BalanceReturnFailureResolution.MONEY_AVAILABLE,
        metadata={"idempotency_key": idempotency_key, "notes": command.notes.strip()},
    )
    event_metadata = {
        "investor_user_id": investor_id,
        "currency": currency.code,
        "amount_minor": amount_minor,
        "withdrawal_request_id": str(withdrawal_request.id),
        "bank_operation_id": str(bank_operation.id),
        "journal_entry_id": str(journal_entry.id),
        "reason_code": reason.value,
        "lot_ids": lot_ids,
        "status": failure.status,
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="ledger.withdrawal_returned_by_bank",
            target_type="BalanceReturnFailure",
            target_id=str(failure.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BalanceReturnFailed" if due_back else "InvestorWithdrawalReturned",
            aggregate_type="BalanceReturnFailure",
            aggregate_id=str(failure.id),
            payload=event_metadata,
            idempotency_key=f"balance-return-failure:{failure.id}:recorded",
        )
    )
    if (
        reason in INVESTOR_ACCOUNT_REASONS
        and failed_instruction is not None
        and failed_instruction.status == InvestorPayoutInstructionStatus.ACTIVE
    ):
        # Never again to the same invalid data: the account leaves the investor's choices.
        ledger.revoke_investor_payout_instruction(
            ledger.RevokeInvestorPayoutInstructionCommand(
                actor=command.actor,
                instruction_id=str(failed_instruction.id),
                reason=f"The bank returned a transfer: {reason.label}.",
            )
        )
    if not due_back:
        _notify_withdrawal_back(failure)
        return failure
    _notify_return_failed(failure, today=business_date(recorded_at), first=True)
    _admin_ops().ensure_related_admin_task(
        actor=command.actor,
        task_type="return_failed",
        related_object_type=RETURN_FAILURE_TASK_TYPE,
        related_object_id=str(failure.id),
        title=(
            f"Return failed: {format_amount_minor(amount_minor, currency.code)} for "
            f"{_investor_label(investor_id)}"
        ),
        priority="urgent",
        notes=(
            f"The bank sent back the {'return' if failure.is_forced else 'withdrawal'} to "
            f"{masked_iban(failure.failed_destination_iban)}. Reason: {reason.label}"
            + (f" ({failure.bank_reason_text})" if failure.bank_reason_text else "")
            + ".\n\nContact the investor and follow the case. Send again only to a corrected "
            "or newly verified account (Send again in Failed returns). The platform does not "
            "retry by itself."
        ),
    )
    _escalate_if_due(failure, actor=command.actor, as_of=recorded_at, scheduler=scheduler)
    return failure


# --- Notices -------------------------------------------------------------------------------


def _notify_return_failed(failure: BalanceReturnFailure, *, today: date, first: bool) -> None:
    """Email and in-app notice at once, then every day while the failure is open (Q02)."""
    amount = notice_amount(failure.amount_minor, failure.currency)
    reason = INVESTOR_REASON_TEXT.get(
        BalanceReturnFailureReason(failure.reason_code),
        INVESTOR_REASON_TEXT[BalanceReturnFailureReason.OTHER],
    )
    bank_side = failure.reason_code in BANK_SIDE_REASONS
    action = (
        "Our team will contact you and send the money again as soon as possible."
        if bank_side
        else "Add a bank account in your name and wait for its verification, or correct the "
        "account details with support. We send the money again only to a verified account."
    )
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(failure.investor_user_id),
            topic=RETURN_FAILED_TOPIC,
            idempotency_key=f"balance-return-failure:{failure.id}:notice:{today.isoformat()}",
            subject=(
                f"Return failed: {amount} is back on your balance"
                if first
                else f"Reminder: the return of {amount} failed"
            ),
            headline="Your bank sent the money back",
            body_text=(
                f"We sent {amount} to your bank account "
                f"({masked_iban(failure.failed_destination_iban)}), but the bank sent it back. "
                f"{reason}\n\nThe money is on your {brand()} balance again. It keeps its "
                "original dates: it can only be withdrawn or returned, not invested. There is "
                f"no penalty.\n\n{action}"
            ),
            template_key="ledger.return_failed.v1",
            notice_label="Balance notice",
            status_label="Return failed",
            status_tone="warning",
            data_rows=(
                ("Amount", amount),
                ("Account", masked_iban(failure.failed_destination_iban)),
                ("Sent back on", notice_date(failure.returned_value_date)),
            ),
            navigation_target="balances",
            action_label="Open balances",
            metadata={
                "balance_return_failure_id": str(failure.id),
                "currency": str(failure.currency_id),
                "amount_minor": int(failure.amount_minor),
                "reason_code": failure.reason_code,
                "category": "late",
            },
        )
    )


def _notify_withdrawal_back(failure: BalanceReturnFailure) -> None:
    """A voluntary withdrawal that came back while the money was not due back."""
    amount = notice_amount(failure.amount_minor, failure.currency)
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(failure.investor_user_id),
            topic=RETURN_FAILED_TOPIC,
            idempotency_key=f"balance-return-failure:{failure.id}:withdrawal-back",
            subject=f"Withdrawal sent back: {amount} is on your balance again",
            headline="Your bank sent the withdrawal back",
            body_text=(
                f"We sent {amount} to your bank account "
                f"({masked_iban(failure.failed_destination_iban)}), but the bank sent it back. "
                f"{INVESTOR_REASON_TEXT.get(BalanceReturnFailureReason(failure.reason_code))}"
                f"\n\nThe money is on your {brand()} balance again, with its original dates. "
                "Check your bank account details before you withdraw again."
            ),
            template_key="ledger.withdrawal_returned.v1",
            notice_label="Balance notice",
            status_label="Sent back",
            status_tone="warning",
            data_rows=(
                ("Amount", amount),
                ("Account", masked_iban(failure.failed_destination_iban)),
            ),
            navigation_target="balances",
            action_label="Open balances",
            metadata={
                "balance_return_failure_id": str(failure.id),
                "currency": str(failure.currency_id),
                "amount_minor": int(failure.amount_minor),
            },
        )
    )


# --- Daily processing, escalation and resolution ---------------------------------------------


def _failure_lots(failure: BalanceReturnFailure) -> list[InvestorBalanceLot]:
    return list(InvestorBalanceLot.objects.filter(id__in=[str(i) for i in failure.lot_ids]))


def _escalate_if_due(
    failure: BalanceReturnFailure,
    *,
    actor: Model,
    as_of: datetime,
    scheduler: BalanceScheduler,
) -> bool:
    """Compliance after N calendar days, at once when the money is at day 57 or later."""
    if failure.escalated_at is not None:
        return False
    today = business_date(as_of)
    lots = _failure_lots(failure)
    oldest_day = max((scheduler.schedule(lot).holding_day(today) for lot in lots), default=0)
    waited = (today - business_date(failure.recorded_at)).days
    after_days = return_failure_compliance_after_days()
    if oldest_day >= RETURN_FAILURE_COMPLIANCE_HOLDING_DAY:
        reason = f"The money is at day {oldest_day} (60-day limit)."
    elif waited >= after_days:
        reason = f"The failure is open for {waited} days."
    else:
        return False
    amount = format_amount_minor(failure.amount_minor, str(failure.currency_id))
    raise_compliance_alert(
        actor=actor,
        related_object_type=RETURN_FAILURE_TASK_TYPE,
        related_object_id=str(failure.id),
        title=f"Failed return for compliance: {amount}",
        notes=(
            f"The return of {amount} to {masked_iban(failure.failed_destination_iban)} failed "
            f"on {failure.returned_value_date.isoformat()} ({failure.get_reason_code_display()}). "
            f"{reason} Compliance takes the case: the money may not stay longer than 60 days."
        ),
        data_rows=[
            ["Investor", str(failure.investor_user_id)],
            ["Amount", amount],
            ["Holding day", str(oldest_day)],
            ["Reason", failure.get_reason_code_display()],
        ],
        metadata={"balance_return_failure_id": str(failure.id), "holding_day": oldest_day},
    )
    failure.escalated_at = now_utc()
    failure.escalation_reason = reason
    failure.save(update_fields=["escalated_at", "escalation_reason", "updated_at"])
    return True


def _close_failure(
    failure: BalanceReturnFailure,
    *,
    actor: Model,
    resolution: str,
    note: str,
    resend: InvestorWithdrawalRequest | None = None,
) -> BalanceReturnFailure:
    failure.status = BalanceReturnFailureStatus.RESOLVED
    failure.resolved_at = now_utc()
    failure.resolved_by_admin_id = actor.pk
    failure.resolution = resolution
    failure.resolution_note = note
    failure.resend_withdrawal_request = resend
    failure.save(
        update_fields=[
            "status",
            "resolved_at",
            "resolved_by_admin_id",
            "resolution",
            "resolution_note",
            "resend_withdrawal_request",
            "updated_at",
        ]
    )
    metadata = {
        "investor_user_id": str(failure.investor_user_id),
        "resolution": resolution,
        "note": note,
        "resend_withdrawal_request_id": str(resend.id) if resend else "",
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="ledger.balance_return_failure_resolved",
            target_type="BalanceReturnFailure",
            target_id=str(failure.id),
            metadata=metadata,
        )
    )
    _admin_ops().resolve_related_admin_task(
        actor=actor,
        related_object_type=RETURN_FAILURE_TASK_TYPE,
        related_object_id=str(failure.id),
        completion_note=note or str(BalanceReturnFailureResolution(resolution).label),
        task_type="return_failed",
    )
    return failure


def process_open_failures(
    *, actor: Model, as_of: datetime, currency: Currency | None
) -> dict[str, list[str]]:
    """Daily: close failures whose money is gone, notify the investor, escalate (Q02)."""
    queryset = BalanceReturnFailure.objects.select_for_update().filter(
        status=BalanceReturnFailureStatus.OPEN
    )
    if currency is not None:
        queryset = queryset.filter(currency=currency)
    today = business_date(as_of)
    scheduler = BalanceScheduler()
    notified: list[str] = []
    escalated: list[str] = []
    resolved: list[str] = []
    for failure in queryset.select_related("currency").order_by("recorded_at", "id"):
        lots = _failure_lots(failure)
        if not any(
            lot.available_amount_minor > 0 and lot.status == BalanceLotStatus.AVAILABLE
            for lot in lots
        ):
            _close_failure(
                failure,
                actor=actor,
                resolution=BalanceReturnFailureResolution.NO_MONEY_LEFT,
                note="No money of this failed return is left on the balance.",
            )
            resolved.append(str(failure.id))
            continue
        if failure.last_notice_date is None or failure.last_notice_date < today:
            _notify_return_failed(failure, today=today, first=False)
            failure.last_notice_date = today
            failure.save(update_fields=["last_notice_date", "updated_at"])
            notified.append(str(failure.id))
        if _escalate_if_due(failure, actor=actor, as_of=as_of, scheduler=scheduler):
            escalated.append(f"{RETURN_FAILURE_TASK_TYPE}:{failure.id}")
    return {"notified": notified, "escalated": escalated, "resolved": resolved}


@dataclass(frozen=True, slots=True)
class ResendFailedReturnCommand:
    actor: Model
    failure_id: str
    payout_instruction_id: str
    note: str = ""
    # Audit S3-8: to send again to the same account after a bank-side failure, the admin
    # records that the cause is cleared (who confirmed it and how, in ``note``).
    cause_cleared: bool = False


@transaction.atomic
def resend_failed_return(command: ResendFailedReturnCommand) -> InvestorWithdrawalRequest:
    """Send a failed return again, only to a corrected or newly verified account (Q02)."""
    ledger._require_admin_actor(command.actor)
    failure = (
        BalanceReturnFailure.objects.select_for_update()
        .select_related("currency")
        .filter(id=command.failure_id)
        .first()
    )
    if failure is None:
        raise ledger.LedgerValidationError("Failed return does not exist.")
    if failure.status != BalanceReturnFailureStatus.OPEN:
        raise ledger.LedgerConflictError(
            "This failed return is already resolved.", code="return_failure_not_open"
        )
    instruction = (
        InvestorPayoutInstruction.objects.select_for_update()
        .filter(
            id=command.payout_instruction_id,
            investor_user_id=failure.investor_user_id,
            currency=failure.currency,
            status=InvestorPayoutInstructionStatus.ACTIVE,
            is_verified_usable=True,
        )
        .first()
    )
    if instruction is None:
        raise ledger.LedgerValidationError(
            "Choose a verified bank account of this investor in the same currency."
        )
    same_account = instruction.destination_iban == failure.failed_destination_iban
    reverified = (
        instruction.verified_at is not None and instruction.verified_at > failure.recorded_at
    )
    note = command.note.strip()
    cause_cleared = False
    if same_account and not reverified:
        if failure.reason_code not in BANK_SIDE_REASONS:
            raise ledger.LedgerConflictError(
                "The bank returned the money from this account. Send again only to a corrected "
                "or newly verified account.",
                code="return_failure_same_account",
            )
        # A bank restriction or a technical error can still be there: never again to the same
        # data on a guess.
        if not command.cause_cleared or not note:
            raise ledger.LedgerConflictError(
                "The bank returned the money from this account. To send again to the same "
                "account, confirm that the cause is cleared and write in the note who "
                "confirmed it. Otherwise use another verified account.",
                code="return_failure_cause_not_cleared",
            )
        cause_cleared = True
    lots = [
        lot
        for lot in InvestorBalanceLot.objects.select_for_update().filter(
            id__in=[str(i) for i in failure.lot_ids],
            status=BalanceLotStatus.AVAILABLE,
            available_amount_minor__gt=0,
        )
    ]
    if not lots:
        raise ledger.LedgerConflictError(
            "No money of this failed return is left on the balance.",
            code="return_failure_no_money_left",
        )
    destination_selection = {
        "rule": "resend_after_failed_return",
        "payout_instruction_id": str(instruction.id),
        "destination_iban": instruction.destination_iban,
        "reason": note or "Sent again after a failed return.",
        **({"same_account_cause_cleared": True} if cause_cleared else {}),
    }
    withdrawal_request = ledger._create_forced_withdrawal_request(
        actor=command.actor,
        investor_user_id=str(failure.investor_user_id),
        currency=failure.currency,
        amount_minor=sum(lot.available_amount_minor for lot in lots),
        payout_instruction=instruction,
        destination_selection=destination_selection,
        lot_ids=[str(lot.id) for lot in lots],
        as_of=now_utc(),
        scheduler=BalanceScheduler(),
        extra_metadata={"resent_after_failure_id": str(failure.id)},
        key_suffix=f":resend:{failure.id}",
    )
    if cause_cleared:
        record_audit_event(
            AuditCommand(
                actor=actor_ref_for_user(command.actor),
                action="ledger.balance_return_failure_cause_cleared",
                target_type="BalanceReturnFailure",
                target_id=str(failure.id),
                metadata={
                    "reason_code": str(failure.reason_code),
                    "payout_instruction_id": str(instruction.id),
                    "note": note,
                    "resend_withdrawal_request_id": str(withdrawal_request.id),
                },
            )
        )
    _close_failure(
        failure,
        actor=command.actor,
        resolution=BalanceReturnFailureResolution.SENT_AGAIN,
        note=note or f"Sent again to {masked_iban(instruction.destination_iban)}.",
        resend=withdrawal_request,
    )
    investor_notices.notify_forced_return_created(withdrawal_request)
    return withdrawal_request


def reopen_failure_after_cancelled_resend(
    *, actor: Model, withdrawal_request: InvestorWithdrawalRequest
) -> BalanceReturnFailure | None:
    """Audit S3-3: a cancelled "send again" puts the money back, so its failed return is open
    again. Without this the scan would send the money by itself to the default account."""
    failure_id = str(dict(withdrawal_request.metadata or {}).get("resent_after_failure_id") or "")
    if not failure_id:
        return None
    failure = (
        BalanceReturnFailure.objects.select_for_update()
        .select_related("currency")
        .filter(id=failure_id, resend_withdrawal_request=withdrawal_request)
        .first()
    )
    if failure is None or failure.status == BalanceReturnFailureStatus.OPEN:
        return failure
    failure.status = BalanceReturnFailureStatus.OPEN
    failure.resolved_at = None
    failure.resolved_by_admin_id = None
    failure.resolution = ""
    failure.resolution_note = ""
    failure.resend_withdrawal_request = None
    failure.save(
        update_fields=[
            "status",
            "resolved_at",
            "resolved_by_admin_id",
            "resolution",
            "resolution_note",
            "resend_withdrawal_request",
            "updated_at",
        ]
    )
    amount = format_amount_minor(failure.amount_minor, str(failure.currency_id))
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="ledger.balance_return_failure_reopened",
            target_type="BalanceReturnFailure",
            target_id=str(failure.id),
            metadata={
                "investor_user_id": str(failure.investor_user_id),
                "cancelled_withdrawal_request_id": str(withdrawal_request.id),
            },
        )
    )
    _admin_ops().ensure_related_admin_task(
        actor=actor,
        task_type="return_failed",
        related_object_type=RETURN_FAILURE_TASK_TYPE,
        related_object_id=str(failure.id),
        title=f"Return failed: {amount} for {_investor_label(str(failure.investor_user_id))}",
        priority="urgent",
        notes=(
            "The transfer that sent this failed return again was cancelled before it was made. "
            "The money is on the balance again and the failed return is open. Send it again "
            "only to a corrected or newly verified account. The platform does not retry by "
            "itself."
        ),
        reopen_closed=True,
    )
    return failure


@dataclass(frozen=True, slots=True)
class ResolveReturnFailureCommand:
    actor: Model
    failure_id: str
    note: str


@transaction.atomic
def resolve_return_failure(command: ResolveReturnFailureCommand) -> BalanceReturnFailure:
    """Close a failed return with a note, only when none of its money is on the balance.

    Audit S3-2: a note records no payment. While money of the failed return is on the balance
    the case stays open (and the scan sends nothing by itself); it closes when the money leaves
    through a recorded withdrawal or is sent again. A resolution outside the platform (for
    example a court deposit) needs its own journaled service; a note cannot stand for it.
    """
    ledger._require_admin_actor(command.actor)
    note = ledger._clean_required(command.note, "Note")
    failure = BalanceReturnFailure.objects.select_for_update().filter(id=command.failure_id).first()
    if failure is None:
        raise ledger.LedgerValidationError("Failed return does not exist.")
    if failure.status != BalanceReturnFailureStatus.OPEN:
        raise ledger.LedgerConflictError(
            "This failed return is already resolved.", code="return_failure_not_open"
        )
    if any(
        lot.available_amount_minor > 0 and lot.status == BalanceLotStatus.AVAILABLE
        for lot in _failure_lots(failure)
    ):
        raise ledger.LedgerConflictError(
            "The money of this failed return is still on the balance, so a note cannot close "
            "the case. Send it again to a verified account. The case closes by itself when no "
            "money of it is left on the balance.",
            code="return_failure_money_on_balance",
        )
    return _close_failure(
        failure, actor=command.actor, resolution=BalanceReturnFailureResolution.OTHER, note=note
    )


def list_return_failures(*, status: str = "", limit: int = 100) -> list[BalanceReturnFailure]:
    queryset = BalanceReturnFailure.objects.select_related(
        "currency", "withdrawal_request", "resend_withdrawal_request"
    )
    if status:
        queryset = queryset.filter(status=status)
    return list(queryset.order_by("-recorded_at", "-id")[: max(1, min(limit, 500))])


# --- Q02.5: verify a return account from the deposit -----------------------------------------


@dataclass(frozen=True, slots=True)
class VerifyPayoutAccountFromDepositCommand:
    actor: Model
    deposit_bank_operation_id: str
    holder_matches_identity: bool
    not_intermediary_account: bool
    evidence_reference: str
    notes: str = ""


@dataclass(frozen=True, slots=True)
class IdentityReference:
    """Audit S3-6: the name an admin compares the paying account's holder with.

    ``verified_name`` is the legal name on the identity document, from the approved Didit
    decision. The registration name is typed by the investor; it is shown for information and
    is never the reference.
    """

    verified_name: str
    registration_name: str
    kyc_case_id: str = ""
    provider: str = ""
    provider_session_id: str = ""
    provider_verification_id: str = ""
    decision_at: str = ""

    def as_evidence(self) -> dict[str, str]:
        return {
            "verified_identity_name": self.verified_name,
            "identity_name_source": "identity_check" if self.verified_name else "",
            "registration_name": self.registration_name,
            "kyc_case_id": self.kyc_case_id,
            "kyc_provider": self.provider,
            "kyc_provider_session_id": self.provider_session_id,
            "kyc_provider_verification_id": self.provider_verification_id,
            "kyc_decision_at": self.decision_at,
        }


def identity_reference(investor: Model) -> IdentityReference:
    """The investor's name from the approved identity check, with the provider references."""
    registration_name = str(getattr(investor, "full_name", "") or "").strip()
    case = (
        apps.get_model("kyc_compliance", "KycVerificationCase")
        .objects.filter(user_id=investor.pk, status="approved")
        .exclude(verified_full_name="")
        .order_by("-decision_at", "-created_at")
        .first()
    )
    if case is None:
        return IdentityReference(verified_name="", registration_name=registration_name)
    return IdentityReference(
        verified_name=str(case.verified_full_name),
        registration_name=registration_name,
        kyc_case_id=str(case.pk),
        provider="didit",
        provider_session_id=str(case.provider_session_id or ""),
        provider_verification_id=str(case.provider_verification_id or ""),
        decision_at=case.decision_at.isoformat() if case.decision_at else "",
    )


NO_VERIFIED_NAME_MESSAGE = (
    "This investor has no name from an approved identity check, so a deposit cannot prove the "
    "account. Verify the account with a bank statement or bank confirmation."
)


@transaction.atomic
def verify_payout_account_from_deposit(
    command: VerifyPayoutAccountFromDepositCommand,
) -> InvestorPayoutInstruction:
    """Q02.5: the account that sent a deposit becomes a verified return account, with evidence.

    The admin compares the holder and IBAN of the incoming transfer (the bank's data) with the
    investor's verified identity. A collecting or intermediary account, a holder that differs or
    is unclear, needs a bank statement or bank confirmation first; this action is not for it.
    """
    ledger._require_admin_actor(command.actor)
    if not command.holder_matches_identity:
        raise ledger.LedgerValidationError(
            "Confirm that the holder of the incoming transfer matches the investor's verified "
            "identity. If it does not, ask for a bank statement or bank confirmation first."
        )
    if not command.not_intermediary_account:
        raise ledger.LedgerValidationError(
            "Confirm that the transfer did not come through a collecting or intermediary "
            "account. If it did, ask for a bank statement or bank confirmation first."
        )
    evidence_reference = ledger._clean_required(command.evidence_reference, "Evidence reference")
    deposit = (
        BankOperation.objects.select_related("currency")
        .filter(
            id=command.deposit_bank_operation_id,
            operation_type=BankOperationType.LENDER_DEPOSIT,
            linked_object_type="investor",
        )
        .first()
    )
    if deposit is None:
        raise ledger.LedgerValidationError("Choose an investor deposit.")
    if deposit.status == BankOperationStatus.RETURNED:
        raise ledger.LedgerValidationError("This deposit was sent back; it proves no account.")
    try:
        source_iban = ledger._clean_iban(str(deposit.payer_account_identifier or ""))
    except ledger.LedgerValidationError as exc:
        raise ledger.LedgerValidationError(
            "The deposit has no valid IBAN of the paying account."
        ) from exc
    investor = ledger._lender_account_for_id(str(deposit.linked_object_id))
    existing = InvestorPayoutInstruction.objects.filter(
        investor_user_id=investor.pk,
        currency=deposit.currency,
        destination_iban=source_iban,
        status=InvestorPayoutInstructionStatus.ACTIVE,
        is_verified_usable=True,
    ).first()
    if existing is not None:
        raise ledger.LedgerConflictError(
            "This account is already a verified bank account of the investor.",
            code="payout_iban_already_verified",
        )
    if ledger._payout_iban_other_investor_ids(
        destination_iban=source_iban, investor_user_id=str(investor.pk)
    ):
        raise ledger.LedgerConflictError(
            "This IBAN is a verified bank account of another investor. Check who owns it.",
            code=ledger.PAYOUT_IBAN_OWNERSHIP_CONFLICT_CODE,
        )
    identity = identity_reference(investor)
    if not identity.verified_name:
        # The registration name is typed by the investor; it is not identity evidence.
        raise ledger.LedgerValidationError(NO_VERIFIED_NAME_MESSAGE)
    identity_name = identity.verified_name
    evidence = {
        "method": "deposit",
        "deposit_bank_operation_id": str(deposit.id),
        "deposit_value_date": deposit.value_date.isoformat(),
        "payer_name": str(deposit.payer_name or ""),
        "payer_iban": source_iban,
        **identity.as_evidence(),
        "holder_matches_identity": True,
        "not_intermediary_account": True,
        "evidence_reference": evidence_reference,
        "notes": command.notes.strip(),
        "verified_by_admin_id": str(command.actor.pk),
        "verified_at": now_utc().isoformat(),
    }
    try:
        instruction = ledger._create_investor_payout_instruction(
            actor=command.actor,
            investor=investor,
            currency=deposit.currency,
            destination_iban=source_iban,
            destination_account_name=str(deposit.payer_name or "").strip() or identity_name,
            is_verified_usable=True,
            notes="Verified from an incoming deposit (holder and IBAN checked).",
            metadata={"source": "deposit_verification", "verification": evidence},
        )
    except IntegrityError as exc:
        raise ledger.LedgerConflictError(
            "This account changed at the same time. Reload and try again.",
            code="payout_iban_conflict",
        ) from exc
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="ledger.payout_account_verified_from_deposit",
            target_type="InvestorPayoutInstruction",
            target_id=str(instruction.id),
            metadata={"investor_user_id": str(investor.pk), **evidence},
        )
    )
    ledger._resolve_payout_instruction_verification_task(
        actor=command.actor,
        instruction=instruction,
        completion_note="The IBAN was verified from an incoming deposit.",
    )
    return instruction


def deposit_verification_candidates(investor_user_id: str) -> list[dict[str, Any]]:
    """Deposits of an investor whose paying account is not a verified bank account yet."""
    verified = set(
        InvestorPayoutInstruction.objects.filter(
            investor_user_id=investor_user_id,
            status=InvestorPayoutInstructionStatus.ACTIVE,
            is_verified_usable=True,
        ).values_list("currency_id", "destination_iban")
    )
    rows: list[dict[str, Any]] = []
    for deposit in (
        BankOperation.objects.filter(
            operation_type=BankOperationType.LENDER_DEPOSIT,
            linked_object_type="investor",
            linked_object_id=str(investor_user_id),
        )
        .exclude(status=BankOperationStatus.RETURNED)
        .order_by("-value_date", "-id")[:50]
    ):
        iban = str(deposit.payer_account_identifier or "").replace(" ", "").upper()
        if not iban or (deposit.currency_id, iban) in verified:
            continue
        rows.append(
            {
                "id": str(deposit.id),
                "currency": str(deposit.currency_id),
                "amount_minor": int(deposit.amount_minor),
                "value_date": deposit.value_date,
                "payer_name": str(deposit.payer_name or ""),
                "payer_iban": iban,
            }
        )
    return rows
