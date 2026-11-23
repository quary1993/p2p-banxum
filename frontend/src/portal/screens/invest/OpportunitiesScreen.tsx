// IP of Webby-Soft SRL.
/*
 * Investment opportunities (design #/projects, slice S2): search, EUR/CHF, filters, sort, Cards/List,
 * the counter, Smart Invest match marks while a rule is active, and the link to past opportunities.
 * Filters are the ones today's data can apply: currency, security type, minimum rate, maximum term and
 * originator, and the design's maximum loan-to-value, borrower country and repayment structure (the
 * Smart Invest repayment groups). No ratings (U33-DEC-16), no purpose or loan-kind filters
 * (U33-DEC-19). No co-investment claim (U33-DEC-15).
 * U33-DEC-17: Coming soon opportunities follow the open ones, the next to open first, as in the design
 * (r31-coming-soon card without the funding block, "Opens {date}", the ol-soon list tag).
 * U33-DEC-18: a saved opportunity has the design's "Saved" badge (v107-saved-badge), which removes it.
 * C05 (2026-11-13): saved opportunities come first, as in the design; the chosen sort ("Closing
 * soonest" by default) orders the saved group and the other group.
 */
import { useState } from "react";

import { SmartInvestRepaymentEnum, type MarketplaceLoanPreview } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useBalancesData, useComingSoonLoansData, useMarketplaceLoansData, usePortfolioData, usePrimaryOrdersData, useSavedOpportunitiesData, useSmartInvestData } from "../../../investorPortal/data";
import { useSavedOpportunityActions } from "../../../investorPortal/savedOpportunities";
import { formatDate, formatDateShort, formatDecimal, formatMoneyLabel, formatMoneyMinor, formatPercent, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { Button, EmptyState, InfoTip, NiIcon, PageHead, PortalLink, usePortalNav } from "../../components";
import { CountryFlag } from "../../components/CountryFlag";
import {
  collateralGroup,
  collateralIcon,
  collateralLabel,
  closesInLabel,
  placeName,
  daysLeftLabel,
  existingClaimHelp,
  daysUntil,
  fundedPercent,
  isComingSoonLoan,
  isOpenLoan,
  isOriginatorClaimLoan,
  loanTypeLabel,
  countryName,
  loanLtv,
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
import { repaymentOption } from "../portfolio/parts/smartInvestModel";
import { readStored, writeStored } from "./storage";
import "./invest.css";

type Layout = "cards" | "list";
type Sort = "closing" | "newest" | "rate" | "term" | "funded";
type Filters = { q: string; currency: string; minRate: number | null; maxTerm: number | null; security: string[]; maxLtv: number | null; country: string; repayment: string[]; originator: string };

const LAYOUT_KEY = "banxum:marketplace-layout:v1";
const DIRECT = "direct";
const emptyFilters: Filters = { q: "", currency: "", minRate: null, maxTerm: null, security: [], maxLtv: null, country: "", repayment: [], originator: "" };
const rateOptions = [5, 6, 7, 8, 9, 10, 12];
const termOptions = [6, 12, 18, 24, 36, 48, 60];
/** Design: "Up to 60%" / "Up to 70%" / "Up to 80%" (maximum loan-to-value, C06 figure). */
const ltvOptions = [60, 70, 80];
/** Design "Repayment structure": the Smart Invest repayment groups (same grouping as the backend). */
const repaymentGroups: Array<[value: string, label: string]> = [
  [SmartInvestRepaymentEnum.principal_and_interest, "Periodic principal and interest"],
  [SmartInvestRepaymentEnum.interest_only, "Periodic interest; principal at maturity"],
  [SmartInvestRepaymentEnum.at_maturity, "Principal and interest at maturity"]
];
const groupOrder: SecurityGroup[] = ["physical", "rights", "guarantees", "other"];

/** U33-DEC-21: every security type in force; the collateral type for older payloads. */
function securityTypesOf(loan: MarketplaceLoanPreview) {
  return loan.security_types && loan.security_types.length > 0 ? loan.security_types : [loan.collateral_type];
}

type NumberFilter = "minRate" | "maxTerm" | "maxLtv";

/** A typed custom value (design bxm-op-custom: "7.5", "7,5"); null when empty or not a positive number. */
function parseCustomNumber(text: string) {
  const value = Number(text.trim().replace(/['’\s]/g, "").replace(",", "."));
  return text.trim() === "" || !Number.isFinite(value) || value <= 0 ? null : value;
}

function matchesFilters(loan: MarketplaceLoanPreview, filters: Filters) {
  const q = filters.q.trim().toLowerCase();
  if (q) {
    const text = `${loan.loan_id} ${loan.title} ${loan.borrower_display_name ?? ""} ${loan.originator_name ?? ""} ${collateralLabel(loan.collateral_type)}`.toLowerCase();
    if (!text.includes(q)) return false;
  }
  if (filters.currency && loan.currency !== filters.currency) return false;
  if (filters.minRate !== null && loanYieldBps(loan) < filters.minRate * 100) return false;
  if (filters.maxTerm !== null && loan.term_months > filters.maxTerm) return false;
  if (filters.security.length > 0 && !securityTypesOf(loan).some((type) => filters.security.includes(type))) return false;
  if (filters.maxLtv !== null) {
    // An opportunity without a stated loan-to-value does not match a limit (as Smart Invest).
    const ltv = loanLtv(loan);
    if (ltv === null || ltv > filters.maxLtv * 100) return false;
  }
  if (filters.country && (loan.borrower_country ?? "").toUpperCase() !== filters.country) return false;
  if (filters.repayment.length > 0) {
    const group = repaymentOption({ term_months: loan.term_months, repayment_type: loan.repayment_type });
    if (!group || !filters.repayment.includes(group)) return false;
  }
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

/** Coming soon: the next to open first (design: soon after open, by opening date). */
function sortComingSoon(loans: MarketplaceLoanPreview[]) {
  return [...loans].sort((a, b) => (a.planned_opening_date ?? "9999").localeCompare(b.planned_opening_date ?? "9999") || a.loan_id.localeCompare(b.loan_id));
}

function closingText(loan: MarketplaceLoanPreview, asOf: string | undefined, t: ReturnType<typeof useT>) {
  if (isComingSoonLoan(loan)) return t("Opens {date}", { date: formatDateShort(loan.planned_opening_date) });
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
  const soonQuery = useComingSoonLoansData();
  const savedIds = new Set((useSavedOpportunitiesData().data?.saved ?? []).map((item) => item.loan_id));
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
  // Design "Custom…": the field shows a number input next to its unit; the typed text is kept here.
  const [custom, setCustom] = useState<Record<NumberFilter, string | null>>({ minRate: null, maxTerm: null, maxLtv: null });
  const numberSelect = (key: NumberFilter, presets: number[]) => ({
    value: custom[key] !== null ? "custom" : filters[key] !== null && presets.includes(filters[key] as number) ? String(filters[key]) : "",
    onChange: (event: { target: { value: string } }) => {
      const next = event.target.value;
      if (next === "custom") {
        setCustom((current) => ({ ...current, [key]: "" }));
        update({ [key]: null } as Partial<Filters>);
        // As in the design, the typed value is next: move the focus to the new field.
        window.setTimeout(() => document.getElementById(`op-custom-${key}`)?.focus(), 0);
        return;
      }
      setCustom((current) => ({ ...current, [key]: null }));
      update({ [key]: next ? Number(next) : null } as Partial<Filters>);
    }
  });
  const customInput = (key: NumberFilter, label: string, unit: string, extraClass = "") =>
    custom[key] !== null ? (
      <div className={`bxm-op-custom${extraClass}`}>
        <input
          aria-label={label}
          id={`op-custom-${key}`}
          inputMode="decimal"
          onChange={(event) => {
            setCustom((current) => ({ ...current, [key]: event.target.value }));
            update({ [key]: parseCustomNumber(event.target.value) } as Partial<Filters>);
          }}
          type="text"
          value={custom[key] ?? ""}
        />
        <span>{unit}</span>
      </div>
    ) : null;

  const loans = loansQuery.data ?? [];
  const openLoans = loans.filter(isOpenLoan);
  const soonLoans = soonQuery.data ?? [];
  const listedLoans = [...openLoans, ...soonLoans];
  const ruleActive = smartInvestQuery.data?.rule?.is_active === true;
  const matchIds = new Set(ruleActive ? (smartInvestQuery.data?.matches ?? []).map((match) => match.loan_id) : []);
  const matchCount = openLoans.filter((loan) => matchIds.has(loan.loan_id)).length;
  const shown = (loan: MarketplaceLoanPreview) => matchesFilters(loan, filters) && (!matchesOnly || !ruleActive || matchIds.has(loan.loan_id));
  const visibleSoon = sortComingSoon(soonLoans.filter(shown));
  const sortedOpen = sortLoans(openLoans.filter(shown), sort);
  const visible = [...sortedOpen.filter((loan) => savedIds.has(loan.loan_id)), ...sortedOpen.filter((loan) => !savedIds.has(loan.loan_id)), ...visibleSoon];
  const currencies = Array.from(new Set(["EUR", "CHF", ...listedLoans.map((loan) => loan.currency)]));
  const securityTypes = Array.from(new Set(listedLoans.flatMap(securityTypesOf)));
  const originators = Array.from(
    new Map(listedLoans.filter((loan) => isOriginatorClaimLoan(loan) && loan.originator_id).map((loan) => [loan.originator_id as string, loan.originator_name ?? ""])).entries()
  ).sort((a, b) => a[1].localeCompare(b[1]));
  const countries = Array.from(new Set(listedLoans.map((loan) => (loan.borrower_country ?? "").toUpperCase()).filter(Boolean)))
    .map((code) => [code, countryName(code)] as const)
    .sort((a, b) => a[1].localeCompare(b[1]));
  const panelCount = [
    filters.minRate !== null,
    filters.maxTerm !== null,
    filters.security.length > 0,
    filters.maxLtv !== null,
    Boolean(filters.country),
    filters.repayment.length > 0,
    Boolean(filters.originator)
  ].filter(Boolean).length;
  const anyFilter = panelCount > 0 || Boolean(filters.q.trim()) || Boolean(filters.currency) || (matchesOnly && ruleActive);
  const securitySummary = filters.security.length === 0
    ? t("No preference")
    : filters.security.map(collateralLabel).join(", ");
  const repaymentSummary = filters.repayment.length === 0
    ? t("Any repayment")
    : repaymentGroups.filter(([value]) => filters.repayment.includes(value)).map(([, label]) => t(label)).join(", ");
  const maxInvestors = openLoans.map((loan) => loan.max_investors).find((value): value is number => typeof value === "number");
  const clearAll = () => {
    setFilters(emptyFilters);
    setCustom({ minRate: null, maxTerm: null, maxLtv: null });
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
              <select className="bxm-op-select" id="op-minRate" {...numberSelect("minRate", rateOptions)}>
                <option value="">{t("No preference")}</option>
                {rateOptions.map((rate) => <option key={rate} value={rate}>{t("{rate} or more", { rate: formatPercent(rate, 0) })}</option>)}
                <option value="custom">{t("Custom…")}</option>
              </select>
              {customInput("minRate", t("Custom minimum annual interest rate"), t("% per year"))}
            </div>
            <div className="bxm-op-field">
              <label htmlFor="op-maxTerm">{t("Maximum investment duration")}</label>
              <select className="bxm-op-select" id="op-maxTerm" {...numberSelect("maxTerm", termOptions)}>
                <option value="">{t("No preference")}</option>
                {termOptions.map((months) => <option key={months} value={months}>{t("Up to {count} months", { count: months })}</option>)}
                <option value="custom">{t("Custom…")}</option>
              </select>
              {customInput("maxTerm", t("Custom maximum investment duration"), t("months"))}
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
            <div className="bxm-op-field">
              <label htmlFor="op-minCover">
                {t("Maximum loan-to-value")}
                <InfoTip label={t("About loan-to-value")} title={t("Loan-to-value")}>
                  {t("The loan amount divided by the value of the assets that count for the loan-to-value. A lower figure leaves more room if an asset sells for less. An opportunity without a stated loan-to-value does not match a limit.")}
                </InfoTip>
              </label>
              <select className="bxm-op-select" id="op-minCover" {...numberSelect("maxLtv", ltvOptions)}>
                <option value="">{t("No preference")}</option>
                {ltvOptions.map((ltv) => <option key={ltv} value={ltv}>{t("Up to {ltv}", { ltv: formatPercent(ltv, 0) })}</option>)}
                <option value="custom">{t("Custom…")}</option>
              </select>
              {customInput("maxLtv", t("Maximum loan-to-value percent"), "%", " r79-ltv-custom")}
            </div>
          </div>
          <div className="bxm-op-more">
            <button aria-controls="op-secondary" aria-expanded={moreOpen} id="op-more-toggle" onClick={() => setMoreOpen((open) => !open)} type="button">
              <span>{t("More filters")}</span>
              <NiIcon name={moreOpen ? "chevron-up" : "chevron-down"} />
            </button>
          </div>
          <div className="bxm-op-grid" hidden={!moreOpen} id="op-secondary">
            <div className="bxm-op-field">
              <label htmlFor="op-country">{t("Borrower country")}</label>
              <select className="bxm-op-select" id="op-country" onChange={(event) => update({ country: event.target.value })} value={filters.country}>
                <option value="">{t("All countries")}</option>
                {countries.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
            </div>
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
            <div className="bxm-op-field">
              <span className="bxm-op-label" id="op-repayment-label">
                {t("Repayment structure")}
                <InfoTip label={t("About Repayment structure")} title={t("Repayment structure")}>
                  {t("How the borrower pays back: regular payments of principal and interest, regular interest with the principal at maturity, or everything at maturity. An opportunity matches any structure you select.")}
                </InfoTip>
              </span>
              <details className="bxm-op-multi" id="op-repayment-menu">
                <summary aria-labelledby="op-repayment-label op-repayment-value" className="bxm-op-select" id="op-repayment-toggle">
                  <span id="op-repayment-value" title={repaymentSummary}>{repaymentSummary}</span>
                </summary>
                <div className="bxm-op-options bxm-op-repayment-options">
                  <p className="bxm-op-hint">{t("Match any selected repayment structure.")}</p>
                  {repaymentGroups.map(([value, label]) => (
                    <label className="bxm-op-check" htmlFor={`op-repayment-${value}`} key={value}>
                      <input
                        checked={filters.repayment.includes(value)}
                        id={`op-repayment-${value}`}
                        onChange={(event) =>
                          update({ repayment: event.target.checked ? [...filters.repayment, value] : filters.repayment.filter((item) => item !== value) })
                        }
                        type="checkbox"
                      />
                      <span>{t(label)}</span>
                    </label>
                  ))}
                </div>
              </details>
            </div>
          </div>
        </section>

        <div className="bxm-op-result">
          <span role="status">
            <strong>{visible.length === 1 ? t("1 opportunity") : t("{count} opportunities", { count: visible.length })}</strong>
            {anyFilter ? ` · ${t("{count} open in total", { count: openLoans.length })}` : ` · ${t("{count} open", { count: openLoans.length })}`}
            {visibleSoon.length > 0 ? ` · ${t("{count} coming soon", { count: visibleSoon.length })}` : null}
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
            title={listedLoans.length === 0 ? t("No investment opportunities are open right now") : t("No opportunity matches these filters.")}
          >
            {listedLoans.length === 0 ? t("New opportunities appear here when they are published.") : t("Change or clear the filters to see more opportunities.")}
          </EmptyState>
        ) : layout === "cards" ? (
          <div className="row g-gs">
            {visible.map((loan) => <OpportunityCard asOf={asOf} invested={investedIds.has(loan.loan_id)} key={loan.loan_id} loan={loan} matched={matchIds.has(loan.loan_id)} saved={savedIds.has(loan.loan_id)} />)}
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
            {t("Some Swiss borrowers (10/20 mode) can have at most {count} creditors per financing and 20 in total. Their minimum can then be higher: what is still needed to reach minimum funding divided by the places left, rounded up.", { count: maxInvestors })}
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
      {t("This loan is to a Swiss borrower in 10/20 mode: at most {count} creditors in this financing and 20 in total. The minimum for a new investor is what is still needed to reach minimum funding divided by the places left, rounded up.", { count: places.maxInvestors })}
    </InfoTip>
  );
}

export function OpportunityCard({ loan, asOf, matched, invested, saved = false }: { loan: MarketplaceLoanPreview; asOf?: string; matched: boolean; invested: boolean; saved?: boolean }) {
  const t = useT();
  const savedActions = useSavedOpportunityActions();
  const percent = fundedPercent(loan);
  const places = placesInfo(loan);
  const company = isOriginatorClaimLoan(loan) ? loan.borrower_display_name || loan.originator_name : loan.borrower_display_name;
  const country = placeName(loan.borrower_city, loan.borrower_country);
  const payments = paymentFrequencyLabel(loan.repayment_type, loan.loan_status, loan.payment_frequency);
  const securityName = collateralLabel(loan.collateral_type);
  const securityDetail = loan.collateral_description && loan.collateral_description !== loan.collateral_type && loan.collateral_description !== securityName ? loan.collateral_description : "";
  const securityHelp = securityHelpText(loan.collateral_type) || securityVocabText();
  const soon = isComingSoonLoan(loan);
  return (
    <div className="col-md-6 col-xxl-4">
      <div className={`card card-bordered h-100${matched ? " si-highlighted" : ""}`}>
        <div className="card-inner">
          <div className={`project bxm-project r35-card${soon ? " r31-coming-soon" : ""}`}>
            <div className="project-head">
              <PortalLink className="project-title u33-invest-project-link" params={{ loanId: loan.loan_id }} to="loan">
                <div className="bxm-project-tile"><NiIcon name={projectIcon(loan)} /></div>
                <div className="project-info">
                  <h6 className="title">{loan.title}</h6>
                  {company && company !== loan.title ? <span className="sub-text">{company}</span> : null}
                </div>
              </PortalLink>
            </div>
            {country || invested || saved ? (
              <div className="r35-location">
                <span className="r35-location-text">{loan.borrower_country ? <CountryFlag code={loan.borrower_country} /> : null}<span>{country}</span></span>
                <span className="r35-location-badges">
                  {invested ? <span className="bxm-tag is-muted">{t("Invested")}</span> : null}
                  {saved ? (
                    <button
                      aria-label={t("Remove saved opportunity: {title}", { title: loan.title })}
                      className="v107-saved-badge"
                      disabled={savedActions.busy}
                      onClick={() => void savedActions.remove(loan.loan_id).catch(() => undefined)}
                      type="button"
                    >
                      <NiIcon name="bookmark" />{t("Saved")}
                    </button>
                  ) : null}
                </span>
              </div>
            ) : null}
            <div className="bxm-project-tags">
              {soon ? <span className="bxm-tag">{t("Coming soon")}</span> : <span className="bxm-tag is-open">{t("Open")}</span>}
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
              <PortalLink aria-label={t("View details of {title}", { title: loan.title })} className={`btn btn-sm ${soon ? "btn-outline-light" : "btn-primary"}`} params={{ loanId: loan.loan_id }} to="loan">{t("View details")}</PortalLink>
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
            const payments = paymentFrequencyLabel(loan.repayment_type, loan.loan_status, loan.payment_frequency);
            const soon = isComingSoonLoan(loan);
            const days = soon || usesImmediateClaimAssignment(loan) ? null : daysUntil(loan.funding_deadline, asOf);
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
                  {soon ? null : (
                    <span className="ol-secondary ol-min r31-minimum">
                      {t("Min. {amount}", { amount: formatMoneyLabel(loan.currency, loan.minimum_investment_minor) })}
                      <MinimumInfo loan={loan} />
                    </span>
                  )}
                </td>
                <td>
                  {soon ? <span className="bxm-tag ol-status ol-soon">{t("Coming soon")}</span> : <span className="bxm-tag ol-status r75-desktop-hidden">{t("Open")}</span>}
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
