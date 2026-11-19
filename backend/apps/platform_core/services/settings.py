from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.funding import (
    BALANCE_AUTO_RETURN_AFTER_DAYS,
    DEFAULT_BANK_CUTOFF_TIME,
    DEFAULT_BANK_PROCESSING_BUSINESS_DAYS,
    DEFAULT_PAYOUT_MARGIN_BUSINESS_DAYS,
    DEFAULT_RETURN_FAILURE_COMPLIANCE_AFTER_DAYS,
    DEFAULT_RETURN_NOTICE_DAYS_BEFORE,
)
from backend.apps.platform_core.domain.loan_status import (
    DEFAULT_DEFAULT_THRESHOLD_DAYS,
    DEFAULT_LATE_THRESHOLD_DAYS,
)
from backend.apps.platform_core.models import PlatformSetting, PlatformSettingVersion
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event

CHF_COLLECTOR_QR_BILL_PAYLOAD = (
    "SPC\n"
    "0200\n"
    "1\n"
    "CH1183019GARANTAFI001\n"
    "S\n"
    "Garanta Finanzgruppe AG\n"
    "Schauplatzgasse\n"
    "26\n"
    "3011\n"
    "Bern\n"
    "CH\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "CHF\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "\n"
    "NON\n"
    "\n"
    "\n"
    "EPD\n"
    "\n"
    "\n"
)


@dataclass(frozen=True, slots=True)
class SettingDefinition:
    key: str
    value: Any
    value_type: str = "json"
    description: str = ""


