from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.utils import timezone

from backend.apps.originator_claims.domain.imports import (
    OriginatorImportValidationError,
    parse_originator_import_csv,
)
from backend.apps.originator_claims.domain.pricing import (
    price_assigned_principal,
    quote_cash_consideration,
)
from backend.apps.originator_claims.models import (
    InvestorOriginatorRepaymentDistributionLine,
    LoanOriginatorStatus,
    OriginatorClaimEntitlement,
    OriginatorClaimPurchase,
    OriginatorDistributionModel,
    OriginatorFundingRoundClose,
    OriginatorLoanImport,
    OriginatorLoanProfile,
    OriginatorOpportunityStatus,
    OriginatorSettlementPurchase,
    OriginatorSettlementRepayment,
    OriginatorSubscriptionActivation,
    OriginatorSubscriptionCancellation,
)
from backend.apps.originator_claims.services import (
    ActivateOriginatorSubscriptionCommand,
    CancelOriginatorSubscriptionCommand,
    CloseOriginatorSubscriptionRoundCommand,
    CreateLoanOriginatorCommand,
    CreateOriginatorClaimQuoteCommand,
    CreateOriginatorLoanCommand,
    FinalizeOriginatorSettlementCommand,
    HoldOriginatorLoanCommand,
    OriginatorClaimsValidationError,
    PublishOriginatorLoanCommand,
    PurchaseOriginatorClaimCommand,
    RecordOriginatorBorrowerRepaymentCommand,
    _originator_payment_waterfall,
    _originator_repayment_plan,
    _skin_bps,
    _validate_par_subscription_terms,
    activate_originator_subscription,
    cancel_originator_subscription,
    close_originator_subscription_round,
    create_loan_originator,
    create_originator_claim_quote,
    create_originator_loan,
    finalize_originator_settlement,
    get_originator_admin_loan_payload,
    list_outstanding_originator_settlements,
    place_originator_loan_on_hold,
    publish_originator_loan,
    purchase_originator_claim,
    record_originator_borrower_repayment,
    replace_originator_loan_draft,
    scan_originator_opportunity_lifecycle,
    sync_originator_settlement_tasks,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import Currency, OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code

EXAMPLES_DIR = Path(__file__).resolve().parents[4] / "imports_examples"


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="originator-admin@example.test",
            password="AdminPass123!",
            full_name="Originator Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="originator-investor@example.test",
            full_name="Originator Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )


@pytest.fixture
def other_investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="originator-buyer@example.test",
            full_name="Originator Claim Buyer",
            account_type="natural_person_lender",
            status="active",
        ),
    )


def _approve_financial_access(investor: Model) -> None:
    now = timezone.now()
    cast(Any, investor).phone_verified_at = now
    investor.save(update_fields=["phone_verified_at"])
    case_model = import_module("backend.apps.kyc_compliance.models").KycVerificationCase
    case_model.objects.create(
        user_id=investor.pk,
        subject_reference=f"user:{investor.pk}",
        provider_environment="test",
        workflow_id="originator-workflow",
        vendor_data=f"user:{investor.pk}",
        status="approved",
        decision_at=now,
    )


def _primary_acceptance(investor: Model, *, quote_id: str) -> Model:
    documents = import_module("backend.apps.documents.models")
    document_services = import_module("backend.apps.documents.services")
    template = documents.DocumentTemplate.objects.create(
        category="primary_market_investment",
        template_key=f"originator-{quote_id}"[:128],
        language="en",
        name="Originator claim assignment terms",
        created_by_superadmin_id=investor.pk,
    )
    version = documents.DocumentTemplateVersion.objects.create(
        template=template,
        version_number=1,
        status="published",
        title="Originator claim assignment terms",
        body="Assignment terms",
        checkbox_labels=["I accept the claim assignment terms."],
        variable_schema={},
        content_hash="c" * 64,
        created_by_superadmin_id=investor.pk,
        published_at=timezone.now(),
    )
    template.current_published_version = version
    template.save(update_fields=["current_published_version"])
    return cast(
        Model,
        document_services.accept_document_terms(
            document_services.AcceptDocumentTermsCommand(
                actor=investor,
                category="primary_market_investment",
                template_key=str(template.template_key),
                language=str(template.language),
                expected_template_version_id=str(version.id),
                accepted_checkbox_labels=["I accept the claim assignment terms."],
                context_type="originator_claim_quote",
                context_id=quote_id,
                data_snapshot={
                    "user": {"email": "forged@example.test"},
                    "originator": {"legal_name": "Forged Originator"},
                    "order": {"assigned_principal_minor": 1},
                },
                idempotency_key=f"originator-accept-{quote_id}",
            )
        ),
    )


def _primary_order_acceptance(investor: Model, *, order_id: str, suffix: str) -> Model:
    documents = import_module("backend.apps.documents.models")
    template = documents.DocumentTemplate.objects.create(
        category="primary_market_investment",
        template_key=f"originator-subscription-{suffix}"[:128],
        language="en",
        name="Originator subscription terms",
        created_by_superadmin_id=investor.pk,
    )
    version = documents.DocumentTemplateVersion.objects.create(
        template=template,
        version_number=1,
        status="published",
        title="Originator subscription terms",
        body="Originator subscription terms",
        checkbox_labels=["I accept the originator subscription terms."],
        variable_schema={},
        content_hash="e" * 64,
        created_by_superadmin_id=investor.pk,
        published_at=timezone.now(),
    )
    template.current_published_version = version
    template.save(update_fields=["current_published_version"])
    return cast(
        Model,
        documents.DocumentAcceptanceEvidence.objects.create(
            user_id=investor.pk,
            category="primary_market_investment",
            template=template,
            template_version=version,
            template_version_number=1,
            template_hash=version.content_hash,
            context_type="primary_order",
            context_id=order_id,
            accepted_checkbox_labels=["I accept the originator subscription terms."],
            data_snapshot={},
            idempotency_key=f"originator-subscription-accept-{suffix}",
        ),
    )


def _primary_batch_acceptance(
    investor: Model,
    *,
    batch_key: str,
    items: list[dict[str, Any]],
    suffix: str,
) -> Model:
    documents = import_module("backend.apps.documents.models")
    template = documents.DocumentTemplate.objects.create(
        category="primary_market_investment",
        template_key=f"originator-subscription-batch-{suffix}"[:128].lower(),
        language="en",
        name="Originator subscription batch terms",
        created_by_superadmin_id=investor.pk,
    )
    version = documents.DocumentTemplateVersion.objects.create(
        template=template,
        version_number=1,
        status="published",
        title="Originator subscription batch terms",
        body="Originator subscription batch terms",
        checkbox_labels=["I accept the originator subscription batch terms."],
        variable_schema={},
        content_hash="f" * 64,
        created_by_superadmin_id=investor.pk,
        published_at=timezone.now(),
    )
    template.current_published_version = version
    template.save(update_fields=["current_published_version"])
    return cast(
        Model,
        documents.DocumentAcceptanceEvidence.objects.create(
            user_id=investor.pk,
            category="primary_market_investment",
            template=template,
            template_version=version,
            template_version_number=1,
            template_hash=version.content_hash,
            context_type="primary_order_batch",
            context_id=batch_key,
            accepted_checkbox_labels=["I accept the originator subscription batch terms."],
            data_snapshot={"items": items},
            idempotency_key=f"originator-subscription-batch-accept-{suffix}",
        ),
    )


def _secondary_acceptance(
    investor: Model,
    *,
    category: str,
    context_type: str,
    context_id: str,
    suffix: str,
) -> Model:
    documents = import_module("backend.apps.documents.models")
    template = documents.DocumentTemplate.objects.create(
        category=category,
        template_key=f"originator-secondary-{suffix}"[:128],
        language="en",
        name="Originator claim secondary-market terms",
        created_by_superadmin_id=investor.pk,
    )
    version = documents.DocumentTemplateVersion.objects.create(
        template=template,
        version_number=1,
        status="published",
        title="Originator claim secondary-market terms",
        body="Assignment terms",
        checkbox_labels=["I accept the secondary-market assignment terms."],
        variable_schema={},
        content_hash="d" * 64,
        created_by_superadmin_id=investor.pk,
        published_at=timezone.now(),
    )
    template.current_published_version = version
    template.save(update_fields=["current_published_version"])
    return cast(
        Model,
        documents.DocumentAcceptanceEvidence.objects.create(
            user_id=investor.pk,
            category=category,
            template=template,
            template_version=version,
            template_version_number=1,
            template_hash=version.content_hash,
            context_type=context_type,
            context_id=context_id,
            accepted_checkbox_labels=["I accept the secondary-market assignment terms."],
            data_snapshot={},
            idempotency_key=f"originator-secondary-accept-{suffix}",
        ),
    )


def _declare_originator_test_deposit(
    *,
    admin_user: Model,
    investor: Model,
    amount_minor: int,
    today: date,
    suffix: str,
) -> None:
    ledger = import_module("backend.apps.ledger.services")
    ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency="CHF",
            booking_date=today,
            value_date=today,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name=str(cast(Any, investor).full_name),
            payer_account_identifier="CH9300762011623852957",
            bank_reference=f"ORIGINATOR-{suffix}-DEPOSIT",
            payment_reference=f"ORIGINATOR-{suffix}",
            idempotency_key=f"originator-{suffix.lower()}-deposit",
        )
    )


def _csv(name: str = "originator_equal_installments.csv") -> str:
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def _dated_two_period_csv(
    *,
    today: date,
    include_payment: bool,
    include_final_payment: bool = False,
    final_due_days: int = 45,
) -> str:
    accrual_start = today - timedelta(days=15)
    first_due = today + timedelta(days=15)
    second_due = today + timedelta(days=final_due_days)
    header = (
        "row_type,reference,installment_number,accrual_start_date,due_date,value_date,"
        "payment_type,opening_principal_minor,principal_minor,interest_minor,penalty_minor,"
        "fee_minor,total_minor,closing_principal_minor,resulting_principal_minor"
    )
    rows = [
        header,
        (
            f"schedule,,1,{accrual_start.isoformat()},{first_due.isoformat()},,,1000000,"
            "500000,10000,0,0,510000,500000,"
        ),
    ]
    if include_payment:
        rows.append(
            f"payment,LO-PAY-1,,,,{first_due.isoformat()},regular,,500000,10000,0,0,510000,,500000"
        )
    rows.append(
        f"schedule,,2,{first_due.isoformat()},{second_due.isoformat()},,,500000,"
        "500000,5000,0,0,505000,0,"
    )
    if include_final_payment:
        rows.append(
            f"payment,LO-PAY-2,,,,{second_due.isoformat()},regular,,500000,5000,0,0,505000,,0"
        )
    return "\n".join(rows) + "\n"


