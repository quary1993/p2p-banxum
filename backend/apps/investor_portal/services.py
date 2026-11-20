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
from django.db.models import Model, Q, Sum

from backend.apps.platform_core.domain.access import (
    account_status_of,
    has_lender_role,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.money import clean_number_format, localize_number_text
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.selectors.settings import (
    balance_auto_return_after_days,
    get_platform_setting_value,
)
from backend.apps.platform_core.services.activity_archive import merge_archived_activity
from backend.apps.platform_core.services.balance_schedule import BalanceScheduler

# Email bodies are private by default in the investor portal. Add a topic here only after
# confirming the body cannot contain one-time codes, login links, bank details, or third-party PII.
PORTAL_BODY_VISIBLE_EMAIL_TOPICS = frozenset(
    {
        "email.investor_notice",
        # 18.3: "Document ready" (in-app only).
        "notice.document_ready",
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
        "notice.smart_invest_opportunity_match",
        "email.loan_opening_alert",
        "email.saved_opportunity_closing",
        "notice.saved_opportunity_closing",
        "email.support_request_received",
        "email.security_new_sign_in",
        "email.originator_claim_purchase_confirmation",
        "email.originator_claim_repayment_credited",
        "email.originator_subscription_activated",
        "email.originator_subscription_cancelled",
        "email.balance_forced_return",
        "email.balance_return_failed",
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
    "email.balance_return_failed": "Return failed",
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
    "email.smart_invest_opportunity_match": "Smart-Invest",
    "notice.smart_invest_opportunity_match": "Smart-Invest",
    "email.loan_opening_alert": "Opportunity open",
    "email.saved_opportunity_closing": "Saved opportunity",
    "notice.saved_opportunity_closing": "Saved opportunity",
    "notice.document_ready": "Documents",
    "email.support_request_received": "Support",
    "email.security_new_sign_in": "Security",
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


def _balance_bucket(lot: Any, *, as_of: datetime, scheduler: BalanceScheduler) -> str:
    status = str(lot.status)
    if status == "frozen":
        return "frozen"
    if status == "penalty_mode":
        return "penalty_mode"
    if status == "penalty_exhausted":
        return "penalty_exhausted"
    if status != "available":
        return status
    last_day = scheduler.schedule(lot).last_day
    if business_date(as_of) > last_day:
        # Due back to the bank (from the return date); without a usable IBAN it waits here.
        return "overdue"
    if business_date(as_of) == last_day:
        # Last day (day 56): it can still be withdrawn today, but no longer invested.
        return "withdraw_only"
    return "investable"


def _days_until(value: datetime, *, as_of: datetime) -> int:
    return (business_date(value) - business_date(as_of)).days


def _reserved_minor_by_lot(investor_user_id: str) -> dict[str, int]:
    """18.3: money of each lot reserved for primary investments still waiting for the closing.

    A reservation takes the money out of the lot's available amount (it counts as invested in the
    lot until the closing or the release); the design's "Reserved" column shows that part.
    """
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    reserved: dict[str, int] = defaultdict(int)
    for allocations in order_model.objects.filter(
        investor_user_id=investor_user_id,
        status__in=["balance_allocated", "partially_allocated"],
    ).values_list("lot_allocations", flat=True):
        for allocation in cast(list[dict[str, Any]], allocations or []):
            lot_id = str(allocation.get("lot_id") or "")
            amount = allocation.get("amount_minor")
            if lot_id and type(amount) is int and amount > 0:
                reserved[lot_id] += amount
    return dict(reserved)


def _lot_payload(
    lot: Any,
    *,
    as_of: datetime,
    scheduler: BalanceScheduler,
    failed_lot_ids: set[str],
) -> dict[str, Any]:
    bucket = _balance_bucket(lot, as_of=as_of, scheduler=scheduler)
    schedule = scheduler.schedule(lot)
    last_day = schedule.last_day
    return_failed = bucket == "overdue" and str(lot.pk) in failed_lot_ids
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
        "return_after_days": schedule.return_after_days,
        "last_day": last_day,
        # Q01: the day the return is requested, with the calendar adjustment.
        "return_date": schedule.return_date,
        "return_date_adjusted": schedule.adjusted,
        "days_until_last_day": (last_day - business_date(as_of)).days,
        # F01: the latest last subscription date of a direct loan this money can fund.
        "direct_funding_until": (
            scheduler.direct_funding_until(lot, as_of=as_of) if bucket == "investable" else None
        ),
        "return_failed": return_failed,
        "original_amount_minor": int(lot.original_amount_minor),
        "available_amount_minor": int(lot.available_amount_minor),
        "invested_amount_minor": int(lot.invested_amount_minor),
        "converted_amount_minor": int(lot.converted_amount_minor),
        "withdrawn_amount_minor": int(lot.withdrawn_amount_minor),
        "penalized_amount_minor": int(lot.penalized_amount_minor),
        "requires_withdrawal": bucket in {"withdraw_only", "overdue", "penalty_mode"},
        # Penalty mode is gone (U33-DEC-04); a failed return does not block other actions.
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
        "next_return_date": None,
    }


def _balance_summaries(
    *,
    investor_user_id: str,
    as_of: datetime,
    lots: Iterable[Any],
    scheduler: BalanceScheduler,
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
        bucket = _balance_bucket(lot, as_of=as_of, scheduler=scheduler)
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
        if bucket in {"investable", "withdraw_only"}:
            # The next return still ahead; money already due back has its own figure.
            return_date = scheduler.schedule(lot).return_date
            if summary["next_return_date"] is None or return_date < summary["next_return_date"]:
                summary["next_return_date"] = return_date
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
    return_after_days = balance_auto_return_after_days()
    scheduler = BalanceScheduler()
    reserved_by_lot = _reserved_minor_by_lot(investor_user_id)
    return_failures = _open_return_failures(investor_user_id)
    failed_lot_ids = {
        str(lot_id) for failure in return_failures for lot_id in failure.pop("lot_ids")
    }
    visible_lots = [
        {
            **_lot_payload(
                lot, as_of=as_of_value, scheduler=scheduler, failed_lot_ids=failed_lot_ids
            ),
            "reserved_amount_minor": reserved_by_lot.get(str(lot.pk), 0),
        }
        for lot in lots
        if int(lot.available_amount_minor) > 0 or reserved_by_lot.get(str(lot.pk), 0) > 0
    ]
    active_instructions = list(
        payout_model.objects.filter(
            investor_user_id=investor_user_id,
            status="active",
        )
        .select_related("currency")
        .order_by("currency", "-created_at")
    )
    # 18.3: the bank name (SIX bank master for CH and LI IBANs, else the name the investor typed).
    bank_master = import_module("backend.apps.platform_core.services.bank_master")
    master_names = bank_master.bank_names_for_ibans(
        [str(instruction.destination_iban) for instruction in active_instructions]
    )
    payout_instructions = [
        {
            "id": str(instruction.pk),
            "currency": _currency_code(instruction.currency),
            "status": str(instruction.status),
            "destination_iban": str(instruction.destination_iban),
            "destination_account_name": str(instruction.destination_account_name),
            "bank_name": master_names.get(str(instruction.destination_iban))
            or (
                ""
                if bank_master.uses_bank_master(str(instruction.destination_iban))
                else str((instruction.metadata or {}).get("bank_name") or "")
            ),
            "is_verified_usable": bool(instruction.is_verified_usable),
            # U33-DEC-05: "Verified" and "Pending verification" are shown separately.
            "verification_status": "verified" if instruction.is_verified_usable else "pending",
            "is_default_return": bool(instruction.is_default_return),
            "verified_at": instruction.verified_at,
            "created_at": instruction.created_at,
        }
        for instruction in active_instructions
    ]
    summaries = _balance_summaries(
        investor_user_id=investor_user_id,
        as_of=as_of_value,
        lots=lots,
        scheduler=scheduler,
    )
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
        "auto_return_after_days": return_after_days,
        "return_failures": return_failures,
    }


# Q02: the cause shown follows the bank's answer; a bank-side cause is not the investor's fault.
RETURN_FAILURE_INVESTOR_TEXT = {
    "account_closed": "Your bank says the account is closed.",
    "account_unknown": "Your bank does not know this account number.",
    "name_mismatch": "The account holder name does not match the account.",
    "account_blocked": "Your bank says the account is blocked or restricted.",
    "bank_restriction": "The receiving bank could not accept the transfer.",
    "technical": "The transfer came back because of a technical error. This is not your fault.",
    "other": "Your bank sent the transfer back.",
}


def _open_return_failures(investor_user_id: str) -> list[dict[str, Any]]:
    """18.4 (Q02): the investor's open failed returns, for the Account page."""
    failure_model = _model("ledger", "BalanceReturnFailure")
    return [
        {
            "id": str(failure.pk),
            "currency": _currency_code(failure.currency),
            "amount_minor": int(failure.amount_minor),
            "is_forced": bool(failure.is_forced),
            "reason_code": str(failure.reason_code),
            "reason_text": RETURN_FAILURE_INVESTOR_TEXT.get(
                str(failure.reason_code), RETURN_FAILURE_INVESTOR_TEXT["other"]
            ),
            "destination_iban": str(failure.failed_destination_iban),
            "returned_value_date": failure.returned_value_date,
            "recorded_at": failure.recorded_at,
            "lot_ids": list(failure.lot_ids or []),
        }
        for failure in failure_model.objects.filter(
            investor_user_id=investor_user_id, status="open"
        )
        .select_related("currency")
        .order_by("recorded_at", "id")
    ]


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


def _investor_reports() -> Any:
    return import_module("backend.apps.reporting.investor_reports")


def list_investor_reports(*, actor: Model) -> dict[str, Any]:
    """18.3: the reports the investor created and the monthly statements, newest first."""
    investor_user_id = _require_financial_access(actor)
    return {"reports": _investor_reports().list_investor_reports(investor_user_id=investor_user_id)}


def create_investor_report(
    *,
    actor: Model,
    audit_actor: Model,
    kind: str,
    start_date: date,
    end_date: date,
    currency: str,
    output_format: str,
) -> dict[str, Any]:
    """18.3: generate and keep a report; a "Document ready" notice announces it."""
    _require_financial_access(actor)
    if str(audit_actor.pk) != str(actor.pk):
        raise InvestorPortalAuthorizationError(
            "A read-only view cannot create reports for the investor."
        )
    reports = _investor_reports()
    reporting = _reporting_services()
    try:
        return cast(
            dict[str, Any],
            reports.create_investor_report(
                reports.CreateInvestorReportCommand(
                    actor=actor,
                    kind=kind,
                    start_date=start_date,
                    end_date=end_date,
                    currency=currency,
                    output_format=output_format,
                )
            ),
        )
    except reporting.ReportingAuthorizationError as exc:
        raise InvestorPortalAuthorizationError(str(exc)) from exc
    except (reporting.ReportingError, reports.InvestorReportError) as exc:
        raise InvestorPortalValidationError(str(exc)) from exc


def download_investor_report(*, actor: Model, report_id: str) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    reports = _investor_reports()
    try:
        return cast(
            dict[str, Any],
            reports.investor_report_file(investor_user_id=investor_user_id, report_id=report_id),
        )
    except reports.InvestorReportError as exc:
        raise InvestorPortalNotFoundError(str(exc)) from exc


def investor_report_summary(*, actor: Model, year: int | None) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    return cast(
        dict[str, Any],
        _investor_reports().investor_report_summary(investor_user_id=investor_user_id, year=year),
    )


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
    {
        "email.magic_link_requested",
        "email.sensitive_action_code_requested",
        # 18.5: the forgotten-password link the investor asked for.
        "email.password_reset",
    }
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
# 18.3: the design's targets for movements, reports and documents.
NOTIFICATION_TARGET_TRANSACTIONS = "transactions"
NOTIFICATION_TARGET_REPORTS = "reports"
NOTIFICATION_TARGET_DOCUMENTS = "documents"
NOTIFICATION_TARGET_TYPES = (
    NOTIFICATION_TARGET_NONE,
    NOTIFICATION_TARGET_LOAN,
    NOTIFICATION_TARGET_HOLDING,
    NOTIFICATION_TARGET_PORTFOLIO,
    NOTIFICATION_TARGET_BALANCES,
    NOTIFICATION_TARGET_SECONDARY_MARKET,
    NOTIFICATION_TARGET_FX,
    NOTIFICATION_TARGET_TRANSACTIONS,
    NOTIFICATION_TARGET_REPORTS,
    NOTIFICATION_TARGET_DOCUMENTS,
)
# 18.3: the design's tones of a notification (positive, late, default, neutral).
NOTIFICATION_CATEGORIES = ("positive", "late", "default", "neutral")
_POSITIVE_NOTIFICATION_TOPICS = frozenset(
    {
        "email.repayment_distribution_credited",
        "email.recovery_distribution_credited",
        "email.originator_claim_repayment_credited",
        "email.deposit_reconciled",
        "email.secondary_market_sale_confirmation",
    }
)


def _notification_category(*, topic: str, payload: Any) -> str:
    """The tone of a notice: an explicit category, money credited, or a loan that turned late
    or defaulted; everything else is neutral."""
    payload_dict = payload if isinstance(payload, dict) else {}
    metadata = payload_dict.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    explicit = str(metadata_dict.get("category") or "")
    if explicit in NOTIFICATION_CATEGORIES:
        return explicit
    if topic == "email.loan_status_changed":
        status = str(metadata_dict.get("new_status") or "")
        if status == "late":
            return "late"
        if status in {"defaulted", "written_off"}:
            return "default"
    if topic in _POSITIVE_NOTIFICATION_TOPICS:
        return "positive"
    return "neutral"
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
        "email.balance_return_failed",
        "email.balance_penalty_mode",
        "email.payout_account_status",
        "email.primary_order_released",
    }
)
_TARGETS_WITH_ID = frozenset({NOTIFICATION_TARGET_LOAN, NOTIFICATION_TARGET_HOLDING})


