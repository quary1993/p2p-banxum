# IP of Webby-Soft SRL.
"""18.4 (Q01): new money goes back to the bank after day 56 (request on day 57).

A seeded `balance.auto_return_after_days` row that still holds the 58-day default moves to 56; a
value a superadmin set stays. The old holding-day reminder schedule (`balance.reminder_days`) is no
longer used: notices now come 14, 10 and 3 days before the return date
(`balance.return_notice_days_before`), so its row is removed. Existing lots keep their 58 days
(ledger migration 0015). Each change gets a setting version and an audit event, like a change made
through the settings service.
"""

from __future__ import annotations

from django.db import migrations

ACTOR_ID = "migration:platform_core.0011"
RETURN_KEY = "balance.auto_return_after_days"
REMINDER_KEY = "balance.reminder_days"
REASON = (
    "18.4 (Q01, U33-DEC-03): day 56 is the last day of money not invested; the return is "
    "requested on day 57."
)


def _audit(apps, *, key: str, action: str, metadata: dict) -> None:
    apps.get_model("platform_core", "AuditEvent").objects.create(
        actor_type="system",
        actor_id=ACTOR_ID,
        action=action,
        target_type="PlatformSetting",
        target_id=key,
        metadata=metadata,
    )


def forwards(apps, schema_editor) -> None:
    del schema_editor
    setting_model = apps.get_model("platform_core", "PlatformSetting")
    version_model = apps.get_model("platform_core", "PlatformSettingVersion")
    setting = setting_model.objects.filter(key=RETURN_KEY).first()
    if setting is not None and setting.value == 58:
        version = setting.current_version + 1
        setting.value = 56
        setting.current_version = version
        setting.save(update_fields=["value", "current_version", "updated_at"])
        version_model.objects.create(
            key=RETURN_KEY,
            version=version,
            value=56,
            value_type=setting.value_type,
            changed_by_type="system",
            changed_by_id=ACTOR_ID,
            reason=REASON,
        )
        _audit(
            apps,
            key=RETURN_KEY,
            action="platform_setting.updated",
            metadata={"version": version, "previous_value": 58, "reason": REASON},
        )
    reminder = setting_model.objects.filter(key=REMINDER_KEY).first()
    if reminder is not None:
        previous = reminder.value
        reminder.delete()
        _audit(
            apps,
            key=REMINDER_KEY,
            action="platform_setting.removed",
            metadata={
                "previous_value": previous,
                "reason": "Replaced by balance.return_notice_days_before (18.4).",
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0010_settlement_calendars"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
