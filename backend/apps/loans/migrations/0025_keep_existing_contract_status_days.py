# IP of Webby-Soft SRL.
"""U33-DEC-09 (audit G-01): existing contracts keep their Late and Default days.

Before U33-DEC-09 every loan used Late from day 5 and Default from day 16 (SERV-DEC-008), and
the investment terms disclosed these days (plan/13). The decision says that existing contracts
keep their terms, so each loan that investors could already sign keeps day 5 / day 16 as its
contract days. Draft loans have no contract yet and follow the platform days (15 / 60). A loan
that already has contract days keeps them. Each changed loan gets an append-only
"status_thresholds_changed" loan event from the system actor. An admin can still set other
contract days with a reason.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import migrations

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
PREVIOUS_LATE_DAYS = 5
PREVIOUS_DEFAULT_DAYS = 16
# Loans whose terms investors could already accept or hold. Draft loans have no contract yet;
# cancelled, repaid and written-off loans have no further status check.
CONTRACT_STATUSES = ("published", "funding_close_failed", "funded", "active", "late", "defaulted")


def contract_days_metadata() -> dict[str, Any]:
    return {
        "decision": "U33-DEC-09",
        "previous": None,
        "effective": {
            "late_days": PREVIOUS_LATE_DAYS,
            "default_days": PREVIOUS_DEFAULT_DAYS,
            "source": "loan",
        },
        "reason": "Existing contracts keep their terms (Late from day 5, Default from day 16).",
        "source": "migration",
    }


def keep_existing_contract_days(apps: Any, schema_editor: Any) -> None:
    loan_model = apps.get_model("loans", "Loan")
    event_model = apps.get_model("loans", "LoanEvent")
    loans = loan_model.objects.filter(
        status__in=CONTRACT_STATUSES,
        late_threshold_days__isnull=True,
        default_threshold_days__isnull=True,
    )
    for loan in loans.iterator():
        # queryset.update() keeps updated_at: no admin edited the loan.
        loan_model.objects.filter(pk=loan.pk).update(
            late_threshold_days=PREVIOUS_LATE_DAYS,
            default_threshold_days=PREVIOUS_DEFAULT_DAYS,
        )
        event_model.objects.create(
            loan_id=loan.pk,
            event_type="status_thresholds_changed",
            actor_user_id=SYSTEM_ACTOR_ID,
            actor_account_type="system",
            previous_status=str(loan.status),
            new_status=str(loan.status),
            note="U33-DEC-09: existing contracts keep Late from day 5 and Default from day 16.",
            metadata=contract_days_metadata(),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0024_credit_check_status_reporting_plan"),
    ]

    operations = [
        # Not reversed: an admin may have changed the days since; the loan events keep the trace.
        migrations.RunPython(keep_existing_contract_days, migrations.RunPython.noop),
    ]