def _par_subscription_csv(
    *,
    today: date,
    include_boundary_payment: bool,
    include_second_payment: bool = False,
) -> str:
    boundary_due = today + timedelta(days=10)
    second_due = boundary_due + timedelta(days=30)
    final_due = second_due + timedelta(days=30)
    rows = [
        (
            "row_type,reference,installment_number,accrual_start_date,due_date,value_date,"
            "payment_type,opening_principal_minor,principal_minor,interest_minor,penalty_minor,"
            "fee_minor,total_minor,closing_principal_minor,resulting_principal_minor"
        ),
        (
            f"schedule,,1,{(today - timedelta(days=20)).isoformat()},"
            f"{boundary_due.isoformat()},,,1000000,200000,10000,2000,0,212000,800000,"
        ),
    ]
    if include_boundary_payment:
        rows.append(
            f"payment,BOUNDARY-1,,,,{boundary_due.isoformat()},regular,,200000,10000,"
            "2000,0,212000,,800000"
        )
    rows.extend(
        [
            (
                f"schedule,,2,{boundary_due.isoformat()},{second_due.isoformat()},,,800000,"
                "400000,100000,40000,0,540000,400000,"
            ),
            (
                f"schedule,,3,{second_due.isoformat()},{final_due.isoformat()},,,400000,"
                "400000,50000,20000,0,470000,0,"
            ),
        ]
    )
    if include_second_payment:
        rows.append(
            f"payment,SUBSCRIPTION-PAY-2,,,,{second_due.isoformat()},regular,,400000,"
            "100000,40000,0,540000,,400000"
        )
    return "\n".join(rows) + "\n"


def test_par_subscription_boundary_is_first_installment_after_funding() -> None:
    today = date(2026, 9, 3)
    command = SimpleNamespace(
        as_of_date=today,
        funding_deadline=today + timedelta(days=5),
        entitlement_start_date=today + timedelta(days=10),
        activation_outstanding_principal_minor=800_000,
        investor_interest_participation_bps=7_000,
        investor_penalty_participation_bps=5_000,
    )
    parsed = SimpleNamespace(
        schedule_rows=[
            SimpleNamespace(
                installment_number=1,
                due_date=today + timedelta(days=7),
                closing_principal_minor=900_000,
                principal_minor=100_000,
            ),
            SimpleNamespace(
                installment_number=2,
                due_date=today + timedelta(days=10),
                closing_principal_minor=800_000,
                principal_minor=100_000,
            ),
        ],
        maturity_date=today + timedelta(days=90),
    )

    with pytest.raises(
        OriginatorClaimsValidationError,
        match="first installment due after the funding deadline",
    ):
        _validate_par_subscription_terms(
            cast(CreateOriginatorLoanCommand, command),
            parsed=cast(Any, parsed),
        )


def _create_par_subscription_loan(
    *,
    admin_user: Model,
    today: date,
    suffix: str,
    skin_in_the_game_bps: int = 0,
) -> Any:
    originator = create_loan_originator(
        CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name=f"Subscription Originator {suffix} AG",
            public_name=f"Subscription Originator {suffix}",
            registration_number=f"CHE-SUBSCRIPTION-{suffix}",
            jurisdiction="CH",
            registered_address="Zurich, Switzerland",
            settlement_account_name=f"Subscription Originator {suffix} AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference=f"KYB-SUBSCRIPTION-{suffix}",
            status=LoanOriginatorStatus.ACTIVE,
        )
    )
    result = create_originator_loan(
        CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title=f"Par subscription {suffix}",
            investor_summary="Par subscription with component participation.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1_200,
            distribution_model=OriginatorDistributionModel.PAR_COMPONENT_V2,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_par_subscription_csv(today=today, include_boundary_payment=False),
            source_filename=f"subscription-{suffix}.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": f"Subscription Borrower {suffix} AG",
                "borrower_display_name": f"Subscription borrower {suffix}",
            },
            skin_in_the_game_bps=skin_in_the_game_bps,
            funding_deadline=today + timedelta(days=5),
            entitlement_start_date=today + timedelta(days=10),
            activation_outstanding_principal_minor=800_000,
            investor_interest_participation_bps=7_000,
            investor_penalty_participation_bps=5_000,
        )
    )
    publish_originator_loan(
        PublishOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today,
        )
    )
    return result


def _allocate_par_subscription(
    *,
    admin_user: Model,
    investor: Model,
    loan: Model,
    today: date,
    amount_minor: int,
    suffix: str,
) -> Any:
    _approve_financial_access(investor)
    _declare_originator_test_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=amount_minor,
        today=today,
        suffix=suffix,
    )
    marketplace = import_module("backend.apps.marketplace_primary.services")
    order = marketplace.create_primary_investment_order(
        marketplace.CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=amount_minor,
            idempotency_key=f"subscription-{suffix}-order",
        )
    )
    acceptance = _primary_order_acceptance(
        investor,
        order_id=str(order.id),
        suffix=suffix,
    )
    code = issue_sensitive_action_test_code(investor, "primary_investment")
    return marketplace.allocate_primary_order_from_balance(
        marketplace.AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=f"subscription-{suffix}-allocate",
            sensitive_action_code_id=code.code_id,
            sensitive_action_code=code.raw_code,
        )
    )


def _activate_par_subscription_for_test(
    *,
    admin_user: Model,
    result: Any,
    today: date,
    suffix: str,
) -> OriginatorSubscriptionActivation:
    close_originator_subscription_round(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today + timedelta(days=6),
            close_reason="Funding deadline reached.",
            idempotency_key=f"subscription-{suffix}-close",
        )
    )
    boundary_date = today + timedelta(days=10)
    return activate_originator_subscription(
        ActivateOriginatorSubscriptionCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=_par_subscription_csv(
                today=today,
                include_boundary_payment=True,
            ),
            source_filename=f"subscription-{suffix}-activation.csv",
            as_of_date=boundary_date,
            boundary_payment_reference="BOUNDARY-1",
            boundary_payment_date=boundary_date,
            notes="Verified boundary installment received by the originator.",
            idempotency_key=f"subscription-{suffix}-activate",
        )
    )


def _create_dated_originator_loan(
    *,
    admin_user: Model,
    today: date,
    suffix: str,
    final_due_days: int = 90,
    skin_in_the_game_bps: int = 0,
) -> Any:
    originator = create_loan_originator(
        CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name=f"Lifecycle Originator {suffix} AG",
            public_name=f"Lifecycle Originator {suffix}",
            registration_number=f"CHE-LIFECYCLE-{suffix}",
            jurisdiction="CH",
            registered_address="Zurich, Switzerland",
            settlement_account_name=f"Lifecycle Originator {suffix} AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference=f"KYB-LIFECYCLE-{suffix}",
            status=LoanOriginatorStatus.ACTIVE,
        )
    )
    result = create_originator_loan(
        CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title=f"Lifecycle claim {suffix}",
            investor_summary="Performing claim used to verify lifecycle boundaries.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1200,
            target_yield_bps=800,
            distribution_model=OriginatorDistributionModel.LEGACY_YIELD_V1,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_dated_two_period_csv(
                today=today,
                include_payment=False,
                final_due_days=final_due_days,
            ),
            source_filename=f"lifecycle-{suffix}.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": f"Confidential Borrower {suffix} AG",
                "borrower_display_name": "Swiss SME borrower",
            },
            skin_in_the_game_bps=skin_in_the_game_bps,
        )
    )
    publish_originator_loan(
        PublishOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today,
        )
    )
    return result


def test_import_parser_accepts_every_documented_example() -> None:
    expectations = {
        "originator_equal_installments.csv": (1_000_000, 0, "equal_installments", 0),
        "originator_bullet_periodic_interest.csv": (1_000_000, 0, "bullet_periodic_interest", 0),
        "originator_amortizing_principal_interest.csv": (
            1_000_000,
            0,
            "amortizing_principal_interest",
            0,
        ),
        "originator_interest_only_then_bullet.csv": (1_000_000, 0, "interest_only_then_bullet", 1),
        "originator_interest_only_then_amortizing.csv": (
            1_000_000,
            0,
            "interest_only_then_amortizing",
            1,
        ),
        "originator_historical_prepayment.csv": (600_000, 1, "equal_installments", 0),
    }
    for filename, (outstanding, payment_count, repayment_type, io_months) in expectations.items():
        parsed = parse_originator_import_csv(
            csv_content=_csv(filename),
            original_principal_minor=1_000_000,
            as_of_date=date(2026, 9, 1),
            repayment_type=repayment_type,
            interest_only_months=io_months,
        )
        assert parsed.current_outstanding_principal_minor == outstanding
        assert len(parsed.payment_rows) == payment_count


def test_import_parser_rejects_non_reconciling_future_principal() -> None:
    content = _csv().replace("500000,500000,5000", "500000,499999,5000", 1)
    with pytest.raises(OriginatorImportValidationError):
        parse_originator_import_csv(
            csv_content=content,
            original_principal_minor=1_000_000,
            as_of_date=date(2026, 9, 1),
        )


def test_import_parser_rejects_schedule_shape_that_conflicts_with_product_type() -> None:
    with pytest.raises(OriginatorImportValidationError, match="(?i)bullet"):
        parse_originator_import_csv(
            csv_content=_csv("originator_equal_installments.csv"),
            original_principal_minor=1_000_000,
            as_of_date=date(2026, 9, 1),
            repayment_type="bullet_periodic_interest",
            interest_only_months=0,
        )


