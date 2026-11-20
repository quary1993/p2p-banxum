"""IP of Webby-Soft SRL. 18.6: servicing of new direct loans with the interest engine.

Rules: platform_core.domain.interest_engine (validated 2026-11-18). This module keeps the loan's
position in the database and runs the actions of the admin:

- the position: installments of the current schedule version with what is still owed (from the
  repayment events), recovery expenses, the Default declaration, and penalty X counted per item up
  to the last recorded date (``LoanPenaltyState``);
- the status (on schedule, Pending, Due, Late, Default, repaid) and the alert when Default can be
  declared (never automatic);
- payments: preview and record (allocation, ledger, investor distributions with whole cents and
  carried fractions, prepayment recalculation as a new schedule version);
- expenses, the Default declaration and its cancellation by a super admin.

Earlier loans (before 18.6) keep the servicing of ``services.py``; the Default declaration applies
to them too (``declare_loan_default``).
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model, Sum

from backend.apps.platform_core.domain import interest_engine as ie
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.money import format_amount_minor
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.selectors.settings import loan_status_thresholds
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.platform_core.services.settlement_calendar import settlement_calendar
from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    BorrowerRepaymentEventType,
    InvestorDistributionFraction,
    InvestorRepaymentDistributionLine,
    LoanDefaultDeclaration,
    LoanExpense,
    LoanPenaltyState,
)

ENGINE_CONVENTION = ie.CONVENTION_ACT_365_FIXED
ENGINE_REPAYMENT_STATUSES = {"active", "late", "defaulted"}
EXPENSE_STATUSES = {ie.STATUS_DUE, ie.STATUS_LATE, ie.STATUS_DEFAULT}
CENT = Decimal("1")


class EngineServicingError(ValueError):
    pass


def _services() -> Any:
    from backend.apps.servicing import services

    return services


def is_engine_loan(loan: Model) -> bool:
    """A direct loan on the 18.6 engine (a Loan Originator claim never is)."""
    return (
        str(getattr(loan, "interest_convention", "")) == ENGINE_CONVENTION
        and str(getattr(loan, "product_type", "direct")) == "direct"
    )


def _require_admin(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise EngineServicingError("Admin access is required.")


def _require_superadmin(actor: Model) -> None:
    if not bool(getattr(actor, "is_superuser", False)):
        raise EngineServicingError("Only a super admin can cancel a Default declaration.")


def _today() -> date:
    return business_date(now_utc())


def _loan_model() -> Any:
    return apps.get_model("loans", "Loan")


def _installment_model() -> Any:
    return apps.get_model("loans", "LoanInstallment")


def _interest_start_date(loan: Model) -> date:
    loan_ref = cast(Any, loan)
    return cast(date, loan_ref.payout_date or loan_ref.loan_start_date)


def _penalty_rate(loan: Model) -> Decimal:
    return ie.penalty_rate_fraction(Decimal(str(cast(Any, loan).penalty_daily_rate_percent)))


def _kind(loan: Model) -> str:
    return ie.REPAYMENT_TYPE_KINDS.get(str(cast(Any, loan).repayment_type), ie.KIND_CUSTOM)


def _row_key(number: int, due_date: date) -> str:
    return f"{number}:{due_date.isoformat()}"


def _meta_date(row: Any, key: str) -> date | None:
    value = (row.metadata or {}).get(key)
    return date.fromisoformat(str(value)) if value else None


def active_declaration(loan: Model) -> LoanDefaultDeclaration | None:
    return (
        LoanDefaultDeclaration.objects.filter(loan=cast(Any, loan), cancelled_at__isnull=True)
        .order_by("-created_at")
        .first()
    )


@dataclass
class PositionContext:
    loan: Model
    position: ie.LoanPosition
    rows_by_key: dict[str, Any]
    expenses_by_key: dict[str, LoanExpense]
    declaration: LoanDefaultDeclaration | None
    last_receipt_date: date | None


def _paid_by_row(loan: Model, version: int) -> dict[int, tuple[int, int]]:
    rows = (
        BorrowerRepaymentEvent.objects.filter(loan=loan, installment__schedule_version=version)
        .values("installment__installment_number")
        .annotate(principal=Sum("principal_applied_minor"), interest=Sum("interest_applied_minor"))
    )
    return {
        int(row["installment__installment_number"]): (
            int(row["principal"] or 0),
            int(row["interest"] or 0),
        )
        for row in rows
    }


def build_position(loan: Model, *, lock: bool = False) -> PositionContext:
    """The loan's position as recorded: what is owed, with penalties up to ``through_date``."""
    loan_ref = cast(Any, loan)
    # The stored version (an instance loaded before a payment or declaration may be stale).
    version = int(
        _loan_model().objects.filter(pk=loan_ref.pk).values_list("schedule_version", flat=True)[0]
    )
    loan_ref.schedule_version = version
    query = (
        _installment_model()
        .objects.filter(loan=loan, schedule_version=version)
        .order_by("due_date", "installment_number", "id")
    )
    if lock:
        query = query.select_for_update()
    rows = list(query)
    paid = _paid_by_row(loan, version)
    state_row = LoanPenaltyState.objects.filter(loan=cast(Any, loan)).first()
    state: dict[str, Any] = dict(state_row.state) if state_row is not None else {}
    item_state: dict[str, Any] = dict(state.get("installments") or {})
    expense_state: dict[str, Any] = dict(state.get("expenses") or {})
    interest_start = _interest_start_date(loan)
    installments: list[ie.OpenInstallment] = []
    rows_by_key: dict[str, Any] = {}
    previous_due = interest_start
    for row in rows:
        principal_paid, interest_paid = paid.get(int(row.installment_number), (0, 0))
        key = _row_key(int(row.installment_number), cast(date, row.due_date))
        rows_by_key[key] = row
        saved = dict(item_state.get(key) or {})
        installments.append(
            ie.OpenInstallment(
                key=key,
                number=int(row.installment_number),
                due_date=cast(date, row.due_date),
                interest_start=_meta_date(row, "interest_start") or previous_due,
                principal_owed=int(row.principal_minor) - principal_paid,
                interest_owed=int(row.interest_minor) - interest_paid,
                original_due_date=_meta_date(row, "original_due_date") or cast(date, row.due_date),
                scheduled_principal=int(row.principal_minor),
                scheduled_interest=int(row.interest_minor),
                penalty_accrued=Decimal(str(saved.get("accrued", "0"))),
                penalty_paid=int(saved.get("paid", 0)),
                # Audit S5-4: interest already paid on this row of this schedule version.
                interest_paid=interest_paid,
            )
        )
        previous_due = cast(date, row.due_date)
    expenses: list[ie.OpenExpense] = []
    expenses_by_key: dict[str, LoanExpense] = {}
    for expense in LoanExpense.objects.filter(loan=loan).order_by("value_date", "created_at"):
        key = str(expense.id)
        expenses_by_key[key] = expense
        saved = dict(expense_state.get(key) or {})
        expenses.append(
            ie.OpenExpense(
                key=key,
                value_date=expense.value_date,
                amount_owed=int(expense.amount_minor) - int(saved.get("paid", 0)),
                penalty_accrued=Decimal(str(saved.get("accrued", "0"))),
                penalty_paid=int(saved.get("penalty_paid", 0)),
            )
        )
    declaration = active_declaration(loan)
    frozen = dict(state.get("frozen") or {})
    default_state = dict(state.get("default") or {})
    last_receipt = (
        BorrowerRepaymentEvent.objects.filter(loan=loan)
        .order_by("-value_date")
        .values_list("value_date", flat=True)
        .first()
    )
    position = ie.LoanPosition(
        through_date=state_row.through_date if state_row is not None else interest_start,
        penalty_rate=_penalty_rate(loan),
        installments=installments,
        expenses=expenses,
        default_on=declaration.declared_on if declaration is not None else None,
        frozen_penalty_minor=int(frozen.get("minor", 0)),
        frozen_penalty_paid=int(frozen.get("paid", 0)),
        default_penalty_accrued=Decimal(str(default_state.get("accrued", "0"))),
        default_penalty_paid=int(default_state.get("paid", 0)),
    )
    return PositionContext(
        loan=loan,
        position=position,
        rows_by_key=rows_by_key,
        expenses_by_key=expenses_by_key,
        declaration=declaration,
        last_receipt_date=cast(date | None, last_receipt),
    )


