// IP of Webby-Soft SRL.
/*
 * Companies looking for a loan (design: pages_home.js projects(), filtersBar, projectsList and the
 * interest calculator: calculator, calcResult, seg).
 *
 * Data: usePublicProjects(). The filters (status chips with counts, currency) change the list
 * in place and are kept for the browser tab; "?status=&currency=" in the address sets them once
 * and leaves the address. The calculator's "See open projects in <CUR>" sets the filters and
 * scrolls to them.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { CurrencyFlag, Eyebrow, PageHead, ProjectCard, ProjectsBox, RiskLine, SiteLink, SubscribeBlock } from "../components";
import { useSiteNav } from "../context";
import { usePublicProjects } from "../data";
import { amountValue, cleanAmountInput, money, num, parseAmount, pct, SITE_MINIMUM, siteToday, type PlanRepayment } from "../format";
import { projectView } from "../projects";
import {
  calcAmount,
  CURRENCY_OPTIONS,
  filterProjects,
  filtersFromQuery,
  hasFilterQuery,
  PROJECT_FILTERS,
  readProjectFilters,
  saveProjectFilters,
  simulate,
  type FilterCurrency,
  type ProjectFilters
} from "./projectHelpers";

export function Projects() {
  const { path, search, navigate } = useSiteNav();
  const projectsQuery = usePublicProjects();
  const today = siteToday();
  const views = useMemo(() => (projectsQuery.data ?? []).map((p) => projectView(p, today)), [projectsQuery.data, today]);
  const [filters, setFilters] = useState<ProjectFilters>(() =>
    filtersFromQuery(new URLSearchParams(search), readProjectFilters())
  );
  const filtersRef = useRef<HTMLDivElement>(null);

  // A query in the address sets the filters once; clear it so it does not override the next choice.
  useEffect(() => {
    const query = new URLSearchParams(search);
    if (!hasFilterQuery(query)) return;
    setFilters((current) => filtersFromQuery(query, current));
    navigate(path, { replace: true });
  }, [path, search, navigate]);

  useEffect(() => saveProjectFilters(filters), [filters]);

  const showOpenIn = (currency: FilterCurrency) => {
    setFilters({ status: "open", currency });
    filtersRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const ready = projectsQuery.isSuccess;
  const list = filterProjects(views, filters);

  return (
    <>
      <PageHead
        eyebrow="Projects"
        lead="Open projects, the ones opening soon and every loan funded so far. Company names and documents are shown after you open an account."
        title="Companies looking for a loan"
      />
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap">
          <div id="site-project-filters" ref={filtersRef}>
            <div className="site-filters">
              <div aria-label="Status" className="site-chips" role="group">
                {PROJECT_FILTERS.map((filter) => (
                  <button
                    aria-pressed={filters.status === filter.id}
                    className={filters.status === filter.id ? "active" : ""}
                    data-status={filter.id}
                    key={filter.id}
                    onClick={() => setFilters((current) => ({ ...current, status: filter.id }))}
                    type="button"
                  >
                    {filter.label}
                    {ready ? <span className="site-chip-count">{views.filter(filter.test).length}</span> : null}
                  </button>
                ))}
              </div>
              <select
                aria-label="Currency"
                className="form-select site-select"
                onChange={(event) => setFilters((current) => ({ ...current, currency: event.target.value as FilterCurrency }))}
                value={filters.currency}
              >
                {CURRENCY_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div id="site-project-list">
            {!ready ? (
              <ProjectsBox>
                {projectsQuery.isError ? (
                  <>
                    The projects could not be loaded.{" "}
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
                  "Loading the projects."
                )}
              </ProjectsBox>
            ) : list.length ? (
              <div className="site-projects">
                {list.map((view) => (
                  <ProjectCard key={view.p.loan_id} view={view} />
                ))}
              </div>
            ) : (
              <ProjectsBox>
                No projects match.{" "}
                <a
                  href="#"
                  onClick={(event) => {
                    event.preventDefault();
                    setFilters({ status: "all", currency: "all" });
                  }}
                >
                  Show all projects
                </a>
              </ProjectsBox>
            )}
          </div>
          <div className="site-split is-center mt-5 pt-4">
            <div className="site-locked">
              <h3 className="site-h4">See the full project pages</h3>
              <p className="site-text mb-0">
                Company names, financial statements, loan agreements and security documents are shown to investors with a
                verified account.
              </p>
              <div className="site-actions mt-4">
                <SiteLink className="btn btn-lg btn-primary" href="/register">
                  Open account
                </SiteLink>
                <SiteLink className="btn btn-lg btn-site-outline" href="/login">
                  Log in
                </SiteLink>
              </div>
            </div>
            <div>
              <h3 className="site-h4">Get new projects by email</h3>
              <p className="site-text">Projects are often funded within days. We tell you when a new one opens.</p>
              <SubscribeBlock id="projects" source="projects" />
            </div>
          </div>
          <RiskLine />
        </div>
      </section>
      <section className="site-section is-paper">
        <div className="site-wrap">
          <div className="site-section-head">
            <div>
              <Eyebrow>Calculator</Eyebrow>
              <h2 className="site-h2">What a loan pays back</h2>
            </div>
            <p className="site-text mb-0">
              Choose an amount, a rate, a term and how the loan is repaid. Interest is counted every day, as in your account.
            </p>
          </div>
          <Calculator onShowProjects={showOpenIn} />
        </div>
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------------------------
// Interest calculator (design calculator, calcUpdate, calcResult).

type CalcCurrency = "EUR" | "CHF";

/** Radio buttons drawn as a segmented control (design seg). */
function Seg<T extends string>({
  name,
  options,
  value,
  onChange
}: {
  name: string;
  options: [T, ReactNode][];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="site-seg" role="radiogroup">
      {options.map(([optionValue, label]) => (
        <SegOption
          checked={optionValue === value}
          id={`calc-${name}-${optionValue}`}
          key={optionValue}
          label={label}
          name={name}
          onChange={() => onChange(optionValue)}
          value={optionValue}
        />
      ))}
    </div>
  );
}