def test_pricing_uses_act_365_and_conserves_cash() -> None:
    parsed = parse_originator_import_csv(
        csv_content=_csv(),
        original_principal_minor=1_000_000,
        as_of_date=date(2026, 9, 1),
    )
    opening_price, opening_flows = price_assigned_principal(
        schedule_rows=parsed.schedule_rows,
        current_outstanding_principal_minor=1_000_000,
        assigned_principal_minor=200_000,
        target_yield_bps=800,
        pricing_date=date(2026, 9, 1),
        currency="CHF",
    )
    mid_period_price, mid_period_flows = price_assigned_principal(
        schedule_rows=parsed.schedule_rows,
        current_outstanding_principal_minor=1_000_000,
        assigned_principal_minor=200_000,
        target_yield_bps=800,
        pricing_date=date(2026, 9, 16),
        currency="CHF",
    )
    assert sum(flow.principal_minor for flow in opening_flows) == 200_000
    assert opening_flows[0].interest_minor == 2_000
    assert mid_period_flows[0].interest_minor == 1_000
    assert mid_period_price < opening_price

    quote = quote_cash_consideration(
        schedule_rows=parsed.schedule_rows,
        current_outstanding_principal_minor=1_000_000,
        unsold_principal_minor=1_000_000,
        requested_cash_minor=250_000,
        minimum_investment_minor=100_000,
        target_yield_bps=800,
        premium_fee_bps=5000,
        pricing_date=date(2026, 9, 1),
        currency="CHF",
    )
    assert quote.executable_cash_minor <= 250_000
    assert quote.executable_cash_minor + quote.rounding_remainder_minor == 250_000
    assert quote.platform_fee_minor + quote.originator_payable_minor == quote.executable_cash_minor
    assert sum(flow.principal_minor for flow in quote.cash_flows) == quote.assigned_principal_minor


@pytest.mark.django_db
def test_admin_creates_and_publishes_originator_loan(admin_user: Model) -> None:
    originator = create_loan_originator(
        CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name="Alpine Credit Originator AG",
            public_name="Alpine Credit",
            registration_number="CHE-111.222.333",
            jurisdiction="CH",
            registered_address="Zurich, Switzerland",
            settlement_account_name="Alpine Credit Originator AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference="KYB-2026-001",
            status=LoanOriginatorStatus.ACTIVE,
        )
    )
    result = create_originator_loan(
        CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title="Anonymized SME receivable",
            investor_summary="Existing performing SME claim assigned by a Loan Originator.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1200,
            target_yield_bps=800,
            distribution_model=OriginatorDistributionModel.LEGACY_YIELD_V1,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_csv(),
            source_filename="originator_equal_installments.csv",
            as_of_date=date(2026, 9, 1),
            borrower_snapshot={
                "borrower_legal_name": "Confidential Borrower AG",
                "borrower_display_name": "Swiss SME borrower",
                "country": "Switzerland",
            },
        )
    )
    assert result.loan.product_type == "originator_claim"
    assert result.loan.borrower_id is None
    assert result.loan.funding_deadline is None
    assert result.profile.unsold_principal_minor == 1_000_000
    assert OriginatorLoanImport.objects.filter(loan=result.loan).count() == 1
    direct_loan_services = import_module("backend.apps.loans.services")
    with pytest.raises(ValueError, match="(?i)originator claim"):
        direct_loan_services.update_loan(
            direct_loan_services.UpdateLoanCommand(
                actor=admin_user,
                loan_id=str(result.loan.id),
                title="Generic service must not mutate this product",
            )
        )
    with pytest.raises(ValueError, match="(?i)originator claim"):
        direct_loan_services.publish_loan(
            direct_loan_services.PublishLoanCommand(
                actor=admin_user,
                loan_id=str(result.loan.id),
            )
        )

    detail = get_originator_admin_loan_payload(
        actor=admin_user,
        loan_id=str(result.loan.id),
    )
    assert detail["borrower_snapshot"]["borrower_legal_name"] == "Confidential Borrower AG"
    assert len(detail["schedule"]) == 2

    replacement = replace_originator_loan_draft(
        loan_id=str(result.loan.id),
        command=CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title="Corrected anonymized SME receivable",
            investor_summary="Corrected existing performing SME claim.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1200,
            target_yield_bps=825,
            distribution_model=OriginatorDistributionModel.LEGACY_YIELD_V1,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_csv(),
            source_filename="corrected-originator-equal-installments.csv",
            as_of_date=date(2026, 9, 1),
            borrower_snapshot={
                "borrower_legal_name": "Confidential Borrower AG",
                "borrower_display_name": "Swiss SME borrower",
                "country": "Switzerland",
            },
        ),
    )
    assert replacement.loan.title == "Corrected anonymized SME receivable"
    assert replacement.profile.schedule_revision == 2
    assert OriginatorLoanImport.objects.filter(loan=result.loan).count() == 2

    profile = publish_originator_loan(
        PublishOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=date(2026, 9, 1),
        )
    )
    assert profile.opportunity_status == "open"
    assert OriginatorLoanProfile.objects.get(id=profile.id).loan.status == "active"
    with pytest.raises(ValueError, match="Only an unpublished"):
        replace_originator_loan_draft(
            loan_id=str(result.loan.id),
            command=CreateOriginatorLoanCommand(
                actor=admin_user,
                originator_id=str(originator.id),
                title="Forbidden published replacement",
                investor_summary="Must not replace published evidence.",
                purpose="working_capital",
                purpose_description="Working capital",
                currency="CHF",
                original_principal_minor=1_000_000,
                interest_rate_bps=1200,
                target_yield_bps=800,
                distribution_model=OriginatorDistributionModel.LEGACY_YIELD_V1,
                minimum_investment_minor=100_000,
                repayment_type="equal_installments",
                interest_only_months=0,
                collateral_type="receivables",
                collateral_value_minor=1_500_000,
                collateral_description="Assigned receivables",
                risk_rating="BBB",
                csv_content=_csv(),
                source_filename="forbidden.csv",
                as_of_date=date(2026, 9, 1),
                borrower_snapshot={
                    "borrower_legal_name": "Confidential Borrower AG",
                    "borrower_display_name": "Swiss SME borrower",
                },
            ),
        )


@pytest.mark.django_db
def test_investor_purchase_is_immediate_balanced_and_creates_entitlements(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    originator = create_loan_originator(
        CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name="Purchase Test Originator AG",
            public_name="Purchase Test Originator",
            registration_number="CHE-444.555.666",
            jurisdiction="CH",
            registered_address="Bern, Switzerland",
            settlement_account_name="Purchase Test Originator AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference="KYB-PURCHASE-001",
            status=LoanOriginatorStatus.ACTIVE,
        )
    )
    result = create_originator_loan(
        CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title="Assigned performing SME loan",
            investor_summary="Performing claim offered by a Loan Originator.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1200,
            target_yield_bps=800,
            distribution_model=OriginatorDistributionModel.LEGACY_YIELD_V1,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_csv(),
            source_filename="originator_equal_installments.csv",
            as_of_date=date(2026, 9, 1),
            borrower_snapshot={
                "borrower_legal_name": "Confidential Purchase Borrower AG",
                "borrower_display_name": "Swiss SME borrower",
            },
        )
    )
    publish_originator_loan(
        PublishOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=date(2026, 9, 1),
        )
    )
    ledger = import_module("backend.apps.ledger.services")
    today = business_date(timezone.now())
    ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=500_000,
            currency="CHF",
            booking_date=today,
            value_date=today,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Originator Investor",
            payer_account_identifier="CH9300762011623852957",
            bank_reference="ORIGINATOR-PURCHASE-DEPOSIT",
            payment_reference="ORIGINATOR-PURCHASE",
            idempotency_key="originator-purchase-deposit",
        )
    )
    quote = create_originator_claim_quote(
        CreateOriginatorClaimQuoteCommand(
            actor=investor,
            loan_id=str(result.loan.id),
            requested_cash_minor=250_000,
        )
    )
    acceptance = _primary_acceptance(investor, quote_id=str(quote.id))
    code = issue_sensitive_action_test_code(investor, "primary_investment")
    purchase = purchase_originator_claim(
        PurchaseOriginatorClaimCommand(
            actor=investor,
            quote_id=str(quote.id),
            document_acceptance_id=str(acceptance.pk),
            sensitive_action_code_id=code.code_id,
            sensitive_action_code=code.raw_code,
            idempotency_key="originator-purchase-1",
        )
    )

    purchase = OriginatorClaimPurchase.objects.get(id=purchase.id)
    assert purchase.holding.current_principal_minor == purchase.assigned_principal_minor
    assert purchase.holding.source_type == "originator_claim"
    assert purchase.outstanding_principal_at_pricing_minor == 1_000_000
    assert purchase.quote.outstanding_principal_at_pricing_minor == 1_000_000
    assert purchase.assigned_principal_minor <= purchase.outstanding_principal_at_pricing_minor
    snapshot = purchase.document_acceptance.data_snapshot
    assert snapshot["user"]["email"] == cast(Any, investor).email
    assert snapshot["originator"]["legal_name"] == "Purchase Test Originator AG"
    assert snapshot["borrower"]["legal_name"] == "Swiss SME borrower"
    assert snapshot["order"]["assigned_principal_minor"] == purchase.assigned_principal_minor
    assert snapshot["order"]["outstanding_principal_at_pricing_minor"] == 1_000_000
    assert "platform_fee_minor" not in snapshot["order"]
    assert purchase.cash_consideration_minor == (
        purchase.originator_payable_minor + purchase.platform_fee_minor
    )
    assert (
        sum(
            entitlement.expected_principal_minor
            for entitlement in OriginatorClaimEntitlement.objects.filter(purchase=purchase)
        )
        == purchase.assigned_principal_minor
    )
    assert (
        OriginatorLoanProfile.objects.get(id=result.profile.id).unsold_principal_minor
        == 1_000_000 - purchase.assigned_principal_minor
    )
    postings = list(purchase.journal_entry.postings.all())
    assert sum(item.amount_minor for item in postings if item.side == "debit") == (
        purchase.cash_consideration_minor
    )
    assert sum(item.amount_minor for item in postings if item.side == "credit") == (
        purchase.cash_consideration_minor
    )
    assert Currency.objects.get(code="CHF").code == "CHF"
    purchase_email = OutboxMessage.objects.get(topic="email.originator_claim_purchase_confirmation")
    assert purchase_email.payload["email"] == cast(Any, investor).email
    assert purchase_email.payload["metadata"]["purchase_id"] == str(purchase.id)
    assert "platform_fee_minor" not in purchase_email.payload["metadata"]
    assert "originator_payable_minor" not in purchase_email.payload["metadata"]

    portal = import_module("backend.apps.investor_portal.services")
    portfolio = portal.get_investor_portfolio(actor=investor, as_of=timezone.now())
    portal_holding = next(
        item for item in portfolio["holdings"] if item["id"] == str(purchase.holding_id)
    )
    assert portal_holding["loan"]["product_type"] == "originator_claim"
    assert portal_holding["loan"]["borrower_id"] is None
    assert portal_holding["loan"]["borrower_name"] == "Swiss SME borrower"
    assert portal_holding["loan"]["originator_name"] == "Purchase Test Originator"
    assert (
        portal_holding["acquisition_cash_consideration_minor"] == purchase.cash_consideration_minor
    )
    assert (
        sum(row["projected_principal_minor"] for row in portal_holding["investment_schedule"])
        == purchase.assigned_principal_minor
    )
    activity = portal.get_investor_activity(actor=investor)
    assert any(
        item["activity_type"] == "originator_claim_purchase"
        and item["amount_minor"] == purchase.cash_consideration_minor
        for item in activity["entries"]
    )


