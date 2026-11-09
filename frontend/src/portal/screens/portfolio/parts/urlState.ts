// IP of Webby-Soft SRL.
// Sub-views of the portfolio screens as query parameters on the screen's own address
// (/portfolio?view=history, /secondary-market?tab=mine, /secondary-market?offer=<id>), so they can be
// shared and the browser's Back button returns to the list. App.tsx routing stays untouched: the
// parameters are read here; Back/Forward (popstate) and the app's own navigation re-read them.
import { useCallback, useEffect, useState } from "react";

import { isFixturePreview } from "../../../../investorPortal/data";
import { PORTAL_ADDRESS_EVENT } from "../../../components/portalNav";

function readParams() {
  return new URLSearchParams(window.location.search);
}

export function useQueryParams(): [URLSearchParams, (next: Record<string, string | null>, options?: { replace?: boolean }) => void] {
  const [params, setParams] = useState(readParams);
  useEffect(() => {
    // Back/Forward (popstate) and the app's own navigation (menu links, PORTAL_ADDRESS_EVENT).
    const onAddressChange = () => setParams(readParams());
    window.addEventListener("popstate", onAddressChange);
    window.addEventListener(PORTAL_ADDRESS_EVENT, onAddressChange);
    return () => {
      window.removeEventListener("popstate", onAddressChange);
      window.removeEventListener(PORTAL_ADDRESS_EVENT, onAddressChange);
    };
  }, []);
  const update = useCallback((next: Record<string, string | null>, options?: { replace?: boolean }) => {
    const merged = readParams();
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === "") merged.delete(key);
      else merged.set(key, value);
    }
    const search = merged.toString();
    const address = `${window.location.pathname}${search ? `?${search}` : ""}`;
    if (options?.replace) window.history.replaceState(window.history.state, "", address);
    else window.history.pushState(window.history.state, "", address);
    setParams(new URLSearchParams(search));
    if (!options?.replace) window.scrollTo({ top: 0, behavior: "instant" });
  }, []);
  return [params, update];
}

/**
 * Preview mode only (fixture data): ?preview=<variant> shows a state the fixtures do not hold by
 * default (empty portfolio, no listings, Smart Invest not set up, criteria that saving removes...).
 */
export function usePreviewVariant() {
  const [params] = useQueryParams();
  return isFixturePreview ? params.get("preview") ?? "" : "";
}
