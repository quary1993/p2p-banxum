// Borrower schedule rows of a holding's loan (the investment page counts received installments).
import type { PortfolioInstallment } from "../api/generated/banxumApi";

const paidStatuses = new Set(["paid", "paid_in_advance"]);

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
