"""Move a seeded balance reminder schedule to the 58-day automatic return (2026-10-16).

Money still not invested goes back to the investor's bank after day 58, so the reminders
end on day 58. Only a row that still holds the old default changes; a schedule a superadmin
set stays as it is. Each change gets a new setting version and an audit event, like a
change made through the settings service.
"""

from __future__ import annotations

from django.db import migrations

SETTING_KEY = "balance.reminder_days"
OLD_DEFAULT = [25, 46, 53, 58, 59, 60]
NEW_DEFAULT = [25, 46, 53, 56, 57, 58]
ACTOR_ID = "migration:platform_core.0008"


def _move_schedule(apps, *, from_value: list[int], to_value: list[int], reason: str) -> None:
    setting_model = apps.get_model("platform_core", "PlatformSetting")
    version_model = apps.get_model("platform_core", "PlatformSettingVersion")
    audit_model = apps.get_model("platform_core", "AuditEvent")
    setting = setting_model.objects.filter(key=SETTING_KEY).first()
    if setting is None or setting.value != from_value:
        return
    version = setting.current_version + 1
    setting.value = to_value
    setting.current_version = version
    setting.save(update_fields=["value", "current_version", "updated_at"])
    version_model.objects.create(
        key=SETTING_KEY,
        version=version,
        value=to_value,
        value_type=setting.value_type,
        changed_by_type="system",
        changed_by_id=ACTOR_ID,
        reason=reason,
    )
    audit_model.objects.create(
        actor_type="system",
        actor_id=ACTOR_ID,
        action="platform_setting.updated",
        target_type="PlatformSetting",
        target_id=SETTING_KEY,
        metadata={"version": version, "previous_value": from_value, "reason": reason},
    )


def forwards(apps, schema_editor) -> None:
    del schema_editor
    _move_schedule(
        apps,
        from_value=OLD_DEFAULT,
        to_value=NEW_DEFAULT,
        reason=(
            "Owner decision 2026-10-16: money not invested goes back to the bank after 58 "
            "days, so the last reminders come before the return."
        ),
    )


def backwards(apps, schema_editor) -> None:
    del schema_editor
    _move_schedule(
        apps,
        from_value=NEW_DEFAULT,
        to_value=OLD_DEFAULT,
        reason="Migration platform_core.0008 reversed.",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0007_storyimage"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
