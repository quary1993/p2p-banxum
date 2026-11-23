"""Staging-only release smoke checks.

This script runs through ``manage.py shell`` in the deployed backend container. It uses the
current staging database, but all temporary users and money mutations are inside one outer
transaction that is rolled back. It prints check names only. It never prints credentials,
codes, personal data, or provider secrets.
"""

from __future__ import annotations

import uuid
from importlib import import_module
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client
from django.utils import timezone

from backend.apps.accounts_auth import totp
from backend.apps.accounts_auth.crypto import encrypt_delivery_secret
from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    AuthenticatorApp,
    EmailLoginToken,
    SensitiveAction,
)
from backend.apps.accounts_auth.services import (
    SensitiveActionCodeCommand,
    issue_sensitive_action_code,
)
from backend.apps.kyc_compliance import declarations
from backend.apps.loans import security_proofs
from backend.apps.marketplace_primary import services as marketplace
from backend.apps.platform_core.domain import declarations as declaration_rules
from backend.apps.platform_core.domain.time import business_date, now_utc


class SmokeFailure(RuntimeError):
    pass


class RollBackSmoke(RuntimeError):
    pass


def check(condition: bool, name: str, detail: str = "") -> None:
    if not condition:
        raise SmokeFailure(f"{name}: {detail or 'failed'}")
    print(f"smoke_check={name}:passed")


def post_json(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, data=payload, content_type="application/json", secure=True)


def smoke_client(ip_address: str = "198.51.100.1") -> Client:
    return Client(
        HTTP_HOST="staging.nxnarena.com",
        HTTP_X_FORWARDED_PROTO="https",
        REMOTE_ADDR=ip_address,
    )


def add_confirmed_email(user: Any) -> None:
    EmailLoginToken.objects.create(
        user=user,
        email=user.email,
        token_digest=f"staging-smoke-confirmed-{user.pk}",
        encrypted_token="",
        expires_at=timezone.now(),
        used_at=timezone.now(),
    )


def add_authenticator(user: Any) -> str:
    secret = totp.new_secret()
    AuthenticatorApp.objects.create(
        user=user,
        encrypted_secret=encrypt_delivery_secret(secret),
        confirmed_at=timezone.now(),
    )
    return secret


def make_user(
    *,
    prefix: str,
    account_type: str,
    password: str,
    is_staff: bool = False,
    is_superuser: bool = False,
    staff_roles: list[str] | None = None,
) -> tuple[Any, str]:
    marker = uuid.uuid4().hex
    user = get_user_model().objects.create_user(
        email=f"{prefix}-{marker}@example.test",
        password=password,
        full_name=f"Staging smoke {prefix}",
        account_type=account_type,
        status=AccountStatus.ACTIVE,
        is_staff=is_staff,
        is_superuser=is_superuser,
        staff_roles=staff_roles or [],
        phone_verified_at=timezone.now() if not is_staff else None,
    )
    add_confirmed_email(user)
    return user, add_authenticator(user)


def approve_kyc(user: Any) -> None:
    case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    case_model.objects.create(
        user=user,
        subject_reference=f"user:{user.pk}",
        provider_environment="staging-smoke",
        workflow_id="staging-smoke",
        vendor_data=f"user:{user.pk}",
        status="approved",
        decision_at=now_utc(),
    )


def clean_declaration(user: Any) -> None:
    declarations.submit_declaration(
        declarations.SubmitDeclarationCommand(
            actor=user,
            data={
                "beneficial_owner_is_self": True,
                "sources_of_funds": ["salary", "savings"],
                "savings_origin": "Employment income saved for investing",
                "pep_status": "no",
                "yearly_volume_band": "50k_250k",
            },
        )
    )


def declare_deposit(*, actor: Any, investor: Any, currency: str, amount_minor: int) -> None:
    ledger = import_module("backend.apps.ledger.services")
    marker = uuid.uuid4().hex
    today = business_date(now_utc())
    payer_account = "CH5604835012345678009" if currency == "CHF" else "DE89370400440532013000"
    ledger.declare_deposit_and_verify_account(
        ledger.DeclareLenderDepositCommand(
            actor=actor,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency=currency,
            booking_date=today,
            value_date=today,
            collection_account_identifier=f"SMOKE-{currency}-COLLECTION",
            payer_name=investor.full_name,
            payer_account_identifier=payer_account,
            bank_reference=f"SMOKE-BANK-{marker}",
            payment_reference=f"SMOKE-PAY-{marker}",
            evidence_reference=f"staging-smoke:{marker}",
            idempotency_key=f"staging-smoke-deposit-{marker}",
        )
    )


