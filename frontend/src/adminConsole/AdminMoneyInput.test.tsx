// Admin money and integer fields (audit 2026-10-09, A-16): "25000.00" in a minor-unit field used
// to be cut to 25000 minor units (CHF 250.00) and submitted. Such input must now block the form.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { App } from "../App";

function openFinanceOps() {
  window.history.pushState({}, "", "/admin");
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>
  );
  fireEvent.click(screen.getByRole("button", { name: "Finance ops" }));
  const heading = screen.getByRole("heading", { name: "Lender deposit" });
  const scope = within(heading.closest("form") ?? (heading.parentElement as HTMLElement));
  const amount = scope.getByLabelText("Amount minor units") as HTMLInputElement;
  return { form: amount.form as HTMLFormElement, scope };
}

test.each(["25000.00", "25'000", "25 000", "2.5e6", "1,5"])(
  "a minor-unit amount of %s blocks the deposit form instead of being truncated",
  (typed) => {
    const { form, scope } = openFinanceOps();
    const amount = scope.getByLabelText("Amount minor units") as HTMLInputElement;
    fireEvent.change(amount, { target: { value: typed } });

    expect(amount).toHaveAttribute("aria-invalid", "true");
    expect(amount.validity.patternMismatch).toBe(true);
    expect(form.checkValidity()).toBe(false);
    expect(scope.getByText(/Enter whole minor units only/)).toBeInTheDocument();
  }
);

test("a whole minor-unit amount is valid and shows the formatted value", () => {
  const { scope } = openFinanceOps();
  const amount = scope.getByLabelText("Amount minor units") as HTMLInputElement;
  fireEvent.change(amount, { target: { value: "2500000" } });

  expect(amount).not.toHaveAttribute("aria-invalid");
  expect(amount.validity.patternMismatch).toBe(false);
  expect(scope.getByText(/Formatted amount: CHF 25.000\.00/)).toBeInTheDocument();
});

test("the recovery panel cannot record a payment while an amount is not a whole number", () => {
  window.history.pushState({}, "", "/admin/loans");
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>
  );
  const row = screen.getAllByText("Luzern Quartier renovation")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Manage" }));
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Luzern Quartier renovation" });
  fireEvent.click(within(dialog).getByRole("button", { name: /Record a recovery payment/ }));

  const record = () => within(dialog).getByRole("button", { name: "Record recovery" });
  // No made-up defaults (SERVICING-13): the amount and the payer come from the bank statement.
  expect(within(dialog).getByLabelText("Gross recovered")).toHaveValue("");
  expect(within(dialog).getByLabelText("Payer name")).toHaveValue("");
  expect(record()).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("Gross recovered"), { target: { value: "100000" } });
  expect(record()).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("Payer name"), { target: { value: "Recovery counsel" } });
  expect(record()).toBeEnabled();

  // "1'000" used to count as 0, so the whole receipt was booked as principal.
  fireEvent.change(within(dialog).getByLabelText(/Externally deducted c/), { target: { value: "1'000" } });
  expect(record()).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText(/Externally deducted c/), { target: { value: "1000" } });
  expect(record()).toBeEnabled();
  fireEvent.change(within(dialog).getByLabelText(/Outstanding contractu/), { target: { value: "6000.50" } });
  expect(record()).toBeDisabled();
});
