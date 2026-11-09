// IP of Webby-Soft SRL.
// Smart Invest preferences of the U33 wizard, limited to the criteria the backend applies today
// (currency, minimum yield, maximum term, security types, originator). The rule never carries risk
// ratings, purposes or loan kinds (U33-DEC-16/19): they are saved empty. LTV, repayment, country,
// usual amount, channels and Pause come with Phase 17.2 (U33-DEC-19).
import {
  SmartInvestCollateralEnum,
  type MarketplaceLoanPreview,
  type SmartInvestCurrencyEnum,
  type SmartInvestOpportunity,
  type SmartInvestResponse,
  type SmartInvestRule,
  type SmartInvestRuleSaveRequest
} from "../../../../api/generated/banxumApi";
import { ALL_SECURED_TYPES } from "./labels";

export const SMART_CURRENCIES = ["EUR", "CHF"] as const;
/** The Smart-Invest token of Banxum's direct loans in the originator list. */
export const BANXUM_SOURCE = "banxum";
const ANY_SECURED = SmartInvestCollateralEnum.any_secured as string;
const UNSECURED = SmartInvestCollateralEnum.unsecured as string;

export type SmartPreferences = {
  currencies: string[];
  /** Percent, e.g. 7.5; null = no preference. */
  minRate: number | null;
  /** Months; null = no preference. */
  maxTerm: number | null;
  /** Selected security types; null = no preference. "unsecured" only when an older rule had it. */
  security: string[] | null;
  /** Originator sources (BANXUM_SOURCE or Loan Originator ids); empty = no preference. */
  originators: string[];
};

export const DEFAULT_PREFERENCES: SmartPreferences = { currencies: [...SMART_CURRENCIES], minRate: null, maxTerm: null, security: null, originators: [] };

/** Criteria the U33 preferences no longer offer, still saved in an older rule (saving removes them). */
export function retiredCriteria(rule: SmartInvestRule | null | undefined) {
  if (!rule?.is_active) return [];
  return [
    rule.risk_ratings.length > 0 ? "risk" : "",
    rule.purposes.length > 0 ? "purpose" : "",
    rule.loan_kinds.length > 0 ? "kind" : ""
  ].filter(Boolean);
}

export function preferencesFromRule(rule: SmartInvestRule | null | undefined): SmartPreferences {
  if (!rule?.is_active) return { ...DEFAULT_PREFERENCES, currencies: [...SMART_CURRENCIES] };
  const collateral = rule.collateral as string[];
  let security: string[] | null = null;
  if (collateral.length > 0) {
    const types = collateral.includes(ANY_SECURED) ? [...ALL_SECURED_TYPES] : collateral.filter((value) => value !== UNSECURED);
    security = collateral.includes(UNSECURED) ? [...types, UNSECURED] : types;
  }
  return {
    currencies: rule.currencies.length > 0 ? [...rule.currencies] : [...SMART_CURRENCIES],
    minRate: rule.minimum_yield_bps === null ? null : rule.minimum_yield_bps / 100,
    maxTerm: rule.maximum_term_months,
    security,
    originators: [...rule.originators]
  };
}

function collateralList(security: string[] | null) {
  if (security === null) return [];
  const secured = security.filter((value) => value !== UNSECURED);
  const everySecured = ALL_SECURED_TYPES.every((type) => secured.includes(type));
  // Every secured type ticked: "any_secured" also covers security types added later.
  const base = everySecured ? [ANY_SECURED, ...secured.filter((type) => !ALL_SECURED_TYPES.includes(type))] : secured;
  return security.includes(UNSECURED) ? [...base, UNSECURED] : base;
}

export function requestFromPreferences(preferences: SmartPreferences): SmartInvestRuleSaveRequest {
  return {
    minimum_yield_bps: preferences.minRate === null ? null : Math.round(preferences.minRate * 100),
    maximum_term_months: preferences.maxTerm,
    originators: [...preferences.originators],
    collateral: collateralList(preferences.security) as SmartInvestCollateralEnum[],
    currencies: [...preferences.currencies] as SmartInvestCurrencyEnum[],
    // U33-DEC-16/19: never sent; an older rule's values are removed by saving.
    risk_ratings: [],
    purposes: [],
    loan_kinds: []
  };
}

/**
 * The backend refuses a rule without any effective criterion (smart_invest.services
 * _has_effective_criterion): at least one limit beyond "both currencies, no preference".
 */
export function hasEffectiveCriterion(preferences: SmartPreferences) {
  const collateral = collateralList(preferences.security);
  const everyCollateralOption = (Object.values(SmartInvestCollateralEnum) as string[]).every((option) => collateral.includes(option));
  return (
    preferences.minRate !== null ||
    preferences.maxTerm !== null ||
    preferences.originators.length > 0 ||
    (collateral.length > 0 && !everyCollateralOption) ||
    (preferences.currencies.length > 0 && !SMART_CURRENCIES.every((code) => preferences.currencies.includes(code)))
  );
}

type Matchable = Pick<MarketplaceLoanPreview, "yield_bps" | "interest_rate_bps" | "term_months" | "product_type" | "originator_id" | "collateral_type" | "ltv_bps" | "currency">;

