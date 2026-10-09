"""Read-only ledger projections from dated financial evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from django.apps import apps
from django.db.models import CharField, F, Q
from django.db.models.functions import Cast, Coalesce

from backend.apps.ledger.models import (
    BalanceLotStatus,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorPayoutInstructionStatus,
    InvestorWithdrawalRequest,
    InvestorWithdrawalRequestStatus,
    LedgerJournalEntry,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import Currency, DomainEvent
from backend.apps.platform_core.selectors.settings import get_collection_account


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


PAYOUT_INSTRUCTION_LIST_MAX_LIMIT = 200
PAYOUT_INSTRUCTION_STATES = ("pending", "verified", "revoked", "rejected")


def payout_instruction_state(instruction: InvestorPayoutInstruction) -> str:
    """pending, verified, revoked (was verified) or rejected (never verified)."""
    if instruction.status == InvestorPayoutInstructionStatus.ACTIVE:
        return "verified" if instruction.is_verified_usable else "pending"
    revocation = cast(dict[str, Any], instruction.metadata).get("revocation") or {}
    return "rejected" if revocation.get("action") == "rejected" else "revoked"


def _payout_instruction_origin(instruction: InvestorPayoutInstruction) -> str:
    metadata = cast(dict[str, Any], instruction.metadata)
    if metadata.get("submitted_by") == "investor_self_service" or str(
        instruction.created_by_admin_id
    ) == str(instruction.investor_user_id):
        return "investor_request"
    if metadata.get("source") == "lender_deposit" or metadata.get("deposit_bank_operation_id"):
        return "lender_deposit"
    return "admin"


def _payout_instruction_rows(instructions: list[InvestorPayoutInstruction]) -> list[dict[str, Any]]:
    user_model = apps.get_model("accounts_auth", "User")
    users = {
        str(user.pk): user
        for user in user_model.objects.filter(
            id__in={instruction.investor_user_id for instruction in instructions}
        )
    }
    ibans = {instruction.destination_iban for instruction in instructions}
    verified_owners: dict[str, set[str]] = {}
    for iban, owner_id in InvestorPayoutInstruction.objects.filter(
        destination_iban__in=ibans,
        status=InvestorPayoutInstructionStatus.ACTIVE,
        is_verified_usable=True,
    ).values_list("destination_iban", "investor_user_id"):
        verified_owners.setdefault(str(iban), set()).add(str(owner_id))
    open_withdrawals: dict[tuple[str, str, str], int] = {}
    for row in InvestorWithdrawalRequest.objects.filter(
        destination_iban__in=ibans,
        status=InvestorWithdrawalRequestStatus.REQUESTED,
    ).values("investor_user_id", "currency_id", "destination_iban"):
        key = (str(row["investor_user_id"]), str(row["currency_id"]), str(row["destination_iban"]))
        open_withdrawals[key] = open_withdrawals.get(key, 0) + 1
    rows: list[dict[str, Any]] = []
    for instruction in instructions:
        investor_id = str(instruction.investor_user_id)
        user = users.get(investor_id)
        metadata = cast(dict[str, Any], instruction.metadata)
        verification = metadata.get("verification") or {}
        revocation = metadata.get("revocation") or {}
        rows.append(
            {
                "id": instruction.id,
                "investor_user_id": instruction.investor_user_id,
                "investor_name": str(getattr(user, "full_name", "") or ""),
                "investor_email": str(getattr(user, "email", "") or ""),
                "investor_reference": str(getattr(user, "investor_reference", "") or ""),
                "currency": instruction.currency_id,
                "destination_iban": instruction.destination_iban,
                "destination_account_name": instruction.destination_account_name,
                "state": payout_instruction_state(instruction),
                "origin": _payout_instruction_origin(instruction),
                "verified_at": instruction.verified_at,
                "verified_by_admin_id": instruction.verified_by_admin_id,
                "evidence_reference": str(verification.get("evidence_reference", "")),
                "other_investor_count": len(
                    verified_owners.get(instruction.destination_iban, set()) - {investor_id}
                ),
                "open_withdrawal_count": open_withdrawals.get(
                    (investor_id, str(instruction.currency_id), instruction.destination_iban),
                    0,
                ),
                "revocation_reason": str(revocation.get("reason", "")),
                "revoked_at": revocation.get("revoked_at") or None,
                "created_at": instruction.created_at,
                "updated_at": instruction.updated_at,
            }
        )
    return rows


def list_admin_payout_instructions(
    *,
    state: str = "",
    investor_user_id: str = "",
    currency: str = "",
    query: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Payout IBANs for the admin console: pending requests first, then newest."""
    queryset = InvestorPayoutInstruction.objects.all()
    if state == "pending":
        queryset = queryset.filter(
            status=InvestorPayoutInstructionStatus.ACTIVE,
            is_verified_usable=False,
        )
    elif state == "verified":
        queryset = queryset.filter(
            status=InvestorPayoutInstructionStatus.ACTIVE,
            is_verified_usable=True,
        )
    elif state == "rejected":
        queryset = queryset.filter(
            status=InvestorPayoutInstructionStatus.DISABLED,
            metadata__revocation__action="rejected",
        )
    elif state == "revoked":
        queryset = queryset.filter(status=InvestorPayoutInstructionStatus.DISABLED).exclude(
            metadata__revocation__action="rejected"
        )
    if investor_user_id:
        queryset = queryset.filter(investor_user_id=investor_user_id)
    if currency:
        queryset = queryset.filter(currency_id=currency.strip().upper())
    cleaned_query = query.strip()
    if cleaned_query:
        user_model = apps.get_model("accounts_auth", "User")
        matching_users = user_model.objects.filter(
            Q(email__icontains=cleaned_query)
            | Q(full_name__icontains=cleaned_query)
            | Q(investor_reference__icontains=cleaned_query)
        ).values_list("id", flat=True)[:200]
        compact_query = cleaned_query.replace(" ", "").upper()
        queryset = queryset.filter(
            Q(investor_user_id__in=list(matching_users))
            | Q(destination_iban__icontains=compact_query)
            | Q(destination_account_name__icontains=cleaned_query)
        )
    limit = max(1, min(limit, PAYOUT_INSTRUCTION_LIST_MAX_LIMIT))
    offset = max(0, offset)
    count = queryset.count()
    page = list(
        queryset.order_by("-updated_at", "-created_at", "-id")[offset : offset + limit]
    )
    rows = _payout_instruction_rows(page)
    return {"count": count, "limit": limit, "offset": offset, "results": rows}


def admin_payout_instruction_detail(instruction_id: str) -> dict[str, Any] | None:
    instruction = InvestorPayoutInstruction.objects.filter(id=instruction_id).first()
    if instruction is None:
        return None
    return _payout_instruction_rows([instruction])[0]


def list_collection_accounts() -> list[dict[str, str]]:
    """Configured collection account of each enabled currency (one per currency)."""
    accounts: list[dict[str, str]] = []
    for code in Currency.objects.filter(is_enabled=True).order_by("code").values_list(
        "code", flat=True
    ):
        account = get_collection_account(str(code))
        accounts.append({"currency": str(code), **account})
    return accounts
