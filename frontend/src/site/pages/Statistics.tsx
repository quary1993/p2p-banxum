// IP of Webby-Soft SRL.
/*
 * Every loan, including the ones that went wrong (design: pages_more.js statistics()).
 *
 * Data: usePublicStatistics() for the figures and the amounts by currency, usePublicProjects()
 * for the track record (every funded loan: repaying, late, repaid, default; newest funding
 * close first). The design's prototype sentence "This prototype shows its sample data." is not
 * shown.
 */
import { useMemo } from "react";

import { Eyebrow, PageHead, ProjectsBox, SiteLink, Tag } from "../components";
import { usePublicProjects, usePublicStatistics, type PublicProject, type PublicStatistics } from "../data";
import { date, dateKey, moneyMinor, numMinor, pctBps } from "../format";
import { countryName, recordTag } from "../projects";

const CURRENCIES = ["CHF", "EUR"] as const;

export function Statistics() {
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
    <>
      <PageHead
        eyebrow="Statistics"
        lead="All loans funded on Banxum. Built from live data, so it is always current."
        title="Every loan, including the ones that went wrong"
      />
      {stats ? (
        <>
          <section className="site-section is-tight">
            <div className="site-wrap">
              <div className="site-figures">
                <div>
                  <strong>{stats.loans_funded}</strong>
                  <span>loans funded</span>
                </div>
                <div>
                  <strong>{stats.loans_repaid}</strong>
                  <span>repaid in full</span>
                </div>
                <div>
                  <strong>{stats.loans_late}</strong>
                  <span>with a late payment now</span>
                </div>
                <div>
                  <strong>{stats.loans_defaulted}</strong>
                  <span>in default</span>
                </div>
              </div>
            </div>
          </section>
          <AmountsSection stats={stats} />
        </>
      ) : (
        <section className="site-section is-tight">
          <div className="site-wrap">
            <ProjectsBox>
              {statsQuery.isError ? (
                <>
                  The statistics could not be loaded.{" "}
                  <a
                    href="#"
                    onClick={(event) => {
                      event.preventDefault();
                      void statsQuery.refetch();
                    }}
                  >
                    Try again
                  </a>
                </>
              ) : (
                "Loading the statistics."
              )}
            </ProjectsBox>
          </div>
        </section>
      )}
      <section className="site-section">
        <div className="site-wrap">
          <div className="site-section-head is-single">
            <div>
              <Eyebrow>Track record</Eyebrow>
              <h2 className="site-h2">All funded loans</h2>
            </div>
          </div>
          {projectsQuery.isSuccess ? (
            <FundedTable projects={funded} />
          ) : (
            <ProjectsBox>
              {projectsQuery.isError ? (
                <>
                  The loans could not be loaded.{" "}
                  <a
                    href="#"
                    onClick={(event) => {
                      event.preventDefault();
                      void projectsQuery.refetch();
                    }}
                  >
                    Try again
                  </a>
                </>
              ) : (
                "Loading the loans."
              )}
            </ProjectsBox>
          )}
          <div className="site-split mt-5">
            <div>
              <h3 className="site-h4">How we count</h3>
              <p className="site-text">
                A payment is late from day 5 after its due date. A loan is in default from day 16 (calendar days, Swiss
                time); recovery continues after that and is shown on the project page.
              </p>
            </div>
            <div>
              <h3 className="site-h4">Past results</h3>
              <p className="site-text">
                Figures of past loans do not predict future results. Every loan can be repaid late or not at all.
              </p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function AmountsSection({ stats }: { stats: PublicStatistics }) {
  return (
    <section className="site-section">
      <div className="site-wrap">
        <div className="site-section-head is-single">
          <div>
            <Eyebrow>By currency</Eyebrow>
            <h2 className="site-h2">Amounts</h2>
          </div>
        </div>
        <div className="site-table-scroll">
          <table className="site-table">
            <thead>
              <tr>
                <th>Currency</th>
                <th className="is-num">Loans</th>
                <th className="is-num">Lent</th>
                <th className="is-num">Principal repaid</th>
                <th className="is-num">Interest paid</th>
                <th className="is-num">Outstanding</th>
                <th className="is-num">In default</th>
              </tr>
            </thead>
            <tbody>
              {CURRENCIES.map((currency) => {
                const row = stats.by_currency.find((item) => item.currency === currency);
                return (
                  <tr key={currency}>
                    <td>
                      <strong>{currency}</strong>
                    </td>
                    <td className="is-num">{row?.loans ?? 0}</td>
                    <td className="is-num">{numMinor(row?.lent_minor ?? 0)}</td>
                    <td className="is-num">{numMinor(row?.principal_repaid_minor ?? 0)}</td>
                    <td className="is-num">{numMinor(row?.interest_paid_minor ?? 0)}</td>
                    <td className="is-num">{numMinor(row?.outstanding_minor ?? 0)}</td>
                    <td className="is-num">
                      {row?.defaulted_minor ? (
                        <span className="bxm-signal-text">{numMinor(row.defaulted_minor)}</span>
                      ) : (
                        numMinor(0)
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="site-small mt-3">
          {`Average interest rate, weighted by amount: ${
            stats.average_interest_rate_bps === null ? "–" : pctBps(stats.average_interest_rate_bps)
          }. In default: principal outstanding when the loan went into default, before recovery.`}
        </p>
      </div>
    </section>
  );
}

function FundedTable({ projects }: { projects: PublicProject[] }) {
  return (
    <div className="site-table-scroll">
      <table className="site-table">
        <thead>
          <tr>
            <th>Project</th>
            <th className="site-hide-sm">Country</th>
            <th className="is-num">Rate</th>
            <th className="is-num site-hide-sm">Term</th>
            <th className="is-num">Amount</th>
            <th className="is-num site-hide-sm">Payments</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => {
            const tag = recordTag(p);
            const funded = dateKey(p.funded_at);
            return (
              <tr key={p.loan_id}>
                <td>
                  <SiteLink href={`/projects/${encodeURIComponent(p.loan_id)}`}>{p.title}</SiteLink>
                  <span className="site-table-sub">
                    {funded ? `Funded ${date(funded)} · risk ${p.risk_rating}` : `Risk ${p.risk_rating}`}
                  </span>
                </td>
                <td className="site-hide-sm">{countryName(p.borrower_country)}</td>
                <td className="is-num">{pctBps(p.interest_rate_bps)}</td>
                <td className="is-num site-hide-sm">{`${p.term_months} mo`}</td>
                <td className="is-num">{moneyMinor(p.principal_minor, p.currency)}</td>
                <td className="is-num site-hide-sm">{`${p.record?.installments_paid ?? 0} / ${p.record?.installments_total ?? 0}`}</td>
                <td>{tag ? <Tag cls={tag.cls} label={tag.label} /> : null}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
