// Real-API Buy modal checks (QA audit 2026-10-09, A-01): the buyer must review and
// accept the fresh listing price, the purchase must carry those reviewed economics,
// and a "price changed" conflict must reload the new price for a second review.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  getV1AuthMeRetrieveResponseMock,
  getV1DocumentsAcceptancesCreateResponseMock,
  getV1DocumentsTemplatesCurrentRetrieveResponseMock,
  getV1KycStatusRetrieveResponseMock,
  getV1MarketplaceSecondaryListingsListResponseMock,
  getV1MarketplaceSecondaryListingsPurchaseCreateResponseMock,
  getV1MarketplaceSecondaryListingsRetrieveResponseMock
} from "./api/generated/banxumApi";

// Leave fixture preview mode so the modal talks to the (mocked) API.
vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

const listingId = "44444444-4444-4444-8444-444444444444";

// The "For sale now" row was loaded at par; the seller has since repriced it.
const listRow = {
  ...getV1MarketplaceSecondaryListingsListResponseMock()[0],
  id: listingId,
  loan_title: "Price lock listing",
  currency: "CHF",
  current_principal_minor: 1_000_000,
  price_bps: 10_000,
  discount_premium_bps: 0,
  transfer_price_minor: 1_000_000,
  accrued_interest_minor: 0,
  taker_fee_minor: 7_500,
  buyer_total_cost_minor: 1_007_500,
  risk_acknowledgement_required: false,
  loan_status_at_listing: "active",
  collateral_type: "real_estate",
  risk_rating: "A",
  // Another investor's listing (the generated mock picks this flag at random).
  is_own_listing: false
};

function detailAt(priceBps: number) {
  const transfer = (1_000_000 * priceBps) / 10_000;
  const takerFee = Math.round(transfer * 0.0075);
  return {
    ...getV1MarketplaceSecondaryListingsRetrieveResponseMock(),
    ...listRow,
    price_bps: priceBps,
    discount_premium_bps: priceBps - 10_000,
    transfer_price_minor: transfer,
    taker_fee_minor: takerFee,
    buyer_total_cost_minor: transfer + takerFee,
    investment_schedule: [],
    loan_schedule: [],
    borrower_name: "Price Lock AG",
    borrower_country: "CH",
    purpose: "working_capital",
    interest_rate_bps: 800,
    term_months: 12,
    ltv_bps: 5000,
    repayment_type: "equal_installments",
    public_disclosure_note: "",
    latest_public_note: null,
    schedule_version: 1
  };
}

