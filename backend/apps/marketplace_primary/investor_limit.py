# IP of Webby-Soft SRL.
"""Investors of a loan and the Swiss-borrower investor limit (plan/09 MKT-DEC-028).

``loan_investor_ids`` is the one source of truth for the public ``investors_count`` and
for the Swiss-borrower limit. The rule itself (places left, minimum for a new investor)
is in ``backend.apps.platform_core.domain.investor_limit``. Other modules (Loan
Originator claims, secondary market) reach these selectors through ``import_module``.

A "Swiss borrower" loan is a Direct loan whose borrower entity country is Switzerland, or
a Loan Originator claim whose borrower country is Switzerland, in any spelling the admin
forms accept ("Switzerland", "CH", "Schweiz", "Suisse", ...).

Callers that enforce the limit hold the loan row lock (``select_for_update``) while they
count, so two new investors cannot both take the last place.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any, cast

from django.apps import apps
from django.db.models import Model

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryInvestmentOrderStatus,
)
from backend.apps.platform_core.domain.countries import is_switzerland
from backend.apps.platform_core.domain.investor_limit import (
    SWISS_BORROWER_MAX_INVESTORS_DEFAULT,
    SWISS_BORROWER_MAX_INVESTORS_SETTING,
    InvestorLimit,
)
from backend.apps.platform_core.selectors.settings import get_platform_setting_value

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


def swiss_borrower_max_investors() -> int:
    """The platform limit of investors per Swiss-borrower loan; 0 switches it off."""
    value = get_platform_setting_value(
        SWISS_BORROWER_MAX_INVESTORS_SETTING,
        SWISS_BORROWER_MAX_INVESTORS_DEFAULT,
    )
    if type(value) is int and value >= 0:
        return value
    return SWISS_BORROWER_MAX_INVESTORS_DEFAULT


def max_investors_for_borrower_country(
    borrower_country: Any,
    *,
    platform_limit: int | None = None,
) -> int | None:
    """The investor limit of a loan to a borrower in this country, or None."""
    if not is_switzerland(borrower_country):
        return None
    limit = swiss_borrower_max_investors() if platform_limit is None else platform_limit
    return limit if limit > 0 else None


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


def investor_limit(*, loan_id: str, borrower_country: Any) -> InvestorLimit:
    """The investor limit of one loan, with its investors when the limit applies."""
    max_investors = max_investors_for_borrower_country(borrower_country)
    if max_investors is None:
        return InvestorLimit(max_investors=None)
    investors = loan_investor_ids([str(loan_id)]).get(str(loan_id), frozenset())
    return InvestorLimit(max_investors=max_investors, investor_ids=investors)


def loan_investor_limit(loan: Model) -> InvestorLimit:
    return investor_limit(loan_id=str(loan.pk), borrower_country=loan_borrower_country(loan))


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
        "places_left": limit.places_left,
        "is_existing_investor": (
            limit.is_investor(viewer_user_id)
            if limit.applies and viewer_user_id is not None
            else None
        ),
    }