def penalty_state_payload(position: ie.LoanPosition) -> dict[str, Any]:
    return {
        "installments": {
            row.key: {"accrued": str(row.penalty_accrued), "paid": row.penalty_paid}
            for row in position.installments
            if row.penalty_accrued or row.penalty_paid
        },
        "expenses": {
            item.key: {
                "paid": 0,  # filled in by _save_state from the expense amounts
                "accrued": str(item.penalty_accrued),
                "penalty_paid": item.penalty_paid,
            }
            for item in position.expenses
        },
        "frozen": {"minor": position.frozen_penalty_minor, "paid": position.frozen_penalty_paid},
        "default": {
            "accrued": str(position.default_penalty_accrued),
            "paid": position.default_penalty_paid,
        },
    }


def _save_state(context: PositionContext) -> dict[str, Any]:
    payload = penalty_state_payload(context.position)
    for item in context.position.expenses:
        expense = context.expenses_by_key[item.key]
        payload["expenses"][item.key]["paid"] = int(expense.amount_minor) - item.amount_owed
    LoanPenaltyState.objects.update_or_create(
        loan=context.loan,
        defaults={"through_date": context.position.through_date, "state": payload},
    )
    return payload


# ---------------------------------------------------------------------------------------------
# Status


@dataclass(frozen=True)
class EngineStatus:
    label: str
    days_late: int
    oldest_unpaid_due_date: date | None
    default_possible: bool
    as_of: date
    principal_owed_minor: int
    due_now_minor: int
    penalty_owed_minor: int
    expenses_owed_minor: int
    default_declared_on: date | None
    late_days: int
    default_days: int
    penalty_daily_rate_percent: str


def engine_status(loan: Model, *, as_of: date | None = None) -> EngineStatus:
    """The status of an engine loan on ``as_of`` (today by default), penalties counted to it."""
    as_of = as_of or _today()
    context = build_position(loan)
    position = copy.deepcopy(context.position)
    if as_of > position.through_date:
        ie.accrue_penalties(position, as_of)
    thresholds = loan_status_thresholds(loan)
    oldest = position.oldest_unpaid_due_date(as_of)
    anything_owed = (
        position.principal_owed > 0
        or any(row.interest_owed > 0 for row in position.installments)
        or position.expenses_owed > 0
        or position.penalty_owed > 0
    )
    status = ie.installment_status(
        oldest_unpaid_due_date=oldest,
        as_of=as_of,
        days=settlement_calendar(str(cast(Any, loan).currency_id)),
        late_days=thresholds.late_days,
        default_days=thresholds.default_days,
        default_declared=context.declaration is not None,
        anything_owed=anything_owed,
    )
    due_now = sum(row.owed for row in position.due_installments(as_of))
    if context.declaration is not None:
        due_now = sum(row.owed for row in position.installments)
    return EngineStatus(
        label=status.status,
        days_late=status.days_late,
        oldest_unpaid_due_date=status.oldest_unpaid_due_date,
        default_possible=status.default_possible,
        as_of=as_of,
        principal_owed_minor=position.principal_owed,
        due_now_minor=due_now + position.expenses_owed + position.penalty_owed,
        penalty_owed_minor=position.penalty_owed,
        expenses_owed_minor=position.expenses_owed,
        default_declared_on=context.declaration.declared_on if context.declaration else None,
        late_days=thresholds.late_days,
        default_days=thresholds.default_days,
        penalty_daily_rate_percent=str(cast(Any, loan).penalty_daily_rate_percent),
    )


def loan_status_for_label(label: str) -> str:
    return {
        ie.STATUS_LATE: "late",
        ie.STATUS_DEFAULT: "defaulted",
        ie.STATUS_REPAID: "repaid",
    }.get(label, "active")


def refresh_engine_loan_status(
    loan: Model, *, actor: Model, as_of: date, reason: str, metadata: dict[str, Any] | None = None
) -> Any:
    """Set active / late / repaid from the engine status; never defaulted (declared only)."""
    status = engine_status(loan, as_of=as_of)
    new_status = loan_status_for_label(status.label)
    if new_status == "defaulted" and str(cast(Any, loan).status) != "defaulted":
        new_status = "late"
    change = _services()._record_loan_servicing_status_change(
        loan=loan,
        actor=actor,
        new_status=new_status,
        as_of_date=as_of,
        days_past_due=status.days_late,
        outstanding_minor=status.due_now_minor,
        triggering_installment=None,
        reason=reason,
        metadata={"servicing_label": status.label, **(metadata or {})},
    )
    if status.label == ie.STATUS_LATE and status.default_possible:
        open_default_possible_alert(loan, actor=actor, status=status)
    return change


def open_default_possible_alert(loan: Model, *, actor: Model, status: EngineStatus) -> None:
    loan_ref = cast(Any, loan)
    admin_ops = _services()._admin_ops_services()
    admin_ops.ensure_loan_default_review_task(
        admin_ops.EnsureLoanDefaultReviewTaskCommand(
            actor=actor,
            loan_id=str(loan_ref.id),
            loan_title=str(loan_ref.title),
            product_type=str(loan_ref.product_type),
            currency=str(loan_ref.currency_id),
            as_of_date=status.as_of,
            days_past_due=status.days_late,
            outstanding_minor=status.due_now_minor,
            triggering_due_date=status.oldest_unpaid_due_date,
            default_possible=True,
        )
    )


# ---------------------------------------------------------------------------------------------
# Distribution to investors (F13 B)


@dataclass
class EngineDistributionLine:
    holding: Model
    investor_user_id: str
    principal_minor: int = 0
    interest_minor: int = 0
    penalty_minor: int = 0
    current_principal_before_minor: int = 0
    current_principal_after_minor: int = 0
    final_cents: bool = False

    @property
    def amount_minor(self) -> int:
        return self.principal_minor + self.interest_minor + self.penalty_minor


@dataclass
class EngineDistribution:
    lines: list[EngineDistributionLine]
    withheld_minor: int
    released_minor: int
    fractions: dict[str, tuple[Decimal, Decimal]] = field(default_factory=dict)
    final_paid: dict[str, int] = field(default_factory=dict)


def _largest_remainder(total: int, exact: list[Decimal]) -> list[int]:
    floors = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in exact]
    remainder = total - sum(floors)
    order = sorted(range(len(exact)), key=lambda index: (-(exact[index] - floors[index]), index))
    for index in order[: max(0, remainder)]:
        floors[index] += 1
    return floors


