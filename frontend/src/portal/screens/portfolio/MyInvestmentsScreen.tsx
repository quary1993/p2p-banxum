// IP of Webby-Soft SRL.
// My investments (design #/investments, U33 slice S3): interest received and to be received, "In funding"
// (open primary orders) apart from "Current investments", status filter, sort, the payment-update
// notice, and the sub-views History (?view=history) and Payment schedule (?view=payments).
import { useState, type ReactNode } from "react";

import type { Holding, MarketplaceLoanPreview, PrimaryOrderPortal } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useMarketplaceLoansData, usePortfolioData, usePrimaryOrdersData, useSecondaryActivityData } from "../../../investorPortal/data";
import { formatDate, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { ButtonLink, CurrencySwitch, EmptyState, InfoTip, NiIcon, PageHead, PortalLink, StatusTag, usePortalNav } from "../../components";
import { InvestmentHistory } from "./InvestmentHistory";
import { PortfolioInsights } from "./PortfolioInsights";
import { PortfolioSchedule } from "./PortfolioSchedule";
import {
  addTo,
  earliestNextPayment,
  holdingState,
  interestReceivedMinor,
  isCurrentHolding,
  isOpenOrder,
  lifetimeInterestMinor,
  loanCount,
  maturityDate,
  nextPayment,
  orderAmountMinor,
  overdueRows,
  projectedInterestMinor,
  sortedCurrencies,
  sortHoldings,
  totalsList,
  investorRateBps,
  type HoldingSortKey,
  type InvestmentState
} from "./parts/investmentModel";
import { monthsText, stateTag } from "./parts/labels";
import { usePreviewVariant, useQueryParams } from "./parts/urlState";
import { CurrencyFigure, PageError, PageLoading, ProjectTile, SelectFilter } from "./parts/ui";
import { useMoneyText } from "./parts/money";
import "./portfolio.css";

type StatusFilter = "current" | "active" | "due" | "late" | "default";

const PAGE_CLASS = "bxm-my-investments mi40";

export function MyInvestmentsScreen() {
  const t = useT();
  const portfolioQuery = usePortfolioData(true);
  const ordersQuery = usePrimaryOrdersData();
  const loansQuery = useMarketplaceLoansData();
  const activityQuery = useSecondaryActivityData();
  const preview = usePreviewVariant();
  const [params, setParams] = useQueryParams();
  const view = params.get("view");
  const currencyParam = params.get("cur");

  if ((portfolioQuery.isError && !portfolioQuery.data) || (ordersQuery.isError && !ordersQuery.data)) {
    return (
      <PageError
        className={PAGE_CLASS}
        message={t("Your investments could not be loaded. Retry once the connection is restored.")}
        onRetry={() => {
          void portfolioQuery.refetch();
          void ordersQuery.refetch();
        }}
        title={t("My investments")}
      />
    );
  }
  if (!portfolioQuery.data || !ordersQuery.data) return <PageLoading className={PAGE_CLASS} title={t("My investments")} />;

  const empty = preview === "empty";
  const holdings = empty ? [] : portfolioQuery.data.holdings;
  const orders = empty ? [] : ordersQuery.data.orders.filter(isOpenOrder);
  const loansById = new Map((loansQuery.data ?? []).map((loan) => [loan.loan_id, loan]));
  const currencies = sortedCurrencies([...holdings.map((holding) => holding.currency), ...orders.map((order) => order.currency)]);
  const currency = currencyParam && currencies.includes(currencyParam) ? currencyParam : null;
  const setCurrency = (code: string | null) => setParams({ cur: code }, { replace: true });
  const currencySwitch = currencies.length > 1 ? (
    <CurrencySwitch
      onChange={(value: string) => setCurrency(value === "All" ? null : value)}
      options={["All", ...currencies]}
      value={currency ?? "All"}
    />
  ) : null;

  if (view === "history") {
    return <InvestmentHistory activity={activityQuery.data?.entries ?? []} currency={currency} currencySwitch={currencySwitch} holdings={holdings} onBack={() => setParams({ view: null })} />;
  }
  if (view === "payments") {
    return <PortfolioSchedule asOf={portfolioQuery.data.as_of} currency={currency} currencySwitch={currencySwitch} holdings={holdings} onBack={() => setParams({ view: null })} />;
  }
  if (holdings.length === 0 && orders.length === 0) {
    return (
      <main className={PAGE_CLASS} aria-label={t("My investments")}>
        <PageHead title={t("My investments")} />
        <div className="card card-bordered u33-state-card">
          <EmptyState
            actions={<ButtonLink to="market" variant="primary">{t("Investment opportunities")}</ButtonLink>}
            icon="growth"
            title={t("No investments yet")}
          >
            {t("Your reservations, current investments and repayments appear here after your first investment.")}
          </EmptyState>
        </div>
      </main>
    );
  }
  return (
    <InvestmentsOverview
      asOf={portfolioQuery.data.as_of}
      currency={currency}
      currencySwitch={currencySwitch}
      holdings={holdings}
      loansById={loansById}
      onView={(next) => setParams({ view: next })}
      orders={orders}
    />
  );
}

function InvestmentsOverview({
  asOf,
  holdings,
  orders,
  loansById,
  currency,
  currencySwitch,
  onView
}: {
  asOf: string;
  holdings: Holding[];
  orders: PrimaryOrderPortal[];
  loansById: Map<string, MarketplaceLoanPreview>;
  currency: string | null;
  currencySwitch: ReactNode;
  onView: (view: "history" | "payments") => void;
}) {
  const t = useT();
  const money = useMoneyText();
  const inCurrency = <T extends { currency: string }>(item: T) => currency === null || item.currency === currency;
  const scopedHoldings = holdings.filter(inCurrency);
  const current = scopedHoldings.filter(isCurrentHolding);
  const scopedOrders = orders.filter(inCurrency);
  const visibleCurrencies = sortedCurrencies([...scopedHoldings.map((holding) => holding.currency), ...scopedOrders.map((order) => order.currency)]);

  const received = new Map<string, number>();
  const future = new Map<string, number>();
  const outstanding = new Map<string, number>();
  const reserved = new Map<string, number>();
  for (const code of visibleCurrencies) {
    received.set(code, 0);
    future.set(code, 0);
  }
  for (const holding of scopedHoldings) addTo(received, holding.currency, interestReceivedMinor(holding));
  for (const holding of current) {
    addTo(future, holding.currency, projectedInterestMinor(holding) ?? 0);
    addTo(outstanding, holding.currency, holding.current_principal_minor);
  }
  for (const order of scopedOrders) addTo(reserved, order.currency, orderAmountMinor(order));
  const next = earliestNextPayment(current);
  const subtitle = current.length === 0
    ? undefined
    : t("{investments} in {companies}.", {
        // Two lots of one loan (bought at different times) count as one investment (audit SECONDARY-11).
        investments: loanCount(current) === 1 ? t("1 investment") : t("{count} investments", { count: loanCount(current) }),
        companies: (() => {
          const count = new Set(current.map((holding) => holding.loan.borrower_name || holding.loan.loan_id)).size;
          return count === 1 ? t("1 company") : t("{count} companies", { count });
        })()
      });

  return (
    <main aria-label={t("My investments")} className={PAGE_CLASS}>
      <PageHead actions={currencySwitch ?? undefined} subtitle={subtitle} title={t("My investments")} />
      <div className="mi40-body">
        <div className="mi64-summary-grid r84-portfolio" data-r84="true">
          <section aria-labelledby="mi40-earned-title" className="mi40-earned">
            <header className="r84-portfolio-head">
              <h2 id="mi40-earned-title">{t("Interest received")}</h2>
              <span className="r84-inline-caption">{t("Since your first investment")}</span>
            </header>
            <div className="mi40-earned-values">
              {totalsList(received).map(([code, amount]) => <CurrencyFigure amountMinor={amount} currency={code} key={code} />)}
            </div>
          </section>
          <section aria-labelledby="mi64-payments-title" className="mi64-next-payment">
            <header className="r84-portfolio-head">
              <h2 id="mi64-payments-title">{t("Interest to be received")}</h2>
              <span className="r84-inline-caption">{t("Projected")}</span>
            </header>
            <div className="r84-values">
              {totalsList(future).map(([code, amount]) => (
                <CurrencyFigure amountMinor={amount} className="r84-amount" codeAs="small" currency={code} key={code} />
              ))}
            </div>
            <div className="r84-portfolio-footer">
              {next ? (
                <p className="r84-nextline">
                  <span>{t("Next payment")}</span>
                  <span>{formatDate(next.row.due_date)}</span>
                  <strong>{money(next.holding.currency, next.row.projected_total_minor)}</strong>
                </p>
              ) : (
                <p className="r84-nextline"><span>{t("No scheduled payment")}</span></p>
              )}
              <a
                className="r84-schedule-link"
                href="?view=payments"
                onClick={(event) => {
                  event.preventDefault();
                  onView("payments");
                }}
              >
                {t("Payment schedule")} <NiIcon name="arrow-right" />
              </a>
            </div>
          </section>
        </div>

        {scopedOrders.length > 0 ? (
          <section aria-labelledby="mi40-funding-title" className="mi40-funding">
            <div className="mi40-section-head">
              <div>
                <h2 id="mi40-funding-title">{t("In funding")} <span>{scopedOrders.length}</span></h2>
                <p>{t("Your reserved investments")}</p>
              </div>
              <div className="mi40-group-total">
                {totalsList(reserved).map(([code, amount]) => <strong key={code}>{money(code, amount)}</strong>)}
              </div>
            </div>
            <div className="mi40-funding-grid" id="mi40-funding-list">
              {scopedOrders.map((order) => <FundingCard key={order.id} loan={loansById.get(order.loan_id)} order={order} />)}
            </div>
          </section>
        ) : null}

        <CurrentInvestments currentHoldings={current} hasHistory={scopedHoldings.some((holding) => !isCurrentHolding(holding))} onHistory={() => onView("history")} outstanding={outstanding} />
        {current.length > 0 ? <PortfolioInsights asOf={asOf} holdings={current} /> : null}
      </div>
    </main>
  );
}

function FundingCard({ order, loan }: { order: PrimaryOrderPortal; loan: MarketplaceLoanPreview | undefined }) {
  const t = useT();
  const money = useMoneyText();
  useNumberFormat();
  const funded = loan && loan.principal_minor > 0 ? Math.min(100, (loan.committed_principal_minor / loan.principal_minor) * 100) : null;
  const allocated = order.allocated_amount_minor > 0;
  return (
    <PortalLink className="mi40-funding-card" params={{ holdingId: order.id }} to="investment">
      <div className="mi40-fund-project">
        <ProjectTile as="span" className="mi40-tile" collateralType={loan?.collateral_type ?? ""} />
        <div>
          <h3>{order.loan_title}</h3>
          {loan?.borrower_display_name || loan?.originator_name ? <p>{loan.borrower_display_name || loan.originator_name}</p> : null}
        </div>
      </div>
      <div className="mi40-fund-amount">
        <small>{allocated ? t("Your reserved amount") : t("Requested · not reserved yet")}</small>
        <strong>{money(order.currency, orderAmountMinor(order))}</strong>
      </div>
      {loan ? (
        <div className="mi40-fund-terms">
          <b>{formatRateBps(investorRateBps(loan))} <small>{t("per year")}</small></b>
          <span>{monthsText(loan.term_months)}</span>
        </div>
      ) : null}
      {loan && funded !== null ? (
        <div className="mi40-fund-progress">
          <div>
            <span>{t("{percent}% funded", { percent: Math.round(funded) })}</span>
            {loan.funding_deadline ? <span className="mi64-closes">{t("Closes {date}", { date: formatDate(loan.funding_deadline) })}</span> : null}
          </div>
          <div aria-hidden="true" className="mi40-track"><i style={{ width: `${funded}%` }} /></div>
        </div>
      ) : null}
      <span className="mi40-arrow"><NiIcon name="chevron-right" /></span>
    </PortalLink>
  );
}

function CurrentInvestments({
  currentHoldings,
  outstanding,
  hasHistory,
  onHistory
}: {
  currentHoldings: Holding[];
  outstanding: Map<string, number>;
  hasHistory: boolean;
  onHistory: () => void;
}) {
  const t = useT();
  const nav = usePortalNav();
  const [status, setStatus] = useState<StatusFilter>("current");
  const [sort, setSort] = useState<HoldingSortKey>("maturity");
  const states = new Map(currentHoldings.map((holding) => [holding.id, holdingState(holding)]));
  const lateCount = currentHoldings.filter((holding) => states.get(holding.id) === "late").length;
  const defaultCount = currentHoldings.filter((holding) => ["default", "writtenOff"].includes(states.get(holding.id) ?? "")).length;
  const dueCount = currentHoldings.filter((holding) => states.get(holding.id) === "due").length;
  const lotsPerLoan = new Map<string, number>();
  for (const holding of currentHoldings) lotsPerLoan.set(holding.loan.loan_id, (lotsPerLoan.get(holding.loan.loan_id) ?? 0) + 1);
  const matchesFilter = (state: InvestmentState) =>
    status === "current" ||
    (status === "active" && (state === "active" || state === "funded")) ||
    (status === "due" && state === "due") ||
    (status === "late" && state === "late") ||
    (status === "default" && (state === "default" || state === "writtenOff"));
  const singleCurrency = new Set(currentHoldings.map((holding) => holding.currency)).size <= 1;
  const effectiveSort = sort === "principal" && !singleCurrency ? "maturity" : sort;
  const rows = sortHoldings(currentHoldings.filter((holding) => matchesFilter(states.get(holding.id) ?? "active")), effectiveSort);
  const statusOptions: Array<{ value: StatusFilter; label: string }> = [
    { value: "current", label: t("All current") },
    { value: "active", label: t("On schedule") },
    ...(dueCount > 0 ? [{ value: "due" as const, label: t("Payment due") }] : []),
    { value: "late", label: t("Late") },
    { value: "default", label: t("Default") }
  ];
  return (
    <section aria-labelledby="mi40-current-title" className="mi40-current">
      <div className="mi40-section-head">
        <div className="mi64-current-heading">
          <h2 id="mi40-current-title">{t("Current investments")} <span>{loanCount(currentHoldings)}</span></h2>
          {hasHistory ? (
            <a
              className="mi64-history"
              href="?view=history"
              onClick={(event) => {
                event.preventDefault();
                onHistory();
              }}
            >
              {t("View history")} <NiIcon name="arrow-up-right" />
            </a>
          ) : null}
        </div>
        {outstanding.size > 0 ? (
          <div className="mi64-capital">
            <span className="mi64-capital-label">
              {t("Outstanding principal")}
              <InfoTip label={t("Outstanding principal")} title={t("Outstanding principal")}>
                {t("The invested amount still to be repaid, excluding interest.")}
              </InfoTip>
            </span>
            <div className="mi40-current-total">
              {totalsList(outstanding).map(([code, amount]) => <CurrencyFigure amountMinor={amount} currency={code} key={code} />)}
            </div>
          </div>
        ) : null}
      </div>
      <div className="mi40-current-panel">
        {lateCount + defaultCount > 0 ? <PaymentUpdates defaultCount={defaultCount} lateCount={lateCount} onFilter={setStatus} signature={currentHoldings.filter((holding) => ["late", "default", "writtenOff"].includes(states.get(holding.id) ?? "")).map((holding) => `${holding.id}:${states.get(holding.id)}`).join("|")} /> : null}
        {currentHoldings.length === 0 ? (
          <EmptyState icon="growth" title={t("No current investments")}>
            {t("Investments appear here once their funding has closed. Reservations stay under In funding until then.")}
          </EmptyState>
        ) : (
          <>
            <div className="mi40-list-tools">
              <div className="mi40-filter-slot">
                <SelectFilter ariaLabel={t("Investment status")} className="bxm-mi-filter" label={t("Status")} onChange={setStatus} options={statusOptions} value={status} />
              </div>
              <SelectFilter
                ariaLabel={t("Sort investments")}
                className="mi64-sort-label"
                label={t("Sort")}
                onChange={setSort}
                options={[
                  { value: "maturity", label: t("Maturity: soonest") },
                  { value: "next", label: t("Next payment: soonest") },
                  { value: "principal", label: singleCurrency ? t("Outstanding principal: highest") : t("Outstanding principal: highest — select a currency"), disabled: !singleCurrency },
                  { value: "interest", label: t("Interest rate: highest") }
                ]}
                selectClassName="mi64-sort"
                value={effectiveSort}
              />
            </div>
            <div className="mi40-table-slot">
              {rows.length === 0 ? (
                <EmptyState icon="filter" title={t("No investments with this status")}>
                  <button className="link" onClick={() => setStatus("current")} type="button">{t("Show all current investments")}</button>
                </EmptyState>
              ) : (
                <table className="bxm-mi-table mi64-table">
                  <caption className="visually-hidden">{t("Your investments. Open an investment for its payment schedule, documents and available actions.")}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{t("Status")}</th>
                      <th scope="col">{t("Investment")}</th>
                      <th scope="col">{t("Outstanding principal")}</th>
                      <th scope="col">{t("Interest received")}</th>
                      <th scope="col">{t("Next payment")}</th>
                      <th scope="col"><span className="visually-hidden">{t("Details")}</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((holding) => (
                      <InvestmentRow
                        holding={holding}
                        key={holding.id}
                        multipleLots={(lotsPerLoan.get(holding.loan.loan_id) ?? 0) > 1}
                        onOpen={() => nav.go("investment", { holdingId: holding.id })}
                        state={states.get(holding.id) ?? "active"}
                      />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function InvestmentRow({ holding, state, multipleLots, onOpen }: { holding: Holding; state: InvestmentState; multipleLots: boolean; onOpen: () => void }) {
  const t = useT();
  const money = useMoneyText();
  const tag = stateTag(state, holding.loan.days_past_due);
  const receivedMinor = interestReceivedMinor(holding);
  const lifetime = lifetimeInterestMinor(holding);
  const overdue = overdueRows(holding);
  const next = nextPayment(holding);
  const maturity = maturityDate(holding);
  const inRecovery = state === "default" || state === "writtenOff";
  const listed = holding.open_secondary_listing?.status === "active";
  return (
    <tr
      className="bxm-mi-row"
      onClick={(event) => {
        if ((event.target as HTMLElement).closest("a, button")) return;
        onOpen();
      }}
    >
      <td className="mi64-status-cell" data-status={state}>
        <div className="bxm-mi-status">
          <StatusTag tone={tag.tone}>{tag.label}</StatusTag>
          {listed ? <StatusTag status="listed" /> : null}
        </div>
      </td>
      <td>
        <PortalLink className="bxm-mi-investment-link" params={{ holdingId: holding.id }} to="investment">
          <ProjectTile collateralType={holding.loan.collateral_type} />
          <div className="bxm-mi-identity">
            <h6 className="bxm-mi-name">{holding.loan.loan_title}</h6>
            <div className="bxm-mi-meta">
              {t("{borrower} · {rate} annual interest rate", { borrower: holding.loan.borrower_name, rate: formatRateBps(investorRateBps(holding.loan)) })}
            </div>
            {maturity && !inRecovery ? <div className="bxm-mi-meta bxm-mi-end-date">{t("Maturity · {date}", { date: formatDate(maturity) })}</div> : null}
            {multipleLots ? (
              <div className="bxm-mi-meta u33-lot-date">
                {holding.source_type === "secondary_market"
                  ? t("Bought on {date}", { date: formatDate(holding.assignment_effective_at) })
                  : t("Invested on {date}", { date: formatDate(holding.assignment_effective_at) })}
              </div>
            ) : null}
          </div>
        </PortalLink>
      </td>
      <td><span className="bxm-mi-primary">{money(holding.currency, holding.current_principal_minor)}</span></td>
      <td>
        <span className={`bxm-mi-primary${receivedMinor > 0 ? " bxm-mi-earned" : ""}`}>{money(holding.currency, receivedMinor)}</span>
        <span className="bxm-mi-secondary mi64-projection">
          {lifetime === null ? t("Projection unavailable") : t("out of {amount} projected", { amount: money(holding.currency, lifetime) })}
        </span>
      </td>
      <td>
        {inRecovery ? (
          <span>{t("Recovery in progress")}</span>
        ) : overdue.length > 0 ? (
          <>
            <span className="bxm-mi-primary bxm-mi-overdue">{formatDate(overdue[0].due_date)}</span>
            <span className="bxm-mi-secondary bxm-mi-overdue">{t("{amount} · Overdue", { amount: money(holding.currency, overdue[0].projected_total_minor) })}</span>
          </>
        ) : next ? (
          <>
            <span className="bxm-mi-primary">{formatDate(next.due_date)}</span>
            <span className="bxm-mi-secondary">{money(holding.currency, next.projected_total_minor)}</span>
          </>
        ) : (
          <span className="bxm-mi-secondary">{t("No scheduled payment")}</span>
        )}
      </td>
      <td>
        <PortalLink aria-label={t("Open {title}", { title: holding.loan.loan_title })} className="btn btn-sm btn-icon btn-trigger" params={{ holdingId: holding.id }} tabIndex={-1} to="investment">
          <NiIcon name="chevron-right" />
        </PortalLink>
      </td>
    </tr>
  );
}

const DISMISS_KEY = "banxum:u33-payment-updates-dismissed";

function readDismissed() {
  try {
    return window.sessionStorage.getItem(DISMISS_KEY) ?? "";
  } catch {
    return "";
  }
}

/**
 * The design's payment-update notice: Banxum follows up, the investor does not have to act. Closing it
 * hides it for this session only (the investments stay marked in the list); a new late or default
 * investment shows it again.
 */
function PaymentUpdates({ lateCount, defaultCount, signature, onFilter }: { lateCount: number; defaultCount: number; signature: string; onFilter: (status: StatusFilter) => void }) {
  const t = useT();
  const [dismissed, setDismissed] = useState(readDismissed);
  if (dismissed === signature) return null;
  const dismiss = () => {
    try {
      window.sessionStorage.setItem(DISMISS_KEY, signature);
    } catch {
      // Private mode: the notice is hidden until the page is reloaded.
    }
    setDismissed(signature);
  };
  return (
    <div className="mi40-notice-slot">
      <section aria-labelledby="ra-mi-updates-title" className="ra-mi-updates">
        <div className="ra-mi-update-copy">
          <h2 id="ra-mi-updates-title">{t("Payment updates")}</h2>
          <p>{t("Banxum follows up on overdue payments. No action is needed from you.")}</p>
        </div>
        <div className="ra-mi-update-links">
          {lateCount > 0 ? (
            <a className="is-late" href="#mi40-current-title" onClick={(event) => { event.preventDefault(); onFilter("late"); }}>
              {lateCount === 1 ? t("1 investment with late payments") : t("{count} investments with late payments", { count: lateCount })}
            </a>
          ) : null}
          {defaultCount > 0 ? (
            <a className="is-default" href="#mi40-current-title" onClick={(event) => { event.preventDefault(); onFilter("default"); }}>
              {defaultCount === 1 ? t("1 investment in default") : t("{count} investments in default", { count: defaultCount })}
            </a>
          ) : null}
        </div>
        <button aria-label={t("Dismiss payment updates")} className="ra-dismiss" onClick={dismiss} title={t("Dismiss payment updates")} type="button">
          <NiIcon name="cross" />
        </button>
      </section>
    </div>
  );
}
