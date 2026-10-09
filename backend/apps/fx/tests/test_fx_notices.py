"""The investor gets one notice for an executed currency exchange."""

from __future__ import annotations

from datetime import date

import pytest
from django.db.models import Model
from django.test import override_settings

from backend.apps.fx.services import ExecuteFxQuoteCommand, execute_fx_quote, issue_fx_quote
from backend.apps.fx.tests.test_fx import (  # noqa: F401 - pytest fixtures
    _approve_financial_access,
    _as_of,
    _deposit,
    _quote_command,
    _sensitive_code_payload,
    admin_user,
    investor,
)
from backend.apps.platform_core.tests.notices import assert_renders_to, only_notice


@pytest.mark.django_db
@override_settings(PUBLIC_APP_BASE_URL="https://app.banxum.test")
def test_executed_exchange_sends_one_notice_with_amounts_rate_fee_and_date(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    _approve_financial_access(investor)
    _deposit(admin_user, investor, amount_minor=1_000_00, value_date=date(2026, 1, 1))
    as_of = _as_of(date(2026, 1, 10), hour=0)
    quote = issue_fx_quote(
        _quote_command(investor, amount_minor=100_00, rate="1.050000", as_of=as_of)
    )
    command = ExecuteFxQuoteCommand(
        actor=investor,
        quote_id=str(quote.id),
        idempotency_key="fx-notice",
        as_of=as_of,
        **_sensitive_code_payload(investor, "fx"),
    )
    exchange = execute_fx_quote(command)
    execute_fx_quote(
        ExecuteFxQuoteCommand(
            actor=investor,
            quote_id=str(quote.id),
            idempotency_key="fx-notice",
            as_of=as_of,
            **_sensitive_code_payload(investor, "fx"),
        )
    )

    notice = only_notice(investor, "email.fx_exchange_confirmation")
    # CHF 100.00 at 1.05 = EUR 105.00 gross; fee 1.5% = EUR 1.58 (half up); net EUR 103.42.
    assert exchange.target_amount_minor == 103_42
    assert notice.payload["subject"] == "Currency exchange completed: CHF 100.00 to EUR 103.42"
    body = notice.payload["body_text"]
    assert "Rate: 1 CHF = 1.0500 EUR" in body
    assert "Fee: EUR 1.58" in body
    # 00:00 on 10 January in Europe/Zurich is still 9 January in UTC: the business date wins.
    assert "Date: 2026-01-10" in body
    assert notice.payload["metadata"]["navigation_target"] == "fx"
    assert notice.payload["buttons"][0]["url"] == "https://app.banxum.test/fx"
    assert_renders_to(notice, investor, "CHF 100.00", "EUR 103.42")
