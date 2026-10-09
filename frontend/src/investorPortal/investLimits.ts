// Why an investment amount cannot be placed, naming the limit that actually binds: the opportunity's
// remaining capacity, the investor's balance, or the age of that balance (60-day holding limit).
import type { BalanceLot } from "../api/generated/banxumApi";

export const sourceAgeRuleText =
  "Every incoming amount has a 60-day holding limit. To invest, that amount must have enough time left to cover the loan's remaining funding period. Shorter periods can use older funds. Eligible lots are consumed oldest-first. FX conversion does not reset this limit.";

/** balanceMinor: everything still available in the currency; eligibleMinor: the part old enough rules allow for this loan. */
export type InvestFunds = { balanceMinor: number; eligibleMinor: number };

/** Available money in the currency, whatever its age (lots that are frozen or in penalty mode excluded). */
export function currencyBalanceMinor(lots: BalanceLot[] | undefined, currency: string) {
  return (lots ?? [])
    .filter((lot) => lot.currency === currency && lot.status === "available" && lot.available_amount_minor > 0)
    .reduce((total, lot) => total + lot.available_amount_minor, 0);
}

/** The reason nothing can be committed to a loan from the investor's funds, or null when something can. */
export function noEligibleFundsReason(currency: string, funds: InvestFunds): { title: string; detail: string } | null {
  if (funds.eligibleMinor > 0) return null;
  if (funds.balanceMinor <= 0) {
    return {
      title: "No investable balance is available in this currency.",
      detail: `Add ${currency} funds to invest in this loan.`
    };
  }
  return {
    title: `Your ${currency} balance does not have enough holding time left for this loan's funding period.`,
    detail: sourceAgeRuleText
  };
}

/** Message for an amount above what can be committed, or null when the amount fits every limit. */
export function investAmountLimitMessage({
  amountMinor,
  capacityMinor,
  currency,
  funds,
  money
}: {
  amountMinor: number;
  capacityMinor: number;
  currency: string;
  funds: InvestFunds;
  money: (amountMinor: number) => string;
}): string | null {
  if (amountMinor <= Math.min(capacityMinor, funds.eligibleMinor)) return null;
  if (capacityMinor <= funds.eligibleMinor) {
    return `This opportunity has only ${money(capacityMinor)} left, so that is the most you can invest here.`;
  }
  const noFunds = noEligibleFundsReason(currency, funds);
  if (noFunds) return noFunds.title;
  if (funds.eligibleMinor < funds.balanceMinor) {
    return `Only ${money(funds.eligibleMinor)} of your ${currency} balance has enough holding time left for this loan's funding period — today's maximum here.`;
  }
  return `Only ${money(funds.eligibleMinor)} is not lent — today's maximum here.`;
}
