// IP of Webby-Soft SRL.
/*
 * Credit file (design #/projects/:id/credit-file, slice S2): the U33 folder cover and the chapter
 * reader, filled only with recorded data. U33-DEC-20: the seven chapters stay: Summary, Borrower &
 * business (the published story and the public profile fields), Financials (the structured years with
 * the key ratios and the existing debt; the last-year figures when no year is recorded), Security (each
 * security of the loan, U33-DEC-21), Loan terms (rate, term, repayment, schedule, originator
 * participation, refinanced loan), Checks & updates (recorded checks, monitoring, recovery stages and
 * loan notes) and Documents (with their library metadata). An empty chapter says what is missing.
 */
import { useState, type ReactNode } from "react";

import type { MarketplaceLoanDetail } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { isFixturePreview, useLoanDetailData } from "../../../investorPortal/data";
import { formatDate, formatDecimal, formatMoneyLabel, formatMoneyMinor, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { LoanDocumentList } from "../../../investorPortal/LoanDocumentList";
import { isNotFoundError } from "../../../investorPortal/session";
import { normalizeStory, storyIsEmpty } from "../../../investorPortal/story";
import { StoryView } from "../../../investorPortal/StoryView";
import { Button, Dialog, EmptyState, NiIcon, PageHead, PdfReader, PortalLink } from "../../components";
import { MOBILE_SHELL_QUERY, useMediaQuery } from "../../shell/useMediaQuery";
import { legalDocumentPath } from "./investRules";
import {
  frequencyWords,
  borrowerDisclosure,
  borrowerName,
  collateralIcon,
  collateralLabel,
  placeName,
  fullLoanSchedule,
  isOpenLoan,
  isOriginatorClaimLoan,
  formatLtv,
  loanLtv,
  loanTypeLabel,
  loanYieldBps,
  minimumFunding,
  repaymentText,
  usesImmediateClaimAssignment,
  usesOriginatorSubscription
} from "./loanFacts";
import { LtvFigure } from "./parts/LtvFigure";
import { ScheduleTable } from "./parts/ScheduleTable";
import "./invest.css";
import { AdditionalSecurityBlock, LtvAssets, SecurityFacts, SecurityNotes } from "./parts/SecurityDetails";
import { ltvValueLabel, splitSecurities } from "./parts/securityParts";
import { ChecksAndUpdates } from "./parts/CreditFileChecks";
import { FinancialStatements } from "./parts/CreditFileFinancials";
import { securityValueLabel } from "../portfolio/parts/labels";

type ChapterId = "summary" | "business" | "financials" | "security" | "terms" | "checks" | "documents";

function humanize(token: string) {
  const text = token.replaceAll("_", " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export function CreditFileScreen({ loanId, initialChapter }: { loanId: string; initialChapter?: string }) {
  const t = useT();
  const loanQuery = useLoanDetailData(loanId);
  const loan = loanQuery.data;
  const back = <PortalLink className="back" params={{ loanId }} to="loan"><NiIcon name="arrow-left" />{t("Back to the opportunity")}</PortalLink>;
  if (loanQuery.isError && !loan) {
    const notFound = isNotFoundError(loanQuery.error);
    return (
      <main className="r37-credit r100-credit u33-invest-state">
        {back}
        <PageHead title={t("Credit file")} />
        <EmptyState
          actions={notFound ? null : <Button onClick={() => void loanQuery.refetch()} variant="primary">{t("Retry")}</Button>}
          icon={notFound ? "search" : "alert-circle"}
          title={notFound ? t("This loan does not exist, or it is no longer shown to investors.") : t("We could not load this credit file")}
        />
      </main>
    );
  }
  if (!loan) {
    return (
      <main className="r37-credit r100-credit u33-invest-state">
        {back}
        <EmptyState icon="clock" title={t("Loading the credit file")} />
      </main>
    );
  }
  return <CreditFile back={back} initialChapter={initialChapter} key={loan.loan_id} loan={loan} />;
}

function CreditFile({ loan, back, initialChapter }: { loan: MarketplaceLoanDetail; back: ReactNode; initialChapter?: string }) {
  const t = useT();
  useNumberFormat();
  const mobile = useMediaQuery(MOBILE_SHELL_QUERY);
  const disclosure = borrowerDisclosure(loan);
  const company = borrowerName(loan);
  const country = placeName(disclosure.city, disclosure.country);
  const sector = disclosure.business_classification || disclosure.industry_activity || "";
  const documents = (disclosure.documents ?? []).filter((document) => document && typeof document === "object");
  const financialsCurrency = disclosure.financials_currency || loan.currency;
  const financials = [
    ["revenue", t("Revenue"), disclosure.revenue_last_year_minor],
    ["profit", t("Profit"), disclosure.profit_last_year_minor],
    ["assets", t("Total assets"), disclosure.assets_minor],
    ["liabilities", t("Total liabilities"), disclosure.liabilities_minor]
  ].filter((row): row is [string, string, number] => typeof row[2] === "number");
  // `short` is the cover divider label (design: Summary, Business, Financials, Security, Terms, ...).
  const chapters: Array<{ id: ChapterId; label: string; short: string }> = [
    { id: "summary", label: t("Summary"), short: t("Summary") },
    { id: "business", label: isOriginatorClaimLoan(loan) ? t("Borrower & originator") : t("Borrower & business"), short: t("Business") },
    { id: "financials", label: t("Financials"), short: t("Financials") },
    { id: "security", label: t("Security"), short: t("Security") },
    { id: "terms", label: t("Loan terms"), short: t("Terms") },
    // Design cover tab: "06 Review" (the chapter itself is "Checks & updates").
    { id: "checks", label: t("Checks & updates"), short: t("Review") },
    { id: "documents", label: t("Documents"), short: t("Documents") }
  ];
  const financialYears = loan.financial_years ?? [];
  const known = chapters.find((chapter) => chapter.id === initialChapter);
  const [opened, setOpened] = useState(Boolean(known));
  const [chapter, setChapter] = useState<ChapterId>(known?.id ?? "summary");
  const [scheduleOpen, setScheduleOpen] = useState(false);
  // 18.3: a borrower PDF opens in the in-app reader.
  const [reader, setReader] = useState<{ title: string; data: Uint8Array; filename: string } | null>(null);
  const number = (position: number) => String(position + 1).padStart(2, "0");
  const openChapter = (id: ChapterId) => {
    setOpened(true);
    setChapter(id);
    // A chapter changed from the bottom of a long chapter starts at its top.
    window.requestAnimationFrame(() => {
      const reader = document.getElementById("r47-credit-reader");
      if (reader && reader.getBoundingClientRect().top < 0) reader.scrollIntoView({ block: "start" });
    });
  };
  const open = isOpenLoan(loan);
  const shortId = loan.loan_id.length > 12 ? loan.loan_id.slice(0, 8).toUpperCase() : loan.loan_id.toUpperCase();
  const statusText = open ? t("Funding open") : loan.loan_status === "repaid" ? t("Repaid") : ["defaulted", "written_off"].includes(loan.loan_status) ? t("Default") : t("Funding closed");

  const heading = (id: ChapterId, title: string, context?: string) => {
    const position = chapters.findIndex((item) => item.id === id);
    const previous = chapters[position - 1];
    const next = chapters[position + 1];
    return (
      <div className="r100-heading">
        <span className="r100-no">{number(position)}</span>
        <h2 id={`heading-${id}`}>{title}</h2>
        {context ? <span className="r100-context">{context}</span> : null}
        <nav aria-label={t("Chapter navigation")} className="r100-nav-arrows">
          {previous ? (
            <a aria-label={t("Previous: {title}", { title: previous.label })} className="r100-arrow" href={`#${previous.id}`} onClick={(event) => { event.preventDefault(); openChapter(previous.id); }} title={previous.label}>
              <NiIcon name="arrow-left" />
            </a>
          ) : <span aria-hidden="true" className="r100-arrow disabled"><NiIcon name="arrow-left" /></span>}
          {next ? (
            <a aria-label={t("Next: {title}", { title: next.label })} className="r100-arrow" href={`#${next.id}`} onClick={(event) => { event.preventDefault(); openChapter(next.id); }} title={next.label}>
              <NiIcon name="arrow-right" />
            </a>
          ) : <span aria-hidden="true" className="r100-arrow disabled"><NiIcon name="arrow-right" /></span>}
        </nav>
      </div>
    );
  };
  const chapterLink = (id: ChapterId, label: string) =>
    chapters.some((item) => item.id === id) ? (
      <a className="r100-link" href={`#${id}`} onClick={(event) => { event.preventDefault(); openChapter(id); }}>
        <span>{label}</span><NiIcon name="arrow-right" />
      </a>
    ) : null;

  return (
    <section className={`r37-credit cf-demo r100-credit${opened ? "" : " r37-closed"}${mobile ? " m82-credit-navigation" : ""}`} data-chapter={chapter} data-ready={opened ? "true" : "false"}>
      {back}
      <header className="case-head">
        <div>
          <h1>{t("Credit file")}</h1>
          <p className="heading-project">{loan.title}</p>
          <div className="head-meta">
            {[company !== loan.title ? company : "", country, sector, loan.credit_file_updated_at ? t("Updated {date}", { date: formatDate(loan.credit_file_updated_at) }) : ""].filter(Boolean).flatMap((item, position) => [
              position > 0 ? <i aria-hidden="true" key={`sep-${item}`} /> : null,
              <span key={item}>{item}</span>
            ])}
          </div>
        </div>
        <div className="r37-file-actions">
          {documents.length > 0 ? (
            <button className="outline head-action" onClick={() => openChapter("documents")} type="button">
              <span>{t("View Documents")}</span><NiIcon name="arrow-right" />
            </button>
          ) : null}
          {open ? (
            <PortalLink className="r37-primary" params={{ loanId: loan.loan_id }} to="loan">
              {t("Choose investment amount")} <NiIcon name="arrow-right" />
            </PortalLink>
          ) : null}
        </div>
      </header>

      {!opened ? (
        <div className="r37-folder-opening r47-stage">
          <div aria-hidden="true" className="r47-paper back-sheet" />
          <div aria-hidden="true" className="r47-paper" />
          <ol aria-label={t("Credit file sections")} className="r47-dividers">
            {chapters.map((item, position) => (
              <li key={item.id} style={{ ["--r47-tab-offset" as string]: `${position * 2}px` }}>
                <button aria-controls="r47-credit-reader" aria-expanded="false" aria-label={t("Open {title} section", { title: item.label })} className="r47-divider" onClick={() => openChapter(item.id)} type="button">
                  <span aria-hidden="true">{number(position)}</span>
                  {item.short}
                </button>
              </li>
            ))}
          </ol>
          <section aria-labelledby="r47-project-title" className="r47-cover">
            <span className="r47-tab-id">{`BANXUM · ${shortId}`}</span>
            <div className="r47-cover-meta"><strong>{t("Credit file")}</strong><span>{statusText}</span></div>
            <div className="r47-main">
              <p className="r47-eyebrow">{isOriginatorClaimLoan(loan) ? t("Existing claim") : t("Company & financing")}</p>
              <h1 id="r47-project-title">{loan.title}</h1>
              {company && company !== loan.title ? <p className="r47-company">{company}</p> : null}
              {country || sector ? <p className="r47-location">{[country, sector].filter(Boolean).join(" · ")}</p> : null}
            </div>
            <dl className="r47-facts">
              <div><dt>{t("Chapters")}</dt><dd>{chapters.length}</dd></div>
              {financials.length > 0 ? <div><dt>{t("Financial history")}</dt><dd>{t("Last year")}</dd></div> : null}
              <div><dt>{isOriginatorClaimLoan(loan) ? t("Claim offered") : t("Total loan amount")}</dt><dd>{`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency, 0)}`}</dd></div>
            </dl>
            <div className="r47-bottom">
              <p>{t("Business, financials, security")}<br />{t("and supporting documents.")}</p>
              <button aria-controls="r47-credit-reader" aria-expanded="false" className="r47-open" onClick={() => openChapter("summary")} type="button">
                {t("Open credit file")} <NiIcon name="arrow-right" />
              </button>
            </div>
          </section>
        </div>
      ) : null}

      <div className="reader-layout" hidden={!opened} id="r47-credit-reader">
        <nav aria-label={t("Credit file navigation")} className="m82-credit-nav">
          <label className="m82-credit-chapter">
            <span>{t("Chapter")}</span>
            <select aria-label={t("Credit file chapter")} onChange={(event) => openChapter(event.target.value as ChapterId)} value={chapter}>
              {chapters.map((item, position) => <option key={item.id} value={item.id}>{`${number(position)} ${item.label}`}</option>)}
            </select>
          </label>
        </nav>
        <nav aria-label={t("Credit file contents")} className="case-nav">
          <div className="nav-caption">{t("In this file")}</div>
          {chapters.map((item, position) => (
            <button aria-current={item.id === chapter ? "location" : undefined} className={item.id === chapter ? "active" : ""} key={item.id} onClick={() => openChapter(item.id)} type="button">
              <span>{number(position)}</span>
              <b>{item.label}</b>
            </button>
          ))}
          <div className="nav-foot">
            <strong className="nav-project">{loan.title}</strong>
            <span>{`${shortId} · ${loan.currency}`}</span>
          </div>
          <PortalLink className="nav-footer-action" params={{ loanId: loan.loan_id }} to="loan"><NiIcon name="arrow-left" />{t("Back to opportunity")}</PortalLink>
        </nav>
        <main className="case-content">
          {chapter === "summary" ? (
            <section aria-labelledby="heading-summary" className="case-chapter r100-chapter" id="summary">
              {heading("summary", t("Summary"), statusText)}
              <p className="r100-lead">{loan.investor_summary || loan.purpose_description}</p>
              <SummaryTerms loan={loan} />
              <div className="r100-two">
                <section>
                  <h3>{t("Intended use of funds")}</h3>
                  <p>{loan.purpose_description || humanize(loan.purpose)}</p>
                  {chapterLink("business", isOriginatorClaimLoan(loan) ? t("View Borrower & originator") : t("View Borrower & business"))}
                </section>
                <section>
                  <h3>{t("Security")}</h3>
                  <p>{[collateralLabel(loan.collateral_type), loan.collateral_description !== loan.collateral_type ? loan.collateral_description : ""].filter(Boolean).join(": ")}</p>
                  {chapterLink("security", t("View Security"))}
                </section>
              </div>
              {loan.is_refinancing ? (
                <aside className="r100-material">
                  <div><NiIcon name="file-check" /><strong>{t("Refinancing")}</strong></div>
                  <p>{t("This loan refinances an existing loan of the borrower. The original terms are in Loan terms.")}</p>
                </aside>
              ) : null}
              {usesOriginatorSubscription(loan) ? (
                <aside className="r100-material">
                  <div><NiIcon name="file-check" /><strong>{t("Loan Originator claim")}</strong></div>
                  <p>{t("You receive {share} of the borrower's interest and your share of the principal. The first installment after the funding deadline belongs to the Loan Originator.", { share: formatRateBps(loan.investor_interest_participation_bps ?? 0) })}</p>
                </aside>
              ) : null}
            </section>
          ) : null}

          {chapter === "business" ? <BusinessChapter heading={heading} loan={loan} /> : null}

          {chapter === "financials" ? (
            <section aria-labelledby="heading-financials" className="case-chapter r100-chapter" id="financials">
              {heading("financials", t("Financials"))}
              {/* 18.3: the design's "Source of repayment" (cf-text-fact). */}
              {loan.repayment_source ? (
                <div className="cf-text-fact section-row">
                  <h3>{t("Source of repayment")}</h3>
                  <p className="section-intro">{loan.repayment_source}</p>
                </div>
              ) : null}
              {financialYears.length > 0 ? (
                <FinancialStatements company={company} currency={financialsCurrency} facilities={loan.debt_facilities ?? []} years={financialYears} />
              ) : financials.length > 0 ? (
              <>
              <div className="r100-financial-context">
                <span>{[company, t("last financial year")].filter(Boolean).join(" · ")}</span>
                <span><span>{t("As disclosed")}</span> · {financialsCurrency}</span>
              </div>
              <section aria-labelledby="r100-figures-title" className="r100-financial-card">
                <div className="r100-table-heading"><h3 id="r100-figures-title">{t("Key figures")}</h3><span>{t("Last financial year")}</span></div>
                <div className="r100-table-scroll">
                  <table className="r100-table r100-financial-table">
                    <thead><tr><th scope="col"><span className="visually-hidden">{t("Measure")}</span></th><th scope="col">{t("Last year")}</th></tr></thead>
                    <tbody>
                      {financials.map(([key, label, value]) => (
                        <tr key={key}>
                          <th scope="row"><span className="r100-row-indent" /><span>{label}</span></th>
                          <td>{formatMoneyLabel(financialsCurrency, value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <p className="bxm-muted small">{t("Figures as disclosed for the borrower's last financial year. They are not audited by Banxum.")}</p>
              </>
              ) : (
                <p className="bxm-muted">{t("No financial figures are published for this borrower.")}</p>
              )}
            </section>
          ) : null}

          {chapter === "checks" ? (
            <section aria-labelledby="heading-checks" className="case-chapter r100-chapter" id="checks">
              {heading("checks", t("Checks & updates"))}
              <ChecksAndUpdates loan={loan} />
            </section>
          ) : null}

          {chapter === "security" ? <SecurityChapter heading={heading} loan={loan} /> : null}

          {chapter === "terms" ? (
            <section aria-labelledby="heading-terms" className="case-chapter r100-chapter" id="terms">
              {heading("terms", t("Loan terms"))}
              <p className="r100-terms-intro"><span>{loanTypeLabel(loan)}</span> · <span>{t("Rights to principal and interest payments")}</span></p>
              <div className="r100-key-terms">
                <div><span>{usesOriginatorSubscription(loan) ? t("Investor interest rate") : t("Annual interest rate")}</span><strong>{formatRateBps(loanYieldBps(loan))}</strong><small>{t("On outstanding principal")}</small></div>
                <div><span>{t("Investment term")}</span><strong>{loan.term_months} <small>{t("months")}</small></strong></div>
                <div><span>{isOriginatorClaimLoan(loan) ? t("Claim offered") : t("Total loan amount")}</span><strong>{`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency, 0)}`}</strong></div>
              </div>
              <section className="r100-repayment">
                <div>
                  <h3>{t("Repayments")}</h3>
                  <p>{repaymentText(loan.repayment_type, loan.payment_frequency) || t("As the loan schedule says")}</p>
                </div>
                {fullLoanSchedule(loan).length > 0 ? (
                  <button aria-haspopup="dialog" className="r100-compact-schedule" onClick={() => setScheduleOpen(true)} type="button">
                    <NiIcon name="calendar" />
                    <span>
                      <b>{t("Payment schedule")}</b>
                      <small><span>{t("Full loan")}</span> · <span>{t("{count} payments", { count: fullLoanSchedule(loan).length })}</span></small>
                    </span>
                    <NiIcon name="arrow-up-right" />
                  </button>
                ) : null}
              </section>
              <TermsFacts loan={loan} />
              {(loan.originator_payment_history ?? []).length > 0 ? <BorrowerPayments loan={loan} /> : null}
              {loan.is_refinancing ? <OriginalLoan loan={loan} /> : null}
              <div className="r100-contract">
                <NiIcon name="file-text" />
                <div>
                  <a className="r100-link" href={legalDocumentPath("primary_market_investment")} rel="noopener noreferrer" target="_blank">
                    <span>{t("Investment terms and claim assignment")}</span><NiIcon name="arrow-up-right" />
                  </a>
                  <small>{t("Contractual conditions")}</small>
                </div>
              </div>
            </section>
          ) : null}

          {chapter === "documents" ? (
            <section aria-labelledby="heading-documents" className="case-chapter r100-chapter" id="documents">
              {heading("documents", t("Documents"))}
              <div className="r100-file-library">
                <section className="r100-file-group">
                  <h3>{t("Borrower documents")}</h3>
                  {documents.length > 0 ? (
                    <LoanDocumentList disabled={isFixturePreview} documents={documents} humanize={humanize} loanId={loan.loan_id} onView={(file) => setReader(file)} />
                  ) : (
                    <p className="bxm-muted">{t("No document is published for this loan.")}</p>
                  )}
                </section>
              </div>
            </section>
          ) : null}
        </main>
      </div>

      {scheduleOpen ? (
        <Dialog className="u33-invest-schedule-dialog" onClose={() => setScheduleOpen(false)} size="lg" title={t("Payment schedule")}>
          <p className="bxm-muted">{t("Full loan · {amount}", { amount: formatMoneyLabel(loan.currency, loan.principal_minor) })}</p>
          <ScheduleTable currency={loan.currency} label={t("Full loan payment schedule, {count} payments", { count: fullLoanSchedule(loan).length })} rows={fullLoanSchedule(loan)} />
        </Dialog>
      ) : null}
      {reader ? <PdfReader load={async () => reader} onClose={() => setReader(null)} title={reader.title} /> : null}
    </section>
  );
}

function SummaryTerms({ loan }: { loan: MarketplaceLoanDetail }) {
  const t = useT();
  const minimum = minimumFunding(loan);
  return (
    <div className="r100-terms">
      <div>
        <span>{usesOriginatorSubscription(loan) ? t("Investor interest rate") : t("Annual interest rate")}</span>
        <strong>{formatRateBps(loanYieldBps(loan))}</strong>
        {/* Design credit file: "Principal and interest monthly". */}
        {repaymentText(loan.repayment_type, loan.payment_frequency) ? <small>{["equal_installments", "amortizing_principal_interest"].includes(loan.repayment_type) ? t("Principal and interest {frequency}", { frequency: frequencyWords(loan.payment_frequency).adverb }) : repaymentText(loan.repayment_type, loan.payment_frequency)}</small> : null}
      </div>
      <div>
        <span>{t("Investment term")}</span>
        <strong>{loan.term_months} <small>{t("months")}</small></strong>
        <small>{isOriginatorClaimLoan(loan) ? t("Remaining schedule") : t("From funding close")}</small>
      </div>
      <div>
        <span>{isOriginatorClaimLoan(loan) ? t("Claim offered") : t("Total loan amount")}</span>
        <strong>{`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency, 0)}`}</strong>
        {minimum ? <small><span>{t("Minimum funding")}</span> {`${loan.currency} ${formatMoneyMinor(minimum.amountMinor, loan.currency, 0)}`}</small> : null}
      </div>
    </div>
  );
}

type HeadingFn = (id: ChapterId, title: string, context?: string) => ReactNode;

function BusinessChapter({ loan, heading }: { loan: MarketplaceLoanDetail; heading: HeadingFn }) {
  const t = useT();
  const disclosure = borrowerDisclosure(loan);
  const story = normalizeStory(loan.story);
  const claim = isOriginatorClaimLoan(loan);
  // Design order: Established, Employees, Industry. The head count always shows its year (U33-DEC-23).
  const employees = typeof disclosure.employees === "number" && typeof disclosure.employees_year === "number"
    ? t("{count} in {year}", { count: formatDecimal(disclosure.employees, 0), year: disclosure.employees_year })
    : "";
  const facts = [
    ["established", t("Established"), disclosure.year_founded ? String(disclosure.year_founded) : ""],
    ["employees", t("Employees"), employees],
    ["industry", t("Industry"), disclosure.business_classification || disclosure.industry_activity || ""],
    ["location", t("Location"), placeName(disclosure.city, disclosure.country)]
  ].filter((row) => row[2]);
  const records = [
    ["address", t("Registered address"), disclosure.registered_address ?? ""],
    ["contact", t("Contact"), disclosure.contact_info ?? ""]
  ].filter((row) => row[2]);
  return (
    <section aria-labelledby="heading-business" className="case-chapter r100-chapter" id="business">
      {heading("business", claim ? t("Borrower & originator") : t("Borrower & business"))}
      <p className="r100-lead">{borrowerName(loan) || loan.title}</p>
      {facts.length > 0 ? (
        <div className="r100-company r100-company-inline">
          {facts.map(([key, label, value]) => <div key={key}><small>{label}</small><strong>{value}</strong></div>)}
        </div>
      ) : null}
      {claim && loan.originator_name ? (
        <section className="r100-section">
          <div className="r100-section-head"><h3>{t("Loan originator")}</h3><span>{loan.originator_name}</span></div>
          <p>
            {(loan.skin_in_the_game_bps ?? 0) > 0
              ? t("{name} made the loan to the borrower and keeps {share} of the outstanding principal.", { name: loan.originator_name, share: formatRateBps(loan.skin_in_the_game_bps ?? 0) })
              : t("{name} made the loan to the borrower.", { name: loan.originator_name })}
          </p>
        </section>
      ) : null}
      <section className="r100-section r100-meet">
        <div className="r100-section-head"><h3>{claim ? t("About the loan originator") : t("Meet the borrower")}</h3><span>{t("Published by Banxum")}</span></div>
        {storyIsEmpty(story) ? (
          <p className="bxm-muted">{claim ? t("No profile of this loan originator has been published yet.") : t("No profile of this borrower has been published yet.")}</p>
        ) : (
          <div className="u33-invest-story"><StoryView story={story} /></div>
        )}
      </section>
      {records.length > 0 ? (
        <dl className="r100-facts">
          {records.map(([key, label, value]) => <div key={key}><dt>{label}</dt><dd>{value}</dd></div>)}
        </dl>
      ) : null}
    </section>
  );
}

function SecurityChapter({ loan, heading }: { loan: MarketplaceLoanDetail; heading: HeadingFn }) {
  const t = useT();
  const ltv = loanLtv(loan);
  const hasValue = ltv !== null && loan.collateral_value_minor > 0;
  // C06: the main security gives the summary; the others follow, each on its own. F16: the
  // loan-to-value uses the sum of the counted assets, listed when there are several.
  const { main: first, others, counted } = splitSecurities(loan.securities ?? []);
  const valueLabel = ltvValueLabel(counted, loan.collateral_type, t);
  return (
    <section aria-labelledby="heading-security" className="case-chapter r100-chapter" id="security">
      {heading("security", t("Security"))}
      <section className="r100-security-block">
        <div className="r100-security-title">
          <span className="r100-symbol"><NiIcon name={collateralIcon(loan.collateral_type)} /></span>
          <div>
            <h3>{collateralLabel(loan.collateral_type)}</h3>
            {loan.collateral_description && loan.collateral_description !== loan.collateral_type ? <p>{loan.collateral_description}</p> : null}
          </div>
        </div>
        {hasValue && ltv !== null ? (
          <div className="r100-property-grid">
            <div className="r100-security-graph">
              <LtvFigure currency={loan.currency} loanMinor={loan.principal_minor} ltvBps={ltv} valueLabel={valueLabel} valueMinor={loan.collateral_value_minor} />
            </div>
            <div>
              <dl className="r100-security-facts compact">
                <div><dt>{valueLabel}</dt><dd>{formatMoneyLabel(loan.currency, loan.collateral_value_minor)}</dd></div>
                <div><dt>{t("Loan-to-value")}</dt><dd>{formatLtv(ltv)}</dd></div>
              </dl>
              <LtvAssets counted={counted} currency={loan.currency} main={first} />
            </div>
          </div>
        ) : first?.is_guarantee ? null : (
          <dl className="r100-security-facts r100-security-record">
            <div><dt>{t(securityValueLabel(loan.collateral_type))}</dt><dd>{t("Not recorded")}</dd></div>
          </dl>
        )}
        {first ? (
          <>
            <SecurityFacts currency={loan.currency} loanMinor={loan.principal_minor} security={first} withValue={!(counted.length === 1 && counted[0] === first)} />
            <SecurityNotes security={first} />
          </>
        ) : null}
        {(loan.ltv_warnings ?? []).length > 0 ? (
          <ul className="u33-invest-warnings">{loan.ltv_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        ) : null}
      </section>
      {others.map((security) => <AdditionalSecurityBlock currency={loan.currency} key={security.id} loanMinor={loan.principal_minor} security={security} />)}
      <p className="bxm-muted small">{t("Security can help recover money if the borrower stops paying. It does not guarantee repayment.")}</p>
    </section>
  );
}

function TermsFacts({ loan }: { loan: MarketplaceLoanDetail }) {
  const t = useT();
  const rows: Array<[string, string]> = [];
  if (usesOriginatorSubscription(loan)) {
    // U33-DEC-24: the actual split of this loan, for interest and for penalty interest (set case by case).
    const interestShare = loan.investor_interest_participation_bps ?? 0;
    rows.push([t("Borrower interest rate"), formatRateBps(loan.underlying_interest_rate_bps)]);
    rows.push([t("Your share of the borrower's interest"), formatRateBps(interestShare)]);
    rows.push([t("Originator's share of interest"), formatRateBps(10_000 - interestShare)]);
    if (loan.investor_penalty_participation_bps !== null && loan.investor_penalty_participation_bps !== undefined) {
      rows.push([t("Your share of penalty interest"), formatRateBps(loan.investor_penalty_participation_bps)]);
      rows.push([t("Originator's share of penalty interest"), formatRateBps(10_000 - loan.investor_penalty_participation_bps)]);
    }
    if (loan.entitlement_start_date) rows.push([t("First installment for the Loan Originator"), formatDate(loan.entitlement_start_date)]);
    if (loan.funding_deadline) rows.push([t("Funding deadline"), formatDate(loan.funding_deadline)]);
  } else if (usesImmediateClaimAssignment(loan)) {
    rows.push([t("Borrower interest rate"), formatRateBps(loan.underlying_interest_rate_bps)]);
    rows.push([t("Target investor yield"), `${formatRateBps(loan.yield_bps)} ${t("effective annual · ACT/365")}`]);
    if (loan.maturity_date) rows.push([t("Maturity"), formatDate(loan.maturity_date)]);
    if (loan.pricing_as_of_date) rows.push([t("Pricing data as of"), formatDate(loan.pricing_as_of_date)]);
  } else if (loan.first_payment_date) {
    rows.push([t("First payment"), formatDate(loan.first_payment_date)]);
  }
  if (isOriginatorClaimLoan(loan) && (loan.skin_in_the_game_bps ?? 0) > 0) rows.push([t("Kept by the originator"), formatRateBps(loan.skin_in_the_game_bps ?? 0)]);
  if ((loan.default_penalty_interest_bps ?? 0) > 0) rows.push([t("Penalty interest on overdue amounts"), t("{rate} a year", { rate: formatRateBps(loan.default_penalty_interest_bps ?? 0) })]);
  if (rows.length === 0) return null;
  return (
    <section className="r100-early">
      <h3>{t("Terms for investors")}</h3>
      <dl className="r100-facts">
        {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
    </section>
  );
}

function OriginalLoan({ loan }: { loan: MarketplaceLoanDetail }) {
  const t = useT();
  const schedule = loan.original_loan_schedule ?? [];
  const facts: Array<[string, string]> = [[t("Original principal"), formatMoneyLabel(loan.currency, loan.original_principal_minor)]];
  if (loan.original_interest_rate_bps !== null) facts.push([t("Original interest rate"), formatRateBps(loan.original_interest_rate_bps)]);
  if (loan.original_term_months !== null) facts.push([t("Original term"), t("{count} months", { count: loan.original_term_months })]);
  if (loan.original_repayment_type) facts.push([t("Original repayment"), repaymentText(loan.original_repayment_type)]);
  if (loan.original_loan_start_date) facts.push([t("Original start date"), formatDate(loan.original_loan_start_date)]);
  return (
    <details className="r100-detail" id="r100-original-loan">
      <summary>
        <span>{t("Refinanced loan: original terms")}</span>
        <small>{formatMoneyLabel(loan.currency, loan.original_principal_minor)}</small>
        <NiIcon name="chevron-down" />
      </summary>
      <dl className="r100-facts">
        {facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
      <p>{t("This loan refinances an existing loan of the borrower. The original loan is shown for information; investors fund the new loan on the terms above.")}</p>
      {schedule.length > 0 ? (
        <ScheduleTable
          currency={loan.currency}
          label={t("Original loan repayment schedule")}
          rows={schedule.map((row) => ({ key: String(row.installment_number), dueDate: row.due_date, principalMinor: row.principal_minor, interestMinor: row.interest_minor, totalMinor: row.total_minor }))}
        />
      ) : null}
    </details>
  );
}

/** Payments the borrower made on an originator claim before and during the offer (imported evidence). */
function BorrowerPayments({ loan }: { loan: MarketplaceLoanDetail }) {
  const t = useT();
  const payments = loan.originator_payment_history ?? [];
  return (
    <details className="r100-detail" id="r100-borrower-payments">
      <summary>
        <span>{t("Payments received from the borrower")}</span>
        <small>{payments.length === 1 ? t("1 payment") : t("{count} payments", { count: payments.length })}</small>
        <NiIcon name="chevron-down" />
      </summary>
      <div className="pd-schedule-table" role="region" tabIndex={0} aria-label={t("Payments received from the borrower")}>
        <table className="table bxm-table">
          <thead>
            <tr>
              <th scope="col">{t("Value date")}</th>
              <th scope="col">{t("Reference")}</th>
              <th className="text-end" scope="col">{t("Total")}</th>
              <th className="text-end" scope="col">{t("Principal after")}</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((row) => (
              <tr key={`${row.reference}-${row.value_date}`}>
                <td>{formatDate(row.value_date)}</td>
                <td>{row.reference}</td>
                <td className="text-end">{formatMoneyLabel(loan.currency, row.total_minor)}</td>
                <td className="text-end">{formatMoneyLabel(loan.currency, row.resulting_principal_minor)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
