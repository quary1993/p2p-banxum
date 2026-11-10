import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { AdminApp } from "./AdminApp";
import { adminTasksFixture } from "./adminFixtures";

function renderAdmin(path: string) {
  window.history.pushState({}, "", path);
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AdminApp />
    </QueryClientProvider>
  );
}

/** Unmounts and mounts again at the current URL, like a browser reload. */
function reload() {
  cleanup();
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AdminApp />
    </QueryClientProvider>
  );
}

function nav() {
  return screen.getByRole("complementary", { name: "Admin console navigation" });
}

function currentUrl() {
  return `${window.location.pathname}${window.location.search}`;
}

test("reloading an admin page keeps the section, filters and open record", async () => {
  renderAdmin("/admin");
  fireEvent.click(within(nav()).getByRole("button", { name: "Tasks" }));
  expect(window.location.pathname).toBe("/admin/tasks");
  // Labels are linked to their inputs, so the open task's own "Priority" also matches: use the filter.
  const priorityFilter = () => within(document.querySelector(".admin-task-filters") as HTMLElement).getByLabelText("Priority");
  fireEvent.change(priorityFilter(), { target: { value: "urgent" } });
  expect(currentUrl()).toBe("/admin/tasks?priority=urgent");
  const task = adminTasksFixture[0];
  fireEvent.click(screen.getByText(task.title));
  expect(window.location.pathname).toBe(`/admin/tasks/${task.id}`);

  reload();
  expect(screen.getByRole("heading", { level: 1, name: "Tasks" })).toBeInTheDocument();
  expect(priorityFilter()).toHaveValue("urgent");
  expect(screen.getByRole("dialog", { name: task.title })).toBeInTheDocument();

  // Back closes the task, Back again leaves Tasks for the dashboard.
  await act(async () => {
    window.history.back();
  });
  await waitFor(() => expect(screen.queryByRole("dialog", { name: task.title })).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { level: 1, name: "Tasks" })).toBeInTheDocument();
  await act(async () => {
    window.history.back();
  });
  await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Admin operations" })).toBeInTheDocument());
});

test("a loan's Manage view and the chosen action reopen after a reload", () => {
  renderAdmin("/admin/loans?status=late");
  expect(screen.getByLabelText("Filter loans by status")).toHaveValue("late");
  const row = screen.getAllByText("Basel Riverside refurbishment")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Manage" }));
  fireEvent.click(screen.getByRole("button", { name: /Record borrower repayment/ }));
  expect(currentUrl()).toBe("/admin/loans/loan-basel-riverside/manage/servicing?status=late&loan=loan-basel-riverside");

  reload();
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Basel Riverside refurbishment" });
  expect(within(dialog).getByText("Current repayment schedule")).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: /All actions/ }));
  expect(currentUrl()).toBe("/admin/loans/loan-basel-riverside/manage?status=late&loan=loan-basel-riverside");
  fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  expect(currentUrl()).toBe("/admin/loans?status=late&loan=loan-basel-riverside");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("dashboard queue selection is kept in the URL", () => {
  renderAdmin("/admin?queue=withdrawals_requested");
  expect(screen.getByRole("button", { name: /^Withdrawals:/ })).toHaveAttribute("aria-selected", "true");
  fireEvent.click(screen.getByRole("button", { name: /^Reconciliation breaks:/ }));
  expect(currentUrl()).toBe("/admin?queue=reconciliation_breaks");
});

test("a forced withdrawal is listed once in pending finance operations and counted once", () => {
  renderAdmin("/admin");
  // The fixture returns the forced withdrawal in both withdrawal queues, as the API does.
  expect(screen.getByRole("button", { name: /^Withdrawals: 2 open/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Forced withdrawals: 1 open/ })).toBeInTheDocument();

  fireEvent.click(within(nav()).getByRole("button", { name: "Finance ops" }));
  const resolveButtons = screen.getAllByRole("button", { name: "Resolve" });
  expect(resolveButtons).toHaveLength(2);
  fireEvent.click(resolveButtons[1]);
  expect(currentUrl()).toBe("/admin/finance?withdrawal=wd-forced-301");
  expect(screen.getByDisplayValue("wd-forced-301")).toBeInTheDocument();
});

