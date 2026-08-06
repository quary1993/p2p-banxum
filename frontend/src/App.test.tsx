import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { App } from "./App";
import {
  readReadonlyImpersonationLabel,
  readReadonlyImpersonationToken,
  writeReadonlyImpersonation
} from "./api/client/impersonation";
import { activityFixture, portfolioFixture, primaryOrdersFixture } from "./investorPortal/fixtures";
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

  expect(screen.getByRole("img", { name: "BANXUM" })).toBeInTheDocument();
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

  expect(screen.getByRole("heading", { name: "Money working for you" })).toBeInTheDocument();
  expect(screen.getByText("Preview data")).toBeInTheDocument();
  expect(screen.getByText(/not real account data/i)).toBeInTheDocument();

  const portalNav = screen.getByRole("navigation", { name: "Investor portal navigation" });
  const opportunitiesLink = within(portalNav).getByRole("button", { name: "Investment Opportunities" });
  const smartInvestLink = within(portalNav).getByRole("button", { name: "Smart Invest" });
  expect(opportunitiesLink).toBeInTheDocument();
  expect(smartInvestLink).toBeInTheDocument();
  expect(opportunitiesLink.nextElementSibling).toBe(smartInvestLink);
  expect(smartInvestLink).toHaveClass("nav-link");
  expect(smartInvestLink).not.toHaveClass("nav-link-sub");
  expect(within(portalNav).getByRole("button", { name: "My Portfolio" })).toBeInTheDocument();
  expect(within(portalNav).queryByRole("button", { name: "Notifications" })).not.toBeInTheDocument();

  const topbar = screen.getByRole("banner", { name: "Investor account header" });
  expect(within(topbar).getByRole("button", { name: "Notifications" })).toBeInTheDocument();
  fireEvent.click(within(topbar).getByRole("button", { name: "Add Funds" }));
  expect(screen.getByRole("heading", { name: "Add Funds · CHF" })).toBeInTheDocument();
  expect(screen.getByLabelText("Currency")).toHaveClass("select");
});

test("dashboard renders the v9 financial overview and opens matching loans in the opportunity sheet", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  expect(screen.getByRole("heading", { name: "Money working for you" })).toBeInTheDocument();
  expect(screen.getByText("Waiting on your decision")).toBeInTheDocument();
  expect(screen.getByText("Matches ready to review")).toBeInTheDocument();
  expect(screen.getByText(/Each currency is shown separately/i)).toBeInTheDocument();

  const matches = screen.getByRole("table", { name: "Smart Invest matches" });
  fireEvent.click(within(matches).getByRole("row", { name: /Adriatic Marine d\.o\.o\./i }));

  expect(screen.getByRole("dialog", { name: "Adriatic Marine d.o.o." })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/dashboard");
});

test("Smart Invest matching loans open the same opportunity sheet without leaving the rule page", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Smart Invest" }));

  const matches = screen.getByRole("table", { name: "Smart Invest matches" });
  fireEvent.click(within(matches).getByRole("row", { name: /Adriatic Marine d\.o\.o\./i }));

  expect(screen.getByRole("dialog", { name: "Adriatic Marine d.o.o." })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/smart-invest");
});

test("Smart Invest uses the five approved wizard steps and never implies automatic investing", async () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Smart Invest" }));

  expect(screen.getByRole("heading", { name: "It finds them. You approve them." })).toBeInTheDocument();
  expect(screen.getByText(/never invests for you/i)).toBeInTheDocument();
  expect(screen.queryByText(/cap on any one originator/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/reinvest/i)).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Deactivate the rule" }));
  expect(await screen.findByText("Not active", { selector: ".smart-invest-state" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Walk me through it/ }));

  const wizard = screen.getByRole("dialog", { name: "Set the conditions. Review every match." });
  expect(within(wizard).getByText("Step 1 of 5")).toBeInTheDocument();
  expect(within(wizard).queryByRole("heading", { name: /originator cap/i })).not.toBeInTheDocument();
  expect(within(wizard).queryByRole("heading", { name: /repayment/i })).not.toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole("button", { name: /Required/ }));
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Step 2 of 5")).toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole("button", { name: /CHF only/ }));
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Optional · step 3 of 5")).toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Optional · step 4 of 5")).toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Step 5 of 5 · review")).toBeInTheDocument();
  expect(within(wizard).getByRole("button", { name: "Collateral Collateral required change" })).toBeInTheDocument();
  expect(within(wizard).getByRole("button", { name: "Currency CHF change" })).toBeInTheDocument();
  expect(within(wizard).getByRole("button", { name: "Minimum yield No minimum change" })).toBeInTheDocument();
  expect(within(wizard).getByRole("button", { name: "Maximum term Any term change" })).toBeInTheDocument();
  expect(within(wizard).queryByText(/originator cap/i)).not.toBeInTheDocument();
  expect(within(wizard).queryByText(/repayment preference/i)).not.toBeInTheDocument();
});

