// IP of Webby-Soft SRL.
/*
 * Statistics in the U33 public design (U33-DEC-39, Q24, D-10: real data, CHF and EUR separate; a
 * larger redesign later). The design has no statistics page; it uses the legal page hero, the
 * document card and white panels in the design's visual language (Q23).
 *
 * Data: usePublicStatistics() for the figures and the amounts by currency, usePublicProjects()
 * for the track record (every funded loan with a repayment record: repaying, late, repaid,
 * default; newest funding first). No risk rating (U33-DEC-16).
 *
 * "How we count" follows the servicing rules (IMPLEMENTATION_PLAN 18.6, U33-DEC-09): late from
 * day 15; from day 60 Banxum can declare the loan in default (no automatic default); a loan
 * contract can set other days.
 */
import { useMemo } from "react";

import { useT } from "../../../i18n";
import { useSiteTitle } from "../../context";
import { usePublicProjects, usePublicStatistics, type PublicProject, type PublicStatistics } from "../../data";
import { date, dateKey, moneyMinor, numMinor, pctBps, siteToday } from "../../format";
import { countryName, projectView, recordTag } from "../../projects";
import { statusBadge } from "../loans";
import { PublicLink } from "../ui";

const CURRENCIES = ["CHF", "EUR"] as const;

export function Statistics() {
  const t = useT();
  useSiteTitle(t("Statistics"));
  const statsQuery = usePublicStatistics();
  const projectsQuery = usePublicProjects();
  const funded = useMemo(
    () =>
      (projectsQuery.data ?? [])
        .filter((p) => p.record && recordTag(p))
        .sort((a, b) => (b.funded_at ?? "").localeCompare(a.funded_at ?? "")),
    [projectsQuery.data]
  );
  const stats = statsQuery.data;

  return (
    <div className="content-shell legal-view bxp-statistics">
      <section aria-labelledby="statistics-title" className="page-hero legal-hero">
        <p className="page-kicker">{t("STATISTICS")}</p>
        <h1 className="page-title" id="statistics-title">
          {t("Every loan, including the ones that went wrong")}
        </h1>
        <p className="page-lead">{t("All loans funded on Banxum. Built from live data, so it is always current.")}</p>
      </section>
      {stats ? (
        <>
          <div aria-label={t("Key figures")} className="bxp-figures">
            <Figure label={t("loans funded")} value={stats.loans_funded} />
            <Figure label={t("repaid in full")} value={stats.loans_repaid} />
            <Figure label={t("with a late payment now")} value={stats.loans_late} />
            <Figure label={t("in default")} value={stats.loans_defaulted} />
          </div>
          <Amounts stats={stats} />
        </>
      ) : (
        <div className="bxp-notice-card" role="status">
          {statsQuery.isError ? (
            <p>
              {t("The statistics could not be loaded.")}{" "}
              <button className="bxp-text-button" onClick={() => void statsQuery.refetch()} type="button">
                {t("Try again")}
              </button>
            </p>
          ) : (
            <p>{t("Loading the statistics.")}</p>
          )}
        </div>
      )}
      <section aria-labelledby="track-title" className="bxp-stat-section">
        <p className="page-kicker">{t("TRACK RECORD")}</p>
        <h2 className="section-title" id="track-title">
          {t("All funded loans")}
        </h2>
        {projectsQuery.isSuccess ? (
          funded.length ? (
            <FundedTable projects={funded} />
          ) : (
            <div className="bxp-notice-card">
              <p>{t("No loan has been funded yet.")}</p>
            </div>
          )
        ) : (
          <div className="bxp-notice-card" role="status">
            {projectsQuery.isError ? (
              <p>
                {t("The loans could not be loaded.")}{" "}
                <button className="bxp-text-button" onClick={() => void projectsQuery.refetch()} type="button">
                  {t("Try again")}
                </button>
              </p>
            ) : (
              <p>{t("Loading the loans.")}</p>
            )}
          </div>
        )}
        <div className="bxp-stat-notes">
          <div>
            <h3>{t("How we count")}</h3>
            <p>
              {t(
                "A payment is late from day 15 after its due date. From day 60 Banxum can declare the loan in default (calendar days, Swiss time); a loan contract can set other days. Recovery continues after that and is shown on the project page."
              )}
            </p>
          </div>
          <div>
            <h3>{t("Past results")}</h3>
            <p>{t("Figures of past loans do not predict future results. Every loan can be repaid late or not at all.")}</p>
          </div>
        </div>
      </section>
    </div>
  );
}

