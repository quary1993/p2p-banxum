// IP of Webby-Soft SRL.
// The Transactions page's reading of GET /investor/portal/activity/: one row per entry with its type,
// status, sign and description; the type groups of the filter; the period filter; the per-currency
// summary of the rows in view; the CSV export. Only API values are used (no running balance: the
// API does not give one, see docs/claude-design/TODO.md).
import type { ActivityEntry } from "../../../api/generated/banxumApi";
import { minorUnitDecimalsForCurrency, zurichDateKey, type NumberFormat } from "../../../investorPortal/format";

export type TransactionGroup =
  | "deposit"
  | "reservation"
  | "investment"
  | "repayment"
  | "recovery"
  | "withdrawal"
  | "return"
  | "purchase"
  | "sale"
  | "fee"
  | "fx"
  | "other";

/** Filter options in the design's order; groups without rows are hidden by the page. */
export const TRANSACTION_GROUPS: Array<{ value: TransactionGroup; label: string }> = [
  { value: "deposit", label: "Deposits" },
  { value: "reservation", label: "Reservations" },
  { value: "investment", label: "Investments" },
  { value: "repayment", label: "Repayments" },
  { value: "recovery", label: "Recoveries" },
  { value: "withdrawal", label: "Withdrawals" },
  { value: "return", label: "Automatic returns" },
  { value: "purchase", label: "Secondary purchases" },
  { value: "sale", label: "Secondary sales" },
  { value: "fee", label: "Fees and penalties" },
  { value: "fx", label: "Currency exchange" },
  { value: "other", label: "Other" }
];

export type Sign = "in" | "out" | "none";

export type Description = { text: string; vars?: Record<string, string> };

const plain = (value: string): Description => ({ text: "{value}", vars: { value } });

export type TransactionRow = {
  entry: ActivityEntry;
  group: TransactionGroup;
  /** English type label (translated by the page). */
  label: string;
  /** English status label (translated by the page). */
  status: string;
  /** Reservation still waiting for the funding to close (design: dot + "Until closing"). */
  pending: boolean;
  sign: Sign;
  /** Second line: loan, bank account or source, as an English template and its values. */
  description: Description;
  icon: string;
  amountMinor: number;
  dateKey: string;
};

const RESERVED = new Set(["balance_allocated", "partially_allocated"]);
const ORDER_PLACED = new Set(["pending", "pending_allocation"]);

function metadataOf(entry: ActivityEntry): Record<string, unknown> {
  return entry.metadata && typeof entry.metadata === "object" && !Array.isArray(entry.metadata) ? (entry.metadata as Record<string, unknown>) : {};
}

