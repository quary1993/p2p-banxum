"""Investor notices for deposits, withdrawals, forced returns, penalty mode and payout IBANs."""

from __future__ import annotations

from datetime import date, datetime, time
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import override_settings
from django.utils import timezone

from backend.apps.ledger.models import InvestorPayoutInstruction
from backend.apps.ledger.notices import notify_payout_instruction_saved
from backend.apps.ledger.services import (
    CancelInvestorWithdrawalCommand,
    DeclareLenderDepositCommand,
    FinalizeInvestorWithdrawalCommand,
    RegisterInvestorSelfServicePayoutInstructionCommand,
    RequestInvestorWithdrawalCommand,
    RevokeInvestorPayoutInstructionCommand,
    RunBalanceAgeingScanCommand,
    VerifyInvestorPayoutInstructionCommand,
    cancel_investor_withdrawal,
    declare_lender_deposit,
    finalize_investor_withdrawal,
    register_investor_self_service_payout_instruction,
    request_investor_withdrawal,
    revoke_investor_payout_instruction,
    run_balance_ageing_scan,
    verify_investor_payout_instruction,
)
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code
from backend.apps.platform_core.tests.notices import (
    assert_renders_to,
    investor_notices,
    only_notice,
    payload_text,
)

IBAN = "CH9300762011623852957"
SECOND_IBAN = "CH5604835012345678009"
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("notice_settings"),
]


@pytest.fixture
def notice_settings() -> Any:
    with override_settings(
        PUBLIC_APP_BASE_URL="https://app.banxum.test", BALANCE_PENALTY_BPS_PER_DAY=100
    ):
        yield


@pytest.fixture
def admin_user() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="notice-admin@example.test",
            password="AdminPass123!",
            full_name="Notice Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def _investor(email: str) -> Model:
    user = cast(
        Model,
        get_user_model().objects.create_user(
            email=email,
            full_name="Notice Investor",
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


@pytest.fixture
def investor() -> Model:
    return _investor("notice-investor@example.test")


def _code(user: Model, action: str) -> dict[str, str]:
    code = issue_sensitive_action_test_code(user, action)
    return {"sensitive_action_code_id": code.code_id, "sensitive_action_code": code.raw_code}


def _deposit(
    admin_user: Model,
    investor: Model,
    *,
    key: str,
    amount_minor: int = 25_000_00,
    value_date: date = date(2026, 1, 5),
    iban: str = IBAN,
) -> Any:
    return declare_lender_deposit(
        DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency="CHF",
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="CH00GARANTALEDGER",
            payer_name="Notice Investor",
            payer_account_identifier=iban,
            bank_reference=f"BANK-{key}",
            payment_reference=f"BX-CHF-{key}",
            evidence_reference=f"statement:{key}",
            idempotency_key=key,
        )
    )


def _at(value: date, hour: int = 0, minute: int = 30) -> datetime:
    return datetime.combine(value, time(hour, minute), tzinfo=business_timezone())


def test_deposit_credit_sends_one_notice_with_amount_value_date_and_hold_limit(
    admin_user: Model, investor: Model
) -> None:
    result = _deposit(admin_user, investor, key="dep-1")
    # The same bank movement declared again (idempotent replay) creates no second notice.
    _deposit(admin_user, investor, key="dep-1")

    notice = only_notice(investor, "email.deposit_reconciled")
    assert notice.payload["email"] == "notice-investor@example.test"
    assert notice.payload["subject"] == "Deposit credited: CHF 25'000.00"
    body = notice.payload["body_text"]
    assert "CHF 25'000.00" in body
    assert "Value date: 2026-01-05" in body
    # Received 2026-01-05 (Europe/Zurich): the money can stay until day 60, 2026-03-06.
    assert "until 2026-03-06" in body
    assert notice.payload["metadata"]["navigation_target"] == "balances"
    assert notice.payload["metadata"]["bank_operation_id"] == str(result.bank_operation.id)
    assert_renders_to(notice, investor, "CHF 25'000.00", "2026-03-06")

    # The deposit verified the sending IBAN: one notice, IBAN masked, never in full.
    iban_notice = only_notice(investor, "email.payout_account_status")
    assert iban_notice.payload["subject"] == "Payout IBAN verified"
    assert "IBAN ending 2957" in iban_notice.payload["body_text"]
    assert IBAN not in payload_text(iban_notice)
    assert IBAN not in payload_text(notice)

    # A second deposit from the same, already verified IBAN: a deposit notice, no IBAN notice.
    _deposit(admin_user, investor, key="dep-2", amount_minor=1_00, value_date=date(2026, 1, 6))
    assert len(investor_notices(investor, "email.deposit_reconciled")) == 2
    assert len(investor_notices(investor, "email.payout_account_status")) == 1


def test_withdrawal_requested_sent_and_cancelled_each_send_one_notice(
    admin_user: Model, investor: Model
) -> None:
    _deposit(admin_user, investor, key="dep-w")
    command = RequestInvestorWithdrawalCommand(
        actor=investor,
        amount_minor=250_00,
        currency="CHF",
        destination_iban=IBAN,
        destination_account_name="Notice Investor",
        idempotency_key="withdraw-1",
        **_code(investor, "withdrawal"),
    )
    withdrawal = request_investor_withdrawal(command)
    request_investor_withdrawal(command)

    requested = only_notice(investor, "email.withdrawal_status")
    assert requested.payload["subject"] == "Withdrawal requested: CHF 250.00"
    assert "IBAN ending 2957" in requested.payload["body_text"]
    assert IBAN not in payload_text(requested)
    assert requested.payload["metadata"]["withdrawal_event"] == "requested"
    assert_renders_to(requested, investor, "CHF 250.00")

    finalize = FinalizeInvestorWithdrawalCommand(
        actor=admin_user,
        withdrawal_request_id=str(withdrawal.id),
        booking_date=date(2026, 1, 8),
        value_date=date(2026, 1, 8),
        collection_account_identifier="CH00GARANTALEDGER",
        bank_reference="OUT-1",
        payment_reference="BX-OUT-1",
        evidence_reference="statement:out-1",
        idempotency_key="finalize-1",
    )
    finalize_investor_withdrawal(finalize)
    finalize_investor_withdrawal(finalize)
    sent = [
        notice
        for notice in investor_notices(investor, "email.withdrawal_status")
        if notice.payload["metadata"]["withdrawal_event"] == "finalized"
    ]
    assert len(sent) == 1
    assert sent[0].payload["subject"] == "Withdrawal sent: CHF 250.00"
    assert "Value date: 2026-01-08" in sent[0].payload["body_text"]
    assert_renders_to(sent[0], investor, "CHF 250.00", "2026-01-08")

    second = request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=1_000_00,
            currency="CHF",
            destination_iban=IBAN,
            destination_account_name="Notice Investor",
            idempotency_key="withdraw-2",
            **_code(investor, "withdrawal"),
        )
    )
    cancel = CancelInvestorWithdrawalCommand(
        actor=admin_user,
        withdrawal_request_id=str(second.id),
        reason="Internal: duplicate request.",
        idempotency_key="cancel-2",
    )
    cancel_investor_withdrawal(cancel)
    cancel_investor_withdrawal(cancel)
    cancelled = [
        notice
        for notice in investor_notices(investor, "email.withdrawal_status")
        if notice.payload["metadata"]["withdrawal_event"] == "cancelled"
    ]
    assert len(cancelled) == 1
    assert cancelled[0].payload["subject"] == "Withdrawal cancelled: CHF 1'000.00"
    # The admin's internal reason is not sent to the investor.
    assert "duplicate" not in payload_text(cancelled[0])
    assert_renders_to(cancelled[0], investor, "CHF 1'000.00")
    assert len(investor_notices(investor, "email.withdrawal_status")) == 4


