// IP of Webby-Soft SRL.
// Smart Invest preferences of the U33 wizard: mapping to and from today's rule, the backend's
// "effective criterion" check and its matching rule (opportunity_matches_criteria).
import { describe, expect, test } from "vitest";

import type { SmartInvestRule } from "../../../../api/generated/banxumApi";
import { smartInvestFixture } from "../../../../investorPortal/fixtures";
import { ALL_SECURED_TYPES } from "./labels";
import {
  BANXUM_SOURCE,
  DEFAULT_PREFERENCES,
  hasEffectiveCriterion,
  matchesPreferences,
  preferencesFromRule,
  previewSwitchedOff,
  requestFromPreferences,
  retiredCriteria,
  type SmartPreferences
} from "./smartInvestModel";

const rule = smartInvestFixture.rule as SmartInvestRule;

const opportunity = {
  yield_bps: 900,
  interest_rate_bps: 900,
  term_months: 24,
  product_type: "direct",
  originator_id: null,
  collateral_type: "real_estate",
  ltv_bps: 5_000,
  currency: "CHF"
};

function preferences(overrides: Partial<SmartPreferences>): SmartPreferences {
  return { ...DEFAULT_PREFERENCES, currencies: ["EUR", "CHF"], ...overrides };
}

describe("rule mapping", () => {
  test("a saved rule becomes wizard preferences; any_secured ticks every security type", () => {
    expect(preferencesFromRule(rule)).toEqual({
      currencies: ["EUR", "CHF"],
      minRate: 8.5,
      maxTerm: 36,
      security: ALL_SECURED_TYPES,
      originators: []
    });
    expect(preferencesFromRule(null)).toEqual(preferences({}));
  });

  test("every secured type is saved as any_secured, and retired criteria are never sent", () => {
    const request = requestFromPreferences(preferences({ minRate: 7.25, security: [...ALL_SECURED_TYPES], currencies: ["CHF"] }));
    expect(request).toMatchObject({
      minimum_yield_bps: 725,
      maximum_term_months: null,
      collateral: ["any_secured"],
      currencies: ["CHF"],
      risk_ratings: [],
      purposes: [],
      loan_kinds: []
    });
    expect(requestFromPreferences(preferences({ security: ["real_estate", "corporate_guarantee"] })).collateral).toEqual(["real_estate", "corporate_guarantee"]);
  });

  test("risk rating, purpose or loan type in an older rule are reported as retired", () => {
    expect(retiredCriteria(rule)).toEqual([]);
    expect(retiredCriteria({ ...rule, risk_ratings: ["A"], purposes: ["working_capital"] })).toEqual(["risk", "purpose"]);
    expect(retiredCriteria({ ...rule, is_active: false, risk_ratings: ["A"] })).toEqual([]);
  });

  test("switching off clears the rule (no Pause today)", () => {
    const response = previewSwitchedOff(rule, []);
    expect(response.rule).toMatchObject({ is_active: false, minimum_yield_bps: null, maximum_term_months: null, collateral: [], currencies: [] });
    expect(response.matches).toEqual([]);
  });
});

describe("effective criterion", () => {
  test("both currencies with no other preference is refused, like the backend", () => {
    expect(hasEffectiveCriterion(preferences({}))).toBe(false);
    expect(hasEffectiveCriterion(preferences({ currencies: ["CHF", "EUR"], security: null, originators: [] }))).toBe(false);
  });

  test("one currency, a rate, a term, a security type or an originator is enough", () => {
    expect(hasEffectiveCriterion(preferences({ currencies: ["CHF"] }))).toBe(true);
    expect(hasEffectiveCriterion(preferences({ minRate: 6 }))).toBe(true);
    expect(hasEffectiveCriterion(preferences({ maxTerm: 12 }))).toBe(true);
    expect(hasEffectiveCriterion(preferences({ security: [...ALL_SECURED_TYPES] }))).toBe(true);
    expect(hasEffectiveCriterion(preferences({ originators: [BANXUM_SOURCE] }))).toBe(true);
  });
});

describe("matching", () => {
  test("rate, term, currency and source must all match", () => {
    expect(matchesPreferences(opportunity, preferences({ minRate: 9, maxTerm: 24 }))).toBe(true);
    expect(matchesPreferences(opportunity, preferences({ minRate: 9.5 }))).toBe(false);
    expect(matchesPreferences(opportunity, preferences({ maxTerm: 12 }))).toBe(false);
    expect(matchesPreferences(opportunity, preferences({ currencies: ["EUR"] }))).toBe(false);
    // Banxum's direct loans are the "banxum" source; originator claims match their originator.
    expect(matchesPreferences(opportunity, preferences({ originators: [BANXUM_SOURCE] }))).toBe(true);
    expect(matchesPreferences({ ...opportunity, product_type: "originator_claim", originator_id: "lo-1" }, preferences({ originators: ["lo-1"] }))).toBe(true);
    expect(matchesPreferences({ ...opportunity, product_type: "originator_claim", originator_id: "lo-2" }, preferences({ originators: ["lo-1", BANXUM_SOURCE] }))).toBe(false);
  });

  test("one matching security type is enough; a loan without LTV counts as unsecured", () => {
    expect(matchesPreferences(opportunity, preferences({ security: ["equipment", "real_estate"] }))).toBe(true);
    expect(matchesPreferences(opportunity, preferences({ security: ["equipment"] }))).toBe(false);
    expect(matchesPreferences(opportunity, preferences({ security: [...ALL_SECURED_TYPES] }))).toBe(true);
    expect(matchesPreferences({ ...opportunity, ltv_bps: null }, preferences({ security: [...ALL_SECURED_TYPES] }))).toBe(false);
  });
});
