from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from backend.apps.loans.domain.schedules import (
    ManualScheduleRow,
    ScheduleGenerationError,
    ScheduleInstallmentDraft,
    add_months,
    generate_bullet_schedule,
    generate_equal_installment_schedule,
    generate_equal_principal_schedule,
    generate_interest_only_then_amortizing_schedule,
    schedule_from_manual_rows,
)
from backend.apps.loans.models import (
    CollateralType,
    Loan,
    LoanEvent,
    LoanEventType,
    LoanInstallment,
    LoanProductType,
    LoanPurpose,
    LoanStatus,
    RepaymentType,
    RiskRating,
)
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.money import Money, normalize_currency
from backend.apps.platform_core.domain.payment_waterfall import PAYMENT_WATERFALL_VERSION
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class LoansError(ValueError):
    pass


class LoanAuthorizationError(LoansError):
    pass


class LoanValidationError(LoansError):
    pass


MIN_PRINCIPAL_MAJOR = 1_000
MAX_PRINCIPAL_MAJOR = 1_000_000_000
MIN_TERM_MONTHS = 1
MAX_TERM_MONTHS = 600
MAX_FUNDING_DEADLINE_DAYS = 60
MAX_PUBLISHABLE_FUNDING_DEADLINE_DAYS = 29
DEFAULT_FUNDING_DEADLINE_DAYS = MAX_PUBLISHABLE_FUNDING_DEADLINE_DAYS
MAX_RATE_BPS = 100_000
MAX_FEE_BPS = 10_000


@dataclass(frozen=True, slots=True)
class ManualScheduleRowCommand:
    due_date: date
    principal_minor: int
    interest_minor: int


@dataclass(frozen=True, slots=True)
class CreateLoanCommand:
    actor: Model
    borrower_id: str
    title: str
    investor_summary: str
    purpose: str
    principal_minor: int
    currency: str
    interest_rate_bps: int
    term_months: int
    repayment_type: str
    collateral_type: str
    collateral_value_minor: int
    risk_rating: str
    is_refinancing: bool = False
    original_principal_minor: int | None = None
    original_interest_rate_bps: int | None = None
    original_term_months: int | None = None
    original_repayment_type: str | None = None
    original_interest_only_months: int | None = None
    original_loan_start_date: date | None = None
    purpose_description: str = ""
    collateral_description: str = ""
    loan_start_date: date | None = None
    funding_deadline: date | None = None
    interest_only_months: int = 0
    borrower_success_fee_bps: int = 200
    lender_payment_fee_minor: int = 0
    default_penalty_interest_bps: int = 0
    recovery_fee_bps: int = 0
    minimum_subscription_bps: int = 5_000
    manual_schedule_rows: list[ManualScheduleRowCommand] | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class UpdateLoanCommand:
    actor: Model
    loan_id: str
    title: str | None = None
    investor_summary: str | None = None
    purpose: str | None = None
    purpose_description: str | None = None
    is_refinancing: bool | None = None
    original_principal_minor: int | None = None
    original_interest_rate_bps: int | None = None
    original_term_months: int | None = None
    original_repayment_type: str | None = None
    original_interest_only_months: int | None = None
    original_loan_start_date: date | None = None
    principal_minor: int | None = None
    interest_rate_bps: int | None = None
    term_months: int | None = None
    repayment_type: str | None = None
    collateral_type: str | None = None
    collateral_value_minor: int | None = None
    collateral_description: str | None = None
    risk_rating: str | None = None
    loan_start_date: date | None = None
    funding_deadline: date | None = None
    interest_only_months: int | None = None
    borrower_success_fee_bps: int | None = None
    lender_payment_fee_minor: int | None = None
    default_penalty_interest_bps: int | None = None
    recovery_fee_bps: int | None = None
    minimum_subscription_bps: int | None = None
    manual_schedule_rows: list[ManualScheduleRowCommand] | None = None
    investor_message: str = ""
    note: str = ""
    funding_close_adjustment: bool = False


@dataclass(frozen=True, slots=True)
class PublishLoanCommand:
    actor: Model
    loan_id: str
    pre_publication_paid_installment_numbers: list[int] | None = None
    note: str = ""


def _actor_account_type(actor: Model) -> str:
    return str(getattr(actor, "account_type", ""))


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise LoanAuthorizationError("Only an active admin can manage loans.")


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise LoanValidationError(f"{label} is required.")
    return cleaned


def _optional_clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


def _text_choice(enum_type: type, value: str, label: str) -> Any:
    try:
        return enum_type(value)
    except ValueError as exc:
        raise LoanValidationError(f"Invalid {label}: {value}") from exc


def _purpose(value: str) -> LoanPurpose:
    return cast(LoanPurpose, _text_choice(LoanPurpose, value, "loan purpose"))


def _collateral_type(value: str) -> CollateralType:
    return cast(CollateralType, _text_choice(CollateralType, value, "collateral type"))


def _repayment_type(value: str) -> RepaymentType:
    return cast(RepaymentType, _text_choice(RepaymentType, value, "repayment type"))


def _risk_rating(value: str) -> RiskRating:
    return cast(RiskRating, _text_choice(RiskRating, value, "risk rating"))


def _enabled_currency(currency_code: str) -> Currency:
    code = normalize_currency(currency_code)
    currency = Currency.objects.filter(code=code, is_enabled=True).first()
    if currency is None:
        raise LoanValidationError(f"Currency is not enabled: {code}")
    return currency


def _minor_limit(major_units: int, minor_units: int) -> int:
    return int(major_units * (10**minor_units))


