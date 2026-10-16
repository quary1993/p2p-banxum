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
  return screen.getByRole("heading", { level: 2, name: title, hidden: true }).parentElement as HTMLElement;
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
    const topics = screen.getByRole("list", { name: "Topics" });
    expect(within(topics).getByRole("link", { name: "Risks and defaults" })).toHaveClass("active");
    expect(within(topics).getByRole("link", { name: "Investing" })).not.toHaveClass("active");
    expect(within(topics).getByRole("link", { name: "For companies" })).toHaveAttribute("href", "/companies");
    expect(scrolled).toContain(document.querySelector('[data-faq-group="risks"]'));

    // A topic link is a new address: the page shows afresh (search emptied) at that topic.
    const search = screen.getByRole("searchbox", { name: "Search the questions" });
    fireEvent.change(search, { target: { value: "tax" } });
    fireEvent.click(within(topics).getByRole("link", { name: "Selling early" }));
    expect(window.location.pathname + window.location.search).toBe("/help?topic=selling");
    expect(screen.getByRole("searchbox", { name: "Search the questions" })).toHaveValue("");
    expect(group("Getting started")).not.toHaveAttribute("hidden");
    expect(within(screen.getByRole("list", { name: "Topics" })).getByRole("link", { name: "Selling early" })).toHaveClass("active");
    expect(scrolled).toContain(document.querySelector('[data-faq-group="selling"]'));
  } finally {
    Element.prototype.scrollIntoView = original;
  }

  expect(screen.getByRole("heading", { name: "Still have a question?" }).parentElement).toHaveTextContent(
    "Write to support@banxum.com or call +41 31 000 00 00 (sample), Monday to Friday, 9:00 to 17:00 (Swiss time)."
  );
});

test("guides list every guide and article, an article links to the others", () => {
  const list = renderSite("/guides");
  const cards = document.querySelectorAll("a.site-article-card");
  expect(cards).toHaveLength(5);
  expect(screen.getByRole("link", { name: /Our first year in figures/ })).toHaveAttribute("href", "/guides/first-year");
  expect(screen.getByRole("heading", { name: "New projects and guides by email" })).toBeInTheDocument();
  expect(screen.getByLabelText("Email address")).toHaveAttribute("id", "site-sub-guides");
  list.unmount();

  renderSite("/guides/first-year");
  expect(screen.getByRole("heading", { level: 1, name: "Our first year in figures" })).toBeInTheDocument();
  expect(document.title).toBe("Our first year in figures · Banxum");
  // Owner decision 2026-10-15: the article is shown exactly as the design, callout included.
  expect(screen.getByText("Sample article of the prototype: the figures are the sample data of the statistics page.")).toBeInTheDocument();
  expect(screen.getByText("15 Jan 2026", { selector: ".site-page-head span" })).toBeInTheDocument();
  const ready = screen.getByRole("heading", { name: "Ready to look at the projects?" }).parentElement as HTMLElement;
  expect(within(ready).getByRole("link", { name: "See open projects" })).toHaveAttribute("href", "/projects");
  expect(within(ready).getByRole("link", { name: "Open account" })).toHaveAttribute("href", "/register");
  const others = screen.getByRole("heading", { name: "Other guides" }).closest("section") as HTMLElement;
  expect(others.querySelectorAll("a.site-article-card")).toHaveLength(3);
  fireEvent.click(screen.getByRole("link", { name: "statistics page" }));
  expect(window.location.pathname).toBe("/statistics");
});

test("an unknown guide or legal page shows the 404", () => {
  const guide = renderSite("/guides/nothing");
  expect(screen.getByRole("heading", { level: 1, name: "This page does not exist" })).toBeInTheDocument();
  guide.unmount();
  renderSite("/legal/nothing");
  expect(screen.getByRole("heading", { level: 1, name: "This page does not exist" })).toBeInTheDocument();
  expect(document.title).toBe("Not found · Banxum");
});

test("legal pages: the six design documents and the backend template addresses", () => {
  const nav = () => within(screen.getByRole("list", { name: "Legal pages" }));
  const active = () => nav().queryAllByRole("link").filter((link) => link.classList.contains("active")).map((link) => link.textContent);

  const risk = renderSite("/legal/risk");
  expect(screen.getByRole("heading", { level: 1, name: "Risk information" })).toBeInTheDocument();
  expect(active()).toEqual(["Risk information"]);
  expect(screen.getByText("Version 1.0")).toBeInTheDocument();
  expect(screen.getByText("Valid from 1 Sep 2026")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "No deposit protection" })).toBeInTheDocument();
  risk.unmount();

  const privacy = renderSite("/legal/privacy");
  expect(screen.getByText("Outline of the privacy notice. The text follows from the lawyers.")).toBeInTheDocument();
  expect(screen.getByText("Transfers abroad")).toBeInTheDocument();
  privacy.unmount();

  const imprint = renderSite("/legal/imprint");
  expect(document.title).toBe("Imprint · Banxum");
  expect(screen.queryByText(/^Version/)).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "Bank" })).toBeInTheDocument();
  expect(screen.getByText("UBS Switzerland AG")).toBeInTheDocument();
  expect(screen.getByText("CH83 0020 6206 9567 6601 M")).toBeInTheDocument();
  // Owner decision 2026-10-15: the closing paragraph stays exactly as the design.
  expect(screen.getByText(/The sample figures of this prototype are invented\.$/)).toBeInTheDocument();
  imprint.unmount();

  // The investor flows' addresses: registration is the terms page, risk-disclosure the risk page.
  const registration = renderSite("/legal/registration");
  expect(screen.getByRole("heading", { level: 1, name: "Terms of use" })).toBeInTheDocument();
  expect(active()).toEqual(["Terms of use"]);
  expect(screen.getByText("Scope and parties")).toBeInTheDocument();
  registration.unmount();

  const riskDisclosure = renderSite("/legal/risk-disclosure");
  expect(screen.getByRole("heading", { level: 1, name: "Risk information" })).toBeInTheDocument();
  expect(active()).toEqual(["Risk information"]);
  riskDisclosure.unmount();

  // The other templates: their own title, no active item (preview mode does not load them).
  for (const [path, title] of [
    ["/legal/primary-market-investment", "Investment terms and loan claim assignment"],
    ["/legal/secondary-market-listing", "Secondary-market seller/listing terms"],
    ["/legal/secondary_market_purchase", "Secondary-market buyer terms"]
  ]) {
    const view = renderSite(path);
    expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
    expect(document.title).toBe(`${title} · Banxum`);
    expect(active()).toEqual([]);
    expect(screen.getByText(/Preview mode: the text of this document loads from the published server template\./)).toBeInTheDocument();
    view.unmount();
  }

  // Side navigation stays in the site.
  renderSite("/legal/terms");
  fireEvent.click(nav().getByRole("link", { name: "Complaints" }));
  expect(window.location.pathname).toBe("/legal/complaints");
  expect(screen.getByRole("heading", { level: 1, name: "Complaints" })).toBeInTheDocument();
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
  expect(window.location.pathname).toBe("/");
  expect(document.activeElement).toBe(screen.getByLabelText("Email address"));
});
