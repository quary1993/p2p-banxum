"""One borrower bank movement is recorded once (audit A-28 / SERVICING-08).

Like lender deposits: same loan, amount, payer account (spaces and case ignored)
and value date describe the same movement, unless both carry different bank
references. A repeat is refused with 409 until the admin explicitly confirms it.
Also: the Direct recovery endpoint refuses Loan Originator loans (SERVICING-14).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any, cast
from unittest.mock import patch

import pytest
from django.db.models import Model
from django.test import Client

from backend.apps.servicing import services as servicing_services
from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    InvestorRepaymentDistributionLine,
    LoanRecoveryEvent,
)
from backend.apps.servicing.services import (
    RecordLoanRecoveryPaymentCommand,
    ScanLoanServicingStatusesCommand,
    ServicingDuplicatePaymentError,
    ServicingValidationError,
    record_borrower_repayment,
    record_loan_recovery_payment,
    scan_loan_servicing_statuses,
)
from backend.apps.servicing.tests.test_servicing_repayments import (  # noqa: F401
    _funded_loan_with_holdings,
    _repayment_command,
    admin_user,
    investor_one,
    investor_two,
)


def _advance(admin: Model, loan: Model, key: str, **changes: Any) -> Any:
    command = _repayment_command(
        admin,
        loan,
        amount_minor=1_000_00,
        booking_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        repayment_in_advance=True,
        borrower_repayment_bank_date=date(2026, 2, 10),
        idempotency_key=key,
    )
    return record_borrower_repayment(replace(command, **{"bank_reference": "", **changes}))


def _credited_total() -> int:
    return sum(int(line.amount_minor) for line in InvestorRepaymentDistributionLine.objects.all())


@pytest.mark.django_db
def test_same_borrower_payment_twice_is_refused_until_confirmed(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    first = _advance(admin_user, loan, "dup-first")
    credited = _credited_total()

    # Same movement entered again with a new idempotency key; the payer account
    # is typed with spaces and lower case. Old code: recorded and credited twice.
    with pytest.raises(ServicingDuplicatePaymentError) as error:
        _advance(admin_user, loan, "dup-second", payer_account_identifier=" ch22 borrower ")
    assert error.value.duplicate_bank_operation_id == str(first.repayment_event.bank_operation_id)
    assert "Possible duplicate: CHF 1'000.00 from CH22BORROWER" in str(error.value)
    assert BorrowerRepaymentEvent.objects.count() == 1
    assert _credited_total() == credited

    confirmed = _advance(admin_user, loan, "dup-second", confirm_repeat_payment=True)
    assert BorrowerRepaymentEvent.objects.count() == 2
    assert confirmed.repayment_event.metadata["confirmed_repeat_of_bank_operation_ids"] == [
        str(first.repayment_event.bank_operation_id)
    ]
    # An identical retry of the confirmed request is idempotent.
    retried = _advance(admin_user, loan, "dup-second", confirm_repeat_payment=True)
    assert retried.repayment_event.id == confirmed.repayment_event.id


@pytest.mark.django_db
def test_regular_installment_then_same_movement_as_advance_is_a_duplicate(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    regular = _repayment_command(admin_user, loan, idempotency_key="dup-regular")
    record_borrower_repayment(replace(regular, bank_reference=""))
    with pytest.raises(ServicingDuplicatePaymentError):
        record_borrower_repayment(
            replace(
                _repayment_command(
                    admin_user,
                    loan,
                    amount_minor=3_300_00,
                    repayment_in_advance=True,
                    borrower_repayment_bank_date=date(2026, 3, 1),
                    idempotency_key="dup-regular-as-advance",
                ),
                bank_reference="",
            )
        )


@pytest.mark.django_db
def test_other_bank_reference_value_date_or_payer_is_another_payment(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _advance(admin_user, loan, "other-1", bank_reference="BANK-A")
    _advance(admin_user, loan, "other-2", bank_reference="BANK-B")
    _advance(
        admin_user,
        loan,
        "other-3",
        payer_account_identifier="CH33OTHERPAYER",
    )
    _advance(
        admin_user,
        loan,
        "other-4",
        booking_date=date(2026, 2, 11),
        value_date=date(2026, 2, 11),
        borrower_repayment_bank_date=date(2026, 2, 11),
    )
    assert BorrowerRepaymentEvent.objects.count() == 4


@pytest.mark.django_db
def test_duplicate_repayment_api_returns_409_then_201_with_confirmation(
    client: Client,
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    client.force_login(cast(Any, admin_user))
    payload = {
        "loan_id": str(loan.pk),
        "amount_minor": 1_000_00,
        "booking_date": "2026-02-10",
        "value_date": "2026-02-10",
        "payer_name": "Servicing Borrower AG",
        "payer_account_identifier": "CH22BORROWER",
        "collection_account_identifier": "CH00GARANTALEDGER",
        "repayment_in_advance": True,
        "borrower_repayment_bank_date": "2026-02-10",
    }

    def post(key: str, **extra: Any) -> Any:
        return client.post(
            "/api/v1/servicing/admin/borrower-repayments/",
            data={**payload, "idempotency_key": key, **extra},
            content_type="application/json",
        )

    assert post("api-dup-1").status_code == 201
    conflict = post("api-dup-2")
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "duplicate_borrower_payment"
    assert conflict.json()["duplicate_bank_operation_id"]
    assert BorrowerRepaymentEvent.objects.count() == 1
    assert post("api-dup-2", confirm_repeat_payment=True).status_code == 201
    assert BorrowerRepaymentEvent.objects.count() == 2


def _recovery(admin: Model, loan: Model, key: str, **changes: Any) -> Any:
    command = RecordLoanRecoveryPaymentCommand(
        actor=admin,
        loan_id=str(loan.pk),
        gross_recovered_minor=1_000_00,
        externally_deducted_costs_minor=0,
        third_party_costs_from_received_minor=0,
        recovery_fee_applied=False,
        recovery_fee_bps=0,
        contractual_interest_due_minor=0,
        default_interest_due_minor=0,
        penalties_due_minor=0,
        booking_date=date(2026, 3, 20),
        value_date=date(2026, 3, 20),
        collection_account_identifier="CH00GARANTARECOVERY",
        payer_name="Recovery counsel",
        payer_account_identifier="CH0000000000000000009",
        idempotency_key=key,
    )
    return record_loan_recovery_payment(replace(command, **changes))


def _defaulted(admin: Model, loan: Model) -> None:
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin, as_of_date=date(2026, 3, 16), loan_ids=(str(loan.pk),)
        )
    )


@pytest.mark.django_db
def test_same_recovery_receipt_twice_is_refused_until_confirmed(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _defaulted(admin_user, loan)
    _recovery(admin_user, loan, "rec-dup-1")
    with pytest.raises(ServicingDuplicatePaymentError):
        _recovery(admin_user, loan, "rec-dup-2")
    assert LoanRecoveryEvent.objects.count() == 1
    confirmed = _recovery(admin_user, loan, "rec-dup-2", confirm_repeat_payment=True)
    assert confirmed.recovery_event.metadata["confirmed_repeat_of_bank_operation_ids"]
    assert LoanRecoveryEvent.objects.count() == 2


@pytest.mark.django_db
def test_direct_recovery_endpoint_refuses_loan_originator_loans(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _defaulted(admin_user, loan)
    real_locked_loan = servicing_services._locked_loan

    def locked_originator_loan(loan_id: str) -> Model:
        # An LO loan needs originator data the direct fixture does not have; only
        # the product type matters for this guard.
        locked = real_locked_loan(loan_id)
        cast(Any, locked).product_type = "originator_claim"
        return locked

    with (
        patch.object(servicing_services, "_locked_loan", locked_originator_loan),
        pytest.raises(ServicingValidationError, match="Loan Originator servicing workflow"),
    ):
        _recovery(admin_user, loan, "rec-lo")
    assert not LoanRecoveryEvent.objects.exists()
