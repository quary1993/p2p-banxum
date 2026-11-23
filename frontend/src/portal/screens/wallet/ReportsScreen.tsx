// IP of Webby-Soft SRL.
/*
 * Reports (design #/reports: main.tr-page.tr-reports-page): the Period (All time, last 30/90 days, a
 * year, custom dates; a report matches when its period overlaps), the type filter, the summary per
 * currency (for a year or all time), and one list with
 * - the reports kept as issued (GET /investor/portal/reports/): those the investor created (Account
 *   statement, Portfolio report, Interest and repayments, Tax report) and the monthly statements the
 *   platform creates (18.3);
 * - the account statements and the annual tax information the platform offers on request
 *   (GET /investor/portal/documents/).
 * A PDF opens in the in-app reader ("View"); a CSV is downloaded. Create report generates and keeps a
 * report for a month range (the portfolio as of today), a currency and a format; a "Document ready"
 * notification announces it. The Tax report says it is not an official tax certificate (E-09).
 */
import { useCallback, useId, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  getV1InvestorPortalReportsRetrieveQueryKey,
  v1InvestorPortalDocumentsDownloadCreate,
  v1InvestorPortalReportsCreate,
  v1InvestorPortalReportsDownloadRetrieve,
  type InvestorDocument,
  type InvestorReport,
  type InvestorReportCreateRequestKindEnum
} from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useDocumentsData, useInvestorReportsData, useReportSummaryData } from "../../../investorPortal/data";
import { formatDate, formatMoneyMinor, zurichDateKey } from "../../../investorPortal/format";
import { platformTodayKey } from "../../../investorPortal/platformClock";
import { EmptyState, NiIcon, PageHead, PdfReader, bytesOfArtifact, type PdfFile } from "../../components";
import {
  REPORT_TYPES,
  documentYears,
  isReport,
  keptPeriodLabel,
  keptYears,
  monthRange,
  newestFirst,
  periodLabel,
  reportFilterOf,
  reportSubtitle,
  reportTitle,
  type ReportFilter
} from "./documentsModel";
import { documentDownloadRequest, downloadPortalArtifact, errorMessage, useDocumentDownload } from "./parts/downloads";
import { Toast } from "./parts/Toast";
import { WalletDialog } from "./parts/WalletDialog";
import { choiceToPeriod, periodRange, type PeriodChoice } from "./transactionsModel";
import "./wallet.css";

type Row =
  | { key: string; filter: ReportFilter; years: number[]; sortKey: string; source: "kept"; report: InvestorReport }
  | { key: string; filter: ReportFilter; years: number[]; sortKey: string; source: "offered"; document: InvestorDocument };

type Reader = { title: string; load: () => Promise<PdfFile> };

const KEPT_NOTES: Record<string, string> = {
  monthly_statement: "Created by Banxum each month",
  account_statement: "Money received, invested, sent back and withdrawn",
  portfolio: "Your investments and their status",
  interest_repayments: "Every repayment, split into principal and interest",
  tax: "For your tax return. Not an official tax certificate."
};

function CreateReportDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (report: InvestorReport) => void }) {
  const t = useT();
  const titleId = useId();
  const today = platformTodayKey();
  const thisMonth = today.slice(0, 7);
  const [kind, setKind] = useState<ReportFilter>("account_statement");
  const [from, setFrom] = useState(`${today.slice(0, 4)}-01`);
  const [to, setTo] = useState(thisMonth);
  const [currency, setCurrency] = useState<"" | "EUR" | "CHF">("");
  const [format, setFormat] = useState<"pdf" | "csv">("pdf");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (kind !== "portfolio") {
      if (!from || !to || from > to) {
        setError(t("Choose a valid start and end month. The start must not be after the end."));
        return;
      }
      if (to > thisMonth) {
        setError(t("A report can end this month at the latest."));
        return;
      }
    }
    const range = kind === "portfolio" ? { start: today, end: today } : monthRange(from, to, today);
    setBusy(true);
    try {
      const report = await v1InvestorPortalReportsCreate({
        kind: kind as InvestorReportCreateRequestKindEnum,
        start_date: range.start,
        end_date: range.end,
        currency,
        output_format: format
      });
      onCreated(report);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <WalletDialog busy={busy} className="tr-report-modal" labelledBy={titleId} onClose={onClose} size="lg">
      <form className="tr-report-form rr-report-form" noValidate onSubmit={(event) => void submit(event)}>
        <div className="tr-form-head">
          <div>
            <h3 id={titleId}>{t("Create report")}</h3>
            <p>{t("Choose the information you need.")}</p>
          </div>
          <button aria-label={t("Close")} className="tr-close" data-autofocus disabled={busy} onClick={onClose} type="button"><NiIcon name="cross" /></button>
        </div>
        <div className="tr-form-body">
          <fieldset>
            <legend className="form-label">{t("Report type")}</legend>
            <div className="tr-report-options">
              {REPORT_TYPES.map((item) => (
                <label className="tr-report-option" key={item.value}>
                  <input checked={kind === item.value} name="type" onChange={() => setKind(item.value)} type="radio" value={item.value} />
                  <span><strong>{t(item.label)}</strong><small>{t(item.help)}</small></span>
                </label>
              ))}
            </div>
          </fieldset>
          {kind === "portfolio" ? (
            <div className="tr-as-of">
              <span>{t("As of {date}", { date: formatDate(today) })}</span>
              <small>{t("Your current investments and their status.")}</small>
            </div>
          ) : (
            <div className="tr-form-row">
              <div>
                <label className="form-label" htmlFor="tr-rp-from">{t("From")}</label>
                <input aria-describedby="wl-report-error" className="form-control" id="tr-rp-from" max={thisMonth} onChange={(event) => setFrom(event.target.value)} required type="month" value={from} />
              </div>
              <div>
                <label className="form-label" htmlFor="tr-rp-to">{t("date|To")}</label>
                <input aria-describedby="wl-report-error" className="form-control" id="tr-rp-to" max={thisMonth} onChange={(event) => setTo(event.target.value)} required type="month" value={to} />
              </div>
            </div>
          )}
          <div className="tr-form-row">
            <div>
              <label className="form-label" htmlFor="tr-rp-cur">{t("Currency")}</label>
              <select className="form-select" id="tr-rp-cur" onChange={(event) => setCurrency(event.target.value as typeof currency)} value={currency}>
                <option value="">{t("EUR and CHF")}</option>
                <option value="EUR">EUR</option>
                <option value="CHF">CHF</option>
              </select>
            </div>
            <div>
              <label className="form-label" htmlFor="tr-rp-format">{t("Format")}</label>
              <select className="form-select" id="tr-rp-format" onChange={(event) => setFormat(event.target.value as typeof format)} value={format}>
                <option value="pdf">{t("PDF")}</option>
                <option value="csv">{t("CSV (Excel)")}</option>
              </select>
            </div>
          </div>
          <div className="tr-form-note"><NiIcon name="info" /><span>{t("EUR and CHF are reported separately.")}</span></div>
          {kind === "tax" ? (
            <div className="tr-form-note"><NiIcon name="info" /><span>{t("The tax report is information for your tax return. It is not an official tax certificate.")}</span></div>
          ) : null}
          <p className="tr-form-error" hidden={!error} id="wl-report-error" role="alert">{error}</p>
        </div>
        <footer className="tr-form-footer">
          <button className="btn btn-outline-light" disabled={busy} onClick={onClose} type="button">{t("Cancel")}</button>
          <button className="btn btn-primary" disabled={busy} type="submit">
            {busy ? t("Creating report...") : t("Create report")} <NiIcon name="arrow-right" />
          </button>
        </footer>
      </form>
    </WalletDialog>
  );
}

function AnnualSummary({ year }: { year: string }) {
  const t = useT();
  const summary = useReportSummaryData(year).data;
  const label = year === "all" ? t("all time") : year === platformTodayKey().slice(0, 4) ? t("in {year} so far", { year }) : t("in {year}", { year });
  return (
    <div className="tr-summary-grid">
      {(summary?.currencies ?? []).map((item) => (
        <section key={item.currency}>
          <h3>{item.currency} <span>{label}</span></h3>
          <dl>
            <div><dt>{t("Invested")}</dt><dd>{formatMoneyMinor(item.invested_minor, item.currency)}</dd></div>
            <div><dt>{t("Principal repaid")}</dt><dd>{formatMoneyMinor(item.principal_repaid_minor, item.currency)}</dd></div>
            <div><dt>{t("Interest received")}</dt><dd>{formatMoneyMinor(item.interest_received_minor, item.currency)}</dd></div>
          </dl>
        </section>
      ))}
    </div>
  );
}

