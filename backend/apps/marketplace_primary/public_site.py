# IP of Webby-Soft SRL.
"""Anonymous public site projections: projects, statistics and Loan Originators.

Owner decision 2026-10-15 (MKT-DEC-002 update in plan/09): the public site publishes the
design's project fields for every loan a visitor may see, without the borrower's legal or
display name, registration number, address or documents. The rules for "open", the
investor yield, the minimum investment and the repayment schedule are the investor
marketplace and servicing rules; this module only selects and shapes them.

Money is in integer minor units, business dates are Europe/Zurich.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.db.models import Model, Sum

from backend.apps.marketplace_primary.investor_limit import (
    loan_investor_ids,
    max_investors_for_borrower_country,
    swiss_borrower_max_investors,
)
from backend.apps.marketplace_primary.models import PrimaryLoanClose
from backend.apps.marketplace_primary.services import (
    MarketplacePrimaryValidationError,
    _assert_published_loan_open,
    _loan_minimum_investment_minor,
    _loan_remaining_capacity_minor,
    marketplace_payload_has_capacity,
)
from backend.apps.platform_core.domain.countries import country_code
from backend.apps.platform_core.domain.investor_limit import (
    InvestorLimit,
    new_investor_minimum_minor,
)
from backend.apps.platform_core.domain.time import business_date, now_utc

PUBLIC_PROJECTS_LIMIT_DEFAULT = 250
PUBLIC_PROJECTS_LIMIT_MAX = 500
PUBLIC_CURRENCIES = ("CHF", "EUR")

PUBLIC_STATUS_OPEN = "open"
PUBLIC_STATUS_FULLY_FUNDED = "fully_funded"
PUBLIC_STATUS_REPAYING = "repaying"
PUBLIC_STATUS_LATE = "late"
PUBLIC_STATUS_REPAID = "repaid"
PUBLIC_STATUS_DEFAULT = "default"
PUBLIC_STATUSES = (
    PUBLIC_STATUS_OPEN,
    PUBLIC_STATUS_FULLY_FUNDED,
    PUBLIC_STATUS_REPAYING,
    PUBLIC_STATUS_LATE,
    PUBLIC_STATUS_REPAID,
    PUBLIC_STATUS_DEFAULT,
)
# Funded loans: they carry a repayment record and count in the statistics.
FUNDED_PUBLIC_STATUSES = frozenset(
    {PUBLIC_STATUS_REPAYING, PUBLIC_STATUS_LATE, PUBLIC_STATUS_REPAID, PUBLIC_STATUS_DEFAULT}
)
# Drafts, cancelled rounds and failed funding closes are never public.
PUBLIC_LOAN_STATUSES = (
    "published",
    "funded",
    "active",
    "late",
    "defaulted",
    "written_off",
    "repaid",
)
_PUBLIC_STATUS_BY_LOAN_STATUS = {
    "funded": PUBLIC_STATUS_REPAYING,
    "active": PUBLIC_STATUS_REPAYING,
    "late": PUBLIC_STATUS_LATE,
    "defaulted": PUBLIC_STATUS_DEFAULT,
    "written_off": PUBLIC_STATUS_DEFAULT,
    "repaid": PUBLIC_STATUS_REPAID,
}
_DEFAULT_LOAN_STATUSES = frozenset({"defaulted", "written_off"})


class PublicProjectNotFoundError(MarketplacePrimaryValidationError):
    """The loan does not exist or is not shown on the public site."""


@dataclass(slots=True)
class _Project:
    loan: Any
    profile: Any | None
    payload: dict[str, Any]
    sort_key: tuple[Any, ...] = field(default_factory=tuple)


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _originator_services() -> Any:
    return import_module("backend.apps.originator_claims.services")


def _servicing_services() -> Any:
    return import_module("backend.apps.servicing.services")


def public_country_code(value: Any) -> str:
    """ISO 3166-1 alpha-2 code for a stored country value, or "" when unknown.

    Borrower and originator countries are free text in the admin forms ("Switzerland",
    "CH", ...); the Swiss-borrower investor limit reads them the same way.
    """
    return country_code(value)


def _round_half_up(numerator: int, denominator: int) -> int:
    return int((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("1"), ROUND_HALF_UP))


def _date_of(value: datetime | None) -> date | None:
    return business_date(value) if value is not None else None


def _originator_profile(loan: Any) -> Any | None:
    if str(loan.product_type) != "originator_claim":
        return None
    # Reverse one-to-one: a missing profile raises an AttributeError subclass.
    return getattr(loan, "originator_profile", None)


def _is_par_subscription(profile: Any) -> bool:
    return str(profile.distribution_model) == "par_component_v2"


def _candidate_loans(*, loan_id: str | None = None) -> list[Any]:
    loan_model = _model("loans", "Loan")
    queryset = loan_model.objects.filter(
        status__in=PUBLIC_LOAN_STATUSES,
        published_at__isnull=False,
    ).select_related(
        "borrower",
        "originator_profile__originator",
        "originator_profile__current_import",
        "originator_profile__funding_round_close",
    )
    if loan_id is not None:
        queryset = queryset.filter(id=loan_id)
    return list(queryset)


def _published_round_figures(loan: Any, profile: Any | None) -> dict[str, Any] | None:
    """Status and capacity of a loan still in its funding round (loan status "published").

    Open uses the investor marketplace rule: capacity left and the round still taking
    orders (deadline not passed; for a Loan Originator subscription also not on hold,
    originator active and the other checks of the investor marketplace projection).
    A round with nothing left to invest is fully funded. Any other published round (for
    example past its deadline with capacity left, waiting for the expiry resolution) is
    not shown until it closes or is cancelled.
    """
    if profile is None:
        try:
            _assert_published_loan_open(cast(Model, loan))
            taking_orders = True
        except MarketplacePrimaryValidationError:
            taking_orders = False
        remaining = max(0, _loan_remaining_capacity_minor(cast(Model, loan)))
        committed = int(loan.committed_principal_minor)
        if taking_orders and remaining > 0:
            return {
                "public_status": PUBLIC_STATUS_OPEN,
                "principal_minor": int(loan.principal_minor),
                "committed_principal_minor": committed,
                "remaining_capacity_minor": remaining,
            }
        if remaining == 0:
            return {
                "public_status": PUBLIC_STATUS_FULLY_FUNDED,
                "principal_minor": int(loan.principal_minor),
                "committed_principal_minor": committed,
                "remaining_capacity_minor": 0,
            }
        return None
    if not _is_par_subscription(profile):
        return None
    originator = _originator_services()
    try:
        payload = originator.originator_marketplace_payload(
            profile,
            include_detail=False,
            allow_closed=True,
        )
        remaining = max(0, _loan_remaining_capacity_minor(cast(Model, loan)))
    except (originator.OriginatorClaimsError, MarketplacePrimaryValidationError):
        return None
    committed = int(payload["committed_principal_minor"])
    if str(payload["status"]) == "published" and marketplace_payload_has_capacity(payload):
        # The amount offered to investors in this round: what is reserved plus what is
        # left (the retained skin-in-the-game share is not offered).
        offered = committed + int(payload["remaining_capacity_minor"])
        return {
            "public_status": PUBLIC_STATUS_OPEN,
            "principal_minor": offered,
            "committed_principal_minor": committed,
            "remaining_capacity_minor": int(payload["remaining_capacity_minor"]),
        }
    if remaining == 0 and committed > 0:
        return {
            "public_status": PUBLIC_STATUS_FULLY_FUNDED,
            "principal_minor": committed,
            "committed_principal_minor": committed,
            "remaining_capacity_minor": 0,
        }
    return None


def _funded_principal_minor(loan: Any, profile: Any | None, legacy_sold: dict[str, int]) -> int:
    """Principal investors funded on BANXUM, for a loan whose round has closed."""
    if profile is None:
        # A partial close lowers Loan.principal_minor to the accepted principal.
        return int(loan.principal_minor)
    if _is_par_subscription(profile):
        round_close = getattr(profile, "funding_round_close", None)
        if round_close is not None:
            return int(round_close.subscribed_principal_minor)
        # Reduced by investor principal repayments after activation; best effort only.
        return int(loan.committed_principal_minor)
    # Historical quoted claims: the principal sold to investors through claim purchases.
    return int(legacy_sold.get(str(loan.id), 0))


def _funded_at(loan: Any, profile: Any | None, direct_closes: dict[str, datetime]) -> date | None:
    if profile is None:
        closed_at = direct_closes.get(str(loan.id))
        # Loans funded before close records existed (seeded or migrated data) start on
        # their funding date.
        return _date_of(closed_at) if closed_at is not None else cast(date, loan.loan_start_date)
    if _is_par_subscription(profile):
        round_close = getattr(profile, "funding_round_close", None)
        if round_close is not None:
            return _date_of(round_close.closed_at)
        if profile.closed_at is not None:
            return _date_of(profile.closed_at)
        return cast(date | None, profile.funding_deadline)
    return _date_of(profile.closed_at) or _date_of(loan.published_at)


def _base_payload(loan: Any, profile: Any | None) -> dict[str, Any]:
    if profile is None:
        borrower = loan.borrower
        borrower_country = public_country_code(getattr(borrower, "country", ""))
        borrower_sector = (
            str(borrower.business_classification or "")
            if bool(borrower.business_classification_public)
            else ""
        )
        borrower_year_founded = (
            int(borrower.year_founded) if borrower.year_founded is not None else None
        )
        interest_rate_bps = int(loan.interest_rate_bps)
        originator_payload = None
        funding_deadline = loan.funding_deadline
        published_at = loan.published_at
    else:
        borrower_country = public_country_code(profile.borrower_country)
        borrower_sector = (
            str(profile.business_classification or "")
            if bool(profile.business_classification_public)
            else ""
        )
        borrower_year_founded = (
            int(profile.borrower_year_founded)
            if profile.borrower_year_founded is not None
            else None
        )
        # The investor-facing yield of the investor marketplace (participation applied).
        interest_rate_bps = int(profile.target_yield_bps)
        originator = profile.originator
        originator_payload = {
            "id": str(originator.id),
            "name": str(originator.public_name),
            "country": public_country_code(originator.jurisdiction),
        }
        funding_deadline = profile.funding_deadline or loan.funding_deadline
        published_at = loan.published_at or profile.published_at
    return {
        "loan_id": str(loan.id),
        "title": str(loan.title),
        "product_type": str(loan.product_type),
        "is_refinancing": bool(loan.is_refinancing),
        "currency": str(loan.currency_id),
        "interest_rate_bps": interest_rate_bps,
        "term_months": int(loan.term_months),
        "repayment_type": str(loan.repayment_type),
        "risk_rating": str(loan.risk_rating),
        "collateral_type": str(loan.collateral_type),
        "collateral_description": str(loan.collateral_description or ""),
        "ltv_bps": loan.ltv_bps,
        "purpose": str(loan.purpose),
        "purpose_description": str(loan.purpose_description or ""),
        "investor_summary": str(loan.investor_summary or ""),
        "borrower_country": borrower_country,
        "borrower_sector": borrower_sector,
        "borrower_year_founded": borrower_year_founded,
        "originator": originator_payload,
        "published_at": published_at,
        "funding_deadline": funding_deadline,
    }


def _project_sort_key(payload: dict[str, Any]) -> tuple[Any, ...]:
    """Open first (newest published first), then the rest (newest funding close first)."""
    published_at = payload["published_at"]
    published_rank = -published_at.timestamp() if published_at is not None else 0.0
    status = payload["public_status"]
    if status == PUBLIC_STATUS_OPEN:
        return (0, 0, published_rank, payload["loan_id"])
    if status == PUBLIC_STATUS_FULLY_FUNDED:
        # Still in its round, so newer than every closed round.
        return (1, 0, published_rank, payload["loan_id"])
    funded_at = payload["funded_at"]
    funded_rank = -funded_at.toordinal() if funded_at is not None else 0
    return (1, 1, funded_rank, published_rank, payload["loan_id"])


def _legacy_sold_principal(loans: list[Any]) -> dict[str, int]:
    legacy_ids = [
        str(loan.id)
        for loan in loans
        if (profile := _originator_profile(loan)) is not None and not _is_par_subscription(profile)
    ]
    if not legacy_ids:
        return {}
    holding_model = _model("holdings", "InvestorLoanHolding")
    return {
        str(row["loan_id"]): int(row["total"] or 0)
        for row in holding_model.objects.filter(
            loan_id__in=legacy_ids,
            source_type="originator_claim",
        )
        .values("loan_id")
        .annotate(total=Sum("original_principal_minor"))
    }


def _build_projects(loans: list[Any]) -> list[_Project]:
    """Public projects without the repayment record, in public order."""
    direct_closes = {
        str(loan_id): closed_at
        for loan_id, closed_at in PrimaryLoanClose.objects.filter(
            loan_id__in=[loan.id for loan in loans if loan.product_type == "direct"]
        )
        .order_by("loan_id", "closed_at")
        .values_list("loan_id", "closed_at")
    }
    legacy_sold = _legacy_sold_principal(loans)
    # One source of truth with the Swiss-borrower investor limit (MKT-DEC-028).
    investors_by_loan = loan_investor_ids([str(loan.id) for loan in loans])
    platform_investor_limit = swiss_borrower_max_investors()
    minimum_by_currency: dict[str, int] = {}
    projects: list[_Project] = []
    for loan in loans:
        profile = _originator_profile(loan)
        if str(loan.product_type) == "originator_claim" and profile is None:
            continue
        loan_status = str(loan.status)
        if loan_status == "published":
            figures = _published_round_figures(loan, profile)
            if figures is None:
                continue
            funded_at = None
        else:
            principal = _funded_principal_minor(loan, profile, legacy_sold)
            figures = {
                "public_status": _PUBLIC_STATUS_BY_LOAN_STATUS[loan_status],
                "principal_minor": principal,
                "committed_principal_minor": principal,
                "remaining_capacity_minor": 0,
            }
            funded_at = _funded_at(loan, profile, direct_closes)
        base_payload = _base_payload(loan, profile)
        investor_limit = InvestorLimit(
            max_investors=max_investors_for_borrower_country(
                base_payload["borrower_country"],
                platform_limit=platform_investor_limit,
            ),
            investor_ids=investors_by_loan.get(str(loan.id), frozenset()),
        )
        minimum: int | None = None
        if figures["public_status"] == PUBLIC_STATUS_OPEN:
            if profile is None:
                # The Direct minimum is a platform setting per currency: read it once.
                currency = str(loan.currency_id)
                if currency not in minimum_by_currency:
                    minimum_by_currency[currency] = _loan_minimum_investment_minor(
                        cast(Model, loan)
                    )
                loan_minimum = minimum_by_currency[currency]
            else:
                loan_minimum = _loan_minimum_investment_minor(cast(Model, loan))
            remaining = int(figures["remaining_capacity_minor"])
            if investor_limit.applies:
                # Swiss borrower: the minimum that lets the places left fill the loan;
                # null when no new investor can join (MKT-DEC-028).
                minimum = new_investor_minimum_minor(
                    minimum_minor=loan_minimum,
                    remaining_minor=remaining,
                    places_left=int(investor_limit.places_left or 0),
                )
            else:
                # What a new investor must invest now: the loan minimum, or the
                # remaining capacity when less than the minimum is left.
                minimum = min(loan_minimum, remaining)
        payload = {
            **base_payload,
            **figures,
            "minimum_investment_minor": minimum,
            "investors_count": investor_limit.investors_count,
            "max_investors": investor_limit.max_investors,
            "places_left": investor_limit.places_left,
            "funded_at": funded_at,
            "record": None,
        }
        projects.append(
            _Project(
                loan=loan,
                profile=profile,
                payload=payload,
                sort_key=_project_sort_key(payload),
            )
        )
    projects.sort(key=lambda project: project.sort_key)
    return projects


def _latest_public_notes(loan_ids: list[str]) -> dict[str, str]:
    """The latest public loan note text per loan (RISK-DEC-004 loan notes)."""
    notes: dict[str, str] = {}
    if not loan_ids:
        return notes
    note_model = _model("servicing", "LoanRiskNote")
    for loan_id, body in (
        note_model.objects.filter(loan_id__in=loan_ids, visibility="public")
        .order_by("loan_id", "-occurred_at", "-id")
        .values_list("loan_id", "body")
    ):
        notes.setdefault(str(loan_id), str(body or ""))
    return notes


def _defaulted_on_dates(loan_ids: list[str]) -> dict[str, date]:
    """Date of the latest change of each loan into default (defaulted or written off)."""
    result: dict[str, date] = {}
    if not loan_ids:
        return result
    event_model = _model("loans", "LoanEvent")
    for row in (
        event_model.objects.filter(loan_id__in=loan_ids, new_status__in=_DEFAULT_LOAN_STATUSES)
        .order_by("loan_id", "occurred_at", "id")
        .values("loan_id", "previous_status", "new_status", "occurred_at", "metadata")
    ):
        if str(row["previous_status"]) in _DEFAULT_LOAN_STATUSES:
            continue
        metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
        event_date: date | None = None
        as_of_value = metadata.get("as_of_date")
        if isinstance(as_of_value, str) and as_of_value:
            try:
                event_date = date.fromisoformat(as_of_value)
            except ValueError:
                event_date = None
        result[str(row["loan_id"])] = event_date or business_date(row["occurred_at"])
    return result


def _direct_records(projects: list[_Project], *, as_of_date: date) -> dict[str, dict[str, Any]]:
    """Record figures of Direct loans from the servicing repayment schedule snapshots."""
    if not projects:
        return {}
    schedules = _servicing_services().get_loan_repayment_schedule_snapshots(
        loans=[project.loan for project in projects],
        as_of_date=as_of_date,
    )
    records: dict[str, dict[str, Any]] = {}
    for project in projects:
        rows = schedules.get(str(project.loan.id), [])
        installment_numbers = {int(row.installment_number) for row in rows}
        unpaid_rows = [
            row for row in rows if row.row_type == "scheduled_installment" and not row.is_paid
        ]
        unpaid_numbers = {int(row.installment_number) for row in unpaid_rows}
        payments = [row for row in rows if row.row_type == "repayment_event"]
        records[str(project.loan.id)] = {
            "installments_total": len(installment_numbers),
            "installments_paid": len(installment_numbers - unpaid_numbers),
            "principal_repaid_minor": sum(int(row.paid_principal_minor) for row in payments),
            "interest_paid_minor": sum(int(row.paid_interest_minor) for row in payments),
            "days_past_due": max((int(row.days_past_due) for row in unpaid_rows), default=0),
        }
    return records


def _originator_records(projects: list[_Project], *, as_of_date: date) -> dict[str, dict[str, Any]]:
    """Record figures of Loan Originator claims: the investors' share and schedule.

    Installments are the rows of the current Loan Originator schedule after the investor
    entitlement boundary, with the paid/overdue status the investor schedule page uses.
    Repaid principal and paid interest are what investors received.
    """
    if not projects:
        return {}
    originator = _originator_services()
    line_model = _model("originator_claims", "InvestorOriginatorRepaymentDistributionLine")
    distributed = {
        str(row["holding__loan_id"]): (int(row["principal"] or 0), int(row["interest"] or 0))
        for row in line_model.objects.filter(
            holding__loan_id__in=[project.loan.id for project in projects]
        )
        .values("holding__loan_id")
        .annotate(principal=Sum("principal_minor"), interest=Sum("interest_minor"))
    }
    records: dict[str, dict[str, Any]] = {}
    for project in projects:
        profile = cast(Any, project.profile)
        loan = project.loan
        boundary: date | None = (
            profile.entitlement_start_date
            if _is_par_subscription(profile)
            else _date_of(loan.published_at)
        )
        rows = [
            row
            for row in originator.originator_portfolio_schedule_payload(
                profile, as_of_date=as_of_date
            )
            if row["row_type"] == "originator_schedule"
            and (boundary is None or row["due_date"] > boundary)
        ]
        unpaid_rows = [row for row in rows if not row["is_paid"]]
        principal_repaid, interest_paid = distributed.get(str(loan.id), (0, 0))
        records[str(loan.id)] = {
            "installments_total": len(rows),
            "installments_paid": len(rows) - len(unpaid_rows),
            "principal_repaid_minor": principal_repaid,
            "interest_paid_minor": interest_paid,
            "days_past_due": max((int(row["days_past_due"]) for row in unpaid_rows), default=0),
        }
    return records


def _attach_records(projects: list[_Project]) -> None:
    record_projects = [
        project
        for project in projects
        if project.payload["public_status"] in FUNDED_PUBLIC_STATUSES
    ]
    if not record_projects:
        return
    as_of_date = business_date(now_utc())
    records = _direct_records(
        [project for project in record_projects if project.profile is None],
        as_of_date=as_of_date,
    )
    records.update(
        _originator_records(
            [project for project in record_projects if project.profile is not None],
            as_of_date=as_of_date,
        )
    )
    loan_ids = [str(project.loan.id) for project in record_projects]
    notes = _latest_public_notes(loan_ids)
    defaulted_on = _defaulted_on_dates(
        [
            str(project.loan.id)
            for project in record_projects
            if project.payload["public_status"] == PUBLIC_STATUS_DEFAULT
        ]
    )
    for project in record_projects:
        loan_id = str(project.loan.id)
        figures = records.get(loan_id, {})
        status = project.payload["public_status"]
        principal_repaid = int(figures.get("principal_repaid_minor", 0))
        project.payload["record"] = {
            "installments_total": int(figures.get("installments_total", 0)),
            "installments_paid": int(figures.get("installments_paid", 0)),
            "principal_repaid_minor": principal_repaid,
            "interest_paid_minor": int(figures.get("interest_paid_minor", 0)),
            "outstanding_principal_minor": max(
                0, int(project.payload["principal_minor"]) - principal_repaid
            ),
            "days_past_due": (
                int(figures.get("days_past_due", 0))
                if status in {PUBLIC_STATUS_LATE, PUBLIC_STATUS_DEFAULT}
                else 0
            ),
            "defaulted_on": (
                defaulted_on.get(loan_id) if status == PUBLIC_STATUS_DEFAULT else None
            ),
            "public_note": notes.get(loan_id, ""),
        }


def _clean_limit(limit: int) -> int:
    return min(max(int(limit), 1), PUBLIC_PROJECTS_LIMIT_MAX)


def list_public_projects(*, limit: int = PUBLIC_PROJECTS_LIMIT_DEFAULT) -> list[dict[str, Any]]:
    """Every loan a visitor may see, as ``PublicProject`` payloads, in public order."""
    projects = _build_projects(_candidate_loans())[: _clean_limit(limit)]
    _attach_records(projects)
    return [project.payload for project in projects]


def get_public_project(*, loan_id: str) -> dict[str, Any]:
    projects = _build_projects(_candidate_loans(loan_id=loan_id))
    if not projects:
        raise PublicProjectNotFoundError("This project is not public.")
    _attach_records(projects)
    return projects[0].payload


def _public_originator_projects(projects: list[_Project]) -> dict[str, list[_Project]]:
    """Public claims per active Loan Originator."""
    by_originator: dict[str, list[_Project]] = defaultdict(list)
    for project in projects:
        if project.profile is None:
            continue
        if str(project.profile.originator.status) != "active":
            continue
        by_originator[str(project.profile.originator_id)].append(project)
    return by_originator


def get_public_statistics() -> dict[str, Any]:
    """Track record over every funded public loan, from the same data as the projects."""
    projects = _build_projects(_candidate_loans())
    _attach_records(projects)
    funded = [
        project.payload
        for project in projects
        if project.payload["public_status"] in FUNDED_PUBLIC_STATUSES
    ]
    currencies = list(PUBLIC_CURRENCIES) + sorted(
        {str(payload["currency"]) for payload in funded} - set(PUBLIC_CURRENCIES)
    )
    by_currency: dict[str, dict[str, Any]] = {
        currency: {
            "currency": currency,
            "loans": 0,
            "lent_minor": 0,
            "principal_repaid_minor": 0,
            "interest_paid_minor": 0,
            "outstanding_minor": 0,
            "defaulted_minor": 0,
        }
        for currency in currencies
    }
    weighted_rate = 0
    weight = 0
    for payload in funded:
        row = by_currency[str(payload["currency"])]
        record = payload["record"] or {}
        principal = int(payload["principal_minor"])
        outstanding = int(record.get("outstanding_principal_minor", 0))
        row["loans"] += 1
        row["lent_minor"] += principal
        row["principal_repaid_minor"] += int(record.get("principal_repaid_minor", 0))
        row["interest_paid_minor"] += int(record.get("interest_paid_minor", 0))
        if payload["public_status"] == PUBLIC_STATUS_DEFAULT:
            row["defaulted_minor"] += outstanding
        else:
            row["outstanding_minor"] += outstanding
        # Weighted by principal at face value across currencies, as the design shows it.
        weighted_rate += int(payload["interest_rate_bps"]) * principal
        weight += principal
    return {
        "as_of": now_utc(),
        "loans_funded": len(funded),
        "loans_repaid": sum(1 for p in funded if p["public_status"] == PUBLIC_STATUS_REPAID),
        "loans_late": sum(1 for p in funded if p["public_status"] == PUBLIC_STATUS_LATE),
        "loans_defaulted": sum(1 for p in funded if p["public_status"] == PUBLIC_STATUS_DEFAULT),
        "average_interest_rate_bps": _round_half_up(weighted_rate, weight) if weight else None,
        "originators_count": len(_public_originator_projects(projects)),
        "countries_count": len(
            {
                project.payload["borrower_country"]
                for project in projects
                if project.payload["borrower_country"]
            }
        ),
        "by_currency": [by_currency[currency] for currency in currencies],
    }


def list_public_originators() -> list[dict[str, Any]]:
    """Active Loan Originators with at least one public claim."""
    by_originator = _public_originator_projects(_build_projects(_candidate_loans()))
    originators: list[dict[str, Any]] = []
    for projects in by_originator.values():
        originator = cast(Any, projects[0].profile).originator
        originators.append(
            {
                "id": str(originator.id),
                "name": str(originator.public_name),
                "country": public_country_code(originator.jurisdiction),
                "partner_since": business_date(originator.created_at),
                "claims_funded": sum(
                    1
                    for project in projects
                    if project.payload["public_status"] in FUNDED_PUBLIC_STATUSES
                ),
            }
        )
    return sorted(originators, key=lambda row: (str(row["name"]).casefold(), str(row["id"])))
