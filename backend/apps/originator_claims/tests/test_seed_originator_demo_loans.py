from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from backend.apps.originator_claims.management.commands.seed_originator_demo_loans import (
    DEMO_ORIGINATOR_LOAN_SPECS,
    DEMO_ORIGINATOR_SPECS,
    SEED_NAME,
)
from backend.apps.originator_claims.models import (
    LoanOriginator,
    OriginatorLoanImport,
    OriginatorLoanProfile,
    OriginatorOpportunityStatus,
)
from backend.apps.originator_claims.services import list_open_originator_marketplace_payloads
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import Currency


def _superadmin() -> Any:
    return get_user_model().objects.create_superuser(
        email="originator-demo-admin@example.test",
        password="DemoAdmin123!",
        full_name="Originator Demo Admin",
    )


def _currencies() -> None:
    Currency.objects.update_or_create(
        code="CHF",
        defaults={"name": "Swiss franc", "minor_units": 2, "is_enabled": True},
    )
    Currency.objects.update_or_create(
        code="EUR",
        defaults={"name": "Euro", "minor_units": 2, "is_enabled": True},
    )


@pytest.mark.django_db
def test_seed_originator_demo_loans_publishes_varied_open_catalogue(settings: Any) -> None:
    actor = _superadmin()
    settings.GARANTA_SUPERADMIN_EMAIL = actor.email
    _currencies()

    call_command("seed_originator_demo_loans", verbosity=0)

    imports = list(
        OriginatorLoanImport.objects.select_related("loan", "loan__originator_profile")
        .filter(source_filename__startswith=f"{SEED_NAME}:")
        .order_by("source_filename")
    )
    profiles = [loan_import.loan.originator_profile for loan_import in imports]
    assert len(imports) == len(DEMO_ORIGINATOR_LOAN_SPECS) == 10
    assert (
        LoanOriginator.objects.filter(
            registration_number__startswith="BANXUM-QA-LO-"
        ).count()
        == len(DEMO_ORIGINATOR_SPECS)
    )
    assert {loan_import.currency_code for loan_import in imports} == {"CHF", "EUR"}
    assert len({profile.loan.repayment_type for profile in profiles}) == 5
    assert len({profile.target_yield_bps for profile in profiles}) == 10
    assert all(
        profile.opportunity_status == OriginatorOpportunityStatus.OPEN for profile in profiles
    )
    assert all(profile.loan.status == "active" for profile in profiles)
    assert all(profile.loan.borrower_id is None for profile in profiles)
    assert all(profile.target_yield_bps < profile.loan.interest_rate_bps for profile in profiles)
    assert all(
        profile.unsold_principal_minor == profile.current_outstanding_principal_minor
        for profile in profiles
    )
    assert all(
        profile.maturity_date > business_date(now_utc()) + timedelta(days=30)
        for profile in profiles
    )
    assert len(list_open_originator_marketplace_payloads(limit=100)) == 10


@pytest.mark.django_db
def test_seed_originator_demo_loans_is_idempotent(settings: Any) -> None:
    actor = _superadmin()
    settings.GARANTA_SUPERADMIN_EMAIL = actor.email
    _currencies()

    call_command("seed_originator_demo_loans", verbosity=0)
    first_ids = set(
        OriginatorLoanProfile.objects.filter(
            current_import__source_filename__startswith=f"{SEED_NAME}:"
        ).values_list("id", flat=True)
    )
    call_command("seed_originator_demo_loans", verbosity=0)
    second_ids = set(
        OriginatorLoanProfile.objects.filter(
            current_import__source_filename__startswith=f"{SEED_NAME}:"
        ).values_list("id", flat=True)
    )

    assert second_ids == first_ids
    assert len(second_ids) == 10


@pytest.mark.django_db
def test_seed_originator_demo_loans_requires_explicit_production_acknowledgement(
    settings: Any,
) -> None:
    settings.IS_PRODUCTION = True

    with pytest.raises(CommandError, match="--allow-production"):
        call_command("seed_originator_demo_loans", verbosity=0)
