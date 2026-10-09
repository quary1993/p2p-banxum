from __future__ import annotations

from typing import Any

from backend.apps.platform_core.models import PlatformSetting, PlatformSettingVersion


def get_platform_setting_value(key: str, default: Any = None) -> Any:
    try:
        return PlatformSetting.objects.get(key=key).value
    except PlatformSetting.DoesNotExist:
        return default


def get_collection_account_identifier(currency: str) -> str:
    return get_collection_account(currency).get("collection_account_identifier", "")


COLLECTION_ACCOUNT_FIELDS = (
    "collection_account_identifier",
    "iban",
    "qr_iban",
    "account_holder_name",
    "bank_name",
)


def get_collection_account(currency: str) -> dict[str, str]:
    """The configured collection account of one currency (blank values when not set)."""
    currency_code = currency.strip().upper()
    configured = get_platform_setting_value(
        "payments.deposit_instructions_by_currency",
        {},
    ) or {}
    currency_settings = configured.get(currency_code, {}) if isinstance(configured, dict) else {}
    if not isinstance(currency_settings, dict):
        currency_settings = {}
    account: dict[str, str] = {}
    for field in COLLECTION_ACCOUNT_FIELDS:
        value = currency_settings.get(field, "")
        account[field] = value.strip() if isinstance(value, str) else ""
    return account


def platform_setting_versions(key: str) -> list[PlatformSettingVersion]:
    return list(PlatformSettingVersion.objects.filter(key=key).order_by("version"))
