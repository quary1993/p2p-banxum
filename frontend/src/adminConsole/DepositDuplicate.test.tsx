import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test, vi } from "vitest";

import { App } from "../App";
import { ApiClientError } from "../api/client/httpClient";
import type { LenderDepositDeclareRequest } from "../api/generated/banxumApi";

type DepositMutationOptions = {
  mutation?: {
    onError?: (error: unknown, variables: { data: LenderDepositDeclareRequest }) => void;
  };
};

const depositHook = vi.hoisted(() => ({
  options: undefined as DepositMutationOptions | undefined,
  error: null as unknown
}));

vi.mock("../api/generated/banxumApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/generated/banxumApi")>();
  return {
    ...actual,
    useV1LedgerAdminLenderDepositsCreate: (options: DepositMutationOptions) => {
      depositHook.options = options;
      return { isPending: false, error: depositHook.error, mutate: vi.fn(), reset: vi.fn() };
    }
  };
});

function depositForm() {
  const heading = screen.getByRole("heading", { name: "Lender deposit" });
  return within(heading.closest("form") ?? (heading.parentElement as HTMLElement));
}

function fieldValue(label: string) {
  return (depositForm().getByLabelText(label) as HTMLInputElement).value;
}

test("a duplicate lender deposit asks for explicit confirmation of a repeat transfer", () => {
  window.history.pushState({}, "", "/admin");
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>
  );
  fireEvent.click(screen.getByRole("button", { name: "Finance ops" }));
  fireEvent.change(depositForm().getByLabelText("Source IBAN"), {
    target: { value: "CH93 0076 2011 6238 5295 7" }
  });

  const rejected: LenderDepositDeclareRequest = {
    investor_user_id: "00000000-0000-4000-8000-000000002048",
    amount_minor: 2500000,
    currency: fieldValue("Currency"),
    booking_date: fieldValue("Booking date"),
    value_date: fieldValue("Value date"),
    collection_account_identifier: fieldValue("Collection account"),
    payer_account_identifier: "CH9300762011623852957",
    idempotency_key: "deposit-test"
  };
  const conflict = new ApiClientError(
    409,
    "Duplicate deposit: CHF 25'000.00 from CH9300762011623852957 with value date was already credited to this investor (deposit op-1). It was not credited again.",
    { code: "duplicate_lender_deposit", duplicate_bank_operation_id: "op-1" }
  );
  depositHook.error = conflict;
  act(() => depositHook.options?.mutation?.onError?.(conflict, { data: rejected }));

  expect(screen.getByText("Possible duplicate deposit")).toBeInTheDocument();
  expect(screen.getByText(/It was not credited again/)).toBeInTheDocument();
  expect(screen.queryByText("Action failed")).not.toBeInTheDocument();
  const confirm = screen.getByRole("checkbox", { name: /second, separate transfer/ });
  expect(confirm).not.toBeChecked();
  expect(depositForm().getByRole("button", { name: "Declare deposit" })).toBeInTheDocument();

  fireEvent.click(confirm);
  expect(depositForm().getByRole("button", { name: "Declare repeat deposit" })).toBeInTheDocument();

  // Editing the movement (here the value date) withdraws the confirmation offer.
  fireEvent.change(depositForm().getByLabelText("Value date"), { target: { value: "2026-01-02" } });
  expect(screen.queryByText("Possible duplicate deposit")).not.toBeInTheDocument();
  expect(depositForm().getByRole("button", { name: "Declare deposit" })).toBeInTheDocument();
});
