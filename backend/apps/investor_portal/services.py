from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from importlib import import_module
from typing import Any

from django.apps import apps
from django.db.models import Model, Sum

from backend.apps.platform_core.domain.access import user_can_access_financial_features
from backend.apps.platform_core.domain.time import business_date, now_utc


class InvestorPortalAuthorizationError(RuntimeError):
    pass


class InvestorPortalValidationError(RuntimeError):
    pass


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _servicing_services() -> Any:
    return import_module("backend.apps.servicing.services")


def _require_financial_access(actor: Model) -> str:
    if not user_can_access_financial_features(actor):
        raise InvestorPortalAuthorizationError(
            "Investor portal financial data requires active lender access, phone verification, "
            "and approved KYC/KYB status."
        )
    return str(actor.pk)


def _bounded_limit(limit: int | None, *, default: int = 50, maximum: int = 250) -> int:
    if limit is None:
        return default
    if limit < 1:
        raise InvestorPortalValidationError("Limit must be at least 1.")
    return min(limit, maximum)


def _enabled_currencies() -> list[Any]:
    currency_model = _model("platform_core", "Currency")
    return list(currency_model.objects.filter(is_enabled=True).order_by("code"))


def _currency_code(value: Any) -> str:
    return str(getattr(value, "code", value))


def _balance_bucket(lot: Any, *, as_of: datetime) -> str:
    status = str(lot.status)
    if status == "frozen":
        return "frozen"
    if status == "penalty_mode":
        return "penalty_mode"
    if status == "penalty_exhausted":
        return "penalty_exhausted"
    if status != "available":
        return status
    if as_of > lot.withdrawal_deadline_at:
        return "overdue"
    if as_of > lot.investment_deadline_at:
        return "withdraw_only"
    return "investable"


def _days_until(value: datetime, *, as_of: datetime) -> int:
    return (business_date(value) - business_date(as_of)).days


def _lot_payload(lot: Any, *, as_of: datetime) -> dict[str, Any]:
    bucket = _balance_bucket(lot, as_of=as_of)
    return {
        "id": str(lot.pk),
        "currency": _currency_code(lot.currency),
        "source_type": str(lot.source_type),
        "status": str(lot.status),
        "bucket": bucket,
        "received_at": lot.received_at,
        "investment_deadline_at": lot.investment_deadline_at,
        "withdrawal_deadline_at": lot.withdrawal_deadline_at,
        "days_until_investment_deadline": _days_until(
            lot.investment_deadline_at,
            as_of=as_of,
        ),
        "days_until_withdrawal_deadline": _days_until(
            lot.withdrawal_deadline_at,
            as_of=as_of,
        ),
        "original_amount_minor": int(lot.original_amount_minor),
        "available_amount_minor": int(lot.available_amount_minor),
        "invested_amount_minor": int(lot.invested_amount_minor),
        "converted_amount_minor": int(lot.converted_amount_minor),
        "withdrawn_amount_minor": int(lot.withdrawn_amount_minor),
        "penalized_amount_minor": int(lot.penalized_amount_minor),
        "requires_withdrawal": bucket in {"withdraw_only", "overdue", "penalty_mode"},
        "blocks_financial_actions": bucket == "penalty_mode",
    }


def _empty_balance_summary(*, investor_user_id: str, currency: str) -> dict[str, Any]:
    return {
        "investor_user_id": investor_user_id,
        "currency": currency,
        "total_available_minor": 0,
        "investable_minor": 0,
        "withdraw_only_minor": 0,
        "overdue_minor": 0,
        "frozen_minor": 0,
        "penalty_mode_minor": 0,
        "lot_count": 0,
        "active_lot_count": 0,
        "next_investment_deadline_at": None,
        "next_withdrawal_deadline_at": None,
    }


