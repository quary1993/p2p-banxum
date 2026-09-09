"""Validate the manual test files using BANXUM services in pytest's test database.

IP of Webby-Soft SRL.
"""

import csv
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.apps.originator_claims.domain.imports import (
    OriginatorImportValidationError,
    parse_originator_import_csv,
)
from backend.apps.originator_claims.models import InvestorOriginatorRepaymentDistributionLine
from backend.apps.originator_claims.services import (
    OriginatorClaimsValidationError,
    RecordOriginatorBorrowerRepaymentCommand,
    record_originator_borrower_repayment,
)
from backend.apps.originator_claims.tests.test_originator_claims import (
    _allocate_par_subscription,
    _create_par_subscription_loan,
)

pytest_plugins = ["backend.apps.originator_claims.tests.test_originator_claims"]
ROOT = Path(__file__).resolve().parents[1] / "resources"
ROWS = list(csv.DictReader((ROOT / "lo-import-map.csv").open()))
BY_NAME = {Path(row["file"]).name: row for row in ROWS}


def parse(row):
    return parse_originator_import_csv(
        csv_content=(ROOT / row["file"]).read_text(),
        original_principal_minor=1000000,
        as_of_date=date.fromisoformat(row["as_of_date"]),
        repayment_type=row["repayment_type"],
        interest_only_months=int(row["interest_only_months"]),
    )


@pytest.mark.parametrize(
    "row", [r for r in ROWS if r["expected"] == "accept"], ids=lambda row: row["file"]
)
def test_valid_resource_parses(row):
    parsed = parse(row)
    assert parsed.schedule_rows


@pytest.mark.parametrize(
    "row",
    [r for r in ROWS if r["expected"] == "reject" and "before-interest" not in r["file"]],
    ids=lambda row: row["file"],
)
def test_invalid_resource_is_rejected_by_parser(row):
    with pytest.raises(OriginatorImportValidationError):
        parse(row)


@pytest.mark.django_db
@pytest.mark.parametrize("branch", ["main", "advance", "waterfall"])
def test_resource_repayments_match_manual(branch, admin_user, investor, other_investor):
    initial = "lo-waterfall-01-publish.csv" if branch == "waterfall" else "lo-a-01-publish.csv"
    today = date.fromisoformat(BY_NAME[initial]["as_of_date"])
    with patch(
        "backend.apps.originator_claims.tests.test_originator_claims._par_subscription_csv",
        return_value=(ROOT / "valid" / initial).read_text(),
    ):
        result = _create_par_subscription_loan(
            admin_user=admin_user, today=today, suffix=branch, skin_in_the_game_bps=1000
        )
    for user, amount in [(investor, 400000), (other_investor, 320000)]:
        _allocate_par_subscription(
            admin_user=admin_user,
            investor=user,
            loan=result.loan,
            today=today,
            amount_minor=amount,
            suffix=f"{branch}-{amount}",
        )
    result.loan.refresh_from_db()
    assert result.loan.status == "active"

    def command(name):
        row = BY_NAME[name]
        day = date.fromisoformat(row["as_of_date"])
        return RecordOriginatorBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=(ROOT / row["file"]).read_text(),
            source_filename=name,
            as_of_date=day,
            payment_reference=row["payment_reference"],
            booking_date=day,
            value_date=day,
            collection_account_identifier="QA-COLLECTION",
            payer_name="Synthetic QA borrower",
            bank_reference=f"QA-{branch}-{name}",
            bank_payment_reference=row["payment_reference"],
            evidence_reference="QA-TEST-EVIDENCE",
            notes="Test database only",
            idempotency_key=f"qa-resource-{branch}-{name}",
        )

    boundary_name = (
        "lo-waterfall-02-boundary-paid.csv"
        if branch == "waterfall"
        else "lo-a-02-boundary-paid.csv"
    )
    boundary = record_originator_borrower_repayment(command(boundary_name))
    assert boundary.investor_distributed_minor == 0
    assert boundary.originator_payable_minor == 210000

    if branch == "main":
        with pytest.raises(OriginatorClaimsValidationError, match="waterfall"):
            record_originator_borrower_repayment(command("bad-principal-before-interest.csv"))
        second = record_originator_borrower_repayment(command("lo-a-03-next-paid.csv"))
        assert second.investor_distributed_minor == 365040
        assert second.originator_payable_minor == 42960
        expected = {investor.pk: 202800, other_investor.pk: 162240}
        for line in InvestorOriginatorRepaymentDistributionLine.objects.filter(repayment=second):
            assert line.amount_minor == expected[line.investor_user_id]
        final = record_originator_borrower_repayment(command("lo-a-04-final-paid.csv"))
        assert final.originator_payable_minor == 41480
        assert final.investor_distributed_minor == 362520
    elif branch == "waterfall":
        receipt = record_originator_borrower_repayment(command("lo-waterfall-03-next-paid.csv"))
        assert receipt.platform_costs_minor == 1000
        assert receipt.originator_payable_minor == 44060
        assert receipt.investor_distributed_minor == 365940
    else:
        cmd = command("lo-a-05-advance-alternative.csv")
        receipt = record_originator_borrower_repayment(cmd)
        assert receipt.principal_minor == 100000
        result.profile.refresh_from_db()
        assert result.profile.current_outstanding_principal_minor == 700000
        assert record_originator_borrower_repayment(cmd).pk == receipt.pk
        with pytest.raises(OriginatorClaimsValidationError):
            record_originator_borrower_repayment(replace(cmd, notes="Conflicting replay"))