def acceptance(*, investor: Any, order: Any) -> Any:
    template_model = apps.get_model("documents", "DocumentTemplate")
    version_model = apps.get_model("documents", "DocumentTemplateVersion")
    evidence_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    template = template_model.objects.filter(
        category="primary_market_investment",
        current_published_version__isnull=False,
    ).first()
    if template is None:
        template = template_model.objects.create(
            category="primary_market_investment",
            template_key=f"staging-smoke-{uuid.uuid4().hex}",
            language="en",
            name="Staging smoke primary terms",
            created_by_superadmin_id=investor.pk,
        )
        version = version_model.objects.create(
            template=template,
            version_number=1,
            status="published",
            title="Staging smoke primary terms",
            body="Staging-only smoke acceptance.",
            checkbox_labels=["I accept the primary-market terms."],
            variable_schema={},
            content_hash="0" * 64,
            created_by_superadmin_id=investor.pk,
            published_at=now_utc(),
        )
        template.current_published_version = version
        template.save(update_fields=["current_published_version"])
    version = template.current_published_version
    return evidence_model.objects.create(
        user_id=investor.pk,
        category="primary_market_investment",
        template=template,
        template_version=version,
        template_version_number=version.version_number,
        template_hash=version.content_hash,
        context_type="primary_order",
        context_id=str(order.pk),
        accepted_checkbox_labels=list(version.checkbox_labels or []),
        data_snapshot={"source": "staging_release_smoke"},
        idempotency_key=f"staging-smoke-accept-{uuid.uuid4().hex}",
    )


def operation_code(*, investor: Any, secret: str, loan: Any, amount_minor: int) -> tuple[Any, str]:
    details = {
        "amount_minor": amount_minor,
        "currency": str(loan.currency_id),
        "loan_id": str(loan.pk),
    }
    issued = issue_sensitive_action_code(
        SensitiveActionCodeCommand(
            user=investor,
            action=SensitiveAction.PRIMARY_INVESTMENT,
            operation=details,
            ip_address="127.0.0.1",
            user_agent="BANXUM staging release smoke",
        )
    )
    return issued, totp.code_at_step(secret, totp.current_step())


def sandbox_ack(order: Any) -> dict[str, Any]:
    regimes = import_module("backend.apps.marketplace_primary.creditor_regime")
    loan = apps.get_model("loans", "Loan").objects.select_related("borrower").get(pk=order.loan_id)
    notice = regimes.sandbox_notice(loan, borrower_name=marketplace._borrower_public_name(loan))
    if notice is None:
        return {}
    return {"sandbox_notice_confirmed": True, "sandbox_notice_version": notice["version"]}


def allocate_full_loan(*, admin: Any, investor: Any, secret: str, loan: Any) -> Any:
    remaining = marketplace._loan_remaining_capacity_minor(loan)
    check(remaining > 0, f"{loan.pk}-has-capacity")
    approve_kyc(investor)
    clean_declaration(investor)
    declare_deposit(
        actor=admin,
        investor=investor,
        currency=str(loan.currency_id),
        amount_minor=max(remaining + 100_000_00, 6_000_000_00),
    )
    order = marketplace.create_primary_investment_order(
        marketplace.CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=remaining,
            idempotency_key=f"staging-smoke-order-{uuid.uuid4().hex}",
        )
    )
    accepted = acceptance(investor=investor, order=order)
    issued, app_code = operation_code(
        investor=investor,
        secret=secret,
        loan=loan,
        amount_minor=remaining,
    )
    allocated = marketplace.allocate_primary_order_from_balance(
        marketplace.AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.pk),
            document_acceptance_id=str(accepted.pk),
            idempotency_key=f"staging-smoke-allocate-{uuid.uuid4().hex}",
            sensitive_action_code_id=str(issued.code_record.pk),
            sensitive_action_code=issued.raw_code,
            pin=app_code,
            ip_address="127.0.0.1",
            user_agent="BANXUM staging release smoke",
            **sandbox_ack(order),
        )
    )
    check(
        str(allocated.status) in {"balance_allocated", "invested"},
        f"{loan.pk}-balance-allocation",
        str(allocated.status),
    )
    return allocated


