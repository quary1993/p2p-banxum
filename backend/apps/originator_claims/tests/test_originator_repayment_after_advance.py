"""LO servicing after a repayment in advance and its replacement schedule (audit A-09).

The replacement schedule already excludes the prepaid principal and the accrued
interest the advance collected, so later installments must be validated against
the replacement rows without netting the advance a second time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from types import SimpleNamespace
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.utils import timezone

from backend.apps.originator_claims.models import (
    InvestorOriginatorRepaymentDistributionLine,
    LoanOriginatorStatus,
    OriginatorBorrowerRepayment,
    OriginatorDistributionModel,
    OriginatorFundingRoundClose,
    OriginatorLoanImport,
)
from backend.apps.originator_claims.services import (
    CloseOriginatorSubscriptionRoundCommand,
    CreateLoanOriginatorCommand,
    CreateOriginatorLoanCommand,
    OriginatorClaimsValidationError,
    PublishOriginatorLoanCommand,
    RecordOriginatorBorrowerRepaymentCommand,
    _originator_payment_waterfall,
    create_loan_originator,
    create_originator_loan,
    publish_originator_loan,
    record_originator_borrower_repayment,
)
from backend.apps.originator_claims.tests.test_originator_claims import (
    _allocate_par_subscription,
    _close_originator_at_as_of,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.tests.qa_clock import wall_clock

HEADER = (
    "row_type,reference,installment_number,accrual_start_date,due_date,value_date,"
    "payment_type,opening_principal_minor,principal_minor,interest_minor,penalty_minor,"
    "fee_minor,total_minor,closing_principal_minor,resulting_principal_minor"
)


def _schedule_row(
    number: int, start: date, due: date, opening: int, principal: int, interest: int
) -> str:
    return (
        f"schedule,,{number},{start.isoformat()},{due.isoformat()},,,{opening},{principal},"
        f"{interest},0,0,{principal + interest},{opening - principal},"
    )


@dataclass(frozen=True)
class Receipt:
    reference: str
    value_date: date
    payment_type: str
    principal_minor: int
    interest_minor: int
    resulting_principal_minor: int

    def csv_row(self) -> str:
        total = self.principal_minor + self.interest_minor
        return (
            f"payment,{self.reference},,,,{self.value_date.isoformat()},{self.payment_type},,"
            f"{self.principal_minor},{self.interest_minor},0,0,{total},,"
            f"{self.resulting_principal_minor}"
        )


def _csv(schedule: list[str], receipts: list[Receipt]) -> str:
    return "\n".join([HEADER, *schedule, *(receipt.csv_row() for receipt in receipts)]) + "\n"


@dataclass(frozen=True)
class Shape:
    """One LO repayment shape: boundary, optional regular rows, advance, next, final."""

    repayment_type: str
    activation_principal_minor: int
    holdings: tuple[int, int]
    original: list[str]
    replacement: list[str]
    pre_advance: list[Receipt]
    advance: Receipt
    next_due: date
    next_principal_minor: int
    next_interest_minor: int
    final: Receipt


def _amortizing_shape(boundary: date) -> Shape:
    """LO-A: EUR-like 10,000 at 12% (1% a month), boundary 2,000 + 100, then 4,000 + 80, 4,000 + 40.

    Advance on day 15 of the second period: 1,000 principal + 40 accrued interest, then the
    replacement schedule re-amortizes the remaining 7,000 as 3,500 + 35 twice (QA C13).
    """
    second = boundary + timedelta(days=30)
    final = second + timedelta(days=30)
    row_1 = _schedule_row(1, boundary - timedelta(days=30), boundary, 1_000_000, 200_000, 10_000)
    return Shape(
        repayment_type="amortizing_principal_interest",
        activation_principal_minor=800_000,
        holdings=(400_000, 320_000),
        original=[
            row_1,
            _schedule_row(2, boundary, second, 800_000, 400_000, 8_000),
            _schedule_row(3, second, final, 400_000, 400_000, 4_000),
        ],
        replacement=[
            row_1,
            _schedule_row(2, boundary, second, 700_000, 350_000, 3_500),
            _schedule_row(3, second, final, 350_000, 350_000, 3_500),
        ],
        pre_advance=[Receipt("LO-BOUNDARY-1", boundary, "regular", 200_000, 10_000, 800_000)],
        advance=Receipt(
            "LO-ADVANCE-1",
            boundary + timedelta(days=15),
            "repayment_in_advance",
            100_000,
            4_000,
            700_000,
        ),
        next_due=second,
        next_principal_minor=350_000,
        next_interest_minor=3_500,
        final=Receipt("LO-FINAL-3", final, "regular", 350_000, 3_500, 0),
    )


def _bullet_shape(boundary: date) -> Shape:
    """Bullet 10,000 at 12%: interest-only 100 a month, principal at maturity.

    After a regular interest-only installment, an advance pays 2,000 principal + 50 accrued
    interest mid-period; the replacement keeps the bullet shape on the remaining 8,000.
    """
    second = boundary + timedelta(days=30)
    third = second + timedelta(days=30)
    final = third + timedelta(days=30)
    row_1 = _schedule_row(1, boundary - timedelta(days=30), boundary, 1_000_000, 0, 10_000)
    row_2 = _schedule_row(2, boundary, second, 1_000_000, 0, 10_000)
    return Shape(
        repayment_type="bullet_periodic_interest",
        activation_principal_minor=1_000_000,
        holdings=(500_000, 400_000),
        original=[
            row_1,
            row_2,
            _schedule_row(3, second, third, 1_000_000, 0, 10_000),
            _schedule_row(4, third, final, 1_000_000, 1_000_000, 10_000),
        ],
        replacement=[
            row_1,
            row_2,
            _schedule_row(3, second, third, 800_000, 0, 4_000),
            _schedule_row(4, third, final, 800_000, 800_000, 8_000),
        ],
        pre_advance=[
            Receipt("LO-BOUNDARY-1", boundary, "regular", 0, 10_000, 1_000_000),
            Receipt("LO-REGULAR-2", second, "regular", 0, 10_000, 1_000_000),
        ],
        advance=Receipt(
            "LO-ADVANCE-1",
            second + timedelta(days=15),
            "repayment_in_advance",
            200_000,
            5_000,
            800_000,
        ),
        next_due=third,
        next_principal_minor=0,
        next_interest_minor=4_000,
        final=Receipt("LO-FINAL-4", final, "regular", 800_000, 8_000, 0),
    )


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="lo-advance-admin@example.test",
            password="AdminPass123!",
            full_name="LO Advance Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def _investor(email: str, name: str) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name=name,
            account_type="natural_person_lender",
            status="active",
        ),
    )


def _create_lo_loan(*, admin_user: Model, today: date, shape: Shape, suffix: str) -> Any:
    originator = create_loan_originator(
        CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name=f"Advance Originator {suffix} AG",
            public_name=f"Advance Originator {suffix}",
            registration_number=f"CHE-ADVANCE-{suffix}",
            jurisdiction="CH",
            registered_address="Zurich, Switzerland",
            settlement_account_name=f"Advance Originator {suffix} AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference=f"KYB-ADVANCE-{suffix}",
            status=LoanOriginatorStatus.ACTIVE,
        )
    )
    result = create_originator_loan(
        CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title=f"LO advance {suffix}",
            investor_summary="LO claim serviced after a repayment in advance.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1_200,
            distribution_model=OriginatorDistributionModel.PAR_COMPONENT_V2,
            minimum_investment_minor=100_000,
            repayment_type=shape.repayment_type,
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_csv(shape.original, []),
            source_filename=f"lo-advance-{suffix}.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": f"Advance Borrower {suffix} AG",
                "borrower_display_name": f"Advance borrower {suffix}",
            },
            skin_in_the_game_bps=1_000,
            funding_deadline=today + timedelta(days=5),
            entitlement_start_date=today + timedelta(days=10),
            activation_outstanding_principal_minor=shape.activation_principal_minor,
            investor_interest_participation_bps=7_000,
            investor_penalty_participation_bps=5_000,
        )
    )
    publish_originator_loan(
        PublishOriginatorLoanCommand(
            actor=admin_user, loan_id=str(result.loan.id), as_of_date=today
        )
    )
    return result


def _record(
    *,
    admin_user: Model,
    loan: Model,
    schedule: list[str],
    receipts: list[Receipt],
    as_of_date: date | None = None,
    reference: str | None = None,
) -> OriginatorBorrowerRepayment:
    payment = receipts[-1]
    as_of = as_of_date or payment.value_date
    # Record on the receipt's business day so a "no future value date" guard is satisfied.
    with wall_clock(datetime.combine(as_of, time(12), UTC)):
        return record_originator_borrower_repayment(
            RecordOriginatorBorrowerRepaymentCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                csv_content=_csv(schedule, receipts),
                source_filename=f"{payment.reference.lower()}.csv",
                as_of_date=as_of,
                payment_reference=reference or payment.reference,
                booking_date=payment.value_date,
                value_date=payment.value_date,
                collection_account_identifier="CH11 83019 GARANTAFI001",
                payer_name="Advance borrower",
                payer_account_identifier="CH9300762011623852957",
                bank_reference=f"BANK-{payment.reference}",
                bank_payment_reference=payment.reference,
                evidence_reference=f"STMT-{payment.reference}",
                notes="LO receipt.",
                idempotency_key=f"lo-advance-{loan.pk}-{payment.reference}-{as_of}",
            )
        )


def _investor_split(repayment: OriginatorBorrowerRepayment, investor: Model) -> tuple[int, ...]:
    line = InvestorOriginatorRepaymentDistributionLine.objects.get(
        repayment=repayment, investor_user_id=investor.pk
    )
    return (int(line.principal_minor), int(line.interest_minor), int(line.amount_minor))


def _balance(investor: Model) -> int:
    ledger = import_module("backend.apps.ledger.services")
    summary = ledger.summarize_investor_balance(investor_user_id=str(investor.pk), currency="CHF")
    return int(summary.total_available_minor)


def _setup_through_advance(
    *, admin_user: Model, shape_factory: Any, suffix: str
) -> tuple[Any, Shape, Model, Model]:
    today = business_date(timezone.now())
    boundary = today + timedelta(days=10)
    shape = cast(Shape, shape_factory(boundary))
    result = _create_lo_loan(admin_user=admin_user, today=today, shape=shape, suffix=suffix)
    first = _investor(f"lo-advance-first-{suffix.lower()}@example.test", "First Investor")
    second = _investor(f"lo-advance-second-{suffix.lower()}@example.test", "Second Investor")
    for investor, amount, key in (
        (first, shape.holdings[0], f"{suffix}-FIRST"),
        (second, shape.holdings[1], f"{suffix}-SECOND"),
    ):
        _allocate_par_subscription(
            admin_user=admin_user,
            investor=investor,
            loan=result.loan,
            today=today,
            amount_minor=amount,
            suffix=key,
        )
    # A fully subscribed round closes on the last allocation; close it explicitly otherwise.
    if not OriginatorFundingRoundClose.objects.filter(loan_profile=result.profile).exists():
        _close_originator_at_as_of(
            CloseOriginatorSubscriptionRoundCommand(
                actor=admin_user,
                loan_id=str(result.loan.id),
                as_of_date=today + timedelta(days=6),
                close_reason="Funding deadline reached.",
                idempotency_key=f"lo-advance-{suffix}-close",
            )
        )
    result.loan.refresh_from_db()
    assert result.loan.status == "active"
    for index in range(len(shape.pre_advance)):
        _record(
            admin_user=admin_user,
            loan=result.loan,
            schedule=shape.original,
            receipts=shape.pre_advance[: index + 1],
        )
    _record(
        admin_user=admin_user,
        loan=result.loan,
        schedule=shape.replacement,
        receipts=[*shape.pre_advance, shape.advance],
    )
    return result, shape, first, second


SHAPES = {"amortizing": _amortizing_shape, "bullet": _bullet_shape}

# Hand calculation, skin 10%, interest participation 70%:
#   investors' principal share = their holdings / outstanding principal (90%)
#   investors' interest pool   = interest x 90% x 70% = interest x 63%
#   each investor's share is its holding / all investor holdings (5/9 and 4/9)
EXPECTED = {
    "amortizing": {
        # advance 1,040.00: investors 900.00 + 25.20 = 925.20, LO 114.80 (QA C13)
        "advance": (92_520, 11_480, (50_000, 1_400, 51_400), (40_000, 1_120, 41_120)),
        # 3,535.00: principal 3,150.00 / 350.00, interest 35.00 x 63% = 22.05
        "next": (317_205, 36_295, (175_000, 1_225, 176_225), (140_000, 980, 140_980)),
        "final": (317_205, 36_295, (175_000, 1_225, 176_225), (140_000, 980, 140_980)),
    },
    "bullet": {
        # 2,050.00: principal 1,800.00 / 200.00, interest 50.00 x 63% = 31.50
        "advance": (183_150, 21_850, (100_000, 1_750, 101_750), (80_000, 1_400, 81_400)),
        # interest-only 40.00 x 63% = 25.20
        "next": (2_520, 1_480, (0, 1_400, 1_400), (0, 1_120, 1_120)),
        # 8,080.00: principal 7,200.00 / 800.00, interest 80.00 x 63% = 50.40
        "final": (725_040, 82_960, (400_000, 2_800, 402_800), (320_000, 2_240, 322_240)),
    },
}


def _assert_split(
    repayment: OriginatorBorrowerRepayment,
    expected: tuple[int, int, tuple[int, ...], tuple[int, ...]],
    first: Model,
    second: Model,
) -> None:
    investors_minor, originator_minor, first_split, second_split = expected
    assert repayment.investor_distributed_minor == investors_minor
    assert repayment.originator_payable_minor == originator_minor
    assert repayment.platform_costs_minor == 0
    assert investors_minor + originator_minor == repayment.amount_minor
    assert _investor_split(repayment, first) == first_split
    assert _investor_split(repayment, second) == second_split


@pytest.mark.django_db
@pytest.mark.parametrize("shape_name", ["amortizing", "bullet"])
@pytest.mark.parametrize("days_early", [0, 1])
def test_next_and_final_installments_are_accepted_after_repayment_in_advance(
    admin_user: Model,
    shape_name: str,
    days_early: int,
) -> None:
    suffix = f"{shape_name.upper()}-{days_early}"
    result, shape, first, second = _setup_through_advance(
        admin_user=admin_user, shape_factory=SHAPES[shape_name], suffix=suffix
    )
    expected = EXPECTED[shape_name]
    advance = OriginatorBorrowerRepayment.objects.get(
        loan_profile=result.profile, payment_reference="LO-ADVANCE-1"
    )
    _assert_split(advance, expected["advance"], first, second)
    balances_after_advance = (_balance(first), _balance(second))

    # The next installment exactly as the replacement schedule states (on time or one day
    # early with the due date as the replacement as-of date).
    result.profile.refresh_from_db()
    outstanding = int(result.profile.current_outstanding_principal_minor)
    next_receipt = Receipt(
        "LO-NEXT",
        shape.next_due - timedelta(days=days_early),
        "regular",
        shape.next_principal_minor,
        shape.next_interest_minor,
        outstanding - shape.next_principal_minor,
    )
    receipts = [*shape.pre_advance, shape.advance, next_receipt]
    next_repayment = _record(
        admin_user=admin_user,
        loan=result.loan,
        schedule=shape.replacement,
        receipts=receipts,
        as_of_date=shape.next_due,
    )
    _assert_split(next_repayment, expected["next"], first, second)

    final_repayment = _record(
        admin_user=admin_user,
        loan=result.loan,
        schedule=shape.replacement,
        receipts=[*receipts, shape.final],
    )
    _assert_split(final_repayment, expected["final"], first, second)

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert result.loan.status == "repaid"
    assert result.loan.committed_principal_minor == 0
    assert result.profile.current_outstanding_principal_minor == 0
    assert result.profile.unsold_principal_minor == 0
    assert final_repayment.principal_after_minor == 0
    first_credits = expected["next"][2][2] + expected["final"][2][2]
    second_credits = expected["next"][3][2] + expected["final"][3][2]
    assert (_balance(first), _balance(second)) == (
        balances_after_advance[0] + first_credits,
        balances_after_advance[1] + second_credits,
    )
    # Over the life of the loan the investors got back exactly the principal they funded.
    investor_principal = sum(
        int(line.principal_minor)
        for line in InvestorOriginatorRepaymentDistributionLine.objects.filter(
            repayment__loan_profile=result.profile
        )
    )
    assert investor_principal == sum(shape.holdings)


@pytest.mark.django_db
def test_invalid_payments_after_repayment_in_advance_are_still_refused(
    admin_user: Model,
) -> None:
    result, shape, first, second = _setup_through_advance(
        admin_user=admin_user, shape_factory=_amortizing_shape, suffix="REFUSALS"
    )
    history = [*shape.pre_advance, shape.advance]
    due = shape.next_due
    valid = Receipt("LO-NEXT", due, "regular", 350_000, 3_500, 350_000)
    changed_advance = Receipt(
        "LO-ADVANCE-1", shape.advance.value_date, "repayment_in_advance", 100_000, 4_001, 700_000
    )
    changed_schedule = [
        *shape.replacement[:2],
        shape.replacement[2].replace(",3500,0,0,353500,", ",3600,0,0,353600,"),
    ]
    assert changed_schedule != shape.replacement
    attempts: list[tuple[str, list[str], list[Receipt], str | None]] = [
        # Principal before interest.
        (
            "violates the universal payment waterfall",
            shape.replacement,
            [*history, Receipt("LO-NEXT", due, "regular", 350_000, 0, 350_000)],
            None,
        ),
        # More than the installment still due.
        (
            "Payment exceeds the declared",
            shape.replacement,
            [*history, Receipt("LO-NEXT", due, "regular", 350_000, 3_501, 350_000)],
            None,
        ),
        # Missing history: the advance row is dropped and its principal relabelled.
        (
            "preserve every previously imported payment exactly",
            shape.replacement,
            [*shape.pre_advance, Receipt("LO-NEXT", due, "regular", 450_000, 3_500, 350_000)],
            None,
        ),
        # Changed history.
        (
            "preserve every previously imported payment exactly",
            shape.replacement,
            [*shape.pre_advance, changed_advance, valid],
            None,
        ),
        # Duplicate reference.
        (
            "Payment references must be unique",
            shape.replacement,
            [*history, Receipt("LO-ADVANCE-1", due, "regular", 350_000, 3_500, 350_000)],
            "LO-ADVANCE-1",
        ),
        # A regular installment cannot change the replacement schedule.
        (
            "must preserve the agreed loan schedule",
            changed_schedule,
            [*history, valid],
            None,
        ),
    ]
    repayments_before = OriginatorBorrowerRepayment.objects.filter(
        loan_profile=result.profile
    ).count()
    balances_before = (_balance(first), _balance(second))
    for message, schedule, receipts, reference in attempts:
        with pytest.raises(OriginatorClaimsValidationError, match=message):
            _record(
                admin_user=admin_user,
                loan=result.loan,
                schedule=schedule,
                receipts=receipts,
                reference=reference,
            )
    assert (
        OriginatorBorrowerRepayment.objects.filter(loan_profile=result.profile).count()
        == repayments_before
    )
    assert (_balance(first), _balance(second)) == balances_before
    result.profile.refresh_from_db()
    assert result.profile.current_outstanding_principal_minor == 700_000

    accepted = _record(
        admin_user=admin_user,
        loan=result.loan,
        schedule=shape.replacement,
        receipts=[*history, valid],
    )
    assert accepted.amount_minor == 353_500


def _unit_import(rows: list[Any], payments: list[Any]) -> OriginatorLoanImport:
    return cast(
        OriginatorLoanImport,
        SimpleNamespace(
            schedule_rows=SimpleNamespace(order_by=lambda *_args: rows),
            payment_rows=SimpleNamespace(order_by=lambda *_args: payments),
        ),
    )


def _unit_row(number: int, start: date, due: date, principal: int, interest: int) -> Any:
    return SimpleNamespace(
        installment_number=number,
        accrual_start_date=start,
        due_date=due,
        principal_minor=principal,
        interest_minor=interest,
        penalty_minor=0,
        fee_minor=0,
    )


def _unit_payment(value_date: date, payment_type: str, principal: int, interest: int) -> Any:
    return SimpleNamespace(
        value_date=value_date,
        payment_type=payment_type,
        principal_minor=principal,
        interest_minor=interest,
        penalty_minor=0,
        fee_minor=0,
        total_minor=principal + interest,
    )


def test_second_advance_accrues_interest_only_from_the_previous_advance() -> None:
    boundary = date(2026, 10, 19)
    second_due = boundary + timedelta(days=30)
    first_advance = boundary + timedelta(days=15)
    rows = [
        _unit_row(1, boundary - timedelta(days=30), boundary, 200_000, 10_000),
        # Replacement row after the first advance: 35.00 covers day 15 to day 30 on 7,000.
        _unit_row(2, boundary, second_due, 350_000, 3_500),
        _unit_row(3, second_due, second_due + timedelta(days=30), 350_000, 3_500),
    ]
    payments = [
        _unit_payment(boundary, "regular", 200_000, 10_000),
        _unit_payment(first_advance, "repayment_in_advance", 100_000, 4_000),
    ]
    loan_import = _unit_import(rows, payments)

    # Seven of the fifteen remaining days elapsed: 35.00 x 7 / 15 = 16.33.
    second_advance = _unit_payment(
        first_advance + timedelta(days=7), "repayment_in_advance", 50_000, 1_633
    )
    allocation = _originator_payment_waterfall(
        loan_import=loan_import, payment=second_advance, outstanding_principal_minor=700_000
    )
    assert (allocation.interest_minor, allocation.principal_minor) == (1_633, 50_000)

    principal_first = _unit_payment(
        first_advance + timedelta(days=7), "repayment_in_advance", 51_633, 0
    )
    with pytest.raises(
        OriginatorClaimsValidationError, match="violates the universal payment waterfall"
    ):
        _originator_payment_waterfall(
            loan_import=loan_import, payment=principal_first, outstanding_principal_minor=700_000
        )

    # A second advance on the same bank date has no newly elapsed interest.
    same_day = _unit_payment(first_advance, "repayment_in_advance", 50_000, 0)
    allocation = _originator_payment_waterfall(
        loan_import=loan_import, payment=same_day, outstanding_principal_minor=700_000
    )
    assert (allocation.interest_minor, allocation.principal_minor) == (0, 50_000)
