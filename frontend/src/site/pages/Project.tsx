// IP of Webby-Soft SRL.
/*
 * Public project page (design: pages_home.js projectPage(), investBox, recordBlock):
 * everything but the company's identity and documents.
 *
 * Data: usePublicProject(id) for the page, usePublicProjects() for "Other projects". The API
 * has no city, governing law or number of employees: the lead reads "Country · Sector", the
 * region is the country and Employees shows "–". An unknown or non-public id shows the 404.
 */
import { useMemo, useState } from "react";

import { Eyebrow, NiIcon, Progress, ProjectCard, ProjectsBox, RiskLine, SiteLink, Tag } from "../components";
import { useSiteTitle } from "../context";
import { isNotFound, usePublicProject, usePublicProjects, type PublicProject } from "../data";
import {
  amountValue,
  cleanAmountInput,
  date,
  dateKey,
  money,
  moneyMinor,
  moneyShortMinor,
  parseAmount,
  pct,
  pctBps,
  SITE_MINIMUM,
  siteToday
} from "../format";
import {
  countryName,
  openProjects,
  placeLine,
  projectView,
  recordTag,
  repaymentShort,
  statusOf,
  timeText,
  type ProjectView
} from "../projects";
import type { SitePageProps } from "../SitePages";
import { NotFound } from "./NotFound";
import { expectedInterest, ltvText, purposeItems, securityText } from "./projectHelpers";

/** Short reference of a loan for the crumbs: the first 8 characters of its id, upper case. */
function shortRef(loanId: string) {
  return loanId.slice(0, 8).toUpperCase();
}

export function Project({ params }: SitePageProps) {
  const id = params.id ?? "";
  const query = usePublicProject(id);
  const projectsQuery = usePublicProjects();
  const project = query.data;
  const today = siteToday();
  const views = useMemo(() => (projectsQuery.data ?? []).map((p) => projectView(p, today)), [projectsQuery.data, today]);
  useSiteTitle(project ? project.title : "Project");

  if (query.isError && isNotFound(query.error)) return <NotFound />;
  if (!project) {
    return (
      <>
        <section className="site-page-head" style={{ paddingBottom: 48 }}>
          <div className="site-wrap">
            <nav aria-label="Breadcrumb" className="site-crumbs">
              <SiteLink href="/projects">Projects</SiteLink>
              <span>/</span>
              <span>{shortRef(id)}</span>
            </nav>
            <h1 className="site-h1">Project</h1>
          </div>
        </section>
        <section className="site-section no-rule" style={{ paddingTop: 0 }}>
          <div className="site-wrap">
            <ProjectsBox>
              {query.isError ? (
                <>
                  The project could not be loaded.{" "}
                  <a
                    href="#"
                    onClick={(event) => {
                      event.preventDefault();
                      void query.refetch();
                    }}
                  >
                    Try again
                  </a>
                </>
              ) : (
                "Loading the project."
              )}
            </ProjectsBox>
          </div>
        </section>
      </>
    );
  }

  const view = projectView(project, today);
  const others = openProjects(views)
    .filter((other) => other.p.loan_id !== project.loan_id)
    .slice(0, 3);
  return <ProjectBody others={others} view={view} />;
}

function StatusTag({ view }: { view: ProjectView }) {
  const record = recordTag(view.p);
  const st = record ?? statusOf(view);
  return <Tag cls={st.cls} label={st.label} />;
}