@pytest.mark.django_db
def test_originator_repayment_preserves_dated_interest_and_batch_settles(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    today = business_date(timezone.now())
    first_due = today + timedelta(days=15)
    originator = create_loan_originator(
        CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name="Dated Entitlement Originator AG",
            public_name="Dated Entitlement Originator",
            registration_number="CHE-777.888.999",
            jurisdiction="CH",
            registered_address="Zurich, Switzerland",
            settlement_account_name="Dated Entitlement Originator AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference="KYB-DATED-001",
            status=LoanOriginatorStatus.ACTIVE,
        )
    )
    result = create_originator_loan(
        CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title="Mid-period assigned SME claim",
            investor_summary="Performing claim sold during an accrual period.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1200,
            target_yield_bps=800,
            distribution_model=OriginatorDistributionModel.LEGACY_YIELD_V1,
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=_dated_two_period_csv(today=today, include_payment=False),
            source_filename="dated-entitlement.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": "Confidential Dated Borrower AG",
                "borrower_display_name": "Swiss SME borrower",
            },
        )
    )
    publish_originator_loan(
        PublishOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today,
        )
    )
    ledger = import_module("backend.apps.ledger.services")
    ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=600_000,
            currency="CHF",
            booking_date=today,
            value_date=today,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Originator Investor",
            payer_account_identifier="CH9300762011623852957",
            bank_reference="DATED-ENTITLEMENT-DEPOSIT",
            payment_reference="DATED-ENTITLEMENT",
            idempotency_key="dated-entitlement-deposit",
        )
    )
    quote = create_originator_claim_quote(
        CreateOriginatorClaimQuoteCommand(
            actor=investor,
            loan_id=str(result.loan.id),
            requested_cash_minor=250_000,
        )
    )
    acceptance = _primary_acceptance(investor, quote_id=str(quote.id))
    code = issue_sensitive_action_test_code(investor, "primary_investment")
    purchase = purchase_originator_claim(
        PurchaseOriginatorClaimCommand(
            actor=investor,
            quote_id=str(quote.id),
            document_acceptance_id=str(acceptance.pk),
            sensitive_action_code_id=code.code_id,
            sensitive_action_code=code.raw_code,
            idempotency_key="dated-entitlement-purchase",
        )
    )

    repayment = record_originator_borrower_repayment(
        RecordOriginatorBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=_dated_two_period_csv(today=today, include_payment=True),
            source_filename="dated-entitlement-repayment.csv",
            as_of_date=first_due,
            payment_reference="LO-PAY-1",
            booking_date=first_due,
            value_date=first_due,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Confidential Dated Borrower AG",
            bank_reference="LO-PAY-1-BANK",
            bank_payment_reference="LO-PAY-1",
            evidence_reference="BANK-STMT-LO-PAY-1",
            notes="First contractual repayment.",
            idempotency_key="dated-entitlement-repayment-1",
        )
    )
    line = InvestorOriginatorRepaymentDistributionLine.objects.get(repayment=repayment)
    expected_interest = (
        2 * 10_000 * purchase.assigned_principal_minor * 15 + (1_000_000 * 30)
    ) // (2 * 1_000_000 * 30)
    assert line.interest_minor == expected_interest
    assert repayment.investor_distributed_minor + repayment.originator_payable_minor == 510_000
    assert (
        OriginatorLoanProfile.objects.get(id=result.profile.id).current_outstanding_principal_minor
        == 500_000
    )
    purchase.refresh_from_db()
    assert purchase.holding.current_principal_minor == (
        purchase.assigned_principal_minor - line.principal_minor
    )
    repayment_email = OutboxMessage.objects.get(topic="email.originator_claim_repayment_credited")
    assert repayment_email.payload["metadata"]["repayment_id"] == str(repayment.id)
    assert repayment_email.payload["metadata"]["amount_minor"] == line.amount_minor
    assert "originator_payable_minor" not in repayment_email.payload["metadata"]

    reporting = import_module("backend.apps.reporting.services")
    tax_artifact = reporting.generate_investor_self_service_report(
        reporting.GenerateInvestorSelfServiceReportCommand(
            actor=investor,
            report_type="annual_tax_information",
            start_date=today,
            end_date=first_due,
            output_format="csv",
        )
    )
    tax_rows = list(csv.DictReader(io.StringIO(tax_artifact.content)))
    tax_amounts = {row["category"]: int(row["amount_minor"]) for row in tax_rows}
    assert tax_amounts["originator_claim_interest_received_or_credited"] == line.interest_minor
    assert tax_amounts["originator_claim_principal_repaid"] == line.principal_minor
    assert tax_amounts["originator_claim_cash_consideration"] == purchase.cash_consideration_minor
    assert tax_amounts["originator_claim_principal_assigned"] == purchase.assigned_principal_minor

    queue = list_outstanding_originator_settlements(actor=admin_user)
    assert len(queue) == 1
    assert queue[0]["purchase_ids"] == [str(purchase.id)]
    assert queue[0]["repayment_ids"] == [str(repayment.id)]
    settlement = finalize_originator_settlement(
        FinalizeOriginatorSettlementCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            currency="CHF",
            purchase_ids=[str(purchase.id)],
            repayment_ids=[str(repayment.id)],
            booking_date=first_due,
            value_date=first_due,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            bank_reference="LO-SETTLEMENT-1",
            payment_reference="LO-SETTLEMENT-1",
            evidence_reference="BANK-STMT-LO-SETTLEMENT-1",
            notes="Purchase and servicing batch settlement.",
            idempotency_key="originator-combined-settlement-1",
        )
    )
    assert settlement.amount_minor == (
        settlement.purchase_amount_minor + settlement.servicing_amount_minor
    )
    assert OriginatorSettlementPurchase.objects.filter(settlement=settlement).count() == 1
    assert OriginatorSettlementRepayment.objects.filter(settlement=settlement).count() == 1
    assert list_outstanding_originator_settlements(actor=admin_user) == []


@pytest.mark.django_db
def test_originator_claim_resale_preserves_entitlement_and_pays_current_holder(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    today = business_date(timezone.now())
    first_due = today + timedelta(days=15)
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix="RESALE",
    )
    _declare_originator_test_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=600_000,
        today=today,
        suffix="RESALE-SELLER",
    )
    quote = create_originator_claim_quote(
        CreateOriginatorClaimQuoteCommand(
            actor=investor,
            loan_id=str(result.loan.id),
            requested_cash_minor=250_000,
        )
    )
    primary_acceptance = _primary_acceptance(investor, quote_id=str(quote.id))
    primary_code = issue_sensitive_action_test_code(investor, "primary_investment")
    primary_purchase = purchase_originator_claim(
        PurchaseOriginatorClaimCommand(
            actor=investor,
            quote_id=str(quote.id),
            document_acceptance_id=str(primary_acceptance.pk),
            sensitive_action_code_id=primary_code.code_id,
            sensitive_action_code=primary_code.raw_code,
            idempotency_key="originator-resale-primary-purchase",
        )
    )
    entitlement_start = primary_purchase.holding.economic_entitlement_start_at
    secondary = import_module("backend.apps.secondary_market.services")
    listing_acceptance = _secondary_acceptance(
        investor,
        category="secondary_market_listing",
        context_type="secondary_market_listing",
        context_id=str(primary_purchase.holding_id),
        suffix="resale-listing",
    )
    listing_code = issue_sensitive_action_test_code(
        investor,
        "secondary_market_listing",
    )
    listing = secondary.create_secondary_market_listing(
        secondary.CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(primary_purchase.holding_id),
            price_bps=10_000,
            document_acceptance_id=str(listing_acceptance.pk),
            sensitive_action_code_id=listing_code.code_id,
            sensitive_action_code=listing_code.raw_code,
            idempotency_key="originator-resale-listing",
        )
    )
    _declare_originator_test_deposit(
        admin_user=admin_user,
        investor=other_investor,
        amount_minor=1_000_000,
        today=today,
        suffix="RESALE-BUYER",
    )
    purchase_acceptance = _secondary_acceptance(
        other_investor,
        category="secondary_market_purchase",
        context_type="secondary_market_purchase",
        context_id=str(listing.id),
        suffix="resale-purchase",
    )
    purchase_code = issue_sensitive_action_test_code(
        other_investor,
        "secondary_market_purchase",
    )
    resale = secondary.purchase_secondary_market_listing(
        secondary.PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            sensitive_action_code_id=purchase_code.code_id,
            sensitive_action_code=purchase_code.raw_code,
            idempotency_key="originator-resale-purchase",
        )
    )

    primary_purchase.holding.refresh_from_db()
    resale.buyer_holding.refresh_from_db()
    assert primary_purchase.holding.status == "transferred"
    assert primary_purchase.holding.current_principal_minor == 0
    assert resale.buyer_holding.economic_entitlement_start_at == entitlement_start
    assert resale.metadata["buyer_projected_yield_bps"] > 0
    assert "target_yield_bps" not in resale.metadata

    repayment = record_originator_borrower_repayment(
        RecordOriginatorBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=_dated_two_period_csv(today=today, include_payment=True),
            source_filename="originator-resale-repayment.csv",
            as_of_date=first_due,
            payment_reference="LO-PAY-1",
            booking_date=first_due,
            value_date=first_due,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Confidential Borrower RESALE AG",
            bank_reference="ORIGINATOR-RESALE-REPAYMENT",
            bank_payment_reference="LO-PAY-1",
            evidence_reference="BANK-STMT-ORIGINATOR-RESALE",
            notes="First payment after a secondary-market transfer.",
            idempotency_key="originator-resale-repayment",
        )
    )
    lines = list(InvestorOriginatorRepaymentDistributionLine.objects.filter(repayment=repayment))
    assert len(lines) == 1
    assert str(lines[0].investor_user_id) == str(other_investor.pk)
    assert str(lines[0].holding_id) == str(resale.buyer_holding_id)
    assert not InvestorOriginatorRepaymentDistributionLine.objects.filter(
        repayment=repayment,
        investor_user_id=investor.pk,
    ).exists()

    result.loan.status = "late"
    result.loan.save(update_fields=["status", "updated_at"])
    impaired_acceptance = _secondary_acceptance(
        other_investor,
        category="secondary_market_listing",
        context_type="secondary_market_listing",
        context_id=str(resale.buyer_holding_id),
        suffix="impaired-resale-listing",
    )
    impaired_code = issue_sensitive_action_test_code(
        other_investor,
        "secondary_market_listing",
    )
    with pytest.raises(
        secondary.SecondaryMarketValidationError,
        match="Late or defaulted Loan Originator claims",
    ):
        secondary.create_secondary_market_listing(
            secondary.CreateSecondaryMarketListingCommand(
                actor=other_investor,
                holding_id=str(resale.buyer_holding_id),
                price_bps=10_000,
                document_acceptance_id=str(impaired_acceptance.pk),
                sensitive_action_code_id=impaired_code.code_id,
                sensitive_action_code=impaired_code.raw_code,
                idempotency_key="originator-impaired-resale-listing",
            )
        )


