# IP of Webby-Soft SRL.
"""18.9 (Q03, F06-F09, E-02, E-03): Swiss creditor modes applied to publications, investments,
closes and the sandbox notice. The rules are in ``platform_core.domain.creditor_regime``; the
creditor counts and limits per loan in ``marketplace_primary.investor_limit``.

Checks:

- at publication (Direct loans and Loan Originator offers): a Swiss borrower needs a valid UID;
  its mode is recorded (pre-selected sandbox) and confirmed by the publishing admin when nobody
  confirmed it yet; sandbox: the total with the whole new amount stays below CHF 500,000; 10/20:
  the borrower has at most 20 creditors; production refuses a sandbox publication while the
  notice text is not approved;
- at each investment path (order, claim purchase, resale) the creditor limit of the 10/20 mode,
  under the loan lock and the borrower's regime lock (``lock_borrower``);
- before a close: the same limits and the sandbox total again; a failure stops the close.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db.models import Model

from backend.apps.marketplace_primary.investor_limit import (
    active_external_debts,
    borrower_creditor_ids,
    is_in_funding,
    loan_borrower_country,
    loan_borrower_uid,
    loan_investor_ids,
    normalized_uid,
    regime_for_uid,
    uid_loans,
)
from backend.apps.platform_core.domain import creditor_regime as rules
from backend.apps.platform_core.domain.countries import is_switzerland
from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.selectors.settings import get_platform_setting_value


class CreditorRegimeViolation(ValueError):
    pass


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def is_swiss_loan(loan: Model) -> bool:
    return is_switzerland(loan_borrower_country(loan))


def chf_minor(amount_minor: int, currency: str, *, on: date) -> int:
    """An amount in CHF minor units at the SNB reference rate of ``on`` (or the last one before)."""
    code = str(currency).upper()
    if code == "CHF":
        return int(amount_minor)
    rate = (
        _model("platform_core", "SnbReferenceRate")
        .objects.filter(currency=code, rate_date__lte=on)
        .order_by("-rate_date")
        .first()
    )
    if rate is None:
        raise CreditorRegimeViolation(
            f"Enter the SNB reference rate for {code} (Admin > Swiss creditor modes) before this "
            "check: the borrower total is counted in CHF."
        )
    value = Decimal(int(amount_minor)) * Decimal(rate.chf_per_unit)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _loan_count_amount_minor(loan: Any) -> int:
    """F07 / Q03: the whole published amount while in funding, the original amount after."""
    if str(loan.product_type) == "originator_claim":
        # The underlying loan counted once.
        return int(loan.original_principal_minor)
    if is_in_funding(loan):
        return int(loan.principal_minor)
    return int(loan.original_principal_minor or loan.principal_minor)


def _financing_key(loan: Any, claim_keys: dict[str, str]) -> str:
    """Audit S6-9: one key per underlying financing. A Loan Originator claim is keyed by its
    originator and the originator's financing identifier, so two offers of one underlying loan
    count once; any other loan by its own id."""
    return claim_keys.get(str(loan.pk)) or f"loan:{loan.pk}"


def _claim_keys(loans: list[Any]) -> dict[str, str]:
    claim_ids = [loan.pk for loan in loans if str(loan.product_type) == "originator_claim"]
    if not claim_ids:
        return {}
    rows = (
        _model("originator_claims", "OriginatorLoanProfile")
        .objects.filter(loan_id__in=claim_ids)
        .exclude(underlying_financing_id="")
        .values_list("loan_id", "originator_id", "underlying_financing_id")
    )
    return {
        str(loan_id): f"claim:{originator_id}:{financing_id}"
        for loan_id, originator_id, financing_id in rows
    }


def borrower_total_chf_minor(uid: str, *, on: date, include_loan: Model | None = None) -> int:
    """T: the borrower's loans in funding or running (each underlying financing once), plus the
    external debts that run on ``on``, in CHF."""
    total = 0
    loans = uid_loans(uid)
    seen = {str(loan.pk) for loan in loans}
    if include_loan is not None and str(include_loan.pk) not in seen:
        loans.append(include_loan)
    claim_keys = _claim_keys(loans)
    counted: set[str] = set()
    for loan in loans:
        key = _financing_key(loan, claim_keys)
        if key in counted:
            continue
        counted.add(key)
        total += chf_minor(_loan_count_amount_minor(loan), str(loan.currency_id), on=on)
    for debt in active_external_debts(uid, on=on):
        total += chf_minor(int(debt.principal_minor), str(debt.currency), on=on)
    return total


MISSING_UID_MESSAGE = (
    "This Swiss borrower has no valid UID (CHE-123.456.789) recorded. Investments, transfers "
    "and closes of its financings stop until an admin records the UID; the creditor mode "
    "checks need it."
)


def require_valid_uid(loan: Model) -> str:
    """Audit S6-5: a Swiss loan needs a valid UID for every investment, transfer and close (a
    loan published before 18.9 may have none). The UID is never guessed."""
    uid = normalized_uid(loan_borrower_uid(loan))
    if not uid:
        raise CreditorRegimeViolation(MISSING_UID_MESSAGE)
    return uid


def lock_borrower(loan: Model) -> Any | None:
    """Lock the borrower's regime row so concurrent investments of the same UID queue (Q03).

    A UID without a row yet (a loan published before 18.9) gets one in the pre-selected sandbox
    mode, not confirmed, so there is always a row to lock. Audit S6-5: a Swiss loan without a
    valid UID is refused (CreditorRegimeViolation). Lock order: the loan, then this row, then
    the money rows.
    """
    if not is_swiss_loan(loan):
        return None
    uid = require_valid_uid(loan)
    regime, _created = (
        _model("entities", "SwissCreditorRegime")
        .objects.select_for_update()
        .get_or_create(uid=uid, defaults={"mode": rules.MODE_SANDBOX})
    )
    return regime


def ensure_uid_and_regime(loan: Model, *, actor: Model) -> Any | None:
    """At publication: a valid UID and a confirmed mode (pre-selected sandbox)."""
    if not is_swiss_loan(loan):
        return None
    raw_uid = loan_borrower_uid(loan)
    try:
        uid = rules.normalize_uid(raw_uid)
    except rules.CreditorRegimeError as exc:
        raise CreditorRegimeViolation(
            "A Swiss borrower needs its UID (CHE-123.456.789) before publication. " + str(exc)
        ) from exc
    model = _model("entities", "SwissCreditorRegime")
    regime, _created = model.objects.select_for_update().get_or_create(
        uid=uid, defaults={"mode": rules.MODE_SANDBOX}
    )
    if regime.confirmed_at is None:
        # The admin's creditor mode panel shows the pre-selected mode; publishing confirms it.
        regime.confirmed_by_admin_id = cast(Any, actor).pk
        regime.confirmed_at = now_utc()
        regime.confirmation_note = "Confirmed with the first publication."
        regime.save(
            update_fields=[
                "confirmed_by_admin_id",
                "confirmed_at",
                "confirmation_note",
                "updated_at",
            ]
        )
    return regime


def check_publication(loan: Model, *, actor: Model, on: date) -> None:
    regime = ensure_uid_and_regime(loan, actor=actor)
    if regime is None:
        return
    uid = str(regime.uid)
    if str(regime.mode) == rules.MODE_SANDBOX:
        if getattr(settings, "IS_PRODUCTION", False) and not sandbox_notice_approved():
            raise CreditorRegimeViolation(
                "The sandbox notice text is not approved yet: a borrower in sandbox mode cannot "
                "be published in production."
            )
        result = rules.check_sandbox_total(borrower_total_chf_minor(uid, on=on, include_loan=loan))
    else:
        result = rules.check_ten_twenty(
            financing_creditors=0, borrower_creditors=len(borrower_creditor_ids(uid, on=on))
        )
    if not result.ok:
        raise CreditorRegimeViolation(result.message)


def check_before_close(loan: Model, *, on: date) -> None:
    """Before a funding close (F08): a failure stops the close; an admin decides. The regime
    row is locked (audit S6-8) and a valid UID is required (audit S6-5)."""
    if not is_swiss_loan(loan):
        return
    regime = lock_borrower(loan)
    uid = str(regime.uid) if regime is not None else ""
    mode = str(regime.mode) if regime is not None else rules.MODE_SANDBOX
    if mode == rules.MODE_SANDBOX:
        result = rules.check_sandbox_total(borrower_total_chf_minor(uid, on=on, include_loan=loan))
    else:
        financing = loan_investor_ids([str(loan.pk)]).get(str(loan.pk), frozenset())
        result = rules.check_ten_twenty(
            financing_creditors=len(financing),
            borrower_creditors=len(borrower_creditor_ids(uid, on=on)),
        )
    if not result.ok:
        raise CreditorRegimeViolation(f"Swiss creditor mode check failed: {result.message}")


def sandbox_notice_approved() -> bool:
    return bool(get_platform_setting_value(rules.SANDBOX_NOTICE_APPROVED_SETTING, False))


def sandbox_notice(loan: Model, *, borrower_name: str) -> dict[str, Any] | None:
    """E-03: the notice of a borrower in sandbox mode, with its version (sha256 of the text)."""
    if not is_swiss_loan(loan):
        return None
    uid = loan_borrower_uid(loan)
    regime = regime_for_uid(uid)
    mode = str(regime.mode) if regime is not None else rules.MODE_SANDBOX
    if mode != rules.MODE_SANDBOX:
        return None
    configured = get_platform_setting_value(
        rules.SANDBOX_NOTICE_TEXT_SETTING, rules.SANDBOX_NOTICE_PLACEHOLDER
    )
    template = str(configured or rules.SANDBOX_NOTICE_PLACEHOLDER)
    text = template.replace("{borrower}", borrower_name or "The borrower")
    return {
        "text": text,
        "version": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "approved": sandbox_notice_approved(),
    }


def creditor_mode_payload(loan: Model) -> str | None:
    if not is_swiss_loan(loan):
        return None
    regime = regime_for_uid(loan_borrower_uid(loan))
    return str(regime.mode) if regime is not None else rules.MODE_SANDBOX


def swiss_loans_without_uid() -> list[Any]:
    """Audit S6-5: live Swiss financings (in funding or running) whose borrower has no valid UID
    (loans published before 18.9). They take no investment, transfer or close until an admin
    records the UID from the borrower's register entry; the UID is never guessed."""
    from backend.apps.marketplace_primary.investor_limit import REGIME_LOAN_STATUSES

    loans = _model("loans", "Loan").objects.filter(status__in=REGIME_LOAN_STATUSES).order_by("id")
    return [
        loan
        for loan in loans
        if is_swiss_loan(cast(Model, loan))
        and not normalized_uid(loan_borrower_uid(cast(Model, loan)))
    ]


def open_missing_uid_tasks(*, actor: Model) -> list[str]:
    """One operations task per Swiss financing without a valid UID; returns the loan ids."""
    admin_ops = import_module("backend.apps.admin_ops.services")
    loan_ids: list[str] = []
    for loan in swiss_loans_without_uid():
        admin_ops.ensure_related_admin_task(
            actor=actor,
            task_type="compliance_review",
            related_object_type="SwissBorrowerUidMissing",
            related_object_id=str(loan.pk),
            title=f"Record the Swiss UID of the borrower of {loan.title}",
            priority="high",
            notes=MISSING_UID_MESSAGE,
        )
        loan_ids.append(str(loan.pk))
    return loan_ids
