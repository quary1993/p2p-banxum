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
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db.models import Model

from backend.apps.marketplace_primary.investor_limit import (
    borrower_creditor_ids,
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
    if str(loan.status) == "published":
        return int(loan.principal_minor)
    return int(loan.original_principal_minor or loan.principal_minor)


def borrower_total_chf_minor(uid: str, *, on: date, include_loan: Model | None = None) -> int:
    """T: the borrower's loans in funding or running, plus open external debts, in CHF."""
    total = 0
    loans = uid_loans(uid)
    seen = {str(loan.pk) for loan in loans}
    if include_loan is not None and str(include_loan.pk) not in seen:
        loans.append(include_loan)
    for loan in loans:
        total += chf_minor(_loan_count_amount_minor(loan), str(loan.currency_id), on=on)
    for debt in _model("entities", "BorrowerExternalDebt").objects.filter(
        uid=uid, ended_on__isnull=True
    ):
        total += chf_minor(int(debt.principal_minor), str(debt.currency), on=on)
    return total


def lock_borrower(loan: Model) -> Any | None:
    """Lock the borrower's regime row so concurrent investments of the same UID queue (Q03).

    A UID without a row yet (a loan published before 18.9) gets one in the pre-selected sandbox
    mode, not confirmed, so there is always a row to lock. A loan without a valid UID has none.
    """
    if not is_swiss_loan(loan):
        return None
    uid = normalized_uid(loan_borrower_uid(loan))
    if not uid:
        return None
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
            financing_creditors=0, borrower_creditors=len(borrower_creditor_ids(uid))
        )
    if not result.ok:
        raise CreditorRegimeViolation(result.message)


def check_before_close(loan: Model, *, on: date) -> None:
    """Before a funding close (F08): a failure stops the close; an admin decides."""
    if not is_swiss_loan(loan):
        return
    uid = loan_borrower_uid(loan)
    regime = regime_for_uid(uid)
    mode = str(regime.mode) if regime is not None else rules.MODE_SANDBOX
    if mode == rules.MODE_SANDBOX:
        result = rules.check_sandbox_total(borrower_total_chf_minor(uid, on=on, include_loan=loan))
    else:
        financing = loan_investor_ids([str(loan.pk)]).get(str(loan.pk), frozenset())
        result = rules.check_ten_twenty(
            financing_creditors=len(financing),
            borrower_creditors=len(borrower_creditor_ids(uid)),
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
