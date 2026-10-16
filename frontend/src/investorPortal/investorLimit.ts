// IP of Webby-Soft SRL.
// Swiss-borrower loans have at most 20 investors (plan/09 MKT-DEC-028, 2026-10-16). The
// marketplace API reports the limit (max_investors), the places left and whether the viewing
// investor already invests in the loan; its minimum_investment_minor already applies the rule.
import { ApiClientError } from "../api/client/httpClient";

export type InvestorLimitFields = {
  max_investors?: number | null;
  places_left?: number | null;
  is_existing_investor?: boolean | null;
};

export const SWISS_INVESTOR_LIMIT_CODE = "swiss_investor_limit";

export function swissInvestorLimitMessage(maxInvestors: number) {
  return `This loan to a Swiss company already has the maximum of ${maxInvestors} investors.`;
}

/** True when a Swiss-borrower loan has no place left and the viewer does not invest in it yet. */
export function swissLoanFullForViewer(loan: InvestorLimitFields) {
  return typeof loan.max_investors === "number" && loan.places_left === 0 && loan.is_existing_investor !== true;
}

/** The server refused a new investor: the Swiss-borrower loan has no place left (409). */
export function isSwissInvestorLimitError(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 409) return false;
  const payload = error.payload as { code?: unknown } | null | undefined;
  return payload?.code === SWISS_INVESTOR_LIMIT_CODE;
}
