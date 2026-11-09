// Real-API secondary-market seller checks (QA audit 2026-10-09): A-36 (a listing
// re-confirmed at a new price gets new evidence and keys), A-34 (the seller sees the
// server's net proceeds, with accrued interest and the configured fee) and A-35 (your
// own listing has no Buy and never creates a buyer acceptance). U33: "Sell investment" on the
// investment page opens the selling dialog; your own listing is not among the offers to buy.
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
import { enterPin } from "./test/pin";

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
        days_past_due: 0,
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

// The server's seller pricing: 2 % maker fee (minimum CHF 20.00, owner decision
// 2026-10-16), no buyer fee, and accrued interest of CHF 7.89 to today.
function serverPricing(priceBps: number) {
  const transfer = Math.round((600_000 * priceBps) / 10_000);
  const accrued = 789;
  const makerFee = Math.max(2_000, Math.round(transfer * 0.02));
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
    maker_fee_bps: 200,
    minimum_maker_fee_minor: 2_000,
    maker_fee_minor: makerFee,
    seller_net_proceeds_minor: transfer + accrued - makerFee,
    taker_fee_minor: 0,
    buyer_total_cost_minor: transfer + accrued
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

async function openSellDialog() {
  renderLiveApp(App, "/portfolio/h1");
  fireEvent.click(await screen.findByRole("button", { name: "Sell investment" }, { timeout: 5000 }));
  return screen.findByRole("dialog", { name: "Sell investment" });
}

function typePrice(dialog: HTMLElement, value: string) {
  const input = within(dialog).getByRole("textbox", { name: /Selling price/ });
  fireEvent.change(input, { target: { value } });
  fireEvent.blur(input);
  return input;
}

test("A-34: the listing form shows the server's seller net, with accrued interest and the configured fee", async () => {
  server.use(...sellerHandlers(holdingFixture(), () => HttpResponse.json(getV1MarketplaceSecondaryListingsCreateResponseMock(), { status: 201 })));
  const dialog = await openSellDialog();
  const input = typePrice(dialog, "5940");

  // 5,940.00 selling price + 7.89 accrued - 118.80 selling fee (2 %).
  await waitFor(() => expect(reviewValue("You receive if sold")).toMatch(/CHF 5\.829,09/));
  expect(reviewValue("Accrued interest")).toMatch(/CHF 7,89/);
  expect(reviewValue("Selling fee")).toMatch(/CHF 118,80/);
  expect(within(dialog).getByText("1,0% discount", { selector: ".s106-adjustment" })).toBeInTheDocument();
  expect((input as HTMLInputElement).value).toMatch(/5\.?940,00/);
  expect(calls.previews.at(-1)).toEqual({ priceBps: 9_900 });
}, 30_000);

test("the sale price is par or a discount: above the investment value shows an error and cannot continue", async () => {
  server.use(...sellerHandlers(holdingFixture(), () => HttpResponse.json(getV1MarketplaceSecondaryListingsCreateResponseMock(), { status: 201 })));
  const dialog = await openSellDialog();
  expect(within(dialog).getByText("Up to 100% of the investment value")).toBeInTheDocument();
  expect(within(dialog).getByRole("slider", { name: "Selling price" })).toHaveAttribute("max", "100");
  await waitFor(() => expect(calls.previews).toHaveLength(1));

  const input = typePrice(dialog, "6060");
  expect(await within(dialog).findByText(/at most the investment value \(CHF 6\.000,00\), with no premium\./)).toBeInTheDocument();
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(within(dialog).getByRole("button", { name: "Review listing" })).toBeDisabled();
  // No server pricing is asked for a price the server refuses.
  expect(calls.previews.some((preview) => Number(preview.priceBps) > 10_000)).toBe(false);

  // Exactly par is fine again.
  typePrice(dialog, "6000");
  expect(within(dialog).queryByText(/at most the investment value/)).not.toBeInTheDocument();
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Review listing" })).toBeEnabled());
}, 30_000);

test("A-36: a new price after a failed confirm gets a new acceptance for that price and new keys", async () => {
  server.use(
    ...sellerHandlers(holdingFixture(), (attempt) =>
      attempt === 1
        ? HttpResponse.json({ detail: "Invalid or expired confirmation code." }, { status: 400 })
        : HttpResponse.json({ ...getV1MarketplaceSecondaryListingsCreateResponseMock(), id: "listing-1" }, { status: 201 })
    )
  );
  const dialog = await openSellDialog();
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Review listing" })).toBeEnabled());
  fireEvent.click(within(dialog).getByRole("button", { name: "Review listing" }));
  const review = await screen.findByRole("dialog", { name: "Confirm listing" });
  // The email code is sent once the seller reaches the confirmation.
  await waitFor(() => expect(calls.codes).toHaveLength(1));
  fireEvent.click(within(review).getByRole("checkbox"));
  fireEvent.change(within(review).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "111111" } });
  enterPin();
  await waitFor(() => expect(within(review).getByRole("button", { name: "Confirm listing" })).toBeEnabled());
  fireEvent.click(within(review).getByRole("button", { name: "Confirm listing" }));
  await screen.findByText("Invalid or expired confirmation code.", {}, { timeout: 5000 });

  // The seller goes back and lowers the price to a 5 % discount.
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  const priceDialog = await screen.findByRole("dialog", { name: "Sell investment" });
  typePrice(priceDialog, "5700");
  await waitFor(() => expect(within(priceDialog).getByText("5,0% discount", { selector: ".s106-adjustment" })).toBeInTheDocument());
  await waitFor(() => expect(within(priceDialog).getByRole("button", { name: "Review listing" })).toBeEnabled());
  fireEvent.click(within(priceDialog).getByRole("button", { name: "Review listing" }));
  const second = await screen.findByRole("dialog", { name: "Confirm listing" });
  const ack = within(second).getByRole("checkbox");
  expect(ack).not.toBeChecked();
  fireEvent.click(ack);
  fireEvent.change(within(second).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "222222" } });
  enterPin();
  await waitFor(() => expect(within(second).getByRole("button", { name: "Confirm listing" })).toBeEnabled());
  fireEvent.click(within(second).getByRole("button", { name: "Confirm listing" }));
  await screen.findAllByText("Listing published", {}, { timeout: 5000 });

  expect(calls.codes).toHaveLength(1);
  expect(calls.acceptances).toHaveLength(2);
  expect(calls.acceptances[1].data_snapshot).toMatchObject({ price_bps: 9_500, seller_net_proceeds_minor: serverPricing(9_500).seller_net_proceeds_minor });
  expect(calls.acceptances[1].idempotency_key).not.toBe(calls.acceptances[0].idempotency_key);
  expect(calls.listings[1]).toMatchObject({ price_bps: 9_500, document_acceptance_id: "acc-2", sensitive_action_code: "222222" });
  expect(calls.listings[1].idempotency_key).not.toBe(calls.listings[0].idempotency_key);
}, 30_000);

test("A-35: your own listing is not offered to you, and its offer page has no Buy, terms or code", async () => {
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
  const view = renderLiveApp(App, "/secondary-market");
  expect(await screen.findByRole("button", { name: "View offer Someone else's listing" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByText("My own listing")).not.toBeInTheDocument();
  view.unmount();

  // Opened from its address, your own offer says so and offers no purchase.
  renderLiveApp(App, `/secondary-market?offer=${ownListing.id}`);
  expect(await screen.findByText("This is your listing. You cannot buy it.", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Manage it under My listings" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Buy for / })).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: "Email confirmation code" })).not.toBeInTheDocument();
  expect(calls.acceptances).toHaveLength(0);
  expect(calls.codes).toHaveLength(0);
}, 30_000);
