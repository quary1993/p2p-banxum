from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from backend.apps.platform_core.domain.actors import ActorRef
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
                "iban": "",
                "bic": "",
                "bank_name": "",
                "collection_account_identifier": "EUR-COLLECTION",
                "notes": "Configure the live EUR collection account before launch.",
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
        "balance.reminder_days",
        [25, 46, 53, 58, 59, 60],
        "json",
        "Balance ageing reminder schedule.",
    ),
    SettingDefinition(
        "balance.penalty_policy_display",
        "Deployment-configured day-60 penalty policy.",
        "string",
        "Display-only penalty policy text.",
    ),
    SettingDefinition("secondary_market.maker_fee_bps", 25, "integer", "Seller/maker fee."),
    SettingDefinition("secondary_market.taker_fee_bps", 75, "integer", "Buyer/taker fee."),
    SettingDefinition(
        "secondary_market.minimum_maker_fee_minor_by_currency",
        {},
        "json",
        "Optional seller/maker minimum fee by currency in minor units.",
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
