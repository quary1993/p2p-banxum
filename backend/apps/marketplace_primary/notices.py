"""Investor notices for primary-market events (plan 14: investment order confirmation,
funding status update, partial funding close or refund decision). Each function is called at
the end of the successful service path, inside its transaction.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryLoanCancellation,
    PrimaryLoanClose,
    PrimaryLoanCloseType,
)
from backend.apps.platform_core.services.investor_notices import (
    InvestorNotice,
    brand,
    enqueue_investor_notice,
    notice_amount,
    notice_date,
)


def _message_paragraph(message: str) -> str:
    text = message.strip()
    return f"\n\nMessage from {brand()}: {text}" if text else ""


def notify_order_allocated(order: PrimaryInvestmentOrder) -> None:
    """Balance reserved for a primary investment, with the amount actually allocated."""
    loan: Any = order.loan
    currency = loan.currency
    allocated = notice_amount(order.allocated_amount_minor, currency)
    requested = notice_amount(order.requested_amount_minor, currency)
    partial = int(order.allocated_amount_minor) < int(order.requested_amount_minor)
    deadline = notice_date(loan.funding_deadline) if loan.funding_deadline else ""
    partial_text = (
        f"\n\nYou asked for {requested}. Only {allocated} was still available in this loan, "
        f"so we reserved {allocated}."
        if partial
        else ""
    )
    deadline_text = f" Funding closes after {deadline}." if deadline else ""
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(order.investor_user_id),
            topic="email.primary_investment_confirmation",
            idempotency_key=f"primary-order:{order.id}:allocated",
            subject=f"Investment placed: {allocated} in {loan.title}",
            headline="Your investment is placed",
            body_text=(
                f"We reserved {allocated} from your balance for {loan.title}.{deadline_text} "
                "If the loan is funded, your investment becomes active. If it is not funded, "
                f"the money comes back to your balance.{partial_text}"
            ),
            template_key="marketplace.order_allocated.v1",
            notice_label="Investment notice",
            status_label="Partly placed" if partial else "Placed",
            status_tone="confirmation",
            data_rows=(
                ("Loan", str(loan.title)),
                ("Amount reserved", allocated),
                ("Amount requested", requested if partial else ""),
                ("Funding deadline", deadline),
                ("Placed on", notice_date(order.allocated_at) if order.allocated_at else ""),
            ),
            navigation_target="portfolio",
            action_label="Open My investments",
            metadata={
                "order_id": str(order.id),
                "loan_id": str(loan.id),
                "currency": str(currency.code),
                "requested_amount_minor": int(order.requested_amount_minor),
                "allocated_amount_minor": int(order.allocated_amount_minor),
            },
        )
    )


def notify_order_released(order: PrimaryInvestmentOrder) -> None:
    """An admin released the reserved balance of one order outside a funding resolution."""
    loan: Any = order.loan
    amount = notice_amount(order.allocated_amount_minor, loan.currency)
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(order.investor_user_id),
            topic="email.primary_order_released",
            idempotency_key=f"primary-order:{order.id}:released",
            subject=f"Investment order released: {loan.title}",
            headline="Your investment order was released",
            body_text=(
                f"We released your {amount} order for {loan.title}. You did not invest in this "
                f"loan. The amount is back on your {brand()} balance.\n\n"
                "Contact support if you have questions."
            ),
            template_key="marketplace.order_released.v1",
            notice_label="Investment notice",
            status_label="Released",
            status_tone="warning",
            data_rows=(
                ("Loan", str(loan.title)),
                ("Amount released", amount),
                ("Released on", notice_date(order.released_at) if order.released_at else ""),
            ),
            navigation_target="balances",
            action_label="Open balances",
            metadata={
                "order_id": str(order.id),
                "loan_id": str(loan.id),
                "currency": str(loan.currency_id),
                "released_amount_minor": int(order.allocated_amount_minor),
            },
        )
    )


def notify_funding_closed(close: PrimaryLoanClose) -> None:
    """Funding closed in full or in part: each investor's orders became active holdings."""
    loan: Any = close.loan
    currency = loan.currency
    order_ids = list(close.metadata.get("allocated_order_ids", []))
    by_investor: dict[str, list[PrimaryInvestmentOrder]] = defaultdict(list)
    for order in PrimaryInvestmentOrder.objects.filter(id__in=order_ids).order_by(
        "allocated_at", "id"
    ):
        by_investor[str(order.investor_user_id)].append(order)
    partial = close.close_type == PrimaryLoanCloseType.PARTIAL
    loan_amount = notice_amount(close.accepted_principal_minor, currency)
    for investor_user_id, orders in by_investor.items():
        invested_minor = sum(int(order.allocated_amount_minor) for order in orders)
        invested = notice_amount(invested_minor, currency)
        holding_ids = [
            str(order.metadata.get("holding_id", ""))
            for order in orders
            if order.metadata.get("holding_id")
        ]
        if partial:
            subject = f"Loan partly funded: {loan.title}"
            first = (
                f"{loan.title} reached its minimum funding but not its target. The loan closed "
                f"at {loan_amount}, which is the new loan amount. Your investment of {invested} "
                "is now active."
            )
        else:
            subject = f"Loan funded: {loan.title}"
            first = f"{loan.title} is funded. Your investment of {invested} is now active."
        enqueue_investor_notice(
            InvestorNotice(
                investor_user_id=investor_user_id,
                topic="email.loan_funding_status",
                idempotency_key=f"primary-close:{close.id}:{investor_user_id}",
                subject=subject,
                headline="Your investment is active",
                # The investor message explains a partial close (plan 09); the automatic
                # resolver also stores one for a full close, which adds nothing there.
                body_text=(
                    f"{first} You can follow repayments in My investments."
                    f"{_message_paragraph(close.investor_message) if partial else ''}"
                ),
                template_key=(
                    "marketplace.funding_closed_partial.v1"
                    if partial
                    else "marketplace.funding_closed.v1"
                ),
                notice_label="Investment notice",
                status_label="Partly funded" if partial else "Funded",
                status_tone="confirmation",
                data_rows=(
                    ("Loan", str(loan.title)),
                    ("Your investment", invested),
                    ("Loan amount", loan_amount),
                    ("Closed on", notice_date(close.closed_at)),
                ),
                navigation_target="holding" if holding_ids else "portfolio",
                navigation_target_id=holding_ids[0] if holding_ids else "",
                action_label="View your investment",
                metadata={
                    "primary_close_id": str(close.id),
                    "loan_id": str(loan.id),
                    "close_type": str(close.close_type),
                    "holding_ids": holding_ids,
                    "currency": str(currency.code),
                    "invested_amount_minor": invested_minor,
                    "accepted_principal_minor": int(close.accepted_principal_minor),
                },
            )
        )


