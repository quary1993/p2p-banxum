"""Read-only ledger projections from dated financial evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.apps.ledger.models import (
    BalanceLotStatus,
    InvestorBalanceLot,
    InvestorWithdrawalRequest,
    LedgerJournalEntry,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import DomainEvent


def balance_lot_amounts_as_of(
    *,
    lots: list[InvestorBalanceLot],
    as_of: datetime,
) -> dict[str, dict[str, Any]]:
    """Replay consumption, releases and penalties without reading mutable balances."""
    amounts: dict[str, dict[str, Any]] = {
        str(lot.pk): {
            "available_amount_minor": lot.original_amount_minor,
            "invested_amount_minor": 0,
            "converted_amount_minor": 0,
            "withdrawn_amount_minor": 0,
            "penalized_amount_minor": 0,
            "status": BalanceLotStatus.AVAILABLE,
        }
        for lot in lots
    }
    if not amounts:
        return amounts

    def apply(allocations: list[dict[str, Any]], field: str, sign: int = 1) -> None:
        for allocation in allocations:
            state = amounts.get(str(allocation["lot_id"]))
            if state is not None:
                value = sign * int(allocation["amount_minor"])
                state[field] += value
                state["available_amount_minor"] -= value

    allocation_events = {
        "primary_investment_balance_reserved": ("lot_allocations", "invested_amount_minor", 1),
        "primary_investment_balance_released": ("lot_allocations", "invested_amount_minor", -1),
        "originator_claim_purchase_settled": (
            "investor_lot_allocations",
            "invested_amount_minor",
            1,
        ),
        "secondary_market_purchase_settled": (
            "buyer_lot_allocations",
            "invested_amount_minor",
            1,
        ),
        "investor_fx_source_balance_converted": (
            "source_lot_allocations",
            "converted_amount_minor",
            1,
        ),
    }
    investors = {lot.investor_user_id for lot in lots}
    journals = LedgerJournalEntry.objects.filter(
        lender_user_id__in=investors,
        event_type__in=[*allocation_events, "balance_penalty_charged"],
        effective_at__lte=as_of,
        value_date__lte=business_date(as_of),
    ).order_by("effective_at", "created_at", "pk")
    for journal in journals.iterator():
        if journal.event_type == "balance_penalty_charged":
            apply(
                [
                    {
                        "lot_id": journal.metadata["balance_lot_id"],
                        "amount_minor": journal.gross_amount_minor,
                    },
                ],
                "penalized_amount_minor",
            )
        else:
            key, field, sign = allocation_events[journal.event_type]
            apply(journal.metadata[key], field, sign)
    for withdrawal in InvestorWithdrawalRequest.objects.filter(
        investor_user_id__in=investors,
        requested_at__lte=as_of,
    ).iterator():
        apply(withdrawal.lot_allocations, "withdrawn_amount_minor")
        if withdrawal.cancelled_at is not None and withdrawal.cancelled_at <= as_of:
            apply(withdrawal.lot_allocations, "withdrawn_amount_minor", -1)
    penalty_lots = set(
        DomainEvent.objects.filter(
            event_type="BalancePenaltyModeEnabled",
            aggregate_id__in=amounts,
            occurred_at__lte=as_of,
        ).values_list("aggregate_id", flat=True)
    )
    for lot_id, state in amounts.items():
        if any(value < 0 for key, value in state.items() if key.endswith("_minor")):
            raise ValueError(f"Balance history does not reconcile for lot {lot_id}.")
        if state["available_amount_minor"] == 0:
            state["status"] = (
                BalanceLotStatus.PENALTY_EXHAUSTED
                if state["penalized_amount_minor"]
                else BalanceLotStatus.CONSUMED
            )
        elif lot_id in penalty_lots or state["penalized_amount_minor"]:
            state["status"] = BalanceLotStatus.PENALTY_MODE
    return amounts
