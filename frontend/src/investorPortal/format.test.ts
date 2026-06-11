import { describe, expect, test } from "vitest";

import {
  formatMoneyMinor,
  minorUnitDecimalsForCurrency,
  parseMoneyInputToMinorUnits
} from "./format";

describe("money formatting", () => {
  test("formats launch currencies from integer minor units", () => {
    expect(formatMoneyMinor(123456, "CHF")).toBe("1'234.56");
    expect(formatMoneyMinor(123456, "EUR")).toBe("1'234.56");
  });

  test("uses currency minor-unit precision for non-2-decimal currencies", () => {
    expect(minorUnitDecimalsForCurrency("JPY")).toBe(0);
    expect(minorUnitDecimalsForCurrency("KWD")).toBe(3);
    expect(formatMoneyMinor(1234, "JPY")).toBe("1'234");
    expect(formatMoneyMinor(1234, "KWD")).toBe("1.234");
  });
});

describe("money input parsing", () => {
  test("parses decimal strings without float multiplication", () => {
    expect(parseMoneyInputToMinorUnits("1000.50", "CHF")).toEqual({
      amountMinor: 100050,
      error: undefined
    });
    expect(parseMoneyInputToMinorUnits(".50", "EUR")).toEqual({
      amountMinor: 50,
      error: undefined
    });
  });

  test("rejects malformed and over-precision amounts", () => {
    expect(parseMoneyInputToMinorUnits("100.999", "CHF")).toEqual({
      amountMinor: 0,
      error: "CHF amounts support at most 2 decimal places."
    });
    expect(parseMoneyInputToMinorUnits("12..3", "EUR")).toEqual({
      amountMinor: 0,
      error: "Enter a valid amount."
    });
  });
});
