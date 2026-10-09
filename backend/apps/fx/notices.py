"""Investor notice for an executed currency exchange (plan 14: "Currency exchange completed")."""

from __future__ import annotations

from decimal import Decimal

from backend.apps.fx.models import FxExchange
from backend.apps.platform_core.services.investor_notices import (
    InvestorNotice,
    brand,
    enqueue_investor_notice,
    notice_amount,
    notice_date,
)


def notify_fx_exchange_completed(exchange: FxExchange) -> None:
    source = notice_amount(exchange.source_amount_minor, exchange.source_currency)
    target = notice_amount(exchange.target_amount_minor, exchange.target_currency)
    fee = notice_amount(exchange.fee_minor, exchange.target_currency)
    rate = (
        f"1 {exchange.source_currency_id} = "
        f"{Decimal(exchange.rate).quantize(Decimal('0.0001'))} {exchange.target_currency_id}"
    )
    executed_on = notice_date(exchange.executed_at)
    enqueue_investor_notice(
        InvestorNotice(
            investor_user_id=str(exchange.investor_user_id),
            topic="email.fx_exchange_confirmation",
            idempotency_key=f"fx-exchange:{exchange.id}:completed",
            subject=f"Currency exchange completed: {source} to {target}",
            headline="Your currency exchange is complete",
            body_text=(
                f"We exchanged {source} from your {brand()} balance into {target}. "
                f"Rate: {rate}. Fee: {fee}. Date: {executed_on}.\n\n"
                "The exchanged money keeps the 60-day holding limit of the money you exchanged."
            ),
            template_key="fx.exchange_completed.v1",
            notice_label="Currency exchange",
            status_label="Completed",
            status_tone="confirmation",
            data_rows=(
                ("You exchanged", source),
                ("You received", target),
                ("Rate", rate),
                ("Fee", fee),
                ("Date", executed_on),
            ),
            navigation_target="fx",
            action_label="Open currency exchange",
            metadata={
                "fx_exchange_id": str(exchange.id),
                "source_currency": str(exchange.source_currency_id),
                "target_currency": str(exchange.target_currency_id),
                "source_amount_minor": int(exchange.source_amount_minor),
                "target_amount_minor": int(exchange.target_amount_minor),
                "fee_minor": int(exchange.fee_minor),
            },
        )
    )
