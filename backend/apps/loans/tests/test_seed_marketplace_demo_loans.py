from __future__ import annotations

from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Model

from backend.apps.loans.management.commands.seed_marketplace_demo_loans import (
    DEMO_LOAN_SPECS,
    SEED_NAME,
)
from backend.apps.loans.models import Loan, LoanEvent, LoanEventType, LoanStatus


def _superadmin() -> Any:
    user_model: Any = get_user_model()
    return user_model.objects.create_superuser(
        email="demo-catalogue-admin@example.test",
        password="DemoAdmin123!",
        full_name="Demo Catalogue Admin",
    )


def _borrower(*, actor: Model, legal_name: str) -> Model:
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    return cast(
        Model,
        borrower_model.objects.create(
            legal_name=legal_name,
            year_founded=2017,
            kyb_status="approved",
            compliance_hold=False,
            country="Switzerland",
            created_by_admin_id=actor.pk,
        ),
    )


@pytest.mark.django_db
def test_seed_marketplace_demo_loans_publishes_varied_zero_percent_catalogue(
    settings: Any,
) -> None:
    actor = _superadmin()
    settings.GARANTA_SUPERADMIN_EMAIL = actor.email
    borrowers = {
        _borrower(actor=actor, legal_name="Demo Borrower Alpha AG").pk,
        _borrower(actor=actor, legal_name="Demo Borrower Beta AG").pk,
    }

    call_command("seed_marketplace_demo_loans", verbosity=0)

    loans = list(Loan.objects.filter(title__startswith="Demo - ").order_by("title"))
    assert len(loans) == len(DEMO_LOAN_SPECS) == 8
    assert {loan.borrower_id for loan in loans} == borrowers
    assert {loan.currency_id for loan in loans} == {"CHF", "EUR"}
    assert len({loan.interest_rate_bps for loan in loans}) == 8
    assert len({loan.term_months for loan in loans}) >= 6
    assert len({loan.repayment_type for loan in loans}) >= 4
    assert all(loan.status == LoanStatus.PUBLISHED for loan in loans)
    assert all(loan.committed_principal_minor == 0 for loan in loans)
    assert all(
        sum(
            row.principal_minor
            for row in loan.installments.filter(schedule_version=loan.schedule_version)
        )
        == loan.principal_minor
        for loan in loans
    )
    assert (
        LoanEvent.objects.filter(
            event_type=LoanEventType.CREATED,
            note__startswith=f"{SEED_NAME}:",
        ).count()
        == 8
    )


@pytest.mark.django_db
def test_seed_marketplace_demo_loans_is_idempotent(settings: Any) -> None:
    actor = _superadmin()
    settings.GARANTA_SUPERADMIN_EMAIL = actor.email
    _borrower(actor=actor, legal_name="Demo Borrower AG")

    call_command("seed_marketplace_demo_loans", verbosity=0)
    first_ids = set(Loan.objects.filter(title__startswith="Demo - ").values_list("id", flat=True))
    call_command("seed_marketplace_demo_loans", verbosity=0)
    second_ids = set(Loan.objects.filter(title__startswith="Demo - ").values_list("id", flat=True))

    assert second_ids == first_ids
    assert len(second_ids) == 8


@pytest.mark.django_db
def test_seed_marketplace_demo_loans_requires_explicit_production_acknowledgement(
    settings: Any,
) -> None:
    settings.IS_PRODUCTION = True

    with pytest.raises(CommandError, match="--allow-production"):
        call_command("seed_marketplace_demo_loans", verbosity=0)