test("finance ops shows withdrawal history and calls payout checks IBAN verification", () => {
  renderAdmin("/admin/finance");
  expect(screen.getByRole("heading", { name: "IBAN verification" })).toBeInTheDocument();
  expect(screen.queryByText(/payout instruction/i)).not.toBeInTheDocument();
  // The admin picks the investor's pending request instead of retyping the IBAN (A-13).
  const ibans = screen.getByRole("table", { name: "Payout IBANs" });
  fireEvent.click(within(ibans).getByRole("button", { name: "Open" }));
  const actions = screen.getByTestId("payout-iban-actions");
  expect(within(actions).getByText("CH56 0483 5012 3456 7800 9")).toBeInTheDocument();
  expect(within(actions).getByRole("button", { name: "Verify IBAN" })).toBeDisabled();
  fireEvent.change(within(actions).getByLabelText("Evidence reference"), { target: { value: "bank-letter:1" } });
  expect(within(actions).getByRole("button", { name: "Verify IBAN" })).toBeEnabled();
  expect(within(actions).getByRole("button", { name: "Reject request" })).toBeDisabled();

  const history = screen.getByRole("table", { name: "Withdrawals history" });
  expect(within(history).getByText("L4F8K2Q9R")).toBeInTheDocument();
  expect(within(history).getByText("Investor asked to cancel before bank execution.")).toBeInTheDocument();
  expect(within(history).getByText("Forced return")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Filter withdrawal history by status"), { target: { value: "cancelled" } });
  expect(currentUrl()).toBe("/admin/finance?history_status=cancelled");
  const filtered = screen.getByRole("table", { name: "Withdrawals history" });
  expect(within(filtered).queryByText("L4F8K2Q9R")).not.toBeInTheDocument();
  expect(within(filtered).getByText("L7MPX3TDA")).toBeInTheDocument();

  // Forced returns have their own filter (MONEY-24).
  fireEvent.change(screen.getByLabelText("Filter withdrawal history by type"), { target: { value: "forced" } });
  expect(currentUrl()).toBe("/admin/finance?history_status=cancelled&history_kind=forced");
});

test("resolving a task asks for confirmation that it does not perform the action", () => {
  const task = adminTasksFixture[0];
  renderAdmin(`/admin/tasks/${task.id}`);
  const drawer = screen.getByRole("dialog", { name: task.title });

  fireEvent.click(within(drawer).getByRole("button", { name: "Resolve" }));
  const confirm = screen.getByRole("dialog", { name: "Resolve this task?" });
  expect(confirm).toHaveTextContent(/it will not verify an IBAN, execute a payment or change any other record/);
  fireEvent.click(within(confirm).getByRole("button", { name: "Back" }));
  expect(screen.queryByRole("dialog", { name: "Resolve this task?" })).not.toBeInTheDocument();
  expect(within(drawer).queryByText("Terminal")).not.toBeInTheDocument();

  // Choosing "Resolved" in the status field and saving asks too.
  fireEvent.change(within(drawer).getByLabelText("Status"), { target: { value: "resolved" } });
  fireEvent.click(within(drawer).getByRole("button", { name: "Save changes" }));
  fireEvent.click(within(screen.getByRole("dialog", { name: "Resolve this task?" })).getByRole("button", { name: "Mark as resolved" }));
  expect(within(screen.getByRole("dialog", { name: task.title })).getByText("Terminal")).toBeInTheDocument();
});

test("a defaulted loan can still publish a loan note as public note, email or both", () => {
  renderAdmin("/admin/loans");
  const row = screen.getAllByText("Luzern Quartier renovation")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Manage" }));
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Luzern Quartier renovation" });
  expect(within(dialog).getByRole("button", { name: /Record a recovery payment/ })).toBeInTheDocument();
  expect(within(dialog).queryByRole("button", { name: /Publish loan/ })).not.toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: /Publish a loan note/ }));

  expect(within(dialog).getByLabelText("Note type")).toHaveValue("default_update");
  fireEvent.click(within(dialog).getByLabelText("Email to current lenders only"));
  fireEvent.change(within(dialog).getByLabelText("Message to lenders"), { target: { value: "Recovery steps have started." } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Send email to lenders" }));
  fireEvent.click(within(screen.getByRole("dialog", { name: "Confirm loan note" })).getByRole("button", { name: "Publish and send" }));
  expect(within(dialog).getByText(/update email would be sent to the current lenders/)).toBeInTheDocument();
  expect(currentUrl()).toBe("/admin/loans/loan-luzern-quartier/manage/note?loan=loan-luzern-quartier");
});

