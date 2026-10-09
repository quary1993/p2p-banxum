"""An external FX settlement is recorded after the bank executed it (audit A-08 leftover)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest
from django.db.models import Model
from django.utils import timezone

from backend.apps.fx.models import FxExternalSettlement
from backend.apps.fx.services import (
    DeclareFxExternalSettlementCommand,
    ExecuteFxQuoteCommand,
    FxValidationError,
    declare_fx_external_settlement,
    execute_fx_quote,
    issue_fx_quote,
)
from backend.apps.fx.tests.test_fx import (  # noqa: F401
    _approve_financial_access,
    _as_of,
    _deposit,
    _quote_command,
    _sensitive_code_payload,
    admin_user,
    investor,
)
from backend.apps.platform_core.domain.time import business_date


@pytest.mark.django_db
def test_fx_external_settlement_refuses_future_value_and_booking_dates(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    _approve_financial_access(investor)
    _deposit(admin_user, investor, amount_minor=12_000_00, idempotency_key="fx-dates-deposit")
    as_of = _as_of()
    quote = issue_fx_quote(
        _quote_command(
            investor, amount_minor=12_000_00, idempotency_key="fx-dates-quote", as_of=as_of
        )
    )
    execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-dates-execute",
            as_of=as_of,
            **_sensitive_code_payload(investor, "fx"),
        )
    )
    tomorrow = business_date(timezone.now()) + timedelta(days=1)
    command = DeclareFxExternalSettlementCommand(
        actor=admin_user,
        sold_currency="CHF",
        bought_currency="EUR",
        sold_amount_minor=12_000_00,
        bought_amount_minor=13_180_00,
        start_date=as_of.date(),
        end_date=as_of.date(),
        booking_date=date(2026, 1, 10),
        value_date=tomorrow,
        collection_account_identifier="FX-COLLECTION",
        bank_reference="FX-BANK-DATES",
        idempotency_key="fx-dates-settlement",
        as_of=as_of,
    )

    with pytest.raises(FxValidationError, match="Value date cannot be in the future"):
        declare_fx_external_settlement(command)
    with pytest.raises(FxValidationError, match="Booking date cannot be in the future"):
        declare_fx_external_settlement(
            replace(command, value_date=date(2026, 1, 10), booking_date=tomorrow)
        )
    assert not FxExternalSettlement.objects.exists()

    settlement = declare_fx_external_settlement(replace(command, value_date=date(2026, 1, 10)))
    assert settlement.value_date == date(2026, 1, 10)
