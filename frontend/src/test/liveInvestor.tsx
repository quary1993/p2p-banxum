// Shared pieces for real-API (not fixture preview) investor tests: msw handlers for the
// signed-in investor shell and a render helper. Each test file still calls
// vi.stubEnv("MODE", "development") and vi.stubEnv("VITE_PREVIEW", "false") itself,
// before it imports App.
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse, type JsonBodyType } from "msw";
import type { ComponentType } from "react";

import {
  getV1AuthMeRetrieveResponseMock,
  getV1KycStatusRetrieveResponseMock
} from "../api/generated/banxumApi";

export type RecordedCalls = Record<string, Array<Record<string, unknown>>>;

export function emptyCalls(...names: string[]): RecordedCalls {
  return Object.fromEntries(names.map((name) => [name, []]));
}

type BalanceSummary = { currency: string; investableMinor: number };

export function balancesPayload(summaries: BalanceSummary[], payoutInstructions: unknown[] = []) {
  return {
    as_of: "2026-10-09T11:47:00Z",
    summaries: summaries.map(({ currency, investableMinor }) => ({
      investor_user_id: "u1",
      currency,
      total_available_minor: investableMinor,
      investable_minor: investableMinor,
      withdraw_only_minor: 0,
      overdue_minor: 0,
      frozen_minor: 0,
      penalty_mode_minor: 0,
      penalty_charged_minor: 0,
      lot_count: 1,
      active_lot_count: 1,
      next_investment_deadline_at: "2026-12-01T00:00:00Z",
      next_withdrawal_deadline_at: "2026-12-01T00:00:00Z"
    })),
    lots: summaries.map(({ currency, investableMinor }) => ({
      id: `lot-${currency}`,
      currency,
      source_type: "deposit",
      status: "available",
      bucket: "investable",
      received_at: "2026-10-02T10:00:00Z",
      investment_deadline_at: "2026-12-01T00:00:00Z",
      withdrawal_deadline_at: "2026-12-01T00:00:00Z",
      days_until_investment_deadline: 53,
      days_until_withdrawal_deadline: 53,
      original_amount_minor: investableMinor,
      available_amount_minor: investableMinor,
      invested_amount_minor: 0,
      converted_amount_minor: 0,
      withdrawn_amount_minor: 0,
      penalized_amount_minor: 0,
      requires_withdrawal: false,
      blocks_financial_actions: false
    })),
    payout_instructions: payoutInstructions,
    has_penalty_mode_balance: false
  };
}

export const emptyPortfolio = {
  as_of: "2026-10-09T11:47:00Z",
  holdings: [],
  summary: {
    holding_count: 0,
    active_holding_count: 0,
    outstanding_principal_by_currency: [],
    original_principal_by_currency: [],
    realized_interest_by_currency: [],
    late_or_defaulted_exposure_by_currency: []
  },
  exposure: {
    by_borrower: [],
    by_country: [],
    by_purpose: [],
    by_risk_rating: [],
    by_collateral_type: [],
    by_maturity: [],
    by_loan_status: []
  }
};

/** The signed-in investor shell; `calls.codes` records email-code requests. */
export function investorShellHandlers(
  calls: RecordedCalls,
  options: { balances?: () => JsonBodyType; portfolio?: () => JsonBodyType; marketplaceLoans?: () => JsonBodyType } = {}
) {
  calls.codes ??= [];
  calls.balanceReads ??= [];
  return [
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        ...getV1AuthMeRetrieveResponseMock(),
        user: {
          id: "u1",
          email: "u1@example.com",
          full_name: "Una Investor",
          investor_reference: "R1",
          account_type: "investor",
          status: "active",
          phone_verified: true,
          marketing_consent: false
        }
      })
    ),
    http.get("*/api/v1/kyc/status/", () =>
      HttpResponse.json({ ...getV1KycStatusRetrieveResponseMock(), status: "approved", financial_access_allowed: true })
    ),
    http.get("*/api/v1/investor/portal/notifications/", () => HttpResponse.json({ notifications: [], unread_count: 0 })),
    // Logged-in investors read the full list from /opportunities/ (A-44); /loans/ is the public preview.
    http.get("*/api/v1/marketplace/primary/opportunities/", () => HttpResponse.json(options.marketplaceLoans ? options.marketplaceLoans() : [])),
    http.get("*/api/v1/marketplace/primary/loans/", () => HttpResponse.json(options.marketplaceLoans ? options.marketplaceLoans() : [])),
    http.get("*/api/v1/investor/portal/balances/", () => {
      calls.balanceReads.push({});
      return HttpResponse.json(options.balances ? options.balances() : balancesPayload([{ currency: "CHF", investableMinor: 10_000_000 }]));
    }),
    http.get("*/api/v1/investor/portal/portfolio/", () => HttpResponse.json(options.portfolio ? options.portfolio() : emptyPortfolio)),
    http.get("*/api/v1/investor/portal/secondary-market/", () => HttpResponse.json({ entries: [] })),
    http.get("*/api/v1/marketplace/secondary/listings/", () => HttpResponse.json([])),
    http.post("*/api/v1/auth/sensitive-action-code/request/", async ({ request }) => {
      calls.codes.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({
        code_id: "22222222-2222-4222-8222-222222222222",
        action: "x",
        status: "sent",
        expires_at: "2026-10-09T11:57:00Z"
      });
    })
  ];
}

export function renderLiveApp(App: ComponentType, path: string) {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false, retry: false } } });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
  return { queryClient, ...view };
}
