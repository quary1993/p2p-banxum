// IP of Webby-Soft SRL.
// Public site (preview data): Help search and topics, guides, legal routing including the
// backend template addresses, the newsletter link pages and the 404.
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test } from "vitest";

import { App } from "../../App";

function renderSite(path: string) {
  window.history.pushState({}, "", path);
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>
  );
}

function group(title: string) {
  // hidden: true finds the topics the search hides too.
  return screen.getByRole("heading", { level: 2, name: title, hidden: true }).closest("[data-faq-group]") as HTMLElement;
}

function question(text: string) {
  return screen.getByText(text).closest("details") as HTMLDetailsElement;
}

test("help search filters the questions, opens the matches and says when nothing matches", () => {
  renderSite("/help");
  const search = screen.getByRole("searchbox", { name: "Search the questions" });
  expect(question("Is Banxum regulated?")).not.toHaveAttribute("open");
  expect(screen.getByText(/No question matches/)).not.toBeVisible();

  fireEvent.change(search, { target: { value: "taxed" } });
  // Only "How is interest taxed?" says "taxed": its topic stays, every other topic is hidden.
  expect(question("How is interest taxed?")).not.toHaveAttribute("hidden");
  expect(question("How is interest taxed?")).toHaveAttribute("open");
  expect(question("Which documents do I receive?")).toHaveAttribute("hidden");
  expect(group("Tax and documents")).not.toHaveAttribute("hidden");
  expect(group("Getting started")).toHaveAttribute("hidden");
  expect(group("Risks and defaults")).toHaveAttribute("hidden");

  // The answer text counts too ("segregated" is only in an answer).
  fireEvent.change(search, { target: { value: "SEGREGATED" } });
  expect(question("What is my Banxum wallet?")).not.toHaveAttribute("hidden");
  expect(group("Money and payments")).not.toHaveAttribute("hidden");
  expect(group("Tax and documents")).toHaveAttribute("hidden");

  fireEvent.change(search, { target: { value: "zzzzqqq" } });
  expect(screen.getByText(/No question matches/)).toBeVisible();
  expect(within(screen.getByText(/No question matches/)).getByRole("link", { name: "ask us" })).toHaveAttribute("href", "/contact");

  // Clearing shows everything again; a question opened by a search stays open (as the design).
  fireEvent.change(search, { target: { value: "" } });
  expect(group("Getting started")).not.toHaveAttribute("hidden");
  expect(screen.getByText(/No question matches/)).not.toBeVisible();
  expect(question("How is interest taxed?")).toHaveAttribute("open");
  expect(question("Who can invest?")).not.toHaveAttribute("open");
});

test("help ?q= searches on arrival and ?topic= marks and scrolls to the topic", () => {
  const first = renderSite("/help?q=minimum");
  expect(screen.getByRole("searchbox", { name: "Search the questions" })).toHaveValue("minimum");
  expect(question("How much do I need to start?")).toHaveAttribute("open");
  expect(group("Money and payments")).toHaveAttribute("hidden");
  first.unmount();

  const scrolled: Element[] = [];
  const original = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function (this: Element) {
    scrolled.push(this);
  };
  try {
    renderSite("/help?topic=risks");
    // U33 (Q24, D-10): the topics are the legal layout's "On this page" index; ?topic= marks the
    // topic and scrolls to it, a click scrolls to the topic in the page.
    const topics = screen.getByRole("navigation", { name: "Topics" });
    expect(within(topics).getByRole("link", { name: /Risks and defaults/ })).toHaveAttribute("aria-current", "location");
    expect(within(topics).getByRole("link", { name: /Investing/ })).not.toHaveAttribute("aria-current");
    expect(within(topics).getByRole("link", { name: /How it works/ })).toHaveAttribute("href", "/help#how-it-works");
    expect(scrolled).toContain(document.querySelector('[data-faq-group="risks"]'));

    fireEvent.click(within(topics).getByRole("link", { name: /Selling early/ }));
    expect(scrolled).toContain(document.querySelector('[data-faq-group="selling"]'));
    expect(window.location.pathname + window.location.search).toBe("/help?topic=risks");
  } finally {
    Element.prototype.scrollIntoView = original;
  }

  // No phone number or support hours (U33-DEC-35); the email and the contact form.
  const contact = screen.getByRole("heading", { name: "Write to us." }).closest("section") as HTMLElement;
  expect(contact).toHaveTextContent("support@banxum.com");
  expect(contact).not.toHaveTextContent("+41");
  expect(contact).not.toHaveTextContent("Monday");
  expect(within(contact).getByRole("link", { name: "Contact form" })).toHaveAttribute("href", "/contact");
});

