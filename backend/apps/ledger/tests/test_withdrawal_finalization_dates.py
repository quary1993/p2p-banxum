"""A withdrawal payout is recorded after the bank sent it (audit A-08 leftover)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from django.db.models import Model
from django.utils import timezone

from backend.apps.ledger.models import InvestorWithdrawalRequestStatus
from backend.apps.ledger.services import (
    FinalizeInvestorWithdrawalCommand,
    LedgerValidationError,
    RequestInvestorWithdrawalCommand,
    declare_lender_deposit,
    finalize_investor_withdrawal,
    request_investor_withdrawal,
)
from backend.apps.ledger.tests.test_ledger_foundation import (  # noqa: F401
    _approve_financial_access,
    _deposit_command,
    _register_verified_iban,
    _sensitive_code_payload,
    admin_user,
    investor,
)
from backend.apps.platform_core.domain.time import business_date


@pytest.mark.django_db
def test_withdrawal_finalization_refuses_future_value_and_booking_dates(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    _approve_financial_access(investor)
    _register_verified_iban(admin_user, investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    withdrawal_request = request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=60_00,
            currency="CHF",
            destination_iban="CH9300762011623852957",
            idempotency_key="withdrawal-future-dates",
            **_sensitive_code_payload(investor, "withdrawal"),
        )
    )
    today = business_date(timezone.now())
    command = FinalizeInvestorWithdrawalCommand(
        actor=admin_user,
        withdrawal_request_id=str(withdrawal_request.id),
        booking_date=today,
        value_date=today + timedelta(days=1),
        collection_account_identifier="CH00GARANTALEDGER",
        idempotency_key="bank-withdrawal-future",
    )

    with pytest.raises(LedgerValidationError, match="Value date cannot be in the future"):
        finalize_investor_withdrawal(command)
    with pytest.raises(LedgerValidationError, match="Booking date cannot be in the future"):
        finalize_investor_withdrawal(
            replace(command, value_date=today, booking_date=today + timedelta(days=1))
        )
    withdrawal_request.refresh_from_db()
    assert withdrawal_request.status == InvestorWithdrawalRequestStatus.REQUESTED

    finalized = finalize_investor_withdrawal(replace(command, value_date=today))
    assert finalized.withdrawal_request.status == InvestorWithdrawalRequestStatus.FINALIZED
