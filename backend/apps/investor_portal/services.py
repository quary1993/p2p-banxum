from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any, cast
from uuid import UUID

from django.apps import apps
from django.conf import settings
from django.db.models import Model, Q, Sum

from backend.apps.platform_core.domain.access import user_can_access_financial_features
from backend.apps.platform_core.domain.funding import balance_deadline_date, balance_is_overdue
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.activity_archive import merge_archived_activity

# Email bodies are private by default in the investor portal. Add a topic here only after
# confirming the body cannot contain one-time codes, login links, bank details, or third-party PII.
PORTAL_BODY_VISIBLE_EMAIL_TOPICS = frozenset(
    {
        "email.investor_notice",
        "email.balance_ageing_reminder",
        "email.deposit_reconciled",
        "email.withdrawal_status",
        "email.primary_investment_confirmation",
        "email.secondary_market_listing_status",
        "email.secondary_market_purchase_confirmation",
        "email.secondary_market_sale_confirmation",
        "email.fx_exchange_confirmation",
        "email.repayment_distribution_credited",
        "email.recovery_distribution_credited",
        "email.loan_status_changed",
        "email.loan_risk_note_published",
        "email.smart_invest_opportunity_match",
        "email.originator_claim_purchase_confirmation",
        "email.originator_claim_repayment_credited",
        "email.originator_subscription_activated",
        "email.originator_subscription_cancelled",
        "email.balance_forced_return",
        "email.balance_penalty_mode",
        "email.payout_account_status",
        "email.loan_funding_status",
        "email.primary_order_released",
    }
)

# Human labels for the notification centre; the raw topic key is never shown to investors.
NOTIFICATION_TOPIC_LABELS = {
    "email.investor_notice": "Investor notice",
    "email.balance_ageing_reminder": "Balance reminder",
    "email.deposit_reconciled": "Deposit",
    "email.withdrawal_status": "Withdrawal",
    "email.balance_forced_return": "Balance return",
    "email.balance_penalty_mode": "Penalty mode",
    "email.payout_account_status": "Payout IBAN",
    "email.fx_exchange_confirmation": "Currency exchange",
    "email.primary_investment_confirmation": "Investment",
    "email.primary_order_released": "Investment",
    "email.loan_funding_status": "Funding",
    "email.loan_status_changed": "Loan status",
    "email.loan_risk_note_published": "Loan update",
    "email.repayment_distribution_credited": "Repayment",
    "email.recovery_distribution_credited": "Recovery",
    "email.originator_claim_purchase_confirmation": "Investment",
    "email.originator_claim_repayment_credited": "Repayment",
    "email.originator_subscription_activated": "Investment",
    "email.originator_subscription_cancelled": "Funding",
    "email.secondary_market_listing_status": "Secondary market",
    "email.secondary_market_purchase_confirmation": "Secondary market",
    "email.secondary_market_sale_confirmation": "Secondary market",
    "email.smart_invest_opportunity_match": "Smart Invest",
    "email.document_acceptance_pdf": "Documents",
    "email.account_login_blocked": "Account",
}


class InvestorPortalAuthorizationError(RuntimeError):
    pass


class InvestorPortalValidationError(RuntimeError):
    pass


class InvestorPortalNotFoundError(InvestorPortalValidationError):
    pass


@dataclass(frozen=True, slots=True)
class InvestorDocumentDownloadCommand:
    actor: Model
    document_kind: str
    output_format: str = "pdf"
    document_id: str = ""
    start_date: date | None = None
    end_date: date | None = None
    year: int | None = None
    audit_actor: Model | None = None


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _servicing_services() -> Any:
    return import_module("backend.apps.servicing.services")


def _reporting_services() -> Any:
    return import_module("backend.apps.reporting.services")


def _documents_services() -> Any:
    return import_module("backend.apps.documents.services")


def _originator_services() -> Any:
    return import_module("backend.apps.originator_claims.services")


def _fx_services() -> Any:
    return import_module("backend.apps.fx.services")


def _require_financial_access(actor: Model) -> str:
    if not user_can_access_financial_features(actor):
        raise InvestorPortalAuthorizationError(
            "Investor portal financial data requires active lender access, phone verification, "
            "and approved KYC/KYB status."
        )
    return str(actor.pk)


def _bounded_limit(limit: int | None, *, default: int = 50, maximum: int = 250) -> int:
    if limit is None:
        return default
    if limit < 1:
        raise InvestorPortalValidationError("Limit must be at least 1.")
    return min(limit, maximum)


def _investor_payment_reference(*, investor_reference: str, currency: str) -> str:
    return f"BX-{currency}-{investor_reference}"


def _enabled_currencies() -> list[Any]:
    currency_model = _model("platform_core", "Currency")
    return list(currency_model.objects.filter(is_enabled=True).order_by("code"))


def _currency_code(value: Any) -> str:
    return str(getattr(value, "code", value))


def _effective_fx_rate(exchange: Any) -> str:
    source_factor = Decimal(10) ** int(exchange.source_currency.minor_units)
    target_factor = Decimal(10) ** int(exchange.target_currency.minor_units)
    source_major = Decimal(exchange.source_amount_minor) / source_factor
    target_major = Decimal(exchange.target_amount_minor) / target_factor
    if source_major <= 0:
        raise InvestorPortalValidationError("FX exchange source amount must be positive.")
    return str((target_major / source_major).quantize(Decimal("0.000000000001")))


def _balance_bucket(lot: Any, *, as_of: datetime) -> str:
    status = str(lot.status)
    if status == "frozen":
        return "frozen"
    if status == "penalty_mode":
        return "penalty_mode"
    if status == "penalty_exhausted":
        return "penalty_exhausted"
    if status != "available":
        return status
    if balance_is_overdue(withdrawal_deadline_at=lot.withdrawal_deadline_at, as_of=as_of):
        return "overdue"
    if business_date(as_of) == balance_deadline_date(lot.withdrawal_deadline_at):
        # Last day (day 60): it can still be withdrawn today, but no longer invested.
        return "withdraw_only"
    return "investable"


def _days_until(value: datetime, *, as_of: datetime) -> int:
    return (business_date(value) - business_date(as_of)).days


def _lot_payload(lot: Any, *, as_of: datetime) -> dict[str, Any]:
    bucket = _balance_bucket(lot, as_of=as_of)
    return {
        "id": str(lot.pk),
        "currency": _currency_code(lot.currency),
        "source_type": str(lot.source_type),
        "status": str(lot.status),
        "bucket": bucket,
        "received_at": lot.received_at,
        "investment_deadline_at": lot.withdrawal_deadline_at,
        "withdrawal_deadline_at": lot.withdrawal_deadline_at,
        "days_until_investment_deadline": _days_until(
            lot.withdrawal_deadline_at,
            as_of=as_of,
        ),
        "days_until_withdrawal_deadline": _days_until(
            lot.withdrawal_deadline_at,
            as_of=as_of,
        ),
        "original_amount_minor": int(lot.original_amount_minor),
        "available_amount_minor": int(lot.available_amount_minor),
        "invested_amount_minor": int(lot.invested_amount_minor),
        "converted_amount_minor": int(lot.converted_amount_minor),
        "withdrawn_amount_minor": int(lot.withdrawn_amount_minor),
        "penalized_amount_minor": int(lot.penalized_amount_minor),
        "requires_withdrawal": bucket in {"withdraw_only", "overdue", "penalty_mode"},
        "blocks_financial_actions": bucket == "penalty_mode",
    }


def _empty_balance_summary(*, investor_user_id: str, currency: str) -> dict[str, Any]:
    return {
        "investor_user_id": investor_user_id,
        "currency": currency,
        "total_available_minor": 0,
        "investable_minor": 0,
        "withdraw_only_minor": 0,
        "overdue_minor": 0,
        "frozen_minor": 0,
        "penalty_mode_minor": 0,
        "penalty_charged_minor": 0,
        "lot_count": 0,
        "active_lot_count": 0,
        "next_investment_deadline_at": None,
        "next_withdrawal_deadline_at": None,
    }


def _balance_summaries(
    *,
    investor_user_id: str,
    as_of: datetime,
    lots: Iterable[Any],
) -> list[dict[str, Any]]:
    summaries = {
        _currency_code(currency): _empty_balance_summary(
            investor_user_id=investor_user_id,
            currency=_currency_code(currency),
        )
        for currency in _enabled_currencies()
    }
    for lot in lots:
        currency = _currency_code(lot.currency)
        summary = summaries.setdefault(
            currency,
            _empty_balance_summary(investor_user_id=investor_user_id, currency=currency),
        )
        summary["lot_count"] += 1
        # Ageing penalties already taken from the lot; they are no longer part of any balance.
        summary["penalty_charged_minor"] += int(lot.penalized_amount_minor)
        available = int(lot.available_amount_minor)
        if available <= 0:
            continue
        summary["active_lot_count"] += 1
        summary["total_available_minor"] += available
        bucket = _balance_bucket(lot, as_of=as_of)
        if bucket == "investable":
            summary["investable_minor"] += available
        elif bucket == "withdraw_only":
            summary["withdraw_only_minor"] += available
        elif bucket == "overdue":
            summary["overdue_minor"] += available
        elif bucket == "frozen":
            summary["frozen_minor"] += available
        elif bucket == "penalty_mode":
            summary["penalty_mode_minor"] += available
        if bucket in {"investable", "withdraw_only", "overdue"}:
            investment_deadline = lot.withdrawal_deadline_at
            withdrawal_deadline = lot.withdrawal_deadline_at
            current_investment_deadline = summary["next_investment_deadline_at"]
            current_withdrawal_deadline = summary["next_withdrawal_deadline_at"]
            if (
                current_investment_deadline is None
                or investment_deadline < current_investment_deadline
            ):
                summary["next_investment_deadline_at"] = investment_deadline
            if (
                current_withdrawal_deadline is None
                or withdrawal_deadline < current_withdrawal_deadline
            ):
                summary["next_withdrawal_deadline_at"] = withdrawal_deadline
    return [summaries[key] for key in sorted(summaries)]


