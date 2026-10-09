// Shared msw handlers for real-API (non-preview) investor portal tests. Each test file stubs
// MODE/VITE_PREVIEW before importing App (see SessionGate.test.tsx).
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";

import {
  getV1AuthMeRetrieveResponseMock,
  getV1InvestorPortalDashboardRetrieveResponseMock,
  getV1InvestorPortalPortfolioRetrieveResponseMock,
  getV1KycStatusRetrieveResponseMock,
  type BalanceLot,
  type BalanceSummary,
  type InvestorBalancePortal
} from "../api/generated/banxumApi";

export const investorUser = {
  id: "u1",
  email: "investor@example.com",
  full_name: "Una Investor",
  investor_reference: "R1",
  account_type: "natural_person_lender",
  status: "active",
  phone_verified: true,
  marketing_consent: false
};

export const platformAsOf = "2026-12-10T11:00:00Z";

export function meResponse(businessDate = "2026-12-10") {
  return {
    ...getV1AuthMeRetrieveResponseMock(),
    user: investorUser,
    qa_controls_available: false,
    platform_business_date: businessDate
  };
}

export function summary(currency: string, values: Partial<BalanceSummary> = {}): BalanceSummary {
  return {
    investor_user_id: "u1",
    currency,
    total_available_minor: 0,
    investable_minor: 0,
    withdraw_only_minor: 0,
    overdue_minor: 0,
    frozen_minor: 0,
    penalty_mode_minor: 0,
    penalty_charged_minor: 0,
    lot_count: 0,
    active_lot_count: 0,
    next_investment_deadline_at: null,
    next_withdrawal_deadline_at: null,
    ...values
  };
}

export function lot(values: Partial<BalanceLot> & Pick<BalanceLot, "id" | "currency">): BalanceLot {
  return {
    source_type: "deposit",
    status: "available",
    bucket: "investable",
    received_at: "2026-10-01T10:00:00Z",
    investment_deadline_at: "2026-11-30T23:00:00Z",
    withdrawal_deadline_at: "2026-11-30T23:00:00Z",
    days_until_investment_deadline: 20,
    days_until_withdrawal_deadline: 20,
    original_amount_minor: 0,
    available_amount_minor: 0,
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: false,
    blocks_financial_actions: false,
    ...values
  };
}

export function balances(values: Partial<InvestorBalancePortal> = {}): InvestorBalancePortal {
  return {
    as_of: platformAsOf,
    summaries: [summary("CHF"), summary("EUR")],
    lots: [],
    payout_instructions: [],
    pending_withdrawals: [],
    has_penalty_mode_balance: false,
    penalty_bps_per_day: 100,
    ...values
  };
}

/** /auth/me, KYC, notifications, loans, dashboard and portfolio for a signed-in investor. */
export function shellHandlers(options: { balances?: () => InvestorBalancePortal; me?: () => Response } = {}) {
  return [
    http.get("*/api/v1/auth/me/", () => options.me?.() ?? HttpResponse.json(meResponse())),
    http.get("*/api/v1/kyc/status/", () =>
      HttpResponse.json({ ...getV1KycStatusRetrieveResponseMock(), status: "approved", financial_access_allowed: true })
    ),
    http.get("*/api/v1/investor/portal/notifications/", () => HttpResponse.json({ notifications: [], unread_count: 0 })),
    http.get("*/api/v1/marketplace/primary/loans/", () => HttpResponse.json([])),
    http.get("*/api/v1/investor/portal/balances/", () => HttpResponse.json(options.balances?.() ?? balances())),
    http.get("*/api/v1/investor/portal/dashboard/", () =>
      HttpResponse.json({
        ...getV1InvestorPortalDashboardRetrieveResponseMock(),
        as_of: platformAsOf,
        portfolio_summary: {
          holding_count: 0,
          active_holding_count: 0,
          outstanding_principal_by_currency: [],
          original_principal_by_currency: [],
          realized_interest_by_currency: [],
          late_or_defaulted_exposure_by_currency: []
        },
        pending_actions: [],
        recent_activity: []
      })
    ),
    http.get("*/api/v1/investor/portal/portfolio/", () =>
      HttpResponse.json({ ...getV1InvestorPortalPortfolioRetrieveResponseMock(), as_of: platformAsOf, holdings: [] })
    ),
    http.get("*/api/v1/investor/smart-invest/", () =>
      HttpResponse.json({ rule: null, match_count: 0, open_opportunity_count: 0, matches: [] })
    )
  ];
}

export function renderLiveApp(App: ComponentType, path: string, queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  window.history.pushState({}, "", path);
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
  return queryClient;
}
