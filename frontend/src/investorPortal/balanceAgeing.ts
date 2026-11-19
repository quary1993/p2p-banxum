// IP of Webby-Soft SRL.
// The balance ageing rule as the investor area shows it (18.4, Q01): money that is not invested can
// stay until day 56 after its value date; the return starts on day 57, or earlier when the bank is
// closed on that day. The legal limit stays 60 days; there is no penalty after it (U33-DEC-04). The
// live day count comes from the balances API (`auto_return_after_days`); this default covers static
// texts and the time before it loads. Each lot's own dates come with the lot.
import type { BalanceLot } from "../api/generated/banxumApi";
import { formatDate } from "./format";

export const AUTO_RETURN_AFTER_DAYS = 56;

/** The day count from the balances API, or the default when it is missing. */
export function autoReturnDays(value: number | null | undefined) {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : AUTO_RETURN_AFTER_DAYS;
}

export const autoReturnRuleText = (days: number = AUTO_RETURN_AFTER_DAYS) =>
  `Money that is not invested can stay until day ${days}. Then it goes back to your bank automatically.`;

/** The two lines under a lot's age bar: time left, and when the money goes back to the bank. */
export function lotAgeLines(lot: Pick<BalanceLot, "days_until_last_day" | "return_date" | "return_failed">) {
  if (lot.return_failed) return { status: "Return failed", detail: "Your bank sent the money back" };
  const left = lot.days_until_last_day;
  if (left > 0) return { status: `${left}d holding time left`, detail: `Goes back to your bank on ${formatDate(lot.return_date)}` };
  if (left === 0) return { status: "Last day", detail: `Goes back to your bank on ${formatDate(lot.return_date)}` };
  return { status: "Due back to your bank", detail: `Return due since ${formatDate(lot.return_date)}` };
}
