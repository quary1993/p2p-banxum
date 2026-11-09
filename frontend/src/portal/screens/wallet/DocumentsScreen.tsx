// IP of Webby-Soft SRL.
/*
 * Documents (design #/documents: main.tr-page.dp-page): the investor's own documents in three tabs:
 * investment documents (the investment and resale agreements accepted with the email code + PIN),
 * statements and tax information (generated on request, also under Reports) and platform documents
 * (accepted terms and risk disclosures). Search, type and year filters, download as PDF or CSV.
 * U33-DEC-13: an acceptance is not a signature; there are no "Signed by Banxum" (QES) assignment
 * declarations yet (TODO, Phase 17.6).
 */
import { useState } from "react";

import type { InvestorDocument } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useDocumentsData } from "../../../investorPortal/data";
import { formatDate } from "../../../investorPortal/format";
import { ButtonLink, EmptyState, NiIcon, PageHead, Tabs } from "../../components";
import { documentTab, documentYears, newestFirst, periodLabel, reportSubtitle, reportTitle, type DocumentTab } from "./documentsModel";
import { documentDownloadRequest, useDocumentDownload, type OutputFormat } from "./parts/downloads";
import "./wallet.css";

function versionLabel(version: string) {
  if (/^v?\d+(\.\d+)*$/.test(version)) return version.replace(/^v/, "");
  const suffix = version.match(/-v(\d+)$/);
  return suffix ? suffix[1] : "";
}

function DownloadButtons({
  document,
  title,
  busyKey,
  onDownload
}: {
  document: InvestorDocument;
  title: string;
  busyKey: string;
  onDownload: (document: InvestorDocument, format: OutputFormat) => void;
}) {
  const t = useT();
  const pdfKey = `${document.id}:pdf`;
  return (
    <div className="dp-actions">
      <button
        aria-label={t("Download {title} as PDF", { title })}
        className="dp-download"
        disabled={Boolean(busyKey)}
        onClick={() => onDownload(document, "pdf")}
        title={t("Download PDF")}
        type="button"
      >
        <NiIcon name="download" />
        <span>{busyKey === pdfKey ? t("Preparing...") : t("Download")}</span>
      </button>
      {document.output_formats.includes("csv") ? (
        <button
          aria-label={t("Download {title} as CSV", { title })}
          className="dp-download wl-download-csv"
          disabled={Boolean(busyKey)}
          onClick={() => onDownload(document, "csv")}
          title={t("Download CSV")}
          type="button"
        >
          <span>{busyKey === `${document.id}:csv` ? t("Preparing...") : t("CSV")}</span>
        </button>
      ) : null}
    </div>
  );
}

