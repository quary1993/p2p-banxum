"""Current holders of a Loan Originator claim get one notice when the loan turns Late (day 5)
and one when it turns Defaulted (day 16)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.apps import apps
from django.db.models import Model
from django.utils import timezone

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

    # The first installment is due 15 days after today: day 4 is grace, day 5 is Late.
    for days in (19, 20, 21):
        _scan_originator_at_as_of(actor=admin_user, as_of_date=today + timedelta(days=days))
    notices = investor_notices(investor, "email.loan_status_changed")
    assert [notice.payload["metadata"]["new_status"] for notice in notices] == ["late"]
    late = notices[0]
    assert late.payload["subject"] == f"Loan payment late: {result.loan.title}"
    assert ["Your current principal", "CHF 2'500.00"] in late.payload["data_rows"]
    assert ["Status date", (today + timedelta(days=20)).isoformat()] in late.payload["data_rows"]
    assert late.payload["metadata"]["navigation_target_id"] == str(holding.id)
    assert_renders_to(late, investor, "CHF 2'500.00")

    for days in (31, 32):
        _scan_originator_at_as_of(actor=admin_user, as_of_date=today + timedelta(days=days))
    notices = investor_notices(investor, "email.loan_status_changed")
    assert [notice.payload["metadata"]["new_status"] for notice in notices] == [
        "late",
        "defaulted",
    ]
    assert notices[1].payload["subject"] == f"Loan in default: {result.loan.title}"
    assert_renders_to(notices[1], investor, "recovery process")
