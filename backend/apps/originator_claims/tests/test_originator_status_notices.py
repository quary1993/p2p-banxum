"""Current holders of a Loan Originator claim get one notice when the loan turns Late (day 15)
and one when it turns Defaulted (day 60), U33-DEC-09."""

from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.utils import timezone
from freezegun import freeze_time

from backend.apps.originator_claims.tests.test_originator_claims import (  # noqa: F401
    _create_dated_originator_loan,
    _scan_originator_at_as_of,
    admin_user,
    investor,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.tests.notices import assert_renders_to, investor_notices


@pytest.mark.django_db
def test_originator_loan_late_and_default_notify_the_current_holder_once_each(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    today = business_date(timezone.now())
    result: Any = _create_dated_originator_loan(admin_user=admin_user, today=today, suffix="NTC")
    holding = apps.get_model("holdings", "InvestorLoanHolding").objects.create(
        loan=result.loan,
        investor_user_id=investor.pk,
        source_type="originator_claim",
        source_id="notice-claim-1",
        status="active",
        original_principal_minor=2_500_00,
        current_principal_minor=2_500_00,
        currency=result.loan.currency,
        loan_share_ppm=250_000,
        assignment_effective_at=timezone.now(),
        created_by_admin_id=admin_user.pk,
        idempotency_key="notice-claim-holding-1",
    )

    # The first installment is due 15 days after today. U33-DEC-09: day 14 is still due, day
    # 15 is Late, day 60 is Default.
    for days in (29, 30, 31):
        _scan_originator_at_as_of(actor=admin_user, as_of_date=today + timedelta(days=days))
    notices = investor_notices(investor, "email.loan_status_changed")
    assert [notice.payload["metadata"]["new_status"] for notice in notices] == ["late"]
    late = notices[0]
    assert late.payload["subject"] == f"Loan payment late: {result.loan.title}"
    assert ["Your current principal", "CHF 2'500.00"] in late.payload["data_rows"]
    assert ["Status date", (today + timedelta(days=30)).isoformat()] in late.payload["data_rows"]
    assert late.payload["metadata"]["navigation_target_id"] == str(holding.id)
    assert_renders_to(late, investor, "CHF 2'500.00")

    for days in (75, 76):
        _scan_originator_at_as_of(actor=admin_user, as_of_date=today + timedelta(days=days))
    # 18.6: the scan never declares Default; the admin does, and the declaration notifies.
    notices = investor_notices(investor, "email.loan_status_changed")
    assert [notice.payload["metadata"]["new_status"] for notice in notices] == ["late"]
    declared_day = today + timedelta(days=76)
    with freeze_time(f"{declared_day.isoformat()}T11:00:00Z"):
        engine = import_module("backend.apps.servicing.engine")
        engine.declare_loan_default(
            engine.DeclareLoanDefaultCommand(actor=admin_user, loan_id=str(result.loan.id))
        )
    notices = investor_notices(investor, "email.loan_status_changed")
    assert [notice.payload["metadata"]["new_status"] for notice in notices] == [
        "late",
        "defaulted",
    ]
    assert notices[1].payload["subject"] == f"Loan in default: {result.loan.title}"
    assert_renders_to(notices[1], investor, "recovery process")


@pytest.mark.django_db
def test_claim_offers_close_from_the_due_date_until_the_installment_is_paid(
    admin_user: Model,  # noqa: F811
) -> None:
    """C03 (Vlad, 2026-11-17): the offer closes on the due date of an unpaid installment, not at
    the Late day (an import that records the payment reopens it)."""
    from importlib import import_module

    services = import_module("backend.apps.originator_claims.services")
    today = business_date(timezone.now())
    result: Any = _create_dated_originator_loan(
        admin_user=admin_user, today=today, suffix="LTD", final_due_days=200
    )
    profile = result.profile
    profile.refresh_from_db()
    # The first installment is due on day 15 after today.
    due_date = today + timedelta(days=15)

    def reason(as_of: date) -> str:
        return cast(
            str,
            services._originator_opportunity_closed_reason(
                profile, is_par_subscription=False, as_of_date=as_of
            ),
        )

    assert reason(due_date - timedelta(days=1)) == ""
    assert reason(due_date) == services.DUE_INSTALLMENT_UNAVAILABLE_MESSAGE
    assert reason(due_date + timedelta(days=10)) == services.DUE_INSTALLMENT_UNAVAILABLE_MESSAGE
    assert services.originator_loan_ids_with_due_unpaid_installment(
        loans=[profile.loan], as_of_date=due_date
    ) == {str(profile.loan_id)}
    assert (
        services.originator_loan_ids_with_due_unpaid_installment(
            loans=[profile.loan], as_of_date=due_date - timedelta(days=1)
        )
        == set()
    )


def _components(
    principal: int = 0, interest: int = 0, penalty: int = 0, fee: int = 0
) -> dict[str, int]:
    return {
        "principal_minor": principal,
        "interest_minor": interest,
        "penalty_minor": penalty,
        "fee_minor": fee,
    }


@pytest.mark.parametrize(
    ("scheduled", "paid", "import_as_of_offset", "settled"),
    [
        # Audit S1-2: CHF 1,000 interest due, CHF 100 recorded on the due date: still closed.
        (_components(interest=1_000_00), _components(interest=100_00), 0, False),
        # The full catch-up payment reopens it.
        (_components(interest=1_000_00), _components(interest=1_000_00), 0, True),
        # Paid on the due date and reported by an import of the same day.
        (_components(500_000, 10_000), _components(500_000, 10_000), 0, True),
        # An import older than the due date cannot show the payment yet.
        (_components(500_000, 10_000), _components(500_000, 10_000), -1, False),
        # Principal paid in advance covers the later principal, not unpaid interest.
        (_components(500_000, 10_000), _components(1_000_000, 5_000), 3, False),
        (_components(500_000, 10_000), _components(1_000_000, 10_000), 3, True),
        # Scheduled penalty and fee tiers must be paid too.
        (_components(500_000, 10_000, 2_000, 500), _components(500_000, 10_000, 2_000), 0, False),
        (
            _components(500_000, 10_000, 2_000, 500),
            _components(500_000, 10_000, 2_000, 500),
            0,
            True,
        ),
    ],
)
def test_c03_needs_every_due_component_paid(
    scheduled: dict[str, int], paid: dict[str, int], import_as_of_offset: int, settled: bool
) -> None:
    from importlib import import_module

    services = import_module("backend.apps.originator_claims.services")
    due = date(2026, 12, 15)
    assert (
        services.due_installments_settled(
            scheduled=scheduled,
            paid=paid,
            latest_due_date=due,
            import_as_of_date=due + timedelta(days=import_as_of_offset),
        )
        is settled
    )


@pytest.mark.django_db
def test_the_offer_list_reads_the_c03_check_and_the_schedules_once(
    admin_user: Model,  # noqa: F811
) -> None:
    """Audit S1-6: the schedule queries of the list do not grow with the number of offers."""
    from importlib import import_module

    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    services = import_module("backend.apps.originator_claims.services")
    today = business_date(timezone.now())

    def schedule_queries() -> tuple[int, int]:
        with CaptureQueriesContext(connection) as captured:
            payloads = services.list_open_originator_marketplace_payloads()
        count = sum(
            "originatorloanschedulerow" in query["sql"].lower()
            or "originatorloanpaymentrow" in query["sql"].lower()
            for query in captured.captured_queries
        )
        return len(payloads), count

    _create_dated_originator_loan(admin_user=admin_user, today=today, suffix="NQ1")
    one_offer, one_count = schedule_queries()
    for suffix in ("NQ2", "NQ3"):
        _create_dated_originator_loan(admin_user=admin_user, today=today, suffix=suffix)
    three_offers, three_count = schedule_queries()
    assert (one_offer, three_offers) == (1, 3)
    assert three_count == one_count


@pytest.mark.django_db
def test_a_loan_originator_claim_is_never_an_engine_loan(admin_user: Model) -> None:  # noqa: F811
    """Audit S5-7: the new default convention is for direct loans; a claim keeps its source
    convention and its loan is not served by the 18.6 engine."""
    engine = import_module("backend.apps.servicing.engine")
    loans_services = import_module("backend.apps.loans.services")
    today = business_date(timezone.now())
    result: Any = _create_dated_originator_loan(admin_user=admin_user, today=today, suffix="ENG")

    assert result.loan.interest_convention == "legacy_monthly"
    assert not engine.is_engine_loan(result.loan)
    # Also when the field says otherwise, the product decides.
    result.loan.interest_convention = "act_365_fixed"
    assert not engine.is_engine_loan(result.loan)
    assert not loans_services.is_engine_loan(result.loan)
