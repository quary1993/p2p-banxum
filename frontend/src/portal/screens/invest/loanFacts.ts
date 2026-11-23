// IP of Webby-Soft SRL.
/*
 * Facts of a marketplace loan as the U33 investing screens show them (slice S2): product and flow,
 * investor yield, what is still open, funding progress, the investor's eligible balance, the U33
 * names of the collateral types and repayment types, and the investor's share of the schedule.
 * The rules are the platform's current ones (Phase 17.1): values come from the API, never from the
 * design's sample rules. Ratings are never used here (U33-DEC-16).
 */
import type {
  BalanceLot,
  Holding,
  MarketplaceLoanDetail,
  MarketplaceLoanPreview
} from "../../../api/generated/banxumApi";
import { readReadonlyImpersonationToken } from "../../../api/client/impersonation";
import { t } from "../../../i18n";
import { formatPercent } from "../../../investorPortal/format";
import { platformTodayKey } from "../../../investorPortal/platformClock";
import { loanLtvBps } from "../../../investorPortal/portfolioCollateral";

type LoanLike = Pick<MarketplaceLoanPreview, "product_type" | "investment_flow">;

export function isOriginatorClaimLoan(loan: Pick<MarketplaceLoanPreview, "product_type">) {
  return loan.product_type === "originator_claim";
}

/** Legacy originator claim bought through an executable quote (immediate legal assignment). */
export function usesImmediateClaimAssignment(loan: Pick<MarketplaceLoanPreview, "investment_flow">) {
  return loan.investment_flow === "immediate_claim_assignment";
}

/** Loan Originator claim subscribed at par during a funding round (primary order). */
export function usesOriginatorSubscription(loan: LoanLike) {
  return isOriginatorClaimLoan(loan) && loan.investment_flow === "primary_order";
}

export function loanYieldBps(loan: Pick<MarketplaceLoanPreview, "yield_bps" | "interest_rate_bps">) {
  return loan.yield_bps || loan.interest_rate_bps;
}

/** What can still be invested in the opportunity. */
export function loanAvailableMinor(loan: Pick<MarketplaceLoanPreview, "fillable_amount_minor" | "remaining_capacity_minor">) {
  return loan.fillable_amount_minor ?? loan.remaining_capacity_minor;
}

export function isOpenLoan(
  loan: Pick<MarketplaceLoanPreview, "status" | "opportunity_status" | "fillable_amount_minor" | "remaining_capacity_minor">
) {
  const openStatus = ["open", "published"].includes(loan.status) || loan.opportunity_status === "open";
  return openStatus && loanAvailableMinor(loan) > 0;
}

/** U33-DEC-17: shown before it opens. Nothing can be invested or reserved yet. */
export function isComingSoonLoan(loan: Pick<MarketplaceLoanPreview, "opportunity_status">) {
  return loan.opportunity_status === "coming_soon";
}

/** Funded share of the loan, 0-100 with one decimal (bar width). */
export function fundedPercent(loan: Pick<MarketplaceLoanPreview, "principal_minor" | "committed_principal_minor">) {
  if (loan.principal_minor <= 0) return 0;
  return Math.min(100, Math.round((loan.committed_principal_minor / loan.principal_minor) * 1000) / 10);
}

/** Minimum funding threshold of a direct loan (minimum_subscription_bps), null when none applies. */
export function minimumFunding(loan: Pick<MarketplaceLoanPreview, "principal_minor" | "minimum_subscription_bps" | "product_type" | "investment_flow">) {
  if (isOriginatorClaimLoan(loan)) return null;
  const bps = loan.minimum_subscription_bps ?? 0;
  if (bps <= 0 || loan.principal_minor <= 0) return null;
  return { bps, amountMinor: Math.ceil((loan.principal_minor * bps) / 10_000) };
}

/** Whole days until the funding deadline on the platform's Europe/Zurich business date. */
export function daysUntil(dateKey: string | null | undefined, asOf?: string | null) {
  if (!dateKey) return null;
  const today = Date.parse(`${platformTodayKey(asOf)}T00:00:00Z`);
  const target = Date.parse(`${dateKey.slice(0, 10)}T00:00:00Z`);
  if (!Number.isFinite(today) || !Number.isFinite(target)) return null;
  return Math.max(0, Math.round((target - today) / 86_400_000));
}

