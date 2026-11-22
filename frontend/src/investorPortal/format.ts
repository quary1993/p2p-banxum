// IP of Webby-Soft SRL.
/*
 * Formatting of the investor area: money, rates, numbers and dates, and the parsing of typed amounts.
 *
 * Number format (U33-DEC-32): European "1.234,56" by default, Swiss "1’234.56" (typographic
 * apostrophe U+2019, as in the design) as the alternative, independent of the language. The
 * investor's choice is saved in the account (and in localStorage for the signed-out screens).
 * The choice applies to the investor area only: InvestorShell enters the "number format scope"
 * (useNumberFormatScope) while it is mounted. Everywhere else (admin console, sign-in screens) the
 * formatters keep the platform's previous format "1'234.56" (ASCII apostrophe); the public site
 * has its own formatting (site/format.ts).
 *
 * Rules for new code: every amount, percentage and number shown to the investor goes through this
 * module (formatMoneyMinor, formatMoneyLabel, formatRateBps, formatPercent, formatDecimal); every
 * typed amount goes through parseMoneyInputToMinorUnits, and amounts written back into an input
 * use formatAmountInput. Formatting never changes a value: integer minor units, no float maths.
 */
import { useCallback, useEffect, useSyncExternalStore } from "react";

import { getLocale, t } from "../i18n";

const currencyMinorUnitDecimals: Record<string, number> = {
  BHD: 3,
  CHF: 2,
  EUR: 2,
  GBP: 2,
  JPY: 0,
  KWD: 3,
  USD: 2
};

export function minorUnitDecimalsForCurrency(currency: string | null | undefined) {
  if (!currency) return 2;
  return currencyMinorUnitDecimals[currency.toUpperCase()] ?? 2;
}

/** The investor's number format (U33-DEC-32). */
export type NumberFormat = "european" | "swiss";
/** "legacy": the platform's previous format, kept outside the investor area. */
export type NumberFormatStyle = NumberFormat | "legacy";

export const NUMBER_FORMATS: readonly NumberFormat[] = ["european", "swiss"];
export const DEFAULT_NUMBER_FORMAT: NumberFormat = "european";
const NUMBER_FORMAT_STORAGE_KEY = "banxum.numberFormat";

const SEPARATORS: Record<NumberFormatStyle, { group: string; decimal: string }> = {
  european: { group: ".", decimal: "," },
  swiss: { group: "\u2019", decimal: "." },
  legacy: { group: "'", decimal: "." }
};

/** The separators of a style: { group, decimal }. */
export function numberFormatSeparators(style: NumberFormatStyle = activeNumberFormatStyle()) {
  return SEPARATORS[style];
}

function isNumberFormat(value: unknown): value is NumberFormat {
  return value === "european" || value === "swiss";
}

/** The saved preference, or the default when nothing (or nothing valid) is saved. */
export function readNumberFormatPreference(): NumberFormat {
  try {
    const saved = window.localStorage.getItem(NUMBER_FORMAT_STORAGE_KEY);
    return isNumberFormat(saved) ? saved : DEFAULT_NUMBER_FORMAT;
  } catch {
    return DEFAULT_NUMBER_FORMAT;
  }
}

let preference: NumberFormat | null = null;
// The investor area's scope: mounted scope components, plus a flag set by the first render (before
// its effect runs), so that render already uses the investor's format.
let mountedScopes = 0;
let renderedScope = false;
const formatListeners = new Set<() => void>();

function currentPreference(): NumberFormat {
  if (preference === null) preference = readNumberFormatPreference();
  return preference;
}

function notifyFormatListeners() {
  formatListeners.forEach((listener) => listener());
}

/** Saves the investor's choice in this browser; the Preferences tab also saves it in the account (U33-DEC-32). */
export function setNumberFormatPreference(format: NumberFormat) {
  if (!isNumberFormat(format)) return;
  preference = format;
  try {
    window.localStorage.setItem(NUMBER_FORMAT_STORAGE_KEY, format);
  } catch {
    // The choice still applies for this visit when storage is unavailable.
  }
  notifyFormatListeners();
}

/** The style the formatters use when no explicit style is passed. */
export function activeNumberFormatStyle(): NumberFormatStyle {
  return mountedScopes > 0 || renderedScope ? currentPreference() : "legacy";
}

function subscribeFormat(listener: () => void) {
  formatListeners.add(listener);
  return () => {
    formatListeners.delete(listener);
  };
}

