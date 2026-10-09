import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { App } from "./App";
import { loansFixture } from "./adminConsole/adminFixtures";
import {
  readReadonlyImpersonationLabel,
  readReadonlyImpersonationToken,
  writeReadonlyImpersonation
} from "./api/client/impersonation";
import { hasSessionExpiredNotice, reportSessionExpired } from "./api/client/sessionExpiry";
import { activityFixture, balanceLotsFixture, balancesFixture, loanDetailsFixture, marketplaceLoansFixture, portfolioFixture, primaryOrdersFixture, smartInvestFixture } from "./investorPortal/fixtures";
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

// The sidebar uses the design names. "Primary market" and "Secondary market" sit
// under the "Projects" entry, which opens on click.
function clickNav(label: string | RegExp) {
  const nav = screen.getByRole("navigation", { name: "Investor portal navigation" });
  if (!within(nav).queryByRole("button", { name: label })) {
    fireEvent.click(within(nav).getByRole("button", { name: /^Projects/ }));
  }
  fireEvent.click(within(nav).getByRole("button", { name: label }));
}

test("renders the BANXUM public investor preview", () => {
  renderApp("/projects");

  const header = screen.getByRole("banner");
  expect(within(header).getByRole("img", { name: "BANXUM" })).toBeInTheDocument();
  const footer = screen.getByRole("contentinfo");
  expect(within(footer).getByText(/BANXUM is owned and operated by Garanta Finanzgruppe AG\./)).toBeInTheDocument();
  expect(within(footer).getByText(`© ${new Date().getFullYear()} Garanta Finanzgruppe AG`)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Open loan opportunities" })).toBeInTheDocument();
  expect(screen.getByText("Preview mode.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Get started" })).toBeInTheDocument();
  expect(within(header).getByRole("button", { name: "Open account" })).toBeInTheDocument();
  expect(within(header).getByRole("link", { name: "Projects" })).toHaveAttribute("aria-current", "page");

  fireEvent.click(screen.getByRole("button", { name: "View Rhône Vignobles SA" }));
  expect(window.location.pathname).toBe("/projects/GA-2399");
  expect(screen.getByRole("heading", { name: "Rhône Vignobles SA" })).toBeInTheDocument();
  expect(screen.getByText("Registration required")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "All loans" }));
  expect(window.location.pathname).toBe("/projects");
  expect(screen.getByRole("heading", { name: "Open loan opportunities" })).toBeInTheDocument();
});

test("public project URLs restore the selected loan", () => {
  renderApp("/projects/GA-2399");

  expect(window.location.pathname).toBe("/projects/GA-2399");
  expect(screen.getByRole("heading", { name: "Rhône Vignobles SA" })).toBeInTheDocument();
  expect(screen.getByText("Registration required")).toBeInTheDocument();
});

test("page titles follow public routes and reset after sign out", () => {
  const projects = renderApp("/projects");
  expect(document.title).toBe("Projects · BANXUM");
  projects.unmount();

  renderApp("/smart-invest");
  expect(document.title).toBe("Smart Invest · BANXUM");
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(window.location.pathname).toBe("/");
  expect(document.title).toBe("BANXUM");
});

test("public home page shows live open loans and links to the projects page", () => {
  renderApp();

  expect(screen.getByRole("heading", { name: "Your capital. Your choice." })).toBeInTheDocument();
  const carousel = screen.getByRole("region", { name: "Loans open for investment" });
  expect(within(carousel).getByText("Funding now")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Projects looking for investors" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Choose. Build. Follow." }).closest("section")).toHaveAttribute("id", "how-it-works");
  expect(screen.getAllByText(/60-day holding limit/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/50 days/)).not.toBeInTheDocument();
  expect(screen.getByText(/Lending to companies puts your capital at risk: a borrower can pay late/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /^All \d+ open projects$/ }));
  expect(window.location.pathname).toBe("/projects");
  expect(screen.getByRole("heading", { name: "Open loan opportunities" })).toBeInTheDocument();
});

