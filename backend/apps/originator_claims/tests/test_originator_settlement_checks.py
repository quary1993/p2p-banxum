"""LO settlement dates and replays, and the early-receipt message.

- Audit A-08 leftover: an LO settlement cannot be dated after today.
- FINCODE-10: a retry with the same idempotency key but other items is refused.
- NEW-3: a receipt entered before its installment is due says what to do.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from django.db.models import Model
from freezegun import freeze_time

from backend.apps.originator_claims.domain.imports import (
    OriginatorImportValidationError,
    parse_originator_import_csv,
)
from backend.apps.originator_claims.models import OriginatorSettlement
from backend.apps.originator_claims.services import (
    CloseOriginatorSubscriptionRoundCommand,
    FinalizeOriginatorSettlementCommand,
    OriginatorClaimsValidationError,
    finalize_originator_settlement,
    list_outstanding_originator_settlements,
)
from backend.apps.originator_claims.tests.test_originator_claims import (  # noqa: F401
    _allocate_par_subscription,
    _close_originator_at_as_of,
    _create_par_subscription_loan,
    _dated_two_period_csv,
    admin_user,
    investor,
    other_investor,
)

T0 = date(2026, 6, 1)


def _two_purchases(admin: Model, first: Model, second: Model) -> tuple[Any, list[str]]:
    with freeze_time(datetime.combine(T0, time(10), UTC)):
        result = _create_par_subscription_loan(admin_user=admin, today=T0, suffix="SETTLE")
        _allocate_par_subscription(
            admin_user=admin,
            investor=first,
            loan=result.loan,
            today=T0,
            amount_minor=160_000,
            suffix="SETTLE-A",
        )
        _allocate_par_subscription(
            admin_user=admin,
            investor=second,
            loan=result.loan,
            today=T0,
            amount_minor=100_000,
            suffix="SETTLE-B",
        )
    with freeze_time(datetime.combine(T0 + timedelta(days=6), time(10), UTC)):
        _close_originator_at_as_of(
            CloseOriginatorSubscriptionRoundCommand(
                actor=admin,
                loan_id=str(result.loan.id),
                as_of_date=T0 + timedelta(days=6),
                close_reason="Funding deadline reached.",
                idempotency_key="settle-close",
            )
        )
        queue = list_outstanding_originator_settlements(actor=admin)
    assert len(queue) == 1
    assert len(queue[0]["purchase_ids"]) == 2
    return queue[0], list(queue[0]["purchase_ids"])


@pytest.mark.django_db
def test_settlement_refuses_future_dates_and_a_replay_with_other_items(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
    other_investor: Model,  # noqa: F811
) -> None:
    row, purchase_ids = _two_purchases(admin_user, investor, other_investor)
    day = T0 + timedelta(days=7)
    command = FinalizeOriginatorSettlementCommand(
        actor=admin_user,
        originator_id=row["originator_id"],
        currency=row["currency"],
        purchase_ids=[purchase_ids[0]],
        repayment_ids=[],
        booking_date=day,
        value_date=day + timedelta(days=1),
        collection_account_identifier="CH11 83019 GARANTAFI001",
        bank_reference="LO-SETTLE-1",
        payment_reference="LO-SETTLE-1",
        evidence_reference="BANK-STMT-LO-SETTLE-1",
        notes="LO settlement batch.",
        idempotency_key="lo-settlement-1",
    )
    with freeze_time(datetime.combine(day, time(10), UTC)):
        with pytest.raises(
            OriginatorClaimsValidationError, match="Value date cannot be in the future"
        ):
            finalize_originator_settlement(command)
        with pytest.raises(
            OriginatorClaimsValidationError, match="Booking date cannot be in the future"
        ):
            finalize_originator_settlement(
                replace(command, value_date=day, booking_date=day + timedelta(days=1))
            )
        assert not OriginatorSettlement.objects.exists()

        settled = finalize_originator_settlement(replace(command, value_date=day))
        # The same request again returns the same settlement.
        assert finalize_originator_settlement(replace(command, value_date=day)).id == settled.id
        # Old code: returned the old settlement as if both items were settled.
        with pytest.raises(
            OriginatorClaimsValidationError, match="different originator settlement"
        ):
            finalize_originator_settlement(
                replace(command, value_date=day, purchase_ids=purchase_ids)
            )
        queue = list_outstanding_originator_settlements(actor=admin_user)
    assert queue[0]["purchase_ids"] == [purchase_ids[1]]


def test_receipt_recorded_before_its_due_date_explains_what_to_do() -> None:
    today = date(2026, 11, 4)
    first_due = today + timedelta(days=15)
    # The borrower paid installment 1 one day early; the admin enters it with the
    # value date as import as-of date, before the installment is due.
    csv_content = _dated_two_period_csv(today=today, include_payment=True).replace(
        f"payment,LO-PAY-1,,,,{first_due.isoformat()}",
        f"payment,LO-PAY-1,,,,{(first_due - timedelta(days=1)).isoformat()}",
    )
    with pytest.raises(OriginatorImportValidationError) as error:
        parse_originator_import_csv(
            csv_content=csv_content,
            original_principal_minor=1_000_000,
            as_of_date=first_due - timedelta(days=1),
        )
    message = str(error.value)
    # Old message: "Future schedule principal must equal current outstanding principal."
    assert "Installment 1 is due on 2026-11-19" in message
    assert "import as-of date on or after 2026-11-19" in message

    parsed = parse_originator_import_csv(
        csv_content=csv_content,
        original_principal_minor=1_000_000,
        as_of_date=first_due,
    )
    assert parsed.current_outstanding_principal_minor == 500_000
