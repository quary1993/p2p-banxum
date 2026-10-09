"""Read-only ledger projections from dated financial evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.apps import apps
from django.db.models import CharField, F, Q
from django.db.models.functions import Cast, Coalesce

from backend.apps.ledger.models import (
    BalanceLotStatus,
    InvestorBalanceLot,
    InvestorWithdrawalRequest,
    InvestorWithdrawalRequestStatus,
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


CLOSED_WITHDRAWAL_STATUSES = (
    InvestorWithdrawalRequestStatus.FINALIZED,
    InvestorWithdrawalRequestStatus.CANCELLED,
)
WITHDRAWAL_HISTORY_MAX_LIMIT = 200


def list_closed_investor_withdrawals(
    *,
    status: str = "",
    currency: str = "",
    is_forced: bool | None = None,
    query: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Finalized and cancelled withdrawals, newest close first, for the admin history."""
    statuses: list[str] = [str(value) for value in CLOSED_WITHDRAWAL_STATUSES]
    if status in statuses:
        statuses = [status]
    queryset = InvestorWithdrawalRequest.objects.filter(status__in=statuses)
    if currency:
        queryset = queryset.filter(currency_id=currency.strip().upper())
    if is_forced is not None:
        queryset = queryset.filter(is_forced=is_forced)
    user_model = apps.get_model("accounts_auth", "User")
    cleaned_query = query.strip()
    if cleaned_query:
        matching_users = user_model.objects.filter(
            Q(email__icontains=cleaned_query)
            | Q(full_name__icontains=cleaned_query)
            | Q(investor_reference__icontains=cleaned_query)
        ).values_list("id", flat=True)[:200]
        compact_query = cleaned_query.replace(" ", "")
        queryset = queryset.annotate(id_text=Cast("id", output_field=CharField())).filter(
            Q(id_text__icontains=cleaned_query)
            | Q(investor_user_id__in=list(matching_users))
            | Q(destination_iban__icontains=compact_query)
            | Q(destination_account_name__icontains=cleaned_query)
            | Q(bank_reference__icontains=cleaned_query)
            | Q(payment_reference__icontains=cleaned_query)
        )
    limit = max(1, min(limit, WITHDRAWAL_HISTORY_MAX_LIMIT))
    offset = max(0, offset)
    count = queryset.count()
    page = list(
        queryset.annotate(closed_at=Coalesce("finalized_at", "cancelled_at")).order_by(
            F("closed_at").desc(nulls_last=True), "-requested_at", "-id"
        )[offset : offset + limit]
    )
    users = {
        str(user.pk): user
        for user in user_model.objects.filter(
            id__in={withdrawal.investor_user_id for withdrawal in page}
        )
    }
    results = []
    for withdrawal in page:
        user = users.get(str(withdrawal.investor_user_id))
        results.append(
            {
                "id": withdrawal.id,
                "investor_user_id": withdrawal.investor_user_id,
                "investor_name": str(getattr(user, "full_name", "") or ""),
                "investor_email": str(getattr(user, "email", "") or ""),
                "investor_reference": str(getattr(user, "investor_reference", "") or ""),
                "status": withdrawal.status,
                "is_forced": withdrawal.is_forced,
                "amount_minor": withdrawal.amount_minor,
                "currency": withdrawal.currency_id,
                "destination_iban": withdrawal.destination_iban,
                "destination_account_name": withdrawal.destination_account_name,
                "requested_at": withdrawal.requested_at,
                "closed_at": getattr(withdrawal, "closed_at", None),
                "finalized_at": withdrawal.finalized_at,
                "cancelled_at": withdrawal.cancelled_at,
                "bank_reference": withdrawal.bank_reference,
                "payment_reference": withdrawal.payment_reference,
                "cancellation_reason": withdrawal.cancellation_reason,
            }
        )
    return {"count": count, "limit": limit, "offset": offset, "results": results}
