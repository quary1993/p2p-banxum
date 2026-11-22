"""IP of Webby-Soft SRL. Audit step 6: the Swiss creditor modes on every path.

S6-5 a Swiss financing without a valid UID takes no order, allocation or close; S6-6 a failed
close still counts and blocks a mode change; S6-7 external debts count on the dates they run;
S6-8 a debt or an SNB rate is recorded under the regime lock, and a breach opens a task; S6-10
an order quotes its minimum under the regime lock.
"""

from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.utils import timezone

from backend.apps.marketplace_primary import creditor_regime as regimes
from backend.apps.marketplace_primary.investor_limit import borrower_creditor_ids
from backend.apps.marketplace_primary.services import (
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimaryValidationError,
    create_primary_investment_order,
)
from backend.apps.marketplace_primary.tests.test_primary_marketplace import (
    _create_published_loan,
    _declare_deposit,
)
from backend.apps.marketplace_primary.tests.test_swiss_creditor_modes_18_9 import (  # noqa: F401
    _lender,
    _uid,
    admin_user,
)
from backend.apps.platform_core.domain.time import business_date

_entities_regimes: Any = import_module("backend.apps.entities.creditor_regime")
BorrowerValidationError = import_module("backend.apps.entities.services").BorrowerValidationError


def _debt(admin_user: Model, uid: str, **values: Any) -> Any:  # noqa: F811
    fields: dict[str, Any] = {
        "actor": admin_user,
        "uid": uid,
        "creditor_name": "Private Lender AG",
        "creditor_identification": "CHE-116.281.710",
        "creditor_is_bank": False,
        "financing_id": "PL-1",
        "principal_minor": 50_000_00,
        "currency": "CHF",
        "start_date": business_date(timezone.now()),
        "declaration_reference": "Signed declaration",
    }
    fields.update(values)
    return _entities_regimes.record_external_debt(
        _entities_regimes.RecordExternalDebtCommand(**fields)
    )


def _order(investor: Model, loan: Model, key: str, amount_minor: int = 10_000_00) -> Any:
    return create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor, loan_id=str(loan.pk), amount_minor=amount_minor, idempotency_key=key
        )
    )


@pytest.mark.django_db
def test_a_swiss_financing_without_a_uid_takes_no_order_and_no_close(admin_user: Model) -> None:  # noqa: F811
    """Audit S6-5: a loan published before 18.9 without a UID is stopped, never guessed; an
    operations task asks for the UID."""
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    apps.get_model("entities", "BorrowerEntity").objects.filter(
        pk=cast(Any, loan).borrower_id
    ).update(uid="")
    investor = _lender("no-uid")
    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="no-uid-d")

    with pytest.raises(MarketplacePrimaryValidationError, match="no valid UID"):
        _order(investor, loan, "no-uid-order")
    with pytest.raises(regimes.CreditorRegimeViolation, match="no valid UID"):
        regimes.check_before_close(loan, on=business_date(timezone.now()))
    assert [str(row.pk) for row in regimes.swiss_loans_without_uid()] == [str(loan.pk)]
    assert regimes.open_missing_uid_tasks(actor=admin_user) == [str(loan.pk)]
    task = apps.get_model("admin_ops", "AdminTask").objects.get(
        related_object_type="SwissBorrowerUidMissing", related_object_id=str(loan.pk)
    )
    assert task.status == "open"


@pytest.mark.django_db
def test_a_failed_close_still_counts_and_blocks_a_mode_change(admin_user: Model) -> None:  # noqa: F811
    """Audit S6-6: a failed close keeps its reservations; its amount stays in the total and the
    mode cannot change while it is unresolved."""
    loan = _create_published_loan(admin_user, principal_minor=120_000_00)
    uid = _uid(loan)
    cast(Any, loan).status = "funding_close_failed"
    cast(Any, loan).save(update_fields=["status"])
    today = business_date(timezone.now())

    assert regimes.borrower_total_chf_minor(uid, on=today) == 120_000_00
    with pytest.raises(BorrowerValidationError, match="in funding"):
        _entities_regimes.set_creditor_mode(
            _entities_regimes.SetCreditorModeCommand(actor=admin_user, uid=uid, mode="ten_twenty")
        )


