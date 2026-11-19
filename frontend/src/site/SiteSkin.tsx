// IP of Webby-Soft SRL.
/*
 * Skin of the public site: while mounted, <html> has the class "bxs" and <body> the design's class
 * "bxm-site". site.css and site-overrides.css are scoped to html.bxs, so they style nothing else.
 * A mount counter keeps it right under StrictMode double effects (like U33Skin).
 */
import { useLayoutEffect, type ReactNode } from "react";

let siteSkinMounts = 0;

export function SiteSkin({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    siteSkinMounts += 1;
    const html = document.documentElement;
    html.classList.add("bxs");
    document.body.classList.add("bxm-site");
    return () => {
      siteSkinMounts -= 1;
      if (siteSkinMounts <= 0) {
        siteSkinMounts = 0;
        html.classList.remove("bxs");
        document.body.classList.remove("bxm-site", "site-menu-open", "site-has-cta");
      }
    };
  }, []);
  return <>{children}</>;
}
