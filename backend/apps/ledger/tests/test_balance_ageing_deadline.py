"""Day-60 deadline, forced-return lot choice and future-date guards for balance ageing."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone
from freezegun import freeze_time

from backend.apps.ledger.models import (
    BalanceLotStatus,
    BankOperation,
    InvestorBalanceLot,
    InvestorWithdrawalRequest,
    LedgerJournalEntry,
)
from backend.apps.ledger.services import (
    DeclareLenderDepositCommand,
    ExecuteInvestorFxExchangeLedgerCommand,
    FinalizeBorrowerDisbursementCommand,
    LedgerValidationError,
    RunBalanceAgeingScanCommand,
    declare_lender_deposit,
    execute_investor_fx_exchange_ledger,
    finalize_borrower_disbursement,
    plan_investment_balance_consumption,
    run_balance_ageing_scan,
    summarize_investor_balance,
)
from backend.apps.ledger.tests.test_ledger_foundation import _closed_primary_loan_funding
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import Currency, DomainEvent, OutboxMessage


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="ageing-admin@example.test",
            password="AdminPass123!",
            full_name="Ageing Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    user = cast(
        Model,
        user_model.objects.create_user(
            email="ageing-investor@example.test",
            full_name="Ageing Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )
    now = timezone.now()
    cast(Any, user).phone_verified_at = now
    user.save(update_fields=["phone_verified_at"])
    apps.get_model("kyc_compliance", "KycVerificationCase").objects.update_or_create(
        user_id=user.pk,
        defaults={
            "subject_reference": f"user:{user.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{user.pk}",
            "status": "approved",
            "decision_at": now,
        },
    )
    return user


def _at(value: date, hour: int = 12, minute: int = 0) -> datetime:
    return datetime.combine(value, time(hour, minute), tzinfo=business_timezone())


def _deposit(
    admin_user: Model,
    investor: Model,
    *,
    amount_minor: int,
    currency: str = "CHF",
    value_date: date,
    key: str,
    iban: str = "CH9300762011623852957",
    booking_date: date | None = None,
) -> Any:
    Currency.objects.filter(code=currency).update(is_enabled=True)
    return declare_lender_deposit(
        DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency=currency,
            booking_date=booking_date or value_date,
            value_date=value_date,
            collection_account_identifier="CH00GARANTALEDGER",
            payer_name="Ageing Investor",
            payer_account_identifier=iban,
            bank_reference=f"BANK-{key}",
            payment_reference=f"INV-{key}",
            evidence_reference=f"statement:{key}",
            notes="Matched manually.",
            idempotency_key=key,
        )
    )


def _scan(admin_user: Model, as_of: datetime, *, dry_run: bool = False) -> Any:
    return run_balance_ageing_scan(
        RunBalanceAgeingScanCommand(actor=admin_user, as_of=as_of, dry_run=dry_run)
    )


def _reminder_days(lot_id: Any) -> list[int]:
    return sorted(
        int(payload["day"])
        for payload in DomainEvent.objects.filter(
            event_type="BalanceAgeingReminderDue",
            aggregate_id=str(lot_id),
        ).values_list("payload", flat=True)
    )


def _fx_all_chf_on_day_50(admin_user: Model, investor: Model) -> tuple[Any, Any]:
    """CHF deposit 2026-01-01 (deadline 03-02) converted to EUR on 02-20 (holding day 50);
    a fresh EUR deposit from 02-01 (deadline 04-02) stays untouched by ageing."""
    _deposit(admin_user, investor, amount_minor=1000_00, value_date=date(2026, 1, 1), key="chf")
    eur = _deposit(
        admin_user,
        investor,
        amount_minor=5000_00,
        currency="EUR",
        value_date=date(2026, 2, 1),
        key="eur",
        iban="DE89370400440532013000",
    )
    fx = execute_investor_fx_exchange_ledger(
        ExecuteInvestorFxExchangeLedgerCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            source_currency="CHF",
            target_currency="EUR",
            source_amount_minor=1000_00,
            gross_target_amount_minor=1050_00,
            target_amount_minor=1034_25,
            fee_minor=15_75,
            source_type="test",
            source_id="fx-1",
            idempotency_key="fx-1",
            as_of=_at(date(2026, 2, 20)),
        )
    )
    return fx.target_balance_lot, eur.balance_lot


@pytest.mark.django_db
def test_forced_return_takes_only_the_overdue_fx_lot_and_never_fresh_money(
    admin_user: Model,
    investor: Model,
) -> None:
    fx_lot, fresh_lot = _fx_all_chf_on_day_50(admin_user, investor)
    assert fx_lot.withdrawal_deadline_at == _at(date(2026, 3, 2), 0)

    day = date(2026, 2, 20)
    while day <= date(2026, 3, 2):
        _scan(admin_user, _at(day, 0, 30))
        day += timedelta(days=1)
    # Deadline day: still the investor's last day, nothing is taken yet.
    assert InvestorWithdrawalRequest.objects.filter(is_forced=True).count() == 0

    for _ in range(4):
        _scan(admin_user, _at(day, 0, 30))
        day += timedelta(days=1)

    forced = list(InvestorWithdrawalRequest.objects.filter(is_forced=True))
    fx_lot.refresh_from_db()
    fresh_lot.refresh_from_db()
    assert len(forced) == 1
    assert forced[0].amount_minor == 1034_25
    assert forced[0].requested_at == _at(date(2026, 3, 3), 0, 30)
    assert [item["lot_id"] for item in forced[0].lot_allocations] == [str(fx_lot.id)]
    assert fx_lot.status == BalanceLotStatus.CONSUMED
    assert fx_lot.withdrawn_amount_minor == 1034_25
    assert fresh_lot.status == BalanceLotStatus.AVAILABLE
    assert fresh_lot.available_amount_minor == 5000_00
    assert fresh_lot.withdrawn_amount_minor == 0


@pytest.mark.django_db
def test_fx_lot_reminders_count_back_from_the_inherited_deadline(
    admin_user: Model,
    investor: Model,
) -> None:
    fx_lot, fresh_lot = _fx_all_chf_on_day_50(admin_user, investor)

    day = date(2026, 2, 20)
    while day <= date(2026, 3, 2):
        _scan(admin_user, _at(day, 0, 30))
        day += timedelta(days=1)

    # Day 25 and 46 were before the FX lot existed (they belong to the CHF source lot).
    assert _reminder_days(fx_lot.id) == [53, 58, 59, 60]
    assert _reminder_days(fresh_lot.id) == [25]
    day_60 = DomainEvent.objects.get(
        idempotency_key=f"balance-lot:{fx_lot.id}:ageing-reminder-day:60"
    )
    assert day_60.payload["as_of"] == _at(date(2026, 3, 2), 0, 30).isoformat()


@pytest.mark.django_db
def test_investor_consumption_uses_the_lot_closest_to_its_deadline_first(
    admin_user: Model,
    investor: Model,
) -> None:
    fx_lot, fresh_lot = _fx_all_chf_on_day_50(admin_user, investor)

    plan = plan_investment_balance_consumption(
        investor_user_id=str(investor.pk),
        currency="EUR",
        amount_minor=1500_00,
        loan_funding_deadline=date(2026, 2, 25),
        as_of=_at(date(2026, 2, 21)),
    )

    assert [(line.lot_id, line.amount_minor) for line in plan] == [
        (str(fx_lot.id), 1034_25),
        (str(fresh_lot.id), 465_75),
    ]


@pytest.mark.django_db
def test_deadline_date_is_the_last_day_and_penalty_mode_starts_the_next_day(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(
        admin_user, investor, amount_minor=1000_00, value_date=date(2026, 1, 1), key="dl"
    )
    deposit.payout_instruction.status = "disabled"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])
    lot_id = deposit.balance_lot.id

    day_59 = _scan(admin_user, _at(date(2026, 3, 1), 0, 30))
    assert [reminder.day for reminder in day_59.reminders_due] == [25, 46, 53, 58, 59]
    final = OutboxMessage.objects.get(
        idempotency_key=f"email:balance-lot:{lot_id}:ageing-reminder-day:59"
    ).payload["body_text"]
    assert "Withdrawal deadline: 2026-03-02 (end of day, Europe/Zurich)." in final
    assert "needs a usable IBAN" in final

    # Day 60 (deadline date, both the 00:30 job and the QA-advance 12:00 run): last day.
    for as_of in (_at(date(2026, 3, 2), 0, 30), _at(date(2026, 3, 2), 12)):
        deadline_day = _scan(admin_user, as_of)
        assert deadline_day.penalty_mode_transitions == []
        assert deadline_day.penalty_charges == []
        assert deadline_day.forced_withdrawal_candidates == []
    lot = InvestorBalanceLot.objects.get(id=lot_id)
    assert lot.status == BalanceLotStatus.AVAILABLE
    assert lot.available_amount_minor == 1000_00
    assert _reminder_days(lot_id) == [25, 46, 53, 58, 59, 60]
    summary = summarize_investor_balance(
        investor_user_id=str(investor.pk), currency="CHF", as_of=_at(date(2026, 3, 2))
    )
    assert (summary.investable_minor, summary.withdraw_only_minor, summary.overdue_minor) == (
        0,
        1000_00,
        0,
    )
    day_60_email = OutboxMessage.objects.get(
        idempotency_key=f"email:balance-lot:{lot_id}:ageing-reminder-day:60"
    )
    assert day_60_email.payload["subject"] == (
        "Last day: your BANXUM balance reaches the 60-day limit today"
    )
    body = day_60_email.payload["body_text"]
    assert "reaches the 60-day holding limit today, 2026-03-02" in body
    assert "by the end of today" in body
    assert "penalty mode and is charged a penalty of 1% per day" in body
    assert "frozen until you add a usable IBAN" in body
    assert "You can invest" not in body

    day_61 = _scan(admin_user, _at(date(2026, 3, 3), 0, 30))
    lot.refresh_from_db()
    assert day_61.reminders_due == []
    assert [transition.days_overdue for transition in day_61.penalty_mode_transitions] == [1]
    assert [(charge.charge_date, charge.amount_minor) for charge in day_61.penalty_charges] == [
        (date(2026, 3, 3), 10_00)
    ]
    assert lot.status == BalanceLotStatus.PENALTY_MODE
    assert lot.available_amount_minor == 990_00
    assert (
        LedgerJournalEntry.objects.filter(event_type="balance_penalty_charged").count() == 1
    )


@pytest.mark.django_db
def test_lot_found_overdue_gets_no_contradicting_reminders(
    admin_user: Model,
    investor: Model,
) -> None:
    # Past value dates stay allowed (E05): the lot is already past its deadline.
    with freeze_time("2026-03-10T11:00:00Z"):
        deposit = _deposit(
            admin_user, investor, amount_minor=500_00, value_date=date(2026, 1, 1), key="old"
        )
        result = _scan(admin_user, _at(date(2026, 3, 10)))

    assert result.reminders_due == []
    assert _reminder_days(deposit.balance_lot.id) == []
    assert [request.amount_minor for request in result.forced_withdrawal_requests] == [500_00]


@pytest.mark.django_db
def test_live_ageing_scan_refuses_a_future_as_of_but_dry_run_can_preview(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    with freeze_time("2026-10-09T10:00:00Z"):
        _deposit(
            admin_user, investor, amount_minor=1000_00, value_date=date(2026, 10, 9), key="now"
        )
        future = _at(date(2027, 1, 15))
        with pytest.raises(LedgerValidationError, match="cannot run for a future time"):
            _scan(admin_user, future)
        preview = _scan(admin_user, future, dry_run=True)
        client.force_login(cast(Any, admin_user))
        response = client.post(
            "/api/v1/ledger/admin/balance-ageing-scans/",
            data={"as_of": "2027-01-15T12:00:00+01:00"},
            content_type="application/json",
        )
        now_response = client.post(
            "/api/v1/ledger/admin/balance-ageing-scans/",
            data={},
            content_type="application/json",
        )

    assert [candidate.amount_minor for candidate in preview.forced_withdrawal_candidates] == [
        1000_00
    ]
    assert response.status_code == 400
    assert "cannot run for a future time" in response.json()["detail"]
    assert now_response.status_code == 200
    assert InvestorWithdrawalRequest.objects.count() == 0
    assert InvestorBalanceLot.objects.get().available_amount_minor == 1000_00
    assert not DomainEvent.objects.filter(event_type="BalanceAgeingReminderDue").exists()


@pytest.mark.django_db
def test_lender_deposit_refuses_future_value_and_booking_dates(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    with freeze_time("2026-10-09T21:30:00Z"):  # 23:30 in Zurich, still 2026-10-09
        with pytest.raises(LedgerValidationError, match="Value date cannot be in the future"):
            _deposit(
                admin_user, investor, amount_minor=100_00, value_date=date(2026, 10, 10), key="v"
            )
        with pytest.raises(LedgerValidationError, match="Booking date cannot be in the future"):
            _deposit(
                admin_user,
                investor,
                amount_minor=100_00,
                value_date=date(2026, 10, 9),
                booking_date=date(2026, 10, 10),
                key="b",
            )
        client.force_login(cast(Any, admin_user))
        response = client.post(
            "/api/v1/ledger/admin/lender-deposits/",
            data={
                "investor_user_id": str(investor.pk),
                "amount_minor": 100_00,
                "currency": "CHF",
                "booking_date": "2026-10-09",
                "value_date": "2027-10-09",
                "collection_account_identifier": "CH00GARANTALEDGER",
                "payer_name": "Ageing Investor",
                "payer_account_identifier": "CH9300762011623852957",
                "idempotency_key": "deposit-future-api",
            },
            content_type="application/json",
        )
        today = _deposit(
            admin_user, investor, amount_minor=100_00, value_date=date(2026, 10, 9), key="t"
        )
        # Accepted product decision (E05): past value dates and value before booking.
        past = _deposit(
            admin_user,
            investor,
            amount_minor=200_00,
            value_date=date(2026, 9, 1),
            booking_date=date(2026, 10, 9),
            key="p",
        )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Value date cannot be in the future: 2027-10-09 is after today "
        "(2026-10-09, Europe/Zurich)."
    )
    assert today.balance_lot.withdrawal_deadline_at == _at(date(2026, 12, 8), 0)
    assert past.balance_lot.received_at == _at(date(2026, 9, 1), 0)
    assert BankOperation.objects.count() == 2


@pytest.mark.django_db
def test_borrower_disbursement_refuses_future_value_and_booking_dates(
    admin_user: Model,
) -> None:
    loan_id, borrower_id = _closed_primary_loan_funding(admin_user)

    def command(*, booking: date, value: date) -> FinalizeBorrowerDisbursementCommand:
        return FinalizeBorrowerDisbursementCommand(
            actor=admin_user,
            loan_id=str(loan_id),
            borrower_id=str(borrower_id),
            amount_minor=98_000_00,
            fee_minor=2_000_00,
            currency="CHF",
            booking_date=booking,
            value_date=value,
            collection_account_identifier="CH00GARANTALEDGER",
            payee_name="Borrower AG",
            payee_account_identifier="CH22BORROWER",
            idempotency_key=f"disbursement-{booking}-{value}",
        )

    with freeze_time("2026-03-23T11:00:00Z"):
        with pytest.raises(LedgerValidationError, match="Value date cannot be in the future"):
            finalize_borrower_disbursement(
                command(booking=date(2026, 3, 23), value=date(2026, 5, 22))
            )
        with pytest.raises(LedgerValidationError, match="Booking date cannot be in the future"):
            finalize_borrower_disbursement(
                command(booking=date(2026, 3, 24), value=date(2026, 3, 23))
            )
        assert not BankOperation.objects.filter(
            operation_type="borrower_loan_disbursement"
        ).exists()
        result = finalize_borrower_disbursement(
            command(booking=date(2026, 3, 23), value=date(2026, 3, 23))
        )

    assert result.bank_operation.value_date == date(2026, 3, 23)


@pytest.mark.django_db
def test_short_balance_messages_name_the_real_reason(
    admin_user: Model,
    investor: Model,
) -> None:
    """SECONDARY-08: only money too old for the window gets the 60-day message."""
    today = date(2026, 1, 20)
    as_of = _at(today)

    def plan(amount_minor: int, funding_deadline: date) -> str:
        with pytest.raises(LedgerValidationError) as error:
            plan_investment_balance_consumption(
                investor_user_id=str(investor.pk),
                currency="CHF",
                amount_minor=amount_minor,
                loan_funding_deadline=funding_deadline,
                as_of=as_of,
            )
        return str(error.value)

    # No CHF money at all (an immediate purchase has no funding window).
    assert plan(100_00, today) == (
        "You have no available CHF balance. Add funds or exchange currency first."
    )

    _deposit(admin_user, investor, amount_minor=100_00, value_date=date(2026, 1, 10), key="new")
    assert plan(4050_00, today) == (
        "Your available CHF balance is CHF 100.00. This needs CHF 4'050.00."
    )

    # 2025-11-21 + 60 days: today is this lot's last day; it can only be withdrawn.
    _deposit(admin_user, investor, amount_minor=5000_00, value_date=date(2025, 11, 21), key="old")
    assert plan(1000_00, today) == (
        "Only CHF 100.00 of your CHF balance can be used today. The rest has reached its "
        "60-day holding deadline and can only be withdrawn."
    )
    assert plan(1000_00, date(2026, 2, 15)).startswith(
        "Insufficient eligible balance for this funding window. Only CHF 100.00 of your CHF "
        "balance has enough time left before its 60-day holding deadline"
    )
