// IP of Webby-Soft SRL.
// A Smart Invest match as the design's opportunity card (.bxm-project.r35-card), from the match data of
// the Smart Invest API, with the same figures, security block and icons as the Investment opportunities
// card. No risk rating (U33-DEC-16) and no "Banxum co-investment" claim (U33-DEC-15).
// "Review investment" opens the opportunity page; nothing is reserved or confirmed here (U33-DEC-19).
// With a usual amount, a card says when that amount cannot be invested here (below the minimum or more
// than is left); the opportunity stays a match (U33-DEC-19).
// As in the design's Smart Invest page, the badge, funded amount and availability are .r31-discovery-hidden.
// U33-DEC-17: a Coming soon match has the design's soon card (r31-coming-soon: no funding block,
// "Opens {date}") and "View details" instead of "Review investment".
import type { SmartInvestOpportunity } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { daysBetweenDateKeys, formatDateShort, formatDecimal, formatMoneyMinor, formatRateBps, useNumberFormat } from "../../../../investorPortal/format";
import { platformTodayKey } from "../../../../investorPortal/platformClock";
import { InfoTip, NiIcon, PortalLink, usePortalNav } from "../../../components";
import { CountryFlag } from "../../../components/CountryFlag";
import { collateralIcon, collateralLabel, paymentFrequencyLabel, placeName, projectIcon, securityHelpText, securityVocabText } from "../../invest/loanFacts";
import { investmentTypeText } from "./labels";

/** "95k", "1,2M": the design's short loan amount; the exact amount is in the title. */
function shortAmount(amountMinor: number, currency: string) {
  const units = amountMinor / 10 ** (currency === "JPY" ? 0 : 2);
  if (units >= 1_000_000) return `${formatDecimal(units / 1_000_000, units % 1_000_000 === 0 ? 0 : 1)}M`;
  if (units >= 1_000) return `${formatDecimal(units / 1_000, units % 1_000 === 0 ? 0 : 1)}k`;
  return formatDecimal(units, 0);
}

