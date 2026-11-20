"""IP of Webby-Soft SRL. Audit S7-2: the compliance block is checked again at the money step.

Each test lets the early check pass (as if the review opened just after it) and shows that the
final step, under the investor row lock, refuses: primary allocation, Loan Originator claim
purchase (the path the internal batch helper uses too) and resale purchase.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.utils import timezone

from backend.apps.kyc_compliance import declarations as services
from backend.apps.platform_core.domain import declarations as rules
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code

CLEAN = {
    "beneficial_owner_is_self": True,
    "sources_of_funds": ["salary"],
    "pep_status": "no",
    "yearly_volume_band": "10k_50k",
}


def _user(email: str, *, account_type: str = "natural_person_lender", **extra: Any) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name=email.split("@")[0],
            account_type=account_type,
            status="active",
            **extra,
        ),
    )


def _review_opens_after_the_early_check(
    investor: Model, monkeypatch: pytest.MonkeyPatch, settings: Any
) -> None:
    """A clean declaration, then a necessary review; the first block check still passes."""
    settings.COMPLIANCE_DECLARATIONS_REQUIRED = True
    services.submit_declaration(services.SubmitDeclarationCommand(actor=investor, data=CLEAN))
    officer = _user(
        "race-officer@example.test",
        account_type="admin",
        is_staff=True,
        staff_roles=[rules.ROLE_COMPLIANCE],
    )
    services.open_review(
        services.OpenReviewCommand(
            actor=officer, investor_id=str(investor.pk), reason="Adverse media hit."
        )
    )
    real = services.investment_block
    calls = {"count": 0}

    def first_passes(user: Any, **kwargs: Any) -> str | None:
        calls["count"] += 1
        return None if calls["count"] == 1 else real(user, **kwargs)

    monkeypatch.setattr(services, "investment_block", first_passes)


@pytest.mark.django_db
def test_primary_allocation_rechecks_under_the_investor_lock(
    monkeypatch: pytest.MonkeyPatch, settings: Any, row_locks_need_a_transaction: None
) -> None:
    helpers: Any = import_module("backend.apps.marketplace_primary.tests.test_primary_marketplace")
    primary: Any = import_module("backend.apps.marketplace_primary.services")
    admin = _user("race-admin@example.test", account_type="admin", is_staff=True)
    investor = _user("race-primary@example.test")
    helpers._approve_financial_access(investor)
    loan = helpers._create_published_loan(admin)
    helpers._declare_deposit(admin, investor, amount_minor=10_000_00, idempotency_key="race-d")
    order = primary.create_primary_investment_order(
        primary.CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(cast(Any, loan).pk),
            amount_minor=10_000_00,
            idempotency_key="race-order",
        )
    )
    acceptance = helpers._create_primary_acceptance(
        investor, order_id=str(order.id), idempotency_key="race-accept"
    )
    _review_opens_after_the_early_check(investor, monkeypatch, settings)

    with pytest.raises(primary.MarketplacePrimaryValidationError, match="compliance team"):
        primary.allocate_primary_order_from_balance(
            primary.AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                **helpers._sandbox_ack(order),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="race-allocate",
                **helpers._sensitive_code_payload(investor, "primary_investment"),
            )
        )
    order.refresh_from_db()
    assert str(order.status) not in {"balance_allocated", "partially_allocated"}


@pytest.mark.django_db
def test_loan_originator_purchase_rechecks_under_the_investor_lock(
    monkeypatch: pytest.MonkeyPatch, settings: Any
) -> None:
    claims: Any = import_module("backend.apps.originator_claims.tests.test_originator_claims")
    originator: Any = import_module("backend.apps.originator_claims.services")
    models: Any = import_module("backend.apps.originator_claims.models")
    ledger: Any = import_module("backend.apps.ledger.services")
    accounts: Any = import_module("backend.apps.platform_core.tests.deposit_accounts")
    admin = _user("race-lo-admin@example.test", account_type="admin", is_staff=True)
    investor = _user("race-lo@example.test")
    claims._approve_financial_access(investor)
    today = business_date(timezone.now())
    lo = originator.create_loan_originator(
        originator.CreateLoanOriginatorCommand(
            actor=admin,
            legal_name="Race Originator AG",
            public_name="Race Originator",
            registration_number="CHE-444.555.667",
            jurisdiction="CH",
            registered_address="Bern, Switzerland",
            settlement_account_name="Race Originator AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference="KYB-RACE-001",
            status=models.LoanOriginatorStatus.ACTIVE,
        )
    )
    result = originator.create_originator_loan(
        originator.CreateOriginatorLoanCommand(
            actor=admin,
            originator_id=str(lo.id),
            title="Race claim",
            investor_summary="Performing claim.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1200,
            target_yield_bps=800,
            distribution_model=models.OriginatorDistributionModel.LEGACY_YIELD_V1,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=claims._dated_two_period_csv(
                today=today, include_payment=False, final_due_days=90
            ),
            source_filename="race.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": "Race Borrower AG",
                "borrower_display_name": "Race borrower",
            },
            historical_boundary_offer=True,
        )
    )
    originator.publish_originator_loan(
        originator.PublishOriginatorLoanCommand(
            actor=admin, loan_id=str(result.loan.id), as_of_date=today
        )
    )
    accounts.declare_deposit_and_verify_account(
        ledger.DeclareLenderDepositCommand(
            actor=admin,
            investor_user_id=str(investor.pk),
            amount_minor=500_000,
            currency="CHF",
            booking_date=today,
            value_date=today,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Race Investor",
            payer_account_identifier="CH9300762011623852957",
            bank_reference="RACE-DEPOSIT",
            payment_reference="RACE",
            idempotency_key="race-lo-deposit",
        )
    )
    quote = originator.create_originator_claim_quote(
        originator.CreateOriginatorClaimQuoteCommand(
            actor=investor, loan_id=str(result.loan.id), requested_cash_minor=250_000
        )
    )
    acceptance = claims._primary_acceptance(investor, quote_id=str(quote.id))
    code = issue_sensitive_action_test_code(investor, "primary_investment")
    _review_opens_after_the_early_check(investor, monkeypatch, settings)

    with pytest.raises(originator.OriginatorClaimsValidationError, match="compliance team"):
        originator.purchase_originator_claim(
            originator.PurchaseOriginatorClaimCommand(
                actor=investor,
                quote_id=str(quote.id),
                document_acceptance_id=str(acceptance.pk),
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
                pin=code.pin,
                idempotency_key="race-lo-purchase",
            )
        )
    assert not models.OriginatorClaimPurchase.objects.filter(quote_id=quote.id).exists()


@pytest.mark.django_db
def test_resale_purchase_rechecks_under_the_investor_lock(
    monkeypatch: pytest.MonkeyPatch, settings: Any
) -> None:
    resale: Any = import_module("backend.apps.secondary_market.tests.test_secondary_market")
    market: Any = import_module("backend.apps.secondary_market.services")
    admin = _user("race-sm-admin@example.test", account_type="admin", is_staff=True)
    seller = _user("race-seller@example.test")
    buyer = _user("race-buyer@example.test")
    resale._approve_financial_access(seller)
    resale._approve_financial_access(buyer)
    loan = resale._create_funded_loan(admin)
    holding = resale._create_holding(admin, seller, loan)
    listing = market.create_secondary_market_listing(
        market.CreateSecondaryMarketListingCommand(
            actor=seller,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(resale._create_listing_acceptance(seller, holding).pk),
            idempotency_key="race-listing",
            **resale._sensitive_code_payload(seller, "secondary_market_listing"),
        )
    )
    resale._declare_deposit(
        admin, buyer, amount_minor=20_000_00, idempotency_key="race-buyer-deposit"
    )
    review = resale._review_purchase(buyer, listing)
    acceptance = resale._create_purchase_acceptance(buyer, listing, review=review)
    code = resale._sensitive_code_payload(buyer, "secondary_market_purchase")
    _review_opens_after_the_early_check(buyer, monkeypatch, settings)

    with pytest.raises(market.SecondaryMarketValidationError, match="compliance team"):
        market.purchase_secondary_market_listing(
            market.PurchaseSecondaryMarketListingCommand(
                actor=buyer,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="race-purchase",
                **resale._expected_terms(review),
                **code,
            )
        )
    listing.refresh_from_db()
    assert str(listing.status) == "active"