/** The list view's closing line (design: "Closes in 7 days"). */
export function closesInLabel(days: number) {
  if (days <= 0) return t("Closes today");
  return days === 1 ? t("Closes in 1 day") : t("Closes in {count} days", { count: days });
}

export function daysLeftLabel(days: number) {
  if (days === 0) return t("Closes today");
  return days === 1 ? t("1 day left") : t("{count} days left", { count: days });
}

/**
 * Lots of the loan's currency that may fund this loan. Direct loans (F01, 18.4): the money must reach
 * the borrower by day 56, so the funding deadline must be on or before the lot's `direct_funding_until`.
 * Loan Originator rounds: the whole funding window before the lot's last day.
 */
export function eligibleLots(
  lots: BalanceLot[] | undefined,
  loan: Pick<MarketplaceLoanPreview, "currency" | "funding_deadline"> & { product_type?: string }
) {
  const direct = loan.product_type !== "originator_claim";
  return (lots ?? []).filter((lot) => {
    if (lot.currency !== loan.currency || lot.status !== "available" || lot.bucket !== "investable" || lot.available_amount_minor <= 0) return false;
    if (!loan.funding_deadline) return true;
    if (direct) return Boolean(lot.direct_funding_until) && loan.funding_deadline <= (lot.direct_funding_until as string);
    return loan.funding_deadline < lot.last_day;
  });
}

export function sumAvailableMinor(lots: BalanceLot[]) {
  return lots.reduce((total, lot) => total + lot.available_amount_minor, 0);
}

/** The read-only superadmin view can look at everything but never invest. */
export function isReadonlyView() {
  return Boolean(readReadonlyImpersonationToken());
}

// ---- Borrower disclosure ----------------------------------------------------------------------

export type DisclosureDocument = {
  id?: string;
  document_type?: string;
  display_name?: string;
  description?: string;
  category?: string;
  document_date?: string | null;
  period_label?: string;
  issuer?: string;
  version?: string;
  document_status?: string;
};

export type BorrowerDisclosure = {
  legal_name?: string;
  year_founded?: number;
  business_classification?: string;
  industry_activity?: string;
  registered_address?: string;
  contact_info?: string;
  country?: string;
  // U33-DEC-23: empty or null when the admin has not entered them; never shown as zero.
  city?: string;
  employees?: number | null;
  employees_year?: number | null;
  financials_currency?: string;
  assets_minor?: number;
  liabilities_minor?: number;
  revenue_last_year_minor?: number;
  profit_last_year_minor?: number;
  documents?: DisclosureDocument[];
};

export function borrowerDisclosure(loan: Pick<MarketplaceLoanDetail, "borrower_disclosure">): BorrowerDisclosure {
  const raw = loan.borrower_disclosure;
  return raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as BorrowerDisclosure) : {};
}

/** The company the claim is against: the borrower for a direct loan, the final borrower for a claim. */
export function borrowerName(loan: MarketplaceLoanPreview | MarketplaceLoanDetail) {
  const disclosed = "borrower_disclosure" in loan ? borrowerDisclosure(loan).legal_name : undefined;
  return disclosed || loan.borrower_display_name || "";
}

const countryNames: Record<string, string> = {
  AT: "Austria",
  BE: "Belgium",
  CH: "Switzerland",
  DE: "Germany",
  ES: "Spain",
  FR: "France",
  IT: "Italy",
  LI: "Liechtenstein",
  LU: "Luxembourg",
  NL: "Netherlands",
  PL: "Poland",
  PT: "Portugal",
  RO: "Romania"
};

/** "Switzerland" for "CH"; other values are shown as they are. */
export function countryName(code: string | null | undefined) {
  if (!code) return "";
  return t(countryNames[code.toUpperCase()] ?? code);
}

/** Design "Münsingen, Switzerland": the city when known (U33-DEC-23), then the country name. */
export function placeName(city: string | null | undefined, country: string | null | undefined) {
  return [city?.trim() ?? "", countryName(country)].filter(Boolean).join(", ");
}