test("help: How it works follows the current rules (Q24, D-1, D-12, U33-DEC-06/07)", () => {
  renderSite("/help");
  const how = document.getElementById("how-it-works") as HTMLElement;
  expect(how).toHaveTextContent("confirm with the code we email you and your PIN (or your authenticator code)");
  expect(how).toHaveTextContent("from 0% to 102% of the outstanding principal");
  expect(how).not.toHaveTextContent(/qualified electronic signature/);
  const answers = document.querySelector(".bxp-help-document") as HTMLElement;
  expect(answers).not.toHaveTextContent(/magic link/);
  expect(answers).not.toHaveTextContent(/never above/);
  expect(answers).toHaveTextContent("From day 60 Banxum can declare the loan in default");
});

test("guides list every guide and article, an article links to the others", () => {
  const list = renderSite("/guides");
  const rows = document.querySelectorAll(".bxp-guide-row");
  // Q24.2: "Our first year in figures" is removed from the launch version.
  expect(rows).toHaveLength(4);
  expect(screen.queryByRole("link", { name: /Our first year in figures/ })).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "New projects and guides by email" })).toBeInTheDocument();
  expect(screen.getByLabelText("Email address")).toHaveAttribute("id", "bxp-subscribe-guides");
  list.unmount();

  const firstYear = renderSite("/guides/first-year");
  expect(screen.getByRole("heading", { level: 1, name: "This page does not exist" })).toBeInTheDocument();
  firstYear.unmount();

  renderSite("/guides/late-payments");
  expect(screen.getByRole("heading", { level: 1, name: "What happens when a borrower pays late" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See open projects" })).toHaveAttribute("href", "/projects");
  expect(screen.getByRole("link", { name: "Open account" })).toHaveAttribute("href", "/register");
  const others = screen.getByRole("list", { name: "Other guides" });
  expect(within(others).getAllByRole("link")).toHaveLength(3);
  expect(screen.getByRole("heading", { level: 2, name: "From day 60" }).parentElement).toHaveTextContent("Banxum can declare the loan in default");
});

test("an unknown guide or legal page shows the 404", () => {
  const guide = renderSite("/guides/nothing");
  expect(screen.getByRole("heading", { level: 1, name: "This page does not exist" })).toBeInTheDocument();
  guide.unmount();
  renderSite("/legal/nothing");
  expect(screen.getByRole("heading", { level: 1, name: "This page does not exist" })).toBeInTheDocument();
  expect(document.title).toBe("Not found · Banxum");
});

test("legal pages: the real documents in the U33 layout and the backend template addresses", () => {
  const others = () => within(screen.getByRole("list", { name: "Legal pages" }));
  const contents = () => within(screen.getByRole("navigation", { name: /contents$/ }));

  const risk = renderSite("/legal/risk");
  // The design's risk hero; the text is the real risk information (content.ts), not the design's.
  expect(screen.getByRole("heading", { level: 1, name: /Understand the risks/ })).toBeInTheDocument();
  expect(document.title).toBe("Risk information · Banxum");
  expect(others().queryByRole("link", { name: "Risk information" })).not.toBeInTheDocument();
  expect(screen.getByText("Version 1.0")).toBeInTheDocument();
  expect(screen.getByText("Valid from 1 Sep 2026")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "No deposit protection" })).toBeInTheDocument();
  expect(contents().getByRole("link", { name: "07 No deposit protection" })).toHaveAttribute("href", "#risk-section-7");
  expect(screen.queryByRole("heading", { name: "The borrower" })).not.toBeInTheDocument();
  risk.unmount();

  // 18.12: the privacy notice is the full text drafted from the real application.
  const privacy = renderSite("/legal/privacy");
  expect(screen.getByRole("heading", { level: 1, name: "Privacy policy" })).toBeInTheDocument();
  expect(screen.queryByText("Outline. The full text follows from the lawyers.")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Transfers abroad" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "DB-IP" })).toHaveAttribute("href", "https://db-ip.com");
  privacy.unmount();

  const imprint = renderSite("/legal/imprint");
  expect(document.title).toBe("Imprint · Banxum");
  expect(screen.queryByText(/^Version/)).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Bank" })).toBeInTheDocument();
  expect(screen.getByText("UBS Switzerland AG")).toBeInTheDocument();
  expect(screen.getByText("CH83 0020 6206 9567 6601 M")).toBeInTheDocument();
  // Owner decision 2026-10-15: the closing paragraph stays exactly as before.
  expect(screen.getByText(/The sample figures of this prototype are invented\.$/)).toBeInTheDocument();
  // U33-DEC-34: the operator identification in the footer.
  expect(within(screen.getByRole("contentinfo")).getByText(/^Banxum is a brand of Garanta Finanzgruppe AG/)).toBeInTheDocument();
  imprint.unmount();

  // The investor flows' addresses: registration is the terms page, risk-disclosure the risk page.
  const registration = renderSite("/legal/registration");
  expect(screen.getByRole("heading", { level: 1, name: "Terms & conditions" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Scope and parties" })).toBeInTheDocument();
  registration.unmount();

  const riskDisclosure = renderSite("/legal/risk-disclosure");
  expect(screen.getByRole("heading", { level: 1, name: /Understand the risks/ })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Credit risk" })).toBeInTheDocument();
  riskDisclosure.unmount();

  // The other templates: their own title (preview mode does not load them).
  for (const [path, title] of [
    ["/legal/primary-market-investment", "Investment terms and loan claim assignment"],
    ["/legal/secondary-market-listing", "Secondary-market seller/listing terms"],
    ["/legal/secondary_market_purchase", "Secondary-market buyer terms"]
  ]) {
    const view = renderSite(path);
    expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
    expect(document.title).toBe(`${title} · Banxum`);
    expect(screen.getByText(/Preview mode: the text of this document loads from the published server template\./)).toBeInTheDocument();
    view.unmount();
  }

  // "Other documents" stays in the site.
  renderSite("/legal/terms");
  fireEvent.click(others().getByRole("link", { name: "Complaints" }));
  expect(window.location.pathname).toBe("/legal/complaints");
  expect(screen.getByRole("heading", { level: 1, name: "Complaints" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "How to complain" })).toBeInTheDocument();
});

test("newsletter links: confirm, unsubscribe and a link without a token", async () => {
  const confirm = renderSite("/newsletter/confirm?token=abc");
  expect(document.title).toBe("New projects by email · Banxum");
  expect(screen.getByText("Confirming your subscription…")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Your subscription is confirmed." })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: "See open projects" }));
  expect(window.location.pathname).toBe("/projects");
  confirm.unmount();

  const unsubscribe = renderSite("/newsletter/unsubscribe?token=abc");
  expect(screen.getByText("Unsubscribing…")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "You are unsubscribed." })).toBeInTheDocument();
  expect(screen.getByText("You will not get new projects by email any more.")).toBeInTheDocument();
  unsubscribe.unmount();

  renderSite("/newsletter/confirm");
  expect(screen.getByRole("heading", { name: "This link is not valid or has expired." })).toBeInTheDocument();
  await act(async () => {
    fireEvent.click(screen.getByRole("link", { name: "Subscribe again" }));
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(window.location.pathname).toBe("/projects");
  expect(document.activeElement).toBe(screen.getByLabelText("Email address"));
});

test("E-06 (audit S1-5): the kept public pages show no language control", () => {
  for (const path of ["/help", "/projects", "/statistics", "/guides"]) {
    const view = renderSite(path);
    expect(screen.queryByRole("button", { name: /^Language:/ })).not.toBeInTheDocument();
    view.unmount();
  }
});
