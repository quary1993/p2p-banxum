"""IP of Webby-Soft SRL. The Transactions page from the server (IMPLEMENTATION_PLAN 18.3).

The design's Transactions list has server filters (period, currency, type, search), pages, the
"Available after transaction" balance of each movement and an export of the whole history. The
movements are the investor's activity entries (``services._investor_activity_entries``).

Available after a movement: the balance of the investor's ``investor_balance_liability`` ledger
account in that currency just after the movement's journal entry. Reservations, withdrawals and
investments move money out of that account when they happen (to the loan escrow or the withdrawal
payable), so its balance is the money the investor can use. A movement that has no own journal
entry (for example the closing of a reserved investment, or a resale listing) shows the balance
after the last entry posted before it.
"""

from __future__ import annotations

import csv
import io
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.db.models import Sum

from backend.apps.platform_core.domain.money import csv_number_format, minor_units_to_decimal
from backend.apps.platform_core.domain.time import business_timezone

INVESTOR_LIABILITY_ACCOUNT_TYPE = "investor_balance_liability"
TRANSACTION_GROUPS = (
    "deposit",
    "reservation",
    "investment",
    "repayment",
    "recovery",
    "withdrawal",
    "return",
    "purchase",
    "sale",
    "fee",
    "fx",
    "other",
)
_BALANCE_SOURCE_GROUPS = {
    "deposit": "deposit",
    "secondary_market_proceeds": "sale",
    "fx_proceeds": "fx",
    "penalty_reversal": "fee",
}
_TYPE_GROUPS = {
    "primary_reservation": "reservation",
    "primary_reservation_released": "reservation",
    "primary_order_ended": "reservation",
    "primary_investment": "investment",
    "originator_claim_purchase": "investment",
    "repayment_distribution": "repayment",
    "interest_distribution": "repayment",
    "originator_repayment_distribution": "repayment",
    "recovery_distribution": "recovery",
    "balance_penalty_charge": "fee",
    "secondary_market_fee": "fee",
    "secondary_purchase": "purchase",
    "secondary_sale": "sale",
    "secondary_listing": "sale",
    "fx_exchange": "fx",
}
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def activity_group(entry: dict[str, Any]) -> str:
    """The filter group of an entry, as the page shows it (transactionsModel.ts)."""
    activity_type = str(entry.get("activity_type", ""))
    status = str(entry.get("status", ""))
    metadata = entry.get("metadata") or {}
    if activity_type.startswith("balance_") and activity_type != "balance_penalty_charge":
        return _BALANCE_SOURCE_GROUPS.get(activity_type.removeprefix("balance_"), "other")
    if activity_type in {"withdrawal_request", "withdrawal_cancellation"}:
        forced = isinstance(metadata, dict) and bool(metadata.get("is_forced"))
        return "return" if forced else "withdrawal"
    if activity_type == "primary_order":
        return "investment" if status == "closed_invested" else "reservation"
    return _TYPE_GROUPS.get(activity_type, "other")


@dataclass(frozen=True, slots=True)
class TransactionFilters:
    currency: str = ""
    group: str = ""
    date_from: date | None = None
    date_to: date | None = None
    search: str = ""


def _zurich_date(value: datetime) -> date:
    return value.astimezone(business_timezone()).date()


def _matches(entry: dict[str, Any], filters: TransactionFilters) -> bool:
    if filters.currency and str(entry.get("currency", "")).upper() != filters.currency.upper():
        return False
    if filters.group and activity_group(entry) != filters.group:
        return False
    occurred = entry.get("occurred_at")
    if isinstance(occurred, datetime):
        day = _zurich_date(occurred)
        if filters.date_from and day < filters.date_from:
            return False
        if filters.date_to and day > filters.date_to:
            return False
    needle = filters.search.strip().lower()
    if needle:
        metadata = entry.get("metadata") or {}
        amount = abs(int(entry.get("amount_minor") or 0))
        plain_amount = f"{amount // 100}.{amount % 100:02d}" if amount else ""
        haystack = " ".join(
            str(value)
            for value in (
                entry.get("title", ""),
                entry.get("loan_title", ""),
                entry.get("id", ""),
                activity_group(entry),
                _GROUP_LABELS.get(activity_group(entry), ""),
                metadata.get("reason", "") if isinstance(metadata, dict) else "",
                # The amount as typed in either number format, without thousands separators.
                plain_amount,
                plain_amount.replace(".", ","),
            )
        ).lower()
        if needle not in haystack:
            return False
    return True


