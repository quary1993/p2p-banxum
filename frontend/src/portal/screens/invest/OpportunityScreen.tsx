// IP of Webby-Soft SRL.
/*
 * Opportunity page (design #/projects/:id, slice S2): factual summary, rate and term, the security
 * (one collateral item today, with the loan-to-value comparison when a value is recorded), funding
 * progress with the minimum funding threshold, the Swiss-borrower places line (today's rule,
 * MKT-DEC-028), the originator of a claim, the payment schedule, the credit file link and the amount
 * field. A closed loan shows its state instead of the amount field. No co-investment line
 * (U33-DEC-15), no ratings (U33-DEC-16), no Save for later yet (U33-DEC-18).
 */
import { useState, type FormEvent, type ReactNode } from "react";

import type { MarketplaceLoanDetail } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useFrozenAccount } from "../../../investorPortal/accountState";
import { useBalancesData, useLoanDetailData, usePortfolioData } from "../../../investorPortal/data";
import { formatAmountInput, formatDate, formatMoneyLabel, formatMoneyMinor, formatPercent, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { currencyBalanceMinor } from "../../../investorPortal/investLimits";
import { swissInvestorLimitMessage } from "../../../investorPortal/investorLimit";
import { isNotFoundError } from "../../../investorPortal/session";
import type { DemoAccountState } from "../../../investorPortal/types";
import { Button, Dialog, EmptyState, InfoTip, NiIcon, PageHead, PortalLink, usePortalNav } from "../../components";
import { checkInvestAmount, investBlockedReason } from "./investRules";
import {
  borrowerDisclosure,
  borrowerName,
  collateralIcon,
  collateralLabel,
  countryName,
  daysLeftLabel,
  daysUntil,
  eligibleLots,
  fullLoanSchedule,
  fundedPercent,
  holdingForLoan,
  isOpenLoan,
  isOriginatorClaimLoan,
  loanAvailableMinor,
  paymentFrequencyLabel,
  securityVocabText,
  formatLtv,
  loanLtv,
  loanTypeLabel,
  loanYieldBps,
  minimumFunding,
  placesInfo,
  projectIcon,
  repaymentCadence,
  repaymentText,
  sumAvailableMinor,
  usesImmediateClaimAssignment,
  usesOriginatorSubscription
} from "./loanFacts";
import { LtvFigure } from "./parts/LtvFigure";
import { ScheduleTable } from "./parts/ScheduleTable";
import "./invest.css";
import { securityValueLabel } from "../portfolio/parts/labels";

export function OpportunityScreen({
  loanId,
  demoState,
  fromArchive = false,
  scheduleOpen: initialScheduleOpen = false,
  onAddFunds
}: {
  loanId: string;
  demoState: DemoAccountState;
  fromArchive?: boolean;
  scheduleOpen?: boolean;
  onAddFunds: () => void;
}) {
  const t = useT();
  const loanQuery = useLoanDetailData(loanId);
  const loan = loanQuery.data;
  const back = fromArchive
    ? <PortalLink className="ip-back" params={{ view: "archive" }} to="market"><NiIcon name="arrow-left" />{t("Past opportunities")}</PortalLink>
    : <PortalLink className="ip-back" to="market"><NiIcon name="arrow-left" />{t("Investment opportunities")}</PortalLink>;
  if (loanQuery.isError && !loan) {
    const notFound = isNotFoundError(loanQuery.error);
    return (
      <main className="bxm-invest-desktop ip-page l8-opportunity u33-invest-state">
        <div className="l8-back-row">{back}</div>
        <PageHead title={notFound ? t("Opportunity not found") : t("We could not load this opportunity")} />
        <EmptyState
          actions={notFound ? null : <Button onClick={() => void loanQuery.refetch()} variant="primary">{t("Retry")}</Button>}
          icon={notFound ? "search" : "alert-circle"}
          title={notFound ? t("This loan does not exist, or it is no longer shown to investors.") : t("Try again in a moment.")}
        />
      </main>
    );
  }
  if (!loan) {
    return (
      <main className="bxm-invest-desktop ip-page l8-opportunity u33-invest-state">
        <div className="l8-back-row">{back}</div>
        <EmptyState icon="clock" title={t("Loading the opportunity")} />
      </main>
    );
  }
  return <OpportunityPage back={back} demoState={demoState} initialScheduleOpen={initialScheduleOpen} key={loan.loan_id} loan={loan} onAddFunds={onAddFunds} />;
}

function OpportunityPage({
  loan,
  back,
  demoState,
  initialScheduleOpen,
  onAddFunds
}: {
  loan: MarketplaceLoanDetail;
  back: ReactNode;
  demoState: DemoAccountState;
  initialScheduleOpen: boolean;
  onAddFunds: () => void;
}) {
  const t = useT();
  useNumberFormat();
  const nav = usePortalNav();
  const frozenAccount = useFrozenAccount();
  const balances = useBalancesData().data;
  const holdings = usePortfolioData(true).data?.holdings;
  const [scheduleOpen, setScheduleOpen] = useState(initialScheduleOpen);
  const [ltvOpen, setLtvOpen] = useState(false);
  const [howOpen, setHowOpen] = useState(false);
  const [amountText, setAmountText] = useState("");
  const [error, setError] = useState<{ message: string; shortfall: boolean } | null>(null);

  const open = isOpenLoan(loan);
  const claim = isOriginatorClaimLoan(loan);
  const subscription = usesOriginatorSubscription(loan);
  const immediate = usesImmediateClaimAssignment(loan);
  const disclosure = borrowerDisclosure(loan);
  const company = borrowerName(loan);
  const meta = [company && company !== loan.title ? company : "", countryName(disclosure.country), disclosure.business_classification || disclosure.industry_activity || ""].filter(Boolean);
  const ltv = loanLtv(loan);
  const minimum = minimumFunding(loan);
  const places = placesInfo(loan);
  const percent = fundedPercent(loan);
  const holding = holdingForLoan(holdings, loan.loan_id);
  const schedule = fullLoanSchedule(loan);
  const scheduleInterest = schedule.reduce((sum, row) => sum + row.interestMinor, 0);
  const lots = eligibleLots(balances?.lots, loan);
  const funds = { balanceMinor: currencyBalanceMinor(balances?.lots, loan.currency), eligibleMinor: sumAvailableMinor(lots) };
  const blocked = investBlockedReason(demoState, frozenAccount);
  const days = daysUntil(loan.funding_deadline, balances?.as_of);
  const statusPill = statusPillOf(loan, t);
  const cadence = repaymentCadence(loan.repayment_type);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (blocked) {
      setError({ message: blocked, shortfall: false });
      return;
    }
    if (error?.shortfall) {
      onAddFunds();
      return;
    }
    const check = checkInvestAmount(amountText, loan, funds);
    if (!check.ok) {
      setError({ message: check.message, shortfall: check.shortfallMinor !== undefined });
      return;
    }
    nav.go("invest", { loanId: loan.loan_id, amount: formatAmountInput(check.amountMinor, loan.currency) });
  };

  return (
    <main className={`bxm-invest-desktop ip-page l8-opportunity r34-project-entry r36-opportunity${open ? " v107-compact" : ""}`}>
      <div className="l8-back-row">{back}</div>
      <section className="ip-panel">
        <header className="ip-project l8-project-header">
          <span className="ip-project-icon"><NiIcon name={projectIcon(loan)} /></span>
          <div>
            <h1>{loan.title}</h1>
            <p>
              {meta.join(" · ")}
              {claim ? (
                <>
                  {meta.length > 0 ? " · " : ""}
                  <span className="r58-claim">
                    <span className="l8-type">{loanTypeLabel(loan)}</span>
                    <InfoTip label={t("Existing claim")} title={t("Existing claim")}>
                      {t("A loan that a loan originator has already made to the borrower. You invest in part of the originator's claim against the borrower.")}
                    </InfoTip>
                  </span>
                </>
              ) : null}
              {statusPill}
            </p>
          </div>
        </header>
        <div className="l8-op-grid">
          <section className="l8-information">
            <div className="l8-terms">
              <div><strong>{formatRateBps(loanYieldBps(loan))}</strong><span>{subscription ? t("Investor interest rate") : t("Annual interest rate")}</span></div>
              {immediate && loan.remaining_term_days !== null ? (
                <div><strong>{loan.remaining_term_days} <small>{t("days")}</small></strong><span>{t("Remaining term")}</span></div>
              ) : (
                <div><strong>{loan.term_months} <small>{t("months")}</small></strong><span>{t("Duration")}</span></div>
              )}
            </div>
            {repaymentText(loan.repayment_type) ? <p className="l8-repayment">{repaymentText(loan.repayment_type)}</p> : null}
            <div className="l8-project-story">
              <h2>{t("About this project")}</h2>
              <p>{loan.purpose_description || loan.investor_summary || collateralLabel(loan.purpose)}</p>
            </div>
            {claim && loan.originator_name ? (
              <p className="r36-originator">
                {t("Originator")}
                <InfoTip label={t("Originator")} title={t("Originator")}>
                  {t("The company that made the loan to the borrower and offers part of its claim on Banxum.")}
                </InfoTip>
                : <span className="u33-invest-originator">{loan.originator_name}</span>
              </p>
            ) : null}
            <section className="refined-security" data-clarity="true">
              <div className="r36-security-head">
                <h2>
                  {t("Security")}
                  <InfoTip label={t("Security")} title={t("Security")}>{securityVocabText()}</InfoTip>
                </h2>
                <PortalLink aria-label={t("Security details & documents")} className="rc-resource" params={{ loanId: loan.loan_id, section: "credit-file", chapter: "security" }} to="loan">
                  {t("Details")} <NiIcon name="arrow-right" />
                </PortalLink>
              </div>
              <div className="rc-security-types">
                {ltv !== null && loan.collateral_value_minor > 0 ? (
                  <div className="r62-collateral-group">
                    <div className="r62-collateral-head">
                      <NiIcon name={collateralIcon(loan.collateral_type)} />
                      <div className="r62-collateral-copy">
                        <strong>{collateralLabel(loan.collateral_type)}</strong>
                        {loan.collateral_description && loan.collateral_description !== loan.collateral_type ? <span>{loan.collateral_description}</span> : null}
                      </div>
                      <button
                        aria-controls={`r62-collateral-${loan.loan_id}`}
                        aria-expanded={ltvOpen}
                        aria-describedby={`r62-collateral-${loan.loan_id}-explanation`}
                        aria-label={t("Loan-to-value {ratio}. {valueLabel} comparison", { ratio: formatLtv(ltv), valueLabel: t(securityValueLabel(loan.collateral_type)) })}
                        className="r62-toggle"
                        title={t("The loan amount is {ratio} of the stated {value}.", { ratio: formatLtv(ltv), value: t(securityValueLabel(loan.collateral_type)).toLowerCase() })}
                        onClick={() => setLtvOpen((value) => !value)}
                        type="button"
                      >
                        <span>{t("Loan-to-value")}</span>
                        <strong>{formatLtv(ltv)}</strong>
                        <i aria-hidden="true" className="r62-circle" />
                      </button>
                    </div>
                    <div aria-hidden={!ltvOpen} className={`r62-disclosure${ltvOpen ? " is-open" : ""}`} id={`r62-collateral-${loan.loan_id}`} inert={!ltvOpen}>
                      <div className="r62-clip">
                        <figure className="r62-figure">
                          <LtvFigure currency={loan.currency} loanMinor={loan.principal_minor} ltvBps={ltv} valueLabel={t(securityValueLabel(loan.collateral_type))} valueMinor={loan.collateral_value_minor} />
                        </figure>
                      </div>
                      <span className="sr-only" id={`r62-collateral-${loan.loan_id}-explanation`}>
                        {t("The loan amount is {ratio} of the stated {value}.", { ratio: formatLtv(ltv), value: t(securityValueLabel(loan.collateral_type)).toLowerCase() })}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="rc-security-type">
                    <NiIcon name={collateralIcon(loan.collateral_type)} />
                    <strong>{collateralLabel(loan.collateral_type)}</strong>
                    {loan.collateral_description && loan.collateral_description !== loan.collateral_type ? <span>{loan.collateral_description}</span> : null}
                  </div>
                )}
              </div>
            </section>
            <div className="r58-project-actions">
              <div className="r58-action-row">
                <PortalLink className="btn btn-outline-light r34-credit-file" params={{ loanId: loan.loan_id, section: "credit-file" }} to="loan">
                  <NiIcon name="folder" /><span>{t("Open credit file")}</span><NiIcon name="arrow-right" />
                </PortalLink>
                <button aria-controls="pd-payment-schedule" aria-expanded={scheduleOpen} className="r36-schedule-toggle r60-frequency" onClick={() => setScheduleOpen((value) => !value)} type="button">
                  <NiIcon name="calendar" />
                  <span className="r36-toggle-copy">
                    <strong>{t("Payment schedule")}</strong>
                    <small>{paymentFrequencyLabel(loan.repayment_type) || cadence || t("Full loan schedule")}</small>
                  </span>
                  <span className="r36-chevron"><NiIcon name={scheduleOpen ? "chevron-up" : "chevron-down"} /></span>
                </button>
              </div>
            </div>
          </section>

          {open ? (
            <div className="v107-right">
              <FundingCard days={days} loan={loan} minimum={minimum} percent={percent} places={places} />
              <section aria-labelledby="v107-amount-label" className="v107-amount-card">
                <form className={`v107-form${error ? (error.shortfall ? " has-warning" : " has-error") : ""}`} noValidate onSubmit={submit}>
                  <label htmlFor="iv-amount" id="v107-amount-label">{t("Choose investment amount")}</label>
                  <div className="v107-input">
                    <span>{loan.currency}</span>
                    <input
                      aria-describedby="iv-error"
                      aria-invalid={Boolean(error) && !error?.shortfall}
                      aria-labelledby="v107-amount-label"
                      autoComplete="off"
                      className="bxm-amount"
                      id="iv-amount"
                      inputMode="decimal"
                      name="amount"
                      onChange={(event) => {
                        setAmountText(event.target.value);
                        setError(null);
                      }}
                      placeholder={t("Enter an amount")}
                      type="text"
                      value={amountText}
                    />
                    <label aria-label={t("Edit investment amount")} htmlFor="iv-amount"><NiIcon name="edit" /></label>
                  </div>
                  <p aria-live="polite" className="v107-error" id="iv-error">
                    {error?.message ?? (places?.fullForViewer ? swissInvestorLimitMessage(places.maxInvestors) : "")}
                  </p>
                  {/* Kept (audit A-39): the minimum, what the loan still takes and the balance usable for this
                      loan's funding window, which can differ from the available balance. */}
                  <p className="u33-invest-amount-hint">
                    {t("Minimum {minimum} · {available} available", { minimum: formatMoneyLabel(loan.currency, loan.minimum_investment_minor), available: formatMoneyLabel(loan.currency, loanAvailableMinor(loan)) })}
                    <br />
                    {t("Your {currency} balance for this loan: {amount}", { currency: loan.currency, amount: formatMoneyLabel(loan.currency, funds.eligibleMinor) })}
                  </p>
                  <div className="v107-amount-actions">
                    <button className="v107-review" disabled={Boolean(places?.fullForViewer)} type="submit">
                      {error?.shortfall ? t("Add funds") : t("Review investment")} <NiIcon name="arrow-right" />
                    </button>
                    <p className="v107-fees">{t("No investment fees.")}</p>
                  </div>
                </form>
              </section>
            </div>
          ) : (
            <ClosedState holdingId={holding?.id ?? null} loan={loan} />
          )}
        </div>
        <div className="v107-help-row">
          <button aria-haspopup="dialog" className="l8-how" onClick={() => setHowOpen(true)} type="button"><NiIcon name="info" />{t("How investing works")}</button>
          <PortalLink className="v107-help" to="faq"><NiIcon name="help" />{t("Help with this step")}<NiIcon name="arrow-right" /></PortalLink>
        </div>
        <details
          aria-labelledby="r36-schedule-title"
          className="pd-inline-details l8-schedule r50-motion-schedule"
          id="pd-payment-schedule"
          onToggle={(event) => setScheduleOpen(event.currentTarget.open)}
          open={scheduleOpen}
        >
          <summary aria-expanded={scheduleOpen}>{t("Payment schedule")} <NiIcon name="chevron-down" /></summary>
          <div className="r50-schedule-body">
            <div className="pd-disclosure-body">
              <div className="r36-schedule-head">
                <div>
                  <h2 id="r36-schedule-title">{t("Scheduled repayments")}</h2>
                  <p>
                    {schedule.length === 1
                      ? t("Full loan · {amount} · 1 payment", { amount: formatMoneyLabel(loan.currency, loan.principal_minor) })
                      : t("Full loan · {amount} · {count} payments", { amount: formatMoneyLabel(loan.currency, loan.principal_minor), count: schedule.length })}
                  </p>
                </div>
                {schedule.length > 0 ? (
                  <div className="r36-total-interest">
                    <span>{t("Projected interest · full loan")}</span>
                    <strong>{formatMoneyLabel(loan.currency, scheduleInterest)}</strong>
                  </div>
                ) : null}
              </div>
              {schedule.length > 0 ? (
                <ScheduleTable currency={loan.currency} label={t("Full loan payment schedule, {count} payments", { count: schedule.length })} rows={schedule} />
              ) : (
                <p className="bxm-muted">{t("The schedule appears once the loan is published with its installments.")}</p>
              )}
              <p className="bxm-muted pd-schedule-note">
                {subscription
                  ? t("Only installments after the funding deadline count for investors; the first one after it belongs to the Loan Originator. Your share follows your share of the principal.")
                  : open
                    ? t("Your repayments depend on the amount invested. If the loan closes at its minimum, the schedule is recalculated on the smaller amount.")
                    : t("Your repayments depend on the amount invested. Repayments are credited to your Banxum balance.")}
              </p>
            </div>
          </div>
        </details>
      </section>

      {howOpen ? (
        <Dialog className="u33-invest-how" onClose={() => setHowOpen(false)} size="md" title={t("How investing works")}>
          <ol className="u33-invest-steps-list">
            <li>{t("You choose an amount and confirm it. The amount is reserved from your balance in the loan currency, first come, first served.")}</li>
            <li>{t("Only balance with enough holding time left for the loan's funding period can be used. CHF and EUR stay separate.")}</li>
            <li>{t("When funding closes, the reserved amount becomes your investment. Repayments are credited to your Banxum balance.")}</li>
            <li>{t("If the funding round is cancelled or does not reach its minimum, the reservation is released to your balance.")}</li>
          </ol>
          <p className="bxm-muted">{t("Repayments are not guaranteed. You can lose part or all of your investment.")}</p>
        </Dialog>
      ) : null}
    </main>
  );
}

