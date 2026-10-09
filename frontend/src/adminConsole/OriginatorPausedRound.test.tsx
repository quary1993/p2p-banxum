// Real-API Loan Originator Manage checks (audit 2026-10-09):
// - A-12: a paused subscription round past its deadline offers Resume, Close and
//   Cancel and refund; Resume sends the reason to the new endpoint.
// - A-29: the LO Manage screen offers the loan note action (public / email / both).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import {
  getOriginatorClaimsAdminLoansRetrieveResponseMock,
  getOriginatorClaimsAdminLoansSubscriptionResumeResponseMock,
  getV1AuthMeRetrieveResponseMock,
  getV1LoansAdminLoansListResponseMock,
  getV1ServicingAdminRiskNotesCreateResponseMock
} from "../api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("../App")).App;
});

const loanId = "66666666-6666-4666-8666-666666666666";

function adminMe() {
  return getV1AuthMeRetrieveResponseMock({
    user: {
      id: "00000000-0000-4000-8000-0000000000ad",
      email: "admin@example.test",
      full_name: "Ops Admin",
      investor_reference: null,
      account_type: "admin",
      status: "active",
      phone_verified: true,
      marketing_consent: false
    },
    platform_business_date: "2026-06-08"
  });
}

function loLoan(status: string, opportunityStatus: string) {
  return {
    ...getV1LoansAdminLoansListResponseMock()[0],
    id: loanId,
    product_type: "originator_claim",
    status,
    opportunity_status: opportunityStatus,
    title: "Paused LO round",
    originator_name: "Example Originator",
    currency: "EUR",
    committed_principal_minor: 160_000,
    current_outstanding_principal_minor: 1_000_000,
    unsold_principal_minor: 840_000,
    funding_deadline: "2026-06-06",
    is_refinancing: false,
    term_months: 2,
    interest_rate_bps: 1_200
  };
}

function loDetail(paused: boolean) {
  return getOriginatorClaimsAdminLoansRetrieveResponseMock({
    loan_id: loanId,
    distribution_model: "par_component_v2",
    funding_deadline: "2026-06-06",
    entitlement_start_date: "2026-06-11",
    is_on_hold: paused,
    is_subscription_paused: paused,
    hold_reason: paused ? "Schedule evidence needs review." : "",
    schedule: [],
    payment_history: []
  });
}

function renderManage() {
  window.history.pushState({}, "", `/admin/loans/${loanId}/manage`);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>
  );
}

test("a paused LO round past its deadline can be resumed, closed or cancelled", async () => {
  const resumeBodies: Array<Record<string, unknown>> = [];
  server.use(
    http.get("*/api/v1/auth/me/", () => HttpResponse.json(adminMe())),
    http.get("*/api/v1/loans/admin/loans/", () => HttpResponse.json([loLoan("published", "open")])),
    http.get("*/api/v1/originator-claims/admin/loans/:loanId/", () => HttpResponse.json(loDetail(true))),
    http.post("*/api/v1/originator-claims/admin/loans/:loanId/subscription-resume/", async ({ request }) => {
      resumeBodies.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(getOriginatorClaimsAdminLoansSubscriptionResumeResponseMock());
    })
  );
  renderManage();

  expect(await screen.findByText("Subscription is paused", undefined, { timeout: 10_000 })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Close paused round/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Cancel and refund reservations/ })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Pause subscription/ })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Resume subscription/ }));
  fireEvent.change(screen.getByLabelText("Resume reason"), { target: { value: "Evidence checked." } });
  fireEvent.click(screen.getByRole("button", { name: "Review and resume" }));
  const confirmDialog = await screen.findByRole("dialog", { name: "Resume Loan Originator subscription" });
  fireEvent.click(within(confirmDialog).getByRole("button", { name: "Resume subscription" }));

  await waitFor(() => expect(resumeBodies).toEqual([{ reason: "Evidence checked." }]));
}, 30_000);

test("the LO Manage screen sends a loan note to the current lenders", async () => {
  const noteBodies: Array<Record<string, unknown>> = [];
  server.use(
    http.get("*/api/v1/auth/me/", () => HttpResponse.json(adminMe())),
    http.get("*/api/v1/loans/admin/loans/", () => HttpResponse.json([loLoan("active", "active")])),
    http.get("*/api/v1/originator-claims/admin/loans/:loanId/", () => HttpResponse.json(loDetail(false))),
    http.post("*/api/v1/servicing/admin/risk-notes/", async ({ request }) => {
      noteBodies.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(
        getV1ServicingAdminRiskNotesCreateResponseMock({
          loan_id: loanId,
          borrower_id: null,
          visibility: "internal",
          metadata: { email_recipient_count: 2 }
        }),
        { status: 201 }
      );
    })
  );
  renderManage();

  fireEvent.click(await screen.findByRole("button", { name: /Publish loan note/ }, { timeout: 10_000 }));
  fireEvent.click(screen.getByRole("radio", { name: "Email to current lenders only" }));
  fireEvent.change(screen.getByLabelText("Message to lenders"), {
    target: { value: "The Loan Originator reports the borrower is on schedule." }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send email to lenders" }));
  const confirmDialog = await screen.findByRole("dialog", { name: "Confirm loan note" });
  fireEvent.click(within(confirmDialog).getByRole("button", { name: "Publish and send" }));

  await waitFor(() => expect(noteBodies).toHaveLength(1));
  expect(noteBodies[0]).toMatchObject({
    loan_id: loanId,
    visibility: "internal",
    email_affected_investors: true
  });
  expect(await screen.findByText("Update email queued for 2 current lenders.")).toBeInTheDocument();
}, 30_000);