/** The investor's number format and a setter; re-renders the caller when it changes. */
export function useNumberFormat(): { format: NumberFormat; setFormat: (format: NumberFormat) => void } {
  const format = useSyncExternalStore(subscribeFormat, currentPreference, currentPreference);
  const setFormat = useCallback((next: NumberFormat) => setNumberFormatPreference(next), []);
  return { format, setFormat };
}

/**
 * Makes the investor's format the active one while the calling component (the investor shell) is
 * mounted, and re-renders it when the format changes so every screen below shows the new format.
 * Entered during render as well, so the first render already uses the investor's format.
 */
export function useNumberFormatScope(): NumberFormat {
  const { format } = useNumberFormat();
  renderedScope = true;
  useEffect(() => {
    mountedScopes += 1;
    return () => {
      mountedScopes = Math.max(0, mountedScopes - 1);
      if (mountedScopes === 0) renderedScope = false;
    };
  }, []);
  return format;
}

/** Test helper: resets the cached preference and the scope. */
export function resetNumberFormatForTests() {
  preference = null;
  mountedScopes = 0;
  renderedScope = false;
  notifyFormatListeners();
}

function groupThousands(digits: string, group: string) {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, group);
}

/**
 * Integer minor units -> "1.234,56" (European), "1’234.56" (Swiss) or "1'234.56" (legacy, outside
 * the investor area), with the currency's minor-unit precision unless `displayDecimals` is given.
 * The last argument picks a style explicitly (tests, previews); by default the active one is used.
 */
export function formatMoneyMinor(
  amountMinor: number | null | undefined,
  currencyOrDecimals: string | number = 2,
  displayDecimals?: number,
  style: NumberFormatStyle = activeNumberFormatStyle()
) {
  if (amountMinor === null || amountMinor === undefined || Number.isNaN(amountMinor)) {
    return "-";
  }
  const { group, decimal } = SEPARATORS[style];
  const minorUnitDecimals =
    typeof currencyOrDecimals === "string" ? minorUnitDecimalsForCurrency(currencyOrDecimals) : 2;
  const decimals =
    typeof currencyOrDecimals === "number"
      ? currencyOrDecimals
      : (displayDecimals ?? minorUnitDecimals);

  if (Number.isInteger(amountMinor) && decimals >= minorUnitDecimals) {
    // Exact path for integer minor units: no float division.
    const negative = amountMinor < 0;
    const digits = String(Math.abs(amountMinor)).padStart(minorUnitDecimals + 1, "0");
    const whole = minorUnitDecimals > 0 ? digits.slice(0, -minorUnitDecimals) : digits;
    const fraction = (minorUnitDecimals > 0 ? digits.slice(-minorUnitDecimals) : "").padEnd(decimals, "0");
    return `${negative ? "-" : ""}${groupThousands(whole, group)}${decimals > 0 ? `${decimal}${fraction}` : ""}`;
  }
  const fixed = Math.abs(amountMinor / 10 ** minorUnitDecimals).toFixed(decimals);
  const [whole, fraction] = fixed.split(".");
  const negative = amountMinor < 0 && Number(fixed) !== 0;
  return `${negative ? "-" : ""}${groupThousands(whole, group)}${fraction ? `${decimal}${fraction}` : ""}`;
}

/** "EUR 1.234,56": the currency code first, then the amount in the currency's minor units. */
export function formatMoneyLabel(currency: string, amountMinor: number | null | undefined, style?: NumberFormatStyle) {
  return `${currency} ${formatMoneyMinor(amountMinor, currency, undefined, style)}`;
}

/** Whole-unit amounts such as share capital or limits: "CHF 1.100.000". */
export function formatWholeAmount(currency: string, amountMinor: number, style?: NumberFormatStyle) {
  return `${currency} ${formatMoneyMinor(amountMinor, currency, 0, style)}`;
}

/** An amount written back into an amount field: no grouping, the convention's decimal sign ("1500,00"). */
export function formatAmountInput(amountMinor: number, currency: string, style: NumberFormatStyle = activeNumberFormatStyle()) {
  const decimals = minorUnitDecimalsForCurrency(currency);
  const negative = amountMinor < 0;
  const digits = String(Math.abs(Math.round(amountMinor))).padStart(decimals + 1, "0");
  const whole = decimals > 0 ? digits.slice(0, -decimals) : digits;
  const fraction = decimals > 0 ? digits.slice(-decimals) : "";
  return `${negative ? "-" : ""}${whole}${fraction ? `${SEPARATORS[style].decimal}${fraction}` : ""}`;
}

