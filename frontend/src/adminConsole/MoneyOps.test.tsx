// Real-API admin money-ops checks (QA audit 2026-10-09, round 2): FX settlement without a
// typed collection account (A-17), the deposit form's configured collection account (A-25),
// the withdrawal side panel and its evidence (A-26) and IBAN verification from a task (A-27).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import {
  getV1AdminOpsTasksRetrieveResponseMock,
  getV1FxAdminExternalSettlementsCreateResponseMock,
  getV1LedgerAdminPayoutInstructionsVerifyCreateResponseMock,
  getV1LedgerAdminWithdrawalRequestsFinalizeCreateResponseMock,
  type AdminDashboardQueueItem,
  type AdminPayoutInstructionRow
} from "../api/generated/banxumApi";

// Leave fixture preview mode so the forms talk to the (mocked) API.
vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let panels: typeof import("./AdminModulePanels");
let adminApp: typeof import("./AdminApp");
let payoutIbans: typeof import("./PayoutIbans");
let tasksPanel: typeof import("./AdminTasksPanel");
beforeAll(async () => {
  panels = await import("./AdminModulePanels");
  adminApp = await import("./AdminApp");
  payoutIbans = await import("./PayoutIbans");
  tasksPanel = await import("./AdminTasksPanel");
});

const accounts = [
  {
    currency: "CHF",
    collection_account_identifier: "Garanta_CHF",
    iban: "CH1183019GARANTAFI001",
    qr_iban: "CH8330334GARANTAFI001",
    account_holder_name: "Garanta Finanzgruppe AG",
    bank_name: "Yapeal"
  },
  {
    currency: "EUR",
    collection_account_identifier: "Garanta_EUR",
    iban: "CH8183019GARANTAFI002",
    qr_iban: "",
    account_holder_name: "Garanta Finanzgruppe AG",
    bank_name: "Yapeal"
  }
];

function renderLive(node: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

function useCollectionAccounts() {
  server.use(http.get("*/api/v1/ledger/admin/collection-accounts/", () => HttpResponse.json(accounts)));
}

test("FX settlement is declared without a typed collection account, with dates and evidence", async () => {
  useCollectionAccounts();
  let body: Record<string, unknown> | null = null;
  server.use(
    http.post("*/api/v1/fx/admin/external-settlements/", async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(getV1FxAdminExternalSettlementsCreateResponseMock(), { status: 201 });
    })
  );
  renderLive(<panels.FxAdminOps />);

  expect(await screen.findByText(/sold CHF from Garanta_CHF, bought EUR into Garanta_EUR/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Sold amount minor"), { target: { value: "47600" } });
  fireEvent.change(screen.getByLabelText("Bought amount minor"), { target: { value: "50000" } });
  fireEvent.change(screen.getByLabelText("Value date"), { target: { value: "2026-10-08" } });
  fireEvent.change(screen.getByLabelText("Bank reference"), { target: { value: "FX-BANK-7" } });
  fireEvent.change(screen.getByLabelText("Evidence reference"), { target: { value: "statement:fx-7" } });
  fireEvent.click(screen.getByRole("button", { name: "Declare settlement" }));

  expect(await screen.findByText("Settlement submitted")).toBeInTheDocument();
  expect(body).not.toBeNull();
  const sent = body as unknown as Record<string, unknown>;
  // The old form sent collection_account_identifier: "" and always failed.
  expect(sent).not.toHaveProperty("collection_account_identifier");
  expect(sent).toMatchObject({
    sold_amount_minor: 47600,
    bought_amount_minor: 50000,
    value_date: "2026-10-08",
    bank_reference: "FX-BANK-7",
    evidence_reference: "statement:fx-7"
  });
});

test("deposit form selects the configured collection account of the currency", async () => {
  useCollectionAccounts();
  renderLive(<panels.DepositForm />);

  const select = (await screen.findByRole("combobox", { name: "Collection account" })) as HTMLSelectElement;
  await waitFor(() => expect(select.value).toBe("Garanta_CHF"));
  expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual(["Garanta_CHF (CHF)"]);

  fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "EUR" } });
  await waitFor(() =>
    expect((screen.getByRole("combobox", { name: "Collection account" }) as HTMLSelectElement).value).toBe("Garanta_EUR")
  );
});