@pytest.mark.django_db
def test_direct_servicing_scanner_does_not_mutate_originator_loans(
    admin_user: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix="DIRECT-SCANNER",
    )
    servicing = import_module("backend.apps.servicing.services")
    scan_result = servicing.scan_loan_servicing_statuses(
        servicing.ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=today + timedelta(days=31),
            loan_ids=[str(result.loan.id)],
        )
    )
    result.loan.refresh_from_db()
    assert scan_result.changes == []
    assert result.loan.status == "active"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("days_after_first_due", "expected_status", "expected_close_reason"),
    [
        (4, "active", ""),
        (5, "late", "loan_status_late"),
        (16, "defaulted", "loan_status_defaulted"),
    ],
)
def test_originator_lifecycle_scan_uses_day_5_and_day_16_boundaries(
    admin_user: Model,
    days_after_first_due: int,
    expected_status: str,
    expected_close_reason: str,
) -> None:
    today = business_date(timezone.now())
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix=f"DPD-{days_after_first_due}",
    )
    as_of_date = today + timedelta(days=15 + days_after_first_due)
    closed = scan_originator_opportunity_lifecycle(
        actor=admin_user,
        as_of_date=as_of_date,
    )
    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert result.loan.status == expected_status
    if expected_close_reason:
        assert result.profile.opportunity_status == OriginatorOpportunityStatus.CLOSED
        assert result.profile.close_reason == expected_close_reason
        assert closed == [{"loan_id": str(result.loan.id), "reason": expected_close_reason}]
    else:
        assert result.profile.opportunity_status == OriginatorOpportunityStatus.OPEN
        assert closed == []


@pytest.mark.django_db
def test_quote_at_30_day_boundary_persists_opportunity_closure(
    admin_user: Model,
    investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approve_financial_access(investor)
    today = business_date(timezone.now())
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix="MATURITY-CLOSE",
        final_due_days=31,
    )
    services = import_module("backend.apps.originator_claims.services")
    monkeypatch.setattr(services, "now_utc", lambda: timezone.now() + timedelta(days=1))

    with pytest.raises(OriginatorClaimsValidationError, match="30 days or less"):
        create_originator_claim_quote(
            CreateOriginatorClaimQuoteCommand(
                actor=investor,
                loan_id=str(result.loan.id),
                requested_cash_minor=200_000,
            )
        )

    result.profile.refresh_from_db()
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.CLOSED
    assert result.profile.close_reason == "maturity_within_30_days"


@pytest.mark.django_db
def test_stale_originator_loan_id_returns_domain_validation(admin_user: Model) -> None:
    with pytest.raises(OriginatorClaimsValidationError, match="does not exist"):
        publish_originator_loan(
            PublishOriginatorLoanCommand(
                actor=admin_user,
                loan_id=str(uuid.uuid4()),
                as_of_date=business_date(timezone.now()),
            )
        )


@pytest.mark.django_db
def test_full_originator_repayment_closes_claim_without_nulling_shared_dates(
    admin_user: Model,
) -> None:
    today = business_date(timezone.now())
    first_due = today + timedelta(days=15)
    second_due = today + timedelta(days=45)
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix="FULL-PAYOFF",
        final_due_days=45,
    )
    original_first_payment_date = result.loan.first_payment_date
    first = record_originator_borrower_repayment(
        RecordOriginatorBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=_dated_two_period_csv(today=today, include_payment=True),
            source_filename="full-payoff-first.csv",
            as_of_date=first_due,
            payment_reference="LO-PAY-1",
            booking_date=first_due,
            value_date=first_due,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Confidential Borrower FULL-PAYOFF AG",
            bank_reference="FULL-PAYOFF-1",
            bank_payment_reference="LO-PAY-1",
            evidence_reference="BANK-FULL-PAYOFF-1",
            notes="First contractual repayment.",
            idempotency_key="originator-full-payoff-1",
        )
    )
    assert first.principal_after_minor == 500_000
    second = record_originator_borrower_repayment(
        RecordOriginatorBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=_dated_two_period_csv(
                today=today,
                include_payment=True,
                include_final_payment=True,
            ),
            source_filename="full-payoff-final.csv",
            as_of_date=second_due,
            payment_reference="LO-PAY-2",
            booking_date=second_due,
            value_date=second_due,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Confidential Borrower FULL-PAYOFF AG",
            bank_reference="FULL-PAYOFF-2",
            bank_payment_reference="LO-PAY-2",
            evidence_reference="BANK-FULL-PAYOFF-2",
            notes="Final contractual repayment.",
            idempotency_key="originator-full-payoff-2",
        )
    )
    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert second.principal_after_minor == 0
    assert result.loan.status == "repaid"
    assert result.loan.first_payment_date == original_first_payment_date
    assert result.profile.current_outstanding_principal_minor == 0
    assert result.profile.unsold_principal_minor == 0
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.CLOSED


@pytest.mark.django_db
def test_originator_settlement_task_appears_after_three_calendar_days(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    today = business_date(timezone.now())
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix="TASK",
    )
    ledger = import_module("backend.apps.ledger.services")
    ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=300_000,
            currency="CHF",
            booking_date=today,
            value_date=today,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Originator Investor",
            payer_account_identifier="CH9300762011623852957",
            bank_reference="ORIGINATOR-TASK-DEPOSIT",
            payment_reference="ORIGINATOR-TASK",
            idempotency_key="originator-task-deposit",
        )
    )
    quote = create_originator_claim_quote(
        CreateOriginatorClaimQuoteCommand(
            actor=investor,
            loan_id=str(result.loan.id),
            requested_cash_minor=200_000,
        )
    )
    acceptance = _primary_acceptance(investor, quote_id=str(quote.id))
    code = issue_sensitive_action_test_code(investor, "primary_investment")
    purchase = purchase_originator_claim(
        PurchaseOriginatorClaimCommand(
            actor=investor,
            quote_id=str(quote.id),
            document_acceptance_id=str(acceptance.pk),
            sensitive_action_code_id=code.code_id,
            sensitive_action_code=code.raw_code,
            idempotency_key="originator-task-purchase",
        )
    )
    assert (
        sync_originator_settlement_tasks(
            actor=admin_user,
            as_of=purchase.purchased_at + timedelta(days=2, hours=23),
        )
        == []
    )
    tasks = sync_originator_settlement_tasks(
        actor=admin_user,
        as_of=purchase.purchased_at + timedelta(days=3),
    )
    assert len(tasks) == 1
    assert tasks[0].task_type == "originator_settlement"
    assert tasks[0].due_at == purchase.purchased_at + timedelta(days=5)


@pytest.mark.django_db
def test_skin_in_the_game_caps_sellable_claim_and_survives_repricing(
    admin_user: Model,
    investor: Model,
) -> None:
    from backend.apps.originator_claims.services import (
        originator_marketplace_payload,
        originator_retained_principal_minor,
        originator_sellable_principal_minor,
    )

    today = business_date(timezone.now())
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix="SKIN",
        skin_in_the_game_bps=2_000,
    )
    profile = OriginatorLoanProfile.objects.get(id=result.profile.id)

    assert int(result.loan.skin_in_the_game_bps) == 2_000
    assert originator_retained_principal_minor(profile) == 200_000
    assert originator_sellable_principal_minor(profile) == 800_000

    payload = originator_marketplace_payload(profile, include_detail=True)
    assert payload["skin_in_the_game_bps"] == 2_000
    assert payload["remaining_capacity_minor"] == 800_000

    _approve_financial_access(investor)
    quote = create_originator_claim_quote(
        CreateOriginatorClaimQuoteCommand(
            actor=investor,
            loan_id=str(result.loan.id),
            requested_cash_minor=2_000_000,
        )
    )
    assert quote.assigned_principal_minor <= 800_000

    admin_payload = get_originator_admin_loan_payload(actor=admin_user, loan_id=str(result.loan.id))
    assert admin_payload["skin_in_the_game_bps"] == 2_000
    assert admin_payload["retained_principal_minor"] == 200_000
    assert admin_payload["sellable_principal_minor"] == 800_000

    # Once unsold principal reaches the retained floor nothing more can be sold.
    profile.unsold_principal_minor = 200_000
    profile.save(update_fields=["unsold_principal_minor"])
    assert originator_sellable_principal_minor(profile) == 0
    with pytest.raises(OriginatorClaimsValidationError):
        originator_marketplace_payload(profile, include_detail=False)

    profile.unsold_principal_minor = 199_999
    profile.save(update_fields=["unsold_principal_minor"])
    with pytest.raises(
        OriginatorClaimsValidationError,
        match="below the declared skin-in-the-game floor",
    ):
        originator_sellable_principal_minor(profile)


