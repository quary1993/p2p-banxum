import type {
  BalanceLot,
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

const emptySummary: PortfolioSummary = {
  holding_count: 0,
  active_holding_count: 0,
  outstanding_principal_by_currency: [],
  original_principal_by_currency: [],
  realized_interest_by_currency: [],
  late_or_defaulted_exposure_by_currency: []
};

const emptyExposure: PortfolioExposure = {
  by_borrower: [],
  by_country: [],
  by_purpose: [],
  by_risk_rating: [],
  by_collateral_type: [],
  by_maturity: [],
  by_loan_status: []
};

export const portalFixture: InvestorPortalFixture = {
  today: "",
  profile: {
    id: "",
    name: "Investor account",
    initials: "IN",
    email: "Live account",
    country: "Self-scoped account",
    memberSince: "",
    phone: ""
  },
  depositInstructions: [],
  documents: [],
  notifications: [],
  recoverySplit: {
    loanId: "",
    totalMinor: 0,
    currency: "CHF",
    parts: []
  }
};

export const balanceLotsFixture: BalanceLot[] = [];

export const balancesFixture: InvestorBalancePortal = {
  as_of: "",
  summaries: [],
  lots: [],
  payout_instructions: [],
  has_penalty_mode_balance: false
};

export const marketplaceLoansFixture: MarketplaceLoanPreview[] = [];

export const loanDetailsFixture: MarketplaceLoanDetail[] = [];

export const portfolioFixture: InvestorPortfolio = {
  as_of: "",
  summary: emptySummary,
  exposure: emptyExposure,
  holdings: []
};

export const activityFixture: InvestorActivity = {
  entries: []
};

export const dashboardFixture: InvestorDashboard = {
  as_of: "",
  investor_user_id: "",
  balances: [],
  portfolio_summary: emptySummary,
  exposure: emptyExposure,
  pending_actions: [],
  recent_activity: []
};

export const primaryOrdersFixture: PrimaryOrdersPortal = {
  orders: []
};

export const secondaryListingsFixture: SecondaryMarketBuyerListing[] = [];

export const secondaryActivityFixture: SecondaryMarketActivityPortal = {
  listings: [],
  purchases_as_buyer: [],
  sales_as_seller: []
};

export const fxFixture: FxHistoryPortal = {
  quotes: [],
  exchanges: []
};
