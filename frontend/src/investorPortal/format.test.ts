import { describe, expect, test } from "vitest";

import {
  formatMoneyLabel,
  formatMoneyMinor,
  formatRateBps,
  formatWholeAmount,
  humanizeEnum,
  minorUnitDecimalsForCurrency,
  parseMoneyInputToMinorUnits,
  pluralize,
  zurichDateKey
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

describe("money input separators (audit A-40 / UIUX-04 / FRONTCODE-19)", () => {
  test("keeps the decimal comma instead of dropping it", () => {
    expect(parseMoneyInputToMinorUnits("1500,50", "EUR")).toEqual({ amountMinor: 150050, error: undefined });
    expect(parseMoneyInputToMinorUnits("10,5", "CHF")).toEqual({ amountMinor: 1050, error: undefined });
  });

  test("accepts the app's own thousands separators and spaces", () => {
    for (const input of ["1'500.50", "1\u2019500.50", "1 500.50", "1\u2009500.50", "1\u202f500,50", " 1'500.50 "]) {
      expect(parseMoneyInputToMinorUnits(input, "CHF")).toEqual({ amountMinor: 150050, error: undefined });
    }
  });

  test("a formatted amount parses back to the same minor units", () => {
    for (const minor of [0, 5, 100050, 500_000_000, 123_456_789]) {
      expect(parseMoneyInputToMinorUnits(formatMoneyMinor(minor, "CHF"), "CHF")).toEqual({ amountMinor: minor, error: undefined });
    }
  });

  test("refuses ambiguous separators with a clear message", () => {
    expect(parseMoneyInputToMinorUnits("1,000", "CHF").error).toBe(
      "CHF amounts support at most 2 decimal places. A comma is the decimal sign. Write thousands as 1'000."
    );
    expect(parseMoneyInputToMinorUnits("1.000,50", "EUR").error).toMatch(/^Enter a valid amount\. Use one decimal sign/);
    expect(parseMoneyInputToMinorUnits("1,000.50", "EUR").error).toMatch(/^Enter a valid amount\. Use one decimal sign/);
    expect(parseMoneyInputToMinorUnits("1,000,000", "CHF").error).toBe("Enter a valid amount.");
    expect(parseMoneyInputToMinorUnits("-5", "CHF").error).toBe("Enter a valid amount.");
  });
});

describe("Zurich business dates", () => {
  test("formats ISO instants by Europe/Zurich calendar date", () => {
    expect(zurichDateKey("2026-07-14T22:00:00+00:00")).toBe("2026-07-15");
  });
});

describe("one money and rate format (audit A-64/item 9)", () => {
  test("money labels put the currency code first, Swiss apostrophes, currency minor units", () => {
    expect(formatMoneyLabel("EUR", 127_685)).toBe("EUR 1'276.85");
    expect(formatMoneyLabel("CHF", 489_803_689)).toBe("CHF 4'898'036.89");
    expect(formatMoneyLabel("CHF", -5)).toBe("CHF -0.05");
    expect(formatMoneyLabel("JPY", 1_234_567)).toBe("JPY 1'234'567");
    expect(formatWholeAmount("CHF", 10_000_000)).toBe("CHF 100'000");
  });

  test("rates keep the basis points: two decimals unless the rate is a whole tenth", () => {
    expect(formatRateBps(845)).toBe("8.45%");
    expect(formatRateBps(725)).toBe("7.25%");
    expect(formatRateBps(800)).toBe("8.0%");
    expect(formatRateBps(750)).toBe("7.5%");
    expect(formatRateBps(100)).toBe("1.0%");
    expect(formatRateBps(5)).toBe("0.05%");
  });

  test("copy helpers", () => {
    expect(pluralize(1, "document")).toBe("1 document");
    expect(pluralize(2, "month")).toBe("2 months");
    expect(humanizeEnum("penalty_mode")).toBe("Penalty mode");
  });
});
