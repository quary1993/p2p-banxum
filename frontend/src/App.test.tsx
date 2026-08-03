import { fireEvent, render, screen, within } from "@testing-library/react";
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

test("renders the FAQ for logged-out visitors", () => {
  renderApp("/faq");

  expect(screen.getByRole("heading", { name: "Help & FAQ" })).toBeInTheDocument();
  expect(screen.getByText("How BANXUM works")).toBeInTheDocument();
  expect(screen.getByText("Account and verification")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create lender account" })).toBeInTheDocument();
});

test("direct registration and login URLs render the requested public flow", () => {
  const registration = renderApp("/register");

  expect(screen.getByRole("heading", { name: "Create your lender account" })).toBeInTheDocument();
  registration.unmount();

  renderApp("/login");
  expect(screen.getByRole("heading", { name: "Log in" })).toBeInTheDocument();
});

test("client navigation writes a stable URL and browser history restores the screen", () => {
  renderApp("/");

  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  expect(window.location.pathname).toBe("/register");
  expect(screen.getByRole("heading", { name: "Create your lender account" })).toBeInTheDocument();

  window.history.pushState({}, "", "/faq");
  fireEvent(window, new PopStateEvent("popstate"));
  expect(screen.getByRole("heading", { name: "Help & FAQ" })).toBeInTheDocument();
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
  const login = renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.submit(screen.getByTestId("login-magic-link-form"));

  expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Link sent\. Send new in \d+s/ })).toBeDisabled();

  login.unmount();
  renderApp("/login");

  expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Link sent\. Send new in \d+s/ })).toBeDisabled();
});

test("expired login links offer a cooldown-aware resend and a different-email escape", () => {
  window.localStorage.setItem(
    "banxum:login-flow:v1",
    JSON.stringify({
      email: "investor@example.test",
      sent: true,
      linkExpired: true,
      resendCooldownUntil: 0
    })
  );

  renderApp("/login?token=expired-token");

  expect(screen.getByRole("heading", { name: "Login link expired" })).toBeInTheDocument();
  expect(screen.getByText(/expired or is no longer valid/i)).toBeInTheDocument();
  const resend = screen.getByRole("button", { name: "Send a new magic link" });
  expect(resend).toBeEnabled();

  fireEvent.click(resend);

  expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Link sent\. Send new in \d+s/ })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "Use a different email address" }));

  expect(screen.getByRole("heading", { name: "Log in" })).toBeInTheDocument();
  expect(screen.getByPlaceholderText("you@example.com")).toHaveValue("");
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

test("marketplace redesign preserves live filters, detail mode, and order guidance", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Marketplace" }));

  expect(screen.getByRole("heading", { name: "These companies want your investment" })).toBeInTheDocument();
  expect(screen.getByText("Two ways to put your money to work")).toBeInTheDocument();
  expect(screen.getByText(/From € 1.000/i)).toBeInTheDocument();
  expect(screen.getByText("Available to commit")).toBeInTheDocument();
  expect(screen.getByText("available to invest")).toBeInTheDocument();
  expect(screen.getAllByText("58.0%").length).toBeGreaterThan(0);
  expect(screen.getByText("4 loans")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Set your investing rule" }));
  const investingRuleDialog = screen.getByRole("dialog", { name: "Investing rule" });
  expect(investingRuleDialog).toBeInTheDocument();
  expect(screen.getByText(/future BANXUM module/i)).toBeInTheDocument();
  fireEvent.click(within(investingRuleDialog).getAllByRole("button", { name: "Close" })[1]);

  fireEvent.click(screen.getByRole("tab", { name: "Detailed" }));
  expect(screen.getAllByText("Loan amount")).toHaveLength(4);
  expect(screen.getAllByText("First come, first served")).toHaveLength(4);

  fireEvent.change(screen.getByRole("textbox", { name: "Search investment opportunities" }), {
    target: { value: "solar" }
  });
  expect(screen.getByText("Nordwind Energie GmbH")).toBeInTheDocument();
  expect(screen.queryByText("Helvetia Logistik AG")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Full order explanation" }));
  const dialog = screen.getByRole("dialog", { name: "How primary-market orders work" });
  expect(within(dialog).getByText(/pending order does not reserve loan capacity/i)).toBeInTheDocument();
});

test("FX redesign uses CHF/EUR preview data and net-rate conversion history", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "FX" }));

  expect(screen.getByRole("heading", { name: "Currency & FX" })).toBeInTheDocument();
  expect(screen.getByText("Your balances")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Amount to convert from CHF" }), {
    target: { value: "1000.00" }
  });

  expect(screen.getAllByText("1 CHF = 1.0262 EUR")).toHaveLength(2);
  expect(screen.getByRole("button", { name: "Convert" })).toBeEnabled();
  expect(screen.getByRole("table", { name: "Your conversions" })).toBeInTheDocument();
  expect(screen.getByText(/Every rate below is the rate you received, net of fees/i)).toBeInTheDocument();
  expect(screen.queryByText(/Euro is the only currency/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Convert incoming payments/i)).not.toBeInTheDocument();
});

