// IP of Webby-Soft SRL.
// Real-API checks of the U33 wallet screens (Phase 17.1, slice S4; 18.3): Transactions server
// filters, pages, available balance, detail, summary and CSV export; Reports downloads and Create report with the outputs the platform
// generates; Documents tabs and downloads; Add funds when the deposit account is not set up.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { renderLiveApp, shellHandlers } from "./test/liveHarness";

// No canvas in jsdom: the reader's engine is replaced by two blank pages.
vi.mock("./portal/components/pdf/pdfEngine", () => ({
  openPdf: async () => ({ numPages: 2, renderPage: async () => undefined, destroy: () => undefined })
}));

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

// jsdom has no object URLs: record the saved files instead.
let saved: Array<{ name: string; blob: Blob }> = [];
let restore: () => void = () => undefined;
beforeEach(() => {
  saved = [];
  const urls = URL as unknown as Record<string, unknown>;
  const original = { createObjectURL: urls.createObjectURL, revokeObjectURL: urls.revokeObjectURL };
  let lastBlob: Blob | null = null;
  Object.assign(urls, {
    createObjectURL: vi.fn((blob: Blob) => {
      lastBlob = blob;
      return "blob:wallet";
    }),
    revokeObjectURL: vi.fn()
  });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    if (this.download && lastBlob) saved.push({ name: this.download, blob: lastBlob });
  });
  restore = () => {
    click.mockRestore();
    Object.assign(urls, original);
  };
});
afterEach(() => restore());

const activity = {
  entries: [
    {
      id: "rep-1",
      activity_type: "repayment_distribution",
      occurred_at: "2026-11-21T07:00:00Z",
      direction: "in",
      title: "Loan repayment credited",
      amount_minor: 41_235,
      currency: "CHF",
      status: "",
      loan_id: "11111111-1111-4111-8111-111111111111",
      loan_title: "Helvetia Logistik AG",
      metadata: { principal_minor: 35_410, interest_minor: 5_825, fee_minor: 0 }
    },
    {
      id: "ord-1",
      activity_type: "primary_order",
      occurred_at: "2026-11-15T09:00:00Z",
      direction: "internal",
      title: "Primary-market investment order",
      amount_minor: 150_000,
      currency: "EUR",
      status: "balance_allocated",
      loan_id: "22222222-2222-4222-8222-222222222222",
      loan_title: "Wine cellar expansion",
      metadata: {}
    },
    {
      id: "dep-1",
      activity_type: "balance_deposit",
      occurred_at: "2026-10-02T08:00:00Z",
      direction: "in",
      title: "Deposit",
      amount_minor: 1_200_000,
      currency: "CHF",
      status: "available",
      loan_id: null,
      loan_title: "",
      metadata: {}
    },
    {
      id: "wd-1",
      activity_type: "withdrawal_request",
      occurred_at: "2025-12-20T10:00:00Z",
      direction: "out",
      title: "Withdrawal request",
      amount_minor: 50_000,
      currency: "CHF",
      status: "finalized",
      loan_id: null,
      loan_title: "",
      metadata: { is_forced: false, destination_iban: "CH5604835012345678009", finalized_at: "2025-12-21T10:00:00Z", cancelled_at: "" }
    }
  ]
};

