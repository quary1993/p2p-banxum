// IP of Webby-Soft SRL.
// Swiss-borrower loans: at most 20 investors (plan/09 MKT-DEC-028, 2026-10-16; U33-DEC-08 replaces it
// in Phase 17.7). Review & sign shows the minimum from the API and, for these loans, the places left
// under the amount; a new investor cannot continue when no place is left, and the server's 409 is shown.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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

async function applyAmount(amount: string) {
  const input = await screen.findByRole("textbox", { name: "Your investment amount" }, { timeout: 5000 });
  fireEvent.change(input, { target: { value: amount } });
  fireEvent.keyDown(input, { key: "Enter" });
  return input;
}

test("Review & sign shows the API minimum and the places left of a Swiss-borrower loan", async () => {
  server.use(...investorShellHandlers(calls), ...orderHandlers(swissLoan(), () => HttpResponse.json({})));
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);

  await screen.findByRole("textbox", { name: "Your investment amount" }, { timeout: 5000 });
  expect(screen.getByText("Swiss borrower: at most 20 investors. 19 places left.")).toBeInTheDocument();
  expect(screen.getByText(/Minimum CHF 4\.211,00 · CHF 80\.000,00 available in this opportunity/)).toBeInTheDocument();
  await applyAmount("4000");
  expect(await screen.findByText("The minimum investment is CHF 4.211,00.")).toBeInTheDocument();
  for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
  expect(screen.getByRole("button", { name: "Confirm investment" })).toBeDisabled();
  await applyAmount("4211");
  for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm investment" })).toBeEnabled());
}, 30_000);

test("a full Swiss-borrower loan stops a new investor; the server's 409 message is shown", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...orderHandlers(swissLoan({ places_left: 1, minimum_investment_minor: 8_000_000 }), () =>
      HttpResponse.json({ detail: FULL, code: "swiss_investor_limit" }, { status: 409 })
    )
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await applyAmount("80000");
  expect(screen.getByText("Swiss borrower: at most 20 investors. 1 place left.")).toBeInTheDocument();
  for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
  fireEvent.click(screen.getByRole("button", { name: "Confirm investment" }));
  const dialog = await screen.findByRole("dialog", { name: "Confirm your investment" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  enterPin(undefined, undefined, dialog);
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Confirm and reserve" })).toBeEnabled());
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm and reserve" }));

  expect(await within(dialog).findByText(FULL, {}, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.allocate).toHaveLength(1);
}, 30_000);

test("an investor who already invests may add to a full Swiss-borrower loan", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...orderHandlers(swissLoan({ places_left: 0, is_existing_investor: true, minimum_investment_minor: 100_000 }), () => HttpResponse.json({}))
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await screen.findByRole("textbox", { name: "Your investment amount" }, { timeout: 5000 });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByText("Swiss borrower: at most 20 investors. You already invest in this loan, so you can add to it.")).toBeInTheDocument();
}, 30_000);

test("a new investor cannot continue on a Swiss-borrower loan with no place left", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...orderHandlers(swissLoan({ places_left: 0, minimum_investment_minor: 100_000 }), () => HttpResponse.json({}))
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await screen.findByRole("textbox", { name: "Your investment amount" }, { timeout: 5000 });
  expect(screen.getByRole("alert")).toHaveTextContent(FULL);
  await applyAmount("5000");
  for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
  expect(screen.getByRole("button", { name: "Confirm investment" })).toBeDisabled();
  expect(calls.orders).toHaveLength(0);

  // The opportunity page says the same and keeps the amount step closed.
  window.history.pushState({}, "", `/marketplace/${LOAN_ID}`);
  window.dispatchEvent(new PopStateEvent("popstate"));
  await waitFor(() => expect(screen.getByText(FULL)).toBeInTheDocument(), { timeout: 5000 });
  expect(screen.getByRole("button", { name: /Review investment/ })).toBeDisabled();
}, 30_000);