/** The period a report covers (kept report: its dates; offered document: its period or its date). */
function rowPeriod(row: Row) {
  if (row.source === "kept") return { from: row.report.start_date, to: row.report.end_date };
  const date = zurichDateKey(row.document.date);
  return { from: row.document.period_start ?? date, to: row.document.period_end ?? date };
}

function overlaps(period: { from: string; to: string }, range: { from: string; to: string }) {
  return (!range.to || period.from <= range.to) && (!range.from || period.to >= range.from);
}

export function ReportsScreen() {
  const t = useT();
  const queryClient = useQueryClient();
  const documentsQuery = useDocumentsData();
  const reportsQuery = useInvestorReportsData();
  const thisYear = platformTodayKey().slice(0, 4);
  // Design #/reports Period: All time, last 30/90 days, a year, custom dates (as on Transactions).
  const [choice, setChoice] = useState<PeriodChoice>(`y${Number(thisYear)}`);
  const [custom, setCustom] = useState({ from: "", to: "" });
  const [draft, setDraft] = useState({ from: "", to: "" });
  const [rangeError, setRangeError] = useState(false);
  const period = choiceToPeriod(choice, custom);
  const range = periodRange(period, platformTodayKey());
  // The server summary is per calendar year or all time; rolling and custom periods have none.
  const summaryYear = period.kind === "year" ? String(period.year) : period.kind === "all" ? "all" : null;
  const [type, setType] = useState<"" | ReportFilter>("");
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [reader, setReader] = useState<Reader | null>(null);
  const [toast, setToast] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [error, setError] = useState("");
  const { download, busyKey: documentBusy, error: documentError } = useDocumentDownload();
  const clearToast = useCallback(() => setToast(""), []);
  const documents = documentsQuery.data;
  const kept = reportsQuery.data?.reports;

  const rows: Row[] = [
    ...(kept ?? []).map((report): Row => ({ key: `kept:${report.id}`, filter: reportFilterOf(report.kind), years: keptYears(report), sortKey: report.issued_at, source: "kept", report })),
    ...(documents?.documents ?? []).filter(isReport).sort(newestFirst).map((document): Row => ({
      key: `offered:${document.id}`,
      filter: reportFilterOf(document.document_kind),
      years: documentYears(document),
      sortKey: document.period_end ?? zurichDateKey(document.date),
      source: "offered",
      document
    }))
  ];
  const years = [...new Set([Number(thisYear), ...rows.flatMap((row) => row.years)])].sort((a, b) => b - a).slice(0, 3);
  // "Shows reports covering any of your selected dates": a report matches when its period overlaps.
  const visible = rows
    .filter((row) => (!type || row.filter === type) && overlaps(rowPeriod(row), range))
    .sort((a, b) => b.sortKey.localeCompare(a.sortKey));
  const applyRange = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.from || !draft.to || draft.from > draft.to) {
      setRangeError(true);
      return;
    }
    setRangeError(false);
    setCustom(draft);
  };

  const openKept = (report: InvestorReport) => {
    if (report.output_format !== "pdf") {
      setBusyKey(report.id);
      setError("");
      v1InvestorPortalReportsDownloadRetrieve(report.id)
        .then(downloadPortalArtifact)
        .catch((failure) => setError(errorMessage(failure)))
        .finally(() => setBusyKey(""));
      return;
    }
    setReader({
      title: report.title,
      load: async () => {
        const artifact = await v1InvestorPortalReportsDownloadRetrieve(report.id);
        return { data: bytesOfArtifact(artifact), filename: artifact.filename };
      }
    });
  };
  const viewOffered = (document: InvestorDocument) => {
    const title = `${t(reportTitle(document))} · ${periodLabel(document)}`;
    setReader({
      title,
      load: async () => {
        const artifact = await v1InvestorPortalDocumentsDownloadCreate(documentDownloadRequest(document, "pdf"));
        return { data: bytesOfArtifact(artifact), filename: artifact.filename };
      }
    });
  };
  const loaded = Boolean(documents && kept);
  const failed = documentsQuery.isError || reportsQuery.isError;
  const message = error || documentError;

  return (
    <main className="tr-page tr-reports-page rr-page r31m-reports">
      <PageHead
        actions={<button className="btn btn-primary" onClick={() => setCreating(true)} type="button"><NiIcon name="plus" /><span>{t("Create report")}</span></button>}
        subtitle={t("Statements and reports for your records and your tax return.")}
        title={t("Reports")}
      />
      {!loaded ? (
        failed ? (
          <EmptyState
            actions={<button className="btn btn-outline-light" onClick={() => { void documentsQuery.refetch(); void reportsQuery.refetch(); }} type="button">{t("Try again")}</button>}
            icon="alert-circle"
            title={t("We could not load your reports")}
          >
            {t("The list of statements is not available right now. Try again in a moment.")}
          </EmptyState>
        ) : (
          <div className="bxm-empty" role="status"><NiIcon name="loader" /><p>{t("Loading reports...")}</p></div>
        )
      ) : (
        <>
          <div className="tr-toolbar tr-reports-toolbar">
            <div className="r30-period-control">
              <label htmlFor="rr-period">{t("Period")}</label>
              <details className="r31m-period-help">
                <summary aria-label={t("How the period filter works")}><NiIcon name="info" /></summary>
                <div>{t("Shows reports covering any of your selected dates. Each statement keeps its full original period.")}</div>
              </details>
              <select
                className="form-select tr-period"
                id="rr-period"
                onChange={(event) => {
                  setChoice(event.target.value as PeriodChoice);
                  setRangeError(false);
                }}
                value={choice}
              >
                <option value="all">{t("All time")}</option>
                <option value="30">{t("Last 30 days")}</option>
                <option value="90">{t("Last 90 days")}</option>
                {years.map((value) => <option key={value} value={`y${value}`}>{value}</option>)}
                <option value="custom">{t("Custom dates")}</option>
              </select>
            </div>
            <select aria-label={t("Report type")} className="form-select tr-type" id="tr-report-type" onChange={(event) => setType(event.target.value as typeof type)} value={type}>
              <option value="">{t("All report types")}</option>
              {REPORT_TYPES.map((item) => <option key={item.value} value={item.value}>{t(item.label)}</option>)}
            </select>
            {summaryYear ? (
              <button aria-controls="tr-annual-summary" aria-expanded={summaryOpen} className="tr-link" onClick={() => setSummaryOpen((open) => !open)} type="button">
                {t("Summary")} <NiIcon name="chevron-down" />
              </button>
            ) : null}
          </div>
          {choice === "custom" ? (
            <form className="r30-date-range" noValidate onSubmit={applyRange}>
              <div className="r30-date-field">
                <label htmlFor="rr-from">{t("From")}</label>
                <input aria-describedby="rr-date-error" aria-invalid={rangeError} className="form-control" id="rr-from" onChange={(event) => setDraft({ ...draft, from: event.target.value })} required type="date" value={draft.from} />
              </div>
              <div className="r30-date-field">
                <label htmlFor="rr-to">{t("date|To")}</label>
                <input aria-describedby="rr-date-error" aria-invalid={rangeError} className="form-control" id="rr-to" onChange={(event) => setDraft({ ...draft, to: event.target.value })} required type="date" value={draft.to} />
              </div>
              <button className="btn btn-outline-light" type="submit">{t("Apply")}</button>
              <p className="r30-range-error" hidden={!rangeError} id="rr-date-error" role="alert">{t("Choose a start and end date. From must be on or before To.")}</p>
            </form>
          ) : null}
          <div className="tr-summary" hidden={!summaryOpen || !summaryYear} id="tr-annual-summary">
            {summaryOpen && summaryYear ? <AnnualSummary year={summaryYear} /> : null}
          </div>
          {message ? (
            <div className="alert alert-danger alert-icon wl-alert" role="alert">
              <NiIcon name="alert-circle" />
              <strong className="bxm-signal-text">{t("The report could not be opened.")}</strong> {message}
            </div>
          ) : null}
          <div className="tr-meta">
            <span><strong>{visible.length === 1 ? t("1 report") : t("{count} reports", { count: visible.length })}</strong></span>
          </div>
          {visible.length === 0 ? (
            <div className="bxm-empty"><NiIcon name="file-text" /><p>{rows.length === 0 ? t("No reports yet.") : t("No reports for these filters.")}</p></div>
          ) : (
            <table className="tr-table tr-reports-table mobile-records" data-mobile-table="true">
              <colgroup><col style={{ width: "44%" }} /><col style={{ width: "26%" }} /><col style={{ width: "15%" }} /><col style={{ width: "15%" }} /></colgroup>
              <thead><tr><th>{t("Report")}</th><th>{t("Period")}</th><th>{t("Issued")}</th><th><span className="visually-hidden">{t("Action")}</span></th></tr></thead>
              <tbody>
                {visible.map((row) => {
                  if (row.source === "kept") {
                    const report = row.report;
                    const csv = report.output_format !== "pdf";
                    const period = t(keptPeriodLabel(report));
                    const note = [t(KEPT_NOTES[report.kind] ?? ""), report.currency || t("EUR and CHF"), csv ? "CSV" : "PDF"].filter(Boolean).join(" · ");
                    return (
                      <tr key={row.key}>
                        <td data-mobile-label={t("Report")}>
                          <div className="tr-item">
                            <span className="tr-icon tr-document"><NiIcon name={csv ? "file-text" : "file-pdf"} /></span>
                            <div><strong>{t(report.title)}</strong><small>{note}</small></div>
                          </div>
                        </td>
                        <td data-mobile-label={t("Period")}>{period}</td>
                        <td data-mobile-label={t("Issued")}>{formatDate(report.issued_at)}</td>
                        <td className="tr-right" data-mobile-label={t("Action")}>
                          <button aria-label={t(csv ? "Download {title} · {period}" : "View {title} · {period}", { title: t(report.title), period })} className="tr-link" disabled={busyKey === report.id} onClick={() => openKept(report)} type="button">
                            {csv ? (busyKey === report.id ? t("Preparing...") : t("Download")) : t("action|View")} <NiIcon name={csv ? "download" : "arrow-right"} />
                          </button>
                        </td>
                      </tr>
                    );
                  }
                  const document = row.document;
                  const title = t(reportTitle(document));
                  const period = periodLabel(document);
                  return (
                    <tr key={row.key}>
                      <td data-mobile-label={t("Report")}>
                        <div className="tr-item">
                          <span className="tr-icon tr-document"><NiIcon name="file-pdf" /></span>
                          <div><strong>{title}</strong><small>{t(reportSubtitle(document))}</small></div>
                        </div>
                      </td>
                      <td data-mobile-label={t("Period")}>{period}</td>
                      <td data-mobile-label={t("Issued")}>{document.generated_on_request ? t("On request") : null}</td>
                      <td className="tr-right" data-mobile-label={t("Action")}>
                        <span className="wl-report-actions">
                          <button aria-label={t("View {title} · {period}", { title, period })} className="tr-link" onClick={() => viewOffered(document)} type="button">
                            {t("action|View")} <NiIcon name="arrow-right" />
                          </button>
                          {document.output_formats.includes("csv") ? (
                            <button
                              aria-label={t("Download {title} {period} as {format}", { title, period, format: "CSV" })}
                              className="tr-link"
                              disabled={Boolean(documentBusy)}
                              onClick={() => void download(documentDownloadRequest(document, "csv"), `${document.id}:csv`)}
                              type="button"
                            >
                              {documentBusy === `${document.id}:csv` ? t("Preparing...") : "CSV"} <NiIcon name="download" />
                            </button>
                          ) : null}
                          {/* D-11: the evidence package (PDF, CSV and checksums) stays available. */}
                          {document.output_formats.includes("zip") ? (
                            <button
                              aria-label={t("Download {title} {period} as {format}", { title, period, format: "ZIP" })}
                              className="tr-link"
                              disabled={Boolean(documentBusy)}
                              onClick={() => void download(documentDownloadRequest(document, "zip"), `${document.id}:zip`)}
                              title={t("ZIP (PDF, CSV and checksums)")}
                              type="button"
                            >
                              {documentBusy === `${document.id}:zip` ? t("Preparing...") : "ZIP"} <NiIcon name="download" />
                            </button>
                          ) : null}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {documents?.disclaimer ? <p className="wl-list-note">{documents.disclaimer}</p> : null}
        </>
      )}
      {creating ? (
        <CreateReportDialog
          onClose={() => setCreating(false)}
          onCreated={(report) => {
            setCreating(false);
            setToast(t("Document ready: {title}", { title: t(report.title) }));
            void queryClient.invalidateQueries({ queryKey: getV1InvestorPortalReportsRetrieveQueryKey() });
          }}
        />
      ) : null}
      {reader ? <PdfReader load={reader.load} onClose={() => setReader(null)} title={reader.title} /> : null}
      {toast ? <Toast icon="file-pdf" message={toast} onDone={clearToast} /> : null}
    </main>
  );
}