def _balance_summaries(
    *,
    investor_user_id: str,
    as_of: datetime,
    lots: Iterable[Any],
) -> list[dict[str, Any]]:
    summaries = {
        _currency_code(currency): _empty_balance_summary(
            investor_user_id=investor_user_id,
            currency=_currency_code(currency),
        )
        for currency in _enabled_currencies()
    }
    for lot in lots:
        currency = _currency_code(lot.currency)
        summary = summaries.setdefault(
            currency,
            _empty_balance_summary(investor_user_id=investor_user_id, currency=currency),
        )
        summary["lot_count"] += 1
        available = int(lot.available_amount_minor)
        if available <= 0:
            continue
        summary["active_lot_count"] += 1
        summary["total_available_minor"] += available
        bucket = _balance_bucket(lot, as_of=as_of)
        if bucket == "investable":
            summary["investable_minor"] += available
        elif bucket == "withdraw_only":
            summary["withdraw_only_minor"] += available
        elif bucket == "overdue":
            summary["overdue_minor"] += available
        elif bucket == "frozen":
            summary["frozen_minor"] += available
        elif bucket == "penalty_mode":
            summary["penalty_mode_minor"] += available
        if bucket in {"investable", "withdraw_only", "overdue"}:
            investment_deadline = lot.investment_deadline_at
            withdrawal_deadline = lot.withdrawal_deadline_at
            current_investment_deadline = summary["next_investment_deadline_at"]
            current_withdrawal_deadline = summary["next_withdrawal_deadline_at"]
            if (
                current_investment_deadline is None
                or investment_deadline < current_investment_deadline
            ):
                summary["next_investment_deadline_at"] = investment_deadline
            if (
                current_withdrawal_deadline is None
                or withdrawal_deadline < current_withdrawal_deadline
            ):
                summary["next_withdrawal_deadline_at"] = withdrawal_deadline
    return [summaries[key] for key in sorted(summaries)]


