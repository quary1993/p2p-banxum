// IP of Webby-Soft SRL.
// Investment history (design #/investments?tab=history): repaid and sold investments with what came
// back, and the all-time totals per currency. EUR and CHF stay separate (U33-DEC-33).
import { useState, type ReactNode } from "react";

import type { Holding, SecondaryMarketActivityEntryPortal } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { formatDate, formatRateBps, useNumberFormat, formatMoneyMinor } from "../../../investorPortal/format";
import { EmptyState, NiIcon, PortalLink, StatusTag, usePortalNav } from "../../components";
import {
  addTo,
  completedOnDate,
  holdingState,
  interestReceivedMinor,
  investorRateBps,
  principalReturnedMinor,
  sortedCurrencies,
  totalsList
} from "./parts/investmentModel";
import { monthsText, stateTag } from "./parts/labels";
import { BackLink, ProjectTile, SelectFilter } from "./parts/ui";
import { useMoneyText } from "./parts/money";

type HistoryFilter = "history" | "repaid" | "sold";

/** The sale of a holding on the resale market, from the investor's resale activity. */
function saleOf(holding: Holding, activity: SecondaryMarketActivityEntryPortal[]) {
  return activity.find((entry) => entry.action === "sale" && entry.holding_id === holding.id) ?? null;
}

