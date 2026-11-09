// Real-API invest page checks (QA audit 2026-10-09): A-15 (a changed amount after a
// failed confirm must not commit the old order), A-33 / SECONDARY-06 (show what the
// server allocated), A-40 (decimal comma), A-37 (legacy claim after Reprice) and
// FRONTCODE-24 (closed loan / read-only view).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  getOriginatorClaimsLoansQuoteCreateResponseMock,
  getOriginatorClaimsQuotesPurchaseCreateResponseMock,
  getV1DocumentsAcceptancesCreateResponseMock,
  getV1DocumentsTemplatesCurrentRetrieveResponseMock,
  getV1MarketplacePrimaryLoansRetrieveResponseMock,
  getV1MarketplacePrimaryOrdersCreateResponseMock
} from "./api/generated/banxumApi";
import { writeReadonlyImpersonation } from "./api/client/impersonation";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";
import { enterPin } from "./test/pin";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

const LOAN_ID = "11111111-1111-4111-8111-111111111111";
let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("orders", "acceptances", "allocate", "codes", "quotes", "purchases");
});

function directLoan(overrides: Record<string, unknown> = {}) {
  return {
    ...getV1MarketplacePrimaryLoansRetrieveResponseMock(),
    loan_id: LOAN_ID,
    product_type: "direct_loan",
    investment_flow: "primary_order",
    distribution_model: "",
    title: "Audit Direct Loan",
    purpose: "working_capital",
    collateral_type: "real_estate",
    interest_rate_bps: 800,
    yield_bps: 800,
    underlying_interest_rate_bps: 800,
    term_months: 12,
    remaining_term_days: null,
    funding_deadline: "2026-10-20",
    maturity_date: null,
    status: "published",
    loan_status: "published",
    opportunity_status: "open",
    currency: "CHF",
    principal_minor: 10_000_000,
    committed_principal_minor: 0,
    remaining_capacity_minor: 10_000_000,
    fillable_amount_minor: 10_000_000,
    minimum_investment_minor: 100_000,
    // Not a Swiss-borrower loan: the generated mock fills these at random, which sometimes made the
    // loan "full" for the viewer and blocked the amount (flaky tests).
    max_investors: null,
    places_left: null,
    is_existing_investor: false,
    ltv_bps: 5000,
    is_refinancing: false,
    originator_id: null,
    originator_name: null,
    borrower_display_name: null,
    borrower_disclosure: { legal_name: "Audit AG" },
    story: { version: 1, blocks: [] },
    loan_schedule: [],
    originator_schedule: [],
    collateral_value_minor: 20_000_000,
    repayment_type: "equal_installments",
    ...overrides
  };
}

type OrderRecord = { id: string; amount: number; key: string };

/** Primary order API with a server-side order store; `allocate` decides each result. */
function primaryOrderHandlers(
  loan: Record<string, unknown>,
  allocate: (order: OrderRecord, attempt: number) => Response | Record<string, unknown>
) {
  const orders: OrderRecord[] = [];
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
      const body = (await request.json()) as { amount_minor: number; idempotency_key: string };
      calls.orders.push(body);
      const existing = orders.find((order) => order.key === body.idempotency_key);
      const order = existing ?? { id: `order-${orders.length + 1}`, amount: body.amount_minor, key: body.idempotency_key };
      if (!existing) orders.push(order);
      return HttpResponse.json(
        { ...getV1MarketplacePrimaryOrdersCreateResponseMock(), id: order.id, status: "pending", requested_amount_minor: order.amount, allocated_amount_minor: 0, closed_reason: "" },
        { status: 201 }
      );
    }),
    http.post("*/api/v1/documents/acceptances/", async ({ request }) => {
      calls.acceptances.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ ...getV1DocumentsAcceptancesCreateResponseMock(), id: `acc-${calls.acceptances.length}` }, { status: 201 });
    }),
    http.post("*/api/v1/marketplace/primary/orders/:orderId/allocate-balance/", async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.allocate.push({ orderId: params.orderId, ...body });
      const order = orders.find((item) => item.id === params.orderId) as OrderRecord;
      const result = allocate(order, calls.allocate.length);
      if (result instanceof Response) return result;
      return HttpResponse.json({
        ...getV1MarketplacePrimaryOrdersCreateResponseMock(),
        id: order.id,
        requested_amount_minor: order.amount,
        currency: "CHF",
        closed_reason: "",
        ...result
      });
    })
  ];
}

