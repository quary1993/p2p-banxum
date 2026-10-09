import { describe, expect, test } from "vitest";

import {
  collateralBreakdown,
  isUnsecuredHolding,
  isUnsecuredLoan,
  loanLtvBps,
  valuedSecuredHoldings,
  weightedLtvPercent
} from "./portfolioCollateral";

const holding = (principal: number, collateralType: string, collateralValue: number, ltvBps: number | null) => ({
  current_principal_minor: principal,
  loan: { collateral_type: collateralType, collateral_value_minor: collateralValue, ltv_bps: ltvBps }
});

// QA S18 EUR tab: an invoice-backed loan plus "QA LO Main", recorded as real estate with a collateral value of 0.
const invoices = holding(16_400_000, "invoices", 24_600_000, 6667);
const zeroValueProperty = holding(400_000, "real_estate", 0, null);

describe("portfolio collateral", () => {
  test("a loan with collateral value 0 is unsecured whatever type is recorded", () => {
    expect(isUnsecuredHolding(zeroValueProperty)).toBe(true);
    expect(isUnsecuredHolding(holding(100, "unsecured_exception", 0, null))).toBe(true);
    expect(isUnsecuredHolding(invoices)).toBe(false);
  });

  test("collateral spread excludes zero-value collateral and counts it as nothing pledged", () => {
    const breakdown = collateralBreakdown([invoices, zeroValueProperty], (item) => item.loan.collateral_type);

    expect(breakdown.secured).toEqual([["invoices", 16_400_000]]);
    expect(breakdown.unsecuredMinor).toBe(400_000);
    expect(breakdown.unsecuredCount).toBe(1);
  });

  test("weighted LTV only uses holdings with pledged, valued collateral", () => {
    // Even if a stale LTV figure came with a zero-value loan, it must not enter the average.
    const staleLtv = holding(400_000, "real_estate", 0, 2000);

    expect(valuedSecuredHoldings([invoices, staleLtv])).toEqual([invoices]);
    expect(weightedLtvPercent([invoices, staleLtv])).toBeCloseTo(66.67, 2);
    expect(weightedLtvPercent([zeroValueProperty])).toBeNull();
  });
});

describe("one LTV and one unsecured rule for every screen (audit A-65)", () => {
  test("unsecured: unsecured type, no pledged value, or no LTV when the value is unknown", () => {
    expect(isUnsecuredLoan({ collateral_type: "unsecured_exception", ltv_bps: null })).toBe(true);
    expect(isUnsecuredLoan({ collateral_type: "real_estate", collateral_value_minor: 0, ltv_bps: 5000 })).toBe(true);
    // Marketplace list rows carry no value: no LTV means nothing is pledged.
    expect(isUnsecuredLoan({ collateral_type: "real_estate", ltv_bps: null })).toBe(true);
    expect(isUnsecuredLoan({ collateral_type: "real_estate", ltv_bps: 6000 })).toBe(false);
  });

  test("LTV is the principal still owed on the loan over the valuation", () => {
    // Direct loan of 250'000 against 380'000 after 20'150.09 was repaid: 229'849.91 / 380'000.
    const direct = {
      collateral_type: "real_estate",
      collateral_value_minor: 38_000_000,
      ltv_bps: 6579,
      product_type: "direct",
      principal_minor: 25_000_000,
      schedule: [{ outstanding_principal_minor: 0 }, { outstanding_principal_minor: 22_984_991 }]
    };
    expect(loanLtvBps(direct)).toBe(6049);
    // Originator claims report the outstanding principal itself.
    expect(loanLtvBps({ collateral_type: "receivables", collateral_value_minor: 31_500_000, ltv_bps: 6667, product_type: "originator_claim", principal_minor: 18_993_535, schedule: [] })).toBe(6030);
    // Without a valuation in the payload the API figure is used.
    expect(loanLtvBps({ collateral_type: "real_estate", ltv_bps: 6100 })).toBe(6100);
    expect(loanLtvBps({ collateral_type: "real_estate", collateral_value_minor: 0, ltv_bps: 6100 })).toBeNull();
  });
});
