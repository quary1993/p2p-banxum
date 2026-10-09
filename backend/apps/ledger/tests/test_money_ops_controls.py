"""Payout-IBAN controls, forced-return destination and money-ops regressions (round 2).

A-13 (IBAN verification, revocation, forced-return destination), A-19 (penalty mode
blocks investing), A-23 (reconciliation with escrow), A-25 (duplicate deposits across
collection-account spellings), A-26 (payee name, finalize evidence) and MONEY-23 / NEW-4.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date, datetime
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client

from backend.apps.ledger.models import (
    BalanceLotStatus,
    BankOperation,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorWithdrawalRequest,
)
from backend.apps.ledger.services import (
    CancelInvestorWithdrawalCommand,
    CreateReconciliationSnapshotCommand,
    ExecuteInvestorFxExchangeLedgerCommand,
    FinalizeInvestorWithdrawalCommand,
    LedgerConflictError,
    LedgerDuplicateDepositError,
    LedgerValidationError,
    RegisterInvestorPayoutInstructionCommand,
    RegisterInvestorSelfServicePayoutInstructionCommand,
    RequestInvestorWithdrawalCommand,
    ReserveInvestmentBalanceCommand,
    RevokeInvestorPayoutInstructionCommand,
    RunBalanceAgeingScanCommand,
    VerifyInvestorPayoutInstructionCommand,
    cancel_investor_withdrawal,
    create_reconciliation_snapshot,
    declare_lender_deposit,
    execute_investor_fx_exchange_ledger,
    finalize_investor_withdrawal,
    register_investor_payout_instruction,
    register_investor_self_service_payout_instruction,
    request_investor_withdrawal,
    reserve_investor_balance_for_investment,
    revoke_investor_payout_instruction,
    run_balance_ageing_scan,
    verify_investor_payout_instruction,
)
from backend.apps.ledger.tests.test_ledger_foundation import (
    _approve_financial_access,
    _deposit_command,
    _received_at,
    _register_verified_iban,
    _sensitive_code_payload,
)
from backend.apps.platform_core.models import (
    AuditEvent,
    DomainEvent,
    OutboxMessage,
    PlatformSetting,
)

DEPOSIT_IBAN = "CH9300762011623852957"
SECOND_IBAN = "CH5604835012345678009"
THIRD_IBAN = "DE89370400440532013000"


def _user(email: str, *, account_type: str, full_name: str) -> Model:
    user_model: Any = get_user_model()
    extra: dict[str, Any] = {"password": "AdminPass123!", "is_staff": True}
    if account_type != "admin":
        extra = {"is_staff": False}
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name=full_name,
            account_type=account_type,
            status="active",
            **extra,
        ),
    )


@pytest.fixture
def admin_user() -> Model:
    return _user("ops-admin@example.test", account_type="admin", full_name="Ops Admin")


@pytest.fixture
def investor() -> Model:
    return _user(
        "ops-investor@example.test",
        account_type="natural_person_lender",
        full_name="Ops Investor",
    )


@pytest.fixture
def other_investor() -> Model:
    return _user(
        "ops-other@example.test",
        account_type="natural_person_lender",
        full_name="Other Investor",
    )


def _request_iban(investor: Model, iban: str, name: str = "Ops Investor") -> Any:
    return register_investor_self_service_payout_instruction(
        RegisterInvestorSelfServicePayoutInstructionCommand(
            actor=investor,
            currency="CHF",
            destination_iban=iban,
            destination_account_name=name,
            **_sensitive_code_payload(investor, "bank_account_change"),
        )
    )


def _verify(admin_user: Model, instruction: Any, **kwargs: Any) -> Any:
    return verify_investor_payout_instruction(
        VerifyInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(instruction.pk),
            evidence_reference=kwargs.pop("evidence_reference", "bank-letter:ops"),
            **kwargs,
        )
    )


def _withdraw(investor: Model, *, iban: str, amount_minor: int, key: str, name: str = "") -> Any:
    return request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=amount_minor,
            currency="CHF",
            destination_iban=iban,
            destination_account_name=name,
            idempotency_key=key,
            **_sensitive_code_payload(investor, "withdrawal"),
        )
    )


def _finalize(admin_user: Model, withdrawal: Any, *, key: str, **kwargs: Any) -> Any:
    return finalize_investor_withdrawal(
        FinalizeInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(withdrawal.pk),
            booking_date=kwargs.pop("booking_date", date(2026, 1, 5)),
            value_date=kwargs.pop("value_date", date(2026, 1, 5)),
            collection_account_identifier=kwargs.pop(
                "collection_account_identifier", "CH00GARANTALEDGER"
            ),
            idempotency_key=key,
            **kwargs,
        )
    )


# --- A-13: admin verification controls ------------------------------------------------


@pytest.mark.django_db
def test_admin_cannot_verify_an_iban_the_investor_never_requested(
    admin_user: Model,
    investor: Model,
) -> None:
    with pytest.raises(LedgerValidationError, match="no pending request"):
        register_investor_payout_instruction(
            RegisterInvestorPayoutInstructionCommand(
                actor=admin_user,
                investor_user_id=str(investor.pk),
                currency="CHF",
                destination_iban=THIRD_IBAN,
                destination_account_name="Typo Person",
                evidence_reference="ticket-1",
            )
        )

    assert InvestorPayoutInstruction.objects.count() == 0


@pytest.mark.django_db
def test_verification_needs_evidence_and_unverify_is_refused(
    admin_user: Model,
    investor: Model,
) -> None:
    requested = _request_iban(investor, SECOND_IBAN)

    with pytest.raises(LedgerValidationError, match="Evidence reference is required"):
        _verify(admin_user, requested, evidence_reference="  ")
    requested.refresh_from_db()
    assert requested.is_verified_usable is False

    verified = _verify(admin_user, requested, evidence_reference="bank-letter:42")
    assert verified.is_verified_usable is True
    assert verified.metadata["verification"]["evidence_reference"] == "bank-letter:42"
    assert AuditEvent.objects.filter(
        action="ledger.investor_payout_instruction_verified",
        target_id=str(verified.pk),
    ).exists()

    # "is_verified_usable: false" used to answer 201 and change nothing.
    with pytest.raises(LedgerValidationError, match="revoke it"):
        register_investor_payout_instruction(
            RegisterInvestorPayoutInstructionCommand(
                actor=admin_user,
                investor_user_id=str(investor.pk),
                currency="CHF",
                destination_iban=SECOND_IBAN,
                destination_account_name="Ops Investor",
                is_verified_usable=False,
            )
        )
    verified.refresh_from_db()
    assert verified.is_verified_usable is True


@pytest.mark.django_db
def test_iban_verified_for_another_investor_needs_an_override_reason(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    # The other investor's deposit came from SECOND_IBAN, so it is verified for them.
    declare_lender_deposit(
        replace(
            _deposit_command(admin_user, other_investor, idempotency_key="other-deposit"),
            payer_account_identifier=SECOND_IBAN,
        )
    )
    requested = _request_iban(investor, SECOND_IBAN)

    with pytest.raises(LedgerConflictError) as conflict:
        _verify(admin_user, requested)
    assert conflict.value.code == "payout_iban_verified_for_other_investor"
    requested.refresh_from_db()
    assert requested.is_verified_usable is False

    verified = _verify(
        admin_user,
        requested,
        other_investor_override_reason="Joint account of spouses, bank letter on file.",
    )
    assert verified.is_verified_usable is True
    verification = verified.metadata["verification"]
    assert verification["other_investor_user_ids"] == [str(other_investor.pk)]
    assert verification["other_investor_override_reason"].startswith("Joint account")


# --- A-13: revocation ------------------------------------------------------------------


@pytest.mark.django_db
def test_revoked_iban_leaves_withdrawals_and_blocks_open_ones(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    second = _register_verified_iban(admin_user, investor, iban=SECOND_IBAN)
    open_withdrawal = _withdraw(investor, iban=SECOND_IBAN, amount_minor=40_00, key="wd-open")

    result = revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(second.pk),
            reason="Bank confirmed the account is closed.",
        )
    )

    second.refresh_from_db()
    open_withdrawal.refresh_from_db()
    assert result.action == "revoked"
    assert result.flagged_withdrawal_request_ids == [str(open_withdrawal.pk)]
    assert second.status == "disabled"
    assert second.is_verified_usable is False
    assert open_withdrawal.metadata["destination_revoked"]["reason"].startswith("Bank confirmed")
    assert AuditEvent.objects.filter(
        action="ledger.investor_payout_instruction_revoked",
        target_id=str(second.pk),
    ).exists()
    # One investor notice (portal and email); the admin's reason stays internal.
    email = OutboxMessage.objects.get(
        topic="email.payout_account_status", payload__subject="Payout IBAN no longer usable"
    )
    assert email.payload["user_id"] == str(investor.pk)
    assert "Open withdrawals to this account are stopped for review" in email.payload["body_text"]
    assert "Bank confirmed" not in str(email.payload)
    assert SECOND_IBAN not in str(email.payload)

    # The open withdrawal cannot be paid out to the revoked IBAN; it can be cancelled.
    with pytest.raises(LedgerConflictError) as blocked:
        _finalize(admin_user, open_withdrawal, key="wd-open-finalize")
    assert blocked.value.code == "withdrawal_destination_not_verified"
    cancel_investor_withdrawal(
        CancelInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(open_withdrawal.pk),
            reason="Destination IBAN revoked.",
            idempotency_key="wd-open-cancel",
        )
    )
    # New withdrawals to it are refused; a second revoke is a conflict.
    with pytest.raises(LedgerValidationError, match="verified bank account"):
        _withdraw(investor, iban=SECOND_IBAN, amount_minor=10_00, key="wd-after-revoke")
    with pytest.raises(LedgerConflictError):
        revoke_investor_payout_instruction(
            RevokeInvestorPayoutInstructionCommand(
                actor=admin_user,
                instruction_id=str(second.pk),
                reason="Again.",
            )
        )
    portal = __import__(
        "backend.apps.investor_portal.services", fromlist=["get_investor_balances"]
    )
    choices = portal.get_investor_balances(actor=investor)["payout_instructions"]
    assert [choice["destination_iban"] for choice in choices] == [DEPOSIT_IBAN]


@pytest.mark.django_db
def test_rejecting_a_pending_request_closes_its_task(
    admin_user: Model,
    investor: Model,
) -> None:
    requested = _request_iban(investor, SECOND_IBAN)
    task_model = apps.get_model("admin_ops", "AdminTask")
    task = task_model.objects.get(related_object_id=str(requested.pk))

    result = revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(requested.pk),
            reason="Account holder name does not match.",
        )
    )

    task.refresh_from_db()
    assert result.action == "rejected"
    assert task.status == "resolved"
    assert task.completion_note == "IBAN request rejected: Account holder name does not match."
    assert DomainEvent.objects.filter(
        event_type="InvestorPayoutInstructionRejected",
        aggregate_id=str(requested.pk),
    ).exists()
    with pytest.raises(LedgerConflictError):
        _verify(admin_user, requested)


# --- A-13: forced-return destination ----------------------------------------------------


@pytest.mark.django_db
def test_forced_return_goes_to_the_deposit_proven_iban_not_the_newest_verified(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    deposit = declare_lender_deposit(_deposit_command(admin_user, investor))
    # Verified later than the deposit IBAN, so the old "newest verified" rule picked it.
    _register_verified_iban(admin_user, investor, iban=SECOND_IBAN, account_name="Newer")

    result = run_balance_ageing_scan(
        RunBalanceAgeingScanCommand(actor=admin_user, as_of=_received_at(date(2026, 3, 3)))
    )

    forced = result.forced_withdrawal_requests[0]
    assert forced.destination_iban == DEPOSIT_IBAN
    assert forced.metadata["destination_selection"]["rule"] == "deposit_proven"
    assert forced.metadata["destination_selection"]["deposit_bank_operation_id"] == str(
        deposit.bank_operation.pk
    )
    assert result.forced_withdrawal_candidates[0].destination_rule == "deposit_proven"


@pytest.mark.django_db
def test_forced_return_after_revocation_uses_the_latest_admin_verified_iban(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    deposit = declare_lender_deposit(_deposit_command(admin_user, investor))
    _register_verified_iban(admin_user, investor, iban=SECOND_IBAN, account_name="Second")
    latest = _register_verified_iban(admin_user, investor, iban=THIRD_IBAN, account_name="Third")
    first_scan = run_balance_ageing_scan(
        RunBalanceAgeingScanCommand(actor=admin_user, as_of=_received_at(date(2026, 3, 3)))
    )
    first_forced = first_scan.forced_withdrawal_requests[0]
    assert first_forced.destination_iban == DEPOSIT_IBAN

    # The admin learns the deposit account is closed: revoke, cancel, and the next scan
    # returns the money to another verified IBAN instead of the same wrong one.
    assert deposit.payout_instruction is not None
    revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(deposit.payout_instruction.pk),
            reason="Account closed.",
        )
    )
    cancel_investor_withdrawal(
        CancelInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(first_forced.pk),
            reason="Destination IBAN revoked.",
            idempotency_key="forced-cancel",
        )
    )
    next_scan = run_balance_ageing_scan(
        RunBalanceAgeingScanCommand(actor=admin_user, as_of=_received_at(date(2026, 3, 4)))
    )

    second_forced = next_scan.forced_withdrawal_requests[0]
    assert second_forced.destination_iban == THIRD_IBAN
    assert second_forced.destination_account_name == "Third"
    selection = second_forced.metadata["destination_selection"]
    assert selection["rule"] == "admin_verified"
    assert selection["payout_instruction_id"] == str(latest.pk)


# --- A-19: penalty mode blocks investing --------------------------------------------------


def _penalty_mode_investor(admin_user: Model, investor: Model) -> InvestorBalanceLot:
    old = declare_lender_deposit(_deposit_command(admin_user, investor, idempotency_key="old"))
    assert old.payout_instruction is not None
    revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(old.payout_instruction.pk),
            reason="Returned by the bank.",
        )
    )
    run_balance_ageing_scan(
        RunBalanceAgeingScanCommand(actor=admin_user, as_of=_received_at(date(2026, 3, 3)))
    )
    lot = InvestorBalanceLot.objects.get(id=old.balance_lot.id)
    assert lot.status == BalanceLotStatus.PENALTY_MODE
    return lot


@pytest.mark.django_db
def test_penalty_mode_investor_cannot_reserve_a_primary_investment(
    admin_user: Model,
    investor: Model,
) -> None:
    _penalty_mode_investor(admin_user, investor)
    fresh = declare_lender_deposit(
        replace(
            _deposit_command(
                admin_user,
                investor,
                amount_minor=1_000_00,
                value_date=date(2026, 3, 3),
                idempotency_key="fresh",
            ),
            payer_account_identifier=SECOND_IBAN,
        )
    )

    with pytest.raises(LedgerValidationError, match="Investing is not possible: your account"):
        reserve_investor_balance_for_investment(
            ReserveInvestmentBalanceCommand(
                actor=admin_user,
                investor_user_id=str(investor.pk),
                loan_id=str(uuid.uuid4()),
                amount_minor=400_00,
                currency="CHF",
                loan_funding_deadline=date(2026, 3, 10),
                source_type="primary_investment_order",
                source_id="order-1",
                idempotency_key="reserve-penalty",
                as_of=_received_at(date(2026, 3, 3)),
            )
        )
    lot = InvestorBalanceLot.objects.get(id=fresh.balance_lot.id)
    assert lot.available_amount_minor == 1_000_00


# --- A-23: reconciliation with escrow -------------------------------------------------------


@pytest.mark.django_db
def test_reconciliation_snapshot_counts_money_reserved_for_open_orders(
    admin_user: Model,
    investor: Model,
) -> None:
    declare_lender_deposit(
        _deposit_command(admin_user, investor, amount_minor=1_000_00, value_date=date(2026, 3, 1))
    )
    reserve_investor_balance_for_investment(
        ReserveInvestmentBalanceCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            loan_id=str(uuid.uuid4()),
            amount_minor=400_00,
            currency="CHF",
            loan_funding_deadline=date(2026, 3, 20),
            source_type="primary_investment_order",
            source_id="order-escrow",
            idempotency_key="reserve-escrow",
            as_of=_received_at(date(2026, 3, 2)),
        )
    )

    matching = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 3, 2),
            bank_stated_balance_minor=1_000_00,
        )
    )
    off_by_one = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 3, 2),
            bank_stated_balance_minor=1_000_01,
        )
    )

    assert matching.reconciliation_difference_minor == 0
    assert matching.metadata["loan_funding_escrow_minor"] == 400_00
    assert matching.metadata["expected_bank_balance_minor"] == 1_000_00
    assert matching.metadata["bank_to_collection_cash_difference_minor"] == 0
    assert not DomainEvent.objects.filter(
        event_type="LedgerReconciliationBreakDetected",
        aggregate_id=str(matching.pk),
    ).exists()
    assert off_by_one.reconciliation_difference_minor == 1


# --- A-25: duplicate deposits across collection-account spellings --------------------------


def _configure_collection_accounts() -> None:
    PlatformSetting.objects.update_or_create(
        key="payments.deposit_instructions_by_currency",
        defaults={
            "value": {
                "CHF": {
                    "collection_account_identifier": "Garanta_CHF",
                    "iban": "CH1183019GARANTAFI001",
                    "qr_iban": "CH8330334GARANTAFI001",
                },
                "EUR": {"collection_account_identifier": "Garanta_EUR"},
            },
            "value_type": "json",
        },
    )


@pytest.mark.django_db
def test_duplicate_deposit_is_caught_whatever_the_collection_account_spelling(
    admin_user: Model,
    investor: Model,
) -> None:
    _configure_collection_accounts()
    first = declare_lender_deposit(
        replace(
            _deposit_command(admin_user, investor, idempotency_key="dup-1"),
            collection_account_identifier="Garanta_CHF",
            bank_reference="",
            payment_reference="",
        )
    )
    for index, spelling in enumerate(
        ["Garanta CHF", "garanta-chf", " GARANTA_CHF ", "CH11 8301 9GAR ANTA FI001"]
    ):
        with pytest.raises(LedgerDuplicateDepositError):
            declare_lender_deposit(
                replace(
                    _deposit_command(admin_user, investor, idempotency_key=f"dup-variant-{index}"),
                    collection_account_identifier=spelling,
                    bank_reference="",
                    payment_reference="",
                )
            )

    assert BankOperation.objects.filter(operation_type="lender_deposit").count() == 1
    assert first.bank_operation.collection_account_identifier == "Garanta_CHF"


@pytest.mark.django_db
def test_deposit_without_collection_account_uses_the_configured_one(
    admin_user: Model,
    investor: Model,
) -> None:
    _configure_collection_accounts()
    spelled = declare_lender_deposit(
        replace(
            _deposit_command(admin_user, investor, idempotency_key="spelled"),
            collection_account_identifier="garanta chf",
        )
    )
    blank = declare_lender_deposit(
        replace(
            _deposit_command(
                admin_user,
                investor,
                idempotency_key="blank",
                value_date=date(2026, 1, 2),
            ),
            collection_account_identifier="",
        )
    )

    assert spelled.bank_operation.collection_account_identifier == "Garanta_CHF"
    assert blank.bank_operation.collection_account_identifier == "Garanta_CHF"


# --- A-26: payee name and finalize -----------------------------------------------------------


@pytest.mark.django_db
def test_withdrawal_payee_name_comes_from_the_verified_instruction(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))

    withdrawal = _withdraw(
        investor,
        iban=DEPOSIT_IBAN,
        amount_minor=25_00,
        key="wd-payee",
        name="Somebody Else GmbH",
    )
    result = _finalize(admin_user, withdrawal, key="wd-payee-finalize")

    assert withdrawal.destination_account_name == "Ledger Investor"
    assert withdrawal.metadata["requested_destination_account_name"] == "Somebody Else GmbH"
    assert result.bank_operation.payee_name == "Ledger Investor"


@pytest.mark.django_db
def test_finalizing_a_finalized_withdrawal_again_is_a_conflict(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    withdrawal = _withdraw(investor, iban=DEPOSIT_IBAN, amount_minor=25_00, key="wd-twice")
    first = _finalize(admin_user, withdrawal, key="wd-twice-finalize")

    replay = _finalize(admin_user, withdrawal, key="wd-twice-finalize")
    with pytest.raises(LedgerConflictError) as conflict:
        _finalize(
            admin_user,
            withdrawal,
            key="wd-twice-finalize-2",
            value_date=date(2026, 1, 6),
            bank_reference="OTHER",
        )

    assert replay.bank_operation.pk == first.bank_operation.pk
    assert conflict.value.code == "withdrawal_already_finalized"
    assert BankOperation.objects.filter(operation_type="lender_withdrawal").count() == 1


@pytest.mark.django_db
def test_withdrawal_finalize_uses_the_configured_collection_account_when_blank(
    admin_user: Model,
    investor: Model,
) -> None:
    _configure_collection_accounts()
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    withdrawal = _withdraw(investor, iban=DEPOSIT_IBAN, amount_minor=25_00, key="wd-blank")

    result = _finalize(
        admin_user,
        withdrawal,
        key="wd-blank-finalize",
        collection_account_identifier="",
        bank_reference="BANK-77",
        evidence_reference="statement:77",
    )

    assert result.bank_operation.collection_account_identifier == "Garanta_CHF"
    assert result.withdrawal_request.evidence_reference == "statement:77"


# --- NEW-4: FX lot made after the day's scan --------------------------------------------------


@pytest.mark.django_db
def test_fx_lot_made_after_the_days_scan_gets_no_late_repeat_of_that_reminder(
    admin_user: Model,
    investor: Model,
) -> None:
    deposit = declare_lender_deposit(_deposit_command(admin_user, investor))
    # Day 53 of the deposit (value date 2026-01-01, day 0) is 2026-02-23.
    day_53 = datetime(2026, 2, 23, 9, 0, tzinfo=_received_at(date(2026, 2, 23)).tzinfo)
    run_balance_ageing_scan(RunBalanceAgeingScanCommand(actor=admin_user, as_of=day_53))
    assert DomainEvent.objects.filter(
        idempotency_key=f"balance-lot:{deposit.balance_lot.id}:ageing-reminder-day:53"
    ).exists()
    fx = execute_investor_fx_exchange_ledger(
        ExecuteInvestorFxExchangeLedgerCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            source_currency="CHF",
            target_currency="EUR",
            source_amount_minor=50_00,
            target_amount_minor=52_00,
            gross_target_amount_minor=53_00,
            fee_minor=1_00,
            source_type="fx_exchange",
            source_id="fx-after-scan",
            idempotency_key="fx-after-scan",
            as_of=datetime(2026, 2, 23, 15, 0, tzinfo=day_53.tzinfo),
        )
    )
    fx_lot = InvestorBalanceLot.objects.get(currency_id="EUR", investor_user_id=investor.pk)
    assert fx is not None

    next_day = run_balance_ageing_scan(
        RunBalanceAgeingScanCommand(
            actor=admin_user,
            as_of=datetime(2026, 2, 24, 9, 0, tzinfo=day_53.tzinfo),
        )
    )

    assert [
        reminder.day for reminder in next_day.reminders_due if reminder.lot_id == str(fx_lot.id)
    ] == []


# --- API --------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_payout_iban_api_lists_verifies_and_revokes(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    requested = _request_iban(investor, SECOND_IBAN)
    client.force_login(cast(Any, admin_user))

    pending = client.get("/api/v1/ledger/admin/payout-instructions/?state=pending")
    missing_evidence = client.post(
        f"/api/v1/ledger/admin/payout-instructions/{requested.pk}/verify/",
        data={"evidence_reference": ""},
        content_type="application/json",
    )
    verified = client.post(
        f"/api/v1/ledger/admin/payout-instructions/{requested.pk}/verify/",
        data={"evidence_reference": "bank-letter:api"},
        content_type="application/json",
    )
    again = client.post(
        f"/api/v1/ledger/admin/payout-instructions/{requested.pk}/verify/",
        data={"evidence_reference": "bank-letter:api"},
        content_type="application/json",
    )
    revoked = client.post(
        f"/api/v1/ledger/admin/payout-instructions/{requested.pk}/revoke/",
        data={"reason": "Account closed."},
        content_type="application/json",
    )
    detail = client.get(f"/api/v1/ledger/admin/payout-instructions/{requested.pk}/")
    accounts = client.get("/api/v1/ledger/admin/collection-accounts/")

    assert pending.status_code == 200
    rows = pending.json()["results"]
    assert [row["id"] for row in rows] == [str(requested.pk)]
    assert rows[0]["state"] == "pending"
    assert rows[0]["investor_name"] == "Ops Investor"
    assert rows[0]["origin"] == "investor_request"
    assert missing_evidence.status_code == 400
    assert verified.status_code == 200
    assert verified.json()["payout_instruction"]["is_verified_usable"] is True
    assert again.status_code == 409
    assert again.json()["code"] == "payout_iban_already_verified"
    assert revoked.status_code == 200
    assert revoked.json()["action"] == "revoked"
    assert detail.json()["state"] == "revoked"
    assert detail.json()["revocation_reason"] == "Account closed."
    assert accounts.status_code == 200
    assert {row["currency"] for row in accounts.json()} >= {"CHF", "EUR"}

    client.force_login(cast(Any, investor))
    assert client.get("/api/v1/ledger/admin/payout-instructions/").status_code == 403
    assert (
        client.post(
            f"/api/v1/ledger/admin/payout-instructions/{requested.pk}/revoke/",
            data={"reason": "x"},
            content_type="application/json",
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_finalize_api_answers_409_for_a_second_finalization(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    withdrawal = _withdraw(investor, iban=DEPOSIT_IBAN, amount_minor=25_00, key="wd-api-409")
    client.force_login(cast(Any, admin_user))
    url = f"/api/v1/ledger/admin/withdrawal-requests/{withdrawal.pk}/finalize/"
    payload = {
        "booking_date": "2026-01-05",
        "value_date": "2026-01-05",
        "collection_account_identifier": "CH00GARANTALEDGER",
        "idempotency_key": "api-finalize-1",
    }

    first = client.post(url, data=payload, content_type="application/json")
    replay = client.post(url, data=payload, content_type="application/json")
    second = client.post(
        url,
        data={**payload, "idempotency_key": "api-finalize-2"},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "withdrawal_already_finalized"
    assert InvestorWithdrawalRequest.objects.get(pk=withdrawal.pk).status == "finalized"
