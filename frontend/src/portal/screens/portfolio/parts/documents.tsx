// IP of Webby-Soft SRL.
// "Your documents" of an investment: today's acceptance documents (terms accepted for this investment,
// its resale listing or purchase), downloaded through the existing documents endpoint. The QES
// assignment declaration of U33-DEC-13 does not exist yet (Phase 17.6), so it is never listed.
import { useState, type ReactNode } from "react";

import {
  DocumentKindEnum,
  InvestorDocumentDownloadRequestOutputFormatEnum,
  useV1InvestorPortalDocumentsDownloadCreate,
  type InvestorDocument,
  type InvestorDocumentDownloadResponse
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { useDocumentsData } from "../../../../investorPortal/data";
import { formatDate } from "../../../../investorPortal/format";
import { NiIcon } from "../../../components";
import { documentsForInvestment } from "./documentMatch";
import { errorMessage, legalDocumentPath } from "./errors";

function downloadArtifact(artifact: InvestorDocumentDownloadResponse) {
  const bytes =
    artifact.content_encoding === "base64"
      ? Uint8Array.from(window.atob(artifact.content), (character) => character.charCodeAt(0))
      : new TextEncoder().encode(artifact.content);
  const url = window.URL.createObjectURL(new Blob([bytes], { type: artifact.content_type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = artifact.filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/** The design's "Your documents" disclosure (details.r71-documents > .rid-document rows). */
export function InvestmentDocuments({ orderId, holdingId, loanTitle, footer }: { orderId?: string; holdingId?: string; loanTitle: string; footer?: ReactNode }) {
  const t = useT();
  const documentsQuery = useDocumentsData();
  const download = useV1InvestorPortalDocumentsDownloadCreate();
  const [error, setError] = useState("");
  const rows = documentsForInvestment(documentsQuery.data?.documents ?? [], { orderId, holdingId, loanTitle });
  const open = (document: InvestorDocument) => {
    setError("");
    download.mutate(
      {
        data: {
          document_kind: DocumentKindEnum.acceptance_evidence,
          document_id: document.id,
          output_format: InvestorDocumentDownloadRequestOutputFormatEnum.pdf
        }
      },
      { onSuccess: downloadArtifact, onError: (failure) => setError(errorMessage(failure)) }
    );
  };
  return (
    <details className="r71-documents">
      <summary>
        {t("Your documents")}
        <NiIcon name="chevron-down" />
      </summary>
      <div className="r71-document-body">
        {documentsQuery.isError && !documentsQuery.data ? (
          <p className="u33-muted">{t("We could not load your documents.")} <button className="link" onClick={() => void documentsQuery.refetch()} type="button">{t("Retry")}</button></p>
        ) : documentsQuery.data === undefined ? (
          <p className="u33-muted">{t("Loading documents...")}</p>
        ) : rows.length === 0 ? (
          <p className="u33-muted">{t("No documents for this investment yet. Your accepted terms are always in Documents.")}</p>
        ) : (
          rows.map((document) => (
            <div className="rid-document" key={document.id}>
              <div className="rid-document-copy">
                <NiIcon className="me-2" name="file-pdf" />
                {document.template_title || document.title}
                <div className="sub-text">
                  {t("Accepted by you on {date} · Version {version}", { date: formatDate(document.date), version: document.version.replace(/^v/i, "") })}
                </div>
              </div>
              <div className="rid-document-actions">
                <button className="link" disabled={download.isPending} onClick={() => open(document)} type="button">{t("View")}</button>
              </div>
            </div>
          ))
        )}
        {error ? <p className="u33-error" role="alert">{error}</p> : null}
        {footer}
      </div>
    </details>
  );
}

/** A terms document opened in a new tab before confirming (U33-DEC-14: documents open before confirmation). */
export function TermsLink({ category, children }: { category: string; children: ReactNode }) {
  return (
    <a className="link u33-terms-link" href={legalDocumentPath(category)} rel="noopener noreferrer" target="_blank">
      {children}
      <NiIcon name="external" />
    </a>
  );
}
