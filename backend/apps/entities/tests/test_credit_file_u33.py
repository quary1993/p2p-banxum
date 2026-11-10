"""IP of Webby-Soft SRL. U33-DEC-20: structured financial years, existing debt and the library."""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.db.models import Model
from django.test import Client

from backend.apps.entities.models import BorrowerDocumentType, BorrowerEntity
from backend.apps.entities.services import (
    AddBorrowerDocumentCommand,
    CreateBorrowerEntityCommand,
    add_borrower_document,
    borrower_investor_disclosure,
    create_borrower_entity,
)
from backend.apps.entities.tests.test_borrowers import _stored_file, admin_user, investor
from backend.apps.platform_core.models import AuditEvent
from backend.apps.platform_core.services.files import mark_file_scan_clean

__all__ = ["admin_user", "investor"]

pytestmark = pytest.mark.django_db

# 2025 in CHF thousands x 100 (minor units): the design's packaging company.
FULL_YEAR = {
    "revenue_minor": 11_800_000_00,
    "materials_costs_minor": 5_800_000_00,
    "staff_costs_minor": 2_770_000_00,
    "other_operating_costs_minor": 1_580_000_00,
    "depreciation_minor": 600_000_00,
    "operating_profit_minor": 1_050_000_00,
    "interest_expense_minor": 160_000_00,
    "profit_before_tax_minor": 890_000_00,
    "income_tax_minor": 210_000_00,
    "net_profit_minor": 680_000_00,
    "cash_minor": 980_000_00,
    "trade_receivables_minor": 1_650_000_00,
    "inventories_minor": 1_420_000_00,
    "other_current_assets_minor": 150_000_00,
    "current_assets_minor": 4_200_000_00,
    "property_plant_equipment_minor": 3_600_000_00,
    "other_non_current_assets_minor": 200_000_00,
    "total_assets_minor": 8_000_000_00,
    "current_financial_debt_minor": 830_000_00,
    "non_current_financial_debt_minor": 2_200_000_00,
    "financial_debt_minor": 3_030_000_00,
    "trade_payables_minor": 1_270_000_00,
    "other_operating_liabilities_minor": 340_000_00,
    "equity_minor": 3_360_000_00,
}


def _borrower(admin_user: Model) -> BorrowerEntity:
    return create_borrower_entity(
        CreateBorrowerEntityCommand(
            actor=admin_user, legal_name="Packaging Works AG", year_founded=2004, country="CH"
        )
    )


def _client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def _years_url(borrower: BorrowerEntity, row_id: str = "") -> str:
    base = f"/api/v1/entities/admin/borrowers/{borrower.pk}/financial-years/"
    return f"{base}{row_id}/" if row_id else base


def _save_year(user: Model, borrower: BorrowerEntity, year: int, amounts: dict[str, Any]) -> Any:
    return _client(user).post(
        _years_url(borrower),
        data={"year": year, "period_end": f"{year}-12-31", "currency": "CHF", "amounts": amounts},
        content_type="application/json",
    )


def test_a_full_financial_year_is_recorded_when_its_details_add_up(admin_user: Model) -> None:
    borrower = _borrower(admin_user)

    response = _save_year(admin_user, borrower, 2025, FULL_YEAR)

    assert response.status_code == 201, response.content
    assert response.json()["operating_profit_minor"] == 1_050_000_00
    totals_only = _save_year(
        admin_user,
        borrower,
        2024,
        {
            "revenue_minor": 11_200_000_00,
            "net_profit_minor": 590_000_00,
            "equity_minor": 3_040_000_00,
        },
    )
    assert totals_only.status_code == 201, totals_only.content
    listed = _client(admin_user).get(_years_url(borrower)).json()["financial_years"]
    assert [row["year"] for row in listed] == [2024, 2025]
    assert AuditEvent.objects.filter(action="borrower.financial_year_saved").count() == 2
    # The same year twice is refused.
    assert _save_year(admin_user, borrower, 2025, {"revenue_minor": 1}).status_code == 400


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"operating_profit_minor": 1_000_000_00}, "operating profit"),
        (
            {"profit_before_tax_minor": 800_000_00, "net_profit_minor": 590_000_00},
            "profit before tax",
        ),
        ({"net_profit_minor": 600_000_00}, "net profit"),
        ({"current_assets_minor": 4_100_000_00}, "current assets"),
        ({"total_assets_minor": 8_100_000_00}, "total assets"),
        ({"financial_debt_minor": 3_000_000_00}, "financial debt does not add up"),
        ({"trade_payables_minor": 1_200_000_00}, "total assets less equity"),
        ({"staff_costs_minor": -1}, "positive amounts"),
    ],
)
def test_figures_that_do_not_add_up_are_refused(
    admin_user: Model, change: dict[str, int], message: str
) -> None:
    borrower = _borrower(admin_user)

    response = _save_year(admin_user, borrower, 2025, {**FULL_YEAR, **change})

    assert response.status_code == 400, response.content
    assert message in response.json()["detail"]


def test_existing_debt_facilities_and_document_metadata(admin_user: Model, investor: Model) -> None:
    borrower = _borrower(admin_user)
    stored = _stored_file(admin_user, borrower_id=str(borrower.id))
    document = add_borrower_document(
        AddBorrowerDocumentCommand(
            actor=admin_user,
            borrower_id=str(borrower.id),
            stored_file_id=str(stored.id),
            document_type=BorrowerDocumentType.FINANCIALS,
            display_name="Annual financial statements 2025",
            investor_visible=True,
        )
    )
    mark_file_scan_clean(stored)
    client = _client(admin_user)
    url = f"/api/v1/entities/admin/borrowers/{borrower.pk}/debt-facilities/"

    created = client.post(
        url,
        data={
            "facility_type": "Property loan",
            "currency": "CHF",
            "balance_minor": 1_700_000_00,
            "current_portion_minor": 150_000_00,
            "security_description": "Mortgage on separate premises",
            "as_at": "2025-12-31",
            "source_document_id": str(document.id),
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    assert created.json()["non_current_portion_minor"] == 1_550_000_00
    too_much = client.post(
        url,
        data={
            "facility_type": "Overdraft",
            "currency": "CHF",
            "balance_minor": 100_00,
            "current_portion_minor": 200_00,
            "as_at": "2025-12-31",
        },
        content_type="application/json",
    )
    assert too_much.status_code == 400

    metadata = client.post(
        f"/api/v1/entities/admin/borrowers/{borrower.pk}/documents/{document.id}/metadata/",
        data={
            "category": "Financial statements",
            "document_date": "2026-04-15",
            "period_label": "FY 2025",
            "issuer": "Audit AG",
            "version": "1",
            "document_status": "Audited",
        },
        content_type="application/json",
    )
    assert metadata.status_code == 200, metadata.content
    [listed] = borrower_investor_disclosure(borrower)["documents"]
    assert (
        listed["category"],
        listed["period_label"],
        listed["issuer"],
        listed["document_status"],
    ) == (
        "Financial statements",
        "FY 2025",
        "Audit AG",
        "Audited",
    )
    # Only admins edit the credit file.
    assert _client(investor).post(url, data={}, content_type="application/json").status_code == 403