const documents = {
  as_of: "2026-12-10T11:00:00Z",
  disclaimer: "Statements and annual tax-information files are informational only and are not tax advice.",
  documents: [
    {
      id: "acc-1",
      document_kind: "acceptance_evidence",
      title: "Loan Helvetia Logistik AG CHF 6,500.00 agreement",
      template_title: "Primary-market investment terms",
      document_type: "Investment agreement",
      category: "primary_market_investment",
      version: "v3",
      date: "2026-11-15T09:00:00Z",
      context_label: "Order 4f1a",
      output_formats: ["pdf", "csv"],
      generated_on_request: true,
      content_hash: "abc"
    },
    {
      id: "acc-2",
      document_kind: "acceptance_evidence",
      title: "Lender user agreement",
      template_title: "Registration terms",
      document_type: "Agreement",
      category: "registration",
      version: "v4",
      date: "2025-11-12T09:00:00Z",
      context_label: "Registration",
      output_formats: ["pdf", "csv"],
      generated_on_request: true
    },
    {
      id: "statement-2026",
      document_kind: "account_statement",
      title: "Investor account statement - 2026",
      document_type: "Statement",
      version: "reporting-v2",
      date: "2026-12-10T11:00:00Z",
      context_label: "2026-01-01 to 2026-12-10",
      output_formats: ["pdf", "csv", "zip"],
      generated_on_request: true,
      period_start: "2026-01-01",
      period_end: "2026-12-10"
    },
    {
      id: "statement-2025",
      document_kind: "account_statement",
      title: "Investor account statement - 2025",
      document_type: "Statement",
      version: "reporting-v2",
      date: "2026-12-10T11:00:00Z",
      context_label: "2025-01-01 to 2025-12-31",
      output_formats: ["pdf", "csv", "zip"],
      generated_on_request: true,
      period_start: "2025-01-01",
      period_end: "2025-12-31"
    },
    {
      id: "tax-2025",
      document_kind: "annual_tax_information",
      title: "Annual lender tax information statement - 2025",
      document_type: "Tax",
      version: "reporting-v2",
      date: "2026-12-10T11:00:00Z",
      context_label: "Calendar year 2025",
      output_formats: ["pdf", "csv", "zip"],
      generated_on_request: true,
      period_start: "2025-01-01",
      period_end: "2025-12-31"
    }
  ]
};

function walletHandlers(downloads: Array<Record<string, unknown>> = []) {
  return [
    ...shellHandlers(),
    http.get("*/api/v1/investor/portal/activity/", () => HttpResponse.json(activity)),
    http.get("*/api/v1/investor/portal/documents/", () => HttpResponse.json(documents)),
    http.get("*/api/v1/investor/portal/primary-orders/", () => HttpResponse.json({ orders: [] })),
    http.post("*/api/v1/investor/portal/documents/download/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      downloads.push(body);
      const extension = String(body.output_format ?? "pdf");
      return HttpResponse.json({
        content_type: extension === "csv" ? "text/csv" : "application/pdf",
        filename: `banxum-${String(body.document_kind)}.${extension}`,
        content_encoding: "utf-8",
        content: "file",
        content_sha256: "x",
        manifest: {}
      });
    })
  ];
}

const GROUPS: Record<string, string> = { "rep-1": "repayment", "ord-1": "reservation", "dep-1": "deposit", "wd-1": "withdrawal" };
const AVAILABLE: Record<string, number> = { "rep-1": 1_191_235, "ord-1": 0, "dep-1": 1_200_000, "wd-1": 50_000 };

/** A small stand-in for the server's filters, pages and summary (18.3). */
function transactionsHandler(seen: URLSearchParams[] = []) {
  return http.get("*/api/v1/investor/portal/transactions/", ({ request }) => {
    const params = new URL(request.url).searchParams;
    seen.push(params);
    const q = (params.get("q") ?? "").toLowerCase();
    const matching = activity.entries.filter((entry) => {
      const day = entry.occurred_at.slice(0, 10);
      return (!params.get("group") || GROUPS[entry.id] === params.get("group")) &&
        (!params.get("currency") || entry.currency === params.get("currency")) &&
        (!params.get("date_from") || day >= String(params.get("date_from"))) &&
        (!params.get("date_to") || day <= String(params.get("date_to"))) &&
        (!q || `${entry.title} ${entry.loan_title} ${GROUPS[entry.id]}`.toLowerCase().includes(q));
    });
    const offset = Number(params.get("offset") ?? 0);
    const limit = Number(params.get("limit") ?? 25);
    const sum = (currency: string, group: string) => matching.filter((e) => e.currency === currency && GROUPS[e.id] === group).reduce((total, e) => total + e.amount_minor, 0);
    return HttpResponse.json({
      entries: matching.slice(offset, offset + limit).map((entry) => ({ ...entry, group: GROUPS[entry.id], available_after_minor: AVAILABLE[entry.id] })),
      total: matching.length,
      offset,
      next_offset: offset + limit < matching.length ? offset + limit : null,
      currencies: ["EUR", "CHF"],
      groups: ["deposit", "reservation", "repayment", "withdrawal"],
      years: [2026, 2025],
      summary: [...new Set(matching.map((e) => e.currency))].map((currency) => ({
        currency,
        deposited_minor: sum(currency, "deposit"),
        invested_minor: 0,
        credited_minor: sum(currency, "repayment"),
        withdrawn_minor: sum(currency, "withdrawal")
      }))
    });
  });
}

