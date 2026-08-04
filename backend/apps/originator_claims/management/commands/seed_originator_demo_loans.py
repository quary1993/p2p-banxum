from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from backend.apps.originator_claims.domain.imports import CSV_COLUMNS
from backend.apps.originator_claims.models import (
    LoanOriginator,
    LoanOriginatorStatus,
    OriginatorLoanImport,
    OriginatorOpportunityStatus,
)
from backend.apps.originator_claims.services import (
    CreateLoanOriginatorCommand,
    CreateOriginatorLoanCommand,
    OriginatorClaimsError,
    PublishOriginatorLoanCommand,
    create_loan_originator,
    create_originator_loan,
    publish_originator_loan,
)
from backend.apps.platform_core.domain.access import is_admin_actor
from backend.apps.platform_core.domain.money import format_amount_minor
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import Currency

SEED_NAME = "seed_originator_demo_loans"
SEED_VERSION = "v1"
DEMO_SETTLEMENT_IBAN = "CH9300762011623852957"


@dataclass(frozen=True, slots=True)
class DemoOriginatorSpec:
    key: str
    legal_name: str
    public_name: str
    registration_number: str


@dataclass(frozen=True, slots=True)
class DemoOriginatorLoanSpec:
    key: str
    originator_key: str
    title: str
    borrower_display_name: str
    borrower_country: str
    industry_activity: str
    investor_summary: str
    purpose: str
    purpose_description: str
    currency: str
    principal_minor: int
    coupon_bps: int
    target_yield_bps: int
    minimum_investment_minor: int
    term_months: int
    repayment_type: str
    interest_only_months: int
    collateral_type: str
    collateral_value_minor: int
    collateral_description: str
    risk_rating: str


DEMO_ORIGINATOR_SPECS = (
    DemoOriginatorSpec(
        key="alpine-credit",
        legal_name="BANXUM Demo Alpine Credit Partners AG",
        public_name="Alpine Credit Partners",
        registration_number="BANXUM-QA-LO-001",
    ),
    DemoOriginatorSpec(
        key="helvetic-receivables",
        legal_name="BANXUM Demo Helvetic Receivables AG",
        public_name="Helvetic Receivables",
        registration_number="BANXUM-QA-LO-002",
    ),
    DemoOriginatorSpec(
        key="rhine-commercial",
        legal_name="BANXUM Demo Rhine Commercial Credit SA",
        public_name="Rhine Commercial Credit",
        registration_number="BANXUM-QA-LO-003",
    ),
)


