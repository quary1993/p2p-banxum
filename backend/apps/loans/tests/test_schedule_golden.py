from __future__ import annotations

from datetime import date

import pytest

from backend.apps.loans.models import RepaymentType
from backend.apps.loans.services import generate_schedule_for_terms

ScheduleRow = tuple[str, int, int, int]


BULLET_GOLDEN: list[ScheduleRow] = [
    ("2026-01-31", 0, 83333, 83333),
    ("2026-02-28", 0, 83333, 83333),
    ("2026-03-31", 0, 83333, 83333),
    ("2026-04-30", 0, 83333, 83333),
    ("2026-05-31", 0, 83333, 83333),
    ("2026-06-30", 0, 83333, 83333),
    ("2026-07-31", 0, 83333, 83333),
    ("2026-08-31", 0, 83333, 83333),
    ("2026-09-30", 0, 83333, 83333),
    ("2026-10-31", 0, 83333, 83333),
    ("2026-11-30", 0, 83333, 83333),
    ("2026-12-31", 10000000, 83333, 10083333),
]


@pytest.mark.parametrize(
    ("repayment_type", "interest_only_months", "effective_interest_only_months", "expected"),
    [
        (
            RepaymentType.EQUAL_INSTALLMENTS,
            0,
            0,
            [
                ("2026-01-31", 795826, 83333, 879159),
                ("2026-02-28", 802458, 76701, 879159),
                ("2026-03-31", 809145, 70014, 879159),
                ("2026-04-30", 815888, 63271, 879159),
                ("2026-05-31", 822687, 56472, 879159),
                ("2026-06-30", 829542, 49617, 879159),
                ("2026-07-31", 836455, 42704, 879159),
                ("2026-08-31", 843426, 35733, 879159),
                ("2026-09-30", 850454, 28705, 879159),
                ("2026-10-31", 857541, 21618, 879159),
                ("2026-11-30", 864688, 14471, 879159),
                ("2026-12-31", 871890, 7266, 879156),
            ],
        ),
        (
            RepaymentType.AMORTIZING_PRINCIPAL_INTEREST,
            0,
            0,
            [
                ("2026-01-31", 833334, 83333, 916667),
                ("2026-02-28", 833334, 76389, 909723),
                ("2026-03-31", 833334, 69444, 902778),
                ("2026-04-30", 833334, 62500, 895834),
                ("2026-05-31", 833333, 55556, 888889),
                ("2026-06-30", 833333, 48611, 881944),
                ("2026-07-31", 833333, 41667, 875000),
                ("2026-08-31", 833333, 34722, 868055),
                ("2026-09-30", 833333, 27778, 861111),
                ("2026-10-31", 833333, 20833, 854166),
                ("2026-11-30", 833333, 13889, 847222),
                ("2026-12-31", 833333, 6944, 840277),
            ],
        ),
        (RepaymentType.BULLET_PERIODIC_INTEREST, 0, 0, BULLET_GOLDEN),
        (RepaymentType.INTEREST_ONLY_THEN_BULLET, 0, 11, BULLET_GOLDEN),
        (
            RepaymentType.INTEREST_ONLY_THEN_AMORTIZING,
            3,
            3,
            [
                ("2026-01-31", 0, 83333, 83333),
                ("2026-02-28", 0, 83333, 83333),
                ("2026-03-31", 0, 83333, 83333),
                ("2026-04-30", 1074587, 83333, 1157920),
                ("2026-05-30", 1083542, 74378, 1157920),
                ("2026-06-30", 1092571, 65349, 1157920),
                ("2026-07-30", 1101676, 56244, 1157920),
                ("2026-08-30", 1110856, 47064, 1157920),
                ("2026-09-30", 1120114, 37806, 1157920),
                ("2026-10-30", 1129448, 28472, 1157920),
                ("2026-11-30", 1138860, 19060, 1157920),
                ("2026-12-30", 1148346, 9570, 1157916),
            ],
        ),
    ],
)
def test_launch_repayment_type_schedule_golden_rows(
    repayment_type: str,
    interest_only_months: int,
    effective_interest_only_months: int,
    expected: list[ScheduleRow],
) -> None:
    rows, actual_effective_interest_only_months = generate_schedule_for_terms(
        principal_minor=100_000_00,
        currency="CHF",
        term_months=12,
        annual_interest_bps=1000,
        repayment_type=repayment_type,
        first_payment_date=date(2026, 1, 31),
        interest_only_months=interest_only_months,
    )

    assert actual_effective_interest_only_months == effective_interest_only_months
    assert [
        (row.due_date.isoformat(), row.principal_minor, row.interest_minor, row.total_minor)
        for row in rows
    ] == expected
    assert sum(row.principal_minor for row in rows) == 100_000_00
