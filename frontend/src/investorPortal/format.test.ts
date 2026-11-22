// IP of Webby-Soft SRL.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  activeNumberFormatStyle,
  formatAmountInput,
  formatDecimal,
  formatMoneyLabel,
  formatMoneyMinor,
  formatPercent,
  formatRateBps,
  formatWholeAmount,
  humanizeEnum,
  minorUnitDecimalsForCurrency,
  parseMoneyInputToMinorUnits,
  pluralize,
  readNumberFormatPreference,
  resetNumberFormatForTests,
  useNumberFormat,
  useNumberFormatScope,
  zurichDateKey
} from "./format";

beforeEach(() => {
  window.localStorage.clear();
  resetNumberFormatForTests();
});
afterEach(() => resetNumberFormatForTests());

describe("money formatting in the two U33 number formats (U33-DEC-32)", () => {
  test("European is 1.234,56 and Swiss is 1’234.56 with the typographic apostrophe", () => {
    expect(formatMoneyMinor(123456, "CHF", undefined, "european")).toBe("1.234,56");
    expect(formatMoneyMinor(123456, "EUR", undefined, "swiss")).toBe("1’234.56");
    expect(formatMoneyLabel("CHF", 489_803_689, "european")).toBe("CHF 4.898.036,89");
    expect(formatMoneyLabel("EUR", 127_685, "swiss")).toBe("EUR 1’276.85");
    expect(formatMoneyLabel("CHF", -5, "european")).toBe("CHF -0,05");
    expect(formatWholeAmount("CHF", 10_000_000, "european")).toBe("CHF 100.000");
  });

  test("uses currency minor-unit precision for non-2-decimal currencies", () => {
    expect(minorUnitDecimalsForCurrency("JPY")).toBe(0);
    expect(minorUnitDecimalsForCurrency("KWD")).toBe(3);
    expect(formatMoneyMinor(1234, "JPY", undefined, "european")).toBe("1.234");
    expect(formatMoneyMinor(1234, "KWD", undefined, "european")).toBe("1,234");
    expect(formatMoneyMinor(1234, "KWD", undefined, "swiss")).toBe("1.234");
  });

  test("outside the investor area the formatters keep the previous format (admin console)", () => {
    expect(activeNumberFormatStyle()).toBe("legacy");
    expect(formatMoneyLabel("EUR", 127_685)).toBe("EUR 1'276.85");
    expect(formatRateBps(845)).toBe("8.45%");
  });

  test("the investor shell scope applies the saved preference, European by default", () => {
    expect(readNumberFormatPreference()).toBe("european");
    const scope = renderHook(() => useNumberFormatScope());
    expect(activeNumberFormatStyle()).toBe("european");
    expect(formatMoneyLabel("CHF", 123456)).toBe("CHF 1.234,56");
    const hook = renderHook(() => useNumberFormat());
    act(() => hook.result.current.setFormat("swiss"));
    expect(window.localStorage.getItem("banxum.numberFormat")).toBe("swiss");
    expect(scope.result.current).toBe("swiss");
    expect(formatMoneyLabel("CHF", 123456)).toBe("CHF 1’234.56");
    scope.unmount();
    expect(activeNumberFormatStyle()).toBe("legacy");
  });

  test("a broken or missing preference falls back to European", () => {
    window.localStorage.setItem("banxum.numberFormat", "klingon");
    expect(readNumberFormatPreference()).toBe("european");
  });

  test("rates, percentages and plain numbers follow the format", () => {
    expect(formatRateBps(845, "european")).toBe("8,45%");
    expect(formatRateBps(750, "european")).toBe("7,5%");
    expect(formatRateBps(800, "swiss")).toBe("8.0%");
    expect(formatRateBps(5, "european")).toBe("0,05%");
    expect(formatPercent(12.345, 1, "european")).toBe("12,3%");
    expect(formatPercent(56.7, 1, "swiss")).toBe("56.7%");
    expect(formatDecimal(1234.5, 2, "european")).toBe("1.234,50");
    expect(formatDecimal(-0.001, 2, "swiss")).toBe("0.00");
  });

  test("amounts written back into a field have no grouping and the format's decimal sign", () => {
    expect(formatAmountInput(150050, "EUR", "european")).toBe("1500,50");
    expect(formatAmountInput(150050, "EUR", "swiss")).toBe("1500.50");
    expect(formatAmountInput(1234, "JPY", "european")).toBe("1234");
  });
});