DEMO_ORIGINATOR_LOAN_SPECS = (
    DemoOriginatorLoanSpec(
        key="merchant-receivables",
        originator_key="helvetic-receivables",
        title="Demo LO - Merchant receivables portfolio",
        borrower_display_name="Swiss consumer-goods distributor",
        borrower_country="Switzerland",
        industry_activity="Wholesale distribution",
        investor_summary=(
            "Performing receivables-backed claim sold by a demo Loan Originator. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="working_capital",
        purpose_description="Seasonal merchant inventory and receivables financing.",
        currency="CHF",
        principal_minor=18_000_000,
        coupon_bps=1180,
        target_yield_bps=820,
        minimum_investment_minor=50_000,
        term_months=12,
        repayment_type="equal_installments",
        interest_only_months=0,
        collateral_type="receivables",
        collateral_value_minor=28_000_000,
        collateral_description="Illustrative assigned merchant receivables.",
        risk_rating="BBB+",
    ),
    DemoOriginatorLoanSpec(
        key="medical-equipment",
        originator_key="alpine-credit",
        title="Demo LO - Medical equipment financing",
        borrower_display_name="Swiss outpatient clinic group",
        borrower_country="Switzerland",
        industry_activity="Healthcare services",
        investor_summary=(
            "Performing equipment-finance claim with declining principal. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="capex",
        purpose_description="Diagnostic and outpatient treatment equipment.",
        currency="CHF",
        principal_minor=32_000_000,
        coupon_bps=1040,
        target_yield_bps=740,
        minimum_investment_minor=100_000,
        term_months=24,
        repayment_type="amortizing_principal_interest",
        interest_only_months=0,
        collateral_type="equipment",
        collateral_value_minor=44_000_000,
        collateral_description="Illustrative first-ranking equipment security.",
        risk_rating="A-",
    ),
    DemoOriginatorLoanSpec(
        key="logistics-fleet-bridge",
        originator_key="rhine-commercial",
        title="Demo LO - Logistics fleet bridge",
        borrower_display_name="Central European logistics operator",
        borrower_country="Germany",
        industry_activity="Road freight and logistics",
        investor_summary=(
            "Performing short-duration claim with periodic coupon and bullet principal. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="bridge_financing",
        purpose_description="Fleet replacement bridge financing.",
        currency="CHF",
        principal_minor=24_000_000,
        coupon_bps=1320,
        target_yield_bps=910,
        minimum_investment_minor=50_000,
        term_months=9,
        repayment_type="bullet_periodic_interest",
        interest_only_months=0,
        collateral_type="equipment",
        collateral_value_minor=33_000_000,
        collateral_description="Illustrative pledge over commercial vehicles.",
        risk_rating="BB+",
    ),
    DemoOriginatorLoanSpec(
        key="hospitality-refurbishment",
        originator_key="alpine-credit",
        title="Demo LO - Hospitality refurbishment",
        borrower_display_name="Alpine hospitality operator",
        borrower_country="Switzerland",
        industry_activity="Hotels and accommodation",
        investor_summary=(
            "Performing secured claim with an initial interest-only period. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="development",
        purpose_description="Refurbishment of operating hospitality assets.",
        currency="CHF",
        principal_minor=45_000_000,
        coupon_bps=1240,
        target_yield_bps=870,
        minimum_investment_minor=100_000,
        term_months=18,
        repayment_type="interest_only_then_amortizing",
        interest_only_months=3,
        collateral_type="real_estate",
        collateral_value_minor=76_000_000,
        collateral_description="Illustrative mortgage-backed security package.",
        risk_rating="BBB",
    ),
    DemoOriginatorLoanSpec(
        key="food-inventory",
        originator_key="helvetic-receivables",
        title="Demo LO - Food wholesaler inventory",
        borrower_display_name="Regional food wholesaler",
        borrower_country="Switzerland",
        industry_activity="Food wholesale",
        investor_summary=(
            "Performing inventory-backed claim with bullet maturity. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="inventory_trade_finance",
        purpose_description="Committed seasonal food inventory purchases.",
        currency="CHF",
        principal_minor=12_500_000,
        coupon_bps=1410,
        target_yield_bps=1020,
        minimum_investment_minor=25_000,
        term_months=8,
        repayment_type="interest_only_then_bullet",
        interest_only_months=7,
        collateral_type="inventory",
        collateral_value_minor=18_500_000,
        collateral_description="Illustrative pledge over eligible inventory.",
        risk_rating="BB",
    ),
    DemoOriginatorLoanSpec(
        key="solar-equipment",
        originator_key="rhine-commercial",
        title="Demo LO - Commercial solar equipment",
        borrower_display_name="German commercial energy installer",
        borrower_country="Germany",
        industry_activity="Renewable-energy installation",
        investor_summary=(
            "Performing euro-denominated equipment claim with monthly amortization. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="project_finance",
        purpose_description="Commercial rooftop solar installations.",
        currency="EUR",
        principal_minor=38_000_000,
        coupon_bps=1080,
        target_yield_bps=780,
        minimum_investment_minor=50_000,
        term_months=30,
        repayment_type="amortizing_principal_interest",
        interest_only_months=0,
        collateral_type="asset_backed",
        collateral_value_minor=55_000_000,
        collateral_description="Illustrative security over installed energy assets.",
        risk_rating="BBB+",
    ),
    DemoOriginatorLoanSpec(
        key="trade-receivables",
        originator_key="helvetic-receivables",
        title="Demo LO - Benelux trade receivables",
        borrower_display_name="Benelux industrial supplier",
        borrower_country="Netherlands",
        industry_activity="Industrial components",
        investor_summary=(
            "Performing euro receivables claim with level monthly payments. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="liquidity",
        purpose_description="Liquidity against contracted trade receivables.",
        currency="EUR",
        principal_minor=21_000_000,
        coupon_bps=1210,
        target_yield_bps=860,
        minimum_investment_minor=50_000,
        term_months=10,
        repayment_type="equal_installments",
        interest_only_months=0,
        collateral_type="invoices",
        collateral_value_minor=31_500_000,
        collateral_description="Illustrative assignment of approved invoices.",
        risk_rating="BBB",
    ),
    DemoOriginatorLoanSpec(
        key="manufacturing-capex",
        originator_key="rhine-commercial",
        title="Demo LO - Manufacturing capex",
        borrower_display_name="Austrian precision manufacturer",
        borrower_country="Austria",
        industry_activity="Precision manufacturing",
        investor_summary=(
            "Performing capex claim with an interest-only ramp-up period. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="capex",
        purpose_description="Production-line automation and tooling.",
        currency="EUR",
        principal_minor=52_500_000,
        coupon_bps=1130,
        target_yield_bps=800,
        minimum_investment_minor=100_000,
        term_months=36,
        repayment_type="interest_only_then_amortizing",
        interest_only_months=6,
        collateral_type="equipment",
        collateral_value_minor=79_000_000,
        collateral_description="Illustrative security over production equipment.",
        risk_rating="A-",
    ),
    DemoOriginatorLoanSpec(
        key="pharmacy-acquisition",
        originator_key="alpine-credit",
        title="Demo LO - Pharmacy acquisition",
        borrower_display_name="French community pharmacy operator",
        borrower_country="France",
        industry_activity="Community pharmacy",
        investor_summary=(
            "Performing acquisition claim with periodic coupon and bullet principal. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="acquisition",
        purpose_description="Acquisition of an operating community pharmacy.",
        currency="EUR",
        principal_minor=29_000_000,
        coupon_bps=1350,
        target_yield_bps=940,
        minimum_investment_minor=100_000,
        term_months=18,
        repayment_type="bullet_periodic_interest",
        interest_only_months=0,
        collateral_type="mixed_collateral",
        collateral_value_minor=42_000_000,
        collateral_description="Illustrative share pledge and business-asset security.",
        risk_rating="BB+",
    ),
    DemoOriginatorLoanSpec(
        key="distribution-vehicles",
        originator_key="rhine-commercial",
        title="Demo LO - Distribution vehicles",
        borrower_display_name="Dutch last-mile delivery operator",
        borrower_country="Netherlands",
        industry_activity="Last-mile delivery",
        investor_summary=(
            "Performing vehicle-finance claim with level monthly payments. "
            "Private-test data only; not a live investment offer."
        ),
        purpose="capex",
        purpose_description="Low-emission distribution vehicle fleet.",
        currency="EUR",
        principal_minor=16_500_000,
        coupon_bps=990,
        target_yield_bps=700,
        minimum_investment_minor=25_000,
        term_months=15,
        repayment_type="equal_installments",
        interest_only_months=0,
        collateral_type="equipment",
        collateral_value_minor=24_000_000,
        collateral_description="Illustrative first-ranking vehicle security.",
        risk_rating="BBB+",
    ),
)


def _marker(spec: DemoOriginatorLoanSpec) -> str:
    return f"{SEED_NAME}:{SEED_VERSION}:{spec.key}"


def _schedule_drafts(spec: DemoOriginatorLoanSpec, *, today: date) -> list[Any]:
    schedules = import_module("backend.apps.loans.domain.schedules")
    first_due_date = schedules.add_months(today, 1)
    common = {
        "principal_minor": spec.principal_minor,
        "currency": spec.currency,
        "term_months": spec.term_months,
        "annual_interest_bps": spec.coupon_bps,
        "first_due_date": first_due_date,
    }
    if spec.repayment_type == "equal_installments":
        return list(schedules.generate_equal_installment_schedule(**common))
    if spec.repayment_type == "amortizing_principal_interest":
        return list(schedules.generate_equal_principal_schedule(**common))
    if spec.repayment_type in {"bullet_periodic_interest", "interest_only_then_bullet"}:
        return list(schedules.generate_bullet_schedule(**common))
    if spec.repayment_type == "interest_only_then_amortizing":
        return list(
            schedules.generate_interest_only_then_amortizing_schedule(
                **common,
                interest_only_months=spec.interest_only_months,
            )
        )
    raise CommandError(f"Unsupported demo repayment type: {spec.repayment_type}")


def _csv_content(spec: DemoOriginatorLoanSpec, *, today: date) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    opening = spec.principal_minor
    accrual_start = today
    for draft in _schedule_drafts(spec, today=today):
        closing = opening - int(draft.principal_minor)
        writer.writerow(
            {
                "row_type": "schedule",
                "installment_number": int(draft.installment_number),
                "accrual_start_date": accrual_start.isoformat(),
                "due_date": draft.due_date.isoformat(),
                "opening_principal_minor": opening,
                "principal_minor": int(draft.principal_minor),
                "interest_minor": int(draft.interest_minor),
                "penalty_minor": 0,
                "fee_minor": 0,
                "total_minor": int(draft.total_minor),
                "closing_principal_minor": closing,
            }
        )
        opening = closing
        accrual_start = draft.due_date
    return output.getvalue()


def _borrower_snapshot(spec: DemoOriginatorLoanSpec) -> dict[str, Any]:
    return {
        "borrower_legal_name": f"BANXUM Demo Confidential Borrower - {spec.key}",
        "borrower_display_name": spec.borrower_display_name,
        "year_founded": 2014,
        "entity_type": "Private company",
        "country": spec.borrower_country,
        "business_classification": "Small or medium-sized operating company",
        "business_classification_public": True,
        "registered_address": "Withheld in private-test catalogue",
        "registered_address_public": False,
        "contact_info": "",
        "contact_info_public": False,
        "industry_activity": spec.industry_activity,
        "ownership_structure": "Privately held",
        "beneficial_owners": [],
        "directors_officers": [],
        "authorized_signatories": [],
        "bank_account_details": {},
        "kyb_aml_observations": "Private-test borrower snapshot",
        "financial_risk": "Illustrative risk data only",
        "financials_currency": spec.currency,
        "assets_minor": spec.collateral_value_minor + spec.principal_minor,
        "liabilities_minor": spec.principal_minor,
        "revenue_last_year_minor": spec.principal_minor * 3,
        "profit_last_year_minor": spec.principal_minor // 8,
    }


class Command(BaseCommand):
    help = (
        "Publish ten clearly labelled, idempotent Loan Originator demo claims through the "
        "validated CSV import and production pricing paths."
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
                "Refusing to seed demo Loan Originator claims in production without "
                "--allow-production."
            )

        actor_email = str(options["actor_email"] or settings.GARANTA_SUPERADMIN_EMAIL).strip()
        if not actor_email:
            raise CommandError(
                "Set GARANTA_SUPERADMIN_EMAIL or provide --actor-email for audit attribution."
            )
        actor = get_user_model().objects.filter(email__iexact=actor_email).first()
        if actor is None or not is_admin_actor(actor):
            raise CommandError(f"Active admin actor does not exist: {actor_email}")

        required_currencies = {spec.currency for spec in DEMO_ORIGINATOR_LOAN_SPECS}
        enabled_currencies = set(
            Currency.objects.filter(code__in=required_currencies, is_enabled=True).values_list(
                "code", flat=True
            )
        )
        if missing := required_currencies - enabled_currencies:
            raise CommandError("Enable required currencies before seeding: " + ", ".join(missing))

        today = business_date(now_utc())
        created_originators = 0
        created_loans = 0
        skipped_loans = 0
        try:
            with transaction.atomic():
                originators: dict[str, LoanOriginator] = {}
                for originator_spec in DEMO_ORIGINATOR_SPECS:
                    existing = LoanOriginator.objects.filter(
                        jurisdiction="CH",
                        registration_number=originator_spec.registration_number,
                    ).first()
                    if existing is not None:
                        if existing.legal_name != originator_spec.legal_name:
                            raise CommandError(
                                "Demo registration number is already used by "
                                f"{existing.legal_name}."
                            )
                        if existing.status != LoanOriginatorStatus.ACTIVE:
                            raise CommandError(
                                f"Demo Loan Originator is not active: {existing.legal_name}."
                            )
                        originators[originator_spec.key] = existing
                        continue
                    self.stdout.write(f"PLAN originator {originator_spec.public_name}")
                    if options["dry_run"]:
                        continue
                    originators[originator_spec.key] = create_loan_originator(
                        CreateLoanOriginatorCommand(
                            actor=actor,
                            legal_name=originator_spec.legal_name,
                            public_name=originator_spec.public_name,
                            registration_number=originator_spec.registration_number,
                            jurisdiction="CH",
                            registered_address="BANXUM private-test address, Zurich, Switzerland",
                            contact_info="Private-test Loan Originator",
                            settlement_account_name=originator_spec.legal_name,
                            settlement_iban=DEMO_SETTLEMENT_IBAN,
                            settlement_bic="POFICHBEXXX",
                            kyb_evidence_reference=(
                                f"{SEED_NAME}:{SEED_VERSION}:{originator_spec.key}:kyb"
                            ),
                            kyb_aml_observations="Private-test originator only",
                            risk_observations="Illustrative data; not approved for real money",
                            status=LoanOriginatorStatus.ACTIVE,
                        )
                    )
                    created_originators += 1

                for loan_spec in DEMO_ORIGINATOR_LOAN_SPECS:
                    marker = _marker(loan_spec)
                    existing_import = (
                        OriginatorLoanImport.objects.select_related("loan")
                        .filter(source_filename=f"{marker}.csv", revision=1)
                        .first()
                    )
                    if existing_import is not None:
                        skipped_loans += 1
                        self.stdout.write(
                            f"SKIP {existing_import.loan.title} [{existing_import.loan.status}]"
                        )
                        continue
                    self.stdout.write(
                        f"PLAN {loan_spec.title} | "
                        f"{format_amount_minor(loan_spec.principal_minor, loan_spec.currency)} "
                        f"| coupon={loan_spec.coupon_bps // 100}."
                        f"{loan_spec.coupon_bps % 100:02d}% "
                        f"| yield={loan_spec.target_yield_bps // 100}."
                        f"{loan_spec.target_yield_bps % 100:02d}% "
                        f"| {loan_spec.term_months} months"
                    )
                    if options["dry_run"]:
                        continue
                    originator = originators[loan_spec.originator_key]
                    result = create_originator_loan(
                        CreateOriginatorLoanCommand(
                            actor=actor,
                            originator_id=str(originator.id),
                            title=loan_spec.title,
                            investor_summary=loan_spec.investor_summary,
                            purpose=loan_spec.purpose,
                            purpose_description=loan_spec.purpose_description,
                            currency=loan_spec.currency,
                            original_principal_minor=loan_spec.principal_minor,
                            interest_rate_bps=loan_spec.coupon_bps,
                            target_yield_bps=loan_spec.target_yield_bps,
                            minimum_investment_minor=loan_spec.minimum_investment_minor,
                            repayment_type=loan_spec.repayment_type,
                            interest_only_months=loan_spec.interest_only_months,
                            collateral_type=loan_spec.collateral_type,
                            collateral_value_minor=loan_spec.collateral_value_minor,
                            collateral_description=loan_spec.collateral_description,
                            risk_rating=loan_spec.risk_rating,
                            csv_content=_csv_content(loan_spec, today=today),
                            source_filename=f"{marker}.csv",
                            as_of_date=today,
                            borrower_snapshot=_borrower_snapshot(loan_spec),
                        )
                    )
                    profile = publish_originator_loan(
                        PublishOriginatorLoanCommand(
                            actor=actor,
                            loan_id=str(result.loan.id),
                            as_of_date=today,
                        )
                    )
                    if (
                        profile.opportunity_status != OriginatorOpportunityStatus.OPEN
                        or profile.unsold_principal_minor != loan_spec.principal_minor
                    ):
                        raise CommandError(
                            f"Demo originator claim did not reach the expected open state: "
                            f"{result.loan.id}"
                        )
                    created_loans += 1
        except OriginatorClaimsError as exc:
            raise CommandError(str(exc)) from exc

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete: {len(DEMO_ORIGINATOR_LOAN_SPECS) - skipped_loans} "
                    f"loans planned, {skipped_loans} already present."
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                "Demo Loan Originator catalogue ready: "
                f"{created_originators} originators created, {created_loans} loans created, "
                f"{skipped_loans} loans skipped."
            )
        )
