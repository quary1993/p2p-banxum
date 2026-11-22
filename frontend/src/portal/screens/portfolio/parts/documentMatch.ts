// IP of Webby-Soft SRL.
// Which acceptance documents belong to one investment.
import type { InvestorDocument } from "../../../../api/generated/banxumApi";

/**
 * Acceptance documents of one investment. Exact links where the API gives one (a reserved order, a
 * resale listing of this holding); otherwise the investment and purchase agreements whose title names
 * the loan (the server builds those titles from the loan title).
 */
export function documentsForInvestment(documents: InvestorDocument[], target: { orderId?: string; holdingId?: string; loanTitle: string }) {
  const title = target.loanTitle.trim().toLowerCase();
  return documents.filter((document) => {
    if (document.document_kind !== "acceptance_evidence") return false;
    if (target.orderId) return document.context_type === "primary_order" && document.context_id === target.orderId;
    if (target.holdingId && document.context_id === target.holdingId) return true;
    const category = document.category ?? "";
    const titled = title.length > 0 && document.title.toLowerCase().includes(title);
    return titled && (category === "primary_market_investment" || category === "secondary_market_purchase");
  });
}
