import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, onTestFinished, test } from "vitest";

import { App } from "./App";
import { setMultilanguageForTests } from "./i18n/language";
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

test("the language menu is hidden while multilanguage is paused", () => {
  renderApp("/");
  expect(within(screen.getByRole("banner")).queryByRole("button", { name: /^Language/ })).not.toBeInTheDocument();
});

test("the language menu announces German and French with a toast (kept for 18.13)", () => {
  setMultilanguageForTests(true);
  onTestFinished(() => setMultilanguageForTests(false));
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

// The activity list moved from the portfolio's Activity tab to Transactions (U33).
test("transactions label preserved pre-reset activity without replacing its details", () => {
  const entry = activityFixture.entries[0];
  const previous = entry.archived_at;
  entry.archived_at = "2026-09-09T12:00:00Z";
  try {
    renderApp();
    fireEvent.click(screen.getByRole("link", { name: "Log in" }));
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "lukas.brunner@example.ch" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in link" }));
    fireEvent.click(screen.getByRole("button", { name: "Open link in demo" }));
    clickNav("Transactions");
    // The entry keeps its own label and details; the mark is added next to them.
    const row = screen.getByText("Before QA reset").closest("tr") as HTMLElement;
    expect(within(row).getByText("Investment order")).toBeInTheDocument();
    expect(within(row).getByText("Tessin Bauwerk AG")).toBeInTheDocument();
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

  // The design's public home has no sign-up band: Log in, then "Create an account".
  fireEvent.click(screen.getAllByRole("link", { name: /^Log in/ })[0]);
  fireEvent.click(screen.getByRole("link", { name: "Create an account" }));
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

test("Smart Invest shows each match as its own opportunity with no bulk selection or batch approval", () => {
  renderApp();
  loginDemo();
  clickNav("Smart Invest");

  expect(screen.getByRole("heading", { level: 1, name: "Smart Invest" })).toBeInTheDocument();
  expect(screen.getByText("Your preferences").nextElementSibling).toHaveTextContent("EUR / CHF · 8,5% per year or more · Up to 36 months · Any security type");
  expect(screen.getAllByRole("button", { name: /^Review investment in / })).toHaveLength(smartInvestFixture.matches.length);
  // U33-DEC-19: nothing to tick, approve or confirm in bulk, and nothing is reserved on this page.
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Review & confirm|Untick|Place \d|Approve/ })).not.toBeInTheDocument();
  expect(screen.getByText(/You review and confirm each investment\./)).toBeInTheDocument();
  // No risk rating anywhere (U33-DEC-16).
  expect(screen.queryByText(/risk rating|Rating/)).not.toBeInTheDocument();

  // U33-DEC-30: the in-app and email alerts have their own switches.
  expect(screen.getByText("New matches appear in your notifications.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Notification settings/ }));
  const channels = screen.getByRole("dialog", { name: "Notify me about matching investment opportunities" });
  const inApp = within(channels).getByRole("checkbox", { name: "In the app" });
  expect(inApp).toBeChecked();
  expect(within(channels).getByRole("checkbox", { name: "By email" })).toBeChecked();
  fireEvent.click(inApp);
  fireEvent.click(within(channels).getByRole("button", { name: "Save preferences" }));
  expect(screen.queryByRole("dialog", { name: "Notify me about matching investment opportunities" })).not.toBeInTheDocument();
  expect(screen.getByText("New matches are sent to you by email.")).toBeInTheDocument();
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

    // Smart Invest reserves nothing: each match is its own card with its minimum, and the amount is
    // chosen on the opportunity page (U33-DEC-19).
    clickNav("Smart Invest");
    const card = screen.getByRole("button", { name: "Review investment in Expensive minimum loan" }).closest(".r35-card") as HTMLElement;
    expect(within(card).getByText("Min. CHF 25.000,00")).toBeInTheDocument();
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

test("Smart-Invest matches open their opportunity page, where the investment is reviewed and confirmed", () => {
  renderApp();
  loginDemo();
  clickNav("Smart Invest");

  fireEvent.click(screen.getByRole("button", { name: "Review investment in Adriatic Marine d.o.o." }));
  expect(window.location.pathname).toBe("/marketplace/GA-2395");
  expect(screen.getAllByText("Adriatic Marine d.o.o.").length).toBeGreaterThan(0);
});

test("Smart Invest pauses with the preferences kept and resumes with the matches recalculated (U33-DEC-19)", async () => {
  renderApp();
  loginDemo();
  clickNav("Smart Invest");

  fireEvent.click(screen.getByRole("button", { name: "Pause Smart Invest" }));
  expect(await screen.findByRole("heading", { name: "Smart Invest is paused." })).toBeInTheDocument();
  expect(screen.getByText("Preferred investment amount").nextElementSibling).toHaveTextContent("Choose for each investment");
  expect(screen.getByText("Minimum annual interest rate").nextElementSibling).toHaveTextContent("8,5% per year");
  expect(screen.getByText("Maximum investment duration").nextElementSibling).toHaveTextContent("36 months");
  // No matches, marks or counters while paused.
  expect(screen.queryByRole("button", { name: /^Review investment in / })).not.toBeInTheDocument();
  clickNav("Overview");
  expect(screen.getByText("Smart Invest is paused. Your preferences are saved.")).toBeInTheDocument();
  clickNav("Smart Invest");

  fireEvent.click(screen.getByRole("button", { name: /Resume Smart Invest/ }));
  expect(await screen.findByText("Your preferences")).toBeInTheDocument();
  expect(screen.getByText("Active")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Pause Smart Invest" })).toBeInTheDocument();
});

test("Smart Invest uses the four U33 preference steps and never implies automatic investing", async () => {
  const savedRule = smartInvestFixture.rule;
  smartInvestFixture.rule = null;
  try {
  renderApp();
  loginDemo();
  clickNav("Smart Invest");

  expect(await screen.findByRole("heading", { name: "A simpler way to find investments." })).toBeInTheDocument();
  expect(screen.getByText("You review and confirm each investment.")).toBeInTheDocument();
  expect(screen.queryByText(/reinvest|automatic/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Set up Smart Invest/ }));

  expect(screen.getByRole("heading", { level: 1, name: "Set up Smart Invest" })).toBeInTheDocument();
  const progress = screen.getByRole("list", { name: "Smart Invest setup" });
  expect(within(progress).getAllByRole("listitem").map((item) => item.querySelector("b")?.textContent)).toEqual([
    "Currency",
    "Interest & duration",
    "Security",
    "Review & activate"
  ]);
  expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Choose your currencies" })).toBeInTheDocument();
  // Both currencies are preselected; at least one is required.
  fireEvent.click(screen.getByRole("checkbox", { name: /EUR/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /CHF/ }));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Choose at least one currency.");
  fireEvent.click(screen.getByRole("checkbox", { name: /CHF/ }));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  expect(screen.getByRole("heading", { name: "Set your interest and duration preferences" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "No preference", pressed: true })).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  expect(screen.getByRole("heading", { name: "Choose your security preferences" })).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "No preference" })).toBeChecked();
  // No risk rating, purpose or loan type preference (U33-DEC-16/19).
  expect(screen.queryByText(/risk rating|purpose|loan type/i)).not.toBeInTheDocument();
  // Maximum loan-to-value (U33-DEC-19).
  const ltv = screen.getByRole("heading", { name: "Maximum loan-to-value" }).closest("section") as HTMLElement;
  fireEvent.click(within(ltv).getByRole("button", { name: "Set a limit" }));
  fireEvent.click(within(ltv).getByRole("button", { name: "70%" }));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  expect(screen.getByRole("heading", { name: "Review & activate Smart Invest" })).toBeInTheDocument();
  expect(screen.getByText("Currencies", { selector: "dt" }).nextElementSibling).toHaveTextContent("CHF");
  const rates = screen.getByText("Interest & duration", { selector: "dt" }).nextElementSibling;
  expect(rates).toHaveTextContent("Interest rate: no preference");
  expect(rates).toHaveTextContent("Term: no preference");
  const security = screen.getByText("Security", { selector: "dt" }).nextElementSibling;
  expect(security).toHaveTextContent("Security type: no preference");
  expect(security).toHaveTextContent("Maximum loan-to-value 70%");
  for (const name of ["Edit currencies", "Edit interest & duration", "Edit security"]) {
    expect(screen.getByRole("button", { name })).toBeInTheDocument();
  }
  // More preferences: borrower country, originator and the optional usual amount.
  fireEvent.change(screen.getByLabelText("Borrower country"), { target: { value: "CH" } });
  fireEvent.change(screen.getByLabelText(/Preferred investment amount/), { target: { value: "1000" } });
  expect(screen.getByText(/A saved amount applies separately in each selected currency\./)).toBeInTheDocument();
  expect(screen.getByText("No money is invested or reserved when you activate Smart Invest. You confirm each investment.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Activate Smart Invest" }));

  expect(await screen.findByText("CHF 1.000,00 per investment · Any interest rate · Any duration · Loan-to-value up to 70% · Switzerland")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Edit preferences" })).toBeInTheDocument();
  } finally {
    smartInvestFixture.rule = savedRule;
  }
});

test("the usual Smart Invest amount prepares the amount but is never raised to the minimum (U33-DEC-19)", () => {
  const rule = smartInvestFixture.rule;
  if (!rule) throw new Error("fixture rule missing");
  const saved = rule.preferred_amount_minor;
  rule.preferred_amount_minor = 250_000;
  try {
    renderApp();
    loginDemo();
    clickNav("Smart Invest");
    expect(screen.getByText("Your preferences").nextElementSibling).toHaveTextContent("EUR 2.500,00 / CHF 2.500,00 per investment");
    // The match stays; its card says why the usual amount does not fit.
    const card = screen.getByRole("button", { name: "Review investment in Adriatic Marine d.o.o." }).closest(".r35-card") as HTMLElement;
    expect(within(card).getByText("Your usual amount of EUR 2.500,00 is more than is still available here.")).toBeInTheDocument();

    goToPath("/marketplace/GA-2401");
    expect(screen.getByRole("textbox", { name: "Choose investment amount" })).toHaveValue("2500,00");
    expect(screen.getByText("Your usual Smart Invest amount. You can change it.")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Choose investment amount" }), { target: { value: "1500" } });
    expect(screen.getByRole("textbox", { name: "Choose investment amount" })).toHaveValue("1500");
    expect(screen.queryByText("Your usual Smart Invest amount. You can change it.")).not.toBeInTheDocument();

    rule.preferred_amount_minor = 50_000;
    goToPath("/marketplace/GA-2399");
    expect(screen.getByRole("textbox", { name: "Choose investment amount" })).toHaveValue("500,00");
    expect(screen.getByText("Your usual Smart Invest amount is below the minimum here. Enter at least the minimum to invest.")).toBeInTheDocument();
  } finally {
    rule.preferred_amount_minor = saved;
  }
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
    expect(resultLine()).toHaveTextContent("6 opportunities · 5 open · 1 coming soon");
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

  // The resale market uses the design's resale table (U33).
  clickNav("Resale market");
  expect(screen.getByRole("table")).toHaveClass("rs-table");
  fireEvent.click(screen.getByRole("button", { name: "My listings" }));
  const resaleTables = screen.getAllByRole("table");
  expect(resaleTables.length).toBeGreaterThan(0);
  for (const table of resaleTables) expect(table).toHaveClass("rs-table");

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
  expect(resultLine()).toHaveTextContent("6 opportunities · 5 open · 1 coming soon");
  expect(screen.getByRole("button", { name: "Cards" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("heading", { name: "Helvetia Logistik AG" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View details of Helvetia Logistik AG" })).toHaveAttribute("href", "/marketplace/GA-2401");
  // No ratings (U33-DEC-16) and no co-investment claim (U33-DEC-15).
  expect(screen.getByRole("main")).not.toHaveTextContent(/rating|alongside you/i);

  // U33-DEC-17: the Coming soon card comes after the open ones, without the funding block.
  const soonCard = screen.getByRole("heading", { name: "Engadin Lodge AG" }).closest(".bxm-project") as HTMLElement;
  expect(soonCard).toHaveClass("r31-coming-soon");
  expect(within(soonCard).getByText("Coming soon")).toHaveClass("bxm-tag");
  expect(soonCard).toHaveTextContent(/Opens \d{1,2} [A-Z][a-z]{2}/);
  const cardTitles = screen.getAllByRole("heading", { level: 6 }).map((heading) => heading.textContent);
  expect(cardTitles[cardTitles.length - 1]).toBe("Engadin Lodge AG");

  fireEvent.click(screen.getByRole("button", { name: "List" }));
  const table = screen.getByRole("table");
  expect(within(table).getAllByRole("row")).toHaveLength(7);
  expect(within(table).getByRole("link", { name: "Helvetia Logistik AG" })).toHaveAttribute("href", "/marketplace/GA-2401");
  const soonRow = within(table).getByRole("link", { name: "Engadin Lodge AG" }).closest("tr") as HTMLElement;
  expect(within(soonRow).getByText("Coming soon")).toHaveClass("ol-soon");
  expect(soonRow).not.toHaveTextContent("Min.");
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

test("a Coming soon opportunity cannot be invested in and offers the opening alert (U33-DEC-17)", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/GA-2410");

  expect(screen.getByRole("heading", { level: 1, name: "Engadin Lodge AG" })).toBeInTheDocument();
  expect(screen.getByText("Coming soon", { selector: ".l8-open" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 6, name: /^Opens on \d{1,2} [A-Z][a-z]{2} \d{4}$/ })).toBeInTheDocument();
  expect(screen.getByText(/^You can reserve an amount from that day\. Funding closes on \d{1,2} [A-Z][a-z]{2} \d{4}\.$/)).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: "Choose investment amount" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Tell me when it opens" }));
  expect(screen.getByText("We will email you when this loan opens")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel the opening alert" }));
  expect(screen.getByRole("button", { name: "Tell me when it opens" })).toBeInTheDocument();
  expect(screen.queryByText("We will email you when this loan opens")).not.toBeInTheDocument();
});

test("Save for later keeps the opportunity and the amount, on Overview and on the cards, and reserves nothing (U33-DEC-18)", async () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/GA-2401");
  const amount = () => screen.getByRole("textbox", { name: "Choose investment amount" });

  // An amount below the minimum is not saved.
  fireEvent.change(amount(), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "Save for later" }));
  expect(screen.getByText(/^The minimum investment is/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save for later" })).toHaveAttribute("aria-pressed", "false");

  fireEvent.change(amount(), { target: { value: "5000" } });
  fireEvent.click(screen.getByRole("button", { name: "Save for later" }));
  const saved = await screen.findByRole("button", { name: "Saved" });
  expect(saved).toHaveAttribute("aria-pressed", "true");
  expect(saved).toHaveAttribute("title", "Remove saved opportunity");

  goToPath("/dashboard");
  const panel = screen.getByRole("region", { name: "Saved investment reviews" });
  expect(within(panel).getByRole("heading", { name: "Continue your investment review" })).toBeInTheDocument();
  expect(panel).toHaveTextContent("Saved for later · No funds reserved");
  expect(within(panel).getByRole("heading", { name: "Helvetia Logistik AG" })).toBeInTheDocument();
  expect(panel).toHaveTextContent(/Your amount\s*CHF 5.000,00/);
  fireEvent.click(within(panel).getByRole("button", { name: /Continue review/ }));
  expect(window.location.pathname).toBe("/marketplace/GA-2401");
  expect(amount()).toHaveValue("5000,00");
  expect(screen.getByRole("button", { name: "Saved" })).toBeInTheDocument();

  // The card has the Saved badge; it removes the saved opportunity. The order does not change.
  goToPath("/marketplace");
  fireEvent.click(screen.getByRole("button", { name: "Remove saved opportunity: Helvetia Logistik AG" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: /Remove saved opportunity/ })).not.toBeInTheDocument());
  goToPath("/dashboard");
  expect(screen.queryByRole("region", { name: "Saved investment reviews" })).not.toBeInTheDocument();

  // Without an amount the opportunity is saved alone.
  goToPath("/marketplace/GA-2402");
  expect(amount()).toHaveValue("");
  fireEvent.click(screen.getByRole("button", { name: "Save for later" }));
  expect(await screen.findByRole("button", { name: "Saved" })).toBeInTheDocument();
  goToPath("/dashboard");
  const row = within(screen.getByRole("region", { name: "Saved investment reviews" }));
  expect(row.getByRole("heading", { name: "Nordwind Energie GmbH" })).toBeInTheDocument();
  expect(row.queryByText("Your amount")).not.toBeInTheDocument();
  fireEvent.click(row.getByRole("button", { name: "Remove saved review: Nordwind Energie GmbH" }));
  await waitFor(() => expect(screen.queryByRole("region", { name: "Saved investment reviews" })).not.toBeInTheDocument());
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
  expect(resultLine()).toHaveTextContent("6 opportunities · 5 open · 1 coming soon");

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
  expect(resultLine()).toHaveTextContent("6 opportunities · 5 open · 1 coming soon");

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
  // Four open Direct loans and the Coming soon one (U33-DEC-17).
  expect(resultLine()).toHaveTextContent("5 opportunities · 5 open in total · 1 coming soon");
});

test("Smart Invest preferences save several security types and an originator", async () => {
  renderApp();
  loginDemo();
  clickNav("Smart Invest");
  fireEvent.click(screen.getByRole("button", { name: "Edit preferences" }));

  expect(screen.getByRole("heading", { level: 1, name: "Edit Smart Invest" })).toBeInTheDocument();
  // Editing opens any step directly.
  fireEvent.click(within(screen.getByRole("list", { name: "Smart Invest setup" })).getByRole("button", { name: "Security" }));
  // The saved fixture rule accepts any security: every type is ticked, group by group.
  expect(screen.getByRole("checkbox", { name: "Property mortgage" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Select all: Guarantees" })).toBeChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: "No preference" }));
  expect(screen.getByRole("checkbox", { name: "Property mortgage" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: "Property mortgage" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Company guarantee" }));
  expect(screen.getByRole("checkbox", { name: "No preference" })).not.toBeChecked();
  fireEvent.click(within(screen.getByRole("list", { name: "Smart Invest setup" })).getByRole("button", { name: "Review & save" }));

  expect(screen.getByText("Security", { selector: "dt" }).nextElementSibling).toHaveTextContent("Security type: Property mortgage, Company guarantee");
  fireEvent.change(screen.getByLabelText("Originator"), { target: { value: "banxum" } });
  fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));

  expect(await screen.findByText("Your preferences")).toBeInTheDocument();
  expect(screen.getByText("Your preferences").nextElementSibling).toHaveTextContent(
    "EUR / CHF · 8,5% per year or more · Up to 36 months · Property mortgage, Company guarantee · Banxum direct loans"
  );
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
  expect(screen.getByText("Total over 24 months")).toBeInTheDocument();
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
  fireEvent.click(within(claim).getByRole("button", { name: "Close" }));
  // U33-DEC-24: the actual split of this loan is stated before confirmation.
  const split = document.querySelector(".u33-rights-split") as HTMLElement;
  expect(split).toHaveTextContent(/Interest: 70,0+% to you, 30,0+% to the Loan Originator\./);
  expect(split).toHaveTextContent(/Penalty interest, when the borrower pays it: 50,0+% to you, 50,0+% to the Loan Originator\./);
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

test("current investments sort by interest rate and, in one currency, by outstanding principal", () => {
  renderApp();
  loginDemo();
  clickNav("My investments");

  const current = () => screen.getByRole("region", { name: /Current investments/ });
  const names = () => Array.from(current().querySelectorAll(".bxm-mi-name")).map((node) => node.textContent);
  const currentHoldings = portfolioFixture.holdings.filter((holding) => holding.status === "active" && holding.current_principal_minor > 0);
  const rate = (holding: (typeof currentHoldings)[number]) => holding.loan.yield_bps || holding.loan.interest_rate_bps;
  const sort = within(current()).getByRole("combobox", { name: "Sort investments" });

  fireEvent.change(sort, { target: { value: "interest" } });
  expect(names()).toEqual(
    [...currentHoldings].sort((left, right) => rate(right) - rate(left) || left.loan.loan_title.localeCompare(right.loan.loan_title)).map((holding) => holding.loan.loan_title)
  );

  // Principal amounts are compared within one currency only: the option asks for a currency first.
  const principalOption = within(sort).getByRole("option", { name: /Outstanding principal: highest/ }) as HTMLOptionElement;
  expect(principalOption).toBeDisabled();
  fireEvent.click(within(screen.getByRole("main")).getByRole("button", { name: "CHF" }));
  const chfSort = within(current()).getByRole("combobox", { name: "Sort investments" });
  expect(within(chfSort).getByRole("option", { name: "Outstanding principal: highest" })).toBeEnabled();
  fireEvent.change(chfSort, { target: { value: "principal" } });
  expect(names()).toEqual(
    currentHoldings
      .filter((holding) => holding.currency === "CHF")
      .sort((left, right) => right.current_principal_minor - left.current_principal_minor || left.loan.loan_title.localeCompare(right.loan.loan_title))
      .map((holding) => holding.loan.loan_title)
  );
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

test("several securities show on the opportunity, in the credit file and in the filter (U33-DEC-21)", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/GA-2401");
  // The first security keeps the loan-to-value figure; the guarantee follows with its limit.
  const securityTypes = document.querySelector(".rc-security-types") as HTMLElement;
  expect(within(securityTypes).getByText("Personal guarantee")).toBeInTheDocument();
  expect(securityTypes).toHaveTextContent(/Main shareholder · Limit CHF 400.000,00/);

  goToPath("/marketplace/GA-2401/credit-file");
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  fireEvent.click(within(screen.getByRole("navigation", { name: "Credit file contents" })).getByRole("button", { name: /Security$/ }));
  const chapter = document.getElementById("security") as HTMLElement;
  expect(within(chapter).getByText("Rights & priority").nextElementSibling).toHaveTextContent("Rank 2");
  expect(within(chapter).getByText("Prepared by").nextElementSibling).toHaveTextContent("Wüest Partner AG");
  expect(within(chapter).getByText("Prior-ranking debt").nextElementSibling).toHaveTextContent("CHF 300.000,00");
  // (300,000 + 1,450,000) / 2,500,000 = 70%: the combined share is labelled as such.
  expect(chapter).toHaveTextContent("Including prior debt, total secured borrowing is 70,0% of the stated value.");
  const guarantee = chapter.querySelector(".r100-guarantee") as HTMLElement;
  expect(within(guarantee).getByText("Guarantee limit").nextElementSibling).toHaveTextContent("CHF 400.000,00");
  expect(within(guarantee).getByText("Provider / owner").nextElementSibling).toHaveTextContent("Main shareholder");
  expect(guarantee).toHaveTextContent("Joint and several guarantee for principal and interest.");

  // The security filter matches any security of the loan.
  goToPath("/marketplace");
  fireEvent.click(screen.getByRole("button", { name: /^Filters/ }));
  fireEvent.click(within(screen.getByRole("region", { name: "Investment filters" })).getByRole("checkbox", { name: "Personal guarantee" }));
  expect(resultLine()).toHaveTextContent("1 opportunity");
  expect(screen.getByRole("heading", { name: "Helvetia Logistik AG" })).toBeInTheDocument();
});

test("the credit file has seven chapters with structured financials, key ratios, checks and document metadata (U33-DEC-20)", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/GA-2401/credit-file");
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  const contents = within(screen.getByRole("navigation", { name: "Credit file contents" }));
  expect(contents.getAllByRole("button").map((button) => button.textContent?.replace(/^\d+/, ""))).toEqual([
    "Summary",
    "Borrower & business",
    "Financials",
    "Security",
    "Loan terms",
    "Checks & updates",
    "Documents"
  ]);

  fireEvent.click(contents.getByRole("button", { name: /Financials$/ }));
  const chapter = document.getElementById("financials") as HTMLElement;
  expect(chapter).toHaveTextContent(/2023–2025/);
  expect(chapter).toHaveTextContent(/Historical · CHF thousands/);
  const pl = within(chapter).getByRole("heading", { name: "Profit & loss" }).closest("section") as HTMLElement;
  expect(within(pl).getByRole("row", { name: /^Revenue/ })).toHaveTextContent(/10.400\s*11.200\s*11.800/);
  expect(within(pl).queryByText("Staff costs")).not.toBeInTheDocument();
  fireEvent.click(within(pl).getByRole("button", { name: "Operating profit" }));
  expect(within(pl).getByRole("row", { name: /Staff costs/ })).toHaveTextContent(/-2.500\s*-2.650\s*-2.770/);
  const ratios = within(chapter).getByRole("heading", { name: "Key ratios" }).closest("section") as HTMLElement;
  // 2025: equity 3,360 / assets 8,000 = 42.0%; debt 3,030 / equity 3,360 = 0.90x; 1,050 / 11,800 = 8.9%; 1,050 / 160 = 6.56x.
  expect(within(ratios).getByRole("row", { name: /Equity \/ total assets/ })).toHaveTextContent(/42,0%$/);
  expect(within(ratios).getByRole("row", { name: /Financial debt \/ equity/ })).toHaveTextContent(/0,90×$/);
  expect(within(ratios).getByRole("row", { name: /Operating margin/ })).toHaveTextContent(/8,9%$/);
  expect(within(ratios).getByRole("row", { name: /Interest coverage/ })).toHaveTextContent(/6,56×$/);
  fireEvent.click(within(ratios).getByRole("button", { name: "Ratio formulas" }));
  expect(within(screen.getByRole("dialog", { name: "Key ratios" })).getByText("Operating profit ÷ interest expense.")).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("dialog", { name: "Key ratios" })).getByRole("button", { name: /Close/ }));
  expect(within(chapter).getByRole("row", { name: /Property loan/ })).toHaveTextContent("Mortgage on separate premises");

  fireEvent.click(contents.getByRole("button", { name: /Checks & updates$/ }));
  const checks = document.getElementById("checks") as HTMLElement;
  expect(checks).toHaveTextContent("Recorded by Banxum");
  expect(within(checks).getByText("Company and owners")).toBeInTheDocument();
  expect(checks).toHaveTextContent("Source: Commercial register and shareholder register");
  expect(checks).toHaveTextContent("Warehouse occupancy, fleet costs and cash generation.");
  // The design's chips and the reporting plan (proposed, so the note says it is still to be agreed).
  expect(within(within(checks).getByText("Company and owners").closest(".r100-check") as HTMLElement).getByText("Reviewed")).toBeInTheDocument();
  expect(within(within(checks).getByText("Property and charges").closest(".r100-check") as HTMLElement).getByText("Received")).toBeInTheDocument();
  const reporting = within(checks).getByRole("heading", { name: "Reporting over the loan term" }).closest("section") as HTMLElement;
  expect(within(reporting).getByText("Proposed plan")).toBeInTheDocument();
  expect(within(reporting).getByRole("heading", { name: "Annual financial statements" })).toBeInTheDocument();
  expect(reporting).toHaveTextContent("Reporting requirements and delivery dates are to be agreed for this loan.");

  fireEvent.click(contents.getByRole("button", { name: /Documents$/ }));
  expect(screen.getByRole("button", { name: "Download Borrower financial summary" })).toHaveTextContent("Financial statements · FY 2025 · Helvetia Logistik AG · Version 1 · Final");
});

test("Loan terms show the investor's and the originator's shares of interest and penalty interest (U33-DEC-24)", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/LO-2601/credit-file");
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  fireEvent.click(within(screen.getByRole("navigation", { name: "Credit file contents" })).getByRole("button", { name: /Loan terms$/ }));
  const facts = (label: string) => screen.getByText(label).nextElementSibling;
  expect(facts("Your share of the borrower's interest")).toHaveTextContent(/^70,0+%$/);
  expect(facts("Originator's share of interest")).toHaveTextContent(/^30,0+%$/);
  expect(facts("Your share of penalty interest")).toHaveTextContent(/^50,0+%$/);
  expect(facts("Originator's share of penalty interest")).toHaveTextContent(/^50,0+%$/);
});

test("the credit file's Borrower & business chapter shows the published story, safely rendered", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/GA-2401/credit-file");
  fireEvent.click(screen.getByRole("button", { name: /Open credit file/ }));
  fireEvent.click(screen.getByRole("button", { name: /Borrower & business/ }));

  expect(screen.getByRole("heading", { level: 3, name: "Meet the borrower" })).toBeInTheDocument();
  expect(screen.getByText("Established").nextElementSibling).toHaveTextContent("2011");
  // U33-DEC-23: the head count always shows its year; the city comes before the country.
  expect(screen.getByText("Employees").nextElementSibling).toHaveTextContent("118 in 2025");
  expect(screen.getByText("Location").nextElementSibling).toHaveTextContent("Basel, Switzerland");
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
  // A missing head count is left out, never shown as zero.
  expect(screen.queryByText("Employees")).not.toBeInTheDocument();
  expect(screen.getByText("Location").nextElementSibling).toHaveTextContent("Sion, Switzerland");
});

test("opportunity cards show the borrower's city, and only the country when the city is unknown", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace");
  const card = (title: string) => screen.getByRole("heading", { level: 6, name: title }).closest(".card") as HTMLElement;
  expect(within(card("Helvetia Logistik AG")).getByText("Basel, Switzerland")).toBeInTheDocument();
  expect(within(card("Swiss SME equipment claim")).getByText("Winterthur, Switzerland")).toBeInTheDocument();
});

test("the loan originators pages show the originator's city, sector and founding year", () => {
  renderApp();
  loginDemo();
  goToPath("/marketplace/originators");
  const row = screen.getByRole("link", { name: "Alpine Credit Partners AG" }).closest("article") as HTMLElement;
  expect(within(row).getByText("Zug, Switzerland")).toBeInTheDocument();
  expect(within(row).getByText("Equipment financing for Swiss SMEs")).toBeInTheDocument();

  fireEvent.click(within(row).getByRole("link", { name: "Alpine Credit Partners AG" }));
  expect(screen.getByRole("heading", { level: 1, name: "Alpine Credit Partners AG" })).toBeInTheDocument();
  expect(screen.getByText("Equipment financing for Swiss SMEs · Zug, Switzerland")).toBeInTheDocument();
  expect(screen.getByText("Founded").nextElementSibling).toHaveTextContent("2011");
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

test("reserved orders stay under In funding until funding closes and open their own page", () => {
  const originalHoldings = portfolioFixture.holdings;
  const originalOrders = primaryOrdersFixture.orders;
  portfolioFixture.holdings = [];
  primaryOrdersFixture.orders = [
    {
      ...originalOrders[0],
      status: "balance_allocated",
      requested_amount_minor: 500000,
      allocated_amount_minor: 500000,
      allocated_at: "2026-06-04T10:00:00+02:00"
    }
  ];
  const order = primaryOrdersFixture.orders[0];

  try {
    renderApp();
    loginDemo();
    clickNav("My investments");

    const funding = screen.getByRole("region", { name: /In funding/ });
    expect(within(funding).getByText("Your reserved investments")).toBeInTheDocument();
    expect(within(funding).getByText("Your reserved amount")).toBeInTheDocument();
    expect(within(funding).getAllByText("CHF 5.000,00").length).toBeGreaterThan(0);
    // An order is not an investment yet.
    expect(screen.getByText("No current investments")).toBeInTheDocument();
    expect(screen.getByText(/Reservations stay under In funding until then\./)).toBeInTheDocument();
    expect(screen.queryByText("Portfolio interest")).not.toBeInTheDocument();

    fireEvent.click(within(funding).getByRole("link", { name: new RegExp(order.loan_title) }));
    expect(window.location.pathname).toBe(`/portfolio/${order.id}`);
    expect(screen.getByRole("heading", { level: 1, name: order.loan_title })).toBeInTheDocument();
    expect(screen.getByText("Reserved", { selector: ".r71-status" })).toBeInTheDocument();
    expect(screen.getByText(/Reserved from your Banxum account on/)).toBeInTheDocument();
    expect(screen.getByText("Reserved for investments")).toBeInTheDocument();
  } finally {
    portfolioFixture.holdings = originalHoldings;
    primaryOrdersFixture.orders = originalOrders;
  }
});

test("released and never-invested primary orders are not shown as in funding", () => {
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
    loginDemo();
    clickNav("My investments");

    expect(screen.getByRole("heading", { level: 1, name: "My investments" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /In funding/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Your reserved amount")).not.toBeInTheDocument();
    expect(screen.queryByText("Requested · not reserved yet")).not.toBeInTheDocument();

    // A released order is no investment: its address shows the not-found page.
    window.history.pushState({}, "", "/portfolio/O-RELEASED");
    fireEvent(window, new PopStateEvent("popstate"));
    expect(screen.getByRole("heading", { level: 1, name: "Investment not found" })).toBeInTheDocument();
  } finally {
    primaryOrdersFixture.orders = originalOrders;
  }
});

test("resale market shows the offers table and explains how resale works", () => {
  renderApp();
  loginDemo();
  clickNav("Resale market");

  expect(screen.getByRole("heading", { level: 1, name: "Resale market" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Available" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "My listings" })).toHaveAttribute("aria-pressed", "false");

  // Design table columns with buyer-safe loan context.
  const table = screen.getByRole("table");
  for (const header of ["Investment", "Outstanding principal", "Total price", "Projected annual return", "Remaining term"]) {
    expect(within(table).getByRole("columnheader", { name: new RegExp(`^${header}`) })).toBeInTheDocument();
  }
  expect(within(table).getByText("2,0% discount")).toBeInTheDocument();
  expect(within(table).getByText("24 months")).toBeInTheDocument();
  // Total price without a buyer fee (owner decision 2026-10-16).
  expect(within(table).getByText("CHF 5.147,00")).toBeInTheDocument();
  expect(within(table).getAllByRole("button", { name: /^View offer / }).length).toBeGreaterThan(0);

  // "How resale works" (U33-DEC-06/07): a premium of up to 2%, the capped 2% fee, and a listing is not a sale.
  fireEvent.click(screen.getByRole("button", { name: "How resale works" }));
  const help = screen.getByRole("dialog", { name: "How resale works" });
  expect(within(help).getByText("New listings can have a premium of up to 2%.")).toBeInTheDocument();
  expect(within(help).getByText(/^The seller pays 2% of the selling price, capped at 2% of the remaining investment value\./)).toBeInTheDocument();
  const example = within(help).getByRole("slider", { name: "Discount or premium" });
  expect(example).toHaveAttribute("max", "2");
  fireEvent.change(example, { target: { value: "2" } });
  expect(within(help).getByText("2% premium", { selector: "strong" })).toBeInTheDocument();
  expect(within(help).getByText("The premium increases the price by EUR 20.")).toBeInTheDocument();
  expect(within(help).getByText("Accrued interest is excluded from the fee. Buyers pay no fee.")).toBeInTheDocument();
  expect(within(help).getByText("A listing is not a completed sale. A buyer must purchase the investment.")).toBeInTheDocument();
});

test("My investments shows the summary, current investments, insights and the payment schedule", () => {
  renderApp();
  loginDemo();
  clickNav("My investments");

  expect(screen.getByRole("heading", { level: 1, name: "My investments" })).toBeInTheDocument();
  expect(screen.getByText(/^\d+ investments in \d+ companies\.$/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Interest received" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Interest to be received" })).toBeInTheDocument();
  // EUR and CHF stay separate; the switch narrows the page to one currency.
  expect(within(screen.getByRole("main")).getByRole("group", { name: "Currency" })).toBeInTheDocument();
  // The activity list moved to Transactions; orders are under In funding (no tabs).
  expect(screen.queryByRole("tab", { name: "Activity" })).not.toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Orders" })).not.toBeInTheDocument();

  const current = screen.getByRole("region", { name: /Current investments/ });
  for (const header of ["Status", "Investment", "Outstanding principal", "Interest received", "Next payment"]) {
    expect(within(current).getByRole("columnheader", { name: header })).toBeInTheDocument();
  }
  expect(within(current).getByText(/^Late payment · \d+ days$/)).toBeInTheDocument();
  expect(within(current).getAllByText("Recovery in progress").length).toBeGreaterThan(0);
  expect(within(current).getByText("Listed for sale")).toBeInTheDocument();
  // Banxum follows up on late payments; nothing is asked of the investor.
  expect(screen.getByRole("heading", { name: "Payment updates" })).toBeInTheDocument();
  expect(screen.getByText("Banxum follows up on overdue payments. No action is needed from you.")).toBeInTheDocument();

  // The status filter narrows the table to late investments.
  fireEvent.change(within(current).getByRole("combobox", { name: "Investment status" }), { target: { value: "late" } });
  expect(within(current).getAllByRole("row").slice(1).every((row) => /Late payment/.test(row.textContent ?? ""))).toBe(true);
  fireEvent.change(within(current).getByRole("combobox", { name: "Investment status" }), { target: { value: "current" } });

  expect(screen.getByText("Portfolio insights")).toBeInTheDocument();

  // The payment schedule groups late payments apart from the projected ones.
  fireEvent.click(screen.getByRole("link", { name: /Payment schedule/ }));
  expect(screen.getByRole("heading", { level: 1, name: "Payment schedule" })).toBeInTheDocument();
  expect(screen.getAllByText("Late payments").length).toBeGreaterThan(0);
  fireEvent.click(within(screen.getByRole("main")).getByRole("link", { name: "My investments" }));
  expect(screen.getByRole("heading", { level: 1, name: "My investments" })).toBeInTheDocument();

  // Repaid and sold investments are under the history.
  fireEvent.click(screen.getByRole("link", { name: /View history/ }));
  expect(screen.getByRole("heading", { level: 1, name: "Investment history" })).toBeInTheDocument();
  const history = screen.getByRole("region", { name: "Completed investments" });
  expect(within(history).getByText("Lombardia trade receivables")).toBeInTheDocument();
  expect(within(history).getByText("Lugano logistics hub")).toBeInTheDocument();
});

test("My investments and Transactions show their empty states without holdings, orders or activity", () => {
  const originalActivity = activityFixture.entries;
  const originalHoldings = portfolioFixture.holdings;
  const originalOrders = primaryOrdersFixture.orders;
  activityFixture.entries = [];
  portfolioFixture.holdings = [];
  primaryOrdersFixture.orders = [];

  try {
    renderApp();
    loginDemo();
    clickNav("My investments");
    expect(screen.getByText("No investments yet")).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("link", { name: "Investment opportunities" })).toBeInTheDocument();
    expect(screen.queryByText("Portfolio insights")).not.toBeInTheDocument();

    clickNav("Transactions");
    expect(screen.getByText("No transactions yet. Deposits, investments and repayments will appear here.")).toBeInTheDocument();
  } finally {
    activityFixture.entries = originalActivity;
    portfolioFixture.holdings = originalHoldings;
    primaryOrdersFixture.orders = originalOrders;
  }
});

test("a menu click leaves a sub-view kept in the query string (My investments history)", () => {
  renderApp();
  loginDemo();
  clickNav("My investments");
  fireEvent.click(screen.getByRole("link", { name: "View history" }));
  expect(window.location.search).toBe("?view=history");
  expect(screen.getByRole("heading", { level: 1, name: "Investment history" })).toBeInTheDocument();

  // The menu entry of the same page returns to My investments and clears the sub-view.
  clickNav("My investments");
  expect(window.location.pathname).toBe("/portfolio");
  expect(window.location.search).toBe("");
  expect(screen.getByRole("heading", { level: 1, name: "My investments" })).toBeInTheDocument();
});

// A holding opens as its own page (/portfolio/:holdingId), the design's investment page.
function openHoldingPage(loanTitle: string) {
  fireEvent.click(screen.getByRole("link", { name: `Open ${loanTitle}` }));
  expect(screen.getByRole("heading", { level: 1, name: loanTitle })).toBeInTheDocument();
  return screen.getByRole("main");
}

test("holding details open on the investment page with factual projections and collateral", () => {
  renderApp();
  loginDemo();
  clickNav("My investments");

  const page = openHoldingPage("Engadin Alpine refinancing");
  expect(window.location.pathname).toBe("/portfolio/H-2310");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(within(page).getByText("Engadin Hospitality AG")).toBeInTheDocument();
  const summary = within(page).getByRole("region", { name: "Investment summary" });
  for (const label of ["Outstanding principal", "Interest received", "Annual interest rate", "Maturity"]) {
    expect(within(summary).getByText(label)).toBeInTheDocument();
  }
  expect(within(page).getByText("Interest to be received")).toBeInTheDocument();
  expect(within(page).getAllByText("Projected").length).toBeGreaterThan(0);
  // Repayments go to the Banxum balance (U33-DEC-02).
  expect(within(page).getByText("Credited to your Banxum balance")).toBeInTheDocument();

  // The schedule shows the investor's share of every remaining payment; received payments are one total row.
  fireEvent.click(within(page).getAllByRole("button", { name: /View payment schedule/ })[0]);
  const schedule = within(page).getByRole("region", { name: "All payments for this investment, CHF" });
  expect(within(schedule).getByRole("columnheader", { name: "Due date" })).toBeInTheDocument();
  expect(within(schedule).getByText("Received to date")).toBeInTheDocument();
  expect(within(schedule).getAllByText("Outstanding principal after this payment").length).toBeGreaterThan(0);

  // Security: LTV uses the principal still owed on the whole loan (audit A-65), not the original amount lent.
  expect(within(page).getByText("Registered real-estate security supporting the borrower obligation.")).toBeInTheDocument();
  const engadin = portfolioFixture.holdings.find((holding) => holding.id === "H-2310")!.loan;
  const owedMinor = engadin.schedule.reduce((sum, row) => sum + row.outstanding_principal_minor, 0);
  const ratio = formatRateBps(Math.round((owedMinor * 10_000) / engadin.collateral_value_minor), "european");
  fireEvent.click(within(page).getByRole("button", { name: `Loan-to-value ${ratio}. Show comparison` }));
  const ltv = within(page).getByRole("group", { name: /^Loan amount CHF / });
  expect(ltv.getAttribute("aria-label")).toContain(`Loan amount CHF ${formatMoneyMinor(owedMinor, "CHF", 0, "european")}.`);

  // The back link returns to the list.
  fireEvent.click(within(page).getByRole("link", { name: "My investments" }));
  expect(window.location.pathname).toBe("/portfolio");
  expect(screen.getByRole("heading", { level: 1, name: "My investments" })).toBeInTheDocument();
});

test("an unknown holding link shows a not-found investment page", () => {
  renderApp("/portfolio/H-UNKNOWN");

  expect(screen.getByRole("heading", { level: 1, name: "Investment not found" })).toBeInTheDocument();
  expect(screen.getByText("We could not find this investment")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: "Back to My investments" }));
  expect(window.location.pathname).toBe("/portfolio");
});

test("the investment page shows every public loan update with its full message, newest first", async () => {
  const holding = portfolioFixture.holdings.find((item) => item.id === "H-2201") as (typeof portfolioFixture.holdings)[number];
  const saved = { stages: holding.recovery_stages, next: holding.recovery_next_step };
  // Without recorded stages (U33-DEC-22) the public notes are the stages, as before.
  holding.recovery_stages = [];
  holding.recovery_next_step = null;
  try {
    renderApp("/portfolio/H-2201#loan-notes");

    const heading = await screen.findByRole("heading", { name: "Recovery in progress" });
    const updates = heading.closest("#loan-notes") as HTMLElement;
    expect(within(updates).getByText("Latest update").nextElementSibling).toHaveTextContent("Recovery process update");
    expect(within(updates).getByText(/Garanta has instructed external recovery counsel/)).toBeInTheDocument();
    expect(within(updates).getByRole("heading", { level: 6, name: "Formal demand issued" })).toBeInTheDocument();
    expect(within(updates).getByText(/Garanta has issued a formal payment demand/)).toBeInTheDocument();
    expect(window.location.hash).toBe("#loan-notes");
  } finally {
    holding.recovery_stages = saved.stages;
    holding.recovery_next_step = saved.next;
  }
});

test("a late payment shows the missed payment, the recorded stages and the known next step (U33-DEC-22)", async () => {
  renderApp("/portfolio/H-2256");

  const heading = await screen.findByRole("heading", { name: "Payment update" });
  const card = heading.closest(".rc-payment-update") as HTMLElement;
  const steps = card.querySelector(".rc-payment-body .rc-steps") as HTMLElement;
  expect(Array.from(steps.querySelectorAll("strong")).map((node) => node.textContent)).toEqual(["Payment missed", "Reminder sent", "Next step · Formal notice"]);
  expect(steps.querySelectorAll(".rc-step-dot.next")).toHaveLength(1);
  expect(steps).toHaveTextContent("Planned if the payment has not arrived by then.");
});

test("recorded recovery stages give the current stage and the known next milestone, with every note kept (U33-DEC-22)", async () => {
  renderApp("/portfolio/H-2201#loan-notes");

  const heading = await screen.findByRole("heading", { name: "Recovery in progress" });
  const updates = heading.closest("#loan-notes") as HTMLElement;
  expect(within(updates).getByText("Current stage").nextElementSibling).toHaveTextContent("Enforcement of the security");
  expect(within(updates).getByText(/Banxum is collecting the assigned receivables for all investors\./, { selector: "section p" })).toBeInTheDocument();
  const next = within(updates).getByText("Next milestone");
  expect(next.nextElementSibling).toHaveTextContent("Collection from the debtors");
  // No date is shown when the team does not know it.
  expect(next.parentElement?.querySelector("time")).toBeNull();
  expect(within(updates).queryByText("Latest update")).not.toBeInTheDocument();
  expect(within(updates).getByRole("heading", { level: 6, name: "Formal notice" })).toBeInTheDocument();
  expect(within(updates).getByRole("heading", { level: 6, name: "Recovery process update" })).toBeInTheDocument();
  expect(within(updates).getByRole("heading", { level: 6, name: "Formal demand issued" })).toBeInTheDocument();
});

test("originator claim holdings disclose the retained claim without implying protection", () => {
  renderApp();
  loginDemo();
  clickNav("My investments");

  const page = openHoldingPage("Nord Trans Cargo working capital");
  expect(
    within(page).getByText(/Nord Capital Finance keeps at least 15,0% of the loan's outstanding principal/)
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
    loginDemo();
    clickNav("My investments");

    const page = openHoldingPage("Engadin Alpine refinancing");
    expect(within(page).getByText(/18 days since the first unpaid payment/)).toBeInTheDocument();
    expect(within(page).getByText(/default interest of 12,0% a year/)).toBeInTheDocument();
    expect(within(page).getByText(/does not estimate default interest from the days overdue/)).toBeInTheDocument();
    expect(within(page).queryByText(/a day at today/i)).not.toBeInTheDocument();
  } finally {
    holding.loan.loan_status = originalStatus;
    holding.loan.days_past_due = originalDaysPastDue;
  }
});

test("funded holdings explain that selling starts after the payout to the borrower", () => {
  const holding = portfolioFixture.holdings[0];
  const originalStatus = holding.loan.loan_status;
  const originalListing = holding.open_secondary_listing;
  holding.loan.loan_status = "funded";
  holding.open_secondary_listing = null;
  try {
    renderApp();
    loginDemo();
    clickNav("My investments");

    const page = openHoldingPage("Engadin Alpine refinancing");
    expect(within(page).getByText("Funded", { selector: ".r71-status" })).toBeInTheDocument();
    expect(
      within(page).getByText("You can sell this investment on the resale market after the loan is paid out to the borrower.")
    ).toBeInTheDocument();
    expect(within(page).queryByRole("button", { name: "Sell investment" })).not.toBeInTheDocument();
  } finally {
    holding.loan.loan_status = originalStatus;
    holding.open_secondary_listing = originalListing;
  }
});

test("Sell investment separates the price from the review with the email code", () => {
  const holding = portfolioFixture.holdings[0];
  const originalListing = holding.open_secondary_listing;
  holding.open_secondary_listing = null;
  try {
    renderApp();
    loginDemo();
    clickNav("My investments");

    const page = openHoldingPage("Engadin Alpine refinancing");
    fireEvent.click(within(page).getByRole("button", { name: "Sell investment" }));

    const dialog = screen.getByRole("dialog", { name: "Sell investment" });
    expect(within(dialog).getByText("Up to 2% premium")).toBeInTheDocument();
    expect(within(dialog).getByText("You receive if sold")).toBeInTheDocument();
    expect(within(dialog).queryByRole("textbox", { name: "Email confirmation code" })).not.toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Review listing" }));

    const review = screen.getByRole("dialog", { name: "Confirm listing" });
    expect(within(review).getByRole("checkbox", { name: /seller listing terms/ })).not.toBeChecked();
    expect(within(review).getByRole("textbox", { name: "Email confirmation code" })).toBeInTheDocument();
    expect(within(review).getByRole("button", { name: "Send email code" })).toBeEnabled();
    expect(within(review).getByRole("button", { name: "Confirm listing" })).toBeDisabled();
  } finally {
    holding.open_secondary_listing = originalListing;
  }
});

test("listed holdings expose edit and cancel controls, and My listings shows completed sales", () => {
  renderApp();
  loginDemo();
  clickNav("My investments");

  const page = openHoldingPage("Engadin Alpine refinancing");
  expect(within(page).getByText(/^Listed on the resale market at CHF 8\.420,50\./)).toBeInTheDocument();
  expect(within(page).queryByRole("button", { name: "Sell investment" })).not.toBeInTheDocument();

  fireEvent.click(within(page).getByRole("button", { name: "Edit listing" }));
  const editDialog = screen.getByRole("dialog", { name: "Edit listing" });
  expect(within(editDialog).getByText("No discount or premium", { selector: ".s106-adjustment" })).toBeInTheDocument();
  expect(within(editDialog).queryByRole("textbox", { name: "Email confirmation code" })).not.toBeInTheDocument();
  fireEvent.click(within(editDialog).getByRole("button", { name: "Review listing" }));
  const review = screen.getByRole("dialog", { name: "Confirm new price" });
  expect(within(review).getByRole("button", { name: "Confirm new price" })).toBeDisabled();
  fireEvent.click(within(review).getByRole("button", { name: "Back" }));
  fireEvent.click(within(screen.getByRole("dialog", { name: "Edit listing" })).getByRole("button", { name: "Cancel" }));

  fireEvent.click(within(page).getByRole("button", { name: "Cancel listing" }));
  const cancelDialog = screen.getByRole("dialog", { name: "Cancel listing" });
  expect(within(cancelDialog).getByText(/The investment is not sold and stays in your portfolio/)).toBeInTheDocument();
  fireEvent.click(within(cancelDialog).getByRole("button", { name: "Keep listing" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  clickNav("Resale market");
  fireEvent.click(screen.getByRole("button", { name: "My listings" }));
  const ownRow = screen.getByText("Engadin Alpine refinancing").closest("tr") as HTMLElement;
  expect(within(ownRow).getByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(within(ownRow).getByRole("button", { name: "Cancel listing" })).toBeInTheDocument();
  const completed = screen.getByRole("region", { name: "Completed sales and purchases" });
  expect(within(completed).getAllByText("Sale").length).toBeGreaterThan(0);
  expect(within(completed).getAllByText("Purchase").length).toBeGreaterThan(0);
  expect(within(completed).queryByText(/Listing updated|Listing cancelled/)).not.toBeInTheDocument();
});

test("secondary purchase review shows the remaining payments and waits for a manual code request", () => {
  renderApp();
  loginDemo();
  clickNav("Resale market");
  fireEvent.click(screen.getByRole("button", { name: "View offer Loan A - Manufacturing - CH" }));

  expect(screen.getByRole("heading", { level: 1, name: "Loan A - Manufacturing - CH" })).toBeInTheDocument();
  expect(screen.getByText("Annual interest rate")).toBeInTheDocument();
  expect(screen.getByText("Remaining term")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Remaining repayments" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Buy for / }));

  const dialog = screen.getByRole("dialog", { name: "Confirm purchase" });
  for (const label of ["Outstanding principal", "Purchase price", "Accrued interest"]) {
    expect(within(dialog).getByText(label)).toBeInTheDocument();
  }
  expect(within(dialog).getByRole("button", { name: "Send email code" })).toBeEnabled();
  expect(within(dialog).queryByText(/Code sent\. Send new in/)).not.toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Confirm purchase" })).toBeDisabled();
});

test("a frozen investor can inspect a resale offer but cannot buy it", () => {
  renderApp();
  loginDemo();
  setUxState("frozen");
  clickNav("Resale market");
  fireEvent.click(screen.getByRole("button", { name: "View offer Loan A - Manufacturing - CH" }));

  expect(screen.getByRole("heading", { level: 1, name: "Loan A - Manufacturing - CH" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Remaining repayments" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Buy for / })).toBeDisabled();
  expect(screen.getByText(/You can still review every offer\./)).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
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

  // The design's public home has no sign-up band: Log in, then "Create an account".
  fireEvent.click(screen.getAllByRole("link", { name: /^Log in/ })[0]);
  fireEvent.click(screen.getByRole("link", { name: "Create an account" }));
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

test("deposit instructions explain how to use the required payment reference", async () => {
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
  // The design's line; U33-DEC-05: unclear deposits checked by hand; U33-DEC-34: the operator named.
  expect(within(dialog).getByText("Transfer from your verified bank account.")).toBeInTheDocument();
  expect(within(dialog).getByText(/checked by hand before they become available/)).toBeInTheDocument();
  expect(within(dialog).queryByText(/other accounts are returned/i)).not.toBeInTheDocument();
  expect(within(dialog).getByText("Banxum is a brand of Garanta Finanzgruppe AG.")).toBeInTheDocument();
  // CHF has the design's QR-bill download; there are no simulated deposits.
  expect(await within(dialog).findByRole("link", { name: "Download QR-bill" })).toBeInTheDocument();
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
  // U33-DEC-25: signed-in devices with this device first, and the sign-in history.
  expect(screen.getByText("This device")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out on all other devices" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(screen.getByText("Safari on iPhone is signed out.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Sign out on all other devices" })).not.toBeInTheDocument();
  expect(within(screen.getByRole("table")).getByRole("columnheader", { name: "Device and place" })).toBeInTheDocument();

  fireEvent.click(within(tabs).getByRole("link", { name: "Bank accounts" }));
  expect(window.location.pathname).toBe("/settings/bank-accounts");
  expect(screen.getByText("CH93 0076 2011 6238 5295 7")).toBeInTheDocument();
  expect(screen.getByText(/^Verified · /)).toBeInTheDocument();
  // No 48-hour pause (U33-DEC-05) and repayments go to the Banxum balance (U33-DEC-02).
  expect(screen.queryByText(/48 hours/)).not.toBeInTheDocument();
  expect(screen.getByText(/Repayments are credited to your Banxum balance/)).toBeInTheDocument();
  // One default return account per currency (U33-DEC-05); "Change" adds a new account in it.
  expect(screen.getByText("Money that goes back to your bank in CHF is sent to this account.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Use for returns" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Change" }));
  expect(screen.getByRole("dialog", { name: "New CHF bank account" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Add a bank account" }));
  expect(screen.getByRole("dialog", { name: "Add a bank account" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  fireEvent.click(within(tabs).getByRole("link", { name: "Notifications" }));
  expect(screen.getByRole("checkbox", { name: "News from Banxum" })).not.toBeChecked();
  expect(screen.getAllByText("Always on").length).toBeGreaterThan(0);
  // U33-DEC-30: Smart Invest has its own in-app / email channels.
  expect(screen.getByText("Investment opportunities matching your preferences")).toBeInTheDocument();
  expect(screen.getByText(/In-app notifications on · Email notifications on/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Manage" }));
  expect(screen.getByRole("dialog", { name: "Notify me about matching investment opportunities" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));

  fireEvent.click(within(tabs).getByRole("link", { name: "Preferences" }));
  fireEvent.click(screen.getByRole("button", { name: "Dark" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  fireEvent.click(screen.getByRole("button", { name: /^Swiss/ }));
  expect(screen.getByRole("button", { name: /^Swiss/ })).toHaveAttribute("aria-pressed", "true");
  // Multilanguage is paused (IMPLEMENTATION_PLAN 18.0): no language choice in Preferences.
  expect(screen.queryByRole("combobox", { name: "Language" })).not.toBeInTheDocument();
  // Closing is a request to support, not an instant closure (U33-DEC-28).
  fireEvent.click(screen.getByRole("button", { name: "Close account" }));
  const closure = screen.getByRole("dialog", { name: "Request account closure" });
  expect(within(closure).getByText("Receiving your request does not close the account yet.")).toBeInTheDocument();
  fireEvent.click(within(closure).getByRole("button", { name: "Send closure request" }));
  expect(within(closure).getByRole("heading", { name: "Request received" })).toBeInTheDocument();
  expect(within(closure).getByText("Demo: nothing was sent.")).toBeInTheDocument();
  fireEvent.click(within(closure).getByRole("button", { name: "Done" }));

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

test("the Help page searches its questions and sends a message to support", () => {
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
  expect(screen.getByText("How do I change my bank account?").closest("details")).not.toHaveAttribute("hidden");
  expect(screen.getByText("How much can I invest?").closest("details")).toHaveAttribute("hidden");

  // Contact support sends the message by email to the team (U33-DEC-35); the preview sends nothing.
  fireEvent.click(within(screen.getByRole("complementary")).getByRole("button", { name: /^Contact support/ }));
  const dialog = screen.getByRole("dialog", { name: "Contact support" });
  const send = within(dialog).getByRole("button", { name: "Send message" });
  expect(send).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("Message"), { target: { value: "Question about my statement" } });
  expect(send).toBeEnabled();
  fireEvent.click(send);
  expect(within(dialog).getByRole("heading", { name: "Message sent" })).toBeInTheDocument();
  expect(within(dialog).getByText("Demo: nothing was sent.")).toBeInTheDocument();
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

test("Smart-Invest matches show readable security and investment-type labels, never API tokens", () => {
  const match = smartInvestFixture.matches[0];
  const previous = { collateral_type: match.collateral_type, product_type: match.product_type, purpose: match.purpose };
  match.collateral_type = "corporate_guarantee";
  match.product_type = "originator_claim";
  match.purpose = "bridge_financing";
  try {
    renderApp();
    loginDemo();
    clickNav("Smart Invest");

    const card = screen.getByRole("button", { name: `Review investment in ${match.title}` }).closest(".r35-card") as HTMLElement;
    expect(within(card).getByText("Company guarantee")).toBeInTheDocument();
    expect(within(card).queryByText(/corporate_guarantee|originator_claim|bridge_financing/)).not.toBeInTheDocument();
    expect(card.textContent).not.toMatch(/\b[a-z]+_[a-z_]+\b/);
  } finally {
    Object.assign(match, previous);
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
  clickNav("Transactions");

  const table = screen.getByRole("table");
  const cancelledRow = within(table).getByText("Cancelled").closest("tr") as HTMLElement;
  expect(within(cancelledRow).getByText("Withdrawal")).toBeInTheDocument();
  const sentRow = within(table).getByText("Sent").closest("tr") as HTMLElement;
  expect(within(sentRow).getByText("Withdrawal")).toBeInTheDocument();
  // The cancellation credits the amount back to the balance.
  const reversalRow = within(table).getByText("Returned to your balance").closest("tr") as HTMLElement;
  expect(within(reversalRow).getByText("Withdrawal cancelled")).toBeInTheDocument();
  expect(within(reversalRow).getByText(/\+ CHF 2\.000,00|\+ EUR 2\.000,00/)).toBeInTheDocument();
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
    // with a note that it is already deducted (penalties charged before U33-DEC-04 removed them stay in the history).
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
  expect(within(dialog).getByText("Usually 1–3 business days · No Banxum fees")).toBeInTheDocument();
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
    clickNav("Transactions");

    // Penalty mode exists until U33-DEC-04: the charge is a fee row with its reason.
    const penaltyRow = screen.getByText("Balance past the 60-day limit").closest("tr") as HTMLElement;
    expect(within(penaltyRow).getByText("Penalty")).toBeInTheDocument();
    expect(within(penaltyRow).getByText("− CHF 50,00")).toBeInTheDocument();
    // A forced withdrawal is shown as the automatic return, not as an investor withdrawal.
    const forcedRow = screen.getByText("Automatic return").closest("tr") as HTMLElement;
    expect(within(forcedRow).getByText("Pending")).toBeInTheDocument();
    expect(within(forcedRow).getByText(/^To CH93/)).toBeInTheDocument();
  } finally {
    activityFixture.entries.splice(activityFixture.entries.length - added.length, added.length);
  }
});
