// IP of Webby-Soft SRL.
/*
 * Interface language of the investor platform (plan/22 U33-DEC-31): English or Swiss Standard
 * German (de-CH). English is the default on the first visit; the choice is kept in this browser
 * (`banxum-investor-language`, the design's key) and saved in the account, which wins after sign-in.
 * `?lang=de` / `?lang=en` in the address (a link from the public site) sets the choice, so a
 * visitor of the German public site continues in German.
 *
 * Only the investor area uses the choice. The public site and the admin console stay in English
 * until their own languages exist (public DE/FR is a later step), so `setInvestorScope` switches
 * the active catalog when the visitor moves between them. Changing the language re-renders the
 * page in place: the route, the state and the entered data stay.
 */
import { useSyncExternalStore } from "react";

import { registerMessages, setLocale, type Locale, type Messages } from "./index";

export type InterfaceLanguage = "en" | "de-CH";

export const INTERFACE_LANGUAGES: ReadonlyArray<{ value: InterfaceLanguage; label: string; short: string }> = [
  { value: "en", label: "English", short: "EN" },
  { value: "de-CH", label: "Deutsch", short: "DE" }
];

export const LANGUAGE_STORAGE_KEY = "banxum-investor-language";
// Set while a choice made before sign-in (or with ?lang=) is not yet saved in the account.
const UNSAVED_CHOICE_KEY = "banxum-investor-language-unsaved";

const catalogLoaders: Partial<Record<Locale, () => Promise<Messages>>> = {
  "de-CH": () => import("./locales/de-CH").then((module) => module.default)
};
const loadedCatalogs = new Set<Locale>(["en"]);
const listeners = new Set<() => void>();

/** "de", "de-CH" and "de-ch" mean Swiss Standard German; anything unknown is null. */
export function parseInterfaceLanguage(value: string | null | undefined): InterfaceLanguage | null {
  const normalized = (value ?? "").trim().toLowerCase();
  if (normalized === "en") return "en";
  if (normalized === "de" || normalized === "de-ch") return "de-CH";
  return null;
}

function storeLanguage(language: InterfaceLanguage) {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Private windows and blocked storage: the choice lasts for this page only.
  }
}

function markUnsavedChoice(unsaved: boolean) {
  try {
    if (unsaved) window.localStorage.setItem(UNSAVED_CHOICE_KEY, "1");
    else window.localStorage.removeItem(UNSAVED_CHOICE_KEY);
  } catch {
    // See storeLanguage.
  }
}

/** True while the visitor's own choice still has to be saved in the account after sign-in. */
export function hasUnsavedLanguageChoice(): boolean {
  try {
    return window.localStorage.getItem(UNSAVED_CHOICE_KEY) === "1";
  } catch {
    return false;
  }
}

function initialLanguage(): InterfaceLanguage {
  if (typeof window === "undefined") return "en";
  try {
    const fromAddress = parseInterfaceLanguage(new URL(window.location.href).searchParams.get("lang"));
    if (fromAddress) {
      storeLanguage(fromAddress);
      markUnsavedChoice(true);
      return fromAddress;
    }
    return parseInterfaceLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)) ?? "en";
  } catch {
    return "en";
  }
}

let preferredLanguage: InterfaceLanguage = initialLanguage();
let investorScope = false;

function notify() {
  listeners.forEach((listener) => listener());
}

function wantedLocale(): Locale {
  return investorScope ? preferredLanguage : "en";
}

/** Loads the catalog of one language once (a separate chunk, so English pages do not carry it). */
export async function loadLanguageCatalog(locale: Locale): Promise<void> {
  if (loadedCatalogs.has(locale)) return;
  const loader = catalogLoaders[locale];
  if (!loader) return;
  registerMessages(locale, await loader());
  loadedCatalogs.add(locale);
}

async function activateWantedLocale() {
  const locale = wantedLocale();
  // A loaded catalog switches in the same render pass (no English flash on navigation).
  if (loadedCatalogs.has(locale)) {
    setLocale(locale);
    return;
  }
  try {
    await loadLanguageCatalog(locale);
  } catch {
    // A chunk that does not load (offline, new deployment): stay in the current language.
    return;
  }
  // Another change may have happened while the catalog loaded.
  if (wantedLocale() === locale) setLocale(locale);
}

export function getPreferredLanguage(): InterfaceLanguage {
  return preferredLanguage;
}

function setPreferredLanguage(language: InterfaceLanguage): Promise<void> {
  if (language !== preferredLanguage) {
    preferredLanguage = language;
    storeLanguage(language);
    notify();
  }
  return activateWantedLocale();
}

/** The visitor's own choice. Applies at once in the investor area; saved in the account by the caller
 * (signed in) or after the next sign-in (signed out). */
export function chooseLanguage(language: InterfaceLanguage): Promise<void> {
  markUnsavedChoice(true);
  return setPreferredLanguage(language);
}

/** The language saved in the account: it applies on every device after sign-in. */
export function applyAccountLanguage(language: InterfaceLanguage): Promise<void> {
  markUnsavedChoice(false);
  return setPreferredLanguage(language);
}

/** The choice is now saved in the account. */
export function markLanguageChoiceSaved() {
  markUnsavedChoice(false);
}

/** The investor area (sign-in, registration and the portal) uses the chosen language; other areas English. */
export function setInvestorScope(active: boolean): Promise<void> {
  investorScope = active;
  return activateWantedLocale();
}

/** Loads the chosen catalog before the first render, so a German visitor does not see English first. */
export function preloadPreferredLanguage(): Promise<void> {
  return loadLanguageCatalog(preferredLanguage).catch(() => undefined);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The chosen interface language, re-rendering when it changes. */
export function usePreferredLanguage(): InterfaceLanguage {
  return useSyncExternalStore(subscribe, getPreferredLanguage, getPreferredLanguage);
}

/** Resets the module state between tests. */
export function resetLanguageForTests() {
  markUnsavedChoice(false);
  preferredLanguage = "en";
  investorScope = false;
  setLocale("en");
  notify();
}
