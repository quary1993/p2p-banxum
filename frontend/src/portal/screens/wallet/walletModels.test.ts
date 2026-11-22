// IP of Webby-Soft SRL.
// How the wallet screens read the API: transaction types and signs, periods, the per-currency
// summary and the CSV in both number formats; the Account page's next return, notices and
// reservations; the Documents tabs and report periods.
import { expect, test } from "vitest";

import type { ActivityEntry, BalanceLot, BalanceSummary, PrimaryOrderPortal } from "../../../api/generated/banxumApi";
import { accountNotices, detailLots, nextReturn, orderedSummaries, reservedMinor, reservedOrders } from "./accountModel";
import { documentTab, documentYears, periodLabel, reportSubtitle } from "./documentsModel";
import { csvAmount, inRange, periodRange, previewTransactionPage, summarize, transactionRow, transactionsCsv } from "./transactionsModel";

function entry(values: Partial<ActivityEntry> & Pick<ActivityEntry, "activity_type">): ActivityEntry {
  return {
    id: "e1",
    occurred_at: "2026-05-21T08:00:00+02:00",
    direction: "in",
    title: "",
    amount_minor: 10_000,
    currency: "CHF",
    status: "",
    loan_id: null,
    loan_title: "",
    metadata: {},
    ...values
  };
}

function summary(currency: string, values: Partial<BalanceSummary> = {}): BalanceSummary {
  return {
    investor_user_id: "u1",
    currency,
    total_available_minor: 0,
    investable_minor: 0,
    withdraw_only_minor: 0,
    overdue_minor: 0,
    frozen_minor: 0,
    penalty_mode_minor: 0,
    penalty_charged_minor: 0,
    lot_count: 0,
    active_lot_count: 0,
    next_investment_deadline_at: null,
    next_withdrawal_deadline_at: null,
    next_return_date: null,
    ...values
  };
}

function lot(values: Partial<BalanceLot> & Pick<BalanceLot, "id" | "currency">): BalanceLot {
  return {
    source_type: "deposit",
    status: "available",
    bucket: "investable",
    received_at: "2026-10-01T10:00:00Z",
    investment_deadline_at: "2026-11-30T23:00:00Z",
    withdrawal_deadline_at: "2026-11-30T23:00:00Z",
    days_until_investment_deadline: 20,
    days_until_withdrawal_deadline: 20,
    return_after_days: 56,
    last_day: "2026-11-29",
    return_date: "2026-11-30",
    return_date_adjusted: false,
    days_until_last_day: 18,
    direct_funding_until: "2026-11-20",
    return_failed: false,
    original_amount_minor: 0,
    available_amount_minor: 0,
    invested_amount_minor: 0,
    converted_amount_minor: 0,
    withdrawn_amount_minor: 0,
    penalized_amount_minor: 0,
    requires_withdrawal: false,
    blocks_financial_actions: false,
    ...values
  };
}

test("repayments and recoveries are credited to the Banxum balance (U33-DEC-02)", () => {
  for (const type of ["repayment_distribution", "originator_repayment_distribution", "recovery_distribution"]) {
    const row = transactionRow(entry({ activity_type: type }));
    expect(row.status).toBe("Credited to your balance");
    expect(row.sign).toBe("in");
    expect(row.status).not.toMatch(/bank account/i);
  }
});

test("orders read as reservation until funding closes, then as an investment", () => {
  const reserved = transactionRow(entry({ activity_type: "primary_order", direction: "internal", status: "balance_allocated" }));
  expect(reserved).toMatchObject({ group: "reservation", label: "Reservation", status: "Until closing", pending: true, sign: "none" });
  const invested = transactionRow(entry({ activity_type: "primary_order", direction: "internal", status: "closed_invested" }));
  expect(invested).toMatchObject({ group: "investment", label: "Investment", status: "Completed", sign: "out" });
  const released = transactionRow(entry({ activity_type: "primary_order", direction: "internal", status: "balance_released" }));
  expect(released.group).toBe("reservation");
  expect(released.sign).toBe("none");
});