DEFAULT_PLATFORM_SETTINGS = (
    SettingDefinition("platform.brand_name", "BANXUM", "string", "User-facing platform name."),
    SettingDefinition(
        "platform.legal_operator_name",
        "Garanta Finanzgruppe AG",
        "string",
        "Legal operator/contracting entity.",
    ),
    SettingDefinition("platform.support_email", "", "string", "Support mailbox."),
    SettingDefinition(
        "payments.deposit_instructions_by_currency",
        {
            "CHF": {
                "account_holder_name": "Garanta Finanzgruppe AG",
                "iban": "CH1183019GARANTAFI001",
                "qr_iban": "CH8330334GARANTAFI001",
                "bic": "YAPECHZ2",
                "bank_name": "Yapeal",
                "collection_account_identifier": "Garanta_CHF",
                "qr_bill_payload": CHF_COLLECTOR_QR_BILL_PAYLOAD,
                "notes": (
                    "Use the exact BANXUM payment reference shown below in the bank transfer "
                    "reference/description. The QR-bill code identifies the CHF collection "
                    "account but does not carry the investor-specific reference."
                ),
            },
            "EUR": {
                "account_holder_name": "Garanta Finanzgruppe AG",
                "iban": "CH8183019GARANTAFI002",
                "bic": "YAPECHZ2",
                "bank_name": "Yapeal",
                "collection_account_identifier": "Garanta_EUR",
                "notes": (
                    "Use the exact BANXUM payment reference shown below in the bank transfer "
                    "reference/description."
                ),
            },
        },
        "json",
        "Investor-facing lender-deposit bank instructions by currency.",
    ),
    SettingDefinition("currencies.enabled", ["CHF", "EUR"], "json", "Enabled balance currencies."),
    SettingDefinition(
        "investment.minimum_by_currency",
        {"CHF": 100000, "EUR": 100000},
        "json",
        "Minimum investment amounts in minor units.",
    ),
    SettingDefinition(
        "investment.swiss_borrower_max_investors",
        20,
        "integer",
        "Most investors per loan to a Swiss borrower; 0 switches the limit off.",
    ),
    SettingDefinition(
        "investment.banxum_investor_emails",
        [],
        "json",
        "Q04: emails of the investor accounts through which Garanta invests its own money. A "
        "loan with a confirmed reservation or a held participation of one of them shows the "
        '"Banxum invests" label (no amount).',
    ),
    SettingDefinition(
        "fx.enabled",
        False,
        "boolean",
        "Currency exchange (FX) for investors. Off: FX quotes and exchanges are refused "
        "and the investor app hides FX; past exchanges stay visible. Owner decision "
        "2026-10-16: off for now.",
    ),
    SettingDefinition("fx.platform_fee_bps", 150, "integer", "FX platform fee in basis points."),
    SettingDefinition(
        "fx.enabled_pairs",
        ["CHF/EUR", "EUR/CHF"],
        "json",
        "Enabled FX currency pairs.",
    ),
    SettingDefinition(
        "fx.daily_limit_chf_minor",
        10000000,
        "integer",
        "Per-investor daily FX limit in CHF minor units.",
    ),
    SettingDefinition(
        "fx.pair_rate_bounds",
        {
            "CHF/EUR": {"min": "0.500000", "max": "2.000000"},
            "EUR/CHF": {"min": "0.500000", "max": "2.000000"},
        },
        "json",
        "Sanity-check min/max executable FX rates by pair.",
    ),
    SettingDefinition(
        "fx.provider_rate_freshness_seconds",
        300,
        "integer",
        "Maximum accepted provider-rate age for executable FX quotes.",
    ),
    SettingDefinition(
        "fx.market_holidays",
        ["01-01", "12-25"],
        "json",
        "FX market holidays that should explain stale provider rates. "
        "Supports recurring MM-DD and exact YYYY-MM-DD values.",
    ),
    SettingDefinition(
        "fx.mock_rates",
        {"CHF/EUR": "1.050000", "EUR/CHF": "0.952381"},
        "json",
        "Local/mock FX provider rates used until the production provider is configured.",
    ),
    SettingDefinition(
        "fx.yahoo_symbols",
        {"CHF/EUR": "CHFEUR=X", "EUR/CHF": "EURCHF=X"},
        "json",
        "Yahoo Finance chart symbols by enabled FX pair.",
    ),
    SettingDefinition(
        "balance.return_notice_days_before",
        list(DEFAULT_RETURN_NOTICE_DAYS_BEFORE),
        "json",
        "Q01: notices go out this many calendar days before the scheduled return date of "
        "money not invested (14, 10 and 3). A confirmation follows when the return is "
        "requested and after the transfer is made.",
    ),
    SettingDefinition(
        "balance.auto_return_after_days",
        BALANCE_AUTO_RETURN_AFTER_DAYS,
        "integer",
        "Q01: holding day that new money may stay until (day 0 is the value date; 1 to 56). "
        "The return is requested the next day, or earlier when that day is not a settlement "
        "day or the bank's processing time needs it. Each lot keeps the days it got.",
    ),
    SettingDefinition(
        "balance.return_failure_compliance_after_days",
        DEFAULT_RETURN_FAILURE_COMPLIANCE_AFTER_DAYS,
        "integer",
        "Q02: compliance takes a failed return after this many calendar days (0 to 30), and "
        "at once when the money is at day 57 or later.",
    ),
    SettingDefinition(
        "bank.processing_business_days",
        DEFAULT_BANK_PROCESSING_BUSINESS_DAYS,
        "integer",
        "D9: business days the bank needs to execute a transfer ordered before the cut-off "
        "(0 to 10). Return dates move earlier so that the debit happens by day 59.",
    ),
    SettingDefinition(
        "bank.cutoff_time",
        DEFAULT_BANK_CUTOFF_TIME,
        "string",
        "D9: the bank's cut-off for same-day orders, HH:MM Europe/Zurich. Return transfers "
        "are sent before it on the return date.",
    ),
    SettingDefinition(
        "funding.payout_margin_business_days",
        DEFAULT_PAYOUT_MARGIN_BUSINESS_DAYS,
        "integer",
        "F01: money can fund a direct loan only if the funding close plus this many business "
        "days (signing and payment) is on or before day 56 of the money (0 to 10).",
    ),
    SettingDefinition(
        "compliance.alert_email",
        "",
        "string",
        "Mailbox for compliance alerts (failed returns, returns not made by day 59). Empty: "
        "the operations alert address.",
    ),
    SettingDefinition(
        "balance.penalty_policy_display",
        "Deployment-configured day-60 penalty policy.",
        "string",
        "Display-only penalty policy text.",
    ),
    SettingDefinition(
        "security.sign_in_history_retention_days",
        365,
        "integer",
        "Days the sign-in history and ended device sessions are kept (U33-DEC-25), then "
        "deleted by the account security retention job (30 to 3650).",
    ),
    SettingDefinition(
        "servicing.late_threshold_days",
        DEFAULT_LATE_THRESHOLD_DAYS,
        "integer",
        "A loan is Late from this day after the due date of its first unpaid installment "
        "(Europe/Zurich calendar days; before it the payment is Due). U33-DEC-09: day 15. "
        "A loan with its own contract thresholds uses those.",
    ),
    SettingDefinition(
        "servicing.default_threshold_days",
        DEFAULT_DEFAULT_THRESHOLD_DAYS,
        "integer",
        "A loan is in Default from this day after the due date of its first unpaid "
        "installment (U33-DEC-09: day 60). Default does not end the contract; the "
        "termination is a separate admin event.",
    ),
    SettingDefinition(
        "secondary_market.maker_fee_bps",
        200,
        "integer",
        "Seller fee rate in basis points (2%, U33-DEC-07). The fee is the smaller of this "
        "rate on the sale price of the principal and this rate on the outstanding "
        "principal. There is no fee on accrued interest.",
    ),
    SettingDefinition(
        "secondary_market.taker_fee_bps",
        0,
        "integer",
        "Buyer/taker fee in basis points of the sale price (none, owner decision 2026-10-16).",
    ),
    SettingDefinition(
        "secondary_market.minimum_maker_fee_minor_by_currency",
        {},
        "json",
        "Not used for new listings: U33-DEC-07 has no minimum seller fee. Older listings "
        "keep the minimum they accepted until they are edited or refreshed.",
    ),
    SettingDefinition(
        "secondary_market.minimum_taker_fee_minor_by_currency",
        {},
        "json",
        "Optional buyer/taker minimum fee by currency in minor units.",
    ),
    SettingDefinition("payments.lender_payment_fee_minor", 0, "integer", "Lender payment fee."),
    SettingDefinition(
        "loans.validation_limits",
        {"min_principal_minor": 100000, "max_principal_minor": 100000000000},
        "json",
        "Loan principal sanity limits in minor units.",
    ),
)


