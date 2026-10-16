"""Balance ageing: the 58-day automatic return, the 60-day legal limit and penalty mode,
forced-return lot choice and future-date guards (owner decision 2026-10-16)."""

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
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import Currency, DomainEvent, OutboxMessage
from backend.apps.platform_core.services.settings import (
    SetPlatformSettingCommand,
    set_platform_setting,
)


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
    # The FX lot keeps the CHF source's dates: last day 02-28 (day 58), legal limit 03-02.
    assert fx_lot.withdrawal_deadline_at == _at(date(2026, 3, 2), 0)

    day = date(2026, 2, 20)
    while day <= date(2026, 2, 28):
        _scan(admin_user, _at(day, 0, 30))
        day += timedelta(days=1)
    # Day 58: still the investor's last day, nothing is taken yet.
    assert InvestorWithdrawalRequest.objects.filter(is_forced=True).count() == 0

    for _ in range(4):
        _scan(admin_user, _at(day, 0, 30))
        day += timedelta(days=1)

    forced = list(InvestorWithdrawalRequest.objects.filter(is_forced=True))
    fx_lot.refresh_from_db()
    fresh_lot.refresh_from_db()
    assert len(forced) == 1
    assert forced[0].amount_minor == 1034_25
    # Day 59: the money goes back to the bank automatically.
    assert forced[0].requested_at == _at(date(2026, 3, 1), 0, 30)
    assert forced[0].metadata["auto_return_after_days"] == 58
    assert "not invested within 58 days" in forced[0].notes
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

    # Day 25 and 46 were before the FX lot existed (they belong to the CHF source lot). The
    # EUR IBAN is verified, so the FX lot went back on day 59: no day-59/60 notices.
    assert _reminder_days(fx_lot.id) == [53, 56, 57, 58]
    assert _reminder_days(fresh_lot.id) == [25]
    day_58 = DomainEvent.objects.get(
        idempotency_key=f"balance-lot:{fx_lot.id}:ageing-reminder-day:58"
    )
    assert day_58.payload["as_of"] == _at(date(2026, 2, 28), 0, 30).isoformat()
    assert day_58.payload["kind"] == "last_day"
    assert day_58.payload["return_date"] == "2026-03-01"
    last_day_email = OutboxMessage.objects.get(
        idempotency_key=f"email:balance-lot:{fx_lot.id}:ageing-reminder-day:58"
    )
    assert last_day_email.payload["subject"] == (
        "Last day: tomorrow we return the money to your bank"
    )
    assert "IBAN ending 3000" in last_day_email.payload["body_text"]


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


def _email(lot_id: Any, day: int) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        OutboxMessage.objects.get(
            idempotency_key=f"email:balance-lot:{lot_id}:ageing-reminder-day:{day}"
        ).payload,
    )


def _buckets(investor: Model, as_of: datetime) -> tuple[int, int, int]:
    summary = summarize_investor_balance(
        investor_user_id=str(investor.pk), currency="CHF", as_of=as_of
    )
    return summary.investable_minor, summary.withdraw_only_minor, summary.overdue_minor


