// IP of Webby-Soft SRL.
/*
 * Live public projects in the U33 public design: which projects the home page shows, the
 * labels of a loan card, the security figure (loan against asset value) and the calculators.
 *
 * The figures are display estimates with the platform's current schedule (format.ts plan(): daily
 * interest on the outstanding principal, actual/365, monthly dates; U33-DEC-10/-11 change the
 * engine in Phase 17.5). No risk rating is shown anywhere (U33-DEC-16).
 */
import { t } from "../../i18n";
import type { PublicProject } from "../data";
import { dateKey, num, plan, round2, siteToday } from "../format";
import { collateralLabel, planRepaymentOf, securityText } from "../pages/projectHelpers";
import { soonProjects, type ProjectView } from "../projects";
import type { GlyphName } from "./glyphs";

/** U33 public shows three opportunities (U33-DEC-39). */
export const HOME_OPPORTUNITIES = 3;

/**
 * The home page's opportunities: open projects, closing soonest first (then the most funded),
 * then projects opening soon; at most three.
 */
export function homeOpportunities(views: ProjectView[], limit = HOME_OPPORTUNITIES) {
  const open = views
    .filter((view) => view.isOpen)
    .sort((a, b) => {
      const left = a.daysLeft ?? Number.MAX_SAFE_INTEGER;
      const right = b.daysLeft ?? Number.MAX_SAFE_INTEGER;
      return left !== right ? left - right : b.percent - a.percent;
    });
  return [...open, ...soonProjects(views)].slice(0, limit);
}

/** 1050 -> "10.5", 800 -> "8", 775 -> "7.75" (the design's toLocaleString). */
export function rateText(bps: number) {
  const value = bps / 100;
  return num(value, 2).replace(/\.?0+$/, "");
}

/** The highest rate of the open projects, in basis points, or null. */
export function maxOpenRateBps(views: ProjectView[]) {
  const open = views.filter((view) => view.isOpen);
  return open.length ? Math.max(...open.map((view) => view.p.interest_rate_bps)) : null;
}

/** Whole amount of minor units without decimals: 80000000 -> "800,000" (the design's cards). */
export function wholeAmount(minor: number) {
  return num(Math.round(minor / 100), 0);
}

export type PaymentSummary = { title: string; detail: string };

/** The card's payment line (design card-payment): "One payment · At the end of 18 months". */
export function paymentSummary(p: Pick<PublicProject, "repayment_type" | "term_months">): PaymentSummary {
  const months = p.term_months;
  switch (p.repayment_type) {
    case "interest_only_then_bullet":
      return { title: t("One payment"), detail: t("At the end of {months} months", { months }) };
    case "bullet_periodic_interest":
      return { title: t("Monthly interest"), detail: t("Principal at the end of {months} months", { months }) };
    default:
      return { title: t("Monthly payments"), detail: t("Over {months} months", { months }) };
  }
}

/** The payment frequency line of the project page's repayments panel. */
export function frequencyText(p: Pick<PublicProject, "repayment_type">) {
  switch (planRepaymentOf(p.repayment_type)) {
    case "bullet":
      return t("Paid at maturity");
    case "interest-only":
      return t("Monthly interest, principal at maturity");
    default:
      return t("Monthly payments");
  }
}

/** Nioicon glyph of a security type (design: building for property, gear for equipment). */
export function securityGlyph(collateralType: string): GlyphName {
  switch (collateralType) {
    case "real_estate":
      return "building";
    case "equipment":
    case "inventory":
      return "gear";
    case "receivables":
    case "invoices":
      return "file";
    case "corporate_guarantee":
    case "personal_guarantee":
      return "user";
    case "cash_collateral":
      return "coins";
    default:
      return "shield";
  }
}

/** The secured asset or right in a few words ("Property", "Equipment", "Personal guarantee"). */
export function assetName(collateralType: string) {
  switch (collateralType) {
    case "real_estate":
      return t("Property");
    case "equipment":
      return t("Equipment");
    case "inventory":
      return t("Inventory");
    case "receivables":
      return t("Receivables");
    case "invoices":
      return t("Invoices");
    case "securities_pledge":
      return t("Pledged securities");
    case "share_pledge":
      return t("Pledged shares");
    case "cash_collateral":
      return t("Cash collateral");
    case "corporate_guarantee":
      return t("Corporate guarantee");
    case "personal_guarantee":
      return t("Personal guarantee");
    default:
      return t(collateralLabel(collateralType));
  }
}

