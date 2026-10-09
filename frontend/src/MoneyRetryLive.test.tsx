// Real-API retry checks for money actions (QA audit 2026-10-09, A-41 / FRONTCODE-07):
// a retry after a timeout must carry the same idempotency key, so the server answers
// with the original result instead of "code already used" or a second withdrawal.
// A network failure shows a clear message, not the browser's "Failed to fetch".
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  getV1FxQuotePreviewRetrieveResponseMock,
  getV1FxQuotesCreateResponseMock,
  getV1FxQuotesExecuteCreateResponseMock,
  getV1LedgerWithdrawalRequestsCreateResponseMock
} from "./api/generated/banxumApi";
import { NETWORK_ERROR_MESSAGE } from "./api/client/httpClient";
import { balancesPayload, emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("withdrawals", "codes", "fxExecutions");
});
afterEach(() => {
  vi.useRealTimers();
});

const verifiedIban = {
  id: "pi1",
  currency: "CHF",
  status: "active",
  destination_iban: "CH9300762011623852957",
  destination_account_name: "Una Investor",
  is_verified_usable: true,
  verified_at: "2026-10-01T00:00:00Z",
  created_at: "2026-10-01T00:00:00Z"
};

function withdrawalHandlers(results: Array<() => Response>) {
  return [
    ...investorShellHandlers(calls, { balances: () => balancesPayload([{ currency: "CHF", investableMinor: 500_000 }], [verifiedIban]) }),
    http.post("*/api/v1/ledger/withdrawal-requests/", async ({ request }) => {
      calls.withdrawals.push((await request.json()) as Record<string, unknown>);
      const next = results.shift();
      return next ? next() : HttpResponse.json(getV1LedgerWithdrawalRequestsCreateResponseMock(), { status: 201 });
    })
  ];
}

async function openWithdrawalConfirm(amount: string) {
  fireEvent.click((await screen.findAllByRole("button", { name: "Withdraw to IBAN" }, { timeout: 5000 }))[0]);
  const dialog = await screen.findByRole("dialog");
  fireEvent.change(within(dialog).getByPlaceholderText("0.00"), { target: { value: amount } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Review" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm withdrawal" })).toBeEnabled());
}

test("A-41: a withdrawal retried after a network error keeps its key and is not paid twice", async () => {
  server.use(
    ...withdrawalHandlers([
      () => HttpResponse.error(),
      // The first request was committed: the server replays it for the same key.
      () => HttpResponse.json(getV1LedgerWithdrawalRequestsCreateResponseMock(), { status: 201 })
    ])
  );
  renderLiveApp(App, "/balances");
  await openWithdrawalConfirm("100");
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findByText(NETWORK_ERROR_MESSAGE, {}, { timeout: 5000 });
  expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findAllByText("Withdrawal requested", {}, { timeout: 5000 });
  expect(calls.withdrawals).toHaveLength(2);
  expect(calls.withdrawals[1].idempotency_key).toBe(calls.withdrawals[0].idempotency_key);
  expect(calls.withdrawals[1]).toMatchObject({ amount_minor: 10_000, destination_iban: verifiedIban.destination_iban });
}, 30_000);

test("A-41: a new withdrawal amount gets a new key", async () => {
  server.use(...withdrawalHandlers([() => HttpResponse.error()]));
  renderLiveApp(App, "/balances");
  await openWithdrawalConfirm("100,50");
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findByText(NETWORK_ERROR_MESSAGE, {}, { timeout: 5000 });
  expect(calls.withdrawals[0]).toMatchObject({ amount_minor: 10_050 });

  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  fireEvent.change(within(screen.getByRole("dialog")).getByPlaceholderText("0.00"), { target: { value: "150" } });
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Review" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm withdrawal" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findAllByText("Withdrawal requested", {}, { timeout: 5000 });
  expect(calls.withdrawals[1]).toMatchObject({ amount_minor: 15_000 });
  expect(calls.withdrawals[1].idempotency_key).not.toBe(calls.withdrawals[0].idempotency_key);
}, 30_000);

test("A-41: an FX execution retried after a network error keeps the key of its quote", async () => {
  // FX is closed on Zurich weekends; run on a Wednesday.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-07T10:00:00Z"));
  const quote = {
    ...getV1FxQuotesCreateResponseMock(),
    id: "77777777-7777-4777-8777-777777777777",
    source_currency: "CHF",
    target_currency: "EUR",
    source_amount_minor: 100_000,
    target_amount_minor: 103_420,
    fee_minor: 158,
    effective_net_rate: "1.0342"
  };
  let executions = 0;
  server.use(
    ...investorShellHandlers(calls, {
      balances: () => balancesPayload([{ currency: "CHF", investableMinor: 500_000 }, { currency: "EUR", investableMinor: 0 }])
    }),
    http.get("*/api/v1/investor/portal/fx/", () => HttpResponse.json({ exchanges: [], quotes: [] })),
    http.get("*/api/v1/fx/quote-preview/", () =>
      HttpResponse.json({
        ...getV1FxQuotePreviewRetrieveResponseMock(),
        source_currency: "CHF",
        target_currency: "EUR",
        source_amount_minor: 100_000,
        target_amount_minor: 103_420,
        fee_minor: 158,
        effective_net_rate: "1.0342",
        platform_fee_bps: 150
      })
    ),
    http.post("*/api/v1/fx/quotes/", () => HttpResponse.json(quote, { status: 201 })),
    http.post("*/api/v1/fx/quotes/:quoteId/execute/", async ({ request, params }) => {
      calls.fxExecutions.push({ quoteId: params.quoteId, ...((await request.json()) as Record<string, unknown>) });
      executions += 1;
      if (executions === 1) return HttpResponse.error();
      return HttpResponse.json(getV1FxQuotesExecuteCreateResponseMock(), { status: 201 });
    })
  );
  renderLiveApp(App, "/fx");
  fireEvent.change(await screen.findByRole("textbox", { name: "Amount to convert from CHF" }, { timeout: 5000 }), { target: { value: "1000" } });
  const convert = await screen.findByRole("button", { name: "Convert" });
  await waitFor(() => expect(convert).toBeEnabled(), { timeout: 5000 });
  fireEvent.click(convert);
  const dialog = await screen.findByRole("dialog", {}, { timeout: 5000 });
  fireEvent.click(within(dialog).getByRole("checkbox"));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Confirm exchange" })).toBeEnabled());
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm exchange" }));
  await within(dialog).findByText(NETWORK_ERROR_MESSAGE, {}, { timeout: 5000 });
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm exchange" }));
  await screen.findByText("Exchange settled", {}, { timeout: 5000 });

  expect(calls.fxExecutions).toHaveLength(2);
  expect(calls.fxExecutions[0].quoteId).toBe(quote.id);
  expect(calls.fxExecutions[1].idempotency_key).toBe(calls.fxExecutions[0].idempotency_key);
}, 30_000);