/**
 * A plain number with a fixed number of decimals in the active convention: 1234.5 -> "1.234,5".
 * For display values that are not money in minor units (ratios, multipliers, counts).
 */
export function formatDecimal(value: number, decimals = 2, style: NumberFormatStyle = activeNumberFormatStyle()) {
  if (!Number.isFinite(value)) return "-";
  const { group, decimal } = SEPARATORS[style];
  const fixed = Math.abs(value).toFixed(decimals);
  const [whole, fraction] = fixed.split(".");
  const negative = value < 0 && Number(fixed) !== 0;
  return `${negative ? "-" : ""}${groupThousands(whole, group)}${fraction ? `${decimal}${fraction}` : ""}`;
}

/** A percentage from a number of percent: 12.5 -> "12,5%" (decimals default 1). */
export function formatPercent(value: number, decimals = 1, style?: NumberFormatStyle) {
  if (!Number.isFinite(value)) return "-";
  return `${formatDecimal(value, decimals, style)}%`;
}

// Rates are stored in basis points. Show one decimal when the rate is a whole tenth of a percent
// (800 bps = 8,0%, 750 bps = 7,5%) and two otherwise (845 bps = 8,45%), using integer maths only.
export function formatRateBps(bps: number, style: NumberFormatStyle = activeNumberFormatStyle()) {
  if (!Number.isFinite(bps)) return "-";
  const rounded = Math.round(bps);
  const negative = rounded < 0;
  const absolute = Math.abs(rounded);
  const whole = Math.floor(absolute / 100);
  const hundredths = absolute % 100;
  const fraction = hundredths % 10 === 0 ? String(hundredths / 10) : String(hundredths).padStart(2, "0");
  return `${negative ? "-" : ""}${groupThousands(String(whole), SEPARATORS[style].group)}${SEPARATORS[style].decimal}${fraction}%`;
}

/** The design's month abbreviations (B.date: "Sep", never the "Sept" of newer browsers). */
export const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** The design's German month abbreviations (U33-DEC-31: "4. Okt. 2026"). */
const GERMAN_SHORT_MONTHS = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."];

function isGerman() {
  return getLocale().startsWith("de");
}

/** "Oct" (English) or "Okt." (German) for a month number 1-12. */
export function shortMonthName(month: number) {
  return (isGerman() ? GERMAN_SHORT_MONTHS : SHORT_MONTHS)[month - 1] ?? "";
}

/** "4 Oct" or "4. Okt." for a day and a month number. */
export function formatDayMonth(day: number, month: number) {
  return isGerman() ? `${day}. ${shortMonthName(month)}` : `${day} ${shortMonthName(month)}`;
}

function validDate(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "4 Oct 2026" (German "4. Okt. 2026") in Zurich time (design B.date). */
export function formatDate(value: string | null | undefined) {
  const date = validDate(value);
  if (!date) return "-";
  const parts = zurichParts(date);
  return `${formatDayMonth(parts.day, parts.month)} ${parts.year}`;
}

/** "4 Oct" (German "4. Okt.") in Zurich time (design B.dateShort). */
export function formatDateShort(value: string | null | undefined) {
  const date = validDate(value);
  if (!date) return "-";
  const parts = zurichParts(date);
  return formatDayMonth(parts.day, parts.month);
}

/** "4 Oct 2026, 14:30" (German "4. Okt. 2026, 14:30") in Zurich time (design B.dateTime). */
export function formatDateTime(value: string | null | undefined) {
  const date = validDate(value);
  if (!date) return "-";
  const parts = zurichParts(date);
  const two = (number: number) => String(number).padStart(2, "0");
  return `${formatDayMonth(parts.day, parts.month)} ${parts.year}, ${two(parts.hour)}:${two(parts.minute)}`;
}

export function zurichDateKey(value: string | Date | null | undefined) {
  if (!value) return "";
  const date = typeof value === "string" ? new Date(value) : value;
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Zurich"
  }).formatToParts(date);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function safeMetadataCategory(metadata: unknown) {
  if (metadata && typeof metadata === "object" && "category" in metadata) {
    const value = (metadata as { category?: unknown }).category;
    return typeof value === "string" ? value : "principal";
  }
  return "principal";
}