test("withdrawals show their outcome and destination; automatic returns are their own type", () => {
  const pending = transactionRow(entry({ activity_type: "withdrawal_request", direction: "out", status: "requested", metadata: { is_forced: false, destination_iban: "CH9300762011623852957" } }));
  expect(pending).toMatchObject({ group: "withdrawal", label: "Withdrawal", status: "Pending", sign: "out" });
  expect(pending.description).toEqual({ text: "To {iban}", vars: { iban: "CH93 •••• 2957" } });
  const forced = transactionRow(entry({ activity_type: "withdrawal_request", direction: "out", status: "finalized", metadata: { is_forced: true } }));
  expect(forced).toMatchObject({ group: "return", label: "Automatic return", status: "Sent" });
  const back = transactionRow(entry({ activity_type: "withdrawal_cancellation", status: "returned", metadata: { is_forced: false } }));
  expect(back).toMatchObject({ label: "Withdrawal cancelled", status: "Returned to your balance", sign: "in" });
});

test("balance credits are named by their source, never by a raw key", () => {
  expect(transactionRow(entry({ activity_type: "balance_deposit", title: "Deposit" }))).toMatchObject({ group: "deposit", label: "Deposit", status: "Received" });
  expect(transactionRow(entry({ activity_type: "balance_secondary_market_proceeds" })).label).toBe("Secondary sale");
  expect(transactionRow(entry({ activity_type: "balance_penalty_charge", direction: "out" }))).toMatchObject({ group: "fee", label: "Penalty" });
  expect(transactionRow(entry({ activity_type: "balance_deposit", title: "QA opening balance" })).label).toBe("Opening balance");
});

test("periods are inclusive Zurich date ranges", () => {
  expect(periodRange({ kind: "days", days: 30 }, "2026-06-05")).toEqual({ from: "2026-05-07", to: "2026-06-05" });
  expect(periodRange({ kind: "year", year: 2025 }, "2026-06-05")).toEqual({ from: "2025-01-01", to: "2025-12-31" });
  expect(periodRange({ kind: "all" }, "2026-06-05")).toEqual({ from: "", to: "" });
  const range = periodRange({ kind: "custom", from: "2026-05-01", to: "2026-05-31" }, "2026-06-05");
  expect(inRange("2026-05-01", range)).toBe(true);
  expect(inRange("2026-05-31", range)).toBe(true);
  expect(inRange("2026-06-01", range)).toBe(false);
  // A late-evening UTC time is the next day in Zurich.
  expect(transactionRow(entry({ activity_type: "balance_deposit", occurred_at: "2026-05-31T22:30:00Z" })).dateKey).toBe("2026-06-01");
});

test("the summary adds the rows in view per currency, withdrawals only once they are sent", () => {
  const rows = [
    entry({ id: "1", activity_type: "balance_deposit", amount_minor: 100_000 }),
    entry({ id: "2", activity_type: "balance_deposit", amount_minor: 50_000, currency: "EUR" }),
    entry({ id: "3", activity_type: "primary_order", direction: "internal", status: "closed_invested", amount_minor: 40_000 }),
    entry({ id: "4", activity_type: "primary_order", direction: "internal", status: "balance_allocated", amount_minor: 30_000 }),
    entry({ id: "5", activity_type: "repayment_distribution", amount_minor: 1_250 }),
    entry({ id: "6", activity_type: "withdrawal_request", direction: "out", status: "finalized", amount_minor: 20_000 }),
    entry({ id: "7", activity_type: "withdrawal_request", direction: "out", status: "requested", amount_minor: 5_000 })
  ].map(transactionRow);
  expect(summarize(rows)).toEqual([
    { currency: "EUR", deposited: 50_000, invested: 0, credited: 0, withdrawn: 0 },
    { currency: "CHF", deposited: 100_000, invested: 40_000, credited: 1_250, withdrawn: 20_000 }
  ]);
});

test("the CSV follows the investor's number format without float maths (U33-DEC-32)", () => {
  expect(csvAmount(123_456, "CHF", "in", "european")).toBe("1234,56");
  expect(csvAmount(123_456, "CHF", "out", "swiss")).toBe("-1234.56");
  expect(csvAmount(5, "EUR", "none", "european")).toBe("0,05");
  const rows = [transactionRow(entry({ id: "tx-1", activity_type: "repayment_distribution", amount_minor: 41_235, loan_title: "Helvetia; Logistik" }))];
  const translate = (text: string, vars?: Record<string, string>) => (vars ? text.replace(/\{(\w+)\}/g, (_, key: string) => vars[key] ?? "") : text);
  const european = transactionsCsv(rows, "european", translate, () => "21 May 2026, 08:00").split("\r\n");
  expect(european[0]).toBe("Date;Type;Status;Description;Currency;Amount;Reference");
  expect(european[1]).toBe('21 May 2026, 08:00;Repayment;Credited to your balance;"Helvetia; Logistik";CHF;412,35;tx-1');
  const swiss = transactionsCsv(rows, "swiss", translate, () => "21 May 2026, 08:00").split("\r\n");
  expect(swiss[1]).toBe('"21 May 2026, 08:00",Repayment,Credited to your balance,Helvetia; Logistik,CHF,412.35,tx-1');
});

