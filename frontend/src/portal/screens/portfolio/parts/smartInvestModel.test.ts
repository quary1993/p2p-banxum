// IP of Webby-Soft SRL.
// Smart Invest preferences of the U33 wizard: mapping to and from today's rule, the backend's
// "effective criterion" check and its matching rule (opportunity_matches_criteria).
import { describe, expect, test } from "vitest";

import type { MarketplaceLoanPreview, SmartInvestRule } from "../../../../api/generated/banxumApi";
import { marketplaceLoansFixture, smartInvestFixture } from "../../../../investorPortal/fixtures";
import { ALL_SECURED_TYPES } from "./labels";
import {
  BANXUM_SOURCE,
  DEFAULT_PREFERENCES,
  hasEffectiveCriterion,
  matchesPreferences,
  preferencesFromRule,
  previewPaused,
  previewResponse,
  previewResumed,
  requestFromPreferences,
  smartState,
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
  currency: "CHF",
  borrower_country: "CH"
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
      maxLtv: null,
      originators: [],
      countries: [],
      preferredAmount: null
    });
    expect(preferencesFromRule(null)).toEqual(preferences({}));
    // A paused rule keeps its preferences for editing (U33-DEC-19).
    expect(preferencesFromRule({ ...rule, is_active: false, state: "paused" }).minRate).toBe(8.5);
  });

  test("every secured type is saved as any_secured; LTV, countries and the usual amount are sent", () => {
    const request = requestFromPreferences(preferences({ minRate: 7.25, security: [...ALL_SECURED_TYPES], currencies: ["CHF"], maxLtv: 65, countries: ["CH"], preferredAmount: 1000.5 }));
    expect(request).toEqual({
      minimum_yield_bps: 725,
      maximum_term_months: null,
      originators: [],
      collateral: ["any_secured"],
      currencies: ["CHF"],
      maximum_ltv_bps: 6500,
      countries: ["CH"],
      preferred_amount_minor: 100050
    });
    expect(requestFromPreferences(preferences({ security: ["real_estate", "corporate_guarantee"] })).collateral).toEqual(["real_estate", "corporate_guarantee"]);
  });

  test("pause keeps the preferences and shows no matches; resume calculates them again", () => {
    const loan = { ...smartInvestFixture.matches[0] } as never;
    const paused = previewPaused(rule, [loan]);
    expect(paused.rule).toMatchObject({ is_active: false, state: "paused", minimum_yield_bps: 850, maximum_term_months: 36 });
    expect(paused.matches).toEqual([]);
    expect(smartState(paused.rule)).toBe("paused");
    // Saving while paused stays paused, like the backend.
    expect(previewResponse(preferences({ minRate: 9 }), [loan], paused.rule).rule?.state).toBe("paused");
    const resumed = previewResumed(paused.rule, [loan]);
    expect(resumed.rule).toMatchObject({ is_active: true, state: "active", minimum_yield_bps: 850 });
    expect(smartState(null)).toBe("not_set_up");
  });

  test("Coming soon matches are kept apart from the open matches and their count (U33-DEC-17)", () => {
    const published = marketplaceLoansFixture.find((loan) => loan.loan_id === "GA-2399") as MarketplaceLoanPreview;
    const soon: MarketplaceLoanPreview = { ...published, loan_id: "soon-1", status: "draft", loan_status: "draft", opportunity_status: "coming_soon", planned_opening_date: "2026-12-01" };
    const active = previewResponse(preferences({ minRate: 5 }), [published, soon], null);
    expect(active.matches.map((match) => match.loan_id)).toEqual(["GA-2399"]);
    expect(active.match_count).toBe(1);
    expect(active.coming_soon_matches.map((match) => [match.loan_id, match.planned_opening_date])).toEqual([["soon-1", "2026-12-01"]]);
    expect(previewPaused(active.rule, [published, soon]).coming_soon_matches).toEqual([]);
  });
});

describe("effective criterion", () => {
  test("both currencies with no other preference is refused, like the backend", () => {
    expect(hasEffectiveCriterion(preferences({}))).toBe(false);
    expect(hasEffectiveCriterion(preferences({ currencies: ["CHF", "EUR"], security: null, originators: [] }))).toBe(false);
  });

  test("the usual amount alone never limits the matches", () => {
    expect(hasEffectiveCriterion(preferences({ preferredAmount: 500 }))).toBe(false);
  });

  test("one currency, a rate, a term, a security type, an LTV, a country or an originator is enough", () => {
    expect(hasEffectiveCriterion(preferences({ maxLtv: 70 }))).toBe(true);
    expect(hasEffectiveCriterion(preferences({ countries: ["CH"] }))).toBe(true);
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

describe("loan-to-value, country and usual amount", () => {
  test("a loan above the LTV limit or without an LTV figure does not match", () => {
    expect(matchesPreferences(opportunity, preferences({ maxLtv: 50 }))).toBe(true);
    expect(matchesPreferences(opportunity, preferences({ maxLtv: 49.9 }))).toBe(false);
    expect(matchesPreferences({ ...opportunity, ltv_bps: null }, preferences({ maxLtv: 80 }))).toBe(false);
  });

  test("countries compare without letter case; the usual amount never excludes a match", () => {
    expect(matchesPreferences(opportunity, preferences({ countries: ["ch"] }))).toBe(true);
    expect(matchesPreferences(opportunity, preferences({ countries: ["RO"] }))).toBe(false);
    expect(matchesPreferences(opportunity, preferences({ preferredAmount: 1_000_000 }))).toBe(true);
  });
});
