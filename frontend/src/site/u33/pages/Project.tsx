// IP of Webby-Soft SRL.
/*
 * U33 public project page (design residential.html / manufacturing.html / winery.html, one page
 * type): heading, key numbers, loan repayments for all investors, the security with loan and
 * asset value on one scale, the account gate.
 *
 * Live data (usePublicProject): anonymous, never the company's name (decided 2026-10-15); no
 * risk rating (U33-DEC-16). Funded, repaying, late, repaid and defaulted loans use the same page:
 * the badge shows the status and the repayments panel shows the record so far (payments made,
 * principal repaid, interest paid, days late or default, the admin's public note) instead of the
 * projection. The pager browses the home page's opportunities. Unknown ids show a U33 notice.
 */
import { useMemo, type ReactNode } from "react";

import { useT } from "../../../i18n";
import { useSiteTitle } from "../../context";
import { isNotFound, usePublicProject, usePublicProjects, type PublicProject } from "../../data";
import { date, dateKey, dateShort, num, siteToday } from "../../format";
import { projectView, type ProjectView } from "../../projects";
import type { SitePageProps } from "../../SitePages";
import { useNarrow } from "../hooks";
import {
  assetName,
  estimate,
  frequencyText,
  homeOpportunities,
  ltvText,
  rateText,
  securityFigure,
  securityTitle,
  splitCents,
  wholeAmount,
  type SecurityFigure
} from "../loans";
import { Flag, HomeSectionLink, MobileLtv, Ni, PublicLink } from "../ui";

const BAR_WIDTH = 482;

export function Project({ params }: SitePageProps) {
  const t = useT();
  const id = params.id ?? "";
  const query = usePublicProject(id);
  const projects = usePublicProjects();
  const today = siteToday();
  const project = query.data;
  useSiteTitle(project ? project.title : t("Project"));
  const list = useMemo(
    () => homeOpportunities((projects.data ?? []).map((p) => projectView(p, today))),
    [projects.data, today]
  );

  if (!project) {
    const missing = query.isError && isNotFound(query.error);
    return (
      <div className="content-shell">
        <div className="opportunity-navigation">
          <Breadcrumb open />
        </div>
        <section aria-labelledby="opportunity-title" className="compact-heading bxp-project-notice">
          <h1 id="opportunity-title">{missing ? t("This project is not available.") : t("Project")}</h1>
          <p className="page-lead">
            {missing ? (
              t("The address may be wrong, or the project is no longer public.")
            ) : query.isError ? (
              <>
                {t("The project could not be loaded.")}{" "}
                <button className="bxp-text-button" onClick={() => void query.refetch()} type="button">
                  {t("Try again")}
                </button>
              </>
            ) : (
              t("Loading the project.")
            )}
          </p>
          {missing ? (
            <PublicLink className="text-link" href="/projects">
              {t("See all projects")} <Ni glyph="arrow" />
            </PublicLink>
          ) : null}
        </section>
      </div>
    );
  }

  const view = projectView(project, today);
  const index = list.findIndex((item) => item.p.loan_id === project.loan_id);
  return <ProjectBody index={index} list={list} view={view} />;
}

function Breadcrumb({ open }: { open: boolean }) {
  const t = useT();
  return open ? (
    <HomeSectionLink className="breadcrumb" section="opportunities">
      <Ni glyph="arrow" /> {t("All opportunities")}
    </HomeSectionLink>
  ) : (
    <PublicLink className="breadcrumb" href="/projects">
      <Ni glyph="arrow" /> {t("All projects")}
    </PublicLink>
  );
}

/** The badge of the heading: open with the days left, coming soon, or the loan's status. */
function statusBadge(view: ProjectView, t: (text: string, vars?: Record<string, string | number>) => string) {
  const p = view.p;
  if (view.isSoon) return { label: t("Opens {date}", { date: dateShort(dateKey(p.published_at)) }), cls: "" };
  if (view.isOpen) {
    if (view.daysLeft === null) return { label: t("Open"), cls: "is-open" };
    return {
      label: view.daysLeft <= 0 ? t("Open · closes today") : t("Open · {days} days left", { days: view.daysLeft }),
      cls: "is-open"
    };
  }
  switch (p.public_status) {
    case "repaying":
      return { label: t("Repaying"), cls: "" };
    case "late":
      return { label: t("Late {days} days", { days: p.record?.days_past_due ?? 0 }), cls: "is-late" };
    case "repaid":
      return { label: t("Repaid"), cls: "" };
    case "default":
      return { label: t("Default"), cls: "is-default" };
    default:
      return { label: t("Fully funded"), cls: "" };
  }
}

