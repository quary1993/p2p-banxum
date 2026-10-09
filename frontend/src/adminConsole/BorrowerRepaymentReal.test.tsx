// Real-API admin repayment checks (audit 2026-10-09):
// - A-28: the same borrower bank payment cannot be recorded twice by mistake. The
//   form shows the duplicate warning and the confirmation checkbox only after the
//   server answers 409, and the repeat is sent only with that explicit confirmation.
// - A-10: the repayment-in-advance preview shows how much goes to overdue
//   installments, what stays overdue, and that the loan stays Late.
// - A-30: schedule rows in the grace period show a neutral "Due"; "Overdue" starts
//   at the late threshold (the server sends the row status).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import {
  getV1AuthMeRetrieveResponseMock,
  getV1LoansAdminLoansListResponseMock,
  getV1ServicingAdminBorrowerRepaymentsCreateResponseMock
} from "../api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("../App")).App;
});

const loanId = "55555555-5555-4555-8555-555555555555";

const loan = {
  ...getV1LoansAdminLoansListResponseMock()[0],
  id: loanId,
  product_type: "direct",
  status: "late",
  opportunity_status: null,
  title: "Late servicing loan",
  currency: "CHF",
  principal_minor: 3_000_000,
  committed_principal_minor: 3_000_000,
  schedule_version: 1,
  funding_deadline: "2026-01-31",
  is_refinancing: false,
  interest_rate_bps: 1_000,
  term_months: 2,
  interest_only_months: 0,
  repayment_type: "equal_installments",
  loan_start_date: "2026-01-31",
  first_payment_date: "2026-02-28",
  total_scheduled_principal_minor: 3_000_000,
  total_scheduled_interest_minor: 52_500,
  pre_publication_paid_installments: []
};

const scheduleRow = (
  number: number,
  dueDate: string,
  principal: number,
  interest: number,
  status: string,
  daysPastDue: number
) => ({
  id: `row-${number}`,
  schedule_version: 1,
  installment_number: number,
  due_date: dueDate,
  principal_minor: principal,
  interest_minor: interest,
  total_minor: principal + interest,
  paid_principal_minor: 0,
  paid_interest_minor: 0,
  outstanding_principal_minor: principal,
  outstanding_interest_minor: interest,
  outstanding_total_minor: principal + interest,
  is_paid: false,
  days_past_due: daysPastDue,
  status,
  row_type: "scheduled_installment",
  label: `Installment ${number}`,
  payment_date: null,
  admin_overridden: false
});

const schedule = [
  scheduleRow(1, "2026-02-28", 300_000, 30_000, "overdue", 10),
  scheduleRow(2, "2026-03-31", 2_700_000, 22_500, "upcoming", 0)
];

function useAdminApi() {
  const repaymentBodies: Array<Record<string, unknown>> = [];
  let repaymentCalls = 0;
  server.use(
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
            marketing_consent: false
          },
          platform_business_date: "2026-03-10"
        })
      )
    ),
    http.get("*/api/v1/loans/admin/loans/", () => HttpResponse.json([loan])),
    http.get("*/api/v1/loans/admin/loans/:loanId/", () => HttpResponse.json(loan)),
    http.get("*/api/v1/loans/admin/loans/:loanId/schedule/", () => HttpResponse.json(schedule)),
    http.post("*/api/v1/servicing/admin/borrower-repayments/advance-preview/", () =>
      HttpResponse.json({
        loan_id: loanId,
        currency: "CHF",
        amount_minor: 38_219,
        bank_date: "2026-03-10",
        interest_accrual_start_date: "2026-03-10",
        interest_accrual_end_date: "2026-03-10",
        accrued_interest_days: 0,
        scheduled_interest_due_minor: 30_000,
        accrued_interest_minor: 0,
        interest_applied_minor: 30_000,
        principal_applied_minor: 8_219,
        outstanding_principal_before_minor: 3_000_000,
        outstanding_principal_after_minor: 2_991_781,
        anchor_installment_number: 1,
        old_schedule_rows: [],
        new_schedule_rows: [],
        overdue_interest_due_minor: 30_000,
        overdue_principal_due_minor: 300_000,
        overdue_interest_applied_minor: 30_000,
        overdue_principal_applied_minor: 8_219,
        overdue_remaining_minor: 291_781,
        prepayment_minor: 0,
        overdue_rows: [
          {
            installment_number: 1,
            due_date: "2026-02-28",
            interest_due_minor: 30_000,
            principal_due_minor: 300_000,
            interest_applied_minor: 30_000,
            principal_applied_minor: 8_219,
            remaining_minor: 291_781
          }
        ],
        interest_paid_through_date: "2026-02-28",
        first_new_installment_interest_start_date: null
      })
    ),
    http.post("*/api/v1/servicing/admin/borrower-repayments/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      repaymentBodies.push(body);
      repaymentCalls += 1;
      if (repaymentCalls === 1) {
        return HttpResponse.json(
          {
            detail:
              "Possible duplicate: CHF 330.00 from CH22BORROWER with value date 2026-03-10 was already recorded for this loan (bank operation op-1, recorded 2026-03-10 09:00). It was not recorded again.",
            code: "duplicate_borrower_payment",
            duplicate_bank_operation_id: "op-1"
          },
          { status: 409 }
        );
      }
      return HttpResponse.json(getV1ServicingAdminBorrowerRepaymentsCreateResponseMock(), { status: 201 });
    })
  );
  return { repaymentBodies };
}