test("Transactions filter on the server by type, currency, search and period, and open a movement's details", async () => {
  const seen: URLSearchParams[] = [];
  server.use(...walletHandlers(), transactionsHandler(seen));
  renderLiveApp(App, "/transactions");

  const table = await screen.findByRole("table", {}, { timeout: 5000 });
  const main = screen.getByRole("main");
  expect(within(main).getByText("4 transactions")).toBeInTheDocument();
  // 18.3: the available balance after each movement, from the server.
  expect(within(table).getByRole("columnheader", { name: /Available balance/ })).toBeInTheDocument();
  const repayment = within(table).getByRole("button", { name: /^Repayment · Helvetia Logistik AG/ });
  expect(repayment).toHaveTextContent("Credited to your balance");
  expect(repayment).toHaveTextContent("+ CHF 412,35");
  expect(repayment).toHaveTextContent("CHF 11.912,35");
  expect(within(table).getByRole("button", { name: /^Reservation · Wine cellar expansion/ })).toHaveTextContent("Until closing");
  expect(within(table).getByRole("button", { name: /^Withdrawal · To CH56 •••• 8009/ })).toHaveTextContent("− CHF 500,00");

  fireEvent.change(within(main).getByLabelText("Transaction type"), { target: { value: "repayment" } });
  expect(await within(main).findByText("1 transaction")).toBeInTheDocument();
  expect(seen.at(-1)?.get("group")).toBe("repayment");
  fireEvent.change(within(main).getByLabelText("Transaction type"), { target: { value: "" } });
  expect(await within(main).findByText("4 transactions")).toBeInTheDocument();

  fireEvent.click(within(within(main).getByRole("group", { name: "Currency" })).getByRole("button", { name: "EUR" }));
  expect(await within(main).findByText("1 transaction")).toBeInTheDocument();
  expect(seen.at(-1)?.get("currency")).toBe("EUR");
  fireEvent.click(within(within(main).getByRole("group", { name: "Currency" })).getByRole("button", { name: "All" }));
  expect(await within(main).findByText("4 transactions")).toBeInTheDocument();

  fireEvent.change(within(main).getByLabelText("Search transactions"), { target: { value: "deposit" } });
  expect(await within(main).findByText("1 transaction", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(seen.at(-1)?.get("q")).toBe("deposit");
  fireEvent.change(within(main).getByLabelText("Search transactions"), { target: { value: "" } });
  expect(await within(main).findByText("4 transactions", {}, { timeout: 3000 })).toBeInTheDocument();

  // Period: a year, then custom dates (from after to is refused, a valid range filters).
  fireEvent.change(within(main).getByLabelText("Period"), { target: { value: "y2025" } });
  expect(await within(main).findByText("1 transaction")).toBeInTheDocument();
  expect([seen.at(-1)?.get("date_from"), seen.at(-1)?.get("date_to")]).toEqual(["2025-01-01", "2025-12-31"]);
  fireEvent.change(within(main).getByLabelText("Period"), { target: { value: "custom" } });
  fireEvent.change(within(main).getByLabelText("From"), { target: { value: "2026-11-30" } });
  fireEvent.change(within(main).getByLabelText("To"), { target: { value: "2026-11-01" } });
  fireEvent.click(within(main).getByRole("button", { name: "Apply" }));
  expect(within(main).getByRole("alert")).toHaveTextContent("Choose a start and end date. From must be on or before To.");
  fireEvent.change(within(main).getByLabelText("From"), { target: { value: "2026-11-01" } });
  fireEvent.change(within(main).getByLabelText("To"), { target: { value: "2026-11-30" } });
  fireEvent.click(within(main).getByRole("button", { name: "Apply" }));
  expect(await within(main).findByText("2 transactions")).toBeInTheDocument();
  fireEvent.change(within(main).getByLabelText("Period"), { target: { value: "all" } });
  expect(await within(main).findByText("4 transactions")).toBeInTheDocument();

  // Details of a repayment: principal and interest, credited to the balance, the balance after it.
  fireEvent.click(within(main).getByRole("button", { name: /^Repayment · Helvetia Logistik AG/ }));
  const detail = screen.getByRole("dialog", { name: "Repayment" });
  expect(within(detail).getByText("CHF 354,10")).toBeInTheDocument();
  expect(within(detail).getByText("CHF 58,25")).toBeInTheDocument();
  expect(within(detail).getByText("Available balance after").nextSibling).toHaveTextContent("CHF 11.912,35");
  expect(within(detail).getByText("Credited to your Banxum balance. You can invest it again or withdraw it.")).toBeInTheDocument();
  expect(within(detail).getByRole("link", { name: "View loan" })).toHaveAttribute("href", "/marketplace/11111111-1111-4111-8111-111111111111");
}, 30_000);

test("Transactions show the server's summary, load more pages and save the server's CSV", async () => {
  const exports: URLSearchParams[] = [];
  server.use(
    ...walletHandlers(),
    transactionsHandler(),
    http.get("*/api/v1/investor/portal/transactions/export/", ({ request }) => {
      exports.push(new URL(request.url).searchParams);
      return new HttpResponse("Date;Type\n2026-11-21 08:00;Repayment\n", { headers: { "Content-Type": "text/csv; charset=utf-8" } });
    })
  );
  renderLiveApp(App, "/transactions");
  await screen.findByRole("table", {}, { timeout: 5000 });
  const main = screen.getByRole("main");

  const toggle = within(main).getByRole("button", { name: "Summary" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(toggle);
  const totals = document.getElementById("tr-totals") as HTMLElement;
  expect(totals).not.toHaveAttribute("hidden");
  const chf = within(totals).getByRole("heading", { name: /^CHF/ }).closest("section") as HTMLElement;
  expect(within(chf).getByText("Deposited").nextSibling).toHaveTextContent("12.000,00");
  expect(within(chf).getByText("Repaid to Banxum account").nextSibling).toHaveTextContent("412,35");
  expect(within(chf).getByText("Withdrawn").nextSibling).toHaveTextContent("500,00");
  expect(within(main).getByText("Showing 4 of 4")).toBeInTheDocument();

  fireEvent.click(within(within(main).getByRole("group", { name: "Currency" })).getByRole("button", { name: "CHF" }));
  expect(await within(main).findByText("3 transactions")).toBeInTheDocument();
  fireEvent.click(within(main).getByRole("button", { name: "Export CSV" }));
  await waitFor(() => expect(saved).toHaveLength(1));
  expect(exports[0].get("currency")).toBe("CHF");
  expect(saved[0].name).toBe("banxum-transactions-2026-12-10.csv");
  // jsdom's Blob has no text(): read it like a browser file.
  const csv = await new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(saved[0].blob);
  });
  expect(csv.replace(/^\uFEFF/, "").split("\n")[0]).toBe("Date;Type");
}, 30_000);

const keptReports = {
  reports: [
    {
      id: "aa9a1f6e-1c4e-4f43-8c7a-0e7a3b9c1d11",
      kind: "monthly_statement",
      title: "Account statement November 2026",
      currency: "",
      start_date: "2026-11-01",
      end_date: "2026-11-30",
      output_format: "pdf",
      filename: "participant_account_statement_2026-11-01_2026-11-30.pdf",
      issued_at: "2026-12-01T06:00:00Z",
      automatic: true
    }
  ]
};

function reportHandlers(created: Array<Record<string, unknown>>) {
  return [
    http.get("*/api/v1/investor/portal/reports/", () => HttpResponse.json(keptReports)),
    http.get("*/api/v1/investor/portal/reports/summary/", ({ request }) =>
      HttpResponse.json({
        year: Number(new URL(request.url).searchParams.get("year")) || null,
        start_date: "2026-01-01",
        end_date: "2026-12-31",
        currencies: [
          { currency: "EUR", invested_minor: 150_000, principal_repaid_minor: 0, interest_received_minor: 0 },
          { currency: "CHF", invested_minor: 650_000, principal_repaid_minor: 35_410, interest_received_minor: 5_825 }
        ]
      })
    ),
    http.get("*/api/v1/investor/portal/reports/:reportId/download/", () =>
      HttpResponse.json({ content_type: "application/pdf", filename: "statement.pdf", content_encoding: "base64", content: "JVBERi0xLjQ=", content_sha256: "x", manifest: {} })
    ),
    http.post("*/api/v1/investor/portal/reports/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      created.push(body);
      return HttpResponse.json(
        { id: "bb9a1f6e-1c4e-4f43-8c7a-0e7a3b9c1d22", kind: body.kind, title: "Tax report", currency: body.currency, start_date: body.start_date, end_date: body.end_date, output_format: body.output_format, filename: "tax.pdf", issued_at: "2026-12-10T11:00:00Z", automatic: false },
        { status: 201 }
      );
    })
  ];
}

test("Reports list kept and offered reports by year and type, open PDFs in the reader and create the design's reports", async () => {
  const downloads: Array<Record<string, unknown>> = [];
  const created: Array<Record<string, unknown>> = [];
  server.use(...walletHandlers(downloads), ...reportHandlers(created));
  renderLiveApp(App, "/reports");
  const table = await screen.findByRole("table", {}, { timeout: 5000 });
  const main = screen.getByRole("main");
  // This year by default: the monthly statement and the year-to-date statement.
  expect(within(main).getByText("2 reports")).toBeInTheDocument();
  expect(within(table).getByText("Account statement November 2026")).toBeInTheDocument();
  expect(within(table).getByText("Nov 2026")).toBeInTheDocument();
  const years = within(main).getByRole("group", { name: "Report year" });
  fireEvent.click(within(years).getByRole("button", { name: "2025" }));
  expect(within(main).getByText("2 reports")).toBeInTheDocument();
  fireEvent.click(within(years).getByRole("button", { name: "All years" }));
  expect(within(main).getByText("4 reports")).toBeInTheDocument();

  fireEvent.change(within(main).getByLabelText("Report type"), { target: { value: "tax" } });
  expect(within(main).getByText("1 report")).toBeInTheDocument();
  fireEvent.click(within(main).getByRole("button", { name: "Download Tax information 2025 as CSV" }));
  await waitFor(() => expect(downloads).toHaveLength(1));
  expect(downloads[0]).toMatchObject({ document_kind: "annual_tax_information", output_format: "csv", start_date: "2025-01-01", end_date: "2025-12-31" });
  fireEvent.change(within(main).getByLabelText("Report type"), { target: { value: "" } });

  // The PDF opens in the in-app reader, with zoom, download and Close.
  fireEvent.click(within(main).getByRole("button", { name: "View Account statement November 2026 · Nov 2026" }));
  const reader = await screen.findByRole("dialog", { name: "Account statement November 2026" });
  expect(await within(reader).findByText("2 pages")).toBeInTheDocument();
  expect(within(reader).getAllByRole("img", { name: /^Page / })).toHaveLength(2);
  fireEvent.click(within(reader).getByRole("button", { name: "Zoom in" }));
  expect(within(reader).getByText("125%")).toBeInTheDocument();
  fireEvent.click(within(reader).getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(saved.map((file) => file.name)).toContain("statement.pdf"));
  // The footer's Close (the corner "×" closes it too).
  fireEvent.click(within(reader).getAllByRole("button", { name: "Close" }).at(-1) as HTMLElement);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  // The annual summary per currency, from the server.
  fireEvent.click(within(main).getByRole("button", { name: /All-time summary/ }));
  const summary = document.getElementById("tr-annual-summary") as HTMLElement;
  const chf = (await within(summary).findByRole("heading", { name: /^CHF/ })).closest("section") as HTMLElement;
  expect(within(chf).getByText("Interest received").nextSibling).toHaveTextContent("58,25");

  // Create report: the design's four types; months; the portfolio as of today.
  fireEvent.click(within(main).getByRole("button", { name: "Create report" }));
  const dialog = screen.getByRole("dialog", { name: "Create report" });
  expect(within(dialog).getAllByRole("radio").map((radio) => (radio as HTMLInputElement).value)).toEqual(["account_statement", "portfolio", "interest_repayments", "tax"]);
  fireEvent.click(within(dialog).getByRole("radio", { name: /Portfolio report/ }));
  expect(within(dialog).getByText("As of 10 Dec 2026")).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("radio", { name: /Tax report/ }));
  expect(within(dialog).getByText("The tax report is information for your tax return. It is not an official tax certificate.")).toBeInTheDocument();
  fireEvent.change(within(dialog).getByLabelText("From"), { target: { value: "2026-03" } });
  fireEvent.change(within(dialog).getByLabelText("To"), { target: { value: "2026-01" } });
  fireEvent.click(within(dialog).getByRole("button", { name: /^Create report/ }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent("Choose a valid start and end month.");
  fireEvent.change(within(dialog).getByLabelText("From"), { target: { value: "2026-01" } });
  fireEvent.change(within(dialog).getByLabelText("To"), { target: { value: "2026-03" } });
  fireEvent.change(within(dialog).getByLabelText("Currency"), { target: { value: "CHF" } });
  fireEvent.click(within(dialog).getByRole("button", { name: /^Create report/ }));
  await waitFor(() => expect(created).toHaveLength(1));
  expect(created[0]).toEqual({ kind: "tax", start_date: "2026-01-01", end_date: "2026-03-31", currency: "CHF", output_format: "pdf" });
  expect(await screen.findByText("Document ready: Tax report")).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "Create report" })).not.toBeInTheDocument();
}, 30_000);