export function OpportunityCard({ match, asOf, preferredAmount = null }: { match: SmartInvestOpportunity; asOf?: string; preferredAmount?: number | null }) {
  const t = useT();
  useNumberFormat();
  const nav = usePortalNav();
  const funded = match.principal_minor > 0 ? Math.min(100, (match.committed_principal_minor / match.principal_minor) * 100) : 0;
  const days = match.funding_deadline ? daysBetweenDateKeys(platformTodayKey(asOf), match.funding_deadline) : null;
  const money = (amount: number) => `${match.currency} ${formatMoneyMinor(amount, match.currency)}`;
  const subtitle = match.borrower_display_name || match.originator_name || "";
  const payments = paymentFrequencyLabel(match.repayment_type, match.loan_status, match.payment_frequency);
  // As on the opportunity cards: the security type, then its description when it says more.
  const securityName = collateralLabel(match.collateral_type);
  const description = match.collateral_description ?? "";
  const securityDetail = description && description !== match.collateral_type && description !== securityName ? description : "";
  const location = placeName(match.borrower_city, match.borrower_country);
  const soon = match.opportunity_status === "coming_soon";
  const usualMinor = preferredAmount === null || soon ? null : Math.round(preferredAmount * 100);
  const amountNote = usualMinor === null
    ? ""
    : usualMinor < match.minimum_investment_minor
      ? t("Your usual amount of {amount} is below the minimum here.", { amount: money(usualMinor) })
      : usualMinor > match.fillable_amount_minor
        ? t("Your usual amount of {amount} is more than is still available here.", { amount: money(usualMinor) })
        : "";
  return (
    <div className="col-md-6 col-xxl-4">
      <div className="card card-bordered h-100">
        <div className="card-inner">
          <div className={`project bxm-project r35-card${soon ? " r31-coming-soon" : ""}`}>
            <div className="project-head">
              <PortalLink className="project-title" params={{ loanId: match.loan_id }} to="loan">
                <div className="bxm-project-tile"><NiIcon name={projectIcon(match)} /></div>
                <div className="project-info">
                  <h3 className="title h6">{match.title}</h3>
                  {subtitle ? <span className="sub-text">{subtitle}</span> : null}
                </div>
              </PortalLink>
            </div>
            <div className="r35-location">
              <span className="r35-location-text">{match.borrower_country ? <CountryFlag code={match.borrower_country} /> : null}{location ? <span>{location}</span> : null}</span>
              <span className="r35-location-badges">
                <span className="bxm-tag si-match-label r31-discovery-hidden" title={t("Matches your Smart Invest preferences.")}>{t("Smart Invest")}</span>
              </span>
            </div>
            <div className="bxm-project-tags">
              {soon ? <span className="bxm-tag">{t("Coming soon")}</span> : <span className="bxm-tag is-open">{t("Open")}</span>}
              <span className="bxm-tag is-type">{investmentTypeText(match.product_type)}</span>
            </div>
            <div className="r60-card-terms">
              <dl className="bxm-project-figures">
                <div>
                  <dt>{t("Annual interest")}</dt>
                  <dd>{formatRateBps(match.yield_bps || match.interest_rate_bps)}</dd>
                </div>
                <div>
                  <dt>{t("Term")}</dt>
                  <dd>{t("{count} mo", { count: match.term_months })}{payments ? <small className="r74-card-payments">{payments}</small> : null}</dd>
                </div>
                <div>
                  <dt>{t("Loan amount · {currency}", { currency: match.currency })}</dt>
                  <dd aria-label={money(match.principal_minor)} tabIndex={0} title={money(match.principal_minor)}>{shortAmount(match.principal_minor, match.currency)}</dd>
                </div>
              </dl>
            </div>
            <section className="r35-security">
              <div className="r35-security-heading">
                {t("Security")}
                <InfoTip label={t("Security")} title={t("Security")}>{securityHelpText(match.collateral_type) || securityVocabText()}</InfoTip>
              </div>
              <div className="r35-security-content">
                <NiIcon className="r35-security-icon" name={collateralIcon(match.collateral_type)} />
                <div>
                  <strong>{securityName}</strong>
                  {securityDetail ? <small>{securityDetail}</small> : null}
                </div>
              </div>
            </section>
            <div className="bxm-project-progress r31-lean-funding">
              <div className="bxm-project-row">
                <span className="r31-discovery-hidden"><strong>{money(match.committed_principal_minor)}</strong> {t("funded")}</span>
                <strong>{Math.round(funded)}% <span className="r31-funded-label">{t("of loan funded")}</span></strong>
              </div>
              <div aria-label={t("{percent}% of the loan funded", { percent: Math.round(funded) })} aria-valuemax={100} aria-valuemin={0} aria-valuenow={Math.round(funded)} className="bxm-progress" role="progressbar">
                <span style={{ width: `${funded}%` }} />
              </div>
              <div className="bxm-project-row">
                <span className="r31-discovery-hidden">{t("{amount} available", { amount: money(match.fillable_amount_minor) })}</span>
                <span className="r31-minimum">{t("Min. {amount}", { amount: money(match.minimum_investment_minor) })}</span>
              </div>
              {amountNote ? <p className="si-amount-note">{amountNote}</p> : null}
            </div>
            <div className="project-meta mt-3">
              <span className="bxm-muted">
                <NiIcon name="clock" />{" "}
                {soon
                  ? t("Opens {date}", { date: formatDateShort(match.planned_opening_date) })
                  : days === null ? t("Open") : days <= 0 ? t("Closes today") : days === 1 ? t("1 day left") : t("{days} days left", { days })}
              </span>
              {soon ? (
                <PortalLink aria-label={t("View details of {title}", { title: match.title })} className="si-detail" params={{ loanId: match.loan_id }} to="loan">
                  {t("View details")} <NiIcon name="chevron-right" />
                </PortalLink>
              ) : (
                <button aria-label={t("Review investment in {title}", { title: match.title })} className="btn si-review-investment r65-result-cta" onClick={() => nav.go("loan", { loanId: match.loan_id })} type="button">
                  {t("Review investment")}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