@pytest.mark.django_db
def test_skin_in_the_game_rejects_invalid_declarations(admin_user: Model) -> None:
    for invalid in (True, 2.5, "2000", 10_000):
        with pytest.raises(OriginatorClaimsValidationError):
            _skin_bps(invalid)

    today = business_date(timezone.now())
    with pytest.raises(OriginatorClaimsValidationError):
        _create_dated_originator_loan(
            admin_user=admin_user,
            today=today,
            suffix="SKINBAD",
            skin_in_the_game_bps=10_000,
        )


def test_skin_in_the_game_repayment_rounding_preserves_retained_floor() -> None:
    entitlement_start = timezone.now()
    holding = SimpleNamespace(
        investor_user_id="rounding-investor",
        current_principal_minor=8_000,
        economic_entitlement_start_at=entitlement_start,
        assignment_effective_at=entitlement_start,
    )

    plan, originator_components = _originator_repayment_plan(
        holdings=[holding],
        originator_principal_minor=2_000,
        skin_in_the_game_bps=2_000,
        principal_minor=3,
        interest_minor=0,
        penalty_minor=0,
        value_date=entitlement_start.date(),
        accrual_start_date=entitlement_start.date(),
        currency="CHF",
    )

    assert plan[0].principal_minor == 3
    assert originator_components["principal_minor"] == 0
    retained_after_minor = -(-(9_997 * 2_000) // 10_000)
    assert 2_000 - originator_components["principal_minor"] == retained_after_minor


def test_originator_interest_entitlement_uses_zurich_business_date() -> None:
    entitlement_start = datetime(2026, 8, 7, 22, 1, tzinfo=UTC)
    holding = SimpleNamespace(
        investor_user_id="midnight-investor",
        current_principal_minor=250_000,
        economic_entitlement_start_at=entitlement_start,
        assignment_effective_at=entitlement_start,
    )

    plan, originator_components = _originator_repayment_plan(
        holdings=[holding],
        originator_principal_minor=750_000,
        skin_in_the_game_bps=0,
        principal_minor=0,
        interest_minor=10_000,
        penalty_minor=0,
        value_date=date(2026, 8, 23),
        accrual_start_date=date(2026, 8, 8),
        currency="CHF",
    )

    assert plan[0].interest_minor == 2_500
    assert originator_components["interest_minor"] == 7_500


@pytest.mark.django_db
def test_originator_repayment_rejects_csv_split_that_pays_principal_before_interest(
    admin_user: Model,
) -> None:
    today = business_date(timezone.now())
    first_due = today + timedelta(days=15)
    result = _create_dated_originator_loan(
        admin_user=admin_user,
        today=today,
        suffix="WATERFALL",
    )
    conflicting_csv = _dated_two_period_csv(today=today, include_payment=True).replace(
        "regular,,500000,10000,0,0,510000,,500000",
        "regular,,500000,0,0,10000,510000,,500000",
    )

    with pytest.raises(
        OriginatorClaimsValidationError,
        match="violates the universal payment waterfall",
    ):
        record_originator_borrower_repayment(
            RecordOriginatorBorrowerRepaymentCommand(
                actor=admin_user,
                loan_id=str(result.loan.id),
                csv_content=conflicting_csv,
                source_filename="waterfall-conflict.csv",
                as_of_date=first_due,
                payment_reference="LO-PAY-1",
                booking_date=first_due,
                value_date=first_due,
                collection_account_identifier="CH11 83019 GARANTAFI001",
                payer_name="Confidential Borrower WATERFALL AG",
                idempotency_key="originator-waterfall-conflict",
            )
        )


def test_originator_waterfall_applies_costs_penalty_and_interest_before_principal() -> None:
    value_date = date(2026, 8, 5)
    schedule_rows = [
        SimpleNamespace(
            accrual_start_date=date(2026, 7, 5),
            due_date=value_date,
            installment_number=1,
            fee_minor=300,
            penalty_minor=200,
            interest_minor=100,
            principal_minor=1_000,
        )
    ]
    loan_import = cast(
        OriginatorLoanImport,
        SimpleNamespace(
            schedule_rows=SimpleNamespace(order_by=lambda *_args: schedule_rows),
            payment_rows=SimpleNamespace(order_by=lambda *_args: []),
        ),
    )
    valid_payment = SimpleNamespace(
        value_date=value_date,
        payment_type="regular",
        total_minor=550,
        fee_minor=300,
        penalty_minor=200,
        interest_minor=50,
        principal_minor=0,
    )

    allocation = _originator_payment_waterfall(
        loan_import=loan_import,
        payment=valid_payment,
        outstanding_principal_minor=1_000,
    )
    assert (
        allocation.costs_minor,
        allocation.penalty_minor,
        allocation.interest_minor,
        allocation.principal_minor,
    ) == (300, 200, 50, 0)

    invalid_payment = SimpleNamespace(
        **{
            **vars(valid_payment),
            "interest_minor": 0,
            "principal_minor": 50,
        }
    )
    with pytest.raises(
        OriginatorClaimsValidationError,
        match="violates the universal payment waterfall",
    ):
        _originator_payment_waterfall(
            loan_import=loan_import,
            payment=invalid_payment,
            outstanding_principal_minor=1_000,
        )


@pytest.mark.django_db
def test_par_subscription_reserves_then_activates_at_par_with_component_rights(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="ACTIVATE",
    )
    order = _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=160_000,
        suffix="ACTIVATE",
    )
    holding_model = import_module("backend.apps.holdings.models").InvestorLoanHolding
    ledger_models = import_module("backend.apps.ledger.models")

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert result.loan.status == "published"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.OPEN
    assert order.status == "balance_allocated"
    assert OriginatorClaimPurchase.objects.filter(loan_profile=result.profile).count() == 0
    assert holding_model.objects.filter(loan=result.loan).count() == 0
    assert not ledger_models.LedgerAccount.objects.filter(
        account_type="originator_settlement_payable",
        owner_id=str(result.profile.originator_id),
    ).exists()

    close = close_originator_subscription_round(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today + timedelta(days=6),
            close_reason="Funding deadline reached.",
            idempotency_key="subscription-activate-close",
        )
    )
    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert close.subscribed_principal_minor == 160_000
    assert result.loan.status == "funded"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.AWAITING_ACTIVATION
    assert (
        import_module("backend.apps.admin_ops.models")
        .AdminTask.objects.filter(
            task_type="loan_setup",
            related_object_type="OriginatorSubscriptionActivationPending",
            related_object_id=str(result.loan.id),
            status="open",
        )
        .exists()
    )
    assert OutboxMessage.objects.filter(
        topic="email.originator_subscription_awaiting_activation"
    ).exists()

    boundary_date = today + timedelta(days=10)
    activation = activate_originator_subscription(
        ActivateOriginatorSubscriptionCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=_par_subscription_csv(today=today, include_boundary_payment=True),
            source_filename="subscription-activation.csv",
            as_of_date=boundary_date,
            boundary_payment_reference="BOUNDARY-1",
            boundary_payment_date=boundary_date,
            notes="Verified boundary installment received by the originator.",
            idempotency_key="subscription-activate",
        )
    )
    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    order.refresh_from_db()
    purchase = OriginatorClaimPurchase.objects.get(loan_profile=result.profile)
    holding = holding_model.objects.get(loan=result.loan, investor_user_id=investor.pk)
    entitlements = list(
        OriginatorClaimEntitlement.objects.filter(purchase=purchase).order_by("due_date")
    )

    assert isinstance(activation, OriginatorSubscriptionActivation)
    assert activation.assigned_principal_minor == 160_000
    assert activation.originator_retained_principal_minor == 640_000
    assert result.loan.status == "active"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.ACTIVE
    assert result.profile.unsold_principal_minor == 640_000
    assert order.status == "closed_invested"
    assert purchase.cash_consideration_minor == purchase.assigned_principal_minor == 160_000
    assert holding.current_principal_minor == 160_000
    assert business_date(holding.economic_entitlement_start_at) == boundary_date
    assert len(entitlements) == 2
    assert (
        entitlements[0].expected_principal_minor,
        entitlements[0].expected_interest_minor,
        entitlements[0].expected_penalty_minor,
    ) == (80_000, 14_000, 4_000)
    postings = list(
        activation.activation_journal_entry.postings.select_related("account").order_by("side")
    )
    assert {
        (posting.account.account_type, posting.side, posting.amount_minor) for posting in postings
    } == {
        ("loan_funding_escrow", "debit", 160_000),
        ("originator_settlement_payable", "credit", 160_000),
    }