const forcedItem: AdminDashboardQueueItem = {
  kind: "withdrawal_request",
  id: "wd-forced-1",
  title: "Forced return awaiting bank execution",
  status: "requested",
  priority: "high",
  due_at: "2026-12-09T11:00:00Z",
  due_date: null,
  currency: "CHF",
  amount_minor: 5_000_750_00,
  object_type: "InvestorWithdrawalRequest",
  object_id: "wd-forced-1",
  metadata: {
    investor_name: "Anna Keller",
    investor_email: "anna@example.test",
    investor_reference: "L4F8K2Q9R",
    investor_user_id: "u-1",
    destination_iban: "CH9300762011623852957",
    destination_account_name: "Anna Keller",
    is_forced: true,
    destination_reason: "Most recent incoming deposit came from this IBAN (value date 2026-10-09)."
  }
};

test("withdrawal side panel shows owner, destination and forced label, and finalizes with evidence", async () => {
  let body: Record<string, unknown> | null = null;
  server.use(
    http.post("*/api/v1/ledger/admin/withdrawal-requests/:id/finalize/", async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(getV1LedgerAdminWithdrawalRequestsFinalizeCreateResponseMock());
    })
  );
  renderLive(<adminApp.AdminQueueDrawer item={forcedItem} onClose={() => undefined} queueLabel="Forced withdrawals" />);

  const drawer = screen.getByRole("dialog", { name: "Forced return awaiting bank execution" });
  expect(within(drawer).getByText("Forced return")).toBeInTheDocument();
  const destination = within(drawer).getByTestId("withdrawal-destination");
  expect(within(destination).getByText("Anna Keller · anna@example.test")).toBeInTheDocument();
  expect(within(destination).getByText("CH9300762011623852957")).toBeInTheDocument();
  expect(within(destination).getByText(/Most recent incoming deposit/)).toBeInTheDocument();

  const finalize = within(drawer).getByRole("button", { name: "Finalize withdrawal" });
  expect(finalize).toBeDisabled();
  fireEvent.change(within(drawer).getByLabelText("Bank reference"), { target: { value: "BANK-4711" } });
  fireEvent.change(within(drawer).getByLabelText("Evidence reference"), { target: { value: "statement:4711" } });
  expect(finalize).toBeEnabled();
  fireEvent.click(finalize);

  expect(await within(drawer).findByText("Withdrawal action completed")).toBeInTheDocument();
  const sent = body as unknown as Record<string, unknown>;
  expect(sent).toMatchObject({ bank_reference: "BANK-4711", evidence_reference: "statement:4711" });
  // Blank: the ledger uses the configured collection account of the currency.
  expect(sent).not.toHaveProperty("collection_account_identifier");
});

const pendingInstruction: AdminPayoutInstructionRow = {
  id: "11111111-1111-4111-8111-111111111111",
  investor_user_id: "22222222-2222-4222-8222-222222222222",
  investor_name: "Anna Keller",
  investor_email: "anna@example.test",
  investor_reference: "L4F8K2Q9R",
  currency: "CHF",
  destination_iban: "DE89370400440532013000",
  destination_account_name: "Anna Keller",
  state: "pending",
  origin: "investor_request",
  verified_at: null,
  verified_by_admin_id: null,
  evidence_reference: "",
  other_investor_count: 0,
  open_withdrawal_count: 0,
  revocation_reason: "",
  revoked_at: null,
  created_at: "2026-10-09T10:00:00Z",
  updated_at: "2026-10-09T10:00:00Z"
};

