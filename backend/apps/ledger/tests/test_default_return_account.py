# IP of Webby-Soft SRL.
"""U33-DEC-05: one default return account per currency, verified/pending states, and the
hand check of the paying account before a deposit's IBAN becomes a return account."""

from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client

from backend.apps.ledger import services as ledger_services
from backend.apps.ledger.models import BankOperation, InvestorPayoutInstruction
from backend.apps.ledger.services import (
    RevokeInvestorPayoutInstructionCommand,
    RunBalanceAgeingScanCommand,
    revoke_investor_payout_instruction,
    run_balance_ageing_scan,
)
from backend.apps.ledger.tests.test_ledger_foundation import (
    _approve_financial_access,
    _deposit_command,
    _received_at,
    _register_verified_iban,
    _sensitive_code_payload,
)
from backend.apps.ledger.tests.test_money_ops_controls import (
    DEPOSIT_IBAN,
    SECOND_IBAN,
    THIRD_IBAN,
    _request_iban,
    admin_user,
    investor,
    other_investor,
)
from backend.apps.platform_core.models import AuditEvent, OutboxMessage

# Audit S3-1: a deposit alone verifies no account; these tests need the account the admin
# verifies after it.
from backend.apps.platform_core.tests.deposit_accounts import (
    declare_deposit_and_verify_account as declare_lender_deposit,
)
from backend.apps.platform_core.tests.deposit_accounts import verify_account_from_deposit

__all__ = ["admin_user", "investor", "other_investor"]


def _default_url(instruction: Any) -> str:
    return f"/api/v1/ledger/payout-instructions/{instruction.pk}/default/"


def _defaults(investor: Model) -> list[str]:
    return list(
        InvestorPayoutInstruction.objects.filter(
            investor_user_id=investor.pk, is_default_return=True, status="active"
        ).values_list("destination_iban", flat=True)
    )


