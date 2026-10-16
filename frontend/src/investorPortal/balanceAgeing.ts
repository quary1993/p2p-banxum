// IP of Webby-Soft SRL.
// The balance ageing rule as the investor area shows it (owner decision 2026-10-16): money that is
// not invested goes back to the investor's bank automatically after 58 days. The legal limit stays
// 60 days; penalty mode can start only after it. The live day count comes from the balances API
// (`auto_return_after_days`); this default covers static texts and the time before it loads.
import type { BalanceLot } from "../api/generated/banxumApi";
import { formatDate } from "./format";

export const AUTO_RETURN_AFTER_DAYS = 58;

/** The day count from the balances API, or the default when it is missing. */
export function autoReturnDays(value: number | null | undefined) {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : AUTO_RETURN_AFTER_DAYS;
}

export const autoReturnRuleText = (days: number = AUTO_RETURN_AFTER_DAYS) =>
  `Money that is not invested goes back to your bank automatically after ${days} days.`;

/** The two lines under a lot's age bar: time left, and when the money goes back to the bank. */
export function lotAgeLines(lot: Pick<BalanceLot, "days_until_last_day" | "return_date">, days: number) {
  const left = lot.days_until_last_day;
  if (left > 0) return { status: `${left}d holding time left`, detail: `Goes back to your bank on ${formatDate(lot.return_date)}` };
  if (left === 0) return { status: `Day ${days}: last day`, detail: `Goes back to your bank on ${formatDate(lot.return_date)}` };
  return { status: "Due back to your bank", detail: `Return due since ${formatDate(lot.return_date)}` };
}
