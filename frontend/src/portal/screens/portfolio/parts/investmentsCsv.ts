// IP of Webby-Soft SRL.
// The CSV of "Export" on My investments (design data-action="export-investments"): every investment,
// built in the browser from the loaded portfolio, with the columns of the design. Amounts use the
// investor's number format, like the Transactions CSV (U33-DEC-32).
import type { Holding, MarketplaceLoanPreview, PrimaryOrderPortal } from "../../../../api/generated/banxumApi";
import type { NumberFormat } from "../../../../investorPortal/format";
import { downloadTextFile } from "../../wallet/parts/downloads";
import { csvAmount, csvCell } from "../../wallet/transactionsModel";
import {
  hasProjection,
  holdingState,
  interestReceivedMinor,
  investorRateBps,
  isOverdueRow,
  orderAmountMinor,
  principalAfterRows,
  principalReturnedMinor
} from "./investmentModel";
import { stateTag } from "./labels";

function rateText(bps: number, format: NumberFormat) {
  return (bps / 100).toFixed(2).replace(".", format === "european" ? "," : ".");
}

export function investmentsCsv(
  holdings: Holding[],
  orders: PrimaryOrderPortal[],
  loansById: Map<string, MarketplaceLoanPreview>,
  format: NumberFormat,
  translate: (text: string) => string
) {
  const separator = format === "european" ? ";" : ",";
  const money = (amountMinor: number, currency: string) => csvAmount(amountMinor, currency, "in", format);
  const header = ["Investment", "Loan", "Borrower", "Currency", "Amount", "Rate", "Term (months)", "Outstanding", "Interest received", "Status"].map(translate);
  const orderLines = orders.map((order) => {
    const loan = loansById.get(order.loan_id);
    return [
      order.id,
      order.loan_title,
      loan?.borrower_display_name ?? "",
      order.currency,
      money(orderAmountMinor(order), order.currency),
      loan ? rateText(investorRateBps(loan), format) : "",
      loan ? String(loan.term_months) : "",
      "",
      "",
      translate(order.allocated_amount_minor > 0 ? "Reserved" : "Requested")
    ];
  });
  const holdingLines = holdings.map((holding) => {
    const state = holdingState(holding);
    return [
      holding.id,
      holding.loan.loan_title,
      holding.loan.borrower_name ?? "",
      holding.currency,
      money(holding.original_principal_minor, holding.currency),
      rateText(investorRateBps(holding.loan), format),
      String(holding.loan.term_months),
      money(state === "sold" || state === "repaid" ? 0 : holding.current_principal_minor, holding.currency),
      money(interestReceivedMinor(holding), holding.currency),
      stateTag(state, holding.loan.days_past_due).label
    ];
  });
  return [header, ...orderLines, ...holdingLines].map((cells) => cells.map((cell) => csvCell(cell, separator)).join(separator)).join("\r\n");
}

/**
 * "Download schedule" of an investment (design data-action="export-schedule", columns #, Due,
 * Principal, Interest, Total, Principal left, Status): the payments received (or one "Received to
 * date" line for older records without per-payment rows), then the remaining payments as the page
 * shows them. Only the investor's share; amounts in the investor's number format.
 */
export function scheduleCsv(holding: Holding, format: NumberFormat, translate: (text: string) => string) {
  const separator = format === "european" ? ";" : ",";
  const header = ["#", "Due", "Principal", "Interest", "Total", "Principal left", "Status"].map(translate);
  const lines = scheduleLines(holding, format, translate);
  return [header, ...lines].map((cells) => cells.map((cell) => csvCell(cell, separator)).join(separator)).join("\r\n");
}

function scheduleLines(holding: Holding, format: NumberFormat, translate: (text: string) => string) {
  const currency = holding.currency;
  const money = (amountMinor: number) => csvAmount(amountMinor, currency, "in", format);
  const paid = holding.received_payments ?? [];
  const lines: string[][] = paid.map((payment) => [
    payment.installment_number ? String(payment.installment_number) : "",
    payment.due_date ?? payment.paid_on,
    money(payment.principal_minor),
    money(payment.interest_minor),
    money(payment.total_minor),
    money(payment.principal_after_minor),
    translate("Paid")
  ]);
  const receivedPrincipal = principalReturnedMinor(holding);
  const receivedInterest = interestReceivedMinor(holding);
  if (paid.length === 0 && receivedPrincipal + receivedInterest > 0) {
    lines.push([
      "",
      translate("Received to date"),
      money(receivedPrincipal),
      money(receivedInterest),
      money(receivedPrincipal + receivedInterest),
      "",
      translate("Paid")
    ]);
  }
  const state = holdingState(holding);
  if (hasProjection(holding) && state !== "default" && state !== "writtenOff") {
    for (const { row, principalAfterMinor } of principalAfterRows(holding)) {
      const status = isOverdueRow(row) ? "Overdue" : row.status === "pending" ? "Pending" : row.status === "due" ? "Due" : "Scheduled";
      lines.push([
        String(row.installment_number),
        row.due_date,
        money(row.projected_principal_minor),
        money(row.projected_interest_minor),
        money(row.projected_total_minor),
        money(principalAfterMinor),
        translate(status)
      ]);
    }
  }
  return lines;
}

/** Whether the investment has a schedule to download (design: the link shows when there are rows). */
export function hasScheduleRows(holding: Holding) {
  return scheduleLines(holding, "swiss", (text) => text).length > 0;
}

/** Saves the investment's payment schedule as CSV (design: "Download schedule", "Repayment schedule"). */
export function downloadSchedule(holding: Holding, format: NumberFormat, translate: (text: string) => string) {
  downloadTextFile(scheduleCsv(holding, format, translate), `banxum-${holding.id}-schedule.csv`);
}
