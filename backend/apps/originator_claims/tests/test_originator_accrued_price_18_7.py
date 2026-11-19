"""IP of Webby-Soft SRL. 18.7: Loan Originator offers priced as principal + accrued interest.

Q09 / F02: the investor pays the principal at the planned settlement day (1 settlement day after
the funding deadline, one reference day for all investors) plus the accrued interest of the rights
bought, and receives the next payment. F03: the claim's day-count convention is required. F04: a
due date (or a borrower payment) before the settlement fails the offer. Q17: Coming soon offers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from typing import Any, cast
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client

from backend.apps.originator_claims.models import (
    LoanOriginatorStatus,
    OriginatorClaimEvent,
    OriginatorClaimEventType,
    OriginatorClaimPurchase,
    OriginatorDistributionModel,
    OriginatorLoanProfile,
    OriginatorOpportunityStatus,
    OriginatorPricingRule,
)
from backend.apps.originator_claims.services import (
    CloseOriginatorSubscriptionRoundCommand,
    CreateLoanOriginatorCommand,
    CreateOriginatorLoanCommand,
    OriginatorClaimsValidationError,
    PublishOriginatorLoanCommand,
    accrued_interest_for_principal,
    create_loan_originator,
    create_originator_loan,
    publish_originator_loan,
)
from backend.apps.originator_claims.tests.test_originator_claims import (
    _approve_financial_access,
    _close_originator_at_as_of,
    _declare_originator_test_deposit,
    _primary_order_acceptance,
    _scan_originator_at_as_of,
)
from backend.apps.platform_core.domain import day_count
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.services.settlement_calendar import settlement_calendar
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code


@pytest.fixture
def admin_user(db: None) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="accrued-admin@example.test",
            password="AdminPass123!",
            full_name="Accrued Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor(db: None) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="accrued-investor@example.test",
            full_name="Accrued Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )


def _csv(today: date) -> str:
    accrual_start = today - timedelta(days=20)
    next_due = today + timedelta(days=30)
    second_due = next_due + timedelta(days=30)
    final_due = second_due + timedelta(days=30)
    return (
        "row_type,reference,installment_number,accrual_start_date,due_date,value_date,"
        "payment_type,opening_principal_minor,principal_minor,interest_minor,penalty_minor,"
        "fee_minor,total_minor,closing_principal_minor,resulting_principal_minor\n"
        f"schedule,,1,{accrual_start.isoformat()},{next_due.isoformat()},,,1000000,200000,"
        "10000,0,0,210000,800000,\n"
        f"schedule,,2,{next_due.isoformat()},{second_due.isoformat()},,,800000,400000,"
        "8000,0,0,408000,400000,\n"
        f"schedule,,3,{second_due.isoformat()},{final_due.isoformat()},,,400000,400000,"
        "4000,0,0,404000,0,\n"
    )


def _create(
    admin_user: Model,
    *,
    today: date,
    suffix: str,
    deadline_days: int = 5,
    convention: str = day_count.ACT_365_FIXED,
    publish: bool = True,
) -> Any:
    originator = create_loan_originator(
        CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name=f"Accrued Originator {suffix} AG",
            public_name=f"Accrued Originator {suffix}",
            registration_number=f"CHE-ACCRUED-{suffix}",
            jurisdiction="CH",
            registered_address="Zurich, Switzerland",
            settlement_account_name=f"Accrued Originator {suffix} AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference=f"KYB-ACCRUED-{suffix}",
            status=LoanOriginatorStatus.ACTIVE,
        )
    )
    result = create_originator_loan(
        CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title=f"Accrued offer {suffix}",
            investor_summary="Offer priced with accrued interest.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1_200,
            distribution_model=OriginatorDistributionModel.PAR_COMPONENT_V2,
            pricing_rule=OriginatorPricingRule.ACCRUED_INTEREST,
            interest_convention=convention,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_csv(today),
            source_filename=f"accrued-{suffix}.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": f"Accrued Borrower {suffix} AG",
                "borrower_display_name": f"Accrued borrower {suffix}",
            },
            funding_deadline=today + timedelta(days=deadline_days),
            investor_interest_participation_bps=7_000,
            investor_penalty_participation_bps=5_000,
        )
    )
    if publish:
        publish_originator_loan(
            PublishOriginatorLoanCommand(
                actor=admin_user, loan_id=str(result.loan.id), as_of_date=today
            )
        )
    return result


def _allocate_par_subscription(
    *,
    admin_user: Model,
    investor: Model,
    loan: Model,
    today: date,
    amount_minor: int,
    suffix: str,
    deposit_minor: int | None = None,
) -> Any:
    """Deposit (by default the principal + its accrued interest), order and allocate."""
    _approve_financial_access(investor)
    profile = OriginatorLoanProfile.objects.get(loan_id=cast(Any, loan).pk)
    _declare_originator_test_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=(
            deposit_minor
            if deposit_minor is not None
            else amount_minor + accrued_interest_for_principal(profile, amount_minor)
        ),
        today=today,
        suffix=suffix,
    )
    marketplace = import_module("backend.apps.marketplace_primary.services")
    order = marketplace.create_primary_investment_order(
        marketplace.CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(cast(Any, loan).pk),
            amount_minor=amount_minor,
            idempotency_key=f"accrued-{suffix}-order",
        )
    )
    acceptance = _primary_order_acceptance(investor, order_id=str(order.id), suffix=suffix)
    code = issue_sensitive_action_test_code(investor, "primary_investment")
    return marketplace.allocate_primary_order_from_balance(
        marketplace.AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=f"accrued-{suffix}-allocate",
            sensitive_action_code_id=code.code_id,
            sensitive_action_code=code.raw_code,
            pin=code.pin,
        )
    )


def test_day_count_conventions() -> None:
    start, end = date(2027, 1, 31), date(2027, 3, 31)
    assert day_count.day_units(start, end, day_count.ACT_365_FIXED) == 59
    assert day_count.day_units(start, end, day_count.THIRTY_360_BOND_BASIS) == 60
    assert day_count.day_units(date(2027, 1, 30), date(2027, 3, 31), "thirty_360_bond_basis") == 60
    assert day_count.day_units(date(2027, 1, 15), date(2027, 3, 31), "thirty_e_360") == 75
    assert day_count.day_units(date(2027, 1, 15), date(2027, 3, 31), "thirty_360_bond_basis") == 76
    # Act/Act ISDA across a leap-year boundary: 31 days of 2027 / 365 + 60 days of 2028 / 366.
    fraction = day_count.year_fraction(date(2027, 12, 1), date(2028, 3, 1), "act_act_isda")
    assert float(fraction) == pytest.approx(31 / 365 + 60 / 366)
    with pytest.raises(day_count.DayCountError, match="day-count convention"):
        day_count.require_convention("act_365_25")
    # Exact integer pricing: 10,000 of interest over 50 days, 26 days accrued, 70% share.
    assert (
        day_count.accrued_interest_minor(
            period_interest_minor=10_000,
            period_principal_minor=1_000_000,
            principal_minor=100_000,
            accrual_start=date(2027, 1, 1),
            due_date=date(2027, 2, 20),
            reference_date=date(2027, 1, 27),
            participation_bps=7_000,
            convention=day_count.ACT_365_FIXED,
        )
        == 364  # 1,000 x 26 / 50 x 0.7 = 364.00
    )


@pytest.mark.django_db
def test_an_accrued_offer_has_no_boundary_and_prices_principal_plus_accrued_interest(
    admin_user: Model,
) -> None:
    today = business_date(now_utc())
    result = _create(admin_user, today=today, suffix="P1")
    profile = OriginatorLoanProfile.objects.get(pk=result.profile.pk)
    reference = settlement_calendar("CHF").add(today + timedelta(days=5), 1)

    assert profile.pricing_rule == OriginatorPricingRule.ACCRUED_INTEREST
    assert profile.price_reference_date == reference
    assert profile.entitlement_start_date == reference
    assert profile.price_next_due_date == today + timedelta(days=30)
    # No boundary installment: investors buy the whole current principal and the next payment.
    assert profile.activation_outstanding_principal_minor == 1_000_000
    accrued_days = (reference - (today - timedelta(days=20))).days
    expected = round(10_000 * 100_000 / 1_000_000 * accrued_days / 50 * 0.7 + 1e-9)
    assert accrued_interest_for_principal(profile, 100_000) == expected

    client = Client()
    client.force_login(cast(Any, admin_user))
    detail = client.get(f"/api/v1/originator-claims/admin/loans/{result.loan.id}/").json()
    assert detail["pricing_rule"] == "accrued_interest"
    assert detail["price"]["price_reference_date"] == reference.isoformat()
    assert detail["price"]["accrued_day_units"] == accrued_days
    assert detail["price"]["period_day_units"] == 50
    assert not any(row["is_originator_boundary"] for row in detail["schedule"])


@pytest.mark.django_db
def test_the_planned_settlement_must_be_before_the_next_due_date(admin_user: Model) -> None:
    today = business_date(now_utc())
    with pytest.raises(OriginatorClaimsValidationError, match="before the next due date"):
        _create(admin_user, today=today, suffix="P2", deadline_days=29, publish=False)
    with pytest.raises(OriginatorClaimsValidationError, match="day-count convention"):
        _create(admin_user, today=today, suffix="P3", convention="", publish=False)


@pytest.mark.django_db
def test_orders_reserve_the_price_and_the_close_pays_it_to_the_originator(
    admin_user: Model, investor: Model
) -> None:
    today = business_date(now_utc())
    result = _create(admin_user, today=today, suffix="P4")
    profile = OriginatorLoanProfile.objects.get(pk=result.profile.pk)
    accrued = accrued_interest_for_principal(profile, 200_000)
    assert accrued > 0
    order = _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=200_000,
        deposit_minor=250_000,
        suffix="P4",
    )
    order.refresh_from_db()
    principal = int(order.allocated_amount_minor)
    reserved = principal + accrued
    assert principal == 200_000
    assert order.metadata["price_accrued_interest_minor"] == accrued
    assert int(order.metadata["reserved_amount_minor"]) == reserved
    ledger = import_module("backend.apps.ledger.services")
    balance = ledger.summarize_investor_balance(investor_user_id=str(investor.pk), currency="CHF")
    assert balance.total_available_minor == 250_000 - reserved

    _close_originator_at_as_of(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today + timedelta(days=6),
            close_reason="Funding deadline reached.",
            idempotency_key="accrued-P4-close",
        )
    )
    purchase = OriginatorClaimPurchase.objects.get(loan_profile=profile)
    assert purchase.cash_consideration_minor == reserved
    assert purchase.originator_payable_minor == reserved
    assert purchase.assigned_principal_minor == principal
    first = purchase.entitlements.order_by("due_date").first()
    assert first is not None and first.due_date == today + timedelta(days=30)
    # The whole next installment's interest share goes to the investor (70% of the pro-rata).
    assert first.expected_interest_minor == round(10_000 * principal / 1_000_000 * 0.7)
    holding = cast(Any, purchase.holding)
    assert holding.original_principal_minor == principal


@pytest.mark.django_db
def test_a_due_date_before_the_settlement_fails_the_offer_and_releases_the_money(
    admin_user: Model, investor: Model
) -> None:
    today = business_date(now_utc())
    result = _create(admin_user, today=today, suffix="P5", deadline_days=5)
    _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=150_000,
        deposit_minor=180_000,
        suffix="P5",
    )
    profile = OriginatorLoanProfile.objects.get(pk=result.profile.pk)
    # The round stays open (paused by an admin) until the next due date passes.
    profile.is_on_hold = True
    profile.hold_reason = "Investigating"
    profile.save(update_fields=["is_on_hold", "hold_reason"])
    due = cast(date, profile.price_next_due_date)
    with patch("backend.apps.marketplace_primary.services.now_utc") as clock:
        clock.return_value = datetime.combine(due, time(12), UTC)
        actions = _scan_originator_at_as_of(actor=admin_user, as_of_date=due)

    assert {"loan_id": str(result.loan.id), "reason": "offer_failed_due_date"} in actions
    profile.refresh_from_db()
    assert profile.opportunity_status == OriginatorOpportunityStatus.CANCELLED
    assert OriginatorClaimEvent.objects.filter(
        loan_id=result.loan.id, event_type=OriginatorClaimEventType.OFFER_FAILED
    ).exists()
    ledger = import_module("backend.apps.ledger.services")
    balance = ledger.summarize_investor_balance(investor_user_id=str(investor.pk), currency="CHF")
    assert balance.total_available_minor == 180_000
    assert OutboxMessage.objects.filter(topic="email.originator_subscription_cancelled").exists()


@pytest.mark.django_db
def test_an_admin_records_a_borrower_payment_during_the_offer(
    admin_user: Model, investor: Model
) -> None:
    today = business_date(now_utc())
    result = _create(admin_user, today=today, suffix="P6")
    _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=120_000,
        suffix="P6",
    )
    client = Client()
    client.force_login(cast(Any, admin_user))
    response = client.post(
        f"/api/v1/originator-claims/admin/loans/{result.loan.id}/offer-failed/",
        {"cause": "payment"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.json()
    assert response.json()["opportunity_status"] == "cancelled"
    again = client.post(
        f"/api/v1/originator-claims/admin/loans/{result.loan.id}/offer-failed/",
        {"cause": "payment"},
        content_type="application/json",
    )
    assert again.status_code == 400


@pytest.mark.django_db
def test_a_coming_soon_offer_is_listed_and_the_opening_alert_goes_out_at_publication(
    admin_user: Model, investor: Model
) -> None:
    today = business_date(now_utc())
    result = _create(admin_user, today=today, suffix="P7", publish=False)
    loans = import_module("backend.apps.loans.services")
    loans.announce_loan_coming_soon(
        loans.AnnounceComingSoonCommand(
            actor=admin_user, loan_id=str(result.loan.id), planned_opening_date=today
        )
    )
    marketplace = import_module("backend.apps.marketplace_primary.services")
    import_module(
        "backend.apps.originator_claims.tests.test_originator_claims"
    )._approve_financial_access(investor)
    coming = marketplace.list_coming_soon_marketplace_loans(actor=investor)
    assert [row["loan_id"] for row in coming] == [str(result.loan.id)]
    assert coming[0]["opportunity_status"] == "coming_soon"
    marketplace.set_loan_opening_alert(actor=investor, loan_id=str(result.loan.id), wanted=True)

    publish_originator_loan(
        PublishOriginatorLoanCommand(
            actor=admin_user, loan_id=str(result.loan.id), as_of_date=today
        )
    )
    assert (
        OutboxMessage.objects.filter(
            topic="email.loan_opening_alert", payload__loan_id=str(result.loan.id)
        ).count()
        == 1
    )