test("Documents sort the investor's documents into tabs and download them on request", async () => {
  const downloads: Array<Record<string, unknown>> = [];
  server.use(...walletHandlers(downloads));
  renderLiveApp(App, "/documents");
  const table = await screen.findByRole("table", {}, { timeout: 5000 });
  const main = screen.getByRole("main");
  const tabs = within(main).getByRole("navigation", { name: "Document categories" });

  // Investment documents: the design's names (an accepted investment is a purchase agreement),
  // accepted with the email code and PIN, never "signed" (U33-DEC-13).
  expect(within(tabs).getByRole("button", { name: "Investment documents" })).toHaveAttribute("aria-pressed", "true");
  const row = within(table).getByRole("button", { name: "Purchase agreement" }).closest("tr") as HTMLElement;
  expect(within(row).getByText("Accepted by you")).toBeInTheDocument();
  expect(within(row).getByText("Loan Helvetia Logistik AG CHF 6,500.00 agreement")).toBeInTheDocument();
  expect(within(row).getByText("Order 4f1a")).toBeInTheDocument();
  expect(main).not.toHaveTextContent(/Signed by/);
  fireEvent.click(within(row).getByRole("button", { name: /as PDF$/ }));
  await waitFor(() => expect(downloads).toHaveLength(1));
  expect(downloads[0]).toMatchObject({ document_kind: "acceptance_evidence", document_id: "acc-1", output_format: "pdf" });

  fireEvent.change(within(main).getByLabelText("Search documents"), { target: { value: "nothing like this" } });
  expect(within(main).getByText("No documents match your search or filters.")).toBeInTheDocument();
  fireEvent.click(within(main).getByRole("button", { name: "Clear filters" }));
  expect(within(main).getByText("1 document")).toBeInTheDocument();

  // Statements are on the Reports page (the design's header link), not in a Documents tab.
  expect(within(tabs).queryByRole("button", { name: "Statements" })).not.toBeInTheDocument();
  expect(within(main).getByRole("link", { name: "Reports" })).toBeInTheDocument();

  fireEvent.click(within(tabs).getByRole("button", { name: "Platform documents" }));
  const platform = within(main).getByRole("table");
  expect(within(platform).getByRole("button", { name: "Lender user agreement" })).toBeInTheDocument();
  expect(within(platform).getByText("Version 4")).toBeInTheDocument();
  expect(within(platform).getByRole("columnheader", { name: "Accepted" })).toBeInTheDocument();
}, 30_000);

