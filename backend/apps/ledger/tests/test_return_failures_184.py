"""IP of Webby-Soft SRL. 18.4: failed returns (Q02) and a return account verified from a
deposit (Q02.5)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone
from freezegun import freeze_time

from backend.apps.ledger import return_failures
from backend.apps.ledger import services as ledger_services
from backend.apps.ledger.models import (
    BalanceLotStatus,
    BalanceReturnFailure,
    BankOperation,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorWithdrawalRequest,
    LedgerJournalEntry,
)
from backend.apps.ledger.services import (
    CancelInvestorWithdrawalCommand,
    DeclareLenderDepositCommand,
    FinalizeInvestorWithdrawalCommand,
    LedgerConflictError,
    LedgerValidationError,
    RequestInvestorWithdrawalCommand,
    RunBalanceAgeingScanCommand,
    cancel_investor_withdrawal,
    finalize_investor_withdrawal,
    investor_balance_integrity_breaks,
    request_investor_withdrawal,
    run_balance_ageing_scan,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import AuditEvent, Currency, OutboxMessage
from backend.apps.platform_core.services.settings import (
    SetPlatformSettingCommand,
    set_platform_setting,
)

# Audit S3-1: a deposit alone verifies no account; these tests need the account the admin
# verifies after it.
from backend.apps.platform_core.tests.deposit_accounts import (
    declare_deposit_and_verify_account as declare_lender_deposit,
)
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code

IBAN = "CH9300762011623852957"
NEW_IBAN = "CH5604835012345678009"
# Value date Monday 2026-01-05: return on Tuesday 03-03 (day 57).
DAY_ZERO = date(2026, 1, 5)


@pytest.fixture
def admin_user() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="return-admin@example.test",
            password="AdminPass123!",
            full_name="Return Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    user = cast(
        Model,
        get_user_model().objects.create_user(
            email="return-investor@example.test",
            full_name="Return Investor",
            account_type="natural_person_lender",
            status="active",
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


def _at(value: date, hour: int = 9) -> datetime:
    return datetime.combine(value, time(hour), tzinfo=business_timezone())


def _deposit(
    admin_user: Model,
    investor: Model,
    *,
    key: str,
    value_date: date = DAY_ZERO,
    amount_minor: int = 1000_00,
    iban: str = IBAN,
    verify_account: bool = True,
) -> Any:
    """A deposit; by default the admin also verifies its paying account (audit S3-1)."""
    Currency.objects.filter(code="CHF").update(is_enabled=True)
    with freeze_time(_at(value_date, 9)):
        return _declare(
            admin_user,
            investor,
            key=key,
            value_date=value_date,
            amount_minor=amount_minor,
            iban=iban,
            verify_account=verify_account,
        )


def _declare(
    admin_user: Model,
    investor: Model,
    *,
    key: str,
    value_date: date,
    amount_minor: int,
    iban: str,
    verify_account: bool,
) -> Any:
    declare = declare_lender_deposit if verify_account else ledger_services.declare_lender_deposit
    return declare(
        DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency="CHF",
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="CH00GARANTALEDGER",
            payer_name="Return Investor",
            payer_account_identifier=iban,
            bank_reference=f"BANK-{key}",
            payment_reference=f"INV-{key}",
            evidence_reference=f"statement:{key}",
            idempotency_key=key,
        )
    )


def _scan(admin_user: Model, day: date) -> Any:
    with freeze_time(_at(day, 1)):
        return run_balance_ageing_scan(
            RunBalanceAgeingScanCommand(actor=admin_user, as_of=_at(day, 0))
        )


def _finalize(admin_user: Model, request: InvestorWithdrawalRequest, day: date) -> None:
    with freeze_time(_at(day, 15)):
        finalize_investor_withdrawal(
            FinalizeInvestorWithdrawalCommand(
                actor=admin_user,
                withdrawal_request_id=str(request.id),
                booking_date=day,
                value_date=day,
                collection_account_identifier="CH00GARANTALEDGER",
                bank_reference=f"OUT-{request.id}",
                idempotency_key=f"finalize-{request.id}",
            )
        )


def _returned(
    admin_user: Model,
    request: InvestorWithdrawalRequest,
    day: date,
    *,
    reason: str = "account_closed",
    key: str = "returned-1",
) -> BalanceReturnFailure:
    with freeze_time(_at(day, 10)):
        return return_failures.record_returned_withdrawal(
            return_failures.RecordReturnedWithdrawalCommand(
                actor=admin_user,
                withdrawal_request_id=str(request.id),
                returned_value_date=day,
                reason_code=reason,
                bank_reason_text="AC04 closed account",
                bank_reference="RET-1",
                idempotency_key=key,
            )
        )


def _forced_and_sent(admin_user: Model, investor: Model) -> tuple[Any, InvestorWithdrawalRequest]:
    deposit = _deposit(admin_user, investor, key="dep")
    forced = _scan(admin_user, date(2026, 3, 3)).forced_withdrawal_requests[0]
    _finalize(admin_user, forced, date(2026, 3, 3))
    return deposit, forced


def _tasks(task_type: str) -> list[Any]:
    return list(apps.get_model("admin_ops", "AdminTask").objects.filter(task_type=task_type))


@pytest.mark.django_db
def test_a_returned_forced_return_restores_the_money_with_its_age_and_opens_the_failure(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit, forced = _forced_and_sent(admin_user, investor)
    lot = deposit.balance_lot

    failure = _returned(admin_user, forced, date(2026, 3, 5))

    forced.refresh_from_db()
    lot.refresh_from_db()
    assert forced.status == "returned"
    assert (lot.status, lot.available_amount_minor, lot.withdrawn_amount_minor) == (
        BalanceLotStatus.AVAILABLE,
        1000_00,
        0,
    )
    # The original age stays: no new 56/60-day period.
    assert lot.withdrawal_deadline_at == datetime.combine(
        date(2026, 3, 6), time.min, tzinfo=business_timezone()
    )
    assert (failure.status, failure.lot_ids, failure.is_forced) == ("open", [str(lot.id)], True)
    assert BankOperation.objects.get(operation_type="lender_withdrawal_return").amount_minor == (
        1000_00
    )
    assert LedgerJournalEntry.objects.filter(event_type="lender_withdrawal_returned").count() == 1
    assert investor_balance_integrity_breaks(currency=Currency.objects.get(code="CHF")) == []
    # Account closed: the account leaves the investor's choices (never again to it).
    instruction = InvestorPayoutInstruction.objects.get(destination_iban=IBAN)
    assert (instruction.status, instruction.is_verified_usable) == ("disabled", False)
    # Admin task, and compliance at once: the money is at day 59 (>= 57).
    assert [task.related_object_id for task in _tasks("return_failed")] == [str(failure.id)]
    assert [task.related_object_type for task in _tasks("compliance_review")] == [
        "BalanceReturnFailure"
    ]
    failure.refresh_from_db()
    assert failure.escalated_at is not None
    assert failure.escalation_reason == "The money is at day 59 (60-day limit)."
    notice = OutboxMessage.objects.get(topic="email.balance_return_failed").payload
    assert notice["subject"] == "Return failed: CHF 1'000.00 is back on your balance"
    assert "Your bank says the account is closed." in notice["body_text"]
    assert "There is no penalty." in notice["body_text"]

    # The investor's Account page and Transactions (investor_portal, read through the registry).
    portal = import_module("backend.apps.investor_portal.services")
    balances = portal.get_investor_balances(actor=investor, as_of=_at(date(2026, 3, 5)))
    assert [item["reason_code"] for item in balances["return_failures"]] == ["account_closed"]
    assert balances["lots"][0]["return_failed"] is True
    assert balances["lots"][0]["bucket"] == "overdue"
    activity = portal.get_investor_activity(actor=investor, limit=50)["entries"]
    returned = [entry for entry in activity if entry["activity_type"] == "withdrawal_returned"]
    assert [(entry["direction"], entry["amount_minor"]) for entry in returned] == [("in", 1000_00)]

    # The same call again returns the same failure; another key is refused.
    assert _returned(admin_user, forced, date(2026, 3, 5)).id == failure.id
    with pytest.raises(LedgerConflictError, match="already recorded"):
        _returned(admin_user, forced, date(2026, 3, 5), key="returned-2")


@pytest.mark.django_db
def test_the_scan_never_sends_a_failed_return_again_and_notifies_every_day(
    admin_user: Model,
    investor: Model,
) -> None:
    _deposit_, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="technical")

    first = _scan(admin_user, date(2026, 3, 5))
    again = _scan(admin_user, date(2026, 3, 5))
    following = _scan(admin_user, date(2026, 3, 6))

    assert first.forced_withdrawal_requests == again.forced_withdrawal_requests == []
    assert following.forced_withdrawal_requests == []
    assert first.return_failure_notices == [str(failure.id)]
    assert again.return_failure_notices == []
    assert following.return_failure_notices == [str(failure.id)]
    assert InvestorWithdrawalRequest.objects.filter(status="requested").count() == 0
    assert OutboxMessage.objects.filter(topic="email.balance_return_failed").count() == 3
    # A technical error is not the investor's fault: the account stays usable.
    assert InvestorPayoutInstruction.objects.get(destination_iban=IBAN).status == "active"


@pytest.mark.django_db
def test_send_again_only_to_a_corrected_or_newly_verified_account(
    admin_user: Model,
    investor: Model,
) -> None:
    _deposit_, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="other")
    old = InvestorPayoutInstruction.objects.get(destination_iban=IBAN)

    def resend(instruction_id: str) -> InvestorWithdrawalRequest:
        with freeze_time(_at(date(2026, 3, 4), 12)):
            return return_failures.resend_failed_return(
                return_failures.ResendFailedReturnCommand(
                    actor=admin_user,
                    failure_id=str(failure.id),
                    payout_instruction_id=instruction_id,
                    note="Investor confirmed the account.",
                )
            )

    with pytest.raises(LedgerConflictError, match="corrected or newly verified account"):
        resend(str(old.id))
    # The investor's account is checked again after the failure: now it can be used.
    InvestorPayoutInstruction.objects.filter(id=old.id).update(
        verified_at=failure.recorded_at + timedelta(hours=1)
    )
    again = resend(str(old.id))

    failure.refresh_from_db()
    assert again.status == "requested" and again.is_forced
    assert again.metadata["resent_after_failure_id"] == str(failure.id)
    assert [item["lot_id"] for item in again.lot_allocations] == failure.lot_ids
    assert (failure.status, failure.resolution) == ("resolved", "sent_again")
    assert failure.resend_withdrawal_request_id == again.id
    assert all(task.status == "resolved" for task in _tasks("return_failed"))
    notice = OutboxMessage.objects.filter(topic="email.balance_forced_return").latest("created_at")
    assert "that your bank returned again" in notice.payload["body_text"]
    with pytest.raises(LedgerConflictError, match="already resolved"):
        resend(str(old.id))


@pytest.mark.django_db
def test_send_again_to_a_new_verified_account_after_an_account_error(
    admin_user: Model,
    investor: Model,
) -> None:
    _deposit_, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="name_mismatch")
    revoked = InvestorPayoutInstruction.objects.get(destination_iban=IBAN)
    with pytest.raises(LedgerValidationError, match="Choose a verified bank account"):
        return_failures.resend_failed_return(
            return_failures.ResendFailedReturnCommand(
                actor=admin_user, failure_id=str(failure.id), payout_instruction_id=str(revoked.id)
            )
        )
    new = InvestorPayoutInstruction.objects.create(
        investor_user_id=investor.pk,
        currency_id="CHF",
        destination_iban=NEW_IBAN,
        destination_account_name="Return Investor",
        is_verified_usable=True,
        verified_at=timezone.now(),
        verified_by_admin_id=admin_user.pk,
        created_by_admin_id=admin_user.pk,
    )
    request = return_failures.resend_failed_return(
        return_failures.ResendFailedReturnCommand(
            actor=admin_user, failure_id=str(failure.id), payout_instruction_id=str(new.id)
        )
    )
    assert request.destination_iban == NEW_IBAN


@pytest.mark.django_db
def test_compliance_takes_a_failed_return_after_five_days(
    admin_user: Model,
    investor: Model,
) -> None:
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=ActorRef("superadmin", "sa-1"), key="balance.auto_return_after_days", value=30
        )
    )
    _deposit(admin_user, investor, key="dep30")
    # Day 31 after 2026-01-05 is Thursday 02-05.
    forced = _scan(admin_user, date(2026, 2, 5)).forced_withdrawal_requests[0]
    _finalize(admin_user, forced, date(2026, 2, 5))
    failure = _returned(admin_user, forced, date(2026, 2, 6), reason="technical")
    assert failure.escalated_at is None

    for day in (date(2026, 2, 7), date(2026, 2, 10)):
        assert _scan(admin_user, day).compliance_alerts == []
    eleventh = _scan(admin_user, date(2026, 2, 11))
    assert eleventh.compliance_alerts == [f"BalanceReturnFailure:{failure.id}"]
    failure.refresh_from_db()
    assert failure.escalation_reason == "The failure is open for 5 days."
    assert _scan(admin_user, date(2026, 2, 12)).compliance_alerts == []


@pytest.mark.django_db
def test_a_failure_closes_when_no_money_is_left_or_with_a_note(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="technical")
    # The investor withdrew everything (shown here directly on the lot).
    InvestorBalanceLot.objects.filter(id=deposit.balance_lot.id).update(
        available_amount_minor=0, withdrawn_amount_minor=1000_00, status="consumed"
    )
    _scan(admin_user, date(2026, 3, 5))
    failure.refresh_from_db()
    assert (failure.status, failure.resolution) == ("resolved", "no_money_left")
    with pytest.raises(LedgerConflictError, match="already resolved"):
        return_failures.resolve_return_failure(
            return_failures.ResolveReturnFailureCommand(
                actor=admin_user, failure_id=str(failure.id), note="Done."
            )
        )


@pytest.mark.django_db
def test_a_note_cannot_close_a_failure_and_restart_automatic_returns(
    admin_user: Model,
    investor: Model,
) -> None:
    """Audit S3-2: with the money still on the balance the case stays open, its task cannot be
    closed alone, and no scan sends the money by itself."""
    deposit, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="technical")
    with pytest.raises(LedgerConflictError, match="a note cannot close the case") as refused:
        return_failures.resolve_return_failure(
            return_failures.ResolveReturnFailureCommand(
                actor=admin_user, failure_id=str(failure.id), note="Handled with the lawyer."
            )
        )
    assert refused.value.code == "return_failure_money_on_balance"
    admin_ops: Any = import_module("backend.apps.admin_ops.services")
    [task] = _tasks("return_failed")
    with pytest.raises(admin_ops.AdminTaskValidationError, match="failed return is still open"):
        admin_ops.update_admin_task(
            admin_ops.UpdateAdminTaskCommand(
                actor=admin_user, task_id=str(task.id), status="resolved", completion_note="Done."
            )
        )
    for day in (date(2026, 3, 5), date(2026, 3, 6), date(2026, 3, 9)):
        assert _scan(admin_user, day).forced_withdrawal_requests == []
    failure.refresh_from_db()
    deposit.balance_lot.refresh_from_db()
    assert failure.status == "open"
    assert deposit.balance_lot.available_amount_minor == 1000_00
    assert InvestorWithdrawalRequest.objects.filter(status="requested").count() == 0


@pytest.mark.django_db
def test_a_cancelled_forced_return_is_requested_again_on_the_same_day(
    admin_user: Model,
    investor: Model,
) -> None:
    """Audit S3-3: the cancelled request is not the day's result; the next scan reserves the
    lots in one new request, also on the same business day."""
    deposit = _deposit(admin_user, investor, key="dep")
    day = date(2026, 3, 3)
    forced = _scan(admin_user, day).forced_withdrawal_requests[0]
    with freeze_time(_at(day, 11)):
        cancel_investor_withdrawal(
            CancelInvestorWithdrawalCommand(
                actor=admin_user,
                withdrawal_request_id=str(forced.id),
                reason="Wrong bank data, corrected.",
                idempotency_key="cancel-forced-1",
            )
        )
    deposit.balance_lot.refresh_from_db()
    assert deposit.balance_lot.available_amount_minor == 1000_00

    [replacement] = _scan(admin_user, day).forced_withdrawal_requests
    assert replacement.id != forced.id
    assert (replacement.status, replacement.is_forced) == ("requested", True)
    assert replacement.metadata["return_attempt"] == 2
    assert [item["lot_id"] for item in replacement.lot_allocations] == [str(deposit.balance_lot.id)]
    deposit.balance_lot.refresh_from_db()
    assert deposit.balance_lot.available_amount_minor == 0
    # A further scan on the day finds nothing due: the lots are reserved; nothing is doubled.
    assert _scan(admin_user, day).forced_withdrawal_requests == []
    assert InvestorWithdrawalRequest.objects.filter(status="requested").count() == 1
    assert InvestorWithdrawalRequest.objects.filter(status="cancelled").count() == 1


@pytest.mark.django_db
def test_a_cancelled_send_again_opens_the_failed_return_again(
    admin_user: Model,
    investor: Model,
) -> None:
    """Audit S3-3: after the cancellation the money is back, the failure and its task are open
    again, and the scan sends nothing by itself."""
    deposit, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="account_closed")
    new_account = InvestorPayoutInstruction.objects.create(
        investor_user_id=investor.pk,
        currency_id="CHF",
        destination_iban=NEW_IBAN,
        destination_account_name="Return Investor",
        is_verified_usable=True,
        verified_at=timezone.now(),
        verified_by_admin_id=admin_user.pk,
        created_by_admin_id=admin_user.pk,
    )

    def resend(key: str) -> InvestorWithdrawalRequest:
        with freeze_time(_at(date(2026, 3, 5), 12)):
            return return_failures.resend_failed_return(
                return_failures.ResendFailedReturnCommand(
                    actor=admin_user,
                    failure_id=str(failure.id),
                    payout_instruction_id=str(new_account.id),
                    note=key,
                )
            )

    first = resend("first")
    with freeze_time(_at(date(2026, 3, 5), 13)):
        cancel_investor_withdrawal(
            CancelInvestorWithdrawalCommand(
                actor=admin_user,
                withdrawal_request_id=str(first.id),
                reason="Stopped before the transfer.",
                idempotency_key="cancel-resend-1",
            )
        )
    failure.refresh_from_db()
    assert (failure.status, failure.resolution, failure.resend_withdrawal_request_id) == (
        "open",
        "",
        None,
    )
    assert [task.status for task in _tasks("return_failed")] == ["open"]
    assert AuditEvent.objects.filter(action="ledger.balance_return_failure_reopened").count() == 1
    assert _scan(admin_user, date(2026, 3, 5)).forced_withdrawal_requests == []
    deposit.balance_lot.refresh_from_db()
    assert deposit.balance_lot.available_amount_minor == 1000_00

    # The team sends it again on the same day: a new request, the failure closes again.
    second = resend("second")
    failure.refresh_from_db()
    assert second.id != first.id and second.status == "requested"
    assert (failure.status, failure.resend_withdrawal_request_id) == ("resolved", second.id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("reason", "same_account_after_cleared_cause"),
    [
        ("bank_restriction", True),
        ("technical", True),
        ("account_closed", False),
        ("account_unknown", False),
        ("name_mismatch", False),
        ("account_blocked", False),
        ("other", False),
    ],
)
def test_the_same_account_is_used_again_only_after_a_recorded_cleared_cause(
    admin_user: Model,
    investor: Model,
    reason: str,
    same_account_after_cleared_cause: bool,
) -> None:
    """Audit S3-8, one case per bank reason: a bank-side failure needs the recorded statement
    that the cause is cleared; an account or holder failure always needs a new verification."""
    _deposit_, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason=reason)
    account = InvestorPayoutInstruction.objects.get(destination_iban=IBAN)

    def resend(**values: Any) -> InvestorWithdrawalRequest:
        with freeze_time(_at(date(2026, 3, 4), 12)):
            return return_failures.resend_failed_return(
                return_failures.ResendFailedReturnCommand(
                    actor=admin_user,
                    failure_id=str(failure.id),
                    payout_instruction_id=str(account.id),
                    **values,
                )
            )

    if not same_account_after_cleared_cause:
        expected = (
            "Choose a verified bank account"
            if account.status != "active" or reason != "other"
            else "corrected or newly verified account"
        )
        with pytest.raises((LedgerConflictError, LedgerValidationError), match=expected):
            resend(cause_cleared=True, note="The bank says it works again.")
        assert InvestorWithdrawalRequest.objects.filter(status="requested").count() == 0
        return
    # The account stays valid, but a guess is not enough.
    with pytest.raises(LedgerConflictError, match="confirm that the cause is cleared") as refused:
        resend(note="Try again.")
    assert refused.value.code == "return_failure_cause_not_cleared"
    with pytest.raises(LedgerConflictError, match="confirm that the cause is cleared"):
        resend(cause_cleared=True, note="  ")
    again = resend(cause_cleared=True, note="Bank X confirmed by phone: restriction lifted.")
    assert again.metadata["destination_selection"]["same_account_cause_cleared"] is True
    cleared = AuditEvent.objects.get(action="ledger.balance_return_failure_cause_cleared")
    assert cleared.metadata["note"] == "Bank X confirmed by phone: restriction lifted."
    assert cleared.metadata["reason_code"] == reason


@pytest.mark.django_db
def test_a_returned_voluntary_withdrawal_puts_the_money_back_without_a_failure_case(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(admin_user, investor, key="vol")
    code = issue_sensitive_action_test_code(investor, "withdrawal")
    with freeze_time(_at(date(2026, 1, 20), 9)):
        request = request_investor_withdrawal(
            RequestInvestorWithdrawalCommand(
                actor=investor,
                amount_minor=250_00,
                currency="CHF",
                destination_iban=IBAN,
                destination_account_name="Return Investor",
                idempotency_key="withdraw-vol",
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
                pin=code.pin,
            )
        )
    _finalize(admin_user, request, date(2026, 1, 20))
    failure = _returned(admin_user, request, date(2026, 1, 22), reason="account_unknown")

    deposit.balance_lot.refresh_from_db()
    assert deposit.balance_lot.available_amount_minor == 1000_00
    assert (failure.status, failure.resolution) == ("resolved", "money_available")
    assert _tasks("return_failed") == []
    notice = OutboxMessage.objects.get(topic="email.balance_return_failed").payload
    assert notice["subject"] == "Withdrawal sent back: CHF 250.00 is on your balance again"


@pytest.mark.django_db
def test_only_a_sent_withdrawal_can_come_back(admin_user: Model, investor: Model) -> None:
    _deposit(admin_user, investor, key="dep")
    forced = _scan(admin_user, date(2026, 3, 3)).forced_withdrawal_requests[0]
    with pytest.raises(LedgerConflictError, match="Only a withdrawal that was sent"):
        _returned(admin_user, forced, date(2026, 3, 4))
    _finalize(admin_user, forced, date(2026, 3, 4))
    with pytest.raises(LedgerValidationError, match="before the transfer was sent"):
        _returned(admin_user, forced, date(2026, 3, 3))


@pytest.mark.django_db
def test_admin_api_records_lists_and_resolves_failed_returns(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _deposit_, forced = _forced_and_sent(admin_user, investor)
    with freeze_time(_at(date(2026, 3, 4), 10)):
        client.force_login(cast(Any, admin_user))
        response = client.post(
            f"/api/v1/ledger/admin/withdrawal-requests/{forced.id}/returned/",
            data={
                "returned_value_date": "2026-03-04",
                "reason_code": "account_blocked",
                "idempotency_key": "api-returned",
            },
            content_type="application/json",
        )
        assert response.status_code == 200, response.json()
        failure_id = response.json()["id"]
        assert response.json()["reason_label"] == "Account blocked or restricted"
        listed = client.get("/api/v1/ledger/admin/return-failures/?status=open")
        assert listed.status_code == 200, listed.json()
        assert [row["id"] for row in listed.json()["results"]] == [failure_id]
        # Audit S3-2: a note cannot close the case while the money is on the balance.
        refused = client.post(
            f"/api/v1/ledger/admin/return-failures/{failure_id}/resolve/",
            data={"note": "Court deposit agreed with the lawyer."},
            content_type="application/json",
        )
        assert refused.status_code == 409, refused.json()
        assert refused.json()["code"] == "return_failure_money_on_balance"
        # The money left the balance (shown here directly on the lot): the note closes it.
        InvestorBalanceLot.objects.filter(id=_deposit_.balance_lot.id).update(
            available_amount_minor=0, withdrawn_amount_minor=1000_00, status="consumed"
        )
        resolved = client.post(
            f"/api/v1/ledger/admin/return-failures/{failure_id}/resolve/",
            data={"note": "The investor withdrew the money to a new account."},
            content_type="application/json",
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"
        investor_client = Client()
        investor_client.force_login(cast(Any, investor))
        assert investor_client.get("/api/v1/ledger/admin/return-failures/").status_code == 403


# --- Q02.5 ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_verify_a_return_account_from_the_deposit_with_evidence(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = _deposit(admin_user, investor, key="unverified", iban=NEW_IBAN, verify_account=False)
    # Audit S3-1: the deposit alone verified nothing.
    assert deposit.payout_instruction is None
    candidates = return_failures.deposit_verification_candidates(str(investor.pk))
    assert [row["payer_iban"] for row in candidates] == [NEW_IBAN]

    def verify(**overrides: Any) -> Any:
        values: dict[str, Any] = {
            "holder_matches_identity": True,
            "not_intermediary_account": True,
            "evidence_reference": "bank statement line 2026-01-05",
            **overrides,
        }
        return return_failures.verify_payout_account_from_deposit(
            return_failures.VerifyPayoutAccountFromDepositCommand(
                actor=admin_user,
                deposit_bank_operation_id=str(deposit.bank_operation.id),
                **values,
            )
        )

    # Audit S3-6: the registration name ("Return Investor") is typed by the investor. Without
    # the name from the approved identity check a deposit proves no account.
    assert return_failures.identity_reference(investor).verified_name == ""
    with pytest.raises(LedgerValidationError, match="no name from an approved identity check"):
        verify()
    case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    case_model.objects.filter(user_id=investor.pk).update(
        verified_full_name="Renate Maria Investor-Keller", provider_session_id="didit-session-1"
    )
    # A name on a case that is not approved is not a reference either.
    case_model.objects.filter(user_id=investor.pk).update(status="manual_review")
    with pytest.raises(LedgerValidationError, match="no name from an approved identity check"):
        verify()
    case_model.objects.filter(user_id=investor.pk).update(status="approved")

    with pytest.raises(LedgerValidationError, match="matches the investor's verified identity"):
        verify(holder_matches_identity=False)
    with pytest.raises(LedgerValidationError, match="collecting or intermediary"):
        verify(not_intermediary_account=False)
    with pytest.raises(LedgerValidationError, match="Evidence reference"):
        verify(evidence_reference=" ")
    instruction = verify()
    assert instruction.is_verified_usable and instruction.is_default_return
    evidence = instruction.metadata["verification"]
    assert evidence["method"] == "deposit"
    assert evidence["payer_iban"] == NEW_IBAN
    # The reference is the Didit name; the registration name is kept for information only.
    assert evidence["verified_identity_name"] == "Renate Maria Investor-Keller"
    assert evidence["identity_name_source"] == "identity_check"
    assert evidence["registration_name"] == "Return Investor"
    assert evidence["kyc_provider"] == "didit"
    assert evidence["kyc_provider_session_id"] == "didit-session-1"
    assert evidence["kyc_case_id"] == str(case_model.objects.get(user_id=investor.pk).pk)
    with pytest.raises(LedgerConflictError, match="already a verified bank account"):
        verify()
    assert return_failures.deposit_verification_candidates(str(investor.pk)) == []

    client.force_login(cast(Any, admin_user))
    listed = client.get(
        f"/api/v1/ledger/admin/investors/{investor.pk}/deposit-verification-candidates/"
    )
    assert listed.status_code == 200
    assert listed.json()["verified_identity_name"] == "Renate Maria Investor-Keller"
    assert listed.json()["registration_name"] == "Return Investor"
    assert listed.json()["identity_decision_at"] is not None
    assert listed.json()["results"] == []


@pytest.mark.django_db
def test_a_failed_return_stays_open_until_a_replacement_withdrawal_is_finalized(
    admin_user: Model,
    investor: Model,
) -> None:
    """Re-audit R3-1: the investor withdraws the money of a failed return; while that
    withdrawal is only requested the case stays open; when it is cancelled, the money is back
    and the scan creates no automatic return (the case is open)."""
    deposit, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="technical")
    code = issue_sensitive_action_test_code(investor, "withdrawal")
    with freeze_time(_at(date(2026, 3, 5), 9)):
        withdrawal = request_investor_withdrawal(
            RequestInvestorWithdrawalCommand(
                actor=investor,
                amount_minor=1000_00,
                currency="CHF",
                destination_iban=IBAN,
                destination_account_name="Return Investor",
                idempotency_key="withdraw-after-failure",
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
                pin=code.pin,
            )
        )
    assert _scan(admin_user, date(2026, 3, 6)).forced_withdrawal_requests == []
    failure.refresh_from_db()
    assert failure.status == "open"

    with freeze_time(_at(date(2026, 3, 6), 11)):
        cancel_investor_withdrawal(
            CancelInvestorWithdrawalCommand(
                actor=admin_user,
                withdrawal_request_id=str(withdrawal.id),
                reason="Investor asked to stop it.",
                idempotency_key="cancel-after-failure",
            )
        )
    deposit.balance_lot.refresh_from_db()
    assert deposit.balance_lot.available_amount_minor == 1000_00
    for day in (date(2026, 3, 9), date(2026, 3, 10)):
        assert _scan(admin_user, day).forced_withdrawal_requests == []
    failure.refresh_from_db()
    assert failure.status == "open"
    assert InvestorWithdrawalRequest.objects.filter(status="requested").count() == 0


@pytest.mark.django_db
def test_a_failed_return_closed_without_money_opens_again_when_the_money_comes_back(
    admin_user: Model,
    investor: Model,
) -> None:
    """Re-audit R3-1: a case closed as "no money left" opens again (with its task) when its lots
    have money again, and the scan does not return that money by itself."""
    deposit, forced = _forced_and_sent(admin_user, investor)
    failure = _returned(admin_user, forced, date(2026, 3, 4), reason="technical")
    lot = InvestorBalanceLot.objects.get(id=deposit.balance_lot.id)
    available = lot.available_amount_minor
    InvestorBalanceLot.objects.filter(id=lot.id).update(
        available_amount_minor=0,
        withdrawn_amount_minor=lot.withdrawn_amount_minor + available,
        status=BalanceLotStatus.CONSUMED,
    )
    _scan(admin_user, date(2026, 3, 5))
    failure.refresh_from_db()
    assert (failure.status, failure.resolution) == ("resolved", "no_money_left")

    InvestorBalanceLot.objects.filter(id=lot.id).update(
        available_amount_minor=available,
        withdrawn_amount_minor=lot.withdrawn_amount_minor,
        status=BalanceLotStatus.AVAILABLE,
    )
    assert _scan(admin_user, date(2026, 3, 6)).forced_withdrawal_requests == []
    failure.refresh_from_db()
    assert failure.status == "open"
    assert AuditEvent.objects.filter(
        action="ledger.balance_return_failure_reopened", target_id=str(failure.id)
    ).exists()
    [task] = _tasks("return_failed")
    assert str(task.status) != "resolved"
