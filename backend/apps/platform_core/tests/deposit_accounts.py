"""IP of Webby-Soft SRL. Test helper: the verified return account after a deposit (audit S3-1).

A deposit never verifies its paying account. Tests that need the investor's verified bank
account call ``verify_account_from_deposit`` after the deposit, like the admin does.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model

EVIDENCE = "statement:test"


def set_verified_name(investor_id: Any, legal_name: str = "") -> str:
    """Give the investor's approved KYC case the name from the identity document (S3-6)."""
    user = get_user_model().objects.get(pk=investor_id)
    name = legal_name or str(getattr(user, "full_name", "") or "").strip() or "Test Investor"
    cases = apps.get_model("kyc_compliance", "KycVerificationCase").objects.filter(
        user_id=user.pk, status="approved"
    )
    if legal_name:
        cases.update(verified_full_name=name)
    else:
        cases.filter(verified_full_name="").update(verified_full_name=name)
    return name


def verify_account_from_deposit(admin_user: Any, deposit: Any, *, legal_name: str = "") -> Any:
    """The admin's "verify from deposit" with both checks and evidence.

    ``deposit`` is the deposit result or its bank operation. An investor with an approved
    identity check goes through the real service. A test investor without one gets the
    verified account as a plain fixture (production has no such path).
    """
    ledger: Any = import_module("backend.apps.ledger.services")
    return_failures: Any = import_module("backend.apps.ledger.return_failures")
    bank_operation = getattr(deposit, "bank_operation", deposit)
    investor = get_user_model().objects.get(pk=bank_operation.linked_object_id)
    existing = ledger._verified_instruction_of_deposit(bank_operation)
    if existing is not None:
        return existing
    set_verified_name(investor.pk, legal_name)
    shared_iban = ledger._payout_iban_other_investor_ids(
        destination_iban=str(bank_operation.payer_account_identifier),
        investor_user_id=str(investor.pk),
    )
    # Older tests reuse one IBAN for several investors; the service refuses that, so those
    # get the fixture below.
    if return_failures.identity_reference(investor).verified_name and not shared_iban:
        return return_failures.verify_payout_account_from_deposit(
            return_failures.VerifyPayoutAccountFromDepositCommand(
                actor=admin_user,
                deposit_bank_operation_id=str(bank_operation.pk),
                holder_matches_identity=True,
                not_intermediary_account=True,
                evidence_reference=EVIDENCE,
            )
        )
    return ledger._create_investor_payout_instruction(
        actor=admin_user,
        investor=investor,
        currency=bank_operation.currency,
        destination_iban=str(bank_operation.payer_account_identifier),
        destination_account_name=str(bank_operation.payer_name or investor.full_name or ""),
        is_verified_usable=True,
        notes="Test fixture: verified bank account.",
        metadata={"source": "test_fixture"},
    )


def declare_deposit_and_verify_account(command: Any) -> Any:
    """A deposit, then the admin's verification of its paying account.

    For tests that need the investor's verified bank account after a deposit. The result
    carries the verified account, like a deposit from an already verified account does.
    """
    from dataclasses import replace

    ledger: Any = import_module("backend.apps.ledger.services")
    result = ledger.declare_lender_deposit(command)
    instruction = verify_account_from_deposit(command.actor, result)
    return replace(result, payout_instruction=instruction)
