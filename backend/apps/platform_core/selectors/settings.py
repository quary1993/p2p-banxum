from __future__ import annotations

from typing import Any

from backend.apps.platform_core.models import PlatformSetting, PlatformSettingVersion


def get_platform_setting_value(key: str, default: Any = None) -> Any:
    try:
        return PlatformSetting.objects.get(key=key).value
    except PlatformSetting.DoesNotExist:
        return default


def platform_setting_versions(key: str) -> list[PlatformSettingVersion]:
    return list(PlatformSettingVersion.objects.filter(key=key).order_by("version"))