def _engine_distribution(
    *,
    loan: Model,
    holdings: list[Model],
    principal_minor: int,
    interest_minor: int,
    penalty_minor: int,
    final_payment: bool,
) -> EngineDistribution:
    total_principal = sum(int(cast(Any, holding).current_principal_minor) for holding in holdings)
    if principal_minor > total_principal:
        raise EngineServicingError("The payment repays more principal than the investors hold.")
    weights = [Decimal(int(cast(Any, holding).current_principal_minor)) for holding in holdings]
    weight_sum = sum(weights) or Decimal(1)
    principal_parts = _largest_remainder(
        principal_minor, [Decimal(principal_minor) * weight / weight_sum for weight in weights]
    )
    lines: list[EngineDistributionLine] = []
    exact_interest: dict[str, Decimal] = {}
    exact_penalty: dict[str, Decimal] = {}
    holding_exact: list[tuple[Decimal, Decimal]] = []
    for holding, weight, principal in zip(holdings, weights, principal_parts, strict=True):
        holding_ref = cast(Any, holding)
        investor = str(holding_ref.investor_user_id)
        interest_exact = Decimal(interest_minor) * weight / weight_sum
        penalty_exact = Decimal(penalty_minor) * weight / weight_sum
        holding_exact.append((interest_exact, penalty_exact))
        exact_interest[investor] = exact_interest.get(investor, Decimal(0)) + interest_exact
        exact_penalty[investor] = exact_penalty.get(investor, Decimal(0)) + penalty_exact
        before = int(holding_ref.current_principal_minor)
        lines.append(
            EngineDistributionLine(
                holding=holding,
                investor_user_id=investor,
                principal_minor=principal,
                current_principal_before_minor=before,
                current_principal_after_minor=before - principal,
            )
        )
    stored = {
        str(row.investor_user_id): row
        for row in InvestorDistributionFraction.objects.select_for_update().filter(
            loan=cast(Any, loan)
        )
    }
    fractions: dict[str, tuple[Decimal, Decimal]] = {
        investor: (Decimal(row.interest_fraction), Decimal(row.penalty_fraction))
        for investor, row in stored.items()
    }
    paid_interest: dict[str, int] = {}
    paid_penalty: dict[str, int] = {}
    for investor in exact_interest:
        carried_interest, carried_penalty = fractions.get(investor, (Decimal(0), Decimal(0)))
        total_interest = exact_interest[investor] + carried_interest
        total_penalty = exact_penalty[investor] + carried_penalty
        whole_interest = int(total_interest.to_integral_value(rounding=ROUND_FLOOR))
        whole_penalty = int(total_penalty.to_integral_value(rounding=ROUND_FLOOR))
        paid_interest[investor] = whole_interest
        paid_penalty[investor] = whole_penalty
        fractions[investor] = (total_interest - whole_interest, total_penalty - whole_penalty)
    # Split each investor's whole cents over the investor's holdings.
    for investor in exact_interest:
        indexes = [index for index, line in enumerate(lines) if line.investor_user_id == investor]
        for component, paid in (("interest", paid_interest), ("penalty", paid_penalty)):
            position = 0 if component == "interest" else 1
            parts = _largest_remainder(
                paid[investor], [holding_exact[index][position] for index in indexes]
            )
            for index, part in zip(indexes, parts, strict=True):
                setattr(lines[index], f"{component}_minor", part)
    # Audit S5-2: the carried fractions can make the whole cents of this payment more than the
    # investors' part of it (a carry crossing). The difference then comes out of the fractions
    # account; it is never a negative amount kept back.
    net_kept = (
        interest_minor + penalty_minor - sum(paid_interest.values()) - sum(paid_penalty.values())
    )
    withheld = max(net_kept, 0)
    released = max(-net_kept, 0)
    final_paid: dict[str, int] = {}
    if final_payment:
        released += _release_final_fractions(
            loan=loan, lines=lines, fractions=fractions, final_paid=final_paid
        )
    return EngineDistribution(
        lines=[line for line in lines if line.amount_minor > 0],
        withheld_minor=withheld,
        released_minor=released,
        fractions=fractions,
        final_paid=final_paid,
    )


def _release_final_fractions(
    *,
    loan: Model,
    lines: list[EngineDistributionLine],
    fractions: dict[str, tuple[Decimal, Decimal]],
    final_paid: dict[str, int],
) -> int:
    """The last cents of a loan (F13 B): the carried fractions, by largest remainder.

    Audit S5-9: interest and penalty are two pools. Each pool sums to whole cents (every payment
    split a whole number of cents of that component), so each is released on its own and a
    released penalty cent stays a penalty cent. Investors who no longer hold the loan get their
    cents on their latest holding. Returns the cents released."""
    released = 0
    for position, component in ((0, "interest"), (1, "penalty")):
        totals = {
            investor: values[position]
            for investor, values in fractions.items()
            if values[position] > 0
        }
        available = int(sum(totals.values(), Decimal(0)).quantize(CENT, rounding=ROUND_HALF_UP))
        investors = sorted(totals)
        parts = _largest_remainder(available, [totals[investor] for investor in investors])
        for investor, cents in zip(investors, parts, strict=True):
            if cents <= 0:
                continue
            line = next((item for item in lines if item.investor_user_id == investor), None)
            if line is None:
                latest = _latest_holding(loan, investor)
                if latest is None:
                    continue
                before = int(cast(Any, latest).current_principal_minor)
                line = EngineDistributionLine(
                    holding=latest,
                    investor_user_id=investor,
                    current_principal_before_minor=before,
                    current_principal_after_minor=before,
                    final_cents=True,
                )
                lines.append(line)
            setattr(line, f"{component}_minor", getattr(line, f"{component}_minor") + cents)
            final_paid[investor] = final_paid.get(investor, 0) + cents
            released += cents
    for investor in fractions:
        fractions[investor] = (Decimal(0), Decimal(0))
    return released


def settle_fractions_at_end_of_servicing(
    loan: Model, *, actor: Model, value_date: date, source_type: str, source_id: str, reason: str
) -> dict[str, Any]:
    """Audit S5-12: a loan that ends without a final borrower payment (a final write-off) pays
    the investors the whole cents kept for them, by largest remainder per pool (interest,
    penalty), from the fractions account. A true sub-cent residue is recorded as the closed
    rounding result. Returns what was settled (empty for a loan without fractions)."""
    if not is_engine_loan(loan):
        return {}
    rows = list(
        InvestorDistributionFraction.objects.select_for_update().filter(loan=cast(Any, loan))
    )
    fractions = {
        str(row.investor_user_id): (Decimal(row.interest_fraction), Decimal(row.penalty_fraction))
        for row in rows
    }
    if not any(any(values) for values in fractions.values()):
        return {}
    lines: list[EngineDistributionLine] = []
    final_paid: dict[str, int] = {}
    pools = (
        sum((values[0] for values in fractions.values()), Decimal(0)),
        sum((values[1] for values in fractions.values()), Decimal(0)),
    )
    released = _release_final_fractions(
        loan=loan, lines=lines, fractions=fractions, final_paid=final_paid
    )
    residue = {
        "interest": str(pools[0] - sum(line.interest_minor for line in lines)),
        "penalty": str(pools[1] - sum(line.penalty_minor for line in lines)),
    }
    if released:
        ledger: Any = import_module("backend.apps.ledger.services")
        ledger.release_loan_cent_fractions(
            ledger.ReleaseLoanCentFractionsCommand(
                actor=actor,
                loan_id=str(cast(Any, loan).pk),
                currency=str(cast(Any, loan).currency_id),
                value_date=value_date,
                source_type=source_type,
                source_id=source_id,
                lines=[
                    ledger.FractionReleaseLineCommand(
                        investor_user_id=line.investor_user_id,
                        holding_id=str(cast(Any, line.holding).pk),
                        interest_minor=line.interest_minor,
                        penalty_minor=line.penalty_minor,
                    )
                    for line in lines
                    if line.amount_minor > 0
                ],
                reason=reason,
            )
        )
    for row in rows:
        row.interest_fraction = Decimal(0)
        row.penalty_fraction = Decimal(0)
        row.final_paid_minor = int(row.final_paid_minor) + final_paid.get(
            str(row.investor_user_id), 0
        )
        row.save(
            update_fields=[
                "interest_fraction",
                "penalty_fraction",
                "final_paid_minor",
                "updated_at",
            ]
        )
    result = {
        "released_minor": released,
        "by_investor": final_paid,
        "closed_rounding_residue": residue,
        "reason": reason,
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="servicing.cent_fractions_settled",
            target_type="Loan",
            target_id=str(cast(Any, loan).pk),
            metadata={**result, "source_type": source_type, "source_id": source_id},
        )
    )
    return result


def _latest_holding(loan: Model, investor_user_id: str) -> Model | None:
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    return cast(
        Model | None,
        holding_model.objects.filter(loan=loan, investor_user_id=investor_user_id)
        .order_by("-assignment_effective_at", "-created_at")
        .first(),
    )


def _save_fractions(loan: Model, distribution: EngineDistribution) -> None:
    currency_id = str(cast(Any, loan).currency_id)
    for investor, (interest_fraction, penalty_fraction) in distribution.fractions.items():
        row, _ = InvestorDistributionFraction.objects.get_or_create(
            loan=loan,
            investor_user_id=investor,
            defaults={"currency_id": currency_id},
        )
        row.interest_fraction = interest_fraction
        row.penalty_fraction = penalty_fraction
        row.final_paid_minor = int(row.final_paid_minor) + distribution.final_paid.get(investor, 0)
        row.save(
            update_fields=[
                "interest_fraction",
                "penalty_fraction",
                "final_paid_minor",
                "updated_at",
            ]
        )


# ---------------------------------------------------------------------------------------------
# Payments


@dataclass(frozen=True)
class EnginePaymentPlan:
    allocation: ie.Allocation
    position_before: ie.LoanPosition
    context: PositionContext
    penalty_investors_minor: int
    garanta_minor: int
    fully_repaid: bool