function SegOption({
  id,
  name,
  value,
  checked,
  label,
  onChange
}: {
  id: string;
  name: string;
  value: string;
  checked: boolean;
  label: ReactNode;
  onChange: () => void;
}) {
  return (
    <>
      <input checked={checked} id={id} name={name} onChange={onChange} type="radio" value={value} />
      <label htmlFor={id}>{label}</label>
    </>
  );
}

function Calculator({ onShowProjects }: { onShowProjects: (currency: CalcCurrency) => void }) {
  const [amountText, setAmountText] = useState(() => num(5000));
  const [currency, setCurrency] = useState<CalcCurrency>("EUR");
  const [rate, setRate] = useState(7.5);
  const [term, setTerm] = useState(24);
  const [repayment, setRepayment] = useState<PlanRepayment>("annuity");
  const amount = calcAmount(amountText);

  return (
    <div className="site-calc" id="site-calc">
      <form className="site-calc-form" onSubmit={(event) => event.preventDefault()}>
        <div className="form-group">
          <label className="form-label" htmlFor="calc-amount">
            Amount
          </label>
          <div className="form-control-wrap">
            <div className="form-text-hint">
              <span className="overline-title">{currency}</span>
            </div>
            <input
              className="form-control form-control-lg bxm-amount"
              id="calc-amount"
              inputMode="decimal"
              name="amount"
              onBlur={(event) => {
                const value = parseAmount(event.target.value);
                if (!Number.isNaN(value)) setAmountText(amountValue(value));
              }}
              onChange={(event) => setAmountText(cleanAmountInput(event.target.value))}
              value={amountText}
            />
          </div>
        </div>
        <div className="form-group">
          <span className="form-label d-block">Currency</span>
          <Seg<CalcCurrency>
            name="currency"
            onChange={setCurrency}
            options={[
              [
                "EUR",
                <>
                  <CurrencyFlag currency="EUR" />
                  EUR
                </>
              ],
              [
                "CHF",
                <>
                  <CurrencyFlag currency="CHF" />
                  CHF
                </>
              ]
            ]}
            value={currency}
          />
        </div>
        <div className="form-group">
          <div className="site-range-head">
            <label className="form-label" htmlFor="calc-rate">
              Interest rate a year
            </label>
            <output>{pct(rate)}</output>
          </div>
          <input
            className="site-range"
            id="calc-rate"
            max="11"
            min="4"
            name="rate"
            onChange={(event) => setRate(Number(event.target.value))}
            step="0.1"
            type="range"
            value={rate}
          />
        </div>
        <div className="form-group">
          <div className="site-range-head">
            <label className="form-label" htmlFor="calc-term">
              Term
            </label>
            <output>{`${term} months`}</output>
          </div>
          <input
            className="site-range"
            id="calc-term"
            max="60"
            min="1"
            name="term"
            onChange={(event) => setTerm(Number(event.target.value))}
            step="1"
            type="range"
            value={term}
          />
        </div>
        <div className="form-group">
          <span className="form-label d-block">Repayment</span>
          <Seg<PlanRepayment>
            name="repayment"
            onChange={setRepayment}
            options={[
              ["annuity", "Monthly instalments"],
              ["interest-only", "Monthly interest"],
              ["bullet", "At the end"]
            ]}
            value={repayment}
          />
        </div>
      </form>
      <div className="site-calc-result">
        <div className="site-calc-result-body">
          {amount ? (
            <CalcResult amount={amount} currency={currency} rate={rate} repayment={repayment} term={term} />
          ) : (
            <p className="site-small">Enter an amount.</p>
          )}
        </div>
        <div className="site-actions mt-4">
          <SiteLink className="btn btn-lg btn-primary" href="/register">
            Open account
          </SiteLink>
          <a
            className="btn btn-lg btn-site-outline"
            data-calc-projects=""
            href="/projects"
            onClick={(event) => {
              event.preventDefault();
              onShowProjects(currency);
            }}
          >
            {`See open projects in ${currency}`}
          </a>
        </div>
      </div>
    </div>
  );
}