@pytest.mark.django_db
def test_investor_chooses_the_default_return_account_with_code_and_pin(
    admin_user: Model, investor: Model
) -> None:
    _approve_financial_access(investor)
    deposit = declare_lender_deposit(_deposit_command(admin_user, investor))
    assert deposit.payout_instruction is not None
    second = _register_verified_iban(admin_user, investor, iban=SECOND_IBAN, account_name="Second")
    # The first verified account is the default; a later one does not take over by itself.
    assert _defaults(investor) == [DEPOSIT_IBAN]

    client = Client()
    client.force_login(cast(Any, investor))
    response = client.post(
        _default_url(second),
        data=_sensitive_code_payload(investor, "bank_account_change"),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["payout_instruction"]["is_default_return"] is True
    assert _defaults(investor) == [SECOND_IBAN]
    assert AuditEvent.objects.filter(
        action="ledger.investor_default_return_account_changed", target_id=str(second.pk)
    ).exists()
    notices = OutboxMessage.objects.filter(payload__metadata__payout_event="default_changed")
    assert notices.count() == 1

    balances = client.get("/api/v1/investor/portal/balances/").json()
    by_iban = {row["destination_iban"]: row for row in balances["payout_instructions"]}
    assert by_iban[SECOND_IBAN]["is_default_return"] is True
    assert by_iban[SECOND_IBAN]["verification_status"] == "verified"
    assert by_iban[DEPOSIT_IBAN]["is_default_return"] is False

    # Money that goes back to the bank uses the investor's choice.
    result = run_balance_ageing_scan(
        RunBalanceAgeingScanCommand(actor=admin_user, as_of=_received_at(date(2026, 3, 3)))
    )
    forced = result.forced_withdrawal_requests[0]
    assert forced.destination_iban == SECOND_IBAN
    assert forced.metadata["destination_selection"]["rule"] == "default_return_account"

    # Switching back is announced again (one notice per change).
    back = client.post(
        _default_url(deposit.payout_instruction),
        data=_sensitive_code_payload(investor, "bank_account_change"),
        content_type="application/json",
    )
    assert back.status_code == 200
    assert notices.count() == 2


@pytest.mark.django_db
def test_only_the_investors_own_verified_account_can_be_the_default(
    admin_user: Model, investor: Model, other_investor: Model
) -> None:
    _approve_financial_access(investor)
    pending = _request_iban(investor, THIRD_IBAN)
    client = Client()
    client.force_login(cast(Any, investor))

    response = client.post(
        _default_url(pending),
        data=_sensitive_code_payload(investor, "bank_account_change"),
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "payout_iban_not_verified"

    balances = client.get("/api/v1/investor/portal/balances/").json()
    assert balances["payout_instructions"][0]["verification_status"] == "pending"
    assert balances["payout_instructions"][0]["is_default_return"] is False

    _approve_financial_access(other_investor)
    others = _register_verified_iban(admin_user, other_investor, iban=SECOND_IBAN)
    response = client.post(
        _default_url(others),
        data=_sensitive_code_payload(investor, "bank_account_change"),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert _defaults(other_investor) == [SECOND_IBAN]

    # Without the code and the PIN nothing changes.
    empty = client.post(_default_url(pending), data={}, content_type="application/json")
    assert empty.status_code == 400


@pytest.mark.django_db
def test_revoking_the_default_moves_it_to_another_verified_account(
    admin_user: Model, investor: Model
) -> None:
    _approve_financial_access(investor)
    deposit = declare_lender_deposit(_deposit_command(admin_user, investor))
    assert deposit.payout_instruction is not None
    latest = _register_verified_iban(admin_user, investor, iban=THIRD_IBAN, account_name="Third")

    revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(deposit.payout_instruction.pk),
            reason="Account closed.",
        )
    )
    assert _defaults(investor) == [THIRD_IBAN]
    deposit.payout_instruction.refresh_from_db()
    assert deposit.payout_instruction.is_default_return is False
    assert deposit.payout_instruction.metadata["revocation"]["was_default_return"] is True

    revoke_investor_payout_instruction(
        RevokeInvestorPayoutInstructionCommand(
            actor=admin_user, instruction_id=str(latest.pk), reason="Account closed."
        )
    )
    assert _defaults(investor) == []


@pytest.mark.django_db
def test_a_deposit_alone_never_makes_a_return_account(admin_user: Model, investor: Model) -> None:
    """Audit S3-1 (U33-DEC-05): the money is credited, but no account is verified, also when the
    payer name equals the investor's name. Only "verify from deposit" does that."""
    _approve_financial_access(investor)
    result = ledger_services.declare_lender_deposit(_deposit_command(admin_user, investor))
    assert result.balance_lot.available_amount_minor == 100_00
    assert result.payout_instruction is None
    assert not InvestorPayoutInstruction.objects.filter(investor_user_id=investor.pk).exists()
    operation = BankOperation.objects.get(pk=result.bank_operation.pk)
    assert "payer_is_account_holder" not in operation.metadata
    declared = AuditEvent.objects.get(action="ledger.lender_deposit_declared")
    assert "verified_payout_instruction_id" not in declared.metadata
    # A later deposit from an account that is verified by then reports that account.
    verified = verify_account_from_deposit(admin_user, result)
    again = ledger_services.declare_lender_deposit(
        _deposit_command(
            admin_user, investor, idempotency_key="deposit-2", value_date=date(2026, 1, 2)
        )
    )
    assert again.payout_instruction is not None
    assert again.payout_instruction.pk == verified.pk


@pytest.mark.django_db
def test_admin_deposit_api_cannot_verify_the_paying_account(
    admin_user: Model, investor: Model
) -> None:
    """Audit S3-1: the old one-checkbox shortcut is gone; the flag is ignored when sent."""
    client = Client()
    client.force_login(cast(Any, admin_user))
    payload = {
        "investor_user_id": str(investor.pk),
        "amount_minor": 100_00,
        "currency": "CHF",
        "booking_date": "2026-01-03",
        "value_date": "2026-01-03",
        "collection_account_identifier": "CH00GARANTALEDGER",
        "payer_name": "Ops Investor",
        "payer_account_identifier": DEPOSIT_IBAN,
        "idempotency_key": "deposit-holder-check",
    }
    created = client.post(
        "/api/v1/ledger/admin/lender-deposits/",
        data={**payload, "payer_is_account_holder": True},
        content_type="application/json",
    )
    assert created.status_code == 201
    assert created.json()["payout_instruction"] is None
    assert not InvestorPayoutInstruction.objects.filter(investor_user_id=investor.pk).exists()


@pytest.mark.django_db
def test_migration_keeps_the_destination_forced_returns_used_before(
    admin_user: Model, investor: Model, other_investor: Model
) -> None:
    migration = import_module("backend.apps.ledger.migrations.0013_set_default_return_accounts")
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    _register_verified_iban(admin_user, investor, iban=SECOND_IBAN)
    _register_verified_iban(admin_user, other_investor, iban=THIRD_IBAN)
    newest = _register_verified_iban(admin_user, other_investor, iban="GB82WEST12345698765432")
    # Data from before U33-DEC-05 has no default.
    InvestorPayoutInstruction.objects.update(is_default_return=False)

    instruction_model = apps.get_model("ledger", "InvestorPayoutInstruction")
    bank_operation_model = apps.get_model("ledger", "BankOperation")
    chosen = migration.plan_default_return_accounts(instruction_model, bank_operation_model)
    by_id = {
        str(row.pk): (str(row.investor_user_id), row.destination_iban)
        for row in InvestorPayoutInstruction.objects.filter(pk__in=chosen)
    }
    # The deposit-proven IBAN for the investor; the newest verified one without a deposit.
    assert sorted(by_id.values()) == sorted(
        [(str(investor.pk), DEPOSIT_IBAN), (str(other_investor.pk), newest.destination_iban)]
    )
