// Real-API checks of the account state (audit 2026-10-09, A-20/A-21): the day-60 frozen
// (penalty-mode) state comes from the balances API, not from the preview switch; the Account
// page shows each payout IBAN's real verification state and the open withdrawal requests.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { balances, lot, renderLiveApp, shellHandlers, summary } from "./test/liveHarness";

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
  server.use(...shellHandlers({ balances: frozenBalances }));
  renderLiveApp(App, "/dashboard");

  const banner = await screen.findByText("Financial actions are frozen", {}, { timeout: 5000 });
  const bannerBox = banner.closest(".banner") as HTMLElement;
  expect(bannerBox).toHaveTextContent("EUR 4'898'036.89 passed the 60-day holding limit");
  expect(bannerBox).toHaveTextContent("A penalty of 1.0% of this money is taken every day");
  expect(bannerBox).toHaveTextContent("add a payout IBAN for EUR");
  expect(within(bannerBox).getByRole("button", { name: "Add payout IBAN" })).toBeInTheDocument();
  // The nav marks the Account entry; Add Funds is disabled.
  expect(screen.getByLabelText("Account frozen")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add Funds" })).toBeDisabled();
  // The raw lot status never reaches the page.
  expect(document.body.textContent).not.toMatch(/penalty_mode|PENALTY_MODE/);

  // Overview: EUR money not working includes the frozen balance.
  fireEvent.click(await screen.findByRole("tab", { name: "EUR" }));
  expect(await screen.findByText("of which EUR 4'898'036.89 frozen, with a daily penalty")).toBeInTheDocument();
  expect(screen.getByText("100.0% of your money, earning nothing")).toBeInTheDocument();

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
    })
  );
  renderLiveApp(App, "/balances");

  const ibanCard = (await screen.findByRole("heading", { name: "Payout IBANs" }, { timeout: 5000 })).closest("section") as HTMLElement;
  const chfRow = within(ibanCard).getByText("CH5604835012345678009").closest(".acct-row") as HTMLElement;
  const eurRow = within(ibanCard).getByText("DE89370400440532013000").closest(".acct-row") as HTMLElement;
  expect(within(chfRow).getByText("Verified")).toBeInTheDocument();
  expect(within(eurRow).getByText("Pending verification")).toBeInTheDocument();
  expect(within(eurRow).queryByText("Verified")).not.toBeInTheDocument();

  const pending = within(screen.getByRole("list", { name: "Pending withdrawals" }));
  expect(pending.getByText("CHF 1'500.50")).toBeInTheDocument();
  expect(pending.getByText("CHF 4'728'199.50")).toBeInTheDocument();
  expect(pending.getAllByText("Forced return")).toHaveLength(1);
  expect(screen.queryByText("No pending withdrawals")).not.toBeInTheDocument();

  // EUR has no verified IBAN: the card says so next to its Withdraw button.
  expect(screen.getByText(/No verified payout IBAN for EUR yet/)).toBeInTheDocument();
  // Lot status is readable.
  fireEvent.click(screen.getByRole("tab", { name: "EUR" }));
  const lots = (await screen.findByRole("heading", { name: "EUR balance lots" })).closest("section") as HTMLElement;
  expect(within(lots).getByText("Frozen, penalty charged")).toBeInTheDocument();
  expect(within(lots).getByText("1 lot · used oldest first")).toBeInTheDocument();

  // Withdraw maximum (CHF): everything except the "frozen" status lot.
  fireEvent.click(screen.getAllByRole("button", { name: "Withdraw to IBAN" })[0]);
  const dialog = await screen.findByRole("dialog", { name: "Withdraw CHF" });
  expect(within(dialog).getByText("CHF 12'896.30")).toBeInTheDocument();
  await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
}, 30_000);
