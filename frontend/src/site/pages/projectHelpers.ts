// IP of Webby-Soft SRL.
/*
 * Helpers of the Projects, Project and Statistics pages (design: pages_home.js FILTERS,
 * projectsList, simulate, calcResult; core.js expectedInterest). Pure functions and the
 * remembered filter choice; the components live in Projects.tsx, Project.tsx and Statistics.tsx.
 */
import { humanizeEnum } from "../../investorPortal/format";
import type { PublicProject } from "../data";
import { dateKey, parseAmount, plan, round2, siteToday, type PlanRepayment } from "../format";
import type { ProjectView } from "../projects";

// ---------------------------------------------------------------------------------------------
// Filters of the projects list (design FILTERS). The API has no "coming soon" status: Coming soon
// counts the open projects that are not published yet (projectView isSoon), which only the
// preview fixtures have; with live data it is always 0.

export type FilterStatus = "open" | "soon" | "funded" | "all";
export type FilterCurrency = "all" | "CHF" | "EUR";
export type ProjectFilters = { status: FilterStatus; currency: FilterCurrency };

export const PROJECT_FILTERS: { id: FilterStatus; label: string; test: (view: ProjectView) => boolean }[] = [
  { id: "open", label: "Open", test: (view) => view.isOpen },
  { id: "soon", label: "Coming soon", test: (view) => view.isSoon },
  { id: "funded", label: "Funded", test: (view) => !view.isOpen && !view.isSoon },
  { id: "all", label: "All", test: () => true }
];

export const CURRENCY_OPTIONS: [FilterCurrency, string][] = [
  ["all", "All currencies"],
  ["CHF", "CHF · Switzerland"],
  ["EUR", "EUR · EU"]
];

export const DEFAULT_FILTERS: ProjectFilters = { status: "open", currency: "all" };

function isFilterStatus(value: unknown): value is FilterStatus {
  return PROJECT_FILTERS.some((filter) => filter.id === value);
}

function isFilterCurrency(value: unknown): value is FilterCurrency {
  return CURRENCY_OPTIONS.some(([id]) => id === value);
}

/** The projects of a filter, open first, then the newest published (design projectsList). */
export function filterProjects(views: ProjectView[], filters: ProjectFilters) {
  const filter = PROJECT_FILTERS.find((item) => item.id === filters.status) ?? PROJECT_FILTERS[0];
  const key = (view: ProjectView) => view.p.published_at ?? view.p.funded_at ?? "";
  return views
    .filter(filter.test)
    .filter((view) => filters.currency === "all" || view.p.currency === filters.currency)
    .sort((a, b) => (a.isOpen === b.isOpen ? key(b).localeCompare(key(a)) : a.isOpen ? -1 : 1));
}

export function hasFilterQuery(query: URLSearchParams) {
  return query.has("status") || query.has("currency");
}

/** "?status=funded&currency=EUR" applied to the current filters (unknown values are ignored). */
export function filtersFromQuery(query: URLSearchParams, current: ProjectFilters): ProjectFilters {
  const status = query.get("status");
  const currency = query.get("currency");
  return {
    status: isFilterStatus(status) ? status : current.status,
    currency: isFilterCurrency(currency) ? currency : current.currency
  };
}

// The choice is kept for the browser tab, like the design keeps it in its state: coming back
// from a project page shows the same list.
const FILTERS_KEY = "bxm-site-project-filters";

export function readProjectFilters(): ProjectFilters {
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(FILTERS_KEY) ?? "null") as Partial<ProjectFilters> | null;
    return {
      status: isFilterStatus(stored?.status) ? stored.status : DEFAULT_FILTERS.status,
      currency: isFilterCurrency(stored?.currency) ? stored.currency : DEFAULT_FILTERS.currency
    };
  } catch {
    return DEFAULT_FILTERS;
  }
}

export function saveProjectFilters(filters: ProjectFilters) {
  try {
    window.sessionStorage.setItem(FILTERS_KEY, JSON.stringify(filters));
  } catch {
    // Storage blocked: the choice lasts until the page is left.
  }
}

// ---------------------------------------------------------------------------------------------
// Interest calculators (display only, major units like the design): the loans' own schedule
// (format.ts plan: daily interest, actual/365), every payment on time.