test("U33-DEC-09: a defaulted loan records the contract termination; its days no longer change", () => {
  renderAdmin("/admin/loans");
  const row = screen.getAllByText("Luzern Quartier renovation")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Manage" }));
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Luzern Quartier renovation" });
  // A loan in default stays in default: the Late / Default days are not offered.
  expect(within(dialog).queryByRole("button", { name: /Late and default days/ })).not.toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: /Record contract termination/ }));

  expect(within(dialog).getByText(/Default does not end the contract by itself\./)).toBeInTheDocument();
  fireEvent.change(within(dialog).getByLabelText("Note"), { target: { value: "Letter of 2 Nov." } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Record termination" }));
  fireEvent.click(within(screen.getByRole("dialog", { name: "Confirm contract termination" })).getByRole("button", { name: "Record termination" }));
  expect(within(dialog).getByText(/Contract termination on .* would be recorded/)).toBeInTheDocument();
});

test("a draft loan can be shown as Coming soon only with a planned date before the funding deadline (U33-DEC-17)", () => {
  renderAdmin("/admin/loans");
  const row = screen.getAllByText("Seefeld refinancing takeover")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Manage" }));
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Seefeld refinancing takeover" });
  fireEvent.click(within(dialog).getByRole("button", { name: /Show as Coming soon/ }));

  expect(within(dialog).getByText(/The email goes out when you publish the loan, not on the planned/)).toBeInTheDocument();
  // The fixture's funding deadline (25 Jul 2026) has passed: no planned date can be valid.
  expect(within(dialog).getByText("Date after the funding deadline")).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Show as Coming soon" })).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("Planned opening date"), { target: { value: "2026-07-01" } });
  expect(within(dialog).getByText("Date in the past")).toBeInTheDocument();
  expect(within(dialog).queryByRole("button", { name: "Stop showing as Coming soon" })).not.toBeInTheDocument();
});

test("recovery stages are written by the admin with real dates, and the next step only when known (U33-DEC-22)", () => {
  renderAdmin("/admin/loans");
  const row = screen.getAllByText("Luzern Quartier renovation")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Manage" }));
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Luzern Quartier renovation" });
  fireEvent.click(within(dialog).getByRole("button", { name: /Recovery stages/ }));

  expect(within(dialog).getByText(/Add the next step only when you know/)).toBeInTheDocument();
  expect(within(dialog).getByText("No stage is recorded for this loan.")).toBeInTheDocument();
  const record = within(dialog).getByRole("button", { name: "Record stage" });
  expect(record).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Formal notice" } });
  fireEvent.change(within(dialog).getByLabelText("Date"), { target: { value: "2099-01-01" } });
  expect(within(dialog).getByText("Date in the future")).toBeInTheDocument();
  expect(record).toBeDisabled();

  // A next step can have no date.
  fireEvent.change(within(dialog).getByLabelText("Type"), { target: { value: "next" } });
  expect(within(dialog).getByLabelText("Planned date")).toHaveValue("");
  fireEvent.click(within(dialog).getByRole("button", { name: "Save next step" }));
  fireEvent.click(within(screen.getByRole("dialog", { name: "Confirm the next step" })).getByRole("button", { name: "Save next step" }));
  expect(within(dialog).getByText(/Next step "Formal notice" would be recorded/)).toBeInTheDocument();
});

test("each security of a loan is managed on its own; a guarantee has a scope and a limit (U33-DEC-21)", () => {
  renderAdmin("/admin/loans");
  const row = screen.getAllByText("Seefeld refinancing takeover")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Manage" }));
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Seefeld refinancing takeover" });
  fireEvent.click(within(dialog).getByRole("button", { name: /^Securities/ }));

  expect(within(dialog).getByText(/A guarantee has a scope and a limit, never an asset value/)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: "Add a security" }));
  const type = within(dialog).getByLabelText("Security type");
  // "Mixed" and "asset backed" are not offered for new entries; "unsecured" never.
  const options = Array.from((type as HTMLSelectElement).options).map((option) => option.value);
  expect(options).not.toContain("mixed_collateral");
  expect(options).not.toContain("asset_backed");
  expect(options).not.toContain("unsecured_exception");
  expect(within(dialog).getByLabelText("Value minor units")).toBeInTheDocument();

  fireEvent.change(type, { target: { value: "personal_guarantee" } });
  expect(within(dialog).queryByLabelText("Value minor units")).not.toBeInTheDocument();
  expect(within(dialog).getByLabelText("Guarantee limit minor units")).toBeInTheDocument();
  expect(within(dialog).getByLabelText("Guarantor")).toBeInTheDocument();

  fireEvent.change(type, { target: { value: "other" } });
  expect(within(dialog).getByText("Describe a security of the type Other.")).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Add security" })).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("Description"), { target: { value: "Assignment of rental income" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Add security" }));
  expect(within(dialog).getByText(/A security would be added/)).toBeInTheDocument();
});