test("refinanced marketplace loan shows badge and informational original loan schedule", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Marketplace" }));

  // Listing row of the refinancing loan carries the short tag.
  expect(screen.getAllByText("Refinanced").length).toBeGreaterThan(0);

  fireEvent.click(screen.getByText("Helvetia Logistik AG"));

  // Detail header badge plus the informational original-loan section.
  expect(screen.getAllByText("Refinanced loan").length).toBeGreaterThan(0);
  expect(screen.getByText("Original loan")).toBeInTheDocument();
  expect(screen.getByText("Original loan repayment schedule")).toBeInTheDocument();
  expect(screen.getByText(/informational only and show the loan being refinanced/i)).toBeInTheDocument();
  expect(screen.getByRole("row", { name: /Totals/ })).toBeInTheDocument();
  // Column header plus nine installments settled before publication.
  expect(screen.getAllByText("Paid").length).toBe(10);
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

test("primary-order status chips explain released and never-invested outcomes", () => {
  const originalOrders = primaryOrdersFixture.orders;
  primaryOrdersFixture.orders = [
    {
      ...originalOrders[0],
      id: "O-RELEASED",
      status: "balance_released",
      requested_amount_minor: 500000,
      allocated_amount_minor: 500000,
      released_at: "2026-06-05T12:00:00+02:00"
    },
    {
      ...originalOrders[1],
      id: "O-NOT-INVESTED",
      status: "closed_not_invested",
      requested_amount_minor: 300000,
      allocated_amount_minor: 0,
      allocated_at: null,
      closed_at: "2026-06-05T12:00:00+02:00"
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
    fireEvent.click(screen.getByRole("tab", { name: "Orders" }));

    expect(screen.getByTitle(/previously reserved.*released before funding closed/i)).toHaveTextContent(
      "Balance released"
    );
    expect(screen.getByTitle(/closed without any balance being allocated/i)).toHaveTextContent(
      "Not invested"
    );
  } finally {
    primaryOrdersFixture.orders = originalOrders;
  }
});

test("holding details open in a large modal with the current loan schedule", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Portfolio" }));
  fireEvent.click(screen.getByText("Engadin Alpine refinancing"));

  const dialog = screen.getByRole("dialog", { name: "Engadin Alpine refinancing" });
  expect(dialog).toHaveClass("xwide");
  expect(within(dialog).getByText("Borrower: Engadin Hospitality AG")).toBeInTheDocument();
  expect(within(dialog).getByRole("tab", { name: "Your investment schedule" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  expect(within(dialog).getByText("Projection from your current holding")).toBeInTheDocument();
  expect(within(dialog).getByRole("columnheader", { name: "Projected payment" })).toBeInTheDocument();
  expect(within(dialog).getByRole("row", { name: /Totals/ })).toBeInTheDocument();
  expect(within(dialog).getAllByRole("row")).toHaveLength(4);

  fireEvent.click(within(dialog).getByRole("tab", { name: "Full loan schedule" }));

  expect(within(dialog).getByRole("heading", { name: "Full loan schedule" })).toBeInTheDocument();
  expect(within(dialog).getByText("Whole-loan borrower obligations")).toBeInTheDocument();
  expect(within(dialog).getByRole("columnheader", { name: "Outstanding" })).toBeInTheDocument();
  expect(within(dialog).getByRole("row", { name: /Totals/ })).toBeInTheDocument();
  expect(within(dialog).getAllByRole("row")).toHaveLength(5);
});

test("funded holdings explain that secondary listing starts after disbursement", () => {
  const holding = portfolioFixture.holdings[0];
  const originalStatus = holding.loan.loan_status;
  const originalListing = holding.open_secondary_listing;
  holding.loan.loan_status = "funded";
  holding.open_secondary_listing = null;
  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    fireEvent.click(screen.getByRole("button", { name: "Portfolio" }));
    fireEvent.click(screen.getByText("Engadin Alpine refinancing"));

    const dialog = screen.getByRole("dialog", { name: "Engadin Alpine refinancing" });
    expect(
      within(dialog).getByText("Listing available after borrower disbursement")
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "List on secondary market" })
    ).toBeDisabled();

    fireEvent.click(within(dialog).getAllByRole("button", { name: "Close" })[1]);
    fireEvent.click(screen.getByRole("button", { name: "Secondary Market" }));
    fireEvent.click(screen.getByRole("tab", { name: "Sell a holding" }));

    const hint = screen.getByText("Available after disbursement");
    const row = hint.closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByRole("button", { name: "List" })).toBeDisabled();
  } finally {
    holding.loan.loan_status = originalStatus;
    holding.open_secondary_listing = originalListing;
  }
});

