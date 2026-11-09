// IP of Webby-Soft SRL.
// Portal navigation context: real hrefs plus in-app routing (provided by InvestorShell).
import { createContext, useContext, type MouseEvent } from "react";

import type { AppRoute, RouteName } from "../../investorPortal/types";

export type PortalNav = {
  /** The address of a route ("/dashboard", "/marketplace/42"). */
  hrefFor: (name: RouteName, params?: Record<string, string>) => string;
  /** Goes to a route inside the app (history entry, stored route). */
  go: (name: RouteName, params?: Record<string, string>) => void;
  /** The route on screen. */
  route: AppRoute;
};

const fallback: PortalNav = { hrefFor: () => "#", go: () => undefined, route: { name: "dashboard" } };
export const PortalNavContext = createContext<PortalNav>(fallback);

/** The portal navigation of the nearest provider. */
export function usePortalNav() {
  return useContext(PortalNavContext);
}

/** True for a click the app should route itself: left button, no modifier, not handled yet. */
export function isPlainLeftClick(event: MouseEvent<HTMLElement>) {
  return !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}