def _validate_principal(principal_minor: int, currency: Currency) -> int:
    Money(principal_minor, currency.code)
    minimum = _minor_limit(MIN_PRINCIPAL_MAJOR, currency.minor_units)
    maximum = _minor_limit(MAX_PRINCIPAL_MAJOR, currency.minor_units)
    if principal_minor < minimum:
        raise LoanValidationError("Principal must be at least 1,000 in the loan currency.")
    if principal_minor > maximum:
        raise LoanValidationError("Principal must not exceed 1,000,000,000 in the loan currency.")
    return principal_minor


def _validate_term(term_months: int) -> int:
    if type(term_months) is not int or term_months < MIN_TERM_MONTHS:
        raise LoanValidationError("Term must be a positive number of months.")
    if term_months > MAX_TERM_MONTHS:
        raise LoanValidationError("Term must not exceed 600 months.")
    return term_months


def _validate_interest_only_months_for_repayment(
    *,
    repayment_type: RepaymentType,
    interest_only_months: int,
    term_months: int,
    label: str = "Interest-only months",
) -> int:
    if type(interest_only_months) is not int or interest_only_months < 0:
        raise LoanValidationError(f"{label} must be a non-negative integer.")
    if repayment_type in {
        RepaymentType.EQUAL_INSTALLMENTS,
        RepaymentType.AMORTIZING_PRINCIPAL_INTEREST,
        RepaymentType.BULLET_PERIODIC_INTEREST,
    }:
        if interest_only_months != 0:
            raise LoanValidationError(f"{label} are only valid for interest-only repayment types.")
        return 0
    if repayment_type == RepaymentType.INTEREST_ONLY_THEN_BULLET:
        return term_months - 1
    if interest_only_months <= 0 or interest_only_months >= term_months:
        raise LoanValidationError(f"{label} must be between 1 and term_months - 1.")
    return interest_only_months


def _validate_rate_bps(value: int, label: str, *, allow_zero: bool = False) -> int:
    if type(value) is not int:
        raise LoanValidationError(f"{label} must be an integer bps value.")
    if value < 0 or (value == 0 and not allow_zero):
        raise LoanValidationError(f"{label} must be positive.")
    if value > MAX_RATE_BPS:
        raise LoanValidationError(f"{label} is outside the allowed sanity range.")
    return value


def _validate_fee_bps(value: int, label: str) -> int:
    if type(value) is not int or value < 0 or value > MAX_FEE_BPS:
        raise LoanValidationError(f"{label} must be between 0 and 10,000 bps.")
    return value


def _validate_minor_nonnegative(value: int, label: str) -> int:
    if type(value) is not int or value < 0:
        raise LoanValidationError(f"{label} must be a non-negative integer minor-unit amount.")
    return value


def _validate_original_principal(value: int | None, financeable_principal_minor: int) -> int:
    if value is None:
        raise LoanValidationError(
            "Original contractual principal is required for refinancing loans."
        )
    if type(value) is not int or value <= 0:
        raise LoanValidationError(
            "Original contractual principal must be a positive minor-unit amount."
        )
    if value < financeable_principal_minor:
        raise LoanValidationError(
            "Original contractual principal cannot be lower than the financeable principal."
        )
    return value


def _business_today() -> date:
    return business_date(now_utc())


def _resolve_funding_deadline(value: date | None) -> date:
    today = _business_today()
    deadline = value or today + timedelta(days=DEFAULT_FUNDING_DEADLINE_DAYS)
    if deadline < today:
        raise LoanValidationError("Funding deadline cannot be in the past.")
    if (deadline - today).days > MAX_FUNDING_DEADLINE_DAYS:
        raise LoanValidationError("Funding deadline cannot be more than 60 days from today.")
    return deadline


def _assert_publishable_funding_deadline(funding_deadline: date) -> None:
    today = _business_today()
    if funding_deadline < today:
        raise LoanValidationError(
            "Funding deadline must not be before today's Zurich business date "
            f"({today.isoformat()})."
        )
    latest_publishable = today + timedelta(days=MAX_PUBLISHABLE_FUNDING_DEADLINE_DAYS)
    if funding_deadline > latest_publishable:
        raise LoanValidationError(
            "Funding deadline is too far in the future for balance-funded publication. "
            f"Use a deadline no later than {latest_publishable.isoformat()} so investor "
            "funds pledged near the end of their 30-day investment window can still settle "
            "inside the 60-day operating limit."
        )


def _resolve_loan_start_date(value: date | None, funding_deadline: date) -> date:
    return value or funding_deadline


def _derive_first_payment_date(loan_start_date: date) -> date:
    return add_months(loan_start_date, 1)


