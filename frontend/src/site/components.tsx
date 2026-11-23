// IP of Webby-Soft SRL.
/*
 * Shared link helpers of the public site: <SiteLink> (in-app navigation for site paths, exported as
 * PublicLink by u33/ui.tsx) and <SiteHtml> (trusted static HTML of content.ts with its internal
 * links opened in the app). The October blocks that lived here were retired with the October
 * shell (Q24, D-10). Keeping non-components out of this file keeps React Fast Refresh working.
 */
import type { AnchorHTMLAttributes } from "react";

import { useSiteNav } from "./context";
import { isPlainLeftClick, siteHtml, useStaticLinkClick } from "./links";

// ---------------------------------------------------------------------------------------------
// Links

type SiteLinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: string };

/** <a href="/path"> that navigates in the app on a plain left click (design: href="#/path"). */
export function SiteLink({ href, onClick, children, ...rest }: SiteLinkProps) {
  const { navigate } = useSiteNav();
  return (
    <a
      {...rest}
      href={href}
      onClick={(event) => {
        onClick?.(event);
        if (!isPlainLeftClick(event) || rest.target) return;
        event.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </a>
  );
}
type SiteHtmlProps = { html: string; className?: string; as?: "div" | "p" | "span" };

/**
 * Trusted static HTML from content.ts (never API or user data), with the design's internal
 * links opened in the app by a delegated click handler.
 */
export function SiteHtml({ html, className, as: Tag = "div" }: SiteHtmlProps) {
  const onClick = useStaticLinkClick();
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: siteHtml(html) }} onClick={onClick} />;
}
