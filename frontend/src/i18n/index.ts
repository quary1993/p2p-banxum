// IP of Webby-Soft SRL.
/*
 * Message catalog for the U33 interface (plan/22 U33-DEC-31).
 *
 * Gettext style: the English text is the key. `t("Available balance")` returns the text in the
 * active language, or the English text when no translation exists. Placeholders use braces:
 * `t("Welcome back, {name}", { name })`. The investor area has English and Swiss Standard German
 * (language.ts, locales/de-CH.ts); the public site stays English until its DE/FR texts exist.
 *
 * Rules for new UI code:
 * - Wrap every user-facing string in t() (labels, buttons, headings, messages, aria-labels).
 * - Keep one sentence per key; do not build sentences from fragments.
 * - Never put amounts or dates in the key: pass them as placeholders, formatted by format.ts.
 * - A label kept in a list or a function and translated later with t(label) needs its German text
 *   in locales/de-CH.drafts.json too; catalog.test.ts only finds the literal t("...") calls.
 * - When one English text needs two German texts, prefix a context: t("date|To") shows "To".
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

// "context|English": the same English text with two meanings ("Security" of a loan, the account's
// "Security" settings). English shows the text after "|"; the catalog has an entry per context.
const CONTEXT_KEY = /^([a-z][a-z-]*)\|([\s\S]+)$/;

/** Translates one English message. */
export function t(english: string, vars?: MessageVars): string {
  const translated = activeLocale === "en" ? undefined : catalogs.get(activeLocale)?.[english];
  return interpolate(translated ?? CONTEXT_KEY.exec(english)?.[2] ?? english, vars);
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
