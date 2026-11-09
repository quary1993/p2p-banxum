// IP of Webby-Soft SRL.
/*
 * Reports (design #/reports: main.tr-page.tr-reports-page.rr-page): the account statements and the
 * annual tax information the platform offers (GET /investor/portal/documents/), filtered by year and
 * type, each generated on request as PDF or CSV. Create report asks for the outputs the platform
 * generates today: an account statement for any period up to today, or the tax information of a
 * finished year, as PDF, CSV or ZIP. The design's portfolio, interest-and-repayments and per-country
 * tax reports, the monthly automatic statements and the Summary need backend work (TODO).
 */
import { useCallback, useId, useState, type FormEvent } from "react";

import type { InvestorDocument } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useDocumentsData } from "../../../investorPortal/data";
import { platformTodayKey } from "../../../investorPortal/platformClock";
import { EmptyState, NiIcon, PageHead } from "../../components";
import { documentYears, isReport, newestFirst, periodLabel, reportSubtitle, reportTitle } from "./documentsModel";
import { periodRange, type Period } from "./transactionsModel";
import { zurichDateKey } from "../../../investorPortal/format";
import { documentDownloadRequest, reportDownloadRequest, useDocumentDownload, type OutputFormat } from "./parts/downloads";
import { Toast } from "./parts/Toast";
import { WalletDialog } from "./parts/WalletDialog";
import "./wallet.css";

type ReportType = "statement" | "tax";