def _penalty_investors_part(loan: Model, penalty_minor: int) -> int:
    """The investors' part of a penalty payment, in whole cents.

    Audit S5-9 rule: Garanta's part is rounded down to the cent and the investors get the rest,
    so the investors' part is never rounded against them and no sub-cent of the split is left
    over (the investors' cents are then split between them with the carried fractions)."""
    share = int(cast(Any, loan).penalty_investor_share_bps)
    garanta_exact = Decimal(penalty_minor) * Decimal(10_000 - share) / Decimal(10_000)
    garanta = int(garanta_exact.to_integral_value(rounding=ROUND_FLOOR))
    return penalty_minor - garanta


def plan_engine_payment(
    loan: Model, *, amount_minor: int, value_date: date, lock: bool = False
) -> EnginePaymentPlan:
    context = build_position(loan, lock=lock)
    if context.last_receipt_date is not None and value_date < context.last_receipt_date:
        raise EngineServicingError(
            "The value date cannot be before a payment that is already recorded."
        )
    if value_date < context.position.through_date:
        raise EngineServicingError(
            "The value date cannot be before the last recorded payment, expense or declaration."
        )
    if value_date < _interest_start_date(loan):
        raise EngineServicingError("The value date cannot be before the payout day.")
    before = copy.deepcopy(context.position)
    try:
        allocation = ie.allocate_payment(
            context.position,
            amount_minor=amount_minor,
            value_date=value_date,
            annual_rate_bps=int(cast(Any, loan).interest_rate_bps),
            kind=_kind(loan),
        )
    except ie.InterestEngineError as exc:
        raise EngineServicingError(str(exc)) from exc
    if allocation.unapplied_minor:
        owed = amount_minor - allocation.unapplied_minor
        raise EngineServicingError(
            "The payment is more than everything the borrower owes on this value date "
            f"({format_amount_minor(owed, str(cast(Any, loan).currency_id))}). Record only the "
            "amount owed and return the rest to the borrower."
        )
    penalty_investors = _penalty_investors_part(loan, allocation.penalty_minor)
    garanta = allocation.expenses_minor + allocation.penalty_minor - penalty_investors
    position = context.position
    fully_repaid = (
        position.principal_owed == 0
        and all(row.interest_owed == 0 for row in position.installments)
        and position.expenses_owed == 0
        and position.penalty_owed == 0
    )
    return EnginePaymentPlan(
        allocation=allocation,
        position_before=before,
        context=context,
        penalty_investors_minor=penalty_investors,
        garanta_minor=garanta,
        fully_repaid=fully_repaid,
    )


def payment_preview_payload(loan: Model, plan: EnginePaymentPlan) -> dict[str, Any]:
    allocation = plan.allocation
    currency = str(cast(Any, loan).currency_id)
    rows = []
    for key, (penalty, interest, principal) in allocation.installments.items():
        row = plan.context.rows_by_key.get(key)
        rows.append(
            {
                "installment_number": int(row.installment_number) if row is not None else 0,
                "due_date": cast(date, row.due_date).isoformat() if row is not None else "",
                "penalty_minor": penalty,
                "interest_minor": interest,
                "principal_minor": principal,
            }
        )
    return {
        "loan_id": str(cast(Any, loan).id),
        "currency": currency,
        "amount_minor": allocation.amount_minor,
        "value_date": allocation.value_date.isoformat(),
        "expenses_minor": allocation.expenses_minor,
        "penalty_minor": allocation.penalty_minor,
        "interest_minor": allocation.interest_minor,
        "principal_minor": allocation.principal_minor,
        "prepayment_minor": allocation.prepayment_minor,
        "accrued_interest_days": allocation.accrued_interest_days,
        "schedule_changes": allocation.schedule_changed,
        "penalty_to_investors_minor": plan.penalty_investors_minor,
        "to_garanta_minor": plan.garanta_minor,
        "fully_repaid": plan.fully_repaid,
        "installments": rows,
        "new_schedule": [
            {
                "installment_number": row.number,
                "due_date": row.due_date.isoformat(),
                "principal_minor": row.principal_minor,
                "interest_minor": row.interest_minor,
                "total_minor": row.total_minor,
            }
            for row in (allocation.new_future_rows or [])
        ],
    }


def preview_engine_payment(
    *, actor: Model, loan_id: str, amount_minor: int, value_date: date
) -> dict[str, Any]:
    _require_admin(actor)
    loan = _loan_model().objects.filter(id=loan_id).first()
    if loan is None or not is_engine_loan(loan):
        raise EngineServicingError("This loan does not use the 18.6 interest engine.")
    if value_date > _today():
        raise EngineServicingError("The value date cannot be in the future.")
    plan = plan_engine_payment(loan, amount_minor=amount_minor, value_date=value_date)
    return payment_preview_payload(loan, plan)


def _write_schedule_version(
    loan: Model, *, rows: list[ie.OpenInstallment], extra_metadata: dict[str, str] | None = None
) -> int:
    loan_ref = cast(Any, loan)
    new_version = int(loan_ref.schedule_version) + 1
    installment_model = _installment_model()
    installment_model.objects.bulk_create(
        [
            installment_model(
                loan=loan,
                schedule_version=new_version,
                installment_number=row.number,
                due_date=row.due_date,
                principal_minor=row.principal_owed,
                interest_minor=row.interest_owed,
                total_minor=row.owed,
                admin_overridden=False,
                metadata={
                    "original_due_date": row.original_due_date.isoformat(),
                    "interest_start": row.interest_start.isoformat(),
                    **(extra_metadata or {}),
                },
            )
            for row in rows
            if row.owed > 0
        ]
    )
    loan_ref.schedule_version = new_version
    loan.save(update_fields=["schedule_version", "updated_at"])
    return new_version