/** Review & sign: the amount is edited in place and applied with Enter. */
// Waits for data from the mock server; a full parallel test run on a small machine is slow (each test allows 30 s).
const SERVER_WAIT = { timeout: 15_000 };

async function applyAmount(amount: string) {
  // The amount is checked against the balances: wait until they are loaded (the header shows them).
  await screen.findByRole("group", { name: "Available balance" }, SERVER_WAIT);
  const input = await screen.findByRole("textbox", { name: "Your investment amount" }, SERVER_WAIT);
  fireEvent.change(input, { target: { value: amount } });
  fireEvent.keyDown(input, { key: "Enter" });
  return input as HTMLInputElement;
}

function acceptBoth() {
  for (const box of screen.getAllByRole("checkbox") as HTMLInputElement[]) if (!box.checked) fireEvent.click(box);
}

/** The confirmation dialog: email code and PIN (ACC-DEC-009), then the confirm button. */
async function confirmInDialog(code: string, dialogName = "Confirm your investment", confirmName = "Confirm and reserve") {
  const dialog = await screen.findByRole("dialog", { name: dialogName }, SERVER_WAIT);
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: code } });
  enterPin(undefined, undefined, dialog);
  await waitFor(() => expect(within(dialog).getByRole("button", { name: confirmName })).toBeEnabled(), SERVER_WAIT);
  fireEvent.click(within(dialog).getByRole("button", { name: confirmName }));
  return dialog;
}

/** Confirm investment is enabled once the amount is valid (minimum, capacity, balance: data from the mock server) and both acceptances are given. */
async function clickConfirmInvestment() {
  const button = screen.getByRole("button", { name: "Confirm investment" });
  await waitFor(() => expect(button).toBeEnabled(), SERVER_WAIT);
  fireEvent.click(button);
}

async function reviewAndConfirm(amount: string, code: string) {
  await applyAmount(amount);
  acceptBoth();
  await clickConfirmInvestment();
  return confirmInDialog(code);
}

test("A-15: a new amount after a failed confirm places a new order with new evidence and keys", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...primaryOrderHandlers(directLoan(), (order, attempt) =>
      attempt === 1
        ? HttpResponse.json({ detail: "Invalid or expired confirmation code." }, { status: 400 })
        : { status: "balance_allocated", allocated_amount_minor: order.amount, allocated_at: "2026-06-05T08:30:00Z" }
    )
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);

  const firstDialog = await reviewAndConfirm("1000", "111111");
  await within(firstDialog).findByText("Invalid or expired confirmation code.", {}, { timeout: 5000 });
  expect(calls.codes).toHaveLength(1);

  // Close the confirmation, change the amount on the page (the acceptances are cleared), confirm again.
  fireEvent.click(within(firstDialog).getByRole("button", { name: "Cancel" }));
  await applyAmount("2000");
  (screen.getAllByRole("checkbox") as HTMLInputElement[]).forEach((box) => expect(box).not.toBeChecked());
  expect(screen.getByRole("button", { name: "Confirm investment" })).toBeDisabled();
  acceptBoth();
  await clickConfirmInvestment();
  await confirmInDialog("222222");
  await screen.findByRole("heading", { name: "Investment reserved" }, { timeout: 5000 });
  // The receipt shows the server's order reference and allocation time, not the browser clock.
  expect(document.querySelector(".l8-reference")).toHaveTextContent("ORDER-2 · 5 Jun 2026");

  expect(calls.orders.map((order) => order.amount_minor)).toEqual([100_000, 200_000]);
  expect(calls.orders[1].idempotency_key).not.toBe(calls.orders[0].idempotency_key);
  expect(calls.acceptances).toHaveLength(2);
  expect(calls.acceptances[1]).toMatchObject({ context_id: "order-2", data_snapshot: { amount_minor: 200_000 } });
  expect(calls.acceptances[1].idempotency_key).not.toBe(calls.acceptances[0].idempotency_key);
  expect(calls.allocate.map((call) => call.orderId)).toEqual(["order-1", "order-2"]);
  expect(calls.allocate[1]).toMatchObject({ document_acceptance_id: "acc-2" });
  expect(calls.allocate[1].idempotency_key).not.toBe(calls.allocate[0].idempotency_key);
  // The result shows the server's order.
  expect(screen.getByText("Amount reserved").parentElement).toHaveTextContent(/CHF\s*2\.000,00/);
  expect(screen.getByText(/CHF 2\.000,00 of your balance is reserved for this loan/)).toBeInTheDocument();
  expect(screen.queryByText(/pending allocation/)).not.toBeInTheDocument();
}, 30_000);

