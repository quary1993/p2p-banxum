// IP of Webby-Soft SRL.
// Readable labels of the portfolio area: investment states, repayment types, security types and their
// design groups, project tiles. English keys for t(); never raw API tokens on screen.
import { t } from "../../../../i18n";
import { formatRateBps } from "../../../../investorPortal/format";
import type { TagTone } from "../../../components";
import type { InvestmentState } from "./investmentModel";

/** Status pill of an investment (design INV_STATUS): tone and label. */
export function stateTag(state: InvestmentState, daysPastDue = 0): { tone: TagTone; label: string } {
  switch (state) {
    case "active":
      return { tone: "solid", label: t("On schedule") };
    case "due":
      // U33-DEC-09: a payment in its grace days is due, not "On schedule" and not Late yet.
      return { tone: "neutral", label: daysPastDue === 1 ? t("Payment due · 1 day") : t("Payment due · {days} days", { days: daysPastDue }) };
    case "funded":
      return { tone: "neutral", label: t("Funded") };
    case "late":
      return { tone: "late", label: daysPastDue > 0 ? t("Late payment · {days} days", { days: daysPastDue }) : t("Late payment") };
    case "default":
      return { tone: "default", label: t("Default") };
    case "writtenOff":
      return { tone: "default", label: t("Written off") };
    case "repaid":
      return { tone: "muted", label: t("Repaid") };
    case "sold":
      return { tone: "muted", label: t("Sold") };
  }
}

/** How the loan pays back (today: monthly schedules only, PROD-DEC-005 until U33-DEC-11). */
export function repaymentText(repaymentType: string) {
  switch (repaymentType) {
    case "equal_installments":
    case "amortizing_principal_interest":
      return t("Principal and interest paid monthly");
    case "bullet_periodic_interest":
      return t("Interest paid monthly; principal at the end");
    case "interest_only_then_bullet":
      return t("Interest only, then principal at the end");
    case "interest_only_then_amortizing":
      return t("Interest only first, then principal and interest monthly");
    default:
      return t("Repayments follow the payment schedule");
  }
}

/** The short cadence line above a schedule (design: "Monthly interest · Principal repaid at maturity"). */
export function cadenceText(repaymentType: string) {
  switch (repaymentType) {
    case "equal_installments":
    case "amortizing_principal_interest":
      return t("Monthly payments · Principal and interest");
    case "bullet_periodic_interest":
    case "interest_only_then_bullet":
      return t("Monthly interest · Principal repaid at maturity");
    case "interest_only_then_amortizing":
      return t("Monthly interest first · Then principal and interest");
    default:
      return "";
  }
}

const securityLabels: Record<string, string> = {
  real_estate: "Property mortgage",
  equipment: "Equipment pledge",
  inventory: "Inventory pledge",
  receivables: "Rights to payments",
  invoices: "Invoice receivables",
  share_pledge: "Company share pledge",
  securities_pledge: "Securities pledge",
  personal_guarantee: "Personal guarantee",
  corporate_guarantee: "Company guarantee",
  cash_collateral: "Cash collateral",
  asset_backed: "Asset-backed security",
  mixed_collateral: "Several securities",
  other: "Other security",
  unsecured_exception: "No collateral",
  unsecured: "No collateral"
};

/** Readable name of a collateral type (the design's security names where it has one). */
export function securityLabel(collateralType: string) {
  const label = securityLabels[collateralType];
  if (label) return t(label);
  const words = collateralType.replace(/_/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : t("Security");
}

/**
 * The design's Smart Invest security groups. Our collateral types the design does not name stay
 * selectable under their own names: inventory and invoices join the matching group, the rest are in
 * "Other security".
 */
export const SECURITY_GROUPS: Array<{ key: string; label: string; types: string[] }> = [
  { key: "physical", label: "Physical assets", types: ["real_estate", "equipment", "inventory"] },
  { key: "rights", label: "Payment rights & shares", types: ["receivables", "invoices", "share_pledge", "securities_pledge"] },
  { key: "guarantees", label: "Guarantees", types: ["personal_guarantee", "corporate_guarantee"] },
  { key: "other", label: "Other security", types: ["cash_collateral", "asset_backed", "mixed_collateral", "other"] }
];

export const ALL_SECURED_TYPES = SECURITY_GROUPS.flatMap((group) => group.types);

/** The security preference of Smart Invest in a few words ("Any security type", or the chosen types). */
export function securityPreferenceText(security: string[] | null) {
  if (security === null) return t("No preference");
  const secured = security.filter((type) => type !== "unsecured");
  const parts = ALL_SECURED_TYPES.every((type) => secured.includes(type))
    ? [t("Any security type")]
    : secured.length > 3
      ? [t("{count} security types", { count: secured.length })]
      : secured.map(securityLabel);
  if (security.includes("unsecured")) parts.push(securityLabel("unsecured"));
  return parts.join(", ");
}

/** Nioicon glyph of a project tile, from the security behind the loan (the subset has no sector icons). */
export function tileIcon(collateralType: string) {
  switch (collateralType) {
    case "real_estate":
      return "home";
    case "equipment":
      return "truck";
    case "inventory":
      return "package";
    case "receivables":
    case "invoices":
      return "file-text";
    case "share_pledge":
    case "securities_pledge":
      return "growth";
    case "personal_guarantee":
    case "corporate_guarantee":
      return "shield-check";
    case "cash_collateral":
      return "coins";
    case "mixed_collateral":
      return "layers";
    case "asset_backed":
      return "box";
    default:
      return "briefcase";
  }
}

/** New loan, existing claim (Loan Originator) or bought on the resale market. */
export function investmentTypeText(productType: string, sourceType?: string) {
  if (sourceType === "secondary_market") return t("Bought on the resale market");
  return productType === "originator_claim" ? t("Existing claim") : t("New loan");
}

/** "12 months" / "1 month". */
export function monthsText(months: number) {
  return months === 1 ? t("1 month") : t("{count} months", { count: months });
}

/** "1,0% discount", "2,0% premium" (only on listings made before today's par-or-discount rule) or "No discount or premium". */
export function priceAdjustmentText(discountPremiumBps: number) {
  if (discountPremiumBps === 0) return t("No discount or premium");
  const percent = formatRateBps(Math.abs(discountPremiumBps));
  return discountPremiumBps < 0 ? t("{percent} discount", { percent }) : t("{percent} premium", { percent });
}
