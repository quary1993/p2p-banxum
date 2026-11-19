"""IP of Webby-Soft SRL. U33-DEC-21: several securities per loan, managed separately."""

from __future__ import annotations

import uuid
from importlib import import_module
from typing import Any, cast

import pytest
from django.db.models import Model
from django.test import Client

from backend.apps.loans.models import CollateralType, Loan, LoanSecurity
from backend.apps.loans.services import (
    LoanValidationError,
    PublishLoanCommand,
    UpdateLoanCommand,
    create_loan,
    publish_loan,
    update_loan,
)
from backend.apps.loans.tests.test_loans import _borrower, _loan_command, admin_user

__all__ = ["admin_user"]

pytestmark = pytest.mark.django_db


def _client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def _url(loan: Loan, security_id: str = "") -> str:
    base = f"/api/v1/loans/admin/loans/{loan.pk}/securities/"
    return f"{base}{security_id}/" if security_id else base


def _add(user: Model, loan: Loan, **data: Any) -> Any:
    return _client(user).post(_url(loan), data=data, content_type="application/json")


def test_the_loan_form_creates_and_edits_the_first_security(admin_user: Model) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))

    [first] = LoanSecurity.objects.filter(loan=loan)
    assert (first.position, first.security_type, first.value_minor) == (0, "real_estate", 2400_00)
    # Nothing is invented: rank, status and valuation details stay empty.
    assert (first.rank, first.status, first.valuation_date, first.appraiser) == (None, "", None, "")

    update_loan(
        UpdateLoanCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            collateral_value_minor=3000_00,
            collateral_description="Office building, Zug",
        )
    )
    first.refresh_from_db()
    assert (first.value_minor, first.description) == (3000_00, "Office building, Zug")


def test_several_securities_each_with_the_fields_that_apply(admin_user: Model) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    first = LoanSecurity.objects.get(loan=loan)

    changed = _client(admin_user).put(
        _url(loan, str(first.id)),
        data={
            "security_type": "real_estate",
            "description": "First-ranking mortgage note on the office building",
            "holder_name": "Zug Office AG",
            "rank": 2,
            "status": "in_place",
            "value_minor": 2600_00,
            "valuation_date": "2026-09-01",
            "valuation_source": "Independent appraisal",
            "appraiser": "Wüest Partner AG",
            "prior_ranking_debt_minor": 500_00,
            "insurance": "Building insurance, full value",
        },
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    guarantee = _add(
        admin_user,
        loan,
        security_type="personal_guarantee",
        holder_name="Main shareholder",
        status="in_place",
        undertaking_scope="Joint and several guarantee for principal and interest",
        undertaking_limit_minor=600_00,
    )
    assert guarantee.status_code == 201, guarantee.content
    assert guarantee.json()["position"] == 1
    assert guarantee.json()["is_guarantee"] is True

    listed = _client(admin_user).get(_url(loan)).json()["securities"]
    assert [item["security_type"] for item in listed] == ["real_estate", "personal_guarantee"]
    loan.refresh_from_db()
    # The first security gives the loan's summary; the guarantor's limit is never added to it.
    assert (loan.collateral_type, loan.collateral_value_minor) == ("real_estate", 2600_00)
    assert loan.collateral_description == "First-ranking mortgage note on the office building"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"security_type": "personal_guarantee", "value_minor": 100_00}, "not an asset value"),
        ({"security_type": "equipment", "undertaking_limit_minor": 100_00}, "guarantee only"),
        ({"security_type": "other"}, "Describe a security"),
        ({"security_type": "mixed_collateral"}, "on its own"),
        ({"security_type": "asset_backed"}, "on its own"),
        ({"security_type": "unsecured_exception"}, "not a security"),
        ({"security_type": "equipment", "prior_ranking_debt_minor": 10_00}, "value of the asset"),
        ({"security_type": "equipment", "document_ids": [str(uuid.uuid4())]}, "not a document"),
    ],
)
def test_wrong_security_data_is_refused(
    admin_user: Model, data: dict[str, Any], message: str
) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))

    response = _add(admin_user, loan, **data)

    assert response.status_code == 400, response.content
    assert message in response.json()["detail"]
    assert LoanSecurity.objects.filter(loan=loan).count() == 1


