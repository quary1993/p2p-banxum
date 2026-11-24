// IP of Webby-Soft SRL.
/*
 * Live public projects in the U33 public design: which projects the home page shows, the
 * labels of a loan card, the security figure (loan against asset value) and the calculators.
 *
 * The figures are display estimates with the formulas of the interest engine (format.ts plan():
 * Actual/365 Fixed on the outstanding principal, due dates by the loan's payment frequency;
 * IMPLEMENTATION_PLAN 18.6). No risk rating is shown anywhere (U33-DEC-16).
 */
import { t } from "../../i18n";
import type { PublicProject } from "../data";
import { dateKey, dateShort, num, plan, round2, siteToday } from "../format";
import { collateralLabel, planRepaymentOf, planTermsOf, securityText } from "../pages/projectHelpers";
import { openingDate, soonProjects, type ProjectView } from "../projects";
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

type ScheduleFacts = Pick<PublicProject, "repayment_type" | "term_months" | "payment_frequency">;

/** "Monthly" / "Quarterly" / "Half-yearly" / "Yearly" texts of the payment frequency (18.6). */
function frequencyWords(p: Pick<PublicProject, "payment_frequency">) {
  switch (p.payment_frequency) {
    case "quarterly":
      return { interest: t("Quarterly interest"), payments: t("Quarterly payments"), principalLater: t("Quarterly interest, principal at maturity") };
    case "half_yearly":
      return { interest: t("Half-yearly interest"), payments: t("Half-yearly payments"), principalLater: t("Half-yearly interest, principal at maturity") };
    case "annual":
      return { interest: t("Yearly interest"), payments: t("Yearly payments"), principalLater: t("Yearly interest, principal at maturity") };
    default:
      return { interest: t("Monthly interest"), payments: t("Monthly payments"), principalLater: t("Monthly interest, principal at maturity") };
  }
}

/** The card's payment line (design card-payment): "One payment · At the end of 18 months". */
export function paymentSummary(p: ScheduleFacts): PaymentSummary {
  const months = p.term_months;
  const words = frequencyWords(p);
  if (p.repayment_type === "custom_schedule") return { title: t("Custom schedule"), detail: t("Over {months} months", { months }) };
  switch (planRepaymentOf(p.repayment_type)) {
    case "bullet":
      return { title: t("One payment"), detail: t("At the end of {months} months", { months }) };
    case "interest-only":
      return { title: words.interest, detail: t("Principal at the end of {months} months", { months }) };
    default:
      return { title: words.payments, detail: t("Over {months} months", { months }) };
  }
}

/** The payment frequency line of the project page's repayments panel. */
export function frequencyText(p: Pick<PublicProject, "repayment_type" | "payment_frequency">) {
  if (p.repayment_type === "custom_schedule") return t("Custom schedule");
  const words = frequencyWords(p);
  switch (planRepaymentOf(p.repayment_type)) {
    case "bullet":
      return t("Paid at maturity");
    case "interest-only":
      return words.principalLater;
    default:
      return words.payments;
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

/**
 * The secured asset in a few words: the anonymous name the admin entered for the main security
 * (18.3, "Residential building in Biel"), else the type ("Property", "Equipment").
 */
export function projectAssetName(project: { collateral_type: string; security_public_name?: string }) {
  return project.security_public_name?.trim() || assetName(project.collateral_type);
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
  const terms = planTermsOf(p);
  const repayment = terms.repayment;
  const rows = plan(terms, amount, estimateStart(p));
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

/** A project's badge (project page heading, All projects cards): open with the days left, coming soon, or the loan's status. */
export function statusBadge(view: ProjectView, t: (text: string, vars?: Record<string, string | number>) => string) {
  const p = view.p;
  if (view.isSoon) return { label: t("Opens {date}", { date: dateShort(openingDate(p)) }), cls: "" };
  if (view.isOpen) {
    if (view.daysLeft === null) return { label: t("Open"), cls: "is-open" };
    return {
      label: view.daysLeft <= 0 ? t("Open · closes today") : t("Open · {days} days left", { days: view.daysLeft }),
      cls: "is-open"
    };
  }
  switch (p.public_status) {
    case "repaying":
      return { label: t("Repaying"), cls: "" };
    case "late":
      return { label: t("Late {days} days", { days: p.record?.days_past_due ?? 0 }), cls: "is-late" };
    case "repaid":
      return { label: t("Repaid"), cls: "" };
    case "default":
      return { label: t("Default"), cls: "is-default" };
    default:
      return { label: t("Fully funded"), cls: "" };
  }
}
