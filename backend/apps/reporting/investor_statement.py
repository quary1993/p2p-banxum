"""Investor account statement built from the investor's own ledger account.

Every row comes from postings on the investor's ``investor_balance_liability`` account. The
platform books that account as a liability, so a credit is money in for the investor. The
statement turns each journal entry into one movement seen from the investor's side: money in
is positive, money out is negative. Movements are ordered by value date (a Europe/Zurich
business date); the running balance starts at the balance before the period and ends at the
ledger balance on the period end date.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from django.apps import apps
from django.db.models import Q, Sum

from backend.apps.platform_core.domain.money import format_amount_minor

INVESTOR_LIABILITY_ACCOUNT_TYPE = "investor_balance_liability"
INVESTMENT_EVENTS = frozenset(
    {"primary_investment_balance_reserved", "originator_claim_purchase_settled"}
)
REPAYMENT_EVENTS = frozenset(
    {"borrower_repayment_distributed", "originator_borrower_repayment_distributed"}
)
FX_EVENTS = frozenset(
    {"investor_fx_source_balance_converted", "investor_fx_target_balance_credited"}
)
WITHDRAWAL_EVENTS = frozenset({"investor_withdrawal_requested", "forced_withdrawal_requested"})


@dataclass(slots=True)
class StatementMovement:
    value_date: date
    booking_date: date
    movement_type: str
    description: str
    loan_title: str
    amount_minor: int
    balance_after_minor: int = 0
    principal_minor: int | None = None
    interest_minor: int | None = None
    fees_minor: int | None = None
    other_minor: int | None = None
    details: str = ""
    reference: str = ""
    journal_entry_id: str = ""


@dataclass(slots=True)
class StatementSection:
    investor_user_id: str
    currency: str
    minor_units: int
    opening_balance_minor: int
    movements: list[StatementMovement] = field(default_factory=list)

    @property
    def closing_balance_minor(self) -> int:
        return self.opening_balance_minor + sum(item.amount_minor for item in self.movements)

    @property
    def money_in_minor(self) -> int:
        return sum(item.amount_minor for item in self.movements if item.amount_minor > 0)

    @property
    def money_out_minor(self) -> int:
        return sum(item.amount_minor for item in self.movements if item.amount_minor < 0)


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def money_text(amount_minor: int, currency: str, minor_units: int) -> str:
    return format_amount_minor(amount_minor, currency, minor_units=minor_units)


def _masked_iban(value: str) -> str:
    compact = "".join(str(value or "").split())
    if len(compact) <= 8:
        return compact
    return f"{compact[:4]} ... {compact[-4:]}"


def _first_lineage_split(lineage: Any) -> dict[str, Any]:
    if not isinstance(lineage, list):
        return {}
    for item in lineage:
        if isinstance(item, dict) and "principal_minor" in item:
            return item
    return {}


def _component_totals(journal_ids: list[str]) -> dict[tuple[str, str], dict[str, int]]:
    """Principal/interest/fee split per (journal entry, investor) from the credited lots."""
    lot_model = _model("ledger", "InvestorBalanceLot")
    totals: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    lots = lot_model.objects.filter(source_journal_entry_id__in=journal_ids).only(
        "investor_user_id", "source_journal_entry_id", "lineage"
    )
    for lot in lots:
        split = _first_lineage_split(lot.lineage)
        if not split:
            continue
        bucket = totals[(str(lot.source_journal_entry_id), str(lot.investor_user_id))]
        bucket["principal"] += int(split.get("principal_minor") or 0)
        bucket["interest"] += int(split.get("interest_minor") or 0)
        bucket["interest"] += int(split.get("contractual_interest_minor") or 0)
        bucket["default_interest"] += int(split.get("default_interest_minor") or 0)
        bucket["penalty"] += int(split.get("penalty_minor") or 0)
        bucket["penalty"] += int(split.get("penalties_minor") or 0)
        bucket["other"] += int(split.get("other_costs_minor") or 0)
        bucket["fee"] += int(split.get("fee_minor") or 0)
    return totals


class _Lookups:
    """Batched source records that give each journal entry a plain description."""

    def __init__(self, entries: list[Any]) -> None:
        journal_ids = [str(entry.pk) for entry in entries]
        loan_ids = {str(entry.loan_id) for entry in entries if entry.loan_id}
        self.loans: dict[str, tuple[str, str]] = {
            str(row["id"]): (str(row["title"]), str(row["product_type"]))
            for row in _model("loans", "Loan")
            .objects.filter(id__in=loan_ids)
            .values("id", "title", "product_type")
        }
        self.components = _component_totals(journal_ids)
        purchase_model = _model("secondary_market", "SecondaryMarketPurchase")
        self.purchases: dict[str, Any] = {
            str(purchase.ledger_journal_entry_id): purchase
            for purchase in purchase_model.objects.filter(
                ledger_journal_entry_id__in=journal_ids
            ).select_related("loan")
        }
        exchange_model = _model("fx", "FxExchange")
        self.exchanges: dict[str, Any] = {}
        for exchange in exchange_model.objects.filter(
            Q(source_journal_entry_id__in=journal_ids) | Q(target_journal_entry_id__in=journal_ids)
        ).select_related("source_currency", "target_currency"):
            self.exchanges[str(exchange.source_journal_entry_id)] = exchange
            self.exchanges[str(exchange.target_journal_entry_id)] = exchange
        withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
        self.withdrawals: dict[str, Any] = {}
        for withdrawal in withdrawal_model.objects.filter(
            Q(request_journal_entry_id__in=journal_ids)
            | Q(cancellation_journal_entry_id__in=journal_ids)
        ):
            if withdrawal.request_journal_entry_id:
                self.withdrawals[str(withdrawal.request_journal_entry_id)] = withdrawal
            if withdrawal.cancellation_journal_entry_id:
                self.withdrawals[str(withdrawal.cancellation_journal_entry_id)] = withdrawal

    def loan_title(self, entry: Any) -> str:
        if not entry.loan_id:
            return ""
        return self.loans.get(str(entry.loan_id), ("", ""))[0]

    def is_originator_claim(self, entry: Any) -> bool:
        if not entry.loan_id:
            return False
        return self.loans.get(str(entry.loan_id), ("", ""))[1] == "originator_claim"


def _describe(
    *,
    entry: Any,
    investor_user_id: str,
    amount_minor: int,
    currency: str,
    minor_units: int,
    lookups: _Lookups,
    show_references: bool,
) -> StatementMovement:
    event_type = str(entry.event_type)
    loan = lookups.loan_title(entry)
    loan_label = loan or "a loan"
    movement = StatementMovement(
        value_date=entry.value_date,
        booking_date=entry.booking_date,
        movement_type="other",
        description=event_type.replace("_", " ").strip().capitalize() or "Other movement",
        loan_title=loan,
        amount_minor=amount_minor,
        journal_entry_id=str(entry.pk),
    )

    def money(value: int, code: str = currency, units: int = minor_units) -> str:
        return money_text(value, code, units)

    def apply_components() -> None:
        split = lookups.components.get((str(entry.pk), investor_user_id))
        if not split:
            return
        interest = int(split["interest"]) + int(split["default_interest"])
        other = int(split["penalty"]) + int(split["other"])
        movement.principal_minor = int(split["principal"])
        movement.interest_minor = interest
        movement.fees_minor = int(split["fee"]) or None
        movement.other_minor = other or None
        parts = [f"Principal {money(int(split['principal']))}", f"interest {money(interest)}"]
        if split["default_interest"]:
            parts.append(f"of which default interest {money(int(split['default_interest']))}")
        if other:
            parts.append(f"penalties and other {money(other)}")
        if split["fee"]:
            parts.append(f"fee {money(int(split['fee']))}")
        movement.details = ", ".join(parts) + "."

    if event_type == "lender_deposit_reconciled":
        movement.movement_type = "deposit"
        movement.description = "Deposit by bank transfer"
        if show_references and entry.bank_reference:
            movement.reference = str(entry.bank_reference)
    elif event_type == "qa_opening_balance":
        movement.movement_type = "deposit"
        movement.description = "Opening credit (test data)"
    elif event_type in INVESTMENT_EVENTS:
        movement.movement_type = "investment"
        movement.description = f"Investment in {loan_label}"
        if lookups.is_originator_claim(entry):
            movement.details = "Loan Originator claim."
    elif event_type == "primary_investment_balance_released":
        movement.movement_type = "investment_returned"
        movement.description = f"Investment returned: {loan_label}"
        movement.details = "The reserved amount came back to your balance."
    elif event_type in REPAYMENT_EVENTS:
        movement.movement_type = "repayment"
        movement.description = f"Repayment from {loan_label}"
        apply_components()
    elif event_type == "loan_recovery_distributed":
        movement.movement_type = "recovery"
        movement.description = f"Recovery payment from {loan_label}"
        apply_components()
    elif event_type == "secondary_market_purchase_settled":
        purchase = lookups.purchases.get(str(entry.pk))
        if purchase is not None:
            movement.loan_title = str(purchase.loan.title)
        title = movement.loan_title or loan_label
        if amount_minor < 0:
            movement.movement_type = "secondary_market_purchase"
            movement.description = f"Secondary market purchase: {title}"
            if purchase is not None:
                movement.interest_minor = int(purchase.accrued_interest_minor)
                movement.fees_minor = int(purchase.taker_fee_minor)
                movement.details = (
                    f"Price {money(int(purchase.transfer_price_minor))}, accrued interest "
                    f"{money(int(purchase.accrued_interest_minor))}, fee "
                    f"{money(int(purchase.taker_fee_minor))}."
                )
        else:
            movement.movement_type = "secondary_market_sale"
            movement.description = f"Secondary market sale: {title}"
            if purchase is not None:
                movement.interest_minor = int(purchase.accrued_interest_minor)
                movement.fees_minor = int(purchase.maker_fee_minor)
                movement.details = (
                    f"Price {money(int(purchase.transfer_price_minor))}, accrued interest "
                    f"{money(int(purchase.accrued_interest_minor))}, fee "
                    f"{money(int(purchase.maker_fee_minor))}."
                )
    elif event_type in FX_EVENTS:
        exchange = lookups.exchanges.get(str(entry.pk))
        movement.movement_type = "currency_exchange"
        movement.description = "Currency exchange"
        if exchange is not None:
            source = str(exchange.source_currency.code)
            target = str(exchange.target_currency.code)
            movement.description = f"Currency exchange {source} to {target}"
            source_units = int(exchange.source_currency.minor_units)
            target_units = int(exchange.target_currency.minor_units)
            movement.details = (
                f"{money(int(exchange.source_amount_minor), source, source_units)} to "
                f"{money(int(exchange.target_amount_minor), target, target_units)} at rate "
                f"{exchange.rate.normalize():f}, fee "
                f"{money(int(exchange.fee_minor), target, target_units)}."
            )
            if event_type == "investor_fx_target_balance_credited":
                movement.fees_minor = int(exchange.fee_minor)
    elif event_type in WITHDRAWAL_EVENTS:
        withdrawal = lookups.withdrawals.get(str(entry.pk))
        movement.movement_type = "withdrawal"
        forced = event_type == "forced_withdrawal_requested" or bool(
            getattr(withdrawal, "is_forced", False)
        )
        movement.description = (
            "Return of funds held over 60 days" if forced else "Withdrawal to your bank account"
        )
        if withdrawal is not None and show_references:
            movement.reference = f"IBAN {_masked_iban(str(withdrawal.destination_iban))}"
    elif event_type == "investor_withdrawal_cancelled":
        movement.movement_type = "withdrawal_cancelled"
        movement.description = "Withdrawal cancelled"
        movement.details = "The amount came back to your balance."
    elif event_type == "balance_penalty_charged":
        movement.movement_type = "penalty"
        movement.description = "Penalty on funds held over 60 days"
        movement.fees_minor = -amount_minor if amount_minor < 0 else None
        charge_date = (entry.metadata or {}).get("charge_date")
        if charge_date:
            movement.details = f"Charge for {charge_date}."
    elif "correction" in event_type or "reversal" in event_type:
        movement.movement_type = "correction"
        movement.description = "Balance correction"
    return movement


def build_investor_statement_sections(
    *,
    start_date: date,
    end_date: date,
    investor_user_id: str = "",
    currency_code: str = "",
    show_references: bool = True,
) -> list[StatementSection]:
    """One section per investor and currency with the opening balance and every movement."""
    posting_model = _model("ledger", "LedgerPosting")
    currency_model = _model("platform_core", "Currency")
    minor_units = {
        str(code): int(units)
        for code, units in currency_model.objects.values_list("code", "minor_units")
    }
    base = posting_model.objects.filter(
        account__account_type=INVESTOR_LIABILITY_ACCOUNT_TYPE,
        account__owner_type="investor",
        journal_entry__value_date__lte=end_date,
    )
    if investor_user_id:
        base = base.filter(account__owner_id=investor_user_id)
    if currency_code:
        base = base.filter(currency__code=currency_code.upper())

    sections: dict[tuple[str, str], StatementSection] = {}

    def section_for(investor: str, currency: str) -> StatementSection:
        key = (investor, currency)
        if key not in sections:
            sections[key] = StatementSection(
                investor_user_id=investor,
                currency=currency,
                minor_units=minor_units.get(currency, 2),
                opening_balance_minor=0,
            )
        return sections[key]

    opening_rows = (
        base.filter(journal_entry__value_date__lt=start_date)
        .values("account__owner_id", "currency__code")
        .annotate(
            credits=Sum("amount_minor", filter=Q(side="credit")),
            debits=Sum("amount_minor", filter=Q(side="debit")),
        )
    )
    for row in opening_rows:
        section = section_for(str(row["account__owner_id"]), str(row["currency__code"]))
        section.opening_balance_minor = int(row["credits"] or 0) - int(row["debits"] or 0)

    postings = list(
        base.filter(journal_entry__value_date__gte=start_date)
        .select_related("journal_entry", "account", "currency")
        .order_by(
            "journal_entry__value_date",
            "journal_entry__created_at",
            "journal_entry__id",
            "id",
        )
    )
    # One movement per journal entry, investor and currency, in posting order.
    grouped: dict[tuple[str, str, str], int] = {}
    entries: dict[str, Any] = {}
    for posting in postings:
        entry = posting.journal_entry
        key = (str(posting.account.owner_id), str(posting.currency.code), str(entry.pk))
        amount = int(posting.amount_minor)
        signed = amount if posting.side == "credit" else -amount
        grouped[key] = grouped.get(key, 0) + signed
        entries[str(entry.pk)] = entry
    lookups = _Lookups(list(entries.values()))
    for (investor, currency, journal_id), amount_minor in grouped.items():
        section = section_for(investor, currency)
        section.movements.append(
            _describe(
                entry=entries[journal_id],
                investor_user_id=investor,
                amount_minor=amount_minor,
                currency=currency,
                minor_units=section.minor_units,
                lookups=lookups,
                show_references=show_references,
            )
        )
    result: list[StatementSection] = []
    for section_key in sorted(sections):
        section = sections[section_key]
        if not section.movements and section.opening_balance_minor == 0:
            continue
        # Value date, then recording time. When two entries share a timestamp (a pinned QA
        # clock), money in comes first so the running balance never dips below zero.
        section.movements.sort(
            key=lambda item: (
                item.value_date,
                entries[item.journal_entry_id].created_at,
                0 if item.amount_minor >= 0 else 1,
                item.journal_entry_id,
            )
        )
        balance = section.opening_balance_minor
        for movement in section.movements:
            balance += movement.amount_minor
            movement.balance_after_minor = balance
        result.append(section)
    return result