def notify_funding_cancelled(cancellation: PrimaryLoanCancellation) -> None:
    """Funding cancelled: reservations went back to the investors' balances."""
    loan: Any = cancellation.loan
    currency = loan.currency
    released_ids = list(cancellation.metadata.get("released_order_ids", []))
    pending_ids = list(cancellation.metadata.get("closed_not_invested_order_ids", []))
    released_by_investor: dict[str, int] = defaultdict(int)
    for order in PrimaryInvestmentOrder.objects.filter(id__in=released_ids + pending_ids):
        released_by_investor[str(order.investor_user_id)] += (
            int(order.allocated_amount_minor) if str(order.id) in released_ids else 0
        )
    for investor_user_id, released_minor in released_by_investor.items():
        released = notice_amount(released_minor, currency)
        money_text = (
            f"We released {released} back to your {brand()} balance."
            if released_minor > 0
            else "No money was reserved for your order."
        )
        enqueue_investor_notice(
            InvestorNotice(
                investor_user_id=investor_user_id,
                topic="email.loan_funding_status",
                idempotency_key=f"primary-cancellation:{cancellation.id}:{investor_user_id}",
                subject=f"Loan funding cancelled: {loan.title}",
                headline="The loan was not made",
                body_text=(
                    f"Funding for {loan.title} was cancelled. No loan was made and you did not "
                    f"invest. {money_text}{_message_paragraph(cancellation.investor_message)}"
                ),
                template_key="marketplace.funding_cancelled.v1",
                notice_label="Investment notice",
                status_label="Cancelled",
                status_tone="warning",
                data_rows=(
                    ("Loan", str(loan.title)),
                    ("Amount released", released if released_minor > 0 else ""),
                    ("Cancelled on", notice_date(cancellation.cancelled_at)),
                ),
                navigation_target="balances",
                action_label="Open balances",
                metadata={
                    "primary_cancellation_id": str(cancellation.id),
                    "loan_id": str(loan.id),
                    "currency": str(currency.code),
                    "released_amount_minor": released_minor,
                },
            )
        )
