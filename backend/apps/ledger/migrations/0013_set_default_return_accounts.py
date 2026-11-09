# IP of Webby-Soft SRL.
"""U33-DEC-05: give every investor one default return account per currency.

Existing data keeps the destination that forced returns used before (PAY-DEC-022): the
verified IBAN that sent the investor's most recent incoming deposit, otherwise the IBAN an
admin verified most recently. The investor can change it later with the PIN.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db import migrations


def plan_default_return_accounts(instruction_model: Any, bank_operation_model: Any) -> list[Any]:
    """Ids of the instructions that become the default, one per investor and currency."""
    groups: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for instruction in instruction_model.objects.filter(
        status="active", is_verified_usable=True
    ).order_by("-verified_at", "-created_at", "-id"):
        groups[(str(instruction.investor_user_id), str(instruction.currency_id))].append(
            instruction
        )
    chosen: list[Any] = []
    for (investor_user_id, _currency), candidates in groups.items():
        if any(candidate.is_default_return for candidate in candidates):
            continue
        by_iban = {candidate.destination_iban: candidate for candidate in reversed(candidates)}
        latest_deposit = (
            bank_operation_model.objects.filter(
                operation_type="lender_deposit",
                linked_object_type="investor",
                linked_object_id=investor_user_id,
                payer_account_identifier__in=list(by_iban),
            )
            .exclude(status="returned")
            .order_by("-value_date", "-confirmed_at", "-id")
            .first()
        )
        if latest_deposit is not None:
            chosen.append(by_iban[str(latest_deposit.payer_account_identifier)].id)
        else:
            chosen.append(candidates[0].id)
    return chosen


def set_default_return_accounts(apps: Any, schema_editor: Any) -> None:
    instruction_model = apps.get_model("ledger", "InvestorPayoutInstruction")
    bank_operation_model = apps.get_model("ledger", "BankOperation")
    chosen = plan_default_return_accounts(instruction_model, bank_operation_model)
    if chosen:
        instruction_model.objects.filter(id__in=chosen).update(is_default_return=True)


def clear_default_return_accounts(apps: Any, schema_editor: Any) -> None:
    apps.get_model("ledger", "InvestorPayoutInstruction").objects.filter(
        is_default_return=True
    ).update(is_default_return=False)


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0012_default_return_account"),
    ]

    operations = [
        migrations.RunPython(set_default_return_accounts, clear_default_return_accounts),
    ]
