// IP of Webby-Soft SRL.
// Borrower documents of a loan (U33 credit file, Documents chapter: .r100-file rows). Each one
// downloads through the investor document endpoint (FRONTCODE-27).
import { useState } from "react";

import { ApiClientError } from "../api/client/httpClient";
import { v1MarketplacePrimaryLoansDocumentsRetrieve } from "../api/generated/banxumApi";
import { useT } from "../i18n";

export type LoanDocumentItem = {
  id?: string;
  display_name?: string;
  document_type?: string;
  description?: string;
};

type DownloadableFile = { content: string; content_type: string; content_encoding: string; filename: string };

/** Save a base64 (or text) API file payload as a download in the browser. */
function saveDownloadedFile(file: DownloadableFile) {
  const bytes =
    file.content_encoding === "base64"
      ? Uint8Array.from(window.atob(file.content), (character) => character.charCodeAt(0))
      : new TextEncoder().encode(file.content);
  const url = window.URL.createObjectURL(new Blob([bytes], { type: file.content_type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = file.filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

function errorText(error: unknown, fallback: string) {
  if (error instanceof ApiClientError && error.message) return error.message;
  return fallback;
}

/** Borrower documents of a loan. Each one opens as a file download. */
export function LoanDocumentList({
  loanId,
  documents,
  humanize,
  disabled = false
}: {
  loanId: string;
  documents: LoanDocumentItem[];
  humanize: (token: string) => string;
  disabled?: boolean;
}) {
  const t = useT();
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const download = async (documentId: string) => {
    setError("");
    setBusyId(documentId);
    try {
      saveDownloadedFile(await v1MarketplacePrimaryLoansDocumentsRetrieve(loanId, documentId));
    } catch (downloadError) {
      setError(errorText(downloadError, t("The document could not be downloaded. Try again later.")));
    } finally {
      setBusyId("");
    }
  };
  return (
    <>
      <div className="u33-invest-files">
        {documents.map((document, index) => {
          const name = document.display_name || t("Borrower document");
          const meta = [document.document_type ? humanize(document.document_type) : "", document.description ?? ""].filter(Boolean).join(" · ");
          return (
            <button
              aria-label={t("Download {name}", { name })}
              className="r100-file"
              disabled={!document.id || disabled || busyId !== ""}
              key={document.id ?? index}
              onClick={() => document.id && void download(document.id)}
              type="button"
            >
              <span className="r100-file-icon"><em aria-hidden="true" className="icon ni ni-file-text" /></span>
              <span className="r100-file-name">
                <strong>{name}</strong>
                {meta ? <small>{meta}</small> : null}
              </span>
              <span className="r100-file-action">
                <span>{busyId === document.id ? t("Downloading...") : t("Download")}</span>
                <em aria-hidden="true" className="icon ni ni-download" />
              </span>
            </button>
          );
        })}
      </div>
      {error ? (
        <p className="u33-invest-file-error" role="alert">
          {error}
        </p>
      ) : null}
    </>
  );
}
