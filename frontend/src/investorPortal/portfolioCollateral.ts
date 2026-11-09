// The one "unsecured" and LTV rule of every screen (marketplace, Smart Invest, investment page).
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

/**
 * The one "unsecured" rule for every screen (marketplace, Smart-Invest, loan sheet, portfolio):
 * an unsecured type, no pledged collateral value, or no LTV because there is no value.
 */
export function isUnsecuredLoan(loan: CollateralLoan) {
  if (/unsecured/i.test(loan.collateral_type)) return true;
  if (loan.collateral_value_minor !== undefined) return !(loan.collateral_value_minor > 0);
  return loan.ltv_bps === null;
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
