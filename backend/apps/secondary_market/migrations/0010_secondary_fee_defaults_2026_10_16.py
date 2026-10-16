"""Owner decision 2026-10-16 (rows 2 and 3): seller fee 2% of the price, no buyer fee.

Deployments seeded before the decision hold the old default fees in ``PlatformSetting``
rows: ``secondary_market.maker_fee_bps`` 25 and ``secondary_market.taker_fee_bps`` 75. A
row that still holds the old default changes to the new one (200 and 0) with a new
setting version and an audit event from the system actor, as the audited settings
service records them. A value someone configured on purpose (anything other than the
old default) is kept, and a missing row is left to the seed (which uses the new
defaults).

Open listings keep the seller fee rate they were listed with until the next automatic
refresh or seller edit recomputes it with the new rate (plan/09 MKT-DEC-017).
"""

from __future__ import annotations

from django.db import migrations
from django.utils import timezone

SOURCE = "migration secondary_market.0010_secondary_fee_defaults_2026_10_16"
CHANGES = (
    (
        "secondary_market.maker_fee_bps",
        25,
        200,
        "Seller/maker fee in basis points of the sale price (2%, owner decision 2026-10-16).",
        "Owner decision 2026-10-16: secondary-market seller fee 2% of the price.",
    ),
    (
        "secondary_market.taker_fee_bps",
        75,
        0,
        "Buyer/taker fee in basis points of the sale price (none, owner decision 2026-10-16).",
        "Owner decision 2026-10-16: no secondary-market buyer fee.",
    ),
)


def apply_new_fee_defaults(apps, schema_editor):
    setting_model = apps.get_model("platform_core", "PlatformSetting")
    version_model = apps.get_model("platform_core", "PlatformSettingVersion")
    audit_model = apps.get_model("platform_core", "AuditEvent")
    for key, old_default, new_default, description, reason in CHANGES:
        setting = setting_model.objects.filter(key=key).first()
        if setting is None:
            continue
        value = setting.value
        if type(value) is not int or value != old_default:
            continue
        version = int(setting.current_version) + 1
        setting_model.objects.filter(pk=setting.pk).update(
            value=new_default,
            value_type="integer",
            description=description,
            current_version=version,
            updated_at=timezone.now(),
        )
        version_model.objects.create(
            key=key,
            version=version,
            value=new_default,
            value_type="integer",
            changed_by_type="system",
            changed_by_id="system",
            reason=reason,
        )
        audit_model.objects.create(
            actor_type="system",
            actor_id="system",
            action="platform_setting.updated",
            target_type="PlatformSetting",
            target_id=key,
            metadata={
                "version": version,
                "previous_value": old_default,
                "value": new_default,
                "reason": reason,
                "source": SOURCE,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0007_storyimage"),
        ("secondary_market", "0009_cancel_late_or_defaulted_listings"),
    ]

    operations = [
        migrations.RunPython(apply_new_fee_defaults, migrations.RunPython.noop),
    ]
