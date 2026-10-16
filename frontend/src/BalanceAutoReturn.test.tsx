// IP of Webby-Soft SRL.
// Real-API checks of the 58-day automatic return (owner decision 2026-10-16): the Account page shows
// the last day and the return date of each lot, the money due back, and asks for a verified IBAN
// when the money cannot go back; the Help page answers with the same rule.
import { fireEvent, screen, within } from "@testing-library/react";
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

// 10 Dec 2026: one CHF lot on its last day (day 58), one CHF lot with 10 days left, and EUR money
// due back since today (day 59) with no verified EUR IBAN.
const ageingBalances = () =>
  balances({
    summaries: [
      summary("CHF", {
        total_available_minor: 300_00,
        investable_minor: 200_00,
        withdraw_only_minor: 100_00,
        lot_count: 2,
        active_lot_count: 2,
        next_return_date: "2026-12-11"
      }),
      summary("EUR", { total_available_minor: 500_00, overdue_minor: 500_00, lot_count: 1, active_lot_count: 1, next_return_date: "2026-12-10" })
    ],
    lots: [
      lot({
        id: "lot-chf-last",
        currency: "CHF",
        bucket: "withdraw_only",
        available_amount_minor: 100_00,
        original_amount_minor: 100_00,
        last_day: "2026-12-10",
        return_date: "2026-12-11",
        days_until_last_day: 0,
        days_until_withdrawal_deadline: 2,
        requires_withdrawal: true
      }),
      lot({
        id: "lot-chf-new",
        currency: "CHF",
        available_amount_minor: 200_00,
        original_amount_minor: 200_00,
        last_day: "2026-12-20",
        return_date: "2026-12-21",
        days_until_last_day: 10
      }),
      lot({
        id: "lot-eur-due",
        currency: "EUR",
        bucket: "overdue",
        available_amount_minor: 500_00,
        original_amount_minor: 500_00,
        last_day: "2026-12-09",
        return_date: "2026-12-10",
        days_until_last_day: -1,
        days_until_withdrawal_deadline: 1,
        requires_withdrawal: true
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
      }
    ],
    auto_return_after_days: 58
  });

test("Account shows the last day, the return date and asks for an IBAN when money cannot go back", async () => {
  server.use(...shellHandlers({ balances: ageingBalances }));
  renderLiveApp(App, "/balances");

  const lotsCard = (await screen.findByRole("heading", { name: "CHF balance lots" }, { timeout: 5000 })).closest("section") as HTMLElement;
  expect(screen.getAllByText("Funds are non-interest-bearing. Money that is not invested goes back to your bank automatically after 58 days.").length).toBeGreaterThan(0);
  const lastDayRow = within(lotsCard).getByText("Day 58: last day").closest("tr") as HTMLElement;
  expect(within(lastDayRow).getByText("Goes back to your bank on 11 Dec 2026")).toBeInTheDocument();
  expect(within(lastDayRow).getByText("Withdraw-only")).toBeInTheDocument();
  const newRow = within(lotsCard).getByText("10d holding time left").closest("tr") as HTMLElement;
  expect(within(newRow).getByText("Goes back to your bank on 21 Dec 2026")).toBeInTheDocument();

  // Account cards: the last-day tile, the money due back, and the next return date.
  expect(screen.getAllByText("Day 58: last day, can only be withdrawn today")).toHaveLength(2);
  expect(screen.getAllByText("Due back to your bank")).toHaveLength(2);
  expect(screen.getAllByText("Not invested within 58 days")).toHaveLength(2);
  expect(screen.getByText("11 Dec 2026").closest("p")).toHaveTextContent("Goes back to your bank on 11 Dec 2026 if not invested");

  // EUR cannot go back: no verified EUR IBAN. CHF has one, so it gets no such banner.
  const banner = screen.getByRole("heading", { name: "Add a verified bank account so we can return your money" }).closest("[role='status']") as HTMLElement;
  expect(banner).toHaveTextContent("EUR 500.00 was not invested within 58 days and must go back to your bank");
  expect(banner).toHaveTextContent("After 60 days (the legal limit) the money enters penalty mode.");
  expect(within(banner).getByRole("button", { name: "Add payout IBAN" })).toBeInTheDocument();
  expect(screen.getAllByText("Add a verified bank account so we can return your money")).toHaveLength(1);

  fireEvent.click(screen.getByRole("tab", { name: "EUR" }));
  const eurLots = (await screen.findByRole("heading", { name: "EUR balance lots" })).closest("section") as HTMLElement;
  const dueRow = within(eurLots).getByText("Due back to your bank").closest("tr") as HTMLElement;
  expect(within(dueRow).getByText("Return due since 10 Dec 2026")).toBeInTheDocument();
  expect(within(dueRow).getByText("Due back")).toBeInTheDocument();

  // Both the last-day lot and the money due back need action.
  expect(screen.getAllByLabelText("2 balances need action").length).toBeGreaterThan(0);
}, 30_000);

test("the Help page explains the 58-day return and the 60-day legal limit", async () => {
  server.use(...shellHandlers({ balances: ageingBalances }));
  renderLiveApp(App, "/portal/help");

  const question = await screen.findByRole("button", { name: "What happens after 58 days?" }, { timeout: 5000 });
  fireEvent.click(question);
  const answer = document.getElementById(question.getAttribute("aria-controls") ?? "") as HTMLElement;
  expect(answer).toHaveTextContent("Day 58 is the last day");
  expect(answer).toHaveTextContent("The next day we send it back automatically to your verified payout IBAN.");
  expect(answer).toHaveTextContent("after day 60 it enters penalty mode");
  expect(screen.getByText(/Money that is not invested goes back to your bank automatically after 58 days\. Investment eligibility/)).toBeInTheDocument();
}, 30_000);