// ---- U33 vocabulary ---------------------------------------------------------------------------

// Backend loans.CollateralType values with the design's security names and icons. Unknown values
// (older loans, free text) are shown as they are, with a neutral icon.
const collateralNames: Record<string, { label: string; icon: string; group: SecurityGroup }> = {
  real_estate: { label: "Property mortgage", icon: "building", group: "physical" },
  equipment: { label: "Equipment pledge", icon: "package", group: "physical" },
  inventory: { label: "Inventory pledge", icon: "package", group: "physical" },
  // Q15: vehicles have their own type.
  vehicle: { label: "Vehicle pledge", icon: "truck", group: "physical" },
  asset_backed: { label: "Asset-backed", icon: "package", group: "physical" },
  receivables: { label: "Rights to payments", icon: "file-text", group: "rights" },
  invoices: { label: "Invoices", icon: "file-text", group: "rights" },
  securities_pledge: { label: "Securities pledge", icon: "file-text", group: "rights" },
  share_pledge: { label: "Company share pledge", icon: "file-text", group: "rights" },
  cash_collateral: { label: "Cash collateral", icon: "wallet", group: "rights" },
  personal_guarantee: { label: "Personal guarantee", icon: "user", group: "guarantees" },
  corporate_guarantee: { label: "Company guarantee", icon: "building", group: "guarantees" },
  mixed_collateral: { label: "Mixed collateral", icon: "layers", group: "other" },
  other: { label: "Other security", icon: "file-text", group: "other" },
  // Platform rule until U33-DEC-38 closes the exception for new loans (Phase 17.2).
  unsecured_exception: { label: "No collateral", icon: "alert-circle", group: "other" }
};

export type SecurityGroup = "physical" | "rights" | "guarantees" | "other";

export const securityGroupLabels: Record<SecurityGroup, string> = {
  physical: "Physical assets",
  rights: "Payment rights & shares",
  guarantees: "Guarantees",
  other: "Other"
};