def sign_in_checks() -> None:
    password = f"Smoke-{uuid.uuid4().hex}-pass"
    investor, secret = make_user(
        prefix="investor-auth",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        password=password,
    )
    client = smoke_client("198.51.100.10")
    started = post_json(
        client,
        "/api/v1/auth/login/",
        {"email": investor.email, "password": password},
    )
    check(started.status_code == 200, "investor-sign-in-start", str(started.status_code))
    payload = started.json()
    check(payload.get("status") == "factor_required", "investor-factor-required")
    verified = post_json(
        client,
        "/api/v1/auth/login/verify/",
        {
            "challenge_id": payload["challenge_id"],
            "code": totp.code_at_step(secret, totp.current_step()),
            "trust_device": False,
        },
    )
    check(verified.status_code == 200, "investor-authenticator-sign-in", str(verified.status_code))
    check(client.get("/api/v1/auth/me/", secure=True).status_code == 200, "investor-session")

    for label, account_type, superuser, ip_address in (
        ("admin", AccountType.ADMIN, False, "198.51.100.11"),
        ("superadmin", AccountType.SUPERADMIN, True, "198.51.100.12"),
    ):
        admin_password = f"Smoke-{uuid.uuid4().hex}-admin"
        admin, admin_secret = make_user(
            prefix=label,
            account_type=account_type,
            password=admin_password,
            is_staff=True,
            is_superuser=superuser,
        )
        admin_client = smoke_client(ip_address)
        start = post_json(
            admin_client,
            "/api/v1/auth/admin/login/start/",
            {"email": admin.email, "password": admin_password},
        )
        check(start.status_code == 202, f"{label}-sign-in-start", str(start.status_code))
        body = start.json()
        check(body.get("status") == "factor_required", f"{label}-factor-required")
        confirm = post_json(
            admin_client,
            "/api/v1/auth/admin/login/confirm/",
            {
                "challenge_id": body["challenge_id"],
                "code": totp.code_at_step(admin_secret, totp.current_step()),
            },
        )
        check(
            confirm.status_code == 200,
            f"{label}-authenticator-sign-in",
            str(confirm.status_code),
        )
        check(
            admin_client.get("/api/v1/auth/me/", secure=True).status_code == 200,
            f"{label}-session",
        )


def read_paths() -> tuple[Any, Any]:
    user_model = get_user_model()
    lot_model = apps.get_model("ledger", "InvestorBalanceLot")
    investor_id = (
        lot_model.objects.filter(available_amount_minor__gt=0)
        .values_list("investor_user_id", flat=True)
        .first()
    )
    investor = user_model.objects.filter(
        pk=investor_id,
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    ).first()
    admin = user_model.objects.filter(
        account_type=AccountType.ADMIN,
        status=AccountStatus.ACTIVE,
        is_staff=True,
    ).first()
    check(investor is not None, "seed-funded-investor-present")
    check(admin is not None, "seed-regular-admin-present")

    investor_client = smoke_client("198.51.100.20")
    investor_client.force_login(investor)
    for path, name in (
        ("/api/v1/investor/portal/dashboard/", "investor-dashboard-api"),
        ("/api/v1/investor/portal/balances/", "investor-balances-api"),
        ("/api/v1/investor/portal/portfolio/", "investor-portfolio-api"),
        ("/api/v1/investor/portal/transactions/", "investor-transactions-api"),
        ("/api/v1/investor/portal/reports/", "investor-reports-api"),
        ("/api/v1/marketplace/primary/opportunities/", "marketplace-opportunities-api"),
    ):
        response = investor_client.get(path, secure=True)
        check(response.status_code == 200, name, str(response.status_code))
    export = investor_client.get("/api/v1/investor/portal/transactions/export/", secure=True)
    check(export.status_code == 200, "investor-transactions-csv", str(export.status_code))
    check("csv" in str(export.get("Content-Type", "")).lower(), "investor-transactions-csv-type")

    admin_client = smoke_client("198.51.100.21")
    admin_client.force_login(admin)
    for path, name in (
        ("/api/v1/admin-ops/dashboard/", "admin-dashboard-api"),
        ("/api/v1/admin-ops/tasks/", "admin-tasks-api"),
        ("/api/v1/marketplace/primary/opportunities/", "admin-marketplace-api"),
    ):
        response = admin_client.get(path, secure=True)
        check(response.status_code == 200, name, str(response.status_code))
    return admin, investor


