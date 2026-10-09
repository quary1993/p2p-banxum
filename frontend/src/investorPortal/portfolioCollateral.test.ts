import { describe, expect, test } from "vitest";

import { collateralBreakdown, isUnsecuredHolding, valuedSecuredHoldings, weightedLtvPercent } from "./portfolioCollateral";

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