def _communications_services() -> Any:
    return import_module("backend.apps.communications.services")


@dataclass(frozen=True, slots=True)
class SubmitInvestorSupportRequestCommand:
    actor: Model
    kind: str
    idempotency_key: str
    topic: str = ""
    message: str = ""
    context_type: str = ""
    context_id: str = ""


def submit_investor_support_request(command: SubmitInvestorSupportRequestCommand) -> dict[str, Any]:
    """A Help message (U33-DEC-35) or an account closure request (U33-DEC-28) by email.

    Open to every signed-in lender whose account is not closed, also before KYC approval:
    support must stay reachable. Returns the receipt shown in the portal.
    """
    actor: Any = command.actor
    if (
        not bool(getattr(actor, "is_active", False))
        or not has_lender_role(actor)
        or str(account_status_of(actor)) == "closed"
    ):
        raise InvestorPortalAuthorizationError("Only an investor account can send this request.")
    support = import_module("backend.apps.communications.support_requests")
    try:
        request = support.submit_support_request(
            support.SubmitSupportRequestCommand(
                actor=actor,
                kind=command.kind,
                idempotency_key=command.idempotency_key,
                topic=command.topic,
                message=command.message,
                context_type=command.context_type,
                context_id=command.context_id,
            )
        )
    except support.SupportRequestThrottled:
        raise
    except support.SupportRequestConflict:
        raise
    except support.SupportRequestError as exc:
        raise InvestorPortalValidationError(str(exc)) from exc
    return {
        "reference": str(request.reference),
        "kind": str(request.kind),
        "received_at": request.created_at,
        "context_label": str(request.context_label),
        "receipt_email": str(request.investor_email),
    }


