// Real-API checks for the Smart Invest batch and the loan quick-view sheet (QA audit
// 2026-10-09): A-31 (a batch needs the same risk acknowledgement as one investment),
// A-42 (balances refresh after a batch), A-39 (the sheet projects what can really be
// lent, names the borrower, and pre-fills an amount that parses).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  getMarketplacePrimaryOrdersBatchCreateResponseMock,
  getV1DocumentsAcceptancesCreateResponseMock,
  getV1DocumentsTemplatesCurrentRetrieveResponseMock,
  getV1MarketplacePrimaryLoansRetrieveResponseMock,
  getV1MarketplacePrimaryOrdersCreateResponseMock
} from "./api/generated/banxumApi";
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
  risk_rating: "A",
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
    ...overrides
  };
}

test("A-31 / A-42: a Smart Invest batch needs the risk acknowledgement and refreshes balances", async () => {
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
          risk_ratings: [],
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
    http.get("*/api/v1/documents/templates/current/", () =>
      HttpResponse.json({ ...getV1DocumentsTemplatesCurrentRetrieveResponseMock(), id: "tpl-1", title: "Investment terms", version_number: 3, checkbox_labels: ["I accept."] })
    ),
    http.post("*/api/v1/documents/acceptances/", async ({ request }) => {
      calls.acceptances.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ ...getV1DocumentsAcceptancesCreateResponseMock(), id: "acc-1" }, { status: 201 });
    }),
    http.post("*/api/v1/marketplace/primary/orders/batch/", async ({ request }) => {
      const body = (await request.json()) as { items: Array<{ amount_minor: number }> };
      calls.batches.push(body);
      return HttpResponse.json({
        ...getMarketplacePrimaryOrdersBatchCreateResponseMock(),
        orders: [{
          ...getV1MarketplacePrimaryOrdersCreateResponseMock(),
          loan_id: LOAN_ID,
          status: "balance_allocated",
          requested_amount_minor: body.items[0].amount_minor,
          allocated_amount_minor: body.items[0].amount_minor,
          closed_reason: ""
        }],
        originator_purchases: [],
        order_count: 1,
        originator_purchase_count: 0
      }, { status: 201 });
    })
  );
  renderLiveApp(App, "/smart-invest");
  fireEvent.click(await screen.findByRole("button", { name: "Review & confirm →" }, { timeout: 5000 }));
  const dialog = screen.getByRole("dialog", { name: "Approve this allocation." });
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm 1" }));
  await within(dialog).findByText(/one terms acceptance and one email code cover every investment/, {}, { timeout: 5000 });
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /primary-market investment terms/i }));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  await waitFor(() => expect(calls.codes).toHaveLength(1));
  // Without the risk acknowledgement nothing can be placed.
  expect(within(dialog).getByRole("button", { name: "Place 1 investment" })).toBeDisabled();
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /risk disclosure/i }));
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Place 1 investment" })).toBeEnabled());
  const balanceReadsBefore = calls.balanceReads.length;
  fireEvent.click(within(dialog).getByRole("button", { name: "Place 1 investment" }));
  await within(dialog).findByText("Every selected investment is in.", {}, { timeout: 5000 });

  expect(calls.batches).toHaveLength(1);
  // The balance pills and the plan are reloaded after the money moved.
  await waitFor(() => expect(calls.balanceReads.length).toBeGreaterThan(balanceReadsBefore));
  expect(within(dialog).getByText(/One order reserves balance until the applicable funding round closes\./)).toBeInTheDocument();
}, 30_000);

test("A-39: the quick-view sheet projects what can be lent here, names the borrower, and its amount parses", async () => {
  server.use(
    ...investorShellHandlers(calls, {
      // A wallet of CHF 100,500.01 and a loan with CHF 10,000.00 left.
      balances: () => balancesPayload([{ currency: "CHF", investableMinor: 10_050_001 }]),
      marketplaceLoans: () => [preview]
    }),
    http.get(`*/api/v1/marketplace/primary/loans/${LOAN_ID}/`, () => HttpResponse.json(loanDetail()))
  );
  renderLiveApp(App, "/marketplace");
  fireEvent.click(await screen.findByText("Audit Direct Loan", {}, { timeout: 5000 }));
  const sheet = await screen.findByRole("dialog", { name: "Audit Direct Loan" });
  await within(sheet).findByText(/Your claim is against Audit Borrower AG/, {}, { timeout: 5000 });

  expect(within(sheet).getByText(/What your CHF 10.000\.00 does here/)).toBeInTheDocument();
  expect(within(sheet).queryByText(/100.500\.01 does here/)).not.toBeInTheDocument();
  expect(within(sheet).queryByText(/paid at maturity/)).not.toBeInTheDocument();
  expect(within(sheet).getByText(/capital and interest every month/)).toBeInTheDocument();
  expect(within(sheet).queryByText(/claim is against Audit Direct Loan/)).not.toBeInTheDocument();

  fireEvent.click(within(sheet).getByRole("button", { name: "Invest now" }));
  const amount = within(sheet).getByRole("textbox", { name: "Amount to invest" });
  expect(amount).toHaveValue("10000.00");
  // Editing the pre-filled amount works, with or without separators.
  fireEvent.change(amount, { target: { value: "9500.00" } });
  expect(within(sheet).getByText(/^CHF 9.500\.00$/)).toBeInTheDocument();
  fireEvent.change(amount, { target: { value: "9’000,50" } });
  expect(within(sheet).getByText(/^CHF 9.000\.50$/)).toBeInTheDocument();
  expect(within(sheet).getByRole("button", { name: "Review Order" })).toBeEnabled();
  fireEvent.change(amount, { target: { value: "1,000" } });
  expect(within(sheet).getByRole("alert")).toHaveTextContent(/A comma is the decimal sign/);
  expect(within(sheet).getByRole("button", { name: "Review Order" })).toBeDisabled();
}, 30_000);
