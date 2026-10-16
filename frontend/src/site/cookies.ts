// IP of Webby-Soft SRL.
// The visitor's cookie choice (design: state.cookies), kept in localStorage under
// "bxm-site-cookies" as { necessary: true, measure, date }.
import { useSyncExternalStore } from "react";

import { siteToday } from "./format";

export const SITE_COOKIES_KEY = "bxm-site-cookies";

export type SiteCookieChoice = { necessary: true; measure: boolean; date: string };

const listeners = new Set<() => void>();
// Used only when localStorage is blocked: the choice then lasts for this page view.
let memoryChoice: string | null = null;
let cached: { raw: string | null; value: SiteCookieChoice | null } = { raw: null, value: null };

function readRaw() {
  try {
    return window.localStorage.getItem(SITE_COOKIES_KEY);
  } catch {
    return memoryChoice;
  }
}

function parseChoice(raw: string | null): Partial<SiteCookieChoice> | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Partial<SiteCookieChoice> | null;
  } catch {
    return null;
  }
}

export function readCookieChoice(): SiteCookieChoice | null {
  const raw = readRaw();
  if (raw === cached.raw) return cached.value;
  const parsed = parseChoice(raw);
  const value: SiteCookieChoice | null =
    parsed && typeof parsed === "object"
      ? { necessary: true, measure: Boolean(parsed.measure), date: String(parsed.date ?? "") }
      : null;
  cached = { raw, value };
  return value;
}

export function saveCookieChoice(measure: boolean) {
  const raw = JSON.stringify({ necessary: true, measure, date: siteToday() });
  memoryChoice = raw;
  try {
    window.localStorage.setItem(SITE_COOKIES_KEY, raw);
  } catch {
    // Storage blocked: keep the choice in memory only.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The saved cookie choice, or null while the visitor has not answered the notice. */
export function useCookieChoice() {
  return useSyncExternalStore(subscribe, readCookieChoice, () => null);
}
