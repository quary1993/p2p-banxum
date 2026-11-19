// IP of Webby-Soft SRL.
// C06 / F16: the main security (the summary), the others, and the assets whose values make the
// loan-to-value (distinct assets with a documented valuation; never a guarantee or a released one).
import type { MarketplaceSecurity } from "../../../../api/generated/banxumApi";
import type { useT } from "../../../../i18n";
import { securityValueLabel } from "../../portfolio/parts/labels";

type T = ReturnType<typeof useT>;

/** The main security (the summary), the others in order, and the assets in the loan-to-value. */
export function splitSecurities(securities: MarketplaceSecurity[]) {
  const main = securities.find((security) => security.is_main) ?? securities[0];
  return {
    main,
    others: securities.filter((security) => security !== main),
    counted: securities.filter((security) => security.counts_in_ltv && !security.is_guarantee && security.status !== "released" && security.value_minor !== null)
  };
}

/** The value label of the loan-to-value comparison: one asset's own label, or the sum of several. */
export function ltvValueLabel(counted: MarketplaceSecurity[], fallbackType: string, t: T) {
  return counted.length > 1 ? t("Value of the assets that count") : t(securityValueLabel(counted[0]?.security_type ?? fallbackType));
}