def test_a_wrong_security_is_removed_from_a_draft_only_and_a_loan_keeps_one(
    admin_user: Model,
) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    first = LoanSecurity.objects.get(loan=loan)
    extra = _add(admin_user, loan, security_type="equipment", value_minor=400_00).json()

    assert _client(admin_user).delete(_url(loan, str(first.id))).status_code == 204
    assert _client(admin_user).delete(_url(loan, extra["id"])).status_code == 400
    remaining = LoanSecurity.objects.get(loan=loan)
    assert (remaining.position, remaining.security_type) == (0, "equipment")
    loan.refresh_from_db()
    assert (loan.collateral_type, loan.collateral_value_minor) == ("equipment", 400_00)

    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    refused = _client(admin_user).delete(_url(loan, extra["id"]))
    assert refused.status_code == 400
    assert "released" in refused.json()["detail"]


def test_a_loan_whose_securities_are_all_released_is_not_published(admin_user: Model) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    LoanSecurity.objects.filter(loan=loan).update(status="released")

    with pytest.raises(LoanValidationError, match="collateral or guarantees"):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))


def test_investors_and_filters_see_every_security(admin_user: Model) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    _add(
        admin_user,
        loan,
        security_type="personal_guarantee",
        undertaking_scope="Guarantee of the owner",
        undertaking_limit_minor=600_00,
    )
    _add(admin_user, loan, security_type="equipment", value_minor=100_00, status="released")
    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    marketplace = import_module("backend.apps.marketplace_primary.services")

    preview = marketplace.public_marketplace_listing_payload(loan)
    detail = marketplace.full_marketplace_listing_payload(loan)

    # Released securities do not count for filters; investors still see them with their status.
    assert preview["security_types"] == ["real_estate", "personal_guarantee"]
    assert [(item["security_type"], item["status"]) for item in detail["securities"]] == [
        ("real_estate", ""),
        ("personal_guarantee", ""),
        ("equipment", "released"),
    ]
    smart_invest = import_module("backend.apps.smart_invest.services")
    criteria = {
        "minimum_yield_bps": None,
        "maximum_term_months": None,
        "originators": [],
        "collateral": ["personal_guarantee"],
        "maximum_ltv_bps": None,
        "currencies": [],
        "countries": [],
    }
    assert smart_invest.opportunity_matches_criteria(preview, criteria) is True
    assert (
        smart_invest.opportunity_matches_criteria(
            preview, {**criteria, "collateral": ["equipment"]}
        )
        is False
    )


def test_the_migration_copies_the_recorded_collateral_without_inventing_data(
    admin_user: Model,
) -> None:
    migration = import_module("backend.apps.loans.migrations.0022_loan_securities")
    secured = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    guaranteed = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    Loan.objects.filter(pk=guaranteed.pk).update(
        collateral_type=CollateralType.CORPORATE_GUARANTEE, collateral_value_minor=900_00
    )
    unsecured = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    Loan.objects.filter(pk=unsecured.pk).update(collateral_type=CollateralType.UNSECURED_EXCEPTION)

    rows = {row["loan_id"]: row for row in migration.plan_initial_securities(Loan)}

    assert rows[secured.pk]["value_minor"] == 2400_00
    assert rows[guaranteed.pk]["security_type"] == "corporate_guarantee"
    assert rows[guaranteed.pk]["value_minor"] is None
    assert unsecured.pk not in rows


def test_moving_changes_the_order_and_the_main_security_gives_the_summary(
    admin_user: Model,
) -> None:
    """C06: the order is for display; the admin chooses the main security; the loan's value (the
    loan-to-value basis) is the sum of the counted assets (F16)."""
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    extra = _add(admin_user, loan, security_type="equipment", value_minor=900_00).json()
    listed = _client(admin_user).get(_url(loan)).json()
    assert listed["borrower_documents"] == []
    assert [item["is_main"] for item in listed["securities"]] == [True, False]
    assert extra["counts_in_ltv"] is True
    loan.refresh_from_db()
    assert (loan.collateral_type, loan.collateral_value_minor) == ("real_estate", 3300_00)

    moved = _client(admin_user).post(
        f"{_url(loan, extra['id'])}move/", data={"direction": "up"}, content_type="application/json"
    )

    assert moved.status_code == 200, moved.content
    assert [item["security_type"] for item in moved.json()["securities"]] == [
        "equipment",
        "real_estate",
    ]
    loan.refresh_from_db()
    assert loan.collateral_type == "real_estate"
    main = _client(admin_user).post(f"{_url(loan, extra['id'])}main/")
    assert main.status_code == 200, main.content
    assert [item["is_main"] for item in main.json()["securities"]] == [True, False]
    loan.refresh_from_db()
    assert (loan.collateral_type, loan.collateral_value_minor) == ("equipment", 3300_00)
    again = _client(admin_user).post(
        f"{_url(loan, extra['id'])}move/", data={"direction": "up"}, content_type="application/json"
    )
    assert again.status_code == 400
    assert "already first" in again.json()["detail"]

    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    fixed = _client(admin_user).post(
        f"{_url(loan, extra['id'])}move/",
        data={"direction": "down"},
        content_type="application/json",
    )
    assert fixed.status_code == 400
    assert "fixed" in fixed.json()["detail"]



