// IP of Webby-Soft SRL.
// 18.7: the price of a Loan Originator offer (principal + accrued interest) is computed in the
// browser exactly like the server (backend platform_core/domain/day_count.accrued_interest_minor).
import { describe, expect, it } from "vitest";

import type { MarketplaceLoanDetail } from "../../../api/generated/banxumApi";
import { offerAccruedInterestMinor, offerPriceMinor } from "./loanFacts";

const offer = (overrides: Partial<NonNullable<MarketplaceLoanDetail["offer_price"]>> = {}): Pick<MarketplaceLoanDetail, "offer_price"> => ({
  offer_price: {
    pricing_rule: "accrued_interest",
    interest_convention: "act_365_fixed",
    interest_convention_label: "Actual/365 Fixed",
    price_reference_date: "2027-01-27",
    accrual_start_date: "2027-01-01",
    next_due_date: "2027-02-20",
    next_installment_interest_minor: 10_000,
    next_installment_principal_minor: 200_000,
    next_installment_opening_principal_minor: 1_000_000,
    accrued_day_units: 26,
    period_day_units: 50,
    investor_interest_participation_bps: 7_000,
    investor_penalty_participation_bps: 5_000,
    ...overrides
  }
});

describe("offer price (18.7)", () => {
  it("matches the server's exact integer formula", () => {
    // 10,000 x 100,000 / 1,000,000 x 26 / 50 x 0.7 = 364.00 (same case as the backend test).
    expect(offerAccruedInterestMinor(offer(), 100_000)).toBe(364);
    expect(offerPriceMinor(offer(), 100_000)).toBe(100_364);
  });

  it("rounds half up once and stays exact for large amounts", () => {
    // 10,000 x 1 / 1,000,000 x 26 / 50 x 0.7 = 0.00364 -> 0; 125,000 -> 455 exactly.
    expect(offerAccruedInterestMinor(offer(), 1)).toBe(0);
    expect(offerAccruedInterestMinor(offer(), 125_000)).toBe(455);
    // 1/2 cent rounds up: 10,000 x 100 / 1,000,000 x 25 / 50 x 1 = 0.5 -> 1.
    expect(offerAccruedInterestMinor(offer({ accrued_day_units: 25, investor_interest_participation_bps: 10_000 }), 100)).toBe(1);
    expect(offerAccruedInterestMinor(offer({ next_installment_interest_minor: 9_876_543, next_installment_opening_principal_minor: 987_654_321 }), 987_654_321)).toBe(
      Math.round((9_876_543 * 26 * 0.7) / 50)
    );
  });

  it("is zero without an accrued price", () => {
    expect(offerAccruedInterestMinor({ offer_price: null }, 100_000)).toBe(0);
    expect(offerPriceMinor({ offer_price: undefined }, 100_000)).toBe(100_000);
  });
});