test("an IBAN verification task verifies the IBAN with evidence and asks for an override when needed", async () => {
  const bodies: Array<Record<string, unknown>> = [];
  server.use(
    http.get(`*/api/v1/ledger/admin/payout-instructions/${pendingInstruction.id}/`, () =>
      HttpResponse.json(pendingInstruction)
    ),
    http.post(`*/api/v1/ledger/admin/payout-instructions/${pendingInstruction.id}/verify/`, async ({ request }) => {
      bodies.push((await request.json()) as Record<string, unknown>);
      if (bodies.length === 1) {
        return HttpResponse.json(
          {
            detail: "This IBAN is already a verified payout account of another investor.",
            code: "payout_iban_verified_for_other_investor",
            other_investor_count: 1
          },
          { status: 409 }
        );
      }
      return HttpResponse.json(getV1LedgerAdminPayoutInstructionsVerifyCreateResponseMock());
    })
  );
  renderLive(<payoutIbans.PayoutInstructionTaskBlock instructionId={pendingInstruction.id} />);

  const actions = await screen.findByTestId("payout-iban-actions");
  expect(within(actions).getByText("DE89 3704 0044 0532 0130 00")).toBeInTheDocument();
  expect(within(actions).queryByLabelText("Override reason")).not.toBeInTheDocument();
  fireEvent.change(within(actions).getByLabelText("Evidence reference"), { target: { value: "bank-letter:9" } });
  fireEvent.click(within(actions).getByRole("button", { name: "Verify IBAN" }));

  expect(await within(actions).findByText(/verified payout account of another investor/)).toBeInTheDocument();
  fireEvent.change(within(actions).getByLabelText("Override reason"), { target: { value: "Joint account, bank letter." } });
  fireEvent.click(within(actions).getByRole("button", { name: "Verify IBAN" }));

  expect(await screen.findByText(/IBAN verified/)).toBeInTheDocument();
  expect(bodies[0]).toEqual({ evidence_reference: "bank-letter:9" });
  expect(bodies[1]).toMatchObject({
    evidence_reference: "bank-letter:9",
    other_investor_override_reason: "Joint account, bank letter."
  });
});

test("the IBAN actions in the task drawer are not inside the task form and verify the IBAN", async () => {
  // Verify 2026-10-09 (FAIL-1): the IBAN forms sat inside the drawer's task form. A form in a
  // form is invalid HTML, so the browser reloaded the page and nothing was sent.
  let verifyCalls = 0;
  let taskUpdates = 0;
  server.use(
    http.get(`*/api/v1/ledger/admin/payout-instructions/${pendingInstruction.id}/`, () =>
      HttpResponse.json(pendingInstruction)
    ),
    http.post(`*/api/v1/ledger/admin/payout-instructions/${pendingInstruction.id}/verify/`, () => {
      verifyCalls += 1;
      return HttpResponse.json(getV1LedgerAdminPayoutInstructionsVerifyCreateResponseMock());
    }),
    http.patch("*/api/v1/admin-ops/tasks/:taskId/", () => {
      taskUpdates += 1;
      return HttpResponse.json(getV1AdminOpsTasksRetrieveResponseMock());
    })
  );
  const task = getV1AdminOpsTasksRetrieveResponseMock({
    task_type: "payout_instruction_verification",
    title: "Verify payout IBAN",
    status: "open",
    priority: "normal",
    related_object_type: "InvestorPayoutInstruction",
    related_object_id: pendingInstruction.id,
    is_terminal: false
  });
  renderLive(
    <tasksPanel.TaskDetailDrawer
      events={[]}
      eventsLoading={false}
      onClose={() => undefined}
      onPreviewUpdate={() => undefined}
      refetchEvents={() => undefined}
      refetchTasks={() => undefined}
      task={task}
    />
  );

  const actions = await screen.findByTestId("payout-iban-actions");
  const verify = within(actions).getByRole("button", { name: "Verify IBAN" });
  const ibanForm = verify.closest("form") as HTMLFormElement;
  expect(ibanForm.parentElement?.closest("form")).toBeNull();
  expect(screen.getByRole("button", { name: "Save changes" }).closest("form")).not.toBe(ibanForm);

  fireEvent.change(within(actions).getByLabelText("Evidence reference"), { target: { value: "bank-letter:5" } });
  fireEvent.click(verify);
  await waitFor(() => expect(verifyCalls).toBe(1));
  expect(taskUpdates).toBe(0);
});