def _validate_original_loan_terms(
    *,
    is_refinancing: bool,
    original_principal_minor: int | None,
    original_interest_rate_bps: int | None,
    original_term_months: int | None,
    original_repayment_type: str | None,
    original_interest_only_months: int | None,
    original_loan_start_date: date | None,
    principal_minor: int,
    loan_start_date: date,
) -> tuple[int, int | None, int | None, str, int | None, date | None]:
    original_repayment_type = original_repayment_type or None
    if not is_refinancing:
        if any(
            value is not None
            for value in (
                original_principal_minor,
                original_interest_rate_bps,
                original_term_months,
                original_repayment_type,
                original_interest_only_months,
                original_loan_start_date,
            )
        ):
            raise LoanValidationError("Original loan data is only allowed for refinancing loans.")
        return principal_minor, None, None, "", None, None
    original_principal = _validate_original_principal(original_principal_minor, principal_minor)
    if original_interest_rate_bps is None:
        raise LoanValidationError("Original interest rate is required for refinancing loans.")
    original_rate = _validate_rate_bps(original_interest_rate_bps, "Original interest rate")
    if original_term_months is None:
        raise LoanValidationError("Original term is required for refinancing loans.")
    original_term = _validate_term(original_term_months)
    if original_repayment_type is None:
        raise LoanValidationError("Original repayment type is required for refinancing loans.")
    original_repayment = _repayment_type(original_repayment_type)
    if original_interest_only_months is None:
        raise LoanValidationError(
            "Original interest-only months are required for refinancing loans."
        )
    original_interest_only = _validate_interest_only_months_for_repayment(
        repayment_type=original_repayment,
        interest_only_months=original_interest_only_months,
        term_months=original_term,
        label="Original interest-only months",
    )
    if original_loan_start_date is None:
        raise LoanValidationError("Original loan start date is required for refinancing loans.")
    if original_loan_start_date >= loan_start_date:
        raise LoanValidationError(
            "Original loan start date must be before the refinancing loan start date."
        )
    return (
        original_principal,
        original_rate,
        original_term,
        original_repayment,
        original_interest_only,
        original_loan_start_date,
    )


def _borrower_for_id(borrower_id: str) -> Model:
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    borrower = cast(Model | None, borrower_model.objects.filter(id=borrower_id).first())
    if borrower is None:
        raise LoanValidationError("Borrower entity does not exist.")
    return borrower


def _borrower_can_transact(borrower: Model) -> bool:
    return bool(getattr(borrower, "can_transact", False))


def _normalize_manual_rows(
    rows: list[ManualScheduleRowCommand] | None,
) -> list[ManualScheduleRow] | None:
    if rows is None:
        return None
    return [
        ManualScheduleRow(
            due_date=row.due_date,
            principal_minor=row.principal_minor,
            interest_minor=row.interest_minor,
        )
        for row in rows
    ]


def generate_schedule_for_terms(
    *,
    principal_minor: int,
    currency: str,
    term_months: int,
    annual_interest_bps: int,
    repayment_type: str,
    first_payment_date: date,
    interest_only_months: int,
    manual_schedule_rows: list[ManualScheduleRowCommand] | None = None,
) -> tuple[list[ScheduleInstallmentDraft], int]:
    manual_rows = _normalize_manual_rows(manual_schedule_rows)
    if manual_rows is not None:
        try:
            return (
                schedule_from_manual_rows(
                    principal_minor=principal_minor,
                    term_months=term_months,
                    rows=manual_rows,
                ),
                interest_only_months,
            )
        except ScheduleGenerationError as exc:
            raise LoanValidationError(str(exc)) from exc

    repayment = _repayment_type(repayment_type)
    effective_interest_only_months = _validate_interest_only_months_for_repayment(
        repayment_type=repayment,
        interest_only_months=interest_only_months,
        term_months=term_months,
    )

    try:
        if repayment == RepaymentType.EQUAL_INSTALLMENTS:
            return (
                generate_equal_installment_schedule(
                    principal_minor=principal_minor,
                    currency=currency,
                    term_months=term_months,
                    annual_interest_bps=annual_interest_bps,
                    first_due_date=first_payment_date,
                ),
                0,
            )
        if repayment == RepaymentType.AMORTIZING_PRINCIPAL_INTEREST:
            return (
                generate_equal_principal_schedule(
                    principal_minor=principal_minor,
                    currency=currency,
                    term_months=term_months,
                    annual_interest_bps=annual_interest_bps,
                    first_due_date=first_payment_date,
                ),
                0,
            )
        if repayment in {
            RepaymentType.BULLET_PERIODIC_INTEREST,
            RepaymentType.INTEREST_ONLY_THEN_BULLET,
        }:
            return (
                generate_bullet_schedule(
                    principal_minor=principal_minor,
                    currency=currency,
                    term_months=term_months,
                    annual_interest_bps=annual_interest_bps,
                    first_due_date=first_payment_date,
                ),
                effective_interest_only_months,
            )
        return (
            generate_interest_only_then_amortizing_schedule(
                principal_minor=principal_minor,
                currency=currency,
                term_months=term_months,
                annual_interest_bps=annual_interest_bps,
                first_due_date=first_payment_date,
                interest_only_months=effective_interest_only_months,
            ),
            effective_interest_only_months,
        )
    except ScheduleGenerationError as exc:
        raise LoanValidationError(str(exc)) from exc


def original_schedule_for_loan(loan: Loan) -> list[ScheduleInstallmentDraft]:
    """Informational schedule of the original (refinanced) loan.

    Computed on demand from the declared original loan terms. Never persisted and
    never used for servicing; it exists so admins and investors can see the history
    of a refinanced loan.
    """
    if not loan.is_refinancing:
        return []
    if (
        loan.original_interest_rate_bps is None
        or loan.original_term_months is None
        or not loan.original_repayment_type
        or loan.original_interest_only_months is None
        or loan.original_loan_start_date is None
    ):
        raise LoanValidationError("Refinancing loan is missing original loan terms.")
    schedule_rows, _ = generate_schedule_for_terms(
        principal_minor=loan.original_principal_minor,
        currency=loan.currency_id,
        term_months=loan.original_term_months,
        annual_interest_bps=loan.original_interest_rate_bps,
        repayment_type=loan.original_repayment_type,
        first_payment_date=_derive_first_payment_date(loan.original_loan_start_date),
        interest_only_months=loan.original_interest_only_months,
    )
    return schedule_rows


