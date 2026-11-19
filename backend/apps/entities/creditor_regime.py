# IP of Webby-Soft SRL.
"""18.9 (Q03, F06-F09, E-02): admin services of the Swiss creditor modes.

- ``set_creditor_mode``: record / confirm / switch the mode of a borrower UID with the switching
  rules (to 10/20 only with at most 20 creditors and at most 10 per open financing; to sandbox
  only below CHF 500,000; never while a project of the borrower is in funding).
- ``record_external_debt`` / ``end_external_debt``: F09 records from the signed declaration.
- ``record_snb_rate``: the SNB reference rate of a day (source kept), for the CHF total.
- ``creditor_mode_overview``: the admin view of a UID (mode, total, creditors, debts).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from importlib import import_module
from typing import Any, cast

from django.db import transaction
from django.db.models import Model

from backend.apps.entities.models import (
    BorrowerEntity,
    BorrowerEntityEvent,
    BorrowerEntityEventType,
    BorrowerExternalDebt,
    SwissCreditorRegime,
)
from backend.apps.entities.services import BorrowerValidationError, _require_admin_actor
from backend.apps.platform_core.domain import creditor_regime as rules
from backend.apps.platform_core.domain.access import actor_ref_for_user
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import SnbReferenceRate
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event


def _limits() -> Any:
    return import_module("backend.apps.marketplace_primary.investor_limit")


def _regimes() -> Any:
    return import_module("backend.apps.marketplace_primary.creditor_regime")


def _uid(value: str) -> str:
    try:
        return rules.normalize_uid(value)
    except rules.CreditorRegimeError as exc:
        raise BorrowerValidationError(str(exc)) from exc


def _record_events(*, actor: Model, uid: str, event_type: str, metadata: dict[str, Any]) -> None:
    """One borrower event per Direct borrower entity with this UID, plus an audit entry."""
    for borrower in BorrowerEntity.objects.filter(uid=uid):
        BorrowerEntityEvent.objects.create(
            borrower=borrower,
            event_type=event_type,
            actor_user_id=cast(Any, actor).pk,
            actor_account_type=str(getattr(actor, "account_type", "admin")),
            metadata={"uid": uid, **metadata},
        )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action=f"entities.{event_type}",
            target_type="SwissCreditorRegime",
            target_id=uid,
            metadata={"uid": uid, **metadata},
        )
    )


@dataclass(frozen=True, slots=True)
class SetCreditorModeCommand:
    actor: Model
    uid: str
    mode: str
    note: str = ""


@transaction.atomic
def set_creditor_mode(command: SetCreditorModeCommand) -> SwissCreditorRegime:
    _require_admin_actor(command.actor)
    uid = _uid(command.uid)
    try:
        mode = rules.require_mode(command.mode)
    except rules.CreditorRegimeError as exc:
        raise BorrowerValidationError(str(exc)) from exc
    regime, _created = SwissCreditorRegime.objects.select_for_update().get_or_create(
        uid=uid, defaults={"mode": rules.MODE_SANDBOX}
    )
    previous = str(regime.mode)
    if mode != previous:
        loans = _limits().uid_loans(uid)
        if any(str(loan.status) == "published" for loan in loans):
            raise BorrowerValidationError(
                "The creditor mode cannot change while a project of this borrower is in funding."
            )
        if mode == rules.MODE_TEN_TWENTY:
            creditors = len(_limits().borrower_creditor_ids(uid))
            if creditors > rules.BORROWER_CREDITOR_LIMIT:
                raise BorrowerValidationError(
                    f"The borrower has {creditors} creditors; the 10/20 mode allows at most "
                    f"{rules.BORROWER_CREDITOR_LIMIT}."
                )
            investors = _limits().loan_investor_ids([str(loan.pk) for loan in loans])
            crowded = [
                loan_id
                for loan_id, ids in investors.items()
                if len(ids) > rules.FINANCING_CREDITOR_LIMIT
            ]
            if crowded:
                raise BorrowerValidationError(
                    "A financing of this borrower has more than "
                    f"{rules.FINANCING_CREDITOR_LIMIT} creditors; the 10/20 mode is not possible."
                )
        else:
            total = _regimes().borrower_total_chf_minor(uid, on=business_date(now_utc()))
            check = rules.check_sandbox_total(total)
            if not check.ok:
                raise BorrowerValidationError(check.message)
    regime.mode = mode
    regime.confirmed_by_admin_id = cast(Any, command.actor).pk
    regime.confirmed_at = now_utc()
    regime.confirmation_note = command.note.strip()
    regime.save(
        update_fields=[
            "mode",
            "confirmed_by_admin_id",
            "confirmed_at",
            "confirmation_note",
            "updated_at",
        ]
    )
    _record_events(
        actor=command.actor,
        uid=uid,
        event_type=BorrowerEntityEventType.CREDITOR_MODE_CHANGED,
        metadata={"previous_mode": previous, "mode": mode, "note": command.note.strip()},
    )
    return regime


@dataclass(frozen=True, slots=True)
class RecordExternalDebtCommand:
    actor: Model
    uid: str
    creditor_name: str
    creditor_identification: str
    creditor_is_bank: bool
    financing_id: str
    principal_minor: int
    currency: str
    start_date: date
    identical_terms_group: str = ""
    declaration_document_id: str | None = None
    declaration_reference: str = ""
    notes: str = ""


@transaction.atomic
def record_external_debt(command: RecordExternalDebtCommand) -> BorrowerExternalDebt:
    _require_admin_actor(command.actor)
    uid = _uid(command.uid)
    for label, value in (
        ("Creditor name", command.creditor_name),
        ("Creditor identification", command.creditor_identification),
        ("Financing ID", command.financing_id),
    ):
        if not str(value or "").strip():
            raise BorrowerValidationError(f"{label} is required.")
    if type(command.principal_minor) is not int or command.principal_minor <= 0:
        raise BorrowerValidationError("The principal must be positive.")
    currency = str(command.currency).strip().upper()
    if currency not in {"CHF", "EUR"}:
        raise BorrowerValidationError("The currency must be CHF or EUR.")
    if not command.declaration_document_id and not command.declaration_reference.strip():
        raise BorrowerValidationError(
            "Attach the signed borrower declaration (document or reference)."
        )
    identification = command.creditor_identification.strip().upper()
    if BorrowerExternalDebt.objects.filter(
        uid=uid,
        creditor_identification=identification,
        financing_id=command.financing_id.strip(),
        ended_on__isnull=True,
    ).exists():
        raise BorrowerValidationError("This debt is already recorded for the borrower.")
    debt = BorrowerExternalDebt.objects.create(
        uid=uid,
        creditor_name=command.creditor_name.strip(),
        creditor_identification=identification,
        creditor_is_bank=bool(command.creditor_is_bank),
        financing_id=command.financing_id.strip(),
        identical_terms_group=command.identical_terms_group.strip(),
        principal_minor=command.principal_minor,
        currency=currency,
        start_date=command.start_date,
        declaration_document_id=command.declaration_document_id or None,
        declaration_reference=command.declaration_reference.strip(),
        checked_by_admin_id=cast(Any, command.actor).pk,
        checked_at=now_utc(),
        notes=command.notes.strip(),
    )
    _record_events(
        actor=command.actor,
        uid=uid,
        event_type=BorrowerEntityEventType.EXTERNAL_DEBT_RECORDED,
        metadata={
            "external_debt_id": str(debt.id),
            "financing_id": debt.financing_id,
            "principal_minor": debt.principal_minor,
            "currency": currency,
        },
    )
    return debt


@transaction.atomic
def end_external_debt(*, actor: Model, debt_id: str, ended_on: date) -> BorrowerExternalDebt:
    _require_admin_actor(actor)
    debt = BorrowerExternalDebt.objects.select_for_update().filter(id=debt_id).first()
    if debt is None:
        raise BorrowerValidationError("External debt does not exist.")
    if debt.ended_on is not None:
        return debt
    if ended_on < debt.start_date:
        raise BorrowerValidationError("A debt cannot end before it started.")
    debt.ended_on = ended_on
    debt.save(update_fields=["ended_on", "updated_at"])
    _record_events(
        actor=actor,
        uid=str(debt.uid),
        event_type=BorrowerEntityEventType.EXTERNAL_DEBT_ENDED,
        metadata={"external_debt_id": str(debt.id), "ended_on": ended_on.isoformat()},
    )
    return debt


@transaction.atomic
def record_snb_rate(
    *, actor: Model, currency: str, rate_date: date, chf_per_unit: str, source: str
) -> SnbReferenceRate:
    _require_admin_actor(actor)
    code = str(currency).strip().upper()
    if code != "EUR":
        raise BorrowerValidationError("Only EUR needs an SNB reference rate.")
    try:
        rate = Decimal(str(chf_per_unit).strip())
    except InvalidOperation as exc:
        raise BorrowerValidationError("Enter the rate as a number (CHF per 1 EUR).") from exc
    if rate <= 0 or rate > 10:
        raise BorrowerValidationError("The rate must be between 0 and 10 CHF per EUR.")
    if not source.strip():
        raise BorrowerValidationError("Write the source of the rate (SNB publication).")
    if rate_date > business_date(now_utc()):
        raise BorrowerValidationError("The rate date cannot be in the future.")
    record, _created = SnbReferenceRate.objects.update_or_create(
        currency=code,
        rate_date=rate_date,
        defaults={
            "chf_per_unit": rate.quantize(Decimal("0.000001")),
            "source": source.strip(),
            "entered_by_admin_id": cast(Any, actor).pk,
        },
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="platform.snb_rate_recorded",
            target_type="SnbReferenceRate",
            target_id=str(record.id),
            metadata={"currency": code, "rate_date": rate_date.isoformat(), "rate": str(rate)},
        )
    )
    return record


def creditor_mode_overview(*, actor: Model, uid: str) -> dict[str, Any]:
    _require_admin_actor(actor)
    uid = _uid(uid)
    regime = SwissCreditorRegime.objects.filter(uid=uid).first()
    loans = _limits().uid_loans(uid)
    investors = _limits().loan_investor_ids([str(loan.pk) for loan in loans])
    total: int | None
    total_error = ""
    try:
        total = int(_regimes().borrower_total_chf_minor(uid, on=business_date(now_utc())))
    except _regimes().CreditorRegimeViolation as exc:
        total = None
        total_error = str(exc)
    return {
        "uid": uid,
        "mode": str(regime.mode) if regime is not None else rules.MODE_SANDBOX,
        "confirmed": bool(regime is not None and regime.confirmed_at is not None),
        "confirmed_at": regime.confirmed_at if regime is not None else None,
        "confirmed_by_admin_id": (
            str(regime.confirmed_by_admin_id)
            if regime is not None and regime.confirmed_by_admin_id
            else None
        ),
        "confirmation_note": str(regime.confirmation_note) if regime is not None else "",
        "total_chf_minor": total,
        "total_error": total_error,
        "sandbox_limit_chf_minor": rules.SANDBOX_TOTAL_LIMIT_CHF_MINOR,
        "borrower_creditors": len(_limits().borrower_creditor_ids(uid)),
        "borrower_creditor_limit": rules.BORROWER_CREDITOR_LIMIT,
        "financing_creditor_limit": rules.FINANCING_CREDITOR_LIMIT,
        "financings": [
            {
                "loan_id": str(loan.pk),
                "title": str(loan.title),
                "status": str(loan.status),
                "currency": str(loan.currency_id),
                "creditors": len(investors.get(str(loan.pk), frozenset())),
            }
            for loan in loans
        ],
        "external_debts": [
            {
                "id": str(debt.id),
                "creditor_name": debt.creditor_name,
                "creditor_identification": debt.creditor_identification,
                "creditor_is_bank": debt.creditor_is_bank,
                "financing_id": debt.financing_id,
                "identical_terms_group": debt.identical_terms_group,
                "principal_minor": int(debt.principal_minor),
                "currency": debt.currency,
                "start_date": debt.start_date,
                "ended_on": debt.ended_on,
                "declaration_reference": debt.declaration_reference,
                "checked_at": debt.checked_at,
            }
            for debt in BorrowerExternalDebt.objects.filter(uid=uid).order_by("start_date", "id")
        ],
    }
