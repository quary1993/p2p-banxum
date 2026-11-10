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
  MarketplaceCreditCheck,
  MarketplaceDebtFacility,
  MarketplaceFinancialYear,
  MarketplaceSecurity,
  MarketplaceOriginalLoanScheduleRow,
  PortfolioExposure,
  PortfolioSummary,
  PrimaryOrdersPortal,
  PublicLoanRiskNote,
  PublicProject,
  SecondaryMarketActivityPortal,
  SecondaryMarketBuyerListing,
  SecondaryMarketBuyerListingDetail,
  SavedOpportunityList,
  SmartInvestResponse
} from "../api/generated/banxumApi";
import { AUTO_RETURN_AFTER_DAYS } from "./balanceAgeing";
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

const fixtureIsoDateFromToday = (daysAhead: number) => {
  const date = new Date();
  date.setDate(date.getDate() + daysAhead);
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
      size: "312 KB",
      periodStart: "2026-01-01",
      periodEnd: "2026-06-05"
    },
    {
      id: "D-9500",
      title: "Annual Lender Tax Information Statement - 2025",
      type: "Tax",
      version: "-",
      date: "2026-02-15",
      context: "Annual",
      size: "276 KB",
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31"
    },
    {
      id: "D-9401",
      title: "Investor account statement - 2025",
      type: "Statement",
      version: "-",
      date: "2026-01-02",
      context: "Annual",
      size: "298 KB",
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31"
    },
    {
      id: "D-9140",
      title: "Loan Helvetia Logistik AG CHF 6,500.00 agreement",
      type: "Investment agreement",
      version: "v3",
      date: "2026-06-02",
      context: "Order O-58102",
      size: "198 KB",
      category: "primary_market_investment"
    },
    {
      id: "D-9150",
      title: "Loan Rhône Vignobles SA EUR 2,480.00 transfer agreement",
      type: "Transfer agreement",
      version: "v2",
      date: "2026-02-18",
      context: "Resale purchase SM-3290",
      size: "164 KB",
      category: "secondary_market_purchase"
    }
  ],
  notifications: [
    {
      id: "N1",
      tone: "warn",
      label: "Balance reminder",
      title: "Balance ageing - day 57",
      body: "CHF 980.00 from a recovery distribution must be withdrawn within 3 days.",
      time: "2 days ago",
      unread: true,
      target: "balances"
    },
    {
      id: "N2",
      tone: "bad",
      label: "Loan status",
      title: "Loan in default",
      body: "GA-2201 is now 64 days past due.",
      time: "3 days ago",
      unread: true,
      target: "holding",
      targetId: "H-2201"
    },
    {
      id: "N3",
      tone: "ok",
      label: "Repayment",
      title: "Loan repayment credited",
      body: "CHF 412.35 from Helvetia Logistik AG was credited to your Banxum balance.",
      time: "2 weeks ago",
      unread: false,
      target: "portfolio",
      createdAt: "2026-05-21T08:05:00Z"
    },
    {
      id: "N4",
      tone: "ok",
      label: "Deposit",
      title: "Deposit credited: CHF 12,000.00",
      body: "Your bank transfer was booked to your Banxum balance.",
      time: "4 weeks ago",
      unread: false,
      target: "balances",
      createdAt: "2026-05-09T09:30:00Z"
    },
    {
      id: "N5",
      tone: "warn",
      label: "Withdrawal",
      title: "Withdrawal requested: CHF 1,500.00",
      body: "Delivery status only. Message contents are not shown in the portal for this notification type.",
      time: "8 weeks ago",
      unread: false,
      status: "failed",
      createdAt: "2026-04-08T07:12:00Z"
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

export const publicLoanNotesFixture: PublicLoanRiskNote[] = [
  {
    id: "note-late",
    loan_id: "GA-2256",
    visibility: "public",
    note_type: "payment_update",
    title: "Payment overdue; borrower contacted",
    body: "The interest payment due on 15 May 2026 has not been received. Garanta reminded the borrower and is following up.",
    occurred_at: "2026-05-20T09:00:00+02:00"
  },
  {
    id: "note-default-follow-up",
    loan_id: "GA-2201",
    visibility: "public",
    note_type: "default_update",
    title: "Recovery process update",
    body: "Garanta has instructed external recovery counsel. We will publish another note when there is a material update.",
    occurred_at: "2026-05-22T09:00:00+02:00"
  },
  {
    id: "note-default",
    loan_id: "GA-2201",
    visibility: "public",
    note_type: "default_update",
    title: "Formal demand issued",
    body: "Garanta has issued a formal payment demand to the borrower. No recovery amount is confirmed at this time.",
    occurred_at: "2026-05-18T09:00:00+02:00"
  }
];

// The return dates are derived below from the holding deadline (day 60), like the API does.
const sourceBalanceLotsFixture: Omit<BalanceLot, "last_day" | "return_date" | "days_until_last_day">[] = [
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

// Money not invested goes back to the bank after day 58, two days before the 60-day limit.
const FIXTURE_DAYS_BEFORE_LIMIT = 60 - AUTO_RETURN_AFTER_DAYS;

export const balanceLotsFixture: BalanceLot[] = sourceBalanceLotsFixture.map((lot) => {
  const daysLeft = lot.bucket === "overdue" ? -1 : lot.days_until_withdrawal_deadline;
  const deadline = `${fixtureIsoDateFromToday(daysLeft)}T00:00:00Z`;
  const daysToLastDay = daysLeft - FIXTURE_DAYS_BEFORE_LIMIT;
  return {
    ...lot,
    received_at: `${fixtureIsoDateFromToday(daysLeft - 60)}T00:00:00Z`,
    investment_deadline_at: deadline,
    withdrawal_deadline_at: deadline,
    days_until_investment_deadline: daysLeft,
    days_until_withdrawal_deadline: daysLeft,
    last_day: fixtureIsoDateFromToday(daysToLastDay),
    return_date: fixtureIsoDateFromToday(daysToLastDay + 1),
    days_until_last_day: daysToLastDay,
    bucket: daysToLastDay > 0 ? "investable" : daysToLastDay === 0 ? "withdraw_only" : "overdue",
    requires_withdrawal: daysToLastDay <= 0
  };
});

function fixtureBalanceSummary(currency: string): BalanceSummary {
  const lots = balanceLotsFixture.filter((lot) => lot.currency === currency);
  const sum = (bucket?: string) => lots.reduce((total, lot) =>
    total + (!bucket || lot.bucket === bucket ? lot.available_amount_minor : 0), 0
  );
  const next = lots.map((lot) => lot.withdrawal_deadline_at).sort()[0] ?? null;
  const nextReturn = lots.filter((lot) => lot.bucket !== "overdue").map((lot) => lot.return_date).sort()[0] ?? null;
  return {
    investor_user_id: investorId, currency,
    total_available_minor: sum(), investable_minor: sum("investable"),
    withdraw_only_minor: sum("withdraw_only"), overdue_minor: sum("overdue"), frozen_minor: 0,
    penalty_mode_minor: 0,
    penalty_charged_minor: lots.reduce((total, lot) => total + lot.penalized_amount_minor, 0),
    lot_count: lots.length, active_lot_count: lots.length,
    next_investment_deadline_at: next, next_withdrawal_deadline_at: next, next_return_date: nextReturn
  };
}

const chfSummary = fixtureBalanceSummary("CHF");
const eurSummary = fixtureBalanceSummary("EUR");

export const balancesFixture: InvestorBalancePortal = {
  as_of: new Date().toISOString(),
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
      verification_status: "verified",
      is_default_return: true,
      verified_at: "2026-05-18T12:00:00+02:00",
      created_at: "2026-05-18T11:50:00+02:00"
    }
  ],
  pending_withdrawals: [],
  auto_return_after_days: AUTO_RETURN_AFTER_DAYS
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
  | "borrower_country"
  | "borrower_city"
  | "repayment_type"
  | "collateral_description"
  | "published_at"
>;

// U33-DEC-23 borrower cities; Adriatic Marine has none, to show a missing value.
const directBorrowerCities: Record<string, string> = {
  "GA-2401": "Basel",
  "GA-2399": "Sion",
  "GA-2402": "Hamburg",
  "GA-2390": "Lausanne"
};

const directMarketplaceLoansFixture: DirectMarketplaceFixtureInput[] = [
  {
    loan_id: "GA-2401",
    title: "Helvetia Logistik AG",
    purpose: "Warehouse refinancing",
    collateral_type: "Commercial real estate",
    interest_rate_bps: 740,
    term_months: 24,
    funding_deadline: "2026-06-19",
    status: "published",
    currency: "CHF",
    principal_minor: amount(1450000),
    committed_principal_minor: amount(1087500),
    remaining_capacity_minor: amount(362500),
    minimum_investment_minor: amount(1000),
    ltv_bps: 5800,
    is_refinancing: true,
    minimum_subscription_bps: 5000
  },
  {
    loan_id: "GA-2399",
    title: "Rhône Vignobles SA",
    purpose: "Equipment renewal",
    collateral_type: "Agricultural land",
    interest_rate_bps: 680,
    term_months: 18,
    funding_deadline: "2026-06-11",
    status: "published",
    currency: "CHF",
    principal_minor: amount(620000),
    committed_principal_minor: amount(558000),
    remaining_capacity_minor: amount(62000),
    minimum_investment_minor: amount(1000),
    ltv_bps: 4900,
    is_refinancing: false,
    minimum_subscription_bps: 5000,
    // Swiss borrower: at most 20 investors (MKT-DEC-028, today's rule until U33-DEC-08).
    max_investors: 20,
    places_left: 4,
    is_existing_investor: false
  },
  {
    loan_id: "GA-2402",
    title: "Nordwind Energie GmbH",
    purpose: "Solar bridge financing",
    collateral_type: "Solar plant and equipment",
    interest_rate_bps: 810,
    term_months: 36,
    funding_deadline: "2026-06-27",
    status: "published",
    currency: "EUR",
    principal_minor: amount(1980000),
    committed_principal_minor: amount(415800),
    remaining_capacity_minor: amount(1564200),
    minimum_investment_minor: amount(1000),
    ltv_bps: 5800,
    is_refinancing: false,
    minimum_subscription_bps: 5000
  },
  {
    loan_id: "GA-2395",
    title: "Adriatic Marine d.o.o.",
    purpose: "Charter receivables working capital",
    collateral_type: "Vessel and receivables",
    interest_rate_bps: 930,
    term_months: 24,
    funding_deadline: "2026-06-02",
    status: "funded",
    currency: "EUR",
    principal_minor: amount(540000),
    committed_principal_minor: amount(540000),
    remaining_capacity_minor: 0,
    minimum_investment_minor: amount(1000),
    ltv_bps: 6200,
    is_refinancing: false,
    minimum_subscription_bps: 5000
  },
  {
    loan_id: "GA-2390",
    title: "Léman BioTech SA",
    purpose: "Bridge to Series B",
    collateral_type: "Unsecured exception",
    interest_rate_bps: 1020,
    term_months: 12,
    funding_deadline: "2026-06-14",
    status: "published",
    currency: "CHF",
    principal_minor: amount(300000),
    committed_principal_minor: amount(270000),
    remaining_capacity_minor: amount(30000),
    minimum_investment_minor: amount(1000),
    ltv_bps: null,
    is_refinancing: false,
    minimum_subscription_bps: 5000
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
    borrower_display_name: loan.title,
    // The same values as the loan details below.
    borrower_country: loan.currency === "CHF" ? "CH" : "DE",
    borrower_city: directBorrowerCities[loan.loan_id] ?? "",
    repayment_type: loan.term_months >= 24 ? "bullet" : "equal_installments",
    collateral_description: loan.collateral_type,
    security_types: loan.loan_id === "GA-2401" ? [loan.collateral_type, "personal_guarantee"] : [loan.collateral_type],
    published_at: loan.funding_deadline ? `${fixtureIsoDate(-1, 1)}T08:00:00Z` : null
  })
);

const originatorMarketplaceLoanFixture: MarketplaceLoanPreview = {
  loan_id: "LO-2601",
  product_type: "originator_claim",
  investment_flow: "primary_order",
  title: "Swiss SME equipment claim",
  purpose: "Equipment financing",
  collateral_type: "Machinery and equipment",
  // Investor display yield is the underlying coupon multiplied by the declared
  // investor interest participation (10.80% x 70% = 7.56%).
  interest_rate_bps: 756,
  yield_bps: 756,
  underlying_interest_rate_bps: 1080,
  term_months: 9,
  remaining_term_days: 271,
  funding_deadline: fixtureIsoDateFromToday(30),
  maturity_date: fixtureIsoDate(9, 28),
  status: "published",
  loan_status: "published",
  opportunity_status: "open",
  currency: "CHF",
  principal_minor: amount(160_000),
  committed_principal_minor: amount(45_000),
  remaining_capacity_minor: amount(91_000),
  fillable_amount_minor: amount(91_000),
  minimum_investment_minor: amount(500),
  ltv_bps: 5450,
  is_refinancing: false,
  originator_id: "originator-alpine-credit",
  originator_name: "Alpine Credit Partners AG",
  borrower_display_name: "Established Swiss precision manufacturer",
  borrower_country: "CH",
  borrower_city: "Winterthur",
  repayment_type: "amortizing_principal_interest",
  collateral_description: "First-ranking security over financed machinery and equipment.",
  published_at: `${fixtureIsoDate(0, 1)}T08:00:00Z`,
  distribution_model: "par_component_v2",
  entitlement_start_date: fixtureIsoDate(1, 28),
  investor_interest_participation_bps: 7000,
  investor_penalty_participation_bps: 5000,
  skin_in_the_game_bps: 1500,
  minimum_subscription_bps: 0
};

export const marketplaceLoansFixture: MarketplaceLoanPreview[] = [
  ...directMarketplaceLoanPreviews,
  originatorMarketplaceLoanFixture
];

export const smartInvestFixture: SmartInvestResponse = {
  rule: {
    id: "smart-invest-rule-preview",
    is_active: true,
    state: "active",
    revision: 1,
    minimum_yield_bps: 850,
    maximum_term_months: 36,
    maximum_ltv_bps: null,
    preferred_amount_minor: null,
    originators: [],
    collateral: ["any_secured"],
    currencies: [],
    countries: [],
    activated_at: "2026-06-05T10:00:00+02:00",
    deactivated_at: null,
    created_at: "2026-06-05T10:00:00+02:00",
    updated_at: "2026-06-05T10:00:00+02:00"
  },
  open_opportunity_count: marketplaceLoansFixture.length,
  // U33-DEC-17: the preview's Coming soon loan (7.6%) is below this rule's 8.5%.
  coming_soon_matches: [],
  matches: marketplaceLoansFixture
    .filter((loan) => loan.yield_bps >= 850 && loan.term_months <= 36 && !/unsecured/i.test(loan.collateral_type))
    .map((loan) => ({
      loan_id: loan.loan_id,
      product_type: loan.product_type,
      investment_flow: loan.investment_flow,
      title: loan.title,
      purpose: loan.purpose,
      collateral_type: loan.collateral_type,
      interest_rate_bps: loan.interest_rate_bps,
      yield_bps: loan.yield_bps,
      underlying_interest_rate_bps: loan.underlying_interest_rate_bps,
      term_months: loan.term_months,
      remaining_term_days: loan.remaining_term_days,
      funding_deadline: loan.funding_deadline,
      maturity_date: loan.maturity_date,
      status: loan.status,
      loan_status: loan.loan_status,
      opportunity_status: loan.opportunity_status,
      currency: loan.currency,
      principal_minor: loan.principal_minor,
      committed_principal_minor: loan.committed_principal_minor,
      remaining_capacity_minor: loan.remaining_capacity_minor,
      fillable_amount_minor: loan.fillable_amount_minor,
      minimum_investment_minor: loan.minimum_investment_minor,
      ltv_bps: loan.ltv_bps,
      is_refinancing: loan.is_refinancing,
      originator_id: loan.originator_id,
      originator_name: loan.originator_name,
      borrower_display_name: loan.borrower_display_name,
      borrower_country: loan.borrower_country,
      borrower_city: loan.borrower_city,
      skin_in_the_game_bps: loan.skin_in_the_game_bps,
      minimum_subscription_bps: loan.minimum_subscription_bps
    })),
  notification_channels: { in_app: true, email: true },
  match_count: 0
};

smartInvestFixture.match_count = smartInvestFixture.matches.length;

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

const fixtureAnnuityRows = (principalMinor: number, rateBps: number, months: number, firstDueIso: string) => {
  const monthly = rateBps / 120_000;
  const payment = monthly > 0 ? (principalMinor * monthly) / (1 - Math.pow(1 + monthly, -months)) : principalMinor / months;
  const first = new Date(`${firstDueIso}T00:00:00`);
  let outstanding = principalMinor;
  return Array.from({ length: months }, (_, index) => {
    const interest = Math.round(outstanding * monthly);
    const principal = index === months - 1 ? outstanding : Math.round(payment - interest);
    outstanding -= principal;
    const due = new Date(first.getFullYear(), first.getMonth() + index, first.getDate());
    return {
      installment_number: index + 1,
      due_date: `${due.getFullYear()}-${String(due.getMonth() + 1).padStart(2, "0")}-${String(due.getDate()).padStart(2, "0")}`,
      principal_minor: principal,
      interest_minor: interest,
      total_minor: principal + interest,
      outstanding_after_minor: outstanding
    };
  });
};

export const fixtureStoryImageId = "6f1d2c3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f";

const helvetiaStoryFixture = {
  version: 1,
  blocks: [
    { type: "heading", level: 2, runs: [{ text: "Moving Swiss goods since 1994" }] },
    {
      type: "paragraph",
      runs: [
        { text: "Helvetia Logistik AG runs " },
        { text: "42 trucks and two cross-dock warehouses", bold: true },
        { text: " between Zurich, Basel and the Ticino border. Founded by the Brunner family, the company is now in its second generation and employs 118 people." }
      ]
    },
    { type: "image", image_id: fixtureStoryImageId, alt: "Helvetia Logistik cross-dock warehouse in Duebendorf", caption: "The Duebendorf cross-dock, refinanced with this loan." },
    { type: "heading", level: 3, runs: [{ text: "Why they borrow" }] },
    {
      type: "paragraph",
      runs: [
        { text: "The loan refinances the Duebendorf warehouse at a lower rate and adds working capital for six new electric trucks. Management expects the fleet change to cut fuel cost by roughly a fifth; see the " },
        { text: "company site", href: "https://example.test/helvetia" },
        { text: " for the sustainability report." }
      ]
    },
    { type: "bullet_list", items: [[{ text: "Long-term contracts with two national retailers" }], [{ text: "Owner-occupied real estate as collateral" }], [{ text: "Audited accounts since 2012" }]] },
    { type: "quote", runs: [{ text: "We only borrow to buy assets that pay for themselves." }] },
    { type: "divider" },
    { type: "paragraph", runs: [{ text: "This story was written by BANXUM based on borrower-provided material and the credit file." , italic: true }] }
  ]
};

const originatorStoryFixture = {
  version: 1,
  blocks: [
    { type: "heading", level: 2, runs: [{ text: "Alpine Credit Partners AG" }] },
    {
      type: "paragraph",
      runs: [
        { text: "A FINMA-registered SME lender based in Chur, lending to Swiss manufacturers since 2009. Alpine keeps " },
        { text: "skin in every loan it lists", bold: true },
        { text: " and services the borrower relationship end to end." }
      ]
    },
    { type: "numbered_list", items: [[{ text: "CHF 180m originated to date" }], [{ text: "Historic loss rate below 1%" }], [{ text: "Quarterly audited servicing reports" }]] }
  ]
};

const helvetiaSecuritiesFixture: MarketplaceSecurity[] = [
  {
    id: "security-2401-property",
    position: 0,
    security_type: "Commercial real estate",
    is_guarantee: false,
    description: "Commercial real estate",
    holder_name: "Helvetia Logistik AG",
    rank: 2,
    status: "in_place",
    value_minor: amount(2500000),
    valuation_date: "2026-03-12",
    valuation_source: "Independent appraisal",
    appraiser: "Wüest Partner AG",
    prior_ranking_debt_minor: amount(300000),
    insurance: "Building insurance at full rebuilding value.",
    undertaking_scope: "",
    undertaking_limit_minor: null,
    documents: []
  },
  {
    id: "security-2401-guarantee",
    position: 1,
    security_type: "personal_guarantee",
    is_guarantee: true,
    description: "",
    holder_name: "Main shareholder",
    rank: null,
    status: "in_place",
    value_minor: null,
    valuation_date: null,
    valuation_source: "",
    appraiser: "",
    prior_ranking_debt_minor: null,
    insurance: "",
    undertaking_scope: "Joint and several guarantee for principal and interest.",
    undertaking_limit_minor: amount(400000),
    documents: []
  }
];

// U33-DEC-20: a structured credit file (the design's packaging example, in CHF thousands).
const thousandsMinor = (value: number) => amount(value * 1000);
const helvetiaFinancialYearsFixture: MarketplaceFinancialYear[] = [
  [2023, 10400, 5200, 2500, 1420, 500, 780, 140, 640, 160, 480, 720, 1450, 1230, 100, 3500, 3500, 200, 7200, 750, 2170, 2920, 1190, 340, 2750],
  [2024, 11200, 5550, 2650, 1520, 560, 920, 150, 770, 180, 590, 850, 1560, 1340, 100, 3850, 3550, 200, 7600, 800, 2270, 3070, 1150, 340, 3040],
  [2025, 11800, 5800, 2770, 1580, 600, 1050, 160, 890, 210, 680, 980, 1650, 1420, 150, 4200, 3600, 200, 8000, 830, 2200, 3030, 1270, 340, 3360]
].map(([year, ...values]) => {
  const [revenue, materials, staff, other, depreciation, operating, interest, beforeTax, tax, net, cash, receivables, inventories, otherCurrent, current, ppe, otherNonCurrent, assets, currentDebt, nonCurrentDebt, debt, payables, otherLiabilities, equity] = values.map(thousandsMinor);
  return {
    id: `fy-2401-${year}`,
    year,
    period_end: `${year}-12-31`,
    currency: "CHF",
    source_document: year === 2025 ? { id: "GA-2401-financial-summary", display_name: "Borrower financial summary" } : null,
    revenue_minor: revenue,
    materials_costs_minor: materials,
    staff_costs_minor: staff,
    other_operating_costs_minor: other,
    depreciation_minor: depreciation,
    operating_profit_minor: operating,
    interest_expense_minor: interest,
    profit_before_tax_minor: beforeTax,
    income_tax_minor: tax,
    net_profit_minor: net,
    cash_minor: cash,
    trade_receivables_minor: receivables,
    inventories_minor: inventories,
    other_current_assets_minor: otherCurrent,
    current_assets_minor: current,
    property_plant_equipment_minor: ppe,
    other_non_current_assets_minor: otherNonCurrent,
    total_assets_minor: assets,
    current_financial_debt_minor: currentDebt,
    non_current_financial_debt_minor: nonCurrentDebt,
    financial_debt_minor: debt,
    trade_payables_minor: payables,
    other_operating_liabilities_minor: otherLiabilities,
    equity_minor: equity
  };
});
const helvetiaDebtFixture: MarketplaceDebtFacility[] = [
  ["Property loan", 1700, 150, "Mortgage on separate premises"],
  ["Production equipment financing", 950, 130, "Security over existing equipment"],
  ["Working-capital facility", 380, 380, "Security over existing receivables"]
].map(([type, balance, current, security], index) => ({
  id: `debt-2401-${index}`,
  position: index,
  facility_type: String(type),
  currency: "CHF",
  balance_minor: thousandsMinor(Number(balance)),
  current_portion_minor: thousandsMinor(Number(current)),
  non_current_portion_minor: thousandsMinor(Number(balance) - Number(current)),
  security_description: String(security),
  as_at: "2025-12-31",
  source_document: null
}));
const helvetiaChecksFixture: MarketplaceCreditCheck[] = [
  { id: "check-2401-company", position: 0, name: "Company and owners", result: "Register details, ownership and authorised signatories reconciled.", source: "Commercial register and shareholder register", checked_on: "2026-03-02", status: "reviewed" },
  { id: "check-2401-property", position: 1, name: "Property and charges", result: "Land register extract and existing mortgage reviewed.", source: "Land register extract", checked_on: "2026-03-09", status: "received" }
];

const directLoanDetailsFixture: MarketplaceLoanDetail[] = directMarketplaceLoanPreviews.map((loan) => ({
  ...loan,
  story: loan.loan_id === "GA-2401" ? helvetiaStoryFixture : { version: 1, blocks: [] },
  loan_schedule: fixtureAnnuityRows(
    loan.principal_minor,
    loan.interest_rate_bps,
    loan.term_months,
    loan.funding_deadline ? `${loan.funding_deadline.slice(0, 8)}28` : "2026-07-28"
  ),
  default_penalty_interest_bps: loan.loan_id === "GA-2390" ? 0 : 1200,
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
    ...(directBorrowerCities[loan.loan_id] ? { city: directBorrowerCities[loan.loan_id] } : {}),
    ...(loan.loan_id === "GA-2401" ? { employees: 118, employees_year: 2025 } : {}),
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
        description: "Clean-scanned financial summary available to lenders.",
        ...(loan.loan_id === "GA-2401" ? { category: "Financial statements", period_label: "FY 2025", issuer: "Helvetia Logistik AG", version: "1", document_status: "Final" } : {})
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
  // U33-DEC-21: several securities, each on its own (the property and the owner's guarantee).
  ...(loan.loan_id === "GA-2401"
    ? {
        securities: helvetiaSecuritiesFixture,
        financial_years: helvetiaFinancialYearsFixture,
        debt_facilities: helvetiaDebtFixture,
        credit_checks: helvetiaChecksFixture,
        monitoring: { frequency: "Quarterly, with the annual financial statements.", focus: "Warehouse occupancy, fleet costs and cash generation." },
        // The design's standard plan, as a proposal (U33-DEC-20).
        reporting_plan: {
          status: "proposed",
          milestones: [
            { when: "At closing", title: "Signed loan & security records", body: "Executed agreements and confirmation of the security arrangements." },
            { when: "After each year-end", title: "Annual financial statements", body: "Balance sheet and profit & loss for the completed financial year." },
            { when: "When something changes", title: "Project & security updates", body: "Relevant changes to the project, repayments or security documents." }
          ]
        }
      }
    : {}),
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
    due_date: fixtureIsoDate(1, 28),
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
    accrual_start_date: fixtureIsoDate(1, 28),
    due_date: fixtureIsoDate(2, 28),
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
    accrual_start_date: fixtureIsoDate(2, 28),
    due_date: fixtureIsoDate(3, 28),
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
    accrual_start_date: fixtureIsoDate(3, 28),
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
  story: originatorStoryFixture,
  borrower_disclosure: {
    legal_name: "Established Swiss precision manufacturer",
    year_founded: 2007,
    business_classification: "Precision component manufacturing",
    country: "CH",
    city: "Winterthur",
    employees: 85,
    employees_year: 2025,
    industry_activity: "Industrial manufacturing",
    financials_currency: "CHF",
    assets_minor: amount(4_850_000),
    liabilities_minor: amount(2_120_000),
    revenue_last_year_minor: amount(3_760_000),
    profit_last_year_minor: amount(315_000)
  },
  investor_summary:
    "Existing final-borrower loan offered by a Loan Originator during a finite funding round. Investor money is reserved at par and holdings activate automatically at funding close. The boundary installment belongs entirely to the LO.",
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
  first_payment_date: fixtureIsoDate(2, 28),
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

// Investing screens (slice S2): loans that are no longer open (past opportunities, their pages and
// credit files) and a legacy originator claim bought through an executable quote. They are reachable
// from Past opportunities or by address only, so the open marketplace list keeps its preview loans.
type PastLoanInput = {
  loan_id: string;
  title: string;
  borrower: string;
  country: string;
  status: string;
  currency: string;
  principal: number;
  interest_rate_bps: number;
  term_months: number;
  collateral_type: string;
  collateral_value: number;
  purpose: string;
  monthsAgo: number;
};

const pastLoanInputs: PastLoanInput[] = [
  { loan_id: "GA-2310", title: "Engadin Alpine refinancing", borrower: "Engadin Hospitality AG", country: "CH", status: "active", currency: "CHF", principal: 880_000, interest_rate_bps: 690, term_months: 36, collateral_type: "real_estate", collateral_value: 1_600_000, purpose: "Refinancing of the hotel mortgage and renovation of the spa wing.", monthsAgo: 10 },
  { loan_id: "GA-2256", title: "Bodensee Immobilien GmbH", borrower: "Bodensee Immobilien GmbH", country: "DE", status: "late", currency: "EUR", principal: 450_000, interest_rate_bps: 780, term_months: 24, collateral_type: "real_estate", collateral_value: 700_000, purpose: "Completion of a residential building with six flats.", monthsAgo: 14 },
  { loan_id: "GA-2201", title: "Savoie Logistique SAS", borrower: "Savoie Logistique SAS", country: "FR", status: "defaulted", currency: "EUR", principal: 320_000, interest_rate_bps: 840, term_months: 24, collateral_type: "equipment", collateral_value: 410_000, purpose: "Purchase of refrigerated trucks for regional deliveries.", monthsAgo: 18 },
  { loan_id: "GA-2104", title: "Zürichsee Gastro AG", borrower: "Zürichsee Gastro AG", country: "CH", status: "repaid", currency: "CHF", principal: 240_000, interest_rate_bps: 620, term_months: 12, collateral_type: "corporate_guarantee", collateral_value: 0, purpose: "Working capital for the summer season of two lakeside restaurants.", monthsAgo: 20 }
];

const pastLoanDetailsFixture: MarketplaceLoanDetail[] = pastLoanInputs.map((input) => {
  const principal = amount(input.principal);
  const fundedOn = fixtureIsoDate(-input.monthsAgo, 15);
  return {
    loan_id: input.loan_id,
    product_type: "direct",
    investment_flow: "primary_order",
    title: input.title,
    purpose: "working_capital",
    collateral_type: input.collateral_type,
    interest_rate_bps: input.interest_rate_bps,
    yield_bps: input.interest_rate_bps,
    underlying_interest_rate_bps: input.interest_rate_bps,
    term_months: input.term_months,
    remaining_term_days: null,
    funding_deadline: fundedOn,
    maturity_date: fixtureIsoDate(input.term_months - input.monthsAgo, 15),
    status: input.status,
    loan_status: input.status,
    opportunity_status: "closed",
    borrower_country: input.country,
    borrower_city: "",
    published_at: `${fixtureIsoDate(-input.monthsAgo, 1)}T08:00:00Z`,
    currency: input.currency,
    principal_minor: principal,
    committed_principal_minor: principal,
    remaining_capacity_minor: 0,
    fillable_amount_minor: 0,
    minimum_investment_minor: amount(1000),
    ltv_bps: input.collateral_value > 0 ? Math.round((input.principal * 10_000) / input.collateral_value) : null,
    is_refinancing: input.loan_id === "GA-2310",
    originator_id: null,
    originator_name: null,
    borrower_display_name: input.borrower,
    minimum_subscription_bps: 5000,
    default_penalty_interest_bps: 1200,
    borrower_id: `borrower-${input.loan_id}`,
    borrower_disclosure: {
      legal_name: input.borrower,
      country: input.country,
      year_founded: 2009,
      business_classification: input.collateral_type === "equipment" ? "Logistics" : input.collateral_type === "real_estate" ? "Real estate and hospitality" : "Restaurants",
      financials_currency: input.currency
    },
    story: { version: 1, blocks: [] },
    investor_summary: input.purpose,
    purpose_description: input.purpose,
    collateral_value_minor: amount(input.collateral_value),
    collateral_description: input.collateral_type === "corporate_guarantee" ? "Guarantee of the parent company." : input.collateral_type === "equipment" ? "First-ranking pledge on the financed trucks." : "First-ranking mortgage note on the property.",
    ltv_warnings: [],
    original_principal_minor: 0,
    original_interest_rate_bps: null,
    original_term_months: null,
    original_repayment_type: null,
    original_interest_only_months: null,
    original_loan_start_date: null,
    original_loan_schedule: [],
    repayment_type: "equal_installments",
    loan_start_date: fundedOn,
    first_payment_date: fixtureIsoDate(1 - input.monthsAgo, 15),
    schedule_version: 1,
    loan_schedule: fixtureAnnuityRows(principal, input.interest_rate_bps, input.term_months, fixtureIsoDate(1 - input.monthsAgo, 15))
  };
});

/** Legacy Loan Originator claim (immediate assignment through an executable quote): /marketplace/LO-2402. */
const legacyClaimDetailFixture: MarketplaceLoanDetail = {
  ...originatorLoanDetailFixture,
  loan_id: "LO-2402",
  investment_flow: "immediate_claim_assignment",
  distribution_model: "legacy_yield_v1",
  title: "Alpine dental equipment claim",
  interest_rate_bps: 820,
  yield_bps: 820,
  underlying_interest_rate_bps: 900,
  funding_deadline: null,
  remaining_term_days: 300,
  status: "open",
  loan_status: "active",
  opportunity_status: "open",
  principal_minor: amount(95_000),
  committed_principal_minor: amount(43_000),
  remaining_capacity_minor: amount(52_000),
  fillable_amount_minor: amount(52_000),
  minimum_investment_minor: amount(1000),
  entitlement_start_date: null,
  investor_interest_participation_bps: null,
  investor_penalty_participation_bps: null,
  borrower_display_name: "Dental practice in Zürich",
  purpose_description: "Lease of two treatment units and an X-ray device, financed by the loan originator."
};

// U33-DEC-17: a draft shown as Coming soon, with its planned opening date. Nothing is funded yet.
const comingSoonBase = directLoanDetailsFixture.find((loan) => loan.loan_id === "GA-2402") ?? directLoanDetailsFixture[0];
const comingSoonLoanDetailFixture: MarketplaceLoanDetail = {
  ...comingSoonBase,
  loan_id: "GA-2410",
  title: "Engadin Lodge AG",
  purpose: "Hotel renovation",
  collateral_type: "Mortgage note",
  collateral_description: "First-ranking mortgage note on the hotel building.",
  interest_rate_bps: 760,
  yield_bps: 760,
  underlying_interest_rate_bps: 760,
  term_months: 24,
  status: "draft",
  loan_status: "draft",
  opportunity_status: "coming_soon",
  currency: "CHF",
  principal_minor: amount(850000),
  committed_principal_minor: 0,
  remaining_capacity_minor: amount(850000),
  fillable_amount_minor: amount(850000),
  borrower_display_name: "Engadin Lodge AG",
  borrower_country: "CH",
  borrower_city: "St. Moritz",
  repayment_type: "equal_installments",
  ltv_bps: 5200,
  published_at: null,
  funding_deadline: fixtureIsoDateFromToday(36),
  planned_opening_date: fixtureIsoDateFromToday(6),
  opening_alert_requested: false,
  borrower_disclosure: { ...comingSoonBase.borrower_disclosure, legal_name: "Engadin Lodge AG", country: "CH", city: "St. Moritz" }
};

export const comingSoonLoansFixture: MarketplaceLoanPreview[] = [comingSoonLoanDetailFixture];

/** U33-DEC-18: nothing saved at first, as in the design; saving in the preview fills it. */
export const savedOpportunitiesFixture: SavedOpportunityList = { saved: [] };

export const loanDetailsFixture: MarketplaceLoanDetail[] = [
  ...directLoanDetailsFixture,
  originatorLoanDetailFixture,
  ...pastLoanDetailsFixture,
  legacyClaimDetailFixture,
  comingSoonLoanDetailFixture
];

/** Past opportunities (public projects API) for the investor archive, matching the loan details above. */
export const pastProjectsFixture: PublicProject[] = [
  ...pastLoanDetailsFixture.map((loan): PublicProject => ({
    loan_id: loan.loan_id,
    title: loan.title,
    product_type: "direct",
    is_refinancing: loan.is_refinancing,
    public_status: loan.status === "defaulted" ? "default" : loan.status === "active" ? "repaying" : (loan.status as PublicProject["public_status"]),
    currency: loan.currency,
    principal_minor: loan.principal_minor,
    committed_principal_minor: loan.principal_minor,
    remaining_capacity_minor: 0,
    minimum_investment_minor: null,
    investors_count: 40 + loan.term_months,
    max_investors: null,
    places_left: null,
    interest_rate_bps: loan.interest_rate_bps,
    term_months: loan.term_months,
    repayment_type: loan.repayment_type,
    collateral_type: loan.collateral_type,
    collateral_description: loan.collateral_description,
    ltv_bps: loan.ltv_bps,
    purpose: loan.purpose,
    purpose_description: loan.purpose_description,
    investor_summary: loan.investor_summary,
    borrower_country: String((loan.borrower_disclosure as { country?: string }).country ?? ""),
    borrower_sector: "",
    borrower_year_founded: null,
    originator: null,
    published_at: loan.funding_deadline,
    funding_deadline: loan.funding_deadline,
    funded_at: loan.funding_deadline,
    record: loan.status === "defaulted" || loan.status === "late"
      ? {
          installments_total: loan.term_months,
          installments_paid: 9,
          principal_repaid_minor: Math.round(loan.principal_minor * 0.3),
          interest_paid_minor: Math.round(loan.principal_minor * 0.06),
          outstanding_principal_minor: Math.round(loan.principal_minor * 0.7),
          days_past_due: loan.status === "late" ? 21 : 64,
          defaulted_on: loan.status === "defaulted" ? fixtureIsoDate(-2, 10) : null,
          public_note: ""
        }
      : null
  }))
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
        // 2% seller fee (owner decision 2026-10-16).
        seller_net_proceeds_minor: amount(8252.09),
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
        maturity_date: "2028-11-30",
        schedule_version: 1,
        schedule: []
      },
      received_principal_minor: 0,
      received_interest_minor: amount(1044),
      repayment_fee_minor: 0,
      // S3 preview: one overdue interest payment and the next scheduled ones (EUR 12,000 at 8%).
      investment_schedule: [
        { loan_installment_id: "GA-2256-I-7", schedule_version: 1, installment_number: 7, due_date: "2026-05-15", projected_principal_minor: 0, projected_interest_minor: amount(80), projected_total_minor: amount(80), days_past_due: 21, status: "overdue" },
        { loan_installment_id: "GA-2256-I-8", schedule_version: 1, installment_number: 8, due_date: "2026-06-15", projected_principal_minor: 0, projected_interest_minor: amount(80), projected_total_minor: amount(80), days_past_due: 0, status: "upcoming" },
        { loan_installment_id: "GA-2256-I-9", schedule_version: 1, installment_number: 9, due_date: "2026-07-15", projected_principal_minor: 0, projected_interest_minor: amount(80), projected_total_minor: amount(80), days_past_due: 0, status: "upcoming" },
        { loan_installment_id: "GA-2256-I-10", schedule_version: 1, installment_number: 10, due_date: "2026-08-15", projected_principal_minor: 0, projected_interest_minor: amount(80), projected_total_minor: amount(80), days_past_due: 0, status: "upcoming" }
      ],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      // U33-DEC-22: the stages the team recorded, and the next step when it is known.
      recovery_stages: [
        { title: "Reminder sent", occurred_on: fixtureIsoDateFromToday(-18), investor_note: "Banxum reminded the borrower in writing." }
      ],
      recovery_next_step: { title: "Formal notice", occurred_on: fixtureIsoDateFromToday(7), investor_note: "Planned if the payment has not arrived by then." },
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
      recovery_stages: [
        { title: "Formal notice", occurred_on: fixtureIsoDateFromToday(-150), investor_note: "Banxum sent the borrower a formal notice." },
        { title: "Enforcement of the security", occurred_on: fixtureIsoDateFromToday(-60), investor_note: "Banxum is collecting the assigned receivables for all investors." }
      ],
      recovery_next_step: { title: "Collection from the debtors", occurred_on: null, investor_note: "The debtors of the assigned receivables are being contacted. A date is not known yet." },
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
    },
    // S3 preview: a repaid and a sold investment for the history.
    {
      ...directHoldingAcquisitionFields(amount(4000)),
      id: "H-2120",
      status: "closed",
      source_type: "primary",
      original_principal_minor: amount(4000),
      current_principal_minor: 0,
      currency: "EUR",
      loan_share_ppm: 40000,
      assignment_effective_at: "2025-10-10T10:00:00+02:00",
      loan: {
        ...directPortfolioLoanFields(780, amount(150000), "Assigned trade receivables of the borrower."),
        loan_id: "GA-2120",
        loan_title: "Lombardia trade receivables",
        loan_status: "repaid",
        borrower_id: "borrower-2120",
        borrower_name: "Officine Lario Srl",
        borrower_country: "IT",
        purpose: "working_capital",
        collateral_type: "receivables",
        interest_rate_bps: 780,
        default_penalty_interest_bps: 0,
        term_months: 6,
        repayment_type: "bullet_periodic_interest",
        currency: "EUR",
        is_refinancing: false,
        original_principal_minor: amount(100000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(100000),
        funding_deadline: "2025-10-10",
        loan_start_date: "2025-10-10",
        first_payment_date: "2025-11-10",
        ltv_bps: null,
        days_past_due: 0,
        maturity_date: "2026-04-10",
        schedule_version: 1,
        schedule: [
          { id: "GA-2120-I-6", schedule_version: 1, installment_number: 6, due_date: "2026-04-10", principal_minor: amount(100000), interest_minor: amount(650), total_minor: amount(100650), paid_principal_minor: amount(100000), paid_interest_minor: amount(650), outstanding_principal_minor: 0, outstanding_interest_minor: 0, outstanding_total_minor: 0, is_paid: true, days_past_due: 0, status: "paid", row_type: "scheduled_installment", label: "Installment 6", payment_date: "2026-04-10" }
        ]
      },
      received_principal_minor: amount(4000),
      received_interest_minor: amount(154.72),
      repayment_fee_minor: 0,
      investment_schedule: [],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null,
      open_secondary_listing: null
    },
    {
      ...directHoldingAcquisitionFields(amount(4920)),
      id: "H-2199",
      status: "transferred",
      source_type: "primary",
      original_principal_minor: amount(4920),
      current_principal_minor: 0,
      currency: "CHF",
      loan_share_ppm: 0,
      assignment_effective_at: "2025-12-01T10:00:00+01:00",
      loan: {
        ...directPortfolioLoanFields(690, amount(820000), "Registered real-estate security supporting the borrower obligation."),
        loan_id: "GA-2199",
        loan_title: "Lugano logistics hub",
        loan_status: "active",
        borrower_id: "borrower-2199",
        borrower_name: "Ceresio Logistica SA",
        borrower_country: "CH",
        purpose: "capex",
        collateral_type: "real_estate",
        interest_rate_bps: 690,
        default_penalty_interest_bps: 1200,
        term_months: 24,
        repayment_type: "equal_installments",
        currency: "CHF",
        is_refinancing: false,
        original_principal_minor: amount(500000),
        original_repayment_type: null,
        original_interest_only_months: null,
        principal_minor: amount(500000),
        funding_deadline: "2025-12-01",
        loan_start_date: "2025-12-01",
        first_payment_date: "2026-01-01",
        ltv_bps: 6100,
        days_past_due: 0,
        schedule_version: 1,
        schedule: []
      },
      received_principal_minor: 0,
      received_interest_minor: amount(113.16),
      repayment_fee_minor: 0,
      investment_schedule: [],
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null,
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
    },
    {
      id: "W-311:cancellation",
      activity_type: "withdrawal_cancellation",
      occurred_at: "2026-04-22T10:05:00+02:00",
      direction: "in",
      title: "Withdrawal cancelled",
      amount_minor: amount(2000),
      currency: "CHF",
      status: "returned",
      loan_id: null,
      loan_title: "",
      metadata: { withdrawal_request_id: "W-311", is_forced: false }
    },
    {
      id: "W-311",
      activity_type: "withdrawal_request",
      occurred_at: "2026-04-21T16:40:00+02:00",
      direction: "out",
      title: "Withdrawal request",
      amount_minor: amount(2000),
      currency: "CHF",
      status: "cancelled",
      loan_id: null,
      loan_title: "",
      metadata: { is_forced: false, finalized_at: "", cancelled_at: "2026-04-22T10:05:00+02:00" }
    },
    {
      id: "W-298",
      activity_type: "withdrawal_request",
      occurred_at: "2026-04-08T09:12:00+02:00",
      direction: "out",
      title: "Withdrawal request",
      amount_minor: amount(1500),
      currency: "CHF",
      status: "finalized",
      loan_id: null,
      loan_title: "",
      metadata: { is_forced: false, finalized_at: "2026-04-09T11:00:00+02:00", cancelled_at: "" }
    },
    // Wallet preview (Transactions): the backend's own activity types.
    {
      id: "A-5",
      activity_type: "primary_order",
      occurred_at: "2026-06-02T10:10:00+02:00",
      direction: "internal",
      title: "Primary-market investment order",
      amount_minor: amount(6500),
      currency: "CHF",
      status: "partially_allocated",
      loan_id: "GA-2401",
      loan_title: "Helvetia Logistik AG",
      metadata: {}
    },
    {
      id: "A-6",
      activity_type: "repayment_distribution",
      occurred_at: "2026-05-21T08:00:00+02:00",
      direction: "in",
      title: "Loan repayment credited",
      amount_minor: amount(412.35),
      currency: "CHF",
      status: "",
      loan_id: "GA-2380",
      loan_title: "Helvetia Logistik AG",
      metadata: { principal_minor: amount(354.1), interest_minor: amount(58.25), fee_minor: 0 }
    },
    {
      id: "A-7",
      activity_type: "balance_deposit",
      occurred_at: "2026-05-09T09:20:00+02:00",
      direction: "in",
      title: "Deposit",
      amount_minor: amount(12000),
      currency: "CHF",
      status: "available",
      loan_id: null,
      loan_title: "",
      metadata: {}
    },
    {
      id: "A-8",
      activity_type: "recovery_distribution",
      occurred_at: "2026-04-09T10:00:00+02:00",
      direction: "in",
      title: "Recovery payment credited",
      amount_minor: amount(980),
      currency: "CHF",
      status: "",
      loan_id: "GA-2150",
      loan_title: "Alpen Holzbau GmbH",
      metadata: { principal_minor: amount(612), contractual_interest_minor: amount(188), default_interest_minor: amount(96), penalties_minor: 0, other_costs_minor: -amount(42) }
    },
    {
      id: "A-9",
      activity_type: "primary_order",
      occurred_at: "2026-03-12T15:40:00+01:00",
      direction: "internal",
      title: "Primary-market investment order",
      amount_minor: amount(6000),
      currency: "EUR",
      status: "closed_invested",
      loan_id: "GA-2201",
      loan_title: "Lago Maggiore Hotels SA",
      metadata: {}
    },
    {
      id: "A-10",
      activity_type: "secondary_purchase",
      occurred_at: "2026-02-18T11:25:00+01:00",
      direction: "out",
      title: "Secondary-market purchase",
      amount_minor: amount(2480),
      currency: "EUR",
      status: "completed",
      loan_id: "GA-2287",
      loan_title: "Rhône Vignobles SA",
      metadata: {}
    },
    {
      id: "A-11",
      activity_type: "balance_deposit",
      occurred_at: "2026-02-10T09:00:00+01:00",
      direction: "in",
      title: "Deposit",
      amount_minor: amount(8500),
      currency: "EUR",
      status: "invested",
      loan_id: null,
      loan_title: "",
      metadata: {}
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
      message: "CHF 980.00 was not invested within 58 days and goes back to your bank."
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
    // No buyer fee since 2026-10-16.
    taker_fee_bps: 0,
    minimum_taker_fee_minor: 0,
    taker_fee_minor: 0,
    buyer_total_cost_minor: amount(5147),
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
    remaining_term_months: 24,
    is_own_listing: false,
    borrower_name: "Engadin Hospitality AG",
    borrower_country: "CH"
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
    taker_fee_bps: 0,
    minimum_taker_fee_minor: 0,
    taker_fee_minor: 0,
    buyer_total_cost_minor: amount(10980),
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
    remaining_term_months: 14,
    is_own_listing: false,
    borrower_name: "Jura Précision SA",
    borrower_country: "CH"
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
      maker_fee_minor: amount(72.07),
      seller_net_proceeds_minor: amount(3531.53),
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
      loan_title: "Lugano logistics hub",
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
  ],
  terms: {
    daily_limit_chf_minor: amount(100000),
    daily_limit_used_chf_minor: 0,
    quote_ttl_seconds: 60,
    platform_fee_bps: 150
  }
};