function useInvestorApi(state: {
  detailPriceBps: number;
  purchaseResponses: Array<() => Response>;
  acceptanceResponses?: Array<() => Response>;
}) {
  const acceptances: Array<Record<string, unknown>> = [];
  const purchases: Array<Record<string, unknown>> = [];
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        ...getV1AuthMeRetrieveResponseMock(),
        user: {
          id: "u2",
          email: "buyer@example.com",
          full_name: "Buyer Two",
          investor_reference: "R2",
          account_type: "investor",
          status: "active",
          phone_verified: true,
          marketing_consent: false
        }
      })
    ),
    http.get("*/api/v1/kyc/status/", () =>
      HttpResponse.json({ ...getV1KycStatusRetrieveResponseMock(), status: "approved", financial_access_allowed: true })
    ),
    http.get("*/api/v1/investor/portal/notifications/", () => HttpResponse.json({ notifications: [], unread_count: 0 })),
    http.get("*/api/v1/investor/portal/balances/", () =>
      HttpResponse.json({ as_of: "2026-10-09T11:47:00Z", summaries: [], lots: [], payout_instructions: [], has_penalty_mode_balance: false })
    ),
    http.get("*/api/v1/marketplace/primary/loans/", () => HttpResponse.json([])),
    http.get("*/api/v1/marketplace/primary/opportunities/", () => HttpResponse.json([])),
    http.get("*/api/v1/investor/portal/portfolio/", () =>
      HttpResponse.json({
        as_of: "2026-10-09T11:47:00Z",
        holdings: [],
        summary: {
          holding_count: 0,
          active_holding_count: 0,
          outstanding_principal_by_currency: [],
          original_principal_by_currency: [],
          realized_interest_by_currency: [],
          late_or_defaulted_exposure_by_currency: []
        },
        exposure: {
          by_borrower: [],
          by_country: [],
          by_purpose: [],
          by_risk_rating: [],
          by_collateral_type: [],
          by_maturity: [],
          by_loan_status: []
        }
      })
    ),
    http.get("*/api/v1/investor/portal/secondary-market/", () => HttpResponse.json({ entries: [] })),
    http.get("*/api/v1/marketplace/secondary/listings/", () => HttpResponse.json([listRow])),
    http.get("*/api/v1/marketplace/secondary/listings/:listingId/", () => HttpResponse.json(detailAt(state.detailPriceBps))),
    http.get("*/api/v1/documents/templates/current/", () =>
      HttpResponse.json({
        ...getV1DocumentsTemplatesCurrentRetrieveResponseMock(),
        id: "tpl-buyer",
        title: "Buyer terms",
        version_number: 1,
        checkbox_labels: ["I accept."]
      })
    ),
    http.post("*/api/v1/auth/sensitive-action-code/request/", () =>
      HttpResponse.json({
        code_id: "22222222-2222-4222-8222-222222222222",
        action: "secondary_market_purchase",
        status: "sent",
        expires_at: "2026-10-09T11:57:00Z"
      })
    ),
    http.post("*/api/v1/documents/acceptances/", async ({ request }) => {
      acceptances.push((await request.json()) as Record<string, unknown>);
      const next = state.acceptanceResponses?.shift();
      if (next) return next();
      return HttpResponse.json({ ...getV1DocumentsAcceptancesCreateResponseMock(), id: `acc-${acceptances.length}` });
    }),
    http.post("*/api/v1/marketplace/secondary/listings/:listingId/purchase/", async ({ request }) => {
      purchases.push((await request.json()) as Record<string, unknown>);
      const next = state.purchaseResponses.shift();
      return next ? next() : HttpResponse.json(getV1MarketplaceSecondaryListingsPurchaseCreateResponseMock(), { status: 201 });
    })
  );
  return { acceptances, purchases };
}

async function openBuyDialog() {
  window.history.pushState({}, "", "/secondary-market");
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>
  );
  const row = await screen.findByText("Price lock listing", {}, { timeout: 5000 });
  fireEvent.click(row.closest("button") as HTMLElement);
  const dialog = await screen.findByRole("dialog");
  await within(dialog).findByText(/Borrower: Price Lock AG/, {}, { timeout: 5000 });
  return dialog;
}

function reviewValue(dialog: HTMLElement, label: string) {
  return within(dialog).getByText(label).nextElementSibling?.textContent ?? "";
}

test("buy modal shows, accepts and sends the fresh listing price, not the stale list row", async () => {
  const api = useInvestorApi({ detailPriceBps: 12_000, purchaseResponses: [] });
  const dialog = await openBuyDialog();

  expect(reviewValue(dialog, "Sale price")).toBe("20.0% premium");
  expect(reviewValue(dialog, "Total cost")).toMatch(/12.090\.00/);

  fireEvent.click(within(dialog).getByRole("checkbox"));
  fireEvent.click(within(dialog).getByRole("button", { name: /Send email code/ }));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Confirm purchase" })).toBeEnabled());
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm purchase" }));

  await screen.findAllByText("Purchase confirmed", {}, { timeout: 5000 });
  expect(api.acceptances[0]?.data_snapshot).toMatchObject({
    listing_id: listingId,
    price_bps: 12_000,
    current_principal_minor: 1_000_000,
    buyer_total_cost_minor: 1_209_000
  });
  expect(api.purchases[0]).toMatchObject({
    document_acceptance_id: "acc-1",
    expected_buyer_total_cost_minor: 1_209_000,
    expected_price_bps: 12_000,
    expected_current_principal_minor: 1_000_000
  });
}, 30_000);