@transaction.atomic
def record_engine_repayment(command: Any) -> Any:
    """Record a borrower payment on an engine loan (``RecordBorrowerRepaymentCommand``).

    One transaction for the lock, the ledger posting, the events and the distribution (found
    with the audit S1-1 check: the loan row lock needs a transaction on PostgreSQL)."""
    services = _services()
    services._require_admin_actor(command.actor)
    idempotency_key = services._clean_idempotency_key(command.idempotency_key)
    amount_minor = services._validate_positive_minor_amount(
        command.amount_minor, "Repayment amount"
    )
    fingerprint = services._request_fingerprint(
        command,
        amount_minor=amount_minor,
        collection_account_identifier=services._repayment_collection_account_fingerprint(
            command.collection_account_identifier
        ),
        idempotency_key=idempotency_key,
    )
    existing = services._existing_repayment_for_idempotency(
        idempotency_key, expected_fingerprint=fingerprint
    )
    if existing is not None:
        return existing
    services._validate_bank_dates_not_in_future(
        booking_date=command.booking_date, value_date=command.value_date
    )
    payer_account = services._clean_required(command.payer_account_identifier, "Payer account")
    loan = services._locked_loan(command.loan_id)
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) not in ENGINE_REPAYMENT_STATUSES:
        if str(loan_ref.status) == "funded":
            raise EngineServicingError(
                "Loan funds must be disbursed to the borrower before repayments can be recorded."
            )
        raise EngineServicingError(
            "The loan must be active, late or in Default to record a payment."
        )
    if not bool(getattr(loan_ref.borrower, "can_transact", False)):
        raise EngineServicingError("Borrower KYB must be approved and free of compliance hold.")
    existing = services._existing_repayment_for_idempotency(
        idempotency_key, expected_fingerprint=fingerprint
    )
    if existing is not None:
        return existing
    repeat_ids = services._guard_duplicate_borrower_receipt(
        loan_id=str(loan_ref.id),
        currency=str(loan_ref.currency_id),
        amount_minor=amount_minor,
        payer_account_identifier=payer_account,
        value_date=command.value_date,
        bank_reference=command.bank_reference,
        confirm_repeat_payment=command.confirm_repeat_payment,
    )
    currency = services._enabled_currency(str(loan_ref.currency_id))
    collection_account = services._resolve_repayment_collection_account_identifier(
        currency=currency.code, supplied_identifier=command.collection_account_identifier
    )
    plan = plan_engine_payment(
        loan, amount_minor=amount_minor, value_date=command.value_date, lock=True
    )
    allocation = plan.allocation
    holdings = services._active_holdings_for_loan(loan)
    distribution = _engine_distribution(
        loan=loan,
        holdings=holdings,
        principal_minor=allocation.principal_minor,
        interest_minor=allocation.interest_minor,
        penalty_minor=plan.penalty_investors_minor,
        final_payment=plan.fully_repaid,
    )
    context = plan.context
    touched = [key for key in allocation.installments if key in context.rows_by_key]
    anchor_key = touched[0] if touched else _anchor_key(context)
    anchor_row = context.rows_by_key[anchor_key]
    event_ids = {key: uuid.uuid4() for key in (touched or [anchor_key])}
    anchor_id = event_ids[anchor_key]
    ledger = services._ledger_services()
    try:
        ledger_result = ledger.declare_borrower_repayment_distribution(
            ledger.DeclareBorrowerRepaymentDistributionCommand(
                actor=command.actor,
                loan_id=str(loan_ref.id),
                borrower_id=str(loan_ref.borrower_id),
                amount_minor=amount_minor,
                currency=currency.code,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=collection_account,
                payer_name=command.payer_name,
                source_type="borrower_repayment_event",
                source_id=str(anchor_id),
                distribution_lines=[
                    ledger.InvestorBalanceCreditLineCommand(
                        investor_user_id=line.investor_user_id,
                        amount_minor=line.amount_minor,
                        principal_minor=line.principal_minor,
                        interest_minor=line.interest_minor,
                        penalty_minor=line.penalty_minor,
                        holding_id=str(cast(Any, line.holding).id),
                        installment_id=str(anchor_row.id),
                        metadata={
                            "current_principal_before_minor": line.current_principal_before_minor,
                            "current_principal_after_minor": line.current_principal_after_minor,
                            **({"final_cents": True} if line.final_cents else {}),
                        },
                    )
                    for line in distribution.lines
                ],
                payer_account_identifier=payer_account,
                bank_reference=command.bank_reference,
                payment_reference=command.payment_reference,
                evidence_reference=command.evidence_reference,
                admin_notes=command.admin_notes,
                idempotency_key=idempotency_key,
                garanta_minor=plan.garanta_minor,
                garanta_penalty_minor=allocation.penalty_minor - plan.penalty_investors_minor,
                fractions_withheld_minor=distribution.withheld_minor,
                fractions_released_minor=distribution.released_minor,
            )
        )
    except ledger.LedgerError as exc:
        raise EngineServicingError(str(exc)) from exc
    received_at = services._received_at_from_value_date(command.value_date)
    installment_penalties = sum(values[0] for values in allocation.installments.values())
    other_penalties = allocation.penalty_minor - installment_penalties
    installment_principal = sum(values[2] for values in allocation.installments.values())
    future_principal = allocation.principal_minor - installment_principal
    state_payload = penalty_state_payload(context.position)
    base_metadata = {
        services.REQUEST_FINGERPRINT_METADATA_KEY: fingerprint,
        "loan_id": str(loan_ref.id),
        "interest_engine": ENGINE_CONVENTION,
        "allocation": payment_preview_payload(loan, plan),
        "penalty_state_after": state_payload,
        "ledger_journal_entry_id": str(ledger_result.journal_entry.id),
        "bank_operation_id": str(ledger_result.bank_operation.id),
        **({"confirmed_repeat_of_bank_operation_ids": repeat_ids} if repeat_ids else {}),
    }
    events: dict[str, BorrowerRepaymentEvent] = {}
    try:
        with transaction.atomic():
            for position_index, key in enumerate(event_ids):
                penalty, interest, principal = allocation.installments.get(key, (0, 0, 0))
                is_anchor = key == anchor_key
                fees = allocation.expenses_minor if is_anchor else 0
                extra_penalty = other_penalties if is_anchor else 0
                extra_principal = future_principal if is_anchor else 0
                row = context.rows_by_key[key]
                before_row = next(
                    (item for item in plan.position_before.installments if item.key == key), None
                )
                amount = penalty + interest + principal + fees + extra_penalty + extra_principal
                if amount <= 0:
                    continue
                event_type = (
                    BorrowerRepaymentEventType.EARLY_REPAYMENT
                    if allocation.prepayment_minor
                    else BorrowerRepaymentEventType.REGULAR_INSTALLMENT
                    if before_row is not None and interest + principal == before_row.owed
                    else BorrowerRepaymentEventType.PARTIAL_INSTALLMENT
                )
                events[key] = BorrowerRepaymentEvent.objects.create(
                    id=event_ids[key],
                    loan=loan,
                    installment=row,
                    event_type=event_type,
                    amount_minor=amount,
                    currency=currency,
                    booking_date=command.booking_date,
                    value_date=command.value_date,
                    received_at=received_at,
                    expected_due_minor=before_row.owed if before_row is not None else 0,
                    interest_applied_minor=interest,
                    principal_applied_minor=principal,
                    future_principal_applied_minor=extra_principal,
                    fees_applied_minor=fees,
                    penalties_applied_minor=penalty + extra_penalty,
                    remaining_installment_interest_minor=max(
                        0, (before_row.interest_owed if before_row else 0) - interest
                    ),
                    remaining_installment_principal_minor=max(
                        0, (before_row.principal_owed if before_row else 0) - principal
                    ),
                    warning_acknowledged=bool(allocation.prepayment_minor),
                    bank_operation=ledger_result.bank_operation,
                    journal_entry=ledger_result.journal_entry,
                    created_by_admin_id=command.actor.pk,
                    notes=command.admin_notes.strip(),
                    metadata={**base_metadata, "part": position_index, "anchor": is_anchor}
                    if is_anchor
                    else {"loan_id": str(loan_ref.id), "anchor_event_id": str(anchor_id)},
                    idempotency_key=idempotency_key
                    if is_anchor
                    else f"{idempotency_key}:part:{position_index}",
                )
    except IntegrityError:
        existing = services._existing_repayment_for_idempotency(
            idempotency_key, expected_fingerprint=fingerprint
        )
        if existing is None:
            raise
        return existing
    anchor_event = events[anchor_key]
    _save_state(context)
    _save_fractions(loan, distribution)
    credits = {credit.line_index: credit for credit in ledger_result.balance_credits}
    lines: list[InvestorRepaymentDistributionLine] = []
    # Audit S5-10: each investor's credit is recorded under every installment the receipt paid
    # (the investor's share of each one), so the investor's payment table shows each row. The
    # ledger keeps one credit (one balance lot) per holding for the one bank movement.
    event_order = [key for key in event_ids if key in events]
    event_weights = _event_component_weights(
        allocation=allocation,
        anchor_key=anchor_key,
        keys=event_order,
        other_penalties=other_penalties,
        future_principal=future_principal,
    )
    for index, line in enumerate(distribution.lines):
        if line.principal_minor:
            services._record_holding_principal_update(
                holding=line.holding,
                actor=command.actor,
                repayment_event=anchor_event,
                principal_minor=line.principal_minor,
                before_minor=line.current_principal_before_minor,
                after_minor=line.current_principal_after_minor,
            )
        parts = _split_line_over_events(line, keys=event_order, weights=event_weights)
        principal_before = line.current_principal_before_minor
        for key in event_order:
            principal, interest, penalty = parts[key]
            if principal + interest + penalty <= 0:
                continue
            lines.append(
                InvestorRepaymentDistributionLine.objects.create(
                    repayment_event=events[key],
                    holding=line.holding,
                    investor_user_id=line.investor_user_id,
                    currency=currency,
                    balance_lot=credits[index].balance_lot,
                    amount_minor=principal + interest + penalty,
                    principal_minor=principal,
                    interest_minor=interest,
                    penalty_minor=penalty,
                    fee_minor=0,
                    current_principal_before_minor=principal_before,
                    current_principal_after_minor=principal_before - principal,
                    metadata={
                        "line_index": index,
                        "anchor_event_id": str(anchor_id),
                        **({"final_cents": True} if line.final_cents else {}),
                    },
                )
            )
            principal_before -= principal
    new_version = None
    if allocation.schedule_changed:
        new_version = _write_schedule_version(
            loan, rows=[row for row in context.position.installments if row.owed > 0]
        )
    status_change = refresh_engine_loan_status(
        loan,
        actor=command.actor,
        as_of=max(command.value_date, _today()),
        reason="borrower_repayment",
        metadata={"repayment_event_id": str(anchor_event.id)},
    )
    services._after_repayment_listing_refresh_and_emails(
        loan=loan,
        actor=command.actor,
        repayment_event=anchor_event,
        distribution_lines=lines,
        currency=currency,
        value_date=command.value_date,
    )
    audit_metadata = {
        "loan_id": str(loan_ref.id),
        "currency": currency.code,
        "amount_minor": amount_minor,
        "expenses_minor": allocation.expenses_minor,
        "penalty_minor": allocation.penalty_minor,
        "interest_minor": allocation.interest_minor,
        "principal_minor": allocation.principal_minor,
        "prepayment_minor": allocation.prepayment_minor,
        "to_garanta_minor": plan.garanta_minor,
        "fractions_withheld_minor": distribution.withheld_minor,
        "fractions_released_minor": distribution.released_minor,
        "new_schedule_version": new_version,
        "event_ids": [str(event.id) for event in events.values()],
        "loan_status_change": {
            "previous_status": status_change.previous_status,
            "new_status": status_change.new_status,
        }
        if status_change is not None
        else {},
    }
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="servicing.borrower_repayment_recorded",
            target_type="BorrowerRepaymentEvent",
            target_id=str(anchor_event.id),
            metadata=audit_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BorrowerRepaymentRecorded",
            aggregate_type="BorrowerRepaymentEvent",
            aggregate_id=str(anchor_event.id),
            payload=audit_metadata,
            idempotency_key=f"borrower-repayment:{anchor_event.id}:recorded",
        )
    )
    return services.RecordBorrowerRepaymentResult(
        repayment_event=anchor_event, distribution_lines=lines
    )


