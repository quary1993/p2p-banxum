// IP of Webby-Soft SRL.
// Real-API admin follow-ups of the U33 loan features: the loan history (events and audit entries,
// newest first, with who acted and the reason).
import { render, screen, within } from "@testing-library/react";
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
