// IP of Webby-Soft SRL.
// Swiss-borrower loans: at most 20 investors (plan/09 MKT-DEC-028, 2026-10-16). The invest
// page shows the minimum from the API and, for these loans, the places left under the amount;
// a new investor cannot continue when no place is left, and the server's 409 is shown.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  getV1DocumentsAcceptancesCreateResponseMock,
  getV1DocumentsTemplatesCurrentRetrieveResponseMock,
  getV1MarketplacePrimaryLoansRetrieveResponseMock,
  getV1MarketplacePrimaryOrdersCreateResponseMock
} from "./api/generated/banxumApi";
import { SwissInvestorLimitNote } from "./investorPortal/SwissInvestorLimitNote";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";
import { enterPin } from "./test/pin";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

const LOAN_ID = "33333333-3333-4333-8333-333333333333";
const FULL = "This loan to a Swiss company already has the maximum of 20 investors.";
let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("orders", "acceptances", "allocate", "codes");
});

function swissLoan(overrides: Record<string, unknown> = {}) {
  return {
    ...getV1MarketplacePrimaryLoansRetrieveResponseMock(),
    loan_id: LOAN_ID,
    product_type: "direct",
    investment_flow: "primary_order",
    distribution_model: "",
    title: "Swiss Bridge Loan",
    purpose: "working_capital",
    collateral_type: "real_estate",
    interest_rate_bps: 800,
    yield_bps: 800,
    underlying_interest_rate_bps: 800,
    term_months: 12,
    remaining_term_days: null,
    risk_rating: "A",
    funding_deadline: "2026-10-20",
    maturity_date: null,
    status: "published",
    loan_status: "published",
    opportunity_status: "open",
    currency: "CHF",
    principal_minor: 10_000_000,
    committed_principal_minor: 2_000_000,
    remaining_capacity_minor: 8_000_000,
    fillable_amount_minor: 8_000_000,
    // 80,000.00 left over 19 places: 4,210.53, rounded up by the server.
    minimum_investment_minor: 421_100,
    max_investors: 20,
    places_left: 19,
    is_existing_investor: false,
    ltv_bps: 5000,
    is_refinancing: false,
    originator_id: null,
    originator_name: null,
    borrower_display_name: null,
    borrower_disclosure: { legal_name: "Swiss AG" },
    story: { version: 1, blocks: [] },
    loan_schedule: [],
    originator_schedule: [],
    collateral_value_minor: 20_000_000,
    repayment_type: "equal_installments",
    ...overrides
  };
}

function orderHandlers(loan: Record<string, unknown>, allocate: () => Response) {
  return [
    http.get(`*/api/v1/marketplace/primary/loans/${LOAN_ID}/`, () => HttpResponse.json(loan)),
    http.get("*/api/v1/documents/templates/current/", () =>
      HttpResponse.json({
        ...getV1DocumentsTemplatesCurrentRetrieveResponseMock(),
        id: "tpl-1",
        title: "Investment terms",
        version_number: 3,
        checkbox_labels: ["I accept the investment terms."]
      })
    ),
    http.post("*/api/v1/marketplace/primary/orders/", async ({ request }) => {
      const body = (await request.json()) as { amount_minor: number };
      calls.orders.push(body);
      return HttpResponse.json(
        { ...getV1MarketplacePrimaryOrdersCreateResponseMock(), id: "order-1", status: "pending", requested_amount_minor: body.amount_minor, allocated_amount_minor: 0, closed_reason: "" },
        { status: 201 }
      );
    }),
    http.post("*/api/v1/documents/acceptances/", async ({ request }) => {
      calls.acceptances.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ ...getV1DocumentsAcceptancesCreateResponseMock(), id: "acc-1" }, { status: 201 });
    }),
    http.post("*/api/v1/marketplace/primary/orders/:orderId/allocate-balance/", async ({ request }) => {
      calls.allocate.push((await request.json()) as Record<string, unknown>);
      return allocate();
    })
  ];
}

test("the invest page shows the API minimum and the places left of a Swiss-borrower loan", async () => {
  server.use(...investorShellHandlers(calls), ...orderHandlers(swissLoan(), () => HttpResponse.json({})));
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);

  const amountInput = await screen.findByRole("textbox", { name: "Investment amount" }, { timeout: 5000 });
  expect(screen.getByText("Swiss borrower: at most 20 investors. 19 places left.")).toBeInTheDocument();
  expect(screen.getByText(/Between CHF 4.211\.00 and/)).toBeInTheDocument();
  fireEvent.change(amountInput, { target: { value: "4000" } });
  expect(await screen.findByText(/Minimum order is CHF 4.211\.00\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Review order" })).toBeDisabled();
  fireEvent.change(amountInput, { target: { value: "4211" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Review order" })).toBeEnabled());
}, 30_000);

test("a full Swiss-borrower loan stops a new investor; the server's 409 message is shown", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...orderHandlers(swissLoan({ places_left: 1, minimum_investment_minor: 8_000_000 }), () =>
      HttpResponse.json({ detail: FULL, code: "swiss_investor_limit" }, { status: 409 })
    )
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  const amountInput = await screen.findByRole("textbox", { name: "Investment amount" }, { timeout: 5000 });
  expect(screen.getByText("Swiss borrower: at most 20 investors. 1 place left.")).toBeInTheDocument();
  fireEvent.change(amountInput, { target: { value: "80000" } });
  fireEvent.click(screen.getByRole("button", { name: "Review order" }));
  for (const box of await screen.findAllByRole("checkbox")) fireEvent.click(box);
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  enterPin();
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm order" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm order" }));

  expect(await screen.findByText(FULL, {}, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.allocate).toHaveLength(1);
}, 30_000);

test("the note names the full state for a new investor and lets an existing investor add", () => {
  const { rerender } = render(<SwissInvestorLimitNote loan={{ max_investors: 20, places_left: 0, is_existing_investor: false }} />);
  expect(screen.getByRole("alert")).toHaveTextContent(FULL);

  rerender(<SwissInvestorLimitNote loan={{ max_investors: 20, places_left: 0, is_existing_investor: true }} />);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(
    screen.getByText("Swiss borrower: at most 20 investors. No places left for new investors. You already invest in this loan, so you can add to it.")
  ).toBeInTheDocument();

  rerender(<SwissInvestorLimitNote loan={{ max_investors: null, places_left: null, is_existing_investor: null }} />);
  expect(screen.queryByText(/Swiss borrower/)).not.toBeInTheDocument();
});

test("a new investor cannot continue on a Swiss-borrower loan with no place left", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...orderHandlers(swissLoan({ places_left: 0, minimum_investment_minor: 100_000 }), () => HttpResponse.json({}))
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  const amountInput = await screen.findByRole("textbox", { name: "Investment amount" }, { timeout: 5000 });
  expect(screen.getByRole("alert")).toHaveTextContent(FULL);
  fireEvent.change(amountInput, { target: { value: "5000" } });
  expect(screen.getByRole("button", { name: "Review order" })).toBeDisabled();
  expect(calls.orders).toHaveLength(0);
}, 30_000);