def get_investor_balances(*, actor: Model, as_of: datetime | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    as_of_value = as_of or now_utc()
    lot_model = _model("ledger", "InvestorBalanceLot")
    payout_model = _model("ledger", "InvestorPayoutInstruction")
    lots = list(
        lot_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency")
        # Consumption order: earliest withdrawal deadline first (FX proceeds keep their source's).
        .order_by("withdrawal_deadline_at", "received_at", "created_at", "id")
    )
    visible_lots = [
        _lot_payload(lot, as_of=as_of_value) for lot in lots if int(lot.available_amount_minor) > 0
    ]
    payout_instructions = [
        {
            "id": str(instruction.pk),
            "currency": _currency_code(instruction.currency),
            "status": str(instruction.status),
            "destination_iban": str(instruction.destination_iban),
            "destination_account_name": str(instruction.destination_account_name),
            "is_verified_usable": bool(instruction.is_verified_usable),
            "verified_at": instruction.verified_at,
            "created_at": instruction.created_at,
        }
        for instruction in payout_model.objects.filter(
            investor_user_id=investor_user_id,
            status="active",
        )
        .select_related("currency")
        .order_by("currency", "-created_at")
    ]
    summaries = _balance_summaries(
        investor_user_id=investor_user_id,
        as_of=as_of_value,
        lots=lots,
    )
    penalty_mode_minor = sum(item["penalty_mode_minor"] for item in summaries)
    # Requested withdrawals (voluntary and forced) wait for the bank transfer; their amount is
    # already out of the balance.
    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
    pending_withdrawals = [
        {
            "id": str(withdrawal.pk),
            "currency": _currency_code(withdrawal.currency),
            "amount_minor": int(withdrawal.amount_minor),
            "destination_iban": str(withdrawal.destination_iban),
            "destination_account_name": str(withdrawal.destination_account_name),
            "requested_at": withdrawal.requested_at,
            "is_forced": bool(withdrawal.is_forced),
        }
        for withdrawal in withdrawal_model.objects.filter(
            investor_user_id=investor_user_id,
            status="requested",
        )
        .select_related("currency")
        .order_by("requested_at", "id")
    ]
    return {
        "as_of": as_of_value,
        "summaries": summaries,
        "lots": visible_lots,
        "payout_instructions": payout_instructions,
        "pending_withdrawals": pending_withdrawals,
        "has_penalty_mode_balance": penalty_mode_minor > 0,
        "penalty_bps_per_day": int(settings.BALANCE_PENALTY_BPS_PER_DAY),
    }


def get_deposit_instructions(*, actor: Model) -> dict[str, Any]:
    _require_financial_access(actor)
    investor_reference = str(getattr(actor, "investor_reference", "") or "").strip()
    if not investor_reference:
        raise InvestorPortalValidationError("Investor payment reference is not configured.")
    configured = get_platform_setting_value("payments.deposit_instructions_by_currency", {}) or {}
    instructions: list[dict[str, Any]] = []
    for currency in _enabled_currencies():
        currency_code = _currency_code(currency)
        details = dict(configured.get(currency_code, {}) or {})
        iban = str(details.get("iban", "")).strip()
        qr_iban = str(details.get("qr_iban", "")).strip()
        bic = str(details.get("bic", "")).strip()
        bank_name = str(details.get("bank_name", "")).strip()
        qr_bill_payload = str(details.get("qr_bill_payload", ""))
        holder_name = str(
            details.get("account_holder_name") or details.get("account_name") or ""
        ).strip()
        collection_identifier = str(
            details.get("collection_account_identifier") or f"{currency_code}-COLLECTION"
        ).strip()
        instructions.append(
            {
                "currency": currency_code,
                "account_holder_name": holder_name,
                "iban": iban,
                "qr_iban": qr_iban,
                "bic": bic,
                "bank_name": bank_name,
                "collection_account_identifier": collection_identifier,
                "qr_bill_payload": qr_bill_payload,
                "payment_reference": _investor_payment_reference(
                    investor_reference=investor_reference,
                    currency=currency_code,
                ),
                "notes": str(details.get("notes", "")).strip(),
                "is_configured": bool(iban and holder_name),
            }
        )
    return {
        "as_of": now_utc(),
        "instructions": instructions,
        "reference_rule": (
            "The payment reference is unique to the investor and currency and must be included "
            "unchanged in the bank transfer reference/description."
        ),
    }


def _statement_document(
    *, year: int, period_start: date, period_end: date, as_of: datetime, version: str
) -> dict[str, Any]:
    return {
        "id": f"statement-{year}",
        "document_kind": "account_statement",
        "title": f"Investor account statement - {year}",
        "document_type": "Statement",
        "version": version,
        "date": as_of,
        "context_label": f"{period_start.isoformat()} to {period_end.isoformat()}",
        "output_formats": ["pdf", "csv", "zip"],
        "generated_on_request": True,
        "period_start": period_start,
        "period_end": period_end,
    }


def get_investor_documents(*, actor: Model) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    acceptance_model = _model("documents", "DocumentAcceptanceEvidence")
    document_services = _documents_services()
    documents: list[dict[str, Any]] = []
    for acceptance in (
        acceptance_model.objects.filter(user_id=investor_user_id)
        .exclude(context_type="primary_order_batch")
        .select_related("template", "template_version")
        .order_by("-accepted_at", "-id")
    ):
        documents.append(document_services.acceptance_history_item(acceptance))

    as_of = now_utc()
    today = business_date(as_of)
    version = str(_reporting_services().REPORT_DEFINITION_VERSION)
    joined = getattr(actor, "date_joined", None)
    joined_year = business_date(joined).year if isinstance(joined, datetime) else today.year
    # Only finished calendar years get annual documents: the last year always, and earlier
    # years back to the year the account was opened (at most ten years).
    closed_years = list(
        range(today.year - 1, max(min(joined_year, today.year - 1), today.year - 10) - 1, -1)
    )
    documents.append(
        _statement_document(
            year=today.year,
            period_start=date(today.year, 1, 1),
            period_end=today,
            as_of=as_of,
            version=version,
        )
    )
    for year in closed_years:
        if year >= joined_year:
            documents.append(
                _statement_document(
                    year=year,
                    period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31),
                    as_of=as_of,
                    version=version,
                )
            )
    for year in closed_years:
        documents.append(
            {
                "id": f"tax-{year}",
                "document_kind": "annual_tax_information",
                "title": f"Annual lender tax information statement - {year}",
                "document_type": "Tax",
                "version": version,
                "date": as_of,
                "context_label": f"Calendar year {year}",
                "output_formats": ["pdf", "csv", "zip"],
                "generated_on_request": True,
                "period_start": date(year, 1, 1),
                "period_end": date(year, 12, 31),
            }
        )
    return {
        "as_of": as_of,
        "documents": documents,
        "disclaimer": (
            "Statements and annual tax-information files are informational only and are not "
            "tax advice. Final tax treatment remains the responsibility of the investor."
        ),
    }


def _acceptance_download_payload(
    *,
    actor: Model,
    audit_actor: Model,
    document_id: str,
    output_format: str,
) -> dict[str, Any]:
    if not document_id:
        raise InvestorPortalValidationError("document_id is required for acceptance evidence.")
    acceptance_model = _model("documents", "DocumentAcceptanceEvidence")
    acceptance = acceptance_model.objects.filter(id=document_id, user_id=actor.pk).first()
    if acceptance is None:
        raise InvestorPortalValidationError("Document evidence was not found.")
    documents = _documents_services()
    try:
        artifact = documents.render_document_acceptance_artifact(
            documents.RenderDocumentAcceptanceArtifactCommand(
                actor=audit_actor,
                acceptance_id=document_id,
                output_format=output_format,
                purpose="investor_download",
                metadata={
                    "source": "investor_portal",
                    "download_subject_user_id": str(actor.pk),
                    "download_actor_user_id": str(audit_actor.pk),
                },
            )
        )
    except documents.DocumentAuthorizationError as exc:
        raise InvestorPortalValidationError("Document evidence was not found.") from exc
    except documents.DocumentValidationError as exc:
        raise InvestorPortalValidationError(str(exc)) from exc
    return {
        "content_type": artifact.content_type,
        "filename": artifact.filename,
        "content_encoding": artifact.content_encoding,
        "content": artifact.content,
        "content_sha256": artifact.content_sha256,
        "manifest": artifact.manifest,
    }