describe("money input parsing follows the selected format and never guesses", () => {
  test("parses decimal strings without float multiplication", () => {
    expect(parseMoneyInputToMinorUnits("1000.50", "CHF", "swiss")).toEqual({ amountMinor: 100050, error: undefined });
    expect(parseMoneyInputToMinorUnits("1000,50", "CHF", "european")).toEqual({ amountMinor: 100050, error: undefined });
    expect(parseMoneyInputToMinorUnits(".50", "EUR", "swiss")).toEqual({ amountMinor: 50, error: undefined });
    expect(parseMoneyInputToMinorUnits("", "EUR", "european")).toEqual({ amountMinor: 0, error: undefined });
  });

  test("each format's own grouping is accepted", () => {
    expect(parseMoneyInputToMinorUnits("1.500,50", "EUR", "european").amountMinor).toBe(150050);
    expect(parseMoneyInputToMinorUnits("1.234.567", "EUR", "european").amountMinor).toBe(123456700);
    expect(parseMoneyInputToMinorUnits("1’500.50", "CHF", "swiss").amountMinor).toBe(150050);
    expect(parseMoneyInputToMinorUnits("1'500.50", "CHF", "swiss").amountMinor).toBe(150050);
  });

  test("spaces and apostrophes are thousands separators in every format", () => {
    for (const style of ["european", "swiss"] as const) {
      for (const input of ["1 500", "1 500", "1 500", " 1'500 ", "1’500"]) {
        expect(parseMoneyInputToMinorUnits(input, "CHF", style)).toEqual({ amountMinor: 150000, error: undefined });
      }
    }
    expect(parseMoneyInputToMinorUnits("1 500,50", "EUR", "european").amountMinor).toBe(150050);
    expect(parseMoneyInputToMinorUnits("1’500,50", "EUR", "swiss").amountMinor).toBe(150050);
  });

  test("an ambiguous point or comma follows the selected format", () => {
    // 1.234: European grouping (1234) or Swiss decimal (1.234).
    expect(parseMoneyInputToMinorUnits("1.234", "EUR", "european").amountMinor).toBe(123400);
    expect(parseMoneyInputToMinorUnits("1.234", "EUR", "swiss").error).toBe("EUR amounts support at most 2 decimal places. Write thousands as 1’000.");
    // 1,000 with the European format is 1,000 (one), refused for a 2-decimal currency with a hint.
    expect(parseMoneyInputToMinorUnits("1,000", "CHF", "european").error).toBe("CHF amounts support at most 2 decimal places. Write thousands as 1.000.");
  });

  test("a value valid only in another format is accepted when it has one reading", () => {
    expect(parseMoneyInputToMinorUnits("1500.50", "EUR", "european").amountMinor).toBe(150050);
    expect(parseMoneyInputToMinorUnits("1’500.50", "EUR", "european").amountMinor).toBe(150050);
    expect(parseMoneyInputToMinorUnits("1.500,50", "CHF", "swiss").amountMinor).toBe(150050);
    expect(parseMoneyInputToMinorUnits("10,5", "CHF", "swiss").amountMinor).toBe(1050);
    expect(parseMoneyInputToMinorUnits("1,234.56", "EUR", "european").amountMinor).toBe(123456);
  });

  test("a value with two different readings is refused, not guessed", () => {
    // Swiss format: 1,234 is 1.234 (European decimal) or 1234 (English grouping).
    const result = parseMoneyInputToMinorUnits("1,234", "CHF", "swiss");
    expect(result.amountMinor).toBe(0);
    expect(result.ambiguous).toBe(true);
    expect(result.error).toBe("This amount can be read in two ways. Write it in your number format, for example 1’500.50.");
  });

  test("a formatted amount parses back to the same minor units in both formats", () => {
    for (const style of ["european", "swiss"] as const) {
      for (const minor of [0, 5, 100050, 500_000_000, 123_456_789]) {
        expect(parseMoneyInputToMinorUnits(formatMoneyMinor(minor, "CHF", undefined, style), "CHF", style)).toEqual({ amountMinor: minor, error: undefined });
        expect(parseMoneyInputToMinorUnits(formatAmountInput(minor, "CHF", style), "CHF", style)).toEqual({ amountMinor: minor, error: undefined });
      }
    }
  });

  test("rejects malformed, negative and over-precision amounts", () => {
    expect(parseMoneyInputToMinorUnits("100,999", "CHF", "european").error).toBe("CHF amounts support at most 2 decimal places. Write thousands as 1.000.");
    expect(parseMoneyInputToMinorUnits("100.9999", "CHF", "swiss").error).toBe("CHF amounts support at most 2 decimal places.");
    expect(parseMoneyInputToMinorUnits("12..3", "EUR", "european").error).toBe("Enter a valid amount.");
    expect(parseMoneyInputToMinorUnits("1.000,50.2", "EUR", "european").error).toBe("Enter a valid amount.");
    expect(parseMoneyInputToMinorUnits("1'5'00", "EUR", "swiss").error).toBe("Enter a valid amount.");
    expect(parseMoneyInputToMinorUnits("-5", "CHF", "swiss").error).toBe("Enter a valid amount.");
    expect(parseMoneyInputToMinorUnits("12e3", "CHF", "swiss").error).toBe("Enter a valid amount.");
    expect(parseMoneyInputToMinorUnits("1,5", "JPY", "european").error).toBe("JPY amounts must be whole units.");
  });
});

describe("Zurich business dates", () => {
  test("formats ISO instants by Europe/Zurich calendar date", () => {
    expect(zurichDateKey("2026-07-14T22:00:00+00:00")).toBe("2026-07-15");
  });
});

describe("copy helpers", () => {
  test("plural and enum labels", () => {
    expect(pluralize(1, "document")).toBe("1 document");
    expect(pluralize(2, "month")).toBe("2 months");
    expect(humanizeEnum("penalty_mode")).toBe("Penalty mode");
  });
});
