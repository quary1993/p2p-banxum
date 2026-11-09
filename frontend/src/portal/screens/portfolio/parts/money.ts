// IP of Webby-Soft SRL.
import { formatMoneyMinor, useNumberFormat } from "../../../../investorPortal/format";

/** "EUR 1.234,56" as plain text in the investor's number format. */
export function useMoneyText() {
  useNumberFormat();
  return (currency: string, amountMinor: number) => `${currency} ${formatMoneyMinor(amountMinor, currency)}`;
}
