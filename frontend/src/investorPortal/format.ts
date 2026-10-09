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

// Money is shown one way everywhere: Swiss grouping with an ASCII apostrophe, a point before the
// minor units, and the currency's own minor-unit precision. The grouping is done here, not by the
// browser's ICU data, so every browser (and the test runner) prints the same text.
function groupThousands(digits: string) {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, "'");
}

export function formatMoneyMinor(
  amountMinor: number | null | undefined,
  currencyOrDecimals: string | number = 2,
  displayDecimals?: number
) {
  if (amountMinor === null || amountMinor === undefined || Number.isNaN(amountMinor)) {
    return "-";
  }
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
    return `${negative ? "-" : ""}${groupThousands(whole)}${decimals > 0 ? `.${fraction}` : ""}`;
  }
  const fixed = Math.abs(amountMinor / 10 ** minorUnitDecimals).toFixed(decimals);
  const [whole, fraction] = fixed.split(".");
  const negative = amountMinor < 0 && Number(fixed) !== 0;
  return `${negative ? "-" : ""}${groupThousands(whole)}${fraction ? `.${fraction}` : ""}`;
}

/** "CHF 1'234.56": the currency code first, then the amount in the currency's minor units. */
export function formatMoneyLabel(currency: string, amountMinor: number | null | undefined) {
  return `${currency} ${formatMoneyMinor(amountMinor, currency)}`;
}

/** Whole-unit amounts such as share capital or limits: "CHF 1'100'000". */
export function formatWholeAmount(currency: string, amountMinor: number) {
  return `${currency} ${formatMoneyMinor(amountMinor, currency, 0)}`;
}

// Rates are stored in basis points. Show one decimal when the rate is a whole tenth of a percent
// (800 bps = 8.0%, 750 bps = 7.5%) and two otherwise (845 bps = 8.45%), using integer maths only.
export function formatRateBps(bps: number) {
  if (!Number.isFinite(bps)) return "-";
  const rounded = Math.round(bps);
  const negative = rounded < 0;
  const absolute = Math.abs(rounded);
  const whole = Math.floor(absolute / 100);
  const hundredths = absolute % 100;
  const fraction = hundredths % 10 === 0 ? String(hundredths / 10) : String(hundredths).padStart(2, "0");
  return `${negative ? "-" : ""}${whole}.${fraction}%`;
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "Europe/Zurich"
  });
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Zurich"
  });
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

// Thousands separators the app itself prints (formatMoneyMinor gives ’ or ' and a
// thin space depending on the browser) or that people type: apostrophes and spaces.
const THOUSANDS_SEPARATORS = /['\u2019\u2018\u02bc\s]/g;

/**
 * Parse a typed amount into integer minor units, without float maths.
 *
 * Accepted: "1500.50", "1500,50" (decimal comma), "1'500.50", "1’500.50",
 * "1 500,50". A comma is a decimal sign, never a thousands separator, so
 * "1,000" is 1.000 and is refused for a 2-decimal currency with a hint.
 */
export function parseMoneyInputToMinorUnits(input: string, currency: string) {
  const compact = input.trim().replace(THOUSANDS_SEPARATORS, "");
  const minorUnitDecimals = minorUnitDecimalsForCurrency(currency);
  const usedComma = compact.includes(",");

  if (compact === "") {
    return { amountMinor: 0, error: undefined };
  }

  if (usedComma && compact.includes(".")) {
    // "1,000.50" or "1.000,50": one sign must be a thousands separator. Do not guess.
    return {
      amountMinor: 0,
      error: "Enter a valid amount. Use one decimal sign and ' for thousands, for example 1'500.50."
    };
  }
  // Only a single comma is a decimal sign; "1,000,000" stays invalid.
  const normalized = (compact.match(/,/g) ?? []).length === 1 ? compact.replace(",", ".") : compact;

  if (!/^\d+(?:\.\d*)?$/.test(normalized) && !/^\.\d+$/.test(normalized)) {
    return { amountMinor: 0, error: "Enter a valid amount." };
  }

  const [rawInteger, rawFraction = ""] = normalized.split(".");
  if (rawFraction.length > minorUnitDecimals) {
    const base =
      minorUnitDecimals === 0
        ? `${currency} amounts must be whole units.`
        : `${currency} amounts support at most ${minorUnitDecimals} decimal places.`;
    return {
      amountMinor: 0,
      // "1,000" means one thousand to some people: say how to write it.
      error: usedComma ? `${base} A comma is the decimal sign. Write thousands as 1'000.` : base
    };
  }

  const integerPart = rawInteger === "" ? "0" : rawInteger;
  const fractionPart = rawFraction.padEnd(minorUnitDecimals, "0");
  const minorString = `${integerPart}${fractionPart}`.replace(/^0+(?=\d)/, "") || "0";
  const amountMinor = Number(minorString);

  if (!Number.isSafeInteger(amountMinor)) {
    return { amountMinor: 0, error: "Amount is too large." };
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
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString("en-GB", { ...options, timeZone: "UTC" });
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
