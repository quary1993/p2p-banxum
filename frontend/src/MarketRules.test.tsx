// Real-API checks for the QA audit round 2 market fixes (2026-10-09):
// - A-44: the public site reads only the anonymous public endpoints (since 2026-10-15 the public
//   site API contract: loan title, never the borrower's name) and never the investor list.
// - A-32: late or defaulted holdings cannot be listed; there is no "Request listing" and no
//   "Approval pending" in the investor UI.
// - SECONDARY-11: two lots of one loan count as one loan and say when each was invested or bought.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import type { Holding } from "./api/generated/banxumApi";
import { getV1AuthMeRetrieveResponseMock, getV1KycStatusRetrieveResponseMock } from "./api/generated/banxumApi";
import { portfolioFixture } from "./investorPortal/fixtures";
import type { PublicProject } from "./site/data";

// Leave fixture preview mode so the pages talk to the (mocked) API.
vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
}, 60_000);

afterEach(() => {
  window.history.pushState({}, "", "/");
});

const directLoanId = "11111111-1111-4111-8111-111111111111";
const originatorLoanId = "22222222-2222-4222-8222-222222222222";

// Anonymous public projects (public site API contract 2026-10-15): the loan title, never the
// borrower's name.
function publicProject(overrides: Partial<PublicProject>): PublicProject {
  return {
    loan_id: directLoanId,
    title: "Machining centre purchase",
    product_type: "direct",
    is_refinancing: false,
    public_status: "open",
    currency: "CHF",
    principal_minor: 25_000_000,
    committed_principal_minor: 10_000_000,
    remaining_capacity_minor: 15_000_000,
    minimum_investment_minor: 50_000,
    investors_count: 4,
    interest_rate_bps: 750,
    term_months: 24,
    repayment_type: "equal_installments",
    risk_rating: "B",
    collateral_type: "equipment",
    collateral_description: "Pledge on the machine",
    ltv_bps: null,
    purpose: "capex",
    purpose_description: "",
    investor_summary: "",
    borrower_country: "CH",
    borrower_sector: "Manufacturing",
    borrower_year_founded: 2004,
    originator: null,
    published_at: "2026-09-01T07:00:00Z",
    funding_deadline: "2099-12-31",
    funded_at: null,
    record: null,
    ...overrides
  };
}

const publicProjects: PublicProject[] = [
  publicProject({}),
  publicProject({
    loan_id: originatorLoanId,
    title: "Invoice financing, logistics",
    product_type: "originator_claim",
    currency: "EUR",
    borrower_country: "NL",
    borrower_sector: "",
    originator: { id: "33333333-3333-4333-8333-333333333333", name: "Sample Originator BV", country: "NL" }
  })
];

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

function useAnonymousApi() {
  const calls = { publicList: 0, publicDetail: 0, oldPublicList: 0, investorList: 0 };
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 })
    ),
    http.get("*/api/v1/marketplace/primary/public/projects/", () => {
      calls.publicList += 1;
      return HttpResponse.json(publicProjects);
    }),
    http.get("*/api/v1/marketplace/primary/public/projects/:loanId/", ({ params }) => {
      calls.publicDetail += 1;
      const project = publicProjects.find((item) => item.loan_id === params.loanId);
      return project ? HttpResponse.json(project) : HttpResponse.json({ detail: "Not found." }, { status: 404 });
    }),
    http.get("*/api/v1/marketplace/primary/loans/", () => {
      calls.oldPublicList += 1;
      return HttpResponse.json([]);
    }),
    http.get("*/api/v1/marketplace/primary/opportunities/", () => {
      calls.investorList += 1;
      return HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 });
    })
  );
  return calls;
}

test("the public home page reads only the anonymous public projects and shows titles, not borrowers", async () => {
  const calls = useAnonymousApi();
  renderAt("/");

  expect(await screen.findByRole("heading", { level: 3, name: "Machining centre purchase" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 3, name: "Invoice financing, logistics" })).toBeInTheDocument();
  // No city in the API: "Country · Sector", or the country alone without a public sector.
  expect(screen.getByText("Switzerland · Manufacturing")).toBeInTheDocument();
  expect(screen.getByText("Netherlands")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "All 2 open projects" })).toBeInTheDocument();
  expect(screen.queryByText(/Sample Originator BV/)).not.toBeInTheDocument();
  expect(calls.publicList).toBeGreaterThan(0);
  expect(calls.oldPublicList).toBe(0);
  expect(calls.investorList).toBe(0);
}, 30_000);

