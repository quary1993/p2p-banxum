// IP of Webby-Soft SRL.
/*
 * Investment opportunities (design #/projects, slice S2): search, EUR/CHF, filters, sort, Cards/List,
 * the counter, Smart Invest match marks while a rule is active, and the link to past opportunities.
 * Filters are the ones today's data can apply: currency, security type, minimum rate, maximum term and
 * originator. No ratings (U33-DEC-16), no purpose or loan-kind filters (U33-DEC-19); LTV, country and
 * repayment filters wait for Phase 17.2/17.4 data. No co-investment claim (U33-DEC-15).
 */
import { useState } from "react";

import type { MarketplaceLoanPreview } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useBalancesData, useMarketplaceLoansData, usePortfolioData, usePrimaryOrdersData, useSmartInvestData } from "../../../investorPortal/data";
import { formatDate, formatDecimal, formatMoneyLabel, formatMoneyMinor, formatPercent, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { Button, EmptyState, InfoTip, NiIcon, PageHead, PortalLink, usePortalNav } from "../../components";
import {
  collateralGroup,
  collateralIcon,
  collateralLabel,
  closesInLabel,
  countryName,
  daysLeftLabel,
  existingClaimHelp,
  daysUntil,
  fundedPercent,
  isOpenLoan,
  isOriginatorClaimLoan,
  loanTypeLabel,
  loanYieldBps,
  paymentFrequencyLabel,
  placesInfo,
  projectIcon,
  securityGroupLabels,
  securityHelpText,
  securityVocabText,
  usesImmediateClaimAssignment,
  type SecurityGroup
} from "./loanFacts";
import { isOpenOrder } from "../portfolio/parts/investmentModel";
import { readStored, writeStored } from "./storage";
import "./invest.css";

type Layout = "cards" | "list";
type Sort = "closing" | "newest" | "rate" | "term" | "funded";
type Filters = { q: string; currency: string; minRate: number | null; maxTerm: number | null; security: string[]; originator: string };

const LAYOUT_KEY = "banxum:marketplace-layout:v1";
const DIRECT = "direct";
const emptyFilters: Filters = { q: "", currency: "", minRate: null, maxTerm: null, security: [], originator: "" };
const rateOptions = [5, 6, 7, 8, 9, 10, 12];
const termOptions = [6, 12, 18, 24, 36, 48, 60];
const groupOrder: SecurityGroup[] = ["physical", "rights", "guarantees", "other"];

function matchesFilters(loan: MarketplaceLoanPreview, filters: Filters) {
  const q = filters.q.trim().toLowerCase();
  if (q) {
    const text = `${loan.loan_id} ${loan.title} ${loan.borrower_display_name ?? ""} ${loan.originator_name ?? ""} ${collateralLabel(loan.collateral_type)}`.toLowerCase();
    if (!text.includes(q)) return false;
  }
  if (filters.currency && loan.currency !== filters.currency) return false;
  if (filters.minRate !== null && loanYieldBps(loan) < filters.minRate * 100) return false;
  if (filters.maxTerm !== null && loan.term_months > filters.maxTerm) return false;
  if (filters.security.length > 0 && !filters.security.includes(loan.collateral_type)) return false;
  if (filters.originator) {
    const source = isOriginatorClaimLoan(loan) ? loan.originator_id ?? "" : DIRECT;
    if (source !== filters.originator) return false;
  }
  return true;
}

function closingKey(loan: MarketplaceLoanPreview) {
  return loan.funding_deadline ?? loan.maturity_date ?? "9999-12-31";
}

function sortLoans(loans: MarketplaceLoanPreview[], sort: Sort) {
  return [...loans].sort((a, b) => {
    if (sort === "rate") return loanYieldBps(b) - loanYieldBps(a);
    if (sort === "term") return a.term_months - b.term_months || closingKey(a).localeCompare(closingKey(b));
    if (sort === "funded") return fundedPercent(b) - fundedPercent(a);
    if (sort === "newest") return (b.published_at ?? "").localeCompare(a.published_at ?? "") || closingKey(a).localeCompare(closingKey(b));
    return closingKey(a).localeCompare(closingKey(b));
  });
}

/** Compact loan amount of the cards ("450k", "1,45m"); the full amount is the title and accessible name. */
function compactAmount(amountMinor: number, currency: string) {
  const whole = amountMinor / 100;
  const trimmed = (value: number) => {
    const decimals = Number.isInteger(value) ? 0 : Number.isInteger(value * 10) ? 1 : 2;
    return formatDecimal(value, decimals);
  };
  if (whole >= 1_000_000) return `${trimmed(Math.round(whole / 10_000) / 100)}M`;
  if (whole >= 1_000) return `${trimmed(Math.round(whole / 100) / 10)}k`;
  return formatMoneyMinor(amountMinor, currency, 0);
}

function closingText(loan: MarketplaceLoanPreview, asOf: string | undefined, t: ReturnType<typeof useT>) {
  if (usesImmediateClaimAssignment(loan)) {
    return loan.maturity_date ? t("Matures {date}", { date: formatDate(loan.maturity_date) }) : t("Open while performing");
  }
  const days = daysUntil(loan.funding_deadline, asOf);
  return days === null ? "" : daysLeftLabel(days);
}

export function OpportunitiesScreen({ initialMatchesOnly = false }: { initialMatchesOnly?: boolean }) {
  const t = useT();
  useNumberFormat();
  const nav = usePortalNav();
  const loansQuery = useMarketplaceLoansData();
  const smartInvestQuery = useSmartInvestData();
  const asOf = useBalancesData().data?.as_of;
  // Design "Invested" mark: a loan the investor holds or has an open reservation in.
  const holdings = usePortfolioData(true).data?.holdings;
  const orders = usePrimaryOrdersData().data?.orders;
  const investedIds = new Set([
    ...(holdings ?? []).filter((holding) => holding.status !== "transferred").map((holding) => holding.loan.loan_id),
    ...(orders ?? []).filter(isOpenOrder).map((order) => order.loan_id)
  ]);
  const [layout, setLayoutState] = useState<Layout>(() => (readStored(LAYOUT_KEY) === "list" ? "list" : "cards"));
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [panelOpen, setPanelOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [sort, setSort] = useState<Sort>("closing");
  const [matchesOnly, setMatchesOnly] = useState(initialMatchesOnly);

  const setLayout = (next: Layout) => {
    setLayoutState(next);
    writeStored(LAYOUT_KEY, next);
  };
  const update = (patch: Partial<Filters>) => setFilters((current) => ({ ...current, ...patch }));

  const loans = loansQuery.data ?? [];
  const openLoans = loans.filter(isOpenLoan);
  const ruleActive = smartInvestQuery.data?.rule?.is_active === true;
  const matchIds = new Set(ruleActive ? (smartInvestQuery.data?.matches ?? []).map((match) => match.loan_id) : []);
  const matchCount = openLoans.filter((loan) => matchIds.has(loan.loan_id)).length;
  const visible = sortLoans(
    openLoans.filter((loan) => matchesFilters(loan, filters) && (!matchesOnly || !ruleActive || matchIds.has(loan.loan_id))),
    sort
  );
  const currencies = Array.from(new Set(["EUR", "CHF", ...openLoans.map((loan) => loan.currency)]));
  const securityTypes = Array.from(new Set(openLoans.map((loan) => loan.collateral_type)));
  const originators = Array.from(
    new Map(openLoans.filter((loan) => isOriginatorClaimLoan(loan) && loan.originator_id).map((loan) => [loan.originator_id as string, loan.originator_name ?? ""])).entries()
  ).sort((a, b) => a[1].localeCompare(b[1]));
  const panelCount = [filters.minRate !== null, filters.maxTerm !== null, filters.security.length > 0, Boolean(filters.originator)].filter(Boolean).length;
  const anyFilter = panelCount > 0 || Boolean(filters.q.trim()) || Boolean(filters.currency) || (matchesOnly && ruleActive);
  const securitySummary = filters.security.length === 0
    ? t("No preference")
    : filters.security.map(collateralLabel).join(", ");
  const maxInvestors = openLoans.map((loan) => loan.max_investors).find((value): value is number => typeof value === "number");
  const clearAll = () => {
    setFilters(emptyFilters);
    setMatchesOnly(false);
  };

  return (
    <main className="u33-invest-opportunities">
      <PageHead
        actions={[
          <PortalLink className="btn btn-outline-light" key="originators" params={{ view: "originators" }} to="market">
            <NiIcon name="building" /><span>{t("Loan originators")}</span>
          </PortalLink>,
          <div aria-label={t("View")} className="bxm-seg" key="view" role="group">
            <button aria-pressed={layout === "cards"} className={layout === "cards" ? "active" : ""} onClick={() => setLayout("cards")} type="button">
              <NiIcon name="view-grid-wd" /><span>{t("Cards")}</span>
            </button>
            <button aria-pressed={layout === "list"} className={layout === "list" ? "active" : ""} onClick={() => setLayout("list")} type="button">
              <NiIcon name="view-list-wd" /><span>{t("List")}</span>
            </button>
          </div>
        ]}
        title={t("Investment opportunities")}
      />

      <div className="nk-block bxm-op-controls">
        <div className="bxm-op-toolbar">
          <form className="bxm-op-search" onSubmit={(event) => event.preventDefault()} role="search">
            <NiIcon name="search" />
            <input
              aria-label={t("Search opportunities")}
              id="op-search"
              name="q"
              onChange={(event) => update({ q: event.target.value })}
              placeholder={t("Search opportunities")}
              type="search"
              value={filters.q}
            />
          </form>
          <div aria-label={t("Currency")} className="bxm-op-currency" role="group">
            {[["", t("All")], ...currencies.map((code) => [code, code])].map(([value, label]) => (
              <button aria-pressed={filters.currency === value} key={value || "all"} onClick={() => update({ currency: value })} type="button">{label}</button>
            ))}
          </div>
          {ruleActive ? (
            <button aria-pressed={matchesOnly} className="si-matches-filter" onClick={() => setMatchesOnly((value) => !value)} type="button">
              {t("Smart Invest")} <span>{matchCount}</span>
            </button>
          ) : (
            <button className="si-matches-filter rid-setup-entry" onClick={() => nav.go("smartInvest")} type="button">
              {t("Set up Smart Invest")} <NiIcon name="arrow-right" />
            </button>
          )}
          <button aria-controls="op-panel" aria-expanded={panelOpen} className="bxm-op-toggle" id="op-toggle" onClick={() => setPanelOpen((open) => !open)} type="button">
            <NiIcon name="filter" />
            <span>{panelCount > 0 ? t("Filters ({count})", { count: panelCount }) : t("Filters")}</span>
            <NiIcon name={panelOpen ? "chevron-up" : "chevron-down"} />
          </button>
          <label className="bxm-op-sort" htmlFor="op-sort">
            {t("Sort")}
            <select className="bxm-op-select" id="op-sort" onChange={(event) => setSort(event.target.value as Sort)} value={sort}>
              <option value="closing">{t("Closing soonest")}</option>
              <option value="newest">{t("Newest")}</option>
              <option value="rate">{t("Highest interest")}</option>
              <option value="term">{t("Shortest term")}</option>
              <option value="funded">{t("Most funded")}</option>
            </select>
          </label>
        </div>

        <section aria-label={t("Investment filters")} className="bxm-op-panel" hidden={!panelOpen} id="op-panel">
          <div className="bxm-op-grid">
            <div className="bxm-op-field">
              <label htmlFor="op-minRate">{t("Minimum annual interest rate")}</label>
              <select className="bxm-op-select" id="op-minRate" onChange={(event) => update({ minRate: event.target.value ? Number(event.target.value) : null })} value={filters.minRate ?? ""}>
                <option value="">{t("No preference")}</option>
                {rateOptions.map((rate) => <option key={rate} value={rate}>{t("{rate} or more", { rate: formatPercent(rate, 0) })}</option>)}
              </select>
            </div>
            <div className="bxm-op-field">
              <label htmlFor="op-maxTerm">{t("Maximum investment duration")}</label>
              <select className="bxm-op-select" id="op-maxTerm" onChange={(event) => update({ maxTerm: event.target.value ? Number(event.target.value) : null })} value={filters.maxTerm ?? ""}>
                <option value="">{t("No preference")}</option>
                {termOptions.map((months) => <option key={months} value={months}>{t("Up to {count} months", { count: months })}</option>)}
              </select>
            </div>
            <div className="bxm-op-field">
              <span className="bxm-op-label" id="op-collateral-label">
                {t("Security type")}
                <InfoTip label={t("Security type")} title={t("Security type")}>
                  {t("The collateral or guarantee recorded for the loan. Select one or more types; at least one must match.")}
                </InfoTip>
              </span>
              <details className="bxm-op-multi" id="op-collateral-menu">
                <summary aria-labelledby="op-collateral-label op-collateral-value" className="bxm-op-select" id="op-collateral-toggle">
                  <span id="op-collateral-value" title={securitySummary}>{securitySummary}</span>
                </summary>
                <div className="bxm-op-options" data-r75-groups="true">
                  <p className="bxm-op-hint">{t("Select one or more security types. At least one must match.")}</p>
                  {groupOrder.map((group) => {
                    const types = securityTypes.filter((type) => collateralGroup(type) === group).sort((a, b) => collateralLabel(a).localeCompare(collateralLabel(b)));
                    if (types.length === 0) return null;
                    return (
                      <fieldset key={group}>
                        <legend>{t(securityGroupLabels[group])}</legend>
                        {types.map((type) => (
                          <div className="bxm-op-option-row" key={type}>
                            <label className="bxm-op-check" htmlFor={`op-collateral-${type}`}>
                              <input
                                checked={filters.security.includes(type)}
                                id={`op-collateral-${type}`}
                                onChange={(event) =>
                                  update({ security: event.target.checked ? [...filters.security, type] : filters.security.filter((item) => item !== type) })
                                }
                                type="checkbox"
                              />
                              <span>{collateralLabel(type)}</span>
                            </label>
                          </div>
                        ))}
                      </fieldset>
                    );
                  })}
                </div>
              </details>
            </div>
          </div>
          <div className="bxm-op-more">
            <button aria-controls="op-secondary" aria-expanded={moreOpen} id="op-more-toggle" onClick={() => setMoreOpen((open) => !open)} type="button">
              <span>{moreOpen ? t("Fewer filters") : t("More filters")}</span>
              <NiIcon name={moreOpen ? "chevron-up" : "chevron-down"} />
            </button>
          </div>
          <div className="bxm-op-grid" hidden={!moreOpen} id="op-secondary">
            <div className="bxm-op-field">
              <label htmlFor="op-originator">
                {t("Originator")}
                <InfoTip label={t("Originator")} title={t("Originator")}>
                  {t("Banxum lends directly, or offers existing claims of a loan originator. The originator is named on each opportunity.")}
                </InfoTip>
              </label>
              <select className="bxm-op-select" id="op-originator" onChange={(event) => update({ originator: event.target.value })} value={filters.originator}>
                <option value="">{t("All originators")}</option>
                <option value={DIRECT}>{t("Banxum (direct)")}</option>
                {originators.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
              </select>
            </div>
          </div>
        </section>

        <div className="bxm-op-result">
          <span role="status">
            <strong>{visible.length === 1 ? t("1 opportunity") : t("{count} opportunities", { count: visible.length })}</strong>
            {anyFilter ? ` · ${t("{count} open in total", { count: openLoans.length })}` : ` · ${t("{count} open", { count: openLoans.length })}`}
          </span>
          {anyFilter ? <button className="link u33-invest-clear" onClick={clearAll} type="button">{t("Clear filters")}</button> : null}
        </div>
      </div>

      <div className="nk-block bxm-op-results">
        {loansQuery.isError && loans.length === 0 ? (
          <EmptyState actions={<Button onClick={() => void loansQuery.refetch()} variant="primary">{t("Retry")}</Button>} icon="alert-circle" title={t("We could not load the opportunities")}>
            {t("Try again in a moment.")}
          </EmptyState>
        ) : loansQuery.isPending && loans.length === 0 ? (
          <EmptyState icon="clock" title={t("Loading opportunities")} />
        ) : visible.length === 0 ? (
          <EmptyState
            actions={anyFilter ? <Button onClick={clearAll} variant="primary">{t("Clear filters")}</Button> : <Button onClick={() => nav.go("smartInvest")}>{t("Set up Smart Invest")}</Button>}
            icon="search"
            title={openLoans.length === 0 ? t("No investment opportunities are open right now") : t("No opportunity matches these filters")}
          >
            {openLoans.length === 0 ? t("New opportunities appear here when they are published.") : t("Change or clear the filters to see more opportunities.")}
          </EmptyState>
        ) : layout === "cards" ? (
          <div className="row g-gs">
            {visible.map((loan) => <OpportunityCard asOf={asOf} invested={investedIds.has(loan.loan_id)} key={loan.loan_id} loan={loan} matched={matchIds.has(loan.loan_id)} />)}
          </div>
        ) : (
          <OpportunityList asOf={asOf} loans={visible} matchIds={matchIds} />
        )}
      </div>

      <div className="bxm-op-archive-link">
        <PortalLink className="link" params={{ view: "archive" }} to="market">{t("Past opportunities")} <NiIcon name="arrow-right" /></PortalLink>
      </div>
      <div className="nk-block">
        {typeof maxInvestors === "number" ? (
          <p className="bxm-muted small">
            {t("Loans to Swiss borrowers can have at most {count} investors. Their minimum can then be higher: what is still needed to reach minimum funding divided by the places left, rounded up.", { count: maxInvestors })}
          </p>
        ) : null}
        <p className="bxm-muted small r31-risk-warning">{t("Past repayments do not guarantee future ones; you can lose part or all of your investment.")}</p>
      </div>
    </main>
  );
}

function MinimumInfo({ loan }: { loan: MarketplaceLoanPreview }) {
  const t = useT();
  const places = placesInfo(loan);
  if (!places) return null;
  return (
    <InfoTip label={t("Why this minimum?")} title={t("Why this minimum?")}>
      {t("This loan is to a Swiss borrower and can have at most {count} investors. The minimum for a new investor is what is still needed to reach minimum funding divided by the places left, rounded up.", { count: places.maxInvestors })}
    </InfoTip>
  );
}

export function OpportunityCard({ loan, asOf, matched, invested }: { loan: MarketplaceLoanPreview; asOf?: string; matched: boolean; invested: boolean }) {
  const t = useT();
  const percent = fundedPercent(loan);
  const places = placesInfo(loan);
  const company = isOriginatorClaimLoan(loan) ? loan.borrower_display_name || loan.originator_name : loan.borrower_display_name;
  const country = countryName(loan.borrower_country);
  const payments = paymentFrequencyLabel(loan.repayment_type, loan.loan_status);
  const securityName = collateralLabel(loan.collateral_type);
  const securityDetail = loan.collateral_description && loan.collateral_description !== loan.collateral_type && loan.collateral_description !== securityName ? loan.collateral_description : "";
  const securityHelp = securityHelpText(loan.collateral_type) || securityVocabText();
  return (
    <div className="col-md-6 col-xxl-4">
      <div className={`card card-bordered h-100${matched ? " si-highlighted" : ""}`}>
        <div className="card-inner">
          <div className="project bxm-project r35-card">
            <div className="project-head">
              <PortalLink className="project-title u33-invest-project-link" params={{ loanId: loan.loan_id }} to="loan">
                <div className="bxm-project-tile"><NiIcon name={projectIcon(loan)} /></div>
                <div className="project-info">
                  <h6 className="title">{loan.title}</h6>
                  {company && company !== loan.title ? <span className="sub-text">{company}</span> : null}
                </div>
              </PortalLink>
            </div>
            {country || invested ? (
              <div className="r35-location">
                <span className="r35-location-text"><span>{country}</span></span>
                <span className="r35-location-badges">{invested ? <span className="bxm-tag is-muted">{t("Invested")}</span> : null}</span>
              </div>
            ) : null}
            <div className="bxm-project-tags">
              <span className="bxm-tag is-open">{t("Open")}</span>
              <span className="bxm-tag is-type">{loanTypeLabel(loan)}</span>
              {isOriginatorClaimLoan(loan) ? <InfoTip label={t("Existing claim")} title={t("Existing claim")}>{existingClaimHelp()}</InfoTip> : null}
              {matched ? <span aria-label={t("Smart Invest: matches your Smart Invest preferences.")} className="bxm-tag si-match-label" title={t("Matches your Smart Invest preferences.")}>{t("Smart Invest")}</span> : null}
            </div>
            <div className="r60-card-terms">
              <dl className="bxm-project-figures">
                <div><dt>{t("Annual interest")}</dt><dd>{formatRateBps(loanYieldBps(loan))}</dd></div>
                <div><dt>{t("Term")}</dt><dd>{t("{count} mo", { count: loan.term_months })}{payments ? <small className="r74-card-payments">{payments}</small> : null}</dd></div>
                <div>
                  <dt>{t("Loan amount · {currency}", { currency: loan.currency })}</dt>
                  <dd aria-label={formatMoneyLabel(loan.currency, loan.principal_minor)} tabIndex={0} title={formatMoneyLabel(loan.currency, loan.principal_minor)}>
                    {compactAmount(loan.principal_minor, loan.currency)}
                  </dd>
                </div>
              </dl>
            </div>
            <section className="r35-security">
              <div className="r35-security-heading">
                {t("Security")}
                <InfoTip label={t("Security")} title={t("Security")}>{securityHelp}</InfoTip>
              </div>
              <div className="r35-security-content">
                <NiIcon className="r35-security-icon" name={collateralIcon(loan.collateral_type)} />
                <div>
                  <strong>{securityName}</strong>
                  {securityDetail ? <small>{securityDetail}</small> : null}
                </div>
              </div>
            </section>
            <div className="bxm-project-progress r31-lean-funding">
              <div className="bxm-project-row">
                <span className="r31-discovery-hidden"><strong>{formatMoneyLabel(loan.currency, loan.committed_principal_minor)}</strong> {t("funded")}</span>
                <strong>{formatPercent(Math.round(percent), 0)} <span className="r31-funded-label">{t("of loan funded")}</span></strong>
              </div>
              <div aria-valuemax={100} aria-valuemin={0} aria-valuenow={Math.round(percent)} className="bxm-progress" role="progressbar">
                <span style={{ width: `${percent}%` }} />
              </div>
              <div className="bxm-project-row">
                {/* Design: the investor count stays in the markup but is hidden on the cards (r31-discovery-hidden). */}
                {places ? <span className="r31-discovery-hidden">{t("{investors} of {max} investors", { investors: places.investors, max: places.maxInvestors })}</span> : <span />}
                <span className="r31-minimum">
                  {t("Min. {amount}", { amount: formatMoneyLabel(loan.currency, loan.minimum_investment_minor) })}
                  <MinimumInfo loan={loan} />
                </span>
              </div>
            </div>
            <div className="project-meta mt-3">
              <span className="bxm-muted"><NiIcon name="clock" /> {closingText(loan, asOf, t)}</span>
              <PortalLink aria-label={t("View details of {title}", { title: loan.title })} className="btn btn-sm btn-primary" params={{ loanId: loan.loan_id }} to="loan">{t("View details")}</PortalLink>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function OpportunityList({ loans, asOf, matchIds }: { loans: MarketplaceLoanPreview[]; asOf?: string; matchIds: Set<string> }) {
  const t = useT();
  return (
    <section aria-label={t("Investment opportunities list")} className="ol-preview">
      <table className="ol-table">
        <colgroup>
          <col style={{ width: "32%" }} />
          <col style={{ width: "12%" }} />
          <col style={{ width: "15%" }} />
          <col style={{ width: "16%" }} />
          <col style={{ width: "14%" }} />
          <col style={{ width: "11%" }} />
        </colgroup>
        <thead>
          <tr>
            <th>{t("Opportunity")}</th>
            <th>{t("Annual interest rate")}<br /><span className="ol-heading-secondary">{t("Term")}</span></th>
            <th>{t("Security")} <InfoTip label={t("Security")} title={t("Security")}>{securityVocabText()}</InfoTip></th>
            <th>{t("Loan amount")}</th>
            <th>{t("Availability")}</th>
            <th><span className="visually-hidden">{t("Details")}</span></th>
          </tr>
        </thead>
        <tbody>
          {loans.map((loan) => {
            const name = loan.borrower_display_name && loan.borrower_display_name !== loan.title ? loan.borrower_display_name : loan.originator_name;
            // Design: "Company · CC".
            const company = [name, loan.borrower_country ? loan.borrower_country.toUpperCase() : ""].filter(Boolean).join(" · ");
            const securityName = collateralLabel(loan.collateral_type);
            const securityDetail = loan.collateral_description && loan.collateral_description !== loan.collateral_type && loan.collateral_description !== securityName ? loan.collateral_description : "";
            const payments = paymentFrequencyLabel(loan.repayment_type, loan.loan_status);
            const days = usesImmediateClaimAssignment(loan) ? null : daysUntil(loan.funding_deadline, asOf);
            return (
              <tr className="r75-list-row" data-project={loan.loan_id} key={loan.loan_id}>
                <td>
                  <div className="ol-project">
                    <span className="bxm-project-tile"><NiIcon name={projectIcon(loan)} /></span>
                    <div className="ol-project-info">
                      <PortalLink className="ol-title" params={{ loanId: loan.loan_id }} to="loan">{loan.title}</PortalLink>
                      {matchIds.has(loan.loan_id) ? <span className="si-list-match" title={t("Matches your Smart Invest preferences.")}>{t("Smart Invest")}</span> : null}
                      {company ? <div className="ol-company">{company}</div> : null}
                      <div className="ol-tags">
                        <span className="bxm-tag ol-type r75-desktop-hidden">{loanTypeLabel(loan)}</span>
                        {isOriginatorClaimLoan(loan) ? <span className="r75-desktop-hidden"><InfoTip label={t("Existing claim")} title={t("Existing claim")}>{existingClaimHelp()}</InfoTip></span> : null}
                      </div>
                    </div>
                  </div>
                </td>
                <td>
                  <span className="ol-rate">{formatRateBps(loanYieldBps(loan))} <span className="ol-per">{t("/ year")}</span></span>
                  <span className="ol-secondary">{t("{count} months", { count: loan.term_months })}</span>
                  {payments ? <small className="r75-list-cadence">{payments}</small> : null}
                </td>
                <td>
                  <span className="ol-security">
                    <strong>{securityName}</strong>
                    {securityDetail ? <small>{securityDetail}</small> : null}
                  </span>
                </td>
                <td>
                  <strong className="ol-money">{`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency, 0)}`}</strong>
                  <span className="ol-secondary ol-min r31-minimum">
                    {t("Min. {amount}", { amount: formatMoneyLabel(loan.currency, loan.minimum_investment_minor) })}
                    <MinimumInfo loan={loan} />
                  </span>
                </td>
                <td>
                  <span className="bxm-tag ol-status r75-desktop-hidden">{t("Open")}</span>
                  <span className="ol-secondary ol-time">{days === null ? closingText(loan, asOf, t) : closesInLabel(days)}</span>
                </td>
                <td className="ol-action">
                  <PortalLink aria-label={t("View details of {title}", { title: loan.title })} className="ol-details" params={{ loanId: loan.loan_id }} to="loan">
                    {t("View details")} <NiIcon name="arrow-right" />
                  </PortalLink>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