function renderManageRepayment() {
  window.history.pushState({}, "", `/admin/loans/${loanId}/manage/servicing`);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>
  );
}

test("a duplicate borrower repayment is refused until the admin confirms a second payment", async () => {
  const api = useAdminApi();
  renderManageRepayment();

  const recordButton = await screen.findByRole("button", { name: "Record repayment" }, { timeout: 10_000 });
  // Schedule chips follow the server status: the overdue row says Overdue.
  expect(await screen.findByText("Overdue")).toBeInTheDocument();
  await waitFor(() => expect(recordButton).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Payer account"), { target: { value: "CH22 BORROWER" } });
  // No warning before the server says so.
  expect(screen.queryByText("Possible duplicate payment")).not.toBeInTheDocument();
  fireEvent.click(recordButton);

  expect(await screen.findByText("Possible duplicate payment")).toBeInTheDocument();
  expect(screen.getByText(/It was not recorded again/)).toBeInTheDocument();
  expect(screen.queryByText("Repayment failed")).not.toBeInTheDocument();
  expect(api.repaymentBodies[0].confirm_repeat_payment).toBeUndefined();
  const confirm = screen.getByRole("checkbox", { name: /second, separate payment/ });
  expect(confirm).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Record repayment" })).toBeDisabled();

  fireEvent.click(confirm);
  fireEvent.click(screen.getByRole("button", { name: "Record repeat repayment" }));

  await waitFor(() => expect(api.repaymentBodies).toHaveLength(2));
  expect(api.repaymentBodies[1].confirm_repeat_payment).toBe(true);
  expect(await screen.findByText("Borrower repayment was recorded and distributed to lenders.")).toBeInTheDocument();
}, 30_000);

test("the advance preview shows the overdue split and that overdue amounts remain", async () => {
  useAdminApi();
  renderManageRepayment();

  await screen.findByRole("button", { name: "Record repayment" }, { timeout: 10_000 });
  fireEvent.change(screen.getByLabelText("Payer account"), { target: { value: "CH22BORROWER" } });
  fireEvent.click(screen.getByRole("checkbox", { name: /Repayment in advance/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Preview new schedule" }));

  const dialog = await screen.findByRole("dialog", { name: "Confirm payment of overdue amounts" });
  expect(within(dialog).getByText("Overdue amounts remain")).toBeInTheDocument();
  expect(within(dialog).getByText(/The loan stays Late until it is paid/)).toBeInTheDocument();
  expect(within(dialog).getByText("Overdue installments (paid first)")).toBeInTheDocument();
  expect(within(dialog).getByText("Paid to overdue installments")).toBeInTheDocument();
  // No accrual rows when nothing is prepaid.
  expect(within(dialog).queryByText("Accrued days (ACT/365)")).not.toBeInTheDocument();
}, 30_000);