def test_day_61_forced_return_and_penalty_mode_send_one_notice_each(
    admin_user: Model, investor: Model
) -> None:
    other = _investor("notice-penalty@example.test")
    _deposit(admin_user, investor, key="forced", amount_minor=1_000_00, value_date=date(2026, 1, 1))
    first = _deposit(
        admin_user, other, key="pen-1", amount_minor=600_00, value_date=date(2026, 1, 1)
    )
    _deposit(admin_user, other, key="pen-2", amount_minor=400_00, value_date=date(2026, 1, 2))
    # No usable IBAN for the second investor: day 61 means penalty mode, not a return.
    InvestorPayoutInstruction.objects.filter(investor_user_id=other.pk).update(status="disabled")
    assert first.payout_instruction is not None

    for day in (date(2026, 3, 3), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5)):
        run_balance_ageing_scan(RunBalanceAgeingScanCommand(actor=admin_user, as_of=_at(day)))

    forced = only_notice(investor, "email.balance_forced_return")
    assert forced.payload["subject"] == "We are returning CHF 1'000.00 to your bank account"
    assert "IBAN ending 2957" in forced.payload["body_text"]
    assert "Started on" in [row[0] for row in forced.payload["data_rows"]]
    assert ["Started on", "2026-03-03"] in forced.payload["data_rows"]
    assert_renders_to(forced, investor, "CHF 1'000.00")
    assert not investor_notices(investor, "email.balance_penalty_mode")

    # Two lots entered penalty mode on different days, daily charges followed: the investor
    # gets one notice per entry day, never one per charge.
    penalty = investor_notices(other, "email.balance_penalty_mode")
    assert [notice.payload["metadata"]["as_of"][:10] for notice in penalty] == [
        "2026-03-03",
        "2026-03-04",
    ]
    assert penalty[0].payload["metadata"]["amount_minor"] == 600_00
    assert "CHF 600.00" in penalty[0].payload["body_text"]
    assert "1% per day" in penalty[0].payload["body_text"]
    assert "frozen" in penalty[0].payload["body_text"]
    assert_renders_to(penalty[0], other, "CHF 600.00")
    assert not investor_notices(other, "email.balance_forced_return")


