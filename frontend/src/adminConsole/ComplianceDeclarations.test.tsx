// IP of Webby-Soft SRL.
// Audit step 7: compliance finds an investor without a review (S7-5), opens a manual review and
// sets a re-verification date; the proof panel shows document names and opens a file (S7-8).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import type { SecurityProofStatus } from "../api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let cards: typeof import("./ComplianceDeclarations");
beforeAll(async () => {
  cards = await import("./ComplianceDeclarations");
});

function renderLive(node: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

const INVESTOR_ID = "33333333-3333-4333-8333-333333333333";
const SECURITY_ID = "55555555-5555-4555-8555-555555555555";
const DOC_A = "66666666-6666-4666-8666-666666666666";
const DOC_B = "77777777-7777-4777-8777-777777777777";

test("S7-5: compliance opens any investor's file, a manual review and a re-verification date", async () => {
  const reviews: Array<Record<string, unknown>> = [];
  const dates: Array<Record<string, unknown>> = [];
  server.use(
    http.get("*/api/v1/admin-ops/lookups/investors/", ({ request }) => {
      const q = new URL(request.url).searchParams.get("q") ?? "";
      return HttpResponse.json(q.length >= 2 ? [{ id: INVESTOR_ID, kind: "investor", label: "Ina Investor", meta: "ina@example.test", payload: {} }] : []);
    }),
    http.get(`*/api/v1/kyc/admin/compliance/investors/${INVESTOR_ID}/`, () =>
      HttpResponse.json({ investor_id: INVESTOR_ID, declarations: [], reviews: [], reverifications: [], investment_block: "declaration_missing" })
    ),
    http.post("*/api/v1/kyc/admin/compliance/reviews/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      reviews.push(body);
      return HttpResponse.json({ id: "r1", investor_id: INVESTOR_ID, necessary: true, status: "open" }, { status: 201 });
    }),
    http.post(`*/api/v1/kyc/admin/compliance/investors/${INVESTOR_ID}/reverification/`, async ({ request }) => {
      dates.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({}, { status: 201 });
    })
  );
  renderLive(<cards.InvestorComplianceCard />);
  fireEvent.change(screen.getByRole("textbox", { name: "Find an investor" }), { target: { value: "Ina" } });
  const results = await screen.findByRole("list", { name: "Search results" });
  fireEvent.click(within(results).getByRole("button", { name: "Open file" }));
  expect(await screen.findByText("No declaration")).toBeInTheDocument();

  fireEvent.change(screen.getByRole("textbox", { name: "Reason for the review" }), { target: { value: "Adverse media hit." } });
  fireEvent.click(screen.getByRole("button", { name: "Open the review" }));
  await waitFor(() => expect(reviews).toHaveLength(1));
  expect(reviews[0]).toEqual({ investor_id: INVESTOR_ID, reason: "Adverse media hit.", necessary: true });
  expect(await screen.findByText(/New investments of this investor pause/)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Re-verification date"), { target: { value: "2027-03-01" } });
  fireEvent.click(screen.getByRole("button", { name: "Set the date" }));
  await waitFor(() => expect(dates).toHaveLength(1));
  expect(dates[0]).toMatchObject({ due_date: "2027-03-01" });
});

test("S7-8: the proof panel names the documents, opens one and shows the history", async () => {
  const opened: string[] = [];
  const status: SecurityProofStatus = {
    security_id: SECURITY_ID,
    security_type: "real_estate",
    released: false,
    required_proofs: [
      { key: "land_register_extract", label: "Land register extract" },
      { key: "mortgage_note_or_pledge", label: "Mortgage note or pledge agreement" }
    ],
    configuration_error: "",
    document_ids: [DOC_A, DOC_B],
    documents: [
      { id: DOC_A, title: "Land register extract 2026", document_type: "Other", document_date: "2026-11-02", uploaded_at: "2026-11-03T08:00:00Z", available: true, checked: true, source: "borrower" },
      { id: DOC_B, title: "Mortgage note", document_type: "Other", document_date: null, uploaded_at: "2026-11-03T08:00:00Z", available: true, checked: false, source: "loan" }
    ],
    verified: false,
    verified_by: "",
    verified_at: null,
    proofs: {},
    needs_new_verification: true,
    problem: "an essential detail changed after the verification; verify it again.",
    history: [
      {
        verifier_name: "Vera Verifier",
        verified_at: "2026-11-04T09:00:00Z",
        note: "",
        required_proofs: ["land_register_extract"],
        proofs: [{ key: "land_register_extract", label: "Land register extract", document: { id: DOC_A, title: "Land register extract 2026", document_type: "Other", document_date: "2026-11-02", uploaded_at: null, available: true, checked: true, source: "borrower" } }]
      }
    ]
  };
  server.use(
    http.get("*/api/v1/loans/admin/loans/:loanId/security-proofs/", () => HttpResponse.json([status])),
    http.get("*/api/v1/loans/admin/loans/:loanId/documents/", () => HttpResponse.json([])),
    http.get(`*/api/v1/loans/admin/securities/${SECURITY_ID}/documents/:documentId/`, ({ params }) => {
      opened.push(String(params.documentId));
      return HttpResponse.json({ document_id: DOC_A, display_name: "Land register extract 2026", filename: "extract.pdf", content_type: "application/pdf", content_encoding: "base64", content: "JVBERg==", content_sha256: "x" });
    })
  );
  const openWindow = vi.spyOn(window, "open").mockImplementation(() => null);
  const createUrl = vi.fn(() => "blob:proof");
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createUrl });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });

  renderLive(<cards.SecurityProofsPanel loanId="11111111-1111-4111-8111-111111111111" />);
  const documents = await screen.findByRole("list", { name: "Linked documents" });
  expect(within(documents).getByText(/Land register extract 2026 · Other · 2 Nov 2026/)).toBeInTheDocument();
  expect(within(documents).getByText(`· ID ${DOC_A}`)).toBeInTheDocument();
  expect(screen.getByText(/Why: an essential detail changed/)).toBeInTheDocument();
  const select = screen.getByRole("combobox", { name: "Land register extract" });
  expect(within(select).getByRole("option", { name: /Land register extract 2026/ })).toBeInTheDocument();

  // Re-audit 2: the unchecked file has no "Open" button (the server refuses it).
  expect(within(documents).getAllByRole("button", { name: "Open" })).toHaveLength(1);
  expect(within(documents).getByText(/Mortgage note · Other · .* · waits for its check/)).toBeInTheDocument();
  fireEvent.click(within(documents).getByRole("button", { name: "Open" }));
  await waitFor(() => expect(openWindow).toHaveBeenCalledWith("blob:proof", "_blank", "noopener"));
  expect(opened).toEqual([DOC_A]);
  expect(screen.getByText("Verification history (1)")).toBeInTheDocument();
  openWindow.mockRestore();
});