def _uuid_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return ""


def _notification_target(*, actor: Model, topic: str, payload: Any) -> dict[str, str]:
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
    if (
        topic == "email.loan_risk_note_published"
        and str(metadata_dict.get("visibility") or "") == "public"
    ):
        holding_id = field("holding_id")
        loan_id = field("loan_id")
        if not holding_id and loan_id:
            holding_model = _model("holdings", "InvestorLoanHolding")
            holding_id = str(
                holding_model.objects.filter(
                    investor_user_id=actor.pk,
                    loan_id=loan_id,
                )
                .order_by("-assignment_effective_at", "-id")
                .values_list("id", flat=True)
                .first()
                or ""
            )
        if holding_id:
            return target(NOTIFICATION_TARGET_HOLDING, holding_id)
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
        .exclude(_IN_APP_OFF_DELIVERY)
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
                "category": _notification_category(
                    topic=topic, payload=record.outbox_message.payload
                ),
                **_notification_target(
                    actor=actor,
                    topic=topic,
                    payload=record.outbox_message.payload,
                ),
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
                "notification_source": (
                    "in_app" if topic.startswith(IN_APP_TOPIC_PREFIX) else "email_outbox"
                ),
                "topic": topic,
                "topic_label": notification_topic_label(topic),
                "status": str(outbox.status),
                "title": _notification_title(topic=topic, subject=payload.get("subject")),
                "body": _notification_body(topic=topic, outbox=outbox),
                "created_at": outbox.created_at,
                "sent_at": outbox.processed_at,
                "category": _notification_category(topic=topic, payload=outbox.payload),
                **_notification_target(actor=actor, topic=topic, payload=outbox.payload),
            }
        )

    entries.sort(key=lambda item: item["created_at"], reverse=True)
    return entries[:window]