def get_investor_balances(*, actor: Model, as_of: datetime | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    as_of_value = as_of or now_utc()
    lot_model = _model("ledger", "InvestorBalanceLot")
    payout_model = _model("ledger", "InvestorPayoutInstruction")
    lots = list(
        lot_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency")
        .order_by("received_at", "created_at", "id")
    )
    visible_lots = [
        _lot_payload(lot, as_of=as_of_value)
        for lot in lots
        if int(lot.available_amount_minor) > 0
    ]
    payout_instructions = [
        {
            "id": str(instruction.pk),
            "currency": _currency_code(instruction.currency),
            "status": str(instruction.status),
            "destination_iban": str(instruction.destination_iban),
            "destination_account_name": str(instruction.destination_account_name),
            "is_verified_usable": bool(instruction.is_verified_usable),
            "verified_at": instruction.verified_at,
            "created_at": instruction.created_at,
        }
        for instruction in payout_model.objects.filter(
            investor_user_id=investor_user_id,
            status="active",
        )
        .select_related("currency")
        .order_by("currency", "-created_at")
    ]
    penalty_mode_minor = sum(item["penalty_mode_minor"] for item in _balance_summaries(
        investor_user_id=investor_user_id,
        as_of=as_of_value,
        lots=lots,
    ))
    return {
        "as_of": as_of_value,
        "summaries": _balance_summaries(
            investor_user_id=investor_user_id,
            as_of=as_of_value,
            lots=lots,
        ),
        "lots": visible_lots,
        "payout_instructions": payout_instructions,
        "has_penalty_mode_balance": penalty_mode_minor > 0,
    }


def _loan_days_past_due(loan: Any, *, as_of: datetime) -> int:
    snapshot = _servicing_services().get_loan_servicing_status_snapshot(
        loan=loan,
        as_of_date=business_date(as_of),
    )
    return int(snapshot.days_past_due)


def _loan_projection(loan: Any, *, as_of: datetime) -> dict[str, Any]:
    borrower = loan.borrower
    return {
        "loan_id": str(loan.pk),
        "loan_title": str(loan.title),
        "loan_status": str(loan.status),
        "borrower_id": str(borrower.pk),
        "borrower_name": str(borrower.legal_name),
        "borrower_country": str(getattr(borrower, "country", "")),
        "purpose": str(loan.purpose),
        "collateral_type": str(loan.collateral_type),
        "risk_rating": str(loan.risk_rating),
        "interest_rate_bps": int(loan.interest_rate_bps),
        "term_months": int(loan.term_months),
        "repayment_type": str(loan.repayment_type),
        "currency": _currency_code(loan.currency),
        "principal_minor": int(loan.principal_minor),
        "funding_deadline": loan.funding_deadline,
        "first_payment_date": loan.first_payment_date,
        "ltv_bps": getattr(loan, "ltv_bps", None),
        "days_past_due": _loan_days_past_due(loan, as_of=as_of),
    }


def _aggregate_by_holding(
    *,
    model_label: tuple[str, str],
    investor_user_id: str,
    holding_ids: list[str],
    fields: list[str],
) -> dict[str, dict[str, int]]:
    if not holding_ids:
        return {}
    model = _model(*model_label)
    annotations = {field: Sum(field) for field in fields}
    rows = (
        model.objects.filter(investor_user_id=investor_user_id, holding_id__in=holding_ids)
        .values("holding_id")
        .annotate(**annotations)
    )
    return {
        str(row["holding_id"]): {field: int(row[field] or 0) for field in fields}
        for row in rows
    }


def _latest_public_notes_by_loan(loan_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not loan_ids:
        return {}
    note_model = _model("servicing", "LoanRiskNote")
    notes: dict[str, dict[str, Any]] = {}
    for note in (
        note_model.objects.filter(loan_id__in=loan_ids, visibility="public")
        .order_by("loan_id", "-occurred_at", "-id")
    ):
        loan_id = str(note.loan_id)
        if loan_id in notes:
            continue
        notes[loan_id] = {
            "id": str(note.pk),
            "note_type": str(note.note_type),
            "title": str(note.title),
            "occurred_at": note.occurred_at,
        }
    return notes


def _currency_totals(items: Iterable[tuple[str, int]]) -> list[dict[str, Any]]:
    totals: dict[str, int] = defaultdict(int)
    for currency, amount in items:
        totals[currency] += amount
    return [
        {"currency": currency, "amount_minor": amount}
        for currency, amount in sorted(totals.items())
    ]


def _term_bucket(term_months: int) -> str:
    if term_months <= 6:
        return "0_6_months"
    if term_months <= 12:
        return "7_12_months"
    if term_months <= 24:
        return "13_24_months"
    return "25_plus_months"


def _exposure_dimension(
    holdings: list[Any],
    *,
    key_func: Any,
    label_func: Any | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for holding in holdings:
        loan = holding.loan
        key = str(key_func(holding, loan))
        label = str(label_func(holding, loan)) if label_func else key
        currency = _currency_code(holding.currency)
        grouped_key = (key, currency)
        item = grouped.setdefault(
            grouped_key,
            {
                "key": key,
                "name": label,
                "currency": currency,
                "outstanding_principal_minor": 0,
                "holding_count": 0,
            },
        )
        item["outstanding_principal_minor"] += int(holding.current_principal_minor)
        item["holding_count"] += 1
    return sorted(
        grouped.values(),
        key=lambda item: (
            str(item["currency"]),
            -int(item["outstanding_principal_minor"]),
            str(item["name"]),
        ),
    )


def get_investor_portfolio(
    *,
    actor: Model,
    include_inactive: bool = False,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    as_of_value = as_of or now_utc()
    holding_model = _model("holdings", "InvestorLoanHolding")
    holdings_query = holding_model.objects.filter(investor_user_id=investor_user_id).select_related(
        "loan",
        "loan__borrower",
        "currency",
    )
    if not include_inactive:
        holdings_query = holdings_query.filter(status="active", current_principal_minor__gt=0)
    holdings = list(holdings_query.order_by("loan__title", "created_at", "id"))
    holding_ids = [str(holding.pk) for holding in holdings]
    repayment_totals = _aggregate_by_holding(
        model_label=("servicing", "InvestorRepaymentDistributionLine"),
        investor_user_id=investor_user_id,
        holding_ids=holding_ids,
        fields=["amount_minor", "principal_minor", "interest_minor", "fee_minor"],
    )
    recovery_totals = _aggregate_by_holding(
        model_label=("servicing", "InvestorRecoveryDistributionLine"),
        investor_user_id=investor_user_id,
        holding_ids=holding_ids,
        fields=[
            "amount_minor",
            "principal_minor",
            "contractual_interest_minor",
            "default_interest_minor",
            "penalties_minor",
            "other_costs_minor",
        ],
    )
    latest_notes = _latest_public_notes_by_loan([str(holding.loan_id) for holding in holdings])
    holding_payloads: list[dict[str, Any]] = []
    for holding in holdings:
        loan = holding.loan
        repayment = repayment_totals.get(str(holding.pk), {})
        recovery = recovery_totals.get(str(holding.pk), {})
        holding_payloads.append(
            {
                "id": str(holding.pk),
                "status": str(holding.status),
                "source_type": str(holding.source_type),
                "original_principal_minor": int(holding.original_principal_minor),
                "current_principal_minor": int(holding.current_principal_minor),
                "currency": _currency_code(holding.currency),
                "loan_share_ppm": int(holding.loan_share_ppm),
                "assignment_effective_at": holding.assignment_effective_at,
                "loan": _loan_projection(loan, as_of=as_of_value),
                "received_principal_minor": int(repayment.get("principal_minor", 0)),
                "received_interest_minor": int(repayment.get("interest_minor", 0)),
                "repayment_fee_minor": int(repayment.get("fee_minor", 0)),
                "recovered_principal_minor": int(recovery.get("principal_minor", 0)),
                "recovered_contractual_interest_minor": int(
                    recovery.get("contractual_interest_minor", 0)
                ),
                "recovered_default_interest_minor": int(recovery.get("default_interest_minor", 0)),
                "recovered_penalties_minor": int(recovery.get("penalties_minor", 0)),
                "recovered_other_costs_minor": int(recovery.get("other_costs_minor", 0)),
                "latest_public_note": latest_notes.get(str(holding.loan_id)),
            }
        )
    active_holdings = [
        holding
        for holding in holdings
        if str(holding.status) == "active"
        and int(holding.current_principal_minor) > 0
    ]
    summary = {
        "holding_count": len(holding_payloads),
        "active_holding_count": len(active_holdings),
        "outstanding_principal_by_currency": _currency_totals(
            (
                _currency_code(holding.currency),
                int(holding.current_principal_minor),
            )
            for holding in active_holdings
        ),
        "original_principal_by_currency": _currency_totals(
            (
                _currency_code(holding.currency),
                int(holding.original_principal_minor),
            )
            for holding in holdings
        ),
        "realized_interest_by_currency": _currency_totals(
            (
                item["currency"],
                int(item["received_interest_minor"])
                + int(item["recovered_contractual_interest_minor"])
                + int(item["recovered_default_interest_minor"]),
            )
            for item in holding_payloads
        ),
        "late_or_defaulted_exposure_by_currency": _currency_totals(
            (
                _currency_code(holding.currency),
                int(holding.current_principal_minor),
            )
            for holding in active_holdings
            if str(holding.loan.status) in {"late", "defaulted", "written_off"}
        ),
    }
    exposure = {
        "by_borrower": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.borrower_id),
            label_func=lambda _holding, loan: str(loan.borrower.legal_name),
        ),
        "by_country": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(getattr(loan.borrower, "country", "")),
        ),
        "by_purpose": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.purpose),
        ),
        "by_risk_rating": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.risk_rating),
        ),
        "by_collateral_type": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.collateral_type),
        ),
        "by_maturity": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: _term_bucket(int(loan.term_months)),
        ),
        "by_loan_status": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.status),
        ),
    }
    return {
        "as_of": as_of_value,
        "summary": summary,
        "holdings": holding_payloads,
        "exposure": exposure,
    }


