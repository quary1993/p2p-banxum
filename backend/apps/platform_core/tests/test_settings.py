from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest
from django.apps import apps as django_apps

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import AuditEvent, PlatformSetting
from backend.apps.platform_core.selectors.settings import (
    balance_auto_return_after_days,
    balance_reminder_days,
    get_collection_account_identifier,
    get_platform_setting_value,
    platform_setting_versions,
)
from backend.apps.platform_core.services.settings import (
    SetPlatformSettingCommand,
    seed_default_platform_settings,
    set_platform_setting,
)


@pytest.mark.django_db
def test_platform_setting_updates_are_versioned_and_audited() -> None:
    actor = ActorRef("superadmin", "sa-1")

    setting = set_platform_setting(
        SetPlatformSettingCommand(
            actor=actor,
            key="fx.platform_fee_bps",
            value=150,
            value_type="integer",
            reason="initial",
        )
    )
    setting = set_platform_setting(
        SetPlatformSettingCommand(
            actor=actor,
            key="fx.platform_fee_bps",
            value=175,
            value_type="integer",
            reason="policy update",
        )
    )

    assert setting.current_version == 2
    assert get_platform_setting_value("fx.platform_fee_bps") == 175
    assert [version.value for version in platform_setting_versions("fx.platform_fee_bps")] == [
        150,
        175,
    ]
    assert AuditEvent.objects.filter(target_id="fx.platform_fee_bps").count() == 2


@pytest.mark.django_db
def test_seed_default_platform_settings_is_idempotent() -> None:
    seed_default_platform_settings(actor=ActorRef.system())
    seed_default_platform_settings(actor=ActorRef.system())

    assert PlatformSetting.objects.filter(key="platform.brand_name").count() == 1
    assert get_platform_setting_value("platform.brand_name") == "BANXUM"
    assert get_collection_account_identifier("chf") == "Garanta_CHF"
    assert get_collection_account_identifier("EUR") == "Garanta_EUR"


@pytest.mark.django_db
def test_balance_ageing_settings_seed_the_58_day_return_and_read_back_safely() -> None:
    assert balance_auto_return_after_days() == 58
    assert balance_reminder_days(return_after_days=58) == (25, 46, 53, 56, 57, 58)

    seed_default_platform_settings(actor=ActorRef.system())

    assert get_platform_setting_value("balance.auto_return_after_days") == 58
    assert get_platform_setting_value("balance.reminder_days") == [25, 46, 53, 56, 57, 58]
    actor = ActorRef("superadmin", "sa-1")
    for key, value in (("balance.auto_return_after_days", 55), ("balance.reminder_days", [50])):
        set_platform_setting(SetPlatformSettingCommand(actor=actor, key=key, value=value))
    assert balance_auto_return_after_days() == 55
    assert balance_reminder_days(return_after_days=55) == (50,)
    # A value past the 60-day legal limit falls back to the default.
    set_platform_setting(
        SetPlatformSettingCommand(actor=actor, key="balance.auto_return_after_days", value=75)
    )
    assert balance_auto_return_after_days() == 58


def _reminder_migration() -> Any:
    return import_module(
        "backend.apps.platform_core.migrations.0008_balance_reminder_days_before_auto_return"
    )


def _seed_reminder_days(value: list[int]) -> None:
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=ActorRef.system(),
            key="balance.reminder_days",
            value=value,
            reason="default seed",
        )
    )


@pytest.mark.django_db
def test_reminder_migration_moves_only_the_old_default_schedule() -> None:
    migration = _reminder_migration()
    # No seeded row: nothing to change.
    migration.forwards(django_apps, None)
    assert not PlatformSetting.objects.filter(key="balance.reminder_days").exists()

    _seed_reminder_days([25, 46, 53, 58, 59, 60])
    migration.forwards(django_apps, None)
    migration.forwards(django_apps, None)

    setting = PlatformSetting.objects.get(key="balance.reminder_days")
    assert setting.value == [25, 46, 53, 56, 57, 58]
    assert setting.current_version == 2
    versions = platform_setting_versions("balance.reminder_days")
    assert [(version.version, version.value) for version in versions] == [
        (1, [25, 46, 53, 58, 59, 60]),
        (2, [25, 46, 53, 56, 57, 58]),
    ]
    assert versions[1].changed_by_id == "migration:platform_core.0008"
    audit = AuditEvent.objects.get(
        target_id="balance.reminder_days", actor_id="migration:platform_core.0008"
    )
    assert audit.metadata["previous_value"] == [25, 46, 53, 58, 59, 60]

    migration.backwards(django_apps, None)
    assert PlatformSetting.objects.get(key="balance.reminder_days").value == [
        25,
        46,
        53,
        58,
        59,
        60,
    ]


@pytest.mark.django_db
def test_reminder_migration_keeps_a_schedule_a_superadmin_set() -> None:
    _seed_reminder_days([20, 40, 55])

    _reminder_migration().forwards(django_apps, None)

    setting = PlatformSetting.objects.get(key="balance.reminder_days")
    assert (setting.value, setting.current_version) == ([20, 40, 55], 1)
