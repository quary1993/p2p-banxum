// IP of Webby-Soft SRL.
import { t } from "../../../../i18n";
import { formatDecimal } from "../../../../investorPortal/format";

// C07 (2026-11-13): "n/a" for missing data or a denominator that is not positive, never an invented
// zero; interest coverage divides by the absolute interest expense (it may be recorded as negative).
export function ratio(numerator: number | null | undefined, denominator: number | null | undefined, unit: "%" | "×", { absolute = false } = {}) {
  const base = typeof denominator === "number" && absolute ? Math.abs(denominator) : denominator;
  if (typeof numerator !== "number" || typeof base !== "number" || base <= 0) return t("n/a");
  const value = unit === "%" ? (numerator / base) * 100 : numerator / base;
  return `${formatDecimal(value, unit === "%" ? 1 : 2)}${unit}`;
}