function statusPillOf(loan: MarketplaceLoanDetail, t: ReturnType<typeof useT>) {
  if (isOpenLoan(loan)) return null;
  const status = loan.loan_status || loan.status;
  const [label, tone] =
    status === "defaulted" || status === "written_off"
      ? [status === "written_off" ? t("Written off") : t("Default"), "is-default"]
      : status === "late"
        ? [t("Late"), "is-late"]
        : status === "repaid"
          ? [t("Repaid"), "is-muted"]
          : status === "active"
            ? [t("Repaying"), "is-solid"]
            : [t("Funding closed"), "is-solid"];
  return <span className={`l8-open ${tone} r58-project-status`}>{label}</span>;
}

function FundingCard({
  loan,
  minimum,
  percent,
  places,
  days
}: {
  loan: MarketplaceLoanDetail;
  minimum: ReturnType<typeof minimumFunding>;
  percent: number;
  places: ReturnType<typeof placesInfo>;
  days: number | null;
}) {
  const t = useT();
  const claim = isOriginatorClaimLoan(loan);
  return (
    <aside className="l8-funding">
      <h2>{t("Project funding")}</h2>
      <section className="card card-bordered bxm-invest-box">
        <div className="card-inner">
          <div className="pd-funding-pair">
            <div><span>{usesOriginatorSubscription(loan) ? t("Reserved") : t("Funded")}</span><strong>{`${loan.currency} ${formatMoneyMinor(loan.committed_principal_minor, loan.currency, 0)}`}</strong></div>
            <div><span>{claim ? t("Claim offered") : t("Total loan amount")}</span><strong>{`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency, 0)}`}</strong></div>
          </div>
          <div aria-label={t("Loan funding")} aria-valuemax={100} aria-valuemin={0} aria-valuenow={percent} className="pd-progress" role="progressbar">
            <span style={{ width: `${percent}%` }} />
            {minimum ? <i aria-hidden="true" style={{ left: `${minimum.bps / 100}%` }} /> : null}
          </div>
          {minimum ? (
            <div className="pd-threshold">
              <span>{t("Minimum funding · {percent}", { percent: formatPercent(minimum.bps / 100, 0) })}</span>
              <strong>{`${loan.currency} ${formatMoneyMinor(minimum.amountMinor, loan.currency, 0)}`}</strong>
            </div>
          ) : null}
          {places ? (
            <div className="pd-threshold u33-invest-places-line">
              <span>{t("Swiss borrower: at most {count} investors", { count: places.maxInvestors })}</span>
              <strong>{places.placesLeft === 1 ? t("1 place left") : t("{count} places left", { count: places.placesLeft })}</strong>
            </div>
          ) : null}
          {days !== null && !usesImmediateClaimAssignment(loan) ? (
            <div className="pd-threshold u33-invest-deadline">
              <span>{loan.funding_deadline ? t("Funding closes {date}", { date: formatDate(loan.funding_deadline) }) : ""}</span>
              <strong>{daysLeftLabel(days)}</strong>
            </div>
          ) : null}
          {usesImmediateClaimAssignment(loan) && loan.maturity_date ? (
            <div className="pd-threshold u33-invest-deadline">
              <span>{t("Maturity")}</span>
              <strong>{formatDate(loan.maturity_date)}</strong>
            </div>
          ) : null}
        </div>
      </section>
    </aside>
  );
}

