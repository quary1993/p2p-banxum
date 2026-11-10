// IP of Webby-Soft SRL.
// U33-DEC-18: Overview "Continue your investment review" (design ic-resume): the saved opportunities
// with the amount the investor chose, checked again now. A closed opportunity says so and opens its
// page; an amount that no longer fits (minimum, amount still available, balance) is explained and kept.
// The design has no row without an amount; an item saved without one shows no amount.
import type { SavedOpportunity } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { useBalancesData, useSavedOpportunitiesData } from "../../../../investorPortal/data";
import { formatMoneyLabel } from "../../../../investorPortal/format";
import { currencyBalanceMinor } from "../../../../investorPortal/investLimits";
import { useSavedOpportunityActions } from "../../../../investorPortal/savedOpportunities";
import { NiIcon, usePortalNav } from "../../../components";
import { projectIcon } from "../loanFacts";

function checkText(item: SavedOpportunity, balanceMinor: number, t: ReturnType<typeof useT>) {
  if (!item.is_open) return t("No longer open for investment");
  if (item.amount_check === "below_minimum") return t("Your amount is below the minimum of {amount} now.", { amount: formatMoneyLabel(item.currency, item.minimum_investment_minor ?? 0) });
  if (item.amount_check === "above_available") return t("Only {amount} is still available.", { amount: formatMoneyLabel(item.currency, item.available_minor ?? 0) });
  if (item.amount_minor !== null && item.amount_minor > balanceMinor) return t("Add funds to invest your amount.");
  return "";
}

export function SavedReviews() {
  const t = useT();
  const nav = usePortalNav();
  const saved = useSavedOpportunitiesData().data?.saved ?? [];
  const lots = useBalancesData().data?.lots;
  const actions = useSavedOpportunityActions();
  if (saved.length === 0) return null;
  return (
    <section aria-label={t("Saved investment reviews")} className="ic-resume">
      <div className="ic-resume-heading">
        <h2>{t("Continue your investment review")}</h2>
        <p>{t("Saved for later · No funds reserved")}</p>
      </div>
      {saved.map((item) => {
        const note = checkText(item, currencyBalanceMinor(lots, item.currency), t);
        return (
          <div className="ic-resume-row" key={item.loan_id}>
            <span className="ic-resume-icon"><NiIcon name={projectIcon(item)} /></span>
            <div className="ic-resume-project">
              <h3>{item.title}</h3>
              {item.borrower_display_name && item.borrower_display_name !== item.title ? <span>{item.borrower_display_name}</span> : null}
              {note ? <span className="ic-unavailable">{note}</span> : null}
            </div>
            {item.amount_minor !== null ? (
              <div className="ic-resume-amount">
                <small>{t("Your amount")}</small>
                <strong>{formatMoneyLabel(item.currency, item.amount_minor)}</strong>
              </div>
            ) : null}
            <button className="ic-resume-action" onClick={() => nav.go("loan", { loanId: item.loan_id })} type="button">
              {item.is_open ? t("Continue review") : t("View opportunity")}
              <NiIcon name="arrow-right" />
            </button>
            <button
              aria-label={t("Remove saved review: {title}", { title: item.title })}
              className="ic-remove"
              disabled={actions.busy}
              onClick={() => void actions.remove(item.loan_id).catch(() => undefined)}
              type="button"
            >
              <NiIcon name="cross" />
            </button>
          </div>
        );
      })}
    </section>
  );
}
