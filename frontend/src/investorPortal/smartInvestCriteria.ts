import {
  PurposeEnum,
  RiskRatingEnum,
  SmartInvestCollateralEnum,
  SmartInvestCurrencyEnum,
  SmartInvestLoanKindEnum
} from "../api/generated/banxumApi";
import type { SmartInvestRule, SmartInvestRuleSaveRequest } from "../api/generated/banxumApi";

// Structured primary-market filters, also used as the Smart Invest rule editor
// state. Every list is a multi-select: nothing ticked means no restriction, and
// the values ticked inside one list combine with OR (rating A or A-).
export type MkFilters = {
  q: string;
  minRate: number | null;
  maxTerm: number | null;
  orig: string[];
  col: string[];
  ccy: string[];
  rating: string[];
  purpose: string[];
  kind: string[];
};

export type MkListKey = "orig" | "col" | "ccy" | "rating" | "purpose" | "kind";

export const mkDefaultFilters: MkFilters = {
  q: "",
  minRate: null,
  maxTerm: null,
  orig: [],
  col: [],
  ccy: [],
  rating: [],
  purpose: [],
  kind: []
};

// API tokens for the rule (see SmartInvestRule in the OpenAPI schema).
export const mkBanxumSource = "banxum";
export const mkAnyCollateral: string = SmartInvestCollateralEnum.any_secured;
export const mkNoCollateral: string = SmartInvestCollateralEnum.unsecured;
export const mkNewLending: string = SmartInvestLoanKindEnum.new;
export const mkRefinancing: string = SmartInvestLoanKindEnum.refinancing;

// Every value the rule accepts, independent of what happens to be open today.
export const smartInvestCatalog = {
  currencies: Object.values(SmartInvestCurrencyEnum) as string[],
  ratings: Object.values(RiskRatingEnum) as string[],
  purposes: Object.values(PurposeEnum) as string[],
  collateralTypes: (Object.values(SmartInvestCollateralEnum) as string[]).filter(
    (value) => value !== mkAnyCollateral && value !== mkNoCollateral
  ),
  loanKinds: Object.values(SmartInvestLoanKindEnum) as string[]
};

export function mkToggle(selected: string[], value: string) {
  return selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value];
}

export function mkAnyOf(selected: string[], value: string) {
  return selected.length === 0 || selected.includes(value);
}

// "With collateral (any type)" matches every secured loan (and implies each collateral type);
// "unsecured" matches loans without collateral.
export function mkCollateralMatches(selected: string[], loan: { unsecured: boolean; collateralType: string }) {
  if (selected.length === 0) return true;
  if (loan.unsecured) return selected.includes(mkNoCollateral);
  return selected.includes(mkAnyCollateral) || selected.includes(loan.collateralType);
}

// Values kept in order of first appearance, without duplicates.
export function mkOptionUnion(...lists: string[][]) {
  return Array.from(new Set(lists.flat().filter((value) => value !== "")));
}

// A list restricts matching unless it is empty or ticks every possible option.
function restricts(selected: string[], everyOption?: string[]) {
  if (selected.length === 0) return false;
  return !everyOption || !everyOption.every((option) => selected.includes(option));
}

export function hasSmartInvestCriteria(filters: MkFilters) {
  return filters.minRate !== null
    || filters.maxTerm !== null
    || restricts(filters.orig)
    || restricts(filters.col, [mkAnyCollateral, mkNoCollateral])
    || restricts(filters.ccy, smartInvestCatalog.currencies)
    || restricts(filters.rating, smartInvestCatalog.ratings)
    || restricts(filters.purpose, smartInvestCatalog.purposes)
    || restricts(filters.kind, smartInvestCatalog.loanKinds);
}

// The collateral list as saved: "With collateral (any type)" already covers every type.
export function mkEffectiveCollateral(selected: string[]) {
  return selected.includes(mkAnyCollateral)
    ? selected.filter((value) => value === mkAnyCollateral || value === mkNoCollateral)
    : selected;
}

export function smartInvestRequestFromFilters(filters: MkFilters): SmartInvestRuleSaveRequest {
  return {
    minimum_yield_bps: filters.minRate === null ? null : Math.round(filters.minRate * 100),
    maximum_term_months: filters.maxTerm,
    originators: [...filters.orig],
    collateral: mkEffectiveCollateral(filters.col) as SmartInvestCollateralEnum[],
    currencies: [...filters.ccy] as SmartInvestCurrencyEnum[],
    risk_ratings: [...filters.rating] as RiskRatingEnum[],
    purposes: [...filters.purpose] as PurposeEnum[],
    loan_kinds: [...filters.kind] as SmartInvestLoanKindEnum[]
  };
}

export function smartInvestFiltersFromRule(rule: SmartInvestRule | null | undefined): MkFilters {
  if (!rule?.is_active) return mkDefaultFilters;
  return {
    q: "",
    minRate: rule.minimum_yield_bps === null ? null : rule.minimum_yield_bps / 100,
    maxTerm: rule.maximum_term_months,
    orig: [...rule.originators],
    col: [...rule.collateral],
    ccy: [...rule.currencies],
    rating: [...rule.risk_ratings],
    purpose: [...rule.purposes],
    kind: [...rule.loan_kinds]
  };
}

// "A, A-, BBB" (any of them qualifies); long selections show the first three.
export function mkListSummary(labels: string[], unrestricted: string) {
  if (labels.length === 0) return unrestricted;
  if (labels.length > 4) return `${labels.slice(0, 3).join(", ")} +${labels.length - 3} more`;
  return labels.join(", ");
}
