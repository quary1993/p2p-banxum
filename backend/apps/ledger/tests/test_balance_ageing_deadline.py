"""Balance ageing (18.4, Q01): notices 14/10/3 days before the return, day 56 last day, return
on day 57 (earlier for the calendar), the 60-day legal limit without penalty, compliance alerts
at day 59, F01 for direct loans, FX lot inheritance and future-date guards."""

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


def _notices(lot_id: Any) -> list[tuple[str, int | None]]:
    return sorted(
        (str(payload["kind"]), payload.get("days_before_return"))
        for payload in DomainEvent.objects.filter(
            event_type="BalanceAgeingReminderDue",
            aggregate_id=str(lot_id),
        ).values_list("payload", flat=True)
    )


def _notice_email(lot_id: Any, suffix: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        OutboxMessage.objects.get(idempotency_key=f"email:balance-lot:{lot_id}:{suffix}").payload,
    )


def _buckets(investor: Model, as_of: datetime) -> tuple[int, int, int]:
    summary = summarize_investor_balance(
        investor_user_id=str(investor.pk), currency="CHF", as_of=as_of
    )
    return summary.investable_minor, summary.withdraw_only_minor, summary.overdue_minor


def _scan_days(admin_user: Model, first: date, last: date) -> None:
    day = first
    while day <= last:
        _scan(admin_user, _at(day, 0, 30))
        day += timedelta(days=1)


# Value date Monday 2026-01-05 (day 0): day 56 (last day) = Monday 03-02, day 57 (return) =
# Tuesday 03-03, day 59 (latest debit) = Thursday 03-05, day 60 (legal limit) = Friday 03-06.
DAY_ZERO = date(2026, 1, 5)
LAST_DAY = date(2026, 3, 2)
RETURN_DATE = date(2026, 3, 3)


