// Real-API checks of the account state (audit 2026-10-09, A-20/A-21): the day-60 frozen
// (penalty-mode) state comes from the balances API, not from the preview switch; the Account
// page shows each payout IBAN's real verification state and the open withdrawal requests.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { balances, fxSwitchedOn, lot, renderLiveApp, shellHandlers, summary } from "./test/liveHarness";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

// user1 on 10 Dec in the audit data: EUR past day 60 with no verified EUR IBAN (penalty mode),
// CHF fine, a pending EUR IBAN, one voluntary and one forced withdrawal waiting.
const frozenBalances = () =>
  balances({
    summaries: [
      summary("CHF", { total_available_minor: 1_299_630, investable_minor: 1_299_630, lot_count: 1, active_lot_count: 1 }),
      summary("EUR", {
        total_available_minor: 489_803_689,
        penalty_mode_minor: 489_803_689,
        penalty_charged_minor: 9_995_994,
        lot_count: 1,
        active_lot_count: 1
      })
    ],
    lots: [
      lot({ id: "lot-chf", currency: "CHF", available_amount_minor: 1_299_630, original_amount_minor: 1_299_630 }),
      lot({
        id: "lot-eur",
        currency: "EUR",
        status: "penalty_mode",
        bucket: "penalty_mode",
        days_until_withdrawal_deadline: -10,
        last_day: "2026-11-28",
        return_date: "2026-11-29",
        days_until_last_day: -12,
        available_amount_minor: 489_803_689,
        original_amount_minor: 500_000_000,
        penalized_amount_minor: 9_995_994,
        requires_withdrawal: true,
        blocks_financial_actions: true
      })
    ],
    payout_instructions: [
      {
        id: "pi-chf",
        currency: "CHF",
        status: "active",
        destination_iban: "CH5604835012345678009",
        destination_account_name: "Una Investor",
        is_verified_usable: true,
        verified_at: "2026-10-09T12:00:00Z",
        created_at: "2026-10-09T11:00:00Z"
      },
      {
        id: "pi-eur",
        currency: "EUR",
        status: "active",
        destination_iban: "DE89370400440532013000",
        destination_account_name: "Una Investor",
        is_verified_usable: false,
        verified_at: null,
        created_at: "2026-10-09T11:00:00Z"
      }
    ],
    pending_withdrawals: [
      {
        id: "wd-1",
        currency: "CHF",
        amount_minor: 150_050,
        destination_iban: "CH5604835012345678009",
        destination_account_name: "Una Investor",
        requested_at: "2026-10-09T12:30:00Z",
        is_forced: false
      },
      {
        id: "wd-2",
        currency: "CHF",
        amount_minor: 472_819_950,
        destination_iban: "CH5604835012345678009",
        destination_account_name: "Una Investor",
        requested_at: "2026-12-09T11:00:00Z",
        is_forced: true
      }
    ],
    has_penalty_mode_balance: true,
    penalty_bps_per_day: 100
  });