@pytest.mark.django_db
def test_par_subscription_actual_repayment_uses_component_participation(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="REPAYMENT",
    )
    _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=160_000,
        suffix="REPAYMENT",
    )
    _activate_par_subscription_for_test(
        admin_user=admin_user,
        result=result,
        today=today,
        suffix="repayment",
    )

    second_due = today + timedelta(days=40)
    repayment = record_originator_borrower_repayment(
        RecordOriginatorBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            csv_content=_par_subscription_csv(
                today=today,
                include_boundary_payment=True,
                include_second_payment=True,
            ),
            source_filename="subscription-repayment.csv",
            as_of_date=second_due,
            payment_reference="SUBSCRIPTION-PAY-2",
            booking_date=second_due,
            value_date=second_due,
            collection_account_identifier="CH11 83019 GARANTAFI001",
            payer_name="Subscription Borrower REPAYMENT AG",
            bank_reference="SUBSCRIPTION-PAY-2-BANK",
            bank_payment_reference="SUBSCRIPTION-PAY-2",
            evidence_reference="BANK-STMT-SUBSCRIPTION-PAY-2",
            notes="First investor-entitled installment.",
            idempotency_key="subscription-repayment-record",
        )
    )

    distribution = InvestorOriginatorRepaymentDistributionLine.objects.get(
        repayment=repayment,
        investor_user_id=investor.pk,
    )
    assert (
        distribution.principal_minor,
        distribution.interest_minor,
        distribution.penalty_minor,
        distribution.amount_minor,
    ) == (80_000, 14_000, 4_000, 98_000)
    assert repayment.originator_payable_minor == 442_000
    assert repayment.investor_distributed_minor == 98_000
    assert repayment.platform_costs_minor == 0
    assert (
        repayment.investor_distributed_minor
        + repayment.originator_payable_minor
        + repayment.platform_costs_minor
        == repayment.amount_minor
        == 540_000
    )

    distribution.holding.refresh_from_db()
    result.profile.refresh_from_db()
    result.loan.refresh_from_db()
    assert distribution.holding.current_principal_minor == 80_000
    assert result.profile.current_outstanding_principal_minor == 400_000
    assert result.profile.unsold_principal_minor == 320_000
    assert result.loan.committed_principal_minor == 80_000

    postings = list(repayment.journal_entry.postings.select_related("account"))
    debit_total = sum(posting.amount_minor for posting in postings if posting.side == "debit")
    credit_total = sum(posting.amount_minor for posting in postings if posting.side == "credit")
    assert debit_total == credit_total == 540_000
    assert {
        (posting.account.account_type, posting.side, posting.amount_minor) for posting in postings
    } == {
        ("collection_cash", "debit", 540_000),
        ("investor_balance_liability", "credit", 98_000),
        ("originator_servicing_payable", "credit", 442_000),
    }


@pytest.mark.django_db
def test_full_par_subscription_closes_automatically_without_creating_a_holding(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="FULL",
    )
    _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=800_000,
        suffix="FULL",
    )
    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert result.loan.status == "funded"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.AWAITING_ACTIVATION
    assert OriginatorFundingRoundClose.objects.filter(loan_profile=result.profile).exists()
    assert not OriginatorClaimPurchase.objects.filter(loan_profile=result.profile).exists()
    assert (
        not import_module("backend.apps.holdings.models")
        .InvestorLoanHolding.objects.filter(loan=result.loan)
        .exists()
    )


@pytest.mark.django_db
def test_full_par_subscription_idempotent_replay_recovers_missed_auto_close(
    admin_user: Model,
    investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="REPLAY-CLOSE",
    )
    marketplace = import_module("backend.apps.marketplace_primary.services")

    with monkeypatch.context() as patch:
        patch.setattr(
            marketplace,
            "_resolve_fully_subscribed_originator_round",
            lambda **_kwargs: None,
        )
        order = _allocate_par_subscription(
            admin_user=admin_user,
            investor=investor,
            loan=result.loan,
            today=today,
            amount_minor=800_000,
            suffix="REPLAY-CLOSE",
        )

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    order.refresh_from_db()
    assert result.loan.status == "published"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.OPEN
    assert order.status == "balance_allocated"
    assert not OriginatorFundingRoundClose.objects.filter(loan_profile=result.profile).exists()

    replayed = marketplace.allocate_primary_order_from_balance(
        marketplace.AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(order.document_acceptance_id),
            idempotency_key="subscription-REPLAY-CLOSE-allocate",
            sensitive_action_code_id="already-consumed-on-first-request",
            sensitive_action_code="already-consumed-on-first-request",
        )
    )

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert replayed.id == order.id
    assert result.loan.status == "funded"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.AWAITING_ACTIVATION
    assert OriginatorFundingRoundClose.objects.filter(loan_profile=result.profile).count() == 1


@pytest.mark.django_db
def test_batch_places_multiple_par_subscriptions_as_reserved_orders(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    first = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="BATCH-A",
    )
    second = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="BATCH-B",
    )
    _approve_financial_access(investor)
    _declare_originator_test_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=500_000,
        today=today,
        suffix="BATCH",
    )
    marketplace = import_module("backend.apps.marketplace_primary.services")
    items = [
        marketplace.PrimaryOrderBatchItemCommand(
            loan_id=str(first.loan.id),
            amount_minor=200_000,
        ),
        marketplace.PrimaryOrderBatchItemCommand(
            loan_id=str(second.loan.id),
            amount_minor=300_000,
        ),
    ]
    batch_key = "originator-v2-batch"
    acceptance = _primary_batch_acceptance(
        investor,
        batch_key=batch_key,
        items=[
            {
                "loan_id": item.loan_id,
                "amount_minor": item.amount_minor,
                "currency": "CHF",
            }
            for item in items
        ],
        suffix="BATCH",
    )
    code = issue_sensitive_action_test_code(investor, "primary_investment")

    placed = marketplace.place_primary_order_batch(
        marketplace.PlacePrimaryOrderBatchCommand(
            actor=investor,
            items=items,
            document_acceptance_id=str(acceptance.pk),
            sensitive_action_code_id=code.code_id,
            sensitive_action_code=code.raw_code,
            idempotency_key=batch_key,
        )
    )

    first.loan.refresh_from_db()
    second.loan.refresh_from_db()
    balance_lot = import_module("backend.apps.ledger.models").InvestorBalanceLot.objects.get(
        investor_user_id=investor.pk
    )
    assert len(placed.orders) == 2
    assert placed.originator_purchases == []
    assert all(order.status == "balance_allocated" for order in placed.orders)
    assert int(first.loan.committed_principal_minor) == 200_000
    assert int(second.loan.committed_principal_minor) == 300_000
    assert first.loan.status == "published"
    assert second.loan.status == "published"
    assert balance_lot.available_amount_minor == 0
    assert balance_lot.invested_amount_minor == 500_000
    assert not OriginatorFundingRoundClose.objects.exists()


@pytest.mark.django_db
def test_subscription_deadline_scan_closes_positive_round_without_releasing_reservations(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="DEADLINE-PARTIAL",
    )
    order = _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=200_000,
        suffix="DEADLINE-PARTIAL",
    )

    resolutions = scan_originator_opportunity_lifecycle(
        actor=admin_user,
        as_of_date=today + timedelta(days=6),
    )

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    order.refresh_from_db()
    balance_lot = import_module("backend.apps.ledger.models").InvestorBalanceLot.objects.get(
        investor_user_id=investor.pk
    )
    close = OriginatorFundingRoundClose.objects.get(loan_profile=result.profile)
    assert resolutions == [
        {"loan_id": str(result.loan.id), "reason": "funding_deadline_reached"}
    ]
    assert close.subscribed_principal_minor == 200_000
    assert result.loan.status == "funded"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.AWAITING_ACTIVATION
    assert order.status == "balance_allocated"
    assert balance_lot.available_amount_minor == 0
    assert balance_lot.invested_amount_minor == 200_000
    assert not import_module("backend.apps.holdings.models").InvestorLoanHolding.objects.exists()


@pytest.mark.django_db
def test_subscription_deadline_scan_cancels_empty_round(
    admin_user: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="DEADLINE-EMPTY",
    )

    resolutions = scan_originator_opportunity_lifecycle(
        actor=admin_user,
        as_of_date=today + timedelta(days=6),
    )

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    assert resolutions == [{"loan_id": str(result.loan.id), "reason": "no_subscriptions"}]
    assert result.loan.status == "cancelled"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.CANCELLED
    assert OriginatorSubscriptionCancellation.objects.filter(loan_profile=result.profile).exists()
    assert not OriginatorFundingRoundClose.objects.filter(loan_profile=result.profile).exists()


@pytest.mark.django_db
def test_full_par_subscription_close_failure_preserves_reservation_and_can_retry(
    admin_user: Model,
    investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="CLOSE-FAILURE",
    )
    originator_services = import_module("backend.apps.originator_claims.services")

    def fail_close(_command: object) -> object:
        raise RuntimeError("simulated originator activation-close failure")

    with monkeypatch.context() as patch:
        patch.setattr(originator_services, "close_originator_subscription_round", fail_close)
        order = _allocate_par_subscription(
            admin_user=admin_user,
            investor=investor,
            loan=result.loan,
            today=today,
            amount_minor=800_000,
            suffix="CLOSE-FAILURE",
        )

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    order.refresh_from_db()
    lot_model = import_module("backend.apps.ledger.models").InvestorBalanceLot
    lot = lot_model.objects.get(investor_user_id=investor.pk)
    task_model = import_module("backend.apps.admin_ops.models").AdminTask
    failure_task = task_model.objects.get(
        task_type="loan_setup",
        related_object_type="LoanFundingCloseFailure",
        related_object_id=str(result.loan.id),
    )
    alert = OutboxMessage.objects.get(topic="email.originator_funding_close_failed")

    assert result.loan.status == "funding_close_failed"
    assert result.loan.committed_principal_minor == 800_000
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.OPEN
    assert result.profile.is_on_hold is True
    assert order.status == "balance_allocated"
    assert lot.available_amount_minor == 0
    assert lot.invested_amount_minor == 800_000
    assert not OriginatorFundingRoundClose.objects.filter(loan_profile=result.profile).exists()
    assert failure_task.status == "open"
    assert alert.payload["email"] == "hq@banxum.com"

    close = close_originator_subscription_round(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today,
            close_reason="Resolved the automatic-close failure.",
            idempotency_key="subscription-close-failure-admin-retry",
        )
    )
    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    order.refresh_from_db()
    failure_task.refresh_from_db()
    lot.refresh_from_db()

    assert close.subscribed_principal_minor == 800_000
    assert result.loan.status == "funded"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.AWAITING_ACTIVATION
    assert result.profile.is_on_hold is False
    assert order.status == "balance_allocated"
    assert lot.available_amount_minor == 0
    assert lot.invested_amount_minor == 800_000
    assert failure_task.status == "resolved"


