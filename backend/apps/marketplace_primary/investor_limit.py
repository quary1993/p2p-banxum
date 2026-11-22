# IP of Webby-Soft SRL.
"""Investors of a loan and the Swiss-borrower creditor limit (18.9; replaces MKT-DEC-028).

``loan_investor_ids`` is the one source of truth for the public ``investors_count`` and for the
creditor counts. The rule itself (places left, minimum for a new creditor) is in
``backend.apps.platform_core.domain.investor_limit``; the modes in
``backend.apps.platform_core.domain.creditor_regime``. Other modules (Loan Originator claims,
secondary market) reach these selectors through ``import_module``.

A "Swiss borrower" loan is a Direct loan whose borrower entity country is Switzerland, or a Loan
Originator claim whose borrower country is Switzerland, in any spelling the admin forms accept.
Its creditor mode is the one recorded for the borrower's UID (entities.SwissCreditorRegime);
sandbox when nothing is recorded yet.

Callers that enforce the limit hold the loan row lock (``select_for_update``) and the borrower's
regime row lock while they count, so two new creditors cannot both take the last place.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any, cast

from django.apps import apps
from django.db.models import Model, Q

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryInvestmentOrderStatus,
)
from backend.apps.platform_core.domain import creditor_regime as regime_rules
from backend.apps.platform_core.domain.countries import is_switzerland
from backend.apps.platform_core.domain.investor_limit import InvestorLimit

# Money allocated to a funding round that has not become a holding yet. Loan Originator
# subscriptions use the same primary orders.
_ROUND_ALLOCATION_STATUSES = (
    PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED,
    PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED,
)


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def loan_investor_ids(loan_ids: Iterable[str]) -> dict[str, frozenset[str]]:
    """Distinct investor accounts of each loan.

    An investor holds a current holding of the loan (any status but transferred), or has
    money allocated to its funding round (an allocated or partly allocated primary order,
    which also covers Loan Originator subscriptions). Orders closed as invested count only
    for a loan without any holding record (data funded before holdings were recorded);
    otherwise the holdings are the truth, so a holder who sold their whole holding on the
    secondary market no longer counts.
    """
    ids = sorted({str(loan_id) for loan_id in loan_ids})
    investors: dict[str, set[str]] = defaultdict(set)
    if not ids:
        return {}
    loans_with_holdings: set[str] = set()
    holding_model = _model("holdings", "InvestorLoanHolding")
    for loan_id, investor_id, status in (
        holding_model.objects.filter(loan_id__in=ids)
        .order_by()
        .values_list("loan_id", "investor_user_id", "status")
        .distinct()
    ):
        loans_with_holdings.add(str(loan_id))
        if str(status) != "transferred":
            investors[str(loan_id)].add(str(investor_id))
    for loan_id, investor_id, status in (
        PrimaryInvestmentOrder.objects.filter(
            loan_id__in=ids,
            status__in=(*_ROUND_ALLOCATION_STATUSES, PrimaryInvestmentOrderStatus.CLOSED_INVESTED),
        )
        .order_by()
        .values_list("loan_id", "investor_user_id", "status")
        .distinct()
    ):
        if (
            str(status) == PrimaryInvestmentOrderStatus.CLOSED_INVESTED
            and str(loan_id) in loans_with_holdings
        ):
            continue
        investors[str(loan_id)].add(str(investor_id))
    return {loan_id: frozenset(investors.get(loan_id, set())) for loan_id in ids}


# Loans of a borrower UID that count for the creditor modes (18.9). Audit S6-6: one shared
# set. "In funding" includes a failed close that keeps its reservations until it is resolved
# (closed again or cancelled); it counts like a published financing and blocks a mode change.
IN_FUNDING_LOAN_STATUSES = ("published", "funding_close_failed")
REGIME_LOAN_STATUSES = (*IN_FUNDING_LOAN_STATUSES, "funded", "active", "late", "defaulted")


def is_in_funding(loan: Any) -> bool:
    return str(loan.status) in IN_FUNDING_LOAN_STATUSES


def active_external_debts(uid: str, *, on: date) -> Any:
    """Audit S6-7: the external debts of the UID that run on ``on``: started on or before it and
    not ended (``ended_on`` is the first day without the debt: a debt ended on ``on`` no longer
    counts on ``on``)."""
    return (
        _model("entities", "BorrowerExternalDebt")
        .objects.filter(uid=uid, start_date__lte=on)
        .filter(Q(ended_on__isnull=True) | Q(ended_on__gt=on))
    )


def _today() -> date:
    from backend.apps.platform_core.domain.time import business_date, now_utc

    return business_date(now_utc())


def max_investors_for_borrower_country(
    borrower_country: Any,
    *,
    platform_limit: int | None = None,
) -> int | None:
    """The per-financing creditor limit that can apply to a borrower in this country, or None.

    18.9: only a Swiss borrower in 10/20 mode has a limit; callers use this to decide whether to
    count under locks (the mode itself is read per UID by ``loan_investor_limit``).
    """
    if not is_switzerland(borrower_country):
        return None
    return regime_rules.FINANCING_CREDITOR_LIMIT


def loan_borrower_country(loan: Model) -> str:
    """The free-text borrower country of a Direct loan or Loan Originator claim."""
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) == "originator_claim":
        profile_model = _model("originator_claims", "OriginatorLoanProfile")
        country = (
            profile_model.objects.filter(loan_id=loan_ref.pk)
            .values_list("borrower_country", flat=True)
            .first()
        )
        return str(country or "")
    if loan_ref.borrower_id is None:
        return ""
    return str(loan_ref.borrower.country or "")


def loan_borrower_uid(loan: Model) -> str:
    """The Swiss UID of the loan's borrower (entity UID, or the claim's borrower UID), as stored."""
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) == "originator_claim":
        profile_model = _model("originator_claims", "OriginatorLoanProfile")
        uid = (
            profile_model.objects.filter(loan_id=loan_ref.pk)
            .values_list("borrower_uid", flat=True)
            .first()
        )
        return str(uid or "")
    if loan_ref.borrower_id is None:
        return ""
    # Read from the database: a cached borrower on the loan instance may be older.
    uid = (
        _model("entities", "BorrowerEntity")
        .objects.filter(pk=loan_ref.borrower_id)
        .values_list("uid", flat=True)
        .first()
    )
    return str(uid or "")


def normalized_uid(uid: str) -> str:
    """The UID in its stored form, or "" when it is missing or not valid."""
    try:
        return regime_rules.normalize_uid(uid) if uid else ""
    except regime_rules.CreditorRegimeError:
        return ""


def regime_for_uid(uid: str, *, lock: bool = False) -> Any | None:
    """The recorded creditor regime of a UID (None: not recorded yet = pre-selected sandbox)."""
    uid = normalized_uid(uid)
    if not uid:
        return None
    model = _model("entities", "SwissCreditorRegime")
    queryset = model.objects.select_for_update() if lock else model.objects
    return queryset.filter(uid=uid).first()


def regime_mode_for_uid(uid: str) -> str:
    regime = regime_for_uid(uid)
    return str(regime.mode) if regime is not None else regime_rules.MODE_SANDBOX


def uid_loans(uid: str, *, exclude_loan_id: str | None = None) -> list[Any]:
    """Loans of the borrower UID in funding or running (Direct loans and Loan Originator claims)."""
    if not uid:
        return []
    loan_model = _model("loans", "Loan")
    profile_model = _model("originator_claims", "OriginatorLoanProfile")
    claim_loan_ids = list(
        profile_model.objects.filter(borrower_uid=uid).values_list("loan_id", flat=True)
    )
    queryset = loan_model.objects.filter(status__in=REGIME_LOAN_STATUSES).filter(
        Q(product_type="direct", borrower__uid=uid) | Q(id__in=claim_loan_ids)
    )
    if exclude_loan_id is not None:
        queryset = queryset.exclude(id=exclude_loan_id)
    return list(queryset.order_by("id"))


def borrower_creditor_ids(uid: str, *, on: date | None = None) -> frozenset[str]:
    """Relevant creditors of the borrower UID (F07): investors of its loans counted once, a Loan
    Originator while it keeps part of a claim, and external non-bank creditors whose debt runs
    on ``on`` (today by default)."""
    if not uid:
        return frozenset()
    on = on or _today()
    loans = uid_loans(uid)
    creditors: set[str] = set()
    for investors in loan_investor_ids([str(loan.pk) for loan in loans]).values():
        creditors.update(investors)
    profile_model = _model("originator_claims", "OriginatorLoanProfile")
    for originator_id in profile_model.objects.filter(
        loan_id__in=[loan.pk for loan in loans if str(loan.product_type) == "originator_claim"],
        unsold_principal_minor__gt=0,
    ).values_list("originator_id", flat=True):
        creditors.add(f"originator:{originator_id}")
    for identification in (
        active_external_debts(uid, on=on)
        .filter(creditor_is_bank=False)
        .values_list("creditor_identification", flat=True)
    ):
        creditors.add(f"external:{str(identification).strip().upper()}")
    return frozenset(creditors)


def is_creditor_in_other_financings(loan: Model, user_id: str) -> bool:
    """True when the user invests in another financing of the loan's borrower UID (resales)."""
    uid = normalized_uid(loan_borrower_uid(loan))
    if not uid:
        return False
    others = uid_loans(uid, exclude_loan_id=str(cast(Any, loan).pk))
    return any(
        str(user_id) in investors
        for investors in loan_investor_ids([str(other.pk) for other in others]).values()
    )


