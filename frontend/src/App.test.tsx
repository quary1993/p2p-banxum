import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { App } from "./App";
import {
  readReadonlyImpersonationLabel,
  readReadonlyImpersonationToken,
  writeReadonlyImpersonation
} from "./api/client/impersonation";
import { portfolioFixture, primaryOrdersFixture } from "./investorPortal/fixtures";
import { onboardingStepForUser } from "./onboarding";

function renderApp(path = "/") {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

test("renders the BANXUM public investor preview", () => {
  renderApp();

  expect(screen.getByText("BANXUM")).toBeInTheDocument();
  expect(screen.getByText("by Garanta Finanzgruppe AG")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Open loan opportunities" })).toBeInTheDocument();
  expect(screen.getByText("Preview mode.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Register" })).toBeInTheDocument();
});

test("login resume sends incomplete accounts back to onboarding", () => {
  expect(
    onboardingStepForUser({
      account_type: "natural_person_lender",
      status: "pending_kyc",
      phone_verified: false
    })
  ).toBe(1);

  expect(
    onboardingStepForUser({
      account_type: "natural_person_lender",
      status: "pending_kyc",
      phone_verified: true
    })
  ).toBe(2);

  expect(
    onboardingStepForUser({
      account_type: "natural_person_lender",
      status: "active",
      phone_verified: true
    })
  ).toBeNull();
});

test("fixture-backed authenticated portal is visibly marked as preview data", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  expect(screen.getByRole("heading", { name: "Welcome back, Lukas" })).toBeInTheDocument();
  expect(screen.getByText("Preview data")).toBeInTheDocument();
  expect(screen.getByText(/not real account data/i)).toBeInTheDocument();
});

