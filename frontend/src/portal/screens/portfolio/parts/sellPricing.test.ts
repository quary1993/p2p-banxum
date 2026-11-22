// IP of Webby-Soft SRL.
// Listing price rules of the Sell investment dialog (U33-DEC-06/07: 0-102%, whole basis points, capped fee).
import { describe, expect, test } from "vitest";

import { discountTone, MAX_PRICE_BPS, MIN_PRICE_BPS, PAR_PRICE_BPS, previewSellerFee, priceBpsForAmount } from "./sellPricing";

describe("priceBpsForAmount", () => {
  test("a typed amount becomes whole basis points of the outstanding principal", () => {
    expect(priceBpsForAmount(5_940_00, 6_000_00)).toBe(9_900);
    expect(priceBpsForAmount(6_000_00, 6_000_00)).toBe(PAR_PRICE_BPS);
    expect(priceBpsForAmount(6_120_00, 6_000_00)).toBe(MAX_PRICE_BPS);
    // 3.333,33 of 10.000,00 rounds to 33,33%.
    expect(priceBpsForAmount(3_333_33, 10_000_00)).toBe(3_333);
  });

  test("stays between 0% and 102%", () => {
    expect(MIN_PRICE_BPS).toBe(0);
    expect(priceBpsForAmount(0, 10_000_00)).toBe(0);
    expect(priceBpsForAmount(1_000_00, 0)).toBe(MIN_PRICE_BPS);
    expect(priceBpsForAmount(20_000_00, 10_000_00)).toBe(MAX_PRICE_BPS);
  });
});

describe("previewSellerFee", () => {
  test("2% of the price, capped at 2% of the outstanding principal, zero at a zero price", () => {
    expect(previewSellerFee(9_500_00, 10_000_00)).toBe(190_00);
    expect(previewSellerFee(10_200_00, 10_000_00)).toBe(200_00);
    expect(previewSellerFee(0, 10_000_00)).toBe(0);
  });
});

describe("discountTone", () => {
  test("warns above a 10% discount and strongly from 20%, without blocking", () => {
    expect(discountTone(MAX_PRICE_BPS)).toBe("none");
    expect(discountTone(10_000)).toBe("none");
    expect(discountTone(9_000)).toBe("none");
    expect(discountTone(8_999)).toBe("caution");
    expect(discountTone(8_001)).toBe("caution");
    expect(discountTone(8_000)).toBe("high");
    expect(discountTone(MIN_PRICE_BPS)).toBe("high");
  });
});
