// Real-API secondary-market seller checks (QA audit 2026-10-09): A-36 (a listing
// re-confirmed at a new price gets new evidence and keys), A-34 (the seller sees the
// server's net proceeds, with accrued interest and the configured fee) and A-35 (your
// own listing has no Buy and never creates a buyer acceptance).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse, type JsonBodyType } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  getV1DocumentsAcceptancesCreateResponseMock,
  getV1DocumentsTemplatesCurrentRetrieveResponseMock,
  getV1InvestorPortalPortfolioRetrieveResponseMock,
  getV1MarketplaceSecondaryListingsCreateResponseMock,
  getV1MarketplaceSecondaryListingsListResponseMock,
  getV1MarketplaceSecondaryListingsRetrieveResponseMock
} from "./api/generated/banxumApi";
import { emptyCalls, emptyPortfolio, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("listings", "acceptances", "codes", "previews", "purchases");
});

function holdingFixture(openListingId: string | null = null) {
  const base = getV1InvestorPortalPortfolioRetrieveResponseMock();
  const template = base.holdings[0];
  return {
    ...base,
    as_of: "2026-10-09T11:47:00Z",
    holdings: [{
      ...template,
      id: "h1",
      status: "active",
      currency: "CHF",
      original_principal_minor: 600_000,
      current_principal_minor: 600_000,
      investment_schedule: [],
      open_secondary_listing: openListingId
        ? { ...(template.open_secondary_listing ?? {}), id: openListingId, status: "active", price_bps: 10_000 }
        : null,
      loan: {
        ...template.loan,
        loan_id: "l1",
        loan_title: "Audit loan",
        borrower_name: "Audit AG",
        loan_status: "active",
        interest_rate_bps: 1200,
        term_months: 3,
        ltv_bps: 5000,
        schedule: [],
        collateral_type: "real_estate",
        purpose: "working_capital",
        risk_rating: "A",
        borrower_country: "CH",
        repayment_type: "equal_installments"
      }
    }]
  };
}

// The server's seller pricing: 0.25 % maker fee (minimum CHF 20.00) and accrued
// interest of CHF 7.89 to today, as in the audit's S28 example.
function serverPricing(priceBps: number) {
  const transfer = Math.round((600_000 * priceBps) / 10_000);
  const accrued = 789;
  const makerFee = Math.max(2_000, Math.round(transfer * 0.0025));
  return {
    holding_id: "h1",
    currency: "CHF",
    price_bps: priceBps,
    pricing_date: "2026-10-14",
    current_principal_minor: 600_000,
    transfer_price_minor: transfer,
    discount_premium_bps: priceBps - 10_000,
    accrued_interest_minor: accrued,
    accrued_interest_from_date: "2026-10-10",
    accrued_interest_to_date: "2026-10-14",
    maker_fee_bps: 25,
    minimum_maker_fee_minor: 2_000,
    maker_fee_minor: makerFee,
    seller_net_proceeds_minor: transfer + accrued - makerFee,
    taker_fee_minor: Math.round(transfer * 0.0075),
    buyer_total_cost_minor: transfer + accrued + Math.round(transfer * 0.0075)
  };
}

function sellerHandlers(portfolio: JsonBodyType, listingResult: (attempt: number) => Response) {
  return [
    ...investorShellHandlers(calls, { portfolio: () => portfolio }),
    http.get("*/api/v1/marketplace/secondary/listings/pricing-preview/", ({ request }) => {
      const priceBps = Number(new URL(request.url).searchParams.get("price_bps"));
      calls.previews.push({ priceBps });
      return HttpResponse.json(serverPricing(priceBps));
    }),
    http.get("*/api/v1/documents/templates/current/", () =>
      HttpResponse.json({ ...getV1DocumentsTemplatesCurrentRetrieveResponseMock(), id: "tpl-l", title: "Listing terms", version_number: 1, checkbox_labels: ["I accept."] })
    ),
    http.post("*/api/v1/documents/acceptances/", async ({ request }) => {
      calls.acceptances.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ ...getV1DocumentsAcceptancesCreateResponseMock(), id: `acc-${calls.acceptances.length}` }, { status: 201 });
    }),
    http.post("*/api/v1/marketplace/secondary/listings/", async ({ request }) => {
      calls.listings.push((await request.json()) as Record<string, unknown>);
      return listingResult(calls.listings.length);
    })
  ];
}

function reviewValue(label: string) {
  const dialog = screen.getByRole("dialog");
  return within(dialog).getByText(label).nextElementSibling?.textContent ?? "";
}

test("A-34: the listing form shows the server's seller net, with accrued interest and the configured fee", async () => {
  server.use(...sellerHandlers(holdingFixture(), () => HttpResponse.json(getV1MarketplaceSecondaryListingsCreateResponseMock(), { status: 201 })));
  renderLiveApp(App, "/secondary-market");
  fireEvent.click(await screen.findByRole("tab", { name: "Sell a holding" }, { timeout: 5000 }));
  fireEvent.click(await screen.findByRole("button", { name: "List" }, { timeout: 5000 }));
  await screen.findByRole("dialog");
  fireEvent.change(screen.getByDisplayValue("10000"), { target: { value: "10100" } });

  // 6,060.00 transfer + 7.89 accrued - 20.00 minimum maker fee (not 0.25 % = 15.15).
  await waitFor(() => expect(reviewValue("Seller net proceeds")).toMatch(/CHF 6.047\.89/));
  expect(reviewValue("Transfer price")).toMatch(/CHF 6.060\.00/);
  expect(reviewValue("Accrued interest to you")).toMatch(/CHF 7\.89/);
  expect(reviewValue("Maker fee")).toMatch(/CHF 20\.00/);
  expect(calls.previews.at(-1)).toEqual({ priceBps: 10_100 });
}, 30_000);