/** Largest amount the calculator reads (design calcRead). */
export const CALC_MAX_AMOUNT = 10000000;

/** The calculator's amount field -> a positive amount, or 0 (design calcRead). */
export function calcAmount(text: string) {
  const amount = parseAmount(text);
  return Number.isNaN(amount) || amount <= 0 ? 0 : Math.min(amount, CALC_MAX_AMOUNT);
}

/**
 * The plan() repayment of a RepaymentType, the same grouping as projects.ts repaymentShort:
 * monthly instalments (annuity), monthly interest (interest-only), at the end (bullet).
 */
export function planRepaymentOf(repaymentType: string): PlanRepayment {
  switch (repaymentType) {
    case "bullet_periodic_interest":
      return "interest-only";
    case "interest_only_then_bullet":
      return "bullet";
    default:
      return "annuity";
  }
}

export type CalcRow = { principal: number; interest: number };

/** Design simulate(): the plan from today, one bar per month (also for loans paid at the end). */
export function simulate(amount: number, rate: number, term: number, repayment: PlanRepayment, start = siteToday()) {
  const planned = plan({ rate, term, repayment }, amount, start);
  const rows: CalcRow[] =
    repayment === "bullet"
      ? Array.from({ length: term - 1 }, () => ({ principal: 0, interest: 0 })).concat(planned)
      : planned;
  const interest = round2(planned.reduce((sum, row) => sum + row.interest, 0));
  return { rows, interest, total: round2(amount + interest), first: planned[0]?.total ?? 0 };
}

/**
 * Interest of a new investment from the end of the funding period, if every payment is on time
 * (design core.js expectedInterest). Amount in major units.
 */
export function expectedInterest(p: PublicProject, amount: number, today = siteToday()) {
  const start = dateKey(p.funding_deadline) || today;
  const terms = { rate: p.interest_rate_bps / 100, term: p.term_months, repayment: planRepaymentOf(p.repayment_type) };
  return round2(plan(terms, amount, start).reduce((sum, row) => sum + row.interest, 0));
}

// ---------------------------------------------------------------------------------------------
// Project page labels for the API's values (the backend's choice labels).

const COLLATERAL_LABELS: Record<string, string> = {
  real_estate: "Real estate",
  corporate_guarantee: "Corporate guarantee",
  personal_guarantee: "Personal guarantee",
  receivables: "Receivables",
  invoices: "Invoices",
  equipment: "Equipment",
  inventory: "Inventory",
  securities_pledge: "Securities pledge",
  cash_collateral: "Cash collateral",
  share_pledge: "Share pledge",
  asset_backed: "Asset backed",
  mixed_collateral: "Mixed collateral",
  unsecured_exception: "Unsecured exception",
  other: "Other"
};

const PURPOSE_LABELS: Record<string, string> = {
  working_capital: "Working capital",
  liquidity: "Liquidity",
  refinancing: "Refinancing",
  debt_consolidation: "Debt consolidation",
  acquisition: "Acquisition",
  bridge_financing: "Bridge financing",
  project_finance: "Project finance",
  corporate_project_finance: "Corporate project finance",
  capex: "Capex / business expansion",
  development: "Development",
  inventory_trade_finance: "Inventory or trade finance",
  other: "Other"
};

export function collateralLabel(collateralType: string) {
  return COLLATERAL_LABELS[collateralType] ?? humanizeEnum(collateralType);
}

/** The security line: the project's own text, else the collateral type. */
export function securityText(p: Pick<PublicProject, "collateral_description" | "collateral_type">) {
  return p.collateral_description.trim() || collateralLabel(p.collateral_type);
}

/** "Use of the money": one item per line of the description, else the purpose's label. */
export function purposeItems(p: Pick<PublicProject, "purpose_description" | "purpose">) {
  const lines = p.purpose_description
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length) return lines;
  return [PURPOSE_LABELS[p.purpose] ?? humanizeEnum(p.purpose)].filter(Boolean);
}

/** 6200 -> "62%"; null -> "Not applicable" (design: p.ltv ? p.ltv + "%" : ...). */
export function ltvText(ltvBps: number | null) {
  return ltvBps ? `${ltvBps / 100}%` : "Not applicable";
}
