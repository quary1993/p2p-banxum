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
import { siteDesignProjectIds } from "./site/siteFixtures";
import { formatMoneyMinor, formatRateBps } from "./investorPortal/format";
import { enterPin } from "./test/pin";

/** The U33 home page's heading. */
const HOME_HEADING = "Invest in business loans. Secured by collateral or guarantees.";

/** jsdom has no matchMedia: the public site's layout below 1120 px (its mobile edition). */
function emulateNarrowLayout() {
  const original = window.matchMedia;
  window.matchMedia = ((query: string) => ({
    matches: query.includes("max-width:1119px"),
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false
  })) as unknown as typeof window.matchMedia;
  return () => {
    window.matchMedia = original;
  };
}

function renderApp(path = "/") {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

// The U33 sidebar (Phase 17.1 S1): links with the design names ("Investment opportunities" and
// "Resale market" replace the old "Projects" sub-entries "Primary market" and "Secondary market").
function clickNav(label: string | RegExp) {
  const nav = screen.getByRole("navigation", { name: "Investor portal navigation" });
  // An entry can carry its count ("Investment opportunities 5").
  const name = typeof label === "string" ? new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(\\s+\\d+)?$`) : label;
  fireEvent.click(within(nav).getByRole("link", { name }));
}

// Sign out and Add funds live in the U33 account menu of the header.
function openAccountMenu() {
  fireEvent.click(within(screen.getByRole("banner", { name: "Investor account header" })).getByRole("button", { name: "Account menu" }));
}

function signOut() {
  openAccountMenu();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
}

// Investment opportunities: the result counter ("5 opportunities · 5 open").
function resultLine() {
  return document.querySelector(".bxm-op-result [role=status]") as HTMLElement;
}

// In-app address change (the browser's back/forward path).
function goToPath(path: string) {
  window.history.pushState({}, "", path);
  fireEvent(window, new PopStateEvent("popstate"));
}

// Review & sign: the amount is edited in place and applied with Enter.
function applyReviewAmount(amount: string) {
  const input = screen.getByRole("textbox", { name: "Your investment amount" });
  fireEvent.change(input, { target: { value: amount } });
  fireEvent.keyDown(input, { key: "Enter" });
}

// Preview mode: the fixture account state is switched in the floating preview panel.
function setUxState(value: string) {
  fireEvent.click(screen.getByRole("button", { name: "Preview" }));
  fireEvent.change(screen.getByLabelText("UX state"), { target: { value } });
}

test("renders the public site shell on the projects page", () => {
  renderApp("/projects");

  const header = screen.getByRole("banner");
  expect(within(header).getByRole("img", { name: "Banxum" })).toBeInTheDocument();
  const footer = screen.getByRole("contentinfo");
  expect(within(footer).getByText(/Owned and operated by Garanta Finanzgruppe AG\./)).toBeInTheDocument();
  expect(footer).toHaveTextContent(`© ${new Date().getFullYear()} Garanta Finanzgruppe AG`);
  expect(screen.getByRole("heading", { level: 1, name: "Companies looking for a loan" })).toBeInTheDocument();
  expect(within(header).getByRole("link", { name: "Open account" })).toHaveAttribute("href", "/register");
  expect(within(header).getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
  expect(within(header).getByRole("link", { name: "Projects" })).toHaveAttribute("aria-current", "page");
  expect(within(header).getByRole("link", { name: "Help" })).not.toHaveAttribute("aria-current");
  // The design's skin: html.bxs (not the investor area's html.bxm) and body.bxm-site.
  expect(document.documentElement).toHaveClass("bxs");
  expect(document.documentElement).not.toHaveClass("bxm");
  expect(document.body).toHaveClass("bxm-site");
});

test("public project URLs open the project, and the crumbs lead back to the opportunities", () => {
  renderApp("/");
  fireEvent.click(screen.getByRole("link", { name: "View details: Packaging factory extension" }));
  expect(window.location.pathname).toBe(`/projects/${siteDesignProjectIds["bx-1046"]}`);
  expect(screen.getByRole("heading", { level: 1, name: "Packaging factory extension" })).toBeInTheDocument();
  expect(document.title).toBe("Packaging factory extension · Banxum");
  // U33 skin: html.bxp with the project bundle, not the October skin.
  expect(document.documentElement).toHaveClass("bxp", "bxp-project");
  expect(document.documentElement).not.toHaveClass("bxs");

  fireEvent.click(screen.getByRole("link", { name: "All opportunities" }));
  expect(window.location.pathname).toBe("/");
  expect(window.location.hash).toBe("#opportunities");
  expect(screen.getByRole("heading", { level: 1, name: HOME_HEADING })).toBeInTheDocument();
  expect(document.documentElement).toHaveClass("bxp-home");
  expect(document.documentElement).not.toHaveClass("bxp-project");
});

test("page titles follow public routes and reset after sign out", () => {
  const projects = renderApp("/projects");
  expect(document.title).toBe("Projects · Banxum");
  projects.unmount();

  renderApp("/smart-invest");
  expect(document.title).toBe("Smart Invest · BANXUM");
  signOut();
  expect(window.location.pathname).toBe("/");
  expect(document.title).toBe("Banxum · Lend to real companies");
});

test("public home page shows three open projects, the calculator and links to all projects", () => {
  renderApp();

  expect(screen.getByRole("heading", { level: 1, name: HOME_HEADING })).toBeInTheDocument();
  // U33-DEC-38: no "real assets" claim and no "Your investment is protected".
  expect(screen.queryByText(/real assets/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/investment is protected/i)).not.toBeInTheDocument();
  expect(screen.getByText("Every loan is secured by collateral or guarantees.")).toBeInTheDocument();
  // The hero rate is the highest rate of the open projects.
  expect(screen.getByLabelText("Annual interest up to 10.5 percent")).toBeInTheDocument();

  // U33-DEC-39: three open projects (closing soonest first), from the public projects API.
  const opportunities = screen.getByRole("region", { name: "Investment opportunities" });
  const cards = within(opportunities).getAllByRole("article");
  expect(cards).toHaveLength(3);
  expect(cards.map((card) => within(card).getByRole("heading", { level: 3 }).textContent)).toEqual([
    "Dental practice equipment",
    "Packaging factory extension",
    "Wine cellar expansion"
  ]);
  expect(within(cards[1]).getByText("Loan-to-value: 58%")).toBeInTheDocument();
  // No risk rating on the public site (U33-DEC-16).
  expect(within(opportunities).queryByText(/Risk/)).not.toBeInTheDocument();

  // The calculator uses the same open projects.
  const choices = within(opportunities).getByRole("radiogroup", { name: "Choose an opportunity" });
  expect(within(choices).getAllByRole("radio")).toHaveLength(3);
  fireEvent.click(within(choices).getByRole("radio", { name: /Packaging factory extension/ }));
  expect(within(choices).getByRole("radio", { name: /Packaging factory extension/ })).toHaveAttribute("aria-checked", "true");
  const amount = within(opportunities).getByLabelText("Your investment");
  fireEvent.change(amount, { target: { value: "5" } });
  expect(within(opportunities).getByRole("status")).toHaveTextContent(/^The minimum for this opportunity is CHF /);
  fireEvent.change(amount, { target: { value: "50,000" } });
  expect(within(opportunities).getByText("CHF 50,000.00")).toBeInTheDocument();

  // How it works: confirmation with the PIN (U33-DEC-01), no authenticator code.
  expect(screen.getByText("Confirm with your PIN")).toBeInTheDocument();
  expect(screen.queryByText(/authenticator/i)).not.toBeInTheDocument();
  expect(screen.getByText("What can I review before investing?").closest("details")).toHaveAttribute("open");
  expect(screen.getByText("What fees will I pay?").closest("details")).not.toHaveAttribute("open");
  expect(within(screen.getByRole("contentinfo")).getByText(/^Banxum is a brand of Garanta Finanzgruppe AG, Schauplatzgasse 26/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "All projects, including funded and repaid loans" }));
  expect(window.location.pathname).toBe("/projects");
  expect(screen.getByRole("heading", { level: 1, name: "Companies looking for a loan" })).toBeInTheDocument();
  expect(document.documentElement).toHaveClass("bxs");
  expect(document.documentElement).not.toHaveClass("bxp");
});

test("the old FAQ address opens Help for logged-out visitors", () => {
  renderApp("/faq");

  expect(window.location.pathname).toBe("/help");
  expect(screen.getByRole("heading", { level: 1, name: "Questions and answers" })).toBeInTheDocument();
  expect(document.title).toBe("Help · Banxum");
});

test("site routing: U33 pages, backend legal templates, unknown addresses", () => {
  const legal = renderApp("/legal/terms");
  expect(screen.getByRole("heading", { level: 1, name: "Terms & conditions" })).toBeInTheDocument();
  expect(document.title).toBe("Terms & conditions · Banxum");
  legal.unmount();

  // The investor flows link to the published templates: the same address is the site's terms
  // page (the published "registration" template live, the content outline in preview).
  const template = renderApp("/legal/registration");
  expect(screen.getByRole("heading", { level: 1, name: "Terms & conditions" })).toBeInTheDocument();
  const others = within(screen.getByRole("list", { name: "Legal pages" }));
  expect(others.queryByRole("link", { name: "Terms & conditions" })).not.toBeInTheDocument();
  expect(others.getByRole("link", { name: "Privacy policy" })).toHaveAttribute("href", "/legal/privacy");
  expect(window.location.pathname).toBe("/legal/registration");
  template.unmount();

  const unknown = renderApp("/nothing-here");
  expect(screen.getByRole("heading", { level: 1, name: "This page does not exist" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/nothing-here");
  expect(document.title).toBe("Not found · Banxum");
  fireEvent.click(within(screen.getByRole("main")).getByRole("link", { name: "Home" }));
  expect(window.location.pathname).toBe("/");
  expect(screen.getByRole("heading", { level: 1, name: HOME_HEADING })).toBeInTheDocument();
  unknown.unmount();

  renderApp("/how-it-works");
  expect(screen.getByRole("heading", { level: 1, name: "From your first transfer to the last repayment" })).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("contentinfo")).getByRole("link", { name: "Statistics" }));
  expect(window.location.pathname).toBe("/statistics");
  expect(screen.getByRole("heading", { level: 1, name: "Every loan, including the ones that went wrong" })).toBeInTheDocument();
});

test("the phone menu opens and closes like the design", () => {
  const restore = emulateNarrowLayout();
  try {
    renderApp("/");
    const toggle = screen.getByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAccessibleName("Close menu");
    expect(document.body).toHaveClass("mobile-menu-open");
    expect(screen.getByRole("banner")).toHaveClass("header", "menu-open");
    expect(screen.getByRole("main")).toHaveAttribute("inert");
    const menu = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(menu).getByRole("link", { name: "For loan originators" })).toHaveAttribute("href", "/originators");
    // The mobile edition moves Contact into the menu.
    expect(within(menu).getByRole("link", { name: "Contact" })).toHaveClass("mobile-contact");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.body).not.toHaveClass("mobile-menu-open");

    fireEvent.click(toggle);
    fireEvent.click(within(screen.getByRole("navigation", { name: "Main navigation" })).getByRole("link", { name: "About Banxum" }));
    expect(window.location.pathname).toBe("/about");
    expect(document.body).not.toHaveClass("mobile-menu-open");
    expect(screen.getByRole("heading", { level: 1, name: /An international/ })).toBeInTheDocument();
  } finally {
    restore();
  }
});

test("the cookie choice is stored and can be changed from the footer", () => {
  renderApp("/");
  const notice = screen.getByRole("dialog", { name: "Cookies" });
  expect(within(notice).getByRole("link", { name: "Cookie policy" })).toHaveAttribute("href", "/legal/cookies");

  fireEvent.click(within(notice).getByRole("button", { name: "Necessary only" }));
  expect(screen.queryByRole("dialog", { name: "Cookies" })).not.toBeInTheDocument();
  expect(JSON.parse(window.localStorage.getItem("bxm-site-cookies") ?? "{}")).toMatchObject({ necessary: true, measure: false });
  expect(screen.getByText("Cookie choice saved.")).toBeInTheDocument();

  fireEvent.click(within(screen.getByRole("contentinfo")).getByRole("link", { name: "Cookie settings" }));
  const settings = screen.getByRole("dialog", { name: "Cookies" });
  expect(within(settings).getByLabelText("Necessary (always on)")).toBeDisabled();
  fireEvent.click(within(settings).getByLabelText("Measurement of visits"));
  fireEvent.click(within(settings).getByRole("button", { name: "Save choice" }));
  expect(JSON.parse(window.localStorage.getItem("bxm-site-cookies") ?? "{}")).toMatchObject({ measure: true });
});

test("the language menu announces German and French with a toast", () => {
  renderApp("/");
  const header = screen.getByRole("banner");
  const toggle = within(header).getByRole("button", { name: "Language: English" });
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  const menu = within(header).getByRole("menu", { name: "Language" });
  expect(within(menu).getByRole("menuitemradio", { name: /^English/ })).toHaveAttribute("aria-checked", "true");
  const german = within(menu).getByRole("menuitemradio", { name: /^Deutsch/ });
  expect(german).toHaveAttribute("aria-disabled", "true");
  expect(german).toHaveTextContent("Soon");
  fireEvent.click(german);
  expect(screen.getByText("The German version of the site follows. It is not available yet.")).toBeInTheDocument();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
});

test("the projects page newsletter checks the address and shows the double opt-in note", async () => {
  // U33 home has no newsletter block; the sign-up stays on the October pages (U33-DEC-39).
  renderApp("/projects");
  const input = screen.getByLabelText("Email address");
  const submit = screen.getByRole("button", { name: "Get new projects" });

  fireEvent.click(submit);
  expect(input).toHaveClass("is-invalid");
  expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();

  fireEvent.change(input, { target: { value: "anna@example.com" } });
  expect(input).not.toHaveClass("is-invalid");
  fireEvent.click(submit);
  expect(await screen.findByText(/We sent a confirmation link to anna@example\.com\./)).toBeInTheDocument();
  expect(screen.getByText("Almost done.")).toBeInTheDocument();
  expect(screen.getByText("Check your inbox to confirm.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "Use another address" }));
  expect(screen.getByLabelText("Email address")).toHaveValue("");
});

test("portfolio labels preserved pre-reset activity without replacing its details", () => {
  const entry = activityFixture.entries[0];
  const previous = entry.archived_at;
  entry.archived_at = "2026-09-09T12:00:00Z";
  try {
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "lukas.brunner@example.ch" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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

  expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
  registration.unmount();

  renderApp("/login");
  expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
});

test("client navigation writes a stable URL and browser history restores the screen", () => {
  renderApp("/");

  fireEvent.click(screen.getByRole("link", { name: "Open an account" }));
  expect(window.location.pathname).toBe("/register");
  expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();

  window.history.pushState({}, "", "/faq");
  fireEvent(window, new PopStateEvent("popstate"));
  expect(screen.getByRole("heading", { level: 1, name: "Questions and answers" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/help");
});

test("login resume sends incomplete accounts back to onboarding", () => {
  expect(
    onboardingStepForUser({
      account_type: "natural_person_lender",
      status: "pending_kyc",
      phone_verified: false
    })
  ).toBe(1);

  // Phone verified, no PIN yet: the PIN step (ACC-DEC-009).
  expect(
    onboardingStepForUser({
      account_type: "natural_person_lender",
      status: "pending_kyc",
      phone_verified: true,
      pin_set: false
    })
  ).toBe(2);

  // Phone verified and PIN created: identity verification.
  expect(
    onboardingStepForUser({
      account_type: "natural_person_lender",
      status: "pending_kyc",
      phone_verified: true,
      pin_set: true
    })
  ).toBe(3);

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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  expect(screen.getByRole("heading", { name: "Welcome back, Lukas" })).toBeInTheDocument();
  expect(screen.getByText("Preview data")).toBeInTheDocument();
  expect(screen.getByText(/not real account data/i)).toBeInTheDocument();

  // The U33 sidebar: INVEST / WALLET / ACCOUNT with the design's entries, as links to real addresses.
  const portalNav = screen.getByRole("navigation", { name: "Investor portal navigation" });
  const overview = within(portalNav).getByRole("link", { name: "Overview" });
  expect(overview).toHaveClass("nk-menu-link");
  expect(overview).toHaveAttribute("aria-current", "page");
  expect(overview).toHaveAttribute("href", "/dashboard");
  expect(within(portalNav).getAllByRole("heading").map((heading) => heading.textContent)).toEqual(["Invest", "Wallet", "Account"]);
  expect(within(portalNav).getByRole("link", { name: /^Investment opportunities/ })).toHaveAttribute("href", "/marketplace");
  expect(within(portalNav).getByRole("link", { name: "Resale market" })).toHaveAttribute("href", "/secondary-market");
  expect(within(portalNav).getByRole("link", { name: "My investments" })).toHaveAttribute("href", "/portfolio");
  expect(within(portalNav).getByRole("link", { name: "Smart Invest" })).toHaveAttribute("href", "/smart-invest");
  expect(within(portalNav).getByRole("link", { name: /^Account/ })).toHaveAttribute("href", "/balances");
  expect(within(portalNav).getByRole("link", { name: "Transactions" })).toHaveAttribute("href", "/transactions");
  expect(within(portalNav).getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/reports");
  expect(within(portalNav).getByRole("link", { name: "Profile & Settings" })).toHaveAttribute("href", "/settings");
  expect(within(portalNav).getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/documents");
  expect(within(portalNav).getByRole("link", { name: /^Notifications/ })).toHaveAttribute("href", "/notifications");
  // FX stays hidden (U33-DEC-33) and the operator is named discreetly (U33-DEC-34).
  expect(within(portalNav).queryByRole("link", { name: /exchange|FX/i })).not.toBeInTheDocument();
  expect(screen.getByText("A brand of Garanta Finanzgruppe AG")).toBeInTheDocument();

  // Header: available balance per currency, EUR first, each a link to the account.
  const topbar = screen.getByRole("banner", { name: "Investor account header" });
  const balances = within(topbar).getByRole("group", { name: "Available balance" });
  expect(within(balances).getAllByRole("link").map((link) => link.textContent)).toEqual(["EUR 7.420,00", "CHF 24.190,00"]);
  expect(within(topbar).getByRole("button", { name: "Notifications" })).toBeInTheDocument();
  openAccountMenu();
  expect(within(topbar).getByText("Verified investor")).toBeInTheDocument();
  fireEvent.click(within(topbar).getByRole("button", { name: "Add funds" }));
  const addFunds = screen.getByRole("dialog", { name: "Add funds" });
  expect(addFunds).toHaveClass("p73-modal");
  expect(within(addFunds).getByRole("group", { name: "Currency" })).toHaveClass("p73-currency");
  expect(within(addFunds).getByRole("button", { name: "CHF" })).toHaveAttribute("aria-pressed", "true");
});

test("Overview shows balances, payment updates, cashflow and Smart Invest matches to confirm one by one", () => {
  const rhone = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2399");
  const match = { ...smartInvestFixture.matches[0], ...rhone } as (typeof smartInvestFixture.matches)[number];
  smartInvestFixture.matches = [...smartInvestFixture.matches, match];
  try {
    renderApp();
    loginDemo();

    const main = screen.getByRole("main");
    expect(within(main).getByRole("heading", { level: 1, name: "Welcome back, Lukas" })).toBeInTheDocument();
    // CHF is the larger book; EUR and CHF stay separate (U33-DEC-33).
    expect(within(main).getByRole("button", { name: "CHF" })).toHaveAttribute("aria-pressed", "true");
    expect(within(main).getByText("Principal in repayment")).toBeInTheDocument();
    expect(within(main).getByText("Interest received")).toBeInTheDocument();
    expect(within(main).getByText(/Unused funds return on/)).toBeInTheDocument();

    // Payment updates from the late and defaulted holdings; Banxum follows up.
    expect(within(main).getByText("Banxum follows up on overdue payments. No action is needed from you.")).toBeInTheDocument();
    expect(within(main).getByRole("link", { name: /^Ticino Solar SA\s*Default · CHF/ })).toHaveAttribute("href", "/portfolio/H-2150");

    // Cashflow: interest to come and the next payment, for the whole schedule or 30 days.
    expect(within(main).getByText("Investment cashflow")).toBeInTheDocument();
    expect(within(main).getByText("Next payment")).toBeInTheDocument();
    fireEvent.click(within(main).getByRole("button", { name: "Next 30 days" }));
    expect(within(main).getByRole("button", { name: "Next 30 days" })).toHaveAttribute("aria-pressed", "true");

    // Interest history per investment.
    fireEvent.click(within(main).getByRole("button", { name: "View interest history" }));
    const history = screen.getByRole("dialog", { name: "Interest received" });
    expect(within(history).getByRole("table")).toBeInTheDocument();
    fireEvent.click(within(history).getByRole("button", { name: "Close" }));

    // No batch approval (U33-DEC-19): each Smart Invest match opens its own opportunity.
    expect(screen.queryByRole("button", { name: "Review & confirm →" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Your rule found/)).not.toBeInTheDocument();
    fireEvent.click(within(main).getByRole("button", { name: /1 opportunity matches your preferences/ }));
    fireEvent.click(within(main).getByRole("link", { name: /^Rhône Vignobles SA/ }));
    expect(window.location.pathname).toBe("/marketplace/GA-2399");
    expect(screen.getByRole("heading", { level: 1, name: "Rhône Vignobles SA" })).toBeInTheDocument();

    // EUR shows the EUR book with its own payment updates.
    clickNav("Overview");
    fireEvent.click(within(screen.getByRole("main")).getByRole("button", { name: "EUR" }));
    expect(within(screen.getByRole("main")).getByText("Savoie Logistique SAS")).toBeInTheDocument();
  } finally {
    smartInvestFixture.matches = smartInvestFixture.matches.filter((item) => item !== match);
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

    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("Smart Invest");

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
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /risk disclosure/i }));
    fireEvent.change(within(dialog).getByLabelText("Email confirmation code"), { target: { value: "123456" } });
    enterPin();
    fireEvent.click(within(dialog).getByRole("button", { name: /Place \d+ investments?/ }));
    expect(within(dialog).getByText("Every selected investment is in.")).toBeInTheDocument();
  } finally {
    smartInvestFixture.matches = smartInvestFixture.matches.filter(
      (match) => match !== chfMatch && match !== eurMatch
    );
    smartInvestFixture.match_count = smartInvestFixture.matches.length;
  }
});

test("Smart Invest explains matches whose minimum cannot be reached; Overview offers no batch", () => {
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
  smartInvestFixture.matches = [...smartInvestFixture.matches, expensive];
  smartInvestFixture.match_count = smartInvestFixture.matches.length;
  try {
    renderApp();
    loginDemo();
    // Overview lists the match to open, never a batch to confirm (U33-DEC-19).
    expect(screen.queryByRole("button", { name: "Review & confirm →" })).not.toBeInTheDocument();

    clickNav("Smart Invest");
    const matches = screen.getByRole("table", { name: "Smart-Invest matches" });
    const tableBlocked = within(matches).getByLabelText(/Expensive minimum loan cannot be selected/);
    fireEvent.mouseEnter(tableBlocked);
    expect(screen.getByRole("tooltip")).toHaveTextContent("minimum investment");
  } finally {
    smartInvestFixture.matches = smartInvestFixture.matches.filter((match) => match !== expensive);
    smartInvestFixture.match_count = smartInvestFixture.matches.length;
  }
});

test("balance ageing reminders appear in notifications instead of a persistent dashboard warning", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  expect(screen.queryByText("Balance ageing - action needed")).not.toBeInTheDocument();

  const topbar = screen.getByRole("banner", { name: "Investor account header" });
  fireEvent.click(within(topbar).getByRole("button", { name: "Notifications" }));
  fireEvent.click(within(topbar).getByRole("link", { name: "View all notifications" }));

  expect(screen.getByRole("heading", { name: "Notifications" })).toBeInTheDocument();
  expect(screen.getByText("Balance ageing - day 57")).toBeInTheDocument();
  expect(screen.getByText(/must be withdrawn within 3 days/i)).toBeInTheDocument();
});

test("Smart-Invest matching loans open the same opportunity sheet without leaving the rule page", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Smart Invest");

  const matches = screen.getByRole("table", { name: "Smart-Invest matches" });
  fireEvent.click(within(matches).getByRole("row", { name: /Adriatic Marine d\.o\.o\./i }));

  expect(screen.getByRole("dialog", { name: "Adriatic Marine d.o.o." })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/smart-invest");
});

test("Smart-Invest uses the five approved wizard steps and never implies automatic investing", async () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Smart Invest");

  expect(screen.getByRole("heading", { name: "It finds them. You approve them." })).toBeInTheDocument();
  expect(screen.getByText(/never invests for you/i)).toBeInTheDocument();
  expect(screen.queryByText(/cap on any one originator/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/reinvest/i)).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Deactivate the rule" }));
  expect(await screen.findByText("Not active", { selector: ".si-state" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Walk me through it/ }));

  const wizard = screen.getByRole("dialog", { name: "Smart-Invest setup" });
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

test("Investment opportunities mark Smart Invest matches and can show only them", () => {
  const rhone = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2399");
  const match = { ...smartInvestFixture.matches[0], ...rhone } as (typeof smartInvestFixture.matches)[number];
  smartInvestFixture.matches = [...smartInvestFixture.matches, match];
  const rule = smartInvestFixture.rule;
  try {
    const view = renderApp();
    loginDemo();
    // Overview links to the matches only.
    fireEvent.click(screen.getByRole("link", { name: /View Smart Invest matches/ }));
    expect(window.location.pathname).toBe("/marketplace");
    const toggle = screen.getByRole("button", { name: /^Smart Invest\s*1$/ });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(resultLine()).toHaveTextContent("1 opportunity · 5 open in total");
    expect(screen.getByRole("heading", { name: "Rhône Vignobles SA" })).toBeInTheDocument();
    expect(screen.getByText("Smart Invest", { selector: ".si-match-label" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Helvetia Logistik AG" })).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(resultLine()).toHaveTextContent("5 opportunities · 5 open");
    view.unmount();

    // Without an active rule the toolbar leads to the Smart Invest set-up.
    smartInvestFixture.rule = rule ? { ...rule, is_active: false } : null;
    renderApp("/marketplace");
    expect(screen.queryByText("Smart Invest", { selector: ".si-match-label" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Set up Smart Invest" }));
    expect(window.location.pathname).toBe("/smart-invest");
  } finally {
    smartInvestFixture.rule = rule;
    smartInvestFixture.matches = smartInvestFixture.matches.filter((item) => item !== match);
  }
});

test("investor data tables use the shared editorial table surface", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));

  // U33 wallet screens (S4) use the design's tables: Balance details and the Documents list.
  clickNav(/^Account/);
  expect(screen.getByRole("table")).toHaveClass("p73-balance-table");

  clickNav("Resale market");
  fireEvent.click(screen.getByRole("tab", { name: "Sell a holding" }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "secondary-sell-table");

  fireEvent.click(screen.getByRole("tab", { name: "Secondary market activity" }));
  expect(screen.getByRole("table")).toHaveClass("portal-data-table", "secondary-activity-table");

  clickNav("Documents");
  expect(screen.getByRole("table")).toHaveClass("tr-table", "dp-table");
});

test("read-only impersonation token survives a new tab and opens the investor portal", () => {
  writeReadonlyImpersonation("signed-token", "Viorel Nica (viorel.nica1@gmail.com)", 60);
  window.sessionStorage.clear();

  expect(readReadonlyImpersonationToken()).toBe("signed-token");
  expect(readReadonlyImpersonationLabel()).toBe("Viorel Nica (viorel.nica1@gmail.com)");

  renderApp("/");

  expect(screen.getAllByText("Superadmin read-only view").length).toBeGreaterThan(0);
  expect(screen.getByText(/Viewing the portal as Viorel Nica/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Welcome back, Viorel" })).toBeInTheDocument();
});

test("login form submits when the form is submitted from the email field", () => {
  const login = renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.submit(screen.getByTestId("login-magic-link-form"));

  expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Link sent\. Send new in \d+s/ })).toBeDisabled();

  login.unmount();
  renderApp("/login");

  expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
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

  expect(screen.getByRole("heading", { name: "Your sign-in link has expired" })).toBeInTheDocument();
  expect(screen.getByText(/expired or is no longer valid/i)).toBeInTheDocument();
  const resend = screen.getByRole("button", { name: "Send a new link" });
  expect(resend).toBeEnabled();

  fireEvent.click(resend);

  expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Link sent\. Send new in \d+s/ })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "Use a different email address" }));

  expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  expect(screen.getByPlaceholderText("you@example.com")).toHaveValue("");
});

test("expired login link keeps the email field while typing and sends only on submit", () => {
  window.localStorage.setItem(
    "banxum:login-flow:v1",
    JSON.stringify({ email: "", sent: false, linkExpired: true, resendCooldownUntil: 0 })
  );

  renderApp("/login");

  expect(screen.getByRole("heading", { name: "Your sign-in link has expired" })).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "c" } });

  // The first keystroke neither replaces the field nor sends anything.
  expect(screen.getByPlaceholderText("you@example.com")).toHaveValue("c");
  expect(screen.queryByText(/We will send the new link to/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send a new link" })).toBeDisabled();

  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "claire@example.test" } });
  expect(screen.getByRole("heading", { name: "Your sign-in link has expired" })).toBeInTheDocument();

  fireEvent.submit(screen.getByTestId("login-expired-form"));

  expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
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

  expect(screen.getByRole("heading", { name: "Your sign-in link has expired" })).toBeInTheDocument();
  const field = screen.getByPlaceholderText("you@example.com");
  expect(field).toHaveValue("");
  expect(field).toHaveFocus();
  fireEvent.change(field, { target: { value: "n" } });
  expect(screen.getByPlaceholderText("you@example.com")).toHaveValue("n");
  expect(screen.queryByText(/We will send the new link to/)).not.toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "new@example.test" } });
  fireEvent.click(screen.getByRole("button", { name: "Send a new link" }));

  expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
  expect(screen.getByText("new@example.test")).toBeInTheDocument();
});

test("an expired session returns to the login screen with an explanation", () => {
  renderApp("/dashboard");
  expect(screen.getByRole("heading", { name: "Welcome back, Lukas" })).toBeInTheDocument();

  act(() => reportSessionExpired());

  expect(window.location.pathname).toBe("/login");
  expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  expect(screen.getByText("Your session has expired")).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "lukas.brunner@example.ch" } });
  fireEvent.submit(screen.getByTestId("login-magic-link-form"));

  expect(screen.getByRole("heading", { name: "Check your email" })).toBeInTheDocument();
  expect(hasSessionExpiredNotice()).toBe(false);
});

test("a restricted account is told why its data is unavailable", () => {
  renderApp("/dashboard");

  setUxState("restricted");

  expect(screen.getByRole("heading", { name: "Account access" })).toBeInTheDocument();
  expect(screen.getByText("Your account is restricted")).toBeInTheDocument();
  expect(screen.getByText(/You cannot view or move money while your account is restricted/)).toBeInTheDocument();
  // The remedy: an email to support, with the investor reference so the team finds the account.
  expect(screen.getByRole("link", { name: "Contact support" }).getAttribute("href")).toMatch(/^mailto:support@banxum\.com\?subject=Account%20access&body=Investor%20reference/);

  clickNav("My investments");
  expect(screen.getByText("Your account is restricted")).toBeInTheDocument();
});

test("logos on public, sign-in and registration screens lead back to the home page", () => {
  const projects = renderApp("/projects");
  fireEvent.click(within(screen.getByRole("banner")).getByRole("link", { name: "Banxum home" }));
  expect(window.location.pathname).toBe("/");
  expect(screen.getByRole("heading", { level: 1, name: HOME_HEADING })).toBeInTheDocument();
  expect(within(screen.getByRole("contentinfo")).getByRole("link", { name: "Banxum home" })).toHaveAttribute("href", "/");
  projects.unmount();

  // The U33 sign-in layout has one logo in its header (design: create-account module).
  const login = renderApp("/login");
  const loginLogo = screen.getByRole("link", { name: "Banxum home" });
  expect(loginLogo).toHaveAttribute("href", "/");
  fireEvent.click(loginLogo);
  expect(window.location.pathname).toBe("/");
  expect(screen.getByRole("heading", { level: 1, name: HOME_HEADING })).toBeInTheDocument();
  login.unmount();

  renderApp("/register");
  fireEvent.click(screen.getByRole("link", { name: "Banxum home" }));
  expect(window.location.pathname).toBe("/");
  expect(screen.getByRole("heading", { level: 1, name: HOME_HEADING })).toBeInTheDocument();
});

test("published loans appear on Investment opportunities as cards and as a list, without ratings", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");

  expect(screen.getByRole("heading", { level: 1, name: "Investment opportunities" })).toBeInTheDocument();
  expect(resultLine()).toHaveTextContent("5 opportunities · 5 open");
  expect(screen.getByRole("button", { name: "Cards" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("heading", { name: "Helvetia Logistik AG" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View details of Helvetia Logistik AG" })).toHaveAttribute("href", "/marketplace/GA-2401");
  // No ratings (U33-DEC-16) and no co-investment claim (U33-DEC-15).
  expect(screen.getByRole("main")).not.toHaveTextContent(/rating|alongside you/i);

  fireEvent.click(screen.getByRole("button", { name: "List" }));
  const table = screen.getByRole("table");
  expect(within(table).getAllByRole("row")).toHaveLength(6);
  expect(within(table).getByRole("link", { name: "Helvetia Logistik AG" })).toHaveAttribute("href", "/marketplace/GA-2401");
  expect(table).not.toHaveTextContent(/rating/i);

  // Past opportunities: loans whose funding closed, opened in their closed state.
  fireEvent.click(screen.getByRole("link", { name: "Past opportunities" }));
  expect(window.location.pathname).toBe("/marketplace/archive");
  expect(screen.getByRole("heading", { level: 1, name: "Past opportunities" })).toBeInTheDocument();
  const archive = screen.getByRole("table");
  expect(within(archive).getAllByRole("row")).toHaveLength(5);
  expect(within(archive).getByText(/In default since/)).toBeInTheDocument();
  fireEvent.click(within(archive).getByRole("link", { name: "Details of Savoie Logistique SAS" }));
  expect(window.location.pathname).toBe("/marketplace/GA-2201");
  expect(screen.getByText("In default")).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: "Choose investment amount" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Your investment and the recovery" })).toHaveAttribute("href", "/portfolio/H-2201");
  expect(screen.getByRole("link", { name: "Past opportunities" })).toHaveAttribute("href", "/marketplace/archive");
});

test("Investment opportunities search and filter by currency, and the opportunity explains how investing works", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");

  fireEvent.change(screen.getByRole("searchbox", { name: "Search opportunities" }), { target: { value: "solar" } });
  expect(screen.getByRole("heading", { name: "Nordwind Energie GmbH" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Helvetia Logistik AG" })).not.toBeInTheDocument();
  expect(resultLine()).toHaveTextContent("1 opportunity · 5 open in total");
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(resultLine()).toHaveTextContent("5 opportunities · 5 open");

  const currency = screen.getByRole("group", { name: "Currency" });
  fireEvent.click(within(currency).getByRole("button", { name: "EUR" }));
  expect(screen.getByRole("heading", { name: "Nordwind Energie GmbH" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Helvetia Logistik AG" })).not.toBeInTheDocument();
  fireEvent.click(within(currency).getByRole("button", { name: "All" }));

  fireEvent.click(screen.getByRole("link", { name: "View details of Helvetia Logistik AG" }));
  fireEvent.click(screen.getByRole("button", { name: "How investing works" }));
  const dialog = screen.getByRole("dialog", { name: "How investing works" });
  expect(within(dialog).getByText(/first come, first served/)).toBeInTheDocument();
  expect(within(dialog).getByText(/released to your balance/)).toBeInTheDocument();
});

test("opportunity filters use today's data: security type, rate, term and originator, never ratings or purpose", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");

  fireEvent.click(screen.getByRole("button", { name: /^Filters/ }));
  expect(screen.getByRole("button", { name: /^Filters/ })).toHaveAttribute("aria-expanded", "true");
  const panel = screen.getByRole("region", { name: "Investment filters" });
  expect(panel).not.toHaveTextContent(/rating|purpose|loan type/i);

  // Security type: several can be ticked; at least one must match.
  fireEvent.click(within(panel).getByRole("checkbox", { name: "No collateral" }));
  expect(resultLine()).toHaveTextContent("1 opportunity");
  expect(screen.getByRole("heading", { name: "Léman BioTech SA" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Filters \(1\)/ })).toBeInTheDocument();
  fireEvent.click(within(panel).getByRole("checkbox", { name: "Commercial real estate" }));
  expect(resultLine()).toHaveTextContent("2 opportunities");
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(resultLine()).toHaveTextContent("5 opportunities · 5 open");

  // Minimum rate and maximum term combine.
  fireEvent.change(within(panel).getByLabelText("Minimum annual interest rate"), { target: { value: "8" } });
  expect(resultLine()).toHaveTextContent("2 opportunities");
  fireEvent.change(within(panel).getByLabelText("Maximum investment duration"), { target: { value: "12" } });
  expect(resultLine()).toHaveTextContent("1 opportunity");
  expect(screen.getByRole("heading", { name: "Léman BioTech SA" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));

  // Originator, under More filters.
  fireEvent.click(within(panel).getByRole("button", { name: "More filters" }));
  const originator = within(panel).getByRole("combobox", { name: /^Originator/ });
  fireEvent.change(originator, { target: { value: "originator-alpine-credit" } });
  expect(resultLine()).toHaveTextContent("1 opportunity");
  expect(screen.getByRole("heading", { name: "Swiss SME equipment claim" })).toBeInTheDocument();
  fireEvent.change(originator, { target: { value: "direct" } });
  expect(resultLine()).toHaveTextContent("4 opportunities");
});

test("Smart-Invest rule editor saves several values per condition", async () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Smart Invest");
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

test("the opportunity page shows the summary, security, funding with its minimum and hands the amount to Review & sign", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");
  fireEvent.click(screen.getByRole("link", { name: "View details of Helvetia Logistik AG" }));

  expect(window.location.pathname).toBe("/marketplace/GA-2401");
  expect(screen.getByRole("heading", { level: 1, name: "Helvetia Logistik AG" })).toBeInTheDocument();
  expect(screen.getByText(/Refinancing of a distribution warehouse/)).toBeInTheDocument();
  expect(screen.getByRole("main")).not.toHaveTextContent(/co-investment|rating/i);

  // One collateral item with its loan-to-value comparison.
  const ltv = screen.getByRole("button", { name: /^Loan-to-value 58%/ });
  fireEvent.click(ltv);
  expect(ltv).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("group", { name: /Loan amount CHF 1\.450\.000\. Collateral value CHF 2\.500\.000\. Loan-to-value 58%/ })).toBeInTheDocument();

  // Funding progress with the minimum funding threshold from the loan.
  expect(screen.getByText("Minimum funding · 50%")).toBeInTheDocument();
  expect(screen.getByText("CHF 725.000")).toBeInTheDocument();

  // The full loan schedule opens in place.
  fireEvent.click(document.querySelector(".r36-schedule-toggle") as HTMLElement);
  expect(document.getElementById("pd-payment-schedule")).toHaveAttribute("open");
  expect(screen.getByText("Full loan · CHF 1.450.000,00 · 24 payments")).toBeInTheDocument();

  // The amount starts empty (U33-DEC-08); the minimum comes from the API.
  const amount = screen.getByRole("textbox", { name: "Choose investment amount" });
  expect(amount).toHaveValue("");
  fireEvent.change(amount, { target: { value: "500" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
  expect(screen.getByText("The minimum investment is CHF 1.000,00.")).toBeInTheDocument();
  fireEvent.change(amount, { target: { value: "2000" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));

  expect(window.location.pathname).toBe("/marketplace/GA-2401/invest");
  expect(screen.getByRole("heading", { level: 1, name: "Review & sign" })).toBeInTheDocument();
  expect(document.querySelector('.ip-step[aria-current="step"]')).toHaveTextContent("Review & sign");
  expect(screen.getByRole("textbox", { name: "Your investment amount" })).toHaveValue("2.000,00");
});

test("Add funds keeps the opportunity and the amount when the balance is too low", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");
  fireEvent.click(screen.getByRole("link", { name: "View details of Nordwind Energie GmbH" }));

  const amount = screen.getByRole("textbox", { name: "Choose investment amount" });
  fireEvent.change(amount, { target: { value: "90000" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
  expect(screen.getByText(/^Add EUR .* to invest this amount\.$/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Add funds/ }));
  expect(screen.getByRole("dialog", { name: "Add funds" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/marketplace/GA-2402");
  expect(amount).toHaveValue("90000");
});

test("the closing countdown uses the platform as-of date", () => {
  const previousAsOf = balancesFixture.as_of;
  balancesFixture.as_of = "2026-06-17T10:00:00+02:00";
  try {
    renderApp();
    loginDemo();
    clickNav("Investment opportunities");
    const card = screen.getByRole("heading", { name: "Helvetia Logistik AG" }).closest(".card") as HTMLElement;
    expect(within(card).getByText(/2 days left/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "View details of Helvetia Logistik AG" }));
    expect(screen.getByText("2 days left")).toBeInTheDocument();
  } finally {
    balancesFixture.as_of = previousAsOf;
  }
});

test("Review & sign projects the investor's share of the schedule for a direct loan and an originator subscription", () => {
  renderApp();
  loginDemo();

  // Direct loan: proportional share of the contracted schedule.
  goToPath("/marketplace/GA-2401/invest");
  applyReviewAmount("2000");
  expect(screen.getByText("Total over 24 payments")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Payment schedule/ }));
  const direct = screen.getByRole("dialog", { name: "Your payment schedule" });
  expect(within(direct).getAllByRole("row")).toHaveLength(25);
  expect(within(direct).getByText(/assuming the loan funds in full/)).toBeInTheDocument();
  fireEvent.click(within(direct).getByRole("button", { name: "Close" }));

  // Originator subscription: only the rows after the funding deadline, with the interest share.
  goToPath("/marketplace/LO-2601/invest");
  applyReviewAmount("16000");
  fireEvent.click(screen.getByRole("button", { name: /^Payment schedule/ }));
  const claim = screen.getByRole("dialog", { name: "Your payment schedule" });
  // 10% of the CHF 160'000 principal: installment 2 pays 2'000 principal and 1'440 x 10% x 70% = 100.80
  // interest; the first installment after the funding deadline belongs to the Loan Originator.
  expect(within(claim).getAllByRole("row")).toHaveLength(4);
  expect(within(claim).getAllByText("CHF 2.000,00").length).toBeGreaterThan(0);
  expect(within(claim).getByText("CHF 100,80")).toBeInTheDocument();
  expect(within(claim).getByText(/the first one after it belongs to the Loan Originator/)).toBeInTheDocument();
});

test("Investment opportunities sort by closing date, interest and term in both layouts", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");

  const cardTitles = () => Array.from(document.querySelectorAll(".r35-card .project-info .title")).map((node) => node.textContent);
  const rowTitles = () => Array.from(document.querySelectorAll(".ol-table .ol-title")).map((node) => node.textContent);
  const sort = document.getElementById("op-sort") as HTMLSelectElement;
  expect(sort).toHaveValue("closing");

  fireEvent.change(sort, { target: { value: "rate" } });
  expect(cardTitles()[0]).toBe("Léman BioTech SA");
  fireEvent.change(sort, { target: { value: "term" } });
  expect(cardTitles()[0]).toBe("Swiss SME equipment claim");

  // The same order applies to the List layout.
  fireEvent.click(screen.getByRole("button", { name: "List" }));
  expect(rowTitles()[0]).toBe("Swiss SME equipment claim");
  fireEvent.change(sort, { target: { value: "rate" } });
  expect(rowTitles()[0]).toBe("Léman BioTech SA");
});

test("portfolio loans sort from the header and the sort menu", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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
  fireEvent.click(screen.getByRole("menuitemradio", { name: "Rate" }));
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");

  // A Detailed-only sort never remains active without a visible column indicator.
  fireEvent.click(screen.getByRole("tab", { name: "Focused" }));
  expect(screen.queryByRole("button", { name: "back to largest first" })).not.toBeInTheDocument();
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");

  fireEvent.click(screen.getByRole("tab", { name: "Detailed" }));
  fireEvent.click(screen.getByRole("button", { name: "Sort" }));
  fireEvent.click(screen.getByRole("menuitemradio", { name: "Rate" }));
  fireEvent.click(screen.getByRole("button", { name: "back to largest first" }));
  expect(rowNames()[0]).toBe("Engadin Hospitality AG");
});

test("a loan-specific funding window blocks an otherwise positive balance on the opportunity page", () => {
  const loan = marketplaceLoansFixture.find((item) => item.loan_id === "LO-2601")!;
  const lots = balanceLotsFixture.filter((lot) => lot.currency === loan.currency);
  // A lot whose last day (day 58) is the loan's last funding day cannot cover the window.
  const originals = lots.map((lot) => lot.last_day);
  lots.forEach((lot) => { lot.last_day = loan.funding_deadline ?? lot.last_day; });
  try {
    renderApp();
    loginDemo();
    clickNav("Investment opportunities");
    fireEvent.click(screen.getByRole("link", { name: `View details of ${loan.title}` }));
    expect(screen.getByText(/Your CHF balance for this loan: CHF 0,00/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Choose investment amount" }), { target: { value: "1000" } });
    fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
    expect(screen.getByText("Your CHF balance does not have enough holding time left for this loan's funding period.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Review investment/ })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/marketplace/LO-2601");
  } finally {
    lots.forEach((lot, index) => { lot.last_day = originals[index]; });
  }
});

test("an originator subscription names the originator, checks the minimum and reserves at par", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");
  fireEvent.click(screen.getByRole("link", { name: "View details of Swiss SME equipment claim" }));

  expect(screen.getByText("Alpine Credit Partners AG", { selector: ".u33-invest-originator" })).toBeInTheDocument();
  expect(screen.getByText("Existing claim", { selector: ".l8-type" })).toBeInTheDocument();
  expect(screen.getByText("Investor interest rate")).toBeInTheDocument();
  expect(screen.getByText("Reserved")).toBeInTheDocument();

  const amount = screen.getByRole("textbox", { name: "Choose investment amount" });
  fireEvent.change(amount, { target: { value: "100" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
  expect(screen.getByText("The minimum investment is CHF 500,00.")).toBeInTheDocument();
  fireEvent.change(amount, { target: { value: "1000" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));

  expect(window.location.pathname).toBe("/marketplace/LO-2601/invest");
  const page = screen.getByRole("main");
  expect(within(page).getByText(/Your share of the installments after the funding deadline/)).toBeInTheDocument();
  expect(within(page).queryByRole("button", { name: "Get executable quote" })).not.toBeInTheDocument();
  for (const box of within(page).getAllByRole("checkbox")) fireEvent.click(box);
  fireEvent.click(within(page).getByRole("button", { name: "Confirm investment" }));
  const dialog = screen.getByRole("dialog", { name: "Confirm your investment" });
  expect(within(dialog).getByText(/Loan Originator funding round/)).toBeInTheDocument();
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  enterPin(undefined, undefined, dialog);
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm and reserve" }));
  expect(screen.getByRole("heading", { name: "Investment reserved" })).toBeInTheDocument();
  expect(screen.getByText(/reserved for the Loan Originator funding round/)).toBeInTheDocument();
});

test("FX redesign uses CHF/EUR preview data and net-rate conversion history", () => {
  // FX is off by default since 2026-10-16; the preview switch shows the FX screens.
  window.localStorage.setItem("banxum.preview.fx", "on");
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Currency exchange");

  expect(screen.getByRole("heading", { name: "Currency exchange" })).toBeInTheDocument();
  expect(
    screen.getByText("Convert available CHF and EUR balances. The executable rate and fee are shown before confirmation.")
  ).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "My money" })).not.toBeInTheDocument();
  expect(screen.getByText("Your balances")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Amount to convert from CHF" }), {
    target: { value: "1000.00" }
  });

  expect(screen.getAllByText("1 CHF = 1,0262 EUR")).toHaveLength(2);
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

test("a refinancing loan is named in the credit file Summary and keeps its original terms in Loan terms", () => {
  renderApp();
  loginDemo();

  // The old schedule address opens the opportunity page with its schedule open.
  goToPath("/marketplace/GA-2401/schedule");
  expect(screen.getByRole("heading", { name: "Scheduled repayments" })).toBeInTheDocument();
  expect(document.getElementById("pd-payment-schedule")).toHaveAttribute("open");

  fireEvent.click(screen.getByRole("link", { name: "Open credit file" }));
  expect(window.location.pathname).toBe("/marketplace/GA-2401/credit-file");
  expect(screen.getByRole("heading", { level: 1, name: "Credit file" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  expect(screen.getByRole("heading", { level: 2, name: "Summary" })).toBeInTheDocument();
  expect(screen.getByText(/This loan refinances an existing loan of the borrower/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Loan terms/ }));
  expect(screen.getByRole("heading", { level: 2, name: "Loan terms" })).toBeInTheDocument();
  expect(screen.getByText("Refinancing loan")).toBeInTheDocument();
  const original = screen.getByText("Refinanced loan: original terms").closest("details") as HTMLElement;
  expect(within(original).getByText("Original principal")).toBeInTheDocument();
  expect(within(original).getAllByRole("row")).toHaveLength(25);
  expect(within(original).getByText(/investors fund the new loan on the terms above/)).toBeInTheDocument();
  // Investment terms open before any confirmation.
  expect(screen.getByRole("link", { name: /Investment terms and claim assignment/ })).toHaveAttribute("href", "/legal/primary-market-investment");
});

test("the credit file's Borrower & business chapter shows the published story, safely rendered", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/GA-2401/credit-file");
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  fireEvent.click(screen.getByRole("button", { name: /Borrower & business/ }));

  expect(screen.getByRole("heading", { level: 3, name: "Meet the borrower" })).toBeInTheDocument();
  expect(screen.getByText("Established").nextElementSibling).toHaveTextContent("2011");
  // Story blocks render as real elements built from the JSON document.
  expect(screen.getByRole("heading", { level: 2, name: "Moving Swiss goods since 1994" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 3, name: "Why they borrow" })).toBeInTheDocument();
  expect(screen.getByText("42 trucks and two cross-dock warehouses").tagName).toBe("STRONG");
  const link = screen.getByRole("link", { name: "company site" });
  expect(link).toHaveAttribute("href", "https://example.test/helvetia");
  expect(link).toHaveAttribute("rel", "noopener noreferrer nofollow");
  const image = screen.getByRole("img", { name: "Helvetia Logistik cross-dock warehouse in Duebendorf" });
  expect(image).toHaveAttribute("src", "/api/v1/story-images/6f1d2c3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f/");
  expect(screen.getByText("Audited accounts since 2012").closest("ul")).not.toBeNull();
  expect(screen.getByText("We only borrow to buy assets that pay for themselves.").tagName).toBe("BLOCKQUOTE");

  // Financials show only the figures the borrower disclosed.
  fireEvent.click(screen.getByRole("button", { name: /Financials/ }));
  expect(screen.getByText("Revenue")).toBeInTheDocument();
  expect(screen.getByText("Total liabilities")).toBeInTheDocument();

  // A borrower without a story shows an honest empty state instead of filler.
  goToPath("/marketplace/GA-2399/credit-file");
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  fireEvent.click(screen.getByRole("button", { name: /Borrower & business/ }));
  expect(screen.getByText("No profile of this borrower has been published yet.")).toBeInTheDocument();
});

test("an originator claim's credit file shows the originator, its story, the interest shares and the borrower payments", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/LO-2601/credit-file");
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  fireEvent.click(screen.getByRole("button", { name: /Borrower & originator/ }));

  // The story is about the loan originator, not the end borrower.
  expect(screen.getByRole("heading", { level: 3, name: "About the loan originator" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Alpine Credit Partners AG" })).toBeInTheDocument();
  expect(screen.getByText("Historic loss rate below 1%").closest("ol")).not.toBeNull();
  expect(screen.getByText(/keeps 15,0% of the outstanding principal/)).toBeInTheDocument();

  // Loan terms show the investor's and the originator's shares (U33-DEC-24) and the imported payments.
  fireEvent.click(screen.getByRole("button", { name: /Loan terms/ }));
  expect(screen.getByText("Your share of the borrower's interest").nextElementSibling).toHaveTextContent("70,0%");
  expect(screen.getByText("Originator's share of interest").nextElementSibling).toHaveTextContent("30,0%");
  expect(screen.getByText("Payments received from the borrower")).toBeInTheDocument();
  expect(screen.getByText("LO-2601-PAY-001")).toBeInTheDocument();
});

test("investing runs from the opportunity page to Review & sign: two acceptances, email code + PIN, reservation", () => {
  renderApp();
  loginDemo();
  clickNav("Investment opportunities");
  fireEvent.click(screen.getByRole("link", { name: "View details of Helvetia Logistik AG" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Choose investment amount" }), { target: { value: "2000" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));

  expect(window.location.pathname).toBe("/marketplace/GA-2401/invest");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  const page = screen.getByRole("main");
  // Two acceptances, unchecked by default; the documents open before confirmation (U33-DEC-14).
  const boxes = within(page).getAllByRole("checkbox");
  expect(boxes).toHaveLength(2);
  boxes.forEach((box) => expect(box).not.toBeChecked());
  expect(within(page).getByRole("link", { name: /^Investment terms/ })).toHaveAttribute("href", "/legal/primary-market-investment");
  expect(within(page).getByRole("link", { name: /^Risk information/ })).toHaveAttribute("href", "/legal/risk-disclosure");
  const confirm = within(page).getByRole("button", { name: "Confirm investment" });
  expect(confirm).toBeDisabled();
  fireEvent.click(boxes[0]);
  expect(confirm).toBeDisabled();
  fireEvent.click(boxes[1]);
  expect(confirm).toBeEnabled();

  // A new amount clears the acceptances.
  const amount = within(page).getByRole("textbox", { name: "Your investment amount" });
  fireEvent.change(amount, { target: { value: "3000" } });
  fireEvent.blur(amount);
  boxes.forEach((box) => expect(box).not.toBeChecked());
  expect(confirm).toBeDisabled();
  boxes.forEach((box) => fireEvent.click(box));
  fireEvent.click(confirm);

  // The email code and the PIN confirm this one investment.
  const dialog = screen.getByRole("dialog", { name: "Confirm your investment" });
  expect(within(dialog).getByText("CHF 3.000,00")).toBeInTheDocument();
  const reserve = within(dialog).getByRole("button", { name: "Confirm and reserve" });
  expect(reserve).toBeDisabled();
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  enterPin(undefined, undefined, dialog);
  fireEvent.click(reserve);

  expect(screen.getByRole("heading", { name: "Investment reserved" })).toBeInTheDocument();
  expect(screen.getByText(/credited to your Banxum balance/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Your accepted terms in Documents/ })).toHaveAttribute("href", "/documents");
  fireEvent.click(within(document.querySelector(".l8-done-actions") as HTMLElement).getByRole("link", { name: /^My investments/ }));
  expect(window.location.pathname).toBe("/portfolio");
});

test("legacy originator claims are bought on Review & sign through an executable quote", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/LO-2402");
  expect(screen.getByRole("heading", { level: 1, name: "Alpine dental equipment claim" })).toBeInTheDocument();
  expect(screen.getByText("Remaining term")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Choose investment amount" }), { target: { value: "1000" } });
  fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));

  expect(window.location.pathname).toBe("/marketplace/LO-2402/invest");
  const page = screen.getByRole("main");
  expect(within(page).getByText(/assigns the claim to you immediately/)).toBeInTheDocument();
  fireEvent.click(within(page).getByRole("button", { name: "Get executable quote" }));
  expect(within(page).getByText("Cash price")).toBeInTheDocument();
  expect(within(page).getByText("Principal assigned")).toBeInTheDocument();
  expect(within(page).getByText("Quote expires")).toBeInTheDocument();
  const purchase = within(page).getByRole("button", { name: "Confirm purchase" });
  expect(purchase).toBeDisabled();
  for (const box of within(page).getAllByRole("checkbox")) fireEvent.click(box);
  fireEvent.click(purchase);

  const dialog = screen.getByRole("dialog", { name: "Confirm your claim purchase" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  enterPin(undefined, undefined, dialog);
  fireEvent.click(within(dialog).getByRole("button", { name: "Purchase claim" }));

  expect(screen.getByRole("heading", { name: "Claim purchased" })).toBeInTheDocument();
  fireEvent.click(within(document.querySelector(".l8-done-actions") as HTMLElement).getByRole("link", { name: /^My investments/ }));
  expect(window.location.pathname).toBe("/portfolio");
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

    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("My investments");

    expect(screen.queryByText("Primary orders awaiting funding close")).not.toBeInTheDocument();
    const ordersInfo = screen.getByRole("button", { name: "About primary orders" });
    fireEvent.mouseEnter(ordersInfo);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Primary orders awaiting funding close");
    expect(screen.getByRole("tooltip")).toHaveTextContent("CHF 5.000,00");
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

    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Resale market");

  expect(screen.getByRole("heading", { name: "Loans other people want out of." })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "For sale now" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Sell a holding" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Secondary market activity" })).toBeInTheDocument();

  // Design table columns with buyer-safe loan context.
  expect(screen.getByText("Asking")).toBeInTheDocument();
  expect(screen.getByText("Left to run")).toBeInTheDocument();
  expect(screen.getByText("Buyer cost")).toBeInTheDocument();
  expect(screen.getByText(/Equipment · 9,4% coupon/)).toBeInTheDocument();
  expect(screen.getByText("24 mo")).toBeInTheDocument();
  expect(screen.getByText("2,0% discount")).toBeInTheDocument();
  // Buyer cost without a buyer fee (owner decision 2026-10-16).
  expect(screen.getByText("CHF 5.147,00")).toBeInTheDocument();
  expect(screen.getByText(/non-standard/)).toBeInTheDocument();

  // Discount/par explainer band (no premium since 2026-10-16) and the selling caution card.
  expect(screen.getByRole("heading", { name: "Why do loans sell at a discount?" })).toBeInTheDocument();
  expect(screen.getByText("At a discount")).toBeInTheDocument();
  expect(screen.getByText("Below 100% of principal")).toBeInTheDocument();
  expect(screen.getByText("At par")).toBeInTheDocument();
  expect(screen.queryByText("At a premium")).not.toBeInTheDocument();
  expect(screen.queryByText(/your return/i)).not.toBeInTheDocument();
  expect(screen.getByText(/not a withdrawal button/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Choose a loan to sell" }));
  expect(screen.getByRole("tab", { name: "Sell a holding" })).toHaveAttribute("aria-selected", "true");
});

test("portfolio redesign shows hero, tabs, loans table views and widgets", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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
  expect(screen.getByText("12,0%–16,0% p.a.")).toBeInTheDocument();
  expect(screen.getByText(/CHF 28\.110,50 lent/)).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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
  // LTV uses the principal still owed on the whole loan (audit A-65), not the original amount lent.
  const engadin = portfolioFixture.holdings.find((holding) => holding.id === "H-2310")!.loan;
  const owedMinor = engadin.schedule.reduce((sum, row) => sum + row.outstanding_principal_minor, 0);
  expect(within(page).getByText(`${formatRateBps(Math.round((owedMinor * 10_000) / engadin.collateral_value_minor), "european")} LTV`)).toBeInTheDocument();
  expect(within(page).getByText(/current loan principal against/).textContent).toContain(formatMoneyMinor(owedMinor, "CHF", undefined, "european"));
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

test("the investment page shows every public loan note with its full message, newest first", async () => {
  renderApp("/portfolio/H-2201#loan-notes");

  const notes = await screen.findByRole("region", { name: "Loan notes" });
  const titles = within(notes).getAllByRole("heading", { level: 4 }).map((heading) => heading.textContent);
  expect(titles).toEqual(["Recovery process update", "Formal demand issued"]);
  expect(within(notes).getByText(/Garanta has instructed external recovery counsel/)).toBeInTheDocument();
  expect(within(notes).getByText(/Garanta has issued a formal payment demand/)).toBeInTheDocument();
  expect(within(notes).getAllByText(/^Published /)).toHaveLength(2);
  expect(window.location.hash).toBe("#loan-notes");
});

test("originator claim holdings disclose the retained claim without implying protection", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("My investments");
  fireEvent.click(screen.getByRole("button", { name: "EUR" }));

  const page = openHoldingPage("Nord Trans Cargo working capital");
  expect(
    within(page).getByText(
      /Nord Capital Finance must retain at least 15,0% of the loan's current outstanding principal/
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
    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "lukas.brunner@example.ch" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("My investments");

    const page = openHoldingPage("Engadin Alpine refinancing");
    expect(within(page).getByText(/18 days past due/)).toBeInTheDocument();
    expect(within(page).getByText(/12,0% annual default-interest rate/)).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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
    clickNav("Resale market");
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

    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
      target: { value: "lukas.brunner@example.ch" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Resale market");
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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  setUxState("frozen");
  clickNav("Resale market");
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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  setUxState("frozen");

  const frozenNotice = screen.getByText(/Financial actions are frozen/i).closest(".alert") as HTMLElement;
  expect(frozenNotice).toHaveTextContent(/Your investments, documents and statements remain available/i);
  expect(within(frozenNotice).getByRole("button", { name: "Add a bank account" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Documents" })).toBeInTheDocument();
});

test("registration KYC handoff reflects Didit plus Garanta evidence retention", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Open an account" }));
  expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
  // Checkbox labels embed new-tab document links, so the text spans elements.
  fireEvent.click(
    screen.getByLabelText((label) => label.includes("I have read, understood and accept the") && label.includes("General Terms and Conditions"))
  );
  fireEvent.click(
    screen.getByLabelText(
      (label) => label.includes("I acknowledge the") && label.includes("risk disclosure")
    )
  );
  // Marketing stays optional and unchecked (U33-DEC-30).
  expect(screen.getByLabelText("I agree to optional marketing communications.")).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  expect(screen.getByRole("heading", { name: "Verify your mobile number" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Send SMS code" }));
  expect(screen.getByRole("heading", { name: "Enter your SMS code" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("SMS code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify phone" }));

  // The PIN step comes before the KYC hand-off (ACC-DEC-009).
  expect(screen.getByRole("heading", { name: "Create your security PIN" })).toBeInTheDocument();
  enterPin(undefined, "6-digit PIN");
  enterPin(undefined, "Confirm PIN");
  fireEvent.click(screen.getByRole("button", { name: "Save PIN & continue" }));

  expect(screen.getByRole("heading", { name: "Verify your identity" })).toBeInTheDocument();
  expect(screen.getByText("Continue with Didit, our identity verification provider.")).toBeInTheDocument();
  expect(screen.getByText(/retains the required compliance evidence/i)).toBeInTheDocument();
  expect(screen.queryByText(/does not store your identity documents/i)).not.toBeInTheDocument();

  // Preview: the hand-off and the result are simulated; the verification states follow the design.
  fireEvent.click(screen.getByRole("button", { name: "Continue to identity verification" }));
  expect(screen.getByRole("heading", { name: "Your verification is in review" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Check status" }));
  expect(screen.getByRole("heading", { name: "Your account is ready" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Open my account" }));
  expect(window.location.pathname).toBe("/dashboard");
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

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav(/^Account/);
  fireEvent.click(within(screen.getByRole("region", { name: "CHF account" })).getByRole("button", { name: "Add funds" }));

  const dialog = screen.getByRole("dialog", { name: "Add funds" });
  expect(within(dialog).getByText("Your personal reference")).toBeInTheDocument();
  expect(within(dialog).getByText("BX-LBR-CHF-4471")).toBeInTheDocument();
  expect(within(dialog).getByText("Use your reference with every transfer so we can identify your payment.")).toBeInTheDocument();
  expect(within(dialog).getByText(/must be included unchanged in the bank transfer reference/i)).toBeInTheDocument();
  // U33-DEC-05 and U33-DEC-34: own-name accounts, unclear deposits checked by hand, the operator named.
  expect(within(dialog).getByText("Transfer from a bank account in your name.")).toBeInTheDocument();
  expect(within(dialog).getByText(/checked by hand before they become available/)).toBeInTheDocument();
  expect(within(dialog).queryByText(/other accounts are returned/i)).not.toBeInTheDocument();
  expect(within(dialog).getByText("Banxum is a brand of Garanta Finanzgruppe AG.")).toBeInTheDocument();
  // CHF has a Swiss QR-bill; there are no simulated deposits.
  expect(within(dialog).getByText("Show the QR code")).toBeInTheDocument();
  expect(within(dialog).queryByText(/simulate|prototype/i)).not.toBeInTheDocument();
});

test("account page shows one card per currency whose actions open that currency", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav(/^Account/);

  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Banxum account", level: 1 })).toBeInTheDocument();
  // EUR first, then CHF (design order); each card has its available and reserved amounts.
  expect(within(main).getAllByRole("region", { name: /^[A-Z]{3} account$/ }).map((card) => card.getAttribute("aria-labelledby"))).toEqual(["wl-account-EUR", "wl-account-CHF"]);
  const chf = within(main).getByRole("region", { name: "CHF account" });
  expect(within(chf).getByText("24.190,00")).toBeInTheDocument();
  // The CHF order of 6.500,00 is allocated: reserved until its funding closes.
  expect(within(chf).getByRole("link", { name: "CHF 6.500,00" })).toHaveAttribute("href", "/portfolio");
  expect(within(main).getByText("Balance details")).toBeInTheDocument();
  expect(within(main).getByRole("button", { name: "How your account works" })).toBeInTheDocument();

  const eur = within(main).getByRole("region", { name: "EUR account" });
  fireEvent.click(within(eur).getByRole("button", { name: "Add funds" }));
  const addFunds = screen.getByRole("dialog", { name: "Add funds" });
  expect(within(addFunds).getByRole("button", { name: "EUR" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(within(addFunds).getByRole("button", { name: "Close" }));

  fireEvent.click(within(eur).getByRole("button", { name: "Withdraw" }));
  const withdraw = screen.getByRole("dialog", { name: "Withdraw" });
  expect(within(withdraw).getByRole("button", { name: "EUR" })).toHaveAttribute("aria-pressed", "true");
  expect(within(withdraw).getByText("Available EUR 7.420,00")).toBeInTheDocument();
});

test("profile and settings keep every section reachable from its tabs and the account menu", () => {
  renderApp();

  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
  clickNav("Profile & Settings");

  expect(window.location.pathname).toBe("/settings");
  expect(screen.getByRole("heading", { name: "Profile & Settings", level: 1 })).toBeInTheDocument();
  const tabs = screen.getByRole("navigation", { name: "Profile and settings sections" });
  expect(within(tabs).getByRole("link", { name: "Personal details" })).toHaveAttribute("aria-current", "page");
  // Verified data is read-only; changes go through support (U33-DEC-26).
  expect(screen.getByText("Lukas Brunner", { selector: "dd" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Edit/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Contact support to change" }).getAttribute("href")).toMatch(/^mailto:support@banxum\.com\?subject=/);
  expect(screen.getByText("Verification details")).toBeInTheDocument();

  fireEvent.click(within(tabs).getByRole("link", { name: "Security" }));
  expect(window.location.pathname).toBe("/settings/security");
  expect(screen.getByText("Sign-in link by email")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Change PIN" })).toBeInTheDocument();

  fireEvent.click(within(tabs).getByRole("link", { name: "Bank accounts" }));
  expect(window.location.pathname).toBe("/settings/bank-accounts");
  expect(screen.getByText("CH93 0076 2011 6238 5295 7")).toBeInTheDocument();
  expect(screen.getByText(/^Verified · /)).toBeInTheDocument();
  // No 48-hour pause (U33-DEC-05) and repayments go to the Banxum balance (U33-DEC-02).
  expect(screen.queryByText(/48 hours/)).not.toBeInTheDocument();
  expect(screen.getByText(/Repayments are credited to your Banxum balance/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Add a bank account" }));
  expect(screen.getByRole("dialog", { name: "Add a bank account" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  fireEvent.click(within(tabs).getByRole("link", { name: "Notifications" }));
  expect(screen.getByRole("checkbox", { name: "News from Banxum" })).not.toBeChecked();
  expect(screen.getAllByText("Always on").length).toBeGreaterThan(0);

  fireEvent.click(within(tabs).getByRole("link", { name: "Preferences" }));
  fireEvent.click(screen.getByRole("button", { name: "Dark" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  fireEvent.click(screen.getByRole("button", { name: /^Swiss/ }));
  expect(screen.getByRole("button", { name: /^Swiss/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("option", { name: "Deutsch · Soon" })).toBeDisabled();
  // Closing is a request to support, not an instant closure (U33-DEC-28).
  fireEvent.click(screen.getByRole("button", { name: "Close account" }));
  const closure = screen.getByRole("dialog", { name: "Request account closure" });
  expect(within(closure).getByText("Receiving your request does not close the account yet.")).toBeInTheDocument();
  expect(within(closure).getByRole("link", { name: "Write closure request" }).getAttribute("href")).toMatch(/^mailto:support@banxum\.com\?subject=Account%20closure%20request/);
  fireEvent.click(within(closure).getByRole("button", { name: "Cancel" }));

  // The account menu leads straight to the tabs (design entries).
  openAccountMenu();
  let menu = screen.getByRole("link", { name: "Personal information" }).closest("ul") as HTMLElement;
  fireEvent.click(within(menu).getByRole("link", { name: "Security" }));
  expect(window.location.pathname).toBe("/settings/security");
  openAccountMenu();
  menu = screen.getByRole("link", { name: "Personal information" }).closest("ul") as HTMLElement;
  expect(within(menu).getByRole("link", { name: "Personal information" })).toHaveAttribute("href", "/settings/personal");
  expect(within(menu).getByRole("link", { name: "Bank accounts" })).toHaveAttribute("href", "/settings/bank-accounts");
  expect(within(menu).getByRole("link", { name: "Preferences" })).toHaveAttribute("href", "/settings/preferences");
});

test("the Help page searches its questions and contacts support by email", () => {
  renderApp("/portal/help");

  expect(screen.getByRole("heading", { name: "Help", level: 1 })).toBeInTheDocument();
  const repayments = screen.getByText("Where are my repayments paid?");
  fireEvent.click(repayments);
  // U33-DEC-02: repayments go to the Banxum balance, never straight to the bank account.
  expect(repayments.closest("details")).toHaveAttribute("open");
  expect(repayments.closest("details")).toHaveTextContent("credited to your Banxum balance");
  expect(screen.queryByText(/Repayments go directly to your verified bank account/)).not.toBeInTheDocument();
  // No ratings (U33-DEC-16) and no fixed "0 fees" claim (U33-DEC-12).
  expect(screen.queryByText(/rating/i)).not.toBeInTheDocument();

  fireEvent.change(screen.getByRole("searchbox", { name: "Search for an answer" }), { target: { value: "PIN" } });
  expect(document.getElementById("hp-result-count")).toHaveTextContent(/answers? found/);
  expect(screen.getByText("What if I forget my PIN?").closest("details")).not.toHaveAttribute("hidden");
  expect(screen.getByText("How much can I invest?").closest("details")).toHaveAttribute("hidden");
  fireEvent.change(screen.getByRole("searchbox", { name: "Search for an answer" }), { target: { value: "zzzz" } });
  expect(screen.getByRole("heading", { name: "No answers found" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show all questions" }));
  expect(screen.getByText("How much can I invest?").closest("details")).not.toHaveAttribute("hidden");

  fireEvent.click(screen.getByRole("button", { name: "Account & security" }));
  expect(screen.getByText("How do I add a bank account?").closest("details")).not.toHaveAttribute("hidden");
  expect(screen.getByText("How much can I invest?").closest("details")).toHaveAttribute("hidden");

  // Contact support prepares an email (no Help message endpoint yet, U33-DEC-35).
  fireEvent.click(within(screen.getByRole("complementary")).getByRole("button", { name: /^Contact support/ }));
  const dialog = screen.getByRole("dialog", { name: "Contact support" });
  const write = within(dialog).getByRole("link", { name: "Write email" });
  expect(write).toHaveAttribute("aria-disabled", "true");
  fireEvent.change(within(dialog).getByLabelText("Message"), { target: { value: "Question about my statement" } });
  expect(write.getAttribute("href")).toMatch(/^mailto:support@banxum\.com\?subject=An%20investment&body=Question%20about%20my%20statement/);
  // jsdom cannot open a mailto: address; the app's own click handler still runs.
  write.addEventListener("click", (event) => event.preventDefault());
  fireEvent.click(write);
  expect(within(dialog).getByText("Finish in your email app")).toBeInTheDocument();
  expect(within(dialog).queryByText(/Message submitted/)).not.toBeInTheDocument();
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
  fireEvent.click(screen.getByRole("link", { name: "Log in" }));
  fireEvent.change(screen.getByPlaceholderText("you@example.com"), {
    target: { value: "lukas.brunner@example.ch" }
  });
  fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
  fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
}

test("public and portal footers link the platform Terms and Conditions", () => {
  // The public site's footer links the design's terms page; the portal links the published template.
  const site = renderApp("/projects");
  const siteLink = within(screen.getByRole("contentinfo")).getByRole("link", { name: "Terms" });
  expect(siteLink).toHaveAttribute("href", "/legal/terms");
  site.unmount();

  renderApp();
  loginDemo();
  // The U33 portal footer: "Terms" opens the published Terms and Conditions (/legal/terms).
  const portalLinks = screen.getByRole("navigation", { name: "Legal and help" });
  expect(within(portalLinks).getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/legal/terms");
  expect(within(portalLinks).getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/legal/privacy");
});

test("Add Funds offers a copy icon for the IBAN and QR IBAN in CHF and EUR", () => {
  renderApp();
  loginDemo();

  openAccountMenu();
  fireEvent.click(screen.getByRole("button", { name: "Add funds" }));
  const dialog = screen.getByRole("dialog", { name: "Add funds" });
  expect(within(dialog).getByRole("button", { name: "Copy beneficiary" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Copy IBAN" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Copy QR-IBAN" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Copy BIC" })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Copy your personal reference" })).toBeInTheDocument();

  fireEvent.click(within(dialog).getByRole("button", { name: "EUR" }));
  expect(within(dialog).getByRole("button", { name: "EUR" })).toHaveAttribute("aria-pressed", "true");
  expect(within(dialog).getByRole("button", { name: "Copy IBAN" })).toBeInTheDocument();
  expect(within(dialog).queryByRole("button", { name: "Copy QR-IBAN" })).not.toBeInTheDocument();
  expect(within(dialog).getByText("BX-LBR-EUR-4471")).toBeInTheDocument();
});

test("Smart-Invest matches show the purpose as a readable label under the name", () => {
  const match = smartInvestFixture.matches[0];
  const previous = { purpose: match.purpose, originator_name: match.originator_name };
  match.purpose = "bridge_financing";
  match.originator_name = null;
  try {
    renderApp();
    loginDemo();
    clickNav("Smart Invest");

    const table = screen.getByRole("table", { name: "Smart-Invest matches" });
    expect(within(table).getByText("Bridge financing")).toBeInTheDocument();
    expect(within(table).queryByText(/bridge_financing/)).not.toBeInTheDocument();
  } finally {
    match.purpose = previous.purpose;
    match.originator_name = previous.originator_name;
  }
});

test("notifications open their target, can be marked read one by one or all at once", async () => {
  renderApp();
  loginDemo();
  const topbar = screen.getByRole("banner", { name: "Investor account header" });
  const nav = screen.getByRole("navigation", { name: "Investor portal navigation" });
  expect(within(nav).getByRole("link", { name: /^Notifications\s*2$/ })).toBeInTheDocument();

  // The design's dropdown: unread count, latest items with their destination, unread dots.
  fireEvent.click(within(topbar).getByRole("button", { name: "Notifications" }));
  expect(within(topbar).getByText("2 unread")).toBeInTheDocument();
  expect(within(topbar).getAllByRole("img", { name: "Unread" })).toHaveLength(2);

  // Opening a notification marks it read and goes to the holding it is about.
  const defaultNotice = within(topbar).getByRole("link", { name: /^Loan in default/ });
  expect(defaultNotice).toHaveAttribute("href", "/portfolio/H-2201");
  expect(defaultNotice).toHaveTextContent("View investment");
  fireEvent.click(defaultNotice);
  expect(window.location.pathname).toBe("/portfolio/H-2201");
  expect(await within(nav).findByRole("link", { name: /^Notifications\s*1$/ })).toBeInTheDocument();

  // "Mark all as read" in the dropdown clears the rest.
  fireEvent.click(within(topbar).getByRole("button", { name: "Notifications" }));
  expect(within(topbar).getByText("1 unread")).toBeInTheDocument();
  fireEvent.click(within(topbar).getByRole("button", { name: "Mark all as read" }));
  expect(await within(topbar).findByText("All read")).toBeInTheDocument();
  expect(within(nav).getByRole("link", { name: /^Notifications$/ })).toBeInTheDocument();

  clickNav(/^Notifications/);
  const filters = screen.getByRole("navigation", { name: "Notification view" });
  expect(within(filters).getByRole("button", { name: "Unread 0" })).toBeInTheDocument();
  expect(within(screen.getByRole("main")).queryAllByRole("img", { name: "Unread" })).toHaveLength(0);
  expect(screen.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
});

test("the Notifications page marks all as read and opens a notice's page", async () => {
  renderApp();
  loginDemo();
  clickNav(/^Notifications/);

  const main = screen.getByRole("main");
  const filters = within(main).getByRole("navigation", { name: "Notification view" });
  expect(within(filters).getByRole("button", { name: "All 5" })).toHaveAttribute("aria-pressed", "true");
  expect(within(filters).getByRole("button", { name: "Unread 2" })).toBeInTheDocument();
  expect(within(main).getAllByRole("img", { name: "Unread" })).toHaveLength(2);
  // Rows lead to the screen they are about; a failed delivery is amber and says so.
  expect(within(main).getByRole("link", { name: /^Loan in default/ })).toHaveAttribute("href", "/portfolio/H-2201");
  const failed = within(main).getByText("Withdrawal requested: CHF 1,500.00").closest(".nd-row") as HTMLElement;
  expect(failed).toHaveClass("is-late");
  expect(within(failed).getByText(/Email not delivered/)).toBeInTheDocument();

  // The Unread view lists only unread notices.
  fireEvent.click(within(filters).getByRole("button", { name: "Unread 2" }));
  expect(within(main.querySelector(".nd-list") as HTMLElement).getAllByRole("link")).toHaveLength(2);

  fireEvent.click(within(main).getByRole("button", { name: "Mark all as read" }));
  expect(await within(main).findByRole("heading", { name: "No unread notifications" })).toBeInTheDocument();
  expect(within(filters).getByRole("button", { name: "Unread 0" })).toBeInTheDocument();
  fireEvent.click(within(main).getByRole("button", { name: /View all notifications/ }));

  fireEvent.click(within(main).getByRole("link", { name: /^Balance ageing - day 57/ }));
  expect(window.location.pathname).toBe("/balances");
});

test("the opportunity page explains when the balance is too old for the funding window", () => {
  const chfLots = balanceLotsFixture.filter((lot) => lot.currency === "CHF");
  const previous = chfLots.map((lot) => lot.bucket);
  chfLots.forEach((lot) => {
    lot.bucket = "overdue";
  });
  try {
    renderApp();
    loginDemo();
    clickNav("Investment opportunities");
    fireEvent.click(screen.getByRole("link", { name: "View details of Helvetia Logistik AG" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Choose investment amount" }), { target: { value: "2000" } });
    fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
    const error = document.getElementById("iv-error") as HTMLElement;
    expect(error).toHaveTextContent("Your CHF balance does not have enough holding time left for this loan's funding period.");
    expect(error).not.toHaveTextContent(/No investable balance is available/);
    // Money that is too old cannot be fixed by adding funds: the button stays Review investment.
    expect(screen.getByRole("button", { name: /Review investment/ })).toBeInTheDocument();
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
    clickNav("Investment opportunities");
    fireEvent.click(screen.getByRole("link", { name: "View details of Léman BioTech SA" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Choose investment amount" }), { target: { value: "5001" } });
    fireEvent.click(screen.getByRole("button", { name: /Review investment/ }));
    expect(screen.getByText("This opportunity has only CHF 5.000,00 left, so that is the most you can invest here.")).toBeInTheDocument();
    expect(screen.queryByText(/is not lent/)).not.toBeInTheDocument();

    // Review & sign names the same limit.
    goToPath("/marketplace/GA-2390/invest");
    applyReviewAmount("5001");
    expect(screen.getByText(/This opportunity has only CHF 5\.000,00 left/)).toBeInTheDocument();
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
  expect(within(reversalRow).getByText(/\+2\.000,00/)).toBeInTheDocument();
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
    // The available balance does not include the penalty: it is listed per lot in Balance details,
    // with a note that it is already deducted (penalty mode exists until U33-DEC-04).
    const details = screen.getByText("Balance details").closest("details") as HTMLElement;
    const table = within(details).getByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Penalty charged" })).toBeInTheDocument();
    const overdueRow = within(table).getByText("980,00").closest("tr") as HTMLElement;
    expect(within(overdueRow).getByText("49,00")).toBeInTheDocument();
    expect(within(overdueRow).getByText("Due back")).toBeInTheDocument();
    expect(within(details).getByText("Penalty charged so far: CHF 49,00. It is already deducted and not part of any balance shown.")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "CHF account" })).getByText("24.190,00")).toBeInTheDocument();
  } finally {
    overdueLot!.penalized_amount_minor = 0;
    chf!.penalty_charged_minor = 0;
  }
});

test("withdrawal review shows the destination IBAN and account name before the code step", () => {
  renderApp();
  loginDemo();
  clickNav(/^Account/);
  fireEvent.click(within(screen.getByRole("region", { name: "CHF account" })).getByRole("button", { name: "Withdraw" }));
  const dialog = screen.getByRole("dialog", { name: "Withdraw" });
  // The verified account is chosen; timing and fee follow U33-DEC-35.
  expect(within(dialog).getByText("Usually 1–3 business days · No Banxum fee")).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: /Continue/ }));
  expect(within(dialog).getByText("Enter the amount to withdraw.")).toBeInTheDocument();
  fireEvent.change(within(dialog).getByLabelText("Amount to withdraw"), { target: { value: "250" } });
  fireEvent.click(within(dialog).getByRole("button", { name: /Continue/ }));

  const review = screen.getByRole("dialog", { name: "Confirm withdrawal" });
  expect(within(review).getByText("250,00")).toBeInTheDocument();
  expect(within(review).getByText("CH93 0076 2011 6238 5295 7")).toBeInTheDocument();
  expect(within(review).getByText("Lukas Brunner")).toBeInTheDocument();
  expect(within(review).getByRole("textbox", { name: "Email confirmation code" })).toBeInTheDocument();
});

test("activity shows penalty charges and labels a forced return as such", () => {
  const added = [
    {
      id: "P-1",
      activity_type: "balance_penalty_charge",
      occurred_at: "2026-05-02T12:00:00+02:00",
      direction: "out" as const,
      title: "Penalty charged: balance past the 60-day limit",
      amount_minor: 50_00,
      currency: "CHF",
      status: "charged",
      loan_id: null,
      loan_title: "",
      metadata: { balance_lot_id: "lot-1", charge_date: "2026-05-02", penalty_bps_per_day: 100 }
    },
    {
      id: "W-401",
      activity_type: "withdrawal_request",
      occurred_at: "2026-05-01T12:00:00+02:00",
      direction: "out" as const,
      title: "Forced return to your bank account",
      amount_minor: 4_950_00,
      currency: "CHF",
      status: "requested",
      loan_id: null,
      loan_title: "",
      metadata: { is_forced: true, destination_iban: "CH9300762011623852957", finalized_at: "", cancelled_at: "" }
    }
  ];
  activityFixture.entries.push(...added);
  try {
    renderApp();
    loginDemo();
    clickNav("My investments");
    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));

    const penaltyRow = screen.getByText("Penalty charged: balance past the 60-day limit").closest("tr") as HTMLElement;
    expect(within(penaltyRow).getByText("penalty")).toBeInTheDocument();
    expect(within(penaltyRow).getByText(/-50,00/)).toBeInTheDocument();
    const forcedRow = screen.getByText("Forced return to your bank account").closest("tr") as HTMLElement;
    expect(within(forcedRow).getByText("forced return")).toBeInTheDocument();
    expect(within(forcedRow).getByText("Pending")).toBeInTheDocument();
  } finally {
    activityFixture.entries.splice(activityFixture.entries.length - added.length, added.length);
  }
});