def _event_component_weights(
    *,
    allocation: ie.Allocation,
    anchor_key: str,
    keys: list[str],
    other_penalties: int,
    future_principal: int,
) -> dict[str, tuple[int, int, int]]:
    """(principal, interest, penalty) the receipt paid on each installment event, as recorded on
    the events (the anchor also carries the future principal and the penalties outside rows)."""
    weights: dict[str, tuple[int, int, int]] = {}
    for key in keys:
        penalty, interest, principal = allocation.installments.get(key, (0, 0, 0))
        if key == anchor_key:
            penalty += other_penalties
            principal += future_principal
        weights[key] = (principal, interest, penalty)
    return weights


def _split_by_weights(total: int, keys: list[str], weights: list[int], anchor: str) -> list[int]:
    if total <= 0 or sum(weights) <= 0:
        return [total if key == anchor else 0 for key in keys]
    return _largest_remainder(
        total, [Decimal(total) * Decimal(weight) / Decimal(sum(weights)) for weight in weights]
    )


def _split_line_over_events(
    line: EngineDistributionLine,
    *,
    keys: list[str],
    weights: dict[str, tuple[int, int, int]],
) -> dict[str, tuple[int, int, int]]:
    """One holding's whole-cent credit split over the installment events by largest remainder,
    each component on its own; cents without a weight (final cents) go on the first event."""
    anchor = keys[0]
    split: dict[str, list[int]] = {key: [0, 0, 0] for key in keys}
    for position, total in enumerate(
        (line.principal_minor, line.interest_minor, line.penalty_minor)
    ):
        parts = _split_by_weights(total, keys, [weights[key][position] for key in keys], anchor)
        for key, part in zip(keys, parts, strict=True):
            split[key][position] = part
    return {key: (values[0], values[1], values[2]) for key, values in split.items()}


def _anchor_key(context: PositionContext) -> str:
    """The row a payment without installment parts (expenses, penalties) is recorded on."""
    open_rows = [row for row in context.position.installments if row.owed > 0]
    if open_rows:
        return min(open_rows, key=lambda row: (row.due_date, row.number)).key
    if not context.rows_by_key:
        raise EngineServicingError("The loan has no schedule.")
    return list(context.rows_by_key)[-1]


# ---------------------------------------------------------------------------------------------
# Expenses


@dataclass(frozen=True)
class RecordLoanExpenseCommand:
    actor: Model
    loan_id: str
    amount_minor: int
    value_date: date
    note: str
    evidence_reference: str = ""
    document_id: str = ""
    idempotency_key: str = ""


def _expense_fingerprint(command: RecordLoanExpenseCommand, *, note: str) -> str:
    return cast(
        str,
        _services()._stable_json_fingerprint(
            {
                "loan_id": str(command.loan_id),
                "amount_minor": command.amount_minor,
                "value_date": command.value_date.isoformat(),
                "note": note,
                "evidence_reference": command.evidence_reference.strip()[:255],
                "document_id": str(command.document_id or ""),
            }
        ),
    )


def _existing_expense(idempotency_key: str, *, fingerprint: str) -> LoanExpense | None:
    """Audit S5-8: a replay returns the expense only for the same request (loan, amount, date,
    note, evidence); the key used for another request is refused."""
    existing = LoanExpense.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if dict(existing.metadata or {}).get("request_fingerprint") != fingerprint:
        raise EngineServicingError(
            "This idempotency key was already used for a different expense request."
        )
    return cast(LoanExpense, existing)


@transaction.atomic
def record_loan_expense(command: RecordLoanExpenseCommand) -> LoanExpense:
    _require_admin(command.actor)
    services = _services()
    idempotency_key = services._clean_idempotency_key(command.idempotency_key)
    note = command.note.strip()
    fingerprint = _expense_fingerprint(command, note=note)
    existing = _existing_expense(idempotency_key, fingerprint=fingerprint)
    if existing is not None:
        return existing
    loan = services._locked_loan(command.loan_id)
    loan_ref = cast(Any, loan)
    if not is_engine_loan(loan):
        raise EngineServicingError("Expenses are recorded on loans with the 18.6 interest engine.")
    if type(command.amount_minor) is not int or command.amount_minor <= 0:
        raise EngineServicingError("The expense amount must be positive.")
    if not note:
        raise EngineServicingError("Write what the expense is for.")
    # Checked again under the loan lock (a parallel request with the same key).
    existing = _existing_expense(idempotency_key, fingerprint=fingerprint)
    if existing is not None:
        return existing
    today = _today()
    if command.value_date > today:
        raise EngineServicingError("The value date cannot be in the future.")
    context = build_position(loan, lock=True)
    if command.value_date < context.position.through_date:
        raise EngineServicingError(
            "The value date cannot be before the last recorded payment, expense or declaration."
        )
    # Audit S5-3: the loan must have been Due, Late or in Default on the expense's value date,
    # not only today (an expense cannot go back into the Pending days).
    status = engine_status(loan, as_of=command.value_date)
    if status.label not in EXPENSE_STATUSES:
        raise EngineServicingError(
            "On the value date of the expense an installment must be Due (unpaid after the "
            "Pending days), in Late or after a Default declaration."
        )
    document_id = None
    if command.document_id:
        document_model = apps.get_model("entities", "BorrowerDocument")
        if not document_model.objects.filter(
            id=command.document_id, borrower_id=loan_ref.borrower_id
        ).exists():
            raise EngineServicingError("The file must be a document of this borrower.")
        document_id = uuid.UUID(str(command.document_id))
    try:
        with transaction.atomic():
            expense = LoanExpense.objects.create(
                loan=loan,
                currency_id=str(loan_ref.currency_id),
                amount_minor=command.amount_minor,
                value_date=command.value_date,
                note=note,
                evidence_reference=command.evidence_reference.strip()[:255],
                document_id=document_id,
                created_by_admin_id=command.actor.pk,
                metadata={
                    "status_when_recorded": status.label,
                    "days_late": status.days_late,
                    "request_fingerprint": fingerprint,
                },
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        existing = _existing_expense(idempotency_key, fingerprint=fingerprint)
        if existing is None:
            raise
        return existing
    # Audit S5-3: the expense moves the economic position to its value date (penalties counted
    # to it), so no later payment can have an earlier value date.
    ie.accrue_penalties(context.position, command.value_date)
    _save_state(context)
    event_metadata = {
        "expense_id": str(expense.id),
        "amount_minor": expense.amount_minor,
        "currency": str(loan_ref.currency_id),
        "value_date": expense.value_date.isoformat(),
        "evidence_reference": expense.evidence_reference,
        "document_id": str(document_id or ""),
    }
    apps.get_model("loans", "LoanEvent").objects.create(
        loan=loan,
        event_type="expense_recorded",
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        previous_status=str(loan_ref.status),
        new_status=str(loan_ref.status),
        note=note,
        metadata=event_metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="servicing.loan_expense_recorded",
            target_type="LoanExpense",
            target_id=str(expense.id),
            metadata=event_metadata,
        )
    )
    return cast(LoanExpense, expense)