def financing_threshold_minor(loan: Model) -> int:
    """P of the dynamic minimum: the success threshold of the offer (0 for Loan Originator
    rounds, which have no minimum subscription threshold)."""
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) == "originator_claim":
        return 0
    principal = int(loan_ref.principal_minor)
    return -(-principal * int(loan_ref.minimum_subscription_bps) // 10_000)


def investor_limit(*, loan_id: str, borrower_country: Any) -> InvestorLimit:
    """The creditor limit of one loan, with its creditors when the limit applies."""
    if not is_switzerland(borrower_country):
        return InvestorLimit(max_investors=None)
    loan = _model("loans", "Loan").objects.select_related("borrower").filter(id=loan_id).first()
    if loan is None:
        return InvestorLimit(max_investors=None)
    return _limit_for_loan(cast(Model, loan))


def _limit_for_loan(loan: Model) -> InvestorLimit:
    uid = loan_borrower_uid(loan)
    mode = regime_mode_for_uid(uid)
    if mode != regime_rules.MODE_TEN_TWENTY:
        return InvestorLimit(max_investors=None, mode=mode)
    loan_ref = cast(Any, loan)
    investors = loan_investor_ids([str(loan_ref.pk)]).get(str(loan_ref.pk), frozenset())
    committed = (
        _model("loans", "Loan")
        .objects.filter(pk=loan_ref.pk)
        .values_list("committed_principal_minor", flat=True)
        .first()
    )
    return InvestorLimit(
        max_investors=regime_rules.FINANCING_CREDITOR_LIMIT,
        investor_ids=investors,
        borrower_creditor_ids=borrower_creditor_ids(uid),
        borrower_max_creditors=regime_rules.BORROWER_CREDITOR_LIMIT,
        threshold_minor=financing_threshold_minor(loan),
        allocated_minor=int(committed or 0),
        mode=mode,
    )


def loan_creditor_modes(loans: Iterable[Any]) -> dict[str, str]:
    """The creditor mode of each loan's borrower UID, read in three queries for a whole list.

    Lists (public site) use it to skip the per-loan limit for borrowers without a limit; a loan
    whose borrower has no valid UID gets the pre-selected sandbox mode.
    """
    loans = list(loans)
    claim_ids = [loan.pk for loan in loans if str(loan.product_type) == "originator_claim"]
    borrower_ids = {
        loan.borrower_id
        for loan in loans
        if str(loan.product_type) != "originator_claim" and loan.borrower_id is not None
    }
    claim_uids = dict(
        _model("originator_claims", "OriginatorLoanProfile")
        .objects.filter(loan_id__in=claim_ids)
        .values_list("loan_id", "borrower_uid")
    )
    entity_uids = dict(
        _model("entities", "BorrowerEntity")
        .objects.filter(pk__in=borrower_ids)
        .values_list("pk", "uid")
    )
    uid_by_loan: dict[str, str] = {}
    for loan in loans:
        raw = (
            claim_uids.get(loan.pk, "")
            if str(loan.product_type) == "originator_claim"
            else entity_uids.get(loan.borrower_id, "")
        )
        uid_by_loan[str(loan.pk)] = normalized_uid(str(raw or ""))
    modes = dict(
        _model("entities", "SwissCreditorRegime")
        .objects.filter(uid__in={uid for uid in uid_by_loan.values() if uid})
        .values_list("uid", "mode")
    )
    return {
        loan_id: str(modes.get(uid, regime_rules.MODE_SANDBOX))
        for loan_id, uid in uid_by_loan.items()
    }


def loan_investor_limit(loan: Model) -> InvestorLimit:
    if not is_switzerland(loan_borrower_country(loan)):
        return InvestorLimit(max_investors=None)
    return _limit_for_loan(loan)


def investor_limit_payload(
    limit: InvestorLimit,
    *,
    minimum_minor: int,
    remaining_minor: int,
    viewer_user_id: str | None = None,
) -> dict[str, Any]:
    """Investor marketplace fields of the limit.

    ``minimum_investment_minor`` is what the viewing investor must invest now: the
    minimum for a new investor, or the normal minimum (capped by the remaining capacity)
    when the viewer already invests in the loan. ``is_existing_investor`` is None when no
    limit applies or there is no viewer.
    """
    return {
        "minimum_investment_minor": limit.investor_minimum_minor(
            investor_user_id=viewer_user_id,
            minimum_minor=minimum_minor,
            remaining_minor=remaining_minor,
        ),
        "max_investors": limit.max_investors,
        "places_left": limit.places_left_for(viewer_user_id),
        "is_existing_investor": (
            limit.is_investor(viewer_user_id)
            if limit.applies and viewer_user_id is not None
            else None
        ),
    }