test("renders the FAQ for logged-out visitors", () => {
  renderApp("/faq");

  expect(screen.getByRole("heading", { name: "Help & FAQ" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "How BANXUM works" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Account and verification" })).toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Topics" })).getByRole("link", { name: "How BANXUM works" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create lender account" })).toBeInTheDocument();
});

test("portfolio labels preserved pre-reset activity without replacing its details", () => {
  const entry = activityFixture.entries[0];
  const previous = entry.archived_at;
  entry.archived_at = "2026-09-09T12:00:00Z";
  try {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "lukas.brunner@example.ch" } });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("My investments");
    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(screen.getByText("Before QA reset")).toBeInTheDocument();
    expect(screen.getByText(entry.title)).toBeInTheDocument();
  } finally {
    entry.archived_at = previous;
  }
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

  fireEvent.click(within(screen.getByRole("banner")).getByRole("button", { name: "Open account" }));
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
  expect(within(portalNav).getByRole("button", { name: "Overview" })).toHaveClass("nav-link", "on");
  const projectsToggle = within(portalNav).getByRole("button", { name: /^Projects/ });
  expect(projectsToggle).toHaveAttribute("aria-expanded", "false");
  expect(within(portalNav).queryByRole("button", { name: "Primary market" })).not.toBeInTheDocument();
  fireEvent.click(projectsToggle);
  expect(within(portalNav).getByRole("button", { name: "Primary market" })).toHaveClass("nav-sublink");
  expect(within(portalNav).getByRole("button", { name: "Secondary market" })).toHaveClass("nav-sublink");
  const smartInvestLink = within(portalNav).getByRole("button", { name: "Smart Invest" });
  expect(smartInvestLink).toHaveClass("nav-link");
  expect(smartInvestLink).not.toHaveClass("nav-sublink");
  expect(within(portalNav).getByRole("button", { name: "My investments" })).toBeInTheDocument();
  expect(within(portalNav).getByRole("button", { name: /^Account/ })).toBeInTheDocument();
  expect(within(portalNav).getByRole("button", { name: /^Notifications/ })).toBeInTheDocument();

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
  expect(screen.getByText("the clicks that bind — everything else can wait")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "✓ Active" })).toBeInTheDocument();
  expect(screen.getByText("Expected income, month by month")).toBeInTheDocument();
  expect(screen.getByText("What you invested and what you earned")).toBeInTheDocument();
  // Design-only sections: the old balance table and open-opportunity list are gone.
  expect(screen.queryByRole("heading", { name: "Balances" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Open opportunities" })).not.toBeInTheDocument();

  // The rule desk lists matches for the selected currency; EUR holds Adriatic.
  fireEvent.click(screen.getByRole("tab", { name: "EUR" }));
  expect(screen.getByText(/Your rule found/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Adriatic Marine d.o.o." }));

  expect(screen.getByRole("dialog", { name: "Adriatic Marine d.o.o." })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/dashboard");
});

test("rule desk splits idle balance across ticked matches and confirms one batch", async () => {
  const rhone = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2399");
  expect(rhone).toBeDefined();
  const syntheticMatch = { ...smartInvestFixture.matches[0], ...rhone } as (typeof smartInvestFixture.matches)[number];
  smartInvestFixture.matches = [...smartInvestFixture.matches, syntheticMatch];
  smartInvestFixture.match_count = smartInvestFixture.matches.length;
  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

    // CHF is the larger book, so the desk shows the CHF match by default.
    expect(screen.getByText(/Your rule found/)).toBeInTheDocument();
    expect(screen.getByText(/nothing commits until you confirm/)).toBeInTheDocument();
    expect(screen.getByText(/You commit/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Review & confirm →" }));
    const dialog = screen.getByRole("dialog", { name: "Approve this allocation." });
    expect(within(dialog).getByText("Today's allocation")).toBeInTheDocument();
    expect(within(dialog).getByText(/Allocating/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "all" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "none" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm 1" }));
    await waitFor(() => {
      expect(within(dialog).getByText(/one terms acceptance and one email code cover every investment/)).toBeInTheDocument();
    });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /primary-market investment terms/i }));
    fireEvent.change(within(dialog).getByLabelText("Email confirmation code"), { target: { value: "123456" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Place 1 investment" }));
    expect(within(dialog).getByText("Every selected investment is in.")).toBeInTheDocument();
  } finally {
    smartInvestFixture.matches = smartInvestFixture.matches.filter((match) => match !== syntheticMatch);
    smartInvestFixture.match_count = smartInvestFixture.matches.length;
  }
});

test("rule desk batch-reserves a v2 Loan Originator subscription at par", async () => {
  const originalMatches = smartInvestFixture.matches;
  const originatorMatch = marketplaceLoansFixture.find(
    (loan) => loan.product_type === "originator_claim"
  ) as (typeof smartInvestFixture.matches)[number] | undefined;
  expect(originatorMatch).toBeDefined();
  smartInvestFixture.matches = [originatorMatch!];
  smartInvestFixture.match_count = 1;
  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

    expect(
      screen.getByRole("button", {
        name: `Untick ${originatorMatch!.title}`
      })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Review & confirm →" }));
    const dialog = screen.getByRole("dialog", { name: "Approve this allocation." });
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm 1" }));

    await waitFor(() => {
      expect(within(dialog).getByText(/reserved until funding close/i)).toBeInTheDocument();
    });
    expect(within(dialog).queryByText("Loan Originator prices locked")).not.toBeInTheDocument();
    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: /primary-market investment terms/i })
    );
    fireEvent.change(within(dialog).getByLabelText("Email confirmation code"), {
      target: { value: "123456" }
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Place 1 investment" }));
    expect(within(dialog).getByText("Every selected investment is in.")).toBeInTheDocument();
    expect(within(dialog).queryByText(/purchased immediately/)).not.toBeInTheDocument();
  } finally {
    smartInvestFixture.matches = originalMatches;
    smartInvestFixture.match_count = originalMatches.length;
  }
});

test("smart invest table bulk-selects across currencies and approves one allocation", async () => {
  const rhone = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2399");
  const nordwind = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2402");
  expect(rhone).toBeDefined();
  expect(nordwind).toBeDefined();
  const chfMatch = {
    ...smartInvestFixture.matches[0],
    ...rhone,
    loan_id: "GA-BULK-CHF",
    title: "Bulk CHF loan",
    borrower_display_name: "Bulk CHF loan"
  } as (typeof smartInvestFixture.matches)[number];
  const eurMatch = {
    ...smartInvestFixture.matches[0],
    ...nordwind,
    loan_id: "GA-BULK-EUR",
    title: "Bulk EUR loan",
    borrower_display_name: "Bulk EUR loan"
  } as (typeof smartInvestFixture.matches)[number];
  smartInvestFixture.matches = [...smartInvestFixture.matches, chfMatch, eurMatch];
  smartInvestFixture.match_count = smartInvestFixture.matches.length;
  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    fireEvent.click(screen.getByRole("button", { name: "Smart Invest" }));

    // Both currencies come ticked by default and the committing total shows both books.
    expect(screen.getByRole("button", { name: "Untick Bulk CHF loan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Untick Bulk EUR loan" })).toBeInTheDocument();
    expect(screen.getByText(/committing/)).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("button", { name: "Untick Bulk CHF loan" }), { key: "Enter" });
    expect(screen.queryByRole("dialog", { name: "Bulk CHF loan" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Review & confirm →" }));
    const dialog = screen.getByRole("dialog", { name: "Approve this allocation." });
    // One allocating row per currency, each with its balance chip.
    const chfAmount = within(dialog).getByLabelText("Amount to allocate in CHF");
    expect(chfAmount).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Amount to allocate in EUR")).toBeInTheDocument();
    fireEvent.change(chfAmount, { target: { value: "99999999" } });
    expect(within(dialog).getByText(/exceeds your investable balance/i)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /Confirm \d+/ })).toBeDisabled();
    fireEvent.change(chfAmount, { target: { value: "20090" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Confirm \d+/ }));
    await waitFor(() => {
      expect(within(dialog).getByRole("link", { name: /primary-market investment terms/i })).toBeInTheDocument();
    });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /primary-market investment terms/i }));
    fireEvent.change(within(dialog).getByLabelText("Email confirmation code"), { target: { value: "123456" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Place \d+ investments?/ }));
    expect(within(dialog).getByText("Every selected investment is in.")).toBeInTheDocument();
  } finally {
    smartInvestFixture.matches = smartInvestFixture.matches.filter(
      (match) => match !== chfMatch && match !== eurMatch
    );
    smartInvestFixture.match_count = smartInvestFixture.matches.length;
  }
});

test("rule desk blocks loans whose minimum the split cannot reach and explains why", () => {
  const rhone = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2399");
  expect(rhone).toBeDefined();
  // CHF investable is 20'090.00; a 25'000.00 minimum can never be reached.
  const expensive = {
    ...smartInvestFixture.matches[0],
    ...rhone,
    loan_id: "GA-EXPENSIVE",
    title: "Expensive minimum loan",
    borrower_display_name: "Expensive minimum loan",
    minimum_investment_minor: 2_500_000
  } as (typeof smartInvestFixture.matches)[number];
  const affordable = {
    ...smartInvestFixture.matches[0],
    ...rhone,
    loan_id: "GA-AFFORDABLE",
    title: "Affordable loan",
    borrower_display_name: "Affordable loan"
  } as (typeof smartInvestFixture.matches)[number];
  smartInvestFixture.matches = [...smartInvestFixture.matches, expensive, affordable];
  smartInvestFixture.match_count = smartInvestFixture.matches.length;
  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

    // The unaffordable loan is not ticked, cannot be ticked, and carries an explanation.
    const blocked = screen.getByLabelText(/Expensive minimum loan cannot be selected/);
    fireEvent.mouseEnter(blocked);
    expect(screen.getByRole("tooltip")).toHaveTextContent("minimum investment");
    fireEvent.mouseLeave(blocked);
    expect(screen.queryByRole("button", { name: "Untick Expensive minimum loan" })).not.toBeInTheDocument();
    expect(screen.getByText("below minimum")).toBeInTheDocument();

    // The affordable loan stays ticked and the batch remains confirmable without the blocked one.
    expect(screen.getByRole("button", { name: "Untick Affordable loan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review & confirm →" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Smart Invest" }));
    const matches = screen.getByRole("table", { name: "Smart Invest matches" });
    const tableBlocked = within(matches).getByLabelText(/Expensive minimum loan cannot be selected/);
    fireEvent.mouseEnter(tableBlocked);
    expect(screen.getByRole("tooltip")).toHaveTextContent("minimum investment");
  } finally {
    smartInvestFixture.matches = smartInvestFixture.matches.filter(
      (match) => match !== expensive && match !== affordable
    );
    smartInvestFixture.match_count = smartInvestFixture.matches.length;
  }
});

test("balance ageing reminders appear in notifications instead of a persistent dashboard warning", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  expect(screen.queryByText("Balance ageing - action needed")).not.toBeInTheDocument();

  const topbar = screen.getByRole("banner", { name: "Investor account header" });
  fireEvent.click(within(topbar).getByRole("button", { name: "Notifications" }));
  fireEvent.click(within(topbar).getByRole("button", { name: "View all" }));

  expect(screen.getByRole("heading", { name: "Notifications" })).toBeInTheDocument();
  expect(screen.getByText("Balance ageing - day 57")).toBeInTheDocument();
  expect(screen.getByText(/must be withdrawn within 3 days/i)).toBeInTheDocument();
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
  expect(await screen.findByText("Not active", { selector: ".si-state" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Walk me through it/ }));

  const wizard = screen.getByRole("dialog", { name: "Smart Invest setup" });
  expect(within(wizard).getByText("Step 1 of 5 · what must be behind the loan")).toBeInTheDocument();
  expect(within(wizard).getByText("Would qualify today")).toBeInTheDocument();
  expect(within(wizard).queryByRole("heading", { name: /originator cap/i })).not.toBeInTheDocument();
  expect(within(wizard).queryByRole("heading", { name: /repayment/i })).not.toBeInTheDocument();
  // Every criterion is a multi-select; no combined "Either"/"Both" options remain.
  expect(within(wizard).queryByRole("button", { name: /Not required|Either|Both/ })).not.toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole("checkbox", { name: "With collateral (any type)" }));
  // "With collateral (any type)" includes every collateral type: shown ticked and locked.
  expect(within(wizard).getByRole("checkbox", { name: "Real estate" })).toBeChecked();
  expect(within(wizard).getByRole("checkbox", { name: "Real estate" })).toBeDisabled();
  fireEvent.click(within(wizard).getByRole("checkbox", { name: "No collateral (unsecured)" }));
  fireEvent.click(within(wizard).getByRole("checkbox", { name: "No collateral (unsecured)" }));
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Step 2 of 5 · which currency it uses")).toBeInTheDocument();
  expect(within(wizard).queryByRole("button", { name: /CHF only|EUR only|CHF and EUR/ })).not.toBeInTheDocument();
  expect(within(wizard).getAllByRole("checkbox").map((box) => box.getAttribute("id"))).toEqual(["si-wiz-ccy-CHF", "si-wiz-ccy-EUR"]);
  fireEvent.click(within(wizard).getByRole("checkbox", { name: "CHF" }));
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Your rule already works · everything from here is optional")).toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Optional · step 4 of 5")).toBeInTheDocument();
  expect(within(wizard).getByRole("button", { name: "Finish now, skip the rest" })).toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole("button", { name: "Continue" }));
  expect(within(wizard).getByText("Step 5 of 5 · review")).toBeInTheDocument();
  expect(within(wizard).getByText("With collateral (any type)")).toBeInTheDocument();
  expect(within(wizard).getByText("CHF")).toBeInTheDocument();
  expect(within(wizard).getByText("No minimum")).toBeInTheDocument();
  expect(within(wizard).getByText("Any term")).toBeInTheDocument();
  expect(within(wizard).getAllByRole("button", { name: "change" })).toHaveLength(4);
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
  clickNav("Primary market");
  fireEvent.click(screen.getByRole("button", { name: /Filter/ }));

  const panel = document.getElementById("marketplace-filter-panel");
  expect(panel).not.toBeNull();
  fireEvent.click(within(panel as HTMLElement).getByRole("button", { name: /^CHF\s/ }));
  fireEvent.click(within(panel as HTMLElement).getByRole("button", { name: "Save Smart Filters" }));

  expect(await screen.findByRole("heading", { name: "It finds them. You approve them." })).toBeInTheDocument();
  expect(screen.getByText(/CHF/, { selector: ".si-cond-summary" })).toBeInTheDocument();
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

  clickNav(/^Account/);
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "balance-lots-table");

  clickNav("Secondary market");
  fireEvent.click(screen.getByRole("tab", { name: "Sell a holding" }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "secondary-sell-table");

  fireEvent.click(screen.getByRole("tab", { name: "Secondary market activity" }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "secondary-activity-table");

  clickNav("Documents");
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

test("expired login link keeps the email field while typing and sends only on submit", () => {
  window.localStorage.setItem(
    "banxum:login-flow:v1",
    JSON.stringify({ email: "", sent: false, linkExpired: true, resendCooldownUntil: 0 })
  );

  renderApp("/login");

  expect(screen.getByRole("heading", { name: "Login link expired" })).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "c" } });

  // The first keystroke neither replaces the field nor sends anything.
  expect(screen.getByPlaceholderText("you@example.com")).toHaveValue("c");
  expect(screen.queryByText(/We will send the new link to/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send a new magic link" })).toBeDisabled();

  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "claire@example.test" } });
  expect(screen.getByRole("heading", { name: "Login link expired" })).toBeInTheDocument();

  fireEvent.submit(screen.getByTestId("login-expired-form"));

  expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
  expect(screen.getByText("claire@example.test")).toBeInTheDocument();
});