function humanize(value: string) {
  const text = value.replace(/_/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export function collateralLabel(type: string) {
  const known = collateralNames[type];
  if (known) return t(known.label);
  if (/unsecured/i.test(type)) return t("No collateral");
  return humanize(type);
}

// Design explanation of a security (the "i" next to Security on the cards: securityHelp).
const securityHelpTexts: Record<string, string> = {
  real_estate: "The property can be sold to recover unpaid debt if the borrower defaults.",
  equipment: "The equipment can be sold to recover unpaid debt if the borrower defaults.",
  vehicle: "The vehicles can be sold to recover unpaid debt if the borrower defaults.",
  share_pledge: "The pledged shares can be sold to recover unpaid debt if the borrower defaults.",
  invoices: "Customer invoice payments can be collected to recover unpaid debt if the borrower defaults."
};

export function securityHelpText(type: string) {
  const text = securityHelpTexts[type];
  return text ? t(text) : "";
}

/** Design general explanation of Security (vocabulary security). */
export function securityVocabText() {
  return t("Assets or rights provided to support repayment if the borrower defaults. Depending on the opportunity, these may include real estate, rights to payments (receivables), or a guarantee. A corporate guarantee is a commitment by a company to meet the covered obligations if the borrower does not. The Credit file explains the specific security and its limitations. Security does not guarantee recovery.");
}

/** Design "Existing claim" explanation (vocabulary existingClaim). */
export function existingClaimHelp() {
  return t("You acquire the right to receive a share of payments under an existing loan, lease or invoice.");
}

/**
 * The payment line under the term (design paymentLabel): every repayment type of the platform pays
 * monthly except a full bullet; none for a loan in default.
 */
export function paymentFrequencyLabel(repaymentType: string | null | undefined, loanStatus?: string, frequency?: string | null) {
  if (!repaymentType || loanStatus === "defaulted" || loanStatus === "written_off") return "";
  if (AT_MATURITY_REPAYMENTS.has(repaymentType)) return t("Payment at maturity");
  if (repaymentType === "custom_schedule") return t("Custom schedule");
  return PERIODIC_REPAYMENTS.has(repaymentType) ? t("{frequency} payments", { frequency: frequencyWords(frequency).adjective }) : "";
}

/** One payment at maturity: the 18.6 type full_at_maturity ("bullet" in older records and previews). */
const AT_MATURITY_REPAYMENTS = new Set(["full_at_maturity", "bullet"]);

/** Repayment types with periodic payments (interest, or principal and interest). */
const PERIODIC_REPAYMENTS = new Set(["equal_installments", "amortizing_principal_interest", "bullet_periodic_interest", "interest_only_then_bullet", "interest_only_then_amortizing"]);

/**
 * 18.6 (Q08): the words of a loan's payment frequency (monthly, quarterly, half-yearly, yearly;
 * monthly when the API sends none, as every older loan).
 */
export function frequencyWords(frequency?: string | null) {
  switch (frequency) {
    case "quarterly":
      return { adjective: t("Quarterly"), adverb: t("quarterly") };
    case "half_yearly":
      return { adjective: t("Half-yearly"), adverb: t("half-yearly") };
    case "annual":
      return { adjective: t("Yearly"), adverb: t("yearly") };
    default:
      return { adjective: t("Monthly"), adverb: t("monthly") };
  }
}

/** The payment line of Review & sign (design repaymentCopy). */
export function reviewRepaymentCopy(repaymentType: string | null | undefined, frequency?: string | null) {
  const words = frequencyWords(frequency);
  switch (repaymentType) {
    case "equal_installments":
    case "amortizing_principal_interest":
      return t("{frequency} principal and interest payments.", { frequency: words.adjective });
    case "bullet_periodic_interest":
    case "interest_only_then_bullet":
      return t("{frequency} interest payments; principal at maturity.", { frequency: words.adjective });
    case "full_at_maturity":
    case "bullet":
      return t("Principal and interest at maturity.");
    default:
      return t("Your share of each installment.");
  }
}

export function collateralIcon(type: string) {
  return collateralNames[type]?.icon ?? (/estate|property|building/i.test(type) ? "building" : "file-text");
}

export function collateralGroup(type: string): SecurityGroup {
  if (collateralNames[type]) return collateralNames[type].group;
  if (/unsecured/i.test(type)) return "other";
  if (/estate|property|land|building/i.test(type)) return "physical";
  if (/equipment|machinery|vessel|plant|vehicle/i.test(type)) return "physical";
  if (/receivable|invoice|share|securit/i.test(type)) return "rights";
  if (/guarantee/i.test(type)) return "guarantees";
  return "other";
}

/** Tile icon of a project (design: the black square with a pictogram). */
export function projectIcon(loan: Pick<MarketplaceLoanPreview, "product_type" | "collateral_type">) {
  if (isOriginatorClaimLoan(loan)) return "file-text";
  const icon = collateralIcon(loan.collateral_type);
  return icon === "alert-circle" || icon === "user" ? "briefcase" : icon;
}

/** Design line under the terms ("Principal and interest paid monthly"), with the loan's frequency (18.6). */
export function repaymentText(repaymentType: string | null | undefined, frequency?: string | null) {
  const words = frequencyWords(frequency);
  switch (repaymentType) {
    case "equal_installments":
    case "amortizing_principal_interest":
      return t("Principal and interest paid {frequency}", { frequency: words.adverb });
    case "bullet_periodic_interest":
    case "interest_only_then_bullet":
      return t("Interest paid {frequency}; principal at the end", { frequency: words.adverb });
    case "interest_only_then_amortizing":
      return t("Interest only at first, then principal and interest {frequency}", { frequency: words.adverb });
    case "full_at_maturity":
    case "bullet":
      return t("Principal and interest at maturity");
    case "custom_schedule":
      return t("Payments on the loan's own schedule");
    default:
      return repaymentType ? humanize(repaymentType) : "";
  }
}

/** Short cadence for cards and toggles ("Monthly payments"), with the loan's frequency (18.6). */
export function repaymentCadence(repaymentType: string | null | undefined, frequency?: string | null) {
  return repaymentType && PERIODIC_REPAYMENTS.has(repaymentType) ? t("{frequency} payments", { frequency: frequencyWords(frequency).adjective }) : "";
}

/** "New loan" / "Existing claim" (design type tag); refinancing loans are named as such. */
export function loanTypeLabel(loan: Pick<MarketplaceLoanPreview, "product_type" | "is_refinancing">) {
  if (isOriginatorClaimLoan(loan)) return t("Existing claim");
  return loan.is_refinancing ? t("Refinancing loan") : t("New loan");
}

/** Loan-to-value as the design shows it: a whole percentage ("58%"). */
export function formatLtv(bps: number) {
  return formatPercent(bps / 100, 0);
}

export function loanLtv(loan: MarketplaceLoanPreview | MarketplaceLoanDetail) {
  return loanLtvBps({
    ...loan,
    collateral_value_minor: "collateral_value_minor" in loan ? loan.collateral_value_minor : undefined
  });
}

// ---- Swiss-borrower places (MKT-DEC-028, today's rule until U33-DEC-08 / Phase 17.7) -------------

export type PlacesInfo = { maxInvestors: number; placesLeft: number; investors: number; fullForViewer: boolean; existingInvestor: boolean };

export function placesInfo(loan: Pick<MarketplaceLoanPreview, "max_investors" | "places_left" | "is_existing_investor">): PlacesInfo | null {
  if (typeof loan.max_investors !== "number") return null;
  const placesLeft = loan.places_left ?? 0;
  const existingInvestor = loan.is_existing_investor === true;
  return {
    maxInvestors: loan.max_investors,
    placesLeft,
    investors: Math.max(0, loan.max_investors - placesLeft),
    fullForViewer: placesLeft === 0 && !existingInvestor,
    existingInvestor
  };
}

// ---- Holdings ---------------------------------------------------------------------------------

/** The investor's active holding of a loan, if any (link "Your investment"). */
export function holdingForLoan(holdings: Holding[] | undefined, loanId: string) {
  return (holdings ?? []).find((holding) => holding.loan.loan_id === loanId && holding.status !== "transferred");
}

// ---- 18.7: price of a Loan Originator offer (principal + accrued interest) ----------------------

/**
 * The accrued interest of the rights bought with `principalMinor` (Q09, F02), exactly like the
 * server: round half up(interest x principal / opening principal x accrued units / period units
 * x participation / 10000), in whole integers (BigInt). 0 when the offer has no accrued price.
 */
export function offerAccruedInterestMinor(loan: Pick<MarketplaceLoanDetail, "offer_price"> & { product_type?: string }, principalMinor: number) {
  const price = offerPriceFacts(loan);
  if (!price || principalMinor <= 0 || price.period_day_units <= 0 || price.next_installment_opening_principal_minor <= 0) return 0;
  const numerator =
    BigInt(price.next_installment_interest_minor) *
    BigInt(Math.round(principalMinor)) *
    BigInt(price.accrued_day_units) *
    BigInt(price.investor_interest_participation_bps);
  const denominator = BigInt(price.next_installment_opening_principal_minor) * BigInt(price.period_day_units) * 10000n;
  return Number((2n * numerator + denominator) / (2n * denominator));
}

/** The 18.7 price facts of a Loan Originator offer, or null (Direct loans and par offers). */
export function offerPriceFacts(loan: Pick<MarketplaceLoanDetail, "offer_price"> & { product_type?: string }) {
  const price = loan.offer_price;
  if (!price || price.pricing_rule !== "accrued_interest") return null;
  if (loan.product_type !== undefined && loan.product_type !== "originator_claim") return null;
  return price;
}

/** What the investor pays for `principalMinor`: the principal plus the accrued interest in the price. */
export function offerPriceMinor(loan: Pick<MarketplaceLoanDetail, "offer_price"> & { product_type?: string }, principalMinor: number) {
  return principalMinor + offerAccruedInterestMinor(loan, principalMinor);
}

// ---- The investor's share of the schedule -------------------------------------------------------

export type ScheduleShareRow = {
  installment: number;
  dueDate: string;
  principalMinor: number;
  interestMinor: number;
  penaltyMinor: number;
  totalMinor: number;
  owedAfterMinor: number;
};

export type ScheduleShare = {
  basis: "direct" | "subscription" | "quoted" | "unavailable";
  rows: ScheduleShareRow[];
  principalMinor: number;
  interestMinor: number;
  penaltyMinor: number;
  totalMinor: number;
};

/**
 * The investor's projected share of the contracted schedule, mirroring the backend entitlement:
 * direct loans pay the investor's share of the financeable principal of each installment; Loan
 * Originator subscriptions entitle only rows after the boundary installment, with the declared
 * interest and penalty participation. Legacy claims are priced by a quote instead.
 */
export function scheduleShare(detail: MarketplaceLoanDetail, amountMinor: number): ScheduleShare {
  const empty = (basis: ScheduleShare["basis"]): ScheduleShare => ({ basis, rows: [], principalMinor: 0, interestMinor: 0, penaltyMinor: 0, totalMinor: 0 });
  if (amountMinor <= 0) return empty("unavailable");
  if (usesImmediateClaimAssignment(detail)) return empty("quoted");
  const subscription = usesOriginatorSubscription(detail);
  const boundary = detail.entitlement_start_date ?? null;
  const source = subscription
    ? (detail.originator_schedule ?? [])
        .filter((row) => !boundary || row.due_date > boundary)
        .map((row) => ({ installment: row.installment_number, dueDate: row.due_date, opening: Math.max(1, row.opening_principal_minor), principal: row.principal_minor, interest: row.interest_minor, penalty: row.penalty_minor }))
    : (detail.loan_schedule ?? [])
        .filter((row) => row.row_type !== "repayment_event")
        .map((row) => ({ installment: row.installment_number, dueDate: row.due_date, opening: Math.max(1, detail.principal_minor), principal: row.principal_minor, interest: row.interest_minor, penalty: 0 }));
  if (source.length === 0) return empty("unavailable");
  const interestParticipation = subscription ? (detail.investor_interest_participation_bps ?? 0) : 10_000;
  const penaltyParticipation = subscription ? (detail.investor_penalty_participation_bps ?? 0) : 10_000;
  const rows: ScheduleShareRow[] = [];
  let remaining = amountMinor;
  let interestTotal = 0;
  let penaltyTotal = 0;
  source.forEach((row, index) => {
    const share = BigInt(subscription ? remaining : amountMinor);
    const denominator = BigInt(row.opening) * 10_000n;
    const part = (component: number, participation = 10_000) => {
      const numerator = BigInt(component) * share * BigInt(participation);
      return Number((numerator * 2n + denominator) / (denominator * 2n));
    };
    const principal = index === source.length - 1 ? remaining : Math.min(remaining, part(row.principal));
    const interest = part(row.interest, interestParticipation);
    const penalty = part(row.penalty, penaltyParticipation);
    remaining -= principal;
    interestTotal += interest;
    penaltyTotal += penalty;
    rows.push({ installment: row.installment, dueDate: row.dueDate, principalMinor: principal, interestMinor: interest, penaltyMinor: penalty, totalMinor: principal + interest + penalty, owedAfterMinor: Math.max(0, remaining) });
  });
  return {
    basis: subscription ? "subscription" : "direct",
    rows,
    principalMinor: amountMinor,
    interestMinor: interestTotal,
    penaltyMinor: penaltyTotal,
    totalMinor: amountMinor + interestTotal + penaltyTotal
  };
}

/** Rows of the full loan schedule shown on the opportunity page (borrower's installments). */
export function fullLoanSchedule(detail: MarketplaceLoanDetail) {
  if (isOriginatorClaimLoan(detail)) {
    return (detail.originator_schedule ?? []).map((row) => ({
      key: `${row.installment_number}-${row.due_date}`,
      dueDate: row.due_date,
      principalMinor: row.principal_minor,
      interestMinor: row.interest_minor,
      totalMinor: row.total_minor
    }));
  }
  return (detail.loan_schedule ?? [])
    .filter((row) => row.row_type !== "repayment_event")
    .map((row) => ({
      key: row.id ?? String(row.installment_number),
      dueDate: row.due_date,
      principalMinor: row.principal_minor,
      interestMinor: row.interest_minor,
      totalMinor: row.total_minor
    }));
}