test("the next automatic return is the earliest date of money that can still be invested", () => {
  const chf = summary("CHF", { next_return_date: "2026-12-11" });
  const lots = [
    lot({ id: "a", currency: "CHF", bucket: "withdraw_only", available_amount_minor: 10_000, return_date: "2026-12-11" }),
    lot({ id: "b", currency: "CHF", available_amount_minor: 20_000, return_date: "2026-12-21" }),
    lot({ id: "c", currency: "CHF", available_amount_minor: 5_000, return_date: "2026-12-21" })
  ];
  expect(nextReturn(chf, lots)).toEqual({ date: "2026-12-21", amountMinor: 25_000, lastDay: false });
  expect(nextReturn(chf, lots.slice(0, 1))).toEqual({ date: "2026-12-11", amountMinor: 10_000, lastDay: true });
  // Only money already due back: no upcoming return. No lots at all: the summary's date.
  expect(nextReturn(chf, [lot({ id: "d", currency: "CHF", bucket: "overdue", available_amount_minor: 1 })])).toBeNull();
  expect(nextReturn(chf, [])).toEqual({ date: "2026-12-11", amountMinor: null, lastDay: false });
});

test("account notices put money that cannot go back first", () => {
  const notices = accountNotices({
    summaries: [summary("CHF", { withdraw_only_minor: 10_000 }), summary("EUR", { overdue_minor: 50_000 })],
    lots: [lot({ id: "a", currency: "CHF", bucket: "withdraw_only", available_amount_minor: 10_000, return_date: "2026-12-11" })],
    payout_instructions: [
      { id: "p1", currency: "CHF", status: "active", destination_iban: "CH56", destination_account_name: "U", is_verified_usable: true, verification_status: "verified", is_default_return: true, verified_at: null, created_at: "" }
    ]
  });
  expect(notices).toEqual([
    { kind: "dueBackNoAccount", currency: "EUR", amountMinor: 50_000 },
    { kind: "lastDay", currency: "CHF", amountMinor: 10_000, returnDate: "2026-12-11", hasAccount: true }
  ]);
});

test("reserved money comes from allocated orders only; EUR is listed before CHF", () => {
  const order = (status: string, allocated: number, currency = "CHF"): PrimaryOrderPortal => ({
    id: status,
    loan_id: "l",
    loan_title: "Loan",
    loan_status: "open",
    status,
    requested_amount_minor: 10_000,
    allocated_amount_minor: allocated,
    currency,
    created_at: "",
    allocated_at: null,
    released_at: null,
    closed_at: null
  });
  const orders = reservedOrders([order("pending_allocation", 0), order("balance_allocated", 6_000), order("partially_allocated", 2_500), order("closed_invested", 9_000), order("balance_allocated", 1_000, "EUR")]);
  expect(reservedMinor(orders, "CHF")).toBe(8_500);
  expect(reservedMinor(orders, "EUR")).toBe(1_000);
  expect(orderedSummaries([summary("CHF"), summary("EUR")]).map((item) => item.currency)).toEqual(["EUR", "CHF"]);
});