def _journal_ids_by_entry(entries: list[dict[str, Any]]) -> dict[str, str]:
    """The journal entry of each activity entry that has one (by its source record)."""
    by_type: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        by_type[str(entry["activity_type"])].append(str(entry["id"]))
    result: dict[str, str] = {}

    def add(rows: Any, key_prefix: str = "") -> None:
        for pk, journal_id in rows:
            if journal_id:
                result[f"{key_prefix}{pk}"] = str(journal_id)

    lot_ids = [eid for kind, ids in by_type.items() if kind.startswith("balance_") for eid in ids]
    if lot_ids:
        add(
            apps.get_model("ledger", "InvestorBalanceLot")
            .objects.filter(pk__in=[i for i in lot_ids if len(i) == 36])
            .values_list("pk", "source_journal_entry_id")
        )
    for kind, model in (
        ("repayment_distribution", ("servicing", "InvestorRepaymentDistributionLine")),
        ("recovery_distribution", ("servicing", "InvestorRecoveryDistributionLine")),
        (
            "originator_repayment_distribution",
            ("originator_claims", "InvestorOriginatorRepaymentDistributionLine"),
        ),
    ):
        if by_type.get(kind):
            add(
                apps.get_model(*model)
                .objects.filter(pk__in=by_type[kind])
                .values_list("pk", "balance_lot__source_journal_entry_id")
            )
    withdrawal_model = apps.get_model("ledger", "InvestorWithdrawalRequest")
    if by_type.get("withdrawal_request"):
        add(
            withdrawal_model.objects.filter(pk__in=by_type["withdrawal_request"]).values_list(
                "pk", "request_journal_entry_id"
            )
        )
    if by_type.get("withdrawal_cancellation"):
        ids = [eid.removesuffix(":cancellation") for eid in by_type["withdrawal_cancellation"]]
        for pk, journal_id in withdrawal_model.objects.filter(pk__in=ids).values_list(
            "pk", "cancellation_journal_entry_id"
        ):
            if journal_id:
                result[f"{pk}:cancellation"] = str(journal_id)
    if by_type.get("originator_claim_purchase"):
        add(
            apps.get_model("originator_claims", "OriginatorClaimPurchase")
            .objects.filter(pk__in=by_type["originator_claim_purchase"])
            .values_list("pk", "journal_entry_id")
        )
    purchase_ids = by_type.get("secondary_purchase", []) + by_type.get("secondary_sale", [])
    if purchase_ids:
        add(
            apps.get_model("secondary_market", "SecondaryMarketPurchase")
            .objects.filter(pk__in=purchase_ids)
            .values_list("pk", "ledger_journal_entry_id")
        )
    if by_type.get("balance_penalty_charge"):
        for eid in by_type["balance_penalty_charge"]:
            result[eid] = eid
    order_entries = by_type.get("primary_reservation", []) + by_type.get(
        "primary_reservation_released", []
    )
    if order_entries:
        order_ids = {eid.split(":", 1)[0] for eid in order_entries}
        journals = {
            str(pk): (reserved, released)
            for pk, reserved, released in apps.get_model(
                "marketplace_primary", "PrimaryInvestmentOrder"
            )
            .objects.filter(pk__in=order_ids)
            .values_list("pk", "reservation_journal_entry_id", "release_journal_entry_id")
        }
        for eid in by_type.get("primary_reservation", []):
            reserved = journals.get(eid.split(":", 1)[0], (None, None))[0]
            if reserved:
                result[eid] = str(reserved)
        for eid in by_type.get("primary_reservation_released", []):
            released = journals.get(eid.split(":", 1)[0], (None, None))[1]
            if released:
                result[eid] = str(released)
    return result