test("the credit file editors take the financial years, existing debt, document details and checks (U33-DEC-20)", () => {
  renderAdmin("/admin/loans");
  const borrowerRow = screen.getAllByText("Helvetic Wohnbau AG").map((cell) => cell.closest("tr")).find((row) => row && within(row).queryByRole("button", { name: "Credit file" })) as HTMLElement;
  fireEvent.click(within(borrowerRow).getByRole("button", { name: "Credit file" }));
  const editor = screen.getByRole("dialog", { name: "Credit file - Helvetic Wohnbau AG" });
  expect(within(editor).getByText(/the details must add up to the totals/)).toBeInTheDocument();
  fireEvent.click(within(editor).getByRole("button", { name: "Add a financial year" }));
  expect(within(editor).getByLabelText("Revenue minor units")).toBeInTheDocument();
  expect(within(editor).getByLabelText("Non-current financial debt minor units")).toBeInTheDocument();
  fireEvent.change(within(editor).getByLabelText("Revenue minor units"), { target: { value: "1000000" } });
  fireEvent.click(within(editor).getByRole("button", { name: "Save financial year" }));
  expect(within(editor).getByText(/Financial year \d{4} would be saved/)).toBeInTheDocument();
  fireEvent.click(within(editor).getByRole("button", { name: "Add a facility" }));
  expect(within(editor).getByRole("button", { name: "Save facility" })).toBeDisabled();
  fireEvent.click(within(editor).getByRole("button", { name: "Close" }));

  const loanRow = screen.getAllByText("Seefeld refinancing takeover")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(loanRow).getByRole("button", { name: "Manage" }));
  const dialog = screen.getByRole("dialog", { name: "Manage loan - Seefeld refinancing takeover" });
  fireEvent.click(within(dialog).getByRole("button", { name: /Checks & updates/ }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Add a check" }));
  expect(within(dialog).getByRole("button", { name: "Save check" })).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("What was checked"), { target: { value: "Company and owners" } });
  fireEvent.change(within(dialog).getByLabelText("Result"), { target: { value: "Register details reconciled." } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Save check" }));
  expect(within(dialog).getByText(/The check "Company and owners" would be saved/)).toBeInTheDocument();
});

test("direct loan forms ask for interest-only months for interest-only then amortizing", () => {
  renderAdmin("/admin/loans");
  fireEvent.click(screen.getByRole("button", { name: "Create direct loan" }));
  const createForm = screen.getByRole("dialog", { name: "Create loan draft" });
  expect(within(createForm).queryByLabelText("Interest-only months")).not.toBeInTheDocument();
  fireEvent.change(within(createForm).getByLabelText("Repayment type"), { target: { value: "interest_only_then_amortizing" } });
  const months = within(createForm).getByLabelText("Interest-only months");
  expect(months).toBeRequired();
  expect(within(createForm).getByText("Months with interest only before amortizing: 1 to 11.")).toBeInTheDocument();
  fireEvent.click(within(createForm).getByRole("button", { name: "Close" }));

  const row = screen.getAllByText("Zug Park II bridge facility")[0].closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Edit" }));
  const editForm = screen.getByRole("dialog", { name: "Edit loan - Zug Park II bridge facility" });
  fireEvent.change(within(editForm).getByLabelText("Repayment type"), { target: { value: "interest_only_then_amortizing" } });
  expect(within(editForm).getByLabelText("Interest-only months")).toBeRequired();
});

test("user filters, page and the open user dialog are kept in the URL", () => {
  renderAdmin("/admin/users?status=active");
  expect(screen.getByLabelText("Account status")).toHaveValue("active");
  const row = screen.getByText("Marie Dupont").closest("tr") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Documents" }));
  expect(currentUrl()).toBe("/admin/users/1b7c3e82-2222-4b63-8e21-visitor00002/documents?status=active");

  reload();
  expect(screen.getByRole("dialog", { name: "Accepted documents - Marie Dupont" })).toBeInTheDocument();
});