function ProjectBody({ view, list, index }: { view: ProjectView; list: ProjectView[]; index: number }) {
  const t = useT();
  const p = view.p;
  const badge = statusBadge(view, t);
  const open = view.isOpen || view.isSoon;
  const minimum = p.minimum_investment_minor;
  return (
    <div className="content-shell">
      <div className="opportunity-navigation">
        <Breadcrumb open={open} />
        {index >= 0 && list.length > 1 ? <Pager index={index} list={list} /> : null}
      </div>
      <section aria-labelledby="opportunity-title" className="compact-heading">
        <div className="page-meta">
          <Flag code={p.borrower_country} />
          <span>{p.borrower_sector || view.countryName}</span>
          <span className="loan-currency">{p.currency}</span>
          <span className={`preview-badge bxp-status ${badge.cls}`}>{badge.label}</span>
        </div>
        <h1 id="opportunity-title">{p.title}</h1>
        {p.investor_summary ? <p className="page-lead">{p.investor_summary}</p> : null}
      </section>
      <dl className="compact-numbers">
        <div>
          <dd className="compact-rate">
            {rateText(p.interest_rate_bps)}
            <small>%</small>
          </dd>
          <dt>{t("Annual interest")}</dt>
        </div>
        <div>
          <dd>
            {p.term_months} <small>{t("months")}</small>
          </dd>
          <dt>{t("Investment term")}</dt>
        </div>
        {open && minimum !== null ? (
          <div>
            <dd>
              <small>{p.currency}</small> {wholeAmount(minimum)}
            </dd>
            <dt>{t("Minimum investment")}</dt>
          </div>
        ) : (
          <div>
            <dd>
              <small>{p.currency}</small> {wholeAmount(p.principal_minor)}
            </dd>
            <dt>{t("Loan amount")}</dt>
          </div>
        )}
      </dl>
      <div className="compact-panels">
        {p.record ? <RecordPanel p={p} /> : <RepaymentsPanel p={p} />}
        <SecurityPanel p={p} />
      </div>
      <section aria-labelledby="gate-title" className="compact-gate">
        <div className="gate-intro">
          <span aria-hidden="true" className="gate-lock">
            <Ni glyph="lock" />
          </span>
          <div>
            {open ? (
              <>
                <h2 id="gate-title">{t("The full picture. Before you invest.")}</h2>
                <p>{t("Create an account and verify your identity to access the company, financial analysis and full loan documents.")}</p>
              </>
            ) : (
              <>
                <h2 id="gate-title">{t("This loan is no longer open for investment.")}</h2>
                <p>{t("Investors follow its repayments in their account. Current opportunities are on the home page.")}</p>
              </>
            )}
          </div>
        </div>
        <div className="compact-gate-actions">
          {open ? (
            <>
              <PublicLink className="button-primary" href="/register">
                {t("Create an account")} <Ni glyph="arrow" />
              </PublicLink>
            </>
          ) : (
            <HomeSectionLink className="button-primary" section="opportunities">
              {t("View opportunities")} <Ni glyph="arrow" />
            </HomeSectionLink>
          )}
        </div>
      </section>
      <p className="compact-risk">{t("Capital at risk. Collateral does not guarantee repayment.")}</p>
    </div>
  );
}

function Pager({ list, index }: { list: ProjectView[]; index: number }) {
  const t = useT();
  const count = list.length;
  const previous = index > 0 ? list[index - 1].p : null;
  const next = index < count - 1 ? list[index + 1].p : null;
  return (
    <nav aria-label={t("Browse opportunities")} className="opportunity-pager">
      {previous ? (
        <PublicLink
          aria-label={t("Previous opportunity: {title}", { title: previous.title })}
          className="opportunity-step previous"
          href={`/projects/${encodeURIComponent(previous.loan_id)}`}
          rel="prev"
          title={previous.title}
        >
          <Ni glyph="arrow" />
        </PublicLink>
      ) : (
        <button aria-label={t("Previous opportunity")} className="opportunity-step previous" disabled type="button">
          <Ni glyph="arrow" />
        </button>
      )}
      <span aria-label={t("Opportunity {index} of {count}", { index: index + 1, count })} className="opportunity-position">
        {index + 1} <span aria-hidden="true">/</span> {count}
      </span>
      {next ? (
        <PublicLink
          aria-label={t("Next opportunity: {title}", { title: next.title })}
          className="opportunity-step next"
          href={`/projects/${encodeURIComponent(next.loan_id)}`}
          rel="next"
          title={next.title}
        >
          <Ni glyph="arrow" />
        </PublicLink>
      ) : (
        <button aria-label={t("Next opportunity")} className="opportunity-step next" disabled type="button">
          <Ni glyph="arrow" />
        </button>
      )}
    </nav>
  );
}