def _report_period_from_download(
    command: InvestorDocumentDownloadCommand, *, document_kind: str
) -> tuple[date, date]:
    today = business_date(now_utc())
    if command.start_date and command.end_date:
        if command.end_date < command.start_date:
            raise InvestorPortalValidationError("end_date must be on or after start_date.")
        start_date, end_date = command.start_date, command.end_date
    elif document_kind == "annual_tax_information":
        year = command.year or today.year - 1
        start_date, end_date = date(year, 1, 1), date(year, 12, 31)
    else:
        year = command.year or today.year
        start_date = date(year, 1, 1)
        end_date = today if year == today.year else date(year, 12, 31)
    if document_kind == "annual_tax_information" and end_date >= today:
        raise InvestorPortalValidationError(
            "Tax information is only available for a year that has ended. "
            f"{end_date.year} ends on {end_date.isoformat()}."
        )
    if document_kind == "account_statement" and end_date > today:
        raise InvestorPortalValidationError(
            f"An account statement cannot end after today ({today.isoformat()})."
        )
    return start_date, end_date


def download_investor_document(command: InvestorDocumentDownloadCommand) -> dict[str, Any]:
    _require_financial_access(command.actor)
    audit_actor = command.audit_actor or command.actor
    output_format = command.output_format.lower().strip()
    if output_format not in {"pdf", "csv", "zip"}:
        raise InvestorPortalValidationError("output_format must be pdf, csv, or zip.")
    document_kind = command.document_kind.lower().strip()
    if document_kind == "acceptance_evidence":
        return _acceptance_download_payload(
            actor=command.actor,
            audit_actor=audit_actor,
            document_id=command.document_id,
            output_format=output_format,
        )
    if document_kind not in {"account_statement", "annual_tax_information"}:
        raise InvestorPortalValidationError("Unsupported investor document kind.")
    start_date, end_date = _report_period_from_download(command, document_kind=document_kind)
    reporting = _reporting_services()
    report_type = (
        "participant_account_statement"
        if document_kind == "account_statement"
        else "annual_tax_information"
    )
    try:
        artifact = reporting.generate_investor_self_service_report(
            reporting.GenerateInvestorSelfServiceReportCommand(
                actor=command.actor,
                participant_actor=command.actor,
                audit_actor=audit_actor,
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                output_format=output_format,
            )
        )
    except reporting.ReportingAuthorizationError as exc:
        raise InvestorPortalAuthorizationError(str(exc)) from exc
    except reporting.ReportingError as exc:
        raise InvestorPortalValidationError(str(exc)) from exc
    return {
        "content_type": artifact.content_type,
        "filename": artifact.filename,
        "content_encoding": artifact.content_encoding,
        "content": artifact.content,
        "content_sha256": artifact.manifest.get("content_sha256", ""),
        "manifest": artifact.manifest,
    }


def notification_topic_label(topic: str) -> str:
    label = NOTIFICATION_TOPIC_LABELS.get(topic)
    if label:
        return label
    words = topic.removeprefix("email.").replace("_", " ").replace(".", " ").strip()
    return words.capitalize() if words else "Notice"


def _notification_title(*, topic: str, subject: Any = "") -> str:
    return str(subject or "").strip() or notification_topic_label(topic)


def _notification_body(*, topic: str, record: Any | None = None, outbox: Any | None = None) -> str:
    if topic not in PORTAL_BODY_VISIBLE_EMAIL_TOPICS:
        return (
            "Delivery status only. Message contents are not shown in the portal for this "
            "notification type."
        )
    if record is not None and str(record.body_text).strip():
        return str(record.body_text).strip()
    if outbox is not None:
        payload = dict(outbox.payload or {})
        body = str(payload.get("body_text", "")).strip()
        if body:
            return body
    return "Notification delivery status update."


# Receipts of emails the investor triggered for themselves (sign-in links, investor and admin
# confirmation codes) are not notices: the notification centre never lists or counts them.
SELF_TRIGGERED_EMAIL_TOPICS = frozenset(
    {"email.magic_link_requested", "email.sensitive_action_code_requested"}
)
NOTIFICATION_UNREAD_WINDOW = 250

# Where a notification leads in the portal. Only these kinds and UUID identifiers taken from the
# investor's own message are exposed; the portal still authorizes every page it opens.
NOTIFICATION_TARGET_NONE = "none"
NOTIFICATION_TARGET_LOAN = "loan"
NOTIFICATION_TARGET_HOLDING = "holding"
NOTIFICATION_TARGET_PORTFOLIO = "portfolio"
NOTIFICATION_TARGET_BALANCES = "balances"
NOTIFICATION_TARGET_SECONDARY_MARKET = "secondary_market"
NOTIFICATION_TARGET_FX = "fx"
NOTIFICATION_TARGET_TYPES = (
    NOTIFICATION_TARGET_NONE,
    NOTIFICATION_TARGET_LOAN,
    NOTIFICATION_TARGET_HOLDING,
    NOTIFICATION_TARGET_PORTFOLIO,
    NOTIFICATION_TARGET_BALANCES,
    NOTIFICATION_TARGET_SECONDARY_MARKET,
    NOTIFICATION_TARGET_FX,
)
_PORTFOLIO_NOTIFICATION_TOPICS = frozenset(
    {
        "email.primary_investment_confirmation",
        "email.originator_claim_purchase_confirmation",
        "email.originator_claim_repayment_credited",
        "email.originator_subscription_activated",
        "email.originator_subscription_activation_overdue",
        "email.originator_subscription_cancelled",
        "email.loan_funding_close_failed",
        "email.originator_funding_close_failed",
    }
)
_BALANCE_NOTIFICATION_TOPICS = frozenset(
    {
        "email.balance_ageing_reminder",
        "email.deposit_reconciled",
        "email.withdrawal_status",
        "email.balance_forced_return",
        "email.balance_penalty_mode",
        "email.payout_account_status",
        "email.primary_order_released",
    }
)
_TARGETS_WITH_ID = frozenset({NOTIFICATION_TARGET_LOAN, NOTIFICATION_TARGET_HOLDING})


def _communications_services() -> Any:
    return import_module("backend.apps.communications.services")


def _uuid_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return ""


def _notification_target(*, topic: str, payload: Any) -> dict[str, str]:
    payload_dict = payload if isinstance(payload, dict) else {}
    metadata = payload_dict.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}

    def field(name: str) -> str:
        return _uuid_text(metadata_dict.get(name) or payload_dict.get(name))

    def target(kind: str, target_id: str = "") -> dict[str, str]:
        return {"navigation_target": kind, "navigation_target_id": target_id}

    # Notices name their own target (platform_core investor_notices); it is validated here.
    explicit = str(metadata_dict.get("navigation_target") or "")
    if explicit in NOTIFICATION_TARGET_TYPES:
        if explicit not in _TARGETS_WITH_ID:
            return target(explicit)
        if field("navigation_target_id"):
            return target(explicit, field("navigation_target_id"))
    if topic == "email.secondary_market_purchase_confirmation" and field("buyer_holding_id"):
        return target(NOTIFICATION_TARGET_HOLDING, field("buyer_holding_id"))
    if topic.startswith("email.secondary_market_"):
        return target(NOTIFICATION_TARGET_SECONDARY_MARKET)
    if topic in {"email.repayment_distribution_credited", "email.recovery_distribution_credited"}:
        holding_ids = metadata_dict.get("holding_ids")
        first_holding = (
            _uuid_text(holding_ids[0]) if isinstance(holding_ids, list) and holding_ids else ""
        )
        if first_holding:
            return target(NOTIFICATION_TARGET_HOLDING, first_holding)
        return target(NOTIFICATION_TARGET_PORTFOLIO)
    if topic in _BALANCE_NOTIFICATION_TOPICS:
        return target(NOTIFICATION_TARGET_BALANCES)
    if topic == "email.fx_exchange_confirmation":
        return target(NOTIFICATION_TARGET_FX)
    if topic in _PORTFOLIO_NOTIFICATION_TOPICS:
        return target(NOTIFICATION_TARGET_PORTFOLIO)
    if field("loan_id"):
        return target(NOTIFICATION_TARGET_LOAN, field("loan_id"))
    return target(NOTIFICATION_TARGET_NONE)


def _investor_notification_entries(actor: Model, *, window: int) -> list[dict[str, Any]]:
    """Newest-first notifications of the investor, one per outbox message.

    Each entry carries its ``outbox_message_id``; read receipts are keyed by it.
    """
    investor_user_id = str(actor.pk)
    email = str(getattr(actor, "email", "")).strip().lower()
    delivery_model = _model("communications", "EmailDeliveryRecord")
    outbox_model = _model("platform_core", "OutboxMessage")
    latest_records: dict[str, Any] = {}
    for record in (
        delivery_model.objects.filter(recipient_email=email, topic__startswith="email.")
        .exclude(topic__in=SELF_TRIGGERED_EMAIL_TOPICS)
        .select_related("outbox_message")
        .defer("body_html")
        .order_by("-outbox_message__created_at", "-created_at", "-id")[: window * 3]
    ):
        key = str(record.outbox_message_id)
        if key not in latest_records:
            latest_records[key] = record
        if len(latest_records) >= window:
            break

    entries: list[dict[str, Any]] = []
    for record in latest_records.values():
        topic = str(record.topic)
        # Delivery internals (provider ids, attempts, errors) stay out of the investor payload.
        entries.append(
            {
                "id": str(record.id),
                "outbox_message_id": int(record.outbox_message_id),
                "notification_source": "email_delivery",
                "topic": topic,
                "topic_label": notification_topic_label(topic),
                "status": str(record.status),
                "title": _notification_title(topic=topic, subject=record.subject),
                "body": _notification_body(topic=topic, record=record),
                # When the event happened (platform clock), not when the email went out.
                "created_at": record.outbox_message.created_at,
                "sent_at": record.sent_at,
                **_notification_target(topic=topic, payload=record.outbox_message.payload),
            }
        )

    known_outbox_ids = {str(record.outbox_message_id) for record in latest_records.values()}
    pending_outboxes = (
        _investor_outbox_queryset(outbox_model, investor_user_id=investor_user_id, email=email)
        .exclude(id__in=known_outbox_ids)
        .order_by("-created_at", "-id")[:window]
    )
    for outbox in pending_outboxes:
        topic = str(outbox.topic)
        payload = outbox.payload if isinstance(outbox.payload, dict) else {}
        entries.append(
            {
                "id": str(outbox.id),
                "outbox_message_id": int(outbox.id),
                "notification_source": "email_outbox",
                "topic": topic,
                "topic_label": notification_topic_label(topic),
                "status": str(outbox.status),
                "title": _notification_title(topic=topic, subject=payload.get("subject")),
                "body": _notification_body(topic=topic, outbox=outbox),
                "created_at": outbox.created_at,
                "sent_at": outbox.processed_at,
                **_notification_target(topic=topic, payload=outbox.payload),
            }
        )

    entries.sort(key=lambda item: item["created_at"], reverse=True)
    return entries[:window]


