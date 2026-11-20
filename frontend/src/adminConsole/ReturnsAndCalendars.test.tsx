// IP of Webby-Soft SRL.
// Real-API admin checks for 18.4: failed returns (send again, resolve), a returned transfer, a return
// account verified from a deposit and the settlement calendars.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import type { BalanceReturnFailure, SettlementCalendarYear } from "../api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let cards: typeof import("./ReturnsAndCalendars");
beforeAll(async () => {
  cards = await import("./ReturnsAndCalendars");
});

function renderLive(node: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

const failure: BalanceReturnFailure = {
  id: "11111111-1111-4111-8111-111111111111",
  withdrawal_request_id: "22222222-2222-4222-8222-222222222222",
  investor_user_id: "33333333-3333-4333-8333-333333333333",
  currency: "CHF",
  amount_minor: 100_000,
  is_forced: true,
  reason_code: "account_closed",
  reason_label: "Account closed",
  bank_reason_text: "AC04",
  returned_value_date: "2026-03-05",
  failed_destination_iban: "CH9300762011623852957",
  failed_payout_instruction_id: null,
  lot_ids: ["lot-1"],
  status: "open",
  recorded_by_admin_id: "44444444-4444-4444-8444-444444444444",
  recorded_at: "2026-03-05T09:00:00Z",
  last_notice_date: "2026-03-05",
  escalated_at: "2026-03-05T09:00:00Z",
  escalation_reason: "The money is at day 59 (60-day limit).",
  resolved_at: null,
  resolution: "",
  resolution_note: "",
  resend_withdrawal_request_id: null
};

test("a failed return is sent again to a verified account chosen by the admin", async () => {
  let resendBody: Record<string, unknown> | null = null;
  server.use(
    http.get("*/api/v1/ledger/admin/return-failures/", () => HttpResponse.json({ results: [failure] })),
    http.get("*/api/v1/ledger/admin/payout-instructions/", () =>
      HttpResponse.json({
        count: 1,
        limit: 50,
        offset: 0,
        results: [
          {
            id: "55555555-5555-4555-8555-555555555555",
            investor_user_id: failure.investor_user_id,
            investor_name: "Una Investor",
            investor_email: "una@example.test",
            investor_reference: "INV-1",
            currency: "CHF",
            destination_iban: "CH5604835012345678009",
            destination_account_name: "Una Investor",
            state: "verified",
            is_default_return: true,
            origin: "investor_request",
            verified_at: "2026-03-06T09:00:00Z",
            verified_by_admin_id: null,
            evidence_reference: "",
            other_investor_count: 0,
            open_withdrawal_count: 0,
            revocation_reason: "",
            revoked_at: null,
            created_at: "2026-03-06T08:00:00Z"
          }
        ]
      })
    ),
    http.post("*/api/v1/ledger/admin/return-failures/:id/resend/", async ({ request }) => {
      resendBody = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ withdrawal_request: {} });
    })
  );
  renderLive(<cards.ReturnFailuresCard />);

  const row = (await screen.findByText("Account closed")).closest("tr") as HTMLElement;
  expect(within(row).getByText("CH93 ... 2957")).toBeInTheDocument();
  expect(within(row).getByText("Return failed")).toBeInTheDocument();
  fireEvent.click(within(row).getByRole("button", { name: "Act" }));
  const select = await screen.findByLabelText("Send again to");
  await waitFor(() => expect(within(select).getAllByRole("option")).toHaveLength(2));
  fireEvent.change(select, { target: { value: "55555555-5555-4555-8555-555555555555" } });
  fireEvent.click(screen.getByRole("button", { name: "Send again" }));
  await waitFor(() => expect(resendBody).toEqual({ payout_instruction_id: "55555555-5555-4555-8555-555555555555" }));
});

test("a returned transfer is recorded with the bank's reason", async () => {
  let body: Record<string, unknown> | null = null;
  server.use(
    http.post("*/api/v1/ledger/admin/withdrawal-requests/:id/returned/", async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(failure);
    })
  );
  renderLive(<cards.ReturnedTransferForm />);
  fireEvent.change(screen.getByLabelText("Withdrawal request ID"), { target: { value: failure.withdrawal_request_id } });
  fireEvent.change(screen.getByLabelText("Value date of the returned money"), { target: { value: "2026-03-05" } });
  fireEvent.change(screen.getByLabelText("Bank reason"), { target: { value: "name_mismatch" } });
  fireEvent.click(screen.getByRole("button", { name: "Record returned transfer" }));
  expect(await screen.findByText(/a failed-return task is open/)).toBeInTheDocument();
  expect(body).toMatchObject({ returned_value_date: "2026-03-05", reason_code: "name_mismatch" });
  expect((body as unknown as { idempotency_key: string }).idempotency_key).toMatch(/^admin-withdrawal-returned/);
});

