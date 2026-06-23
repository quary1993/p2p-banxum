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
  PortfolioExposure,
  PortfolioSummary,
  PrimaryOrdersPortal,
  SecondaryMarketActivityPortal,
  SecondaryMarketBuyerListing
} from "../api/generated/banxumApi";
import type { InvestorPortalFixture } from "./types";

const investorId = "demo-investor-1";

const amount = (value: number) => Math.round(value * 100);

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

export const marketplaceLoansFixture: MarketplaceLoanPreview[] = [
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
    remaining_capacity_minor: amount(362500)
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
    remaining_capacity_minor: amount(62000)
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
    remaining_capacity_minor: amount(1564200)
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
    remaining_capacity_minor: 0
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
    remaining_capacity_minor: amount(30000)
  }
];

export const loanDetailsFixture: MarketplaceLoanDetail[] = marketplaceLoansFixture.map((loan) => ({
  ...loan,
  borrower_id: `borrower-${loan.loan_id}`,
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
  repayment_type: loan.term_months >= 24 ? "bullet" : "equal_installments",
  first_payment_date: "2026-07-31",
  schedule_version: 1
}));

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

export const portfolioFixture: InvestorPortfolio = {
  as_of: "2026-06-05T10:00:00+02:00",
  summary: portfolioSummary,
  exposure: exposureFixture,
  holdings: [
    {
      id: "H-2310",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(10000),
      current_principal_minor: amount(8420.5),
      currency: "CHF",
      loan_share_ppm: 120000,
      assignment_effective_at: "2026-01-18T10:00:00+01:00",
      loan: {
        loan_id: "GA-2310",
        loan_title: "Engadin Hospitality AG",
        loan_status: "funded",
        borrower_id: "borrower-2310",
        borrower_name: "Engadin Hospitality AG",
        borrower_country: "CH",
        purpose: "Hospitality refinancing",
        collateral_type: "real_estate",
        risk_rating: "B",
        interest_rate_bps: 720,
        term_months: 24,
        repayment_type: "equal_installments",
        currency: "CHF",
        principal_minor: amount(100000),
        funding_deadline: "2026-01-31",
        first_payment_date: "2026-02-28",
        ltv_bps: 6100,
        days_past_due: 0
      },
      received_principal_minor: amount(1579.5),
      received_interest_minor: amount(612.4),
      repayment_fee_minor: 0,
      recovered_principal_minor: 0,
      recovered_contractual_interest_minor: 0,
      recovered_default_interest_minor: 0,
      recovered_penalties_minor: 0,
      recovered_other_costs_minor: 0,
      latest_public_note: null
    },
    {
      id: "H-2256",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(12000),
      current_principal_minor: amount(12000),
      currency: "EUR",
      loan_share_ppm: 90000,
      assignment_effective_at: "2025-11-15T10:00:00+01:00",
      loan: {
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
        term_months: 36,
        repayment_type: "bullet",
        currency: "EUR",
        principal_minor: amount(800000),
        funding_deadline: "2025-11-30",
        first_payment_date: "2025-12-31",
        ltv_bps: 6500,
        days_past_due: 21
      },
      received_principal_minor: 0,
      received_interest_minor: amount(1044),
      repayment_fee_minor: 0,
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
      }
    },
    {
      id: "H-2201",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(6000),
      current_principal_minor: amount(6000),
      currency: "EUR",
      loan_share_ppm: 45000,
      assignment_effective_at: "2025-09-01T10:00:00+02:00",
      loan: {
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
        term_months: 24,
        repayment_type: "bullet",
        currency: "EUR",
        principal_minor: amount(400000),
        funding_deadline: "2025-09-15",
        first_payment_date: "2025-10-31",
        ltv_bps: 7000,
        days_past_due: 64
      },
      received_principal_minor: 0,
      received_interest_minor: amount(270),
      repayment_fee_minor: 0,
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
      }
    },
    {
      id: "H-2150",
      status: "active",
      source_type: "primary",
      original_principal_minor: amount(5000),
      current_principal_minor: amount(1180),
      currency: "CHF",
      loan_share_ppm: 80000,
      assignment_effective_at: "2025-06-01T10:00:00+02:00",
      loan: {
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
        term_months: 24,
        repayment_type: "equal_installments",
        currency: "CHF",
        principal_minor: amount(250000),
        funding_deadline: "2025-06-15",
        first_payment_date: "2025-07-31",
        ltv_bps: 7500,
        days_past_due: 142
      },
      received_principal_minor: amount(3820),
      received_interest_minor: amount(95.2),
      repayment_fee_minor: 0,
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
      }
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
      loan_title: "Engadin Hospitality AG",
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
    listed_at: "2026-06-01T09:00:00+02:00"
  },
  {
    id: "SM-3298",
    loan_id: "GA-2256",
    loan_title: "Loan C - Real estate - DE",
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
    listed_at: "2026-06-02T09:00:00+02:00"
  }
];

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
  purchases_as_buyer: [],
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
      fee_minor: amount(67.5),
      target_amount_minor: amount(4500.86),
      status: "settled",
      executed_at: "2026-05-30T11:03:00+02:00"
    }
  ]
};