def _investor_outbox_queryset(outbox_model: Any, *, investor_user_id: str, email: str) -> Any:
    return (
        outbox_model.objects.filter(topic__startswith="email.")
        .exclude(topic__in=SELF_TRIGGERED_EMAIL_TOPICS)
        .filter(
            Q(payload__user_id=investor_user_id)
            | Q(payload__email=email)
            | Q(payload__recipient_email=email)
            | Q(payload__to_email=email)
        )
    )


def _investor_notification_index(actor: Model, *, window: int) -> list[tuple[int, str]]:
    """Lightweight (outbox message id, topic) list of the investor's newest notifications."""
    email = str(getattr(actor, "email", "")).strip().lower()
    delivery_model = _model("communications", "EmailDeliveryRecord")
    outbox_model = _model("platform_core", "OutboxMessage")
    rows: dict[int, tuple[Any, str]] = {}
    for outbox_message_id, topic, created_at in (
        delivery_model.objects.filter(recipient_email=email, topic__startswith="email.")
        .exclude(topic__in=SELF_TRIGGERED_EMAIL_TOPICS)
        .order_by("-outbox_message__created_at", "-created_at", "-id")
        .values_list("outbox_message_id", "topic", "outbox_message__created_at")[: window * 3]
    ):
        if outbox_message_id not in rows:
            rows[int(outbox_message_id)] = (created_at, str(topic))
        if len(rows) >= window:
            break
    for outbox_id, topic, created_at in (
        _investor_outbox_queryset(outbox_model, investor_user_id=str(actor.pk), email=email)
        .exclude(id__in=list(rows))
        .order_by("-created_at", "-id")
        .values_list("id", "topic", "created_at")[:window]
    ):
        rows[int(outbox_id)] = (created_at, str(topic))
    ordered = sorted(rows.items(), key=lambda item: item[1][0], reverse=True)[:window]
    return [(message_id, topic) for message_id, (_created_at, topic) in ordered]


def _unread_message_ids(*, investor_user_id: str, index: list[tuple[int, str]]) -> set[int]:
    read_ids = _communications_services().read_notification_message_ids(
        investor_user_id=investor_user_id,
        outbox_message_ids=[message_id for message_id, _topic in index],
    )
    return {
        message_id
        for message_id, topic in index
        if message_id not in read_ids and topic not in SELF_TRIGGERED_EMAIL_TOPICS
    }


def _unread_notification_count(actor: Model, *, investor_user_id: str) -> int:
    index = _investor_notification_index(actor, window=NOTIFICATION_UNREAD_WINDOW)
    return len(_unread_message_ids(investor_user_id=investor_user_id, index=index))


