// Real-API retry checks for money actions (QA audit 2026-10-09, A-41 / FRONTCODE-07):
// a retry after a timeout must carry the same idempotency key, so the server answers
// with the original result instead of "code already used" or a second withdrawal.
// A network failure shows a clear message, not the browser's "Failed to fetch".
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1LedgerWithdrawalRequestsCreateResponseMock } from "./api/generated/banxumApi";
import { NETWORK_ERROR_MESSAGE } from "./api/client/httpClient";
import { balancesPayload, emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";
import { enterPin } from "./test/pin";

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
  const card = await screen.findByRole("region", { name: "CHF account" }, { timeout: 5000 });
  fireEvent.click(within(card).getByRole("button", { name: "Withdraw" }));
  const dialog = await screen.findByRole("dialog", { name: "Withdraw" });
  fireEvent.change(within(dialog).getByLabelText("Amount to withdraw"), { target: { value: amount } });
  fireEvent.click(within(dialog).getByRole("button", { name: /Continue/ }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  enterPin();
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
  fireEvent.change(within(screen.getByRole("dialog", { name: "Withdraw" })).getByLabelText("Amount to withdraw"), { target: { value: "150" } });
  fireEvent.click(within(screen.getByRole("dialog", { name: "Withdraw" })).getByRole("button", { name: /Continue/ }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm withdrawal" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findAllByText("Withdrawal requested", {}, { timeout: 5000 });
  expect(calls.withdrawals[1]).toMatchObject({ amount_minor: 15_000 });
  expect(calls.withdrawals[1].idempotency_key).not.toBe(calls.withdrawals[0].idempotency_key);
}, 30_000);
