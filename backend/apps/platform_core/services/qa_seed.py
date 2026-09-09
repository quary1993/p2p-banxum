"""Opt-in synthetic QA setup, never part of application startup."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from importlib import import_module
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction

from backend.apps.platform_core.domain.access import is_superadmin_actor
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.services.qa_guard import qa_environment_guard

SEED_KEY = "banxum-qa-start-v1"
INVESTOR_EMAIL = "qa.investor@banxum.example.test"


def seed_qa_starting_point(*, actor: Any) -> dict[str, Any]:
    if settings.IS_PRODUCTION or settings.ENVIRONMENT not in {"local", "staging", "test"}:
        raise ValueError("The QA starting point is forbidden in production.")
    if settings.COMMUNICATIONS_EMAIL_PROVIDER != "mock":
        raise ValueError("Set COMMUNICATIONS_EMAIL_PROVIDER=mock before seeding QA data.")
    if not is_superadmin_actor(actor):
        raise ValueError("An active superadmin must run the QA seed.")
    with qa_environment_guard(exclusive=True), transaction.atomic():
        return _seed(actor=actor)


def _seed(*, actor: Any) -> dict[str, Any]:
    entities = import_module("backend.apps.entities.services")
    loans = import_module("backend.apps.loans.services")
    ledger = import_module("backend.apps.ledger.services")
    kyc = import_module("backend.apps.kyc_compliance.services")
    docs = import_module("backend.apps.documents.services")
    primary = import_module("backend.apps.marketplace_primary.services")
    auth = import_module("backend.apps.accounts_auth.services")
    originators = import_module("backend.apps.originator_claims.services")
    today = business_date(now_utc())
    call_command("seed_reference_data", verbosity=0)
    user_model = get_user_model()
    investor = user_model.objects.filter(email=INVESTOR_EMAIL).first()
    if investor is None:
        investor = user_model.objects.create_user(
            email=INVESTOR_EMAIL,
            full_name="QA Synthetic Investor",
            password=None,
            account_type="natural_person_lender",
            status="active",
            phone_verified_at=now_utc(),
        )
        case = kyc.get_or_create_user_kyc_case(investor)
        for decision in ("reopen", "approve"):
            kyc.record_manual_review_decision(
                kyc.ManualReviewDecisionCommand(
                    actor=actor,
                    case_id=str(case.pk),
                    decision=decision,
                    reason_code="other",
                    note="Synthetic QA identity, not a real KYC approval.",
                    evidence_summary=SEED_KEY,
                )
            )
    elif investor.full_name != "QA Synthetic Investor" or investor.is_staff:
        raise ValueError("QA investor identifier is occupied by a non-seed account.")
    for currency in ("CHF", "EUR"):
        key = f"{SEED_KEY}:deposit:{currency}"
        if (
            not apps.get_model("ledger", "BankOperation")
            .objects.filter(idempotency_key=key)
            .exists()
        ):
            ledger.declare_lender_deposit(
                ledger.DeclareLenderDepositCommand(
                    actor=actor,
                    investor_user_id=str(investor.pk),
                    amount_minor=100_000_000,
                    currency=currency,
                    booking_date=today,
                    value_date=today,
                    collection_account_identifier=f"QA-{currency}-COLLECTION",
                    payer_name=investor.full_name,
                    payer_account_identifier="CH9300762011623852957",
                    bank_reference=key,
                    payment_reference=key,
                    evidence_reference=SEED_KEY,
                    idempotency_key=key,
                )
            )
    borrowers = []
    for index, name in enumerate(("QA Alpine Equipment AG", "QA Lake Trading SA")):
        registration = f"{SEED_KEY}:borrower:{index}"
        borrower = (
            apps.get_model("entities", "BorrowerEntity")
            .objects.filter(
                registration_number=registration,
            )
            .first()
        )
        if borrower is None:
            borrower = entities.create_borrower_entity(
                entities.CreateBorrowerEntityCommand(
                    actor=actor,
                    legal_name=name,
                    year_founded=2015 + index,
                    registration_number=registration,
                    country="Switzerland",
                    kyb_status="approved",
                    business_classification="Manufacturing" if index == 0 else "Wholesale",
                    business_classification_public=True,
                    note=SEED_KEY,
                )
            )
        borrowers.append(borrower)
    catalogue = import_module("backend.apps.loans.management.commands.seed_marketplace_demo_loans")
    direct_loans = []
    for index, spec in enumerate(catalogue.DEMO_LOAN_SPECS):
        title = f"QA - {spec.title.removeprefix('Demo - ')}"
        borrower = borrowers[index % len(borrowers)]
        loan = (
            apps.get_model("loans", "Loan").objects.filter(title=title, borrower=borrower).first()
        )
        if loan is None:
            values = asdict(spec)
            values.pop("key")
            days = values.pop("funding_deadline_days")
            values.update(
                actor=actor,
                borrower_id=str(borrower.pk),
                title=title,
                funding_deadline=today + timedelta(days=days),
                note=SEED_KEY,
            )
            loan = loans.create_loan(loans.CreateLoanCommand(**values))
            loans.publish_loan(loans.PublishLoanCommand(actor=actor, loan_id=str(loan.pk)))
        direct_loans.append(loan)
    call_command("seed_originator_demo_loans", actor_email=actor.email, verbosity=0)
    profile = (
        apps.get_model("originator_claims", "OriginatorLoanProfile")
        .objects.select_related(
            "loan",
            "originator",
        )
        .filter(
            originator__registration_number__startswith="BANXUM-QA-LO-",
            loan__title="Demo LO - Merchant receivables portfolio",
        )
        .get()
    )
    version = (
        apps.get_model("documents", "DocumentTemplateVersion")
        .objects.filter(
            template__template_key=SEED_KEY,
            status="published",
        )
        .first()
    )
    labels = ["I accept these synthetic QA investment terms."]
    if version is None:
        docs.create_document_template_version(
            docs.CreateDocumentTemplateVersionCommand(
                actor=actor,
                category="primary_market_investment",
                template_key=SEED_KEY,
                name="QA investment terms",
                title="QA investment terms",
                body="Synthetic QA agreement. Not a real financial offer. {{ lender.full_name }}",
                checkbox_labels=labels,
                publish_now=True,
                legal_review_reference=SEED_KEY,
            )
        )

    def order(loan: Any, amount: int, *, allocate: bool) -> None:
        key = f"{SEED_KEY}:order:{loan.pk}"
        existing = (
            apps.get_model("marketplace_primary", "PrimaryInvestmentOrder")
            .objects.filter(
                idempotency_key=key,
            )
            .first()
        )
        if existing is not None:
            return
        created = primary.create_primary_investment_order(
            primary.CreatePrimaryInvestmentOrderCommand(
                actor=investor,
                loan_id=str(loan.pk),
                amount_minor=amount,
                idempotency_key=key,
            )
        )
        if not allocate:
            return
        evidence = docs.accept_document_terms(
            docs.AcceptDocumentTermsCommand(
                actor=investor,
                category="primary_market_investment",
                template_key=SEED_KEY,
                accepted_checkbox_labels=labels,
                context_type="primary_order",
                context_id=str(created.pk),
                idempotency_key=f"{key}:terms",
            )
        )
        code = auth.issue_sensitive_action_code(
            auth.SensitiveActionCodeCommand(
                user=investor,
                action="primary_investment",
            )
        )
        primary.allocate_primary_order_from_balance(
            primary.AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(created.pk),
                document_acceptance_id=str(evidence.pk),
                idempotency_key=f"{key}:allocate",
                sensitive_action_code_id=str(code.code_record.pk),
                sensitive_action_code=code.raw_code,
            )
        )

    order(direct_loans[0], direct_loans[0].principal_minor, allocate=True)
    order(direct_loans[1], 100_000, allocate=True)
    order(direct_loans[2], 100_000, allocate=False)
    if profile.opportunity_status == "open":
        order(profile.loan, originators.originator_sellable_principal_minor(profile), allocate=True)
    return {
        "investor_email": INVESTOR_EMAIL,
        "direct_loans": len(direct_loans),
        "originator_loans": 10,
        "seed_key": SEED_KEY,
        "note": "Synthetic data only. No usable password was created; email delivery is mocked.",
    }
