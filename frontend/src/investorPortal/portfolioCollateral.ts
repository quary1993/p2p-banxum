// Collateral figures of the My investments widgets ("Collateral spread", "Weighted LTV", "Nothing pledged").
// A loan counts as secured only when a collateral value is actually pledged: the recorded collateral type
// alone (for example "real_estate" with a value of 0) does not secure anything.

type CollateralLoan = {
  collateral_type: string;
  /** Unknown on some list payloads (the marketplace preview); LTV null then means "no value". */
  collateral_value_minor?: number;
  ltv_bps: number | null;
  product_type?: string;
  principal_minor?: number;
  schedule?: Array<{ outstanding_principal_minor: number }>;
};

type CollateralHolding = {
  current_principal_minor: number;
  loan: CollateralLoan;
};

/**
 * The one "unsecured" rule for every screen (marketplace, Smart Invest, loan sheet, portfolio):
 * an unsecured type, no pledged collateral value, or no LTV because there is no value.
 */
export function isUnsecuredLoan(loan: CollateralLoan) {
  if (/unsecured/i.test(loan.collateral_type)) return true;
  if (loan.collateral_value_minor !== undefined) return !(loan.collateral_value_minor > 0);
  return loan.ltv_bps === null;
}

export function isUnsecuredHolding(holding: CollateralHolding) {
  return isUnsecuredLoan(holding.loan);
}

/**
 * Principal still owed on the whole loan. Originator claims report it as `principal_minor`; for
 * direct loans it is the unpaid principal of the current schedule (falls back to the loan amount).
 */
export function currentLoanPrincipalMinor(loan: CollateralLoan) {
  if (loan.product_type === "originator_claim") return loan.principal_minor ?? null;
  if (loan.schedule && loan.schedule.length > 0) {
    return loan.schedule.reduce((sum, row) => sum + Math.max(0, row.outstanding_principal_minor), 0);
  }
  return loan.principal_minor ?? null;
}

/**
 * LTV, one definition everywhere: principal still owed on the loan divided by the collateral
 * valuation (for an open loan that is the loan amount). Null when nothing is pledged.
 */
export function loanLtvBps(loan: CollateralLoan) {
  if (isUnsecuredLoan(loan)) return null;
  const valuation = loan.collateral_value_minor;
  const principal = currentLoanPrincipalMinor(loan);
  if (valuation !== undefined && valuation > 0 && principal !== null) {
    return Math.round((principal * 10_000) / valuation);
  }
  return loan.ltv_bps;
}

/** Principal per collateral group (largest first) for secured holdings, and the unsecured remainder. */
export function collateralBreakdown<T extends CollateralHolding>(holdings: T[], groupFor: (holding: T) => string) {
  const byGroup = new Map<string, number>();
  let unsecuredMinor = 0;
  let unsecuredCount = 0;
  for (const holding of holdings) {
    if (isUnsecuredHolding(holding)) {
      unsecuredMinor += holding.current_principal_minor;
      unsecuredCount += 1;
      continue;
    }
    const key = groupFor(holding);
    byGroup.set(key, (byGroup.get(key) ?? 0) + holding.current_principal_minor);
  }
  return {
    secured: Array.from(byGroup.entries()).sort((left, right) => right[1] - left[1]),
    unsecuredMinor,
    unsecuredCount
  };
}

/** Secured holdings that carry a loan-to-value figure. */
export function valuedSecuredHoldings<T extends CollateralHolding>(holdings: T[]) {
  return holdings.filter((holding) => !isUnsecuredHolding(holding) && loanLtvBps(holding.loan) !== null);
}

/** Principal-weighted LTV in percent across valued secured holdings, or null when none is valued. */
export function weightedLtvPercent(holdings: CollateralHolding[]) {
  const valued = valuedSecuredHoldings(holdings);
  const principal = valued.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  if (principal <= 0) return null;
  return valued.reduce((sum, holding) => sum + ((loanLtvBps(holding.loan) ?? 0) / 100) * holding.current_principal_minor, 0) / principal;
}