# U33-DEC-30: in-app notices (never emailed) are listed with the emails; an email whose payload
# says `in_app: false` (the investor switched the in-app channel off) is not listed.
IN_APP_TOPIC_PREFIX = "notice."
# A JSON key that is missing compares as NULL: has_key keeps the rows without the flag listed.
_IN_APP_OFF_OUTBOX = Q(payload__has_key="in_app") & Q(payload__in_app=False)
_IN_APP_OFF_DELIVERY = Q(outbox_message__payload__has_key="in_app") & Q(
    outbox_message__payload__in_app=False
)


def _investor_outbox_queryset(outbox_model: Any, *, investor_user_id: str, email: str) -> Any:
    return (
        outbox_model.objects.filter(
            Q(topic__startswith="email.") | Q(topic__startswith=IN_APP_TOPIC_PREFIX)
        )
        .exclude(topic__in=SELF_TRIGGERED_EMAIL_TOPICS)
        .exclude(_IN_APP_OFF_OUTBOX)
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
        .exclude(_IN_APP_OFF_DELIVERY)
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
    # U33-DEC-32: amounts and percentages in the investor's number format.
    number_format = clean_number_format(getattr(actor, "number_format", None))
    notifications = [
        {
            **{key: value for key, value in entry.items() if key != "outbox_message_id"},
            "title": localize_number_text(str(entry.get("title", "")), number_format),
            "body": localize_number_text(str(entry.get("body", "")), number_format),
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
        "contract_terminated_on": getattr(loan, "contract_terminated_on", None),
        "schedule_version": int(loan.schedule_version),
        "schedule": [
            {key: value for key, value in asdict(row).items() if key != "admin_overridden"}
            for row in schedule
        ],
    }


def _recovery_events_by_holding(
    *, investor_user_id: str, holding_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """U33-DEC-12: each recovery of the loan with its gross, costs and net, and the investor's
    own credited share, per holding. Closed recoveries are shown as recorded."""
    if not holding_ids:
        return {}
    line_model = _model("servicing", "InvestorRecoveryDistributionLine")
    events: dict[str, dict[str, dict[str, Any]]] = {}
    lines = (
        line_model.objects.filter(investor_user_id=investor_user_id, holding_id__in=holding_ids)
        .select_related("recovery_event")
        .order_by("recovery_event__value_date", "recovery_event__created_at", "id")
    )
    for line in lines:
        event = line.recovery_event
        by_event = events.setdefault(str(line.holding_id), {})
        entry = by_event.get(str(event.pk))
        if entry is None:
            entry = {
                "recovery_event_id": str(event.pk),
                "value_date": event.value_date,
                "gross_recovered_minor": int(event.gross_recovered_minor),
                "external_costs_minor": int(event.externally_deducted_costs_minor)
                + int(event.third_party_costs_from_received_minor),
                "recovery_fee_minor": int(event.recovery_fee_minor),
                "net_distributed_minor": int(event.net_available_for_distribution_minor)
                - int(event.rounding_difference_minor),
                "credited_to_you_minor": 0,
            }
            by_event[str(event.pk)] = entry
        entry["credited_to_you_minor"] += int(line.amount_minor)
    return {holding_id: list(rows.values()) for holding_id, rows in events.items()}


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


def _received_payments_by_holding(
    *, investor_user_id: str, holding_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """18.3: the investor's share of each payment already received ("Paid" rows of All payments).

    Direct loans: one row per borrower installment (several partial payments of one installment
    are added up), with its number and due date. Loan Originator claims: one row per payment the
    originator passed on, dated by its value date. Recoveries are listed with the recovery events.
    """
    if not holding_ids:
        return {}
    rows: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)

    def add(holding_id: str, key: str, values: dict[str, Any], line: Any) -> None:
        row = rows[holding_id].setdefault(
            (holding_id, key),
            {
                **values,
                "principal_minor": 0,
                "interest_minor": 0,
                "penalty_minor": 0,
                "fee_minor": 0,
                "credited_minor": 0,
                "principal_after_minor": int(line.current_principal_after_minor),
            },
        )
        row["principal_minor"] += int(line.principal_minor)
        row["interest_minor"] += int(line.interest_minor)
        row["penalty_minor"] += int(getattr(line, "penalty_minor", 0) or 0)
        row["fee_minor"] += int(getattr(line, "fee_minor", 0) or 0)
        row["credited_minor"] += int(line.amount_minor)
        row["principal_after_minor"] = min(
            int(row["principal_after_minor"]), int(line.current_principal_after_minor)
        )
        if values["paid_on"] > row["paid_on"]:
            row["paid_on"] = values["paid_on"]

    for line in (
        _model("servicing", "InvestorRepaymentDistributionLine")
        .objects.filter(investor_user_id=investor_user_id, holding_id__in=holding_ids)
        .select_related("repayment_event__installment")
    ):
        installment = line.repayment_event.installment
        add(
            str(line.holding_id),
            f"installment:{installment.pk}",
            {
                "installment_number": int(installment.installment_number),
                "due_date": installment.due_date,
                "paid_on": line.repayment_event.value_date,
            },
            line,
        )
    for line in (
        _model("originator_claims", "InvestorOriginatorRepaymentDistributionLine")
        .objects.filter(investor_user_id=investor_user_id, holding_id__in=holding_ids)
        .select_related("repayment")
    ):
        add(
            str(line.holding_id),
            f"originator:{line.repayment_id}",
            {
                "installment_number": None,
                "due_date": None,
                "paid_on": line.repayment.value_date,
            },
            line,
        )
    result: dict[str, list[dict[str, Any]]] = {}
    for holding_id, by_key in rows.items():
        payments = sorted(
            by_key.values(),
            key=lambda row: (row["due_date"] or row["paid_on"], row["paid_on"]),
        )
        for payment in payments:
            payment["total_minor"] = (
                int(payment["principal_minor"])
                + int(payment["interest_minor"])
                + int(payment["penalty_minor"])
            )
        result[holding_id] = payments
    return result


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
        # Audit S5-9: direct loans on the 18.6 engine pay penalty X to the investors too.
        fields=["amount_minor", "principal_minor", "interest_minor", "penalty_minor", "fee_minor"],
    )
    originator_repayment_totals = _aggregate_by_holding(
        model_label=("originator_claims", "InvestorOriginatorRepaymentDistributionLine"),
        investor_user_id=investor_user_id,
        holding_ids=all_holding_ids,
        fields=["amount_minor", "principal_minor", "interest_minor", "penalty_minor"],
    )
    recovery_events = _recovery_events_by_holding(
        investor_user_id=investor_user_id, holding_ids=all_holding_ids
    )
    received_payments = _received_payments_by_holding(
        investor_user_id=investor_user_id, holding_ids=all_holding_ids
    )
    # U33-DEC-22: the recorded stages and the known next step of each loan.
    recovery_stages = import_module(
        "backend.apps.servicing.recovery_stages"
    ).investor_recovery_stages(sorted({str(holding.loan_id) for holding in holdings}))
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
        for purchase in (
            originator_purchase_model.objects.filter(
                holding_id__in=[holding.pk for holding in holdings]
            )
            .select_related("loan_profile")
            .prefetch_related("entitlements")
        )
    }
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    open_listings_by_holding_id = {
        str(listing.holding_id): listing
        for listing in listing_model.objects.filter(
            holding_id__in=[holding.pk for holding in holdings],
            status__in=["active", "approval_requested"],
        )
        .select_related("loan", "loan__originator_profile")
        .order_by("holding_id", "-updated_at", "-id")
    }
    # C03: an open listing is "Pending" while an installment of its loan is due and unpaid.
    paused_loan_ids = (
        import_module("backend.apps.secondary_market.services").loan_ids_closed_to_new_buyers(
            loans=list(
                {
                    str(listing.loan_id): listing.loan
                    for listing in open_listings_by_holding_id.values()
                }.values()
            ),
            as_of_date=business_date(now_utc()),
        )
        if open_listings_by_holding_id
        else set()
    )
    # Q04: the "Banxum invests" label on the investment page (no amount).
    banxum_loan_ids = import_module(
        "backend.apps.marketplace_primary.services"
    ).banxum_invests_loan_ids(list({str(holding.loan_id) for holding in holdings}))
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
                "loan": {
                    **_loan_projection(
                        loan,
                        as_of=as_of_value,
                        schedule=schedules_by_loan_id.get(str(holding.loan_id), []),
                    ),
                    "banxum_invests": str(holding.loan_id) in banxum_loan_ids,
                },
                "received_principal_minor": int(repayment.get("principal_minor", 0))
                + int(originator_repayment.get("principal_minor", 0)),
                "received_interest_minor": int(repayment.get("interest_minor", 0))
                + int(originator_repayment.get("interest_minor", 0)),
                "received_penalty_minor": int(repayment.get("penalty_minor", 0))
                + int(originator_repayment.get("penalty_minor", 0)),
                "repayment_fee_minor": int(repayment.get("fee_minor", 0)),
                "received_payments": received_payments.get(str(holding.pk), []),
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
                # 18.7: the accrued interest paid in the price of a Loan Originator offer. It
                # comes back with the next payment and is not interest earned.
                "bought_accrued_interest_minor": (
                    max(
                        0,
                        int(originator_purchase.cash_consideration_minor)
                        - int(originator_purchase.assigned_principal_minor),
                    )
                    if originator_purchase is not None
                    and str(originator_purchase.loan_profile.pricing_rule) == "accrued_interest"
                    else 0
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
                "recovery_events": recovery_events.get(str(holding.pk), []),
                "recovery_stages": recovery_stages.get(str(holding.loan_id), {}).get(
                    "stages", []
                ),
                "recovery_next_step": recovery_stages.get(str(holding.loan_id), {}).get(
                    "next_step"
                ),
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
                        "paused_for_due_installment": str(open_listing.loan_id) in paused_loan_ids,
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


def get_investor_transactions(
    *, actor: Model, filters: Any, offset: int = 0, limit: int = 15
) -> dict[str, Any]:
    """18.3: the Transactions page from the server (filters, pages, available after)."""
    investor_user_id = _require_financial_access(actor)
    transactions = import_module("backend.apps.investor_portal.transactions")
    entries = merge_archived_activity(
        investor_user_id=investor_user_id,
        stream="portfolio",
        entries=_investor_activity_entries(investor_user_id, None),
        # Audit S2-1: the whole history; no cap that would hide the oldest movements.
        limit=None,
    )
    return cast(
        dict[str, Any],
        transactions.transaction_page(
            investor_user_id=investor_user_id,
            entries=entries,
            filters=filters,
            offset=offset,
            limit=limit,
        ),
    )


def export_investor_transactions_csv(*, actor: Model, filters: Any) -> str:
    """18.3: the whole filtered history as CSV, in the investor's number format."""
    investor_user_id = _require_financial_access(actor)
    transactions = import_module("backend.apps.investor_portal.transactions")
    entries = merge_archived_activity(
        investor_user_id=investor_user_id,
        stream="portfolio",
        entries=_investor_activity_entries(investor_user_id, None),
        # Audit S2-1: the whole history; no cap that would hide the oldest movements.
        limit=None,
    )
    return cast(
        str,
        transactions.transactions_csv(
            investor_user_id=investor_user_id,
            entries=entries,
            filters=filters,
            number_format=clean_number_format(getattr(actor, "number_format", None)),
        ),
    )


def _investor_activity_entries(
    investor_user_id: str, limit_value: int | None
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    lot_model = _model("ledger", "InvestorBalanceLot")
    withdrawal_model = _model("ledger", "InvestorWithdrawalRequest")
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
        .select_related(
            "currency", "repayment_event", "repayment_event__loan", "repayment_event__installment"
        )
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
                    "penalty_minor": int(line.penalty_minor),
                    "fee_minor": int(line.fee_minor),
                    "installment_number": int(line.repayment_event.installment.installment_number),
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
        .select_related("currency", "return_failure")
        .order_by("-requested_at")[:limit_value]
    ):
        withdrawal_status = str(withdrawal.status)
        entries.append(
            _activity(
                activity_id=str(withdrawal.pk),
                activity_type="withdrawal_request",
                occurred_at=withdrawal.requested_at,
                direction="out",
                # A forced return is started by Garanta when money was not invested within the
                # auto-return days (58 by default), not by the investor.
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
        returned = (
            getattr(withdrawal, "return_failure", None)
            if withdrawal_status == "returned"
            else None
        )
        if returned is not None:
            # 18.4 (Q02): the bank sent the transfer back; the money is on the balance again.
            entries.append(
                _activity(
                    activity_id=f"{withdrawal.pk}:returned",
                    activity_type="withdrawal_returned",
                    occurred_at=returned.recorded_at,
                    direction="in",
                    title=(
                        "Return sent back by the bank"
                        if withdrawal.is_forced
                        else "Withdrawal sent back by the bank"
                    ),
                    amount_minor=int(withdrawal.amount_minor),
                    currency=_currency_code(withdrawal.currency),
                    status="returned",
                    metadata={
                        "withdrawal_request_id": str(withdrawal.pk),
                        "is_forced": bool(withdrawal.is_forced),
                        "reason_code": str(returned.reason_code),
                        "value_date": returned.returned_value_date.isoformat(),
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
    entries.extend(_primary_order_activity(investor_user_id, limit_value))
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


# Q26 (2026-11-13): why a reservation ended without an investment, from the order event's code.
PRIMARY_ORDER_END_REASONS = {
    "no_capacity_at_allocation": "No amount was left in the project when the order was processed.",
    "remaining_capacity_below_loan_minimum": (
        "The amount left in the project was below the minimum investment."
    ),
    "loan_funding_closed": "The funding closed without this order.",
    "loan_funding_cancelled": "The project's funding was cancelled.",
    "replaced_by_new_order": "Replaced by a newer order on the same loan before confirmation.",
    "pending_order_expired": "Not confirmed within the pending-order time limit.",
    "released_by_banxum": "Released by Banxum.",
}


def _primary_order_activity(investor_user_id: str, limit_value: int | None) -> list[dict[str, Any]]:
    """Q26: the reservation, its release and the closing are separate entries in Transactions.

    Each entry has the project, amount, currency, date, the reason of a release and the order it
    belongs to. An order still waiting for allocation is one "order placed" entry.
    """
    order_model = _model("marketplace_primary", "PrimaryInvestmentOrder")
    event_model = _model("marketplace_primary", "PrimaryInvestmentOrderEvent")
    orders = {
        str(order.pk): order
        for order in order_model.objects.filter(investor_user_id=investor_user_id)
        .select_related("currency", "loan")
        .order_by("-created_at")[:limit_value]
    }
    if not orders:
        return []
    events = list(
        event_model.objects.filter(order_id__in=list(orders)).order_by("occurred_at", "id")
    )
    released_order_ids = {
        str(event.order_id) for event in events if event.event_type == "balance_released"
    }
    allocated_order_ids = {
        str(event.order_id) for event in events if event.event_type == "balance_allocated"
    }
    entries: list[dict[str, Any]] = []

    def entry(
        order: Any, event: Any, activity_type: str, amount_minor: int, direction: str, title: str
    ) -> dict[str, Any]:
        metadata = dict(cast(dict[str, Any], event.metadata or {}))
        # The admin's note stays internal (it is never shown to the investor); the reason comes
        # from the event's code.
        code = str(metadata.get("reason_code") or metadata.get("reason") or "")
        reason = PRIMARY_ORDER_END_REASONS.get(code, "")
        if not reason and activity_type == "primary_reservation_released":
            reason = (
                "Released by Banxum."
                if str(event.event_type) == "balance_released"
                else "The order ended without an investment."
            )
        return _activity(
            activity_id=f"{order.pk}:{event.pk}",
            activity_type=activity_type,
            occurred_at=event.occurred_at,
            direction=direction,
            title=title,
            amount_minor=amount_minor,
            currency=_currency_code(order.currency),
            status=str(order.status),
            loan_id=str(order.loan_id),
            loan_title=str(order.loan.title),
            metadata={"order_id": str(order.pk), "reason": reason},
        )

    for event in events:
        order = orders[str(event.order_id)]
        metadata = dict(cast(dict[str, Any], event.metadata or {}))
        event_type = str(event.event_type)
        if event_type == "created" and str(order.pk) not in allocated_order_ids:
            if str(order.status) in {"pending", "pending_allocation"}:
                entries.append(
                    entry(
                        order,
                        event,
                        "primary_order",
                        int(order.requested_amount_minor),
                        "internal",
                        "Investment order placed",
                    )
                )
        elif event_type == "balance_allocated":
            entries.append(
                entry(
                    order,
                    event,
                    "primary_reservation",
                    int(metadata.get("allocated_amount_minor") or order.allocated_amount_minor),
                    "internal",
                    "Amount reserved",
                )
            )
        elif event_type == "balance_released":
            entries.append(
                entry(
                    order,
                    event,
                    "primary_reservation_released",
                    int(metadata.get("released_amount_minor") or order.allocated_amount_minor),
                    "internal",
                    "Reservation released",
                )
            )
        elif event_type == "closed_invested":
            entries.append(
                entry(
                    order,
                    event,
                    "primary_investment",
                    int(metadata.get("allocated_amount_minor") or order.allocated_amount_minor),
                    "out",
                    "Investment",
                )
            )
        elif event_type == "closed_not_invested":
            had_reservation = (
                str(order.pk) in allocated_order_ids and str(order.pk) not in released_order_ids
            )
            entries.append(
                entry(
                    order,
                    event,
                    "primary_reservation_released" if had_reservation else "primary_order_ended",
                    int(order.allocated_amount_minor)
                    if had_reservation
                    else int(order.requested_amount_minor),
                    "internal",
                    "Reservation released" if had_reservation else "Investment order not invested",
                )
            )
    # An order without recorded events (older records): one entry with its current state.
    ordered_ids = {str(event.order_id) for event in events}
    for order_id, order in orders.items():
        if order_id in ordered_ids:
            continue
        entries.append(
            _activity(
                activity_id=order_id,
                activity_type="primary_order",
                occurred_at=order.created_at,
                direction="internal",
                title="Primary-market investment order",
                amount_minor=int(order.allocated_amount_minor) or int(order.requested_amount_minor),
                currency=_currency_code(order.currency),
                status=str(order.status),
                loan_id=str(order.loan_id),
                loan_title=str(order.loan.title),
                metadata={"order_id": order_id, "reason": ""},
            )
        )
    return entries


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


def _listing_state(status: str) -> str:
    """18.3: the design's state of a seller's listing: listed, sold or cancelled.

    A listing removed or refused by Banxum is shown as cancelled (it is no longer on sale).
    """
    if status in {"active", "approval_requested"}:
        return "listed"
    if status == "sold":
        return "sold"
    return "cancelled"


def _secondary_market_activity(investor_user_id: str, limit_value: int | None) -> dict[str, Any]:
    listing_model = _model("secondary_market", "SecondaryMarketListing")
    listing_event_model = _model("secondary_market", "SecondaryMarketListingEvent")
    purchase_model = _model("secondary_market", "SecondaryMarketPurchase")
    seller_listings = list(
        listing_model.objects.filter(seller_user_id=investor_user_id)
        .select_related("currency", "loan", "loan__originator_profile")
        .order_by("-created_at", "-id")[:limit_value]
    )
    open_loans = {
        str(listing.loan_id): listing.loan
        for listing in seller_listings
        if str(listing.status) in {"active", "approval_requested"}
    }
    # C03: an open listing is "Pending" while an installment of its loan is due and unpaid.
    paused_loan_ids = (
        import_module("backend.apps.secondary_market.services").loan_ids_closed_to_new_buyers(
            loans=list(open_loans.values()), as_of_date=business_date(now_utc())
        )
        if open_loans
        else set()
    )
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
            # 18.3: My listings states (listed, sold, cancelled) and the day the listing closed.
            "state": _listing_state(str(listing.status)),
            "closed_at": (
                listing.cancelled_at or listing.removed_at or listing.rejected_at
                if str(listing.status) in {"cancelled", "removed", "rejected"}
                else None
            ),
            "paused_for_due_installment": (
                str(listing.status) in {"active", "approval_requested"}
                and str(listing.loan_id) in paused_loan_ids
            ),
        }
        for listing in seller_listings
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


def get_investor_portal_features() -> dict[str, bool]:
    """Platform switches for the investor app (anonymous-safe: no account data).

    ``fx_enabled``: currency exchange is offered (owner decision 2026-10-16: off for now).
    """
    return {"fx_enabled": bool(_fx_services().fx_enabled())}


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
                        "This money was not invested in time and must go back to your bank. "
                        "Add a verified bank account so we can return your money."
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
                        "Last day: this money can only be withdrawn today. Tomorrow it goes "
                        "back to your bank."
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