// Characters that can only be thousands separators, in every convention: apostrophes (the app
// prints ’ or '), and spaces (also no-break and thin spaces) that people type or paste.
const NEUTRAL_GROUP = "'\u2019\u2018\u02bc \u00a0\u2009\u202f";
type Convention = "european" | "swiss" | "english";
const CONVENTIONS: Record<Convention, { group: string; decimal: string }> = {
  european: { group: `.${NEUTRAL_GROUP}`, decimal: "," },
  swiss: { group: NEUTRAL_GROUP, decimal: "." },
  // Pasted from English-language sources: "1,234.56". Only used when it is the single reading.
  english: { group: `,${NEUTRAL_GROUP}`, decimal: "." }
};
const AMOUNT_EXAMPLE: Record<NumberFormatStyle, string> = { european: "1.500,50", swiss: "1\u2019500.50", legacy: "1'500.50" };
const THOUSAND_EXAMPLE: Record<NumberFormatStyle, string> = { european: "1.000", swiss: "1\u2019000", legacy: "1'000" };

type Reading = { integer: string; fraction: string };

function escapeClass(chars: string) {
  return chars.replace(/[\\\]^-]/g, "\\$&");
}

/** The amount as written in one convention, or null when the text is not valid in it. */
function readAs(text: string, convention: Convention): Reading | null {
  const { group, decimal } = CONVENTIONS[convention];
  const allowed = new RegExp(`^[0-9${escapeClass(group + decimal)}]+$`);
  if (!allowed.test(text)) return null;
  const parts = text.split(decimal);
  if (parts.length > 2) return null;
  const [integerText, fraction = ""] = parts;
  if (!/^\d*$/.test(fraction)) return null;
  let integer = integerText;
  if (new RegExp(`[${escapeClass(group)}]`).test(integerText)) {
    // Separators must sit between complete groups of three digits: 1.234.567, 12 345.
    if (!new RegExp(`^\\d{1,3}(?:[${escapeClass(group)}]\\d{3})+$`).test(integerText)) return null;
    integer = integerText.replace(new RegExp(`[${escapeClass(group)}]`, "g"), "");
  }
  if (!/^\d*$/.test(integer)) return null;
  if (integer === "" && fraction === "") return null;
  return { integer: integer === "" ? "0" : integer, fraction };
}

function readingKey(reading: Reading) {
  return `${reading.integer.replace(/^0+(?=\d)/, "")}.${reading.fraction.replace(/0+$/, "")}`;
}

export type ParsedMoneyInput = { amountMinor: number; error: string | undefined; ambiguous?: boolean };

/**
 * Parses a typed amount into integer minor units, without float maths (U33-DEC-32).
 *
 * The investor's convention decides: European "1.500,50" / "1500,50", Swiss "1’500.50" / "1500.50".
 * Spaces and apostrophes are always thousands separators. A value that is not valid in the
 * selected convention is accepted only when every other reading gives the same amount ("1500.50"
 * typed with the European format, "1,234.56" pasted from an English source); when the readings
 * differ ("1,234" with the Swiss format: 1.234 or 1234) the amount is refused with a hint instead
 * of being guessed. More decimals than the currency allows are refused, never rounded.
 */
export function parseMoneyInputToMinorUnits(
  input: string,
  currency: string,
  style: NumberFormatStyle = activeNumberFormatStyle()
): ParsedMoneyInput {
  const text = input.trim();
  const minorUnitDecimals = minorUnitDecimalsForCurrency(currency);
  if (text === "") {
    return { amountMinor: 0, error: undefined };
  }
  const selected: Convention = style === "european" ? "european" : "swiss";
  let reading = readAs(text, selected);
  if (!reading) {
    const others = (["european", "swiss", "english"] as Convention[])
      .filter((convention) => convention !== selected)
      .map((convention) => readAs(text, convention))
      .filter((item): item is Reading => item !== null);
    const distinct = new Map(others.map((item) => [readingKey(item), item]));
    if (distinct.size > 1) {
      return {
        amountMinor: 0,
        ambiguous: true,
        error: t("This amount can be read in two ways. Write it in your number format, for example {example}.", { example: AMOUNT_EXAMPLE[style] })
      };
    }
    reading = distinct.size === 1 ? [...distinct.values()][0] : null;
  }
  if (!reading) {
    return { amountMinor: 0, error: t("Enter a valid amount.") };
  }
  if (reading.fraction.length > minorUnitDecimals) {
    const base =
      minorUnitDecimals === 0
        ? t("{currency} amounts must be whole units.", { currency })
        : t("{currency} amounts support at most {count} decimal places.", { currency, count: minorUnitDecimals });
    // "1,000" (European) or "1.000" (Swiss) means one thousand to some people: say how to write it.
    const thousandsHint = reading.fraction.length === 3 ? ` ${t("Write thousands as {example}.", { example: THOUSAND_EXAMPLE[style] })}` : "";
    return { amountMinor: 0, error: `${base}${thousandsHint}` };
  }
  const fractionPart = reading.fraction.padEnd(minorUnitDecimals, "0");
  const minorString = `${reading.integer}${fractionPart}`.replace(/^0+(?=\d)/, "") || "0";
  const amountMinor = Number(minorString);
  if (!Number.isSafeInteger(amountMinor)) {
    return { amountMinor: 0, error: t("Amount is too large.") };
  }
  return { amountMinor, error: undefined };
}

