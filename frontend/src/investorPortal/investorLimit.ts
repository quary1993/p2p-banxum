// IP of Webby-Soft SRL.
// Swiss creditor modes (18.9, replaces MKT-DEC-028): a borrower in 10/20 mode has at most 10
// creditors per financing and 20 in total. The marketplace API reports the limit (max_investors,
// per financing), the places left for the viewer and whether the viewer already invests in the
// loan; its minimum_investment_minor already applies the rule. Sandbox mode has no creditor limit.
import { ApiClientError } from "../api/client/httpClient";

export type InvestorLimitFields = {
  max_investors?: number | null;
  places_left?: number | null;
  is_existing_investor?: boolean | null;
};

export const SWISS_INVESTOR_LIMIT_CODE = "swiss_investor_limit";

export function swissInvestorLimitMessage(maxInvestors: number) {
  return `This loan to a Swiss company has no place left for a new creditor (10/20 mode: at most ${maxInvestors} creditors per financing and 20 per borrower).`;
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