test("Marketplace filters can be saved as the active Smart Invest rule", async () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));
  fireEvent.click(screen.getByRole("button", { name: /Filter/ }));

  const panel = document.getElementById("marketplace-filter-panel");
  expect(panel).not.toBeNull();
  fireEvent.click(within(panel as HTMLElement).getByRole("button", { name: /^CHF\s/ }));
  fireEvent.click(within(panel as HTMLElement).getByRole("button", { name: "Save Smart Filters" }));

  expect(await screen.findByRole("heading", { name: "It finds them. You approve them." })).toBeInTheDocument();
  expect(screen.getByText("CHF", { selector: ".smart-rule-summary strong" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/smart-invest");
});

test("investor data tables use the shared editorial table surface", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  fireEvent.click(screen.getByRole("button", { name: /^Balances/ }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "balance-lots-table");

  fireEvent.click(screen.getByRole("button", { name: "Secondary Market" }));
  fireEvent.click(screen.getByRole("tab", { name: "Sell a holding" }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "secondary-sell-table");

  fireEvent.click(screen.getByRole("tab", { name: "Secondary market activity" }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "secondary-activity-table");

  fireEvent.click(screen.getByRole("button", { name: "Documents" }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "documents-data-table");
});

test("read-only impersonation token survives a new tab and opens the investor portal", () => {
  writeReadonlyImpersonation("signed-token", "Viorel Nica (viorel.nica1@gmail.com)", 60);
  window.sessionStorage.clear();

  expect(readReadonlyImpersonationToken()).toBe("signed-token");
  expect(readReadonlyImpersonationLabel()).toBe("Viorel Nica (viorel.nica1@gmail.com)");

  renderApp("/");

  expect(screen.getAllByText("Superadmin read-only view").length).toBeGreaterThan(0);
  expect(screen.getByText(/Viewing the portal as Viorel Nica/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Money working for you" })).toBeInTheDocument();
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

  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));

  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "5 of 5 match")
  ).toBeInTheDocument();
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
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));

  expect(screen.getByRole("heading", { name: "These companies want your investment" })).toBeInTheDocument();
  expect(screen.getByText("Two ways to put your money to work")).toBeInTheDocument();
  expect(screen.getByText(/From CHF 500/i)).toBeInTheDocument();
  expect(screen.getByText("Available to commit")).toBeInTheDocument();
  expect(screen.getByText("available to invest")).toBeInTheDocument();
  expect(screen.getAllByText("58.0%").length).toBeGreaterThan(0);
  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "5 of 5 match")
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Set your investing rule" }));
  expect(screen.getByRole("heading", { name: "It finds them. You approve them." })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));

  fireEvent.click(screen.getByRole("tab", { name: "Detailed" }));
  expect(screen.getAllByText("Loan amount")).toHaveLength(4);
  expect(screen.getAllByText("First come, first served")).toHaveLength(4);

  fireEvent.click(screen.getByRole("button", { name: /^Filter/ }));
  fireEvent.change(screen.getByRole("textbox", { name: "Search investment opportunities" }), {
    target: { value: "solar" }
  });
  expect(screen.getByText("Nordwind Energie GmbH")).toBeInTheDocument();
  expect(screen.queryByText("Helvetia Logistik AG")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Done" }));

  fireEvent.click(screen.getByRole("button", { name: "Full order explanation" }));
  const dialog = screen.getByRole("dialog", { name: "How primary-market orders work" });
  expect(within(dialog).getByText(/pending order does not reserve loan capacity/i)).toBeInTheDocument();
});