def annotate_available_after(investor_user_id: str, entries: list[dict[str, Any]]) -> None:
    """Set ``available_after_minor`` on each entry with a currency (None when unknown)."""
    posting_model = apps.get_model("ledger", "LedgerPosting")
    rows = list(
        posting_model.objects.filter(
            account__account_type=INVESTOR_LIABILITY_ACCOUNT_TYPE,
            account__owner_type="investor",
            account__owner_id=investor_user_id,
        )
        .values("journal_entry_id", "currency__code", "journal_entry__created_at", "side")
        .annotate(total=Sum("amount_minor"))
        .order_by("journal_entry__created_at", "journal_entry_id")
    )
    # Running balance per currency after each journal entry (credits raise the liability).
    per_journal: dict[tuple[str, str], int] = defaultdict(int)
    order: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for row in rows:
        signed = int(row["total"] or 0) * (1 if row["side"] == "credit" else -1)
        key = (str(row["currency__code"]), str(row["journal_entry_id"]))
        if key not in per_journal:
            order[key[0]].append((row["journal_entry__created_at"], key[1]))
        per_journal[key] += signed
    balance_after: dict[tuple[str, str], int] = {}
    timeline: dict[str, tuple[list[datetime], list[int]]] = {}
    for currency, journals in order.items():
        running = 0
        times: list[datetime] = []
        balances: list[int] = []
        for created_at, journal_id in journals:
            running += per_journal[(currency, journal_id)]
            balance_after[(currency, journal_id)] = running
            times.append(created_at)
            balances.append(running)
        timeline[currency] = (times, balances)
    journal_ids = _journal_ids_by_entry(entries)
    for entry in entries:
        currency = str(entry.get("currency") or "").upper()
        value: int | None = None
        entry_journal = journal_ids.get(str(entry["id"]))
        if currency and entry_journal and (currency, entry_journal) in balance_after:
            value = balance_after[(currency, entry_journal)]
        elif currency in timeline and isinstance(entry.get("occurred_at"), datetime):
            times, balances = timeline[currency]
            index = bisect_right(times, entry["occurred_at"]) - 1
            value = balances[index] if index >= 0 else 0
        entry["available_after_minor"] = value


def _currency_rank(currency: str) -> tuple[int, str]:
    # The design lists EUR first, then the other currencies by code.
    return (0 if currency == "EUR" else 1, currency)