test("A-15: a retry of the same amount reuses the same order, acceptance and keys", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...primaryOrderHandlers(directLoan(), (order, attempt) =>
      attempt === 1
        ? HttpResponse.json({ detail: "Invalid or expired confirmation code." }, { status: 400 })
        : { status: "balance_allocated", allocated_amount_minor: order.amount }
    )
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  const dialog = await reviewAndConfirm("1000", "111111");
  await within(dialog).findByText("Invalid or expired confirmation code.", {}, { timeout: 5000 });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "222222" } });
  enterPin(undefined, undefined, dialog);
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm and reserve" }));
  await screen.findByRole("heading", { name: "Investment reserved" }, { timeout: 5000 });

  expect(calls.orders).toHaveLength(1);
  expect(calls.acceptances).toHaveLength(1);
  expect(calls.allocate.map((call) => call.idempotency_key)).toEqual([calls.allocate[0].idempotency_key, calls.allocate[0].idempotency_key]);
}, 30_000);

test("A-33: the done screen says when only part of the amount, or nothing, was invested", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...primaryOrderHandlers(directLoan(), () => ({ status: "partially_allocated", allocated_amount_minor: 150_000 }))
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await reviewAndConfirm("5000", "111111");
  await screen.findByRole("heading", { name: "Investment partly reserved" }, { timeout: 5000 });
  expect(screen.getByText(/Only CHF 1\.500,00 was left in this loan\. We reserved CHF 1\.500,00 of the CHF 5\.000,00 you asked for\./)).toBeInTheDocument();
  expect(screen.getByText("Amount reserved").parentElement).toHaveTextContent(/CHF\s*1\.500,00/);
  expect(screen.queryByRole("heading", { name: "Investment reserved" })).not.toBeInTheDocument();
}, 30_000);

test("A-33: an order closed below the minimum is shown as not placed, with no money moved", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...primaryOrderHandlers(directLoan(), () => ({
      status: "closed_not_invested",
      allocated_amount_minor: 0,
      closed_reason: "Remaining loan capacity was below the minimum order."
    }))
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await reviewAndConfirm("5000", "111111");
  await screen.findByRole("heading", { name: "Investment not placed" }, { timeout: 5000 });
  expect(screen.getByText(/Less than the minimum order of CHF 1\.000,00 was left in this loan\. Nothing was invested and no money moved\./)).toBeInTheDocument();
  expect(screen.getByText("Amount invested").parentElement).toHaveTextContent(/CHF\s*0,00/);
  expect(screen.queryByText(/accepted terms in Documents/)).not.toBeInTheDocument();
}, 30_000);

