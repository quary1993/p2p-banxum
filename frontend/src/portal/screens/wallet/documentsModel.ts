// IP of Webby-Soft SRL.
// How the Reports and Documents pages read GET /investor/portal/documents/: account statements and
// annual tax information (generated on request), and acceptance evidence of the agreements the
// investor accepted (investment and resale agreements, platform terms and risk disclosures).
import type { InvestorDocument } from "../../../api/generated/banxumApi";
import { formatDate, zurichDateKey } from "../../../investorPortal/format";

export type DocumentTab = "investment" | "statements" | "platform";

export function isReport(document: Pick<InvestorDocument, "document_kind">) {
  return document.document_kind === "account_statement" || document.document_kind === "annual_tax_information";
}

const PLATFORM_CATEGORIES = new Set(["registration", "risk_disclosure"]);

export function documentTab(document: Pick<InvestorDocument, "document_kind" | "category" | "document_type">): DocumentTab {
  if (isReport(document)) return "statements";
  if (document.category) return PLATFORM_CATEGORIES.has(document.category) ? "platform" : "investment";
  // Older payloads without a category: registration terms and risk notices are platform documents.
  return document.document_type === "Agreement" || document.document_type === "Risk" ? "platform" : "investment";
}

/** English title of a report row (translated by the page). */
export function reportTitle(document: Pick<InvestorDocument, "document_kind">) {
  return document.document_kind === "annual_tax_information" ? "Tax information" : "Account statement";
}

/** English second line of a report row. */
export function reportSubtitle(document: Pick<InvestorDocument, "document_kind" | "period_start" | "period_end">) {
  if (document.document_kind === "annual_tax_information") return "Annual statement for your tax return";
  return isFullYear(document) ? "Annual statement" : "Year to date";
}

function isFullYear(document: Pick<InvestorDocument, "period_start" | "period_end">) {
  const start = document.period_start ?? "";
  const end = document.period_end ?? "";
  return Boolean(start && end) && start.slice(5) === "01-01" && end.slice(5) === "12-31" && start.slice(0, 4) === end.slice(0, 4);
}

/** "2025" for a calendar year, otherwise "01 Jan 2026 – 09 Nov 2026"; "" without a period. */
export function periodLabel(document: Pick<InvestorDocument, "period_start" | "period_end">) {
  if (!document.period_start || !document.period_end) return "";
  if (isFullYear(document)) return document.period_start.slice(0, 4);
  return `${formatDate(document.period_start)} – ${formatDate(document.period_end)}`;
}

/** Calendar years a document covers (its period, or the year of its date). */
export function documentYears(document: Pick<InvestorDocument, "period_start" | "period_end" | "date">) {
  const from = Number((document.period_start ?? zurichDateKey(document.date)).slice(0, 4));
  const to = Number((document.period_end ?? zurichDateKey(document.date)).slice(0, 4));
  const years: number[] = [];
  for (let year = from; year <= to && years.length < 20; year += 1) years.push(year);
  return years;
}

/** Newest first: by period end (reports) or acceptance date (evidence). */
export function newestFirst(a: InvestorDocument, b: InvestorDocument) {
  const key = (document: InvestorDocument) => document.period_end ?? zurichDateKey(document.date);
  return key(b).localeCompare(key(a)) || b.date.localeCompare(a.date);
}

/** The design's investment document types (filter options), in the design's order. */
export const DESIGN_TYPES = ["Purchase and transfer", "Assignment declarations", "Sale agreements"];

/**
 * The design's type of an investment document: an accepted investment or resale purchase is a
 * purchase agreement ("Purchase and transfer"), accepted seller listing terms a sale agreement.
 * Assignment declarations signed by Banxum come with the QES of U33-DEC-13. Other documents keep the
 * platform's type.
 */
export function documentGroup(document: Pick<InvestorDocument, "category" | "document_type">) {
  if (document.category === "primary_market_investment" || document.category === "secondary_market_purchase") return "Purchase and transfer";
  if (document.category === "secondary_market_listing") return "Sale agreements";
  return document.document_type;
}

/** The design's row title of an investment document. */
export function documentTitle(document: Pick<InvestorDocument, "category" | "document_type" | "title">) {
  if (document.category === "primary_market_investment" || document.category === "secondary_market_purchase") return "Purchase agreement";
  if (document.category === "secondary_market_listing") return "Sale agreement";
  return document.document_type || document.title;
}
