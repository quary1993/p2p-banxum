from __future__ import annotations

from datetime import time
from typing import Any, cast

from backend.apps.platform_core.domain.funding import (
    BALANCE_AUTO_RETURN_AFTER_DAYS,
    DEFAULT_BANK_CUTOFF_TIME,
    DEFAULT_BANK_PROCESSING_BUSINESS_DAYS,
    DEFAULT_PAYOUT_MARGIN_BUSINESS_DAYS,
    DEFAULT_RETURN_FAILURE_COMPLIANCE_AFTER_DAYS,
    DEFAULT_RETURN_NOTICE_DAYS_BEFORE,
    normalized_auto_return_after_days,
    normalized_business_days,
    normalized_cutoff_time,
    normalized_return_notice_days,
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
    """Return days given to new lots (Q01): day 56 is the last day, the return is on day 57.

    Setting `balance.auto_return_after_days` (default 56, at most 56). Each lot keeps its days.
    """
    return normalized_auto_return_after_days(
        get_platform_setting_value("balance.auto_return_after_days", BALANCE_AUTO_RETURN_AFTER_DAYS)
    )


def balance_return_notice_days_before() -> tuple[int, ...]:
    """Days before the scheduled return date that get a notice (Q01: 14, 10 and 3)."""
    return normalized_return_notice_days(
        get_platform_setting_value(
            "balance.return_notice_days_before", list(DEFAULT_RETURN_NOTICE_DAYS_BEFORE)
        )
    )


def bank_processing_business_days() -> int:
    """D9: business days the bank needs to execute a transfer (setting, default 1)."""
    return normalized_business_days(
        get_platform_setting_value(
            "bank.processing_business_days", DEFAULT_BANK_PROCESSING_BUSINESS_DAYS
        ),
        default=DEFAULT_BANK_PROCESSING_BUSINESS_DAYS,
    )


def bank_cutoff_time() -> time:
    """D9: the bank's cut-off for same-day orders, Europe/Zurich (setting, default 12:00)."""
    return normalized_cutoff_time(
        get_platform_setting_value("bank.cutoff_time", DEFAULT_BANK_CUTOFF_TIME)
    )


def payout_margin_business_days() -> int:
    """F01: business days between a direct loan's funding close and the payout (default 3)."""
    return normalized_business_days(
        get_platform_setting_value(
            "funding.payout_margin_business_days", DEFAULT_PAYOUT_MARGIN_BUSINESS_DAYS
        ),
        default=DEFAULT_PAYOUT_MARGIN_BUSINESS_DAYS,
    )


def return_failure_compliance_after_days() -> int:
    """Q02: calendar days after which compliance takes a failed return (default 5)."""
    return normalized_business_days(
        get_platform_setting_value(
            "balance.return_failure_compliance_after_days",
            DEFAULT_RETURN_FAILURE_COMPLIANCE_AFTER_DAYS,
        ),
        default=DEFAULT_RETURN_FAILURE_COMPLIANCE_AFTER_DAYS,
        maximum=30,
    )


def compliance_alert_email(default: str) -> str:
    """The compliance mailbox for 18.4 alerts (setting `compliance.alert_email`)."""
    value = get_platform_setting_value("compliance.alert_email", "")
    return value.strip() if isinstance(value, str) and value.strip() else default


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