def default_pre_publication_paid_installments(
    schedule_rows: list[ScheduleInstallmentDraft],
) -> list[int]:
    today = _business_today()
    return [int(row.installment_number) for row in schedule_rows if row.due_date < today]


def original_schedule_payload(loan: Loan) -> list[dict[str, Any]]:
    schedule_rows = original_schedule_for_loan(loan)
    if loan.status == LoanStatus.DRAFT:
        paid_numbers = set(default_pre_publication_paid_installments(schedule_rows))
    else:
        paid_numbers = {
            int(value)
            for value in (loan.pre_publication_paid_installments or [])
            if isinstance(value, int)
        }
    outstanding = loan.original_principal_minor
    payload: list[dict[str, Any]] = []
    for row in schedule_rows:
        outstanding -= row.principal_minor
        payload.append(
            {
                "installment_number": row.installment_number,
                "due_date": row.due_date,
                "principal_minor": row.principal_minor,
                "interest_minor": row.interest_minor,
                "total_minor": row.total_minor,
                "outstanding_after_minor": outstanding,
                "paid_before_publication": int(row.installment_number) in paid_numbers,
            }
        )
    return payload


def _schedule_summary(schedule_rows: list[ScheduleInstallmentDraft]) -> dict[str, Any]:
    return {
        "installments": len(schedule_rows),
        "total_principal_minor": sum(row.principal_minor for row in schedule_rows),
        "total_interest_minor": sum(row.interest_minor for row in schedule_rows),
        "admin_overridden": any(row.admin_overridden for row in schedule_rows),
    }


def _write_schedule(
    *,
    loan: Loan,
    schedule_rows: list[ScheduleInstallmentDraft],
    schedule_version: int,
) -> None:
    LoanInstallment.objects.bulk_create(
        [
            LoanInstallment(
                loan=loan,
                schedule_version=schedule_version,
                installment_number=row.installment_number,
                due_date=row.due_date,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                total_minor=row.total_minor,
                admin_overridden=row.admin_overridden,
                metadata={},
            )
            for row in schedule_rows
        ]
    )


def _record_loan_event(
    *,
    loan: Loan,
    actor: Model,
    event_type: LoanEventType,
    previous_status: str = "",
    new_status: str = "",
    note: str = "",
    metadata: dict[str, Any] | None = None,
) -> LoanEvent:
    return cast(
        LoanEvent,
        LoanEvent.objects.create(
            loan=loan,
            event_type=event_type,
            actor_user_id=actor.pk,
            actor_account_type=_actor_account_type(actor),
            previous_status=previous_status,
            new_status=new_status,
            note=note.strip(),
            metadata=metadata or {},
        ),
    )


def _loan_metadata(
    loan: Loan,
    schedule_rows: list[ScheduleInstallmentDraft] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "borrower_id": str(loan.borrower_id),
        "status": loan.status,
        "is_refinancing": loan.is_refinancing,
        "original_principal_minor": loan.original_principal_minor,
        "original_interest_rate_bps": loan.original_interest_rate_bps,
        "original_term_months": loan.original_term_months,
        "original_loan_start_date": (
            loan.original_loan_start_date.isoformat() if loan.original_loan_start_date else None
        ),
        "principal_minor": loan.principal_minor,
        "currency": loan.currency_id,
        "interest_rate_bps": loan.interest_rate_bps,
        "term_months": loan.term_months,
        "repayment_type": loan.repayment_type,
        "risk_rating": loan.risk_rating,
        "minimum_subscription_bps": loan.minimum_subscription_bps,
        "ltv_bps": loan.ltv_bps,
        "ltv_warnings": loan.ltv_warnings,
        "loan_start_date": loan.loan_start_date.isoformat(),
        "first_payment_date": loan.first_payment_date.isoformat(),
        "schedule_version": loan.schedule_version,
        "pre_publication_paid_installments": list(loan.pre_publication_paid_installments),
    }
    if schedule_rows is not None:
        metadata["schedule"] = _schedule_summary(schedule_rows)
    return metadata


def _normalize_pre_publication_paid_installments(
    values: list[int] | None,
    *,
    schedule_rows: list[ScheduleInstallmentDraft],
) -> list[int]:
    if values is None:
        values = default_pre_publication_paid_installments(schedule_rows)
    cleaned: list[int] = []
    seen: set[int] = set()
    row_by_number = {int(row.installment_number): row for row in schedule_rows}
    today = _business_today()
    for value in values:
        if type(value) is not int or value <= 0:
            raise LoanValidationError("Pre-publication paid installments must be positive numbers.")
        if value in seen:
            continue
        row = row_by_number.get(value)
        if row is None:
            raise LoanValidationError("Pre-publication paid installment does not exist.")
        if row.due_date >= today:
            raise LoanValidationError(
                "Only installments with pay dates before today's Zurich business date can be "
                "marked paid before publication."
            )
        seen.add(value)
        cleaned.append(value)
    cleaned.sort()
    if cleaned and cleaned != list(range(1, cleaned[-1] + 1)):
        raise LoanValidationError(
            "Pre-publication paid installments must be a contiguous prefix of the schedule."
        )
    return cleaned


def _assert_current_schedule_complete(loan: Loan) -> None:
    installments = list(
        loan.installments.filter(schedule_version=loan.schedule_version).order_by(
            "installment_number"
        )
    )
    if len(installments) != loan.term_months:
        raise LoanValidationError("Loan repayment schedule is incomplete.")
    principal_sum = sum(installment.principal_minor for installment in installments)
    if principal_sum != loan.principal_minor:
        raise LoanValidationError(
            "Loan repayment schedule principal does not match the financeable principal."
        )


