// IP of Webby-Soft SRL.
// Pure figures of My investments and the investment page (U33 slice S3), from today's portfolio API.
// No invented data: a figure the API does not give is null and the screen leaves it out.
import type { Holding, PortfolioHoldingInstallment, PrimaryOrderPortal } from "../../../../api/generated/banxumApi";
import { installmentProgress, isPaidScheduleRow } from "../../../../investorPortal/holdingProgress";

/** The design's investment states (INV_STATUS). "due" is a payment in its grace days (not Late yet). */
export type InvestmentState = "active" | "due" | "funded" | "late" | "default" | "writtenOff" | "repaid" | "sold";

export const CURRENT_STATES: InvestmentState[] = ["active", "due", "funded", "late", "default", "writtenOff"];
export const HISTORY_STATES: InvestmentState[] = ["repaid", "sold"];

/** Orders still waiting for the funding close (balance reserved or requested). */
const OPEN_ORDER_STATUSES = new Set(["pending", "balance_allocated", "partially_allocated"]);

export function isOpenOrder(order: Pick<PrimaryOrderPortal, "status">) {
  return OPEN_ORDER_STATUSES.has(order.status);
}

/** The amount an open order stands for: the reserved part once allocated, otherwise the requested amount. */
export function orderAmountMinor(order: Pick<PrimaryOrderPortal, "allocated_amount_minor" | "requested_amount_minor">) {
  return order.allocated_amount_minor > 0 ? order.allocated_amount_minor : order.requested_amount_minor;
}

export function holdingState(holding: Pick<Holding, "status" | "current_principal_minor" | "loan">): InvestmentState {
  if (holding.status === "transferred") return "sold";
  if (!(holding.status === "active" && holding.current_principal_minor > 0)) return "repaid";
  const loanStatus = holding.loan.loan_status;
  if (loanStatus === "written_off") return "writtenOff";
  if (loanStatus === "defaulted") return "default";
  if (loanStatus === "late") return "late";
  if (loanStatus === "funded") return "funded";
  if (holding.loan.days_past_due > 0) return "due";
  return "active";
}

export function isCurrentHolding(holding: Pick<Holding, "status" | "current_principal_minor" | "loan">) {
  return CURRENT_STATES.includes(holdingState(holding));
}

/** Contractual interest received, including interest recovered for a loan in default (not penalties). */
export function interestReceivedMinor(holding: Holding) {
  return holding.received_interest_minor + holding.recovered_contractual_interest_minor + holding.recovered_default_interest_minor;
}

/** Principal paid back so far: scheduled repayments and recovered principal. */
export function principalReturnedMinor(holding: Holding) {
  return holding.received_principal_minor + holding.recovered_principal_minor;
}

function sortedRows(holding: Holding) {
  return [...holding.investment_schedule].sort(
    (left, right) => left.due_date.localeCompare(right.due_date) || left.installment_number - right.installment_number
  );
}

/** Remaining rows of the investor's projected schedule, oldest first (the API sends unpaid rows only). */
export function projectedRows(holding: Holding) {
  return sortedRows(holding);
}

export function isOverdueRow(row: Pick<PortfolioHoldingInstallment, "status">) {
  return row.status === "overdue";
}

/** A projection exists for performing, funded and late loans; a loan in default has none. */
export function hasProjection(holding: Holding) {
  const state = holdingState(holding);
  return state === "active" || state === "due" || state === "funded" || state === "late";
}

/**
 * Interest to be received (design: "Interest to be received · Projected"): future scheduled interest of
 * active and late investments. Overdue payments, reservations, loans in default, sold and repaid
 * investments are excluded. Null when there is no projection.
 */
export function projectedInterestMinor(holding: Holding) {
  if (!hasProjection(holding)) return null;
  return projectedRows(holding)
    .filter((row) => !isOverdueRow(row))
    .reduce((sum, row) => sum + row.projected_interest_minor, 0);
}

/** Received interest plus every remaining projected interest row (the "out of ... projected" figure). */
export function lifetimeInterestMinor(holding: Holding) {
  if (!hasProjection(holding)) return null;
  return interestReceivedMinor(holding) + projectedRows(holding).reduce((sum, row) => sum + row.projected_interest_minor, 0);
}

export function overdueRows(holding: Holding) {
  return projectedRows(holding).filter(isOverdueRow);
}

/** The next scheduled payment (not overdue), or null. */
export function nextPayment(holding: Holding) {
  if (!hasProjection(holding)) return null;
  return projectedRows(holding).find((row) => !isOverdueRow(row)) ?? null;
}