test("Add funds warns not to send money while the deposit account is not set up", async () => {
  server.use(
    ...walletHandlers(),
    http.get("*/api/v1/investor/portal/deposit-instructions/", () =>
      HttpResponse.json({
        as_of: "2026-12-10T11:00:00Z",
        reference_rule: "Use the reference unchanged.",
        instructions: [
          {
            currency: "EUR",
            account_holder_name: "",
            iban: "",
            qr_iban: "",
            bic: "",
            bank_name: "",
            collection_account_identifier: "EUR-COLLECTION",
            qr_bill_payload: "",
            payment_reference: "BX-EUR-R1",
            notes: "",
            is_configured: false
          }
        ]
      })
    )
  );
  renderLiveApp(App, "/balances");
  const eur = await screen.findByRole("region", { name: "EUR account" }, { timeout: 5000 });
  fireEvent.click(within(eur).getByRole("button", { name: "Add funds" }));
  const dialog = screen.getByRole("dialog", { name: "Add funds" });
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("Do not send money yet.");
  expect(within(dialog).getAllByText("Not configured yet")).toHaveLength(2);
  expect(within(dialog).queryByRole("button", { name: "Copy IBAN" })).not.toBeInTheDocument();
  expect(within(dialog).getByText("BX-EUR-R1")).toBeInTheDocument();
}, 30_000);
