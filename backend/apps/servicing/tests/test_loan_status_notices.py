"""Current holders of a Direct loan get one notice when it turns Late (day 5) and one when it
turns Defaulted (day 16)."""

from __future__ import annotations

from datetime import date

import pytest
from django.db.models import Model
from django.test import override_settings

from backend.apps.platform_core.tests.notices import (
    assert_renders_to,
    investor_notices,
    only_notice,
)
from backend.apps.servicing.services import (
    ScanLoanServicingStatusesCommand,
    scan_loan_servicing_statuses,
)
from backend.apps.servicing.tests.test_servicing_repayments import (  # noqa: F401
    _funded_loan_with_holdings,
    admin_user,
    investor_one,
    investor_two,
)


def _scan(actor: Model, as_of_date: date) -> None:
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(actor=actor, as_of_date=as_of_date)
    )


@pytest.mark.django_db
@override_settings(PUBLIC_APP_BASE_URL="https://app.banxum.test")
def test_late_and_default_notify_each_current_holder_once(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    for as_of_date in (date(2026, 3, 3), date(2026, 3, 4)):
        _scan(admin_user, as_of_date)
    # Days 1-4 are the grace period: no notice.
    assert not investor_notices(investor_one, "email.loan_status_changed")

    _scan(admin_user, date(2026, 3, 5))
    _scan(admin_user, date(2026, 3, 6))
    late = only_notice(investor_one, "email.loan_status_changed")
    assert late.payload["subject"] == "Loan payment late: Servicing Loan"
    assert "due 5 days ago" in late.payload["body_text"]
    assert ["Your current principal", "CHF 10'000.00"] in late.payload["data_rows"]
    assert ["Status date", "2026-03-05"] in late.payload["data_rows"]
    assert late.payload["metadata"]["navigation_target"] == "holding"
    assert late.payload["metadata"]["loan_id"] == str(loan.pk)
    assert_renders_to(late, investor_one, "Servicing Loan")
    other_late = only_notice(investor_two, "email.loan_status_changed")
    assert ["Your current principal", "CHF 20'000.00"] in other_late.payload["data_rows"]

    for as_of_date in (date(2026, 3, 16), date(2026, 3, 17)):
        _scan(admin_user, as_of_date)
    for holder in (investor_one, investor_two):
        notices = investor_notices(holder, "email.loan_status_changed")
        assert [notice.payload["metadata"]["new_status"] for notice in notices] == [
            "late",
            "defaulted",
        ]
    default = investor_notices(investor_one, "email.loan_status_changed")[1]
    assert default.payload["subject"] == "Loan in default: Servicing Loan"
    assert "for 16 days" in default.payload["body_text"]
    assert ["Status date", "2026-03-16"] in default.payload["data_rows"]
    assert_renders_to(default, investor_one, "recovery process")
