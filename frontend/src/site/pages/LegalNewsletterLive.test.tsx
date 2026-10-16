// IP of Webby-Soft SRL.
// Public site against the (mocked) API: the backend's published legal templates on the legal
// pages, the PDF download, and the newsletter links posting their token once.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { StrictMode, type ComponentType } from "react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "../../api/mocks/server";

// Leave fixture preview mode so the pages talk to the (mocked) API.
vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("../../App")).App;
});

function renderSite(path: string) {
  window.history.pushState({}, "", path);
  return render(
    <StrictMode>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <App />
      </QueryClientProvider>
    </StrictMode>
  );
}

const published = {
  registration: {
    id: "11111111-1111-4111-8111-111111111111",
    category: "registration",
    template_key: "default",
    language: "en",
    version_number: 3,
    title: "Lender user agreement",
    body: "# Scope\n\nThese terms bind {{ platform.name }} lenders and {{ operator.name }}. Questions: {{ platform.support_email }}. Your reference: {{ lender.reference }}.\n\n## Fees\n\n- No fee to invest\n- 1% for a secondary-market sale\n\n| Item | Fee |\n|---|---|\n| Listing | 1% |",
    checkbox_labels: ["I accept the Lender user agreement."],
    content_hash: "abc",
    // 2 October in Zurich.
    published_at: "2026-10-01T22:30:00Z"
  },
  primary_market_investment: {
    id: "22222222-2222-4222-8222-222222222222",
    category: "primary_market_investment",
    template_key: "default",
    language: "en",
    version_number: 5,
    title: "Investment terms and loan claim assignment",
    body: "# Assignment\n\nGaranta assigns a share of the claim to you.",
    checkbox_labels: [],
    content_hash: "def",
    published_at: "2026-09-15T08:00:00Z"
  }
};

const templateRequests: string[] = [];
let newsletterCalls: Array<{ path: string; token: string }> = [];

