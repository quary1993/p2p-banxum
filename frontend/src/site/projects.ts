// IP of Webby-Soft SRL.
/*
 * Projects as the public site shows them: the design's helpers (shell.js / core.js statusOf,
 * timeText, securityShort, repaymentShort, recordTag) applied to the API's PublicProject.
 *
 * Differences with the design data, by necessity:
 * - The API has no city: places read "Country · Sector" (or "Country" without a public sector).
 * - The API has no "coming soon" status: a coming-soon project is an "open" project whose
 *   published_at is still after today (only the preview fixtures have such projects for now).
 */
import type { PublicProject } from "./data";
import { dateKey, dateShort, daysBetween, siteToday } from "./format";

const COUNTRY_NAMES: Record<string, string> = {
  CH: "Switzerland",
  DE: "Germany",
  AT: "Austria",
  RO: "Romania",
  IT: "Italy",
  FR: "France",
  LI: "Liechtenstein"
};

/** "CH" -> "Switzerland" (the design's names, then the browser's English names). */
export function countryName(code: string) {
  const value = (code || "").trim().toUpperCase();
  if (!value) return "";
  if (COUNTRY_NAMES[value]) return COUNTRY_NAMES[value];
  if (/^[A-Z]{2}$/.test(value) && typeof Intl.DisplayNames === "function") {
    try {
      return new Intl.DisplayNames(["en"], { type: "region" }).of(value) ?? value;
    } catch {
      return value;
    }
  }
  return value;
}

export type ProjectView = {
  p: PublicProject;
  /** Open and not yet published: "Coming soon". */
  isSoon: boolean;
  /** Open for investment now (the design's p.isOpen). */
  isOpen: boolean;
  /** Funded so far, in % of the amount (unrounded, like the design). */
  percent: number;
  /** Days until the funding deadline (null without a deadline). */
  daysLeft: number | null;
  countryName: string;
};

export function projectView(p: PublicProject, today = siteToday()): ProjectView {
  const published = dateKey(p.published_at);
  const isSoon = p.public_status === "open" && Boolean(published) && published > today;
  // A Swiss-borrower loan with all 20 places taken is closed to new investors (MKT-DEC-028),
  // like the design's placesLeft check.
  const hasPlace = p.places_left === undefined || p.places_left === null || p.places_left > 0;
  const isOpen = p.public_status === "open" && !isSoon && p.remaining_capacity_minor > 0 && hasPlace;
  const percent = p.principal_minor > 0 ? (p.committed_principal_minor / p.principal_minor) * 100 : 0;
  const deadline = dateKey(p.funding_deadline);
  return {
    p,
    isSoon,
    isOpen,
    percent,
    daysLeft: deadline ? daysBetween(today, deadline) : null,
    countryName: countryName(p.borrower_country)
  };
}

/** Open projects, most funded first (Home carousel and "Open now"). */
export function openProjects(views: ProjectView[]) {
  return views.filter((v) => v.isOpen).sort((a, b) => b.percent - a.percent);
}

/** Projects opening soon, the next one to open first. */
export function soonProjects(views: ProjectView[]) {
  return views
    .filter((v) => v.isSoon)
    .sort((a, b) => (a.p.published_at ?? "").localeCompare(b.p.published_at ?? ""));
}

export type StatusLabel = { label: string; cls: string };

/**
 * Status tag of a project card (design statusOf): open green, funding finished black, default
 * red, coming soon neutral. A late loan shows "Repaying" here, like the design's cards; its
 * project page shows the record tag ("Late 12 days").
 */
export function statusOf(v: ProjectView): StatusLabel {
  const status = v.p.public_status;
  if (v.isSoon) return { label: "Coming soon", cls: "" };
  if (status === "open" && v.isOpen) return { label: "Open", cls: "is-open" };
  if (status === "open" || status === "fully_funded") return { label: "Fully funded", cls: "is-solid" };
  if (status === "repaying" || status === "late") return { label: "Repaying", cls: "is-solid" };
  if (status === "repaid") return { label: "Repaid", cls: "is-solid" };
  if (status === "default") return { label: "Default", cls: "is-default" };
  return { label: status, cls: "is-solid" };
}

/** "Opens 29 Sep", "9 days left", "Closes today", "Fully funded" or "Funding closed". */
export function timeText(v: ProjectView) {
  if (v.isSoon) return `Opens ${dateShort(dateKey(v.p.published_at))}`;
  if (v.isOpen) return v.daysLeft === null ? "" : v.daysLeft <= 0 ? "Closes today" : `${v.daysLeft} days left`;
  if (v.p.public_status === "open" || v.p.public_status === "fully_funded") return "Fully funded";
  return "Funding closed";
}

/**
 * Short security label (design securityShort). The design reads the security text; the API has
 * the same text in collateral_description, and a CollateralType value as a fallback.
 */
export function securityShort(p: Pick<PublicProject, "collateral_description" | "collateral_type">) {
  const s = p.collateral_description || "";
  if (/^First-rank mortgage/i.test(s)) return "1st-rank mortgage";
  if (/^Second-rank mortgage/i.test(s)) return "2nd-rank mortgage";
  if (/^Chattel mortgage/i.test(s)) return "Chattel mortgage";
  if (/^Mortgage/i.test(s)) return "Mortgage note";
  if (/^Assignment/i.test(s)) return "Receivables";
  if (/^Pledge/i.test(s)) return "Pledge";
  if (/guarantee/i.test(s)) return "Guarantee";
  switch (p.collateral_type) {
    case "real_estate":
      return "Mortgage note";
    case "receivables":
    case "invoices":
      return "Receivables";
    case "equipment":
    case "inventory":
    case "securities_pledge":
    case "share_pledge":
    case "cash_collateral":
    case "asset_backed":
      return "Pledge";
    case "corporate_guarantee":
    case "personal_guarantee":
      return "Guarantee";
    default:
      return "See project";
  }
}

/**
 * Short repayment label (design repaymentShort: annuity, interest-only, bullet) for our
 * RepaymentType values.
 */
export function repaymentShort(p: Pick<PublicProject, "repayment_type">) {
  switch (p.repayment_type) {
    case "equal_installments":
    case "amortizing_principal_interest":
    case "interest_only_then_amortizing":
      return "Monthly instalments";
    case "bullet_periodic_interest":
      return "Monthly interest";
    case "interest_only_then_bullet":
      return "At the end";
    default:
      return "";
  }
}

/** Repayment status tag of a funded loan (design recordTag), or null before funding ends. */
export function recordTag(p: PublicProject): StatusLabel | null {
  if (!p.record) return null;
  if (p.public_status === "late") return { label: `Late ${p.record.days_past_due} days`, cls: "is-late" };
  if (p.public_status === "default") return { label: "Default", cls: "is-default" };
  if (p.public_status === "repaid") return { label: "Repaid", cls: "is-solid" };
  return { label: "Repaying", cls: "is-solid" };
}

/** "Switzerland · Manufacturing" (the design shows "City, Country · Sector"; the API has no city). */
export function placeLine(v: ProjectView) {
  return v.p.borrower_sector ? `${v.countryName} · ${v.p.borrower_sector}` : v.countryName;
}
