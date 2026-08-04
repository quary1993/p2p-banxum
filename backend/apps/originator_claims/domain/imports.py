from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date


class OriginatorImportValidationError(ValueError):
    pass


CSV_COLUMNS = (
    "row_type",
    "reference",
    "installment_number",
    "accrual_start_date",
    "due_date",
    "value_date",
    "payment_type",
    "opening_principal_minor",
    "principal_minor",
    "interest_minor",
    "penalty_minor",
    "fee_minor",
    "total_minor",
    "closing_principal_minor",
    "resulting_principal_minor",
)
PAYMENT_TYPES = frozenset({"regular", "repayment_in_advance"})
REPAYMENT_TYPES = frozenset(
    {
        "equal_installments",
        "bullet_periodic_interest",
        "amortizing_principal_interest",
        "interest_only_then_bullet",
        "interest_only_then_amortizing",
    }
)


@dataclass(frozen=True)
class ParsedScheduleRow:
    installment_number: int
    accrual_start_date: date
    due_date: date
    opening_principal_minor: int
    principal_minor: int
    interest_minor: int
    penalty_minor: int
    fee_minor: int
    total_minor: int
    closing_principal_minor: int


@dataclass(frozen=True)
class ParsedPaymentRow:
    reference: str
    value_date: date
    payment_type: str
    principal_minor: int
    interest_minor: int
    penalty_minor: int
    fee_minor: int
    total_minor: int
    resulting_principal_minor: int


@dataclass(frozen=True)
class ParsedOriginatorImport:
    schedule_rows: tuple[ParsedScheduleRow, ...]
    payment_rows: tuple[ParsedPaymentRow, ...]
    current_outstanding_principal_minor: int
    maturity_date: date