def _summary(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Totals of the movements in view per currency (the page's "Summary")."""
    totals: dict[str, dict[str, Any]] = {}
    for entry in entries:
        currency = str(entry.get("currency") or "")
        if not currency:
            continue
        item = totals.setdefault(
            currency,
            {
                "currency": currency,
                "deposited_minor": 0,
                "invested_minor": 0,
                "credited_minor": 0,
                "withdrawn_minor": 0,
            },
        )
        amount = abs(int(entry.get("amount_minor") or 0))
        group = activity_group(entry)
        if group == "deposit":
            item["deposited_minor"] += amount
        elif group == "investment":
            item["invested_minor"] += amount
        elif group in {"repayment", "recovery"}:
            item["credited_minor"] += amount
        elif (
            group in {"withdrawal", "return"}
            and entry.get("activity_type") == "withdrawal_request"
            and entry.get("status") == "finalized"
        ):
            item["withdrawn_minor"] += amount
    return [totals[key] for key in sorted(totals, key=_currency_rank)]


def transaction_page(
    *,
    investor_user_id: str,
    entries: list[dict[str, Any]],
    filters: TransactionFilters,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Newest first, filtered on the server, one page at a time, with the available balance."""
    annotate_available_after(investor_user_id, entries)
    matching = sorted(
        (entry for entry in entries if _matches(entry, filters)),
        key=lambda entry: (entry["occurred_at"], str(entry["id"])),
        reverse=True,
    )
    for entry in matching:
        entry["group"] = activity_group(entry)
    page_size = max(1, min(int(limit), MAX_PAGE_SIZE))
    start = max(0, int(offset))
    page = matching[start : start + page_size]
    next_offset = start + page_size if start + page_size < len(matching) else None
    currencies = sorted(
        {str(e.get("currency") or "") for e in entries if e.get("currency")}, key=_currency_rank
    )
    present = {activity_group(e) for e in entries}
    years = sorted(
        {
            _zurich_date(e["occurred_at"]).year
            for e in entries
            if isinstance(e.get("occurred_at"), datetime)
        },
        reverse=True,
    )
    return {
        "entries": page,
        "total": len(matching),
        "offset": start,
        "next_offset": next_offset,
        "currencies": currencies,
        "groups": [group for group in TRANSACTION_GROUPS if group in present],
        "years": years,
        "summary": _summary(matching),
    }


# The design's export columns (Date, Type, Description, Currency, Amount, Available balance,
# Principal, Interest, Status) and the reference of each movement.
_CSV_COLUMNS = (
    ("Date", "date"),
    ("Type", "type"),
    ("Description", "description"),
    ("Currency", "currency"),
    ("Amount", "amount"),
    ("Available balance", "available_after"),
    ("Principal", "principal"),
    ("Interest", "interest"),
    ("Status", "status"),
    ("Reference", "id"),
)
_NUMERIC_COLUMNS = {"amount", "available_after", "principal", "interest"}
_GROUP_LABELS = {
    "deposit": "Deposit",
    "reservation": "Reservation",
    "investment": "Investment",
    "repayment": "Repayment",
    "recovery": "Recovery",
    "withdrawal": "Withdrawal",
    "return": "Automatic return",
    "purchase": "Secondary purchase",
    "sale": "Secondary sale",
    "fee": "Fee or penalty",
    "fx": "Currency exchange",
    "other": "Other",
}
_STATUS_LABELS = {"requested": "Pending", "finalized": "Sent"}


def _status_label(value: str) -> str:
    if value in _STATUS_LABELS:
        return _STATUS_LABELS[value]
    text = value.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def transactions_csv(
    *, investor_user_id: str, entries: list[dict[str, Any]], filters: TransactionFilters,
    number_format: str,
) -> str:
    """The whole filtered history as CSV in the investor's number format (C09 / F15)."""
    annotate_available_after(investor_user_id, entries)
    delimiter, decimal_sign = csv_number_format(number_format)
    rows = sorted(
        (entry for entry in entries if _matches(entry, filters)),
        key=lambda entry: (entry["occurred_at"], str(entry["id"])),
        reverse=True,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow([label for label, _ in _CSV_COLUMNS])

    def amount_text(value: int | None, direction: str = "") -> str:
        if value is None:
            return ""
        signed = -abs(value) if direction == "out" else value
        amount = minor_units_to_decimal(signed, minor_units=2).quantize(Decimal("0.01"))
        return format(amount, "f").replace(".", decimal_sign)

    def metadata_minor(entry: dict[str, Any], *keys: str) -> int | None:
        metadata = entry.get("metadata") or {}
        for key in keys:
            value = metadata.get(key) if isinstance(metadata, dict) else None
            if type(value) is int:
                return value
        return None

    for entry in rows:
        occurred = entry["occurred_at"]
        group = activity_group(entry)
        paid = group in {"repayment", "recovery"}
        parts = (str(entry.get("title") or ""), str(entry.get("loan_title") or ""))
        description = " · ".join(part for part in parts if part)
        cells = {
            "date": occurred.astimezone(business_timezone()).strftime("%Y-%m-%d %H:%M"),
            "type": _GROUP_LABELS.get(group, "Other"),
            "description": description,
            "currency": entry.get("currency", ""),
            "amount": amount_text(entry.get("amount_minor"), str(entry.get("direction", ""))),
            "available_after": amount_text(entry.get("available_after_minor")),
            "principal": amount_text(metadata_minor(entry, "principal_minor")) if paid else "",
            "interest": amount_text(
                metadata_minor(entry, "interest_minor", "contractual_interest_minor")
            )
            if paid
            else "",
            "status": _status_label(str(entry.get("status") or "")),
            "id": entry.get("id", ""),
        }
        values = []
        for _, key in _CSV_COLUMNS:
            text = str(cells[key])
            # A text cell cannot start a spreadsheet formula.
            numeric = key in _NUMERIC_COLUMNS
            if text[:1] in {"=", "+", "@"} or (text[:1] == "-" and not numeric):
                text = f"'{text}"
            values.append(text)
        writer.writerow(values)
    return buffer.getvalue()


__all__ = [
    "TransactionFilters",
    "activity_group",
    "annotate_available_after",
    "transaction_page",
    "transactions_csv",
]
