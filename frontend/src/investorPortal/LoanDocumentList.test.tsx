// FRONTCODE-27: borrower documents on a loan page were listed with only "Copy document ID".
// Each listed document must download through the investor document endpoint.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import { LoanDocumentList } from "./LoanDocumentList";

const loanId = "11111111-1111-4111-8111-111111111111";
const documentId = "22222222-2222-4222-8222-222222222222";
const documents = [
  { id: documentId, display_name: "Financials 2025", document_type: "financials", description: "Audited accounts." }
];

afterEach(() => {
  vi.restoreAllMocks();
});

test("a listed borrower document downloads its file", async () => {
  const requests: string[] = [];
  server.use(
    http.get("*/api/v1/marketplace/primary/loans/:loanId/documents/:documentId/", ({ params }) => {
      requests.push(`${String(params.loanId)}/${String(params.documentId)}`);
      return HttpResponse.json({
        document_id: documentId,
        display_name: "Financials 2025",
        filename: "financials-2025.pdf",
        content_type: "application/pdf",
        content_encoding: "base64",
        content: window.btoa("%PDF-1.4 test"),
        content_sha256: "abc"
      });
    })
  );
  const createObjectURL = vi.fn(() => "blob:financials");
  const revokeObjectURL = vi.fn();
  Object.assign(window.URL, { createObjectURL, revokeObjectURL });
  const clicks: string[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    clicks.push(this.download);
  });

  render(<LoanDocumentList documents={documents} humanize={(token) => token} loanId={loanId} />);
  expect(screen.queryByRole("button", { name: /Copy document ID/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Download Financials 2025" }));

  await waitFor(() => expect(clicks).toEqual(["financials-2025.pdf"]));
  expect(requests).toEqual([`${loanId}/${documentId}`]);
  expect(createObjectURL).toHaveBeenCalledTimes(1);
});

test("a refused download shows the reason", async () => {
  server.use(
    http.get("*/api/v1/marketplace/primary/loans/:loanId/documents/:documentId/", () =>
      HttpResponse.json({ detail: "Document not found." }, { status: 400 })
    )
  );

  render(<LoanDocumentList documents={documents} humanize={(token) => token} loanId={loanId} />);
  fireEvent.click(screen.getByRole("button", { name: "Download Financials 2025" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Document not found.");
});
