from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from backend.apps.loans.models import (
    CollateralType,
    LoanEvent,
    LoanEventType,
    LoanPurpose,
    LoanStatus,
    RepaymentType,
    RiskRating,
)
from backend.apps.loans.services import (
    CreateLoanCommand,
    LoansError,
    PublishLoanCommand,
    create_loan,
    publish_loan,
)
from backend.apps.platform_core.domain.access import is_admin_actor
from backend.apps.platform_core.domain.time import business_date, now_utc

SEED_NAME = "seed_marketplace_demo_loans"
SEED_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class DemoLoanSpec:
    key: str
    title: str
    investor_summary: str
    purpose: str
    purpose_description: str
    principal_minor: int
    currency: str
    interest_rate_bps: int
    term_months: int
    repayment_type: str
    interest_only_months: int
    collateral_type: str
    collateral_value_minor: int
    collateral_description: str
    risk_rating: str
    funding_deadline_days: int


DEMO_LOAN_SPECS = (
    DemoLoanSpec(
        key="working-capital-growth",
        title="Demo - Working capital growth facility",
        investor_summary=(
            "Demonstration opportunity for a business seeking seasonal working-capital capacity. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.WORKING_CAPITAL,
        purpose_description="Seasonal purchasing and operating working capital.",
        principal_minor=25_000_000,
        currency="CHF",
        interest_rate_bps=725,
        term_months=12,
        repayment_type=RepaymentType.EQUAL_INSTALLMENTS,
        interest_only_months=0,
        collateral_type=CollateralType.RECEIVABLES,
        collateral_value_minor=38_000_000,
        collateral_description="Illustrative assignment of eligible trade receivables.",
        risk_rating=RiskRating.BBB_PLUS,
        funding_deadline_days=14,
    ),
    DemoLoanSpec(
        key="equipment-modernisation",
        title="Demo - Equipment modernisation facility",
        investor_summary=(
            "Demonstration equipment-finance opportunity with monthly amortization. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.CAPEX,
        purpose_description="Modernisation of production and quality-control equipment.",
        principal_minor=48_000_000,
        currency="CHF",
        interest_rate_bps=810,
        term_months=24,
        repayment_type=RepaymentType.AMORTIZING_PRINCIPAL_INTEREST,
        interest_only_months=0,
        collateral_type=CollateralType.EQUIPMENT,
        collateral_value_minor=70_000_000,
        collateral_description="Illustrative first-ranking security over financed equipment.",
        risk_rating=RiskRating.A_MINUS,
        funding_deadline_days=17,
    ),
    DemoLoanSpec(
        key="logistics-expansion",
        title="Demo - Logistics expansion facility",
        investor_summary=(
            "Demonstration corporate expansion facility supported by real-estate collateral. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.CORPORATE_PROJECT_FINANCE,
        purpose_description="Expansion of warehousing and regional distribution capacity.",
        principal_minor=75_000_000,
        currency="CHF",
        interest_rate_bps=690,
        term_months=36,
        repayment_type=RepaymentType.EQUAL_INSTALLMENTS,
        interest_only_months=0,
        collateral_type=CollateralType.REAL_ESTATE,
        collateral_value_minor=135_000_000,
        collateral_description="Illustrative commercial property security package.",
        risk_rating=RiskRating.A,
        funding_deadline_days=20,
    ),
    DemoLoanSpec(
        key="renewable-energy-installation",
        title="Demo - Renewable energy installation",
        investor_summary=(
            "Demonstration project-finance opportunity with an initial interest-only period. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.PROJECT_FINANCE,
        purpose_description="Installation of rooftop solar generation and storage assets.",
        principal_minor=32_000_000,
        currency="EUR",
        interest_rate_bps=845,
        term_months=30,
        repayment_type=RepaymentType.INTEREST_ONLY_THEN_AMORTIZING,
        interest_only_months=6,
        collateral_type=CollateralType.ASSET_BACKED,
        collateral_value_minor=48_000_000,
        collateral_description="Illustrative security over project equipment and receivables.",
        risk_rating=RiskRating.BBB,
        funding_deadline_days=22,
    ),
    DemoLoanSpec(
        key="inventory-growth",
        title="Demo - Inventory growth facility",
        investor_summary=(
            "Demonstration inventory-finance opportunity with periodic interest and "
            "bullet principal. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.INVENTORY_TRADE_FINANCE,
        purpose_description="Purchase of committed seasonal inventory.",
        principal_minor=18_000_000,
        currency="CHF",
        interest_rate_bps=920,
        term_months=18,
        repayment_type=RepaymentType.BULLET_PERIODIC_INTEREST,
        interest_only_months=0,
        collateral_type=CollateralType.INVENTORY,
        collateral_value_minor=27_500_000,
        collateral_description="Illustrative pledge over financed inventory.",
        risk_rating=RiskRating.BB_PLUS,
        funding_deadline_days=24,
    ),
    DemoLoanSpec(
        key="receivables-liquidity",
        title="Demo - Receivables-backed liquidity",
        investor_summary=(
            "Demonstration short-term liquidity facility backed by business receivables. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.LIQUIDITY,
        purpose_description="Bridge liquidity against contracted customer receivables.",
        principal_minor=27_500_000,
        currency="EUR",
        interest_rate_bps=780,
        term_months=15,
        repayment_type=RepaymentType.AMORTIZING_PRINCIPAL_INTEREST,
        interest_only_months=0,
        collateral_type=CollateralType.RECEIVABLES,
        collateral_value_minor=41_000_000,
        collateral_description="Illustrative assignment of approved customer receivables.",
        risk_rating=RiskRating.BBB,
        funding_deadline_days=25,
    ),
    DemoLoanSpec(
        key="acquisition-bridge",
        title="Demo - Acquisition bridge facility",
        investor_summary=(
            "Demonstration acquisition bridge with interest-only servicing and bullet repayment. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.ACQUISITION,
        purpose_description="Bridge financing for a complementary business acquisition.",
        principal_minor=60_000_000,
        currency="CHF",
        interest_rate_bps=1_010,
        term_months=24,
        repayment_type=RepaymentType.INTEREST_ONLY_THEN_BULLET,
        interest_only_months=23,
        collateral_type=CollateralType.MIXED_COLLATERAL,
        collateral_value_minor=86_000_000,
        collateral_description="Illustrative share pledge, guarantee and asset-security package.",
        risk_rating=RiskRating.BB,
        funding_deadline_days=27,
    ),
    DemoLoanSpec(
        key="development-capex",
        title="Demo - Development capex facility",
        investor_summary=(
            "Demonstration longer-term development facility with staged amortization. "
            "This is private-test data and is not a live investment offer."
        ),
        purpose=LoanPurpose.DEVELOPMENT,
        purpose_description="Development and fit-out expenditure for an operating site.",
        principal_minor=95_000_000,
        currency="EUR",
        interest_rate_bps=895,
        term_months=48,
        repayment_type=RepaymentType.INTEREST_ONLY_THEN_AMORTIZING,
        interest_only_months=12,
        collateral_type=CollateralType.REAL_ESTATE,
        collateral_value_minor=162_000_000,
        collateral_description="Illustrative real-estate and project-rights security package.",
        risk_rating=RiskRating.BBB_MINUS,
        funding_deadline_days=28,
    ),
)


def _marker(spec: DemoLoanSpec) -> str:
    return f"{SEED_NAME}:{SEED_VERSION}:{spec.key}"


def _format_minor(amount_minor: int) -> str:
    major, minor = divmod(amount_minor, 100)
    return f"{major:,}.{minor:02d}"


def _format_bps(rate_bps: int) -> str:
    percent, fraction = divmod(rate_bps, 100)
    return f"{percent}.{fraction:02d}%"


class Command(BaseCommand):
    help = (
        "Publish eight clearly labelled, idempotent marketplace demo loans using existing "
        "approved borrowers. This command is opt-in and is never part of normal app startup."
    )

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--actor-email",
            default="",
            help="Active admin/superadmin email used for audit attribution.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the intended catalogue without writing records.",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Required explicit acknowledgement when ENVIRONMENT=production.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        if settings.IS_PRODUCTION and not options["allow_production"]:
            raise CommandError(
                "Refusing to seed demo financial products in production without "
                "--allow-production."
            )

        actor_email = str(options["actor_email"] or settings.GARANTA_SUPERADMIN_EMAIL).strip()
        if not actor_email:
            raise CommandError(
                "Set GARANTA_SUPERADMIN_EMAIL or provide --actor-email for audit attribution."
            )
        user_model = get_user_model()
        actor = user_model.objects.filter(email__iexact=actor_email).first()
        if actor is None or not is_admin_actor(actor):
            raise CommandError(f"Active admin actor does not exist: {actor_email}")

        borrower_model = apps.get_model("entities", "BorrowerEntity")
        borrowers = list(
            borrower_model.objects.filter(
                kyb_status="approved",
                compliance_hold=False,
            ).order_by("legal_name", "id")
        )
        if not borrowers:
            raise CommandError(
                "No approved borrower without a compliance hold exists. Create or approve an "
                "existing borrower before seeding marketplace demo loans."
            )

        today = business_date(now_utc())
        created = 0
        skipped = 0

        try:
            with transaction.atomic():
                for index, spec in enumerate(DEMO_LOAN_SPECS):
                    marker = _marker(spec)
                    existing = (
                        LoanEvent.objects.select_related("loan")
                        .filter(event_type=LoanEventType.CREATED, note=marker)
                        .first()
                    )
                    borrower = borrowers[index % len(borrowers)]
                    if existing is not None:
                        skipped += 1
                        self.stdout.write(
                            f"SKIP {existing.loan.title} [{existing.loan.status}] "
                            f"borrower={existing.loan.borrower_id}"
                        )
                        continue

                    deadline = today + timedelta(days=spec.funding_deadline_days)
                    self.stdout.write(
                        f"PLAN {spec.title} | {borrower.legal_name} | {spec.currency} "
                        f"{_format_minor(spec.principal_minor)} | "
                        f"{_format_bps(spec.interest_rate_bps)} "
                        f"| {spec.term_months} months | deadline={deadline.isoformat()}"
                    )
                    if options["dry_run"]:
                        continue

                    loan = create_loan(
                        CreateLoanCommand(
                            actor=actor,
                            borrower_id=str(borrower.pk),
                            title=spec.title,
                            investor_summary=spec.investor_summary,
                            purpose=spec.purpose,
                            purpose_description=spec.purpose_description,
                            principal_minor=spec.principal_minor,
                            currency=spec.currency,
                            interest_rate_bps=spec.interest_rate_bps,
                            term_months=spec.term_months,
                            repayment_type=spec.repayment_type,
                            interest_only_months=spec.interest_only_months,
                            collateral_type=spec.collateral_type,
                            collateral_value_minor=spec.collateral_value_minor,
                            collateral_description=spec.collateral_description,
                            risk_rating=spec.risk_rating,
                            loan_start_date=deadline,
                            funding_deadline=deadline,
                            note=marker,
                        )
                    )
                    loan = publish_loan(
                        PublishLoanCommand(
                            actor=actor,
                            loan_id=str(loan.pk),
                            note=marker,
                        )
                    )
                    if loan.status != LoanStatus.PUBLISHED or loan.committed_principal_minor != 0:
                        raise CommandError(
                            f"Demo loan did not reach the expected 0%-funded state: {loan.pk}"
                        )
                    created += 1
        except LoansError as exc:
            raise CommandError(str(exc)) from exc

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete: {len(DEMO_LOAN_SPECS) - skipped} planned, "
                    f"{skipped} already present."
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo marketplace catalogue ready: {created} created, {skipped} skipped."
            )
        )
