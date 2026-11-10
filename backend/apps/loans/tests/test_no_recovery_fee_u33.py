"""IP of Webby-Soft SRL. U33-DEC-12: no Banxum recovery fee for investors on loans."""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model

from backend.apps.loans.models import Loan, LoanEvent
from backend.apps.loans.services import create_loan
from backend.apps.loans.tests.test_loans import _borrower, _loan_command, admin_user

__all__ = ["admin_user"]


@pytest.fixture
def loan(admin_user: Model) -> Loan:
    return create_loan(_loan_command(admin_user, _borrower(admin_user)))


@pytest.mark.django_db
def test_migration_sets_recovery_fees_to_zero_with_a_loan_event(
    admin_user: Model, loan: Loan
) -> None:
    migration = import_module("backend.apps.loans.migrations.0020_remove_investor_recovery_fee")
    Loan.objects.filter(pk=loan.pk).update(recovery_fee_bps=500)
    before = Loan.objects.get(pk=loan.pk)

    migration.remove_investor_recovery_fee(apps, None)

    after = Loan.objects.get(pk=loan.pk)
    assert after.recovery_fee_bps == 0
    assert after.updated_at == before.updated_at
    event = LoanEvent.objects.get(loan=loan, event_type="updated", actor_account_type="system")
    assert event.metadata["changes"]["recovery_fee_bps"] == {"previous": "500", "new": "0"}
    # Running it again changes nothing.
    migration.remove_investor_recovery_fee(apps, None)
    assert LoanEvent.objects.filter(loan=loan, actor_account_type="system").count() == 1


@pytest.mark.django_db
def test_loan_with_a_recovery_fee_is_refused(admin_user: Model, loan: Loan) -> None:
    services = import_module("backend.apps.loans.services")
    with pytest.raises(services.LoanValidationError, match="no recovery fee"):
        create_loan(replace(_loan_command(admin_user, _borrower(admin_user)), recovery_fee_bps=100))
    with pytest.raises(services.LoanValidationError, match="no recovery fee"):
        services.update_loan(
            services.UpdateLoanCommand(
                actor=cast(Any, admin_user), loan_id=str(loan.pk), recovery_fee_bps=100
            )
        )
