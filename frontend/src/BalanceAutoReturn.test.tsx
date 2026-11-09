// IP of Webby-Soft SRL.
// Real-API checks of the 58-day automatic return (owner decision 2026-10-16): the Account page shows
// the last day and the return date of each lot, the money due back, and asks for a verified IBAN
// when the money cannot go back; the Help page answers with the same rule.
import { fireEvent, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
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
        verification_status: "verified",
        is_default_return: true,
        verified_at: "2026-10-09T12:00:00Z",
        created_at: "2026-10-09T11:00:00Z"
      }
    ],
    auto_return_after_days: 58
  });

test("Account shows the last day, the return date and asks for an IBAN when money cannot go back", async () => {
  server.use(
    ...shellHandlers({ balances: ageingBalances }),
    http.get("*/api/v1/investor/portal/primary-orders/", () => HttpResponse.json({ orders: [] }))
  );
  renderLiveApp(App, "/balances");

  // Account cards: the next automatic return of money that can still be invested, with its real date.
  const chf = await screen.findByRole("region", { name: "CHF account" }, { timeout: 5000 });
  expect(within(chf).getByText("21 Dec 2026").closest("p")).toHaveTextContent("CHF 200,00 returns on 21 Dec 2026 if not invested.");
  // EUR money is already due back: no upcoming return date, the rule with the API's day count.
  const eur = screen.getByRole("region", { name: "EUR account" });
  expect(within(eur).getByText("Money that is not invested goes back to your bank account after 58 days.")).toBeInTheDocument();

  // Notices: EUR cannot go back (no verified EUR account); the CHF last-day money can be withdrawn.
  const notices = within(screen.getByRole("region", { name: "Account notices" }));
  const noAccount = notices.getByText("Add a verified bank account so we can return your money.").closest(".alert") as HTMLElement;
  expect(noAccount).toHaveTextContent("EUR 500,00 was not invested within 58 days and must go back to your bank, but there is no verified EUR bank account.");
  expect(noAccount).toHaveTextContent("After 60 days (the legal limit) the money enters penalty mode.");
  expect(within(noAccount).getByRole("button", { name: "Add a bank account" })).toBeInTheDocument();
  const lastDay = notices.getByText("Last day for CHF 100,00.").closest(".alert") as HTMLElement;
  expect(lastDay).toHaveTextContent("It can no longer be invested and goes back to your bank account on 11 Dec 2026. You can withdraw it until then.");
  expect(notices.getAllByText("Add a verified bank account so we can return your money.")).toHaveLength(1);

  // Balance details: each lot's return date and state.
  const table = within(screen.getByText("Balance details").closest("details") as HTMLElement).getByRole("table");
  const lastDayRow = within(table).getByText("100,00").closest("tr") as HTMLElement;
  expect(within(lastDayRow).getByText("11 Dec 2026")).toBeInTheDocument();
  expect(within(lastDayRow).getByText("Last day")).toBeInTheDocument();
  const newRow = within(table).getByText("200,00").closest("tr") as HTMLElement;
  expect(within(newRow).getByText("21 Dec 2026")).toBeInTheDocument();
  const dueRow = within(table).getByText("500,00").closest("tr") as HTMLElement;
  expect(within(dueRow).getByText("Due since 10 Dec 2026")).toBeInTheDocument();
  expect(within(dueRow).getByText("Due back")).toBeInTheDocument();

  // The account rules name the same 58 days and today's 60-day limit.
  fireEvent.click(screen.getByRole("button", { name: "How your account works" }));
  const rules = screen.getByRole("dialog", { name: "How your account works" });
  expect(rules).toHaveTextContent("return automatically to your verified bank account (IBAN) after 58 days");
  // U33-DEC-02: repayments go to the Banxum account.
  expect(rules).toHaveTextContent("Loan repayments go to your Banxum account.");

  // Both the last-day lot and the money due back need action.
  expect(screen.getAllByLabelText("2 balances need action").length).toBeGreaterThan(0);

  // "Add a bank account" opens the bank-account dialog for the currency that has no account.
  fireEvent.click(within(rules).getByRole("button", { name: "Close" }));
  fireEvent.click(within(noAccount).getByRole("button", { name: "Add a bank account" }));
  expect(await screen.findByRole("dialog", { name: "New EUR bank account" })).toBeInTheDocument();
}, 30_000);

test("the Help page explains the 58-day return and the 60-day legal limit", async () => {
  server.use(...shellHandlers({ balances: ageingBalances }));
  renderLiveApp(App, "/portal/help");

  const question = await screen.findByText("What happens to money I do not invest?", {}, { timeout: 5000 });
  fireEvent.click(question);
  const answer = question.closest("details") as HTMLElement;
  expect(answer).toHaveAttribute("open");
  // The day count comes from the balances API (auto_return_after_days).
  expect(answer).toHaveTextContent("Money you do not invest goes back to your bank automatically after 58 days");
  expect(within(answer).getByText("After 58 days")).toBeInTheDocument();
  expect(answer).toHaveTextContent("Day 58 is the last day");
  expect(answer).toHaveTextContent("The next day we send it back automatically to your verified bank account.");
  expect(answer).toHaveTextContent("after day 60 it enters penalty mode");
}, 30_000);