@pytest.mark.django_db
def test_with_iban_notices_come_14_10_and_3_days_before_and_the_return_is_on_day_57(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(admin_user, investor, amount_minor=1000_00, value_date=DAY_ZERO, key="iban")
    lot = deposit.balance_lot
    assert lot.return_after_days == 56

    _scan_days(admin_user, date(2026, 2, 10), date(2026, 3, 1))
    assert _notices(lot.id) == [("reminder", 3), ("reminder", 10), ("reminder", 14)]
    fourteen = _notice_email(lot.id, "return-notice:14")
    assert fourteen["subject"] == (
        "Reminder: money not invested goes back to your bank on 2026-03-03"
    )
    assert fourteen["template_key"] == "balance.return_notice.v1"
    assert "It goes back to your bank in 14 days." in fourteen["body_text"]
    assert "Until 2026-03-01 you can invest eligible money." in fourteen["body_text"]
    assert "On 2026-03-02 you can only withdraw it" in fourteen["body_text"]
    assert (
        "On 2026-03-03 we start the return of what is left to your verified bank account "
        "(IBAN ending 2957). Our team sends the transfer by hand." in fourteen["body_text"]
    )
    assert _buckets(investor, _at(date(2026, 3, 1))) == (1000_00, 0, 0)

    last_day = _scan(admin_user, _at(LAST_DAY, 12))
    assert last_day.forced_withdrawal_candidates == []
    assert _buckets(investor, _at(LAST_DAY, 23)) == (0, 1000_00, 0)

    day_57 = _scan(admin_user, _at(RETURN_DATE, 0, 30))
    assert day_57.reminders_due == []
    assert [request.amount_minor for request in day_57.forced_withdrawal_requests] == [1000_00]
    forced = day_57.forced_withdrawal_requests[0]
    assert forced.destination_iban == "CH9300762011623852957"
    assert forced.metadata["auto_return_after_days"] == 56
    assert forced.metadata["return_timing"] == {
        "return_date": "2026-03-03",
        "send_before": "2026-03-03T12:00:00+01:00",
        "order_day": "2026-03-03",
        "expected_debit_date": "2026-03-04",
        "latest_debit_date": "2026-03-05",
        "legal_limit_date": "2026-03-06",
        "debit_after_latest_day": False,
    }
    assert "Send the transfer before 12:00 on 2026-03-03" in forced.notes
    notice = OutboxMessage.objects.get(topic="email.balance_forced_return").payload
    assert notice["subject"] == "We are returning CHF 1'000.00 to your bank account"
    assert "Our team sends the transfer by hand on" in notice["body_text"]
    assert day_57.compliance_alerts == []

    for value in (date(2026, 3, 4), date(2026, 3, 5), date(2026, 3, 6)):
        later = _scan(admin_user, _at(value, 0, 30))
        assert later.forced_withdrawal_requests == []
    # Day 59 without the transfer marked as made: compliance is alerted once.
    alert_task = apps.get_model("admin_ops", "AdminTask").objects.get(
        task_type="compliance_review", related_object_type="ForcedReturnNotMade"
    )
    assert alert_task.related_object_id == str(forced.id)
    assert OutboxMessage.objects.filter(topic="email.compliance_alert").count() == 1
    lot.refresh_from_db()
    assert (lot.status, lot.available_amount_minor, lot.withdrawn_amount_minor) == (
        BalanceLotStatus.CONSUMED,
        0,
        1000_00,
    )
    assert not LedgerJournalEntry.objects.filter(event_type="balance_penalty_charged").exists()


@pytest.mark.django_db
def test_a_missed_scan_sends_only_the_closest_notice(admin_user: Model, investor: Model) -> None:
    deposit = _deposit(admin_user, investor, amount_minor=500_00, value_date=DAY_ZERO, key="miss")
    result = _scan(admin_user, _at(date(2026, 2, 28), 0, 30))
    assert [(item.kind, item.days_before_return) for item in result.reminders_due] == [
        ("reminder", 3)
    ]
    _scan_days(admin_user, date(2026, 2, 28), date(2026, 3, 2))
    assert _notices(deposit.balance_lot.id) == [("reminder", 3)]


@pytest.mark.django_db
def test_a_closed_day_57_moves_the_return_and_the_last_day_earlier(
    admin_user: Model,
    investor: Model,
) -> None:
    # Value date 2026-01-10: day 57 is Sunday 03-08 -> return Friday 03-06, last day 03-05.
    deposit = _deposit(
        admin_user, investor, amount_minor=300_00, value_date=date(2026, 1, 10), key="wk"
    )
    _scan(admin_user, _at(date(2026, 3, 5), 0, 30))
    assert _buckets(investor, _at(date(2026, 3, 5))) == (0, 300_00, 0)
    result = _scan(admin_user, _at(date(2026, 3, 6), 0, 30))
    assert [request.amount_minor for request in result.forced_withdrawal_requests] == [300_00]
    timing = result.forced_withdrawal_requests[0].metadata["return_timing"]
    assert (timing["return_date"], timing["expected_debit_date"]) == ("2026-03-06", "2026-03-09")
    assert deposit.balance_lot.return_after_days == 56


@pytest.mark.django_db
def test_without_iban_the_money_waits_withdraw_only_and_compliance_is_alerted_at_day_59(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(admin_user, investor, amount_minor=1000_00, value_date=DAY_ZERO, key="dl")
    deposit.payout_instruction.status = "disabled"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])
    lot_id = deposit.balance_lot.id

    _scan(admin_user, _at(date(2026, 2, 28), 0, 30))
    reminder = _notice_email(lot_id, "return-notice:3")["body_text"]
    assert "Garanta Finanzgruppe AG has no verified bank account in your name for CHF." in reminder

    for as_of in (_at(RETURN_DATE, 0, 30), _at(RETURN_DATE, 12)):
        day_57 = _scan(admin_user, as_of)
        assert day_57.forced_withdrawal_candidates == []
    urgent = _notice_email(lot_id, "ageing-reminder-day:57")
    assert urgent["subject"] == "Urgent: add a verified bank account so we can return your money"
    assert urgent["template_key"] == "balance.return_blocked.v2"
    assert urgent["metadata"]["has_usable_iban"] is False
    assert "There is no penalty." in urgent["body_text"]
    assert _buckets(investor, _at(RETURN_DATE)) == (0, 0, 1000_00)
    with pytest.raises(LedgerValidationError, match="reached its last day"):
        plan_investment_balance_consumption(
            investor_user_id=str(investor.pk),
            currency="CHF",
            amount_minor=100_00,
            loan_funding_deadline=RETURN_DATE,
            as_of=_at(RETURN_DATE),
        )

    day_59 = _scan(admin_user, _at(date(2026, 3, 5), 0, 30))
    assert day_59.compliance_alerts == [f"InvestorBalanceLot:{lot_id}"]
    assert _scan(admin_user, _at(date(2026, 3, 5), 12)).compliance_alerts == []
    alert = OutboxMessage.objects.get(topic="email.compliance_alert").payload
    assert alert["subject"].endswith("Money at day 59 not returned: CHF 1'000.00")

    day_60 = _scan(admin_user, _at(date(2026, 3, 6), 0, 30))
    assert [item.kind for item in day_60.reminders_due] == ["penalty_warning"]
    warning = _notice_email(lot_id, "ageing-reminder-day:60")
    assert warning["subject"] == "Today is the 60-day limit: add a bank account today"
    assert warning["template_key"] == "balance.legal_limit.v2"
    for day in (date(2026, 3, 7), date(2026, 3, 12)):
        later = _scan(admin_user, _at(day, 0, 30))
        assert later.reminders_due == []
    lot = InvestorBalanceLot.objects.get(id=lot_id)
    assert (lot.status, lot.available_amount_minor) == (BalanceLotStatus.AVAILABLE, 1000_00)
    assert not LedgerJournalEntry.objects.filter(event_type="balance_penalty_charged").exists()