def _validate_publication_original_loan_state(
    loan: Loan,
    *,
    pre_publication_paid_installments: list[int] | None = None,
) -> tuple[list[int], dict[str, Any]]:
    if not loan.is_refinancing:
        if pre_publication_paid_installments:
            raise LoanValidationError(
                "Paid-before-publication installments are only valid for refinancing loans."
            )
        return [], {}
    schedule_rows = original_schedule_for_loan(loan)
    paid_numbers = _normalize_pre_publication_paid_installments(
        pre_publication_paid_installments,
        schedule_rows=schedule_rows,
    )
    paid_set = set(paid_numbers)
    paid_principal = sum(
        row.principal_minor for row in schedule_rows if int(row.installment_number) in paid_set
    )
    remaining_principal = loan.original_principal_minor - paid_principal
    if loan.principal_minor > remaining_principal:
        raise LoanValidationError(
            "Financeable principal cannot exceed the remaining outstanding principal of the "
            "original loan schedule."
        )
    return paid_numbers, {
        "original_remaining_principal_minor": remaining_principal,
        "original_paid_principal_minor": paid_principal,
        "financeable_below_original_remaining": loan.principal_minor < remaining_principal,
    }


def _save_loan_totals_from_schedule(
    *,
    loan: Loan,
    schedule_rows: list[ScheduleInstallmentDraft],
) -> None:
    loan.total_scheduled_principal_minor = sum(row.principal_minor for row in schedule_rows)
    loan.total_scheduled_interest_minor = sum(row.interest_minor for row in schedule_rows)


@transaction.atomic
def create_loan(command: CreateLoanCommand) -> Loan:
    _require_admin_actor(command.actor)
    borrower = _borrower_for_id(command.borrower_id)
    currency = _enabled_currency(command.currency)
    funding_deadline = _resolve_funding_deadline(command.funding_deadline)
    loan_start_date = _resolve_loan_start_date(command.loan_start_date, funding_deadline)
    first_payment_date = _derive_first_payment_date(loan_start_date)
    purpose = _purpose(command.purpose)
    collateral_type = _collateral_type(command.collateral_type)
    repayment_type = _repayment_type(command.repayment_type)
    risk_rating = _risk_rating(command.risk_rating)
    principal_minor = _validate_principal(command.principal_minor, currency)
    (
        original_principal_minor,
        original_interest_rate_bps,
        original_term_months,
        original_repayment_type,
        original_interest_only_months,
        original_loan_start_date,
    ) = _validate_original_loan_terms(
        is_refinancing=command.is_refinancing,
        original_principal_minor=command.original_principal_minor,
        original_interest_rate_bps=command.original_interest_rate_bps,
        original_term_months=command.original_term_months,
        original_repayment_type=command.original_repayment_type,
        original_interest_only_months=command.original_interest_only_months,
        original_loan_start_date=command.original_loan_start_date,
        principal_minor=principal_minor,
        loan_start_date=loan_start_date,
    )
    term_months = _validate_term(command.term_months)
    interest_rate_bps = _validate_rate_bps(command.interest_rate_bps, "Interest rate")
    collateral_value_minor = _validate_minor_nonnegative(
        command.collateral_value_minor,
        "Collateral value",
    )
    borrower_success_fee_bps = _validate_fee_bps(
        command.borrower_success_fee_bps,
        "Borrower success fee",
    )
    lender_payment_fee_minor = _validate_minor_nonnegative(
        command.lender_payment_fee_minor,
        "Lender payment fee",
    )
    default_penalty_interest_bps = _validate_rate_bps(
        command.default_penalty_interest_bps,
        "Default penalty interest",
        allow_zero=True,
    )
    recovery_fee_bps = _validate_fee_bps(command.recovery_fee_bps, "Recovery fee")
    minimum_subscription_bps = int(command.minimum_subscription_bps)
    if minimum_subscription_bps < 0 or minimum_subscription_bps > 10_000:
        raise LoanValidationError("Minimum subscription must be between 0% and 100%.")
    schedule_rows, effective_interest_only_months = generate_schedule_for_terms(
        principal_minor=principal_minor,
        currency=currency.code,
        term_months=term_months,
        annual_interest_bps=interest_rate_bps,
        repayment_type=repayment_type,
        first_payment_date=first_payment_date,
        interest_only_months=command.interest_only_months,
        manual_schedule_rows=command.manual_schedule_rows,
    )
    loan = Loan.objects.create(
        borrower=cast(Any, borrower),
        title=_clean_required(command.title, "Title"),
        investor_summary=_clean_required(command.investor_summary, "Investor summary"),
        purpose=purpose,
        purpose_description=command.purpose_description.strip(),
        is_refinancing=command.is_refinancing,
        original_principal_minor=original_principal_minor,
        original_interest_rate_bps=original_interest_rate_bps,
        original_term_months=original_term_months,
        original_repayment_type=original_repayment_type,
        original_interest_only_months=original_interest_only_months,
        original_loan_start_date=original_loan_start_date,
        principal_minor=principal_minor,
        currency=currency,
        interest_rate_bps=interest_rate_bps,
        term_months=term_months,
        repayment_type=repayment_type,
        interest_only_months=effective_interest_only_months,
        loan_start_date=loan_start_date,
        funding_deadline=funding_deadline,
        first_payment_date=first_payment_date,
        collateral_type=collateral_type,
        collateral_value_minor=collateral_value_minor,
        collateral_description=command.collateral_description.strip(),
        risk_rating=risk_rating,
        borrower_success_fee_bps=borrower_success_fee_bps,
        lender_payment_fee_minor=lender_payment_fee_minor,
        default_penalty_interest_bps=default_penalty_interest_bps,
        recovery_fee_bps=recovery_fee_bps,
        minimum_subscription_bps=minimum_subscription_bps,
        recovery_waterfall_version=PAYMENT_WATERFALL_VERSION,
        total_scheduled_principal_minor=sum(row.principal_minor for row in schedule_rows),
        total_scheduled_interest_minor=sum(row.interest_minor for row in schedule_rows),
        created_by_admin_id=command.actor.pk,
    )
    _write_schedule(loan=loan, schedule_rows=schedule_rows, schedule_version=loan.schedule_version)
    if loan.is_refinancing:
        # Fail fast if the declared original terms cannot produce an informational schedule.
        original_schedule_for_loan(loan)
    metadata = _loan_metadata(loan, schedule_rows)
    _record_loan_event(
        loan=loan,
        actor=command.actor,
        event_type=LoanEventType.CREATED,
        new_status=loan.status,
        note=command.note,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.created",
            target_type="Loan",
            target_id=str(loan.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanCreated",
            aggregate_type="Loan",
            aggregate_id=str(loan.id),
            payload=metadata,
            idempotency_key=f"loan:{loan.id}:created",
        )
    )
    return loan