test("marketplace filters combine chips, sliders and tokens with live counts", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));

  fireEvent.click(screen.getByRole("button", { name: /^Filter/ }));
  expect(screen.getByRole("button", { name: /^Filter/ })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("Pays at least")).toBeInTheDocument();
  expect(screen.getByText("Runs no longer than")).toBeInTheDocument();
  expect(screen.getByText("Originated by")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^BANXUM \d+$/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Alpine Credit Partners AG/ })).toBeInTheDocument();
  expect(screen.getByText("Risk rating")).toBeInTheDocument();
  expect(screen.getByText("Loan type")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /No collateral/ }));
  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "1 of 5 match")
  ).toBeInTheDocument();
  expect(screen.getByText("Léman BioTech SA")).toBeInTheDocument();
  expect(screen.queryByText("Helvetia Logistik AG")).not.toBeInTheDocument();

  // Removable token restores the list.
  fireEvent.click(screen.getByRole("button", { name: "no collateral" }));
  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "5 of 5 match")
  ).toBeInTheDocument();

  // Refinancing chip narrows to the refinanced Helvetia loan.
  fireEvent.click(screen.getByRole("button", { name: /^Refinancing/ }));
  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "1 of 5 match")
  ).toBeInTheDocument();
  expect(screen.getByText("Helvetia Logistik AG")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "clear" }));
  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "5 of 5 match")
  ).toBeInTheDocument();
});

test("marketplace sheet shows the v9 opportunity layout and hands off to the order flow", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));
  fireEvent.click(screen.getByText("Helvetia Logistik AG"));

  const sheet = screen.getByRole("dialog", { name: "Helvetia Logistik AG" });
  expect(within(sheet).getByText("originated by Banxum · written when this opportunity funds")).toBeInTheDocument();
  expect(within(sheet).getByText("Use of funds")).toBeInTheDocument();
  expect(within(sheet).getByText("Collateral")).toBeInTheDocument();
  expect(within(sheet).getByText("Valuation")).toBeInTheDocument();
  expect(within(sheet).getByText(/What your/)).toBeInTheDocument();
  expect(within(sheet).getByText("Illustrative — if paid as scheduled")).toBeInTheDocument();
  expect(within(sheet).queryByText(/Reinvested at/)).not.toBeInTheDocument();
  expect(within(sheet).getByText("If it stops paying")).toBeInTheDocument();

  // Direct loans show the subscription window with the configured minimum.
  expect(within(sheet).getByText("Subscription window")).toBeInTheDocument();
  expect(within(sheet).getByText("minimum 50%")).toBeInTheDocument();
  expect(within(sheet).getByText("Minimum reached")).toBeInTheDocument();
  expect(within(sheet).getByText("Who you are lending to")).toBeInTheDocument();
  expect(within(sheet).getByText(/We underwrote this loan ourselves/)).toBeInTheDocument();

  // Inline amount step renames Confirm to Review Order and hands off to the compliant flow.
  fireEvent.click(within(sheet).getByRole("button", { name: "Invest now" }));
  expect(within(sheet).getByText("How much do you want to lend")).toBeInTheDocument();
  fireEvent.change(within(sheet).getByLabelText("Amount to invest"), { target: { value: "2000" } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Review Order" }));

  const orderDialog = screen.getByRole("dialog", { name: "Invest - Helvetia Logistik AG" });
  expect(within(orderDialog).getAllByText(/2.000\.00/).length).toBeGreaterThan(0);
});

