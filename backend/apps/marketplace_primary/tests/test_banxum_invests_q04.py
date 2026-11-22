# IP of Webby-Soft SRL.
"""Q04 (2026-11-13): the "Banxum invests" label, without an amount.

A loan shows it while a Garanta investor account (named in a platform setting) has a confirmed
reservation, and after closing while it holds the participation; a released reservation removes it.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model

from backend.apps.marketplace_primary.services import (
    BANXUM_INVESTOR_EMAILS_SETTING,
    ReleasePrimaryInvestmentOrderCommand,
    banxum_invests_loan_ids,
    get_full_marketplace_loan,
    list_investor_marketplace_loans,
    release_primary_order_balance,
)
from backend.apps.marketplace_primary.tests.test_primary_marketplace import (  # noqa: F401
    _approve_financial_access,
    _create_and_allocate_order,
    _create_published_loan,
    _declare_deposit,
    admin_user,
    investor,
)
from backend.apps.platform_core.models import PlatformSetting

pytestmark = pytest.mark.django_db


def _garanta_account() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="garanta-invests@example.test",
            full_name="Garanta Finanzgruppe AG",
            account_type="legal_entity_lender_representative",
            status="active",
            is_staff=False,
        ),
    )


def test_label_follows_the_confirmed_reservation_of_a_garanta_account(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    garanta = _garanta_account()
    _approve_financial_access(investor)
    _approve_financial_access(garanta)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    loan_id = str(cast(Any, loan).pk)
    _declare_deposit(admin_user, garanta, amount_minor=10_000_00, idempotency_key="q04-dep")
    order = _create_and_allocate_order(
        investor=garanta, loan=loan, amount_minor=5_000_00, idempotency_prefix="q04"
    )

    # Without the setting no account is a Garanta account.
    assert banxum_invests_loan_ids([loan_id]) == set()
    PlatformSetting.objects.update_or_create(
        key=BANXUM_INVESTOR_EMAILS_SETTING,
        defaults={"value": ["Garanta-Invests@example.test"], "value_type": "json"},
    )

    listed = {row["loan_id"]: row for row in list_investor_marketplace_loans(actor=investor)}
    assert listed[loan_id]["banxum_invests"] is True
    detail = get_full_marketplace_loan(actor=investor, loan_id=loan_id)
    assert detail["banxum_invests"] is True
    assert "banxum_amount" not in str(detail)

    release_primary_order_balance(
        ReleasePrimaryInvestmentOrderCommand(
            actor=admin_user,
            order_id=str(order.id),
            reason="Participation cancelled.",
            idempotency_key="q04-release",
        )
    )
    assert get_full_marketplace_loan(actor=investor, loan_id=loan_id)["banxum_invests"] is False