def test_payout_iban_added_rejected_verified_and_revoked_notices(
    admin_user: Model, investor: Model
) -> None:
    register_investor_self_service_payout_instruction(
        RegisterInvestorSelfServicePayoutInstructionCommand(
            actor=investor,
            currency="CHF",
            destination_iban=SECOND_IBAN,
            destination_account_name="Notice Investor",
            **_code(investor, "bank_account_change"),
        )
    )
    added = only_notice(investor, "email.payout_account_status")
    assert added.payload["subject"] == "Payout IBAN added"
    assert "IBAN ending 8009" in added.payload["body_text"]
    assert SECOND_IBAN not in payload_text(added)
    assert_renders_to(added, investor, "IBAN ending 8009")

    # The admin rejects the request: one "not verified" notice; the reason stays internal.
    pending = InvestorPayoutInstruction.objects.get(destination_iban=SECOND_IBAN, status="active")
    revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user, instruction_id=str(pending.pk), reason="Name does not match."
        )
    )
    notices = investor_notices(investor, "email.payout_account_status")
    assert [notice.payload["subject"] for notice in notices] == [
        "Payout IBAN added",
        "Payout IBAN not verified",
    ]
    assert "Name does not match." not in payload_text(notices[1])
    assert_renders_to(notices[1], investor, "IBAN ending 8009")
    # Closing a verification task never sends a second rejection notice.
    assert (
        not apps.get_model("platform_core", "OutboxMessage")
        .objects.filter(topic="email.payout_iban_status")
        .exists()
    )

    # The investor adds it again and an admin verifies it with evidence.
    register_investor_self_service_payout_instruction(
        RegisterInvestorSelfServicePayoutInstructionCommand(
            actor=investor,
            currency="CHF",
            destination_iban=SECOND_IBAN,
            destination_account_name="Notice Investor",
            **_code(investor, "bank_account_change"),
        )
    )
    again = InvestorPayoutInstruction.objects.get(destination_iban=SECOND_IBAN, status="active")
    verify_investor_payout_instruction(
        VerifyInvestorPayoutInstructionCommand(
            actor=admin_user, instruction_id=str(again.pk), evidence_reference="Bank letter 7"
        )
    )
    notices = investor_notices(investor, "email.payout_account_status")
    assert [notice.payload["subject"] for notice in notices][2:] == [
        "Payout IBAN added",
        "Payout IBAN verified",
    ]

    # A verified IBAN that an admin revokes is announced once, without the internal reason.
    revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user, instruction_id=str(again.pk), reason="Account closed."
        )
    )
    notices = investor_notices(investor, "email.payout_account_status")
    assert notices[-1].payload["subject"] == "Payout IBAN no longer usable"
    assert "Account closed." not in payload_text(notices[-1])
    assert len(notices) == 5

    # A repeated "no longer usable" event for the same change is not sent again.
    again.refresh_from_db()
    notify_payout_instruction_saved(again, created=False, previously_verified=True)
    assert len(investor_notices(investor, "email.payout_account_status")) == 5


def test_payout_iban_notices_do_not_depend_on_the_clock(
    admin_user: Model, investor: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Verify 2026-10-09 (FAIL-2): under a frozen QA clock every event of one day had the
    # same time, so a re-added, re-verified or re-revoked IBAN lost its notice.
    frozen = timezone.now().replace(microsecond=0)
    time_module = import_module("backend.apps.platform_core.domain.time")
    monkeypatch.setattr(time_module, "_qa_dev_mode_time_override", lambda: frozen)

    def add() -> InvestorPayoutInstruction:
        register_investor_self_service_payout_instruction(
            RegisterInvestorSelfServicePayoutInstructionCommand(
                actor=investor,
                currency="CHF",
                destination_iban=SECOND_IBAN,
                destination_account_name="Notice Investor",
                **_code(investor, "bank_account_change"),
            )
        )
        return InvestorPayoutInstruction.objects.get(destination_iban=SECOND_IBAN, status="active")

    def revoke(instruction: InvestorPayoutInstruction) -> None:
        revoke_investor_payout_instruction(
            RevokeInvestorPayoutInstructionCommand(
                actor=admin_user, instruction_id=str(instruction.pk), reason="Checked."
            )
        )

    revoke(add())
    instruction = add()
    verify_investor_payout_instruction(
        VerifyInvestorPayoutInstructionCommand(
            actor=admin_user, instruction_id=str(instruction.pk), evidence_reference="Letter 1"
        )
    )
    revoke(instruction)
    instruction = add()
    verify_investor_payout_instruction(
        VerifyInvestorPayoutInstructionCommand(
            actor=admin_user, instruction_id=str(instruction.pk), evidence_reference="Letter 2"
        )
    )
    # A repeated call for the same change sends nothing new.
    instruction.refresh_from_db()
    notify_payout_instruction_saved(instruction, created=False, previously_verified=False)

    subjects = [
        n.payload["subject"] for n in investor_notices(investor, "email.payout_account_status")
    ]
    assert subjects == [
        "Payout IBAN added",
        "Payout IBAN not verified",
        "Payout IBAN added",
        "Payout IBAN verified",
        "Payout IBAN no longer usable",
        "Payout IBAN added",
        "Payout IBAN verified",
    ]