test("a price change at confirm reloads the new price and asks for a fresh review", async () => {
  const state = {
    detailPriceBps: 10_000,
    purchaseResponses: [
      () => {
        // The seller edited the listing between the buyer's review and confirm.
        state.detailPriceBps = 11_000;
        return HttpResponse.json(
          {
            detail: "The price of this listing changed. Review the new price and confirm again.",
            code: "secondary_price_changed"
          },
          { status: 409 }
        );
      }
    ]
  };
  const api = useInvestorApi(state);
  const dialog = await openBuyDialog();
  expect(reviewValue(dialog, "Total cost")).toMatch(/10.075\.00/);

  const ack = within(dialog).getByRole("checkbox");
  fireEvent.click(ack);
  fireEvent.click(within(dialog).getByRole("button", { name: /Send email code/ }));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Confirm purchase" })).toBeEnabled());
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm purchase" }));

  await within(dialog).findByText("Price changed", {}, { timeout: 5000 });
  expect(within(dialog).getByText(/Review the new price and confirm again\. Nothing was charged\./)).toBeInTheDocument();
  await waitFor(() => expect(reviewValue(dialog, "Total cost")).toMatch(/11.082\.50/));
  expect(reviewValue(dialog, "Sale price")).toBe("10.0% premium");
  // The buyer must accept the terms again for the new price.
  expect(within(dialog).getByRole("checkbox")).not.toBeChecked();
  expect(within(dialog).getByRole("button", { name: "Confirm purchase" })).toBeDisabled();

  fireEvent.click(within(dialog).getByRole("checkbox"));
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Confirm purchase" })).toBeEnabled());
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm purchase" }));
  await screen.findAllByText("Purchase confirmed", {}, { timeout: 5000 });

  expect(api.acceptances).toHaveLength(2);
  expect(api.acceptances[0]?.data_snapshot).toMatchObject({ buyer_total_cost_minor: 1_007_500, price_bps: 10_000 });
  expect(api.acceptances[1]?.data_snapshot).toMatchObject({ buyer_total_cost_minor: 1_108_250, price_bps: 11_000 });
  expect(api.acceptances[1]?.idempotency_key).not.toBe(api.acceptances[0]?.idempotency_key);
  expect(api.purchases).toHaveLength(2);
  expect(api.purchases[0]).toMatchObject({ document_acceptance_id: "acc-1", expected_buyer_total_cost_minor: 1_007_500, expected_price_bps: 10_000 });
  expect(api.purchases[1]).toMatchObject({
    document_acceptance_id: "acc-2",
    expected_buyer_total_cost_minor: 1_108_250,
    expected_price_bps: 11_000,
    expected_current_principal_minor: 1_000_000,
    sensitive_action_code: "123456"
  });
}, 30_000);

test("a price change found when the terms are accepted reloads the price before any purchase", async () => {
  // The server builds the purchase evidence itself (SECCODE-11) and answers 409 when the
  // reviewed price is stale; nothing is recorded or charged.
  const state = {
    detailPriceBps: 10_000,
    purchaseResponses: [],
    acceptanceResponses: [
      () => {
        state.detailPriceBps = 11_000;
        return HttpResponse.json(
          {
            detail: "The price of this listing changed. Review the new price and confirm again.",
            code: "secondary_price_changed"
          },
          { status: 409 }
        );
      }
    ]
  };
  const api = useInvestorApi(state);
  const dialog = await openBuyDialog();

  fireEvent.click(within(dialog).getByRole("checkbox"));
  fireEvent.click(within(dialog).getByRole("button", { name: /Send email code/ }));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Confirm purchase" })).toBeEnabled());
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm purchase" }));

  await within(dialog).findByText("Price changed", {}, { timeout: 5000 });
  await waitFor(() => expect(reviewValue(dialog, "Total cost")).toMatch(/11.082\.50/));
  expect(within(dialog).getByRole("checkbox")).not.toBeChecked();
  expect(api.purchases).toHaveLength(0);
}, 30_000);