@pytest.mark.django_db
def test_a_late_return_request_alerts_compliance_when_the_debit_misses_day_59(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(admin_user, investor, amount_minor=700_00, value_date=DAY_ZERO, key="lt")
    deposit.payout_instruction.status = "disabled"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])
    _scan(admin_user, _at(RETURN_DATE, 0, 30))
    # The account is usable again on day 59 after the cut-off: the order goes the next day.
    deposit.payout_instruction.status = "active"
    deposit.payout_instruction.save(update_fields=["status", "updated_at"])
    result = _scan(admin_user, _at(date(2026, 3, 5), 13))
    forced = result.forced_withdrawal_requests[0]
    assert forced.metadata["return_timing"]["order_day"] == "2026-03-06"
    assert forced.metadata["return_timing"]["debit_after_latest_day"] is True
    assert f"InvestorWithdrawalRequest:{forced.id}" in result.compliance_alerts


@pytest.mark.django_db
def test_lots_from_before_the_switch_keep_their_58_days(admin_user: Model, investor: Model) -> None:
    deposit = _deposit(admin_user, investor, amount_minor=400_00, value_date=DAY_ZERO, key="old")
    InvestorBalanceLot.objects.filter(id=deposit.balance_lot.id).update(return_after_days=58)
    # Day 57 and 58 are still the money's own days; it goes back on day 59 (03-05).
    for value in (RETURN_DATE, date(2026, 3, 4)):
        assert _scan(admin_user, _at(value, 0, 30)).forced_withdrawal_requests == []
    result = _scan(admin_user, _at(date(2026, 3, 5), 0, 30))
    assert [request.amount_minor for request in result.forced_withdrawal_requests] == [400_00]
    assert result.forced_withdrawal_requests[0].metadata["auto_return_after_days"] == 58


@pytest.mark.django_db
def test_return_days_and_notices_follow_the_platform_settings(
    admin_user: Model,
    investor: Model,
) -> None:
    actor = ActorRef("superadmin", "sa-1")
    settings_values: tuple[tuple[str, Any], ...] = (
        ("balance.auto_return_after_days", 40),
        ("balance.return_notice_days_before", [5]),
        ("bank.processing_business_days", 0),
    )
    for key, setting_value in settings_values:
        set_platform_setting(SetPlatformSettingCommand(actor=actor, key=key, value=setting_value))
    # Day 41 after 2026-01-05 is Sunday 02-15: the return moves to Friday 02-13 (no processing
    # time), and the notice comes 5 days before it.
    deposit = _deposit(admin_user, investor, amount_minor=1000_00, value_date=DAY_ZERO, key="cfg")
    assert deposit.balance_lot.return_after_days == 40
    _scan_days(admin_user, date(2026, 2, 1), date(2026, 2, 12))
    assert _notices(deposit.balance_lot.id) == [("reminder", 5)]
    result = _scan(admin_user, _at(date(2026, 2, 13), 0, 30))
    assert [request.amount_minor for request in result.forced_withdrawal_requests] == [1000_00]


