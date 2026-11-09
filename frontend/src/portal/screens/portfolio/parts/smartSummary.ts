// IP of Webby-Soft SRL.
// The one-line summary of Smart Invest preferences (design summary(): currencies, minimum interest,
// maximum duration). The security types and originators the app applies today are added only when set.
import { t } from "../../../../i18n";
import { formatDecimal } from "../../../../investorPortal/format";
import { securityPreferenceText } from "./labels";
import { BANXUM_SOURCE, type SmartPreferences } from "./smartInvestModel";

export function preferenceSummary(preferences: SmartPreferences, originators: Array<{ id: string; name: string }>) {
  const parts = [
    preferences.currencies.join(" / "),
    preferences.minRate !== null ? t("{rate} per year or more", { rate: `${formatDecimal(preferences.minRate, 1)}%` }) : t("Any interest rate"),
    preferences.maxTerm !== null ? t("Up to {count} months", { count: preferences.maxTerm }) : t("Any duration")
  ];
  if (preferences.security !== null) parts.push(securityPreferenceText(preferences.security));
  if (preferences.originators.length > 0) {
    parts.push(preferences.originators.map((id) => (id === BANXUM_SOURCE ? t("Banxum direct loans") : originators.find((item) => item.id === id)?.name ?? t("Selected originator"))).join(", "));
  }
  return parts.join(" · ");
}
