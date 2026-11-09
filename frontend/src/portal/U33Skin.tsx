// IP of Webby-Soft SRL.
/*
 * The U33 investor skin. While mounted (the signed-in investor area, InvestorShell), <html> gets:
 * - class "bxu": portal/u33/u33.css and u33-overrides.css are scoped to html.bxu;
 * - the design's root attributes that its CSS selects on: data-edition="refined",
 *   data-responsive, data-visual-study="ars", data-language (from the i18n locale) and
 *   data-theme;
 * and <body> gets the design's body classes (nk-body bg-white has-sidebar bxm-app).
 * Everything is removed on unmount, so the public site (html.bxs) and the admin console keep their
 * look. During the migration UserSkin (html.bxm, the old skin) stays mounted as well; old screen
 * bodies are wrapped in <LegacyBody> (shell/LegacyBody.tsx). A mount counter keeps this correct
 * under StrictMode double effects, like UserSkin and SiteSkin.
 */
import { useLayoutEffect, useRef, type ReactNode } from "react";

import { getLocale, useT } from "../i18n";

const ROOT_ATTRIBUTES: Record<string, string> = {
  "data-edition": "refined",
  "data-responsive": "true",
  "data-visual-study": "ars"
};
const BODY_CLASSES = ["nk-body", "bg-white", "has-sidebar", "bxm-app"];

let u33SkinMounts = 0;

export function U33Skin({ children }: { children: ReactNode }) {
  // Light only for now; the appearance preference follows.
  const appearance = "light";
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
      document.body.classList.remove(...BODY_CLASSES, "nav-shown");
    };
  }, []);

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
