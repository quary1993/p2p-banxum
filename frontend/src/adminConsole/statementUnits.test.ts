// IP of Webby-Soft SRL.
import { describe, expect, it } from "vitest";

import { financialYearCheckResults, minorToUnits, unitsToMinor } from "./statementUnits";

describe("statement figures in currency units", () => {
  it("converts units to minor units without guessing", () => {
    expect(unitsToMinor("1250000", "CHF")).toBe(125_000_000);
    expect(unitsToMinor("1250000.5", "CHF")).toBe(125_000_050);
    expect(unitsToMinor("-30000.25", "EUR")).toBe(-3_000_025);
    for (const wrong of ["1'250'000", "1 250 000", "1,5", "1.234.56", "12.345", "", "abc"]) {
      expect(unitsToMinor(wrong, "CHF")).toBeNull();
    }
  });

  it("shows stored minor units as plain units", () => {
    expect(minorToUnits(125_000_050, "CHF")).toBe("1250000.5");
    expect(minorToUnits(125_000_000, "CHF")).toBe("1250000");
    expect(minorToUnits(-3_000_025, "EUR")).toBe("-30000.25");
    expect(minorToUnits(null, "CHF")).toBe("");
  });

  it("checks each total against its parts once all are filled", () => {
    const results = financialYearCheckResults({
      revenue_minor: 1000,
      materials_costs_minor: 300,
      staff_costs_minor: 200,
      other_operating_costs_minor: 100,
      depreciation_minor: 50,
      operating_profit_minor: 300,
      cash_minor: 10,
      trade_receivables_minor: null,
      current_assets_minor: 99
    });
    // Operating profit: 1000 - 650 = 350, not 300. Current assets are skipped (a part is empty).
    expect(results).toEqual([{ label: "Revenue less operating costs = operating profit", computed: 350, total: 300, ok: false }]);
  });
});
