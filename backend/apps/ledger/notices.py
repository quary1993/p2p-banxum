"""Investor notices for balance events: deposits, withdrawals, forced returns, penalty mode
and payout IBANs (plan 14). Each function is called at the end of the successful ledger
service path, inside its transaction, and creates at most one notice per business event.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.conf import settings

from backend.apps.ledger.models import (
    BankOperation,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorPayoutInstructionStatus,
    InvestorWithdrawalRequest,
)
from backend.apps.platform_core.domain.funding import balance_deadline_date
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.services.investor_notices import (
    InvestorNotice,
    brand,
    enqueue_investor_notice,
    masked_iban,
    notice_amount,
    notice_date,
)

BALANCE_TARGET = "balances"


def _penalty_text() -> str:
    bps = int(settings.BALANCE_PENALTY_BPS_PER_DAY)
    if bps <= 0:
        return ""
    return f"{(Decimal(bps) / Decimal(100)).normalize():f}% per day"


def notify_deposit_credited(
    *, bank_operation: BankOperation, balance_lot: InvestorBalanceLot
) -> None:
    currency = bank_operation.currency
    amount = notice_amount(bank_operation.amount_minor, currency)
    deadline = notice_date(balance_deadline_date(balance_lot.withdrawal_deadline_at))
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(bank_operation.linked_object_id),
            topic="email.deposit_reconciled",
            idempotency_key=f"deposit-credited:{bank_operation.id}",
            subject=f"Deposit credited: {amount}",
            headline="Your deposit is on your balance",
            body_text=(
                f"We credited {amount} to your {brand()} balance. "
                f"Value date: {notice_date(bank_operation.value_date)}.\n\n"
                "You can invest this money or withdraw it. It can stay on your balance for "
                f"60 days, until {deadline}."
            ),
            template_key="ledger.deposit_credited.v1",
            notice_label="Balance notice",
            status_label="Credited",
            status_tone="confirmation",
            data_rows=(
                ("Amount", amount),
                ("Value date", notice_date(bank_operation.value_date)),
                ("Payment reference", bank_operation.payment_reference.strip()),
                ("Hold limit (60 days)", deadline),
            ),
            navigation_target=BALANCE_TARGET,
            action_label="Open balances",
            metadata={
                "bank_operation_id": str(bank_operation.id),
                "balance_lot_id": str(balance_lot.id),
                "currency": str(currency.code),
                "amount_minor": int(bank_operation.amount_minor),
                "value_date": bank_operation.value_date.isoformat(),
            },
        )
    )


def _withdrawal_metadata(request: InvestorWithdrawalRequest, event: str) -> dict[str, Any]:
    return {
        "withdrawal_request_id": str(request.id),
        "withdrawal_event": event,
        "is_forced": bool(request.is_forced),
        "currency": str(request.currency_id),
        "amount_minor": int(request.amount_minor),
    }


def notify_withdrawal_requested(request: InvestorWithdrawalRequest) -> None:
    amount = notice_amount(request.amount_minor, request.currency)
    destination = masked_iban(request.destination_iban)
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(request.investor_user_id),
            topic="email.withdrawal_status",
            idempotency_key=f"withdrawal:{request.id}:requested",
            subject=f"Withdrawal requested: {amount}",
            headline="We received your withdrawal request",
            body_text=(
                f"We received your request to withdraw {amount} to your bank account "
                f"({destination}). We reserved this amount on your balance.\n\n"
                "We send the money after operational processing and tell you when it is sent."
            ),
            template_key="ledger.withdrawal_requested.v1",
            notice_label="Balance notice",
            status_label="Requested",
            status_tone="info",
            data_rows=(
                ("Amount", amount),
                ("To", destination),
                ("Requested on", notice_date(request.requested_at)),
            ),
            navigation_target=BALANCE_TARGET,
            action_label="Open balances",
            metadata=_withdrawal_metadata(request, "requested"),
        )
    )


def notify_forced_return_created(request: InvestorWithdrawalRequest) -> None:
    amount = notice_amount(request.amount_minor, request.currency)
    destination = masked_iban(request.destination_iban)
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(request.investor_user_id),
            topic="email.balance_forced_return",
            idempotency_key=f"withdrawal:{request.id}:forced-return",
            subject=f"We are returning {amount} to your bank account",
            headline="Your balance passed the 60-day limit",
            body_text=(
                f"{amount} of your {brand()} balance passed the 60-day holding limit. "
                f"{settings.LEGAL_OPERATOR_NAME} must return it, so we started a return to "
                f"your verified bank account ({destination}).\n\n"
                "You cannot invest or exchange this amount now. We tell you when the money is "
                "sent."
            ),
            template_key="ledger.forced_return_created.v1",
            notice_label="Balance notice",
            status_label="Action taken",
            status_tone="warning",
            data_rows=(
                ("Amount", amount),
                ("To", destination),
                ("Started on", notice_date(request.requested_at)),
            ),
            navigation_target=BALANCE_TARGET,
            action_label="Open balances",
            metadata=_withdrawal_metadata(request, "forced_return_created"),
        )
    )


def notify_withdrawal_finalized(request: InvestorWithdrawalRequest) -> None:
    amount = notice_amount(request.amount_minor, request.currency)
    destination = masked_iban(request.destination_iban)
    value_date = request.bank_operation.value_date if request.bank_operation else None
    what = "The return of your overdue balance" if request.is_forced else "Your withdrawal"
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(request.investor_user_id),
            topic="email.withdrawal_status",
            idempotency_key=f"withdrawal:{request.id}:finalized",
            subject=f"Withdrawal sent: {amount}",
            headline="We sent your money",
            body_text=(
                f"{what} is complete. We sent {amount} to your bank account ({destination})."
                + (f" Value date: {notice_date(value_date)}." if value_date else "")
            ),
            template_key="ledger.withdrawal_finalized.v1",
            notice_label="Balance notice",
            status_label="Sent",
            status_tone="confirmation",
            data_rows=(
                ("Amount", amount),
                ("To", destination),
                ("Value date", notice_date(value_date) if value_date else ""),
            ),
            navigation_target=BALANCE_TARGET,
            action_label="Open balances",
            metadata=_withdrawal_metadata(request, "finalized"),
        )
    )


def notify_withdrawal_cancelled(request: InvestorWithdrawalRequest) -> None:
    amount = notice_amount(request.amount_minor, request.currency)
    cancelled_on = notice_date(request.cancelled_at) if request.cancelled_at else ""
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(request.investor_user_id),
            topic="email.withdrawal_status",
            idempotency_key=f"withdrawal:{request.id}:cancelled",
            subject=f"Withdrawal cancelled: {amount}",
            headline="Your withdrawal was cancelled",
            body_text=(
                f"Your withdrawal of {amount} was cancelled. We did not send the money. "
                f"The amount is back on your {brand()} balance.\n\n"
                "Contact support if you did not expect this."
            ),
            template_key="ledger.withdrawal_cancelled.v1",
            notice_label="Balance notice",
            status_label="Cancelled",
            status_tone="warning",
            data_rows=(("Amount", amount), ("Cancelled on", cancelled_on)),
            navigation_target=BALANCE_TARGET,
            action_label="Open balances",
            metadata=_withdrawal_metadata(request, "cancelled"),
        )
    )


def notify_penalty_mode_entered(*, transitions: Iterable[Any], as_of: datetime) -> None:
    """One notice per investor and currency when balance sources enter penalty mode.

    Daily penalty charges do not create notices; the investor sees them on the balance page.
    """
    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for transition in transitions:
        grouped[(str(transition.investor_user_id), str(transition.currency))].append(transition)
    penalty = _penalty_text()
    operator = settings.LEGAL_OPERATOR_NAME
    for (investor_user_id, currency_code), rows in grouped.items():
        amount = notice_amount(sum(int(row.amount_minor) for row in rows), currency_code)
        penalty_sentence = (
            f" A penalty of {penalty} of this amount applies until it is returned."
            if penalty
            else ""
        )
        enqueue_investor_notice(
            InvestorNotice(
                investor_user_id=investor_user_id,
                topic="email.balance_penalty_mode",
                idempotency_key=(
                    f"penalty-mode:{investor_user_id}:{currency_code}:{notice_date(as_of)}"
                ),
                subject="Action needed: add a usable IBAN",
                headline="Financial actions are frozen",
                body_text=(
                    f"{amount} of your balance passed the 60-day holding limit. {operator} "
                    "has no usable IBAN to return it to you, so this amount is now in penalty "
                    f"mode.{penalty_sentence}\n\n"
                    "Financial actions on your account are frozen. Add a usable IBAN in your "
                    "name so we can return the money. You can still see your portfolio, "
                    "documents, tax statements, notices and messages."
                ),
                template_key="ledger.balance_penalty_mode.v1",
                notice_label="Balance notice",
                status_label="Action needed",
                status_tone="danger",
                data_rows=(
                    ("Amount in penalty mode", amount),
                    ("Penalty", penalty),
                    ("Since", notice_date(as_of)),
                ),
                navigation_target=BALANCE_TARGET,
                action_label="Add a payout IBAN",
                metadata={
                    "currency": currency_code,
                    "amount_minor": sum(int(row.amount_minor) for row in rows),
                    "balance_lot_ids": [str(row.lot_id) for row in rows],
                    "as_of": as_of.isoformat(),
                },
            )
        )


PAYOUT_ACCOUNT_TOPIC = "email.payout_account_status"


def _payout_notice_sequence(instruction: InvestorPayoutInstruction, event: str) -> int | None:
    """Position of this IBAN event among the IBAN's notices, or None for a repeat.

    The key does not use timestamps: under a frozen QA clock every event of one day has
    the same time, so a re-added or re-verified IBAN lost its notice. A notice for the
    same event as the IBAN's last notice is a repeated call for one change, not a new one.
    """
    previous = OutboxMessage.objects.filter(
        topic=PAYOUT_ACCOUNT_TOPIC,
        payload__metadata__payout_instruction_id=str(instruction.id),
    )
    last = previous.order_by("-created_at", "-id").values_list("payload", flat=True).first()
    if last is not None and dict(last).get("metadata", {}).get("payout_event") == event:
        return None
    return previous.count()


def _payout_notice(
    instruction: InvestorPayoutInstruction,
    *,
    event: str,
    subject: str,
    headline: str,
    body_text: str,
    status_label: str,
    status_tone: str,
) -> None:
    sequence = _payout_notice_sequence(instruction, event)
    if sequence is None:
        return
    destination = masked_iban(instruction.destination_iban)
    data_rows: tuple[tuple[str, str], ...] = (
        ("Bank account", destination),
        ("Currency", str(instruction.currency_id)),
    )
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(instruction.investor_user_id),
            topic=PAYOUT_ACCOUNT_TOPIC,
            idempotency_key=f"payout-instruction:{instruction.id}:{event}:{sequence}",
            subject=subject,
            headline=headline,
            body_text=body_text,
            template_key=f"ledger.payout_iban_{event}.v1",
            notice_label="Account notice",
            status_label=status_label,
            status_tone=status_tone,
            data_rows=data_rows,
            navigation_target=BALANCE_TARGET,
            action_label="Open payout IBANs",
            metadata={
                "payout_instruction_id": str(instruction.id),
                "payout_event": event,
                "currency": str(instruction.currency_id),
            },
        )
    )


def notify_payout_instruction_saved(
    instruction: InvestorPayoutInstruction,
    *,
    created: bool,
    previously_verified: bool,
) -> None:
    """Notice for a new IBAN, a newly verified IBAN, or an IBAN that is no longer usable."""
    destination = masked_iban(instruction.destination_iban)
    usable = (
        bool(instruction.is_verified_usable)
        and instruction.status == InvestorPayoutInstructionStatus.ACTIVE
    )
    currency = str(instruction.currency_id)
    if usable and not previously_verified:
        _payout_notice(
            instruction,
            event="verified",
            subject="Payout IBAN verified",
            headline="Your payout IBAN is verified",
            body_text=(
                f"Your bank account ({destination}) is verified for {currency}. You can use it "
                "for withdrawals. We also use it if we must return money to you."
            ),
            status_label="Verified",
            status_tone="confirmation",
        )
    elif previously_verified and not usable:
        _payout_notice(
            instruction,
            event="revoked",
            subject="Payout IBAN no longer usable",
            headline="Your payout IBAN is no longer usable",
            body_text=(
                f"Your bank account ({destination}) can no longer be used for {currency} "
                "withdrawals. Add another IBAN in your name or contact support."
            ),
            status_label="Not usable",
            status_tone="warning",
        )
    elif created and not usable:
        _payout_notice(
            instruction,
            event="added",
            subject="Payout IBAN added",
            headline="We received your payout IBAN",
            body_text=(
                f"We added your bank account ({destination}) for {currency}. "
                f"{settings.LEGAL_OPERATOR_NAME} must verify it before you can use it for "
                "withdrawals. We tell you when it is verified."
            ),
            status_label="In review",
            status_tone="info",
        )


def notify_payout_instruction_rejected(instruction: InvestorPayoutInstruction) -> None:
    """An admin rejected the investor's IBAN request. The admin's reason stays internal."""
    destination = masked_iban(instruction.destination_iban)
    _payout_notice(
        instruction,
        event="rejected",
        subject="Payout IBAN not verified",
        headline="We could not verify your payout IBAN",
        body_text=(
            f"We could not verify your bank account ({destination}) for "
            f"{instruction.currency_id}. You cannot use it for withdrawals. Add another IBAN "
            "in your name or contact support."
        ),
        status_label="Not verified",
        status_tone="warning",
    )


def notify_payout_instruction_revoked(
    instruction: InvestorPayoutInstruction, *, stopped_withdrawals: int
) -> None:
    """An admin revoked a verified IBAN; open withdrawals to it are stopped for review.

    The admin's reason stays internal, like other admin reasons (plan 14).
    """
    destination = masked_iban(instruction.destination_iban)
    stopped = (
        " Open withdrawals to this account are stopped for review."
        if stopped_withdrawals
        else ""
    )
    _payout_notice(
        instruction,
        event="revoked",
        subject="Payout IBAN no longer usable",
        headline="Your payout IBAN is no longer usable",
        body_text=(
            f"Your bank account ({destination}) can no longer be used for "
            f"{instruction.currency_id} withdrawals.{stopped} Add another IBAN in your name "
            "or contact support."
        ),
        status_label="Not usable",
        status_tone="warning",
    )
