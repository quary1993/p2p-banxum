# IP of Webby-Soft SRL.
"""U33-DEC-04: the daily penalty and penalty mode are removed.

Balance lots that are still in penalty mode go back to "available". They are past their
return date, so the balance shows them as due back (withdraw-only) and they cannot be
invested. Penalties already charged stay in the lot (`penalized_amount_minor`) and in the
ledger; nothing is recalculated. Each lot keeps a lineage entry for the change.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations
from django.utils import timezone


def plan_penalty_mode_release(lineage: list[dict[str, Any]], now_iso: str) -> list[dict[str, Any]]:
    return [
        *lineage,
        {
            "event": "penalty_mode_removed",
            "decision": "U33-DEC-04",
            "as_of": now_iso,
            "reason": "The daily penalty and penalty mode were removed.",
        },
    ]


def release_penalty_mode_lots(apps: Any, schema_editor: Any) -> None:
    lot_model = apps.get_model("ledger", "InvestorBalanceLot")
    now_iso = timezone.now().isoformat()
    for lot in lot_model.objects.filter(status="penalty_mode").iterator():
        lot_model.objects.filter(pk=lot.pk).update(
            status="available",
            lineage=plan_penalty_mode_release(list(lot.lineage or []), now_iso),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0013_set_default_return_accounts"),
    ]

    operations = [
        migrations.RunPython(release_penalty_mode_lots, migrations.RunPython.noop),
    ]
