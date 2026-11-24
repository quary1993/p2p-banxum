// IP of Webby-Soft SRL.
/*
 * Skin of the U33 public site: while mounted, <html> has the class "bxp" plus the page bundle
 * class "bxp-<bundle>" (public.css applies some design files only to some page types), and
 * <body> the design's body classes of that page type. "motion-reduced" mirrors the visitor's
 * reduced-motion preference on <html>, like the design's persuasion.js.
 *
 * The investor area's skin (html.bxu) is taken off while this one is mounted and put back
 * afterwards. A mount counter keeps it right under StrictMode double effects.
 */
import { useLayoutEffect, type ReactNode } from "react";

import { useReducedMotion } from "./hooks";

export type PublicBundle = "home" | "about" | "business" | "contact" | "legal" | "project" | "projects";

/**
 * The CSS bundle of each page type. "projects" (All projects, Q24) uses the home page's rules and
 * body classes (loan cards, calculator); public-overrides.css turns its phone carousel back into a
 * list (section 7).
 */
const CSS_BUNDLE: Record<PublicBundle, string> = {
  home: "home",
  about: "about",
  business: "business",
  contact: "contact",
  legal: "legal",
  project: "project",
  projects: "home"
};

/** The design's <body> classes per page type. */
const BODY_CLASSES: Record<PublicBundle, string[]> = {
  home: ["complete-preview", "home-preview", "persuasion-preview"],
  about: ["complete-preview", "about-v01"],
  business: ["complete-preview", "business-v01"],
  contact: ["complete-preview", "contact-refined"],
  legal: ["complete-preview"],
  project: ["complete-preview", "compact-detail"],
  projects: ["complete-preview", "home-preview", "persuasion-preview"]
};

const OTHER_SKINS = ["bxu"];
let publicSkinMounts = 0;

export function PublicSkin({ bundle, children }: { bundle: PublicBundle; children: ReactNode }) {
  const reducedMotion = useReducedMotion();

  useLayoutEffect(() => {
    publicSkinMounts += 1;
    const html = document.documentElement;
    const removed = OTHER_SKINS.filter((name) => html.classList.contains(name));
    html.classList.remove(...removed);
    html.classList.add("bxp");
    return () => {
      publicSkinMounts -= 1;
      if (publicSkinMounts <= 0) {
        publicSkinMounts = 0;
        html.classList.remove("bxp", "motion-reduced");
        document.body.classList.remove("mobile-menu-open");
        html.classList.add(...removed);
      }
    };
  }, []);

  useLayoutEffect(() => {
    const html = document.documentElement;
    const bodyClasses = BODY_CLASSES[bundle];
    const cssClass = `bxp-${CSS_BUNDLE[bundle]}`;
    html.classList.add(cssClass);
    document.body.classList.add(...bodyClasses);
    return () => {
      html.classList.remove(cssClass);
      document.body.classList.remove(...bodyClasses);
    };
  }, [bundle]);

  useLayoutEffect(() => {
    document.documentElement.classList.toggle("motion-reduced", reducedMotion);
  }, [reducedMotion]);

  return <>{children}</>;
}