def money_and_compliance_checks(admin: Any) -> None:
    loan_model = apps.get_model("loans", "Loan")
    direct = loan_model.objects.filter(status="published", originator_profile__isnull=True).first()
    originator = loan_model.objects.filter(
        status="published", originator_profile__isnull=False
    ).first()
    check(direct is not None, "seed-direct-opportunity-present")
    check(originator is not None, "seed-originator-opportunity-present")
    check(not security_proofs.investment_problem(direct), "direct-security-proof-current")
    check(not security_proofs.investment_problem(originator), "originator-security-proof-current")

    direct_password = f"Smoke-{uuid.uuid4().hex}-direct"
    direct_investor, direct_secret = make_user(
        prefix="direct-investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        password=direct_password,
    )
    direct_order = allocate_full_loan(
        admin=admin,
        investor=direct_investor,
        secret=direct_secret,
        loan=direct,
    )
    check(direct_order.allocated_amount_minor > 0, "direct-primary-investment")

    lo_password = f"Smoke-{uuid.uuid4().hex}-lo"
    lo_investor, lo_secret = make_user(
        prefix="lo-investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        password=lo_password,
    )
    lo_order = allocate_full_loan(
        admin=admin,
        investor=lo_investor,
        secret=lo_secret,
        loan=originator,
    )
    check(lo_order.allocated_amount_minor > 0, "originator-primary-investment")
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    check(
        holding_model.objects.filter(
            investor_user_id=lo_investor.pk,
            loan_id=originator.pk,
        ).exists(),
        "originator-auto-close-holding",
    )

    pep_password = f"Smoke-{uuid.uuid4().hex}-pep"
    pep, _pep_secret = make_user(
        prefix="pep-review",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        password=pep_password,
    )
    approve_kyc(pep)
    declarations.submit_declaration(
        declarations.SubmitDeclarationCommand(
            actor=pep,
            data={
                "beneficial_owner_is_self": True,
                "sources_of_funds": ["salary"],
                "pep_status": "not_sure",
                "yearly_volume_band": "10k_50k",
            },
        )
    )
    check(
        declarations.investment_block(pep) == declarations.BLOCK_REVIEW_OPEN,
        "pep-review-blocks-investment",
    )
    review = apps.get_model("kyc_compliance", "ComplianceReview").objects.get(user_id=pep.pk)
    check(
        apps.get_model("admin_ops", "AdminTask")
        .objects.filter(
            related_object_type="ComplianceReview",
            related_object_id=str(review.pk),
            status="open",
        )
        .exists(),
        "pep-review-admin-task",
    )
    check(
        apps.get_model("platform_core", "OutboxMessage")
        .objects.filter(topic="email.compliance_review_opened")
        .exists(),
        "pep-review-email-queued",
    )

    compliance, _secret = make_user(
        prefix="compliance",
        account_type=AccountType.ADMIN,
        password=f"Smoke-{uuid.uuid4().hex}-compliance",
        is_staff=True,
        staff_roles=[declaration_rules.ROLE_COMPLIANCE, declaration_rules.ROLE_SECURITY_VERIFIER],
    )
    declarations.decide_review(
        declarations.DecideReviewCommand(
            actor=compliance,
            review_id=str(review.pk),
            decision="close",
            note="Staging release smoke review completed.",
        )
    )
    check(declarations.investment_block(pep) is None, "pep-review-close-unblocks")


def main() -> None:
    check(settings.ENVIRONMENT == "staging", "staging-environment")
    check(not settings.IS_PRODUCTION, "production-guard-off")
    check(settings.QA_DEV_MODE_ALLOWED, "qa-mode-allowed")
    check(smoke_client().get("/api/v1/health/", secure=True).status_code == 200, "health-api")
    public = smoke_client().get("/api/v1/marketplace/primary/public/projects/", secure=True)
    check(public.status_code == 200, "public-projects-api", str(public.status_code))

    loan_model = apps.get_model("loans", "Loan")
    direct_before = loan_model.objects.filter(originator_profile__isnull=True).count()
    originator_before = loan_model.objects.filter(originator_profile__isnull=False).count()
    check(direct_before >= 10, "seed-direct-count")
    check(originator_before >= 10, "seed-originator-count")

    try:
        with transaction.atomic():
            sign_in_checks()
            admin, _investor = read_paths()
            money_and_compliance_checks(admin)
            raise RollBackSmoke()
    except RollBackSmoke:
        pass

    check(
        loan_model.objects.filter(originator_profile__isnull=True).count() == direct_before,
        "temporary-direct-data-rolled-back",
    )
    check(
        loan_model.objects.filter(originator_profile__isnull=False).count() == originator_before,
        "temporary-originator-data-rolled-back",
    )
    check(
        not get_user_model().objects.filter(email__startswith="investor-auth-").exists(),
        "temporary-users-rolled-back",
    )
    print("staging_release_smoke_status=passed")


main()
