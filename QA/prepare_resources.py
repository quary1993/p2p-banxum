"""Create local regression fixtures. Never connects to BANXUM or changes a database.

IP of Webby-Soft SRL.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

COLUMNS = (
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


def month(d: date, offset: int) -> date:
    index = d.year * 12 + d.month - 1 + offset
    year, m = divmod(index, 12)
    return date(year, m + 1, min(d.day, calendar.monthrange(year, m + 1)[1]))


def schedule(
    n: int,
    start: date,
    due: date,
    opening: int,
    principal: int,
    interest: int,
    penalty: int = 0,
    fee: int = 0,
) -> dict:
    return dict(
        row_type="schedule",
        installment_number=n,
        accrual_start_date=start,
        due_date=due,
        opening_principal_minor=opening,
        principal_minor=principal,
        interest_minor=interest,
        penalty_minor=penalty,
        fee_minor=fee,
        total_minor=principal + interest + penalty + fee,
        closing_principal_minor=opening - principal,
    )


def payment(
    reference: str,
    day: date,
    principal: int,
    interest: int,
    remaining: int,
    penalty: int = 0,
    fee: int = 0,
    kind: str = "regular",
) -> dict:
    return dict(
        row_type="payment",
        reference=reference,
        value_date=day,
        payment_type=kind,
        principal_minor=principal,
        interest_minor=interest,
        penalty_minor=penalty,
        fee_minor=fee,
        total_minor=principal + interest + penalty + fee,
        resulting_principal_minor=remaining,
    )


def csv_text(rows: list[dict], fields=COLUMNS) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date",
        required=True,
        type=date.fromisoformat,
        help="QA start date in Europe/Zurich, YYYY-MM-DD",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="A NEW folder; existing folders are never overwritten",
    )
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    good, bad = root / "valid", root / "invalid"
    good.mkdir()
    bad.mkdir()
    d0 = args.start_date
    boundary = d0 + timedelta(days=10)
    due2, due3 = month(boundary, 1), month(boundary, 2)
    rows = [
        schedule(1, month(boundary, -1), boundary, 1000000, 200000, 10000),
        schedule(2, boundary, due2, 800000, 400000, 8000),
        schedule(3, due2, due3, 400000, 400000, 4000),
    ]
    p1 = payment("QA-BOUNDARY-1", boundary, 200000, 10000, 800000)
    p2 = payment("QA-REGULAR-2", due2, 400000, 8000, 400000)
    p3 = payment("QA-FINAL-3", due3, 400000, 4000, 0)
    manifest = []

    def write(
        name,
        data,
        as_of,
        *,
        phase,
        expected="accept",
        note="",
        repayment_type="amortizing_principal_interest",
        io_months=0,
        boundary_principal=800000,
        reference="",
        prior="",
        skin=1000,
    ):
        destination = good if expected == "accept" else bad
        path = destination / name
        path.write_text(csv_text(data), encoding="utf-8")
        manifest.append(
            dict(
                file=str(path.relative_to(root)),
                expected=expected,
                phase=phase,
                as_of_date=str(as_of),
                payment_reference=reference,
                previous_file=prior,
                repayment_type=repayment_type,
                interest_only_months=io_months,
                original_principal_minor=1000000,
                coupon_bps=1200,
                interest_participation_bps=7000,
                penalty_participation_bps=5000,
                skin_bps=skin,
                minimum_investment_minor=100000,
                funding_deadline=str(d0 + timedelta(days=5)),
                boundary_date=str(boundary),
                post_boundary_principal_minor=boundary_principal,
                note=note,
            )
        )

    write("lo-a-01-publish.csv", rows, d0, phase="Create or replace DRAFT only")
    write(
        "lo-a-02-boundary-paid.csv",
        rows + [p1],
        boundary,
        phase="Repayment",
        reference=p1["reference"],
        prior="lo-a-01-publish.csv",
    )
    write(
        "lo-a-03-next-paid.csv",
        rows + [p1, p2],
        due2,
        phase="Repayment",
        reference=p2["reference"],
        prior="lo-a-02-boundary-paid.csv",
    )
    write(
        "lo-a-04-final-paid.csv",
        rows + [p1, p2, p3],
        due3,
        phase="Repayment",
        reference=p3["reference"],
        prior="lo-a-03-next-paid.csv",
    )

    # Alternative branch after the boundary, NOT after the normal second payment.
    advance_day = boundary + timedelta(days=15)
    accrued = int(
        (Decimal(8000) * 15 / Decimal((due2 - boundary).days)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    advance = payment(
        "QA-ADVANCE-1", advance_day, 100000, accrued, 700000, kind="repayment_in_advance"
    )
    remaining_interest = int(
        (
            Decimal(7000) * Decimal((due2 - advance_day).days) / Decimal((due2 - boundary).days)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    advance_rows = [
        rows[0],
        schedule(2, advance_day, due2, 700000, 350000, remaining_interest),
        schedule(3, due2, due3, 350000, 350000, 3500),
    ]
    write(
        "lo-a-05-advance-alternative.csv",
        advance_rows + [p1, advance],
        advance_day,
        phase="Repayment alternative branch",
        reference=advance["reference"],
        prior="lo-a-02-boundary-paid.csv",
        note=(
            "Use a separate copy or restore the snapshot after boundary payment. "
            "Do not apply after file 03."
        ),
    )

    waterfall_rows = [
        rows[0],
        {**rows[1], "penalty_minor": 2000, "fee_minor": 1000, "total_minor": 411000},
        rows[2],
    ]
    wp = payment("QA-WATERFALL-2", due2, 400000, 8000, 400000, penalty=2000, fee=1000)
    write(
        "lo-waterfall-01-publish.csv",
        waterfall_rows,
        d0,
        phase="Separate loan draft",
        note="Synthetic declared costs/penalty test only; not real contractual evidence.",
    )
    write(
        "lo-waterfall-02-boundary-paid.csv",
        waterfall_rows + [p1],
        boundary,
        phase="Repayment",
        reference=p1["reference"],
        prior="lo-waterfall-01-publish.csv",
    )
    write(
        "lo-waterfall-03-next-paid.csv",
        waterfall_rows + [p1, wp],
        due2,
        phase="Repayment",
        reference=wp["reference"],
        prior="lo-waterfall-02-boundary-paid.csv",
    )

    variant_specs = {
        "equal_installments": ([330022, 333322, 336656], [10000, 6699, 3367], 0),
        "bullet_periodic_interest": ([0, 0, 1000000], [10000, 10000, 10000], 0),
        "interest_only_then_bullet": ([0, 0, 1000000], [10000, 10000, 10000], 1),
        "interest_only_then_amortizing": ([0, 500000, 500000], [10000, 10000, 5000], 1),
    }
    for kind, (principals, interests, io_months) in variant_specs.items():
        variant_rows = []
        remaining = 1000000
        for i, (principal, interest) in enumerate(zip(principals, interests, strict=True), 1):
            variant_rows.append(
                schedule(
                    i,
                    month(boundary, i - 2),
                    month(boundary, i - 1),
                    remaining,
                    principal,
                    interest,
                )
            )
            remaining -= principal
        write(
            f"lo-type-{kind}.csv",
            variant_rows,
            d0,
            phase="Separate loan draft",
            repayment_type=kind,
            io_months=io_months,
            boundary_principal=1000000 - principals[0],
            skin=0,
            note=(
                "Import type coverage; no repayments attached. "
                "Main LO-A covers amortizing principal and interest."
            ),
        )

    write(
        "bad-total.csv",
        [{**rows[0], "total_minor": 210001}, *rows[1:]],
        d0,
        phase="Draft",
        expected="reject",
        note="Components do not sum to total.",
    )
    write(
        "bad-numbering.csv",
        [rows[0], {**rows[1], "installment_number": 1}, rows[2]],
        d0,
        phase="Draft",
        expected="reject",
        note="Duplicate installment number.",
    )
    write(
        "bad-opening-principal.csv",
        [
            rows[0],
            {**rows[1], "opening_principal_minor": 800001, "closing_principal_minor": 400001},
            rows[2],
        ],
        d0,
        phase="Draft",
        expected="reject",
        note="Principal continuity does not reconcile.",
    )
    write(
        "bad-future-payment.csv",
        rows + [p1],
        d0,
        phase="Draft",
        expected="reject",
        note="Claims a payment after the import as-of date.",
    )
    write(
        "bad-missing-history.csv",
        rows + [p2],
        due2,
        phase="Repayment",
        expected="reject",
        prior="lo-a-02-boundary-paid.csv",
        reference=p2["reference"],
        note="Drops previously recorded boundary receipt.",
    )
    write(
        "bad-duplicate-reference.csv",
        rows + [p1, p1],
        boundary,
        phase="Repayment",
        expected="reject",
        reference=p1["reference"],
        prior="lo-a-01-publish.csv",
        note="Repeated payment reference within one file.",
    )
    # Conservation passes, but the service must reject paying principal ahead of interest.
    shifted = [
        {**rows[0]},
        {
            **rows[1],
            "principal_minor": 408000,
            "interest_minor": 0,
            "closing_principal_minor": 392000,
        },
        schedule(3, due2, due3, 392000, 392000, 3920),
    ]
    wrong = payment("QA-WRONG-WATERFALL", due2, 408000, 0, 392000, kind="repayment_in_advance")
    write(
        "bad-principal-before-interest.csv",
        shifted + [p1, wrong],
        due2,
        phase="Repayment",
        expected="reject",
        prior="lo-a-02-boundary-paid.csv",
        reference=wrong["reference"],
        note="Parser-valid; service must reject skipped due interest.",
    )

    (root / "lo-import-map.csv").write_text(
        csv_text(manifest, tuple(manifest[0])), encoding="utf-8"
    )
    (root / "dates.json").write_text(
        json.dumps(
            {
                "start_date": str(d0),
                "direct_deadline": str(d0 + timedelta(days=2)),
                "direct_resolution_date": str(d0 + timedelta(days=3)),
                "lo_deadline": str(d0 + timedelta(days=5)),
                "lo_deadline_resolution": str(d0 + timedelta(days=6)),
                "lo_boundary": str(boundary),
                "lo_second_payment": str(due2),
                "lo_final_payment": str(due3),
                "lo_advance_date": str(advance_day),
                "lo_advance_interest_minor": accrued,
                "lo_advance_payment_minor": 100000 + accrued,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "RUN-DATES.md").write_text(
        "# Dates for this resource pack\n\n"
        f"Start on **{d0}** in Europe/Zurich. Do not upload a draft after its funding deadline.\n\n"
        f"- Direct draft deadline: {d0 + timedelta(days=2)}; "
        f"resolution: {d0 + timedelta(days=3)}.\n"
        f"- LO draft deadline: {d0 + timedelta(days=5)}; "
        f"deadline resolution: {d0 + timedelta(days=6)}.\n"
        f"- LO boundary receipt: {boundary}; next receipt: {due2}; final receipt: {due3}.\n"
        f"- Alternative advance receipt: {advance_day}; total minor units: {100000 + accrued}; "
        f"interest minor units: {accrued}.\n\n"
        "Use lo-import-map.csv for each file's exact form values, "
        "prerequisite file and expected outcome.\n"
        "The as-of date and bank value date must agree with the new payment row. "
        "Advance the QA clock first.\n"
        "Files in valid are website uploads. "
        "Files in invalid must be rejected in the stated phase.\n"
        "The map and dates files are reference sheets, not website imports.\n",
        encoding="utf-8",
    )
    print(f"Created {len(manifest)} LO files in {root}")


if __name__ == "__main__":
    main()