export function InvestmentHistory({
  holdings,
  activity,
  currency,
  currencySwitch,
  exportAction,
  onBack
}: {
  holdings: Holding[];
  activity: SecondaryMarketActivityEntryPortal[];
  currency: string | null;
  currencySwitch: ReactNode;
  exportAction: ReactNode;
  /** Back to the overview on the same address (the sub-view is a query parameter). */
  onBack: () => void;
}) {
  const t = useT();
  const money = useMoneyText();
  const nav = usePortalNav();
  useNumberFormat();
  const [filter, setFilter] = useState<HistoryFilter>("history");
  const inCurrency = (holding: Holding) => currency === null || holding.currency === currency;
  const finished = holdings.filter((holding) => inCurrency(holding) && ["repaid", "sold"].includes(holdingState(holding)));
  const rows = finished.filter((holding) => filter === "history" || holdingState(holding) === filter);

  // Design: the totals of fully repaid investments per currency, whatever the status filter. A sale's
  // proceeds are never counted as a loan principal repayment. With "All", a currency without a repaid
  // investment has no totals.
  const repaid = finished.filter((holding) => holdingState(holding) === "repaid");
  const metrics = (currency ? [currency] : sortedCurrencies(repaid.map((holding) => holding.currency))).map((code) => {
    const scoped = repaid.filter((holding) => holding.currency === code);
    return {
      code,
      count: scoped.length,
      principal: scoped.reduce((sum, holding) => sum + principalReturnedMinor(holding), 0),
      interest: scoped.reduce((sum, holding) => sum + interestReceivedMinor(holding), 0)
    };
  });

  const allScoped = holdings.filter(inCurrency);
  const invested = new Map<string, number>();
  const earned = new Map<string, number>();
  const loans = new Map<string, Set<string>>();
  for (const holding of allScoped) {
    addTo(invested, holding.currency, holding.original_principal_minor);
    addTo(earned, holding.currency, interestReceivedMinor(holding));
    loans.set(holding.currency, (loans.get(holding.currency) ?? new Set()).add(holding.loan.loan_id));
  }
  const firstDate = allScoped.map((holding) => holding.assignment_effective_at).sort()[0];

  return (
    <main aria-label={t("My investments")} className="bxm-my-investments r75c-portfolio">
      <BackLink onClick={onBack}>{t("My investments")}</BackLink>
      <header className="r75c-head">
        <div>
          <h1>{t("Investment history")}</h1>
          <p>{t("Repaid and sold investments")}</p>
        </div>
        <ul className="nk-block-tools g-3">{currencySwitch ? <li>{currencySwitch}</li> : null}<li>{exportAction}</li></ul>
      </header>
      <section aria-label={t("Completed investments")} className="r75c-surface r75c-history">
        {metrics.length > 0 ? (
          <div className="r75c-history-metrics">
            {metrics.map((metric) => (
              <div className="r75c-metrics" key={metric.code}>
                <div>
                  <span>{t("Repaid investments · {currency}", { currency: metric.code })}</span>
                  <strong>{metric.count}</strong>
                </div>
                <div>
                  <span>{t("Principal returned · {currency}", { currency: metric.code })}</span>
                  <strong>{formatMoneyMinor(metric.principal, metric.code)}</strong>
                </div>
                <div>
                  <span>{t("Interest received · {currency}", { currency: metric.code })}</span>
                  <strong className="r75c-earned">{formatMoneyMinor(metric.interest, metric.code)}</strong>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        <div className="r75c-toolbar">
          <strong>{rows.length === 1 ? t("1 investment") : t("{count} investments", { count: rows.length })}</strong>
          <SelectFilter
            ariaLabel={t("Investment status")}
            className="bxm-mi-filter"
            label={t("Status")}
            onChange={setFilter}
            options={[
              { value: "history", label: t("All history") },
              { value: "repaid", label: t("Repaid") },
              { value: "sold", label: t("Sold") }
            ]}
            value={filter}
          />
        </div>
        {rows.length === 0 ? (
          <EmptyState icon="history" title={finished.length === 0 ? t("No completed investments yet") : t("No investments with this status")}>
            {finished.length === 0 ? t("Investments appear here when they are repaid or sold.") : null}
          </EmptyState>
        ) : (
          <table className="bxm-mi-table r75c-table mobile-records" data-mobile-table="true">
            <caption className="visually-hidden">{t("Your investments. Open an investment for its payment schedule, documents and available actions.")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("Investment")}</th>
                <th scope="col">{t("Principal returned")}</th>
                <th scope="col">{t("Interest received")}</th>
                <th scope="col">{filter === "repaid" ? t("Repaid on") : filter === "sold" ? t("Sold on") : t("Completed on")}</th>
                <th scope="col"><span className="visually-hidden">{t("Details")}</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((holding) => {
                const state = holdingState(holding);
                const tag = stateTag(state);
                const sale = state === "sold" ? saleOf(holding, activity) : null;
                const completed = sale ? sale.occurred_at : completedOnDate(holding);
                const interest = interestReceivedMinor(holding);
                return (
                  <tr
                    className="bxm-mi-row"
                    key={holding.id}
                    onClick={(event) => {
                      if ((event.target as HTMLElement).closest("a, button")) return;
                      nav.go("investment", { holdingId: holding.id });
                    }}
                  >
                    <td data-mobile-label={t("Investment")}>
                      <PortalLink className="bxm-mi-investment-link" params={{ holdingId: holding.id }} to="investment">
                        <ProjectTile collateralType={holding.loan.collateral_type} />
                        <div className="bxm-mi-identity">
                          <h6 className="bxm-mi-name">{holding.loan.loan_title}</h6>
                          <div className="bxm-mi-meta">
                            {t("{borrower} · {rate} annual interest rate · {term}", {
                              borrower: holding.loan.borrower_name,
                              rate: formatRateBps(investorRateBps(holding.loan)),
                              term: monthsText(holding.loan.term_months)
                            })}
                          </div>
                          <div className="bxm-mi-status"><StatusTag tone={tag.tone}>{tag.label}</StatusTag></div>
                        </div>
                      </PortalLink>
                    </td>
                    <td data-mobile-label={t("Principal returned")}>
                      <strong>{money(holding.currency, sale ? sale.principal_minor : principalReturnedMinor(holding))}</strong>
                      <small>
                        {sale
                          ? t("Sold for {amount}", { amount: money(holding.currency, sale.cash_amount_minor) })
                          : t("Initial investment {amount}", { amount: money(holding.currency, holding.original_principal_minor) })}
                      </small>
                    </td>
                    <td data-mobile-label={t("Interest received")}><span className={`bxm-mi-primary${interest > 0 ? " bxm-mi-earned" : ""}`}>{money(holding.currency, interest)}</span></td>
                    <td data-mobile-label={filter === "repaid" ? t("Repaid on") : filter === "sold" ? t("Sold on") : t("Completed on")}>{completed ? formatDate(completed) : "—"}</td>
                    <td data-mobile-label={t("Details")}>
                      <PortalLink aria-label={t("Open {title}", { title: holding.loan.loan_title })} className="btn btn-sm btn-icon btn-trigger" params={{ holdingId: holding.id }} tabIndex={-1} to="investment">
                        <NiIcon name="chevron-right" />
                      </PortalLink>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
      {allScoped.length > 0 ? (
        <details className="bxm-mi-history-totals r75c-disclosure">
          <summary>
            <span>{t("All-time totals")}</span>
            <NiIcon name="chevron-down" />
          </summary>
          <div className="bxm-mi-history-content">
            <p className="bxm-mi-history-note">{t("Totals by currency, across all investment statuses.")}</p>
            <table className="bxm-mi-history-table">
              <caption>
                {t("All time")} {firstDate ? <span>{t("Since {date}", { date: formatDate(firstDate) })}</span> : null}
              </caption>
              <thead>
                <tr>
                  <th scope="col">{t("Currency")}</th>
                  <th scope="col">{t("Invested")}</th>
                  <th scope="col">{t("Interest received")}</th>
                  <th scope="col">{t("Loans")}</th>
                </tr>
              </thead>
              <tbody>
                {totalsList(invested).map(([code, amount]) => (
                  <tr key={code}>
                    <th scope="row">{code}</th>
                    <td>{money(code, amount)}</td>
                    <td>{money(code, earned.get(code) ?? 0)}</td>
                    <td>{loans.get(code)?.size ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </main>
  );
}