test("portfolio listing action opens the sell tab and separates review from email verification", () => {
  const holding = portfolioFixture.holdings[0];
  const originalListing = holding.open_secondary_listing;
  holding.open_secondary_listing = null;
  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    fireEvent.click(screen.getByRole("button", { name: "Portfolio" }));
    fireEvent.click(screen.getByText("Engadin Alpine refinancing"));

    const holdingDialog = screen.getByRole("dialog", { name: "Engadin Alpine refinancing" });
    fireEvent.click(within(holdingDialog).getByRole("button", { name: "List on secondary market" }));

    expect(screen.getByRole("tab", { name: "Sell a holding" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getAllByRole("button", { name: "List" })[0]);

    const listingDialog = screen.getByRole("dialog", { name: "List Engadin Alpine refinancing" });
    expect(listingDialog).toHaveClass("xwide");
    expect(within(listingDialog).queryByLabelText("Email confirmation code")).not.toBeInTheDocument();
    expect(within(listingDialog).getByRole("tab", { name: "Listed holding projection" })).toBeInTheDocument();
    fireEvent.click(
      within(listingDialog).getByLabelText((label) => label.includes("seller/listing terms"))
    );
    fireEvent.click(within(listingDialog).getByRole("button", { name: "Confirm listing data" }));

    expect(within(listingDialog).getByLabelText("Email confirmation code")).toBeInTheDocument();
    expect(within(listingDialog).getByRole("button", { name: "Send email code" })).toBeEnabled();
    expect(within(listingDialog).getByRole("button", { name: "Verify and publish" })).toBeDisabled();
  } finally {
    holding.open_secondary_listing = originalListing;
  }
});

test("listed holdings expose edit and cancel controls plus filtered secondary activity", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Portfolio" }));

  expect(screen.getByText("Listed")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Engadin Alpine refinancing"));
  expect(within(screen.getByRole("dialog", { name: "Engadin Alpine refinancing" })).getByRole("button", { name: "Manage secondary listing" })).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("dialog", { name: "Engadin Alpine refinancing" })).getByRole("button", { name: "Manage secondary listing" }));

  expect(screen.getByRole("tab", { name: "Sell a holding" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "List" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  const editDialog = screen.getByRole("dialog", { name: "Edit listing for Engadin Alpine refinancing" });
  expect(within(editDialog).getByDisplayValue("10000")).toBeInTheDocument();
  expect(within(editDialog).queryByLabelText("Email confirmation code")).not.toBeInTheDocument();
  fireEvent.click(within(editDialog).getByLabelText((label) => label.includes("seller/listing terms")));
  fireEvent.click(within(editDialog).getByRole("button", { name: "Confirm listing data" }));
  expect(within(editDialog).getByRole("button", { name: "Verify and update" })).toBeDisabled();
  fireEvent.click(within(editDialog).getByRole("button", { name: "Back to listing data" }));
  fireEvent.click(within(editDialog).getByRole("button", { name: "Cancel" }));

  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  const cancelDialog = screen.getByRole("dialog", { name: "Cancel Engadin Alpine refinancing listing" });
  expect(within(cancelDialog).getByText(/does not sell or otherwise change the underlying holding/i)).toBeInTheDocument();
  fireEvent.click(within(cancelDialog).getByRole("button", { name: "Keep listing" }));

  fireEvent.click(screen.getByRole("tab", { name: "Secondary market activity" }));
  expect(screen.getByText("Sale completed")).toBeInTheDocument();
  expect(screen.getByText("Purchase completed")).toBeInTheDocument();
  expect(screen.queryByText("Listing updated")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Listings and edits"));
  fireEvent.click(screen.getByLabelText("Listing cancellations"));
  expect(screen.getByText("Listing updated")).toBeInTheDocument();
  expect(screen.getByText("Listing cancelled")).toBeInTheDocument();
});

test("secondary purchase review loads buyer-safe schedules and waits for a manual code request", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Secondary Market" }));
  fireEvent.click(screen.getByText("Loan A - Manufacturing - CH"));

  const dialog = screen.getByRole("dialog", { name: "Buy Loan A - Manufacturing - CH" });
  expect(dialog).toHaveClass("xwide");
  expect(within(dialog).getByText("Annual interest / term")).toBeInTheDocument();
  expect(within(dialog).getByText("LTV")).toBeInTheDocument();
  expect(within(dialog).getByRole("tab", { name: "Listed claim projection" })).toBeInTheDocument();
  expect(within(dialog).getByRole("tab", { name: "Full loan schedule" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Send email code" })).toBeEnabled();
  expect(within(dialog).queryByText(/Code sent\. Send new in/)).not.toBeInTheDocument();
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
  // Checkbox labels embed new-tab document links, so the text spans elements.
  fireEvent.click(
    screen.getByLabelText((label) => label.includes("I accept the") && label.includes("platform terms"))
  );
  fireEvent.click(
    screen.getByLabelText(
      (label) => label.includes("I acknowledge the") && label.includes("risk disclosure")
    )
  );
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
  expect(screen.getByRole("heading", { name: "Pending finance operations" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Resolve" }).length).toBeGreaterThan(0);
  expect(screen.getByRole("heading", { name: "Lender deposit" })).toBeInTheDocument();
  expect(screen.getByLabelText("Source IBAN")).toBeRequired();
  expect(screen.getByRole("heading", { name: "FX settlement" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Loans" }));
  expect(screen.getByRole("heading", { name: "Borrowers" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Servicing operations" })).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Funding progress for Zug Park II bridge facility" })).toHaveAttribute(
    "aria-valuenow",
    "70"
  );

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

test("deposit instructions explain how to use the required payment reference", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: /^Balances/ }));
  fireEvent.click(screen.getByRole("button", { name: "Deposit funds" }));

  expect(screen.getByText("Payment reference - required")).toBeInTheDocument();
  expect(screen.getByText(/enter this reference unchanged in the payment details/i)).toBeInTheDocument();
  expect(screen.getByText(/may delay allocation of the funds/i)).toBeInTheDocument();
});

test("withdrawal dashboard drawer contains the executable withdrawal form", () => {
  renderApp("/admin");

  fireEvent.click(screen.getByRole("button", { name: /^Withdrawals:/i }));
  const withdrawalTitle = screen.getByText("Investor withdrawal awaiting bank execution");
  fireEvent.click(withdrawalTitle.closest("tr") as HTMLElement);

  expect(screen.getByRole("heading", { name: "Execute or cancel withdrawal" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Finalize withdrawal" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel before execution" })).toBeInTheDocument();
  expect(screen.queryByText("Module action deferred")).not.toBeInTheDocument();
});

test("finance ops pending table resolves a withdrawal into the prefilled execution form", () => {
  renderApp("/admin");

  fireEvent.click(screen.getByRole("button", { name: "Finance ops" }));
  const resolveButtons = screen.getAllByRole("button", { name: "Resolve" });
  // Both the requested and the forced withdrawal queue rows must be resolvable.
  expect(resolveButtons.length).toBe(2);
  // The second row is the forced withdrawal; resolving it must prefill the
  // execution form with that withdrawal id (not the preview default).
  fireEvent.click(resolveButtons[1]);

  expect(screen.getByRole("heading", { name: "Withdrawal execution" })).toBeInTheDocument();
  expect(screen.getByDisplayValue("wd-forced-301")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Finalize withdrawal" })).toBeInTheDocument();
});

test("loan manage modal exposes repayment declaration and refinancing publish review", () => {
  renderApp("/admin");

  fireEvent.click(screen.getByRole("button", { name: "Loans" }));

  // Late fixture loan exposes the new servicing action inside Manage.
  const lateLoanRow = screen.getAllByText("Basel Riverside refurbishment")[0].closest("tr");
  expect(lateLoanRow).not.toBeNull();
  expect(within(lateLoanRow as HTMLElement).getByText("Borrower: Helvetic Wohnbau AG")).toBeInTheDocument();
  fireEvent.click(within(lateLoanRow as HTMLElement).getByRole("button", { name: "Manage" }));
  fireEvent.click(screen.getByRole("button", { name: /Record borrower repayment/ }));

  expect(screen.getByText("Current repayment schedule")).toBeInTheDocument();
  expect(screen.getByRole("row", { name: /Totals/ })).toBeInTheDocument();
  expect(screen.getByText(/Repayment in advance \(different amount\)/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Record repayment" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Close" }));

  // Draft refinancing fixture loan publishes through the two-step schedule review.
  const draftLoanRow = screen.getAllByText("Seefeld refinancing takeover")[0].closest("tr");
  expect(draftLoanRow).not.toBeNull();
  fireEvent.click(within(draftLoanRow as HTMLElement).getByRole("button", { name: "Manage" }));
  fireEvent.click(screen.getByRole("button", { name: /Publish loan/ }));

  expect(screen.getByRole("tab", { name: "1. Original loan schedule" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "2. Loan schedule" })).toBeInTheDocument();
  expect(screen.getByText("Remaining outstanding")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Continue to loan schedule" }));
  expect(screen.getByText("Repayment schedule review")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Publish loan after schedule review" })).toBeInTheDocument();
});
