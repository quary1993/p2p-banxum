import type {
  BalanceLot,
  BalanceSummary,
  FxHistoryPortal,
  InvestorActivity,
  InvestorBalancePortal,
  InvestorDashboard,
  InvestorPortfolio,
  MarketplaceLoanDetail,
  MarketplaceLoanPreview,
  MarketplaceOriginalLoanScheduleRow,
  PortfolioExposure,
  PortfolioSummary,
  PrimaryOrdersPortal,
  SecondaryMarketActivityPortal,
  SecondaryMarketBuyerListing,
  SecondaryMarketBuyerListingDetail
} from "../api/generated/banxumApi";
import type { InvestorPortalFixture } from "./types";

const investorId = "demo-investor-1";

const amount = (value: number) => Math.round(value * 100);

// Dynamic dates keep the portfolio earnings calendar meaningful in preview
// mode regardless of when the fixtures are viewed.
const fixtureIsoDate = (monthsAhead: number, day: number) => {
  const now = new Date();
  const base = new Date(now.getFullYear(), now.getMonth() + monthsAhead, 1);
  const lastDay = new Date(base.getFullYear(), base.getMonth() + 1, 0).getDate();
  const date = new Date(base.getFullYear(), base.getMonth(), Math.min(day, lastDay));
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

export const portalFixture: InvestorPortalFixture = {
  today: "2026-06-05",
  profile: {
    id: investorId,
    name: "Lukas Brunner",
    initials: "LB",
    email: "lukas.brunner@example.ch",
    country: "Switzerland",
    memberSince: "2025-11-12",
    phone: "+41 79 ... .. 42"
  },
  depositInstructions: [
    {
      currency: "CHF",
      iban: "CH11 83019 GARANTAFI001",
      qrIban: "CH83 30334 GARANTAFI001",
      qrBillPayload:
        "SPC\n0200\n1\nCH1183019GARANTAFI001\nS\nGaranta Finanzgruppe AG\nSchauplatzgasse\n26\n3011\nBern\nCH\n\n\n\n\n\n\n\n\nCHF\n\n\n\n\n\n\nNON\n\n\nEPD\n\n\n",
      bic: "YAPECHZ2",
      bank: "Yapeal",
      reference: "BX-LBR-CHF-4471"
    },
    {
      currency: "EUR",
      iban: "CH81 83019 GARANTAFI002",
      bic: "YAPECHZ2",
      bank: "Yapeal",
      reference: "BX-LBR-EUR-4471"
    }
  ],
  documents: [
    {
      id: "D-9001",
      title: "Platform Terms of Use",
      type: "Agreement",
      version: "v4.2",
      date: "2025-11-12",
      context: "Registration",
      size: "186 KB"
    },
    {
      id: "D-9002",
      title: "Generic P2P Lending Risk Acknowledgement",
      type: "Risk",
      version: "v3.0",
      date: "2025-11-12",
      context: "Registration",
      size: "92 KB"
    },
    {
      id: "D-9120",
      title: "Loan Claim Assignment - GA-2310",
      type: "Assignment",
      version: "v1.0",
      date: "2026-01-18",
      context: "Investment GA-2310",
      size: "204 KB"
    },
    {
      id: "D-9300",
      title: "Currency Exchange Confirmation - FX-7741",
      type: "Confirmation",
      version: "v1.0",
      date: "2026-05-30",
      context: "FX FX-7741",
      size: "88 KB"
    },
    {
      id: "D-9400",
      title: "Investor Statement - Q1 2026",
      type: "Statement",
      version: "-",
      date: "2026-04-02",
      context: "Quarterly",
      size: "312 KB"
    },
    {
      id: "D-9500",
      title: "Annual Lender Tax Information Statement - 2025",
      type: "Tax",
      version: "-",
      date: "2026-02-15",
      context: "Annual",
      size: "276 KB"
    }
  ],
  notifications: [
    {
      id: "N1",
      tone: "warn",
      title: "Balance ageing - day 57",
      body: "CHF 980.00 from a recovery distribution must be withdrawn within 3 days.",
      time: "2 days ago",
      unread: true
    },
    {
      id: "N2",
      tone: "bad",
      title: "Loan in default",
      body: "GA-2201 is now 64 days past due.",
      time: "3 days ago",
      unread: true
    }
  ],
  recoverySplit: {
    loanId: "GA-2150",
    totalMinor: amount(980),
    currency: "CHF",
    parts: [
      { label: "Principal", amountMinor: amount(612) },
      { label: "Contractual interest", amountMinor: amount(188) },
      { label: "Default / penalty interest", amountMinor: amount(96) },
      { label: "Recovery costs / fees", amountMinor: -amount(42) },
      { label: "Rounding difference", amountMinor: 0 }
    ]
  }
};

const chfSummary: BalanceSummary = {
  investor_user_id: investorId,
  currency: "CHF",
  total_available_minor: amount(28190),
  investable_minor: amount(20090),
  withdraw_only_minor: amount(3120),
  overdue_minor: amount(980),
  frozen_minor: 0,
  penalty_mode_minor: 0,
  lot_count: 5,
  active_lot_count: 5,
  next_investment_deadline_at: "2026-06-08T00:00:00+02:00",
  next_withdrawal_deadline_at: "2026-06-08T00:00:00+02:00"
};

const eurSummary: BalanceSummary = {
  investor_user_id: investorId,
  currency: "EUR",
  total_available_minor: amount(7420),
  investable_minor: amount(5220),
  withdraw_only_minor: amount(2200),
  overdue_minor: 0,
  frozen_minor: 0,
  penalty_mode_minor: 0,
  lot_count: 3,
  active_lot_count: 3,
  next_investment_deadline_at: "2026-06-14T00:00:00+02:00",
  next_withdrawal_deadline_at: "2026-06-19T00:00:00+02:00"
};

export const balanceLotsFixture: BalanceLot[] = [
  {
    id: "L-2041",
    currency: "CHF",
    source_type: "repayment_interest",
    status: "available",
    bucket: "investable",
    received_at: "2026-05-28T00:00:00+02:00",
    investment_deadline_at: "2026-06-27T00:00:00+02:00",
    withdrawal_deadline_at: "2026-07-27T00:00:00+02:00",
    days_until_investment_deadline: 22,
    days_until_withdrawal_deadline: 52,
    original_amount_minor: amount(1840),
    available_amount_minor: amount(1840),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: false,
    blocks_financial_actions: false
  },
  {
    id: "L-2038",
    currency: "CHF",
    source_type: "repayment_principal",
    status: "available",
    bucket: "investable",
    received_at: "2026-05-21T00:00:00+02:00",
    investment_deadline_at: "2026-06-20T00:00:00+02:00",
    withdrawal_deadline_at: "2026-07-20T00:00:00+02:00",
    days_until_investment_deadline: 15,
    days_until_withdrawal_deadline: 45,
    original_amount_minor: amount(6250),
    available_amount_minor: amount(6250),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: false,
    blocks_financial_actions: false
  },
  {
    id: "L-2030",
    currency: "CHF",
    source_type: "deposit",
    status: "available",
    bucket: "investable",
    received_at: "2026-05-09T00:00:00+02:00",
    investment_deadline_at: "2026-06-08T00:00:00+02:00",
    withdrawal_deadline_at: "2026-07-08T00:00:00+02:00",
    days_until_investment_deadline: 3,
    days_until_withdrawal_deadline: 33,
    original_amount_minor: amount(12000),
    available_amount_minor: amount(12000),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: false,
    blocks_financial_actions: false
  },
  {
    id: "L-2019",
    currency: "CHF",
    source_type: "repayment_principal",
    status: "available",
    bucket: "withdraw_only",
    received_at: "2026-04-23T00:00:00+02:00",
    investment_deadline_at: "2026-05-23T00:00:00+02:00",
    withdrawal_deadline_at: "2026-06-22T00:00:00+02:00",
    days_until_investment_deadline: 0,
    days_until_withdrawal_deadline: 17,
    original_amount_minor: amount(3120),
    available_amount_minor: amount(3120),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: true,
    blocks_financial_actions: false
  },
  {
    id: "L-2007",
    currency: "CHF",
    source_type: "recovery_distribution",
    status: "available",
    bucket: "overdue",
    received_at: "2026-04-09T00:00:00+02:00",
    investment_deadline_at: "2026-05-09T00:00:00+02:00",
    withdrawal_deadline_at: "2026-06-08T00:00:00+02:00",
    days_until_investment_deadline: 0,
    days_until_withdrawal_deadline: 3,
    original_amount_minor: amount(980),
    available_amount_minor: amount(980),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: true,
    blocks_financial_actions: false
  },
  {
    id: "L-1990",
    currency: "EUR",
    source_type: "fx_proceeds",
    status: "available",
    bucket: "investable",
    received_at: "2026-05-30T00:00:00+02:00",
    investment_deadline_at: "2026-06-11T00:00:00+02:00",
    withdrawal_deadline_at: "2026-07-11T00:00:00+02:00",
    days_until_investment_deadline: 6,
    days_until_withdrawal_deadline: 36,
    original_amount_minor: amount(4500),
    available_amount_minor: amount(4500),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: false,
    blocks_financial_actions: false
  },
  {
    id: "L-1984",
    currency: "EUR",
    source_type: "repayment_interest",
    status: "available",
    bucket: "investable",
    received_at: "2026-05-15T00:00:00+02:00",
    investment_deadline_at: "2026-06-14T00:00:00+02:00",
    withdrawal_deadline_at: "2026-07-14T00:00:00+02:00",
    days_until_investment_deadline: 9,
    days_until_withdrawal_deadline: 39,
    original_amount_minor: amount(720),
    available_amount_minor: amount(720),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: false,
    blocks_financial_actions: false
  },
  {
    id: "L-1971",
    currency: "EUR",
    source_type: "deposit",
    status: "available",
    bucket: "withdraw_only",
    received_at: "2026-04-20T00:00:00+02:00",
    investment_deadline_at: "2026-05-20T00:00:00+02:00",
    withdrawal_deadline_at: "2026-06-19T00:00:00+02:00",
    days_until_investment_deadline: 0,
    days_until_withdrawal_deadline: 14,
    original_amount_minor: amount(2200),
    available_amount_minor: amount(2200),
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: true,
    blocks_financial_actions: false
  }
];

export const balancesFixture: InvestorBalancePortal = {
  as_of: "2026-06-05T10:00:00+02:00",
  summaries: [chfSummary, eurSummary],
  lots: balanceLotsFixture,
  payout_instructions: [
    {
      id: "ib1",
      currency: "CHF",
      status: "active",
      destination_iban: "CH93 0076 2011 6238 5295 7",
      destination_account_name: "Lukas Brunner",
      is_verified_usable: true,
      verified_at: "2026-05-18T12:00:00+02:00",
      created_at: "2026-05-18T11:50:00+02:00"
    }
  ],
  has_penalty_mode_balance: false
};

type DirectMarketplaceFixtureInput = Omit<
  MarketplaceLoanPreview,
  | "product_type"
  | "investment_flow"
  | "yield_bps"
  | "underlying_interest_rate_bps"
  | "remaining_term_days"
  | "maturity_date"
  | "loan_status"
  | "opportunity_status"
  | "fillable_amount_minor"
  | "originator_id"
  | "originator_name"
  | "borrower_display_name"
>;

const directMarketplaceLoansFixture: DirectMarketplaceFixtureInput[] = [
  {
    loan_id: "GA-2401",
    title: "Helvetia Logistik AG",
    purpose: "Warehouse refinancing",
    collateral_type: "Commercial real estate",
    interest_rate_bps: 740,
    term_months: 24,
    risk_rating: "B",
    funding_deadline: "2026-06-19",
    status: "published",
    currency: "CHF",
    principal_minor: amount(1450000),
    committed_principal_minor: amount(1087500),
    remaining_capacity_minor: amount(362500),
    minimum_investment_minor: amount(1000),
    ltv_bps: 5800,
    is_refinancing: true
  },
  {
    loan_id: "GA-2399",
    title: "Rhône Vignobles SA",
    purpose: "Equipment renewal",
    collateral_type: "Agricultural land",
    interest_rate_bps: 680,
    term_months: 18,
    risk_rating: "A",
    funding_deadline: "2026-06-11",
    status: "published",
    currency: "CHF",
    principal_minor: amount(620000),
    committed_principal_minor: amount(558000),
    remaining_capacity_minor: amount(62000),
    minimum_investment_minor: amount(1000),
    ltv_bps: 4900,
    is_refinancing: false
  },
  {
    loan_id: "GA-2402",
    title: "Nordwind Energie GmbH",
    purpose: "Solar bridge financing",
    collateral_type: "Solar plant and equipment",
    interest_rate_bps: 810,
    term_months: 36,
    risk_rating: "B",
    funding_deadline: "2026-06-27",
    status: "published",
    currency: "EUR",
    principal_minor: amount(1980000),
    committed_principal_minor: amount(415800),
    remaining_capacity_minor: amount(1564200),
    minimum_investment_minor: amount(1000),
    ltv_bps: 5800,
    is_refinancing: false
  },
  {
    loan_id: "GA-2395",
    title: "Adriatic Marine d.o.o.",
    purpose: "Charter receivables working capital",
    collateral_type: "Vessel and receivables",
    interest_rate_bps: 930,
    term_months: 24,
    risk_rating: "C",
    funding_deadline: "2026-06-02",
    status: "funded",
    currency: "EUR",
    principal_minor: amount(540000),
    committed_principal_minor: amount(540000),
    remaining_capacity_minor: 0,
    minimum_investment_minor: amount(1000),
    ltv_bps: 6200,
    is_refinancing: false
  },
  {
    loan_id: "GA-2390",
    title: "Léman BioTech SA",
    purpose: "Bridge to Series B",
    collateral_type: "Unsecured exception",
    interest_rate_bps: 1020,
    term_months: 12,
    risk_rating: "C",
    funding_deadline: "2026-06-14",
    status: "published",
    currency: "CHF",
    principal_minor: amount(300000),
    committed_principal_minor: amount(270000),
    remaining_capacity_minor: amount(30000),
    minimum_investment_minor: amount(1000),
    ltv_bps: null,
    is_refinancing: false
  }
];

const directMarketplaceLoanPreviews: MarketplaceLoanPreview[] = directMarketplaceLoansFixture.map(
  (loan) => ({
    ...loan,
    product_type: "direct",
    investment_flow: "primary_order",
    yield_bps: loan.interest_rate_bps,
    underlying_interest_rate_bps: loan.interest_rate_bps,
    remaining_term_days: null,
    maturity_date: null,
    loan_status: loan.status,
    opportunity_status: loan.status === "published" ? "open" : "closed",
    fillable_amount_minor: loan.remaining_capacity_minor,
    originator_id: null,
    originator_name: null,
    borrower_display_name: loan.title
  })
);

const originatorMarketplaceLoanFixture: MarketplaceLoanPreview = {
  loan_id: "LO-2601",
  product_type: "originator_claim",
  investment_flow: "immediate_claim_assignment",
  title: "Swiss SME equipment claim",
  purpose: "Equipment financing",
  collateral_type: "Machinery and equipment",
  // Compatibility field: investor screens display yield_bps, never this as borrower coupon.
  interest_rate_bps: 710,
  yield_bps: 710,
  underlying_interest_rate_bps: 1080,
  term_months: 9,
  remaining_term_days: 271,
  risk_rating: "B",
  funding_deadline: null,
  maturity_date: fixtureIsoDate(9, 28),
  status: "published",
  loan_status: "active",
  opportunity_status: "open",
  currency: "CHF",
  principal_minor: amount(180_000),
  committed_principal_minor: amount(45_000),
  remaining_capacity_minor: amount(135_000),
  fillable_amount_minor: amount(138_420),
  minimum_investment_minor: amount(500),
  ltv_bps: 5450,
  is_refinancing: false,
  originator_id: "originator-alpine-credit",
  originator_name: "Alpine Credit Partners AG",
  borrower_display_name: "Established Swiss precision manufacturer"
};

export const marketplaceLoansFixture: MarketplaceLoanPreview[] = [
  ...directMarketplaceLoanPreviews,
  originatorMarketplaceLoanFixture
];

// Original loan being refinanced by GA-2401 (Helvetia Logistik AG). Equal-installment
// schedule: CHF 2,400,000 over 24 months at 8.4% p.a. (0.7% per month on outstanding),
// CHF 100,000 principal per installment. The borrower paid the first 9 installments
// before publication, leaving CHF 1,500,000 outstanding; BANXUM lenders refinance
// CHF 1,450,000 of it (financeable principal may be less than remaining outstanding).
const refinancedOriginalPrincipalMinor = amount(2_400_000);
const refinancedOriginalInterestRateBps = 840;
const refinancedOriginalTermMonths = 24;
const refinancedOriginalLoanStartDate = "2025-08-29";

const refinancedOriginalScheduleFixture: MarketplaceOriginalLoanScheduleRow[] = Array.from(
  { length: refinancedOriginalTermMonths },
  (_, index) => {
    const outstandingBeforeMinor = refinancedOriginalPrincipalMinor - index * amount(100_000);
    const principalMinor = amount(100_000);
    const interestMinor = Math.round(outstandingBeforeMinor * 0.007);
    return {
      installment_number: index + 1,
      // Last day of each month from 2025-09-30 onwards.
      due_date: new Date(Date.UTC(2025, 9 + index, 0)).toISOString().slice(0, 10),
      principal_minor: principalMinor,
      interest_minor: interestMinor,
      total_minor: principalMinor + interestMinor,
      outstanding_after_minor: outstandingBeforeMinor - principalMinor,
      paid_before_publication: index < 9
    };
  }
);

const directLoanDetailsFixture: MarketplaceLoanDetail[] = directMarketplaceLoanPreviews.map((loan) => ({
  ...loan,
  borrower_id: `borrower-${loan.loan_id}`,
  borrower_disclosure: {
    legal_name: loan.title,
    year_founded: loan.loan_id === "GA-2402" ? 2018 : 2011,
    business_classification:
      loan.loan_id === "GA-2402"
        ? "Renewable-energy bridge finance"
        : "Real-estate backed corporate borrower",
    registered_address:
      loan.currency === "CHF" ? "Zugerstrasse 18, 6300 Zug, Switzerland" : "Kaiserstrasse 12, 60311 Frankfurt am Main, Germany",
    contact_info: "Investor-facing contact is handled through Garanta Finanzgruppe AG.",
    country: loan.currency === "CHF" ? "CH" : "DE",
    financials_currency: loan.currency,
    assets_minor: loan.loan_id === "GA-2402" ? amount(5_800_000) : amount(12_400_000),
    liabilities_minor: loan.loan_id === "GA-2402" ? amount(2_900_000) : amount(7_200_000),
    revenue_last_year_minor: loan.loan_id === "GA-2402" ? amount(1_240_000) : amount(3_800_000),
    profit_last_year_minor: loan.loan_id === "GA-2402" ? amount(160_000) : amount(420_000),
    documents: [
      {
        id: `${loan.loan_id}-borrower-presentation`,
        document_type: "borrower_presentation",
        display_name: "Borrower presentation",
        description: "Investor-visible borrower overview linked by Garanta."
      },
      {
        id: `${loan.loan_id}-financial-summary`,
        document_type: "financial_summary",
        display_name: "Borrower financial summary",
        description: "Clean-scanned financial summary available to lenders."
      }
    ]
  },
  investor_summary:
    "Admin-entered borrower disclosure. Optional fields are omitted by the backend when absent.",
  purpose_description:
    loan.loan_id === "GA-2401"
      ? "Refinancing of a distribution warehouse near Duebendorf and working capital for fleet expansion."
      : loan.purpose,
  collateral_value_minor:
    loan.collateral_type === "Unsecured exception"
      ? 0
      : loan.loan_id === "GA-2399"
        ? amount(1265000)
        : amount(2500000),
  collateral_description: loan.collateral_type,
  ltv_bps:
    loan.collateral_type === "Unsecured exception"
      ? null
      : loan.loan_id === "GA-2399"
        ? 4900
        : 5800,
  ltv_warnings: loan.collateral_type === "Unsecured exception" ? ["No LTV shown for unsecured loan."] : [],
  original_principal_minor: loan.is_refinancing ? refinancedOriginalPrincipalMinor : 0,
  original_interest_rate_bps: loan.is_refinancing ? refinancedOriginalInterestRateBps : null,
  original_term_months: loan.is_refinancing ? refinancedOriginalTermMonths : null,
  original_repayment_type: loan.is_refinancing ? "amortizing_principal_interest" : null,
  original_interest_only_months: loan.is_refinancing ? 0 : null,
  original_loan_start_date: loan.is_refinancing ? refinancedOriginalLoanStartDate : null,
  original_loan_schedule: loan.is_refinancing ? refinancedOriginalScheduleFixture : [],
  repayment_type: loan.term_months >= 24 ? "bullet" : "equal_installments",
  loan_start_date: "2026-06-30",
  first_payment_date: "2026-07-31",
  schedule_version: 1
}));

const originatorPricingDate = fixtureIsoDate(0, 5);
const originatorScheduleFixture = [
  {
    installment_number: 1,
    accrual_start_date: fixtureIsoDate(-1, 28),
    due_date: fixtureIsoDate(0, 28),
    opening_principal_minor: amount(180_000),
    principal_minor: amount(20_000),
    interest_minor: amount(1_620),
    penalty_minor: 0,
    fee_minor: 0,
    total_minor: amount(21_620),
    outstanding_after_minor: amount(160_000)
  },
  {
    installment_number: 2,
    accrual_start_date: fixtureIsoDate(0, 28),
    due_date: fixtureIsoDate(1, 28),
    opening_principal_minor: amount(160_000),
    principal_minor: amount(20_000),
    interest_minor: amount(1_440),
    penalty_minor: 0,
    fee_minor: 0,
    total_minor: amount(21_440),
    outstanding_after_minor: amount(140_000)
  },
  {
    installment_number: 3,
    accrual_start_date: fixtureIsoDate(1, 28),
    due_date: fixtureIsoDate(2, 28),
    opening_principal_minor: amount(140_000),
    principal_minor: amount(20_000),
    interest_minor: amount(1_260),
    penalty_minor: 0,
    fee_minor: 0,
    total_minor: amount(21_260),
    outstanding_after_minor: amount(120_000)
  },
  {
    installment_number: 4,
    accrual_start_date: fixtureIsoDate(2, 28),
    due_date: fixtureIsoDate(9, 28),
    opening_principal_minor: amount(120_000),
    principal_minor: amount(120_000),
    interest_minor: amount(7_560),
    penalty_minor: 0,
    fee_minor: 0,
    total_minor: amount(127_560),
    outstanding_after_minor: 0
  }
];

const originatorLoanDetailFixture: MarketplaceLoanDetail = {
  ...originatorMarketplaceLoanFixture,
  borrower_id: null,
  borrower_disclosure: {
    legal_name: "Established Swiss precision manufacturer",
    year_founded: 2007,
    business_classification: "Precision component manufacturing",
    country: "CH",
    industry_activity: "Industrial manufacturing",
    financials_currency: "CHF",
    assets_minor: amount(4_850_000),
    liabilities_minor: amount(2_120_000),
    revenue_last_year_minor: amount(3_760_000),
    profit_last_year_minor: amount(315_000)
  },
  investor_summary:
    "Existing final-borrower loan offered by a Loan Originator. Purchasing immediately assigns the selected legal claim to the investor.",
  purpose_description:
    "Financing of production machinery. Garanta services the claim while investor ownership remains outstanding.",
  collateral_value_minor: amount(3_300_000),
  collateral_description: "First-ranking security over financed machinery and equipment.",
  ltv_warnings: [],
  original_principal_minor: amount(240_000),
  original_interest_rate_bps: 1080,
  original_term_months: 12,
  original_repayment_type: "amortizing_principal_interest",
  original_interest_only_months: 0,
  original_loan_start_date: fixtureIsoDate(-3, 28),
  original_loan_schedule: [],
  repayment_type: "amortizing_principal_interest",
  loan_start_date: fixtureIsoDate(-3, 28),
  first_payment_date: fixtureIsoDate(0, 28),
  schedule_version: 1,
  originator_schedule: originatorScheduleFixture,
  originator_payment_history: [
    {
      reference: "LO-2601-PAY-001",
      value_date: fixtureIsoDate(-1, 28),
      payment_type: "scheduled",
      principal_minor: amount(20_000),
      interest_minor: amount(1_800),
      penalty_minor: 0,
      fee_minor: 0,
      total_minor: amount(21_800),
      resulting_principal_minor: amount(180_000)
    }
  ],
  schedule_revision: 1,
  pricing_as_of_date: originatorPricingDate
};

export const loanDetailsFixture: MarketplaceLoanDetail[] = [
  ...directLoanDetailsFixture,
  originatorLoanDetailFixture
];

const portfolioSummary: PortfolioSummary = {
  holding_count: 7,
  active_holding_count: 6,
  outstanding_principal_by_currency: [
    { currency: "CHF", amount_minor: amount(18450.5) },
    { currency: "EUR", amount_minor: amount(18000) }
  ],
  original_principal_by_currency: [
    { currency: "CHF", amount_minor: amount(36500) },
    { currency: "EUR", amount_minor: amount(18000) }
  ],
  realized_interest_by_currency: [
    { currency: "CHF", amount_minor: amount(2255.1) },
    { currency: "EUR", amount_minor: amount(1314) }
  ],
  late_or_defaulted_exposure_by_currency: [
    { currency: "EUR", amount_minor: amount(18000) }
  ]
};

const exposureFixture: PortfolioExposure = {
  by_borrower: [
    { key: "bodensee", name: "Bodensee Immobilien GmbH", currency: "EUR", outstanding_principal_minor: amount(12000), holding_count: 1 },
    { key: "engadin", name: "Engadin Hospitality AG", currency: "CHF", outstanding_principal_minor: amount(8420.5), holding_count: 1 },
    { key: "jura", name: "Jura Précision SA", currency: "CHF", outstanding_principal_minor: amount(5210), holding_count: 1 }
  ],
  by_country: [
    { key: "CH", name: "Switzerland", currency: "CHF", outstanding_principal_minor: amount(18450.5), holding_count: 5 },
    { key: "DE", name: "Germany", currency: "EUR", outstanding_principal_minor: amount(12000), holding_count: 1 },
    { key: "FR", name: "France", currency: "EUR", outstanding_principal_minor: amount(6000), holding_count: 1 }
  ],
  by_purpose: [
    { key: "real_estate", name: "Real estate", currency: "EUR", outstanding_principal_minor: amount(12000), holding_count: 1 },
    { key: "manufacturing", name: "Manufacturing", currency: "CHF", outstanding_principal_minor: amount(5210), holding_count: 1 }
  ],
  by_risk_rating: [
    { key: "A", name: "A", currency: "CHF", outstanding_principal_minor: amount(8850), holding_count: 2 },
    { key: "B", name: "B", currency: "CHF", outstanding_principal_minor: amount(20420.5), holding_count: 3 },
    { key: "C", name: "C", currency: "EUR", outstanding_principal_minor: amount(6000), holding_count: 1 }
  ],
  by_collateral_type: [
    { key: "real_estate", name: "Real estate", currency: "EUR", outstanding_principal_minor: amount(12000), holding_count: 1 },
    { key: "equipment", name: "Equipment", currency: "CHF", outstanding_principal_minor: amount(5210), holding_count: 1 }
  ],
  by_maturity: [
    { key: "0_12", name: "0-12 months", currency: "CHF", outstanding_principal_minor: amount(1180), holding_count: 1 },
    { key: "12_24", name: "12-24 months", currency: "CHF", outstanding_principal_minor: amount(13630.5), holding_count: 3 },
    { key: "24_plus", name: "24+ months", currency: "EUR", outstanding_principal_minor: amount(18000), holding_count: 2 }
  ],
  by_loan_status: [
    { key: "performing", name: "Performing", currency: "CHF", outstanding_principal_minor: amount(20450.5), holding_count: 4 },
    { key: "late", name: "Late", currency: "EUR", outstanding_principal_minor: amount(12000), holding_count: 1 },
    { key: "defaulted", name: "Defaulted", currency: "EUR", outstanding_principal_minor: amount(7180), holding_count: 2 }
  ]
};

const directPortfolioLoanFields = (
  yieldBps: number,
  collateralValueMinor: number,
  collateralDescription: string
) => ({
  product_type: "direct",
  originator_id: null,
  originator_name: "",
  collateral_value_minor: collateralValueMinor,
  collateral_description: collateralDescription,
  yield_bps: yieldBps,
  underlying_interest_rate_bps: yieldBps,
  skin_in_the_game_bps: 0
});

const directHoldingAcquisitionFields = (cashConsiderationMinor: number) => ({
  received_penalty_minor: 0,
  acquisition_cash_consideration_minor: cashConsiderationMinor,
  acquisition_cash_flow: []
});

export const portfolioFixture: InvestorPortfolio = {
  as_of: "2026-06-05T10:00:00+02:00",
  summary: portfolioSummary,
  exposure: exposureFixture,
  holdings: [
    {
      ...directHoldingAcquisitionFields(amount(10000)),
      id: "H-2310",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(10000),
      current_principal_minor: amount(8420.5),
      currency: "CHF",
      loan_share_ppm: 100000,
      assignment_effective_at: "2026-01-18T10:00:00+01:00",
      loan: {
        ...directPortfolioLoanFields(720, amount(163934.43), "Registered real-estate security supporting the borrower obligation."),
        loan_id: "GA-2310",
        loan_title: "Engadin Alpine refinancing",
        loan_status: "active",
        borrower_id: "borrower-2310",
        borrower_name: "Engadin Hospitality AG",
        borrower_country: "CH",
        purpose: "Hospitality refinancing",
        collateral_type: "real_estate",
        risk_rating: "B",
        interest_rate_bps: 720,
        default_penalty_interest_bps: 1200,
        term_months: 24,
        repayment_type: "equal_installments",
        currency: "CHF",
        is_refinancing: true,
        original_principal_minor: amount(100000),
        original_repayment_type: "equal_installments",
        original_interest_only_months: 0,
        principal_minor: amount(100000),
        funding_deadline: "2026-01-31",
        loan_start_date: "2026-01-31",
        first_payment_date: "2026-02-28",
        ltv_bps: 6100,
        days_past_due: 0,
        schedule_version: 1,
        schedule: [
          {
            id: "GA-2310-I-1",
            schedule_version: 1,
            installment_number: 1,
            due_date: "2026-02-28",
            principal_minor: amount(15795),
            interest_minor: amount(6000),
            total_minor: amount(21795),
            paid_principal_minor: amount(15795),
            paid_interest_minor: amount(6000),
            outstanding_principal_minor: 0,
            outstanding_interest_minor: 0,
            outstanding_total_minor: 0,
            is_paid: true,
            days_past_due: 0,
            status: "paid",
            row_type: "repayment_event",
            label: "Installment 1 paid",
            payment_date: "2026-02-28"
          },
          {
            id: "GA-2310-I-2",
            schedule_version: 1,
            installment_number: 2,
            due_date: "2026-03-31",
            principal_minor: amount(42102.5),
            interest_minor: amount(590.5),
            total_minor: amount(42693),
            paid_principal_minor: 0,
            paid_interest_minor: 0,
            outstanding_principal_minor: amount(42102.5),
            outstanding_interest_minor: amount(590.5),
            outstanding_total_minor: amount(42693),
            is_paid: false,
            days_past_due: 0,
            status: "upcoming",
            row_type: "scheduled_installment",
            label: "Installment 2",
            payment_date: null
          },
          {
            id: "GA-2310-I-3",
            schedule_version: 1,
            installment_number: 3,
            due_date: "2026-04-30",
            principal_minor: amount(42102.5),
            interest_minor: amount(580.08),
            total_minor: amount(42682.58),
            paid_principal_minor: 0,
            paid_interest_minor: 0,
            outstanding_principal_minor: amount(42102.5),
            outstanding_interest_minor: amount(580.08),
            outstanding_total_minor: amount(42682.58),
            is_paid: false,
            days_past_due: 0,
            status: "upcoming",
            row_type: "scheduled_installment",
            label: "Installment 3",
            payment_date: null
          }
        ]
      },
      received_principal_minor: amount(1579.5),
      received_interest_minor: amount(600),
      repayment_fee_minor: 0,
      investment_schedule: [
        {
          loan_installment_id: "GA-2310-I-2",
          schedule_version: 1,
          installment_number: 2,
          due_date: "2026-03-31",
          projected_principal_minor: amount(4210.25),
          projected_interest_minor: amount(59.05),
          projected_total_minor: amount(4269.3),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "GA-2310-I-3",
          schedule_version: 1,
          installment_number: 3,
          due_date: "2026-04-30",
          projected_principal_minor: amount(4210.25),
          projected_interest_minor: amount(58.01),
          projected_total_minor: amount(4268.26),
          days_past_due: 0,
          status: "upcoming"
        }
      ],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null,
      open_secondary_listing: {
        id: "SM-H-2310",
        status: "active",
        publication_type: "automatic",
        price_bps: 10000,
        transfer_price_minor: amount(8420.5),
        seller_net_proceeds_minor: amount(8399.45),
        listed_at: "2026-06-04T11:30:00+02:00",
        updated_at: "2026-06-04T11:30:00+02:00"
      }
    },
    {
      ...directHoldingAcquisitionFields(amount(6000)),
      id: "H-2410",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(6000),
      current_principal_minor: amount(5210),
      currency: "CHF",
      loan_share_ppm: 60000,
      assignment_effective_at: "2026-02-10T10:00:00+01:00",
      loan: {
        ...directPortfolioLoanFields(940, amount(173076.92), "Registered security over financed precision tooling and equipment."),
        loan_id: "GA-2410",
        loan_title: "Jura precision tooling loan",
        loan_status: "active",
        borrower_id: "borrower-2410",
        borrower_name: "Jura Précision SA",
        borrower_country: "CH",
        purpose: "capex",
        collateral_type: "equipment",
        risk_rating: "BBB",
        interest_rate_bps: 940,
        default_penalty_interest_bps: 1400,
        term_months: 30,
        repayment_type: "equal_installments",
        currency: "CHF",
        is_refinancing: false,
        original_principal_minor: amount(90000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(90000),
        funding_deadline: "2026-02-05",
        loan_start_date: "2026-02-05",
        first_payment_date: "2026-03-05",
        ltv_bps: 5200,
        days_past_due: 0,
        schedule_version: 1,
        schedule: [
          {
            id: "GA-2410-I-1",
            schedule_version: 1,
            installment_number: 1,
            due_date: fixtureIsoDate(-2, 5),
            principal_minor: amount(2800),
            interest_minor: amount(705),
            total_minor: amount(3505),
            paid_principal_minor: amount(2800),
            paid_interest_minor: amount(705),
            outstanding_principal_minor: 0,
            outstanding_interest_minor: 0,
            outstanding_total_minor: 0,
            is_paid: true,
            days_past_due: 0,
            status: "paid",
            row_type: "repayment_event",
            label: "Installment 1 paid",
            payment_date: fixtureIsoDate(-2, 5)
          },
          {
            id: "GA-2410-I-2",
            schedule_version: 1,
            installment_number: 2,
            due_date: fixtureIsoDate(-1, 5),
            principal_minor: amount(2820),
            interest_minor: amount(683),
            total_minor: amount(3503),
            paid_principal_minor: amount(2820),
            paid_interest_minor: amount(683),
            outstanding_principal_minor: 0,
            outstanding_interest_minor: 0,
            outstanding_total_minor: 0,
            is_paid: true,
            days_past_due: 0,
            status: "paid",
            row_type: "repayment_event",
            label: "Installment 2 paid",
            payment_date: fixtureIsoDate(-1, 10)
          },
          {
            id: "GA-2410-I-3",
            schedule_version: 1,
            installment_number: 3,
            due_date: fixtureIsoDate(0, 26),
            principal_minor: amount(2840),
            interest_minor: amount(661),
            total_minor: amount(3501),
            paid_principal_minor: 0,
            paid_interest_minor: 0,
            outstanding_principal_minor: amount(2840),
            outstanding_interest_minor: amount(661),
            outstanding_total_minor: amount(3501),
            is_paid: false,
            days_past_due: 0,
            status: "upcoming",
            row_type: "scheduled_installment",
            label: "Installment 3",
            payment_date: null
          }
        ]
      },
      received_principal_minor: amount(337),
      received_interest_minor: amount(83),
      repayment_fee_minor: 0,
      investment_schedule: [
        {
          loan_installment_id: "GA-2410-I-3",
          schedule_version: 1,
          installment_number: 3,
          due_date: fixtureIsoDate(0, 26),
          projected_principal_minor: amount(170.4),
          projected_interest_minor: amount(39.66),
          projected_total_minor: amount(210.06),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "GA-2410-I-4",
          schedule_version: 1,
          installment_number: 4,
          due_date: fixtureIsoDate(1, 26),
          projected_principal_minor: amount(171.7),
          projected_interest_minor: amount(38.32),
          projected_total_minor: amount(210.02),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "GA-2410-I-5",
          schedule_version: 1,
          installment_number: 5,
          due_date: fixtureIsoDate(2, 26),
          projected_principal_minor: amount(173.1),
          projected_interest_minor: amount(36.98),
          projected_total_minor: amount(210.08),
          days_past_due: 0,
          status: "upcoming"
        }
      ],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null,
      open_secondary_listing: null
    },
    {
      ...directHoldingAcquisitionFields(amount(8000)),
      id: "H-2405",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(8000),
      current_principal_minor: amount(7300),
      currency: "CHF",
      loan_share_ppm: 80000,
      assignment_effective_at: "2026-03-02T10:00:00+01:00",
      loan: {
        ...directPortfolioLoanFields(1050, amount(181818.18), "Assigned trade receivables supporting the borrower obligation."),
        loan_id: "GA-2405",
        loan_title: "Rheintal logistics receivables",
        loan_status: "active",
        borrower_id: "borrower-2405",
        borrower_name: "Rheintal Logistik AG",
        borrower_country: "CH",
        purpose: "working_capital",
        collateral_type: "receivables",
        risk_rating: "BB+",
        interest_rate_bps: 1050,
        default_penalty_interest_bps: 1500,
        term_months: 18,
        repayment_type: "equal_installments",
        currency: "CHF",
        is_refinancing: false,
        original_principal_minor: amount(120000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(120000),
        funding_deadline: "2026-02-28",
        loan_start_date: "2026-02-28",
        first_payment_date: "2026-03-28",
        ltv_bps: 6600,
        days_past_due: 0,
        schedule_version: 1,
        schedule: [
          {
            id: "GA-2405-I-1",
            schedule_version: 1,
            installment_number: 1,
            due_date: fixtureIsoDate(-1, 12),
            principal_minor: amount(6200),
            interest_minor: amount(1050),
            total_minor: amount(7250),
            paid_principal_minor: amount(6200),
            paid_interest_minor: amount(1050),
            outstanding_principal_minor: 0,
            outstanding_interest_minor: 0,
            outstanding_total_minor: 0,
            is_paid: true,
            days_past_due: 0,
            status: "paid",
            row_type: "repayment_event",
            label: "Installment 1 paid",
            payment_date: fixtureIsoDate(-1, 12)
          },
          {
            id: "GA-2405-I-2",
            schedule_version: 1,
            installment_number: 2,
            due_date: fixtureIsoDate(0, 12),
            principal_minor: amount(6250),
            interest_minor: amount(996),
            total_minor: amount(7246),
            paid_principal_minor: 0,
            paid_interest_minor: 0,
            outstanding_principal_minor: amount(6250),
            outstanding_interest_minor: amount(996),
            outstanding_total_minor: amount(7246),
            is_paid: false,
            days_past_due: 0,
            status: "upcoming",
            row_type: "scheduled_installment",
            label: "Installment 2",
            payment_date: null
          }
        ]
      },
      received_principal_minor: amount(372),
      received_interest_minor: amount(63),
      repayment_fee_minor: 0,
      investment_schedule: [
        {
          loan_installment_id: "GA-2405-I-2",
          schedule_version: 1,
          installment_number: 2,
          due_date: fixtureIsoDate(0, 12),
          projected_principal_minor: amount(375),
          projected_interest_minor: amount(59.76),
          projected_total_minor: amount(434.76),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "GA-2405-I-3",
          schedule_version: 1,
          installment_number: 3,
          due_date: fixtureIsoDate(1, 12),
          projected_principal_minor: amount(378.3),
          projected_interest_minor: amount(56.48),
          projected_total_minor: amount(434.78),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "GA-2405-I-4",
          schedule_version: 1,
          installment_number: 4,
          due_date: fixtureIsoDate(2, 12),
          projected_principal_minor: amount(381.6),
          projected_interest_minor: amount(53.17),
          projected_total_minor: amount(434.77),
          days_past_due: 0,
          status: "upcoming"
        }
      ],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null,
      open_secondary_listing: null
    },
    {
      ...directHoldingAcquisitionFields(amount(6000)),
      id: "H-2402",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(6000),
      current_principal_minor: amount(6000),
      currency: "CHF",
      loan_share_ppm: 50000,
      assignment_effective_at: "2026-04-15T10:00:00+02:00",
      loan: {
        ...directPortfolioLoanFields(1400, 0, "Unsecured exception; no investor-facing collateral valuation."),
        loan_id: "GA-2402",
        loan_title: "Helvetia bridge to Series B",
        loan_status: "active",
        borrower_id: "borrower-2402",
        borrower_name: "Helvetia Software AG",
        borrower_country: "CH",
        purpose: "bridge_financing",
        collateral_type: "unsecured_exception",
        risk_rating: "B-",
        interest_rate_bps: 1400,
        default_penalty_interest_bps: 0,
        term_months: 12,
        repayment_type: "bullet_periodic_interest",
        currency: "CHF",
        is_refinancing: false,
        original_principal_minor: amount(120000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(120000),
        funding_deadline: "2026-04-10",
        loan_start_date: "2026-04-10",
        first_payment_date: "2026-05-10",
        ltv_bps: null,
        days_past_due: 0,
        schedule_version: 1,
        schedule: [
          {
            id: "GA-2402-I-1",
            schedule_version: 1,
            installment_number: 1,
            due_date: fixtureIsoDate(0, 20),
            principal_minor: 0,
            interest_minor: amount(1400),
            total_minor: amount(1400),
            paid_principal_minor: 0,
            paid_interest_minor: 0,
            outstanding_principal_minor: 0,
            outstanding_interest_minor: amount(1400),
            outstanding_total_minor: amount(1400),
            is_paid: false,
            days_past_due: 0,
            status: "upcoming",
            row_type: "scheduled_installment",
            label: "Installment 1",
            payment_date: null
          }
        ]
      },
      received_principal_minor: 0,
      received_interest_minor: 0,
      repayment_fee_minor: 0,
      investment_schedule: [
        {
          loan_installment_id: "GA-2402-I-1",
          schedule_version: 1,
          installment_number: 1,
          due_date: fixtureIsoDate(0, 20),
          projected_principal_minor: 0,
          projected_interest_minor: amount(70),
          projected_total_minor: amount(70),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "GA-2402-I-2",
          schedule_version: 1,
          installment_number: 2,
          due_date: fixtureIsoDate(1, 20),
          projected_principal_minor: 0,
          projected_interest_minor: amount(70),
          projected_total_minor: amount(70),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "GA-2402-I-3",
          schedule_version: 1,
          installment_number: 3,
          due_date: fixtureIsoDate(2, 20),
          projected_principal_minor: 0,
          projected_interest_minor: amount(70),
          projected_total_minor: amount(70),
          days_past_due: 0,
          status: "upcoming"
        }
      ],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null,
      open_secondary_listing: null
    },
    {
      ...directHoldingAcquisitionFields(amount(4880)),
      id: "H-2501",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(5000),
      current_principal_minor: amount(4600),
      currency: "EUR",
      loan_share_ppm: 40000,
      assignment_effective_at: "2026-03-12T10:00:00+01:00",
      loan: {
        loan_id: "LO-2501",
        product_type: "originator_claim",
        loan_title: "Nord Trans Cargo working capital",
        loan_status: "active",
        borrower_id: null,
        borrower_name: "Baltic logistics operator",
        borrower_country: "LT",
        originator_id: "originator-nord",
        originator_name: "Nord Capital Finance",
        purpose: "working_capital",
        collateral_type: "receivables",
        collateral_value_minor: amount(179687.5),
        collateral_description: "Assigned trade receivables supporting the underlying borrower claim.",
        skin_in_the_game_bps: 1500,
        risk_rating: "BB",
        interest_rate_bps: 980,
        yield_bps: 980,
        underlying_interest_rate_bps: 1250,
        default_penalty_interest_bps: 1100,
        term_months: 10,
        repayment_type: "equal_installments",
        currency: "EUR",
        is_refinancing: false,
        original_principal_minor: amount(125000),
        original_repayment_type: "equal_installments",
        original_interest_only_months: 0,
        principal_minor: amount(115000),
        funding_deadline: null,
        loan_start_date: "2026-01-15",
        first_payment_date: "2026-02-15",
        ltv_bps: 6400,
        days_past_due: 0,
        schedule_version: 1,
        schedule: [
          {
            id: "LO-2501-I-1",
            schedule_version: 1,
            installment_number: 1,
            due_date: fixtureIsoDate(-1, 15),
            principal_minor: amount(11200),
            interest_minor: amount(1198),
            total_minor: amount(12398),
            paid_principal_minor: amount(11200),
            paid_interest_minor: amount(1198),
            outstanding_principal_minor: 0,
            outstanding_interest_minor: 0,
            outstanding_total_minor: 0,
            is_paid: true,
            days_past_due: 0,
            status: "paid",
            row_type: "repayment_event",
            label: "Installment 1 paid",
            payment_date: fixtureIsoDate(-1, 15)
          },
          {
            id: "LO-2501-I-2",
            schedule_version: 1,
            installment_number: 2,
            due_date: fixtureIsoDate(0, 15),
            principal_minor: amount(11310),
            interest_minor: amount(1090),
            total_minor: amount(12400),
            paid_principal_minor: 0,
            paid_interest_minor: 0,
            outstanding_principal_minor: amount(11310),
            outstanding_interest_minor: amount(1090),
            outstanding_total_minor: amount(12400),
            is_paid: false,
            days_past_due: 0,
            status: "upcoming",
            row_type: "scheduled_installment",
            label: "Installment 2",
            payment_date: null
          }
        ]
      },
      received_principal_minor: amount(400),
      received_interest_minor: amount(48),
      repayment_fee_minor: 0,
      investment_schedule: [
        {
          loan_installment_id: "LO-2501-I-2",
          schedule_version: 1,
          installment_number: 2,
          due_date: fixtureIsoDate(0, 15),
          projected_principal_minor: amount(452.4),
          projected_interest_minor: amount(43.6),
          projected_total_minor: amount(496),
          days_past_due: 0,
          status: "upcoming"
        },
        {
          loan_installment_id: "LO-2501-I-3",
          schedule_version: 1,
          installment_number: 3,
          due_date: fixtureIsoDate(1, 15),
          projected_principal_minor: amount(456.9),
          projected_interest_minor: amount(39.1),
          projected_total_minor: amount(496),
          days_past_due: 0,
          status: "upcoming"
        }
      ],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null,
      open_secondary_listing: null
    },
    {
      ...directHoldingAcquisitionFields(amount(12000)),
      id: "H-2256",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(12000),
      current_principal_minor: amount(12000),
      currency: "EUR",
      loan_share_ppm: 90000,
      assignment_effective_at: "2025-11-15T10:00:00+01:00",
      loan: {
        ...directPortfolioLoanFields(800, amount(1230769.23), "Registered real-estate security supporting the borrower obligation."),
        loan_id: "GA-2256",
        loan_title: "Bodensee Immobilien GmbH",
        loan_status: "late",
        borrower_id: "borrower-2256",
        borrower_name: "Bodensee Immobilien GmbH",
        borrower_country: "DE",
        purpose: "Real estate bridge",
        collateral_type: "real_estate",
        risk_rating: "B",
        interest_rate_bps: 800,
        default_penalty_interest_bps: 1200,
        term_months: 36,
        repayment_type: "bullet",
        currency: "EUR",
        is_refinancing: false,
        original_principal_minor: amount(800000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(800000),
        funding_deadline: "2025-11-30",
        loan_start_date: "2025-11-30",
        first_payment_date: "2025-12-31",
        ltv_bps: 6500,
        days_past_due: 21,
        schedule_version: 1,
        schedule: []
      },
      received_principal_minor: 0,
      received_interest_minor: amount(1044),
      repayment_fee_minor: 0,
      investment_schedule: [],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: {
        id: "note-late",
        note_type: "payment_update",
        title: "Payment overdue; borrower contacted",
        occurred_at: "2026-05-20T09:00:00+02:00"
      },
      open_secondary_listing: null
    },
    {
      ...directHoldingAcquisitionFields(amount(6000)),
      id: "H-2201",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(6000),
      current_principal_minor: amount(6000),
      currency: "EUR",
      loan_share_ppm: 45000,
      assignment_effective_at: "2025-09-01T10:00:00+02:00",
      loan: {
        ...directPortfolioLoanFields(910, amount(571428.57), "Assigned receivables supporting the borrower obligation."),
        loan_id: "GA-2201",
        loan_title: "Savoie Logistique SAS",
        loan_status: "defaulted",
        borrower_id: "borrower-2201",
        borrower_name: "Savoie Logistique SAS",
        borrower_country: "FR",
        purpose: "Working capital",
        collateral_type: "receivables",
        risk_rating: "C",
        interest_rate_bps: 910,
        default_penalty_interest_bps: 1800,
        term_months: 24,
        repayment_type: "bullet",
        currency: "EUR",
        is_refinancing: false,
        original_principal_minor: amount(400000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(400000),
        funding_deadline: "2025-09-15",
        loan_start_date: "2025-09-15",
        first_payment_date: "2025-10-31",
        ltv_bps: 7000,
        days_past_due: 64,
        schedule_version: 1,
        schedule: []
      },
      received_principal_minor: 0,
      received_interest_minor: amount(270),
      repayment_fee_minor: 0,
      investment_schedule: [],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: {
        id: "note-default",
        note_type: "default_update",
        title: "Formal demand issued",
        occurred_at: "2026-05-18T09:00:00+02:00"
      },
      open_secondary_listing: null
    },
    {
      ...directHoldingAcquisitionFields(amount(5000)),
      id: "H-2150",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(5000),
      current_principal_minor: amount(1180),
      currency: "CHF",
      loan_share_ppm: 80000,
      assignment_effective_at: "2025-06-01T10:00:00+02:00",
      loan: {
        ...directPortfolioLoanFields(840, amount(333333.33), "Registered security over financed solar equipment."),
        loan_id: "GA-2150",
        loan_title: "Ticino Solar SA",
        loan_status: "defaulted",
        borrower_id: "borrower-2150",
        borrower_name: "Ticino Solar SA",
        borrower_country: "CH",
        purpose: "Solar equipment",
        collateral_type: "equipment",
        risk_rating: "D",
        interest_rate_bps: 840,
        default_penalty_interest_bps: 1600,
        term_months: 24,
        repayment_type: "equal_installments",
        currency: "CHF",
        is_refinancing: false,
        original_principal_minor: amount(250000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(250000),
        funding_deadline: "2025-06-15",
        loan_start_date: "2025-06-15",
        first_payment_date: "2025-07-31",
        ltv_bps: 7500,
        days_past_due: 142,
        schedule_version: 1,
        schedule: []
      },
      received_principal_minor: amount(3820),
      received_interest_minor: amount(95.2),
      repayment_fee_minor: 0,
      investment_schedule: [],
      recovered_principal_minor: amount(612),
      recovered_contractual_interest_minor: amount(188),
      recovered_default_interest_minor: amount(96),
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: {
        id: "note-recovery-update",
        note_type: "recovery_update",
        title: "Recovery process ongoing; residual recoveries possible",
        occurred_at: "2026-03-22T09:00:00+01:00"
      },
      open_secondary_listing: null
    }
  ]
};

export const activityFixture: InvestorActivity = {
  entries: [
    {
      id: "A-1",
      activity_type: "primary_order",
      occurred_at: "2026-06-04T14:22:00+02:00",
      direction: "out",
      title: "Investment order placed",
      amount_minor: -amount(5000),
      currency: "CHF",
      status: "pending_allocation",
      loan_id: "GA-2403",
      loan_title: "Tessin Bauwerk AG",
      metadata: { category: "principal" }
    },
    {
      id: "A-2",
      activity_type: "fx_exchange",
      occurred_at: "2026-05-30T11:03:00+02:00",
      direction: "in",
      title: "Currency exchange CHF to EUR",
      amount_minor: amount(4500.86),
      currency: "EUR",
      status: "settled",
      loan_id: null,
      loan_title: "",
      metadata: { category: "principal" }
    },
    {
      id: "A-3",
      activity_type: "interest_distribution",
      occurred_at: "2026-05-28T06:00:00+02:00",
      direction: "in",
      title: "Interest distribution",
      amount_minor: amount(148.2),
      currency: "CHF",
      status: "settled",
      loan_id: "GA-2310",
      loan_title: "Engadin Alpine refinancing",
      metadata: { category: "income" }
    },
    {
      id: "A-4",
      activity_type: "secondary_market_fee",
      occurred_at: "2026-04-30T15:18:00+02:00",
      direction: "out",
      title: "Secondary-market seller fee",
      amount_minor: -amount(12.3),
      currency: "CHF",
      status: "settled",
      loan_id: "GA-2199",
      loan_title: "Holding transfer",
      metadata: { category: "cost" }
    }
  ]
};

export const dashboardFixture: InvestorDashboard = {
  as_of: "2026-06-05T10:00:00+02:00",
  investor_user_id: investorId,
  balances: balancesFixture.summaries,
  portfolio_summary: portfolioSummary,
  exposure: exposureFixture,
  pending_actions: [
    {
      type: "balance_ageing",
      severity: "warn",
      currency: "CHF",
      amount_minor: amount(980),
      count: 1,
      message: "CHF 980.00 reaches the 60-day deadline in 3 days."
    },
    {
      type: "loan_default",
      severity: "bad",
      amount_minor: amount(6000),
      currency: "EUR",
      count: 1,
      message: "GA-2201 is in default and 64 days past due."
    }
  ],
  recent_activity: activityFixture.entries
};

export const primaryOrdersFixture: PrimaryOrdersPortal = {
  orders: [
    {
      id: "O-58120",
      loan_id: "GA-2403",
      loan_title: "Tessin Bauwerk AG",
      loan_status: "open",
      status: "pending_allocation",
      requested_amount_minor: amount(5000),
      allocated_amount_minor: 0,
      currency: "CHF",
      created_at: "2026-06-04T14:22:00+02:00",
      allocated_at: null,
      released_at: null,
      closed_at: null
    },
    {
      id: "O-58102",
      loan_id: "GA-2401",
      loan_title: "Helvetia Logistik AG",
      loan_status: "open",
      status: "partially_allocated",
      requested_amount_minor: amount(10000),
      allocated_amount_minor: amount(6500),
      currency: "CHF",
      created_at: "2026-06-02T09:10:00+02:00",
      allocated_at: "2026-06-02T10:10:00+02:00",
      released_at: null,
      closed_at: null
    }
  ]
};

export const secondaryListingsFixture: SecondaryMarketBuyerListing[] = [
  {
    id: "SM-3310",
    loan_id: "GA-2287",
    loan_title: "Loan A - Manufacturing - CH",
    product_type: "direct",
    originator_name: "",
    status: "active",
    current_principal_minor: amount(5210),
    currency: "CHF",
    price_bps: 9800,
    transfer_price_minor: amount(5105.8),
    discount_premium_bps: -200,
    accrued_interest_minor: amount(41.2),
    accrued_interest_from_date: "2026-05-20",
    accrued_interest_to_date: "2026-06-05",
    taker_fee_bps: 75,
    minimum_taker_fee_minor: 0,
    taker_fee_minor: amount(38.3),
    buyer_total_cost_minor: amount(5185.3),
    loan_status_at_listing: "performing",
    days_past_due: 0,
    last_payment_date: "2026-05-20",
    risk_acknowledgement_required: false,
    public_disclosure_note: "",
    listed_at: "2026-06-01T09:00:00+02:00",
    interest_rate_bps: 940,
    underlying_interest_rate_bps: 940,
    yield_bps: 940,
    projected_yield_bps: 959,
    collateral_type: "equipment",
    remaining_term_months: 24
  },
  {
    id: "SM-3298",
    loan_id: "GA-2256",
    loan_title: "Loan C - Real estate - DE",
    product_type: "direct",
    originator_name: "",
    status: "active",
    current_principal_minor: amount(12000),
    currency: "EUR",
    price_bps: 9150,
    transfer_price_minor: amount(10980),
    discount_premium_bps: -850,
    accrued_interest_minor: 0,
    accrued_interest_from_date: null,
    accrued_interest_to_date: "2026-06-05",
    taker_fee_bps: 75,
    minimum_taker_fee_minor: 0,
    taker_fee_minor: amount(82.35),
    buyer_total_cost_minor: amount(11062.35),
    loan_status_at_listing: "late",
    days_past_due: 21,
    last_payment_date: "2026-04-15",
    risk_acknowledgement_required: true,
    public_disclosure_note: "Payment overdue; buyer must acknowledge non-standard listing risk.",
    listed_at: "2026-06-02T09:00:00+02:00",
    interest_rate_bps: 810,
    underlying_interest_rate_bps: 810,
    yield_bps: 810,
    projected_yield_bps: 902,
    collateral_type: "real_estate",
    remaining_term_months: 14
  }
];

export const secondaryListingDetailsFixture: SecondaryMarketBuyerListingDetail[] =
  secondaryListingsFixture.map((listing, index) => {
    const holding = portfolioFixture.holdings[index] ?? portfolioFixture.holdings[0];
    return {
      ...listing,
      originator_id: null,
      borrower_name: holding.loan.borrower_name,
      borrower_country: holding.loan.borrower_country,
      purpose: holding.loan.purpose,
      collateral_type: holding.loan.collateral_type,
      risk_rating: holding.loan.risk_rating,
      interest_rate_bps: holding.loan.interest_rate_bps,
      term_months: holding.loan.term_months,
      repayment_type: holding.loan.repayment_type,
      ltv_bps: holding.loan.ltv_bps,
      loan_start_date: holding.loan.loan_start_date,
      first_payment_date: holding.loan.first_payment_date,
      maturity_date: holding.loan.maturity_date ?? null,
      schedule_version: holding.loan.schedule_version,
      loan_schedule: holding.loan.schedule,
      investment_schedule: holding.investment_schedule,
      latest_public_note: holding.latest_public_note
        ? {
            id: holding.latest_public_note.id,
            title: holding.latest_public_note.title,
            occurred_at: holding.latest_public_note.occurred_at
          }
        : null
    };
  });

export const secondaryActivityFixture: SecondaryMarketActivityPortal = {
  listings: [
    {
      id: "SM-3201",
      holding_id: "H-2042",
      loan_id: "GA-2042",
      loan_title: "Wallis Agrar AG",
      status: "active",
      publication_type: "automatic",
      current_principal_minor: amount(3640),
      transfer_price_minor: amount(3603.6),
      discount_premium_bps: -100,
      accrued_interest_minor: 0,
      maker_fee_minor: amount(9.01),
      seller_net_proceeds_minor: amount(3594.59),
      currency: "CHF",
      loan_status_at_listing: "performing",
      risk_acknowledgement_required: false,
      public_disclosure_note: "",
      listed_at: "2026-05-28T10:00:00+02:00",
      created_at: "2026-05-28T10:00:00+02:00"
    }
  ],
  purchases_as_buyer: [
    {
      id: "P-9275",
      listing_id: "SM-3188",
      loan_id: "GA-2188",
      loan_title: "Zurich mixed-use refinancing",
      buyer_holding_id: "H-2188",
      current_principal_minor: amount(2500),
      transfer_price_minor: amount(2475),
      discount_premium_bps: -100,
      accrued_interest_minor: amount(18.5),
      taker_fee_minor: amount(6.19),
      buyer_total_cost_minor: amount(2499.69),
      currency: "CHF",
      loan_status_at_purchase: "active",
      risk_acknowledgement_accepted: true,
      purchased_at: "2026-05-12T09:45:00+02:00"
    }
  ],
  sales_as_seller: [
    {
      id: "S-9230",
      listing_id: "SM-3140",
      loan_id: "GA-2199",
      loan_title: "Holding transfer",
      seller_holding_id: "H-2199",
      current_principal_minor: amount(4920),
      transfer_price_minor: amount(4920),
      discount_premium_bps: 0,
      accrued_interest_minor: 0,
      maker_fee_minor: amount(12.3),
      seller_net_proceeds_minor: amount(4907.7),
      currency: "CHF",
      loan_status_at_purchase: "performing",
      purchased_at: "2026-04-30T15:18:00+02:00"
    }
  ],
  entries: [
    {
      id: "listing-event:fixture-edit",
      action: "list",
      event_type: "edited",
      listing_id: "SM-3201",
      holding_id: "H-2042",
      loan_id: "GA-2042",
      loan_title: "Wallis Agrar AG",
      currency: "CHF",
      principal_minor: amount(3640),
      cash_amount_minor: amount(3603.6),
      price_bps: 9900,
      status: "active",
      occurred_at: "2026-05-28T10:20:00+02:00"
    },
    {
      id: "listing-event:fixture-create",
      action: "list",
      event_type: "created",
      listing_id: "SM-3201",
      holding_id: "H-2042",
      loan_id: "GA-2042",
      loan_title: "Wallis Agrar AG",
      currency: "CHF",
      principal_minor: amount(3640),
      cash_amount_minor: amount(3640),
      price_bps: 10000,
      status: "active",
      occurred_at: "2026-05-28T10:00:00+02:00"
    },
    {
      id: "buy:P-9275",
      action: "buy",
      event_type: "buy",
      listing_id: "SM-3188",
      holding_id: "H-2188",
      loan_id: "GA-2188",
      loan_title: "Zurich mixed-use refinancing",
      currency: "CHF",
      principal_minor: amount(2500),
      cash_amount_minor: amount(2499.69),
      price_bps: 9900,
      status: "completed",
      occurred_at: "2026-05-12T09:45:00+02:00"
    },
    {
      id: "sale:S-9230",
      action: "sale",
      event_type: "sale",
      listing_id: "SM-3140",
      holding_id: "H-2199",
      loan_id: "GA-2199",
      loan_title: "Holding transfer",
      currency: "CHF",
      principal_minor: amount(4920),
      cash_amount_minor: amount(4907.7),
      price_bps: 10000,
      status: "completed",
      occurred_at: "2026-04-30T15:18:00+02:00"
    },
    {
      id: "listing-event:fixture-cancel",
      action: "cancel_listing",
      event_type: "cancelled",
      listing_id: "SM-3010",
      holding_id: "H-2010",
      loan_id: "GA-2010",
      loan_title: "Lausanne residential bridge",
      currency: "CHF",
      principal_minor: amount(1800),
      cash_amount_minor: amount(1800),
      price_bps: 10000,
      status: "cancelled",
      occurred_at: "2026-04-18T14:10:00+02:00"
    }
  ]
};

export const fxFixture: FxHistoryPortal = {
  quotes: [],
  exchanges: [
    {
      id: "FX-7741",
      quote_id: "FQ-7741",
      source_currency: "CHF",
      target_currency: "EUR",
      source_amount_minor: amount(4500),
      rate: "1.041800",
      platform_fee_bps: 150,
      gross_target_amount_minor: amount(4688.1),
      fee_minor: amount(70.32),
      target_amount_minor: amount(4617.78),
      effective_net_rate: "1.026173333333",
      status: "settled",
      executed_at: "2026-05-30T11:03:00+02:00"
    }
  ]
};