@pytest.mark.django_db
def test_with_iban_the_money_goes_back_on_day_59_without_penalty(
    admin_user: Model,
    investor: Model,
) -> None:
    # Received 2026-01-01: day 57 = 02-27, day 58 (last day) = 02-28, day 59 = 03-01.
    deposit = _deposit(
        admin_user, investor, amount_minor=1000_00, value_date=date(2026, 1, 1), key="iban"
    )
    lot_id = deposit.balance_lot.id

    day_57 = _scan(admin_user, _at(date(2026, 2, 27), 0, 30))
    assert [reminder.day for reminder in day_57.reminders_due] == [25, 46, 53, 56, 57]
    assert _buckets(investor, _at(date(2026, 2, 27))) == (1000_00, 0, 0)
    reminder = _email(lot_id, 57)
    assert reminder["subject"] == (
        "Reminder: money not invested goes back to your bank on 2026-03-01"
    )
    assert reminder["template_key"] == "balance.ageing_reminder.v2"
    assert "Today is day 57 of 58." in reminder["body_text"]
    assert "goes back to your bank automatically after 58 days" in reminder["body_text"]
    assert "On 2026-02-28 you can only withdraw it" in reminder["body_text"]
    assert (
        "On 2026-03-01 we return what is left to your verified bank account (IBAN ending 2957)."
        in reminder["body_text"]
    )

    for as_of in (_at(date(2026, 2, 28), 0, 30), _at(date(2026, 2, 28), 12)):
        last_day = _scan(admin_user, as_of)
        assert last_day.forced_withdrawal_candidates == []
        assert last_day.penalty_mode_transitions == []
    assert _reminder_days(lot_id) == [25, 46, 53, 56, 57, 58]
    assert _buckets(investor, _at(date(2026, 2, 28), 23)) == (0, 1000_00, 0)
    last_day_email = _email(lot_id, 58)
    assert last_day_email["subject"] == "Last day: tomorrow we return the money to your bank"
    assert last_day_email["template_key"] == "balance.ageing_last_day.v1"
    assert "Today, 2026-02-28, is the last day CHF 1'000.00" in last_day_email["body_text"]
    assert (
        "Tomorrow, 2026-03-01, we return it automatically to your verified bank account "
        "(IBAN ending 2957)." in last_day_email["body_text"]
    )
    assert "penalty" not in last_day_email["body_text"]

    day_59 = _scan(admin_user, _at(date(2026, 3, 1), 0, 30))
    assert day_59.reminders_due == []
    assert day_59.penalty_mode_transitions == []
    assert [request.amount_minor for request in day_59.forced_withdrawal_requests] == [1000_00]
    forced = day_59.forced_withdrawal_requests[0]
    assert forced.requested_at == _at(date(2026, 3, 1), 0, 30)
    assert forced.destination_iban == "CH9300762011623852957"
    notice = OutboxMessage.objects.get(topic="email.balance_forced_return").payload
    assert notice["subject"] == "We are returning CHF 1'000.00 to your bank account"
    assert "was not invested within 58 days" in notice["body_text"]

    for value in (date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4)):
        later = _scan(admin_user, _at(value, 0, 30))
        assert later.penalty_charges == []
        assert later.forced_withdrawal_requests == []
    lot = InvestorBalanceLot.objects.get(id=lot_id)
    assert (lot.status, lot.available_amount_minor, lot.withdrawn_amount_minor) == (
        BalanceLotStatus.CONSUMED,
        0,
        1000_00,
    )
    assert not LedgerJournalEntry.objects.filter(event_type="balance_penalty_charged").exists()
    assert _reminder_days(lot_id) == [25, 46, 53, 56, 57, 58]


