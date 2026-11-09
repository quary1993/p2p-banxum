from __future__ import annotations

from typing import Any, cast

from backend.apps.platform_core.domain.funding import (
    BALANCE_AUTO_RETURN_AFTER_DAYS,
    DEFAULT_BALANCE_REMINDER_DAYS,
    normalized_auto_return_after_days,
    normalized_balance_reminder_days,
)
from backend.apps.platform_core.domain.loan_status import (
    DEFAULT_DEFAULT_THRESHOLD_DAYS,
    DEFAULT_LATE_THRESHOLD_DAYS,
    SOURCE_LOAN,
    LoanStatusThresholds,
    platform_thresholds,
    valid_threshold_pair,
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


def platform_loan_status_thresholds() -> LoanStatusThresholds:
    """Settings ``servicing.late_threshold_days`` / ``servicing.default_threshold_days``.

    U33-DEC-09 defaults: Late from day 15, Default from day 60.
    """
    return platform_thresholds(
        get_platform_setting_value("servicing.late_threshold_days", DEFAULT_LATE_THRESHOLD_DAYS),
        get_platform_setting_value(
            "servicing.default_threshold_days", DEFAULT_DEFAULT_THRESHOLD_DAYS
        ),
    )


def loan_status_thresholds(
    loan: Any, *, platform: LoanStatusThresholds | None = None
) -> LoanStatusThresholds:
    """The loan's own contract thresholds when it has them, otherwise the platform ones."""
    late_days = getattr(loan, "late_threshold_days", None)
    default_days = getattr(loan, "default_threshold_days", None)
    if valid_threshold_pair(late_days, default_days):
        return LoanStatusThresholds(cast(int, late_days), cast(int, default_days), SOURCE_LOAN)
    return platform if platform is not None else platform_loan_status_thresholds()


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