function CreateReportDialog({
  taxYears,
  onClose,
  onCreated
}: {
  taxYears: number[];
  onClose: () => void;
  onCreated: (filename: string) => void;
}) {
  const t = useT();
  const titleId = useId();
  const today = platformTodayKey();
  const [type, setType] = useState<ReportType>("statement");
  const [from, setFrom] = useState(`${today.slice(0, 4)}-01-01`);
  const [to, setTo] = useState(today);
  const [year, setYear] = useState(taxYears[0] ?? 0);
  const [format, setFormat] = useState<OutputFormat>("pdf");
  const [error, setError] = useState("");
  const { download, busyKey, error: downloadError } = useDocumentDownload();
  const busy = Boolean(busyKey);
  const message = error || downloadError;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (type === "statement") {
      if (!from || !to || from > to) {
        setError(t("Choose a valid start and end date. The start must not be after the end."));
        return;
      }
      if (to > today) {
        setError(t("An account statement can end today at the latest."));
        return;
      }
    } else if (!year) {
      setError(t("Tax information is available once a calendar year has ended."));
      return;
    }
    const request = type === "statement" ? reportDownloadRequest({ kind: "statement", from, to }, format) : reportDownloadRequest({ kind: "tax", year }, format);
    const artifact = await download(request, "create");
    if (artifact) onCreated(artifact.filename);
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
              <label className="tr-report-option">
                <input checked={type === "statement"} name="type" onChange={() => setType("statement")} type="radio" value="statement" />
                <span>
                  <strong>{t("Account statement")}</strong>
                  <small>{t("Banxum account transactions and repayments credited to it.")}</small>
                </span>
              </label>
              <label className="tr-report-option">
                <input checked={type === "tax"} disabled={taxYears.length === 0} name="type" onChange={() => setType("tax")} type="radio" value="tax" />
                <span>
                  <strong>{t("Tax information")}</strong>
                  <small>
                    {taxYears.length > 0
                      ? t("Interest and other income of a finished calendar year, for your tax return.")
                      : t("Available once your first calendar year with Banxum has ended.")}
                  </small>
                </span>
              </label>
            </div>
          </fieldset>
          {type === "statement" ? (
            <div>
              <div className="tr-form-row">
                <div>
                  <label className="form-label" htmlFor="wl-report-from">{t("From")}</label>
                  <input aria-describedby="rr-period-note wl-report-error" className="form-control" id="wl-report-from" max={today} onChange={(event) => setFrom(event.target.value)} required type="date" value={from} />
                </div>
                <div>
                  <label className="form-label" htmlFor="wl-report-to">{t("To")}</label>
                  <input aria-describedby="rr-period-note wl-report-error" className="form-control" id="wl-report-to" max={today} onChange={(event) => setTo(event.target.value)} required type="date" value={to} />
                </div>
              </div>
              <p className="rr-period-note" id="rr-period-note">{t("Both dates are included.")}</p>
            </div>
          ) : (
            <div className="tr-form-row">
              <div>
                <label className="form-label" htmlFor="wl-report-year">{t("Year")}</label>
                <select className="form-select" id="wl-report-year" onChange={(event) => setYear(Number(event.target.value))} value={year}>
                  {taxYears.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </div>
              <div />
            </div>
          )}
          <div className="tr-form-row">
            <div>
              <label className="form-label" htmlFor="wl-report-format">{t("Format")}</label>
              <select className="form-select" id="wl-report-format" onChange={(event) => setFormat(event.target.value as OutputFormat)} value={format}>
                <option value="pdf">{t("PDF")}</option>
                <option value="csv">{t("CSV (Excel)")}</option>
                <option value="zip">{t("ZIP (PDF, CSV and checksums)")}</option>
              </select>
            </div>
            <div />
          </div>
          <div className="tr-form-note"><NiIcon name="info" /><span>{t("EUR and CHF are reported separately.")}</span></div>
          <p className="tr-form-error" hidden={!message} id="wl-report-error" role="alert">{message}</p>
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

function ReportRow({ document, busyKey, onDownload }: { document: InvestorDocument; busyKey: string; onDownload: (document: InvestorDocument, format: OutputFormat) => void }) {
  const t = useT();
  const title = t(reportTitle(document));
  const period = periodLabel(document);
  const formats = (["pdf", "csv"] as const).filter((format) => document.output_formats.includes(format));
  return (
    <tr>
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
          {formats.map((format) => {
            const key = `${document.id}:${format}`;
            return (
              <button
                aria-label={t("Download {title} {period} as {format}", { title, period, format: format.toUpperCase() })}
                className="tr-link"
                disabled={Boolean(busyKey)}
                key={format}
                onClick={() => onDownload(document, format)}
                type="button"
              >
                {/* The design's "View" opens the PDF; the CSV of the same statement stays available. */}
                {busyKey === key ? t("Preparing...") : format === "pdf" ? t("View") : format.toUpperCase()} <NiIcon name="download" />
              </button>
            );
          })}
        </span>
      </td>
    </tr>
  );
}

type PeriodChoice = "all" | "30" | "90" | "custom" | `y${number}`;

function choiceToPeriod(choice: PeriodChoice, custom: { from: string; to: string }): Period {
  if (choice === "30" || choice === "90") return { kind: "days", days: Number(choice) };
  if (choice === "custom") return custom.from && custom.to ? { kind: "custom", ...custom } : { kind: "all" };
  if (choice.startsWith("y")) return { kind: "year", year: Number(choice.slice(1)) };
  return { kind: "all" };
}

/** A report matches when its period overlaps the selected dates (the design's period help). */
function overlaps(document: InvestorDocument, range: { from: string; to: string }) {
  if (!range.from && !range.to) return true;
  const start = document.period_start ?? zurichDateKey(document.date);
  const end = document.period_end ?? zurichDateKey(document.date);
  return (!range.to || start <= range.to) && (!range.from || end >= range.from);
}

export function ReportsScreen() {
  const t = useT();
  const documentsQuery = useDocumentsData();
  const [choice, setChoice] = useState<PeriodChoice>("all");
  const [custom, setCustom] = useState({ from: "", to: "" });
  const [type, setType] = useState<"" | "account_statement" | "annual_tax_information">("");
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState("");
  const { download, busyKey, error } = useDocumentDownload();
  const clearToast = useCallback(() => setToast(""), []);
  const documents = documentsQuery.data;
  const reports = (documents?.documents ?? []).filter(isReport).sort(newestFirst);
  const years = [...new Set(reports.flatMap(documentYears))].sort((a, b) => b - a);
  const taxYears = reports.filter((document) => document.document_kind === "annual_tax_information").map((document) => Number((document.period_start ?? "").slice(0, 4))).filter(Boolean).sort((a, b) => b - a);
  const range = periodRange(choiceToPeriod(choice, custom), platformTodayKey());
  const rows = reports.filter((document) => (!type || document.document_kind === type) && overlaps(document, range));
  const onDownload = (document: InvestorDocument, format: OutputFormat) => void download(documentDownloadRequest(document, format), `${document.id}:${format}`);

  return (
    <main className="tr-page tr-reports-page rr-page r31m-reports">
      <PageHead
        actions={
          <button className="btn btn-primary" onClick={() => setCreating(true)} type="button"><NiIcon name="plus" /><span>{t("Create report")}</span></button>
        }
        subtitle={t("Statements and reports for your records and your tax return.")}
        title={t("Reports")}
      />
      {!documents ? (
        documentsQuery.isError ? (
          <EmptyState
            actions={<button className="btn btn-outline-light" onClick={() => void documentsQuery.refetch()} type="button">{t("Try again")}</button>}
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
              <select className="form-select tr-period" id="rr-period" onChange={(event) => setChoice(event.target.value as PeriodChoice)} value={choice}>
                <option value="all">{t("All time")}</option>
                <option value="30">{t("Last 30 days")}</option>
                <option value="90">{t("Last 90 days")}</option>
                {years.map((item) => <option key={item} value={`y${item}`}>{item}</option>)}
                <option value="custom">{t("Custom dates")}</option>
              </select>
            </div>
            <select aria-label={t("Report type")} className="form-select tr-type" onChange={(event) => setType(event.target.value as typeof type)} value={type}>
              <option value="">{t("All report types")}</option>
              <option value="account_statement">{t("Account statement")}</option>
              <option value="annual_tax_information">{t("Tax information")}</option>
            </select>
          </div>
          {choice === "custom" ? (
            <div className="r30-date-range">
              <div className="r30-date-field">
                <label htmlFor="rr-from">{t("From")}</label>
                <input className="form-control" id="rr-from" onChange={(event) => setCustom({ ...custom, from: event.target.value })} type="date" value={custom.from} />
              </div>
              <div className="r30-date-field">
                <label htmlFor="rr-to">{t("To")}</label>
                <input className="form-control" id="rr-to" onChange={(event) => setCustom({ ...custom, to: event.target.value })} type="date" value={custom.to} />
              </div>
            </div>
          ) : null}
          {error ? (
            <div className="alert alert-danger alert-icon wl-alert" role="alert">
              <NiIcon name="alert-circle" />
              <strong className="bxm-signal-text">{t("The report could not be created.")}</strong> {error}
            </div>
          ) : null}
          <div className="tr-meta"><span><strong>{rows.length === 1 ? t("1 report") : t("{count} reports", { count: rows.length })}</strong></span></div>
          {rows.length === 0 ? (
            <div className="bxm-empty"><NiIcon name="file-text" /><p>{reports.length === 0 ? t("No reports yet.") : t("No reports for these filters.")}</p></div>
          ) : (
            <table className="tr-table tr-reports-table mobile-records" data-mobile-table="true">
              <colgroup><col style={{ width: "39%" }} /><col style={{ width: "31%" }} /><col style={{ width: "15%" }} /><col style={{ width: "15%" }} /></colgroup>
              <thead><tr><th>{t("Report")}</th><th>{t("Period")}</th><th>{t("Issued")}</th><th><span className="visually-hidden">{t("Action")}</span></th></tr></thead>
              <tbody>
                {rows.map((document) => <ReportRow busyKey={busyKey} document={document} key={document.id} onDownload={onDownload} />)}
              </tbody>
            </table>
          )}
          {documents.disclaimer ? <p className="wl-list-note">{documents.disclaimer}</p> : null}
        </>
      )}
      {creating ? (
        <CreateReportDialog
          onClose={() => setCreating(false)}
          onCreated={(filename) => {
            setCreating(false);
            setToast(t("Report ready: {filename}", { filename }));
          }}
          taxYears={taxYears}
        />
      ) : null}
      {toast ? <Toast icon="file-pdf" message={toast} onDone={clearToast} /> : null}
    </main>
  );
}