def _post_commit_change_keys(command: UpdateLoanCommand) -> set[str]:
    values = {
        "title": command.title,
        "investor_summary": command.investor_summary,
        "purpose": command.purpose,
        "purpose_description": command.purpose_description,
        "is_refinancing": command.is_refinancing,
        "original_principal_minor": command.original_principal_minor,
        "original_interest_rate_bps": command.original_interest_rate_bps,
        "original_term_months": command.original_term_months,
        "original_repayment_type": command.original_repayment_type,
        "original_interest_only_months": command.original_interest_only_months,
        "original_loan_start_date": command.original_loan_start_date,
        "interest_rate_bps": command.interest_rate_bps,
        "term_months": command.term_months,
        "repayment_type": command.repayment_type,
        "collateral_type": command.collateral_type,
        "collateral_value_minor": command.collateral_value_minor,
        "collateral_description": command.collateral_description,
        "risk_rating": command.risk_rating,
        "loan_start_date": command.loan_start_date,
        "funding_deadline": command.funding_deadline,
        "interest_only_months": command.interest_only_months,
        "borrower_success_fee_bps": command.borrower_success_fee_bps,
        "lender_payment_fee_minor": command.lender_payment_fee_minor,
        "default_penalty_interest_bps": command.default_penalty_interest_bps,
        "recovery_fee_bps": command.recovery_fee_bps,
        "minimum_subscription_bps": command.minimum_subscription_bps,
        "manual_schedule_rows": command.manual_schedule_rows,
    }
    return {key for key, value in values.items() if value is not None}


def _set_if_changed(
    *,
    loan: Loan,
    field: str,
    value: Any,
    changes: dict[str, dict[str, str]],
) -> None:
    previous = getattr(loan, field)
    if previous != value:
        changes[field] = {"previous": str(previous or ""), "new": str(value or "")}
        setattr(loan, field, value)


