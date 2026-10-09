from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """Drop the single-value criteria once 0003 has converted them to lists.

    Kept separate from the data conversion so PostgreSQL never alters the table
    in the same transaction that updated its rows.
    """

    dependencies = [
        ("smart_invest", "0003_smart_invest_multi_select_criteria"),
    ]

    operations = [
        migrations.RemoveField(model_name="smartinvestrule", name="originator_scope"),
        migrations.RemoveField(model_name="smartinvestrule", name="originator_id"),
        migrations.RemoveField(model_name="smartinvestrule", name="collateral_scope"),
        migrations.RemoveField(model_name="smartinvestrule", name="collateral_type"),
        migrations.RemoveField(model_name="smartinvestrule", name="currency_scope"),
        migrations.RemoveField(model_name="smartinvestrule", name="risk_rating"),
        migrations.RemoveField(model_name="smartinvestrule", name="purpose"),
        migrations.RemoveField(model_name="smartinvestrule", name="loan_kind"),
    ]
