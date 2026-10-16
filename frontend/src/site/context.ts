// IP of Webby-Soft SRL.
/*
 * Shared state of the public site: navigation (the current path and query, and navigate()),
 * toasts, the document title and the newsletter sign-up shown by every subscribe block.
 * SitePages provides the navigation, SiteShell the toasts.
 */
import { createContext, useContext, useEffect, useSyncExternalStore } from "react";

export type SiteNavigate = (href: string, options?: { replace?: boolean }) => void;

export type SiteNav = {
  /** Current path without trailing slash ("/", "/projects", "/projects/<id>"). */
  path: string;
  /** Current query string, with "?" ("" when empty). */
  search: string;
  query: URLSearchParams;
  /**
   * In-app navigation to a site path ("/projects?status=all"), to "/login" or "/register".
   * Pushes a history entry (replace: true replaces it, e.g. for filters in the address).
   */
  navigate: SiteNavigate;
};

export const SiteNavContext = createContext<SiteNav | null>(null);

export function useSiteNav(): SiteNav {
  const nav = useContext(SiteNavContext);
  if (!nav) throw new Error("useSiteNav must be used inside SitePages");
  return nav;
}

/** Shows a toast at the bottom right (design B.toast): text and a Nioicon name. */
export type SiteToast = (text: string, icon?: string) => void;

export const SiteToastContext = createContext<SiteToast>(() => undefined);

export function useSiteToast() {
  return useContext(SiteToastContext);
}

export const SITE_BRAND = "Banxum";
export const SITE_HOME_TITLE = "Banxum · Lend to real companies";

export function siteDocumentTitle(title: string | null | undefined) {
  return title ? `${title} · ${SITE_BRAND}` : SITE_HOME_TITLE;
}

/**
 * Sets the document title from a page ("Residential building completion · Banxum"). SitePages
 * sets the route's default title in a layout effect; this passive effect runs after it, so the
 * page's title wins.
 */
export function useSiteTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = siteDocumentTitle(title);
  }, [title]);
}

// ---------------------------------------------------------------------------------------------
// Newsletter sign-up: after a successful sign-up every subscribe block shows "Almost done"
// (as in the design) until the visitor chooses "Use another address". Kept for the browser tab
// (sessionStorage), not longer: it holds an email address.

const NEWSLETTER_KEY = "bxm-site-newsletter";
const listeners = new Set<() => void>();
// Used only when sessionStorage is blocked.
let memoryEmail: string | null = null;

function readSubscribed() {
  try {
    return window.sessionStorage.getItem(NEWSLETTER_KEY);
  } catch {
    return memoryEmail;
  }
}

export function setNewsletterSubscribed(email: string | null) {
  memoryEmail = email;
  try {
    if (email) window.sessionStorage.setItem(NEWSLETTER_KEY, email);
    else window.sessionStorage.removeItem(NEWSLETTER_KEY);
  } catch {
    // Storage blocked: keep the state in memory only.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The address of the last newsletter sign-up in this tab, or null. */
export function useNewsletterSubscribed() {
  return useSyncExternalStore(subscribe, readSubscribed, () => null);
}