beforeEach(() => {
  templateRequests.length = 0;
  newsletterCalls = [];
  server.use(
    http.get("*/api/v1/documents/templates/current/", ({ request }) => {
      const category = new URL(request.url).searchParams.get("category") ?? "";
      templateRequests.push(category);
      if (category === "registration") return HttpResponse.json(published.registration);
      if (category === "primary_market_investment") return HttpResponse.json(published.primary_market_investment);
      if (category === "secondary_market_purchase") return HttpResponse.json({ detail: "Server error." }, { status: 500 });
      return HttpResponse.json({ detail: "No published template." }, { status: 404 });
    }),
    http.get("*/api/v1/documents/templates/current/artifact/", ({ request }) => {
      const category = new URL(request.url).searchParams.get("category");
      return HttpResponse.json({
        template_version_id: published.registration.id,
        category,
        title: "Lender user agreement",
        version_number: 3,
        content_hash: "abc",
        content_type: "application/pdf",
        content_encoding: "base64",
        filename: `${category}-v3.pdf`,
        content: btoa("%PDF-1.7")
      });
    }),
    http.post("*/api/v1/public/newsletter/:action/", async ({ request, params }) => {
      const body = (await request.json()) as { token: string };
      newsletterCalls.push({ path: String(params.action), token: body.token });
      if (body.token === "bad") {
        return HttpResponse.json({ detail: "This link is not valid or has expired.", code: "invalid_token" }, { status: 400 });
      }
      if (body.token === "busy") {
        return HttpResponse.json({ detail: "Too many requests. Try again in a minute.", code: "throttled" }, { status: 429 });
      }
      return HttpResponse.json({ status: params.action === "confirm" ? "confirmed" : "unsubscribed" });
    })
  );
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

function activeLegalItems() {
  return within(screen.getByRole("list", { name: "Legal pages" }))
    .getAllByRole("link")
    .filter((link) => link.classList.contains("active"))
    .map((link) => link.textContent);
}

test("terms and /legal/registration show the published Terms and Conditions template", async () => {
  const terms = renderSite("/legal/terms");
  expect(await screen.findByRole("heading", { level: 2, name: "Scope" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Terms of use" })).toBeInTheDocument();
  expect(activeLegalItems()).toEqual(["Terms of use"]);
  expect(screen.getByText("Version 3")).toBeInTheDocument();
  expect(screen.getByText("Valid from 2 Oct 2026")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Print" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download PDF" })).toBeInTheDocument();
  // Variables: the known ones filled in, the others in brackets; text, lists and tables.
  expect(screen.getByText(/These terms bind BANXUM lenders and Garanta Finanzgruppe AG\. Questions: support@banxum\.com\. Your reference: \[lender\.reference\]\./)).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 3, name: "Fees" })).toBeInTheDocument();
  expect(screen.getByText("1% for a secondary-market sale").tagName).toBe("LI");
  expect(screen.getByRole("table")).toHaveClass("site-table");
  expect(screen.getByRole("heading", { level: 2, name: "You will be asked to confirm" })).toBeInTheDocument();
  expect(screen.getByText("I accept the Lender user agreement.")).toBeInTheDocument();
  // The design outline is not shown once a version is published.
  expect(screen.queryByText(/Outline of the terms of use/)).not.toBeInTheDocument();
  terms.unmount();

  renderSite("/legal/registration");
  expect(await screen.findByRole("heading", { level: 2, name: "Scope" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Terms of use" })).toBeInTheDocument();
  expect(activeLegalItems()).toEqual(["Terms of use"]);
  expect(document.title).toBe("Terms of use · Banxum");
  expect(templateRequests).toContain("registration");
});

test("the PDF of a published template downloads from the meta line", async () => {
  const createObjectURL = vi.fn(() => "blob:terms");
  const revokeObjectURL = vi.fn();
  // jsdom has no object URLs.
  const urlStatics = URL as unknown as Record<string, unknown>;
  const original = { createObjectURL: urlStatics.createObjectURL, revokeObjectURL: urlStatics.revokeObjectURL };
  Object.assign(urlStatics, { createObjectURL, revokeObjectURL });
  const clicked: HTMLAnchorElement[] = [];
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    clicked.push(this);
  });
  try {
    renderSite("/legal/registration");
    fireEvent.click(await screen.findByRole("link", { name: "Download PDF" }));
    await waitFor(() => expect(clicked).toHaveLength(1));
    expect(clicked[0].download).toBe("registration-v3.pdf");
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:terms");
    expect(screen.getByRole("link", { name: "Download PDF" })).toBeInTheDocument();
  } finally {
    click.mockRestore();
    Object.assign(urlStatics, original);
  }
});

test("risk information keeps the design text while no risk disclosure is published", async () => {
  renderSite("/legal/risk-disclosure");
  expect(await screen.findByRole("heading", { level: 2, name: "No deposit protection" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Risk information" })).toBeInTheDocument();
  expect(activeLegalItems()).toEqual(["Risk information"]);
  expect(screen.getByText("Version 1.0")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Download PDF" })).not.toBeInTheDocument();
  expect(templateRequests).toContain("risk_disclosure");
});

test("the other templates show their own document, with no active legal page", async () => {
  const investment = renderSite("/legal/primary-market-investment");
  expect(await screen.findByRole("heading", { level: 1, name: "Investment terms and loan claim assignment" })).toBeInTheDocument();
  expect(await screen.findByText("Garanta assigns a share of the claim to you.")).toBeInTheDocument();
  expect(screen.getByText("Version 5")).toBeInTheDocument();
  expect(activeLegalItems()).toEqual([]);
  expect(screen.queryByRole("heading", { name: "You will be asked to confirm" })).not.toBeInTheDocument();
  investment.unmount();

  const listing = renderSite("/legal/secondary-market-listing");
  expect(await screen.findByText(/The current version of this document is being prepared/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Secondary-market seller/listing terms" })).toBeInTheDocument();
  expect(activeLegalItems()).toEqual([]);
  listing.unmount();

  renderSite("/legal/secondary-market-purchase");
  expect(await screen.findByText(/The current published document could not be loaded\./)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Retry" })).toBeInTheDocument();
});

test("the newsletter confirmation posts its token once and shows the answer", async () => {
  renderSite("/newsletter/confirm?token=good-token");
  expect(await screen.findByRole("heading", { name: "Your subscription is confirmed." })).toBeInTheDocument();
  expect(newsletterCalls).toEqual([{ path: "confirm", token: "good-token" }]);
});

test("an unsubscribe link answers once, idempotent for the visitor", async () => {
  renderSite("/newsletter/unsubscribe?token=good-token");
  expect(await screen.findByRole("heading", { name: "You are unsubscribed." })).toBeInTheDocument();
  expect(newsletterCalls).toEqual([{ path: "unsubscribe", token: "good-token" }]);
});

test("an invalid or expired newsletter link offers to subscribe again", async () => {
  const confirm = renderSite("/newsletter/confirm?token=bad");
  expect(await screen.findByRole("heading", { name: "This link is not valid or has expired." })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Subscribe again" })).toHaveAttribute("href", "/#site-sub-home");
  confirm.unmount();

  renderSite("/newsletter/unsubscribe");
  expect(screen.getByRole("heading", { name: "This link is not valid or has expired." })).toBeInTheDocument();
  expect(newsletterCalls).toEqual([{ path: "confirm", token: "bad" }]);
});

test("a throttled newsletter link shows the server's message and can try again", async () => {
  renderSite("/newsletter/confirm?token=busy");
  expect(await screen.findByText("Too many requests. Try again in a minute.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(newsletterCalls).toHaveLength(2));
});