function CalcResult({
  amount,
  currency,
  rate,
  term,
  repayment
}: {
  amount: number;
  currency: CalcCurrency;
  rate: number;
  term: number;
  repayment: PlanRepayment;
}) {
  const sim = simulate(amount, rate, term, repayment);
  const max = Math.max(...sim.rows.map((row) => row.principal + row.interest)) || 1;
  const firstLabel = repayment === "bullet" ? "Paid at the end" : repayment === "annuity" ? "First month" : "Interest, first month";
  const firstValue = repayment === "bullet" ? sim.total : sim.first;
  return (
    <>
      <dl className="site-calc-figures">
        <div className="is-main">
          <dt>Interest before tax</dt>
          <dd>{money(sim.interest, currency)}</dd>
        </div>
        <div>
          <dt>{firstLabel}</dt>
          <dd>{money(firstValue, currency)}</dd>
        </div>
        <div>
          <dt>Total repaid</dt>
          <dd>{money(sim.total, currency)}</dd>
        </div>
      </dl>
      <div aria-hidden="true" className="site-calc-bars">
        {sim.rows.map((row, index) => (
          <span key={index}>
            <i style={{ height: `${((row.principal / max) * 136).toFixed(1)}px` }} />
            <i className="is-interest" style={{ height: `${((row.interest / max) * 136).toFixed(1)}px` }} />
          </span>
        ))}
      </div>
      <div className="site-calc-legend">
        <span>
          <i />
          Principal
        </span>
        <span>
          <i className="is-interest" />
          Interest
        </span>
        <span>{`Month 1 to ${term}`}</span>
      </div>
      <p className="site-small mt-3 mb-0">
        {
          "Interest counted every day (principal × rate ÷ 365), every payment on time, 0% fees. Borrowers can pay late or not at all, and interest is taxed as income. "
        }
        {amount < SITE_MINIMUM ? <strong>{`The minimum is ${money(SITE_MINIMUM, currency)}.`}</strong> : null}
      </p>
    </>
  );
}
