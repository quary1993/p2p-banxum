// IP of Webby-Soft SRL.
// <PortalNavProvider> and <PortalLink>: real hrefs (new tab, copy link) plus in-app routing on a plain left click.
import type { AnchorHTMLAttributes, ReactNode } from "react";

import type { RouteName } from "../../investorPortal/types";
import { isPlainLeftClick, PortalNavContext, usePortalNav, type PortalNav } from "./portalNav";

/** Provides navigation to the U33 components below (InvestorShell). */
export function PortalNavProvider({ value, children }: { value: PortalNav; children: ReactNode }) {
  return <PortalNavContext.Provider value={value}>{children}</PortalNavContext.Provider>;
}

/** <a> to a portal route: real href, in-app navigation on a plain left click. */
export function PortalLink({
  to,
  params,
  onNavigate,
  children,
  ...rest
}: {
  to: RouteName;
  params?: Record<string, string>;
  onNavigate?: () => void;
  children: ReactNode;
} & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href">) {
  const nav = usePortalNav();
  return (
    <a
      {...rest}
      href={nav.hrefFor(to, params)}
      onClick={(event) => {
        rest.onClick?.(event);
        if (!isPlainLeftClick(event)) return;
        event.preventDefault();
        onNavigate?.();
        nav.go(to, params);
      }}
    >
      {children}
    </a>
  );
}