test("a return account is verified from a deposit only with both checks and evidence", async () => {
  let body: Record<string, unknown> | null = null;
  server.use(
    http.get("*/api/v1/ledger/admin/investors/:id/deposit-verification-candidates/", () =>
      HttpResponse.json({
        investor_user_id: failure.investor_user_id,
        // Audit S3-6: the legal name from Didit, not the name typed at registration.
        verified_identity_name: "Una Maria Investor",
        registration_name: "Una Investor",
        identity_decision_at: "2026-02-10T09:00:00Z",
        results: [
          { id: "66666666-6666-4666-8666-666666666666", currency: "CHF", amount_minor: 50_000, value_date: "2026-03-01", payer_name: "Una Investor", payer_iban: "CH5604835012345678009" }
        ]
      })
    ),
    http.post("*/api/v1/ledger/admin/lender-deposits/:id/verify-account/", async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ payout_instruction: {} });
    })
  );
  renderLive(<cards.DepositAccountVerificationCard />);
  fireEvent.change(screen.getByLabelText("Investor ID"), { target: { value: failure.investor_user_id } });
  fireEvent.click(screen.getByRole("button", { name: "Show deposits" }));
  const verify = await screen.findByRole("button", { name: "Verify from this deposit" });
  const names = screen.getByText(/Name from the identity check/);
  expect(names).toHaveTextContent("Name from the identity check: Una Maria Investor (decision of");
  expect(names).toHaveTextContent("Name at registration (not evidence): Una Investor");
  expect(verify).toBeDisabled();
  fireEvent.click(screen.getByLabelText("The holder of the transfer matches the name from the identity check"));
  fireEvent.click(screen.getByLabelText("Not a collecting or intermediary account"));
  fireEvent.change(screen.getByLabelText("Evidence reference"), { target: { value: "statement 2026-03-01" } });
  expect(verify).toBeEnabled();
  fireEvent.click(verify);
  await waitFor(() =>
    expect(body).toEqual({ holder_matches_identity: true, not_intermediary_account: true, evidence_reference: "statement 2026-03-01" })
  );
});

test("without a name from the identity check a deposit cannot verify an account", async () => {
  server.use(
    http.get("*/api/v1/ledger/admin/investors/:id/deposit-verification-candidates/", () =>
      HttpResponse.json({
        investor_user_id: failure.investor_user_id,
        verified_identity_name: "",
        registration_name: "Una Investor",
        identity_decision_at: null,
        results: [
          { id: "66666666-6666-4666-8666-666666666666", currency: "CHF", amount_minor: 50_000, value_date: "2026-03-01", payer_name: "Una Investor", payer_iban: "CH5604835012345678009" }
        ]
      })
    )
  );
  // Opened by the deposit form with the investor of the deposit.
  renderLive(<cards.DepositAccountVerificationCard investorUserId={failure.investor_user_id} />);
  const verify = await screen.findByRole("button", { name: "Verify from this deposit" });
  expect(screen.getByText("No name from an identity check")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("The holder of the transfer matches the name from the identity check"));
  fireEvent.click(screen.getByLabelText("Not a collecting or intermediary account"));
  fireEvent.change(screen.getByLabelText("Evidence reference"), { target: { value: "statement 2026-03-01" } });
  expect(verify).toBeDisabled();
});

test("the settlement calendar shows the year, closes a day and confirms the year", async () => {
  const year: SettlementCalendarYear = {
    currency: "CHF",
    year: 2027,
    stored: true,
    preloaded_at: "2026-10-01T00:00:00Z",
    confirmed_at: null,
    confirmed_by_admin_id: null,
    confirmation_note: "",
    days: [{ id: "d1", date: "2027-01-01", name: "New Year's Day", origin: "rule", is_active: true, removal_reason: "" }]
  };
  let added: Record<string, unknown> | null = null;
  let confirmed: Record<string, unknown> | null = null;
  server.use(
    http.get("*/api/v1/admin/settlement-calendars/", () => HttpResponse.json(year)),
    http.post("*/api/v1/admin/settlement-calendars/days/", async ({ request }) => {
      added = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(year);
    }),
    http.post("*/api/v1/admin/settlement-calendars/confirm/", async ({ request }) => {
      confirmed = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ ...year, confirmed_at: "2026-11-02T09:00:00Z" });
    })
  );
  renderLive(<cards.SettlementCalendarsCard />);
  fireEvent.change(screen.getByLabelText("Year"), { target: { value: "2027" } });
  expect(await screen.findByText("New Year's Day")).toBeInTheDocument();
  expect(screen.getByText("Preloaded, not confirmed")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Closed day"), { target: { value: "2027-12-24" } });
  fireEvent.change(screen.getByLabelText("Name of the closed day"), { target: { value: "Bank closed" } });
  fireEvent.click(screen.getByRole("button", { name: "Close this day" }));
  await waitFor(() => expect(added).toEqual({ currency: "CHF", date: "2027-12-24", name: "Bank closed" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm CHF 2027" }));
  await waitFor(() => expect(confirmed).toEqual({ currency: "CHF", year: 2027 }));
});