test("marketplace sorts from the header and the sort menu", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));

  const loanTitles = () =>
    Array.from(document.querySelectorAll(".marketplace-opportunity-name strong")).map(
      (node) => node.textContent
    );

  // Header click sorts by yield ascending, second click flips to descending.
  fireEvent.click(screen.getByRole("button", { name: "Sort by Yield" }));
  expect(loanTitles()[0]).toBe("Rhône Vignobles SA");
  expect(screen.getByRole("button", { name: "back to closing soonest" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sort by Yield" }));
  expect(loanTitles()[0]).toBe("Léman BioTech SA");

  // The sort menu picks a different column.
  fireEvent.click(screen.getByRole("button", { name: "Sort" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Term" }));
  expect(loanTitles()[0]).toBe("Swiss SME equipment claim");

  fireEvent.click(screen.getByRole("button", { name: "back to closing soonest" }));
  expect(screen.queryByRole("button", { name: "back to closing soonest" })).not.toBeInTheDocument();
});

test("portfolio loans sort from the header and the sort menu", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));

  const rowNames = () =>
    Array.from(document.querySelectorAll(".pf-row .pf-company-name")).map((node) => node.textContent);

  // Default order: largest outstanding first.
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");

  // Header click sorts by company name.
  fireEvent.click(screen.getByRole("button", { name: "Sort by Company" }));
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");
  fireEvent.click(screen.getByRole("button", { name: "Sort by Company" }));
  expect(rowNames()[0]).toBe("Ticino Solar SA");

  // Sort menu offers the detailed columns and the clear link restores default.
  fireEvent.click(screen.getByRole("tab", { name: "Detailed" }));
  fireEvent.click(screen.getByRole("button", { name: "Sort" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Rate" }));
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");

  // A Detailed-only sort never remains active without a visible column indicator.
  fireEvent.click(screen.getByRole("tab", { name: "Focused" }));
  expect(screen.queryByRole("button", { name: "back to largest first" })).not.toBeInTheDocument();
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");

  fireEvent.click(screen.getByRole("tab", { name: "Detailed" }));
  fireEvent.click(screen.getByRole("button", { name: "Sort" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Rate" }));
  fireEvent.click(screen.getByRole("button", { name: "back to largest first" }));
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");
});

test("originator claim purchase validates the minimum and stages an executable quote", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));
  fireEvent.click(screen.getByText("Swiss SME equipment claim"));

  const claimSheet = screen.getByRole("dialog", { name: "Swiss SME equipment claim" });
  expect(within(claimSheet).getByText(/taken by other investors/)).toBeInTheDocument();
  fireEvent.click(within(claimSheet).getByRole("button", { name: "The full credit file →" }));

  expect(screen.getByText("Originator claim")).toBeInTheDocument();
  expect(screen.getAllByText("Alpine Credit Partners AG").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/7\.1%/).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Review claim purchase" }));

  const purchaseDialog = screen.getByRole("dialog", { name: "Buy claim - Swiss SME equipment claim" });
  const amountInput = within(purchaseDialog).getByPlaceholderText("0.00");
  const quoteButton = within(purchaseDialog).getByRole("button", { name: "Get executable quote" });

  fireEvent.change(amountInput, { target: { value: "100" } });
  expect(within(purchaseDialog).getByText("Minimum investment is CHF 500.00.")).toBeInTheDocument();
  expect(quoteButton).toBeDisabled();

  fireEvent.change(amountInput, { target: { value: "1000" } });
  fireEvent.click(quoteButton);
  expect(within(purchaseDialog).getByText("Executable for five minutes")).toBeInTheDocument();
  expect(within(purchaseDialog).getByRole("row", { name: /Totals/ })).toBeInTheDocument();

  fireEvent.click(
    within(purchaseDialog).getByLabelText((label) => label.includes("primary-market investment terms"))
  );
  fireEvent.click(
    within(purchaseDialog).getByLabelText((label) => label.includes("originator servicing structure"))
  );
  fireEvent.click(within(purchaseDialog).getByRole("button", { name: "Continue" }));

  expect(within(purchaseDialog).getByText("Confirm this claim purchase")).toBeInTheDocument();
  expect(within(purchaseDialog).getByRole("button", { name: "Send email code" })).toBeEnabled();
  expect(within(purchaseDialog).getByRole("button", { name: "Purchase claim" })).toBeDisabled();
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

  expect(screen.getByRole("heading", { name: "Currency exchange" })).toBeInTheDocument();
  expect(
    screen.getByText("Convert available CHF and EUR balances. The executable rate and fee are shown before confirmation.")
  ).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "My money" })).not.toBeInTheDocument();
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

  // The page keeps the redesign's rates rail and closing band without duplicating money navigation.
  expect(screen.getByText("Rates, net of fees", { selector: ".fx-cap" })).toBeInTheDocument();
  expect(screen.getByText("How to avoid all of this")).toBeInTheDocument();
  expect(screen.getByText(/We earn less when you do this/i)).toBeInTheDocument();
  expect(screen.getByText(/balance CHF/i)).toBeInTheDocument();
});

test("refinanced marketplace loan shows badge and informational original loan schedule", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Investment Opportunities" }));

  // Listing row of the refinancing loan carries the short tag.
  expect(screen.getAllByText("Refinanced").length).toBeGreaterThan(0);

  fireEvent.click(screen.getByText("Helvetia Logistik AG"));

  // The v9 sheet opens first; the credit file lives behind "Meet the borrower".
  const refiSheet = screen.getByRole("dialog", { name: "Helvetia Logistik AG" });
  fireEvent.click(within(refiSheet).getByRole("button", { name: "Meet the borrower →" }));

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
    fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));

    expect(screen.queryByText("Primary orders awaiting funding close")).not.toBeInTheDocument();
    const ordersInfo = screen.getByRole("button", { name: "About primary orders" });
    fireEvent.mouseEnter(ordersInfo);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Primary orders awaiting funding close");
    expect(screen.getByRole("tooltip")).toHaveTextContent("CHF 5'000.00");
    expect(screen.getByText("No loan holdings yet")).toBeInTheDocument();
    expect(screen.getByText(/created only when a published loan is closed/i)).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Exposure" })).not.toBeInTheDocument();
    expect(screen.queryByText("Earnings calendar")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Orders" }));
    expect(screen.getByText("Balance allocated")).toBeInTheDocument();
    expect(screen.queryByText("Earnings calendar")).not.toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));
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

