// IP of Webby-Soft SRL.
/*
 * Data of the public site: the API contract types (public site API contract, 2026-10-15) and
 * the hooks every site page uses. ALL calls of the site's anonymous endpoints live in this file.
 *
 * - Preview mode (isFixturePreview: VITE_PREVIEW=true or tests): the hooks return the fixtures
 *   generated from the design's sample data (siteFixtures.ts), and mutations resolve after a
 *   short delay with a fake answer. Production builds alias siteFixtures.ts to
 *   siteFixtures.empty.ts (vite.config.ts).
 * - Live mode: the contract URLs through the app's http client.
 *
 * The main session will later swap the live calls to the generated orval hooks: keep the hook
 * names and their return shapes (react-query results) stable.
 */
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiClientError, httpClient } from "../api/client/httpClient";
import type {
  PublicEnquiryCreated as GeneratedPublicEnquiryCreated,
  PublicOriginator as GeneratedPublicOriginator,
  PublicProject as GeneratedPublicProject,
  PublicStatistics as GeneratedPublicStatistics,
  PublicStatisticsCurrency as GeneratedPublicStatisticsCurrency
} from "../api/generated/banxumApi";
import { isFixturePreview } from "../investorPortal/data";
import { siteOriginatorsFixture, siteProjectsFixture, siteStatisticsFixture } from "./siteFixtures";

// ---------------------------------------------------------------------------------------------
// Contract types

export type PublicProjectStatus = "open" | "fully_funded" | "repaying" | "late" | "repaid" | "default";

export interface PublicProjectRecord {
  installments_total: number;
  installments_paid: number;
  principal_repaid_minor: number;
  interest_paid_minor: number;
  outstanding_principal_minor: number;
  /** 0 unless late or defaulted. */
  days_past_due: number;
  defaulted_on: string | null;
  /** The admin's public loan note, if any, else "". */
  public_note: string;
}

export interface PublicProject {
  loan_id: string;
  /** Loan title. Never the borrower's name. */
  title: string;
  product_type: "direct" | "originator_claim";
  is_refinancing: boolean;
  public_status: PublicProjectStatus;
  currency: "CHF" | "EUR";
  principal_minor: number;
  committed_principal_minor: number;
  /** 0 unless open. */
  remaining_capacity_minor: number;
  /** What a new investor must invest now; null when not open. */
  minimum_investment_minor: number | null;
  investors_count: number;
  /** 20 for Swiss-borrower loans (MKT-DEC-028), null when no limit applies. */
  max_investors?: number | null;
  /** Places left for new investors; null when no limit applies. 0: closed to new investors. */
  places_left?: number | null;
  interest_rate_bps: number;
  term_months: number;
  /** RepaymentType value. */
  repayment_type: string;
  /** RiskRating value. */
  risk_rating: string;
  /** CollateralType value. */
  collateral_type: string;
  collateral_description: string;
  ltv_bps: number | null;
  /** LoanPurpose value. */
  purpose: string;
  purpose_description: string;
  investor_summary: string;
  /** ISO 3166-1 alpha-2 when known, else "". */
  borrower_country: string;
  /** Only when the borrower's classification is public, else "". */
  borrower_sector: string;
  borrower_year_founded: number | null;
  originator: null | { id: string; name: string; country: string };
  published_at: string | null;
  funding_deadline: string | null;
  /** Funding close date (null while open). */
  funded_at: string | null;
  /** Only for repaying / late / repaid / default. */
  record: PublicProjectRecord | null;
}

export interface PublicStatisticsCurrency {
  currency: "CHF" | "EUR";
  loans: number;
  lent_minor: number;
  principal_repaid_minor: number;
  interest_paid_minor: number;
  /** Outstanding principal of loans not in default. */
  outstanding_minor: number;
  /** Outstanding principal of loans in default. */
  defaulted_minor: number;
}

export interface PublicStatistics {
  as_of: string;
  loans_funded: number;
  loans_repaid: number;
  loans_late: number;
  loans_defaulted: number;
  average_interest_rate_bps: number | null;
  originators_count: number;
  countries_count: number;
  /** Always both CHF and EUR rows. */
  by_currency: PublicStatisticsCurrency[];
}

export interface PublicOriginator {
  id: string;
  name: string;
  country: string;
  partner_since: string;
  claims_funded: number;
}

export type NewsletterSource = "home" | "projects" | "guides" | "other";

