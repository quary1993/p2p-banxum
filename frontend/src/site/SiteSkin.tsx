// IP of Webby-Soft SRL.
/*
 * Skin of the public site: while mounted, <html> has the class "bxs" (and not "bxm", the
 * investor area's skin) and <body> the design's class "bxm-site". site.css and
 * site-overrides.css are scoped to html.bxs, so they style nothing else. Mirrors UserSkin
 * (investorPortal/ui.tsx): a mount counter keeps it right under StrictMode double effects.
 */
import { useLayoutEffect, type ReactNode } from "react";

let siteSkinMounts = 0;

export function SiteSkin({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    siteSkinMounts += 1;
    const html = document.documentElement;
    const hadUserSkin = html.classList.contains("bxm");
    html.classList.remove("bxm");
    html.classList.add("bxs");
    document.body.classList.add("bxm-site");
    return () => {
      siteSkinMounts -= 1;
      if (siteSkinMounts <= 0) {
        siteSkinMounts = 0;
        html.classList.remove("bxs");
        document.body.classList.remove("bxm-site", "site-menu-open", "site-has-cta");
        // A UserSkin mounted meanwhile (never in practice: the site renders alone) keeps its class.
        if (hadUserSkin) html.classList.add("bxm");
      }
    };
  }, []);
  return <>{children}</>;
}