test("secondary market redesign shows for-sale table, explainer band and selling card", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Secondary Market" }));

  expect(screen.getByRole("heading", { name: "Loans other people want out of." })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "For sale now" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Sell a holding" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Secondary market activity" })).toBeInTheDocument();

  // Design table columns with buyer-safe loan context.
  expect(screen.getByText("Asking")).toBeInTheDocument();
  expect(screen.getByText("Left to run")).toBeInTheDocument();
  expect(screen.getByText("Buyer cost")).toBeInTheDocument();
  expect(screen.getByText(/Equipment · 9.4% coupon/)).toBeInTheDocument();
  expect(screen.getByText("24 mo")).toBeInTheDocument();
  expect(screen.getByText("−2.0%")).toBeInTheDocument();
  expect(screen.getByText("CHF 5'185.30")).toBeInTheDocument();
  expect(screen.getByText(/non-standard/)).toBeInTheDocument();

  // Premium/discount explainer band and the selling caution card.
  expect(screen.getByRole("heading", { name: "Why do loans sell at a premium or a discount?" })).toBeInTheDocument();
  expect(screen.getByText("At a discount")).toBeInTheDocument();
  expect(screen.getByText("Below 100% of principal")).toBeInTheDocument();
  expect(screen.queryByText(/your return/i)).not.toBeInTheDocument();
  expect(screen.getByText(/not a withdrawal button/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Choose a loan to sell" }));
  expect(screen.getByRole("tab", { name: "Sell a holding" })).toHaveAttribute("aria-selected", "true");
});