test("documents are sorted into investment, statements and platform tabs", () => {
  const doc = { document_type: "Agreement", document_kind: "acceptance_evidence" };
  expect(documentTab({ ...doc, category: "registration" })).toBe("platform");
  expect(documentTab({ ...doc, category: "risk_disclosure" })).toBe("platform");
  expect(documentTab({ ...doc, category: "primary_market_investment", document_type: "Investment agreement" })).toBe("investment");
  expect(documentTab({ ...doc, category: "secondary_market_listing", document_type: "Listing agreement" })).toBe("investment");
  expect(documentTab({ document_kind: "account_statement", document_type: "Statement" })).toBe("statements");
  expect(documentTab({ document_kind: "annual_tax_information", document_type: "Tax" })).toBe("statements");

  const yearToDate = { document_kind: "account_statement", period_start: "2026-01-01", period_end: "2026-06-05", date: "2026-06-05T00:00:00Z" };
  expect(reportSubtitle(yearToDate)).toBe("Year to date");
  expect(periodLabel(yearToDate)).toMatch(/^1 Jan 2026 – 5 Jun 2026$/);
  const fullYear = { document_kind: "account_statement", period_start: "2025-01-01", period_end: "2025-12-31", date: "2026-06-05T00:00:00Z" };
  expect(reportSubtitle(fullYear)).toBe("Annual statement");
  expect(periodLabel(fullYear)).toBe("2025");
  expect(documentYears({ period_start: "2024-07-01", period_end: "2026-01-31", date: "" })).toEqual([2024, 2025, 2026]);
});

test("Q26: reservation, release with its reason and investment are separate Transactions entries", () => {
  const reserved = transactionRow(entry({ activity_type: "primary_reservation", direction: "internal", status: "balance_allocated", loan_title: "Alpine loan" }));
  expect([reserved.label, reserved.status, reserved.group, reserved.sign, reserved.pending]).toEqual(["Reservation", "Until closing", "reservation", "none", true]);
  const ended = transactionRow(entry({ activity_type: "primary_reservation", direction: "internal", status: "balance_released" }));
  expect(ended.status).toBe("Ended");
  const released = transactionRow(
    entry({ activity_type: "primary_reservation_released", direction: "internal", status: "balance_released", loan_title: "Alpine loan", metadata: { order_id: "o1", reason: "The project's funding was cancelled." } })
  );
  expect([released.label, released.status]).toEqual(["Reservation released", "Back on your balance"]);
  expect(released.description).toEqual({ text: "{loan} · {reason}", vars: { loan: "Alpine loan", reason: "The project's funding was cancelled." } });
  const invested = transactionRow(entry({ activity_type: "primary_investment", direction: "out", status: "closed_invested" }));
  expect([invested.label, invested.group, invested.sign]).toEqual(["Investment", "investment", "out"]);
  const notInvested = transactionRow(entry({ activity_type: "primary_order_ended", direction: "internal", status: "closed_not_invested", metadata: { reason: "" } }));
  expect([notInvested.label, notInvested.status]).toEqual(["Investment order", "Not invested"]);
});

test("18.3: a fully reserved lot stays in the balance details with its reserved part", () => {
  const lots = detailLots([
    lot({ id: "free", currency: "CHF", available_amount_minor: 10_000 }),
    lot({ id: "reserved", currency: "CHF", available_amount_minor: 0, reserved_amount_minor: 30_000 }),
    lot({ id: "used", currency: "CHF", available_amount_minor: 0 })
  ]);
  expect(lots.map((item) => item.id)).toEqual(["free", "reserved"]);
});

test("18.3: the review build pages, filters and sums like the server", () => {
  const entries = [
    entry({ id: "d1", activity_type: "balance_deposit", occurred_at: "2026-05-01T08:00:00Z", amount_minor: 50_000 }),
    entry({ id: "r1", activity_type: "repayment_distribution", occurred_at: "2026-05-02T08:00:00Z", amount_minor: 1_000, currency: "EUR" }),
    entry({ id: "d2", activity_type: "balance_deposit", occurred_at: "2025-04-01T08:00:00Z", amount_minor: 20_000 })
  ];
  const all = { currency: "", group: "" as const, date_from: "", date_to: "", q: "" };
  const first = previewTransactionPage(entries, all, 0, 2);
  expect(first.entries.map((item) => [item.id, item.group, item.available_after_minor])).toEqual([["r1", "repayment", null], ["d1", "deposit", null]]);
  expect([first.total, first.next_offset, first.years, first.currencies]).toEqual([3, 2, [2026, 2025], ["EUR", "CHF"]]);
  expect(previewTransactionPage(entries, all, 2, 2).next_offset).toBeNull();
  const chf2026 = previewTransactionPage(entries, { ...all, currency: "CHF", date_from: "2026-01-01", date_to: "2026-12-31" }, 0, 10);
  expect(chf2026.summary).toEqual([{ currency: "CHF", deposited_minor: 50_000, invested_minor: 0, credited_minor: 0, withdrawn_minor: 0 }]);
});
