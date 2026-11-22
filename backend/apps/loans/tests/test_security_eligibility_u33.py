"""IP of Webby-Soft SRL. U33-DEC-38: every loan needs collateral or guarantees."""

from __future__ import annotations

from dataclasses import replace

import pytest
from django.db.models import Model

from backend.apps.loans.models import CollateralType, Loan
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


@pytest.mark.django_db
def test_a_new_loan_cannot_be_unsecured(admin_user: Model) -> None:
    command = _loan_command(admin_user, _borrower(admin_user))
    with pytest.raises(LoanValidationError, match="collateral or guarantees"):
        create_loan(replace(command, collateral_type=CollateralType.UNSECURED_EXCEPTION))
    assert not Loan.objects.exists()


@pytest.mark.django_db
def test_a_draft_cannot_become_unsecured_or_be_published_unsecured(admin_user: Model) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    with pytest.raises(LoanValidationError, match="collateral or guarantees"):
        update_loan(
            UpdateLoanCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                collateral_type=CollateralType.UNSECURED_EXCEPTION,
            )
        )
    # A draft that still carries the old exception (from before the rule) is not published.
    Loan.objects.filter(pk=loan.pk).update(collateral_type=CollateralType.UNSECURED_EXCEPTION)
    with pytest.raises(LoanValidationError, match="collateral or guarantees"):
        publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    loan.refresh_from_db()
    assert loan.status == "draft"
