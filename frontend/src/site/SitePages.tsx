// IP of Webby-Soft SRL.
/*
 * Router of the public site. App.tsx renders <SiteSkin><SitePages .../></SiteSkin> for every
 * site path and gives the navigate() function (history + App route state).
 *
 * To add a page (round 2): write it in pages/<Name>.tsx (start with <PageHead>, use the blocks
 * of components.tsx and the hooks of data.ts), then add a row to SITE_ROUTES below with its
 * design title. App.tsx needs no change: routeFromPathname() sends every non-portal path here
 * (see isSitePath in App.tsx only if the page lives under a new top-level path).
 */
import { useLayoutEffect, useMemo, type ComponentType } from "react";

import { SiteNavContext, siteDocumentTitle, type SiteNavigate } from "./context";
import { SiteShell } from "./SiteShell";
import { About } from "./pages/About";
import { Companies } from "./pages/Companies";
import { Contact } from "./pages/Contact";
import { Guide } from "./pages/Guide";
import { Guides } from "./pages/Guides";
import { Help } from "./pages/Help";
import { Home } from "./pages/Home";
import { HowItWorks } from "./pages/HowItWorks";
import { Legal } from "./pages/Legal";
import { NewsletterConfirm } from "./pages/NewsletterConfirm";
import { NewsletterUnsubscribe } from "./pages/NewsletterUnsubscribe";
import { NotFound } from "./pages/NotFound";
import { Originators } from "./pages/Originators";
import { Project } from "./pages/Project";
import { Projects } from "./pages/Projects";
import { Statistics } from "./pages/Statistics";

/** Props every site page receives: the path parameters (":id" -> params.id). */
export type SitePageProps = { params: Record<string, string> };

type SiteRoute = { pattern: string; page: ComponentType<SitePageProps>; title: string | null };

/** Path patterns as in the design router; the document title is "<title> · Banxum". */
const SITE_ROUTES: SiteRoute[] = [
  { pattern: "/", page: Home, title: null },
  { pattern: "/projects", page: Projects, title: "Projects" },
  { pattern: "/projects/:id", page: Project, title: "Project" },
  { pattern: "/how-it-works", page: HowItWorks, title: "How it works" },
  { pattern: "/statistics", page: Statistics, title: "Statistics" },
  { pattern: "/companies", page: Companies, title: "For companies" },
  { pattern: "/originators", page: Originators, title: "For loan originators" },
  { pattern: "/about", page: About, title: "About" },
  { pattern: "/help", page: Help, title: "Help" },
  { pattern: "/guides", page: Guides, title: "Guides" },
  { pattern: "/guides/:id", page: Guide, title: "Guide" },
  { pattern: "/legal/:doc", page: Legal, title: "Legal" },
  { pattern: "/contact", page: Contact, title: "Contact" },
  { pattern: "/newsletter/confirm", page: NewsletterConfirm, title: "New projects by email" },
  { pattern: "/newsletter/unsubscribe", page: NewsletterUnsubscribe, title: "New projects by email" }
];

const NOT_FOUND: SiteRoute = { pattern: "/404", page: NotFound, title: "Not found" };

const compiled = SITE_ROUTES.map((route) => {
  const keys: string[] = [];
  const re = new RegExp(
    "^" +
      route.pattern.replace(/:([a-z]+)/g, (_, key: string) => {
        keys.push(key);
        return "([^/]+)";
      }) +
      "$"
  );
  return { route, keys, re };
});

function matchSiteRoute(path: string): { route: SiteRoute; params: Record<string, string> } {
  for (const { route, keys, re } of compiled) {
    const match = path.match(re);
    if (!match) continue;
    const params: Record<string, string> = {};
    try {
      keys.forEach((key, index) => (params[key] = decodeURIComponent(match[index + 1])));
    } catch {
      continue;
    }
    return { route, params };
  }
  return { route: NOT_FOUND, params: {} };
}

export function SitePages({ path, search, navigate }: { path: string; search: string; navigate: SiteNavigate }) {
  const normalized = path.replace(/\/+$/, "") || "/";
  const { route, params } = matchSiteRoute(normalized);
  const nav = useMemo(
    () => ({ path: normalized, search, query: new URLSearchParams(search), navigate }),
    [normalized, search, navigate]
  );

  // The route's title; a page can set a better one with useSiteTitle (a passive effect, later).
  useLayoutEffect(() => {
    document.title = siteDocumentTitle(route.title);
  }, [route]);

  const Page = route.page;
  return (
    <SiteNavContext.Provider value={nav}>
      <SiteShell>
        <Page key={normalized} params={params} />
      </SiteShell>
    </SiteNavContext.Provider>
  );
}
