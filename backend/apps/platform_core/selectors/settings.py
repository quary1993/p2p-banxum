from __future__ import annotations

from typing import Any

from backend.apps.platform_core.models import PlatformSetting, PlatformSettingVersion


def get_platform_setting_value(key: str, default: Any = None) -> Any:
    try:
        return PlatformSetting.objects.get(key=key).value
    except PlatformSetting.DoesNotExist:
        return default


def get_collection_account_identifier(currency: str) -> str:
    currency_code = currency.strip().upper()
    configured = get_platform_setting_value(
        "payments.deposit_instructions_by_currency",
        {},
    ) or {}
    if not isinstance(configured, dict):
        return ""
    currency_settings = configured.get(currency_code, {}) or {}
    if not isinstance(currency_settings, dict):
        return ""
    collection_account_identifier = currency_settings.get("collection_account_identifier", "")
    if not isinstance(collection_account_identifier, str):
        return ""
    return collection_account_identifier.strip()


def platform_setting_versions(key: str) -> list[PlatformSettingVersion]:
    return list(PlatformSettingVersion.objects.filter(key=key).order_by("version"))
