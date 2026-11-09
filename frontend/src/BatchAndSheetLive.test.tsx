// Real-API checks for Smart-Invest matches and the opportunity page (QA audit 2026-10-09):
// A-31 / A-42 are superseded by U33-DEC-19 (no batch approval: every match is confirmed on its own
// opportunity page), A-39 (the opportunity names the borrower and what can really be invested here,
// and the amount parses with or without separators; nothing is pre-filled, U33-DEC-08).
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1MarketplacePrimaryLoansRetrieveResponseMock } from "./api/generated/banxumApi";
import { balancesPayload, emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("codes", "acceptances", "batches");
});

const LOAN_ID = "88888888-8888-4888-8888-888888888888";

const preview = {
  loan_id: LOAN_ID,
  product_type: "direct",
  investment_flow: "primary_order",
  title: "Audit Direct Loan",
  purpose: "working_capital",
  collateral_type: "real_estate",
  interest_rate_bps: 1200,
  yield_bps: 1200,
  underlying_interest_rate_bps: 1200,
  term_months: 12,
  remaining_term_days: null,
  funding_deadline: "2026-10-30",
  maturity_date: null,
  status: "published",
  loan_status: "published",
  opportunity_status: "open",
  currency: "CHF",
  principal_minor: 1_000_000,
  committed_principal_minor: 0,
  remaining_capacity_minor: 1_000_000,
  fillable_amount_minor: 1_000_000,
  minimum_investment_minor: 100_000,
  ltv_bps: 5000,
  is_refinancing: false,
  originator_id: null,
  originator_name: null,
  borrower_display_name: null,
  skin_in_the_game_bps: 0,
  minimum_subscription_bps: 5000
};

function loanDetail(overrides: Record<string, unknown> = {}) {
  return {
    ...getV1MarketplacePrimaryLoansRetrieveResponseMock(),
    ...preview,
    borrower_disclosure: { legal_name: "Audit Borrower AG" },
    story: { version: 1, blocks: [] },
    loan_schedule: [],
    originator_schedule: [],
    collateral_value_minor: 2_000_000,
    default_penalty_interest_bps: 0,
    repayment_type: "amortizing_principal_interest",
    entitlement_start_date: null,
    // Not a Swiss-borrower loan: the generated mock fills these at random (a "full" loan blocks investing).
    max_investors: null,
    places_left: null,
    is_existing_investor: false,
    ...overrides
  };
}

// U33-DEC-19 replaces the Smart-Invest batch (A-31 / A-42): a match opens its opportunity page, where
// the single-investment flow asks for the terms, the risk acknowledgement and the code on its own.
test("U33-DEC-19: a Smart-Invest match opens its opportunity page; there is no batch approval", async () => {
  server.use(
    ...investorShellHandlers(calls, {
      balances: () => balancesPayload([{ currency: "CHF", investableMinor: 1_000_000 }]),
      marketplaceLoans: () => [preview]
    }),
    http.get("*/api/v1/investor/smart-invest/", () =>
      HttpResponse.json({
        rule: {
          id: "rule-1",
          is_active: true,
          revision: 1,
          minimum_yield_bps: null,
          maximum_term_months: null,
          originators: [],
          collateral: [],
          currencies: ["CHF"],
          purposes: [],
          loan_kinds: [],
          activated_at: "2026-10-01T00:00:00Z",
          deactivated_at: null,
          created_at: "2026-10-01T00:00:00Z",
          updated_at: "2026-10-01T00:00:00Z"
        },
        match_count: 1,
        open_opportunity_count: 1,
        matches: [preview]
      })
    ),
    http.get(`*/api/v1/marketplace/primary/loans/${LOAN_ID}/`, () => HttpResponse.json(loanDetail())),
    http.post("*/api/v1/marketplace/primary/orders/batch/", async ({ request }) => {
      calls.batches.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({}, { status: 400 });
    })
  );
  renderLiveApp(App, "/smart-invest");
  const review = await screen.findByRole("button", { name: "Review investment in Audit Direct Loan" }, { timeout: 5000 });
  expect(screen.getByText("CHF · Any interest rate · Any duration")).toBeInTheDocument();
  // Nothing to select, approve or confirm in bulk on the Smart Invest page.
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Review & confirm|Approve|Place \d/ })).not.toBeInTheDocument();

  fireEvent.click(review);
  await waitFor(() => expect(window.location.pathname).toBe(`/marketplace/${LOAN_ID}`));
  expect(calls.batches).toHaveLength(0);
  expect(calls.codes).toHaveLength(0);
  expect(calls.acceptances).toHaveLength(0);
}, 30_000);

test("A-39: the opportunity page names the borrower and what can be invested here, and its amount parses", async () => {
  server.use(
    ...investorShellHandlers(calls, {
      // A wallet of CHF 100,500.01 and a loan with CHF 10,000.00 left.
      balances: () => balancesPayload([{ currency: "CHF", investableMinor: 10_050_001 }]),
      marketplaceLoans: () => [preview]
    }),
    http.get(`*/api/v1/marketplace/primary/loans/${LOAN_ID}/`, () => HttpResponse.json(loanDetail()))
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}`);
  await screen.findByRole("heading", { level: 1, name: "Audit Direct Loan" }, { timeout: 5000 });

  // The claim is against the borrower, not the loan title; the limits come from the loan.
  expect(screen.getByText(/Audit Borrower AG/)).toBeInTheDocument();
  expect(screen.getByText(/Minimum CHF 1\.000,00 · CHF 10\.000,00 available/)).toBeInTheDocument();
  expect(screen.getByText("Principal and interest paid monthly")).toBeInTheDocument();
  const amount = screen.getByRole("textbox", { name: "Choose investment amount" });
  expect(amount).toHaveValue("");
  await screen.findByText(/Your CHF balance for this loan: CHF 100\.500,01/, {}, { timeout: 5000 });

  // More than the loan still takes names the capacity, not the wallet.
  fireEvent.change(amount, { target: { value: "50000" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
  const error = document.getElementById("iv-error") as HTMLElement;
  expect(error).toHaveTextContent(/This opportunity has only CHF 10\.000,00 left/);
  expect(error).not.toHaveTextContent(/100\.500,01/);

  // An ambiguous comma is refused with a hint, never guessed.
  fireEvent.change(amount, { target: { value: "1,000" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
  expect(screen.getByText(/Write thousands as 1\.000\./)).toBeInTheDocument();

  // A Swiss-style amount is read and handed to Review & sign.
  fireEvent.change(amount, { target: { value: "9’000,50" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
  expect(window.location.pathname).toBe(`/marketplace/${LOAN_ID}/invest`);
  expect(await screen.findByRole("textbox", { name: "Your investment amount" })).toHaveValue("9.000,50");
}, 30_000);