test("expired login link switches to a different address without sending early", () => {
  window.localStorage.setItem(
    "banxum:login-flow:v1",
    JSON.stringify({ email: "investor@example.test", sent: true, linkExpired: true, resendCooldownUntil: 0 })
  );

  renderApp("/login?token=expired-token");

  expect(screen.getByText("investor@example.test")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Use a different email address" }));

  expect(screen.getByRole("heading", { name: "Login link expired" })).toBeInTheDocument();
  const field = screen.getByPlaceholderText("you@example.com");
  expect(field).toHaveValue("");
  expect(field).toHaveFocus();
  fireEvent.change(field, { target: { value: "n" } });
  expect(screen.getByPlaceholderText("you@example.com")).toHaveValue("n");
  expect(screen.queryByText(/We will send the new link to/)).not.toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "new@example.test" } });
  fireEvent.click(screen.getByRole("button", { name: "Send a new magic link" }));

  expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
  expect(screen.getByText("new@example.test")).toBeInTheDocument();
});

test("an expired session returns to the login screen with an explanation", () => {
  renderApp("/dashboard");
  expect(screen.getByRole("heading", { name: "Money working for you" })).toBeInTheDocument();

  act(() => reportSessionExpired());

  expect(window.location.pathname).toBe("/login");
  expect(screen.getByRole("heading", { name: "Log in" })).toBeInTheDocument();
  expect(screen.getByText("Your session has expired")).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "lukas.brunner@example.ch" } });
  fireEvent.submit(screen.getByTestId("login-magic-link-form"));

  expect(screen.getByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
  expect(hasSessionExpiredNotice()).toBe(false);
});

