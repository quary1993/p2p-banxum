// IP of Webby-Soft SRL.
/*
 * Overview (design #/overview, slice S2): welcome head with the currency switch, the three figures
 * (available balance with the automatic-return date from the API, principal in repayment, interest
 * received), payment updates for late and defaulted holdings, the investment cashflow and the Smart
 * Invest card in its current state. No batch approval: each match opens its opportunity and is
 * confirmed on its own (U33-DEC-19). Repayments go to the Banxum balance (U33-DEC-02).
 * U33-DEC-18: saved opportunities ("Continue your investment review") follow the head, as in the design.
 */
import { useMemo, useState } from "react";

import type { Holding, PortfolioHoldingInstallment } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useComplianceBlock, useReverificationDate } from "../../../investorPortal/complianceBlock";
import {
  useBalancesData,
  useDashboardData,
  usePortfolioData,
  useSmartInvestData
} from "../../../investorPortal/data";
import { formatDate, formatMoneyLabel, formatMoneyMinor, formatRateBps, useNumberFormat, zurichDateKey } from "../../../investorPortal/format";
import { loanIsInDefault } from "../../../investorPortal/holdingProgress";
import { platformTodayKey } from "../../../investorPortal/platformClock";
import type { DemoAccountState } from "../../../investorPortal/types";
import {
  Button,
  ButtonLink,
  CurrencySwitch,
  Dialog,
  EmptyState,
  InfoTip,
  MoneyAmount,
  NiIcon,
  PageHead,
  PortalLink
} from "../../components";
import { isOpenLoan, projectIcon } from "./loanFacts";
import { SavedReviews } from "./parts/SavedReviews";
import { readStored, writeStored } from "./storage";
import "./invest.css";

type Period = "all" | "30";

const RETURN_DISMISS_KEY = "banxum.overview.returnNotice";
const UPDATES_DISMISS_KEY = "banxum.overview.paymentUpdates";

function firstName(name: string) {
  return name.trim().split(/\s+/)[0] ?? "";
}

function isUnpaid(row: PortfolioHoldingInstallment) {
  return row.status !== "paid" && row.status !== "paid_in_advance" && row.status !== "not_expected";
}

