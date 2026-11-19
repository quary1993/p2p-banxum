// IP of Webby-Soft SRL.
/*
 * The U33 investor skin. While mounted (the signed-in investor area, InvestorShell), <html> gets:
 * - class "bxu": portal/u33/u33.css and u33-overrides.css are scoped to html.bxu;
 * - the design's root attributes that its CSS selects on: data-edition="refined",
 *   data-responsive, data-visual-study="ars", data-language (from the i18n locale) and
 *   data-theme ("light" | "dark", from useAppearance);
 * and <body> gets the design's body classes (nk-body bg-white has-sidebar bxm-app).
 * layout="auth" (sign-in, registration, PIN gate, Didit return; slice S5) gives the body the design's
 * classes for the screens outside the app layout (nk-body bg-white bxm-app, no has-sidebar).
 * Everything is removed on unmount, so the public site (html.bxs) and the admin console keep their
 * look. The old skin (html.bxm) and its <LegacyBody> wrapper were removed in the S7 clean-up (18.5).
 * A mount counter keeps this correct under StrictMode double effects, like SiteSkin.
 */
import { useLayoutEffect, useRef, type ReactNode } from "react";

import { getLocale, useT } from "../i18n";
import { useAppearance } from "./appearance";

const ROOT_ATTRIBUTES: Record<string, string> = {
  "data-edition": "refined",
  "data-responsive": "true",
  "data-visual-study": "ars"
};
const BODY_CLASSES = ["nk-body", "bg-white", "bxm-app"];
// The app layout with its sidebar; the auth screens leave it out (design: #bxm-screen).
const PORTAL_BODY_CLASS = "has-sidebar";

let u33SkinMounts = 0;

export function U33Skin({ children, layout = "portal" }: { children: ReactNode; layout?: "portal" | "auth" }) {
  const { appearance } = useAppearance();
  useT(); // re-render on a language change so data-language follows
  const locale = getLocale();
  const firstTheme = useRef(true);

  useLayoutEffect(() => {
    u33SkinMounts += 1;
    const html = document.documentElement;
    html.classList.add("bxu");
    for (const [name, value] of Object.entries(ROOT_ATTRIBUTES)) html.setAttribute(name, value);
    document.body.classList.add(...BODY_CLASSES);
    return () => {
      u33SkinMounts -= 1;
      if (u33SkinMounts > 0) return;
      u33SkinMounts = 0;
      html.classList.remove("bxu", "bxm-theme-switching", "mobile-menu-open");
      for (const name of [...Object.keys(ROOT_ATTRIBUTES), "data-theme", "data-language"]) html.removeAttribute(name);
      document.body.classList.remove(...BODY_CLASSES, PORTAL_BODY_CLASS, "nav-shown");
    };
  }, []);

  useLayoutEffect(() => {
    if (layout !== "portal") return undefined;
    document.body.classList.add(PORTAL_BODY_CLASS);
    return () => document.body.classList.remove(PORTAL_BODY_CLASS);
  }, [layout]);

  useLayoutEffect(() => {
    const html = document.documentElement;
    if (firstTheme.current) {
      firstTheme.current = false;
      html.dataset.theme = appearance;
      return;
    }
    // Switch atomically, without intermediate low-contrast transitions (as the design does).
    html.classList.add("bxm-theme-switching");
    html.dataset.theme = appearance;
    void html.offsetWidth;
    const frame = window.requestAnimationFrame(() =>
      window.requestAnimationFrame(() => html.classList.remove("bxm-theme-switching"))
    );
    return () => window.cancelAnimationFrame(frame);
  }, [appearance]);

  useLayoutEffect(() => {
    document.documentElement.dataset.language = locale.split("-")[0];
  }, [locale]);

  return <>{children}</>;
}
