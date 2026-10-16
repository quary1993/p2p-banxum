from __future__ import annotations

from typing import Any

from backend.apps.platform_core.domain.funding import (
    BALANCE_AUTO_RETURN_AFTER_DAYS,
    DEFAULT_BALANCE_REMINDER_DAYS,
    normalized_auto_return_after_days,
    normalized_balance_reminder_days,
)
from backend.apps.platform_core.models import PlatformSetting, PlatformSettingVersion


def get_platform_setting_value(key: str, default: Any = None) -> Any:
    try:
        return PlatformSetting.objects.get(key=key).value
    except PlatformSetting.DoesNotExist:
        return default


def balance_auto_return_after_days() -> int:
    """Holding day after which money still not invested goes back to the investor's bank.

    Setting `balance.auto_return_after_days` (default 58, at most the 60-day legal limit).
    """
    return normalized_auto_return_after_days(
        get_platform_setting_value("balance.auto_return_after_days", BALANCE_AUTO_RETURN_AFTER_DAYS)
    )


def balance_reminder_days(*, return_after_days: int) -> tuple[int, ...]:
    """Reminder holding days (setting `balance.reminder_days`) up to the last day."""
    return normalized_balance_reminder_days(
        get_platform_setting_value("balance.reminder_days", list(DEFAULT_BALANCE_REMINDER_DAYS)),
        return_after_days=return_after_days,
    )


def platform_switch_enabled(key: str) -> bool:
    """A boolean platform switch (for example ``fx.enabled``).

    Only an explicit ``true`` turns a switch on: a missing row or any other value is
    off, so a broken or unseeded setting fails closed.
    """
    return get_platform_setting_value(key, False) is True


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
    configured = (
        get_platform_setting_value(
            "payments.deposit_instructions_by_currency",
            {},
        )
        or {}
    )
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
