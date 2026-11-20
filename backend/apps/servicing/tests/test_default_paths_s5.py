"""IP of Webby-Soft SRL. Audit step 5: the paths around a Default declaration.

S5-5: a loan on the 18.6 engine cannot enter the earlier recovery form (amounts typed by the
admin); its receipts go through the engine. S5-6: a Default cannot be cancelled once money was
recorded after it, on any path (engine or earlier payment, recovery receipt, expense, write-off,
Loan Originator repayment).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client

from backend.apps.servicing import engine
from backend.apps.servicing.models import LoanDefaultDeclaration, LoanRecoveryEvent
from backend.apps.servicing.services import ServicingValidationError
from backend.apps.servicing.tests.test_engine_servicing_186 import (  # noqa: F401
    _engine_loan,
    at,
    investors,
    superadmin,
)
from backend.apps.servicing.tests.test_servicing_duplicate_payments import (
    _defaulted,
    _recovery,
)
from backend.apps.servicing.tests.test_servicing_repayments import (  # noqa: F401
    _funded_loan_with_holdings,
    admin_user,
    investor_one,
    investor_two,
)

# The legacy part is written for the earlier schedule and the Late 5 / Default 16 thresholds.
pytestmark = pytest.mark.usefixtures("legacy_status_days", "pre_cutover_loans")


def _cancel(actor: Model, loan: Model) -> LoanDefaultDeclaration:
    return engine.cancel_loan_default(
        engine.CancelLoanDefaultCommand(
            actor=actor, loan_id=str(loan.pk), reason="Declared by mistake on this loan."
        )
    )


def _defaulted_engine_loan(admin: Model, holders: list[Model]) -> Model:
    loan = _engine_loan(admin, holders)
    with at(date(2027, 3, 19)):  # the 15 January row is 63 days late
        engine.declare_loan_default(
            engine.DeclareLoanDefaultCommand(actor=admin, loan_id=str(loan.pk))
        )
    return loan


@pytest.mark.django_db
def test_an_engine_loan_cannot_use_the_earlier_recovery_form(
    admin_user: Model,  # noqa: F811
    investors: list[Model],  # noqa: F811
) -> None:
    loan = _defaulted_engine_loan(admin_user, investors)
    client = Client()
    client.force_login(cast(Any, admin_user))

    with at(date(2027, 3, 25)):
        with pytest.raises(ServicingValidationError, match="18.6 interest engine"):
            _recovery(
                admin_user,
                loan,
                "engine-recovery",
                booking_date=date(2027, 3, 25),
                value_date=date(2027, 3, 25),
                penalties_due_minor=5_00,
            )
        response = client.post(
            "/api/v1/servicing/admin/recoveries/",
            data={
                "loan_id": str(loan.pk),
                "gross_recovered_minor": 1_000_00,
                "externally_deducted_costs_minor": 0,
                "third_party_costs_from_received_minor": 0,
                "recovery_fee_applied": False,
                "recovery_fee_bps": 0,
                "contractual_interest_due_minor": 0,
                "default_interest_due_minor": 0,
                "penalties_due_minor": 0,
                "booking_date": "2027-03-25",
                "value_date": "2027-03-25",
                "collection_account_identifier": "CH00GARANTARECOVERY",
                "payer_name": "Recovery counsel",
                "payer_account_identifier": "CH0000000000000000009",
                "idempotency_key": "engine-recovery-api",
            },
            content_type="application/json",
        )

    assert response.status_code == 400
    assert "18.6 interest engine" in response.json()["detail"]
    assert not LoanRecoveryEvent.objects.filter(loan=loan).exists()


@pytest.mark.django_db
def test_an_earlier_loan_default_is_not_cancelled_after_a_recovery_receipt(
    admin_user: Model,  # noqa: F811
    superadmin: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _defaulted(admin_user, loan)
    _recovery(admin_user, loan, "recovery-after-default")

    with pytest.raises(engine.EngineServicingError, match="A recovery receipt was recorded"):
        _cancel(superadmin, loan)
    loan.refresh_from_db()
    assert str(cast(Any, loan).status) == "defaulted"
    assert engine.active_declaration(loan) is not None


@pytest.mark.django_db
def test_an_earlier_loan_default_without_money_after_it_can_be_cancelled(
    admin_user: Model,  # noqa: F811
    superadmin: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _defaulted(admin_user, loan)

    declaration = _cancel(superadmin, loan)

    assert declaration.cancelled_at is not None
    loan.refresh_from_db()
    assert str(cast(Any, loan).status) != "defaulted"


@pytest.mark.django_db
def test_a_loan_originator_repayment_after_the_declaration_blocks_the_cancellation(
    admin_user: Model,  # noqa: F811
    superadmin: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard reads the Loan Originator repayments too. An LO loan needs originator data
    this fixture does not have, so only that one query is replaced."""
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _defaulted(admin_user, loan)
    real_get_model = apps.get_model
    queried: list[dict[str, Any]] = []

    class _Repayments:
        def filter(self, **lookups: Any) -> _Repayments:
            queried.append(lookups)
            return self

        def exists(self) -> bool:
            return True

    def get_model(app_label: str, model_name: str | None = None, **kwargs: Any) -> Any:
        if model_name == "OriginatorBorrowerRepayment":
            return SimpleNamespace(objects=_Repayments())
        return real_get_model(app_label, model_name, **kwargs)

    monkeypatch.setattr(apps, "get_model", get_model)
    with pytest.raises(engine.EngineServicingError, match="A Loan Originator repayment"):
        _cancel(superadmin, loan)
    assert queried[0] == {"loan_profile__loan": loan}
    assert "created_at__gt" in queried[1]


@pytest.mark.django_db
def test_an_engine_default_is_not_cancelled_after_an_expense(
    admin_user: Model,  # noqa: F811
    superadmin: Model,  # noqa: F811
    investors: list[Model],  # noqa: F811
) -> None:
    loan = _defaulted_engine_loan(admin_user, investors)
    with at(date(2027, 3, 22)):
        engine.record_loan_expense(
            engine.RecordLoanExpenseCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                amount_minor=150_00,
                value_date=date(2027, 3, 22),
                note="Debt collection letter",
                idempotency_key="expense-after-default",
            )
        )
        with pytest.raises(engine.EngineServicingError, match="An expense was recorded"):
            _cancel(superadmin, loan)