@pytest.mark.django_db
def test_without_iban_the_money_waits_withdraw_only_and_penalty_starts_on_day_61(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(
        admin_user, investor, amount_minor=1000_00, value_date=date(2026, 1, 1), key="dl"
    )
    deposit.payout_instruction.status = "disabled"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])
    lot_id = deposit.balance_lot.id

    _scan(admin_user, _at(date(2026, 2, 27), 0, 30))
    reminder = _email(lot_id, 57)["body_text"]
    assert "Garanta Finanzgruppe AG has no verified bank account in your name for CHF." in reminder
    assert "add a bank account in your name" in reminder

    # Day 58 (the 00:30 job and a QA-advance 12:00 run): last day, nothing taken.
    for as_of in (_at(date(2026, 2, 28), 0, 30), _at(date(2026, 2, 28), 12)):
        last_day = _scan(admin_user, as_of)
        assert last_day.forced_withdrawal_candidates == []
        assert last_day.penalty_mode_transitions == []
    last_day_email = _email(lot_id, 58)
    assert last_day_email["subject"] == "Last day: add a bank account today"
    body = last_day_email["body_text"]
    assert "Tomorrow, 2026-03-01, we must return it to your bank" in body
    assert "Add a bank account in your name today so we can return your money." in body
    assert "after 2026-03-02 (the 60-day legal limit)" in body
    assert "a penalty of 1% per day is charged on it" in body
    assert "You can still withdraw" not in body

    # Day 59: due back, but no IBAN. It stays withdraw-only, without penalty; urgent notice.
    for as_of in (_at(date(2026, 3, 1), 0, 30), _at(date(2026, 3, 1), 12)):
        day_59 = _scan(admin_user, as_of)
        assert day_59.forced_withdrawal_candidates == []
        assert day_59.penalty_mode_transitions == []
        assert day_59.penalty_charges == []
    assert _reminder_days(lot_id) == [25, 46, 53, 56, 57, 58, 59]
    assert _buckets(investor, _at(date(2026, 3, 1))) == (0, 0, 1000_00)
    urgent = _email(lot_id, 59)
    assert urgent["subject"] == "Urgent: add a verified bank account so we can return your money"
    assert urgent["template_key"] == "balance.return_blocked.v1"
    assert urgent["metadata"]["kind"] == "return_blocked"
    assert urgent["metadata"]["has_usable_iban"] is False
    assert "was not invested within 58 days" in urgent["body_text"]
    assert "Add a verified bank account so we can return your money." in urgent["body_text"]
    with pytest.raises(LedgerValidationError, match="58-day limit"):
        plan_investment_balance_consumption(
            investor_user_id=str(investor.pk),
            currency="CHF",
            amount_minor=100_00,
            loan_funding_deadline=date(2026, 3, 1),
            as_of=_at(date(2026, 3, 1)),
        )

    # Day 60 (legal limit): still no penalty; the notice says penalty mode starts tomorrow.
    day_60 = _scan(admin_user, _at(date(2026, 3, 2), 0, 30))
    assert [reminder.day for reminder in day_60.reminders_due] == [60]
    assert day_60.penalty_mode_transitions == []
    warning = _email(lot_id, 60)
    assert warning["subject"] == "Penalty mode starts tomorrow: add a bank account today"
    assert warning["template_key"] == "balance.penalty_warning.v1"
    assert "reaches the 60-day legal limit today, 2026-03-02" in warning["body_text"]
    assert (
        "If the money is still on your balance tomorrow, it enters penalty mode, a penalty "
        "of 1% per day is charged on it" in warning["body_text"]
    )
    lot = InvestorBalanceLot.objects.get(id=lot_id)
    assert (lot.status, lot.available_amount_minor) == (BalanceLotStatus.AVAILABLE, 1000_00)

    # Day 61: penalty mode and the first daily penalty, exactly as before the 58-day rule.
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
    assert _reminder_days(lot_id) == [25, 46, 53, 56, 57, 58, 59, 60]


@pytest.mark.django_db
def test_an_iban_verified_on_day_60_gets_the_money_back_without_penalty(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(
        admin_user, investor, amount_minor=1000_00, value_date=date(2026, 1, 1), key="late"
    )
    deposit.payout_instruction.status = "disabled"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])
    _scan(admin_user, _at(date(2026, 3, 1), 0, 30))
    assert InvestorWithdrawalRequest.objects.count() == 0

    deposit.payout_instruction.status = "active"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])
    day_60 = _scan(admin_user, _at(date(2026, 3, 2), 0, 30))

    assert [request.amount_minor for request in day_60.forced_withdrawal_requests] == [1000_00]
    assert day_60.reminders_due == []
    assert day_60.penalty_mode_transitions == []
    assert not OutboxMessage.objects.filter(
        idempotency_key=f"email:balance-lot:{deposit.balance_lot.id}:ageing-reminder-day:60"
    ).exists()


@pytest.mark.django_db
def test_a_missed_day_59_scan_sends_only_the_day_60_notice(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(
        admin_user, investor, amount_minor=500_00, value_date=date(2026, 1, 1), key="miss"
    )
    deposit.payout_instruction.status = "disabled"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])

    result = _scan(admin_user, _at(date(2026, 3, 2), 0, 30))

    assert [reminder.day for reminder in result.reminders_due] == [60]
    assert _reminder_days(deposit.balance_lot.id) == [60]


