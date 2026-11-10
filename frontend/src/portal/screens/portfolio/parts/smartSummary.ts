// IP of Webby-Soft SRL.
// The one-line summary of Smart Invest preferences (design summary(): the usual amount per investment or
// the currencies, minimum interest, maximum duration). The security types, loan-to-value limit, borrower
// countries and originators are added only when set (U33-DEC-19).
import type { SmartInvestChannels } from "../../../../api/generated/banxumApi";
import { t } from "../../../../i18n";
import { formatDecimal, formatMoneyLabel } from "../../../../investorPortal/format";
import { countryName } from "../../invest/loanFacts";
import { securityPreferenceText } from "./labels";
import { BANXUM_SOURCE, type SmartPreferences } from "./smartInvestModel";

export function preferenceSummary(preferences: SmartPreferences, originators: Array<{ id: string; name: string }>) {
  const amount = preferences.preferredAmount;
  const parts = [
    amount !== null
      ? t("{amounts} per investment", { amounts: preferences.currencies.map((currency) => formatMoneyLabel(currency, Math.round(amount * 100))).join(" / ") })
      : preferences.currencies.join(" / "),
    preferences.minRate !== null ? t("{rate} per year or more", { rate: `${formatDecimal(preferences.minRate, 1)}%` }) : t("Any interest rate"),
    preferences.maxTerm !== null ? t("Up to {count} months", { count: preferences.maxTerm }) : t("Any duration")
  ];
  if (preferences.security !== null) parts.push(securityPreferenceText(preferences.security));
  if (preferences.maxLtv !== null) parts.push(t("Loan-to-value up to {ratio}%", { ratio: formatDecimal(preferences.maxLtv, Number.isInteger(preferences.maxLtv) ? 0 : 1) }));
  if (preferences.countries.length > 0) parts.push(preferences.countries.map(countryName).join(", "));
  if (preferences.originators.length > 0) {
    parts.push(preferences.originators.map((id) => (id === BANXUM_SOURCE ? t("Banxum direct loans") : originators.find((item) => item.id === id)?.name ?? t("Selected originator"))).join(", "));
  }
  return parts.join(" · ");
}

/** The design's line above "Notification settings" on the Smart Invest page. */
export function channelsLine(channels: SmartInvestChannels) {
  if (channels.in_app) return t("New matches appear in your notifications.");
  if (channels.email) return t("New matches are sent to you by email.");
  return t("Match notifications are off.");
}