/** Label of the asset value bar ("Property value", "Equipment value", "Collateral value"). */
export function assetValueLabel(collateralType: string) {
  if (collateralType === "real_estate") return t("Property value");
  if (collateralType === "equipment") return t("Equipment value");
  return t("Collateral value");
}

/** The security text of a card or panel: the project's own text, else the type. */
export function securityTitle(p: Pick<PublicProject, "collateral_description" | "collateral_type">) {
  return securityText(p);
}

export type SecurityFigure = {
  ltv: number;
  loanMinor: number;
  valueMinor: number;
  valueLabel: string;
};

/**
 * Loan amount and asset value on the same scale (design security-ltv): the value is the one the
 * published loan-to-value implies (principal / LTV). Null without a loan-to-value.
 */
export function securityFigure(p: PublicProject): SecurityFigure | null {
  if (!p.ltv_bps || p.ltv_bps <= 0) return null;
  return {
    ltv: p.ltv_bps / 100,
    loanMinor: p.principal_minor,
    valueMinor: Math.round((p.principal_minor * 10000) / p.ltv_bps),
    valueLabel: assetValueLabel(p.collateral_type)
  };
}

/** "62%" or "62.5%". */
export function ltvText(ltv: number) {
  return `${num(ltv, 2).replace(/\.?0+$/, "")}%`;
}

// ---------------------------------------------------------------------------------------------
// Calculators (display only, major units like the design's calculator.js)

export type Estimate = {
  interestTotal: number;
  principalTotal: number;
  total: number;
  repayment: ReturnType<typeof planRepaymentOf>;
};

/** Schedule start of a new investment: the end of the funding period, else today. */
export function estimateStart(p: Pick<PublicProject, "funding_deadline">) {
  return dateKey(p.funding_deadline) || siteToday();
}

/** Interest, principal and total of an amount over the loan's term, if every payment is on time. */
export function estimate(p: PublicProject, amount: number): Estimate {
  const repayment = planRepaymentOf(p.repayment_type);
  const rows = plan({ rate: p.interest_rate_bps / 100, term: p.term_months, repayment }, amount, estimateStart(p));
  const interestTotal = round2(rows.reduce((sum, row) => sum + row.interest, 0));
  const principalTotal = round2(rows.reduce((sum, row) => sum + row.principal, 0));
  return { interestTotal, principalTotal, total: round2(interestTotal + principalTotal), repayment };
}

/**
 * The design calculator's amount parser (calculator-choices.js): plain decimals, or grouped
 * thousands with "," / "." / spaces; never strips punctuation blindly. NaN when not an amount.
 */
export function parseCalculatorAmount(value: string) {
  const raw = value.trim();
  if (/^\d+(?:[.,]\d{1,2})?$/.test(raw)) return Number(raw.replace(",", "."));
  if (/^[1-9]\d{0,2}(?:,\d{3})+(?:\.\d{1,2})?$/.test(raw)) return Number(raw.replace(/,/g, ""));
  if (/^[1-9]\d{0,2}(?:\.\d{3})+,\d{1,2}$/.test(raw)) return Number(raw.replace(/\./g, "").replace(",", "."));
  if (/^[1-9]\d{0,2}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d{1,2})?$/.test(raw)) {
    return Number(raw.replace(/[ \u00a0\u202f]/g, "").replace(",", "."));
  }
  return Number.NaN;
}

/** An amount as the calculator field shows it after leaving it: "10,000" or "10,000.5". */
export function calculatorAmountText(amount: number) {
  return num(amount, 2).replace(/\.00$/, "").replace(/(\.\d)0$/, "$1");
}

/** Splits "1,131.21" into ["1,131", ".21"] for the design's large amounts with small cents. */
export function splitCents(amount: number): [string, string] {
  const [whole, cents] = num(amount, 2).split(".");
  return [whole, `.${cents}`];
}