test("read-only impersonation token survives a new tab and opens the investor portal", () => {
  writeReadonlyImpersonation("signed-token", "Viorel Nica (viorel.nica1@gmail.com)", 60);
  window.sessionStorage.clear();

  expect(readReadonlyImpersonationToken()).toBe("signed-token");
  expect(readReadonlyImpersonationLabel()).toBe("Viorel Nica (viorel.nica1@gmail.com)");

  renderApp("/");

  expect(screen.getAllByText("Superadmin read-only view").length).toBeGreaterThan(0);
  expect(screen.getByText(/Viewing the portal as Viorel Nica/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Welcome back, Lukas" })).toBeInTheDocument();
});

test("login form submits when the form is submitted from the email field", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.submit(screen.getByTestId("login-magic-link-form"));

  expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
});

test("published primary-market loans appear in dashboard and marketplace open views", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  expect(screen.getByRole("heading", { name: "Open opportunities" })).toBeInTheDocument();
  expect(screen.getByText("Helvetia Logistik AG")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Marketplace" }));

  expect(screen.getByText("4 loans")).toBeInTheDocument();
  expect(screen.getByText("Helvetia Logistik AG")).toBeInTheDocument();
  expect(screen.getAllByText("Open").length).toBeGreaterThan(0);
});

test("portfolio explains allocated orders that are not holdings yet", () => {
  const originalHoldings = portfolioFixture.holdings;
  const originalExposure = portfolioFixture.exposure;
  const originalSummary = portfolioFixture.summary;
  const originalOrders = primaryOrdersFixture.orders;

  portfolioFixture.holdings = [];
  portfolioFixture.exposure = {
    by_borrower: [],
    by_country: [],
    by_purpose: [],
    by_risk_rating: [],
    by_collateral_type: [],
    by_maturity: [],
    by_loan_status: []
  };
  portfolioFixture.summary = {
    ...originalSummary,
    holding_count: 0,
    active_holding_count: 0,
    original_principal_by_currency: [],
    outstanding_principal_by_currency: [],
    late_or_defaulted_exposure_by_currency: []
  };
  primaryOrdersFixture.orders = [
    {
      ...originalOrders[0],
      status: "balance_allocated",
      requested_amount_minor: 500000,
      allocated_amount_minor: 500000
    }
  ];

  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    fireEvent.click(screen.getByRole("button", { name: "Portfolio" }));

    expect(screen.getByText("Primary orders awaiting funding close")).toBeInTheDocument();
    expect(screen.getByText("No loan holdings yet")).toBeInTheDocument();
    expect(screen.getByText(/created only when a published loan is closed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Exposure" }));
    expect(screen.getByText("No funded exposure yet")).toBeInTheDocument();
    expect(screen.getByText(/not yet exposure/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Orders" }));
    expect(screen.getByText("Balance allocated")).toBeInTheDocument();
  } finally {
    portfolioFixture.holdings = originalHoldings;
    portfolioFixture.exposure = originalExposure;
    portfolioFixture.summary = originalSummary;
    primaryOrdersFixture.orders = originalOrders;
  }
});

test("day-60 frozen state keeps read-only access visible and blocks money actions", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.change(screen.getByDisplayValue("Active investor"), {
    target: { value: "frozen" }
  });

  expect(screen.getByText(/Financial actions are frozen/i)).toBeInTheDocument();
  expect(screen.getByText(/portfolio, documents, statements and notices remain available/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add payout IBAN" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Documents" })).toBeInTheDocument();
});

test("registration KYC handoff reflects Didit plus Garanta evidence retention", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  fireEvent.click(screen.getByText("I accept the platform terms and registration documents."));
  fireEvent.click(screen.getByText("I acknowledge the generic P2P lending risk disclosure."));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.change(screen.getByPlaceholderText("000000"), {
    target: { value: "123456" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Verify phone" }));

  expect(screen.getByRole("heading", { name: "Identity verification" })).toBeInTheDocument();
  expect(screen.getByText(/Didit for identity capture and verification/i)).toBeInTheDocument();
  expect(screen.getByText(/retains the required compliance evidence/i)).toBeInTheDocument();
  expect(screen.queryByText(/does not store your identity documents/i)).not.toBeInTheDocument();
});

test("Didit return page tells secondary devices to go back to the original device", () => {
  renderApp("/kyc/callback");

  expect(screen.getByText("Identity check submitted")).toBeInTheDocument();
  expect(screen.getByText(/return to the device where you started/i)).toBeInTheDocument();
  expect(screen.getByText("Log in here")).toBeInTheDocument();
});

test("renders the admin operations dashboard in preview mode", () => {
  renderApp("/admin");

  expect(screen.getByRole("heading", { name: "Admin operations" })).toBeInTheDocument();
  expect(screen.getByText("Preview admin data")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Reconciliation breaks/i })).toBeInTheDocument();
  expect(screen.getByText("Currency operations")).toBeInTheDocument();
});

test("admin task queue renders and updates a preview task", () => {
  renderApp("/admin");

  fireEvent.click(screen.getByRole("button", { name: "Tasks" }));

  expect(screen.getByText("Operational task queue")).toBeInTheDocument();
  expect(screen.getByText("Resolve unmatched CHF lender deposit reference")).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Resolve unmatched CHF lender deposit reference Payment Reconciliation"
    })
  );
  expect(screen.getByText("Task event history")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Mark in progress" }));
  expect(screen.getAllByText("In Progress").length).toBeGreaterThan(0);
});

test("admin module navigation renders operational panels", () => {
  renderApp("/admin");

  fireEvent.click(screen.getByRole("button", { name: "Compliance" }));
  expect(screen.getByRole("heading", { name: "KYC manual review" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Record AML decision" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Finance ops" }));
  expect(screen.getByRole("heading", { name: "Lender deposit" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "FX settlement" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Loans" }));
  expect(screen.getByRole("heading", { name: "Borrowers" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Servicing and recovery" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Reports" }));
  expect(screen.getByRole("heading", { name: "Report generation" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Audit event search" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Users" }));
  expect(screen.getByRole("heading", { name: "User accounts" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Create admin" }));
  expect(screen.getAllByRole("heading", { name: "Create admin user" }).length).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole("button", { name: "Superadmin settings" }));
  expect(screen.getByRole("heading", { name: "Document templates" })).toBeInTheDocument();
});