test("portfolio redesign shows hero, tabs, loans table views and widgets", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));

  // Hero + three tabs (Exposure is gone), CHF is the default currency scope.
  expect(screen.getByRole("heading", { name: "Everything you own." })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "My loans" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Activity" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Orders" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Exposure" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "EUR" })).toBeInTheDocument();

  // Focused view hides detail columns via the container class; Detailed shows them.
  expect(document.querySelector(".pf-table")).toHaveClass("focused");
  fireEvent.click(screen.getByRole("tab", { name: "Detailed" }));
  expect(document.querySelector(".pf-table")).toHaveClass("detailed");
  expect(screen.getAllByText("monthly").length).toBeGreaterThan(0);

  // The four design widgets are present.
  expect(screen.getByText("Earnings calendar")).toBeInTheDocument();
  expect(screen.getByText("Spread of portfolio")).toBeInTheDocument();
  expect(screen.getByText("Collateral spread")).toBeInTheDocument();
  expect(screen.getByText("If a borrower stops paying")).toBeInTheDocument();
  expect(screen.getByText("12.0%–16.0% p.a.")).toBeInTheDocument();
  expect(screen.getByText(/CHF 28'110\.50 lent/)).toBeInTheDocument();
  const widgetPairs = document.querySelectorAll(".pf-widget-pair");
  expect(widgetPairs).toHaveLength(2);
  expect(widgetPairs[0].querySelectorAll(".card471")).toHaveLength(2);
  expect(widgetPairs[1].querySelectorAll(".card471")).toHaveLength(2);

  // Portfolio insights stay below the selected tab instead of belonging only to My loans.
  fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
  expect(screen.getByRole("heading", { name: "Activity" })).toBeInTheDocument();
  expect(screen.getByText("Earnings calendar")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Orders" }));
  expect(screen.getByRole("heading", { name: "Orders" })).toBeInTheDocument();
  expect(screen.getByText("Earnings calendar")).toBeInTheDocument();
  expect(screen.queryByText("Orders are intents")).not.toBeInTheDocument();
  expect(screen.getByText("#1")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Copy order ID" })[0]).toHaveAttribute("title", "Copy order ID");
  expect(screen.getAllByRole("button", { name: "Copy loan ID" })[0]).toHaveAttribute("title", "Copy loan ID");
  expect(screen.queryByText("Copy order ID")).not.toBeInTheDocument();
  expect(screen.queryByText("Copy loan ID")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "My loans" }));

  // Hexagon panel opens with the purpose axis and live sentences.
  fireEvent.click(screen.getByText("Spread of portfolio"));
  expect(screen.getByRole("heading", { name: "How spread out your portfolio is" })).toBeInTheDocument();
  expect(screen.getAllByText("Spread by purpose").length).toBeGreaterThan(0);
  const spreadPair = screen.getByText("Spread of portfolio").closest(".pf-widget-pair");
  expect(spreadPair?.querySelector(".pf-panel")).not.toBeNull();

  // Earnings calendar panel opens and a payment day expands into the detail.
  fireEvent.click(screen.getByText("Earnings calendar"));
  expect(screen.getByRole("heading", { name: "Your earnings calendar, date by date" })).toBeInTheDocument();
  const jura = screen.getAllByText("Jura Précision SA").find((node) => node.classList.contains("who"));
  expect(jura).toBeTruthy();
  fireEvent.click(jura!.closest("button") as HTMLElement);
  expect(screen.getByText("Interest — what you earn")).toBeInTheDocument();
  expect(screen.getByText("Your money coming back")).toBeInTheDocument();

  // Recovery and default-interest copy stays tied to the actual project terms.
  fireEvent.click(screen.getByText("If a borrower stops paying"));
  expect(screen.getByText("Project-specific; not guaranteed")).toBeInTheDocument();
  expect(screen.queryByText(/a day/i)).not.toBeInTheDocument();
});

test("portfolio activity and order empty states retain meaningful holding insights", () => {
  const originalActivity = activityFixture.entries;
  const originalOrders = primaryOrdersFixture.orders;
  activityFixture.entries = [];
  primaryOrdersFixture.orders = [];

  try {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));

    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(screen.getByText("No activity yet")).toBeInTheDocument();
    expect(screen.getByText("Earnings calendar")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Orders" }));
    expect(screen.getByText("No primary orders")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Browse marketplace" })).toBeInTheDocument();
    expect(screen.getByText("Earnings calendar")).toBeInTheDocument();
  } finally {
    activityFixture.entries = originalActivity;
    primaryOrdersFixture.orders = originalOrders;
  }
});

test("holding details open in the v9 position modal with factual projections and collateral", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));
  fireEvent.click(screen.getByText("Engadin Alpine refinancing"));

  const dialog = screen.getByRole("dialog", { name: "Engadin Alpine refinancing" });
  expect(dialog).toHaveClass("xwide");
  expect(within(dialog).getByRole("heading", { name: "Engadin Hospitality AG" })).toBeInTheDocument();
  expect(within(dialog).getByText("Interest received")).toBeInTheDocument();
  expect(within(dialog).getByText("Projected still to earn")).toBeInTheDocument();
  expect(within(dialog).getByText("Collateral")).toBeInTheDocument();
  expect(within(dialog).getByText("Registered real-estate security supporting the borrower obligation.")).toBeInTheDocument();
  expect(within(dialog).getByText("61.0% LTV")).toBeInTheDocument();
  expect(within(dialog).getByText(/Historical rows show the borrower payment recorded for the full loan|deterministic projected share/)).toBeInTheDocument();

  fireEvent.click(within(dialog).getByRole("button", { name: /Open timeline/ }));
  expect(within(dialog).getByRole("group", { name: "Borrower payment timeline" })).toBeInTheDocument();

  fireEvent.click(within(dialog).getByRole("button", { name: "View schedule" }));
  expect(within(dialog).getByRole("heading", { name: "Your future schedule" })).toBeInTheDocument();
  expect(within(dialog).getByRole("columnheader", { name: "Owed after" })).toBeInTheDocument();
  expect(within(dialog).getByRole("row", { name: /Totals/ })).toBeInTheDocument();
});