@pytest.mark.django_db
def test_failed_par_subscription_can_cancel_refund_and_resolve_failure_task(
    admin_user: Model,
    investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="CLOSE-FAILURE-CANCEL",
    )
    originator_services = import_module("backend.apps.originator_claims.services")

    def fail_close(_command: object) -> object:
        raise RuntimeError("simulated originator close failure before cancellation")

    with monkeypatch.context() as patch:
        patch.setattr(originator_services, "close_originator_subscription_round", fail_close)
        order = _allocate_par_subscription(
            admin_user=admin_user,
            investor=investor,
            loan=result.loan,
            today=today,
            amount_minor=800_000,
            suffix="CLOSE-FAILURE-CANCEL",
        )

    task_model = import_module("backend.apps.admin_ops.models").AdminTask
    failure_task = task_model.objects.get(
        task_type="loan_setup",
        related_object_type="LoanFundingCloseFailure",
        related_object_id=str(result.loan.id),
    )
    cancellation = cancel_originator_subscription(
        CancelOriginatorSubscriptionCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            reason="Automatic close could not be completed safely.",
            investor_message="Your reserved subscription balance was returned.",
            idempotency_key="subscription-close-failure-cancel",
        )
    )

    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    order.refresh_from_db()
    failure_task.refresh_from_db()
    lot = import_module("backend.apps.ledger.models").InvestorBalanceLot.objects.get(
        investor_user_id=investor.pk
    )

    assert cancellation.released_principal_minor == 800_000
    assert result.loan.status == "cancelled"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.CANCELLED
    assert result.profile.is_on_hold is False
    assert order.status == "balance_released"
    assert lot.available_amount_minor == 800_000
    assert lot.invested_amount_minor == 0
    assert failure_task.status == "resolved"


@pytest.mark.django_db
def test_par_subscription_cancellation_releases_reserved_balance(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="CANCEL",
    )
    order = _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=160_000,
        suffix="CANCEL",
    )
    close_originator_subscription_round(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today + timedelta(days=6),
            close_reason="Funding deadline reached.",
            idempotency_key="subscription-cancel-close",
        )
    )
    cancellation = cancel_originator_subscription(
        CancelOriginatorSubscriptionCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            reason="Boundary installment was not received.",
            investor_message="The subscription was cancelled and your reserved balance returned.",
            idempotency_key="subscription-cancel",
        )
    )
    result.loan.refresh_from_db()
    result.profile.refresh_from_db()
    order.refresh_from_db()
    lot = import_module("backend.apps.ledger.models").InvestorBalanceLot.objects.get(
        investor_user_id=investor.pk
    )
    assert isinstance(cancellation, OriginatorSubscriptionCancellation)
    assert cancellation.released_principal_minor == 160_000
    assert result.loan.status == "cancelled"
    assert result.profile.opportunity_status == OriginatorOpportunityStatus.CANCELLED
    assert order.status == "balance_released"
    assert lot.available_amount_minor == 160_000
    assert lot.invested_amount_minor == 0


@pytest.mark.django_db
def test_par_subscription_rejects_a_delayed_boundary_payment(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="LATEBOUNDARY",
    )
    _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=160_000,
        suffix="LATEBOUNDARY",
    )
    close_originator_subscription_round(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today + timedelta(days=6),
            close_reason="Funding deadline reached.",
            idempotency_key="subscription-late-boundary-close",
        )
    )
    delayed_date = today + timedelta(days=11)

    with pytest.raises(
        OriginatorClaimsValidationError,
        match="delayed or changed payment requires subscription cancellation",
    ):
        activate_originator_subscription(
            ActivateOriginatorSubscriptionCommand(
                actor=admin_user,
                loan_id=str(result.loan.id),
                csv_content=_par_subscription_csv(today=today, include_boundary_payment=True),
                source_filename="subscription-late-boundary.csv",
                as_of_date=delayed_date,
                boundary_payment_reference="BOUNDARY-1",
                boundary_payment_date=delayed_date,
                notes="Boundary installment arrived one day late.",
                idempotency_key="subscription-late-boundary-activate",
            )
        )


@pytest.mark.django_db
def test_par_subscription_hold_blocks_investment_and_remains_cancellable(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="OPENHOLD",
    )
    _approve_financial_access(investor)
    held = place_originator_loan_on_hold(
        HoldOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            reason="Schedule evidence needs review.",
        )
    )
    assert held.is_on_hold is True
    assert held.opportunity_status == OriginatorOpportunityStatus.OPEN

    marketplace = import_module("backend.apps.marketplace_primary.services")
    with pytest.raises(
        marketplace.MarketplacePrimaryValidationError,
        match="administrative hold",
    ):
        marketplace.create_primary_investment_order(
            marketplace.CreatePrimaryInvestmentOrderCommand(
                actor=investor,
                loan_id=str(result.loan.id),
                amount_minor=100_000,
                idempotency_key="subscription-open-hold-order",
            )
        )
    with pytest.raises(OriginatorClaimsValidationError, match="held originator funding round"):
        close_originator_subscription_round(
            CloseOriginatorSubscriptionRoundCommand(
                actor=admin_user,
                loan_id=str(result.loan.id),
                as_of_date=today + timedelta(days=6),
                close_reason="Cannot close while held.",
                idempotency_key="subscription-open-hold-close",
            )
        )

    cancellation = cancel_originator_subscription(
        CancelOriginatorSubscriptionCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            reason="Schedule evidence was not resolved.",
            investor_message="The subscription was cancelled.",
            idempotency_key="subscription-open-hold-cancel",
        )
    )
    result.loan.refresh_from_db()
    assert cancellation.released_principal_minor == 0
    assert result.loan.status == "cancelled"


@pytest.mark.django_db
def test_par_subscription_hold_blocks_activation_and_allows_refund(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="ACTIVATIONHOLD",
    )
    order = _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=160_000,
        suffix="ACTIVATIONHOLD",
    )
    close_originator_subscription_round(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today + timedelta(days=6),
            close_reason="Funding deadline reached.",
            idempotency_key="subscription-activation-hold-close",
        )
    )
    place_originator_loan_on_hold(
        HoldOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            reason="Boundary payment evidence needs review.",
        )
    )
    boundary_date = today + timedelta(days=10)
    with pytest.raises(OriginatorClaimsValidationError, match="cannot be activated"):
        activate_originator_subscription(
            ActivateOriginatorSubscriptionCommand(
                actor=admin_user,
                loan_id=str(result.loan.id),
                csv_content=_par_subscription_csv(today=today, include_boundary_payment=True),
                source_filename="subscription-activation-hold.csv",
                as_of_date=boundary_date,
                boundary_payment_reference="BOUNDARY-1",
                boundary_payment_date=boundary_date,
                notes="Should remain blocked.",
                idempotency_key="subscription-activation-hold-activate",
            )
        )

    cancellation = cancel_originator_subscription(
        CancelOriginatorSubscriptionCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            reason="Boundary evidence could not be resolved.",
            investor_message="Your reserved balance was returned.",
            idempotency_key="subscription-activation-hold-cancel",
        )
    )
    order.refresh_from_db()
    lot = import_module("backend.apps.ledger.models").InvestorBalanceLot.objects.get(
        investor_user_id=investor.pk
    )
    assert cancellation.released_principal_minor == 160_000
    assert order.status == "balance_released"
    assert lot.available_amount_minor == 160_000


@pytest.mark.django_db
def test_par_subscription_lifecycle_evidence_is_append_only(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    today = business_date(timezone.now())
    activated_result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="APPEND-ACTIVE",
    )
    _allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=activated_result.loan,
        today=today,
        amount_minor=160_000,
        suffix="APPEND-ACTIVE",
    )
    activation = _activate_par_subscription_for_test(
        admin_user=admin_user,
        result=activated_result,
        today=today,
        suffix="append-active",
    )
    close = OriginatorFundingRoundClose.objects.get(loan_profile=activated_result.profile)

    cancelled_result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="APPEND-CANCEL",
    )
    _allocate_par_subscription(
        admin_user=admin_user,
        investor=other_investor,
        loan=cancelled_result.loan,
        today=today,
        amount_minor=160_000,
        suffix="APPEND-CANCEL",
    )
    close_originator_subscription_round(
        CloseOriginatorSubscriptionRoundCommand(
            actor=admin_user,
            loan_id=str(cancelled_result.loan.id),
            as_of_date=today + timedelta(days=6),
            close_reason="Funding deadline reached.",
            idempotency_key="subscription-append-cancel-close",
        )
    )
    cancellation = cancel_originator_subscription(
        CancelOriginatorSubscriptionCommand(
            actor=admin_user,
            loan_id=str(cancelled_result.loan.id),
            reason="Boundary installment was not received.",
            investor_message="Reserved balance was returned.",
            idempotency_key="subscription-append-cancel",
        )
    )

    guarded_records = [
        (close, OriginatorFundingRoundClose, "originator_claims_originatorfundingroundclose"),
        (
            activation,
            OriginatorSubscriptionActivation,
            "originator_claims_originatorsubscriptionactivation",
        ),
        (
            cancellation,
            OriginatorSubscriptionCancellation,
            "originator_claims_originatorsubscriptioncancellation",
        ),
    ]
    for record, model, table in guarded_records:
        record_id = record.pk
        db_record_id = record_id.hex
        with pytest.raises(AppendOnlyViolation):
            record.save()
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).update(id=record_id)
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).delete()
        with pytest.raises(DatabaseError) as update_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {table} SET id = %s WHERE id = %s",
                    [db_record_id, db_record_id],
                )
        assert "append-only" in str(update_error.value)
        with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE id = %s", [db_record_id])
        assert "append-only" in str(delete_error.value)


@pytest.mark.django_db
def test_par_subscription_rejects_quotes_and_secondary_market_premiums(
    admin_user: Model,
    investor: Model,
) -> None:
    today = business_date(timezone.now())
    _approve_financial_access(investor)
    result = _create_par_subscription_loan(
        admin_user=admin_user,
        today=today,
        suffix="POLICY",
    )
    with pytest.raises(OriginatorClaimsValidationError, match="funding subscription"):
        create_originator_claim_quote(
            CreateOriginatorClaimQuoteCommand(
                actor=investor,
                loan_id=str(result.loan.id),
                requested_cash_minor=100_000,
            )
        )
    secondary = import_module("backend.apps.secondary_market.services")
    with pytest.raises(secondary.SecondaryMarketValidationError, match="not at a premium"):
        secondary._validate_loan_listing_price(result.loan, 10_001)
    secondary._validate_loan_listing_price(result.loan, 10_000)
