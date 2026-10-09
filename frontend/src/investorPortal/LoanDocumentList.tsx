import { useState } from "react";

import { ApiClientError } from "../api/client/httpClient";
import { v1MarketplacePrimaryLoansDocumentsRetrieve } from "../api/generated/banxumApi";
import { Button, Icon } from "./ui";

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

function errorText(error: unknown) {
  if (error instanceof ApiClientError && error.message) return error.message;
  return "The document could not be downloaded. Try again later.";
}

/** Borrower documents of a loan page. Each one opens as a file download. */
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
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const download = async (documentId: string) => {
    setError("");
    setBusyId(documentId);
    try {
      saveDownloadedFile(await v1MarketplacePrimaryLoansDocumentsRetrieve(loanId, documentId));
    } catch (downloadError) {
      setError(errorText(downloadError));
    } finally {
      setBusyId("");
    }
  };
  return (
    <>
      <ul className="lp-docs">
        {documents.map((document, index) => {
          const name = document.display_name || "Borrower document";
          return (
            <li className="lp-doc" key={document.id ?? index}>
              <Icon className="lp-doc-icon" name="doc" size={16} />
              <div className="lp-doc-main">
                <div className="lp-doc-name">
                  <strong>{name}</strong>
                  {document.document_type ? <span className="tag">{humanize(document.document_type)}</span> : null}
                </div>
                {document.description ? <div className="lp-doc-desc">{document.description}</div> : null}
              </div>
              {document.id ? (
                <Button
                  aria-label={`Download ${name}`}
                  disabled={disabled || busyId !== ""}
                  icon="download"
                  onClick={() => void download(document.id as string)}
                  size="sm"
                >
                  {busyId === document.id ? "Downloading..." : "Download"}
                </Button>
              ) : null}
            </li>
          );
        })}
      </ul>
      {error ? (
        <p className="lp-doc-error" role="alert">
          {error}
        </p>
      ) : null}
    </>
  );
}
