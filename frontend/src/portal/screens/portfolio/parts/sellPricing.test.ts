// IP of Webby-Soft SRL.
// Listing price rules of the Sell investment dialog (today: par or a discount, whole basis points).
import { describe, expect, test } from "vitest";

import { discountTone, MAX_PRICE_BPS, MIN_PRICE_BPS, priceBpsForAmount } from "./sellPricing";

describe("priceBpsForAmount", () => {
  test("a typed amount becomes whole basis points of the outstanding principal", () => {
    expect(priceBpsForAmount(5_940_00, 6_000_00)).toBe(9_900);
    expect(priceBpsForAmount(6_000_00, 6_000_00)).toBe(MAX_PRICE_BPS);
    // 3.333,33 of 10.000,00 rounds to 33,33%.
    expect(priceBpsForAmount(3_333_33, 10_000_00)).toBe(3_333);
  });

  test("never below the lowest price the server accepts", () => {
    expect(priceBpsForAmount(1, 10_000_00)).toBe(MIN_PRICE_BPS);
    expect(priceBpsForAmount(1_000_00, 0)).toBe(MIN_PRICE_BPS);
  });
});

describe("discountTone", () => {
  test("warns above a 10% discount and strongly from 20%, without blocking", () => {
    expect(discountTone(10_000)).toBe("none");
    expect(discountTone(9_000)).toBe("none");
    expect(discountTone(8_999)).toBe("caution");
    expect(discountTone(8_001)).toBe("caution");
    expect(discountTone(8_000)).toBe("high");
    expect(discountTone(MIN_PRICE_BPS)).toBe("high");
  });
});
