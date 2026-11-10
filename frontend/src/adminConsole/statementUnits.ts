// IP of Webby-Soft SRL.
// U33-DEC-20 admin credit file: statement figures typed in currency units and the server's
// consistency checks shown while typing.
import { minorUnitDecimalsForCurrency } from "../investorPortal/format";

// Statement figures are typed in currency units ("1250000" or "1250000.50"), never with group
// separators, so nothing is guessed; they are stored in minor units.
const UNITS_PATTERN = /^-?\d+(\.\d+)?$/;

export function unitsToMinor(text: string, currency: string): number | null {
  const value = text.trim();
  if (!value || !UNITS_PATTERN.test(value)) return null;
  const decimals = minorUnitDecimalsForCurrency(currency);
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace("-", "").split(".");
  if (fraction.length > decimals) return null;
  const minor = Number(whole) * 10 ** decimals + Number(fraction.padEnd(decimals, "0") || "0");
  return Number.isSafeInteger(minor) ? (negative ? -minor : minor) : null;
}

export function minorToUnits(minor: number | null | undefined, currency: string): string {
  if (minor === null || minor === undefined) return "";
  const decimals = minorUnitDecimalsForCurrency(currency);
  const sign = minor < 0 ? "-" : "";
  const absolute = Math.abs(minor);
  const whole = Math.trunc(absolute / 10 ** decimals);
  const fraction = String(absolute % 10 ** decimals).padStart(decimals, "0").replace(/0+$/, "");
  return `${sign}${whole}${fraction ? `.${fraction}` : ""}`;
}

// The server's checks, shown while typing: each total against its parts (only when all are filled).
const FINANCIAL_YEAR_CHECKS: Array<{ label: string; total: string; parts: Array<[string, 1 | -1]> }> = [
  { label: "Revenue less operating costs = operating profit", total: "operating_profit_minor", parts: [["revenue_minor", 1], ["materials_costs_minor", -1], ["staff_costs_minor", -1], ["other_operating_costs_minor", -1], ["depreciation_minor", -1]] },
  { label: "Operating profit less interest = profit before tax", total: "profit_before_tax_minor", parts: [["operating_profit_minor", 1], ["interest_expense_minor", -1]] },
  { label: "Profit before tax less income tax = net profit", total: "net_profit_minor", parts: [["profit_before_tax_minor", 1], ["income_tax_minor", -1]] },
  { label: "Current assets", total: "current_assets_minor", parts: [["cash_minor", 1], ["trade_receivables_minor", 1], ["inventories_minor", 1], ["other_current_assets_minor", 1]] },
  { label: "Total assets", total: "total_assets_minor", parts: [["current_assets_minor", 1], ["property_plant_equipment_minor", 1], ["other_non_current_assets_minor", 1]] },
  { label: "Financial debt", total: "financial_debt_minor", parts: [["current_financial_debt_minor", 1], ["non_current_financial_debt_minor", 1]] },
  { label: "Financial debt + operating liabilities = total assets less equity", total: "", parts: [["financial_debt_minor", 1], ["trade_payables_minor", 1], ["other_operating_liabilities_minor", 1]] }
];

export function financialYearCheckResults(amounts: Record<string, number | null>) {
  return FINANCIAL_YEAR_CHECKS.flatMap((check) => {
    const values = check.parts.map(([field]) => amounts[field]);
    const total = check.total ? amounts[check.total] : amounts.total_assets_minor !== null && amounts.total_assets_minor !== undefined && amounts.equity_minor !== null && amounts.equity_minor !== undefined ? amounts.total_assets_minor - amounts.equity_minor : null;
    if (total === null || total === undefined || values.some((value) => value === null || value === undefined)) return [];
    const computed = check.parts.reduce((sum, [field, sign]) => sum + sign * (amounts[field] ?? 0), 0);
    return [{ label: check.label, computed, total, ok: computed === total }];
  });
}
