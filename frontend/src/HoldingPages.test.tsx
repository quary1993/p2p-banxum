// Real-API holding page checks (audit SERVICING-17): a repaid holding must stay reachable from
// My investments, an LO holding must not show a "1 months" term or count each payment twice,
// and a defaulted holding must not open on an "Upcoming" payment.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1AuthMeRetrieveResponseMock, getV1KycStatusRetrieveResponseMock } from "./api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

function scheduleRow(overrides: Record<string, unknown>) {
  return {
    id: "row",
    schedule_version: 1,
    installment_number: 1,
    due_date: "2026-11-19",
    principal_minor: 200_000,
    interest_minor: 2_000,
    penalty_minor: 0,
    fee_minor: 0,
    total_minor: 202_000,
    paid_principal_minor: 0,
    paid_interest_minor: 0,
    outstanding_principal_minor: 0,
    outstanding_interest_minor: 0,
    outstanding_total_minor: 0,
    is_paid: false,
    days_past_due: 0,
    status: "upcoming",
    row_type: "scheduled_installment",
    label: "Installment",
    payment_date: null,
    ...overrides
  };
}

function holding(id: string, overrides: Record<string, unknown>, loanOverrides: Record<string, unknown>) {
  return {
    id,
    status: "active",
    source_type: "primary_market",
    original_principal_minor: 400_000,
    current_principal_minor: 400_000,
    currency: "EUR",
    loan_share_ppm: 500_000,
    assignment_effective_at: "2026-10-09T10:00:00Z",
    received_principal_minor: 0,
    received_interest_minor: 0,
    received_penalty_minor: 0,
    repayment_fee_minor: 0,
    investment_schedule: [],
    acquisition_cash_consideration_minor: null,
    acquisition_cash_flow: [],
    recovered_principal_minor: 0,
    recovered_contractual_interest_minor: 0,
    recovered_default_interest_minor: 0,
    recovered_penalties_minor: 0,
    recovered_other_costs_minor: 0,
    latest_public_note: null,
    open_secondary_listing: null,
    ...overrides,
    loan: {
      loan_id: `${id}-loan`,
      product_type: "direct",
      loan_title: "Loan",
      loan_status: "active",
      borrower_id: null,
      borrower_name: "Borrower",
      borrower_country: "CH",
      originator_id: null,
      originator_name: "",
      purpose: "working_capital",
      collateral_type: "receivables",
      collateral_value_minor: 0,
      collateral_description: "",
      skin_in_the_game_bps: 0,
      risk_rating: "B",
      interest_rate_bps: 840,
      yield_bps: 840,
      underlying_interest_rate_bps: 1200,
      default_penalty_interest_bps: 0,
      term_months: 3,
      repayment_type: "amortizing_principal_interest",
      currency: "EUR",
      is_refinancing: false,
      original_principal_minor: 1_000_000,
      original_repayment_type: null,
      original_interest_only_months: null,
      principal_minor: 0,
      funding_deadline: null,
      loan_start_date: "2026-10-09",
      first_payment_date: null,
      ltv_bps: null,
      days_past_due: 0,
      schedule_version: 1,
      schedule: [],
      ...loanOverrides
    }
  };
}

// Repaid LO holding: three recorded payments and three schedule rows. Term was "1 months".
const repaidLo = holding(
  "repaid-lo",
  { status: "closed", current_principal_minor: 0, received_interest_minor: 4_200 },
  {
    product_type: "originator_claim",
    loan_title: "Completed LO claim",
    loan_status: "repaid",
    borrower_name: "European Manufacturing SME #A1",
    originator_name: "Audit Originator A",
    term_months: 1,
    remaining_term_days: 0,
    maturity_date: "2026-12-19",
    schedule: [
      scheduleRow({ id: "p1", installment_number: 0, row_type: "repayment_event", is_paid: true, status: "paid", due_date: "2026-10-19", payment_date: "2026-10-19" }),
      scheduleRow({ id: "s1", installment_number: 1, row_type: "originator_schedule", is_paid: true, status: "historical", due_date: "2026-10-19" }),
      scheduleRow({ id: "p2", installment_number: 0, row_type: "repayment_event", is_paid: true, status: "paid", due_date: "2026-11-19", payment_date: "2026-11-19" }),
      scheduleRow({ id: "s2", installment_number: 2, row_type: "originator_schedule", is_paid: true, status: "historical", due_date: "2026-11-19" }),
      scheduleRow({ id: "p3", installment_number: 0, row_type: "repayment_event", is_paid: true, status: "paid", due_date: "2026-12-19", payment_date: "2026-12-19" }),
      scheduleRow({ id: "s3", installment_number: 3, row_type: "originator_schedule", is_paid: true, status: "historical", due_date: "2026-12-19" })
    ]
  }
);

