// IP of Webby-Soft SRL.
// Smart Invest preferences of the U33 wizard (U33-DEC-19): currency, minimum yield, maximum term,
// security types, maximum loan-to-value, borrower country, originator and the optional usual amount.
// No risk ratings, purposes or loan kinds (U33-DEC-16/19). Repayment groups wait for U33-DEC-11 and
// the app/email channels for U33-DEC-30. A paused rule keeps its preferences.
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
  /** Maximum loan-to-value in percent, e.g. 65; null = no preference. */
  maxLtv: number | null;
  /** Originator sources (BANXUM_SOURCE or Loan Originator ids); empty = no preference. */
  originators: string[];
  /** Borrower countries as the opportunities carry them; empty = no preference. */
  countries: string[];
  /** Usual amount per investment in each selected currency (major units); null = choose each time. */
  preferredAmount: number | null;
};

export const DEFAULT_PREFERENCES: SmartPreferences = {
  currencies: [...SMART_CURRENCIES],
  minRate: null,
  maxTerm: null,
  security: null,
  maxLtv: null,
  originators: [],
  countries: [],
  preferredAmount: null
};

export type SmartState = "not_set_up" | "active" | "paused";

/** U33-DEC-19 state of the saved rule: active, paused (preferences kept) or not set up. */
export function smartState(rule: SmartInvestRule | null | undefined): SmartState {
  if (!rule) return "not_set_up";
  return rule.state;
}

export function preferencesFromRule(rule: SmartInvestRule | null | undefined): SmartPreferences {
  if (smartState(rule) === "not_set_up" || !rule) return { ...DEFAULT_PREFERENCES, currencies: [...SMART_CURRENCIES] };
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
    maxLtv: rule.maximum_ltv_bps === null ? null : rule.maximum_ltv_bps / 100,
    originators: [...rule.originators],
    countries: [...rule.countries],
    preferredAmount: rule.preferred_amount_minor === null ? null : rule.preferred_amount_minor / 100
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
    maximum_ltv_bps: preferences.maxLtv === null ? null : Math.round(preferences.maxLtv * 100),
    countries: [...preferences.countries],
    preferred_amount_minor: preferences.preferredAmount === null ? null : Math.round(preferences.preferredAmount * 100)
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
    preferences.maxLtv !== null ||
    preferences.countries.length > 0 ||
    preferences.originators.length > 0 ||
    (collateral.length > 0 && !everyCollateralOption) ||
    (preferences.currencies.length > 0 && !SMART_CURRENCIES.every((code) => preferences.currencies.includes(code)))
  );
}

type Matchable = Pick<MarketplaceLoanPreview, "yield_bps" | "interest_rate_bps" | "term_months" | "product_type" | "originator_id" | "collateral_type" | "ltv_bps" | "currency" | "borrower_country">;

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
  // Without a loan-to-value figure the limit cannot be checked: no match (as the backend).
  if (preferences.maxLtv !== null && (opportunity.ltv_bps === null || opportunity.ltv_bps > Math.round(preferences.maxLtv * 100))) return false;
  if (preferences.currencies.length > 0 && !preferences.currencies.includes(opportunity.currency)) return false;
  if (preferences.countries.length > 0) {
    const country = (opportunity.borrower_country ?? "").toLowerCase();
    if (!preferences.countries.some((value) => value.toLowerCase() === country)) return false;
  }
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
    borrower_country: loan.borrower_country,
    borrower_city: loan.borrower_city,
    skin_in_the_game_bps: loan.skin_in_the_game_bps,
    minimum_subscription_bps: loan.minimum_subscription_bps
  };
}

/**
 * Preview mode only (no server): the answer the server would give after saving these preferences.
 * As the backend, saving keeps a paused rule paused (U33-DEC-19); a new set-up is active.
 */
export function previewResponse(preferences: SmartPreferences, loans: MarketplaceLoanPreview[], previous: SmartInvestRule | null | undefined, active = smartState(previous) !== "paused"): SmartInvestResponse {
  const open = loans.filter(isOpenOpportunity);
  const matches = active ? open.filter((loan) => matchesPreferences(loan, preferences)).map(asOpportunity) : [];
  const request = requestFromPreferences(preferences);
  const now = new Date().toISOString();
  return {
    rule: {
      id: previous?.id ?? "smart-invest-rule-preview",
      is_active: active,
      state: active ? "active" : "paused",
      revision: (previous?.revision ?? 0) + 1,
      minimum_yield_bps: request.minimum_yield_bps ?? null,
      maximum_term_months: request.maximum_term_months ?? null,
      maximum_ltv_bps: request.maximum_ltv_bps ?? null,
      preferred_amount_minor: request.preferred_amount_minor ?? null,
      originators: request.originators ?? [],
      collateral: request.collateral ?? [],
      currencies: request.currencies ?? [],
      countries: request.countries ?? [],
      activated_at: active ? now : previous?.activated_at ?? null,
      deactivated_at: active ? null : previous?.deactivated_at ?? now,
      created_at: previous?.created_at ?? now,
      updated_at: now
    },
    match_count: matches.length,
    open_opportunity_count: open.length,
    matches
  };
}

/** Preview mode only: the answer after "Pause Smart Invest" (the preferences stay, no matches). */
export function previewPaused(previous: SmartInvestRule | null | undefined, loans: MarketplaceLoanPreview[]): SmartInvestResponse {
  return previewResponse(preferencesFromRule(previous), loans, previous, false);
}

/** Preview mode only: the answer after "Resume Smart Invest" (the matches are calculated anew). */
export function previewResumed(previous: SmartInvestRule | null | undefined, loans: MarketplaceLoanPreview[]): SmartInvestResponse {
  return previewResponse(preferencesFromRule(previous), loans, previous, true);
}
