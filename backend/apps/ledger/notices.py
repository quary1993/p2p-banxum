"""Investor notices for balance events: deposits, withdrawals, forced returns and payout
IBANs (plan 14; penalty mode was removed by U33-DEC-04). Each function is called at the end
of the successful ledger service path, inside its transaction, and creates at most one
notice per business event.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.conf import settings

from backend.apps.ledger.models import (
    BankOperation,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorPayoutInstructionStatus,
    InvestorWithdrawalRequest,
)
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.selectors.settings import platform_switch_enabled
from backend.apps.platform_core.services.balance_schedule import BalanceScheduler
from backend.apps.platform_core.services.investor_notices import (
    InvestorNotice,
    brand,
    enqueue_investor_notice,
    masked_iban,
    notice_amount,
    notice_date,
)

BALANCE_TARGET = "balances"


def _invest_or_exchange() -> str:
    """Texts offer currency exchange only while it is switched on (fx.enabled, 2026-10-16)."""
    return "invest or exchange" if platform_switch_enabled("fx.enabled") else "invest"


def notify_deposit_credited(
    *, bank_operation: BankOperation, balance_lot: InvestorBalanceLot
) -> None:
    currency = bank_operation.currency
    amount = notice_amount(bank_operation.amount_minor, currency)
    schedule = BalanceScheduler().schedule(balance_lot)
    last_day = schedule.last_day
    return_date = notice_date(schedule.return_date)
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
                "You can invest this money or withdraw it. Money that is not invested goes "
                f"back to your bank: it can stay until {notice_date(last_day)} (day "
                f"{schedule.holding_day(last_day)} after the value date), and we start the "
                f"return of what is left on {return_date}."
            ),
            template_key="ledger.deposit_credited.v1",
            notice_label="Balance notice",
            status_label="Credited",
            status_tone="confirmation",
            data_rows=(
                ("Amount", amount),
                ("Value date", notice_date(bank_operation.value_date)),
                ("Payment reference", bank_operation.payment_reference.strip()),
                ("Goes back to your bank on", return_date),
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


def _return_timing_date(request: InvestorWithdrawalRequest, key: str) -> str:
    timing = dict(request.metadata or {}).get("return_timing")
    value = timing.get(key) if isinstance(timing, dict) else None
    if not isinstance(value, str) or not value:
        return ""
    try:
        return notice_date(date.fromisoformat(value[:10]))
    except ValueError:
        return ""


def notify_forced_return_created(request: InvestorWithdrawalRequest) -> None:
    """Q01: confirmation when the return is requested (a second one follows the transfer)."""
    amount = notice_amount(request.amount_minor, request.currency)
    destination = masked_iban(request.destination_iban)
    send_on = _return_timing_date(request, "order_day") or notice_date(request.requested_at)
    resent = bool(dict(request.metadata or {}).get("resent_after_failure_id"))
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(request.investor_user_id),
            topic="email.balance_forced_return",
            idempotency_key=f"withdrawal:{request.id}:forced-return",
            subject=f"We are returning {amount} to your bank account",
            headline="Your money goes back to your bank",
            body_text=(
                (
                    f"We are sending the {amount} that your bank returned again, now to your "
                    f"verified bank account ({destination})."
                    if resent
                    else f"{amount} of your {brand()} balance was not invested in time. Money "
                    "that is not invested goes back to your bank, so we started a return to "
                    f"your verified bank account ({destination})."
                )
                + f"\n\nOur team sends the transfer by hand on {send_on}. You cannot "
                f"{_invest_or_exchange()} this amount now. We tell you when the transfer is made."
            ),
            template_key="ledger.forced_return_created.v3",
            notice_label="Balance notice",
            status_label="Action taken",
            status_tone="warning",
            data_rows=(
                ("Amount", amount),
                ("To", destination),
                # Audit S3-5: at this stage the transfer is planned, not made. "Transfer sent
                # on" is only in the notice after the transfer (notify_withdrawal_finalized).
                ("Planned transfer date", send_on),
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
    what = "The return of your money not invested" if request.is_forced else "Your withdrawal"
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
                + (
                    "\n\nThis confirms that we made the transfer. Your bank credits it on its "
                    "own schedule."
                    if request.is_forced
                    else ""
                )
            ),
            template_key="ledger.withdrawal_finalized.v1",
            notice_label="Balance notice",
            status_label="Sent",
            status_tone="confirmation",
            data_rows=(
                ("Amount", amount),
                ("To", destination),
                (
                    "Transfer sent on" if request.is_forced else "Value date",
                    notice_date(value_date) if value_date else "",
                ),
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


def notify_default_return_account_changed(instruction: InvestorPayoutInstruction) -> None:
    """U33-DEC-05: the investor chose another default return account (change notification).

    One notice per change: the key counts the earlier changes in the same currency, so
    switching back to an account the investor used before is announced again.
    """
    currency = str(instruction.currency_id)
    destination = masked_iban(instruction.destination_iban)
    sequence = OutboxMessage.objects.filter(
        topic=PAYOUT_ACCOUNT_TOPIC,
        payload__metadata__payout_event="default_changed",
        payload__metadata__investor_user_id=str(instruction.investor_user_id),
        payload__metadata__currency=currency,
    ).count()
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(instruction.investor_user_id),
            topic=PAYOUT_ACCOUNT_TOPIC,
            idempotency_key=(
                f"payout-default:{instruction.investor_user_id}:{currency}:{sequence}"
            ),
            subject="Default return account changed",
            headline="Your default return account has changed",
            body_text=(
                f"When we send {currency} back to your bank, we now use your bank account "
                f"({destination}). If you did not make this change, contact support at once."
            ),
            template_key="ledger.payout_iban_default_changed.v1",
            notice_label="Account notice",
            status_label="Changed",
            status_tone="info",
            data_rows=(("Bank account", destination), ("Currency", currency)),
            navigation_target=BALANCE_TARGET,
            action_label="Open payout IBANs",
            metadata={
                "payout_instruction_id": str(instruction.id),
                "payout_event": "default_changed",
                "investor_user_id": str(instruction.investor_user_id),
                "currency": currency,
            },
        )
    )
