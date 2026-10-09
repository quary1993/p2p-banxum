import type { Holding, PortfolioInstallment, PortfolioLoan } from "../api/generated/banxumApi";

const paidStatuses = new Set(["paid", "paid_in_advance"]);
const impairedStatuses = new Set(["defaulted", "written_off"]);

export function isPaidScheduleRow(row: PortfolioInstallment) {
  return row.is_paid || paidStatuses.has(row.status);
}

/**
 * Borrower installments paid out of all installments. The schedule also lists each recorded
 * payment as its own row (LO payments have no installment number), so rows are grouped by
 * installment number: an installment counts as paid when all of its rows are paid.
 */
export function installmentProgress(rows: PortfolioInstallment[]) {
  const installments = new Map<number, boolean>();
  for (const row of rows) {
    if (row.installment_number <= 0) continue;
    const paid = installments.get(row.installment_number) ?? true;
    installments.set(row.installment_number, paid && isPaidScheduleRow(row));
  }
  const total = installments.size;
  const paid = Array.from(installments.values()).filter(Boolean).length;
  return { paid, total };
}

/** A loan in default or written off has no "next" payment to expect from the schedule. */
export function loanIsInDefault(loan: Pick<PortfolioLoan, "loan_status">) {
  return impairedStatuses.has(loan.loan_status);
}

/** Status shown for a schedule row. A future row of a loan in default is not expected. */
export function scheduleRowStatus(row: Pick<PortfolioInstallment, "status">, loan: Pick<PortfolioLoan, "loan_status">) {
  if (loanIsInDefault(loan) && (row.status === "upcoming" || row.status === "due")) return "not_expected";
  return row.status;
}

/**
 * The payment selected when the holding page opens. A performing loan shows the next projected
 * payment. A loan in default shows the first overdue payment, then the last payment received.
 */
export function defaultSelectedPaymentKey(
  loan: Pick<PortfolioLoan, "loan_status">,
  timelineRows: PortfolioInstallment[],
  firstProjectionId: string | null
) {
  if (firstProjectionId && !loanIsInDefault(loan)) return `projection:${firstProjectionId}`;
  const overdue = timelineRows.find((row) => row.status === "overdue");
  if (overdue) return `loan:${overdue.id}`;
  const paidRows = timelineRows.filter(isPaidScheduleRow);
  if (paidRows.length > 0) return `loan:${paidRows[paidRows.length - 1].id}`;
  if (firstProjectionId) return `projection:${firstProjectionId}`;
  return timelineRows.length > 0 ? `loan:${timelineRows[timelineRows.length - 1].id}` : "";
}

/** Holdings that are finished: repaid, sold or closed with no principal left. */
export function completedHoldings(holdings: Holding[]) {
  return holdings.filter((holding) => !(holding.status === "active" && holding.current_principal_minor > 0));
}

export function completedHoldingLabel(holding: Holding) {
  if (holding.status === "transferred") return "Sold";
  if (holding.loan.loan_status === "written_off") return "Written off";
  if (holding.loan.loan_status === "repaid" || holding.status === "closed") return "Repaid";
  return "Closed";
}
