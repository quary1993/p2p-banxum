from __future__ import annotations

import pytest

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import AuditEvent, PlatformSetting
from backend.apps.platform_core.selectors.settings import (
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
