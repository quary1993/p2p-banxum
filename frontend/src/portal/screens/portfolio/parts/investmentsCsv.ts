// IP of Webby-Soft SRL.
// The CSV of "Export" on My investments (design data-action="export-investments"): every investment,
// built in the browser from the loaded portfolio, with the columns of the design. Amounts use the
// investor's number format, like the Transactions CSV (U33-DEC-32).
import type { Holding, MarketplaceLoanPreview, PrimaryOrderPortal } from "../../../../api/generated/banxumApi";
import type { NumberFormat } from "../../../../investorPortal/format";
import { csvAmount, csvCell } from "../../wallet/transactionsModel";
import { holdingState, interestReceivedMinor, investorRateBps, orderAmountMinor } from "./investmentModel";
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