test("a restricted account is told why its data is unavailable", () => {
  renderApp("/dashboard");

  fireEvent.change(screen.getByDisplayValue("Active investor"), { target: { value: "restricted" } });

  expect(screen.getByRole("heading", { name: "Account access" })).toBeInTheDocument();
  expect(screen.getByText("Your account is restricted")).toBeInTheDocument();
  expect(screen.getByText(/You cannot view or move money while your account is restricted/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Contact support" })).toHaveAttribute("href", "mailto:support@banxum.com");

  clickNav("My investments");
  expect(screen.getByText("Your account is restricted")).toBeInTheDocument();
});

test("logos on public, sign-in and registration screens lead back to the home page", () => {
  const projects = renderApp("/projects");
  fireEvent.click(within(screen.getByRole("banner")).getByRole("link", { name: "BANXUM home" }));
  expect(window.location.pathname).toBe("/");
  expect(screen.getByRole("heading", { name: "Your capital. Your choice." })).toBeInTheDocument();
  expect(within(screen.getByRole("contentinfo")).getByRole("link", { name: "BANXUM home" })).toHaveAttribute("href", "/");
  projects.unmount();

  const login = renderApp("/login");
  const loginLogos = screen.getAllByRole("link", { name: "BANXUM home" });
  expect(loginLogos).toHaveLength(2);
  loginLogos.forEach((logo) => expect(logo).toHaveAttribute("href", "/"));
  fireEvent.click(loginLogos[1]);
  expect(window.location.pathname).toBe("/");
  expect(screen.getByRole("heading", { name: "Your capital. Your choice." })).toBeInTheDocument();
  login.unmount();

  renderApp("/register");
  fireEvent.click(screen.getByRole("link", { name: "BANXUM home" }));
  expect(window.location.pathname).toBe("/");
  expect(screen.getByRole("heading", { name: "Your capital. Your choice." })).toBeInTheDocument();
});

test("published primary-market loans appear in dashboard and marketplace open views", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  expect(screen.getByText(/closes within 7 days/)).toBeInTheDocument();

  clickNav("Primary market");

  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "5 of 5 match")
  ).toBeInTheDocument();
  expect(screen.getByText("Helvetia Logistik AG")).toBeInTheDocument();
  // The page opens in the Cards layout; each card keeps the copy-ID control and its
  // Invest button opens the same opportunity sheet as a list row.
  expect(screen.getByRole("button", { name: "Cards" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getAllByRole("button", { name: "Copy loan ID" }).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Invest in Helvetia Logistik AG" }));
  expect(screen.getByRole("dialog", { name: "Helvetia Logistik AG" })).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("dialog", { name: "Helvetia Logistik AG" })).getByRole("button", { name: "Close" }));

  // The List layout keeps the dedicated rating column and the icon-only copy button.
  fireEvent.click(screen.getByRole("button", { name: "List" }));
  expect(screen.getByRole("button", { name: "Sort by Rating" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Copy loan ID" }).length).toBeGreaterThan(0);
});

test("marketplace redesign preserves live filters, detail mode, and order guidance", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");

  expect(screen.getByRole("heading", { name: "These companies want your investment" })).toBeInTheDocument();
  expect(screen.getByText("Two ways to put your money to work")).toBeInTheDocument();
  expect(screen.getByText(/From CHF 500/i)).toBeInTheDocument();
  expect(screen.getByText("Available to commit")).toBeInTheDocument();
  expect(screen.getByText("available to invest")).toBeInTheDocument();
  // The collateral margin column lives in the List layout, which the page remembers.
  fireEvent.click(screen.getByRole("button", { name: "List" }));
  expect(screen.getAllByText("58.0%").length).toBeGreaterThan(0);
  expect(
    screen.getByText((_, element) => element?.className === "fs-count" && element.textContent === "5 of 5 match")
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Set your investing rule" }));
  expect(screen.getByRole("heading", { name: "It finds them. You approve them." })).toBeInTheDocument();
  clickNav("Primary market");

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
  clickNav("Primary market");

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

test("marketplace filter groups are multi-select without combined Either/Both chips", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");
  fireEvent.click(screen.getByRole("button", { name: /^Filter/ }));
  const panel = document.getElementById("marketplace-filter-panel") as HTMLElement;
  const count = (text: string) =>
    within(panel.parentElement as HTMLElement).getByText((_, element) => element?.className === "fs-count" && element.textContent === text);

  expect(within(panel).queryByRole("button", { name: /Either|Both/ })).not.toBeInTheDocument();
  // The old single-select "With collateral" chip is gone; "With collateral (any type)" is one multi-select option.
  expect(within(panel).queryByRole("button", { name: /^With collateral\s*\d*$/ })).not.toBeInTheDocument();
  expect(within(panel).getByText("any rating")).toBeInTheDocument();

  // Rating A together with B.
  fireEvent.click(within(panel).getByRole("button", { name: /^A\s/ }));
  fireEvent.click(within(panel).getByRole("button", { name: /^B\s/ }));
  expect(within(panel).getByRole("button", { name: /^A\s/ })).toHaveAttribute("aria-pressed", "true");
  expect(within(panel).getByRole("button", { name: /^B\s/ })).toHaveAttribute("aria-pressed", "true");
  expect(within(panel).queryByText("any rating")).not.toBeInTheDocument();
  expect(count("4 of 5 match")).toBeInTheDocument();

  // CHF together with EUR keeps both currencies.
  fireEvent.click(within(panel).getByRole("button", { name: /^CHF\s/ }));
  fireEvent.click(within(panel).getByRole("button", { name: /^EUR\s/ }));
  expect(count("4 of 5 match")).toBeInTheDocument();

  // "With collateral (any type)" includes every collateral type.
  fireEvent.click(within(panel).getByRole("button", { name: /^With collateral \(any type\)/ }));
  const typeChip = within(panel).getByRole("button", { name: /^Commercial real estate/ });
  expect(typeChip).toHaveAttribute("aria-pressed", "true");
  expect(typeChip).toBeDisabled();

  // Each ticked value has its own removable token.
  fireEvent.click(screen.getByRole("button", { name: "rated A" }));
  expect(screen.getByRole("button", { name: "rated B" })).toBeInTheDocument();
  expect(count("3 of 5 match")).toBeInTheDocument();
});

test("Smart Invest rule editor saves several values per condition", async () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Smart Invest" }));
  fireEvent.click(screen.getByRole("button", { name: "Adjust the rule" }));

  const editor = document.getElementById("rule-conditions") as HTMLElement;
  // Checkbox ids keep this test fast; the accessible names are covered by the wizard test.
  const box = (id: string) => document.getElementById(id) as HTMLInputElement;
  for (const combined of ["Either", "Both", "Any", "Anyone", "CHF and EUR", "Unsecured only"]) {
    expect(within(editor).queryByText(combined, { selector: "button" })).not.toBeInTheDocument();
  }
  // The saved fixture rule asks for any collateral: every type is included.
  expect(box("si-ed-col-any")).toBeChecked();
  expect(box("si-ed-col-real_estate")).toBeChecked();
  expect(box("si-ed-col-real_estate")).toBeDisabled();
  // The whole rating scale is offered, not only today's ratings (A, B, C).
  expect(box("si-ed-rating-A-").closest("label")).toHaveTextContent("A-");
  fireEvent.click(box("si-ed-rating-A"));
  fireEvent.click(box("si-ed-rating-A-"));
  fireEvent.click(box("si-ed-ccy-CHF"));
  fireEvent.click(box("si-ed-ccy-EUR"));
  expect(box("si-ed-rating-A")).toBeChecked();
  fireEvent.click(within(editor).getByText("Save the rule", { selector: "button" }));

  const rule = await screen.findByText("Risk rating", { selector: "dt" });
  expect(rule.nextElementSibling).toHaveTextContent("A, A-");
  expect(screen.getByText("Currency", { selector: "dt" }).nextElementSibling).toHaveTextContent("CHF, EUR");
  expect(screen.getByText("Collateral", { selector: "dt" }).nextElementSibling).toHaveTextContent("With collateral (any type)");
});

test("marketplace sheet shows the v9 opportunity layout and hands off to the order flow", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");
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

  // The order continues on the invest page, at the review step with the handed-over amount.
  expect(window.location.pathname).toBe("/marketplace/GA-2401/invest");
  expect(screen.queryByRole("dialog", { name: "Helvetia Logistik AG" })).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Invest" })).toBeInTheDocument();
  const orderPage = screen.getByRole("main");
  expect(within(orderPage).getByText("Review and sign").closest("li")).toHaveAttribute("aria-current", "step");
  expect(within(orderPage).getAllByText(/2.000\.00/).length).toBeGreaterThan(0);
});

test("marketplace closing countdown uses the platform as-of date", () => {
  const previousAsOf = balancesFixture.as_of;
  balancesFixture.as_of = "2026-06-17T10:00:00+02:00";
  try {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("Primary market");
    fireEvent.click(screen.getByText("Helvetia Logistik AG"));

    const sheet = screen.getByRole("dialog", { name: "Helvetia Logistik AG" });
    expect(within(sheet).getByText("2 days")).toBeInTheDocument();
    expect(within(sheet).getByText("to close")).toBeInTheDocument();
  } finally {
    balancesFixture.as_of = previousAsOf;
  }
});

test("opportunity sheet calculator validates the amount and projects the investor schedule", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");

  // Direct loan: proportional share of the contracted schedule.
  fireEvent.click(screen.getByText("Helvetia Logistik AG"));
  const sheet = screen.getByRole("dialog", { name: "Helvetia Logistik AG" });
  expect(within(sheet).queryByLabelText("Amount to calculate")).not.toBeInTheDocument();
  fireEvent.click(within(sheet).getByRole("button", { name: /Investment schedule calculator/ }));
  fireEvent.change(within(sheet).getByLabelText("Amount to calculate"), { target: { value: "500" } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Calculate" }));
  expect(within(sheet).getByRole("alert")).toHaveTextContent(/minimum in any one loan is CHF 1.000\.00/);
  fireEvent.change(within(sheet).getByLabelText("Amount to calculate"), { target: { value: "50000" } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Calculate" }));
  // Part of the fixture's CHF balance is past its holding limit, so the eligible part is the limit.
  expect(within(sheet).getByRole("alert")).toHaveTextContent(/of your CHF balance has enough holding time left for this loan's funding period/);
  fireEvent.change(within(sheet).getByLabelText("Amount to calculate"), { target: { value: "2000" } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Calculate" }));
  expect(within(sheet).getByText("24 payments")).toBeInTheDocument();
  expect(within(sheet).getByText(/assuming the campaign funds in full/)).toBeInTheDocument();
  fireEvent.click(within(sheet).getByRole("button", { name: "Close" }));

  // Originator subscription: only post-boundary rows, with participation applied.
  fireEvent.click(screen.getByText("Swiss SME equipment claim"));
  const claimSheet = screen.getByRole("dialog", { name: "Swiss SME equipment claim" });
  fireEvent.click(within(claimSheet).getByRole("button", { name: /Investment schedule calculator/ }));
  fireEvent.change(within(claimSheet).getByLabelText("Amount to calculate"), { target: { value: "16000" } });
  fireEvent.click(within(claimSheet).getByRole("button", { name: "Calculate" }));
  // 10% of the CHF 160'000 post-boundary principal: installment 2 pays 2'000 capital
  // and 1'440 x 10% x 70% = 100.80 interest; the boundary installment is excluded,
  // so only the three post-boundary fixture rows remain.
  expect(within(claimSheet).getByText("3 payments")).toBeInTheDocument();
  expect(within(claimSheet).getAllByText("2'000.00").length).toBeGreaterThan(0);
  expect(within(claimSheet).getByText("100.80")).toBeInTheDocument();
  expect(within(claimSheet).getByText(/boundary installment belongs to the Loan Originator/)).toBeInTheDocument();
});

test("marketplace sorts from the header and the sort menu", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");

  const loanTitles = () =>
    Array.from(document.querySelectorAll(".marketplace-opportunity-name strong")).map(
      (node) => node.textContent
    );
  const cardTitles = () =>
    Array.from(document.querySelectorAll(".mk-card-title button")).map((node) => node.textContent);

  // Sortable column headers belong to the List layout.
  fireEvent.click(screen.getByRole("button", { name: "List" }));

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

  // The same sort applies to the Cards layout.
  fireEvent.click(screen.getByRole("button", { name: "Cards" }));
  expect(cardTitles()[0]).toBe("Swiss SME equipment claim");

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
  clickNav("My investments");

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

test("loan-specific funding windows block an otherwise positive balance in the opportunity sheet", () => {
  const loan = marketplaceLoansFixture.find((item) => item.loan_id === "LO-2601")!;
  const lots = balanceLotsFixture.filter((lot) => lot.currency === loan.currency);
  const originals = lots.map((lot) => lot.withdrawal_deadline_at);
  lots.forEach((lot) => { lot.withdrawal_deadline_at = `${loan.funding_deadline}T00:00:00Z`; });
  try {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("Primary market");
    fireEvent.click(screen.getByText(loan.title));
    const sheet = screen.getByRole("dialog", { name: loan.title });
    expect(within(sheet).getByRole("button", { name: "Invest now" })).toBeDisabled();
  } finally {
    lots.forEach((lot, index) => { lot.withdrawal_deadline_at = originals[index]; });
  }
});

test("originator subscription validates the minimum and stages a par reservation", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");
  fireEvent.click(screen.getByText("Swiss SME equipment claim"));

  const claimSheet = screen.getByRole("dialog", { name: "Swiss SME equipment claim" });
  expect(within(claimSheet).getByText(/reserved.*available at par/i)).toBeInTheDocument();
  expect(within(claimSheet).getByText(/No investor interest accrues during funding/i)).toBeInTheDocument();
  expect(within(claimSheet).getByText(/Your holding activates automatically at funding close/i)).toBeInTheDocument();
  expect(within(claimSheet).queryByText(/after that payment is verified/i)).not.toBeInTheDocument();
  expect(within(claimSheet).getByText(/Your share of attributable interest/i)).toBeInTheDocument();
  fireEvent.click(within(claimSheet).getByRole("button", { name: "Invest now" }));

  const amountInput = within(claimSheet).getByRole("textbox", { name: "Amount to invest" });
  const reviewButton = within(claimSheet).getByRole("button", { name: "Review Order" });
  fireEvent.change(amountInput, { target: { value: "100" } });
  expect(within(claimSheet).getByText("The minimum in any one loan is CHF 500.00.")).toBeInTheDocument();
  expect(reviewButton).toBeDisabled();

  fireEvent.change(amountInput, { target: { value: "1000" } });
  fireEvent.click(reviewButton);
  expect(window.location.pathname).toBe("/marketplace/LO-2601/invest");
  expect(screen.getByRole("heading", { level: 1, name: "Invest" })).toBeInTheDocument();
  const orderPage = screen.getByRole("main");
  expect(within(orderPage).getByText(/Principal acquired at funding close/)).toBeInTheDocument();
  expect(within(orderPage).getByText(/Boundary installment/)).toBeInTheDocument();
  expect(within(orderPage).queryByText(/Executable for five minutes/)).not.toBeInTheDocument();
});

test("FX redesign uses CHF/EUR preview data and net-rate conversion history", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("FX");

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
  clickNav("Primary market");

  // Listing row of the refinancing loan carries the short tag.
  expect(screen.getAllByText("Refinanced").length).toBeGreaterThan(0);

  fireEvent.click(screen.getByText("Helvetia Logistik AG"));

  // The v9 sheet opens first; the schedule lives on its own page behind "Loan schedule".
  const refiSheet = screen.getByRole("dialog", { name: "Helvetia Logistik AG" });
  fireEvent.click(within(refiSheet).getByRole("button", { name: "Loan schedule →" }));

  // Detail header badge, the contracted schedule and the informational original-loan section.
  expect(window.location.pathname).toBe("/marketplace/GA-2401/schedule");
  expect(screen.getAllByText("Refinanced loan").length).toBeGreaterThan(0);
  expect(screen.getByText("Contracted repayment schedule")).toBeInTheDocument();
  expect(screen.getByText("No borrower payments yet")).toBeInTheDocument();
  expect(screen.getByText("Original loan")).toBeInTheDocument();
  expect(screen.getByText("Original loan repayment schedule")).toBeInTheDocument();
  expect(screen.getByText(/informational only and show the loan being refinanced/i)).toBeInTheDocument();
  expect(screen.getAllByRole("row", { name: /Totals/ }).length).toBe(2);
  // Column header plus nine installments settled before publication.
  expect(screen.getAllByText("Paid").length).toBe(10);
  // The schedule page keeps the key facts and lets you invest from here.
  expect(screen.getByText("Key facts")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Invest now/ })).toBeInTheDocument();
  // No story content on the schedule page; the switcher leads back to it.
  expect(screen.queryByText("Moving Swiss goods since 1994")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("navigation", { name: "Loan pages" }).querySelector("button")!);
  expect(window.location.pathname).toBe("/marketplace/GA-2401");
  expect(screen.getByText("Moving Swiss goods since 1994")).toBeInTheDocument();
});

test("meet the borrower page shows key facts plus the admin story, safely rendered", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");
  fireEvent.click(screen.getByText("Helvetia Logistik AG"));
  const sheet = screen.getByRole("dialog", { name: "Helvetia Logistik AG" });
  fireEvent.click(within(sheet).getByRole("button", { name: "Meet the borrower →" }));

  expect(window.location.pathname).toBe("/marketplace/GA-2401");
  // Key facts strip: borrower, rate, LTV, amount and the like — no tabs, no documents/risk pages.
  expect(screen.getByText("Key facts")).toBeInTheDocument();
  expect(screen.getByText("Loan-to-value")).toBeInTheDocument();
  expect(screen.getByText("58.0%")).toBeInTheDocument();
  expect(screen.getByText("Investor yield")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Terms & collateral" })).not.toBeInTheDocument();
  expect(screen.queryByText("Loan-originator evidence")).not.toBeInTheDocument();
  expect(screen.queryByText("Contracted repayment schedule")).not.toBeInTheDocument();
  // Story blocks render as real elements built from the JSON document.
  expect(screen.getByText("About the borrower")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Moving Swiss goods since 1994" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 3, name: "Why they borrow" })).toBeInTheDocument();
  expect(screen.getByText("42 trucks and two cross-dock warehouses").tagName).toBe("STRONG");
  const link = screen.getByRole("link", { name: "company site" });
  expect(link).toHaveAttribute("href", "https://example.test/helvetia");
  expect(link).toHaveAttribute("rel", "noopener noreferrer nofollow");
  const image = screen.getByRole("img", { name: "Helvetia Logistik cross-dock warehouse in Duebendorf" });
  expect(image).toHaveAttribute("src", "/api/v1/story-images/6f1d2c3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f/");
  expect(screen.getByText("The Duebendorf cross-dock, refinanced with this loan.")).toBeInTheDocument();
  expect(screen.getByText("Audited accounts since 2012").closest("ul")).not.toBeNull();
  expect(screen.getByText("We only borrow to buy assets that pay for themselves.").tagName).toBe("BLOCKQUOTE");
  // Investing works from this page too.
  expect(screen.getByRole("button", { name: /Invest now/ })).toBeInTheDocument();

  // A borrower without a story shows an honest empty state instead of filler.
  clickNav("Primary market");
  fireEvent.click(screen.getByText("Rhône Vignobles SA"));
  fireEvent.click(within(screen.getByRole("dialog", { name: "Rhône Vignobles SA" })).getByRole("button", { name: "Meet the borrower →" }));
  expect(screen.getByText("No story published yet for Rhône Vignobles SA")).toBeInTheDocument();
});

test("originator loans lead to the originator story and a schedule page with payment history", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");
  fireEvent.click(screen.getByText("Swiss SME equipment claim"));
  const sheet = screen.getByRole("dialog", { name: "Swiss SME equipment claim" });
  expect(within(sheet).queryByRole("button", { name: /credit file/ })).not.toBeInTheDocument();
  fireEvent.click(within(sheet).getByRole("button", { name: "Meet the originator →" }));

  // The story is about the loan originator, not the end borrower.
  expect(screen.getByText("About the loan originator")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Alpine Credit Partners AG" })).toBeInTheDocument();
  expect(screen.getByText("Historic loss rate below 1%").closest("ol")).not.toBeNull();
  expect(screen.getAllByText("Loan originator").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Skin in the game").length).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole("button", { name: "Loan schedule & payments" }));
  expect(window.location.pathname).toBe("/marketplace/LO-2601/schedule");
  expect(screen.getByText("Loan-originator evidence")).toBeInTheDocument();
  expect(screen.getByText("Current full loan schedule")).toBeInTheDocument();
  expect(screen.getByText("Historical borrower payments")).toBeInTheDocument();
  expect(screen.getByText("LO-2601-PAY-001")).toBeInTheDocument();
  expect(screen.queryByText("Alpine Credit Partners AG", { selector: "h2" })).not.toBeInTheDocument();
});

test("investing from the loan page runs on the invest page: amount, terms, email code and success", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Primary market");
  fireEvent.click(screen.getByText("Helvetia Logistik AG"));
  fireEvent.click(within(screen.getByRole("dialog", { name: "Helvetia Logistik AG" })).getByRole("button", { name: "Meet the borrower →" }));

  // The invest card of the loan page opens the invest page, not a dialog.
  fireEvent.click(screen.getByRole("button", { name: /Invest now/ }));
  expect(window.location.pathname).toBe("/marketplace/GA-2401/invest");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  const page = screen.getByRole("main");
  expect(within(page).getByRole("heading", { level: 1, name: "Invest" })).toBeInTheDocument();
  expect(within(page).getByText("Amount").closest("li")).toHaveAttribute("aria-current", "step");

  // Amount validation keeps the order from moving on below the minimum.
  const amount = within(page).getByRole("textbox", { name: "Investment amount" });
  fireEvent.change(amount, { target: { value: "500" } });
  expect(within(page).getByText(/Minimum order is CHF 1.000\.00\./)).toBeInTheDocument();
  expect(within(page).getByRole("button", { name: "Review order" })).toBeDisabled();
  fireEvent.change(amount, { target: { value: "2000" } });
  fireEvent.click(within(page).getByRole("button", { name: "Review order" }));

  // Both terms checkboxes are required before the email code step.
  expect(within(page).getByText("Review and sign").closest("li")).toHaveAttribute("aria-current", "step");
  const continueButton = within(page).getByRole("button", { name: "Continue" });
  expect(continueButton).toBeDisabled();
  fireEvent.click(within(page).getByRole("checkbox", { name: /primary-market investment terms/i }));
  expect(continueButton).toBeDisabled();
  fireEvent.click(within(page).getByRole("checkbox", { name: /risk disclosure/i }));
  fireEvent.click(continueButton);

  // A 6-digit email code confirms the order.
  const confirmButton = within(page).getByRole("button", { name: "Confirm order" });
  expect(confirmButton).toBeDisabled();
  fireEvent.change(within(page).getByLabelText("Email confirmation code"), { target: { value: "123456" } });
  fireEvent.click(confirmButton);

  // The success state stays on the page and offers the ways onward.
  expect(within(page).getByRole("heading", { name: "Order placed" })).toBeInTheDocument();
  expect(within(page).getByText("Done").closest("li")).toHaveAttribute("aria-current", "step");
  expect(within(page).getByRole("button", { name: "My investments" })).toBeInTheDocument();
  expect(within(page).getByRole("button", { name: "Primary market" })).toBeInTheDocument();
  fireEvent.click(within(page).getByRole("button", { name: "Back to the loan" }));
  expect(window.location.pathname).toBe("/marketplace/GA-2401");
});

test("immediate originator claim purchases run on the invest page: quote, terms, email code and success", () => {
  const detail = loanDetailsFixture.find((loan) => loan.loan_id === "LO-2601")!;
  const preview = marketplaceLoansFixture.find((loan) => loan.loan_id === "LO-2601")!;
  const originalFlows = [detail.investment_flow, preview.investment_flow];
  detail.investment_flow = "immediate_claim_assignment";
  preview.investment_flow = "immediate_claim_assignment";
  try {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("Primary market");
    fireEvent.click(screen.getByText("Swiss SME equipment claim"));
    fireEvent.click(within(screen.getByRole("dialog", { name: "Swiss SME equipment claim" })).getByRole("button", { name: "Meet the originator →" }));

    fireEvent.click(screen.getByRole("button", { name: "Review claim purchase" }));
    expect(window.location.pathname).toBe("/marketplace/LO-2601/invest");
    const page = screen.getByRole("main");
    expect(within(page).getByRole("heading", { level: 1, name: "Buy claim" })).toBeInTheDocument();
    expect(within(page).getByText("Swiss SME equipment claim · Alpine Credit Partners AG")).toBeInTheDocument();
    expect(within(page).getByText("Immediate legal assignment")).toBeInTheDocument();

    const amount = within(page).getByRole("textbox", { name: "Cash amount to invest" });
    fireEvent.change(amount, { target: { value: "100" } });
    expect(within(page).getByText(/Minimum investment is CHF 500\.00\./)).toBeInTheDocument();
    expect(within(page).getByRole("button", { name: "Get executable quote" })).toBeDisabled();
    fireEvent.change(amount, { target: { value: "1000" } });
    fireEvent.click(within(page).getByRole("button", { name: "Get executable quote" }));

    expect(within(page).getByText("Executable for five minutes")).toBeInTheDocument();
    expect(within(page).getByText("Your quoted cash flows")).toBeInTheDocument();
    expect(within(page).getByText("Cash consideration")).toBeInTheDocument();
    const continueButton = within(page).getByRole("button", { name: "Continue" });
    expect(continueButton).toBeDisabled();
    fireEvent.click(within(page).getByRole("checkbox", { name: /claim assignment/i }));
    fireEvent.click(within(page).getByRole("checkbox", { name: /risk disclosure/i }));
    fireEvent.click(continueButton);

    const purchaseButton = within(page).getByRole("button", { name: "Purchase claim" });
    expect(purchaseButton).toBeDisabled();
    fireEvent.change(within(page).getByLabelText("Email confirmation code"), { target: { value: "123456" } });
    fireEvent.click(purchaseButton);

    expect(within(page).getByRole("heading", { name: "Claim purchased" })).toBeInTheDocument();
    fireEvent.click(within(page).getByRole("button", { name: "My investments" }));
    expect(window.location.pathname).toBe("/portfolio");
  } finally {
    detail.investment_flow = originalFlows[0];
    preview.investment_flow = originalFlows[1];
  }
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
    clickNav("My investments");

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
    clickNav("My investments");
    fireEvent.click(screen.getByRole("tab", { name: "Orders" }));

    const released = screen.getByLabelText(/Balance released.*previously reserved/i);
    expect(released).toHaveTextContent("Balance released");
    fireEvent.mouseEnter(released);
    expect(screen.getByRole("tooltip")).toHaveTextContent(/released before funding closed/i);
    fireEvent.mouseLeave(released);

    const notInvested = screen.getByLabelText(/Not invested.*without any balance being allocated/i);
    expect(notInvested).toHaveTextContent("Not invested");
    fireEvent.mouseEnter(notInvested);
    expect(screen.getByRole("tooltip")).toHaveTextContent(/without any balance being allocated/i);
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
  clickNav("Secondary market");

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
  clickNav("My investments");

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

  // Portfolio insights stay on the page for every tab instead of belonging only to My loans.
  fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
  expect(screen.getByRole("heading", { name: "Activity" })).toBeInTheDocument();
  expect(screen.getByText("Earnings calendar")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Orders" }));
  expect(screen.getByRole("heading", { name: "Orders" })).toBeInTheDocument();
  expect(screen.getByText("Earnings calendar")).toBeInTheDocument();
  expect(screen.queryByText("Orders are intents")).not.toBeInTheDocument();
  expect(screen.getByText("#1")).toBeInTheDocument();
  const copyOrder = screen.getAllByRole("button", { name: "Copy order ID" })[0];
  fireEvent.mouseEnter(copyOrder);
  expect(screen.getByRole("tooltip")).toHaveTextContent("Copy order ID");
  fireEvent.mouseLeave(copyOrder);
  const copyLoan = screen.getAllByRole("button", { name: "Copy loan ID" })[0];
  fireEvent.mouseEnter(copyLoan);
  expect(screen.getByRole("tooltip")).toHaveTextContent("Copy loan ID");
  fireEvent.mouseLeave(copyLoan);
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
    clickNav("My investments");

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

// A holding opens as its own page (/portfolio/:holdingId), the design's investment page.
function openHoldingPage(loanTitle: string) {
  fireEvent.click(screen.getByText(loanTitle));
  expect(screen.getByRole("heading", { level: 1, name: loanTitle })).toBeInTheDocument();
  return screen.getByRole("main");
}

test("holding details open on the investment page with factual projections and collateral", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("My investments");

  const page = openHoldingPage("Engadin Alpine refinancing");
  expect(window.location.pathname).toBe("/portfolio/H-2310");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(within(page).getByRole("heading", { name: "Engadin Hospitality AG" })).toBeInTheDocument();
  expect(within(page).getByText("Interest received")).toBeInTheDocument();
  expect(within(page).getByText("Projected still to earn")).toBeInTheDocument();
  expect(within(page).getByText("Collateral")).toBeInTheDocument();
  expect(within(page).getByText("Registered real-estate security supporting the borrower obligation.")).toBeInTheDocument();
  expect(within(page).getByText("61.0% LTV")).toBeInTheDocument();
  expect(within(page).getByText(/Historical rows show the borrower payment recorded for the full loan|deterministic projected share/)).toBeInTheDocument();

  fireEvent.click(within(page).getByRole("button", { name: /Open timeline/ }));
  expect(within(page).getByRole("group", { name: "Borrower payment timeline" })).toBeInTheDocument();

  fireEvent.click(within(page).getByRole("button", { name: "View schedule" }));
  expect(within(page).getByRole("heading", { name: "Your future schedule" })).toBeInTheDocument();
  expect(within(page).getByRole("columnheader", { name: "Owed after" })).toBeInTheDocument();
  expect(within(page).getByRole("row", { name: /Totals/ })).toBeInTheDocument();

  // The back link returns to the list.
  fireEvent.click(within(page).getByRole("button", { name: "My investments" }));
  expect(window.location.pathname).toBe("/portfolio");
  expect(screen.getByRole("heading", { name: "Everything you own." })).toBeInTheDocument();
});

test("an unknown holding link shows a not-found investment page", () => {
  renderApp("/portfolio/H-UNKNOWN");

  expect(screen.getByRole("heading", { level: 1, name: "Investment not found" })).toBeInTheDocument();
  expect(screen.getByText("We could not find this investment")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Back to My investments" }));
  expect(window.location.pathname).toBe("/portfolio");
});

test("originator claim holdings disclose the retained claim without implying protection", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("My investments");
  fireEvent.click(screen.getByRole("button", { name: "EUR" }));

  const page = openHoldingPage("Nord Trans Cargo working capital");
  expect(
    within(page).getByText(
      /Nord Capital Finance must retain at least 15\.0% of the loan's current outstanding principal/
    )
  ).toBeInTheDocument();
  expect(within(page).queryByText(/loses alongside you/i)).not.toBeInTheDocument();
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
    clickNav("My investments");

    const page = openHoldingPage("Engadin Alpine refinancing");
    expect(within(page).getByText(/18 days past due/)).toBeInTheDocument();
    expect(within(page).getByText(/12\.0% annual default-interest rate/)).toBeInTheDocument();
    expect(within(page).getByText(/does not estimate accrued default interest from days past due/)).toBeInTheDocument();
    expect(within(page).queryByText(/a day at today/i)).not.toBeInTheDocument();
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
    clickNav("My investments");

    const page = openHoldingPage("Engadin Alpine refinancing");
    expect(
      within(page).getByText(/Funding has closed, but the borrower payout is still pending/)
    ).toBeInTheDocument();
    expect(
      within(page).getByRole("button", { name: "List on secondary market" })
    ).toBeDisabled();

    fireEvent.click(within(page).getByRole("button", { name: "My investments" }));
    clickNav("Secondary market");
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
    clickNav("My investments");

    const page = openHoldingPage("Engadin Alpine refinancing");
    fireEvent.click(within(page).getByRole("button", { name: "List on secondary market" }));

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
  clickNav("My investments");

  expect(screen.getByText("Listed")).toBeInTheDocument();
  const page = openHoldingPage("Engadin Alpine refinancing");
  expect(within(page).getByRole("button", { name: "Manage secondary listing" })).toBeInTheDocument();
  fireEvent.click(within(page).getByRole("button", { name: "Manage secondary listing" }));

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
  clickNav("Secondary market");
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
  clickNav("Secondary market");
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

  fireEvent.click(within(screen.getByRole("banner")).getByRole("button", { name: "Open account" }));
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

test("QA controls distinguish the original seed from an optional manual snapshot", () => {
  renderApp("/admin");
  fireEvent.click(screen.getByRole("button", { name: "QA mode" }));
  expect(screen.getByRole("heading", { name: "QA development mode" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create snapshot" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Restore snapshot" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Restore seed" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Confirmation"), { target: { value: "REVERT QA DB" } });
  expect(screen.getByRole("button", { name: "Restore seed" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Restore snapshot" })).toBeDisabled();
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

test("admin loans distinguish annual borrower interest from investor yield", () => {
  const originatorLoan = {
    ...loansFixture[0],
    id: "loan-originator-rate-test",
    title: "Originator rate comparison",
    product_type: "originator_claim",
    borrower_id: null,
    originator_id: "originator-rate-test",
    originator_name: "Rate test originator",
    opportunity_status: "open",
    interest_rate_bps: 990,
    yield_bps: 703
  };
  loansFixture.push(originatorLoan);
  try {
    renderApp("/admin");
    fireEvent.click(screen.getByRole("button", { name: "Loans" }));
    const table = screen.getByRole("table", { name: "Admin loans" });
    const headers = within(table).getAllByRole("columnheader").map((header) => header.textContent);
    const interestIndex = headers.indexOf("Loan interest rate");
    const yieldIndex = headers.indexOf("Investor yield");
    expect(interestIndex).toBeGreaterThan(-1);
    expect(yieldIndex).toBe(interestIndex + 1);
    expect(headers).not.toContain("Yield");
    for (const loan of [loansFixture[0], loansFixture[1], originatorLoan]) {
      const row = within(table).getByText(loan.title).closest("tr")!;
      const cells = within(row).getAllByRole("cell");
      expect(cells[interestIndex]).toHaveTextContent(`${(loan.interest_rate_bps / 100).toFixed(2)}% p.a.`);
      expect(cells[yieldIndex]).toHaveTextContent(`${(loan.yield_bps / 100).toFixed(2)}% p.a.`);
    }
  } finally {
    loansFixture.splice(loansFixture.indexOf(originatorLoan), 1);
  }
});

test("deposit instructions explain how to use the required payment reference", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav(/^Account/);
  fireEvent.click(within(screen.getByRole("main")).getByRole("button", { name: "Add Funds" }));

  expect(screen.getByText("Payment reference - required")).toBeInTheDocument();
  expect(screen.getByText(/enter this reference unchanged in the payment details/i)).toBeInTheDocument();
  expect(screen.getByText(/may delay allocation of the funds/i)).toBeInTheDocument();
});

test("account page shows one card per currency whose actions open that currency", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav(/^Account/);

  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Account", level: 1 })).toBeInTheDocument();
  expect(within(main).getByRole("heading", { name: "CHF account" })).toBeInTheDocument();
  expect(within(main).getByRole("heading", { name: "EUR account" })).toBeInTheDocument();
  expect(within(main).getByRole("heading", { name: "CHF balance lots" })).toBeInTheDocument();
  expect(within(main).getByRole("heading", { name: "Rules for your money" })).toBeInTheDocument();

  fireEvent.click(within(main).getByRole("button", { name: "Add EUR" }));
  expect(screen.getByRole("dialog", { name: "Add Funds · EUR" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Done" }));

  fireEvent.click(within(main).getAllByRole("button", { name: "Withdraw to IBAN" })[1]);
  expect(screen.getByRole("dialog", { name: "Withdraw EUR" })).toBeInTheDocument();
});

test("profile and settings keep every section reachable from the side menu", () => {
  renderApp();

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Profile & Settings");

  expect(screen.getByRole("heading", { name: "Profile & Settings", level: 1 })).toBeInTheDocument();
  const menu = screen.getByRole("navigation", { name: "Settings sections" });
  expect(within(menu).getByRole("button", { name: "Profile" })).toHaveAttribute("aria-current", "true");
  expect(screen.getByText("Lukas Brunner", { selector: "dd" })).toBeInTheDocument();

  fireEvent.click(within(menu).getByRole("button", { name: "Verification" }));
  expect(screen.getByText("Identity (KYC/AML)")).toBeInTheDocument();

  fireEvent.click(within(menu).getByRole("button", { name: "Payout accounts" }));
  expect(screen.getByRole("heading", { name: "Payout accounts", level: 2 })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Add/update IBAN" }));
  expect(screen.getByRole("dialog", { name: "Add/update payout IBAN" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  fireEvent.click(within(menu).getByRole("button", { name: "Communication" }));
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(screen.getByText("Product updates and newsletter")).toBeInTheDocument();

  fireEvent.click(within(menu).getByRole("button", { name: "Support & account" }));
  expect(screen.getByRole("link", { name: "support@banxum.com" })).toHaveAttribute("href", "mailto:support@banxum.com");
  fireEvent.click(screen.getByRole("button", { name: "Open" }));
  expect(screen.getByRole("heading", { name: "Help", level: 1 })).toBeInTheDocument();
});

test("withdrawal dashboard drawer contains the executable withdrawal form", () => {
  renderApp("/admin");

  fireEvent.click(screen.getByRole("button", { name: /^Withdrawals:/i }));
  const withdrawalTitle = screen.getAllByText("Investor withdrawal awaiting bank execution")[0];
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
  // Both the requested and the forced withdrawal must be resolvable, and the
  // forced one (returned in both withdrawal queues) is listed only once.
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

test("borrower repayment asks for the payer account before recording", () => {
  renderApp("/admin");

  fireEvent.click(screen.getByRole("button", { name: "Loans" }));
  const lateLoanRow = screen.getAllByText("Basel Riverside refurbishment")[0].closest("tr");
  fireEvent.click(within(lateLoanRow as HTMLElement).getByRole("button", { name: "Manage" }));
  fireEvent.click(screen.getByRole("button", { name: /Record borrower repayment/ }));

  const payerAccount = screen.getByLabelText("Payer account");
  expect(payerAccount).toBeRequired();
  fireEvent.click(screen.getByRole("button", { name: "Record repayment" }));
  expect(
    screen.getByText("Enter the account the borrower paid from (IBAN or account number).")
  ).toBeInTheDocument();
  expect(payerAccount).toHaveAttribute("aria-invalid", "true");
  expect(screen.queryByText("Preview action recorded")).not.toBeInTheDocument();

  fireEvent.change(payerAccount, { target: { value: "CH93 0076 2011 6238 5295 7" } });
  expect(screen.queryByText(/Enter the account the borrower paid from/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Record repayment" }));
  expect(screen.getByText("Preview action recorded")).toBeInTheDocument();
});

function loginDemo() {
  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
}

test("public and portal footers link the platform Terms and Conditions", () => {
  const site = renderApp("/projects");
  const siteLink = within(screen.getByRole("contentinfo")).getByRole("link", { name: "Terms and Conditions" });
  expect(siteLink).toHaveAttribute("href", "/legal/registration");
  site.unmount();

  renderApp();
  loginDemo();
  const portalLinks = screen.getByRole("navigation", { name: "Legal and help" });
  expect(within(portalLinks).getByRole("link", { name: "Terms and Conditions" })).toHaveAttribute("href", "/legal/registration");
});

test("Add Funds offers a copy icon for the IBAN and QR IBAN in CHF and EUR", () => {
  renderApp();
  loginDemo();

  fireEvent.click(within(screen.getByRole("banner", { name: "Investor account header" })).getByRole("button", { name: "Add Funds" }));
  const chf = screen.getByRole("dialog", { name: "Add Funds · CHF" });
  expect(within(chf).getByRole("button", { name: "Copy IBAN" })).toBeInTheDocument();
  expect(within(chf).getByRole("button", { name: "Copy QR IBAN" })).toBeInTheDocument();
  expect(within(chf).getByRole("button", { name: "Copy payment reference" })).toBeInTheDocument();

  fireEvent.change(within(chf).getByLabelText("Currency"), { target: { value: "EUR" } });
  const eur = screen.getByRole("dialog", { name: "Add Funds · EUR" });
  expect(within(eur).getByRole("button", { name: "Copy IBAN" })).toBeInTheDocument();
});

test("Smart Invest matches show the purpose as a readable label under the name", () => {
  const match = smartInvestFixture.matches[0];
  const previous = { purpose: match.purpose, originator_name: match.originator_name };
  match.purpose = "bridge_financing";
  match.originator_name = null;
  try {
    renderApp();
    loginDemo();
    fireEvent.click(screen.getByRole("button", { name: "Smart Invest" }));

    const table = screen.getByRole("table", { name: "Smart Invest matches" });
    expect(within(table).getByText("Bridge financing")).toBeInTheDocument();
    expect(within(table).queryByText(/bridge_financing/)).not.toBeInTheDocument();
  } finally {
    match.purpose = previous.purpose;
    match.originator_name = previous.originator_name;
  }
});

test("rule desk toggle unselects every match and reselects them all", () => {
  const rhone = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2399");
  const leman = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2390");
  const extra = [rhone, leman].map((loan) => ({ ...smartInvestFixture.matches[0], ...loan }) as (typeof smartInvestFixture.matches)[number]);
  smartInvestFixture.matches = [...smartInvestFixture.matches, ...extra];
  smartInvestFixture.match_count = smartInvestFixture.matches.length;
  try {
    renderApp();
    loginDemo();

    // Everything starts ticked.
    expect(screen.getByRole("button", { name: "Untick Rhône Vignobles SA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Untick Léman BioTech SA" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Unselect all" }));
    expect(screen.getByRole("button", { name: "Tick Rhône Vignobles SA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tick Léman BioTech SA" })).toBeInTheDocument();
    expect(screen.getByText(/0 of 2 ticked/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review & confirm →" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByRole("button", { name: "Untick Rhône Vignobles SA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Untick Léman BioTech SA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unselect all" })).toBeInTheDocument();
  } finally {
    smartInvestFixture.matches = smartInvestFixture.matches.filter((match) => !extra.includes(match));
    smartInvestFixture.match_count = smartInvestFixture.matches.length;
  }
});

test("notifications open their target, can be marked read one by one or all at once", async () => {
  renderApp();
  loginDemo();
  const topbar = screen.getByRole("banner", { name: "Investor account header" });
  const nav = screen.getByRole("navigation", { name: "Investor portal navigation" });
  expect(within(nav).getByRole("button", { name: /^Notifications\s*2$/ })).toBeInTheDocument();

  fireEvent.click(within(topbar).getByRole("button", { name: "Notifications" }));
  expect(within(topbar).getByText("Notifications (2 new)")).toBeInTheDocument();
  fireEvent.click(within(topbar).getByRole("menuitem", { name: 'Mark "Balance ageing - day 57" as read' }));
  expect(await within(topbar).findByText("Notifications (1 new)")).toBeInTheDocument();
  expect(within(nav).getByRole("button", { name: /^Notifications\s*1$/ })).toBeInTheDocument();

  // Opening a notification marks it read and goes to the holding it is about.
  fireEvent.click(within(topbar).getByRole("menuitem", { name: /^Loan in default/ }));
  expect(window.location.pathname).toBe("/portfolio/H-2201");
  expect(await within(nav).findByRole("button", { name: /^Notifications$/ })).toBeInTheDocument();

  fireEvent.click(within(nav).getByRole("button", { name: /^Notifications/ }));
  expect(screen.getByText("Up to date")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Mark ".*" as read$/ })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
});

test("the Notifications page marks all as read and opens a notice's page", async () => {
  renderApp();
  loginDemo();
  clickNav(/^Notifications/);

  expect(screen.getByText("2 unread")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: 'Mark "Loan in default" as read' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
  expect(await screen.findByText("Up to date")).toBeInTheDocument();
  expect(screen.queryByText("Unread")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Balance ageing - day 57" }));
  expect(window.location.pathname).toBe("/balances");
});

test("Invest now explains when the balance is too old for the funding window", () => {
  const chfLots = balanceLotsFixture.filter((lot) => lot.currency === "CHF");
  const previous = chfLots.map((lot) => lot.bucket);
  chfLots.forEach((lot) => {
    lot.bucket = "overdue";
  });
  try {
    renderApp();
    loginDemo();
    clickNav("Primary market");
    fireEvent.click(screen.getByText("Helvetia Logistik AG"));

    const sheet = screen.getByRole("dialog", { name: "Helvetia Logistik AG" });
    const investNow = within(sheet).getByRole("button", { name: "Invest now" });
    expect(investNow).toBeDisabled();
    expect(investNow.getAttribute("title")).toMatch(/does not have enough holding time left for this loan's funding period\. Every incoming amount has a 60-day holding limit/);
    expect(investNow.getAttribute("title")).not.toMatch(/No investable balance is available/);
    expect(within(sheet).getByText("Your CHF balance does not have enough holding time left for this loan's funding period.")).toBeInTheDocument();
  } finally {
    chfLots.forEach((lot, index) => {
      lot.bucket = previous[index];
    });
  }
});

test("an amount just over the remaining capacity names the capacity, not the wallet", () => {
  const preview = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2390");
  const detail = loanDetailsFixture.find((loan) => loan.loan_id === "GA-2390");
  expect(preview).toBeDefined();
  expect(detail).toBeDefined();
  const previous = [preview!.remaining_capacity_minor, preview!.fillable_amount_minor, detail!.remaining_capacity_minor, detail!.fillable_amount_minor];
  preview!.remaining_capacity_minor = 5_000_00;
  preview!.fillable_amount_minor = 5_000_00;
  detail!.remaining_capacity_minor = 5_000_00;
  detail!.fillable_amount_minor = 5_000_00;
  try {
    renderApp();
    loginDemo();
    clickNav("Primary market");
    fireEvent.click(screen.getByText("Léman BioTech SA"));
    const sheet = screen.getByRole("dialog", { name: "Léman BioTech SA" });
    fireEvent.click(within(sheet).getByRole("button", { name: "Invest now" }));
    fireEvent.change(within(sheet).getByLabelText("Amount to invest"), { target: { value: "5001" } });
    expect(within(sheet).getByText(/This opportunity has only CHF 5.000\.00 left, so that is the most you can invest here\./)).toBeInTheDocument();
    expect(within(sheet).queryByText(/is not lent/)).not.toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "Review Order" })).toBeDisabled();
    fireEvent.click(within(sheet).getByRole("button", { name: "Close" }));

    // The invest page names the same limit.
    window.history.pushState({}, "", "/marketplace/GA-2390/invest");
    fireEvent(window, new PopStateEvent("popstate"));
    fireEvent.change(screen.getByLabelText("Investment amount"), { target: { value: "5001" } });
    expect(screen.getByText(/This opportunity has only CHF 5.000\.00 left/)).toBeInTheDocument();
  } finally {
    [preview!.remaining_capacity_minor, preview!.fillable_amount_minor, detail!.remaining_capacity_minor, detail!.fillable_amount_minor] = previous;
  }
});

test("activity labels each withdrawal outcome and shows the cancellation credit", () => {
  renderApp();
  loginDemo();
  clickNav("My investments");
  fireEvent.click(screen.getByRole("tab", { name: "Activity" }));

  const cancelledRow = screen.getByText("Cancelled").closest("tr") as HTMLElement;
  expect(within(cancelledRow).getAllByText("Withdrawal request").length).toBeGreaterThan(0);
  const finalizedRow = screen.getByText("Finalized").closest("tr") as HTMLElement;
  expect(within(finalizedRow).getAllByText("Withdrawal request").length).toBeGreaterThan(0);
  const reversalRow = screen.getByText("Returned to balance").closest("tr") as HTMLElement;
  expect(within(reversalRow).getByText("Withdrawal cancelled")).toBeInTheDocument();
  expect(within(reversalRow).getByText("withdrawal reversal")).toBeInTheDocument();
  expect(within(reversalRow).getByText(/\+2.000\.00/)).toBeInTheDocument();
});

test("Account shows the frozen balance apart from the penalty charged on the lots", () => {
  const overdueLot = balanceLotsFixture.find((lot) => lot.currency === "CHF" && lot.bucket === "overdue");
  const chf = balancesFixture.summaries.find((summary) => summary.currency === "CHF");
  expect(overdueLot).toBeDefined();
  expect(chf).toBeDefined();
  overdueLot!.penalized_amount_minor = 49_00;
  chf!.penalty_charged_minor = 49_00;
  try {
    renderApp();
    loginDemo();
    clickNav(/^Account/);

    expect(screen.queryByText("Penalty/frozen")).not.toBeInTheDocument();
    expect(screen.getAllByText("Frozen").length).toBe(2);
    const lots = screen.getByRole("heading", { name: "CHF balance lots" }).closest("section") as HTMLElement;
    expect(within(lots).getByText("Penalty charged", { selector: "span" })).toBeInTheDocument();
    expect(within(lots).getByRole("columnheader", { name: "Penalty charged" })).toBeInTheDocument();
    expect(within(lots).getAllByText(/49\.00/).length).toBeGreaterThanOrEqual(2);
  } finally {
    overdueLot!.penalized_amount_minor = 0;
    chf!.penalty_charged_minor = 0;
  }
});
