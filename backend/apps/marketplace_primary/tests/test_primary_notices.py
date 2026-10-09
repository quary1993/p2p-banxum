"""Investor notices for primary orders, funding close (full and partial), cancellation and
admin order release."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import override_settings

from backend.apps.marketplace_primary.services import (
    AllocatePrimaryInvestmentOrderCommand,
    CancelPrimaryLoanFundingCommand,
    ClosePrimaryLoanFundingCommand,
    CreatePrimaryInvestmentOrderCommand,
    ReleasePrimaryInvestmentOrderCommand,
    allocate_primary_order_from_balance,
    cancel_primary_loan_funding,
    create_primary_investment_order,
    release_primary_order_balance,
)
from backend.apps.marketplace_primary.tests.test_primary_marketplace import (  # noqa: F401
    _approve_financial_access,
    _close_primary_at_as_of,
    _create_and_allocate_order,
    _create_primary_acceptance,
    _create_published_loan,
    _declare_deposit,
    _sensitive_code_payload,
    admin_user,
    investor,
)
from backend.apps.platform_core.tests.notices import (
    assert_renders_to,
    investor_notices,
    only_notice,
)

pytestmark = [pytest.mark.django_db]


def _other_investor(email: str) -> Model:
    user = cast(
        Model,
        get_user_model().objects.create_user(
            email=email,
            full_name="Other Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    _approve_financial_access(user)
    return user


@override_settings(PUBLIC_APP_BASE_URL="https://app.banxum.test")
def test_allocated_orders_send_one_notice_with_the_amount_actually_reserved(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    other = _other_investor("notice-alloc-other@example.test")
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    _declare_deposit(admin_user, other, amount_minor=25_000_00, idempotency_key="alloc-dep-o")
    _declare_deposit(admin_user, investor, amount_minor=20_000_00, idempotency_key="alloc-dep-i")
    # The investor's order is created while the loan still has room; another investor then
    # takes most of it, so only CHF 5'000.00 of the CHF 10'000.00 can be reserved.
    pending = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=10_000_00,
            idempotency_key="alloc-part-order",
        )
    )
    _create_and_allocate_order(
        investor=other, loan=loan, amount_minor=25_000_00, idempotency_prefix="alloc-full"
    )
    acceptance = _create_primary_acceptance(
        investor, order_id=str(pending.id), idempotency_key="alloc-part-accept"
    )
    allocate = AllocatePrimaryInvestmentOrderCommand(
        actor=investor,
        order_id=str(pending.id),
        document_acceptance_id=str(acceptance.pk),
        idempotency_key="alloc-part-allocate",
        **_sensitive_code_payload(investor, "primary_investment"),
    )
    order = allocate_primary_order_from_balance(allocate)
    # Replaying the same allocation does not send a second notice.
    allocate_primary_order_from_balance(allocate)

    assert order.allocated_amount_minor == 5_000_00
    full = only_notice(other, "email.primary_investment_confirmation")
    assert full.payload["subject"] == "Investment placed: CHF 25'000.00 in Real estate bridge loan"
    assert full.payload["status_label"] == "Placed"

    partial = only_notice(investor, "email.primary_investment_confirmation")
    body = partial.payload["body_text"]
    assert partial.payload["status_label"] == "Partly placed"
    assert "We reserved CHF 5'000.00" in body
    assert "You asked for CHF 10'000.00" in body
    deadline = cast(Any, loan).funding_deadline.isoformat()
    assert f"Funding closes after {deadline}" in body
    assert partial.payload["metadata"]["allocated_amount_minor"] == 5_000_00
    assert partial.payload["metadata"]["navigation_target"] == "portfolio"
    assert_renders_to(partial, investor, "CHF 5'000.00", "CHF 10'000.00")


def test_full_and_partial_funding_close_notify_each_holder_once(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    other = _other_investor("notice-close-other@example.test")
    _approve_financial_access(investor)
    full_loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    _declare_deposit(admin_user, investor, amount_minor=40_000_00, idempotency_key="close-dep-i")
    _declare_deposit(admin_user, other, amount_minor=10_000_00, idempotency_key="close-dep-o")
    _create_and_allocate_order(
        investor=investor, loan=full_loan, amount_minor=12_000_00, idempotency_prefix="c-i1"
    )
    _create_and_allocate_order(
        investor=investor, loan=full_loan, amount_minor=8_000_00, idempotency_prefix="c-i2"
    )
    _create_and_allocate_order(
        investor=other, loan=full_loan, amount_minor=10_000_00, idempotency_prefix="c-o1"
    )
    close_command = ClosePrimaryLoanFundingCommand(
        actor=admin_user,
        loan_id=str(full_loan.pk),
        reason="Fully funded.",
        investor_message="The funding window closed with the minimum subscription met.",
        idempotency_key="notice-full-close",
        as_of_date=date(2030, 1, 11),
    )
    close = _close_primary_at_as_of(close_command)
    _close_primary_at_as_of(close_command)

    # Two orders of the same investor are one notice with the summed investment.
    funded = only_notice(investor, "email.loan_funding_status")
    assert funded.payload["subject"] == "Loan funded: Real estate bridge loan"
    assert "Your investment of CHF 20'000.00 is now active" in funded.payload["body_text"]
    # The resolver's automatic message only explains partial closes.
    assert "Message from" not in funded.payload["body_text"]
    assert ["Closed on", "2030-01-11"] in funded.payload["data_rows"]
    holding_ids = funded.payload["metadata"]["holding_ids"]
    assert len(holding_ids) == 2
    assert funded.payload["metadata"]["navigation_target"] == "holding"
    assert funded.payload["metadata"]["navigation_target_id"] == holding_ids[0]
    assert funded.payload["metadata"]["primary_close_id"] == str(close.id)
    assert_renders_to(funded, investor, "CHF 20'000.00")
    assert (
        "CHF 10'000.00 is now active"
        in only_notice(other, "email.loan_funding_status").payload["body_text"]
    )

    partial_loan = _create_published_loan(
        admin_user, principal_minor=50_000_00, minimum_subscription_bps=2_000
    )
    _create_and_allocate_order(
        investor=investor, loan=partial_loan, amount_minor=15_000_00, idempotency_prefix="p-i1"
    )
    _close_primary_at_as_of(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(partial_loan.pk),
            reason="Partial close.",
            investor_message="The loan closes at the amount subscribed by the deadline.",
            idempotency_key="notice-partial-close",
            as_of_date=date(2030, 1, 11),
        )
    )
    notices = investor_notices(investor, "email.loan_funding_status")
    assert len(notices) == 2
    partial = notices[1]
    assert partial.payload["subject"] == "Loan partly funded: Real estate bridge loan"
    body = partial.payload["body_text"]
    assert "The loan closed at CHF 15'000.00, which is the new loan amount" in body
    assert "Message from BANXUM: The loan closes at the amount subscribed by the deadline." in body
    assert_renders_to(partial, investor, "CHF 15'000.00", "amount subscribed by the deadline")


def test_cancelled_funding_and_admin_release_notify_with_message_and_amount(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    _declare_deposit(admin_user, investor, amount_minor=30_000_00, idempotency_key="cancel-dep")
    released_order = _create_and_allocate_order(
        investor=investor, loan=loan, amount_minor=4_000_00, idempotency_prefix="rel-1"
    )
    _create_and_allocate_order(
        investor=investor, loan=loan, amount_minor=6_000_00, idempotency_prefix="can-1"
    )

    release = ReleasePrimaryInvestmentOrderCommand(
        actor=admin_user,
        order_id=str(released_order.id),
        reason="Internal: investor asked by phone.",
        idempotency_key="notice-release",
    )
    release_primary_order_balance(release)
    release_primary_order_balance(release)
    released = only_notice(investor, "email.primary_order_released")
    assert "We released your CHF 4'000.00 order" in released.payload["body_text"]
    assert "phone" not in str(released.payload)
    assert released.payload["metadata"]["navigation_target"] == "balances"
    assert_renders_to(released, investor, "CHF 4'000.00")

    command = CancelPrimaryLoanFundingCommand(
        actor=admin_user,
        loan_id=str(loan.pk),
        reason="Internal: borrower withdrew.",
        investor_message="The borrower withdrew the request. Your money is back on your balance.",
        idempotency_key="notice-cancel",
    )
    cancel_primary_loan_funding(command)
    cancel_primary_loan_funding(command)
    cancelled = only_notice(investor, "email.loan_funding_status")
    body = cancelled.payload["body_text"]
    assert cancelled.payload["subject"] == "Loan funding cancelled: Real estate bridge loan"
    assert "We released CHF 6'000.00 back to your BANXUM balance." in body
    # The admin's investor message is delivered; the internal reason is not.
    assert "Message from BANXUM: The borrower withdrew the request." in body
    assert "Internal" not in str(cancelled.payload)
    assert cancelled.payload["metadata"]["navigation_target"] == "balances"
    assert_renders_to(cancelled, investor, "CHF 6'000.00", "The borrower withdrew the request.")
    # The release made by the cancellation itself is covered by the cancellation notice.
    assert len(investor_notices(investor, "email.primary_order_released")) == 1
