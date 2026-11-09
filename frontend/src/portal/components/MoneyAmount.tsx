// IP of Webby-Soft SRL.
// Currency + amount from integer minor units ("EUR 820,00"), formatted by format.ts
// (format.ts). The currency code is its own element so screens can style it (.currency, small).
import type { ElementType } from "react";

import { formatMoneyMinor } from "../../investorPortal/format";

export function MoneyAmount({
  amountMinor,
  currency,
  as: Tag = "span",
  className = "",
  currencyAs: CurrencyTag = "span",
  currencyClassName = "currency",
  decimals,
  signed = false,
  hideCurrency = false
}: {
  amountMinor: number | null | undefined;
  currency: string;
  as?: ElementType;
  className?: string;
  /** Element of the currency code; the design uses <small> or <span>. */
  currencyAs?: ElementType;
  currencyClassName?: string;
  /** Override of the currency's minor-unit decimals (e.g. 0 for whole amounts). */
  decimals?: number;
  /** Show "+" before positive amounts. */
  signed?: boolean;
  hideCurrency?: boolean;
}) {
  const value = formatMoneyMinor(amountMinor, currency, decimals);
  const plus = signed && (amountMinor ?? 0) > 0 ? "+" : "";
  return (
    <Tag className={className || undefined}>
      {hideCurrency ? null : <><CurrencyTag className={currencyClassName || undefined}>{currency}</CurrencyTag> </>}
      {plus}{value}
    </Tag>
  );
}