/** An amount with small cents (design repay-amount): "CHF 90,082.19". */
function RepayAmount({ currency, amount, cents = true }: { currency: string; amount: number; cents?: boolean }) {
  const [whole, fraction] = splitCents(amount);
  return (
    <strong className="repay-amount">
      <span className="repay-currency">{currency}</span>{" "}
      <span className="repay-digits">
        {cents ? whole : num(Math.round(amount), 0)}
        {cents ? <span className="repay-cents">{fraction}</span> : null}
      </span>
    </strong>
  );
}

/** Before repayments start: the projection for all investors, paid to their Banxum accounts (U33-DEC-02). */
function RepaymentsPanel({ p }: { p: PublicProject }) {
  const t = useT();
  const principal = p.principal_minor / 100;
  const result = estimate(p, principal);
  const [whole, fraction] = splitCents(result.total);
  const months = p.term_months;
  return (
    <section aria-labelledby="income-title" className="income-panel loan-repayments repay-b">
      <div className="receipt-heading">
        <div>
          <h2 id="income-title">{t("Loan repayments")}</h2>
          <p className="repay-scope">{t("For all investors")}</p>
        </div>
      </div>
      <div className="repay-route">
        <div className="repay-values">
          <div className="repay-metric">
            <span className="repay-label">{t("Loan amount")}</span>
            <RepayAmount amount={principal} cents={false} currency={p.currency} />
          </div>
          <div className="repay-metric repay-interest">
            <span className="repay-label">{t("Projected total interest")}</span>
            <RepayAmount amount={result.interestTotal} currency={p.currency} />
          </div>
        </div>
        <RepayJoin />
        <div className="incoming-account">
          <strong className="repay-account-title">{t("Banxum investor accounts")}</strong>
          <strong className="repay-account-total">
            <span className="repay-currency">{p.currency}</span>{" "}
            <span className="repay-digits">
              {whole}
              <span className="repay-cents">{fraction}</span>
            </span>
          </strong>
          <span className="repay-projection">
            {result.repayment === "bullet"
              ? t("Projected · after {months} months", { months })
              : t("Projected · over {months} months", { months })}
          </span>
          <p className="repay-account-frequency">{frequencyText(p)}</p>
        </div>
      </div>
    </section>
  );
}

function RepayJoin() {
  return (
    <div aria-hidden="true" className="repay-join">
      <i />
      <Ni glyph="arrow" />
    </div>
  );
}

/** After funding: what the borrower has paid so far, to the investors' Banxum accounts. */
function RecordPanel({ p }: { p: PublicProject }) {
  const t = useT();
  const record = p.record;
  if (!record) return null;
  const principal = record.principal_repaid_minor / 100;
  const interest = record.interest_paid_minor / 100;
  const [whole, fraction] = splitCents(principal + interest);
  let note: ReactNode = null;
  if (p.public_status === "default") {
    note = (
      <p className="bxp-record-note is-default">
        {record.defaulted_on ? t("In default since {date}.", { date: date(dateKey(record.defaulted_on)) }) : t("In default.")}
        {record.public_note ? ` ${record.public_note}` : null}
      </p>
    );
  } else if (p.public_status === "late") {
    note = (
      <p className="bxp-record-note is-late">
        {t("A payment is {days} days late. Banxum follows up with the borrower and informs the investors.", { days: record.days_past_due })}
        {record.public_note ? ` ${record.public_note}` : null}
      </p>
    );
  } else if (record.public_note) {
    note = <p className="bxp-record-note">{record.public_note}</p>;
  }
  return (
    <section aria-labelledby="income-title" className="income-panel loan-repayments repay-b bxp-record">
      <div className="receipt-heading">
        <div>
          <h2 id="income-title">{t("Repayment record")}</h2>
          <p className="repay-scope">{t("For all investors")}</p>
        </div>
      </div>
      <div className="repay-route">
        <div className="repay-values">
          <div className="repay-metric">
            <span className="repay-label">{t("Principal repaid")}</span>
            <RepayAmount amount={principal} currency={p.currency} />
          </div>
          <div className="repay-metric repay-interest">
            <span className="repay-label">{t("Interest paid")}</span>
            <RepayAmount amount={interest} currency={p.currency} />
          </div>
        </div>
        <RepayJoin />
        <div className="incoming-account">
          <strong className="repay-account-title">{t("Paid to Banxum investor accounts")}</strong>
          <strong className="repay-account-total">
            <span className="repay-currency">{p.currency}</span>{" "}
            <span className="repay-digits">
              {whole}
              <span className="repay-cents">{fraction}</span>
            </span>
          </strong>
          <span className="repay-projection">
            {t("{paid} of {total} payments made", { paid: record.installments_paid, total: record.installments_total })}
          </span>
          <p className="repay-account-frequency">
            {t("Outstanding principal: {amount}", { amount: `${p.currency} ${num(record.outstanding_principal_minor / 100)}` })}
          </p>
        </div>
      </div>
      {note}
    </section>
  );
}