def _activity(
    *,
    activity_id: str,
    activity_type: str,
    occurred_at: datetime,
    direction: str,
    title: str,
    amount_minor: int | None = None,
    currency: str = "",
    status: str = "",
    loan_id: str | None = None,
    loan_title: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": activity_id,
        "activity_type": activity_type,
        "occurred_at": occurred_at,
        "direction": direction,
        "title": title,
        "amount_minor": amount_minor,
        "currency": currency,
        "status": status,
        "loan_id": loan_id,
        "loan_title": loan_title,
        "metadata": metadata or {},
    }


def get_investor_activity(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    entries: list[dict[str, Any]] = []
    lot_model = _model("ledger", "InvestorBalanceLot")
    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    repayment_line_model = _model("servicing", "InvestorRepaymentDistributionLine")
    recovery_line_model = _model("servicing", "InvestorRecoveryDistributionLine")
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    purchase_model = _model("secondary_market", "SecondaryMarketPurchase")
    fx_exchange_model = _model("fx", "FxExchange")
    for lot in (
        lot_model.objects.filter(
            investor_user_id=investor_user_id,
            source_type__in=[
                "deposit",
                "secondary_market_proceeds",
                "fx_proceeds",
                "refund",
                "correction",
                "penalty_reversal",
            ],
        )
        .select_related("currency")
        .order_by("-created_at")[:limit_value]
    ):
        entries.append(
            _activity(
                activity_id=str(lot.pk),
                activity_type=f"balance_{lot.source_type}",
                occurred_at=lot.received_at,
                direction="in",
                title=str(lot.source_type).replace("_", " ").title(),
                amount_minor=int(lot.original_amount_minor),
                currency=_currency_code(lot.currency),
                status=str(lot.status),
            )
        )
    for line in (
        repayment_line_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "repayment_event", "repayment_event__loan")
        .order_by("-occurred_at")[:limit_value]
    ):
        loan = line.repayment_event.loan
        entries.append(
            _activity(
                activity_id=str(line.pk),
                activity_type="repayment_distribution",
                occurred_at=line.occurred_at,
                direction="in",
                title="Loan repayment credited",
                amount_minor=int(line.amount_minor),
                currency=_currency_code(line.currency),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
                metadata={
                    "principal_minor": int(line.principal_minor),
                    "interest_minor": int(line.interest_minor),
                    "fee_minor": int(line.fee_minor),
                },
            )
        )
    for line in (
        recovery_line_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "recovery_event", "recovery_event__loan")
        .order_by("-occurred_at")[:limit_value]
    ):
        loan = line.recovery_event.loan
        entries.append(
            _activity(
                activity_id=str(line.pk),
                activity_type="recovery_distribution",
                occurred_at=line.occurred_at,
                direction="in",
                title="Recovery payment credited",
                amount_minor=int(line.amount_minor),
                currency=_currency_code(line.currency),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
                metadata={
                    "principal_minor": int(line.principal_minor),
                    "contractual_interest_minor": int(
                        line.contractual_interest_minor
                    ),
                    "default_interest_minor": int(line.default_interest_minor),
                    "penalties_minor": int(line.penalties_minor),
                    "other_costs_minor": int(line.other_costs_minor),
                },
            )
        )
    for withdrawal in (
        withdrawal_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency")
        .order_by("-requested_at")[:limit_value]
    ):
        entries.append(
            _activity(
                activity_id=str(withdrawal.pk),
                activity_type="withdrawal_request",
                occurred_at=withdrawal.requested_at,
                direction="out",
                title="Withdrawal request",
                amount_minor=int(withdrawal.amount_minor),
                currency=_currency_code(withdrawal.currency),
                status=str(withdrawal.status),
                metadata={"is_forced": bool(withdrawal.is_forced)},
            )
        )
    for order in (
        order_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-created_at")[:limit_value]
    ):
        loan = order.loan
        entries.append(
            _activity(
                activity_id=str(order.pk),
                activity_type="primary_order",
                occurred_at=order.created_at,
                direction="internal",
                title="Primary-market investment order",
                amount_minor=int(order.allocated_amount_minor)
                or int(order.requested_amount_minor),
                currency=_currency_code(order.currency),
                status=str(order.status),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for listing in (
        listing_model.objects.filter(seller_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-created_at")[:limit_value]
    ):
        loan = listing.loan
        entries.append(
            _activity(
                activity_id=str(listing.pk),
                activity_type="secondary_listing",
                occurred_at=listing.created_at,
                direction="info",
                title="Secondary-market listing",
                amount_minor=int(listing.transfer_price_minor),
                currency=_currency_code(listing.currency),
                status=str(listing.status),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for purchase in (
        purchase_model.objects.filter(buyer_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-purchased_at")[:limit_value]
    ):
        loan = purchase.loan
        entries.append(
            _activity(
                activity_id=str(purchase.pk),
                activity_type="secondary_purchase",
                occurred_at=purchase.purchased_at,
                direction="out",
                title="Secondary-market purchase",
                amount_minor=int(purchase.buyer_total_cost_minor),
                currency=_currency_code(purchase.currency),
                status="completed",
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for purchase in (
        purchase_model.objects.filter(seller_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-purchased_at")[:limit_value]
    ):
        loan = purchase.loan
        entries.append(
            _activity(
                activity_id=str(purchase.pk),
                activity_type="secondary_sale",
                occurred_at=purchase.purchased_at,
                direction="in",
                title="Secondary-market sale",
                amount_minor=int(purchase.seller_net_proceeds_minor),
                currency=_currency_code(purchase.currency),
                status="completed",
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for exchange in (
        fx_exchange_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("source_currency", "target_currency")
        .order_by("-executed_at")[:limit_value]
    ):
        entries.append(
            _activity(
                activity_id=str(exchange.pk),
                activity_type="fx_exchange",
                occurred_at=exchange.executed_at,
                direction="internal",
                title="Currency exchange",
                amount_minor=int(exchange.source_amount_minor),
                currency=_currency_code(exchange.source_currency),
                status=str(exchange.status),
                metadata={
                    "source_currency": _currency_code(exchange.source_currency),
                    "target_currency": _currency_code(exchange.target_currency),
                    "target_amount_minor": int(exchange.target_amount_minor),
                    "fee_minor": int(exchange.fee_minor),
                    "rate": str(exchange.rate),
                },
            )
        )
    entries.sort(key=lambda item: item["occurred_at"], reverse=True)
    return {"entries": entries[:limit_value]}


def get_primary_orders(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    orders = []
    for order in (
        order_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-created_at", "-id")[:limit_value]
    ):
        loan = order.loan
        orders.append(
            {
                "id": str(order.pk),
                "loan_id": str(loan.pk),
                "loan_title": str(loan.title),
                "loan_status": str(loan.status),
                "status": str(order.status),
                "requested_amount_minor": int(order.requested_amount_minor),
                "allocated_amount_minor": int(order.allocated_amount_minor),
                "currency": _currency_code(order.currency),
                "created_at": order.created_at,
                "allocated_at": order.allocated_at,
                "released_at": order.released_at,
                "closed_at": order.closed_at,
            }
        )
    return {"orders": orders}


def get_secondary_market_activity(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    purchase_model = _model("secondary_market", "SecondaryMarketPurchase")
    listings = [
        {
            "id": str(listing.pk),
            "holding_id": str(listing.holding_id),
            "loan_id": str(listing.loan_id),
            "loan_title": str(listing.loan.title),
            "status": str(listing.status),
            "publication_type": str(listing.publication_type),
            "current_principal_minor": int(listing.current_principal_minor),
            "transfer_price_minor": int(listing.transfer_price_minor),
            "discount_premium_bps": int(listing.discount_premium_bps),
            "accrued_interest_minor": int(listing.accrued_interest_minor),
            "maker_fee_minor": int(listing.maker_fee_minor),
            "seller_net_proceeds_minor": int(listing.seller_net_proceeds_minor),
            "currency": _currency_code(listing.currency),
            "loan_status_at_listing": str(listing.loan_status_at_listing),
            "risk_acknowledgement_required": bool(
                listing.risk_acknowledgement_required
            ),
            "public_disclosure_note": str(listing.public_disclosure_note),
            "listed_at": listing.listed_at,
            "created_at": listing.created_at,
        }
        for listing in (
            listing_model.objects.filter(seller_user_id=investor_user_id)
            .select_related("currency", "loan")
            .order_by("-created_at", "-id")[:limit_value]
        )
    ]
    purchases_as_buyer = [
        {
            "id": str(purchase.pk),
            "listing_id": str(purchase.listing_id),
            "loan_id": str(purchase.loan_id),
            "loan_title": str(purchase.loan.title),
            "buyer_holding_id": str(purchase.buyer_holding_id),
            "current_principal_minor": int(purchase.current_principal_minor),
            "transfer_price_minor": int(purchase.transfer_price_minor),
            "discount_premium_bps": int(purchase.discount_premium_bps),
            "accrued_interest_minor": int(purchase.accrued_interest_minor),
            "taker_fee_minor": int(purchase.taker_fee_minor),
            "buyer_total_cost_minor": int(purchase.buyer_total_cost_minor),
            "currency": _currency_code(purchase.currency),
            "loan_status_at_purchase": str(purchase.loan_status_at_purchase),
            "risk_acknowledgement_accepted": bool(
                purchase.risk_acknowledgement_accepted
            ),
            "purchased_at": purchase.purchased_at,
        }
        for purchase in (
            purchase_model.objects.filter(buyer_user_id=investor_user_id)
            .select_related("currency", "loan")
            .order_by("-purchased_at", "-id")[:limit_value]
        )
    ]
    sales_as_seller = [
        {
            "id": str(purchase.pk),
            "listing_id": str(purchase.listing_id),
            "loan_id": str(purchase.loan_id),
            "loan_title": str(purchase.loan.title),
            "seller_holding_id": str(purchase.seller_holding_id),
            "current_principal_minor": int(purchase.current_principal_minor),
            "transfer_price_minor": int(purchase.transfer_price_minor),
            "discount_premium_bps": int(purchase.discount_premium_bps),
            "accrued_interest_minor": int(purchase.accrued_interest_minor),
            "maker_fee_minor": int(purchase.maker_fee_minor),
            "seller_net_proceeds_minor": int(purchase.seller_net_proceeds_minor),
            "currency": _currency_code(purchase.currency),
            "loan_status_at_purchase": str(purchase.loan_status_at_purchase),
            "purchased_at": purchase.purchased_at,
        }
        for purchase in (
            purchase_model.objects.filter(seller_user_id=investor_user_id)
            .select_related("currency", "loan")
            .order_by("-purchased_at", "-id")[:limit_value]
        )
    ]
    return {
        "listings": listings,
        "purchases_as_buyer": purchases_as_buyer,
        "sales_as_seller": sales_as_seller,
    }


def get_fx_history(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    quote_model = _model("fx", "FxQuote")
    exchange_model = _model("fx", "FxExchange")
    quotes = [
        {
            "id": str(quote.pk),
            "source_currency": _currency_code(quote.source_currency),
            "target_currency": _currency_code(quote.target_currency),
            "source_amount_minor": int(quote.source_amount_minor),
            "rate": str(quote.rate),
            "platform_fee_bps": int(quote.platform_fee_bps),
            "gross_target_amount_minor": int(quote.gross_target_amount_minor),
            "fee_minor": int(quote.fee_minor),
            "target_amount_minor": int(quote.target_amount_minor),
            "issued_at": quote.issued_at,
            "expires_at": quote.expires_at,
            "is_expired": now_utc() > quote.expires_at,
            "has_exchange": bool(quote.exchanges.exists()),
        }
        for quote in (
            quote_model.objects.filter(investor_user_id=investor_user_id)
            .select_related("source_currency", "target_currency")
            .order_by("-issued_at", "-id")[:limit_value]
        )
    ]
    exchanges = [
        {
            "id": str(exchange.pk),
            "quote_id": str(exchange.quote_id),
            "source_currency": _currency_code(exchange.source_currency),
            "target_currency": _currency_code(exchange.target_currency),
            "source_amount_minor": int(exchange.source_amount_minor),
            "rate": str(exchange.rate),
            "platform_fee_bps": int(exchange.platform_fee_bps),
            "gross_target_amount_minor": int(exchange.gross_target_amount_minor),
            "fee_minor": int(exchange.fee_minor),
            "target_amount_minor": int(exchange.target_amount_minor),
            "status": str(exchange.status),
            "executed_at": exchange.executed_at,
        }
        for exchange in (
            exchange_model.objects.filter(investor_user_id=investor_user_id)
            .select_related("source_currency", "target_currency")
            .order_by("-executed_at", "-id")[:limit_value]
        )
    ]
    return {"quotes": quotes, "exchanges": exchanges}


def get_investor_dashboard(*, actor: Model, as_of: datetime | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    as_of_value = as_of or now_utc()
    balances = get_investor_balances(actor=actor, as_of=as_of_value)
    portfolio = get_investor_portfolio(actor=actor, include_inactive=False, as_of=as_of_value)
    activity = get_investor_activity(actor=actor, limit=10)
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    pending_primary_orders = int(
        order_model.objects.filter(
            investor_user_id=investor_user_id,
            status__in=["pending", "balance_allocated", "partially_allocated"],
        ).count()
    )
    pending_withdrawals = int(
        withdrawal_model.objects.filter(
            investor_user_id=investor_user_id,
            status="requested",
        ).count()
    )
    pending_secondary_listings = int(
        listing_model.objects.filter(
            seller_user_id=investor_user_id,
            status__in=["active", "approval_requested"],
        ).count()
    )
    pending_actions: list[dict[str, Any]] = []
    for summary in balances["summaries"]:
        if int(summary["penalty_mode_minor"]) > 0:
            pending_actions.append(
                {
                    "type": "usable_iban_required",
                    "severity": "blocking",
                    "currency": summary["currency"],
                    "amount_minor": summary["penalty_mode_minor"],
                    "message": (
                        "A usable withdrawal IBAN is required before further financial "
                        "actions can be unlocked for this overdue balance."
                    ),
                }
            )
        if int(summary["overdue_minor"]) > 0:
            pending_actions.append(
                {
                    "type": "withdrawal_required",
                    "severity": "urgent",
                    "currency": summary["currency"],
                    "amount_minor": summary["overdue_minor"],
                    "message": (
                        "This balance is past the 60-day holding limit and must be "
                        "withdrawn. Garanta cannot extend this regulatory deadline."
                    ),
                }
            )
        if int(summary["withdraw_only_minor"]) > 0:
            pending_actions.append(
                {
                    "type": "withdraw_only_balance",
                    "severity": "warning",
                    "currency": summary["currency"],
                    "amount_minor": summary["withdraw_only_minor"],
                    "message": (
                        "This balance is older than the reinvestment window and can only "
                        "be withdrawn."
                    ),
                }
            )
    if pending_primary_orders:
        pending_actions.append(
            {
                "type": "primary_orders_pending",
                "severity": "info",
                "count": pending_primary_orders,
                "message": "Primary-market orders are open or allocated.",
            }
        )
    if pending_withdrawals:
        pending_actions.append(
            {
                "type": "withdrawals_pending",
                "severity": "info",
                "count": pending_withdrawals,
                "message": "Withdrawal requests are waiting for Garanta processing.",
            }
        )
    if pending_secondary_listings:
        pending_actions.append(
            {
                "type": "secondary_listings_open",
                "severity": "info",
                "count": pending_secondary_listings,
                "message": "Secondary-market listings are active or awaiting approval.",
            }
        )
    return {
        "as_of": as_of_value,
        "investor_user_id": investor_user_id,
        "balances": balances["summaries"],
        "portfolio_summary": portfolio["summary"],
        "exposure": portfolio["exposure"],
        "pending_actions": pending_actions,
        "recent_activity": activity["entries"],
    }