def expense_payload(
    expense: LoanExpense, position: ie.LoanPosition | None = None
) -> dict[str, Any]:
    item = None
    if position is not None:
        item = next((value for value in position.expenses if value.key == str(expense.id)), None)
    return {
        "id": str(expense.id),
        "amount_minor": int(expense.amount_minor),
        "currency": str(expense.currency_id),
        "value_date": expense.value_date.isoformat(),
        "note": expense.note,
        "evidence_reference": expense.evidence_reference,
        "document_id": str(expense.document_id or ""),
        "owed_minor": item.amount_owed if item is not None else int(expense.amount_minor),
        "penalty_owed_minor": item.penalty_owed if item is not None else 0,
        "created_at": expense.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------------------------
# Default declaration


@dataclass(frozen=True)
class DeclareLoanDefaultCommand:
    actor: Model
    loan_id: str
    note: str = ""


@dataclass(frozen=True)
class CancelLoanDefaultCommand:
    actor: Model
    loan_id: str
    reason: str


def _legacy_days_late(loan: Model, as_of: date) -> tuple[int, int, Any]:
    if str(getattr(loan, "product_type", "direct")) == "originator_claim":
        days = import_module(
            "backend.apps.originator_claims.services"
        ).originator_loan_days_past_due(str(cast(Any, loan).pk), as_of_date=as_of)
        return int(days), 0, None
    first_outstanding = _services()._first_outstanding_installment_status
    _status, days, outstanding, installment = first_outstanding(
        loan, as_of_date=as_of, lock_installments=False
    )
    return days, outstanding, installment


@transaction.atomic
def declare_loan_default(command: DeclareLoanDefaultCommand) -> LoanDefaultDeclaration:
    """Default = maturity, decided by the admin once the oldest unpaid installment is late by at
    least the Default days. Everything becomes due at once; the schedule stops."""
    _require_admin(command.actor)
    services = _services()
    loan = services._locked_loan(command.loan_id)
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) not in {"active", "late"}:
        raise EngineServicingError("Default can only be declared on an active or late loan.")
    if active_declaration(loan) is not None:
        raise EngineServicingError("Default is already declared on this loan.")
    today = _today()
    thresholds = loan_status_thresholds(loan)
    previous_status = str(loan_ref.status)
    schedule_before = int(loan_ref.schedule_version)
    if is_engine_loan(loan):
        context = build_position(loan, lock=True)
        state_before = penalty_state_payload(copy.deepcopy(context.position))
        state_before["through_date"] = context.position.through_date.isoformat()
        for item in context.position.expenses:
            expense = context.expenses_by_key[item.key]
            state_before["expenses"][item.key]["paid"] = (
                int(expense.amount_minor) - item.amount_owed
            )
        status = engine_status(loan, as_of=today)
        if not status.default_possible:
            raise EngineServicingError(
                f"Default can be declared once the oldest unpaid installment is late by "
                f"{thresholds.default_days} days (today: {status.days_late})."
            )
        position = context.position
        principal, interest = ie.default_whole_amount(
            position=position,
            declared_on=today,
            annual_rate_bps=int(loan_ref.interest_rate_bps),
        )
        ie.freeze_penalties_at_default(position, today)
        days_late = status.days_late
        declaration = LoanDefaultDeclaration.objects.create(
            loan=loan,
            declared_on=today,
            declared_by_admin_id=command.actor.pk,
            note=command.note.strip(),
            days_late=days_late,
            whole_principal_minor=principal,
            whole_interest_minor=interest,
            frozen_penalty_minor=position.frozen_penalty_minor,
            schedule_version_before=schedule_before,
            penalty_state_before=state_before,
        )
        whole_row = ie.OpenInstallment(
            key=_row_key(1, today),
            number=1,
            due_date=today,
            interest_start=today,
            principal_owed=principal,
            interest_owed=interest,
            original_due_date=today,
        )
        position.installments = [whole_row]
        new_version = _write_schedule_version(
            loan, rows=[whole_row], extra_metadata={"default_declaration_id": str(declaration.id)}
        )
        context.position = position
        context.rows_by_key = {}
        _save_state(context)
        declaration.schedule_version_after = new_version
        declaration.save(update_fields=["schedule_version_after", "updated_at"])
    else:
        days_late, outstanding, _installment = _legacy_days_late(loan, today)
        if days_late < thresholds.default_days:
            raise EngineServicingError(
                f"Default can be declared once the oldest unpaid installment is late by "
                f"{thresholds.default_days} days (today: {days_late})."
            )
        declaration = LoanDefaultDeclaration.objects.create(
            loan=loan,
            declared_on=today,
            declared_by_admin_id=command.actor.pk,
            note=command.note.strip(),
            days_late=days_late,
            schedule_version_before=schedule_before,
            schedule_version_after=schedule_before,
        )
    loan_ref.status = "defaulted"
    loan_ref.default_declared_on = today
    loan_ref.updated_by_admin_id = command.actor.pk
    loan.save(update_fields=["status", "default_declared_on", "updated_by_admin_id", "updated_at"])
    metadata = {
        "declaration_id": str(declaration.id),
        "declared_on": today.isoformat(),
        "days_late": days_late,
        "whole_principal_minor": declaration.whole_principal_minor,
        "whole_interest_minor": declaration.whole_interest_minor,
        "frozen_penalty_minor": declaration.frozen_penalty_minor,
        "schedule_version_before": schedule_before,
        "schedule_version_after": declaration.schedule_version_after,
    }
    apps.get_model("loans", "LoanEvent").objects.create(
        loan=loan,
        event_type="default_declared",
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        previous_status=previous_status,
        new_status="defaulted",
        note=command.note.strip() or "Default declared by the admin.",
        metadata=metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="loan.default_declared",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanDefaultDeclared",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=metadata,
            idempotency_key=f"loan:{loan_ref.id}:default-declared:{declaration.id}",
        )
    )
    _refresh_listings(loan, actor=command.actor, source=f"default:{declaration.id}")
    from backend.apps.platform_core.services.investor_notices import (
        notify_loan_holders_of_status_change,
    )

    notify_loan_holders_of_status_change(
        loan=loan, new_status="defaulted", as_of_date=today, days_past_due=days_late
    )
    return declaration


def money_recorded_after_declaration(loan: Model, declaration: LoanDefaultDeclaration) -> str:
    """Audit S5-6: what money was recorded on the loan after the Default declaration, on any
    path (engine or legacy payment, recovery receipt, expense, write-off, Loan Originator
    repayment); "" when nothing. A cancellation would give such money another meaning."""
    after = declaration.created_at
    checks: list[tuple[str, Any]] = [
        ("A borrower payment", BorrowerRepaymentEvent.objects.filter(loan=loan)),
        ("An expense", LoanExpense.objects.filter(loan=loan)),
        (
            "A recovery receipt",
            apps.get_model("servicing", "LoanRecoveryEvent").objects.filter(loan=loan),
        ),
        (
            "A write-off",
            apps.get_model("servicing", "LoanWriteOffEvent").objects.filter(loan=loan),
        ),
        (
            "A Loan Originator repayment",
            apps.get_model("originator_claims", "OriginatorBorrowerRepayment").objects.filter(
                loan_profile__loan=loan
            ),
        ),
    ]
    for label, query in checks:
        if query.filter(created_at__gt=after).exists():
            return label
    return ""