function SecurityPanel({ p }: { p: PublicProject }) {
  const t = useT();
  const figure = securityFigure(p);
  return (
    <section aria-labelledby="collateral-title" className="compact-security collateral-card">
      <div className="compact-security-head">
        <div>
          <h2 id="collateral-title">{assetName(p.collateral_type)}</h2>
          <p className="security-position">{securityTitle(p)}</p>
        </div>
      </div>
      {figure ? (
        <SecurityFigureView figure={figure} p={p} />
      ) : (
        <p className="figure-note bxp-security-terms">{t("The terms of this security are in the credit file, available to verified investors.")}</p>
      )}
    </section>
  );
}

function SecurityFigureView({ p, figure }: { p: PublicProject; figure: SecurityFigure }) {
  const t = useT();
  const narrow = useNarrow();
  const loan = wholeAmount(figure.loanMinor);
  const value = wholeAmount(figure.valueMinor);
  const ltv = ltvText(figure.ltv);
  const x = ((BAR_WIDTH * figure.ltv) / 100).toFixed(2);
  return (
    <figure
      aria-label={t("Loan amount {currency} {loan}; {label} {currency} {value}. Loan-to-value {ltv}.", {
        currency: p.currency,
        loan,
        label: figure.valueLabel.toLowerCase(),
        value,
        ltv
      })}
      className="compact-collateral-figure"
    >
      <svg aria-hidden="true" className="security-ltv detail-ltv" viewBox="0 0 482 172">
        <defs>
          <linearGradient id="detail-graphite" x1="0" x2="1" y1="0" y2=".6">
            <stop stopColor="#3e4a54" />
            <stop offset="1" stopColor="#202b35" />
          </linearGradient>
        </defs>
        <text className="ltv-label" x="0" y="13">
          {t("Loan amount")}
        </text>
        <text className="ltv-amount" x="0" y="43">
          <tspan className="ltv-currency">{`${p.currency} `}</tspan>
          <tspan>{loan}</tspan>
        </text>
        <rect className="security-ltv-bar loan-bar" height="14" rx="5" style={{ ["--bar-width" as string]: `${figure.ltv}%` }} width={x} x="0" y="59" />
        <g className="security-ltv-marker" transform={`translate(${x},0)`}>
          <path d="M0 73V112" stroke="#b3bdc5" strokeDasharray="2 4" strokeWidth="1" />
          <text className="ltv-ratio" x="12" y="69">
            {ltv}
          </text>
          <text className="ltv-ratio-label" x="12" y="87">
            {t("Loan-to-value")}
          </text>
        </g>
        <rect className="security-ltv-bar property-bar" fill="url(#detail-graphite)" height="14" rx="5" width="482" x="0" y="112" />
        <text className="ltv-full-value" textAnchor="end" x="470" y="123">
          100%
        </text>
        <text className="ltv-label" x="0" y="161">
          {figure.valueLabel}
        </text>
        <text className="ltv-amount" textAnchor="end" x="482" y="165">
          <tspan className="ltv-currency">{`${p.currency} `}</tspan>
          <tspan>{value}</tspan>
        </text>
      </svg>
      {narrow ? <MobileLtv currency={p.currency} figure={figure} id="project-mobile-ltv" loan={loan} value={value} /> : null}
      <figcaption className="figure-note">
        {p.collateral_type === "real_estate"
          ? t("Value implied by the published loan-to-value. Each property value comes from a named valuation report in the credit file.")
          : t("Value implied by the published loan-to-value.")}
      </figcaption>
    </figure>
  );
}