// Defaulted Direct holding: first installment overdue, the rest in the future.
const defaulted = holding(
  "defaulted-direct",
  { currency: "CHF", original_principal_minor: 400_000, current_principal_minor: 370_567 },
  {
    loan_title: "Defaulted direct loan",
    loan_status: "defaulted",
    currency: "CHF",
    days_past_due: 16,
    schedule: [
      scheduleRow({ id: "d1", installment_number: 1, due_date: "2026-11-11", status: "overdue", days_past_due: 16 }),
      scheduleRow({ id: "d2", installment_number: 2, due_date: "2026-12-11" }),
      scheduleRow({ id: "d3", installment_number: 3, due_date: "2027-01-11" })
    ]
  }
);

function useInvestorApi() {
  const portfolio = {
    as_of: "2026-12-20T11:00:00Z",
    holdings: [repaidLo, defaulted],
    summary: {
      holding_count: 2,
      active_holding_count: 1,
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
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        ...getV1AuthMeRetrieveResponseMock(),
        user: {
          id: "u1",
          email: "investor@example.com",
          full_name: "Investor One",
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
    http.get("*/api/v1/investor/portal/balances/", () =>
      HttpResponse.json({ as_of: "2026-12-20T11:00:00Z", summaries: [], lots: [], payout_instructions: [], has_penalty_mode_balance: false })
    ),
    http.get("*/api/v1/marketplace/primary/loans/", () => HttpResponse.json([])),
    http.get("*/api/v1/investor/portal/portfolio/", () => HttpResponse.json(portfolio)),
    http.get("*/api/v1/investor/portal/activity/", () => HttpResponse.json({ entries: [] })),
    http.get("*/api/v1/investor/portal/primary-orders/", () => HttpResponse.json({ orders: [] }))
  );
}

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>
  );
}

test("a repaid holding is listed under Completed and opens its holding page", async () => {
  useInvestorApi();
  renderAt("/portfolio");

  fireEvent.click(await screen.findByRole("tab", { name: "Completed" }, { timeout: 5000 }));
  const table = await screen.findByRole("table");
  expect(within(table).getByText("Completed LO claim")).toBeInTheDocument();
  expect(within(table).getByText("Repaid")).toBeInTheDocument();
  expect(within(table).queryByText("Defaulted direct loan")).not.toBeInTheDocument();

  fireEvent.click(within(table).getByRole("button", { name: "Open Completed LO claim" }));
  expect(await screen.findByRole("heading", { name: "Completed LO claim" }, { timeout: 5000 })).toBeInTheDocument();
  // Three installments, not six rows; the maturity date instead of "1 months".
  expect(screen.getByText(/scheduled borrower payments recorded/).textContent).toContain("3 of 3");
  expect(screen.getByText("Matures")).toBeInTheDocument();
  expect(screen.queryByText("1 months")).not.toBeInTheDocument();
}, 30_000);

test("a defaulted holding opens on the overdue payment, not an upcoming one", async () => {
  useInvestorApi();
  renderAt("/portfolio/defaulted-direct");

  expect(await screen.findByRole("heading", { name: "Defaulted direct loan" }, { timeout: 5000 })).toBeInTheDocument();
  const payment = screen.getByRole("heading", { name: "Selected payment" }).closest(".inv-payment") as HTMLElement;
  expect(within(payment).getByText("11 Nov 2026")).toBeInTheDocument();
  expect(within(payment).getByText("Overdue")).toBeInTheDocument();
  expect(within(payment).queryByText("Upcoming")).not.toBeInTheDocument();
}, 30_000);