@dataclass(frozen=True, slots=True)
class SetPlatformSettingCommand:
    actor: ActorRef
    key: str
    value: Any
    value_type: str = "json"
    reason: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@transaction.atomic
def set_platform_setting(command: SetPlatformSettingCommand) -> PlatformSetting:
    setting, created = PlatformSetting.objects.select_for_update().get_or_create(
        key=command.key,
        defaults={
            "value": command.value,
            "value_type": command.value_type,
            "description": command.description,
            "current_version": 1,
        },
    )

    if created:
        version = 1
    else:
        version = setting.current_version + 1
        setting.value = command.value
        setting.value_type = command.value_type
        if command.description:
            setting.description = command.description
        setting.current_version = version
        setting.save(
            update_fields=[
                "value",
                "value_type",
                "description",
                "current_version",
                "updated_at",
            ]
        )

    PlatformSettingVersion.objects.create(
        key=command.key,
        version=version,
        value=command.value,
        value_type=command.value_type,
        changed_by_type=command.actor.actor_type,
        changed_by_id=command.actor.actor_id,
        reason=command.reason,
    )
    record_audit_event(
        AuditCommand(
            actor=command.actor,
            action="platform_setting.created" if created else "platform_setting.updated",
            target_type="PlatformSetting",
            target_id=command.key,
            metadata={"version": version, **command.metadata},
        )
    )
    return setting


@transaction.atomic
def seed_default_platform_settings(actor: ActorRef | None = None) -> None:
    seed_actor = actor or ActorRef.system()
    for definition in DEFAULT_PLATFORM_SETTINGS:
        if PlatformSetting.objects.filter(key=definition.key).exists():
            continue
        set_platform_setting(
            SetPlatformSettingCommand(
                actor=seed_actor,
                key=definition.key,
                value=definition.value,
                value_type=definition.value_type,
                description=definition.description,
                reason="default seed",
            )
        )