@transaction.atomic
def update_loan(command: UpdateLoanCommand) -> Loan:
    _require_admin_actor(command.actor)
    loan = Loan.objects.select_for_update().filter(id=command.loan_id).first()
    if loan is None:
        raise LoanValidationError("Loan does not exist.")
    if loan.product_type != LoanProductType.DIRECT:
        raise LoanValidationError(
            "Loan Originator claims must be changed through the originator-claims workflow."
        )

    if (
        command.minimum_subscription_bps is not None
        and int(command.minimum_subscription_bps) != int(loan.minimum_subscription_bps)
        and loan.status != LoanStatus.DRAFT
    ):
        raise LoanValidationError(
            "Minimum subscription can only be changed while the loan is a draft."
        )

    if (
        command.principal_minor is not None
        and int(command.principal_minor) != int(loan.principal_minor)
        and loan.status != LoanStatus.DRAFT
        and not command.funding_close_adjustment
    ):
        raise LoanValidationError(
            "Financeable principal is frozen at publication and can only be reduced by "
            "deterministic funding close."
        )

    if loan.committed_principal_minor > 0:
        disallowed = _post_commit_change_keys(command)
        if disallowed:
            raise LoanValidationError(
                "Loan terms cannot be edited after committed investments exist."
            )
        if command.principal_minor is None:
            raise LoanValidationError("No allowed loan change was provided.")
        if command.principal_minor >= loan.principal_minor:
            raise LoanValidationError("Committed loan amount changes must lower the principal.")
        if command.principal_minor < loan.committed_principal_minor:
            raise LoanValidationError("Loan amount cannot be lower than committed investments.")
        if not command.investor_message.strip():
            raise LoanValidationError(
                "Investor message is required when lowering a committed loan."
            )

    changes: dict[str, dict[str, str]] = {}
    schedule_needs_regeneration = command.manual_schedule_rows is not None
    if command.title is not None:
        _set_if_changed(
            loan=loan,
            field="title",
            value=_clean_required(command.title, "Title"),
            changes=changes,
        )
    if command.investor_summary is not None:
        _set_if_changed(
            loan=loan,
            field="investor_summary",
            value=_clean_required(command.investor_summary, "Investor summary"),
            changes=changes,
        )
    if command.purpose is not None:
        _set_if_changed(
            loan=loan,
            field="purpose",
            value=_purpose(command.purpose),
            changes=changes,
        )
    optional_purpose = _optional_clean(command.purpose_description)
    if optional_purpose is not None:
        _set_if_changed(
            loan=loan,
            field="purpose_description",
            value=optional_purpose,
            changes=changes,
        )
    if command.principal_minor is not None:
        new_principal = _validate_principal(command.principal_minor, loan.currency)
        _set_if_changed(
            loan=loan,
            field="principal_minor",
            value=new_principal,
            changes=changes,
        )
        schedule_needs_regeneration = True
    if command.interest_rate_bps is not None:
        _set_if_changed(
            loan=loan,
            field="interest_rate_bps",
            value=_validate_rate_bps(command.interest_rate_bps, "Interest rate"),
            changes=changes,
        )
        schedule_needs_regeneration = True
    if command.term_months is not None:
        _set_if_changed(
            loan=loan,
            field="term_months",
            value=_validate_term(command.term_months),
            changes=changes,
        )
        schedule_needs_regeneration = True
    if command.repayment_type is not None:
        _set_if_changed(
            loan=loan,
            field="repayment_type",
            value=_repayment_type(command.repayment_type),
            changes=changes,
        )
        schedule_needs_regeneration = True
    if command.collateral_type is not None:
        _set_if_changed(
            loan=loan,
            field="collateral_type",
            value=_collateral_type(command.collateral_type),
            changes=changes,
        )
    if command.collateral_value_minor is not None:
        _set_if_changed(
            loan=loan,
            field="collateral_value_minor",
            value=_validate_minor_nonnegative(command.collateral_value_minor, "Collateral value"),
            changes=changes,
        )
    optional_collateral = _optional_clean(command.collateral_description)
    if optional_collateral is not None:
        _set_if_changed(
            loan=loan,
            field="collateral_description",
            value=optional_collateral,
            changes=changes,
        )
    if command.risk_rating is not None:
        _set_if_changed(
            loan=loan,
            field="risk_rating",
            value=_risk_rating(command.risk_rating),
            changes=changes,
        )
    funding_deadline = command.funding_deadline
    if funding_deadline is not None:
        _set_if_changed(
            loan=loan,
            field="funding_deadline",
            value=_resolve_funding_deadline(funding_deadline),
            changes=changes,
        )
    if command.loan_start_date is not None:
        _set_if_changed(
            loan=loan,
            field="loan_start_date",
            value=command.loan_start_date,
            changes=changes,
        )
        _set_if_changed(
            loan=loan,
            field="first_payment_date",
            value=_derive_first_payment_date(loan.loan_start_date),
            changes=changes,
        )
        schedule_needs_regeneration = True
    if command.interest_only_months is not None:
        _set_if_changed(
            loan=loan,
            field="interest_only_months",
            value=command.interest_only_months,
            changes=changes,
        )
        schedule_needs_regeneration = True
    if command.borrower_success_fee_bps is not None:
        _set_if_changed(
            loan=loan,
            field="borrower_success_fee_bps",
            value=_validate_fee_bps(command.borrower_success_fee_bps, "Borrower success fee"),
            changes=changes,
        )
    if command.lender_payment_fee_minor is not None:
        _set_if_changed(
            loan=loan,
            field="lender_payment_fee_minor",
            value=_validate_minor_nonnegative(
                command.lender_payment_fee_minor,
                "Lender payment fee",
            ),
            changes=changes,
        )
    if command.default_penalty_interest_bps is not None:
        _set_if_changed(
            loan=loan,
            field="default_penalty_interest_bps",
            value=_validate_rate_bps(
                command.default_penalty_interest_bps,
                "Default penalty interest",
                allow_zero=True,
            ),
            changes=changes,
        )
    if command.recovery_fee_bps is not None:
        _set_if_changed(
            loan=loan,
            field="recovery_fee_bps",
            value=_validate_fee_bps(command.recovery_fee_bps, "Recovery fee"),
            changes=changes,
        )
    if command.minimum_subscription_bps is not None:
        minimum_subscription_bps = int(command.minimum_subscription_bps)
        if minimum_subscription_bps < 0 or minimum_subscription_bps > 10_000:
            raise LoanValidationError("Minimum subscription must be between 0% and 100%.")
        _set_if_changed(
            loan=loan,
            field="minimum_subscription_bps",
            value=minimum_subscription_bps,
            changes=changes,
        )
    if command.is_refinancing is not None:
        _set_if_changed(
            loan=loan,
            field="is_refinancing",
            value=bool(command.is_refinancing),
            changes=changes,
        )
    if not loan.is_refinancing and any(
        value is not None
        for value in (
            command.original_principal_minor,
            command.original_interest_rate_bps,
            command.original_term_months,
            command.original_repayment_type,
            command.original_interest_only_months,
            command.original_loan_start_date,
        )
    ):
        raise LoanValidationError("Original loan data is only allowed for refinancing loans.")
    if loan.is_refinancing:
        for field, value in (
            ("original_principal_minor", command.original_principal_minor),
            ("original_interest_rate_bps", command.original_interest_rate_bps),
            ("original_term_months", command.original_term_months),
            ("original_repayment_type", command.original_repayment_type),
            ("original_interest_only_months", command.original_interest_only_months),
            ("original_loan_start_date", command.original_loan_start_date),
        ):
            if value is not None:
                _set_if_changed(loan=loan, field=field, value=value, changes=changes)
        (
            _original_principal,
            _original_rate,
            _original_term,
            original_repayment_type,
            original_interest_only_months,
            _original_start,
        ) = _validate_original_loan_terms(
            is_refinancing=True,
            original_principal_minor=loan.original_principal_minor,
            original_interest_rate_bps=loan.original_interest_rate_bps,
            original_term_months=loan.original_term_months,
            original_repayment_type=loan.original_repayment_type,
            original_interest_only_months=loan.original_interest_only_months,
            original_loan_start_date=loan.original_loan_start_date,
            principal_minor=loan.principal_minor,
            loan_start_date=loan.loan_start_date,
        )
        _set_if_changed(
            loan=loan,
            field="original_repayment_type",
            value=original_repayment_type,
            changes=changes,
        )
        _set_if_changed(
            loan=loan,
            field="original_interest_only_months",
            value=original_interest_only_months,
            changes=changes,
        )
        original_schedule_for_loan(loan)
    else:
        _set_if_changed(
            loan=loan,
            field="original_principal_minor",
            value=loan.principal_minor,
            changes=changes,
        )
        for cleared_field in (
            "original_interest_rate_bps",
            "original_term_months",
            "original_interest_only_months",
            "original_loan_start_date",
        ):
            _set_if_changed(loan=loan, field=cleared_field, value=None, changes=changes)
        _set_if_changed(loan=loan, field="original_repayment_type", value="", changes=changes)

    schedule_rows: list[ScheduleInstallmentDraft] | None = None
    if schedule_needs_regeneration:
        schedule_rows, effective_interest_only_months = generate_schedule_for_terms(
            principal_minor=loan.principal_minor,
            currency=loan.currency_id,
            term_months=loan.term_months,
            annual_interest_bps=loan.interest_rate_bps,
            repayment_type=loan.repayment_type,
            first_payment_date=loan.first_payment_date,
            interest_only_months=loan.interest_only_months,
            manual_schedule_rows=command.manual_schedule_rows,
        )
        _set_if_changed(
            loan=loan,
            field="interest_only_months",
            value=effective_interest_only_months,
            changes=changes,
        )
        loan.schedule_version += 1
        changes["schedule_version"] = {
            "previous": str(loan.schedule_version - 1),
            "new": str(loan.schedule_version),
        }
        _save_loan_totals_from_schedule(loan=loan, schedule_rows=schedule_rows)

    if not changes:
        raise LoanValidationError("No loan changes were provided.")

    loan.updated_by_admin_id = command.actor.pk
    loan.save()
    if schedule_rows is not None:
        _write_schedule(
            loan=loan,
            schedule_rows=schedule_rows,
            schedule_version=loan.schedule_version,
        )
    metadata = {
        "changes": changes,
        "investor_message": command.investor_message.strip(),
        **_loan_metadata(loan, schedule_rows),
    }
    loan_event = _record_loan_event(
        loan=loan,
        actor=command.actor,
        event_type=LoanEventType.UPDATED,
        previous_status=loan.status,
        new_status=loan.status,
        note=command.note,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.updated",
            target_type="Loan",
            target_id=str(loan.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanUpdated",
            aggregate_type="Loan",
            aggregate_id=str(loan.id),
            payload=metadata,
            idempotency_key=f"loan:{loan.id}:event:{loan_event.id}",
        )
    )
    return loan