@pytest.mark.django_db
def test_return_day_and_reminders_follow_the_platform_settings(
    admin_user: Model,
    investor: Model,
) -> None:
    actor = ActorRef("superadmin", "sa-1")
    # Back to the old rule (return after day 60), with a custom reminder schedule.
    settings_values: tuple[tuple[str, Any], ...] = (
        ("balance.auto_return_after_days", 60),
        ("balance.reminder_days", [30, 59]),
    )
    for key, setting_value in settings_values:
        set_platform_setting(SetPlatformSettingCommand(actor=actor, key=key, value=setting_value))
    deposit = _deposit(
        admin_user, investor, amount_minor=1000_00, value_date=date(2026, 1, 1), key="cfg"
    )

    for value in (date(2026, 3, 1), date(2026, 3, 2)):
        result = _scan(admin_user, _at(value, 0, 30))
        assert result.forced_withdrawal_requests == []
    assert _reminder_days(deposit.balance_lot.id) == [30, 59]
    assert _email(deposit.balance_lot.id, 59)["body_text"].count("day 59 of 60") == 1
    assert _buckets(investor, _at(date(2026, 3, 2))) == (0, 1000_00, 0)

    day_61 = _scan(admin_user, _at(date(2026, 3, 3), 0, 30))
    assert [request.amount_minor for request in day_61.forced_withdrawal_requests] == [1000_00]


@pytest.mark.django_db
def test_on_its_last_day_money_cannot_be_invested_or_exchanged(
    admin_user: Model,
    investor: Model,
) -> None:
    # Received 2026-01-01: last day 02-28. A loan must close by then (last subscription 02-27).
    _deposit(admin_user, investor, amount_minor=1000_00, value_date=date(2026, 1, 1), key="win")

    def plan(funding_deadline: date, as_of: datetime) -> list[Any]:
        return plan_investment_balance_consumption(
            investor_user_id=str(investor.pk),
            currency="CHF",
            amount_minor=500_00,
            loan_funding_deadline=funding_deadline,
            as_of=as_of,
        )

    assert [line.amount_minor for line in plan(date(2026, 2, 27), _at(date(2026, 2, 1)))] == [
        500_00
    ]
    with pytest.raises(LedgerValidationError, match=r"before it goes back to your bank \(after 58"):
        plan(date(2026, 2, 28), _at(date(2026, 2, 1)))
    with pytest.raises(LedgerValidationError, match="58-day limit"):
        plan(date(2026, 2, 28), _at(date(2026, 2, 28)))

    def exchange(as_of: datetime, key: str) -> Any:
        return execute_investor_fx_exchange_ledger(
            ExecuteInvestorFxExchangeLedgerCommand(
                actor=admin_user,
                investor_user_id=str(investor.pk),
                source_currency="CHF",
                target_currency="EUR",
                source_amount_minor=100_00,
                gross_target_amount_minor=105_00,
                target_amount_minor=103_43,
                fee_minor=1_57,
                source_type="test",
                source_id=key,
                idempotency_key=key,
                as_of=as_of,
            )
        )

    Currency.objects.filter(code="EUR").update(is_enabled=True)
    with pytest.raises(LedgerValidationError, match="Insufficient eligible balance"):
        exchange(_at(date(2026, 2, 28)), "fx-last-day")
    # Day 57 still works; the EUR money keeps the CHF dates and goes back on day 59 too.
    target = exchange(_at(date(2026, 2, 27)), "fx-day-57").target_balance_lot
    assert target.withdrawal_deadline_at == _at(date(2026, 3, 2), 0)
    assert _buckets(investor, _at(date(2026, 2, 28))) == (0, 900_00, 0)


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
    """SECONDARY-08: only money too old for the window gets the holding-time message."""
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
        "You have no available CHF balance. Add funds first."
    )

    _deposit(admin_user, investor, amount_minor=100_00, value_date=date(2026, 1, 10), key="new")
    assert plan(4050_00, today) == (
        "Your available CHF balance is CHF 100.00. This needs CHF 4'050.00."
    )

    # 2025-11-23 + 58 days: today is this lot's last day; it can only be withdrawn.
    _deposit(admin_user, investor, amount_minor=5000_00, value_date=date(2025, 11, 23), key="old")
    assert plan(1000_00, today) == (
        "Only CHF 100.00 of your CHF balance can be used today. The rest has reached its "
        "58-day limit and goes back to your bank: it can only be withdrawn."
    )
    assert plan(1000_00, date(2026, 2, 15)).startswith(
        "Insufficient eligible balance for this funding window. Only CHF 100.00 of your CHF "
        "balance has enough time left before it goes back to your bank (after 58 days)"
    )
