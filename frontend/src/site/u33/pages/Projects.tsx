// IP of Webby-Soft SRL.
/*
 * All projects in the U33 public design (U33-DEC-39, Q24, D-10). The design has no list page: its
 * "Opportunities" is the home page section (opportunities.html only leads there). This page is
 * that section for every project: the design's heading, loan cards and calculator, plus what Q24
 * keeps from the October page, built with the U33 components (Q23): a status filter (open,
 * coming soon, funded, all) with counts, a currency filter, funded loans with the project page's
 * status badge, the sign-in invitation and the newsletter sign-up.
 *
 * Filters: kept for the browser tab; "?status=&currency=" in the address sets them once and
 * leaves the address (as before). The calculator uses the open projects, closing soonest first,
 * three at most, as on the home page.
 */
import { useEffect, useMemo, useState } from "react";

import { useT } from "../../../i18n";
import { useSiteNav, useSiteTitle } from "../../context";
import { usePublicProjects } from "../../data";
import { siteToday } from "../../format";
import {
  CURRENCY_OPTIONS,
  filterProjects,
  filtersFromQuery,
  hasFilterQuery,
  PROJECT_FILTERS,
  readProjectFilters,
  saveProjectFilters,
  type FilterCurrency,
  type ProjectFilters
} from "../../pages/projectHelpers";
import { projectView } from "../../projects";
import { homeOpportunities } from "../loans";
import { Subscribe } from "../Subscribe";
import { Ni, PublicLink } from "../ui";
import { Calculator, LoanCard } from "./Home";

const CURRENCY_LABELS: Record<FilterCurrency, string> = { all: "All currencies", CHF: "CHF · Switzerland", EUR: "EUR · EU" };

export function Projects() {
  const t = useT();
  useSiteTitle(t("All projects"));
  const { path, search, navigate } = useSiteNav();
  const projectsQuery = usePublicProjects();
  const today = siteToday();
  const views = useMemo(() => (projectsQuery.data ?? []).map((p) => projectView(p, today)), [projectsQuery.data, today]);
  const [filters, setFilters] = useState<ProjectFilters>(() => filtersFromQuery(new URLSearchParams(search), readProjectFilters()));

  // A query in the address sets the filters once; clear it so it does not override the next choice.
  useEffect(() => {
    const query = new URLSearchParams(search);
    if (!hasFilterQuery(query)) return;
    setFilters((current) => filtersFromQuery(query, current));
    navigate(path, { replace: true });
  }, [path, search, navigate]);

  useEffect(() => saveProjectFilters(filters), [filters]);

  const ready = projectsQuery.isSuccess;
  const list = filterProjects(views, filters);
  const calculatorViews = homeOpportunities(views).filter((view) => view.isOpen);

  return (
    <>
      <section aria-labelledby="projects-title" className="public-opportunities bxp-all-projects" id="projects">
        <div className="opportunities-heading">
          <div>
            <h1 className="bxp-projects-title" id="projects-title">
              {t("All projects")}
            </h1>
            <p>{t("Open projects, the ones opening soon and every loan funded so far. Company names and documents are shown after you open an account.")}</p>
          </div>
        </div>
        <div className="bxp-filters">
          <div aria-label={t("Status")} className="bxp-segment" role="group">
            {PROJECT_FILTERS.map((filter) => (
              <button
                aria-pressed={filters.status === filter.id}
                className={filters.status === filter.id ? "is-active" : undefined}
                data-status={filter.id}
                key={filter.id}
                onClick={() => setFilters((current) => ({ ...current, status: filter.id }))}
                type="button"
              >
                {t(filter.label)}
                {ready ? <span className="bxp-segment-count">{views.filter(filter.test).length}</span> : null}
              </button>
            ))}
          </div>
          <label className="bxp-select">
            <span className="sr-only">{t("Currency")}</span>
            <select
              aria-label={t("Currency")}
              onChange={(event) => setFilters((current) => ({ ...current, currency: event.target.value as FilterCurrency }))}
              value={filters.currency}
            >
              {CURRENCY_OPTIONS.map(([value]) => (
                <option key={value} value={value}>
                  {t(CURRENCY_LABELS[value])}
                </option>
              ))}
            </select>
          </label>
        </div>
        {!ready ? (
          <div className="bxp-empty" role="status">
            {projectsQuery.isError ? (
              <p>
                {t("The projects could not be loaded.")}{" "}
                <button className="bxp-text-button" onClick={() => void projectsQuery.refetch()} type="button">
                  {t("Try again")}
                </button>
              </p>
            ) : (
              <p>{t("Loading the projects.")}</p>
            )}
          </div>
        ) : list.length ? (
          <div className="opportunity-grid bxp-projects-grid">
            {list.map((view) => (
              <LoanCard key={view.p.loan_id} view={view} />
            ))}
          </div>
        ) : (
          <div className="bxp-empty" role="status">
            <p>
              {t("No project matches these filters.")}{" "}
              <button className="bxp-text-button" onClick={() => setFilters({ status: "all", currency: "all" })} type="button">
                {t("Show all projects")}
              </button>
            </p>
          </div>
        )}
        {calculatorViews.length ? <Calculator views={calculatorViews} /> : null}
        <div className="opportunities-note">
          <p>{t("Projections are before tax and assume repayment as agreed.")}</p>
        </div>
      </section>
      <section aria-label={t("Next steps")} className="bxp-projects-more">
        <div className="bxp-panel">
          <h2>{t("See the full project pages")}</h2>
          <p>{t("Company names, financial statements, loan agreements and security documents are shown to investors with a verified account.")}</p>
          <div className="bxp-actions">
            <PublicLink className="button-primary" href="/register">
              {t("Open account")}
            </PublicLink>
            <PublicLink className="text-link" href="/login">
              {t("Log in")} <Ni glyph="arrow" />
            </PublicLink>
          </div>
        </div>
        <div className="bxp-panel" id="newsletter">
          <h2>{t("Get new projects by email")}</h2>
          <p>{t("Projects are often funded within days. We tell you when a new one opens.")}</p>
          <Subscribe id="projects" source="projects" />
        </div>
      </section>
    </>
  );
}
