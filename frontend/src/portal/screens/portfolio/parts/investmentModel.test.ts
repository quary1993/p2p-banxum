// IP of Webby-Soft SRL.
// Figures of My investments and the investment page (U33 slice S3), checked on the preview fixtures.
import { describe, expect, test } from "vitest";

import type { Holding } from "../../../../api/generated/banxumApi";
import { portfolioFixture } from "../../../../investorPortal/fixtures";
import {
  currencyOrder,
  hasProjection,
  holdingState,
  isCurrentHolding,
  isOpenOrder,
  lifetimeInterestMinor,
  loanCount,
  nextPayment,
  orderAmountMinor,
  overdueRows,
  portfolioPayments,
  projectedInterestMinor,
  sortHoldings,
  sortedCurrencies
} from "./investmentModel";

function fixture(id: string): Holding {
  const holding = portfolioFixture.holdings.find((candidate) => candidate.id === id);
  if (!holding) throw new Error(`Missing fixture holding ${id}`);
  return holding;
}

function withLoan(holding: Holding, loan: Partial<Holding["loan"]>, overrides: Partial<Holding> = {}): Holding {
  return { ...holding, ...overrides, loan: { ...holding.loan, ...loan } };
}

describe("holdingState", () => {
  test("maps the portfolio API to the design's investment states", () => {
    expect(holdingState(fixture("H-2310"))).toBe("active");
    expect(holdingState(fixture("H-2256"))).toBe("late");
    expect(holdingState(fixture("H-2201"))).toBe("default");
    expect(holdingState(fixture("H-2120"))).toBe("repaid");
    expect(holdingState(fixture("H-2199"))).toBe("sold");
  });

  test("a payment within its grace days is due, not late; funded and written-off loans keep their state", () => {
    const active = fixture("H-2310");
    expect(holdingState(withLoan(active, { days_past_due: 3 }))).toBe("due");
    expect(holdingState(withLoan(active, { loan_status: "funded" }))).toBe("funded");
    expect(holdingState(withLoan(active, { loan_status: "written_off" }))).toBe("writtenOff");
    // An active holding with nothing left to repay is finished.
    expect(holdingState(withLoan(active, {}, { current_principal_minor: 0 }))).toBe("repaid");
  });

  test("current investments exclude repaid and sold ones", () => {
    expect(isCurrentHolding(fixture("H-2256"))).toBe(true);
    expect(isCurrentHolding(fixture("H-2201"))).toBe(true);
    expect(isCurrentHolding(fixture("H-2120"))).toBe(false);
    expect(isCurrentHolding(fixture("H-2199"))).toBe(false);
  });
});

describe("projections", () => {
  test("interest to be received leaves out overdue payments of a late investment", () => {
    const late = fixture("H-2256");
    const overdue = overdueRows(late);
    expect(overdue.length).toBeGreaterThan(0);
    const future = late.investment_schedule.filter((row) => row.status !== "overdue").reduce((sum, row) => sum + row.projected_interest_minor, 0);
    expect(projectedInterestMinor(late)).toBe(future);
    // The next payment is the first one not yet overdue.
    expect(nextPayment(late)?.status).not.toBe("overdue");
  });

  test("a loan in default has no projection, no next payment and no projected total", () => {
    const defaulted = fixture("H-2201");
    expect(hasProjection(defaulted)).toBe(false);
    expect(projectedInterestMinor(defaulted)).toBeNull();
    expect(lifetimeInterestMinor(defaulted)).toBeNull();
    expect(nextPayment(defaulted)).toBeNull();
  });

  test("the portfolio schedule lists overdue payments first, then by date", () => {
    const payments = portfolioPayments(portfolioFixture.holdings);
    const firstScheduled = payments.findIndex((payment) => !payment.overdue);
    expect(payments.slice(0, firstScheduled).every((payment) => payment.overdue)).toBe(true);
    const scheduled = payments.slice(firstScheduled).map((payment) => payment.row.due_date);
    expect(scheduled).toEqual([...scheduled].sort());
    // Repaid, sold and defaulted investments have no payments in the schedule.
    expect(payments.some((payment) => ["H-2120", "H-2199", "H-2201"].includes(payment.holding.id))).toBe(false);
  });
});

describe("orders, counts and ordering", () => {
  test("only orders waiting for the funding close are open; their amount is the reserved part once allocated", () => {
    expect(["pending", "balance_allocated", "partially_allocated"].every((status) => isOpenOrder({ status }))).toBe(true);
    expect(["balance_released", "closed_invested", "closed_not_invested"].some((status) => isOpenOrder({ status }))).toBe(false);
    expect(orderAmountMinor({ requested_amount_minor: 10_000_00, allocated_amount_minor: 6_500_00 })).toBe(6_500_00);
    expect(orderAmountMinor({ requested_amount_minor: 5_000_00, allocated_amount_minor: 0 })).toBe(5_000_00);
  });

  test("two lots of one loan count as one investment (audit SECONDARY-11)", () => {
    const base = fixture("H-2310");
    expect(loanCount([base, { ...base, id: "second-lot" }, fixture("H-2256")])).toBe(2);
  });

  test("EUR comes first, then CHF, then other currencies", () => {
    expect(sortedCurrencies(["USD", "CHF", "EUR", "CHF"])).toEqual(["EUR", "CHF", "USD"]);
    expect(currencyOrder("CHF", "EUR")).toBeGreaterThan(0);
  });

  test("sorting by interest rate puts the highest investor rate first", () => {
    const sorted = sortHoldings(portfolioFixture.holdings.filter(isCurrentHolding), "interest");
    const rates = sorted.map((holding) => holding.loan.yield_bps || holding.loan.interest_rate_bps);
    expect(rates).toEqual([...rates].sort((left, right) => right - left));
  });
});
