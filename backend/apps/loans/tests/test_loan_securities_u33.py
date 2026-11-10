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
