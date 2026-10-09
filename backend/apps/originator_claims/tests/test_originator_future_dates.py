"""LO borrower receipts cannot be dated after the platform business date."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.utils import timezone

from backend.apps.originator_claims.models import OriginatorBorrowerRepayment
from backend.apps.originator_claims.services import (
    OriginatorClaimsValidationError,
    RecordOriginatorBorrowerRepaymentCommand,
    record_originator_borrower_repayment,
)
from backend.apps.originator_claims.tests.test_originator_claims import (
    _create_dated_originator_loan,
    _dated_two_period_csv,
    _record_originator_repayment_at_as_of,
)
from backend.apps.platform_core.domain.time import business_date


@pytest.mark.django_db
def test_originator_receipt_refuses_future_value_booking_and_as_of_dates() -> None:
    user_model: Any = get_user_model()
    admin = cast(
        Model,
        user_model.objects.create_user(
            email="lo-future-admin@example.test",
            password="AdminPass123!",
            full_name="LO Future Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )
    today = business_date(timezone.now())
    first_due = today + timedelta(days=15)
    result = _create_dated_originator_loan(admin_user=admin, today=today, suffix="FUTURE")
    command = RecordOriginatorBorrowerRepaymentCommand(
        actor=admin,
        loan_id=str(result.loan.id),
        csv_content=_dated_two_period_csv(today=today, include_payment=True),
        source_filename="future-receipt.csv",
        as_of_date=first_due,
        payment_reference="LO-PAY-1",
        booking_date=first_due,
        value_date=first_due,
        collection_account_identifier="CH11 83019 GARANTAFI001",
        payer_name="Confidential Borrower FUTURE AG",
        idempotency_key="originator-future-receipt",
    )

    with pytest.raises(OriginatorClaimsValidationError, match="Value date cannot be in the future"):
        record_originator_borrower_repayment(command)
    with pytest.raises(
        OriginatorClaimsValidationError,
        match="Booking date cannot be in the future",
    ):
        record_originator_borrower_repayment(replace(command, value_date=today, as_of_date=today))
    with pytest.raises(
        OriginatorClaimsValidationError,
        match="Import as-of date cannot be in the future",
    ):
        record_originator_borrower_repayment(
            replace(command, value_date=today, booking_date=today)
        )
    assert not OriginatorBorrowerRepayment.objects.exists()

    # The same receipt is accepted once the platform clock reaches its bank dates.
    repayment = _record_originator_repayment_at_as_of(command)
    assert repayment.value_date == first_due
