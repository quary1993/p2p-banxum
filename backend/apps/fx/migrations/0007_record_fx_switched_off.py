"""Owner decision 2026-10-16 (row 6): no currency exchange on BANXUM for now.

The platform setting ``fx.enabled`` is off by default, so FX quotes and exchanges are
refused even without a setting row. This migration records the decision as an explicit
row (system actor, setting version with the reason, and an audit event, like the audited
settings service), so the admin console shows when and why FX was switched off. A
superadmin can switch it on again in the admin console. An existing row is left alone,
and a fresh database (no settings seeded yet) gets the row from the seed instead.
"""

from __future__ import annotations

from django.db import migrations
from django.db.models import Max

SETTING_KEY = "fx.enabled"
DESCRIPTION = (
    "Currency exchange (FX) for investors. Off: FX quotes and exchanges are refused "
    "and the investor app hides FX; past exchanges stay visible. Owner decision "
    "2026-10-16: off for now."
)
REASON = (
    "Owner decision 2026-10-16: no currency exchange on BANXUM for now. "
    "FX is hidden and can be switched on again later."
)


def record_fx_switched_off(apps, schema_editor):
    setting_model = apps.get_model("platform_core", "PlatformSetting")
    version_model = apps.get_model("platform_core", "PlatformSettingVersion")
    audit_model = apps.get_model("platform_core", "AuditEvent")
    if setting_model.objects.filter(key=SETTING_KEY).exists():
        return
    if not setting_model.objects.exists():
        # A fresh database: the reference-data seed creates the row with the default
        # (off), so there is nothing to record here.
        return
    latest = version_model.objects.filter(key=SETTING_KEY).aggregate(latest=Max("version"))
    version = int(latest["latest"] or 0) + 1
    setting_model.objects.create(
        key=SETTING_KEY,
        value=False,
        value_type="boolean",
        description=DESCRIPTION,
        current_version=version,
    )
    version_model.objects.create(
        key=SETTING_KEY,
        version=version,
        value=False,
        value_type="boolean",
        changed_by_type="system",
        changed_by_id="system",
        reason=REASON,
    )
    audit_model.objects.create(
        actor_type="system",
        actor_id="system",
        action="platform_setting.created",
        target_type="PlatformSetting",
        target_id=SETTING_KEY,
        metadata={
            "version": version,
            "value": False,
            "reason": REASON,
            "source": "migration fx.0007_record_fx_switched_off",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("fx", "0006_external_settlement_exchange_append_only_guards"),
        ("platform_core", "0007_storyimage"),
    ]

    operations = [
        migrations.RunPython(record_fx_switched_off, migrations.RunPython.noop),
    ]