export function DocumentsScreen() {
  const t = useT();
  const documentsQuery = useDocumentsData();
  const [tab, setTab] = useState<DocumentTab>("investment");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [year, setYear] = useState(0);
  const { download, busyKey, error } = useDocumentDownload();
  const documents = documentsQuery.data;
  const all = [...(documents?.documents ?? [])].sort(newestFirst);
  const inTab = all.filter((document) => documentTab(document) === tab);
  const types = [...new Set(inTab.map((document) => document.document_type).filter(Boolean))];
  const years = [...new Set(inTab.flatMap(documentYears))].sort((a, b) => b - a);
  const query = search.trim().toLowerCase();
  const rows = inTab.filter((document) => {
    if (type && document.document_type !== type) return false;
    if (year && !documentYears(document).includes(year)) return false;
    if (!query) return true;
    return [document.title, document.template_title ?? "", document.context_label, document.document_type, document.id].join(" ").toLowerCase().includes(query);
  });
  const filtering = Boolean(query || type || year);
  const onDownload = (document: InvestorDocument, format: OutputFormat) => void download(documentDownloadRequest(document, format), `${document.id}:${format}`);
  const changeTab = (next: DocumentTab) => {
    setTab(next);
    setSearch("");
    setType("");
    setYear(0);
  };
  const tabs = [
    { value: "investment" as const, label: t("Investment documents") },
    { value: "statements" as const, label: t("Statements") },
    { value: "platform" as const, label: t("Platform documents") }
  ];
  const emptyText = filtering
    ? t("No documents match your search or filters.")
    : tab === "investment"
      ? t("Your investment documents will appear here after you confirm an investment.")
      : tab === "statements"
        ? t("Statements and tax information will appear here.")
        : t("No accepted platform documents yet.");
  const metaNote = tab === "platform" ? t("Accepted platform agreements") : t("Most recent first");

  return (
    <main className="tr-page dp-page">
      <PageHead actions={<ButtonLink icon="file-text" to="reports">{t("Reports")}</ButtonLink>} title={t("Documents")} />
      <Tabs items={tabs} label={t("Document categories")} onChange={changeTab} value={tab} variant="dp-tabs" />
      {!documents ? (
        documentsQuery.isError ? (
          <EmptyState
            actions={<button className="btn btn-outline-light" onClick={() => void documentsQuery.refetch()} type="button">{t("Try again")}</button>}
            icon="alert-circle"
            title={t("We could not load your documents")}
          >
            {t("Your documents are not available right now. Try again in a moment.")}
          </EmptyState>
        ) : (
          <div className="bxm-empty" role="status"><NiIcon name="loader" /><p>{t("Loading documents...")}</p></div>
        )
      ) : (
        <>
          {tab === "investment" && inTab.length > 0 ? (
            <div className="tr-toolbar dp-toolbar">
              <div className="rc-search-field">
                <label htmlFor="dp-search" id="rc-document-search-label">{t("Search documents")}</label>
                <div className="tr-search">
                  <NiIcon name="search" />
                  <input aria-labelledby="rc-document-search-label" className="form-control" id="dp-search" onChange={(event) => setSearch(event.target.value)} placeholder={t("Search document, investment or reference")} type="search" value={search} />
                </div>
              </div>
              <select aria-label={t("Document type")} className="form-select dp-type" onChange={(event) => setType(event.target.value)} value={type}>
                <option value="">{t("All document types")}</option>
                {types.map((item) => <option key={item} value={item}>{t(item)}</option>)}
              </select>
              <select aria-label={t("Document year")} className="form-select dp-year" onChange={(event) => setYear(Number(event.target.value))} value={year}>
                <option value={0}>{t("All years")}</option>
                {years.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
          ) : null}
          {error ? (
            <div className="alert alert-danger alert-icon wl-alert" role="alert">
              <NiIcon name="alert-circle" />
              <strong className="bxm-signal-text">{t("The download failed.")}</strong> {error}
            </div>
          ) : null}
          <div className="tr-meta dp-meta">
            <span><strong>{rows.length === 1 ? t("1 document") : t("{count} documents", { count: rows.length })}</strong> · {metaNote}</span>
          </div>
          {rows.length === 0 ? (
            <div className="dp-empty">
              <div className="bxm-empty"><NiIcon name="file-text" /><p>{emptyText}</p></div>
              {filtering ? (
                <button className="btn btn-outline-light" onClick={() => { setSearch(""); setType(""); setYear(0); }} type="button">{t("Clear filters")}</button>
              ) : null}
            </div>
          ) : (
            <table className="tr-table dp-table mobile-records m82-compact-records" data-mobile-table="true">
              <colgroup><col style={{ width: "55%" }} /><col style={{ width: "24%" }} /><col style={{ width: "21%" }} /></colgroup>
              <thead>
                <tr>
                  <th>{tab === "investment" ? t("Document and investment") : t("Document")}</th>
                  <th>{tab === "platform" ? t("Accepted") : t("Date")}</th>
                  <th><span className="visually-hidden">{t("Actions")}</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((document) => {
                  if (tab === "statements") {
                    const title = t(reportTitle(document));
                    const period = periodLabel(document);
                    return (
                      <tr key={document.id}>
                        <td data-mobile-label={t("Document")}>
                          <div className="tr-item">
                            <span className="tr-icon tr-document"><NiIcon name="file-pdf" /></span>
                            <div>
                              <button className="rss-document-title" disabled={Boolean(busyKey)} onClick={() => onDownload(document, "pdf")} type="button">{title}</button>
                              <small className="dp-reference">{[t(reportSubtitle(document)), period].filter(Boolean).join(" · ")}</small>
                            </div>
                          </div>
                        </td>
                        <td className="dp-date" data-mobile-label={t("Date")}><span>{period}</span><small>{t("Generated on request")}</small></td>
                        <td data-mobile-label={t("Actions")}><DownloadButtons busyKey={busyKey} document={document} onDownload={onDownload} title={`${title} ${period}`} /></td>
                      </tr>
                    );
                  }
                  const version = versionLabel(document.version);
                  const accepted = formatDate(document.date);
                  return (
                    <tr key={document.id}>
                      <td data-mobile-label={tab === "investment" ? t("Document and investment") : t("Document")}>
                        <div className="tr-item">
                          <span className="tr-icon tr-document"><NiIcon name={tab === "platform" ? "file-text" : "file-pdf"} /></span>
                          <div>
                            <button className="rss-document-title" disabled={Boolean(busyKey)} onClick={() => onDownload(document, "pdf")} type="button">{document.title}</button>
                            {tab === "investment" ? (
                              <>
                                {document.context_label ? <span className="dp-investment">{document.context_label}</span> : null}
                                <small className="dp-reference">{[t(document.document_type), version ? t("Version {version}", { version }) : ""].filter(Boolean).join(" · ")}</small>
                              </>
                            ) : (
                              <small>{version ? t("Version {version}", { version }) : t(document.document_type)}</small>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="dp-date" data-mobile-label={tab === "platform" ? t("Accepted") : t("Date")}>
                        <span>{accepted}</span>
                        {tab === "investment" ? <small title={t("Accepted on {date} with your email code and PIN", { date: accepted })}>{t("Accepted by you")}</small> : null}
                      </td>
                      <td data-mobile-label={t("Actions")}><DownloadButtons busyKey={busyKey} document={document} onDownload={onDownload} title={document.title} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {tab === "statements" && documents.disclaimer ? <p className="wl-list-note">{documents.disclaimer}</p> : null}
        </>
      )}
    </main>
  );
}