const SHA = "a".repeat(64);

test("re-audit: a proof file is uploaded to the loan, then its check is confirmed", async () => {
  const uploads: FormData[] = [];
  const checks: Array<Record<string, unknown>> = [];
  let checked = false;
  const document = () => ({
    id: DOC_A,
    display_name: "Assignment agreement 2026",
    document_type: "pledge_or_assignment_agreement",
    document_type_label: "Pledge or assignment agreement",
    document_date: null,
    uploaded_at: "2026-11-20T08:00:00Z",
    checked,
    checked_at: checked ? "2026-11-20T09:00:00Z" : null,
    check_note: checked ? "Scanned." : "",
    size_bytes: 1200,
    checksum_sha256: SHA
  });
  server.use(
    http.get("*/api/v1/loans/admin/loans/:loanId/security-proofs/", () => HttpResponse.json([])),
    http.get("*/api/v1/loans/admin/loans/:loanId/documents/", () => HttpResponse.json(uploads.length ? [document()] : [])),
    http.post("*/api/v1/loans/admin/loans/:loanId/documents/", async ({ request }) => {
      uploads.push(await request.formData());
      return HttpResponse.json(document(), { status: 201 });
    }),
    http.post(`*/api/v1/loans/admin/loan-documents/${DOC_A}/check/`, async ({ request }) => {
      checks.push((await request.json()) as Record<string, unknown>);
      checked = true;
      return HttpResponse.json(document());
    })
  );
  renderLive(<cards.SecurityProofsPanel loanId="11111111-1111-4111-8111-111111111111" />);
  const form = await screen.findByRole("form", { name: "Upload a loan document" });
  const file = new File(["%PDF-1.4 x"], "assignment.pdf", { type: "application/pdf" });
  fireEvent.change(within(form).getByLabelText("File"), { target: { files: [file] } });
  fireEvent.change(within(form).getByRole("textbox", { name: "Document name" }), { target: { value: "Assignment agreement 2026" } });
  fireEvent.change(within(form).getByRole("combobox", { name: "Document type" }), { target: { value: "pledge_or_assignment_agreement" } });
  fireEvent.click(within(form).getByRole("button", { name: "Upload" }));
  await waitFor(() => expect(uploads).toHaveLength(1));
  expect(uploads[0].get("display_name")).toBe("Assignment agreement 2026");
  expect(uploads[0].get("document_type")).toBe("pledge_or_assignment_agreement");
  expect(uploads[0].get("file")).toMatchObject({ type: "application/pdf", size: 10 });

  const list = await screen.findByRole("list", { name: "Loan documents" });
  const confirm = within(list).getByRole("button", { name: "Confirm check" });
  expect(confirm).toBeDisabled();
  expect(within(list).getByText(SHA)).toBeInTheDocument();
  fireEvent.change(within(list).getByRole("textbox", { name: "How Assignment agreement 2026 was checked" }), { target: { value: "Scanned with the office antivirus." } });
  expect(confirm).toBeDisabled(); // the SHA-256 of the scanned file is also required
  fireEvent.change(within(list).getByRole("textbox", { name: "SHA-256 of the scanned Assignment agreement 2026" }), { target: { value: ` ${SHA} ` } });
  fireEvent.click(confirm);
  await waitFor(() => expect(checks).toEqual([{ note: "Scanned with the office antivirus.", checksum_sha256: SHA }]));
  expect(await screen.findByText(/^Checked/)).toBeInTheDocument();
});