@transaction.atomic
def publish_loan(command: PublishLoanCommand) -> Loan:
    _require_admin_actor(command.actor)
    loan = (
        Loan.objects.select_for_update(of=("self",))
        .select_related("borrower")
        .filter(id=command.loan_id)
        .first()
    )
    if loan is None:
        raise LoanValidationError("Loan does not exist.")
    if loan.product_type != LoanProductType.DIRECT:
        raise LoanValidationError(
            "Loan Originator claims must be published through the originator-claims workflow."
        )
    if loan.status != LoanStatus.DRAFT:
        raise LoanValidationError("Only draft loans can be published.")
    if not _borrower_can_transact(cast(Model, loan.borrower)):
        raise LoanValidationError("Borrower KYB must be approved and free of compliance hold.")
    if loan.funding_deadline is None:
        raise LoanValidationError("Direct loans require a funding deadline before publication.")
    _assert_publishable_funding_deadline(loan.funding_deadline)
    _assert_current_schedule_complete(loan)
    paid_installments, original_loan_state = _validate_publication_original_loan_state(
        loan,
        pre_publication_paid_installments=command.pre_publication_paid_installment_numbers,
    )

    previous_status = loan.status
    loan.status = LoanStatus.PUBLISHED
    loan.published_at = timezone.now()
    loan.pre_publication_paid_installments = paid_installments
    loan.updated_by_admin_id = command.actor.pk
    loan.save(
        update_fields=[
            "status",
            "published_at",
            "pre_publication_paid_installments",
            "updated_by_admin_id",
            "updated_at",
        ]
    )
    metadata = {**_loan_metadata(loan), **original_loan_state}
    _record_loan_event(
        loan=loan,
        actor=command.actor,
        event_type=LoanEventType.PUBLISHED,
        previous_status=previous_status,
        new_status=loan.status,
        note=command.note,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.published",
            target_type="Loan",
            target_id=str(loan.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanPublished",
            aggregate_type="Loan",
            aggregate_id=str(loan.id),
            payload=metadata,
            idempotency_key=f"loan:{loan.id}:published",
        )
    )
    import_module(
        "backend.apps.smart_invest.services"
    ).notify_smart_invest_matches_for_published_loan(
        loan_id=str(loan.id),
        product_type=LoanProductType.DIRECT,
    )
    return loan
