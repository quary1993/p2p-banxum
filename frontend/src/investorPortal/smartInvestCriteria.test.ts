import { describe, expect, test } from "vitest";

import type { SmartInvestRule } from "../api/generated/banxumApi";
import {
  hasSmartInvestCriteria,
  mkCollateralMatches,
  mkDefaultFilters,
  mkListSummary,
  mkToggle,
  smartInvestFiltersFromRule,
  smartInvestRequestFromFilters
} from "./smartInvestCriteria";

const activeRule: SmartInvestRule = {
  id: "rule-1",
  is_active: true,
  revision: 4,
  minimum_yield_bps: 850,
  maximum_term_months: 24,
  originators: ["banxum", "8d8f43a5-6f0e-4b5e-a8e0-55c1f0b1e2d3"],
  collateral: ["real_estate", "equipment", "unsecured"],
  currencies: ["CHF", "EUR"],
  risk_ratings: ["A", "A-"],
  purposes: ["working_capital"],
  loan_kinds: ["new"],
  activated_at: "2026-10-01T10:00:00Z",
  deactivated_at: null,
  created_at: "2026-10-01T10:00:00Z",
  updated_at: "2026-10-01T10:00:00Z"
};

describe("Smart Invest multi-select criteria", () => {
  test("a saved rule round-trips through the filters into the same request", () => {
    const filters = smartInvestFiltersFromRule(activeRule);
    expect(filters.rating).toEqual(["A", "A-"]);
    expect(filters.ccy).toEqual(["CHF", "EUR"]);
    expect(smartInvestRequestFromFilters(filters)).toEqual({
      minimum_yield_bps: 850,
      maximum_term_months: 24,
      originators: ["banxum", "8d8f43a5-6f0e-4b5e-a8e0-55c1f0b1e2d3"],
      collateral: ["real_estate", "equipment", "unsecured"],
      currencies: ["CHF", "EUR"],
      risk_ratings: ["A", "A-"],
      purposes: ["working_capital"],
      loan_kinds: ["new"]
    });
    expect(smartInvestFiltersFromRule({ ...activeRule, is_active: false })).toEqual(mkDefaultFilters);
  });

  test("any collateral replaces the individual collateral types it includes", () => {
    const request = smartInvestRequestFromFilters({
      ...mkDefaultFilters,
      col: ["real_estate", "any_secured", "unsecured"]
    });
    expect(request.collateral).toEqual(["any_secured", "unsecured"]);
  });

  test("an empty list or a list with every option is not a criterion", () => {
    expect(hasSmartInvestCriteria(mkDefaultFilters)).toBe(false);
    expect(hasSmartInvestCriteria({ ...mkDefaultFilters, ccy: ["CHF", "EUR"] })).toBe(false);
    expect(hasSmartInvestCriteria({ ...mkDefaultFilters, kind: ["refinancing", "new"] })).toBe(false);
    expect(hasSmartInvestCriteria({ ...mkDefaultFilters, col: ["unsecured", "any_secured"] })).toBe(false);
    expect(hasSmartInvestCriteria({ ...mkDefaultFilters, ccy: ["EUR"] })).toBe(true);
    expect(hasSmartInvestCriteria({ ...mkDefaultFilters, rating: ["A", "A-"] })).toBe(true);
    expect(hasSmartInvestCriteria({ ...mkDefaultFilters, col: ["real_estate", "unsecured"] })).toBe(true);
    expect(hasSmartInvestCriteria({ ...mkDefaultFilters, orig: ["banxum"] })).toBe(true);
  });

  test("collateral matching treats any collateral, types and unsecured as alternatives", () => {
    const secured = { unsecured: false, collateralType: "real_estate" };
    const unsecured = { unsecured: true, collateralType: "unsecured_exception" };
    expect(mkCollateralMatches([], secured)).toBe(true);
    expect(mkCollateralMatches(["any_secured"], secured)).toBe(true);
    expect(mkCollateralMatches(["any_secured"], unsecured)).toBe(false);
    expect(mkCollateralMatches(["equipment", "real_estate"], secured)).toBe(true);
    expect(mkCollateralMatches(["equipment", "unsecured"], secured)).toBe(false);
    expect(mkCollateralMatches(["equipment", "unsecured"], unsecured)).toBe(true);
  });

  test("toggling and summaries", () => {
    expect(mkToggle(["A"], "A-")).toEqual(["A", "A-"]);
    expect(mkToggle(["A", "A-"], "A")).toEqual(["A-"]);
    expect(mkListSummary([], "Any rating")).toBe("Any rating");
    expect(mkListSummary(["A", "A-"], "Any rating")).toBe("A, A-");
    expect(mkListSummary(["AAA", "AA+", "AA", "AA-", "A+"], "Any rating")).toBe("AAA, AA+, AA +2 more");
  });
});