export interface NewsletterSubscribeBody {
  email: string;
  source: NewsletterSource;
  /** Honeypot: always empty for people. */
  website?: string;
}

export interface NewsletterTokenBody {
  token: string;
}

export type EnquiryKind = "company" | "originator" | "contact";

/** Field names per kind (contract section 5). All values are trimmed strings. */
export interface CompanyEnquiryFields {
  company_name: string;
  country: string;
  company_number: string;
  amount: string;
  term: string;
  purpose: string;
  security: string;
  revenue?: string;
  founded: string;
  about?: string;
  contact_name: string;
  role: string;
  email: string;
  phone: string;
}

export interface OriginatorEnquiryFields {
  company_name: string;
  country: string;
  licence: string;
  product: string;
  loan_book: string;
  about?: string;
  contact_name: string;
  email: string;
}

export interface ContactEnquiryFields {
  name: string;
  email: string;
  topic: string;
  message: string;
}

export type EnquiryBody =
  | { kind: "company"; fields: CompanyEnquiryFields; consent: true; website?: string; elapsed_ms?: number }
  | { kind: "originator"; fields: OriginatorEnquiryFields; consent: true; website?: string; elapsed_ms?: number }
  | { kind: "contact"; fields: ContactEnquiryFields; consent: true; website?: string; elapsed_ms?: number };

export interface EnquiryResponse {
  /** "APP-2026-0143", "PAR-2026-0007" or "MSG-2026-0412". */
  reference: string;
}

// The local types above narrow a few strings (currency) for the pages. These checks fail the
// type check if the backend's generated types drift from them.
type Assignable<From, To> = From extends To ? true : never;
type WithoutCurrency<T> = Omit<T, "currency">;
export const siteContractChecks: [
  Assignable<WithoutCurrency<GeneratedPublicProject>, WithoutCurrency<PublicProject>>,
  Assignable<WithoutCurrency<GeneratedPublicStatisticsCurrency>, WithoutCurrency<PublicStatisticsCurrency>>,
  Assignable<Omit<GeneratedPublicStatistics, "by_currency">, Omit<PublicStatistics, "by_currency">>,
  Assignable<GeneratedPublicOriginator, PublicOriginator>,
  Assignable<GeneratedPublicEnquiryCreated, EnquiryResponse>
] = [true, true, true, true, true];

// ---------------------------------------------------------------------------------------------
// URLs (contract)

const PROJECTS_URL = "/api/v1/marketplace/primary/public/projects/";
const STATISTICS_URL = "/api/v1/marketplace/primary/public/statistics/";
const ORIGINATORS_URL = "/api/v1/marketplace/primary/public/originators/";
const SUBSCRIBE_URL = "/api/v1/public/newsletter/subscribe/";
const CONFIRM_URL = "/api/v1/public/newsletter/confirm/";
const UNSUBSCRIBE_URL = "/api/v1/public/newsletter/unsubscribe/";
const ENQUIRIES_URL = "/api/v1/public/enquiries/";

export const siteQueryKeys = {
  projects: (limit: number) => ["site", "public-projects", { limit }] as const,
  project: (loanId: string) => ["site", "public-project", loanId] as const,
  statistics: ["site", "public-statistics"] as const,
  originators: ["site", "public-originators"] as const
};

// Preview data never refetches; live data is fresh for a minute (the server caches 60 s too).
function queryOptions<T>(fixture: T) {
  return isFixturePreview
    ? { enabled: false, initialData: fixture, staleTime: Infinity, retry: false as const }
    : { staleTime: 60_000, retry: 1 };
}

const PREVIEW_DELAY_MS = 600;

function previewAnswer<T>(value: T): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(value), PREVIEW_DELAY_MS));
}

function postJson<T>(url: string, data: unknown) {
  return httpClient<T>({ url, method: "POST", data });
}

// ---------------------------------------------------------------------------------------------
// Queries

/** Every project a visitor may see (open first). */
export function usePublicProjects(limit = 250) {
  return useQuery<PublicProject[]>({
    queryKey: siteQueryKeys.projects(limit),
    queryFn: ({ signal }) => httpClient<PublicProject[]>({ url: PROJECTS_URL, method: "GET", params: { limit }, signal }),
    ...queryOptions(siteProjectsFixture)
  });
}