def get_investor_notifications(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    entries = _investor_notification_entries(actor, window=limit_value)
    unread_ids = _unread_message_ids(
        investor_user_id=investor_user_id,
        index=[(entry["outbox_message_id"], entry["topic"]) for entry in entries],
    )
    notifications = [
        {
            **{key: value for key, value in entry.items() if key != "outbox_message_id"},
            "unread": entry["outbox_message_id"] in unread_ids,
        }
        for entry in entries
    ]
    return {
        "notifications": notifications,
        # Counted over a fixed window, so the header list and the Notifications page agree.
        "unread_count": _unread_notification_count(actor, investor_user_id=investor_user_id),
    }


def _notification_outbox_id_for_actor(*, actor: Model, notification_id: str) -> int:
    email = str(getattr(actor, "email", "")).strip().lower()
    delivery_model = _model("communications", "EmailDeliveryRecord")
    outbox_model = _model("platform_core", "OutboxMessage")
    record_id = _uuid_text(notification_id)
    if record_id:
        record = (
            delivery_model.objects.filter(
                id=record_id, recipient_email=email, topic__startswith="email."
            )
            .exclude(topic__in=SELF_TRIGGERED_EMAIL_TOPICS)
            .only("outbox_message_id")
            .first()
        )
        if record is not None:
            return int(record.outbox_message_id)
    elif notification_id.isdigit():
        outbox = (
            _investor_outbox_queryset(outbox_model, investor_user_id=str(actor.pk), email=email)
            .filter(id=int(notification_id))
            .only("id")
            .first()
        )
        if outbox is not None:
            return int(outbox.id)
    raise InvestorPortalNotFoundError("Notification not found.")


def mark_investor_notification_read(*, actor: Model, notification_id: str) -> dict[str, Any]:
    """Mark one of the investor's own notifications as read. Repeating it changes nothing."""
    investor_user_id = _require_financial_access(actor)
    outbox_message_id = _notification_outbox_id_for_actor(
        actor=actor, notification_id=str(notification_id).strip()
    )
    marked = _communications_services().mark_notifications_read(
        investor_user_id=investor_user_id,
        outbox_message_ids=[outbox_message_id],
    )
    return {
        "marked_count": int(marked),
        "unread_count": _unread_notification_count(actor, investor_user_id=investor_user_id),
    }


def mark_all_investor_notifications_read(*, actor: Model) -> dict[str, Any]:
    """Mark every notification currently listed for the investor as read."""
    investor_user_id = _require_financial_access(actor)
    index = _investor_notification_index(actor, window=NOTIFICATION_UNREAD_WINDOW)
    marked = _communications_services().mark_notifications_read(
        investor_user_id=investor_user_id,
        outbox_message_ids=[message_id for message_id, _topic in index],
    )
    return {
        "marked_count": int(marked),
        "unread_count": _unread_notification_count(actor, investor_user_id=investor_user_id),
    }


def _loan_days_past_due(loan: Any, *, as_of: datetime) -> int:
    snapshot = _servicing_services().get_loan_servicing_status_snapshot(
        loan=loan,
        as_of_date=business_date(as_of),
    )
    return int(snapshot.days_past_due)


def _loan_projection(
    loan: Any,
    *,
    as_of: datetime,
    schedule: list[Any],
) -> dict[str, Any]:
    if str(getattr(loan, "product_type", "direct")) == "originator_claim":
        return cast(
            dict[str, Any],
            _originator_services().originator_portfolio_loan_payload(
                loan.originator_profile,
                as_of_date=business_date(as_of),
            ),
        )
    borrower = loan.borrower
    return {
        "loan_id": str(loan.pk),
        "product_type": "direct",
        "loan_title": str(loan.title),
        "loan_status": str(loan.status),
        "borrower_id": str(borrower.pk),
        "borrower_name": str(borrower.legal_name),
        "borrower_country": str(getattr(borrower, "country", "")),
        "originator_id": None,
        "originator_name": "",
        "purpose": str(loan.purpose),
        "collateral_type": str(loan.collateral_type),
        "collateral_value_minor": int(loan.collateral_value_minor),
        "collateral_description": str(loan.collateral_description),
        "skin_in_the_game_bps": int(getattr(loan, "skin_in_the_game_bps", 0)),
        "risk_rating": str(loan.risk_rating),
        "interest_rate_bps": int(loan.interest_rate_bps),
        "yield_bps": int(loan.interest_rate_bps),
        "underlying_interest_rate_bps": int(loan.interest_rate_bps),
        "default_penalty_interest_bps": int(loan.default_penalty_interest_bps),
        "term_months": int(loan.term_months),
        "repayment_type": str(loan.repayment_type),
        "currency": _currency_code(loan.currency),
        "is_refinancing": bool(loan.is_refinancing),
        "original_principal_minor": int(loan.original_principal_minor),
        "original_repayment_type": (
            str(loan.original_repayment_type)
            if getattr(loan, "original_repayment_type", "")
            else None
        ),
        "original_interest_only_months": (
            int(loan.original_interest_only_months)
            if getattr(loan, "original_interest_only_months", None) is not None
            else None
        ),
        "principal_minor": int(loan.principal_minor),
        "funding_deadline": loan.funding_deadline,
        "loan_start_date": loan.loan_start_date,
        "first_payment_date": loan.first_payment_date,
        "ltv_bps": getattr(loan, "ltv_bps", None),
        "days_past_due": _loan_days_past_due(loan, as_of=as_of),
        "schedule_version": int(loan.schedule_version),
        "schedule": [
            {key: value for key, value in asdict(row).items() if key != "admin_overridden"}
            for row in schedule
        ],
    }


def _aggregate_by_holding(
    *,
    model_label: tuple[str, str],
    investor_user_id: str,
    holding_ids: list[str],
    fields: list[str],
) -> dict[str, dict[str, int]]:
    if not holding_ids:
        return {}
    model = _model(*model_label)
    annotations = {field: Sum(field) for field in fields}
    rows = (
        model.objects.filter(investor_user_id=investor_user_id, holding_id__in=holding_ids)
        .values("holding_id")
        .annotate(**annotations)
    )
    return {
        str(row["holding_id"]): {field: int(row[field] or 0) for field in fields} for row in rows
    }


def _latest_public_notes_by_loan(loan_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not loan_ids:
        return {}
    note_model = _model("servicing", "LoanRiskNote")
    notes: dict[str, dict[str, Any]] = {}
    for note in note_model.objects.filter(loan_id__in=loan_ids, visibility="public").order_by(
        "loan_id", "-occurred_at", "-id"
    ):
        loan_id = str(note.loan_id)
        if loan_id in notes:
            continue
        notes[loan_id] = {
            "id": str(note.pk),
            "note_type": str(note.note_type),
            "title": str(note.title),
            "occurred_at": note.occurred_at,
        }
    return notes


def _currency_totals(items: Iterable[tuple[str, int]]) -> list[dict[str, Any]]:
    totals: dict[str, int] = defaultdict(int)
    for currency, amount in items:
        totals[currency] += amount
    return [
        {"currency": currency, "amount_minor": amount}
        for currency, amount in sorted(totals.items())
    ]


def _term_bucket(term_months: int) -> str:
    if term_months <= 6:
        return "0_6_months"
    if term_months <= 12:
        return "7_12_months"
    if term_months <= 24:
        return "13_24_months"
    return "25_plus_months"


def _exposure_dimension(
    holdings: list[Any],
    *,
    key_func: Any,
    label_func: Any | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for holding in holdings:
        loan = holding.loan
        key = str(key_func(holding, loan))
        label = str(label_func(holding, loan)) if label_func else key
        currency = _currency_code(holding.currency)
        grouped_key = (key, currency)
        item = grouped.setdefault(
            grouped_key,
            {
                "key": key,
                "name": label,
                "currency": currency,
                "outstanding_principal_minor": 0,
                "holding_count": 0,
            },
        )
        item["outstanding_principal_minor"] += int(holding.current_principal_minor)
        item["holding_count"] += 1
    return sorted(
        grouped.values(),
        key=lambda item: (
            str(item["currency"]),
            -int(item["outstanding_principal_minor"]),
            str(item["name"]),
        ),
    )


def get_investor_portfolio(
    *,
    actor: Model,
    include_inactive: bool = False,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    as_of_value = as_of or now_utc()
    holding_model = _model("holdings", "InvestorLoanHolding")
    all_holdings = list(
        holding_model.objects.filter(investor_user_id=investor_user_id)
        .select_related(
            "loan",
            "loan__borrower",
            "loan__originator_profile",
            "loan__originator_profile__originator",
            "loan__originator_profile__current_import",
            "currency",
        )
        .order_by("loan__title", "created_at", "id")
    )
    holdings = (
        all_holdings
        if include_inactive
        else [
            holding
            for holding in all_holdings
            if str(holding.status) == "active" and int(holding.current_principal_minor) > 0
        ]
    )
    all_holding_ids = [str(holding.pk) for holding in all_holdings]
    repayment_totals = _aggregate_by_holding(
        model_label=("servicing", "InvestorRepaymentDistributionLine"),
        investor_user_id=investor_user_id,
        holding_ids=all_holding_ids,
        fields=["amount_minor", "principal_minor", "interest_minor", "fee_minor"],
    )
    originator_repayment_totals = _aggregate_by_holding(
        model_label=("originator_claims", "InvestorOriginatorRepaymentDistributionLine"),
        investor_user_id=investor_user_id,
        holding_ids=all_holding_ids,
        fields=["amount_minor", "principal_minor", "interest_minor", "penalty_minor"],
    )
    recovery_totals = _aggregate_by_holding(
        model_label=("servicing", "InvestorRecoveryDistributionLine"),
        investor_user_id=investor_user_id,
        holding_ids=all_holding_ids,
        fields=[
            "amount_minor",
            "principal_minor",
            "contractual_interest_minor",
            "default_interest_minor",
            "penalties_minor",
            "other_costs_minor",
        ],
    )
    latest_notes = _latest_public_notes_by_loan([str(holding.loan_id) for holding in holdings])
    direct_holdings = [
        holding
        for holding in holdings
        if str(getattr(holding.loan, "product_type", "direct")) != "originator_claim"
    ]
    originator_holdings = [
        holding
        for holding in holdings
        if str(getattr(holding.loan, "product_type", "direct")) == "originator_claim"
    ]
    direct_loans_by_id = {str(holding.loan_id): holding.loan for holding in direct_holdings}
    schedules_by_loan_id = _servicing_services().get_loan_repayment_schedule_snapshots(
        loans=list(direct_loans_by_id.values()),
        as_of_date=business_date(as_of_value),
    )
    investment_schedules_by_holding_id = (
        _servicing_services().get_holding_repayment_schedule_snapshots(
            holdings=direct_holdings,
            loan_schedules=schedules_by_loan_id,
        )
    )
    investment_schedules_by_holding_id.update(
        _originator_services().get_originator_holding_schedule_payloads(
            holdings=originator_holdings,
            as_of_date=business_date(as_of_value),
        )
    )
    originator_purchase_model = _model("originator_claims", "OriginatorClaimPurchase")
    originator_purchases_by_holding_id = {
        str(purchase.holding_id): purchase
        for purchase in originator_purchase_model.objects.filter(
            holding_id__in=[holding.pk for holding in holdings]
        ).prefetch_related("entitlements")
    }
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    open_listings_by_holding_id = {
        str(listing.holding_id): listing
        for listing in listing_model.objects.filter(
            holding_id__in=[holding.pk for holding in holdings],
            status__in=["active", "approval_requested"],
        ).order_by("holding_id", "-updated_at", "-id")
    }
    holding_payloads: list[dict[str, Any]] = []
    for holding in holdings:
        loan = holding.loan
        repayment = repayment_totals.get(str(holding.pk), {})
        originator_repayment = originator_repayment_totals.get(str(holding.pk), {})
        recovery = recovery_totals.get(str(holding.pk), {})
        open_listing = open_listings_by_holding_id.get(str(holding.pk))
        originator_purchase = originator_purchases_by_holding_id.get(str(holding.pk))
        holding_payloads.append(
            {
                "id": str(holding.pk),
                "status": str(holding.status),
                "source_type": str(holding.source_type),
                "original_principal_minor": int(holding.original_principal_minor),
                "current_principal_minor": int(holding.current_principal_minor),
                "currency": _currency_code(holding.currency),
                "loan_share_ppm": int(holding.loan_share_ppm),
                "assignment_effective_at": holding.assignment_effective_at,
                "loan": _loan_projection(
                    loan,
                    as_of=as_of_value,
                    schedule=schedules_by_loan_id.get(str(holding.loan_id), []),
                ),
                "received_principal_minor": int(repayment.get("principal_minor", 0))
                + int(originator_repayment.get("principal_minor", 0)),
                "received_interest_minor": int(repayment.get("interest_minor", 0))
                + int(originator_repayment.get("interest_minor", 0)),
                "received_penalty_minor": int(originator_repayment.get("penalty_minor", 0)),
                "repayment_fee_minor": int(repayment.get("fee_minor", 0)),
                "investment_schedule": [
                    asdict(row) if not isinstance(row, dict) else row
                    for row in investment_schedules_by_holding_id.get(
                        str(holding.pk),
                        [],
                    )
                ],
                "acquisition_cash_consideration_minor": (
                    int(originator_purchase.cash_consideration_minor)
                    if originator_purchase is not None
                    else None
                ),
                "acquisition_cash_flow": (
                    [
                        {
                            "installment_number": int(entitlement.schedule_row.installment_number),
                            "accrual_start_date": entitlement.accrual_start_date,
                            "due_date": entitlement.due_date,
                            "principal_minor": int(entitlement.expected_principal_minor),
                            "interest_minor": int(entitlement.expected_interest_minor),
                            "penalty_minor": int(entitlement.expected_penalty_minor),
                            "total_minor": int(entitlement.expected_total_minor),
                        }
                        for entitlement in originator_purchase.entitlements.all()
                    ]
                    if originator_purchase is not None
                    else []
                ),
                "recovered_principal_minor": int(recovery.get("principal_minor", 0)),
                "recovered_contractual_interest_minor": int(
                    recovery.get("contractual_interest_minor", 0)
                ),
                "recovered_default_interest_minor": int(recovery.get("default_interest_minor", 0)),
                "recovered_penalties_minor": int(recovery.get("penalties_minor", 0)),
                "recovered_other_costs_minor": int(recovery.get("other_costs_minor", 0)),
                "latest_public_note": latest_notes.get(str(holding.loan_id)),
                "open_secondary_listing": (
                    {
                        "id": str(open_listing.pk),
                        "status": str(open_listing.status),
                        "publication_type": str(open_listing.publication_type),
                        "price_bps": int(open_listing.price_bps),
                        "transfer_price_minor": int(open_listing.transfer_price_minor),
                        "seller_net_proceeds_minor": int(open_listing.seller_net_proceeds_minor),
                        "listed_at": open_listing.listed_at,
                        "updated_at": open_listing.updated_at,
                    }
                    if open_listing is not None
                    else None
                ),
            }
        )
    active_holdings = [
        holding
        for holding in holdings
        if str(holding.status) == "active" and int(holding.current_principal_minor) > 0
    ]
    summary = {
        "holding_count": len(holding_payloads),
        "active_holding_count": len(active_holdings),
        "outstanding_principal_by_currency": _currency_totals(
            (
                _currency_code(holding.currency),
                int(holding.current_principal_minor),
            )
            for holding in active_holdings
        ),
        # Lifetime figures cover every holding the investor ever had — a
        # holding sold on the secondary market or repaid to zero must keep
        # contributing its invested principal and received interest.
        "original_principal_by_currency": _currency_totals(
            (
                _currency_code(holding.currency),
                int(holding.original_principal_minor),
            )
            for holding in all_holdings
        ),
        "realized_interest_by_currency": _currency_totals(
            (
                _currency_code(holding.currency),
                repayment_totals.get(str(holding.pk), {}).get("interest_minor", 0)
                + originator_repayment_totals.get(str(holding.pk), {}).get("interest_minor", 0)
                + recovery_totals.get(str(holding.pk), {}).get("contractual_interest_minor", 0)
                + recovery_totals.get(str(holding.pk), {}).get("default_interest_minor", 0),
            )
            for holding in all_holdings
        ),
        "late_or_defaulted_exposure_by_currency": _currency_totals(
            (
                _currency_code(holding.currency),
                int(holding.current_principal_minor),
            )
            for holding in active_holdings
            if str(holding.loan.status) in {"late", "defaulted", "written_off"}
        ),
    }
    exposure = {
        "by_borrower": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: (
                f"originator-claim:{loan.id}"
                if str(getattr(loan, "product_type", "direct")) == "originator_claim"
                else str(loan.borrower_id)
            ),
            label_func=lambda _holding, loan: (
                str(loan.originator_profile.borrower_display_name)
                if str(getattr(loan, "product_type", "direct")) == "originator_claim"
                else str(loan.borrower.legal_name)
            ),
        ),
        "by_country": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: (
                str(loan.originator_profile.borrower_country)
                if str(getattr(loan, "product_type", "direct")) == "originator_claim"
                else str(getattr(loan.borrower, "country", ""))
            ),
        ),
        "by_purpose": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.purpose),
        ),
        "by_risk_rating": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.risk_rating),
        ),
        "by_collateral_type": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.collateral_type),
        ),
        "by_maturity": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: _term_bucket(int(loan.term_months)),
        ),
        "by_loan_status": _exposure_dimension(
            active_holdings,
            key_func=lambda _holding, loan: str(loan.status),
        ),
    }
    return {
        "as_of": as_of_value,
        "summary": summary,
        "holdings": holding_payloads,
        "exposure": exposure,
    }