def test_ltv_assets_follow_the_type_the_flag_and_the_release(admin_user: Model) -> None:
    """F16: guarantees never count, receivables only when the admin says so, a valuation in another
    currency counts converted, excluding is not releasing, and the main security is not released
    while another one is in force."""
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    [real_estate] = LoanSecurity.objects.filter(loan=loan)
    guarantee = _add(
        admin_user, loan, security_type="personal_guarantee", holder_name="A. Owner",
        counts_in_ltv=True,
    )
    assert guarantee.status_code == 400
    assert "never counts" in guarantee.json()["detail"]
    receivables = _add(admin_user, loan, security_type="receivables", value_minor=500_00).json()
    assert receivables["counts_in_ltv"] is False
    euro_equipment = _add(
        admin_user,
        loan,
        security_type="equipment",
        valuation_currency="EUR",
        valuation_amount_minor=1000_00,
        valuation_fx_rate="0.95000000",
        valuation_fx_rate_date="2026-11-02",
    )
    assert euro_equipment.status_code == 201, euro_equipment.content
    assert euro_equipment.json()["value_minor"] == 950_00
    assert euro_equipment.json()["counts_in_ltv"] is True
    loan.refresh_from_db()
    assert loan.collateral_value_minor == 2400_00 + 950_00

    counted = _client(admin_user).put(
        _url(loan, receivables["id"]),
        data={"security_type": "receivables", "value_minor": 500_00, "counts_in_ltv": True},
        content_type="application/json",
    )
    assert counted.status_code == 200, counted.content
    loan.refresh_from_db()
    assert loan.collateral_value_minor == 2400_00 + 950_00 + 500_00
    excluded = _client(admin_user).put(
        _url(loan, euro_equipment.json()["id"]),
        data={
            "security_type": "equipment",
            "valuation_currency": "EUR",
            "valuation_amount_minor": 1000_00,
            "valuation_fx_rate": "0.95000000",
            "valuation_fx_rate_date": "2026-11-02",
            "counts_in_ltv": False,
        },
        content_type="application/json",
    )
    assert excluded.status_code == 200, excluded.content
    assert excluded.json()["status"] == ""
    loan.refresh_from_db()
    assert loan.collateral_value_minor == 2400_00 + 500_00
    release_main = _client(admin_user).put(
        _url(loan, str(real_estate.pk)),
        data={"security_type": "real_estate", "value_minor": 2400_00, "status": "released"},
        content_type="application/json",
    )
    assert release_main.status_code == 400
    assert "another main security" in release_main.json()["detail"]
    invoices = _add(admin_user, loan, security_type="invoices", value_minor=100_00)
    assert invoices.status_code == 400
    assert "Receivables" in invoices.json()["detail"]
    with pytest.raises(LoanValidationError, match="several securities"):
        update_loan(
            UpdateLoanCommand(
                actor=admin_user, loan_id=str(loan.pk), collateral_value_minor=1_00
            )
        )


def test_equal_principal_is_closed_for_new_direct_loans(admin_user: Model) -> None:
    """F14: "Amortizing principal and interest" is refused for a new loan or a change to it."""
    from dataclasses import replace

    command = _loan_command(admin_user, _borrower(admin_user))
    with pytest.raises(LoanValidationError, match="Equal principal repayments are closed"):
        create_loan(replace(command, repayment_type="amortizing_principal_interest"))
    loan = create_loan(command)
    with pytest.raises(LoanValidationError, match="Equal principal repayments are closed"):
        update_loan(
            UpdateLoanCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                repayment_type="amortizing_principal_interest",
            )
        )


def test_the_public_site_shows_the_anonymous_asset_name_of_the_main_security(
    admin_user: Model,
) -> None:
    """18.3: the admin's public asset name of the main security reaches the public project."""
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    [first] = LoanSecurity.objects.filter(loan=loan)
    response = _client(admin_user).put(
        _url(loan, str(first.pk)),
        data={
            "security_type": "real_estate",
            "value_minor": 2400_00,
            "public_name": "  Residential building in Biel  ",
        },
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["public_name"] == "Residential building in Biel"
    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    public = import_module("backend.apps.marketplace_primary.public_site")
    [project] = [
        item for item in public.list_public_projects() if item["loan_id"] == str(loan.pk)
    ]
    assert project["security_public_name"] == "Residential building in Biel"