export function metadataNumber(entry: ActivityEntry, key: string): number | null {
  const value = metadataOf(entry)[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function metadataText(entry: ActivityEntry, key: string): string {
  const value = metadataOf(entry)[key];
  return typeof value === "string" ? value : "";
}

function maskedIban(value: string) {
  const compact = value.replace(/\s+/g, "");
  return compact.length > 8 ? `${compact.slice(0, 4)} •••• ${compact.slice(-4)}` : compact;
}

function humanize(value: string) {
  const text = value.replace(/_/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

const balanceSources: Record<string, { label: string; group: TransactionGroup; icon: string }> = {
  deposit: { label: "Deposit", group: "deposit", icon: "arrow-down-left" },
  secondary_market_proceeds: { label: "Secondary sale", group: "sale", icon: "exchange" },
  fx_proceeds: { label: "Currency exchange proceeds", group: "fx", icon: "exchange" },
  refund: { label: "Refund", group: "other", icon: "arrow-down-left" },
  correction: { label: "Balance correction", group: "other", icon: "edit" },
  penalty_reversal: { label: "Penalty refund", group: "fee", icon: "arrow-down-left" }
};

function withdrawalStatus(status: string) {
  if (status === "requested") return "Pending";
  if (status === "finalized") return "Sent";
  if (status === "cancelled") return "Cancelled";
  return humanize(status);
}

/** How the page shows one activity entry. */
export function transactionRow(entry: ActivityEntry): TransactionRow {
  const type = entry.activity_type;
  const status = entry.status;
  const base = {
    entry,
    amountMinor: Math.abs(entry.amount_minor ?? 0),
    dateKey: zurichDateKey(entry.occurred_at),
    pending: false,
    sign: (entry.direction === "in" ? "in" : entry.direction === "out" ? "out" : "none") as Sign,
    description: plain(entry.loan_title || "")
  };
  const forced = metadataOf(entry).is_forced === true;
  const iban = metadataText(entry, "destination_iban");
  if (type.startsWith("balance_") && type !== "balance_penalty_charge") {
    const source = balanceSources[type.slice("balance_".length)];
    const opening = entry.title === "QA opening balance";
    return {
      ...base,
      group: source?.group ?? "other",
      label: opening ? "Opening balance" : source?.label ?? humanize(type.slice("balance_".length)),
      status: "Received",
      icon: source?.icon ?? "arrow-down-left",
      description: entry.loan_title ? base.description : { text: source?.group === "deposit" ? "Bank transfer" : "Banxum account" }
    };
  }
  switch (type) {
    case "primary_order":
      if (status === "closed_invested") return { ...base, group: "investment", label: "Investment", status: "Completed", icon: "growth", sign: "out" };
      if (RESERVED.has(status)) return { ...base, group: "reservation", label: "Reservation", status: "Until closing", pending: true, icon: "clock", sign: "none" };
      if (ORDER_PLACED.has(status)) return { ...base, group: "reservation", label: "Investment order", status: "Waiting for allocation", icon: "clock", sign: "none" };
      if (status === "balance_released") return { ...base, group: "reservation", label: "Reservation released", status: "Released", icon: "undo", sign: "none" };
      if (status === "closed_not_invested") return { ...base, group: "reservation", label: "Investment order", status: "Not invested", icon: "clock", sign: "none" };
      return { ...base, group: "reservation", label: "Investment order", status: humanize(status), icon: "clock", sign: "none" };
    case "originator_claim_purchase":
      return { ...base, group: "investment", label: "Investment", status: "Completed", icon: "growth" };
    case "repayment_distribution":
    case "interest_distribution":
    case "originator_repayment_distribution":
      // U33-DEC-02: repayments are credited to the Banxum balance.
      return { ...base, group: "repayment", label: "Repayment", status: "Credited to your balance", icon: "arrow-up-right" };
    case "recovery_distribution":
      return { ...base, group: "recovery", label: "Recovery payment", status: "Credited to your balance", icon: "arrow-up-right" };
    case "withdrawal_request":
      return {
        ...base,
        group: forced ? "return" : "withdrawal",
        label: forced ? "Automatic return" : "Withdrawal",
        status: withdrawalStatus(status),
        icon: forced ? "undo" : "wallet-out",
        description: iban ? { text: "To {iban}", vars: { iban: maskedIban(iban) } } : { text: "To your bank account" }
      };
    case "withdrawal_cancellation":
      return {
        ...base,
        group: forced ? "return" : "withdrawal",
        label: forced ? "Automatic return cancelled" : "Withdrawal cancelled",
        status: "Returned to your balance",
        icon: "undo",
        description: { text: "Banxum account" }
      };
    case "balance_penalty_charge":
      return { ...base, group: "fee", label: "Penalty", status: "Charged", icon: "alert", description: { text: "Balance past the 60-day limit" } };
    case "secondary_market_fee":
      return { ...base, group: "fee", label: "Resale fee", status: humanize(status) || "Charged", icon: "coins" };
    case "secondary_purchase":
      return { ...base, group: "purchase", label: "Secondary purchase", status: "Completed", icon: "exchange" };
    case "secondary_sale":
      return { ...base, group: "sale", label: "Secondary sale", status: "Completed", icon: "exchange" };
    case "secondary_listing":
      return { ...base, group: "sale", label: "Secondary listing", status: humanize(status), icon: "tag", sign: "none" };
    case "fx_exchange": {
      const source = metadataText(entry, "source_currency");
      const target = metadataText(entry, "target_currency");
      return {
        ...base,
        group: "fx",
        label: "Currency exchange",
        status: status === "settled" || status === "executed" ? "Completed" : humanize(status),
        icon: "exchange",
        sign: "none",
        description: source && target ? plain(`${source} → ${target}`) : { text: "Banxum account" }
      };
    }
    default:
      return { ...base, group: "other", label: entry.title || humanize(type), status: humanize(status), icon: "tranx" };
  }
}

export type Period = { kind: "all" } | { kind: "days"; days: number } | { kind: "year"; year: number } | { kind: "custom"; from: string; to: string };

function shiftDateKey(key: string, days: number) {
  const date = new Date(`${key}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** Inclusive date range of a period ("" = open end), on Europe/Zurich business dates. */
export function periodRange(period: Period, todayKey: string): { from: string; to: string } {
  switch (period.kind) {
    case "days":
      return { from: shiftDateKey(todayKey, -(period.days - 1)), to: todayKey };
    case "year":
      return { from: `${period.year}-01-01`, to: `${period.year}-12-31` };
    case "custom":
      return { from: period.from, to: period.to };
    default:
      return { from: "", to: "" };
  }
}

export function inRange(dateKey: string, range: { from: string; to: string }) {
  return (!range.from || dateKey >= range.from) && (!range.to || dateKey <= range.to);
}

export type CurrencySummary = { currency: string; deposited: number; invested: number; credited: number; withdrawn: number };

/** Per-currency totals of the rows in view (design Summary: "in this view"). */
export function summarize(rows: TransactionRow[]): CurrencySummary[] {
  const byCurrency = new Map<string, CurrencySummary>();
  for (const row of rows) {
    const currency = row.entry.currency;
    if (!currency) continue;
    const item = byCurrency.get(currency) ?? { currency, deposited: 0, invested: 0, credited: 0, withdrawn: 0 };
    if (row.group === "deposit") item.deposited += row.amountMinor;
    else if (row.group === "investment") item.invested += row.amountMinor;
    else if (row.group === "repayment" || row.group === "recovery") item.credited += row.amountMinor;
    else if ((row.group === "withdrawal" || row.group === "return") && row.entry.activity_type === "withdrawal_request" && row.entry.status === "finalized") item.withdrawn += row.amountMinor;
    byCurrency.set(currency, item);
  }
  return [...byCurrency.values()].sort((a, b) => (a.currency === "EUR" ? -1 : b.currency === "EUR" ? 1 : a.currency.localeCompare(b.currency)));
}

/** A plain decimal for spreadsheets: no grouping, the investor's decimal mark, integer maths only. */
export function csvAmount(amountMinor: number, currency: string, sign: Sign, format: NumberFormat) {
  const decimals = minorUnitDecimalsForCurrency(currency);
  const absolute = Math.abs(amountMinor);
  const scale = 10 ** decimals;
  const whole = Math.floor(absolute / scale);
  const fraction = String(absolute % scale).padStart(decimals, "0");
  const minus = sign === "out" ? "-" : "";
  return decimals > 0 ? `${minus}${whole}${format === "european" ? "," : "."}${fraction}` : `${minus}${whole}`;
}

function csvCell(value: string, separator: string) {
  return /["\n\r]/.test(value) || value.includes(separator) ? `"${value.replace(/"/g, '""')}"` : value;
}

/**
 * The rows in view as CSV. The European format uses ";" between cells and "," as decimal mark, the
 * Swiss format "," and "." (what spreadsheet apps expect in each convention, U33-DEC-32).
 */
export function transactionsCsv(
  rows: TransactionRow[],
  format: NumberFormat,
  translate: (text: string, vars?: Record<string, string>) => string,
  dateTime: (value: string) => string
) {
  const separator = format === "european" ? ";" : ",";
  const header = ["Date", "Type", "Status", "Description", "Currency", "Amount", "Reference"].map((text) => translate(text));
  const lines = rows.map((row) =>
    [
      dateTime(row.entry.occurred_at),
      translate(row.label),
      translate(row.status),
      translate(row.description.text, row.description.vars),
      row.entry.currency,
      row.amountMinor ? csvAmount(row.amountMinor, row.entry.currency, row.sign, format) : "",
      row.entry.id
    ].map((cell) => csvCell(cell, separator)).join(separator)
  );
  return [header.join(separator), ...lines].join("\r\n");
}
