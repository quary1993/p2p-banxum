# IP of Webby-Soft SRL.
"""U33-DEC-12: Banxum charges investors no recovery fee.

Every loan that still carries a recovery fee rate gets 0. Recovery payments already recorded
keep the fee they recorded (closed operations are not recalculated); new recovery payments
can no longer apply a fee. Each changed loan gets an append-only "updated" loan event from
the system actor with the previous rate.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import migrations

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def plan_recovery_fee_removal(previous_bps: int) -> dict[str, Any]:
    """The metadata of the loan event for one loan whose fee rate goes to 0."""
    return {
        "decision": "U33-DEC-12",
        "changes": {"recovery_fee_bps": {"previous": str(previous_bps), "new": "0"}},
        "reason": "No Banxum recovery fee for investors.",
    }


def remove_investor_recovery_fee(apps: Any, schema_editor: Any) -> None:
    loan_model = apps.get_model("loans", "Loan")
    event_model = apps.get_model("loans", "LoanEvent")
    for loan in loan_model.objects.filter(recovery_fee_bps__gt=0).iterator():
        previous = int(loan.recovery_fee_bps)
        # queryset.update() keeps updated_at: no admin edited the loan.
        loan_model.objects.filter(pk=loan.pk).update(recovery_fee_bps=0)
        event_model.objects.create(
            loan_id=loan.pk,
            event_type="updated",
            actor_user_id=SYSTEM_ACTOR_ID,
            actor_account_type="system",
            previous_status=str(loan.status),
            new_status=str(loan.status),
            note="U33-DEC-12: no Banxum recovery fee for investors.",
            metadata=plan_recovery_fee_removal(previous),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0019_loan_status_thresholds_and_termination"),
    ]

    operations = [
        migrations.RunPython(remove_investor_recovery_fee, migrations.RunPython.noop),
    ]
