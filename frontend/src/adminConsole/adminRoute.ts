import { useCallback, useMemo, useSyncExternalStore } from "react";

// Admin console routing. The URL is the single source of truth for the open
// section, the selected record (loan, task, user...) and list filters, so a
// reload or a shared link reopens the same screen and Back/Forward work.
//
//   /admin                      Daily dashboard
//   /admin/<section>            tasks, users, compliance, finance, loans, reports, qa, settings
//   /admin/<section>/<id>/...   a record inside the section (e.g. /admin/loans/<id>/manage)
//   ?key=value                  filters of the open section

export const adminSections = [
  "dashboard",
  "tasks",
  "users",
  "compliance",
  "finance",
  "loans",
  "reports",
  "qa",
  "settings"
] as const;

export type AdminSection = (typeof adminSections)[number];

export type AdminLocation = {
  section: AdminSection;
  /** Path segments after the section, e.g. [loanId, "manage"]. */
  segments: string[];
  params: URLSearchParams;
};

const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("popstate", listener);
  };
}

function currentHref() {
  return `${window.location.pathname}${window.location.search}`;
}

function isAdminSection(value: string | undefined): value is AdminSection {
  return Boolean(value) && (adminSections as readonly string[]).includes(value as string);
}

function safeDecode(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function parseAdminLocation(href: string): AdminLocation {
  const url = new URL(href, "http://admin.invalid");
  const parts = url.pathname.split("/").filter(Boolean).map(safeDecode);
  // parts[0] is "admin".
  const candidate = parts[1];
  if (!isAdminSection(candidate)) {
    return { section: "dashboard", segments: [], params: url.searchParams };
  }
  return { section: candidate, segments: parts.slice(2), params: url.searchParams };
}

export function adminHref(
  section: AdminSection,
  segments: string[] = [],
  params?: URLSearchParams | Record<string, string>
) {
  const path = section === "dashboard" && segments.length === 0
    ? "/admin"
    : ["/admin", section, ...segments.map((segment) => encodeURIComponent(segment))].join("/");
  const search = params instanceof URLSearchParams ? params : new URLSearchParams(params ?? {});
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

/** Moves the admin console to another URL. Filters replace; screens push. */
export function navigateAdmin(href: string, options: { replace?: boolean } = {}) {
  if (href === currentHref()) return;
  if (options.replace) {
    window.history.replaceState(window.history.state, "", href);
  } else {
    window.history.pushState(null, "", href);
  }
  notify();
}

export function useAdminLocation(): AdminLocation {
  const href = useSyncExternalStore(subscribe, currentHref, currentHref);
  return useMemo(() => parseAdminLocation(href), [href]);
}

/** Opens a section (dropping the previous section's record and filters). */
export function openAdminSection(section: AdminSection) {
  navigateAdmin(adminHref(section));
}

/** Path segments after the section and a setter that pushes a new history entry. */
export function useAdminSegments(section: AdminSection): [string[], (segments: string[], replace?: boolean) => void] {
  const location = useAdminLocation();
  const segments = location.section === section ? location.segments : [];
  const setSegments = useCallback(
    (next: string[], replace = false) => {
      const current = parseAdminLocation(currentHref());
      const params = current.section === section ? current.params : new URLSearchParams();
      navigateAdmin(adminHref(section, next, params), { replace });
    },
    [section]
  );
  return [segments, setSegments];
}

/** One query-string filter of the current section, kept in the URL with replaceState. */
export function useAdminParam(name: string, fallback = ""): [string, (value: string) => void] {
  const location = useAdminLocation();
  const value = location.params.get(name) ?? fallback;
  const setValue = useCallback(
    (next: string) => {
      const current = parseAdminLocation(currentHref());
      const params = new URLSearchParams(current.params);
      if (next === "" || next === fallback) params.delete(name);
      else params.set(name, next);
      navigateAdmin(adminHref(current.section, current.segments, params), { replace: true });
    },
    [fallback, name]
  );
  return [value, setValue];
}