/** One public project; the query fails with ApiClientError status 404 when it is not public. */
export function usePublicProject(loanId: string) {
  const fixture = siteProjectsFixture.find((project) => project.loan_id === loanId);
  return useQuery<PublicProject>({
    queryKey: siteQueryKeys.project(loanId),
    queryFn: ({ signal }) =>
      httpClient<PublicProject>({ url: `${PROJECTS_URL}${encodeURIComponent(loanId)}/`, method: "GET", signal }),
    ...(isFixturePreview
      ? fixture
        ? queryOptions(fixture)
        : {
            enabled: true,
            retry: false as const,
            queryFn: () => Promise.reject(new ApiClientError(404, "Not found.", { detail: "Not found." }))
          }
      : { staleTime: 60_000, retry: (count: number, error: unknown) => !isNotFound(error) && count < 1 })
  });
}

export function usePublicStatistics() {
  return useQuery<PublicStatistics>({
    queryKey: siteQueryKeys.statistics,
    queryFn: ({ signal }) => httpClient<PublicStatistics>({ url: STATISTICS_URL, method: "GET", signal }),
    ...queryOptions(siteStatisticsFixture)
  });
}

export function usePublicOriginators() {
  return useQuery<PublicOriginator[]>({
    queryKey: siteQueryKeys.originators,
    queryFn: ({ signal }) => httpClient<PublicOriginator[]>({ url: ORIGINATORS_URL, method: "GET", signal }),
    ...queryOptions(siteOriginatorsFixture)
  });
}

// ---------------------------------------------------------------------------------------------
// Mutations

/** Newsletter sign-up (double opt-in). Answers 202 for every well-formed address. */
export function useNewsletterSubscribe() {
  return useMutation<{ detail: string }, unknown, NewsletterSubscribeBody>({
    mutationFn: (body) =>
      isFixturePreview
        ? previewAnswer({ detail: "Check your inbox to confirm." })
        : postJson<{ detail: string }>(SUBSCRIBE_URL, { ...body, website: body.website ?? "" })
  });
}

export function useNewsletterConfirm() {
  return useMutation<{ status: "confirmed" }, unknown, NewsletterTokenBody>({
    mutationFn: (body) =>
      isFixturePreview ? previewAnswer({ status: "confirmed" as const }) : postJson<{ status: "confirmed" }>(CONFIRM_URL, body)
  });
}

export function useNewsletterUnsubscribe() {
  return useMutation<{ status: "unsubscribed" }, unknown, NewsletterTokenBody>({
    mutationFn: (body) =>
      isFixturePreview
        ? previewAnswer({ status: "unsubscribed" as const })
        : postJson<{ status: "unsubscribed" }>(UNSUBSCRIBE_URL, body)
  });
}

const previewReferences: Record<EnquiryKind, string> = {
  company: "APP-2026-0143",
  originator: "PAR-2026-0007",
  contact: "MSG-2026-0412"
};

/** The three public forms (For companies, For loan originators, Contact). */
export function useEnquirySubmit() {
  return useMutation<EnquiryResponse, unknown, EnquiryBody>({
    mutationFn: (body) =>
      isFixturePreview
        ? previewAnswer({ reference: previewReferences[body.kind] })
        : postJson<EnquiryResponse>(ENQUIRIES_URL, { ...body, website: body.website ?? "" })
  });
}

// ---------------------------------------------------------------------------------------------
// Errors

export function isNotFound(error: unknown) {
  return error instanceof ApiClientError && error.status === 404;
}

/** 429 from an anonymous write endpoint. */
export function isThrottled(error: unknown) {
  return error instanceof ApiClientError && error.status === 429;
}

/** The server's message ("detail") of an error, or a fallback. */
export function errorDetail(error: unknown, fallback: string) {
  if (error instanceof ApiClientError && error.payload && typeof error.payload === "object") {
    const detail = (error.payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return fallback;
}

/** Field errors of a 400 answer: { email: [...] } (newsletter) or { fields: { name: [...] } } (enquiries). */
export function fieldErrors(error: unknown): Record<string, string[]> {
  if (!(error instanceof ApiClientError) || error.status !== 400 || !error.payload || typeof error.payload !== "object") {
    return {};
  }
  const payload = error.payload as Record<string, unknown>;
  const source = payload.fields && typeof payload.fields === "object" ? (payload.fields as Record<string, unknown>) : payload;
  const result: Record<string, string[]> = {};
  Object.entries(source).forEach(([name, value]) => {
    if (Array.isArray(value)) result[name] = value.map(String);
    else if (typeof value === "string") result[name] = [value];
  });
  return result;
}