@transaction.atomic
def cancel_loan_default(command: CancelLoanDefaultCommand) -> LoanDefaultDeclaration:
    """A super admin cancels a Default declared by mistake, with a written reason."""
    _require_superadmin(command.actor)
    reason = command.reason.strip()
    if len(reason) < 10:
        raise EngineServicingError(
            "Write the reason for the cancellation (at least 10 characters)."
        )
    services = _services()
    loan = services._locked_loan(command.loan_id)
    loan_ref = cast(Any, loan)
    declaration = active_declaration(loan)
    if declaration is None:
        raise EngineServicingError("This loan has no Default declaration to cancel.")
    today = _today()
    activity = money_recorded_after_declaration(loan, declaration)
    if activity:
        raise EngineServicingError(
            f"{activity} was recorded after the declaration: it cannot be cancelled any more. "
            "A correction now needs a compensating, audited accounting entry."
        )
    if is_engine_loan(loan):
        installment_model = _installment_model()
        before_rows = list(
            installment_model.objects.filter(
                loan=loan, schedule_version=declaration.schedule_version_before
            ).order_by("due_date", "installment_number")
        )
        paid = _paid_by_row(loan, declaration.schedule_version_before)
        restored: list[ie.OpenInstallment] = []
        for row in before_rows:
            principal_paid, interest_paid = paid.get(int(row.installment_number), (0, 0))
            restored.append(
                ie.OpenInstallment(
                    key=_row_key(int(row.installment_number), cast(date, row.due_date)),
                    number=int(row.installment_number),
                    due_date=cast(date, row.due_date),
                    interest_start=_meta_date(row, "interest_start") or cast(date, row.due_date),
                    principal_owed=int(row.principal_minor) - principal_paid,
                    interest_owed=int(row.interest_minor) - interest_paid,
                    original_due_date=_meta_date(row, "original_due_date")
                    or cast(date, row.due_date),
                )
            )
        new_version = _write_schedule_version(loan, rows=restored)
        state = dict(declaration.penalty_state_before or {})
        through = date.fromisoformat(str(state.pop("through_date", declaration.declared_on)))
        LoanPenaltyState.objects.update_or_create(
            loan=loan, defaults={"through_date": through, "state": state}
        )
        declaration.restored_schedule_version = new_version
    declaration.cancelled_at = now_utc()
    declaration.cancelled_by_admin_id = command.actor.pk
    declaration.cancel_reason = reason
    declaration.save(
        update_fields=[
            "cancelled_at",
            "cancelled_by_admin_id",
            "cancel_reason",
            "restored_schedule_version",
            "updated_at",
        ]
    )
    loan_ref.default_declared_on = None
    loan_ref.status = "late"
    loan_ref.updated_by_admin_id = command.actor.pk
    loan.save(update_fields=["default_declared_on", "status", "updated_by_admin_id", "updated_at"])
    metadata = {
        "declaration_id": str(declaration.id),
        "declared_on": declaration.declared_on.isoformat(),
        "reason": reason,
        "restored_schedule_version": declaration.restored_schedule_version,
    }
    apps.get_model("loans", "LoanEvent").objects.create(
        loan=loan,
        event_type="default_cancelled",
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        previous_status="defaulted",
        new_status="late",
        note=reason,
        metadata=metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="loan.default_cancelled",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata=metadata,
        )
    )
    if is_engine_loan(loan):
        refresh_engine_loan_status(
            loan, actor=command.actor, as_of=today, reason="default_cancelled"
        )
    else:
        status, days, outstanding, installment = services._first_outstanding_installment_status(
            loan, as_of_date=today
        )
        services._record_loan_servicing_status_change(
            loan=loan,
            actor=command.actor,
            new_status=status,
            as_of_date=today,
            days_past_due=days,
            outstanding_minor=outstanding,
            triggering_installment=installment,
            reason="default_cancelled",
        )
    _refresh_listings(loan, actor=command.actor, source=f"default-cancelled:{declaration.id}")
    _notify_holders_of_cancellation(loan, declaration=declaration)
    return declaration


def _refresh_listings(loan: Model, *, actor: Model, source: str) -> None:
    try:
        _services()._secondary_market_services().refresh_open_secondary_market_listings_for_loan(
            actor=actor,
            loan=loan,
            as_of_date=_today(),
            source_type="loan_default_declaration",
            source_id=source,
        )
    except ValueError as exc:
        raise EngineServicingError(
            "The Default change could not safely refresh the loan's resale listings."
        ) from exc


def _notify_holders_of_cancellation(loan: Model, *, declaration: LoanDefaultDeclaration) -> None:
    from backend.apps.platform_core.services.investor_notices import (
        InvestorNotice,
        enqueue_investor_notice,
    )

    loan_ref = cast(Any, loan)
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holdings = holding_model.objects.filter(loan=loan, status="active").order_by("created_at")
    brand = settings.PLATFORM_BRAND_NAME
    notified: set[str] = set()
    for holding in holdings:
        investor_id = str(holding.investor_user_id)
        if investor_id in notified:
            continue
        notified.add(investor_id)
        enqueue_investor_notice(
            InvestorNotice(
                investor_user_id=investor_id,
                topic="email.loan_default_cancelled",
                idempotency_key=f"email:loan-default-cancelled:{declaration.id}:{investor_id}",
                subject=f"{brand}: correction for loan {loan_ref.title}",
                body_text=(
                    f"The Default declared on {declaration.declared_on.isoformat()} for loan "
                    f"{loan_ref.title} was a mistake and is cancelled. The loan is back to its "
                    "payment plan; late installments stay late until the borrower pays them."
                ),
                template_key="servicing.loan_default_cancelled.v1",
                headline="Default declaration cancelled",
                status_label="Correction",
                status_tone="info",
                data_rows=(("Loan", str(loan_ref.title)),),
                navigation_target="holding",
                navigation_target_id=str(holding.id),
                metadata={"loan_id": str(loan_ref.id), "declaration_id": str(declaration.id)},
            )
        )


def declaration_payload(declaration: LoanDefaultDeclaration) -> dict[str, Any]:
    return {
        "id": str(declaration.id),
        "declared_on": declaration.declared_on.isoformat(),
        "days_late": declaration.days_late,
        "note": declaration.note,
        "whole_principal_minor": declaration.whole_principal_minor,
        "whole_interest_minor": declaration.whole_interest_minor,
        "frozen_penalty_minor": declaration.frozen_penalty_minor,
        "cancelled_at": declaration.cancelled_at.isoformat() if declaration.cancelled_at else None,
        "cancel_reason": declaration.cancel_reason,
    }


def servicing_position_payload(loan: Model, *, as_of: date | None = None) -> dict[str, Any]:
    """Admin view of an engine loan: status, amounts owed, expenses and Default history."""
    loan_ref = cast(Any, loan)
    payload: dict[str, Any] = {
        "loan_id": str(loan_ref.id),
        "interest_engine": is_engine_loan(loan),
        "currency": str(loan_ref.currency_id),
        "declarations": [
            declaration_payload(item)
            for item in LoanDefaultDeclaration.objects.filter(loan=cast(Any, loan)).order_by(
                "-created_at"
            )
        ],
    }
    if not is_engine_loan(loan):
        thresholds = loan_status_thresholds(loan)
        days, outstanding, installment = _legacy_days_late(loan, as_of or _today())
        payload.update(
            {
                "status": "default"
                if str(loan_ref.status) == "defaulted"
                else str(loan_ref.status),
                "days_late": days,
                "default_possible": str(loan_ref.status) in {"active", "late"}
                and days >= thresholds.default_days,
                "expenses": [],
                "late_days": thresholds.late_days,
                "default_days": thresholds.default_days,
            }
        )
        return payload
    status = engine_status(loan, as_of=as_of)
    context = build_position(loan)
    position = copy.deepcopy(context.position)
    if status.as_of > position.through_date:
        ie.accrue_penalties(position, status.as_of)
    payload.update(
        {
            "status": status.label,
            "days_late": status.days_late,
            "oldest_unpaid_due_date": status.oldest_unpaid_due_date.isoformat()
            if status.oldest_unpaid_due_date
            else None,
            "default_possible": status.default_possible and status.label == ie.STATUS_LATE,
            "as_of": status.as_of.isoformat(),
            "principal_owed_minor": status.principal_owed_minor,
            "due_now_minor": status.due_now_minor,
            "penalty_owed_minor": status.penalty_owed_minor,
            "expenses_owed_minor": status.expenses_owed_minor,
            "late_days": status.late_days,
            "default_days": status.default_days,
            "penalty_daily_rate_percent": status.penalty_daily_rate_percent,
            "penalty_investor_share_bps": int(loan_ref.penalty_investor_share_bps),
            "grace_business_days": int(loan_ref.grace_business_days),
            "payment_frequency": str(loan_ref.payment_frequency),
            "expenses_allowed": status.label in EXPENSE_STATUSES,
            "expenses": [
                expense_payload(expense, position) for expense in context.expenses_by_key.values()
            ],
            "installment_penalties": [
                {
                    "installment_number": row.number,
                    "due_date": row.due_date.isoformat(),
                    "owed_minor": row.owed,
                    "penalty_owed_minor": row.penalty_owed,
                }
                for row in position.installments
                if row.owed > 0 or row.penalty_owed > 0
            ],
        }
    )
    return payload
