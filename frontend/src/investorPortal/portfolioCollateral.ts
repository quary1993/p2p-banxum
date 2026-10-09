// Collateral figures of the My investments widgets ("Collateral spread", "Weighted LTV", "Nothing pledged").
// A loan counts as secured only when a collateral value is actually pledged: the recorded collateral type
// alone (for example "real_estate" with a value of 0) does not secure anything.

type CollateralLoan = {
  collateral_type: string;
  collateral_value_minor: number;
  ltv_bps: number | null;
};

type CollateralHolding = {
  current_principal_minor: number;
  loan: CollateralLoan;
};

export function isUnsecuredHolding(holding: CollateralHolding) {
  return holding.loan.collateral_type === "unsecured_exception" || !(holding.loan.collateral_value_minor > 0);
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
  return holdings.filter((holding) => !isUnsecuredHolding(holding) && holding.loan.ltv_bps !== null);
}

/** Principal-weighted LTV in percent across valued secured holdings, or null when none is valued. */
export function weightedLtvPercent(holdings: CollateralHolding[]) {
  const valued = valuedSecuredHoldings(holdings);
  const principal = valued.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  if (principal <= 0) return null;
  return valued.reduce((sum, holding) => sum + ((holding.loan.ltv_bps ?? 0) / 100) * holding.current_principal_minor, 0) / principal;
}
