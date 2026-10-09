"""Bank receipts and status scans cannot be dated after the platform business date."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from freezegun import freeze_time

from backend.apps.servicing.models import BorrowerRepaymentEvent, LoanRecoveryEvent
from backend.apps.servicing.services import (
    RecordLoanRecoveryPaymentCommand,
    ScanLoanServicingStatusesCommand,
    ServicingValidationError,
    record_borrower_repayment,
    record_loan_recovery_payment,
    scan_loan_servicing_statuses,
)
from backend.apps.servicing.tests.test_servicing_repayments import (
    _funded_loan_with_holdings,
    _repayment_command,
)


def _user(email: str, account_type: str) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            password="AdminPass123!" if account_type == "admin" else None,
            full_name=email.split("@")[0],
            account_type=account_type,
            status="active",
            is_staff=account_type == "admin",
        ),
    )


@pytest.fixture
def loan_setup() -> tuple[Model, Model]:
    admin = _user("future-admin@example.test", "admin")
    investor_one = _user("future-investor-1@example.test", "natural_person_lender")
    investor_two = _user("future-investor-2@example.test", "natural_person_lender")
    return admin, _funded_loan_with_holdings(admin, investor_one, investor_two)


def _recovery_command(
    admin: Model, loan: Model, *, value: date
) -> RecordLoanRecoveryPaymentCommand:
    return RecordLoanRecoveryPaymentCommand(
        actor=admin,
        loan_id=str(loan.pk),
        gross_recovered_minor=1_000_00,
        externally_deducted_costs_minor=0,
        third_party_costs_from_received_minor=0,
        recovery_fee_applied=False,
        recovery_fee_bps=0,
        contractual_interest_due_minor=500_00,
        default_interest_due_minor=0,
        penalties_due_minor=0,
        booking_date=value,
        value_date=value,
        collection_account_identifier="CH00GARANTARECOVERY",
        payer_name="Recovery counsel",
        idempotency_key=f"future-recovery-{value.isoformat()}",
    )


@pytest.mark.django_db
def test_status_scan_refuses_a_future_as_of_date(
    client: Client,
    loan_setup: tuple[Model, Model],
) -> None:
    admin, loan = loan_setup
    with freeze_time("2026-03-05T11:00:00Z"):
        with pytest.raises(ServicingValidationError, match="cannot run for a future date"):
            scan_loan_servicing_statuses(
                ScanLoanServicingStatusesCommand(
                    actor=admin,
                    as_of_date=date(2026, 3, 16),
                    loan_ids=(str(loan.pk),),
                )
            )
        client.force_login(cast(Any, admin))
        response = client.post(
            "/api/v1/servicing/admin/status-scan/",
            data={"as_of_date": "2026-06-01"},
            content_type="application/json",
        )
        loan.refresh_from_db()
        assert response.status_code == 400
        assert "cannot run for a future date" in response.json()["detail"]
        assert cast(Any, loan).status == "active"

        today = scan_loan_servicing_statuses(
            ScanLoanServicingStatusesCommand(
                actor=admin,
                as_of_date=date(2026, 3, 5),
                loan_ids=(str(loan.pk),),
            )
        )

    assert [change.new_status for change in today.changes] == ["late"]


@pytest.mark.django_db
def test_regular_and_advance_repayments_refuse_future_value_and_booking_dates(
    loan_setup: tuple[Model, Model],
) -> None:
    admin, loan = loan_setup
    with freeze_time("2026-02-20T11:00:00Z"):
        # A future value date no longer skips the early-installment acknowledgement.
        with pytest.raises(ServicingValidationError, match="Value date cannot be in the future"):
            record_borrower_repayment(
                _repayment_command(
                    admin,
                    loan,
                    booking_date=date(2026, 2, 20),
                    value_date=date(2026, 2, 28),
                    idempotency_key="future-regular-value",
                )
            )
        with pytest.raises(ServicingValidationError, match="Booking date cannot be in the future"):
            record_borrower_repayment(
                _repayment_command(
                    admin,
                    loan,
                    booking_date=date(2026, 2, 21),
                    value_date=date(2026, 2, 20),
                    idempotency_key="future-regular-booking",
                )
            )
        with pytest.raises(ServicingValidationError, match="Value date cannot be in the future"):
            record_borrower_repayment(
                _repayment_command(
                    admin,
                    loan,
                    amount_minor=1_000_00,
                    booking_date=date(2026, 2, 20),
                    value_date=date(2026, 3, 22),
                    repayment_in_advance=True,
                    borrower_repayment_bank_date=date(2026, 2, 20),
                    idempotency_key="future-advance-value",
                )
            )
        assert not BorrowerRepaymentEvent.objects.exists()
        with pytest.raises(ServicingValidationError, match="more than one day before"):
            record_borrower_repayment(
                _repayment_command(
                    admin,
                    loan,
                    booking_date=date(2026, 2, 20),
                    value_date=date(2026, 2, 20),
                    idempotency_key="today-regular",
                )
            )


@pytest.mark.django_db
def test_recovery_refuses_a_future_value_date(loan_setup: tuple[Model, Model]) -> None:
    admin, loan = loan_setup
    with freeze_time("2026-03-20T11:00:00Z"):
        scan_loan_servicing_statuses(
            ScanLoanServicingStatusesCommand(
                actor=admin,
                as_of_date=date(2026, 3, 16),
                loan_ids=(str(loan.pk),),
            )
        )
        with pytest.raises(ServicingValidationError, match="Value date cannot be in the future"):
            record_loan_recovery_payment(_recovery_command(admin, loan, value=date(2026, 4, 9)))
        assert not LoanRecoveryEvent.objects.exists()
        result = record_loan_recovery_payment(
            _recovery_command(admin, loan, value=date(2026, 3, 20))
        )

    assert result.recovery_event.contractual_interest_recovered_minor == 500_00
