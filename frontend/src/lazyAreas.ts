// IP of Webby-Soft SRL.
// Audit G-07 (S7 of audit step 4): the public site and the admin console load lazily, each with its own
// stylesheet (site/siteStyles.ts, adminConsole/adminStyles.ts); the investor area keeps the U33
// stylesheet in the main bundle. A loaded area renders at once (no loading flash on later visits; the
// tests preload both areas so they render synchronously, as before).
import { createElement, lazy, Suspense, useState, type ComponentProps, type ComponentType } from "react";

type Loader<P> = () => Promise<ComponentType<P>>;

export function preloadableArea<P extends object>(load: Loader<P>) {
  let loaded: ComponentType<P> | null = null;
  let pending: Promise<ComponentType<P>> | null = null;
  const preload = () => {
    pending ??= load().then((component) => {
      loaded = component;
      return component;
    });
    return pending;
  };
  const Lazy = lazy(() => preload().then((component) => ({ default: component })));
  const fallback = createElement("div", { "aria-busy": "true", className: "area-loading", role: "status" });
  function Area(props: P) {
    // Keep the same tree after the first lazy load. Dropping Suspense on a later
    // parent render would remount the entire area, including any open form.
    const [preloaded] = useState(() => loaded);
    if (preloaded) return createElement(preloaded, props);
    return createElement(Suspense, { fallback }, createElement(Lazy, props));
  }
  return Object.assign(Area, { preload });
}

export const SitePages = preloadableArea<ComponentProps<typeof import("./site/SitePages").SitePages>>(() =>
  import("./site/SitePages").then((module) => module.SitePages)
);

export const AdminApp = preloadableArea<Record<string, never>>(() =>
  import("./adminConsole/AdminApp").then((module) => module.AdminApp)
);