test("a public project page opens from its URL with the loan title", async () => {
  const calls = useAnonymousApi();
  renderAt(`/projects/${originatorLoanId}`);

  expect(await screen.findByRole("heading", { level: 1, name: "Invoice financing, logistics" }, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.publicDetail).toBeGreaterThan(0);
  expect(calls.investorList).toBe(0);
}, 30_000);

test("an unknown public project shows the site's not-found page", async () => {
  useAnonymousApi();
  renderAt("/projects/44444444-4444-4444-8444-444444444444");

  expect(await screen.findByRole("heading", { level: 1, name: "This page does not exist" }, { timeout: 5000 })).toBeInTheDocument();
}, 30_000);

function holdingWith(base: Holding, overrides: Partial<Holding>, loan: Partial<Holding["loan"]>): Holding {
  return { ...base, ...overrides, open_secondary_listing: null, loan: { ...base.loan, ...loan } };
}

function useInvestorApi(holdings: Holding[]) {
  const calls = { publicList: 0, investorList: 0 };
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        ...getV1AuthMeRetrieveResponseMock(),
        user: {
          id: "u1",
          email: "seller@example.com",
          full_name: "Seller One",
          investor_reference: "R1",
          account_type: "investor",
          status: "active",
          phone_verified: true,
          marketing_consent: false
        }
      })
    ),
    http.get("*/api/v1/kyc/status/", () =>
      HttpResponse.json({ ...getV1KycStatusRetrieveResponseMock(), status: "approved", financial_access_allowed: true })
    ),
    http.get("*/api/v1/investor/portal/notifications/", () => HttpResponse.json({ notifications: [], unread_count: 0 })),
    http.get("*/api/v1/investor/portal/balances/", () =>
      HttpResponse.json({ as_of: "2026-10-09T11:47:00Z", summaries: [], lots: [], payout_instructions: [], has_penalty_mode_balance: false })
    ),
    http.get("*/api/v1/marketplace/primary/loans/", () => {
      calls.publicList += 1;
      return HttpResponse.json([]);
    }),
    http.get("*/api/v1/marketplace/primary/opportunities/", () => {
      calls.investorList += 1;
      return HttpResponse.json([]);
    }),
    http.get("*/api/v1/investor/portal/portfolio/", () => HttpResponse.json({ ...portfolioFixture, holdings })),
    http.get("*/api/v1/investor/portal/secondary-market/", () => HttpResponse.json({ entries: [] })),
    http.get("*/api/v1/marketplace/secondary/listings/", () => HttpResponse.json([]))
  );
  return calls;
}

test("the Sell tab offers no listing request for late or defaulted holdings", async () => {
  const base = portfolioFixture.holdings[0];
  const calls = useInvestorApi([
    holdingWith(base, { id: "h-active" }, { loan_id: "loan-active", loan_title: "Performing loan", loan_status: "active" }),
    holdingWith(base, { id: "h-late" }, { loan_id: "loan-late", loan_title: "Late direct loan", loan_status: "late", product_type: "direct" }),
    holdingWith(base, { id: "h-default" }, { loan_id: "loan-default", loan_title: "Defaulted LO claim", loan_status: "defaulted", product_type: "originator_claim" })
  ]);
  renderAt("/secondary-market");
  // The "Selling your own" note counts the holdings that cannot be listed.
  expect(
    await screen.findByText(/2 holdings are late or in default and cannot be listed\./, {}, { timeout: 5000 })
  ).toBeInTheDocument();
  expect(screen.queryByText(/submitted for Garanta approval/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Sell a holding" }));

  const lateCell = await screen.findByText("Late direct loan", {}, { timeout: 5000 });
  const table = lateCell.closest("table") as HTMLElement;
  const row = (title: string) => within(table).getByText(title).closest("tr") as HTMLElement;

  expect(within(row("Performing loan")).getByRole("button", { name: "List" })).toBeEnabled();
  for (const title of ["Late direct loan", "Defaulted LO claim"]) {
    const listButton = within(row(title)).getByRole("button", { name: "List" });
    expect(listButton).toBeDisabled();
    expect(within(row(title)).getByText("Late or in default: cannot be listed")).toBeInTheDocument();
  }
  expect(screen.queryByRole("button", { name: /Request listing/ })).not.toBeInTheDocument();
  expect(screen.queryByText(/Approval pending/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Garanta approval/)).not.toBeInTheDocument();
  await waitFor(() => expect(calls.investorList).toBeGreaterThan(0));
  expect(calls.publicList).toBe(0);
}, 30_000);

test("two lots of one loan count as one loan and say when each was invested or bought", async () => {
  const base = portfolioFixture.holdings[0];
  useInvestorApi([
    holdingWith(
      base,
      { id: "lot-1", source_type: "primary_market", current_principal_minor: 600_000, assignment_effective_at: "2026-10-10T09:00:00Z" },
      { loan_id: "loan-alpine", loan_title: "QA Alpine Equipment", borrower_name: "Alpine AG", loan_status: "active" }
    ),
    holdingWith(
      base,
      { id: "lot-2", source_type: "secondary_market", current_principal_minor: 400_000, assignment_effective_at: "2026-10-14T09:00:00Z" },
      { loan_id: "loan-alpine", loan_title: "QA Alpine Equipment", borrower_name: "Alpine AG", loan_status: "active" }
    ),
    holdingWith(
      base,
      { id: "other", current_principal_minor: 300_000 },
      { loan_id: "loan-other", loan_title: "Other loan", borrower_name: "Other AG", loan_status: "active" }
    )
  ]);
  renderAt("/portfolio");

  await screen.findAllByText("Alpine AG", {}, { timeout: 5000 });
  // Page header ("2 loans · CHF … lent") and table footer count loans, not lots.
  expect(screen.getAllByText(/^2 loans · /)).toHaveLength(2);
  expect(screen.getByText("2 loans · 3 lots")).toBeInTheDocument();
  expect(screen.getByText(/invested on 10 Oct 2026/)).toBeInTheDocument();
  expect(screen.getByText(/bought on 14 Oct 2026/)).toBeInTheDocument();
  expect(screen.queryByText(/^3 loans/)).not.toBeInTheDocument();
}, 30_000);
