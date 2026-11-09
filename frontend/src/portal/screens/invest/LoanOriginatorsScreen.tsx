// IP of Webby-Soft SRL.
/*
 * Loan originators (design #/originators and #/originators/{id}): the originators with funded claims,
 * their figures (claims funded, volume per currency, late claims), the open opportunities and the
 * earlier claims of one originator. Data: the public originators and projects APIs and the investor
 * marketplace. The design's city, business description, "About the originator" text and founding year
 * have no platform data yet (U33-DEC-23) and are left out.
 */
import type { PublicOriginator, PublicProject } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useBalancesData, useMarketplaceLoansData, usePastProjectsData, usePortfolioData, usePrimaryOrdersData, usePublicOriginatorsData } from "../../../investorPortal/data";
import { formatDate, formatDecimal, formatMoneyLabel, formatPercent, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { Button, EmptyState, NiIcon, PortalLink, StatusTag, type TagStatus } from "../../components";
import { isOpenOrder } from "../portfolio/parts/investmentModel";
import { countryName, isOpenLoan, isOriginatorClaimLoan } from "./loanFacts";
import { OpportunityCard } from "./OpportunitiesScreen";
import "./invest.css";

const statusOf: Record<string, TagStatus | undefined> = {
  fully_funded: "funded",
  repaying: "repaying",
  late: "late",
  repaid: "repaid",
  default: "default"
};

/** Compact volume ("1.84M" in the design), with the investor's decimal mark. */
function compactVolume(amountMinor: number) {
  const whole = amountMinor / 100;
  const trimmed = (value: number) => formatDecimal(value, Number.isInteger(value) ? 0 : Number.isInteger(value * 10) ? 1 : 2);
  if (whole >= 1_000_000) return `${trimmed(Math.round(whole / 10_000) / 100)}M`;
  if (whole >= 1_000) return `${trimmed(Math.round(whole / 100) / 10)}k`;
  return trimmed(Math.round(whole));
}

function OriginatorMetrics({ originator }: { originator: PublicOriginator }) {
  const t = useT();
  return (
    <div className="r75c-metrics r75c-originator-metrics">
      <div><span>{t("Claims funded")}</span><strong>{originator.claims_funded}</strong></div>
      {originator.volume.map((row) => (
        <div key={row.currency}>
          <span>{t("Volume · {currency}", { currency: row.currency })}</span>
          <strong aria-label={formatMoneyLabel(row.currency, row.principal_minor)} tabIndex={0} title={formatMoneyLabel(row.currency, row.principal_minor)}>
            {compactVolume(row.principal_minor)}
          </strong>
        </div>
      ))}
      <div><span>{t("Late claims")}</span><strong className={originator.late_claims > 0 ? "r75c-late" : undefined}>{originator.late_claims}</strong></div>
    </div>
  );
}

export function LoanOriginatorsScreen({ originatorId }: { originatorId?: string }) {
  const t = useT();
  useNumberFormat();
  const query = usePublicOriginatorsData();
  const originators = query.data ?? [];
  const selected = originatorId ? originators.find((item) => item.id === originatorId) : undefined;
  if (originatorId && (selected || query.isPending)) {
    return selected ? <OriginatorProfile originator={selected} /> : <main className="u33-invest-originators"><EmptyState icon="clock" title={t("Loading")} /></main>;
  }
  return (
    <main className="u33-invest-originators">
      <section className="r75c-originators">
        <PortalLink className="r75c-back" to="market"><NiIcon name="arrow-left" />{t("Investment opportunities")}</PortalLink>
        <header className="r75c-head"><div><h1>{t("Loan originators")}</h1></div></header>
        {query.isError && originators.length === 0 ? (
          <EmptyState actions={<Button onClick={() => void query.refetch()} variant="primary">{t("Retry")}</Button>} icon="alert-circle" title={t("We could not load the loan originators")}>
            {t("Try again in a moment.")}
          </EmptyState>
        ) : query.isPending && originators.length === 0 ? (
          <EmptyState icon="clock" title={t("Loading")} />
        ) : originators.length === 0 ? (
          <EmptyState icon="building" title={t("No loan originators yet")} />
        ) : (
          originators.map((originator) => (
            <article className="r75c-surface r75c-originator" key={originator.id}>
              <div>
                <h2><PortalLink params={{ view: "originators", originatorId: originator.id }} to="market">{originator.name}</PortalLink></h2>
                {originator.country ? <span className="r75c-muted">{countryName(originator.country)}</span> : null}
              </div>
              <OriginatorMetrics originator={originator} />
              <PortalLink aria-label={t("View {name}", { name: originator.name })} className="r75c-profile-link" params={{ view: "originators", originatorId: originator.id }} to="market">
                <NiIcon name="arrow-right" />
              </PortalLink>
            </article>
          ))
        )}
        <details className="r75c-disclosure">
          <summary>{t("How loan originators work")} <NiIcon name="chevron-down" /></summary>
          <ol className="bxm-timeline mt-3">
            <li><h6>{t("The originator lends")}</h6><p>{t("The originator grants a loan to a company under its own licence and standards.")}</p></li>
            <li><h6>{t("Banxum buys the claim")}</h6><p>{t("After due diligence, the originator assigns the claim to Banxum in writing.")}</p></li>
            <li><h6>{t("You buy a share")}</h6><p>{t("Banxum assigns your share to you and collects the payments for all investors.")}</p></li>
          </ol>
        </details>
      </section>
    </main>
  );
}

function OriginatorProfile({ originator }: { originator: PublicOriginator }) {
  const t = useT();
  const loans = useMarketplaceLoansData().data ?? [];
  const projects = usePastProjectsData().data ?? [];
  const asOf = useBalancesData().data?.as_of;
  const holdings = usePortfolioData(true).data?.holdings;
  const orders = usePrimaryOrdersData().data?.orders;
  const investedIds = new Set([
    ...(holdings ?? []).filter((holding) => holding.status !== "transferred").map((holding) => holding.loan.loan_id),
    ...(orders ?? []).filter(isOpenOrder).map((order) => order.loan_id)
  ]);
  const open = loans.filter((loan) => isOriginatorClaimLoan(loan) && isOpenLoan(loan) && loan.originator_id === originator.id);
  const earlier = projects.filter((project) => project.originator?.id === originator.id && project.public_status !== "open" && statusOf[project.public_status]);
  return (
    <main className="u33-invest-originators">
      <section className="r75c-originators">
        <PortalLink className="back-to r75c-back" params={{ view: "originators" }} to="market"><NiIcon name="arrow-left" /><span>{t("Loan originators")}</span></PortalLink>
        <header className="r75c-head">
          <div>
            <h1>{originator.name}</h1>
            {originator.country ? <p>{countryName(originator.country)}</p> : null}
          </div>
        </header>
        <div className="r75c-profile-grid">
          <section className="r75c-surface r75c-profile-about">
            <h2>{t("About the originator")}</h2>
            <dl>
              <div><dt>{t("Partner since")}</dt><dd>{formatDate(originator.partner_since)}</dd></div>
            </dl>
            <OriginatorMetrics originator={originator} />
          </section>
          <div className="nk-block r75c-profile-opportunity bxm-op-results">
            <div className="nk-block-head nk-block-head-sm">
              <h5 className="nk-block-title">{t("Open opportunities")} <span className="r75c-muted">{open.length}</span></h5>
            </div>
            {open.length > 0 ? (
              <div className="row g-gs">
                {open.map((loan) => <OpportunityCard asOf={asOf} invested={investedIds.has(loan.loan_id)} key={loan.loan_id} loan={loan} matched={false} />)}
              </div>
            ) : (
              <p className="r75c-muted">{t("No open opportunity from this originator right now.")}</p>
            )}
          </div>
        </div>
        {earlier.length > 0 ? <EarlierClaims projects={earlier} /> : null}
      </section>
    </main>
  );
}

function EarlierClaims({ projects }: { projects: PublicProject[] }) {
  const t = useT();
  return (
    <div className="nk-block r75c-originator-earlier">
      <div className="nk-block-head nk-block-head-sm"><h5 className="nk-block-title">{t("Earlier claims")}</h5></div>
      <div className="card card-bordered card-stretch">
        <div className="card-inner-group">
          <div className="card-inner p-0">
            <table className="nk-tb-list nk-tb-ulist bxm-project-list">
              <thead>
                <tr className="nk-tb-item nk-tb-head">
                  <th className="nk-tb-col"><span className="sub-text">{t("Project")}</span></th>
                  <th className="nk-tb-col tb-col-xxl"><span className="sub-text">{t("Type")}</span></th>
                  <th className="nk-tb-col"><span className="sub-text">{t("Interest")}</span></th>
                  <th className="nk-tb-col tb-col-md"><span className="sub-text">{t("Term")}</span></th>
                  <th className="nk-tb-col tb-col-lg"><span className="sub-text">{t("Amount")}</span></th>
                  <th className="nk-tb-col tb-col-md"><span className="sub-text">{t("Funded")}</span></th>
                  <th className="nk-tb-col tb-col-sm"><span className="sub-text">{t("Status")}</span></th>
                  <th className="nk-tb-col nk-tb-col-tools"><span className="visually-hidden">{t("Details")}</span></th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => {
                  const funded = project.principal_minor > 0 ? Math.min(100, Math.round((project.committed_principal_minor / project.principal_minor) * 100)) : 0;
                  return (
                    <tr className="nk-tb-item" key={project.loan_id}>
                      <td className="nk-tb-col">
                        <PortalLink className="project-title" params={{ loanId: project.loan_id, from: "archive" }} to="loan">
                          <div className="bxm-project-tile"><NiIcon name="file-text" /></div>
                          <div className="project-info">
                            <h6 className="title">{project.title}</h6>
                            {project.borrower_country ? <span className="sub-text">{project.borrower_country.toUpperCase()}</span> : null}
                          </div>
                        </PortalLink>
                      </td>
                      <td className="nk-tb-col tb-col-xxl"><span>{t("Existing claim")}</span></td>
                      <td className="nk-tb-col"><span className="tb-lead">{formatRateBps(project.interest_rate_bps)}</span></td>
                      <td className="nk-tb-col tb-col-md"><span>{t("{count} months", { count: project.term_months })}</span></td>
                      <td className="nk-tb-col tb-col-lg"><span>{formatMoneyLabel(project.currency, project.principal_minor)}</span></td>
                      <td className="nk-tb-col tb-col-md"><span>{formatPercent(funded, 0)}</span></td>
                      <td className="nk-tb-col tb-col-sm"><StatusTag status={statusOf[project.public_status]} /></td>
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
    </div>
  );
}
