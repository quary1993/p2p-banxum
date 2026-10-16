// IP of Webby-Soft SRL.
/*
 * Formatting of the public site, ported from the design's core.js (English number format:
 * 1,234.56, a real minus sign "−", dates like "23 Sep 2026").
 *
 * The design formats amounts in major units (500 = CHF 500.00). The API sends integer minor
 * units: use the *Minor helpers for those, which format with integer arithmetic only. The
 * major-unit helpers (num, money, plan...) are for display calculators, exactly like the design.
 */
import { zurichDateKey } from "../investorPortal/format";
import { platformTodayKey } from "../investorPortal/platformClock";
import { siteFixtureToday } from "./siteFixtures";
import { isFixturePreview } from "../investorPortal/data";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December"
];
const GROUP = ",";
const DECIMAL = ".";

/** The platform default minimum investment in CHF or EUR (major units; a superadmin setting, 2026-10-16). */
export const SITE_MINIMUM = 1000;
/** Daily interest basis of the loans (actual/365). */
export const DAY_BASIS = 365;

function group(int: string) {
  return int.replace(/\B(?=(\d{3})+(?!\d))/g, GROUP);
}

/** 1234.5 -> "1,234.50" (decimals default 2); negative numbers get "−". */
export function num(n: number, decimals = 2) {
  const neg = n < 0;
  const fixed = Math.abs(n).toFixed(decimals);
  const [int, frac] = fixed.split(".");
  return (neg ? "−" : "") + group(int) + (frac ? DECIMAL + frac : "");
}

/** "CHF 1,234.50". */
export function money(n: number, currency: string, decimals?: number) {
  return `${currency} ${num(n, decimals)}`;
}

/** "CHF 1.25m", "CHF 300k", or the amount without decimals below 10,000. */
export function moneyShort(n: number, currency: string) {
  if (Math.abs(n) >= 1000000) return `${currency} ${num(n / 1000000, 2)}m`;
  if (Math.abs(n) >= 10000) return `${currency} ${num(n / 1000, 0)}k`;
  return money(n, currency, 0);
}

/** 7.5 -> "7.5%" (decimals default 1). */
export function pct(n: number, decimals = 1) {
  return num(n, decimals) + "%";
}

/** Integer minor units -> "1,234.50", exact (no floating point). */
export function numMinor(minor: number) {
  const value = Math.round(minor);
  const neg = value < 0;
  const abs = Math.abs(value);
  const int = Math.floor(abs / 100);
  const cents = abs % 100;
  return (neg ? "−" : "") + group(String(int)) + DECIMAL + String(cents).padStart(2, "0");
}

/** Integer minor units -> "CHF 1,234.50". */
export function moneyMinor(minor: number, currency: string) {
  return `${currency} ${numMinor(minor)}`;
}

/** Integer minor units -> the short form of moneyShort ("CHF 300k"). Display only. */
export function moneyShortMinor(minor: number, currency: string) {
  return moneyShort(minor / 100, currency);
}

/** Interest in basis points -> "7.5%". */
export function pctBps(bps: number, decimals = 1) {
  return pct(bps / 100, decimals);
}

function parseDate(s: string) {
  const [y, m, d] = s.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function iso(date: Date) {
  return date.toISOString().slice(0, 10);
}

export function addDays(s: string, days: number) {
  const d = parseDate(s);
  d.setUTCDate(d.getUTCDate() + days);
  return iso(d);
}

export function addMonths(s: string, months: number) {
  const d = parseDate(s);
  const day = d.getUTCDate();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + months);
  const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  d.setUTCDate(Math.min(day, last));
  return iso(d);
}

/** Whole days from date a to date b ("YYYY-MM-DD"). */
export function daysBetween(a: string, b: string) {
  return Math.round((parseDate(b).getTime() - parseDate(a).getTime()) / 86400000);
}

/** "2026-09-23" -> "23 Sep 2026". */
export function date(s: string) {
  const d = parseDate(s);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "2026-09-23" -> "23 Sep". */
export function dateShort(s: string) {
  const d = parseDate(s);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** "2026-09-23" -> "September 2026". */
export function monthYear(s: string) {
  const d = parseDate(s);
  return `${MONTHS_LONG[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** An amount field's text ("1,234.56", "1'234.56", "1 234") -> number, or NaN. */
export function parseAmount(value: unknown) {
  let v = String(value == null ? "" : value)
    .trim()
    .replace(/['’\s]/g, "");
  v = v.split(GROUP).join("");
  v = v.replace(/[^\d.]/g, "");
  return v ? Number(v) : NaN;
}

/** The text an amount field shows for a number ("" for no number). */
export function amountValue(n: number | null | undefined) {
  return n || n === 0 ? num(n) : "";
}

/** Keeps only the characters an amount field accepts (the design's input filter). */
export function cleanAmountInput(value: string) {
  return value.replace(/[^\d.,'’\s]/g, "");
}

export function round2(x: number) {
  return Math.round(x * 100) / 100;
}

/**
 * Today for the site ("YYYY-MM-DD", Europe/Zurich): the platform business date when the app
 * knows it. The preview uses the design's date (2026-09-23), so it shows the same "days left".
 */
export function siteToday() {
  if (isFixturePreview && siteFixtureToday) return siteFixtureToday;
  return platformTodayKey();
}

/** A date-time from the API -> its Zurich date key. */
export function dateKey(value: string | null | undefined) {
  if (!value) return "";
  return value.length === 10 ? value : zurichDateKey(value);
}

export type PlanRepayment = "annuity" | "interest-only" | "bullet";

export type PlanRow = {
  due: string;
  days: number;
  principal: number;
  interest: number;
  total: number;
  balance: number;
};

/**
 * The design's repayment plan (core.js plan()), used by the interest calculators only:
 * interest counted daily on the outstanding principal (actual/365), paid on the monthly dates;
 * an annuity keeps the same instalment and the last one clears the balance.
 */
export function plan(terms: { rate: number; term: number; repayment: PlanRepayment }, amount: number, start: string) {
  const n = terms.term;
  const yearly = terms.rate / 100;
  const r = yearly / 12;
  const rows: PlanRow[] = [];
  let balance = amount;
  const annuity = r > 0 ? (amount * r) / (1 - Math.pow(1 + r, -n)) : amount / n;
  for (let k = 1; k <= n; k++) {
    const due = addMonths(start, k);
    const days = daysBetween(addMonths(start, k - 1), due);
    let interest: number;
    let principal: number;
    if (terms.repayment === "annuity") {
      interest = round2((balance * yearly * days) / DAY_BASIS);
      principal = k === n ? balance : Math.min(balance, round2(annuity - interest));
    } else if (terms.repayment === "interest-only") {
      interest = round2((amount * yearly * days) / DAY_BASIS);
      principal = k === n ? amount : 0;
    } else {
      if (k < n) continue;
      interest = round2((amount * yearly * daysBetween(start, due)) / DAY_BASIS);
      principal = amount;
    }
    balance = round2(balance - principal);
    rows.push({ due, days, principal, interest, total: round2(principal + interest), balance });
  }
  return rows;
}