/** Final date of the investment: the loan's maturity, else the last schedule row. */
export function maturityDate(holding: Holding) {
  if (holding.loan.maturity_date) return holding.loan.maturity_date;
  const loanRows = holding.loan.schedule.filter((row) => row.installment_number > 0);
  const last = [...loanRows].sort((left, right) => left.due_date.localeCompare(right.due_date)).at(-1);
  return last?.due_date ?? null;
}

/** The day a finished investment was paid back, from the last recorded borrower payment. */
export function completedOnDate(holding: Holding) {
  const paid = holding.loan.schedule.filter(isPaidScheduleRow);
  const dates = paid.map((row) => row.payment_date ?? row.due_date).sort();
  return dates.at(-1) ?? null;
}

/** Outstanding principal after each projected row, for the "details" line of the schedule. */
export function principalAfterRows(holding: Holding) {
  let remaining = holding.current_principal_minor;
  return projectedRows(holding).map((row) => {
    remaining = Math.max(0, remaining - row.projected_principal_minor);
    return { row, principalAfterMinor: remaining };
  });
}

/** Borrower installments of the loan: received and total, counted once per installment. */
export function installmentCounts(holding: Holding) {
  const { paid, total } = installmentProgress(holding.loan.schedule);
  return { received: paid, total };
}

/** Distinct loans of a list of holdings: two lots of one loan are one investment (audit SECONDARY-11). */
export function loanCount(holdings: Holding[]) {
  return new Set(holdings.map((holding) => holding.loan.loan_id)).size;
}

/** Adds an amount to a per-currency total. */
export function addTo(totals: Map<string, number>, currency: string, amountMinor: number) {
  totals.set(currency, (totals.get(currency) ?? 0) + amountMinor);
}

/** EUR first, then CHF, then any other code alphabetically (the design's header order). */
export function currencyOrder(left: string, right: string) {
  const rank = (code: string) => (code === "EUR" ? 0 : code === "CHF" ? 1 : 2);
  return rank(left) - rank(right) || left.localeCompare(right);
}

export function sortedCurrencies(codes: Iterable<string>) {
  return Array.from(new Set(codes)).sort(currencyOrder);
}

export function totalsList(totals: Map<string, number>) {
  return Array.from(totals.entries()).sort(([left], [right]) => currencyOrder(left, right));
}

export type PortfolioPayment = {
  key: string;
  holding: Holding;
  row: PortfolioHoldingInstallment;
  overdue: boolean;
};

/** Every remaining payment of the current investments with a projection (overdue first, then by date). */
export function portfolioPayments(holdings: Holding[]): PortfolioPayment[] {
  return holdings
    .filter((holding) => isCurrentHolding(holding) && hasProjection(holding))
    .flatMap((holding) =>
      projectedRows(holding).map((row) => ({ key: `${holding.id}:${row.loan_installment_id}`, holding, row, overdue: isOverdueRow(row) }))
    )
    .sort((left, right) => Number(right.overdue) - Number(left.overdue) || left.row.due_date.localeCompare(right.row.due_date));
}

/** The earliest next payment across holdings (amount of that row, its currency). */
export function earliestNextPayment(holdings: Holding[]) {
  let best: { holding: Holding; row: PortfolioHoldingInstallment } | null = null;
  for (const holding of holdings) {
    const row = nextPayment(holding);
    if (row && (!best || row.due_date < best.row.due_date)) best = { holding, row };
  }
  return best;
}

export type HoldingSortKey = "maturity" | "next" | "principal" | "interest";

export function sortHoldings(holdings: Holding[], key: HoldingSortKey) {
  const value = (holding: Holding): string | number => {
    if (key === "maturity") return maturityDate(holding) ?? "9999-12-31";
    if (key === "next") return overdueRows(holding)[0]?.due_date ?? nextPayment(holding)?.due_date ?? "9999-12-31";
    if (key === "principal") return -holding.current_principal_minor;
    return -(holding.loan.yield_bps || holding.loan.interest_rate_bps);
  };
  return [...holdings].sort((left, right) => {
    const x = value(left);
    const y = value(right);
    const compared = typeof x === "string" ? x.localeCompare(String(y)) : x - Number(y);
    return compared || left.loan.loan_title.localeCompare(right.loan.loan_title);
  });
}

/** Annual rate shown to the investor: the investor yield (originator claims), else the loan rate. */
export function investorRateBps(loan: { yield_bps: number; interest_rate_bps: number }) {
  return loan.yield_bps || loan.interest_rate_bps;
}