/** The backend's matching rule (opportunity_matches_criteria), for the live counts of the wizard. */
export function matchesPreferences(opportunity: Matchable, preferences: SmartPreferences) {
  const yieldBps = opportunity.yield_bps || opportunity.interest_rate_bps;
  if (preferences.minRate !== null && yieldBps < Math.round(preferences.minRate * 100)) return false;
  if (preferences.maxTerm !== null && opportunity.term_months > preferences.maxTerm) return false;
  if (preferences.originators.length > 0) {
    const source = opportunity.product_type === "originator_claim" ? opportunity.originator_id ?? "" : BANXUM_SOURCE;
    if (!preferences.originators.includes(source)) return false;
  }
  const collateral = collateralList(preferences.security);
  if (collateral.length > 0) {
    const unsecured = /unsecured/i.test(opportunity.collateral_type) || opportunity.ltv_bps === null;
    const matches = unsecured ? collateral.includes(UNSECURED) : collateral.includes(ANY_SECURED) || collateral.includes(opportunity.collateral_type);
    if (!matches) return false;
  }
  if (preferences.currencies.length > 0 && !preferences.currencies.includes(opportunity.currency)) return false;
  return true;
}

/** Open for new investments now, with capacity left (marketplace_payload_has_capacity). */
export function isOpenOpportunity(loan: Pick<MarketplaceLoanPreview, "status" | "opportunity_status" | "fillable_amount_minor" | "remaining_capacity_minor">) {
  const open = ["open", "published"].includes(loan.status) || loan.opportunity_status === "open";
  return open && (loan.fillable_amount_minor ?? loan.remaining_capacity_minor) > 0;
}

function asOpportunity(loan: MarketplaceLoanPreview): SmartInvestOpportunity {
  return {
    loan_id: loan.loan_id,
    product_type: loan.product_type,
    investment_flow: loan.investment_flow,
    title: loan.title,
    purpose: loan.purpose,
    collateral_type: loan.collateral_type,
    interest_rate_bps: loan.interest_rate_bps,
    yield_bps: loan.yield_bps,
    underlying_interest_rate_bps: loan.underlying_interest_rate_bps,
    term_months: loan.term_months,
    remaining_term_days: loan.remaining_term_days,
    risk_rating: loan.risk_rating,
    funding_deadline: loan.funding_deadline,
    maturity_date: loan.maturity_date,
    status: loan.status,
    loan_status: loan.loan_status,
    opportunity_status: loan.opportunity_status,
    currency: loan.currency,
    principal_minor: loan.principal_minor,
    committed_principal_minor: loan.committed_principal_minor,
    remaining_capacity_minor: loan.remaining_capacity_minor,
    fillable_amount_minor: loan.fillable_amount_minor,
    minimum_investment_minor: loan.minimum_investment_minor,
    ltv_bps: loan.ltv_bps,
    is_refinancing: loan.is_refinancing,
    originator_id: loan.originator_id,
    originator_name: loan.originator_name,
    borrower_display_name: loan.borrower_display_name,
    skin_in_the_game_bps: loan.skin_in_the_game_bps,
    minimum_subscription_bps: loan.minimum_subscription_bps
  };
}

/** Preview mode only (no server): the answer the server would give after saving these preferences. */
export function previewResponse(preferences: SmartPreferences, loans: MarketplaceLoanPreview[], previous: SmartInvestRule | null | undefined): SmartInvestResponse {
  const open = loans.filter(isOpenOpportunity);
  const matches = open.filter((loan) => matchesPreferences(loan, preferences)).map(asOpportunity);
  const request = requestFromPreferences(preferences);
  const now = new Date().toISOString();
  return {
    rule: {
      id: previous?.id ?? "smart-invest-rule-preview",
      is_active: true,
      revision: (previous?.revision ?? 0) + 1,
      minimum_yield_bps: request.minimum_yield_bps ?? null,
      maximum_term_months: request.maximum_term_months ?? null,
      originators: request.originators ?? [],
      collateral: request.collateral ?? [],
      currencies: request.currencies ?? [],
      risk_ratings: [],
      purposes: [],
      loan_kinds: [],
      activated_at: previous?.activated_at ?? now,
      deactivated_at: null,
      created_at: previous?.created_at ?? now,
      updated_at: now
    },
    match_count: matches.length,
    open_opportunity_count: open.length,
    matches
  };
}

/** Preview mode only: the answer after "Switch off" (the backend clears the rule). */
export function previewSwitchedOff(previous: SmartInvestRule | null | undefined, loans: MarketplaceLoanPreview[]): SmartInvestResponse {
  const now = new Date().toISOString();
  return {
    rule: previous
      ? { ...previous, is_active: false, revision: previous.revision + 1, minimum_yield_bps: null, maximum_term_months: null, originators: [], collateral: [], currencies: [], risk_ratings: [], purposes: [], loan_kinds: [], deactivated_at: now, updated_at: now }
      : null,
    match_count: 0,
    open_opportunity_count: loans.filter(isOpenOpportunity).length,
    matches: []
  };
}