test("SECONDARY-09: an order the server closed is replaced by a new order on the next confirm", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...primaryOrderHandlers(directLoan(), (order, attempt) =>
      attempt === 1
        ? HttpResponse.json(
            { detail: "This order was closed before it was confirmed. Nothing was invested. Place the order again.", code: "order_not_pending" },
            { status: 400 }
          )
        : { status: "balance_allocated", allocated_amount_minor: order.amount }
    )
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  const dialog = await reviewAndConfirm("1000", "111111");
  await within(dialog).findByText(/This order was closed before it was confirmed/, {}, { timeout: 5000 });
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm and reserve" }));
  await screen.findByRole("heading", { name: "Investment reserved" }, { timeout: 5000 });
  expect(calls.orders).toHaveLength(2);
  expect(calls.orders[1].idempotency_key).not.toBe(calls.orders[0].idempotency_key);
  expect(calls.allocate.map((call) => call.orderId)).toEqual(["order-1", "order-2"]);
}, 30_000);

test("A-40: the amount field reads the decimal comma and explains an ambiguous comma", async () => {
  server.use(...investorShellHandlers(calls), ...primaryOrderHandlers(directLoan(), () => ({})));
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);

  // The first entry has no amount: nothing is pre-filled (U33-DEC-08), confirming waits for one.
  const amountInput = await applyAmount("1500,50");
  expect(amountInput).toHaveValue("1.500,50");
  acceptBoth();
  expect(screen.getByRole("button", { name: "Confirm investment" })).toBeEnabled();

  // Another amount clears the acceptances; the Swiss way of writing it is read as well.
  await applyAmount("2’500.00");
  expect(amountInput).toHaveValue("2.500,00");
  expect(screen.getByRole("button", { name: "Confirm investment" })).toBeDisabled();
  acceptBoth();

  // European format (U33-DEC-32): 1,000 is one with three decimals, refused with a hint, not guessed.
  await applyAmount("1,000");
  expect(screen.getByText(/CHF amounts support at most 2 decimal places\. Write thousands as 1\.000\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirm investment" })).toBeDisabled();
  // Escape restores the applied amount.
  fireEvent.keyDown(amountInput, { key: "Escape" });
  expect(amountInput).toHaveValue("2.500,00");
  expect(screen.queryByText(/Write thousands as 1\.000\./)).not.toBeInTheDocument();
}, 30_000);

test("FRONTCODE-24: a closed loan shows a notice and sends no email code", async () => {
  server.use(
    ...investorShellHandlers(calls),
    ...primaryOrderHandlers(directLoan({ status: "funded", loan_status: "funded", opportunity_status: "closed", remaining_capacity_minor: 0, fillable_amount_minor: 0 }), () => ({}))
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await screen.findByText("This loan is not open for investment.", {}, { timeout: 5000 });
  expect(screen.queryByRole("textbox", { name: "Your investment amount" })).not.toBeInTheDocument();
  expect(calls.codes).toHaveLength(0);
}, 30_000);

test("FRONTCODE-24: the read-only investor view cannot start an investment", async () => {
  writeReadonlyImpersonation("readonly-token", "Una Investor");
  server.use(...investorShellHandlers(calls), ...primaryOrderHandlers(directLoan(), () => ({})));
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await screen.findByText(/You can see the loan, but you cannot invest\./, {}, { timeout: 5000 });
  expect(screen.queryByRole("textbox", { name: "Your investment amount" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm investment" })).not.toBeInTheDocument();
  expect(calls.codes).toHaveLength(0);
  expect(calls.orders).toHaveLength(0);
}, 30_000);

test("A-37: a legacy claim purchase after Reprice uses a new acceptance and key for the new quote", async () => {
  const quotes: string[] = [];
  const claimLoan = directLoan({
    product_type: "originator_claim",
    investment_flow: "immediate_claim_assignment",
    distribution_model: "legacy_yield_v1",
    title: "Audit LO claim",
    interest_rate_bps: 900,
    underlying_interest_rate_bps: 900,
    term_months: 10,
    remaining_term_days: 300,
    funding_deadline: null,
    maturity_date: "2027-08-01",
    status: "open",
    loan_status: "active",
    principal_minor: 5_000_000,
    remaining_capacity_minor: 5_000_000,
    fillable_amount_minor: 5_100_000,
    ltv_bps: null,
    originator_id: "o1",
    originator_name: "Audit LO",
    borrower_display_name: "Final Borrower"
  });
  server.use(
    ...investorShellHandlers(calls),
    ...primaryOrderHandlers(claimLoan, () => ({})),
    http.post("*/api/v1/originator-claims/loans/:loanId/quote/", async ({ request }) => {
      const body = (await request.json()) as { requested_cash_minor: number };
      const id = `33333333-3333-4333-8333-00000000000${quotes.length + 1}`;
      quotes.push(id);
      return HttpResponse.json({
        ...getOriginatorClaimsLoansQuoteCreateResponseMock(),
        quote_id: id,
        loan_id: LOAN_ID,
        currency: "CHF",
        requested_cash_minor: body.requested_cash_minor,
        executable_cash_minor: body.requested_cash_minor,
        assigned_principal_minor: body.requested_cash_minor - 100,
        premium_discount_minor: 100,
        target_yield_bps: 800,
        entitlement_start_at: "2026-10-09T11:47:00Z",
        expires_at: "2026-10-09T11:52:00Z",
        cash_flows: []
      });
    }),
    http.post("*/api/v1/originator-claims/quotes/:quoteId/purchase/", async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.purchases.push({ quoteId: params.quoteId, ...body });
      if (calls.purchases.length === 1) return HttpResponse.json({ detail: "Originator claim quote has expired." }, { status: 400 });
      // The server binds the acceptance to its quote.
      const acceptance = calls.acceptances.find((_, index) => `acc-${index + 1}` === body.document_acceptance_id);
      if (!acceptance || acceptance.context_id !== params.quoteId) {
        return HttpResponse.json({ detail: "Document acceptance does not match this quote." }, { status: 400 });
      }
      return HttpResponse.json(
        {
          ...getOriginatorClaimsQuotesPurchaseCreateResponseMock(),
          quote_id: String(params.quoteId),
          purchase_id: "77777777-7777-4777-8777-777777777777",
          purchased_at: "2026-06-05T08:30:00Z",
          cash_consideration_minor: 100_000
        },
        { status: 201 }
      );
    })
  );
  renderLiveApp(App, `/marketplace/${LOAN_ID}/invest`);
  await applyAmount("1000");
  fireEvent.click(screen.getByRole("button", { name: "Get executable quote" }));
  await screen.findByText("Cash price", {}, { timeout: 5000 });
  acceptBoth();
  fireEvent.click(screen.getByRole("button", { name: "Confirm purchase" }));
  const dialog = await confirmInDialog("111111", "Confirm your claim purchase", "Purchase claim");
  await within(dialog).findByText("Originator claim quote has expired.", {}, { timeout: 5000 });

  // Reprice, as the message suggests: a new quote, accepted again.
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Reprice" }));
  fireEvent.click(await screen.findByRole("button", { name: "Get executable quote" }));
  await waitFor(() => expect(quotes).toHaveLength(2));
  await screen.findByText("Cash price", {}, { timeout: 5000 });
  const boxes = screen.getAllByRole("checkbox");
  boxes.forEach((box) => expect(box).not.toBeChecked());
  boxes.forEach((box) => fireEvent.click(box));
  fireEvent.click(screen.getByRole("button", { name: "Confirm purchase" }));
  await confirmInDialog("222222", "Confirm your claim purchase", "Purchase claim");
  await screen.findAllByText("Claim purchased", {}, { timeout: 5000 });
  // The receipt shows the purchase as the server booked it.
  expect(document.querySelector(".l8-reference")).toHaveTextContent(/^77777777 · 5 Jun 2026/);

  expect(calls.acceptances.map((acceptance) => acceptance.context_id)).toEqual(quotes);
  expect(calls.acceptances[1].idempotency_key).not.toBe(calls.acceptances[0].idempotency_key);
  expect(calls.purchases.map((purchase) => purchase.quoteId)).toEqual(quotes);
  expect(calls.purchases[1]).toMatchObject({ document_acceptance_id: "acc-2" });
  expect(calls.purchases[1].idempotency_key).not.toBe(calls.purchases[0].idempotency_key);
}, 30_000);
