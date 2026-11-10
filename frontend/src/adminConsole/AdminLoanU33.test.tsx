// IP of Webby-Soft SRL.
// Real-API admin follow-ups of the U33 loan features: the loan history (events and audit entries,
// newest first, with who acted and the reason).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import { getV1AuthMeRetrieveResponseMock, getV1LoansAdminLoansListResponseMock } from "../api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("../App")).App;
});

export const adminLoanId = "66666666-6666-4666-8666-666666666666";

export const adminLoan = {
  ...getV1LoansAdminLoansListResponseMock()[0],
  id: adminLoanId,
  product_type: "direct",
  status: "late",
  opportunity_status: null,
  title: "History loan",
  currency: "CHF",
  funding_deadline: "2026-01-31",
  principal_minor: 3_000_000,
  committed_principal_minor: 3_000_000,
  schedule_version: 1,
  is_refinancing: false,
  interest_rate_bps: 1_000,
  term_months: 2,
  interest_only_months: 0,
  repayment_type: "equal_installments",
  loan_start_date: "2026-01-31",
  first_payment_date: "2026-02-28",
  total_scheduled_principal_minor: 3_000_000,
  total_scheduled_interest_minor: 52_500,
  pre_publication_paid_installments: [],
  coming_soon_at: null,
  planned_opening_date: null
};

export function adminHandlers() {
  return [
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json(
        getV1AuthMeRetrieveResponseMock({
          user: {
            id: "00000000-0000-4000-8000-0000000000ad",
            email: "admin@example.test",
            full_name: "Ops Admin",
            investor_reference: null,
            account_type: "admin",
            status: "active",
            phone_verified: true,
            marketing_consent: false,
            number_format: "european",
            language: "en",
            pin_set: false,
            pin_locked_until: null
          },
          platform_business_date: "2026-03-10"
        })
      )
    ),
    http.get("*/api/v1/loans/admin/loans/", () => HttpResponse.json([adminLoan])),
    http.get("*/api/v1/loans/admin/loans/:loanId/", () => HttpResponse.json(adminLoan)),
    http.get("*/api/v1/loans/admin/loans/:loanId/schedule/", () => HttpResponse.json([]))
  ];
}

export function renderAdmin(path: string) {
  window.history.pushState({}, "", path);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>
  );
}

test("the loan history lists events and changes with the reason and who acted", async () => {
  server.use(
    http.get("*/api/v1/loans/admin/loans/:loanId/history/", () =>
      HttpResponse.json({
        entries: [
          {
            id: "a1",
            kind: "change",
            code: "loan.security_added",
            occurred_at: "2026-03-09T10:00:00Z",
            actor: "ops@example.test",
            previous_status: "",
            new_status: "",
            note: "",
            details: { security_id: "s1", security_type: "personal_guarantee", status: "in_place" }
          },
          {
            id: "e1",
            kind: "event",
            code: "status_thresholds_changed",
            occurred_at: "2026-03-08T10:00:00Z",
            actor: "lead@example.test",
            previous_status: "late",
            new_status: "late",
            note: "Contract clause 7.2",
            details: { effective: { late_days: 20, default_days: 90, source: "contract" } }
          }
        ]
      })
    ),
    ...adminHandlers()
  );
  renderAdmin(`/admin/loans/${adminLoanId}/manage/history`);

  const table = await screen.findByRole("table", { name: "Loan history" }, { timeout: 10_000 });
  const [, first, second] = within(table).getAllByRole("row");
  expect(within(first).getByText("Security added")).toBeInTheDocument();
  expect(within(first).getByText("Security: Personal Guarantee · Status: In Place")).toBeInTheDocument();
  expect(within(first).getByText("ops@example.test")).toBeInTheDocument();
  expect(within(second).getByText("Late and default days changed")).toBeInTheDocument();
  expect(within(second).getByText("Contract clause 7.2 · Late from day 20, Default from day 90 (Contract)")).toBeInTheDocument();
}, 20_000);

test("the loan list shows Coming soon, contract days, termination and the securities", async () => {
  const listed = {
    ...adminLoan,
    coming_soon_at: "2026-03-01T09:00:00Z",
    planned_opening_date: "2026-04-15",
    opening_alert_count: 3,
    late_threshold_days: 20,
    default_threshold_days: 90,
    contract_terminated_on: "2026-03-05",
    security_overview: [
      { security_type: "real_estate", status: "in_place" },
      { security_type: "personal_guarantee", status: "released" }
    ]
  };
  server.use(http.get("*/api/v1/loans/admin/loans/", () => HttpResponse.json([listed])), ...adminHandlers());
  renderAdmin("/admin/loans");

  const table = await screen.findByRole("table", { name: "Admin loans" }, { timeout: 10_000 });
  expect(within(table).getByText("Coming soon · opens 15 Apr 2026 · 3 investors wait for the email")).toBeInTheDocument();
  expect(within(table).getByText("Contract days: Late from day 20, Default from day 90")).toBeInTheDocument();
  expect(within(table).getByText("Contract terminated 5 Mar 2026")).toBeInTheDocument();
  expect(within(table).getByText("Securities: Real Estate, Personal Guarantee (released)")).toBeInTheDocument();
}, 20_000);

test("a superadmin changes the platform's late and default days with a reason", async () => {
  const puts: Array<Record<string, unknown>> = [];
  const days = (late: number, defaulted: number, reason: string) => ({
    late_days: late,
    default_days: defaulted,
    default_late_days: 15,
    default_default_days: 60,
    maximum_days: 365,
    last_change: reason ? { changed_at: "2026-03-10T10:00:00Z", changed_by_email: "sa@example.test", reason } : null
  });
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json(
        getV1AuthMeRetrieveResponseMock({
          user: {
            id: "00000000-0000-4000-8000-0000000000sa",
            email: "sa@example.test",
            full_name: "Super Admin",
            investor_reference: null,
            account_type: "superadmin",
            status: "active",
            phone_verified: true,
            marketing_consent: false,
            number_format: "european",
            language: "en",
            pin_set: false,
            pin_locked_until: null
          },
          qa_controls_available: false,
          platform_business_date: "2026-03-10"
        })
      )
    ),
    http.get("*/api/v1/admin/platform-features/", () => HttpResponse.json({ features: [] })),
    http.get("*/api/v1/admin/loan-status-days/", () => HttpResponse.json(days(15, 60, ""))),
    http.put("*/api/v1/admin/loan-status-days/", async ({ request }) => {
      puts.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(days(20, 90, "Owner decision"));
    }),
    ...adminHandlers()
  );
  renderAdmin("/admin/settings");

  const late = await screen.findByLabelText(/Late from day/, {}, { timeout: 10_000 });
  expect(screen.getByText("Never changed")).toBeInTheDocument();
  fireEvent.change(late, { target: { value: "20" } });
  fireEvent.change(screen.getByLabelText(/Default from day/), { target: { value: "90" } });
  fireEvent.change(screen.getByLabelText(/Reason for the new days/), { target: { value: "Owner decision" } });
  fireEvent.click(screen.getByRole("button", { name: "Save the days" }));

  await waitFor(() => expect(puts).toEqual([{ late_days: 20, default_days: 90, reason: "Owner decision" }]));
  expect(await screen.findByText(/Loans without contract days are Late from day 20/)).toBeInTheDocument();
}, 20_000);