@pytest.mark.django_db
def test_external_debts_count_on_the_dates_they_run(admin_user: Model) -> None:  # noqa: F811
    """Audit S6-7: started on or before the date, and not ended (the end date is the first day
    without the debt). The same for the creditor counts."""
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    cast(Any, loan).status = "active"
    cast(Any, loan).save(update_fields=["status"])
    uid = _uid(loan)
    today = business_date(timezone.now())
    future = _debt(admin_user, uid, financing_id="F-1", start_date=today + timedelta(days=10))
    running = _debt(
        admin_user,
        uid,
        financing_id="F-2",
        creditor_identification="CHE-109.322.551",
        start_date=today - timedelta(days=30),
    )
    _entities_regimes.end_external_debt(
        actor=admin_user, debt_id=str(running.id), ended_on=today + timedelta(days=15)
    )

    def total(on: Any) -> int:
        return int(regimes.borrower_total_chf_minor(uid, on=on))

    def external(on: Any) -> int:
        return len([c for c in borrower_creditor_ids(uid, on=on) if c.startswith("external:")])

    # Today: the loan and the running debt; the future debt not yet.
    assert total(today) == 150_000_00 and external(today) == 1
    # From the future debt's start both debts count, until the running one ends.
    assert total(future.start_date) == 200_000_00 and external(future.start_date) == 2
    assert total(today + timedelta(days=14)) == 200_000_00
    end_day = today + timedelta(days=15)
    assert total(end_day) == 150_000_00 and external(end_day) == 1
    # A past date still sees a debt ended later.
    assert total(today - timedelta(days=1)) == 150_000_00


@pytest.mark.django_db
def test_a_breaching_debt_is_recorded_under_the_lock_and_opens_a_task(
    admin_user: Model,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit S6-8: the debt is true, so it is recorded; the regime row is locked first; the
    breach opens a task and the close then stops at its own check."""
    loan = _create_published_loan(admin_user, principal_minor=460_000_00)
    uid = _uid(loan)
    locked: list[str] = []
    original = _entities_regimes._lock_regime

    def spy(value: str) -> Any:
        locked.append(value)
        return original(value)

    monkeypatch.setattr(_entities_regimes, "_lock_regime", spy)
    debt = _debt(admin_user, uid, principal_minor=60_000_00)

    assert locked == [uid]
    assert debt.pk is not None
    task = apps.get_model("admin_ops", "AdminTask").objects.get(
        related_object_type="SwissCreditorRegime", related_object_id=uid
    )
    assert "below CHF 500,000" in task.notes
    with pytest.raises(regimes.CreditorRegimeViolation, match="below CHF 500,000"):
        regimes.check_before_close(loan, on=business_date(timezone.now()))


@pytest.mark.django_db
def test_an_snb_rate_change_locks_the_regimes_and_flags_a_breach(admin_user: Model) -> None:  # noqa: F811
    loan = _create_published_loan(admin_user, principal_minor=480_000_00, currency_code="EUR")
    uid = _uid(loan)
    today = business_date(timezone.now())
    _entities_regimes.set_creditor_mode(
        _entities_regimes.SetCreditorModeCommand(actor=admin_user, uid=uid, mode="sandbox")
    )
    _entities_regimes.record_snb_rate(
        actor=admin_user, currency="EUR", rate_date=today, chf_per_unit="0.95", source="SNB"
    )
    tasks = apps.get_model("admin_ops", "AdminTask").objects.filter(
        related_object_type="SwissCreditorRegime", related_object_id=uid
    )
    assert not tasks.exists()  # 480,000 x 0.95 = 456,000 CHF
    _entities_regimes.record_snb_rate(
        actor=admin_user, currency="EUR", rate_date=today, chf_per_unit="1.05", source="SNB"
    )
    assert tasks.count() == 1  # 504,000 CHF


@pytest.mark.django_db
def test_an_order_quotes_its_minimum_under_the_regime_lock(
    admin_user: Model,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit S6-10: the order takes the borrower's regime lock before the minimum is worked out
    and records the quoted inputs; the allocation checks them again."""
    loan = _create_published_loan(admin_user, principal_minor=100_000_00)
    investor = _lender("order-lock")
    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="lock-d")
    calls: list[str] = []
    original = regimes.lock_borrower

    def spy(value: Model) -> Any:
        calls.append(str(value.pk))
        return original(value)

    monkeypatch.setattr(regimes, "lock_borrower", spy)
    order = _order(investor, loan, "lock-order")

    assert calls == [str(loan.pk)]
    assert order.metadata["quoted_creditor_mode"] == "sandbox"
    assert order.metadata["quoted_minimum_minor"] > 0