test("A-36: a new price after a failed confirm gets a new acceptance for that price and new keys", async () => {
  server.use(
    ...sellerHandlers(holdingFixture(), (attempt) =>
      attempt === 1
        ? HttpResponse.json({ detail: "Invalid or expired confirmation code." }, { status: 400 })
        : HttpResponse.json({ ...getV1MarketplaceSecondaryListingsCreateResponseMock(), id: "listing-1" }, { status: 201 })
    )
  );
  renderLiveApp(App, "/secondary-market");
  fireEvent.click(await screen.findByRole("tab", { name: "Sell a holding" }, { timeout: 5000 }));
  fireEvent.click(await screen.findByRole("button", { name: "List" }, { timeout: 5000 }));
  const dialog = await screen.findByRole("dialog");
  fireEvent.click(within(dialog).getByRole("checkbox"));
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm listing data" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm listing data" }));
  await waitFor(() => expect(calls.codes).toHaveLength(1));
  fireEvent.change(await screen.findByRole("textbox", { name: "Email confirmation code" }), { target: { value: "111111" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Verify and publish" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Verify and publish" }));
  await screen.findByText("Invalid or expired confirmation code.", {}, { timeout: 5000 });

  // The seller goes back and lowers the price to a 5 % discount.
  fireEvent.click(screen.getByRole("button", { name: "Back to listing data" }));
  fireEvent.change(screen.getByDisplayValue("10000"), { target: { value: "9500" } });
  const ack = within(screen.getByRole("dialog")).getByRole("checkbox");
  expect(ack).not.toBeChecked();
  fireEvent.click(ack);
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm listing data" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm listing data" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Email confirmation code" }), { target: { value: "222222" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify and publish" }));
  await screen.findAllByText("Listing published", {}, { timeout: 5000 });

  expect(calls.acceptances).toHaveLength(2);
  expect(calls.acceptances[1].data_snapshot).toMatchObject({ price_bps: 9_500, seller_net_proceeds_minor: serverPricing(9_500).seller_net_proceeds_minor });
  expect(calls.acceptances[1].idempotency_key).not.toBe(calls.acceptances[0].idempotency_key);
  expect(calls.listings[1]).toMatchObject({ price_bps: 9_500, document_acceptance_id: "acc-2" });
  expect(calls.listings[1].idempotency_key).not.toBe(calls.listings[0].idempotency_key);
}, 30_000);

test("A-35: your own listing shows 'Your listing', without Buy, terms or a code", async () => {
  const ownListing = {
    ...getV1MarketplaceSecondaryListingsListResponseMock()[0],
    id: "55555555-5555-4555-8555-555555555555",
    loan_title: "My own listing",
    currency: "CHF",
    current_principal_minor: 600_000,
    discount_premium_bps: 0,
    is_own_listing: true
  };
  const otherListing = { ...ownListing, id: "66666666-6666-4666-8666-666666666666", loan_title: "Someone else's listing", is_own_listing: false };
  server.use(
    http.get("*/api/v1/marketplace/secondary/listings/", () => HttpResponse.json([ownListing, otherListing])),
    http.get("*/api/v1/marketplace/secondary/listings/:listingId/", () =>
      HttpResponse.json({ ...getV1MarketplaceSecondaryListingsRetrieveResponseMock(), ...ownListing, investment_schedule: [], loan_schedule: [] })
    ),
    http.post("*/api/v1/documents/acceptances/", async ({ request }) => {
      calls.acceptances.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(getV1DocumentsAcceptancesCreateResponseMock(), { status: 201 });
    }),
    // After the listing handlers above: the first matching handler answers.
    ...investorShellHandlers(calls, { portfolio: () => emptyPortfolio })
  );
  renderLiveApp(App, "/secondary-market");
  const ownRow = (await screen.findByText("My own listing", {}, { timeout: 5000 })).closest("button") as HTMLElement;
  const otherRow = screen.getByText("Someone else's listing").closest("button") as HTMLElement;
  expect(within(ownRow).getByText("Your listing")).toBeInTheDocument();
  expect(within(ownRow).queryByText("Buy")).not.toBeInTheDocument();
  expect(within(otherRow).getByText("Buy")).toBeInTheDocument();
  expect(screen.getByText(/1 listing · sold by other investors · 1 of yours/)).toBeInTheDocument();

  fireEvent.click(ownRow);
  const dialog = await screen.findByRole("dialog");
  await within(dialog).findByText("This is your listing", {}, { timeout: 5000 });
  expect(within(dialog).queryByRole("checkbox")).not.toBeInTheDocument();
  expect(within(dialog).queryByRole("button", { name: "Confirm purchase" })).not.toBeInTheDocument();
  expect(within(dialog).queryByRole("textbox", { name: "Email confirmation code" })).not.toBeInTheDocument();
  expect(calls.acceptances).toHaveLength(0);
  expect(calls.codes).toHaveLength(0);
}, 30_000);