function ClosedState({ loan, holdingId }: { loan: MarketplaceLoanDetail; holdingId: string | null }) {
  const t = useT();
  const status = loan.loan_status || loan.status;
  const inDefault = status === "defaulted" || status === "written_off";
  const title = inDefault
    ? t("In default")
    : status === "repaid"
      ? t("Repaid")
      : status === "late"
        ? t("Payment overdue")
        : t("Funding closed");
  const text = inDefault
    ? t("The borrower stopped paying. Banxum follows up on the loan for all investors; recoveries are credited to the investors' Banxum balances.")
    : status === "repaid"
      ? t("This loan has been repaid.")
      : status === "late"
        ? t("A payment of this loan is overdue. Banxum follows up on overdue payments. No action is needed from you.")
        : t("This loan is no longer open for investment.");
  return (
    <aside className="l8-funding">
      <h2>{t("Project funding")}</h2>
      <div className="card card-bordered bxm-invest-box">
        <div className="card-inner">
          <h6 className={`title mb-1${inDefault ? " bxm-signal-text" : ""}`}>{title}</h6>
          <p className="pd-state-amount">
            <span>{t("Total loan amount")}</span>
            <strong>{`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency, 0)}`}</strong>
          </p>
          <p className="bxm-muted mb-0">{text}</p>
          {holdingId ? (
            <PortalLink className="btn btn-outline-light btn-block mt-3" params={{ holdingId }} to="investment">
              {inDefault ? t("Your investment and the recovery") : t("Your investment")}
            </PortalLink>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
