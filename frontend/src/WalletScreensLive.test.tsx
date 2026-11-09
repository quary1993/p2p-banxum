// IP of Webby-Soft SRL.
// Real-API checks of the U33 wallet screens (Phase 17.1, slice S4): Transactions filters, detail,
// summary and CSV export; Reports downloads and Create report with the outputs the platform
// generates; Documents tabs and downloads; Add funds when the deposit account is not set up.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { renderLiveApp, shellHandlers } from "./test/liveHarness";

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

test("Transactions filter by type, currency, search and period, and open a movement's details", async () => {
  server.use(...walletHandlers());
  renderLiveApp(App, "/transactions");

  const table = await screen.findByRole("table", {}, { timeout: 5000 });
  const main = screen.getByRole("main");
  expect(within(main).getByText("4 transactions")).toBeInTheDocument();
  // No running balance column: the API gives no balance after each movement.
  expect(within(table).queryByRole("columnheader", { name: /Available balance/ })).not.toBeInTheDocument();
  const repayment = within(table).getByRole("button", { name: /^Repayment · Helvetia Logistik AG/ });
  expect(repayment).toHaveTextContent("Credited to your balance");
  expect(repayment).toHaveTextContent("+ CHF 412,35");
  expect(within(table).getByRole("button", { name: /^Reservation · Wine cellar expansion/ })).toHaveTextContent("Until closing");
  expect(within(table).getByRole("button", { name: /^Withdrawal · To CH56 •••• 8009/ })).toHaveTextContent("− CHF 500,00");

  fireEvent.change(within(main).getByLabelText("Transaction type"), { target: { value: "repayment" } });
  expect(within(main).getByText("1 transaction")).toBeInTheDocument();
  fireEvent.change(within(main).getByLabelText("Transaction type"), { target: { value: "" } });

  fireEvent.click(within(within(main).getByRole("group", { name: "Currency" })).getByRole("button", { name: "EUR" }));
  expect(within(main).getByText("1 transaction")).toBeInTheDocument();
  fireEvent.click(within(within(main).getByRole("group", { name: "Currency" })).getByRole("button", { name: "All" }));

  fireEvent.change(within(main).getByLabelText("Search transactions"), { target: { value: "deposit" } });
  expect(within(main).getByText("1 transaction")).toBeInTheDocument();
  fireEvent.change(within(main).getByLabelText("Search transactions"), { target: { value: "" } });

  // Period: a year, then custom dates (from after to is refused, a valid range filters).
  fireEvent.change(within(main).getByLabelText("Period"), { target: { value: "y2025" } });
  expect(within(main).getByText("1 transaction")).toBeInTheDocument();
  fireEvent.change(within(main).getByLabelText("Period"), { target: { value: "custom" } });
  fireEvent.change(within(main).getByLabelText("From"), { target: { value: "2026-11-30" } });
  fireEvent.change(within(main).getByLabelText("To"), { target: { value: "2026-11-01" } });
  fireEvent.click(within(main).getByRole("button", { name: "Apply" }));
  expect(within(main).getByRole("alert")).toHaveTextContent("Choose a start and end date. From must be on or before To.");
  fireEvent.change(within(main).getByLabelText("From"), { target: { value: "2026-11-01" } });
  fireEvent.change(within(main).getByLabelText("To"), { target: { value: "2026-11-30" } });
  fireEvent.click(within(main).getByRole("button", { name: "Apply" }));
  expect(within(main).getByText("2 transactions")).toBeInTheDocument();
  fireEvent.change(within(main).getByLabelText("Period"), { target: { value: "all" } });

  // Details of a repayment: principal and interest, credited to the balance.
  fireEvent.click(within(main).getByRole("button", { name: /^Repayment · Helvetia Logistik AG/ }));
  const detail = screen.getByRole("dialog", { name: "Repayment" });
  expect(within(detail).getByText("CHF 354,10")).toBeInTheDocument();
  expect(within(detail).getByText("CHF 58,25")).toBeInTheDocument();
  expect(within(detail).getByText("Credited to your Banxum balance. You can invest it again or withdraw it.")).toBeInTheDocument();
  expect(within(detail).getByRole("link", { name: "View loan" })).toHaveAttribute("href", "/marketplace/11111111-1111-4111-8111-111111111111");
}, 30_000);