function ProjectBody({ view, others }: { view: ProjectView; others: ProjectView[] }) {
  const p = view.p;
  return (
    <>
      <section className="site-page-head" style={{ paddingBottom: 48 }}>
        <div className="site-wrap">
          <nav aria-label="Breadcrumb" className="site-crumbs">
            <SiteLink href="/projects">Projects</SiteLink>
            <span>/</span>
            <span>{shortRef(p.loan_id)}</span>
          </nav>
          <div className="site-project-tags mb-3">
            <StatusTag view={view} /> <Tag label={p.product_type === "originator_claim" ? "Existing claim" : "New loan"} />{" "}
            <Tag cls="is-muted" label={`Risk ${p.risk_rating}`} />
          </div>
          <h1 className="site-h1">{p.title}</h1>
          <p className="site-lead">{placeLine(view)}</p>
        </div>
      </section>
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap site-project-page">
          <div>
            <dl className="site-facts-grid mb-5">
              <div>
                <dt>Interest a year</dt>
                <dd>{pctBps(p.interest_rate_bps)}</dd>
              </div>
              <div>
                <dt>Term</dt>
                <dd>{p.term_months} months</dd>
              </div>
              <div>
                <dt>Amount</dt>
                <dd>{moneyShortMinor(p.principal_minor, p.currency)}</dd>
              </div>
              <div>
                <dt>Repayment</dt>
                <dd style={{ fontSize: "1rem", lineHeight: "1.9rem" }}>{repaymentShort(p)}</dd>
              </div>
            </dl>
            <p className="site-lead">{p.investor_summary}</p>

            <h2 className="site-h3 mt-5">Use of the money</h2>
            <ul className="site-checks">
              {purposeItems(p).map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>

            <h2 className="site-h3 mt-5">Security</h2>
            <dl className="site-kv">
              <div>
                <dt>Security</dt>
                <dd>{securityText(p)}</dd>
              </div>
              <div>
                <dt>Loan to value</dt>
                <dd>{ltvText(p.ltv_bps)}</dd>
              </div>
              <div>
                <dt>Risk class</dt>
                <dd>
                  {p.risk_rating} <span className="site-small">(AAA lowest, D highest)</span>
                </dd>
              </div>
            </dl>

            <h2 className="site-h3 mt-5">The company</h2>
            <dl className="site-kv">
              <div>
                <dt>Sector</dt>
                <dd>{p.borrower_sector || "–"}</dd>
              </div>
              <div>
                <dt>Region</dt>
                <dd>{view.countryName || "–"}</dd>
              </div>
              <div>
                <dt>Founded</dt>
                <dd>{p.borrower_year_founded || "–"}</dd>
              </div>
              <div>
                <dt>Employees</dt>
                <dd>–</dd>
              </div>
              <div>
                <dt>Name, revenue, equity ratio</dt>
                <dd>
                  <span aria-hidden="true" className="site-blur">
                    Sample Company AG
                  </span>
                  <span className="visually-hidden">Shown after you open an account</span>
                </dd>
              </div>
            </dl>

            <h2 className="site-h3 mt-5">Who lends</h2>
            <p className="site-text">
              <WhoLends p={p} />
            </p>

            <RecordBlock p={p} />

            <div className="site-locked mt-5">
              <h2 className="site-h4">After you open an account</h2>
              <p className="site-text mb-0">Verified investors see the full project page:</p>
              <ul>
                <li>
                  <NiIcon name="ni-lock-alt" />
                  Company name and commercial register number
                </li>
                <li>
                  <NiIcon name="ni-lock-alt" />
                  Financial statements and credit report
                </li>
                <li>
                  <NiIcon name="ni-lock-alt" />
                  Loan agreement and security documents
                </li>
                <li>
                  <NiIcon name="ni-lock-alt" />
                  Draft assignment declaration
                </li>
              </ul>
              <SiteLink className="btn btn-lg btn-primary" href="/register">
                Open account
              </SiteLink>
            </div>
            <RiskLine />
          </div>
          <aside>
            <InvestBox view={view} />
          </aside>
        </div>
      </section>
      {others.length ? (
        <section className="site-section">
          <div className="site-wrap">
            <div className="site-section-head">
              <div>
                <Eyebrow>Also open</Eyebrow>
                <h2 className="site-h2">Other projects</h2>
              </div>
            </div>
            <div className="site-projects">
              {others.map((other) => (
                <ProjectCard key={other.p.loan_id} view={other} />
              ))}
            </div>
          </div>
        </section>
      ) : null}
    </>
  );
}

function WhoLends({ p }: { p: PublicProject }) {
  if (p.product_type !== "originator_claim") {
    return (
      <>
        Garanta Finanzgruppe AG lends to the company and assigns shares of the claim to investors when the loan is funded.
      </>
    );
  }
  if (!p.originator) {
    return <>The loan originator assigns the claim to Garanta Finanzgruppe AG, which assigns shares to investors.</>;
  }
  const country = countryName(p.originator.country);
  return (
    <>
      The loan originator <strong>{p.originator.name}</strong>
      {country ? `, ${country}` : ""}, assigns the claim to Garanta Finanzgruppe AG, which assigns shares to investors.
    </>
  );
}

/** Repayment so far of a funded loan (design recordBlock). */
function RecordBlock({ p }: { p: PublicProject }) {
  const record = p.record;
  const tag = recordTag(p);
  if (!record || !tag) return null;
  return (
    <>
      <h2 className="site-h3 mt-5">Repayment so far</h2>
      <dl className="site-kv">
        <div>
          <dt>Status</dt>
          <dd>
            <Tag cls={tag.cls} label={tag.label} />
          </dd>
        </div>
        <div>
          <dt>Payments made</dt>
          <dd>{`${record.installments_paid} of ${record.installments_total}`}</dd>
        </div>
        <div>
          <dt>Principal repaid</dt>
          <dd>{moneyMinor(record.principal_repaid_minor, p.currency)}</dd>
        </div>
        <div>
          <dt>Interest paid</dt>
          <dd>{moneyMinor(record.interest_paid_minor, p.currency)}</dd>
        </div>
      </dl>
      {p.public_status === "default" ? (
        <div className="alert alert-danger mt-4 mb-0">
          <strong>{record.defaulted_on ? `In default since ${date(dateKey(record.defaulted_on))}.` : "In default."}</strong>
          {record.public_note ? ` ${record.public_note}` : null}
        </div>
      ) : p.public_status === "late" ? (
        <div className="alert alert-warning mt-4 mb-0">
          One payment is <span className="bxm-status-late">{`late ${record.days_past_due} days`}</span>. Garanta has
          reminded the borrower; investors are informed of each step.
        </div>
      ) : null}
    </>
  );
}

/** The aside: funding or repayment status, key figures, the mini calculator and the actions. */
function InvestBox({ view }: { view: ProjectView }) {
  const { p, isOpen, isSoon } = view;
  const record = p.record;
  const minimum = isOpen
    ? moneyMinor(p.minimum_investment_minor ?? 0, p.currency)
    : p.minimum_investment_minor !== null
      ? moneyMinor(p.minimum_investment_minor, p.currency)
      : money(SITE_MINIMUM, p.currency);
  return (
    <div className="site-box is-ink-rule site-sticky">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <StatusTag view={view} />
        <span className="site-small">{timeText(view)}</span>
      </div>
      {isSoon ? (
        <p className="site-text">
          This project opens on <strong>{date(dateKey(p.published_at))}</strong>. Open an account now so you can invest
          from the first day.
        </p>
      ) : record ? null : (
        <>
          <Progress percent={view.percent} />
          <div className="site-project-progress mb-3">
            <span>{`${moneyMinor(p.committed_principal_minor, p.currency)} funded`}</span>
            <span>{pct(view.percent, 0)}</span>
          </div>
        </>
      )}
      <dl className="site-kv mb-4">
        <div>
          <dt>Amount</dt>
          <dd>{moneyMinor(p.principal_minor, p.currency)}</dd>
        </div>
        {record ? (
          <>
            <div>
              <dt>Investors</dt>
              <dd>{p.investors_count}</dd>
            </div>
            <div>
              <dt>Payments made</dt>
              <dd>{`${record.installments_paid} of ${record.installments_total}`}</dd>
            </div>
          </>
        ) : (
          <>
            {isSoon ? null : (
              <div>
                <dt>Still to fund</dt>
                <dd>{moneyMinor(p.remaining_capacity_minor, p.currency)}</dd>
              </div>
            )}
            <div>
              <dt>Investors</dt>
              <dd>{p.investors_count}</dd>
            </div>
            <div>
              <dt>{isOpen ? "Minimum now" : "Minimum"}</dt>
              <dd>{minimum}</dd>
            </div>
          </>
        )}
      </dl>
      {isOpen ? <MiniCalc p={p} /> : null}
      {isOpen || isSoon ? (
        <>
          <div className="d-grid gap-2">
            <SiteLink className="btn btn-lg btn-primary" href="/register">
              Open account to invest
            </SiteLink>
            <SiteLink className="btn btn-lg btn-site-outline" href={`/marketplace/${encodeURIComponent(p.loan_id)}`}>
              I have an account
            </SiteLink>
          </div>
          <p className="site-small mt-3 mb-0">
            You pay from the available balance of your wallet; add funds by bank transfer after you open it. 0% fees for
            investors.
          </p>
        </>
      ) : (
        <p className="site-small mb-0">
          This project is no longer open. <SiteLink href="/projects">See the open projects</SiteLink>.
        </p>
      )}
    </div>
  );
}

/** "Your amount": the interest of a new investment if every payment is on time (design investBox). */
function MiniCalc({ p }: { p: PublicProject }) {
  const minimumMinor = p.minimum_investment_minor ?? 0;
  const [text, setText] = useState(() => amountValue(minimumMinor / 100));
  const value = parseAmount(text);
  let out;
  if (Number.isNaN(value) || value <= 0) {
    out = "Enter an amount.";
  } else {
    const interest = expectedInterest(p, value);
    const low =
      value < minimumMinor / 100 ? (
        <>
          <br />
          <span className="bxm-signal-text">{`The minimum now is ${moneyMinor(minimumMinor, p.currency)}.`}</span>
        </>
      ) : value > p.remaining_capacity_minor / 100 ? (
        <>
          <br />
          <span className="bxm-signal-text">{`Only ${moneyMinor(p.remaining_capacity_minor, p.currency)} is left.`}</span>
        </>
      ) : null;
    out = (
      <>
        {`Interest before tax over ${p.term_months} months: `}
        <strong className="text-dark">{money(interest, p.currency)}</strong>
        {", counted every day, if every payment is on time. No fees."}
        {low}
      </>
    );
  }
  return (
    <div className="mb-4" id="site-mini-calc">
      <label className="form-label" htmlFor="mini-amount">
        Your amount
      </label>
      <div className="form-control-wrap">
        <div className="form-text-hint">
          <span className="overline-title">{p.currency}</span>
        </div>
        <input
          className="form-control form-control-lg bxm-amount"
          id="mini-amount"
          inputMode="decimal"
          onBlur={(event) => {
            const parsed = parseAmount(event.target.value);
            if (!Number.isNaN(parsed)) setText(amountValue(parsed));
          }}
          onChange={(event) => setText(cleanAmountInput(event.target.value))}
          value={text}
        />
      </div>
      <p className="site-small mt-2 mb-0">{out}</p>
    </div>
  );
}