def _required(value: str | None, *, row_number: int, field: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise OriginatorImportValidationError(f"Row {row_number}: {field} is required.")
    return cleaned


def _date(value: str | None, *, row_number: int, field: str) -> date:
    cleaned = _required(value, row_number=row_number, field=field)
    try:
        return date.fromisoformat(cleaned)
    except ValueError as exc:
        raise OriginatorImportValidationError(
            f"Row {row_number}: {field} must use YYYY-MM-DD."
        ) from exc


def _integer(
    value: str | None,
    *,
    row_number: int,
    field: str,
    positive: bool = False,
) -> int:
    cleaned = _required(value, row_number=row_number, field=field)
    if not cleaned.isascii() or not cleaned.isdigit():
        raise OriginatorImportValidationError(
            f"Row {row_number}: {field} must be a non-negative integer in minor units."
        )
    parsed = int(cleaned)
    if positive and parsed <= 0:
        raise OriginatorImportValidationError(f"Row {row_number}: {field} must be positive.")
    return parsed


def _assert_unused_blank(
    row: dict[str, str],
    fields: tuple[str, ...],
    *,
    row_number: int,
) -> None:
    populated = [field for field in fields if (row.get(field) or "").strip()]
    if populated:
        raise OriginatorImportValidationError(
            f"Row {row_number}: fields not applicable to this row must be blank: "
            + ", ".join(populated)
            + "."
        )


def parse_originator_import_csv(
    *,
    csv_content: str,
    original_principal_minor: int,
    as_of_date: date,
    repayment_type: str | None = None,
    interest_only_months: int = 0,
) -> ParsedOriginatorImport:
    if type(original_principal_minor) is not int or original_principal_minor <= 0:
        raise OriginatorImportValidationError("Original principal must be a positive integer.")
    if not csv_content.strip():
        raise OriginatorImportValidationError("CSV content is required.")
    if repayment_type is not None and repayment_type not in REPAYMENT_TYPES:
        raise OriginatorImportValidationError(f"Unsupported repayment_type {repayment_type}.")
    if type(interest_only_months) is not int or interest_only_months < 0:
        raise OriginatorImportValidationError(
            "interest_only_months must be a non-negative integer."
        )

    reader = csv.DictReader(io.StringIO(csv_content))
    if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
        raise OriginatorImportValidationError(
            "CSV header must exactly match: " + ",".join(CSV_COLUMNS)
        )

    schedules: list[ParsedScheduleRow] = []
    payments: list[ParsedPaymentRow] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise OriginatorImportValidationError(f"Row {row_number}: too many columns.")
        row_type = _required(row.get("row_type"), row_number=row_number, field="row_type")
        if row_type == "schedule":
            _assert_unused_blank(
                row,
                ("reference", "value_date", "payment_type", "resulting_principal_minor"),
                row_number=row_number,
            )
            schedule = ParsedScheduleRow(
                installment_number=_integer(
                    row.get("installment_number"),
                    row_number=row_number,
                    field="installment_number",
                    positive=True,
                ),
                accrual_start_date=_date(
                    row.get("accrual_start_date"),
                    row_number=row_number,
                    field="accrual_start_date",
                ),
                due_date=_date(row.get("due_date"), row_number=row_number, field="due_date"),
                opening_principal_minor=_integer(
                    row.get("opening_principal_minor"),
                    row_number=row_number,
                    field="opening_principal_minor",
                ),
                principal_minor=_integer(
                    row.get("principal_minor"), row_number=row_number, field="principal_minor"
                ),
                interest_minor=_integer(
                    row.get("interest_minor"), row_number=row_number, field="interest_minor"
                ),
                penalty_minor=_integer(
                    row.get("penalty_minor"), row_number=row_number, field="penalty_minor"
                ),
                fee_minor=_integer(row.get("fee_minor"), row_number=row_number, field="fee_minor"),
                total_minor=_integer(
                    row.get("total_minor"), row_number=row_number, field="total_minor"
                ),
                closing_principal_minor=_integer(
                    row.get("closing_principal_minor"),
                    row_number=row_number,
                    field="closing_principal_minor",
                ),
            )
            if schedule.accrual_start_date >= schedule.due_date:
                raise OriginatorImportValidationError(
                    f"Row {row_number}: accrual_start_date must precede due_date."
                )
            if (
                schedule.opening_principal_minor - schedule.principal_minor
                != schedule.closing_principal_minor
            ):
                raise OriginatorImportValidationError(
                    f"Row {row_number}: opening principal minus principal must equal "
                    "closing principal."
                )
            if (
                schedule.principal_minor
                + schedule.interest_minor
                + schedule.penalty_minor
                + schedule.fee_minor
                != schedule.total_minor
            ):
                raise OriginatorImportValidationError(
                    f"Row {row_number}: schedule components must equal total_minor."
                )
            schedules.append(schedule)
            continue

        if row_type == "payment":
            _assert_unused_blank(
                row,
                (
                    "installment_number",
                    "accrual_start_date",
                    "due_date",
                    "opening_principal_minor",
                    "closing_principal_minor",
                ),
                row_number=row_number,
            )
            payment_type = _required(
                row.get("payment_type"), row_number=row_number, field="payment_type"
            )
            if payment_type not in PAYMENT_TYPES:
                raise OriginatorImportValidationError(
                    f"Row {row_number}: unsupported payment_type {payment_type}."
                )
            payment = ParsedPaymentRow(
                reference=_required(row.get("reference"), row_number=row_number, field="reference"),
                value_date=_date(row.get("value_date"), row_number=row_number, field="value_date"),
                payment_type=payment_type,
                principal_minor=_integer(
                    row.get("principal_minor"), row_number=row_number, field="principal_minor"
                ),
                interest_minor=_integer(
                    row.get("interest_minor"), row_number=row_number, field="interest_minor"
                ),
                penalty_minor=_integer(
                    row.get("penalty_minor"), row_number=row_number, field="penalty_minor"
                ),
                fee_minor=_integer(row.get("fee_minor"), row_number=row_number, field="fee_minor"),
                total_minor=_integer(
                    row.get("total_minor"),
                    row_number=row_number,
                    field="total_minor",
                    positive=True,
                ),
                resulting_principal_minor=_integer(
                    row.get("resulting_principal_minor"),
                    row_number=row_number,
                    field="resulting_principal_minor",
                ),
            )
            if payment.value_date > as_of_date:
                raise OriginatorImportValidationError(
                    f"Row {row_number}: imported payment cannot be after as_of_date."
                )
            if (
                payment.principal_minor
                + payment.interest_minor
                + payment.penalty_minor
                + payment.fee_minor
                != payment.total_minor
            ):
                raise OriginatorImportValidationError(
                    f"Row {row_number}: payment components must equal total_minor."
                )
            payments.append(payment)
            continue

        raise OriginatorImportValidationError(
            f"Row {row_number}: row_type must be schedule or payment."
        )

    if not schedules:
        raise OriginatorImportValidationError("At least one schedule row is required.")
    schedules.sort(key=lambda item: item.installment_number)
    expected_numbers = list(range(1, len(schedules) + 1))
    if [row.installment_number for row in schedules] != expected_numbers:
        raise OriginatorImportValidationError(
            "Schedule installment numbers must be unique and consecutive from 1."
        )
    if any(
        left.due_date >= right.due_date
        for left, right in zip(schedules, schedules[1:], strict=False)
    ):
        raise OriginatorImportValidationError("Schedule due dates must be strictly increasing.")

    if repayment_type is not None:
        principal_pattern = [row.principal_minor for row in schedules]
        if repayment_type in {
            "bullet_periodic_interest",
            "interest_only_then_bullet",
        }:
            if any(principal_pattern[:-1]) or principal_pattern[-1] <= 0:
                raise OriginatorImportValidationError(
                    "Bullet schedules must repay all contractual principal in the final "
                    "installment only."
                )
        elif repayment_type == "interest_only_then_amortizing":
            if interest_only_months <= 0 or interest_only_months >= len(schedules):
                raise OriginatorImportValidationError(
                    "Interest-only then amortizing schedules require interest_only_months "
                    "between 1 and the number of schedule rows minus 1."
                )
            if any(principal_pattern[:interest_only_months]):
                raise OriginatorImportValidationError(
                    "Principal cannot be scheduled during the declared interest-only period."
                )
            if any(amount <= 0 for amount in principal_pattern[interest_only_months:]):
                raise OriginatorImportValidationError(
                    "Every amortizing installment after the interest-only period must repay "
                    "positive principal."
                )
        else:
            if interest_only_months != 0:
                raise OriginatorImportValidationError(
                    "interest_only_months must be zero for this repayment type."
                )
            if any(amount <= 0 for amount in principal_pattern):
                raise OriginatorImportValidationError(
                    "Equal-installment and amortizing schedules must repay positive principal "
                    "in every contractual installment."
                )

    payments.sort(key=lambda item: (item.value_date, item.reference))
    if len({payment.reference for payment in payments}) != len(payments):
        raise OriginatorImportValidationError("Payment references must be unique.")
    running_principal = original_principal_minor
    for payment in payments:
        if payment.principal_minor > running_principal:
            raise OriginatorImportValidationError(
                f"Payment {payment.reference}: principal exceeds outstanding principal."
            )
        running_principal -= payment.principal_minor
        if payment.resulting_principal_minor != running_principal:
            raise OriginatorImportValidationError(
                f"Payment {payment.reference}: resulting principal is inconsistent."
            )

    future_rows = [row for row in schedules if row.due_date > as_of_date]
    if running_principal > 0 and not future_rows:
        raise OriginatorImportValidationError(
            "An outstanding loan requires at least one future schedule row."
        )
    if sum(row.principal_minor for row in future_rows) != running_principal:
        raise OriginatorImportValidationError(
            "Future schedule principal must equal current outstanding principal."
        )
    if future_rows:
        expected_opening = running_principal
        for schedule_row in future_rows:
            if schedule_row.opening_principal_minor != expected_opening:
                raise OriginatorImportValidationError(
                    f"Installment {schedule_row.installment_number}: future opening principal is "
                    "inconsistent."
                )
            expected_opening = schedule_row.closing_principal_minor
        if expected_opening != 0:
            raise OriginatorImportValidationError(
                "Future schedule must amortize principal to zero."
            )

    return ParsedOriginatorImport(
        schedule_rows=tuple(schedules),
        payment_rows=tuple(payments),
        current_outstanding_principal_minor=running_principal,
        maturity_date=max(row.due_date for row in schedules),
    )