// Business dates and months are Europe/Zurich calendar values, never the browser's time zone.
// Callers pass the platform time (`as_of`, `platform_business_date`) instead of the browser clock.
const zurichPartsFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  hour: "2-digit",
  hourCycle: "h23",
  minute: "2-digit",
  month: "2-digit",
  second: "2-digit",
  timeZone: "Europe/Zurich",
  weekday: "short",
  year: "numeric"
});

export function zurichParts(value: string | Date) {
  const date = typeof value === "string" ? new Date(value) : value;
  const parts = zurichPartsFormatter.formatToParts(date);
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return {
    year: Number(part("year")),
    month: Number(part("month")),
    day: Number(part("day")),
    hour: Number(part("hour")),
    minute: Number(part("minute")),
    second: Number(part("second")),
    weekday: part("weekday")
  };
}

/** "YYYY-MM-DD" from a date key or an instant; a plain date key is returned unchanged. */
export function businessDateKey(value: string | Date | null | undefined) {
  if (!value) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  return zurichDateKey(value);
}

/** "YYYY-MM" of the Zurich calendar month, shifted by `offset` months. */
export function zurichMonthKey(value: string | Date, offset = 0) {
  const [year, month] = businessDateKey(value).split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1 + offset, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** Month name for a "YYYY-MM" or "YYYY-MM-DD" key, independent of the browser time zone. */
export function monthLabelFromKey(key: string, options: Intl.DateTimeFormatOptions = { month: "long" }) {
  const [year, month] = key.split("-").map(Number);
  if (options.month === "short" && !options.year && !options.day) return shortMonthName(month);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString(isGerman() ? "de-CH" : "en-GB", { ...options, timeZone: "UTC" });
}

/** Whole calendar days from one business date to another (negative when `to` is earlier). */
export function daysBetweenDateKeys(from: string, to: string) {
  const fromTime = Date.parse(`${from}T00:00:00Z`);
  const toTime = Date.parse(`${to}T00:00:00Z`);
  if (!Number.isFinite(fromTime) || !Number.isFinite(toTime)) return null;
  return Math.round((toTime - fromTime) / 86_400_000);
}

/** Saturday or Sunday in Zurich at the given platform time. */
export function isZurichWeekendAt(value: string | Date) {
  const weekday = zurichParts(value).weekday;
  return weekday === "Sat" || weekday === "Sun";
}

/** "YYYY-MM-DDTHH:mm" Zurich wall time of an instant, for datetime-local inputs. */
export function zurichDateTimeInputValue(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const parts = zurichParts(date);
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${parts.year}-${pad(parts.month)}-${pad(parts.day)}T${pad(parts.hour)}:${pad(parts.minute)}`;
}

/** UTC ISO instant of a Zurich wall time "YYYY-MM-DDTHH:mm" (DST-aware, browser time zone ignored). */
export function zurichDateTimeInputToIso(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return "";
  const [, year, month, day, hour, minute] = match.map(Number);
  const wallClockAsUtc = Date.UTC(year, month - 1, day, hour, minute);
  let instant = wallClockAsUtc;
  // Two passes settle the Zurich offset, also next to a daylight-saving change.
  for (let pass = 0; pass < 2; pass += 1) {
    const parts = zurichParts(new Date(instant));
    const shownAsUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
    instant += wallClockAsUtc - shownAsUtc;
  }
  return new Date(instant).toISOString();
}

/** Readable text for an API enum value: "penalty_mode" -> "Penalty mode". */
export function humanizeEnum(value: string | null | undefined) {
  if (!value) return "";
  const words = value.replace(/[_.-]+/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** "1 document", "2 documents". */
export function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}