test("Transactions summarise the rows in view and export them as CSV in the investor's format", async () => {
  server.use(...walletHandlers());
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

  fireEvent.click(within(main).getByRole("button", { name: "Export CSV" }));
  await waitFor(() => expect(saved).toHaveLength(1));
  expect(saved[0].name).toBe("banxum-transactions-2026-12-10.csv");
  // jsdom's Blob has no text(): read it like a browser file.
  const csv = await new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(saved[0].blob);
  });
  const lines = csv.replace(/^\uFEFF/, "").split("\r\n");
  expect(lines[0]).toBe("Date;Type;Status;Description;Currency;Amount;Reference");
  expect(lines[1]).toContain(";Repayment;Credited to your balance;Helvetia Logistik AG;CHF;412,35;rep-1");
  expect(lines).toHaveLength(5);
}, 30_000);

test("Reports list today's statements and tax information and create reports the platform generates", async () => {
  const downloads: Array<Record<string, unknown>> = [];
  server.use(...walletHandlers(downloads));
  renderLiveApp(App, "/reports");
  const table = await screen.findByRole("table", {}, { timeout: 5000 });
  const main = screen.getByRole("main");
  expect(within(main).getByText("3 reports")).toBeInTheDocument();
  expect(within(table).getByText("Year to date")).toBeInTheDocument();
  expect(within(table).getAllByText("2025")).toHaveLength(2);

  fireEvent.change(within(main).getByLabelText("Report type"), { target: { value: "annual_tax_information" } });
  expect(within(main).getByText("1 report")).toBeInTheDocument();
  fireEvent.click(within(main).getByRole("button", { name: "Download Tax information 2025 as CSV" }));
  await waitFor(() => expect(downloads).toHaveLength(1));
  expect(downloads[0]).toMatchObject({ document_kind: "annual_tax_information", output_format: "csv", start_date: "2025-01-01", end_date: "2025-12-31" });
  await waitFor(() => expect(saved.map((file) => file.name)).toEqual(["banxum-annual_tax_information.csv"]));

  // Create report: only the outputs the platform generates (no portfolio or per-country reports).
  fireEvent.click(within(main).getByRole("button", { name: "Create report" }));
  const dialog = screen.getByRole("dialog", { name: "Create report" });
  expect(within(dialog).getAllByRole("radio").map((radio) => (radio as HTMLInputElement).value)).toEqual(["statement", "tax"]);
  expect(within(dialog).getByLabelText("From")).toHaveValue("2026-01-01");
  expect(within(dialog).getByLabelText("To")).toHaveValue("2026-12-10");
  fireEvent.change(within(dialog).getByLabelText("From"), { target: { value: "2026-12-31" } });
  fireEvent.click(within(dialog).getByRole("button", { name: /^Create report/ }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent("Choose a valid start and end date. The start must not be after the end.");
  expect(downloads).toHaveLength(1);
  fireEvent.change(within(dialog).getByLabelText("From"), { target: { value: "2026-03-01" } });
  fireEvent.change(within(dialog).getByLabelText("To"), { target: { value: "2026-03-31" } });
  fireEvent.click(within(dialog).getByRole("button", { name: /^Create report/ }));
  await waitFor(() => expect(downloads).toHaveLength(2));
  expect(downloads[1]).toMatchObject({ document_kind: "account_statement", output_format: "pdf", start_date: "2026-03-01", end_date: "2026-03-31" });
  expect(await screen.findByText("Report ready: banxum-account_statement.pdf")).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "Create report" })).not.toBeInTheDocument();

  // Tax information of a finished year as ZIP.
  fireEvent.click(within(main).getByRole("button", { name: "Create report" }));
  const second = screen.getByRole("dialog", { name: "Create report" });
  fireEvent.click(within(second).getByRole("radio", { name: /Tax information/ }));
  expect(within(second).getByLabelText("Year")).toHaveValue("2025");
  fireEvent.change(within(second).getByLabelText("Format"), { target: { value: "zip" } });
  fireEvent.click(within(second).getByRole("button", { name: /^Create report/ }));
  await waitFor(() => expect(downloads).toHaveLength(3));
  expect(downloads[2]).toMatchObject({ document_kind: "annual_tax_information", output_format: "zip", year: 2025 });
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
