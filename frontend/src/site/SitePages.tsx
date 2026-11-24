// IP of Webby-Soft SRL.
/*
 * Router of the public site. App.tsx renders <SitePages .../> for every site path and gives the
 * navigate() function (history + App route state).
 *
 * Every page is in the U33 public shell and skin (html.bxp, u33/public.css). A route's "u33" names
 * its page bundle (the design's page type). The design has pages for home, About, the project
 * pages, For borrowers, For loan originators, Contact and the legal pages; the pages it does not
 * have (All projects, Help, Guides, Statistics, the newsletter and alert links, the 404) are built
 * from its blocks (U33-DEC-39, Q24, D-10, Q23). The October shell and skin are retired.
 *
 * To add a page: write it in u33/pages/<Name>.tsx, then add a row to SITE_ROUTES below with its
 * title and bundle. App.tsx needs no change: routeFromPathname() sends every non-portal path here.
 */
import { useLayoutEffect, useMemo, type ComponentType } from "react";

import "./siteStyles";
import { SiteNavContext, siteDocumentTitle, type SiteNavigate } from "./context";
import { HowItWorksMoved } from "./pages/HowItWorks";
import { PublicShell } from "./u33/PublicShell";
import { PublicSkin, type PublicBundle } from "./u33/PublicSkin";
import { About } from "./u33/pages/About";
import { Companies, Originators } from "./u33/pages/Business";
import { Contact } from "./u33/pages/Contact";
import { Guide, Guides } from "./u33/pages/Guides";
import { Help } from "./u33/pages/Help";
import { Home } from "./u33/pages/Home";
import { isPublicLegalDocument } from "./u33/legalRoutes";
import { Legal } from "./u33/pages/Legal";
import { AlertStop, NewsletterLinkPage, NotFound } from "./u33/pages/Notice";
import { Project } from "./u33/pages/Project";
import { Projects } from "./u33/pages/Projects";
import { Statistics } from "./u33/pages/Statistics";

/** Props every site page receives: the path parameters (":id" -> params.id). */
export type SitePageProps = { params: Record<string, string> };

type U33Route = { bundle: PublicBundle; mainClassName?: string; footerDivider?: boolean };

type SiteRoute = {
  pattern: string;
  page: ComponentType<SitePageProps>;
  title: string | null;
  /** The page's bundle, or a function of the params (null: no such page, the 404). */
  u33: U33Route | ((params: Record<string, string>) => U33Route | null);
};

const LEGAL: U33Route = { bundle: "legal" };

const NewsletterConfirm = () => <NewsletterLinkPage kind="confirm" />;
const NewsletterUnsubscribe = () => <NewsletterLinkPage kind="unsubscribe" />;

/** Path patterns; the document title is "<title> · Banxum". */
const SITE_ROUTES: SiteRoute[] = [
  { pattern: "/", page: Home, title: null, u33: { bundle: "home", footerDivider: true } },
  { pattern: "/projects", page: Projects, title: "All projects", u33: { bundle: "projects" } },
  { pattern: "/projects/:id", page: Project, title: "Project", u33: { bundle: "project" } },
  // Q24: retired; the content is in Help (the address leads there).
  { pattern: "/how-it-works", page: HowItWorksMoved, title: "Help", u33: LEGAL },
  { pattern: "/statistics", page: Statistics, title: "Statistics", u33: LEGAL },
  { pattern: "/companies", page: Companies, title: "For borrowers", u33: { bundle: "business", mainClassName: "business-content" } },
  { pattern: "/originators", page: Originators, title: "For loan originators", u33: { bundle: "business", mainClassName: "business-content" } },
  { pattern: "/about", page: About, title: "About Banxum", u33: { bundle: "about", mainClassName: "about-content" } },
  { pattern: "/help", page: Help, title: "Help", u33: LEGAL },
  { pattern: "/guides", page: Guides, title: "Guides", u33: LEGAL },
  { pattern: "/guides/:id", page: Guide, title: "Guide", u33: LEGAL },
  {
    pattern: "/legal/:doc",
    page: Legal,
    title: "Legal",
    u33: (params) => (isPublicLegalDocument(params.doc ?? "") ? LEGAL : null)
  },
  { pattern: "/contact", page: Contact, title: "Contact", u33: { bundle: "contact" } },
  { pattern: "/newsletter/confirm", page: NewsletterConfirm, title: "New projects by email", u33: LEGAL },
  { pattern: "/newsletter/unsubscribe", page: NewsletterUnsubscribe, title: "New projects by email", u33: LEGAL },
  // Q14: the "Stop these alerts" link of alert emails.
  { pattern: "/alerts/stop", page: AlertStop, title: "Stop these alerts", u33: LEGAL }
];

const NOT_FOUND: SiteRoute = { pattern: "/404", page: NotFound, title: "Not found", u33: LEGAL };

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

function matchSiteRoute(path: string): { route: SiteRoute; params: Record<string, string>; u33: U33Route } {
  for (const { route, keys, re } of compiled) {
    const match = path.match(re);
    if (!match) continue;
    const params: Record<string, string> = {};
    try {
      keys.forEach((key, index) => (params[key] = decodeURIComponent(match[index + 1])));
    } catch {
      continue;
    }
    const u33 = typeof route.u33 === "function" ? route.u33(params) : route.u33;
    if (!u33) return { route: NOT_FOUND, params: {}, u33: LEGAL };
    return { route, params, u33 };
  }
  return { route: NOT_FOUND, params: {}, u33: LEGAL };
}

export function SitePages({ path, search, navigate }: { path: string; search: string; navigate: SiteNavigate }) {
  const normalized = path.replace(/\/+$/, "") || "/";
  const { route, params, u33 } = matchSiteRoute(normalized);
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
      <PublicSkin bundle={u33.bundle}>
        <PublicShell footerDivider={u33.footerDivider} mainClassName={u33.mainClassName}>
          <Page key={normalized} params={params} />
        </PublicShell>
      </PublicSkin>
    </SiteNavContext.Provider>
  );
}