@pytest.mark.django_db
def test_fx_proceeds_keep_the_source_dates_and_return_days(
    admin_user: Model,
    investor: Model,
) -> None:
    _deposit(admin_user, investor, amount_minor=1000_00, value_date=DAY_ZERO, key="chf")
    eur = _deposit(
        admin_user,
        investor,
        amount_minor=5000_00,
        currency="EUR",
        value_date=date(2026, 2, 1),
        key="eur",
        iban="DE89370400440532013000",
    )
    InvestorBalanceLot.objects.filter(currency_id="CHF").update(return_after_days=50)
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
            as_of=_at(date(2026, 2, 10)),
        )
    )
    fx_lot = fx.target_balance_lot
    assert fx_lot.withdrawal_deadline_at == _at(date(2026, 3, 6), 0)
    assert fx_lot.return_after_days == 50
    plan = plan_investment_balance_consumption(
        investor_user_id=str(investor.pk),
        currency="EUR",
        amount_minor=1500_00,
        loan_funding_deadline=date(2026, 2, 15),
        as_of=_at(date(2026, 2, 11)),
    )
    assert [(line.lot_id, line.amount_minor) for line in plan] == [
        (str(fx_lot.id), 1034_25),
        (str(eur.balance_lot.id), 465_75),
    ]
    # Day 51 (Wednesday 02-25, a TARGET settlement day) is the FX lot's return date.
    result = _scan(admin_user, _at(date(2026, 2, 25), 0, 30))
    forced = result.forced_withdrawal_requests
    assert [request.amount_minor for request in forced] == [1034_25]
    assert [item["lot_id"] for item in forced[0].lot_allocations] == [str(fx_lot.id)]
    eur.balance_lot.refresh_from_db()
    assert eur.balance_lot.available_amount_minor == 5000_00


@pytest.mark.django_db
def test_on_its_last_day_money_cannot_be_invested_or_exchanged(
    admin_user: Model,
    investor: Model,
) -> None:
    _deposit(admin_user, investor, amount_minor=1000_00, value_date=DAY_ZERO, key="win")

    def plan(funding_deadline: date, as_of: datetime, *, direct: bool = False) -> list[Any]:
        return plan_investment_balance_consumption(
            investor_user_id=str(investor.pk),
            currency="CHF",
            amount_minor=500_00,
            loan_funding_deadline=funding_deadline,
            as_of=as_of,
            direct_loan=direct,
        )

    # Loan Originator rounds and other windows: the last subscription day is before 03-02.
    assert [line.amount_minor for line in plan(date(2026, 3, 1), _at(date(2026, 2, 1)))] == [
        500_00
    ]
    with pytest.raises(LedgerValidationError, match="before it goes back to your bank"):
        plan(LAST_DAY, _at(date(2026, 2, 1)))
    with pytest.raises(LedgerValidationError, match="reached its last day"):
        plan(LAST_DAY, _at(LAST_DAY))
    # F01, direct loans: close + 3 business days by day 56 (03-02). A deadline on Tuesday 02-24
    # closes on 02-25 and pays out on Monday 03-02; one day later is too late.
    direct = plan(date(2026, 2, 24), _at(date(2026, 2, 1)), direct=True)
    assert [line.amount_minor for line in direct] == [500_00]
    with pytest.raises(LedgerValidationError, match="must reach the borrower by day 56"):
        plan(date(2026, 2, 25), _at(date(2026, 2, 1)), direct=True)

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
        exchange(_at(LAST_DAY), "fx-last-day")
    target = exchange(_at(date(2026, 3, 1)), "fx-day-55").target_balance_lot
    assert target.withdrawal_deadline_at == _at(date(2026, 3, 6), 0)
    assert _buckets(investor, _at(LAST_DAY)) == (0, 900_00, 0)


@pytest.mark.django_db
def test_lot_found_overdue_gets_no_contradicting_reminders(
    admin_user: Model,
    investor: Model,
) -> None:
    # Past value dates stay allowed (E05): the lot is already past its return date.
    with freeze_time("2026-03-10T11:00:00Z"):
        deposit = _deposit(
            admin_user, investor, amount_minor=500_00, value_date=date(2026, 1, 1), key="old"
        )
        result = _scan(admin_user, _at(date(2026, 3, 10)))

    assert result.reminders_due == []
    assert _notices(deposit.balance_lot.id) == []
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
                "payer_is_account_holder": True,
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
    assert plan(100_00, today) == ("You have no available CHF balance. Add funds first.")

    _deposit(admin_user, investor, amount_minor=100_00, value_date=date(2026, 1, 10), key="new")
    assert plan(4050_00, today) == (
        "Your available CHF balance is CHF 100.00. This needs CHF 4'050.00."
    )

    # 2025-11-25 + 56 days = 2026-01-20: today is this lot's last day (day 57 is a Wednesday).
    _deposit(admin_user, investor, amount_minor=5000_00, value_date=date(2025, 11, 25), key="old")
    assert plan(1000_00, today) == (
        "Only CHF 100.00 of your CHF balance can be used today. The rest has reached its "
        "last day and goes back to your bank: it can only be withdrawn."
    )
    assert plan(1000_00, date(2026, 2, 15)).startswith(
        "Insufficient eligible balance for this funding window. Only CHF 100.00 of your CHF "
        "balance has enough time left before it goes back to your bank"
    )