function addDays(dateKey: string, days: number) {
  const date = new Date(`${dateKey}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

type Incident = { holding: Holding; kind: "late" | "default"; amountMinor: number };

/** Late and defaulted holdings of the currency, from the portfolio (server statuses). */
function paymentIncidents(holdings: Holding[]): Incident[] {
  const incidents: Incident[] = [];
  for (const holding of holdings) {
    if (holding.current_principal_minor <= 0) continue;
    if (loanIsInDefault(holding.loan)) {
      incidents.push({ holding, kind: "default", amountMinor: holding.current_principal_minor });
      continue;
    }
    const overdue = holding.investment_schedule.filter((row) => row.status === "overdue");
    if (holding.loan.loan_status === "late" || overdue.length > 0) {
      incidents.push({ holding, kind: "late", amountMinor: overdue.reduce((sum, row) => sum + row.projected_total_minor, 0) });
    }
  }
  return incidents;
}

export function OverviewScreen({ demoState, investorName }: { demoState: DemoAccountState; investorName: string }) {
  const t = useT();
  useNumberFormat();
  const dashboardQuery = useDashboardData();
  const balancesQuery = useBalancesData();
  const portfolioQuery = usePortfolioData(false);
  const smartInvestQuery = useSmartInvestData();
  // 18.10 (Q12): accounts without declarations are asked at sign-in (Overview), before investing.
  const complianceBlock = useComplianceBlock();
  const reverificationDate = useReverificationDate();
  const [currencyPick, setCurrencyPick] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>("all");
  const [cashflowOpen, setCashflowOpen] = useState(false);
  const [interestOpen, setInterestOpen] = useState(false);
  const [matchesOpen, setMatchesOpen] = useState(false);
  const [dismissedReturn, setDismissedReturn] = useState(() => readStored(RETURN_DISMISS_KEY));
  const [dismissedUpdates, setDismissedUpdates] = useState(() => readStored(UPDATES_DISMISS_KEY));

  const dashboard = dashboardQuery.data;
  const balances = balancesQuery.data;
  const holdingsAll = useMemo(() => portfolioQuery.data?.holdings ?? [], [portfolioQuery.data]);

  if ((dashboardQuery.isError && !dashboard) || (balancesQuery.isError && !balances)) {
    return (
      <main className="bxm-overview-summary u33-invest-state">
        <PageHead title={t("Overview")} />
        <EmptyState
          actions={<Button onClick={() => { void dashboardQuery.refetch(); void balancesQuery.refetch(); }} variant="primary">{t("Retry")}</Button>}
          icon="alert-circle"
          title={t("We could not load your overview")}
        >
          {t("Your balances and investments are safe. Try again in a moment.")}
        </EmptyState>
      </main>
    );
  }
  if (!dashboard || !balances) {
    return (
      <main className="bxm-overview-summary u33-invest-state">
        <PageHead title={t("Overview")} />
        <EmptyState icon="clock" title={t("Loading your overview")} />
      </main>
    );
  }

  const outstanding = new Map(dashboard.portfolio_summary.outstanding_principal_by_currency.map((item) => [item.currency, item.amount_minor]));
  const currencies = Array.from(new Set([
    ...balances.summaries.map((summary) => summary.currency),
    ...dashboard.portfolio_summary.outstanding_principal_by_currency.filter((item) => item.amount_minor > 0).map((item) => item.currency)
  ])).sort((a, b) => (a === b ? 0 : a === "EUR" ? -1 : b === "EUR" ? 1 : a.localeCompare(b)));
  const defaultCurrency = currencies.reduce((best, code) => ((outstanding.get(code) ?? 0) > (outstanding.get(best) ?? 0) ? code : best), currencies[0] ?? "EUR");
  const currency = currencyPick && currencies.includes(currencyPick) ? currencyPick : defaultCurrency;
  const summary = balances.summaries.find((item) => item.currency === currency);
  const availableMinor = summary?.total_available_minor ?? 0;
  // Frozen money (status "frozen"); penalty mode was removed by U33-DEC-04, older lots count here.
  const frozenMinor = (summary?.penalty_mode_minor ?? 0) + (summary?.frozen_minor ?? 0);
  const principalMinor = outstanding.get(currency) ?? 0;
  const interestMinor = dashboard.portfolio_summary.realized_interest_by_currency.find((item) => item.currency === currency)?.amount_minor ?? 0;
  const holdings = holdingsAll.filter((holding) => holding.currency === currency && holding.status !== "transferred");
  const activeHoldings = holdings.filter((holding) => holding.current_principal_minor > 0);
  const todayKey = platformTodayKey(dashboard.as_of);

  // Automatic return of money not invested: the date the API reports (platform rule; U33-DEC-03 later).
  const returnDate = summary?.next_return_date ?? null;
  const returnKey = returnDate ? `${currency}:${returnDate}` : "";
  const showReturn = Boolean(returnDate) && availableMinor > 0 && dismissedReturn !== returnKey;

  const incidents = paymentIncidents(activeHoldings);
  const incidentKey = incidents.map((item) => `${item.holding.id}:${item.kind}:${item.amountMinor}`).join("|");
  const showIncidents = incidents.length > 0 && dismissedUpdates !== incidentKey;

  // Cashflow from the investor's own schedules: interest still to come and the next payment.
  const horizon = period === "30" ? addDays(todayKey, 30) : null;
  const upcoming = activeHoldings
    .filter((holding) => !loanIsInDefault(holding.loan))
    .flatMap((holding) => holding.investment_schedule.filter(isUnpaid).map((row) => ({ holding, row })))
    .filter(({ row }) => row.status !== "overdue")
    .sort((a, b) => a.row.due_date.localeCompare(b.row.due_date));
  const futureRows = upcoming.filter(({ row }) => row.due_date >= todayKey && (!horizon || row.due_date <= horizon));
  const futureInterest = futureRows.reduce((sum, { row }) => sum + row.projected_interest_minor, 0);
  const nextRow = upcoming.find(({ row }) => row.due_date >= todayKey);
  const nextDate = nextRow?.row.due_date ?? null;
  const nextAmount = nextDate ? upcoming.filter(({ row }) => row.due_date === nextDate).reduce((sum, { row }) => sum + row.projected_total_minor, 0) : 0;
  const overdueRows = activeHoldings.flatMap((holding) => holding.investment_schedule.filter((row) => row.status === "overdue"));
  const overdueMinor = overdueRows.reduce((sum, row) => sum + row.projected_total_minor, 0);
  const band = upcoming.filter(({ row }) => row.due_date >= todayKey).slice(0, 4);

  const smartInvest = smartInvestQuery.data;
  const ruleActive = smartInvest?.rule?.is_active === true;
  // U33-DEC-19: a paused rule shows no matches or counters here, only the way back to Smart Invest.
  const rulePaused = smartInvest?.rule?.state === "paused";
  const matches = (smartInvest?.matches ?? []).filter((match) => isOpenLoan(match));

  const interestHoldings = holdings.filter((holding) => holding.received_interest_minor > 0).sort((a, b) => b.received_interest_minor - a.received_interest_minor);
  const name = firstName(investorName);

  return (
    <main className="bxm-overview-summary u33-invest-overview">
      <PageHead
        actions={[
          currencies.length > 1 ? <CurrencySwitch key="currency" label={t("Overview currency")} onChange={setCurrencyPick} options={currencies} value={currency} /> : null,
          <ButtonLink icon="briefcase" key="opportunities" to="market" variant="primary">{t("View opportunities")}</ButtonLink>
        ].filter(Boolean)}
        subtitle={t("Your investments in {currency} on {date}.", { currency, date: formatDate(dashboard.as_of) })}
        title={name ? t("Welcome back, {name}", { name }) : t("Welcome back")}
      />
      <SavedReviews />
      {complianceBlock?.reason === "declaration_missing" ? (
        <div className="alert alert-info alert-icon u33-invest-kyc" role="status">
          <NiIcon name="file-text" />
          <strong>{t("Complete your declarations.")}</strong>{" "}
          {t("We need a few answers (beneficial owner, source of funds, politically exposed person, expected volume) before your next investment.")}{" "}
          <PortalLink className="alert-link" params={{ tab: "declarations" }} to="settings">{t("Open declarations")}</PortalLink>
        </div>
      ) : null}
      {complianceBlock?.reason === "compliance_review_open" ? (
        <div className="alert alert-warning alert-icon u33-invest-kyc" role="status">
          <NiIcon name="shield-check" />
          <strong>{t("Compliance review in progress.")}</strong>{" "}
          {t("New investments are paused until the review is closed. Your account, documents and investments stay available.")}{" "}
          <PortalLink className="alert-link" params={{ tab: "declarations" }} to="settings">{t("See your declarations")}</PortalLink>
        </div>
      ) : null}
      {reverificationDate && complianceBlock?.reason !== "compliance_review_open" ? (
        <div className={`alert ${complianceBlock?.reason === "reverification_due" ? "alert-danger" : "alert-info"} alert-icon u33-invest-kyc`} role="status">
          <NiIcon name="calendar" />
          <strong>{complianceBlock?.reason === "reverification_due" ? t("Re-verification overdue.") : t("Re-verification due by {date}.", { date: formatDate(reverificationDate) })}</strong>{" "}
          {complianceBlock?.reason === "reverification_due"
            ? t("Update your details to invest again; you can still withdraw your money.")
            : t("Please update your details and declarations before this date. After it, new investments pause until the re-verification is done.")}{" "}
          <PortalLink className="alert-link" params={{ tab: "declarations" }} to="settings">{t("Open declarations")}</PortalLink>
        </div>
      ) : null}
      {demoState === "kyc_pending" ? (
        <div className="alert alert-warning alert-icon u33-invest-kyc" role="status">
          <NiIcon name="shield-check" />
          <strong>{t("Identity verification in progress.")}</strong>{" "}
          {t("Deposits, investing and withdrawals unlock once your verification is approved.")}{" "}
          <PortalLink className="alert-link" to="kyc">{t("View verification status")}</PortalLink>
        </div>
      ) : null}
      <div className="nk-block">
        <div className="row g-gs refined-overview-grid">
          <div className="col-md-4 refined-overview-stat">
            <section className="card card-bordered card-full ov-card" data-r65-role="available">
              <div className="card-inner">
                <h6 className="subtitle">{t("Available balance")}</h6>
                <MoneyAmount amountMinor={availableMinor} as="div" className="ov-amount" currency={currency} currencyClassName="" />
                <div className="ov-facts">
                  {frozenMinor > 0 ? (
                    <div className="ov-account-note u33-invest-frozen">
                      <div className="alert alert-danger alert-icon mb-3">
                        <span>{t("Of which {amount} is frozen.", { amount: formatMoneyLabel(currency, frozenMinor) })}</span>
                      </div>
                    </div>
                  ) : null}
                  {showReturn && returnDate ? (
                    <div className="ov-account-note sl31-return">
                      <div className="alert alert-warning alert-icon mb-3">
                        <span>{t("Unused funds return on {date}.", { date: formatDate(returnDate) })}</span>
                        <button
                          aria-label={t("Dismiss account reminder")}
                          className="ra-dismiss ra-dismiss-return"
                          onClick={() => {
                            writeStored(RETURN_DISMISS_KEY, returnKey);
                            setDismissedReturn(returnKey);
                          }}
                          type="button"
                        >
                          <NiIcon name="cross" />
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="ov-card-footer">
                  <PortalLink to="balances">{t("View account")} <NiIcon name="arrow-right" /></PortalLink>
                </div>
              </div>
            </section>
          </div>
          <div className="col-md-4 refined-overview-stat">
            <section className="card card-bordered card-full ov-card" data-r65-role="principal" data-simplified="true">
              <div className="card-inner">
                <h6 className="subtitle">
                  {t("Principal in repayment")}
                  <InfoTip label={t("Principal in repayment")} title={t("Principal in repayment")}>
                    {t("The part of your investments that borrowers still have to repay. Repayments are credited to your Banxum balance.")}
                  </InfoTip>
                </h6>
                <MoneyAmount amountMinor={principalMinor} as="div" className="ov-amount" currency={currency} currencyClassName="" />
                <p className="ov-caption">
                  {activeHoldings.length === 1 ? t("1 investment") : t("{count} investments", { count: activeHoldings.length })}
                </p>
                <div className="ov-facts" />
                <div className="ov-card-footer">
                  <PortalLink to="portfolio">{t("My investments")} <NiIcon name="arrow-right" /></PortalLink>
                </div>
              </div>
            </section>
          </div>
          <div className="col-md-4 refined-overview-stat">
            <section className="card card-bordered card-full ov-card" data-r65-role="interest">
              <div className="card-inner">
                <h6 className="subtitle">{t("Interest received")}</h6>
                <MoneyAmount amountMinor={interestMinor} as="div" className="ov-amount ov-earned" currency={currency} currencyClassName="" />
                <p className="ov-caption">{interestMinor > 0 ? t("Since your first investment") : t("No interest received yet")}</p>
                <div className="ov-facts" />
                <div className="ov-card-footer">
                  <button aria-haspopup="dialog" className="ov-text-link" onClick={() => setInterestOpen(true)} type="button">
                    {t("View interest history")} <NiIcon name="arrow-right" />
                  </button>
                </div>
              </div>
            </section>
          </div>

          {showIncidents ? (
            <div className="col-12 refined-overview-notice">
              <section aria-labelledby="ra-attention-title" className="ra-attention">
                <div className="ra-attention-heading">
                  <NiIcon name="info" />
                  <div>
                    <h2 id="ra-attention-title">{t("Payment updates")}</h2>
                    <p>{t("Banxum follows up on overdue payments. No action is needed from you.")}</p>
                  </div>
                </div>
                <div className="ra-incidents">
                  {incidents.map((incident) => (
                    <PortalLink
                      className={`ra-incident ${incident.kind === "default" ? "is-default" : "is-late"}`}
                      key={incident.holding.id}
                      params={{ holdingId: incident.holding.id }}
                      to="investment"
                    >
                      <strong>{incident.holding.loan.loan_title}</strong>
                      <span>
                        <i aria-hidden="true" />
                        {incident.kind === "default"
                          ? t("Default · {amount}", { amount: formatMoneyLabel(currency, incident.amountMinor) })
                          : incident.amountMinor > 0
                            ? t("Late payment · {amount}", { amount: formatMoneyLabel(currency, incident.amountMinor) })
                            : t("Late payment")}
                        <NiIcon name="chevron-right" />
                      </span>
                    </PortalLink>
                  ))}
                </div>
                <button
                  aria-label={t("Dismiss these updates")}
                  className="ra-dismiss"
                  onClick={() => {
                    writeStored(UPDATES_DISMISS_KEY, incidentKey);
                    setDismissedUpdates(incidentKey);
                  }}
                  title={t("Dismiss these updates")}
                  type="button"
                >
                  <NiIcon name="cross" />
                </button>
              </section>
            </div>
          ) : null}

          <div className="col-12 refined-overview-cashflow">
            <details
              className="card card-bordered bxm-overview-disclosure ov-cashflow r84-cashflow"
              data-r84="true"
              id="bxm-overview-payments"
              onToggle={(event) => setCashflowOpen(event.currentTarget.open)}
              open={cashflowOpen}
            >
              <summary className="card-inner">
                <div className="ov-cashflow-header">
                  <div><h6 className="title">{t("Investment cashflow")}</h6></div>
                  <div className="r84-head-actions">
                    <div aria-label={t("Interest period")} className="r84-period" role="group">
                      {([["all", t("Until final repayment")], ["30", t("Next 30 days")]] as Array<[Period, string]>).map(([value, label]) => (
                        <button
                          aria-pressed={period === value}
                          data-period={value}
                          key={value}
                          onClick={(event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            setPeriod(value);
                          }}
                          type="button"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <span className="ov-disclosure-label">
                      <span className="ov-show-label">{t("Payment schedule")}</span>
                      <span className="ov-hide-label">{t("Hide schedule")}</span>
                      <NiIcon name="chevron-down" />
                    </span>
                  </div>
                </div>
                <div className="ov-cashflow-metrics">
                  <div className="r84-future">
                    <span className="r84-label">{t("Interest to be received")}</span>
                    <div className="r84-amount"><small>{currency}</small><strong>{formatMoneyMinor(futureInterest, currency)}</strong></div>
                    <span className="r84-projected">{t("Projected")}</span>
                  </div>
                  <div className="r84-next">
                    <span className="r84-label">{t("Next payment")}</span>
                    {nextDate ? (
                      <>
                        <strong className="r84-date">{formatDate(nextDate)}</strong>
                        <span className="r84-next-amount">{formatMoneyLabel(currency, nextAmount)}</span>
                      </>
                    ) : (
                      <strong className="r84-date">{t("No payment scheduled")}</strong>
                    )}
                  </div>
                </div>
              </summary>
              <div className="tab-content">
                <div className="tab-pane active card-inner" id="bxm-payments-upcoming">
                  <div className="bxm-payment-toolbar">
                    <PortalLink className="link" to="portfolio">{t("View all payments")} <span aria-hidden="true">→</span></PortalLink>
                  </div>
                  {overdueRows.length > 0 ? (
                    <p className="bxm-ov-overdue">
                      <span>{t("Late payments")}</span>{" "}
                      {overdueRows.length === 1
                        ? t("{amount} · 1 payment", { amount: formatMoneyLabel(currency, overdueMinor) })
                        : t("{amount} · {count} payments", { amount: formatMoneyLabel(currency, overdueMinor), count: overdueRows.length })}{" "}
                      <PortalLink to="portfolio">{t("View details")}</PortalLink>
                    </p>
                  ) : null}
                  {band.length > 0 ? (
                    <ol className="bxm-payment-band">
                      {band.map(({ holding, row }) => (
                        <li key={`${holding.id}-${row.loan_installment_id}`}>
                          <PortalLink params={{ holdingId: holding.id }} to="investment">
                            <time dateTime={zurichDateKey(row.due_date) || row.due_date}>{formatDate(row.due_date)}</time>
                            <strong>{formatMoneyLabel(currency, row.projected_total_minor)}</strong>
                            <span>{holding.loan.loan_title}</span>
                          </PortalLink>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="bxm-muted mb-0">{t("No upcoming payments in {currency}.", { currency })}</p>
                  )}
                </div>
              </div>
            </details>
          </div>

          <div className="col-12 refined-overview-smart">
            {ruleActive && matches.length > 0 ? (
              <section className="si-overview-card card card-bordered">
                <div className="si-overview-head">
                  <div>
                    <span className="si-eyebrow">{t("SMART INVEST")}</span>
                    <h5>
                      <button aria-controls="si-overview-matches" aria-expanded={matchesOpen} className="si-overview-toggle" onClick={() => setMatchesOpen((open) => !open)} type="button">
                        <span>{matches.length === 1 ? t("1 opportunity matches your preferences") : t("{count} opportunities match your preferences", { count: matches.length })}</span>
                        <NiIcon name={matchesOpen ? "chevron-up" : "chevron-down"} />
                      </button>
                    </h5>
                  </div>
                  <ButtonLink className="si-matches-link" params={{ matches: "1" }} size="sm" to="market" variant="primary">
                    {t("View Smart Invest matches")} <NiIcon name="arrow-right" />
                  </ButtonLink>
                </div>
                <div className="si-mini-grid" hidden={!matchesOpen} id="si-overview-matches">
                  {matches.map((match) => (
                    <PortalLink className="si-mini-project" key={match.loan_id} params={{ loanId: match.loan_id }} to="loan">
                      <span className="bxm-project-tile"><NiIcon name={projectIcon(match)} /></span>
                      <div>
                        <h6>{match.title}</h6>
                        <p>{t("{rate} per year · {term} months · {currency}", { rate: formatRateBps(match.yield_bps || match.interest_rate_bps), term: match.term_months, currency: match.currency })}</p>
                      </div>
                      <NiIcon name="chevron-right" />
                    </PortalLink>
                  ))}
                </div>
              </section>
            ) : (
              <section className="refined-smart-intro">
                <div>
                  <h2>{t("Smart Invest")}</h2>
                  <p>
                    {ruleActive
                      ? t("Smart Invest is on. No open opportunity matches your preferences right now.")
                      : rulePaused
                        ? t("Smart Invest is paused. Your preferences are saved.")
                        : t("Find investments matching your preferences. You confirm each one.")}
                  </p>
                </div>
                <PortalLink className="refined-smart-setup" to="smartInvest">
                  {ruleActive ? t("Smart Invest preferences") : rulePaused ? t("Resume Smart Invest") : t("Set up Smart Invest")} <NiIcon name="arrow-right" />
                </PortalLink>
              </section>
            )}
          </div>
        </div>
      </div>

      {interestOpen ? (
        <Dialog className="u33-invest-interest" onClose={() => setInterestOpen(false)} size="md" title={t("Interest received")}>
          <p className="bxm-muted">{t("Interest credited to your Banxum balance, per investment, in {currency}.", { currency })}</p>
          {interestHoldings.length > 0 ? (
            <table className="table bxm-table">
              <thead>
                <tr><th scope="col">{t("Investment")}</th><th className="text-end" scope="col">{t("Interest received")}</th></tr>
              </thead>
              <tbody>
                {interestHoldings.map((holding) => (
                  <tr key={holding.id}>
                    <td><PortalLink params={{ holdingId: holding.id }} to="investment">{holding.loan.loan_title}</PortalLink></td>
                    <td className="text-end">{formatMoneyLabel(currency, holding.received_interest_minor)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr><th scope="row">{t("Total")}</th><td className="text-end">{formatMoneyLabel(currency, interestMinor)}</td></tr>
              </tfoot>
            </table>
          ) : (
            <p>{t("No interest has been received in {currency} yet.", { currency })}</p>
          )}
        </Dialog>
      ) : null}
    </main>
  );
}