test("originator claim holdings disclose the retained claim without implying protection", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));
  fireEvent.click(screen.getByRole("button", { name: "EUR" }));
  fireEvent.click(screen.getByText("Nord Trans Cargo working capital"));

  const dialog = screen.getByRole("dialog", { name: "Nord Trans Cargo working capital" });
  expect(
    within(dialog).getByText(
      /Nord Capital Finance must retain at least 15\.0% of the loan's current outstanding principal/
    )
  ).toBeInTheDocument();
  expect(within(dialog).queryByText(/loses alongside you/i)).not.toBeInTheDocument();
});

test("impaired holding details do not estimate default interest from days past due", () => {
  const holding = portfolioFixture.holdings[0];
  const originalStatus = holding.loan.loan_status;
  const originalDaysPastDue = holding.loan.days_past_due;
  holding.loan.loan_status = "defaulted";
  holding.loan.days_past_due = 18;
  try {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "lukas.brunner@example.ch" } });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));
    fireEvent.click(screen.getByText("Engadin Alpine refinancing"));

    const dialog = screen.getByRole("dialog", { name: "Engadin Alpine refinancing" });
    expect(within(dialog).getByText(/18 days past due/)).toBeInTheDocument();
    expect(within(dialog).getByText(/12\.0% annual default-interest rate/)).toBeInTheDocument();
    expect(within(dialog).getByText(/does not estimate accrued default interest from days past due/)).toBeInTheDocument();
    expect(within(dialog).queryByText(/a day at today/i)).not.toBeInTheDocument();
  } finally {
    holding.loan.loan_status = originalStatus;
    holding.loan.days_past_due = originalDaysPastDue;
  }
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
    fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));
    fireEvent.click(screen.getByText("Engadin Alpine refinancing"));

    const dialog = screen.getByRole("dialog", { name: "Engadin Alpine refinancing" });
    expect(
      within(dialog).getByText(/Funding has closed, but the borrower payout is still pending/)
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "List on secondary market" })
    ).toBeDisabled();

    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
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
    fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));
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
  fireEvent.click(screen.getByRole("button", { name: "My Portfolio" }));

  expect(screen.getByText("Listed")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Engadin Alpine refinancing"));
  expect(within(screen.getByRole("dialog", { name: "Engadin Alpine refinancing" })).getByRole("button", { name: "Manage secondary listing" })).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("dialog", { name: "Engadin Alpine refinancing" })).getByRole("button", { name: "Manage secondary listing" }));

  expect(screen.getByRole("tab", { name: "Sell a holding" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  // The listed holding's own row swaps List for Edit/Cancel; other active
  // holdings keep their List buttons.
  const engadinSellRow = screen.getByText("Engadin Alpine refinancing").closest("tr") as HTMLElement;
  expect(within(engadinSellRow).queryByRole("button", { name: "List" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "List" }).length).toBeGreaterThan(0);

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

test("a frozen investor can inspect a secondary listing but cannot request a code or purchase", () => {
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
  fireEvent.click(screen.getByRole("button", { name: "Secondary Market" }));
  fireEvent.click(screen.getByText("Loan A - Manufacturing - CH"));

  const dialog = screen.getByRole("dialog", { name: "Buy Loan A - Manufacturing - CH" });
  expect(within(dialog).getByText("Purchase unavailable in this view")).toBeInTheDocument();
  expect(within(dialog).getByRole("tab", { name: "Listed claim projection" })).toBeInTheDocument();
  expect(within(dialog).getByRole("tab", { name: "Full loan schedule" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Send email code" })).toBeDisabled();
  expect(within(dialog).getByRole("button", { name: "Confirm purchase" })).toBeDisabled();
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
  fireEvent.click(within(screen.getByRole("main")).getByRole("button", { name: "Add Funds" }));

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