test("the frozen state from the balances API shows a banner, counts frozen money and blocks FX", async () => {
  server.use(fxSwitchedOn(), ...shellHandlers({ balances: frozenBalances }));
  renderLiveApp(App, "/dashboard");

  const banner = await screen.findByText("Financial actions are frozen", {}, { timeout: 5000 });
  const bannerBox = banner.closest(".alert") as HTMLElement;
  expect(bannerBox).toHaveTextContent("EUR 4.898.036,89 passed the 60-day holding limit");
  expect(bannerBox).toHaveTextContent("A penalty of 1,0% of this money is taken every day");
  expect(bannerBox).toHaveTextContent("add a bank account in your name for EUR");
  expect(within(bannerBox).getByRole("button", { name: "Add a bank account" })).toBeInTheDocument();
  // The nav marks the Account entry; Add funds (account menu) is disabled.
  expect(screen.getByLabelText("Account frozen")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Account menu" }));
  expect(screen.getByRole("button", { name: "Add funds" })).toHaveAttribute("aria-disabled", "true");
  // The raw lot status never reaches the page.
  expect(document.body.textContent).not.toMatch(/penalty_mode|PENALTY_MODE/);

  // Overview: the EUR available balance names the frozen part (penalty mode until U33-DEC-04).
  fireEvent.click(await screen.findByRole("button", { name: "EUR" }));
  expect(await screen.findByText("Of which EUR 4.898.036,89 is frozen, with a daily penalty.")).toBeInTheDocument();

  // FX: the converter is blocked with the reason before any quote is requested.
  server.use(
    ...shellHandlers({ balances: frozenBalances })
  );
  window.history.pushState({}, "", "/fx");
  window.dispatchEvent(new PopStateEvent("popstate"));
  expect(await screen.findByText("FX is frozen", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByLabelText("Amount to convert from CHF")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Convert" })).toBeDisabled();
}, 30_000);

test("Account shows each IBAN's real state, pending withdrawals with forced returns, and the withdraw maximum", async () => {
  server.use(
    ...shellHandlers({
      balances: () => {
        const payload = frozenBalances();
        // A "frozen" status lot is never released for withdrawals: CHF 100.00 of the CHF balance.
        payload.summaries[0] = { ...payload.summaries[0], frozen_minor: 10_000 };
        return payload;
      }
    }),
    http.get("*/api/v1/investor/portal/primary-orders/", () => HttpResponse.json({ orders: [] }))
  );
  renderLiveApp(App, "/balances");

  // Withdrawals waiting for the bank transfer: on the CHF card and listed in Balance details, the
  // automatic return labelled as such.
  const chf = await screen.findByRole("region", { name: "CHF account" }, { timeout: 5000 });
  expect(within(chf).getByText("Withdrawals in progress")).toBeInTheDocument();
  expect(within(chf).getByText("CHF 4.729.700,00")).toBeInTheDocument();
  const pending = within(screen.getByRole("list", { name: "Withdrawals in progress" }));
  expect(pending.getByText("CHF 1.500,50")).toBeInTheDocument();
  expect(pending.getByText("CHF 4.728.199,50")).toBeInTheDocument();
  expect(pending.getAllByText(/^Automatic return to /)).toHaveLength(1);
  expect(pending.getAllByText(/^Withdrawal to /)).toHaveLength(1);

  // Lot status is readable; the penalty already charged is listed apart from the balance.
  const details = screen.getByText("Balance details").closest("details") as HTMLElement;
  expect(within(details).getByText("Frozen, penalty charged")).toBeInTheDocument();
  expect(within(details).getByText(/^Penalty charged so far: EUR 99\.959,94\./)).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/penalty_mode|PENALTY_MODE/);

  // EUR has only a pending IBAN: the Withdraw dialog says so and shows its real state (U33-DEC-05).
  fireEvent.click(within(screen.getByRole("region", { name: "EUR account" })).getByRole("button", { name: "Withdraw" }));
  const eurDialog = await screen.findByRole("dialog", { name: "Withdraw" });
  expect(within(eurDialog).getByText("No verified EUR bank account yet")).toBeInTheDocument();
  expect(within(eurDialog).getByText("DE89 3704 0044 0532 0130 00 · Pending verification")).toBeInTheDocument();
  expect(within(eurDialog).queryByText("Verified bank account")).not.toBeInTheDocument();
  expect(within(eurDialog).getByRole("button", { name: /Continue/ })).toBeDisabled();
  expect(within(eurDialog).getByRole("link", { name: "Add a bank account" })).toBeInTheDocument();

  // CHF: the verified account, and the withdraw maximum is everything except the "frozen" lot.
  fireEvent.click(within(eurDialog).getByRole("button", { name: "CHF" }));
  expect(within(eurDialog).getByText("Available CHF 12.896,30")).toBeInTheDocument();
  expect(within(eurDialog).getByText("CH56 0483 5012 3456 7800 9")).toBeInTheDocument();
  expect(within(eurDialog).getByText("Verified bank account")).toBeInTheDocument();
  await waitFor(() => expect(eurDialog.contains(document.activeElement)).toBe(true));

  // Without a verified EUR account, "Add a bank account" opens the EUR bank-account dialog.
  fireEvent.click(within(eurDialog).getByRole("button", { name: "EUR" }));
  fireEvent.click(within(eurDialog).getByRole("link", { name: "Add a bank account" }));
  expect(await screen.findByRole("dialog", { name: "New EUR bank account" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "Withdraw" })).not.toBeInTheDocument();
}, 30_000);