def _activity(
    *,
    activity_id: str,
    activity_type: str,
    occurred_at: datetime,
    direction: str,
    title: str,
    amount_minor: int | None = None,
    currency: str = "",
    status: str = "",
    loan_id: str | None = None,
    loan_title: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": activity_id,
        "activity_type": activity_type,
        "occurred_at": occurred_at,
        "direction": direction,
        "title": title,
        "amount_minor": amount_minor,
        "currency": currency,
        "status": status,
        "loan_id": loan_id,
        "loan_title": loan_title,
        "metadata": metadata or {},
    }


def get_investor_activity(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    entries = _investor_activity_entries(investor_user_id, limit_value)
    return {
        "entries": merge_archived_activity(
            investor_user_id=investor_user_id,
            stream="portfolio",
            entries=entries,
            limit=limit_value,
        )
    }


def _investor_activity_entries(
    investor_user_id: str, limit_value: int | None
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    lot_model = _model("ledger", "InvestorBalanceLot")
    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    repayment_line_model = _model("servicing", "InvestorRepaymentDistributionLine")
    originator_repayment_line_model = _model(
        "originator_claims", "InvestorOriginatorRepaymentDistributionLine"
    )
    originator_purchase_model = _model("originator_claims", "OriginatorClaimPurchase")
    recovery_line_model = _model("servicing", "InvestorRecoveryDistributionLine")
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    purchase_model = _model("secondary_market", "SecondaryMarketPurchase")
    fx_exchange_model = _model("fx", "FxExchange")
    for lot in (
        lot_model.objects.filter(
            investor_user_id=investor_user_id,
            source_type__in=[
                "deposit",
                "secondary_market_proceeds",
                "fx_proceeds",
                "refund",
                "correction",
                "penalty_reversal",
            ],
        )
        .select_related("currency", "source_journal_entry")
        .order_by("-created_at")[:limit_value]
    ):
        entries.append(
            _activity(
                activity_id=str(lot.pk),
                activity_type=f"balance_{lot.source_type}",
                occurred_at=lot.received_at,
                direction="in",
                title=(
                    "QA opening balance"
                    if lot.source_journal_entry.event_type == "qa_opening_balance"
                    else str(lot.source_type).replace("_", " ").title()
                ),
                amount_minor=int(lot.original_amount_minor),
                currency=_currency_code(lot.currency),
                status=str(lot.status),
            )
        )
    for line in (
        repayment_line_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "repayment_event", "repayment_event__loan")
        .order_by("-occurred_at")[:limit_value]
    ):
        loan = line.repayment_event.loan
        entries.append(
            _activity(
                activity_id=str(line.pk),
                activity_type="repayment_distribution",
                occurred_at=line.occurred_at,
                direction="in",
                title="Loan repayment credited",
                amount_minor=int(line.amount_minor),
                currency=_currency_code(line.currency),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
                metadata={
                    "principal_minor": int(line.principal_minor),
                    "interest_minor": int(line.interest_minor),
                    "fee_minor": int(line.fee_minor),
                },
            )
        )
    for line in (
        originator_repayment_line_model.objects.filter(investor_user_id=investor_user_id)
        .select_related(
            "currency",
            "repayment",
            "repayment__loan_profile__loan",
            "repayment__loan_profile__originator",
        )
        .order_by("-created_at")[:limit_value]
    ):
        profile = line.repayment.loan_profile
        entries.append(
            _activity(
                activity_id=str(line.pk),
                activity_type="originator_repayment_distribution",
                occurred_at=line.created_at,
                direction="in",
                title="Loan Originator claim repayment credited",
                amount_minor=int(line.amount_minor),
                currency=_currency_code(line.currency),
                status="credited",
                loan_id=str(profile.loan_id),
                loan_title=str(profile.loan.title),
                metadata={
                    "principal_minor": int(line.principal_minor),
                    "interest_minor": int(line.interest_minor),
                    "penalty_minor": int(line.penalty_minor),
                    "originator_name": str(profile.originator.public_name),
                },
            )
        )
    for line in (
        recovery_line_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "recovery_event", "recovery_event__loan")
        .order_by("-occurred_at")[:limit_value]
    ):
        loan = line.recovery_event.loan
        entries.append(
            _activity(
                activity_id=str(line.pk),
                activity_type="recovery_distribution",
                occurred_at=line.occurred_at,
                direction="in",
                title="Recovery payment credited",
                amount_minor=int(line.amount_minor),
                currency=_currency_code(line.currency),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
                metadata={
                    "principal_minor": int(line.principal_minor),
                    "contractual_interest_minor": int(line.contractual_interest_minor),
                    "default_interest_minor": int(line.default_interest_minor),
                    "penalties_minor": int(line.penalties_minor),
                    "other_costs_minor": int(line.other_costs_minor),
                },
            )
        )
    for withdrawal in (
        withdrawal_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency")
        .order_by("-requested_at")[:limit_value]
    ):
        withdrawal_status = str(withdrawal.status)
        entries.append(
            _activity(
                activity_id=str(withdrawal.pk),
                activity_type="withdrawal_request",
                occurred_at=withdrawal.requested_at,
                direction="out",
                # A forced return is started by Garanta at the 60-day limit, not by the investor.
                title=(
                    "Forced return to your bank account"
                    if withdrawal.is_forced
                    else "Withdrawal request"
                ),
                amount_minor=int(withdrawal.amount_minor),
                currency=_currency_code(withdrawal.currency),
                # requested (pending bank execution), finalized (paid out) or cancelled.
                status=withdrawal_status,
                metadata={
                    "is_forced": bool(withdrawal.is_forced),
                    "destination_iban": str(withdrawal.destination_iban),
                    "finalized_at": (
                        withdrawal.finalized_at.isoformat() if withdrawal.finalized_at else ""
                    ),
                    "cancelled_at": (
                        withdrawal.cancelled_at.isoformat() if withdrawal.cancelled_at else ""
                    ),
                },
            )
        )
        if withdrawal_status == "cancelled" and withdrawal.cancelled_at is not None:
            # The cancellation reverses the request journal entry and restores the reserved
            # lots; show that credit as its own line instead of leaving it implied.
            entries.append(
                _activity(
                    activity_id=f"{withdrawal.pk}:cancellation",
                    activity_type="withdrawal_cancellation",
                    occurred_at=withdrawal.cancelled_at,
                    direction="in",
                    title=(
                        "Forced return cancelled"
                        if withdrawal.is_forced
                        else "Withdrawal cancelled"
                    ),
                    amount_minor=int(withdrawal.amount_minor),
                    currency=_currency_code(withdrawal.currency),
                    status="returned",
                    metadata={
                        "withdrawal_request_id": str(withdrawal.pk),
                        "is_forced": bool(withdrawal.is_forced),
                    },
                )
            )
    journal_model = _model("ledger", "LedgerJournalEntry")
    for journal in (
        journal_model.objects.filter(
            lender_user_id=investor_user_id,
            event_type="balance_penalty_charged",
        )
        .select_related("currency")
        .order_by("-effective_at", "-created_at")[:limit_value]
    ):
        journal_metadata = journal.metadata if isinstance(journal.metadata, dict) else {}
        entries.append(
            _activity(
                activity_id=str(journal.pk),
                activity_type="balance_penalty_charge",
                occurred_at=journal.effective_at,
                direction="out",
                title="Penalty charged: balance past the 60-day limit",
                amount_minor=int(journal.gross_amount_minor),
                currency=_currency_code(journal.currency),
                status="charged",
                metadata={
                    "balance_lot_id": str(journal_metadata.get("balance_lot_id", "")),
                    "charge_date": str(journal_metadata.get("charge_date", "")),
                    "penalty_bps_per_day": int(journal_metadata.get("penalty_bps_per_day", 0)),
                },
            )
        )
    for order in (
        order_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-created_at")[:limit_value]
    ):
        loan = order.loan
        entries.append(
            _activity(
                activity_id=str(order.pk),
                activity_type="primary_order",
                occurred_at=order.created_at,
                direction="internal",
                title="Primary-market investment order",
                amount_minor=int(order.allocated_amount_minor) or int(order.requested_amount_minor),
                currency=_currency_code(order.currency),
                status=str(order.status),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for purchase in (
        originator_purchase_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "loan_profile__loan", "loan_profile__originator")
        .order_by("-purchased_at")[:limit_value]
    ):
        profile = purchase.loan_profile
        entries.append(
            _activity(
                activity_id=str(purchase.pk),
                activity_type="originator_claim_purchase",
                occurred_at=purchase.purchased_at,
                direction="out",
                title="Loan Originator claim purchased",
                amount_minor=int(purchase.cash_consideration_minor),
                currency=_currency_code(purchase.currency),
                status="completed",
                loan_id=str(profile.loan_id),
                loan_title=str(profile.loan.title),
                metadata={
                    "assigned_principal_minor": int(purchase.assigned_principal_minor),
                    "originator_name": str(profile.originator.public_name),
                },
            )
        )
    for listing in (
        listing_model.objects.filter(seller_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-created_at")[:limit_value]
    ):
        loan = listing.loan
        entries.append(
            _activity(
                activity_id=str(listing.pk),
                activity_type="secondary_listing",
                occurred_at=listing.created_at,
                direction="info",
                title="Secondary-market listing",
                amount_minor=int(listing.transfer_price_minor),
                currency=_currency_code(listing.currency),
                status=str(listing.status),
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for purchase in (
        purchase_model.objects.filter(buyer_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-purchased_at")[:limit_value]
    ):
        loan = purchase.loan
        entries.append(
            _activity(
                activity_id=str(purchase.pk),
                activity_type="secondary_purchase",
                occurred_at=purchase.purchased_at,
                direction="out",
                title="Secondary-market purchase",
                amount_minor=int(purchase.buyer_total_cost_minor),
                currency=_currency_code(purchase.currency),
                status="completed",
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for purchase in (
        purchase_model.objects.filter(seller_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-purchased_at")[:limit_value]
    ):
        loan = purchase.loan
        entries.append(
            _activity(
                activity_id=str(purchase.pk),
                activity_type="secondary_sale",
                occurred_at=purchase.purchased_at,
                direction="in",
                title="Secondary-market sale",
                amount_minor=int(purchase.seller_net_proceeds_minor),
                currency=_currency_code(purchase.currency),
                status="completed",
                loan_id=str(loan.pk),
                loan_title=str(loan.title),
            )
        )
    for exchange in (
        fx_exchange_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("source_currency", "target_currency")
        .order_by("-executed_at")[:limit_value]
    ):
        entries.append(
            _activity(
                activity_id=str(exchange.pk),
                activity_type="fx_exchange",
                occurred_at=exchange.executed_at,
                direction="internal",
                title="Currency exchange",
                amount_minor=int(exchange.source_amount_minor),
                currency=_currency_code(exchange.source_currency),
                status=str(exchange.status),
                metadata={
                    "source_currency": _currency_code(exchange.source_currency),
                    "target_currency": _currency_code(exchange.target_currency),
                    "target_amount_minor": int(exchange.target_amount_minor),
                    "fee_minor": int(exchange.fee_minor),
                    "rate": str(exchange.rate),
                },
            )
        )
    entries.sort(key=lambda item: item["occurred_at"], reverse=True)
    return entries[:limit_value]


def get_primary_orders(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    orders = []
    for order in (
        order_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-created_at", "-id")[:limit_value]
    ):
        loan = order.loan
        orders.append(
            {
                "id": str(order.pk),
                "loan_id": str(loan.pk),
                "loan_title": str(loan.title),
                "loan_status": str(loan.status),
                "status": str(order.status),
                "requested_amount_minor": int(order.requested_amount_minor),
                "allocated_amount_minor": int(order.allocated_amount_minor),
                "currency": _currency_code(order.currency),
                "created_at": order.created_at,
                "allocated_at": order.allocated_at,
                "released_at": order.released_at,
                "closed_at": order.closed_at,
            }
        )
    return {"orders": orders}


def get_secondary_market_activity(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    result = _secondary_market_activity(investor_user_id, limit_value)
    result["entries"] = merge_archived_activity(
        investor_user_id=investor_user_id,
        stream="secondary",
        entries=result["entries"],
        limit=limit_value,
    )
    return result


def _secondary_market_activity(investor_user_id: str, limit_value: int | None) -> dict[str, Any]:
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    listing_event_model = _model("secondary_market", "SecondaryMarketListingEvent")
    purchase_model = _model("secondary_market", "SecondaryMarketPurchase")
    listings: list[dict[str, Any]] = [
        {
            "id": str(listing.pk),
            "holding_id": str(listing.holding_id),
            "loan_id": str(listing.loan_id),
            "loan_title": str(listing.loan.title),
            "status": str(listing.status),
            "publication_type": str(listing.publication_type),
            "current_principal_minor": int(listing.current_principal_minor),
            "transfer_price_minor": int(listing.transfer_price_minor),
            "discount_premium_bps": int(listing.discount_premium_bps),
            "accrued_interest_minor": int(listing.accrued_interest_minor),
            "maker_fee_minor": int(listing.maker_fee_minor),
            "seller_net_proceeds_minor": int(listing.seller_net_proceeds_minor),
            "currency": _currency_code(listing.currency),
            "loan_status_at_listing": str(listing.loan_status_at_listing),
            "risk_acknowledgement_required": bool(listing.risk_acknowledgement_required),
            "public_disclosure_note": str(listing.public_disclosure_note),
            "listed_at": listing.listed_at,
            "created_at": listing.created_at,
        }
        for listing in (
            listing_model.objects.filter(seller_user_id=investor_user_id)
            .select_related("currency", "loan")
            .order_by("-created_at", "-id")[:limit_value]
        )
    ]
    purchases_as_buyer: list[dict[str, Any]] = [
        {
            "id": str(purchase.pk),
            "listing_id": str(purchase.listing_id),
            "loan_id": str(purchase.loan_id),
            "loan_title": str(purchase.loan.title),
            "buyer_holding_id": str(purchase.buyer_holding_id),
            "current_principal_minor": int(purchase.current_principal_minor),
            "transfer_price_minor": int(purchase.transfer_price_minor),
            "discount_premium_bps": int(purchase.discount_premium_bps),
            "accrued_interest_minor": int(purchase.accrued_interest_minor),
            "taker_fee_minor": int(purchase.taker_fee_minor),
            "buyer_total_cost_minor": int(purchase.buyer_total_cost_minor),
            "currency": _currency_code(purchase.currency),
            "loan_status_at_purchase": str(purchase.loan_status_at_purchase),
            "risk_acknowledgement_accepted": bool(purchase.risk_acknowledgement_accepted),
            "purchased_at": purchase.purchased_at,
        }
        for purchase in (
            purchase_model.objects.filter(buyer_user_id=investor_user_id)
            .select_related("currency", "loan")
            .order_by("-purchased_at", "-id")[:limit_value]
        )
    ]
    sales_as_seller: list[dict[str, Any]] = [
        {
            "id": str(purchase.pk),
            "listing_id": str(purchase.listing_id),
            "loan_id": str(purchase.loan_id),
            "loan_title": str(purchase.loan.title),
            "seller_holding_id": str(purchase.seller_holding_id),
            "current_principal_minor": int(purchase.current_principal_minor),
            "transfer_price_minor": int(purchase.transfer_price_minor),
            "discount_premium_bps": int(purchase.discount_premium_bps),
            "accrued_interest_minor": int(purchase.accrued_interest_minor),
            "maker_fee_minor": int(purchase.maker_fee_minor),
            "seller_net_proceeds_minor": int(purchase.seller_net_proceeds_minor),
            "currency": _currency_code(purchase.currency),
            "loan_status_at_purchase": str(purchase.loan_status_at_purchase),
            "purchased_at": purchase.purchased_at,
        }
        for purchase in (
            purchase_model.objects.filter(seller_user_id=investor_user_id)
            .select_related("currency", "loan")
            .order_by("-purchased_at", "-id")[:limit_value]
        )
    ]
    entries: list[dict[str, Any]] = []
    for event in (
        listing_event_model.objects.filter(
            seller_user_id=investor_user_id,
            event_type__in=["created", "edited", "cancelled"],
        )
        .select_related("listing", "listing__currency", "listing__loan")
        .order_by("-occurred_at", "-id")[:limit_value]
    ):
        metadata = event.metadata if isinstance(event.metadata, dict) else {}
        listing = event.listing
        is_cancellation = str(event.event_type) == "cancelled"
        entries.append(
            {
                "id": f"listing-event:{event.pk}",
                "action": "cancel_listing" if is_cancellation else "list",
                "event_type": str(event.event_type),
                "listing_id": str(listing.pk),
                "holding_id": str(event.holding_id),
                "loan_id": str(event.loan_id),
                "loan_title": str(listing.loan.title),
                "currency": _currency_code(listing.currency),
                "principal_minor": int(
                    metadata.get("current_principal_minor", listing.current_principal_minor)
                ),
                "cash_amount_minor": int(
                    metadata.get("transfer_price_minor", listing.transfer_price_minor)
                ),
                "price_bps": int(metadata.get("price_bps", listing.price_bps)),
                "status": str(event.new_status or listing.status),
                "occurred_at": event.occurred_at,
            }
        )
    entries.extend(
        {
            "id": f"buy:{purchase['id']}",
            "action": "buy",
            "event_type": "buy",
            "listing_id": purchase["listing_id"],
            "holding_id": purchase["buyer_holding_id"],
            "loan_id": purchase["loan_id"],
            "loan_title": purchase["loan_title"],
            "currency": purchase["currency"],
            "principal_minor": purchase["current_principal_minor"],
            "cash_amount_minor": purchase["buyer_total_cost_minor"],
            "price_bps": 10_000 + purchase["discount_premium_bps"],
            "status": "completed",
            "occurred_at": purchase["purchased_at"],
        }
        for purchase in purchases_as_buyer
    )
    entries.extend(
        {
            "id": f"sale:{sale['id']}",
            "action": "sale",
            "event_type": "sale",
            "listing_id": sale["listing_id"],
            "holding_id": sale["seller_holding_id"],
            "loan_id": sale["loan_id"],
            "loan_title": sale["loan_title"],
            "currency": sale["currency"],
            "principal_minor": sale["current_principal_minor"],
            "cash_amount_minor": sale["seller_net_proceeds_minor"],
            "price_bps": 10_000 + sale["discount_premium_bps"],
            "status": "completed",
            "occurred_at": sale["purchased_at"],
        }
        for sale in sales_as_seller
    )
    entries.sort(key=lambda item: item["occurred_at"], reverse=True)
    return {
        "listings": listings,
        "purchases_as_buyer": purchases_as_buyer,
        "sales_as_seller": sales_as_seller,
        "entries": entries[:limit_value],
    }


def get_fx_history(*, actor: Model, limit: int | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    limit_value = _bounded_limit(limit)
    result = _fx_history(investor_user_id, limit_value)
    result["exchanges"] = merge_archived_activity(
        investor_user_id=investor_user_id,
        stream="fx",
        entries=result["exchanges"],
        limit=limit_value,
    )
    result["terms"] = _fx_services().investor_fx_terms(investor_user_id=investor_user_id)
    return result


def _fx_history(investor_user_id: str, limit_value: int | None) -> dict[str, Any]:
    quote_model = _model("fx", "FxQuote")
    exchange_model = _model("fx", "FxExchange")
    quotes = [
        {
            "id": str(quote.pk),
            "source_currency": _currency_code(quote.source_currency),
            "target_currency": _currency_code(quote.target_currency),
            "source_amount_minor": int(quote.source_amount_minor),
            "rate": str(quote.rate),
            "platform_fee_bps": int(quote.platform_fee_bps),
            "gross_target_amount_minor": int(quote.gross_target_amount_minor),
            "fee_minor": int(quote.fee_minor),
            "target_amount_minor": int(quote.target_amount_minor),
            "issued_at": quote.issued_at,
            "expires_at": quote.expires_at,
            "is_expired": now_utc() > quote.expires_at,
            "has_exchange": bool(quote.exchanges.exists()),
        }
        for quote in (
            quote_model.objects.filter(investor_user_id=investor_user_id)
            .select_related("source_currency", "target_currency")
            .order_by("-issued_at", "-id")[:limit_value]
        )
    ]
    exchanges = [
        {
            "id": str(exchange.pk),
            "quote_id": str(exchange.quote_id),
            "source_currency": _currency_code(exchange.source_currency),
            "target_currency": _currency_code(exchange.target_currency),
            "source_amount_minor": int(exchange.source_amount_minor),
            "rate": str(exchange.rate),
            "platform_fee_bps": int(exchange.platform_fee_bps),
            "gross_target_amount_minor": int(exchange.gross_target_amount_minor),
            "fee_minor": int(exchange.fee_minor),
            "target_amount_minor": int(exchange.target_amount_minor),
            "effective_net_rate": _effective_fx_rate(exchange),
            "status": str(exchange.status),
            "executed_at": exchange.executed_at,
        }
        for exchange in (
            exchange_model.objects.filter(investor_user_id=investor_user_id)
            .select_related("source_currency", "target_currency")
            .order_by("-executed_at", "-id")[:limit_value]
        )
    ]
    return {"quotes": quotes, "exchanges": exchanges}


def activity_for_qa_archive(*, investor_user_id: str) -> dict[str, list[dict[str, Any]]]:
    """Internal maintenance projection: uncapped, including restricted account history."""
    return {
        "portfolio": _investor_activity_entries(investor_user_id, None),
        "secondary": _secondary_market_activity(investor_user_id, None)["entries"],
        "fx": _fx_history(investor_user_id, None)["exchanges"],
    }


def get_investor_dashboard(*, actor: Model, as_of: datetime | None = None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    as_of_value = as_of or now_utc()
    balances = get_investor_balances(actor=actor, as_of=as_of_value)
    portfolio = get_investor_portfolio(actor=actor, include_inactive=False, as_of=as_of_value)
    activity = get_investor_activity(actor=actor, limit=10)
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    pending_primary_orders = int(
        order_model.objects.filter(
            investor_user_id=investor_user_id,
            status__in=["pending", "balance_allocated", "partially_allocated"],
        ).count()
    )
    pending_withdrawals = int(
        withdrawal_model.objects.filter(
            investor_user_id=investor_user_id,
            status="requested",
        ).count()
    )
    pending_secondary_listings = int(
        listing_model.objects.filter(
            seller_user_id=investor_user_id,
            status__in=["active", "approval_requested"],
        ).count()
    )
    pending_actions: list[dict[str, Any]] = []
    for summary in balances["summaries"]:
        if int(summary["penalty_mode_minor"]) > 0:
            pending_actions.append(
                {
                    "type": "usable_iban_required",
                    "severity": "blocking",
                    "currency": summary["currency"],
                    "amount_minor": summary["penalty_mode_minor"],
                    "message": (
                        "A usable withdrawal IBAN is required before further financial "
                        "actions can be unlocked for this overdue balance."
                    ),
                }
            )
        if int(summary["overdue_minor"]) > 0:
            pending_actions.append(
                {
                    "type": "withdrawal_required",
                    "severity": "urgent",
                    "currency": summary["currency"],
                    "amount_minor": summary["overdue_minor"],
                    "message": (
                        "This balance is past the 60-day holding limit and must be "
                        "withdrawn. Garanta cannot extend this regulatory deadline."
                    ),
                }
            )
        if int(summary["withdraw_only_minor"]) > 0:
            pending_actions.append(
                {
                    "type": "withdraw_only_balance",
                    "severity": "warning",
                    "currency": summary["currency"],
                    "amount_minor": summary["withdraw_only_minor"],
                    "message": (
                        "This balance reaches its 60-day holding deadline today. It can only "
                        "be withdrawn, until the end of today."
                    ),
                }
            )
    if pending_primary_orders:
        pending_actions.append(
            {
                "type": "primary_orders_pending",
                "severity": "info",
                "count": pending_primary_orders,
                "message": "Primary-market orders are open or allocated.",
            }
        )
    if pending_withdrawals:
        pending_actions.append(
            {
                "type": "withdrawals_pending",
                "severity": "info",
                "count": pending_withdrawals,
                "message": "Withdrawal requests are waiting for Garanta processing.",
            }
        )
    if pending_secondary_listings:
        pending_actions.append(
            {
                "type": "secondary_listings_open",
                "severity": "info",
                "count": pending_secondary_listings,
                "message": "Secondary-market listings are active or awaiting approval.",
            }
        )
    return {
        "as_of": as_of_value,
        "investor_user_id": investor_user_id,
        "balances": balances["summaries"],
        "portfolio_summary": portfolio["summary"],
        "exposure": portfolio["exposure"],
        "pending_actions": pending_actions,
        "recent_activity": activity["entries"],
    }
