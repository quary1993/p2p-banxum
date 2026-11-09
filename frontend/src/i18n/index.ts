// IP of Webby-Soft SRL.
/*
 * Message catalog for the U33 interface (plan/22 U33-DEC-31).
 *
 * Gettext style: the English text is the key. `t("Available balance")` returns the text in the
 * active language, or the English text when no translation exists. Placeholders use braces:
 * `t("Welcome back, {name}", { name })`. English is the only active language until Phase 17.8
 * adds de-CH (investor area) and DE/FR (public site); the design's German dictionary keys are the
 * same English strings, so it can be imported without touching the components again.
 *
 * Rules for new UI code:
 * - Wrap every user-facing string in t() (labels, buttons, headings, messages, aria-labels).
 * - Keep one sentence per key; do not build sentences from fragments.
 * - Never put amounts or dates in the key: pass them as placeholders, formatted by format.ts.
 */
import { useSyncExternalStore } from "react";

export type Locale = "en" | "de-CH" | "de" | "fr";
export type Messages = Readonly<Record<string, string>>;
export type MessageVars = Readonly<Record<string, string | number>>;

const catalogs = new Map<Locale, Messages>();
let activeLocale: Locale = "en";
const listeners = new Set<() => void>();

/** Registers (or replaces) the translations of one language. English needs no catalog. */
export function registerMessages(locale: Locale, messages: Messages) {
  catalogs.set(locale, messages);
  if (locale === activeLocale) notify();
}

export function getLocale(): Locale {
  return activeLocale;
}

export function setLocale(locale: Locale) {
  if (locale === activeLocale) return;
  activeLocale = locale;
  if (typeof document !== "undefined") document.documentElement.lang = locale;
  notify();
}

function notify() {
  listeners.forEach((listener) => listener());
}

function interpolate(text: string, vars?: MessageVars) {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match
  );
}

/** Translates one English message. */
export function t(english: string, vars?: MessageVars): string {
  const translated = activeLocale === "en" ? undefined : catalogs.get(activeLocale)?.[english];
  return interpolate(translated ?? english, vars);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Re-renders the calling component when the language changes; returns t. */
export function useT(): typeof t {
  useSyncExternalStore(subscribe, getLocale, getLocale);
  return t;
}
