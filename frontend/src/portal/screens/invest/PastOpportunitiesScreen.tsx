// IP of Webby-Soft SRL.
/*
 * Past opportunities (design #/projects/archive, slice S2): loans whose funding has closed, from the
 * public projects API (funded, repaying, late, repaid, default), with search and EUR/CHF. Each row opens
 * the opportunity page in its closed state; there is no investment action here.
 */
import { useState } from "react";

import type { PublicProject } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { usePastProjectsData } from "../../../investorPortal/data";
import { formatDate, formatMoneyLabel, formatPercent, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { Button, EmptyState, NiIcon, PortalLink, StatusTag, type TagStatus } from "../../components";
import { collateralIcon, countryName } from "./loanFacts";
import "./invest.css";

const statusOf: Record<string, TagStatus | undefined> = {
  fully_funded: "funded",
  repaying: "repaying",
  late: "late",
  repaid: "repaid",
  default: "default"
};

function projectTile(project: PublicProject) {
  if (project.product_type === "originator_claim") return "file-text";
  const icon = collateralIcon(project.collateral_type);
  return icon === "user" || icon === "alert-circle" ? "briefcase" : icon;
}

export function PastOpportunitiesScreen() {
  const t = useT();
  useNumberFormat();
  const query = usePastProjectsData();
  const [q, setQ] = useState("");
  const [currency, setCurrency] = useState("");
  const past = (query.data ?? []).filter((project) => project.public_status !== "open" && statusOf[project.public_status]);
  const needle = q.trim().toLowerCase();
  const visible = past.filter(
    (project) =>
      (!currency || project.currency === currency) &&
      (!needle || `${project.title} ${project.originator?.name ?? ""} ${project.loan_id}`.toLowerCase().includes(needle))
  );

  return (
    <main className="u33-invest-archive">
      <div className="nk-block-head nk-block-head-sm">
        <div className="nk-block-head-sub">
          <PortalLink className="back-to" to="market"><NiIcon name="arrow-left" /><span>{t("Investment opportunities")}</span></PortalLink>
        </div>
        <div className="nk-block-between g-3">
          <div className="nk-block-head-content">
            <h1 className="nk-block-title page-title">{t("Past opportunities")}</h1>
            <div className="nk-block-des text-soft"><p>{t("Funding has closed for these projects. See their current repayment status below.")}</p></div>
          </div>
        </div>
      </div>

      <div className="nk-block bxm-op-controls">
        <div className="bxm-op-toolbar">
          <form className="bxm-op-search" onSubmit={(event) => event.preventDefault()} role="search">
            <NiIcon name="search" />
            <input aria-label={t("Search past opportunities")} id="op-archive-search" name="q" onChange={(event) => setQ(event.target.value)} placeholder={t("Search past opportunities")} type="search" value={q} />
          </form>
          <div aria-label={t("Archive currency")} className="bxm-op-currency" role="group">
            {[["", t("All")], ["EUR", "EUR"], ["CHF", "CHF"]].map(([value, label]) => (
              <button aria-pressed={currency === value} key={value || "all"} onClick={() => setCurrency(value)} type="button">{label}</button>
            ))}
          </div>
        </div>
        <div className="bxm-op-result">
          <span role="status"><strong>{visible.length === 1 ? t("1 past opportunity") : t("{count} past opportunities", { count: visible.length })}</strong></span>
        </div>
      </div>

      <div className="nk-block bxm-op-results">
        {query.isError && past.length === 0 ? (
          <EmptyState actions={<Button onClick={() => void query.refetch()} variant="primary">{t("Retry")}</Button>} icon="alert-circle" title={t("We could not load past opportunities")}>
            {t("Try again in a moment.")}
          </EmptyState>
        ) : query.isPending && past.length === 0 ? (
          <EmptyState icon="clock" title={t("Loading past opportunities")} />
        ) : visible.length === 0 ? (
          <EmptyState icon="archive" title={past.length === 0 ? t("No past opportunities yet") : t("No past opportunity matches your search")} />
        ) : (
          <div className="card card-bordered card-stretch">
            <div className="card-inner-group">
              <div className="card-inner p-0">
                <table className="nk-tb-list nk-tb-ulist bxm-project-list r31-archive">
                  <thead>
                    <tr className="nk-tb-item nk-tb-head">
                      <th className="nk-tb-col"><span className="sub-text">{t("Project")}</span></th>
                      <th className="nk-tb-col tb-col-xxl"><span className="sub-text">{t("Type")}</span></th>
                      <th className="nk-tb-col"><span className="sub-text">{t("Annual interest rate")}</span></th>
                      <th className="nk-tb-col tb-col-md"><span className="sub-text">{t("Duration")}</span></th>
                      <th className="nk-tb-col tb-col-lg"><span className="sub-text">{t("Amount")}</span></th>
                      <th className="nk-tb-col tb-col-md r31-discovery-hidden"><span className="sub-text">{t("Funded")}</span></th>
                      <th className="nk-tb-col tb-col-xxl r31-discovery-hidden"><span className="sub-text">{t("Investors")}</span></th>
                      <th className="nk-tb-col tb-col-sm"><span className="sub-text">{t("Status")}</span></th>
                      <th className="nk-tb-col nk-tb-col-tools"><span className="visually-hidden">{t("Details")}</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((project) => {
                      const funded = project.principal_minor > 0 ? Math.min(100, Math.round((project.committed_principal_minor / project.principal_minor) * 100)) : 0;
                      const sub = [project.originator?.name, project.borrower_country ? project.borrower_country.toUpperCase() : ""].filter(Boolean).join(" · ");
                      return (
                        <tr className="nk-tb-item" key={project.loan_id}>
                          <td className="nk-tb-col">
                            <PortalLink className="project-title" params={{ loanId: project.loan_id, from: "archive" }} to="loan">
                              <div className="bxm-project-tile"><NiIcon name={projectTile(project)} /></div>
                              <div className="project-info">
                                <h6 className="title">{project.title}</h6>
                                {sub ? <span className="sub-text" title={countryName(project.borrower_country)}>{sub}</span> : null}
                              </div>
                            </PortalLink>
                          </td>
                          <td className="nk-tb-col tb-col-xxl"><span>{project.product_type === "originator_claim" ? t("Existing claim") : project.is_refinancing ? t("Refinancing loan") : t("New loan")}</span></td>
                          <td className="nk-tb-col"><span className="tb-lead">{formatRateBps(project.interest_rate_bps)}</span></td>
                          <td className="nk-tb-col tb-col-md"><span>{t("{count} months", { count: project.term_months })}</span></td>
                          <td className="nk-tb-col tb-col-lg"><span>{formatMoneyLabel(project.currency, project.principal_minor)}</span></td>
                          <td className="nk-tb-col tb-col-md r31-discovery-hidden">
                            <div aria-valuemax={100} aria-valuemin={0} aria-valuenow={funded} className="bxm-progress" role="progressbar"><span style={{ width: `${funded}%` }} /></div>
                            <span className="sub-text">{formatPercent(funded, 0)}</span>
                          </td>
                          <td className="nk-tb-col tb-col-xxl r31-discovery-hidden">
                            <span>{typeof project.max_investors === "number" ? `${project.investors_count} / ${project.max_investors}` : project.investors_count}</span>
                          </td>
                          <td className="nk-tb-col tb-col-sm">
                            <StatusTag status={statusOf[project.public_status]} />
                            {project.public_status === "default" && project.record?.defaulted_on ? (
                              <div className="sub-text mt-1">{t("In default since {date}", { date: formatDate(project.record.defaulted_on) })}</div>
                            ) : project.public_status === "late" && (project.record?.days_past_due ?? 0) > 0 ? (
                              <div className="sub-text mt-1">{t("{count} days late", { count: project.record?.days_past_due ?? 0 })}</div>
                            ) : null}
                          </td>
                          <td className="nk-tb-col nk-tb-col-tools">
                            <PortalLink aria-label={t("Details of {title}", { title: project.title })} className="btn btn-sm btn-outline-light" params={{ loanId: project.loan_id, from: "archive" }} to="loan">{t("Details")}</PortalLink>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
