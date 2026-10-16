// IP of Webby-Soft SRL.
// Link helpers of the public site: which clicks the app handles itself, and the design's
// "#/x" links in static HTML.
import type { MouseEvent } from "react";

import { useSiteNav } from "./context";

/** A plain left click (no new tab, no modifier): the only click the app handles itself. */
export function isPlainLeftClick(event: MouseEvent) {
  return !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

/** An in-app href: "/x" but not "//host" and not "/api/...". */
export function isAppHref(href: string | null): href is string {
  return Boolean(href && href.startsWith("/") && !href.startsWith("//") && !href.startsWith("/api/"));
}

/** The design's "#/x" links in static HTML -> "/x". */
export function siteHtml(html: string) {
  return html.replace(/href="#\//g, 'href="/');
}

/** Delegated click handler for containers of static HTML: opens "/x" links in the app. */
export function useStaticLinkClick() {
  const { navigate } = useSiteNav();
  return (event: MouseEvent<HTMLElement>) => {
    const anchor = (event.target as HTMLElement).closest?.("a");
    if (!anchor || !event.currentTarget.contains(anchor)) return;
    const href = anchor.getAttribute("href");
    if (!isAppHref(href) || anchor.target || !isPlainLeftClick(event)) return;
    event.preventDefault();
    navigate(href);
  };
}
