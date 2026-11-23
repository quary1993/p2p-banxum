"""IP of Webby-Soft SRL. 18.6 (Q08): the investor payloads carry the loan's payment frequency.

The investor screens say "Quarterly payments", "Interest paid half-yearly" and so on from this field;
before, they said "monthly" for every loan.
"""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module

import pytest
from django.db.models import Model

from backend.apps.loans.models import PaymentFrequency
from backend.apps.loans.services import PublishLoanCommand, create_loan, publish_loan
from backend.apps.loans.tests.test_loans import _borrower, _loan_command, admin_user  # noqa: F401
from backend.apps.marketplace_primary.api.serializers import MarketplaceLoanDetailSerializer, MarketplaceLoanPreviewSerializer
from backend.apps.smart_invest.api.serializers import SmartInvestOpportunitySerializer

pytestmark = pytest.mark.django_db


def test_preview_detail_and_smart_invest_payloads_carry_the_payment_frequency(admin_user: Model) -> None:  # noqa: F811
    command = replace(_loan_command(admin_user, _borrower(admin_user)), payment_frequency=PaymentFrequency.QUARTERLY)
    loan = create_loan(command)
    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    marketplace = import_module("backend.apps.marketplace_primary.services")

    preview = marketplace.public_marketplace_listing_payload(loan)
    detail = marketplace.full_marketplace_listing_payload(loan)

    assert preview["payment_frequency"] == "quarterly"
    assert detail["payment_frequency"] == "quarterly"
    assert MarketplaceLoanPreviewSerializer(preview).data["payment_frequency"] == "quarterly"
    assert MarketplaceLoanDetailSerializer(detail).data["payment_frequency"] == "quarterly"
    # Smart Invest matches are built from the preview payload.
    assert SmartInvestOpportunitySerializer(preview).data["payment_frequency"] == "quarterly"


def test_a_payload_without_a_frequency_reads_monthly() -> None:
    assert MarketplaceLoanPreviewSerializer().fields["payment_frequency"].default == "monthly"


@pytest.mark.parametrize(
    ("repayment_type", "frequency", "interest_only_months", "installments"),
    [
        ("equal_installments", "monthly", 0, 12),
        ("equal_installments", "quarterly", 0, 4),
        ("bullet_periodic_interest", "half_yearly", 0, 2),
        ("equal_installments", "annual", 0, 1),
        ("interest_only_then_amortizing", "quarterly", 3, 4),
        ("full_at_maturity", "monthly", 0, 1),
    ],
)
def test_every_payment_frequency_and_shape_can_be_published(  # noqa: F811
    admin_user: Model, repayment_type: str, frequency: str, interest_only_months: int, installments: int
) -> None:
    """The publication check counted one installment per month, so quarterly, half-yearly, yearly
    and full-at-maturity loans could not be published (found by the design pass, 2026-11-23)."""
    command = replace(
        _loan_command(admin_user, _borrower(admin_user), repayment_type=repayment_type, interest_only_months=interest_only_months),
        payment_frequency=frequency,
    )
    loan = create_loan(command)
    assert loan.installments.filter(schedule_version=loan.schedule_version).count() == installments

    published = publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))

    assert published.status == "published"