function Figure({ value, label }: { value: number; label: string }) {
  return (
    <div className="bxp-figure">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function Amounts({ stats }: { stats: PublicStatistics }) {
  const t = useT();
  return (
    <section aria-labelledby="amounts-title" className="bxp-stat-section">
      <p className="page-kicker">{t("BY CURRENCY")}</p>
      <h2 className="section-title" id="amounts-title">
        {t("Amounts")}
      </h2>
      <div className="bxp-table-card">
        <table className="bxp-table">
          <thead>
            <tr>
              <th scope="col">{t("Currency")}</th>
              <th className="is-num" scope="col">
                {t("Loans")}
              </th>
              <th className="is-num" scope="col">
                {t("Lent")}
              </th>
              <th className="is-num" scope="col">
                {t("Principal repaid")}
              </th>
              <th className="is-num" scope="col">
                {t("Interest paid")}
              </th>
              <th className="is-num" scope="col">
                {t("Outstanding")}
              </th>
              <th className="is-num" scope="col">
                {t("In default")}
              </th>
            </tr>
          </thead>
          <tbody>
            {CURRENCIES.map((currency) => {
              const row = stats.by_currency.find((item) => item.currency === currency);
              return (
                <tr key={currency}>
                  <th scope="row">{currency}</th>
                  <td className="is-num">{row?.loans ?? 0}</td>
                  <td className="is-num">{numMinor(row?.lent_minor ?? 0)}</td>
                  <td className="is-num">{numMinor(row?.principal_repaid_minor ?? 0)}</td>
                  <td className="is-num">{numMinor(row?.interest_paid_minor ?? 0)}</td>
                  <td className="is-num">{numMinor(row?.outstanding_minor ?? 0)}</td>
                  <td className={row?.defaulted_minor ? "is-num is-default" : "is-num"}>{numMinor(row?.defaulted_minor ?? 0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="bxp-small">
        {t("Average interest rate, weighted by amount: {rate}.", {
          rate: stats.average_interest_rate_bps === null ? "–" : pctBps(stats.average_interest_rate_bps)
        })}{" "}
        {t("In default: principal outstanding when the loan went into default, before recovery.")}
      </p>
    </section>
  );
}

function FundedTable({ projects }: { projects: PublicProject[] }) {
  const t = useT();
  const today = siteToday();
  return (
    <div className="bxp-table-card">
      <table className="bxp-table">
        <thead>
          <tr>
            <th scope="col">{t("Project")}</th>
            <th className="bxp-hide-sm" scope="col">
              {t("Country")}
            </th>
            <th className="is-num" scope="col">
              {t("Rate")}
            </th>
            <th className="is-num bxp-hide-sm" scope="col">
              {t("Term")}
            </th>
            <th className="is-num" scope="col">
              {t("Amount")}
            </th>
            <th className="is-num bxp-hide-sm" scope="col">
              {t("Payments")}
            </th>
            <th scope="col">{t("Status")}</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => {
            const badge = statusBadge(projectView(p, today), t);
            const fundedOn = dateKey(p.funded_at);
            return (
              <tr key={p.loan_id}>
                <td>
                  <PublicLink href={`/projects/${encodeURIComponent(p.loan_id)}`}>{p.title}</PublicLink>
                  {fundedOn ? <span className="bxp-table-sub">{t("Funded {date}", { date: date(fundedOn) })}</span> : null}
                </td>
                <td className="bxp-hide-sm">{countryName(p.borrower_country)}</td>
                <td className="is-num">{pctBps(p.interest_rate_bps)}</td>
                <td className="is-num bxp-hide-sm">{t("{months} months", { months: p.term_months })}</td>
                <td className="is-num">{moneyMinor(p.principal_minor, p.currency)}</td>
                <td className="is-num bxp-hide-sm">{`${p.record?.installments_paid ?? 0} / ${p.record?.installments_total ?? 0}`}</td>
                <td>
                  <span className={`bxp-loan-status ${badge.cls}`.trim()}>{badge.label}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
