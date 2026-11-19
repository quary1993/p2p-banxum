// IP of Webby-Soft SRL.
/*
 * Shell of the U33 public site (design: header of every public page, navigation.js, mobile.js,
 * public-language.js, complete.js menus, closing footer). Differences with the design, on
 * purpose: links are real paths ("/about", "/#opportunities"), "Log in" opens /login, German and
 * French are marked "Soon" (U33-DEC-31: EN only until Phase 17.8), the footer carries the
 * operator line (U33-DEC-34) and links to the October pages kept by U33-DEC-39, and the cookie
 * notice of the October site is kept, in U33 style.
 *
 * One responsive DOM: at 1120 px and wider it is the design's desktop edition; below, the
 * mobile edition (menu toggle, Contact inside the menu, actions in the mobile order).
 *
 * Behaviour: the header turns compact after 48 px of scrolling (desktop) and marks the home
 * section in view; the mobile menu traps the focus, closes on Escape, on a link and when the
 * layout becomes desktop; a page change closes the menus, scrolls to the top (or to the
 * address's #section) and focuses <main> after the first page.
 */
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode
} from "react";

import { useT } from "../../i18n";
import { isMultilanguageEnabled } from "../../i18n/language";
import { siteCompany } from "../content";
import { SiteToastContext, useSiteNav, useSiteToast } from "../context";
import { saveCookieChoice, useCookieChoice } from "../cookies";
import { GLYPHS } from "./glyphs";
import { useNarrow } from "./hooks";
import { HomeSectionLink, Ni, PublicLink } from "./ui";

const LOGO = "/brand/banxum-logo.svg";
const TOAST_MS = 3200;
const COMPACT_Y = 48;
/** navigation.js: a section counts as the current one when it spans this line of the screen. */
const SECTION_LINE = 160;

type Toast = { id: number; text: string; tone: "ok" | "info" };

export function PublicShell({ children, mainClassName, footerDivider = false }: { children: ReactNode; mainClassName?: string; footerDivider?: boolean }) {
  const t = useT();
  const { path, search } = useSiteNav();
  const narrow = useNarrow();
  const [menuOpen, setMenuOpen] = useState(false);
  const [businessOpen, setBusinessOpen] = useState(false);
  const [compact, setCompact] = useState(false);
  const [currentSection, setCurrentSection] = useState<string | null>(null);
  const [cookieSettings, setCookieSettings] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastSeq = useRef(0);
  const headerRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const lastPath = useRef<string | null>(null);

  const toast = useCallback((text: string, icon?: string) => {
    toastSeq.current += 1;
    const id = toastSeq.current;
    const tone = icon && /alert|info|globe/.test(icon) ? "info" : "ok";
    setToasts((list) => [...list, { id, text, tone }]);
    window.setTimeout(() => setToasts((list) => list.filter((item) => item.id !== id)), TOAST_MS);
  }, []);

  const closeMenu = useCallback((focusToggle = false) => {
    setMenuOpen(false);
    setBusinessOpen(false);
    if (focusToggle) toggleRef.current?.focus({ preventScroll: true });
  }, []);

  // A new page: close the menus; a new path: to the #section of the address or to the top,
  // and focus <main> after the first page.
  useLayoutEffect(() => {
    setMenuOpen(false);
    setBusinessOpen(false);
    if (lastPath.current !== path) {
      const hash = decodeURIComponent(window.location.hash.slice(1));
      if (!hash || !scrollToHashWhenReady(hash)) window.scrollTo({ top: 0, behavior: "instant" });
      if (lastPath.current !== null) mainRef.current?.focus({ preventScroll: true });
    }
    lastPath.current = path;
  }, [path, search]);

  // The desktop layout closes the mobile menu (mobile.js).
  useEffect(() => {
    if (!narrow) setMenuOpen(false);
  }, [narrow]);

  useEffect(() => {
    document.body.classList.toggle("mobile-menu-open", menuOpen);
    return () => document.body.classList.remove("mobile-menu-open");
  }, [menuOpen]);

  // Escape closes the open menu; Tab stays inside the header while the mobile menu is open.
  useEffect(() => {
    if (!menuOpen && !businessOpen) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (menuOpen) closeMenu(true);
        else {
          setBusinessOpen(false);
          headerRef.current?.querySelector<HTMLElement>(".business-menu summary")?.focus();
        }
        return;
      }
      if (event.key === "Tab" && menuOpen && headerRef.current) {
        const items = [...headerRef.current.querySelectorAll<HTMLElement>("a,button,summary")].filter(
          (element) => element.getClientRects().length > 0 && !(element as HTMLButtonElement).disabled
        );
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [menuOpen, businessOpen, closeMenu]);

  // A click outside closes the business menu on the desktop (complete.js).
  useEffect(() => {
    if (!businessOpen || narrow) return undefined;
    const onClick = (event: MouseEvent) => {
      const menu = headerRef.current?.querySelector(".business-menu");
      if (menu && !menu.contains(event.target as Node)) setBusinessOpen(false);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [businessOpen, narrow]);

  // Compact header and the home section in view (navigation.js), desktop only.
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const desktop = !window.matchMedia?.("(max-width:1119px)").matches;
      setCompact(desktop && window.scrollY > COMPACT_Y);
      let section: string | null = null;
      if (desktop && path === "/") {
        for (const id of ["opportunities", "how-it-works"]) {
          const rect = document.getElementById(id)?.getBoundingClientRect();
          if (rect && rect.top <= SECTION_LINE && rect.bottom > SECTION_LINE) section = id;
        }
      }
      setCurrentSection(section);
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [path]);

  const onNavClick = (event: ReactMouseEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest("a") && narrow) closeMenu();
  };

  const sectionCurrent = (id: string) =>
    id === "opportunities" && path.startsWith("/projects/") ? ("page" as const) : currentSection === id ? ("location" as const) : undefined;
  const pageCurrent = (href: string) => (path === href ? ("page" as const) : undefined);

  const contactLink = (
    <PublicLink aria-current={pageCurrent("/contact")} className="contact" href="/contact" key="contact">
      {t("Contact")}
    </PublicLink>
  );
  const loginLink = (
    <PublicLink className="login" href="/login" key="login">
      {t("Log in")} <Ni glyph="arrow" />
    </PublicLink>
  );
  const language = (
    <LanguageSwitcher
      key="language"
      onOpen={() => {
        closeMenu();
      }}
    />
  );

  return (
    <SiteToastContext.Provider value={toast}>
      <a
        className="bxp-skip-link"
        href="#public-main"
        onClick={(event) => {
          event.preventDefault();
          mainRef.current?.focus();
        }}
      >
        {t("Skip to content")}
      </a>
      <div className="page">
        <div className="public-header-slot">
          <header className={`header${compact ? " is-compact" : ""}${menuOpen ? " menu-open" : ""}`} ref={headerRef}>
            <PublicLink aria-label={t("Banxum home")} className="brand" href="/">
              <img alt="Banxum" height="54" src={LOGO} width="158" />
            </PublicLink>
            <nav aria-label={t("Main navigation")} id="public-navigation" onClick={onNavClick}>
              <HomeSectionLink aria-current={sectionCurrent("opportunities")} section="opportunities">
                {t("Opportunities")}
              </HomeSectionLink>
              <HomeSectionLink aria-current={sectionCurrent("how-it-works")} section="how-it-works">
                {t("How it works")}
              </HomeSectionLink>
              <PublicLink aria-current={pageCurrent("/about")} href="/about">
                {t("About Banxum")}
              </PublicLink>
              <details
                className="business-menu"
                onToggle={(event) => setBusinessOpen((event.currentTarget as HTMLDetailsElement).open)}
                open={businessOpen}
              >
                <summary>{t("For businesses")}</summary>
                <div className="business-links">
                  <PublicLink aria-current={pageCurrent("/companies")} href="/companies">
                    {t("For borrowers")}
                  </PublicLink>
                  <PublicLink aria-current={pageCurrent("/originators")} href="/originators">
                    {t("For loan originators")}
                  </PublicLink>
                </div>
              </details>
              {narrow ? (
                <PublicLink aria-current={pageCurrent("/contact")} className="mobile-contact" href="/contact">
                  {t("Contact")}
                </PublicLink>
              ) : null}
            </nav>
            {/* The language switcher is hidden while multilanguage is paused (IMPLEMENTATION_PLAN 18.0). */}
            <div className="header-actions">
              {isMultilanguageEnabled() ? (narrow ? [contactLink, loginLink, language] : [language, contactLink, loginLink]) : [contactLink, loginLink]}
            </div>
            {narrow ? (
              <button
                aria-controls="public-navigation"
                aria-expanded={menuOpen}
                aria-label={menuOpen ? t("Close menu") : t("Open menu")}
                className="mobile-menu-toggle"
                onClick={() => (menuOpen ? closeMenu() : setMenuOpen(true))}
                ref={toggleRef}
                type="button"
              >
                <svg aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" viewBox="0 0 24 24">
                  <path className="menu-top" d="M3 8h18" />
                  <path className="menu-bottom" d="M3 16h18" />
                </svg>
              </button>
            ) : null}
          </header>
        </div>
        <main className={mainClassName} id="public-main" inert={menuOpen} ref={mainRef} tabIndex={-1}>
          {children}
        </main>
        <PublicFooter divider={footerDivider} inert={menuOpen} onCookieSettings={() => setCookieSettings(true)} />
      </div>
      <CookieNotice
        onClose={() => setCookieSettings(false)}
        onSaved={() => {
          setCookieSettings(false);
          toast(t("Cookie choice saved."));
        }}
        onSettings={() => setCookieSettings(true)}
        settings={cookieSettings}
      />
      <div aria-live="polite" className="bxp-toasts">
        {toasts.map((item) => (
          <div className={`bxp-toast is-${item.tone}`} key={item.id}>
            <span aria-hidden="true" className="ni">
              {item.tone === "info" ? GLYPHS.alert : GLYPHS.checkCircle}
            </span>
            <span>{item.text}</span>
          </div>
        ))}
      </div>
    </SiteToastContext.Provider>
  );
}

/**
 * Scrolls to the element of the address's #section once it exists (a page may render it a few
 * frames later). Returns false when the id is not a plain element id.
 */
function scrollToHashWhenReady(id: string) {
  if (!/^[\w-]+$/.test(id)) return false;
  let tries = 0;
  const attempt = () => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "instant", block: "start" });
      return;
    }
    tries += 1;
    if (tries < 30) window.requestAnimationFrame(attempt);
  };
  if (document.getElementById(id)) attempt();
  else {
    window.scrollTo({ top: 0, behavior: "instant" });
    window.requestAnimationFrame(attempt);
  }
  return true;
}

// ---------------------------------------------------------------------------------------------
// Language: English only for now (U33-DEC-31: DE/FR with Phase 17.8). The design's switcher
// (public-language.js) with German and French marked "Soon".

const LANGUAGES = [
  { code: "en", label: "English", soon: false },
  { code: "de", label: "Deutsch", soon: true },
  { code: "fr", label: "Français", soon: true }
];

function LanguageSwitcher({ onOpen }: { onOpen: () => void }) {
  const t = useT();
  const toast = useSiteToast();
  const narrow = useNarrow();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionsRef = useRef<(HTMLButtonElement | null)[]>([]);

  const close = useCallback((focus = false) => {
    setOpen(false);
    if (focus) triggerRef.current?.focus({ preventScroll: true });
  }, []);

  const show = (last = false) => {
    onOpen();
    setOpen(true);
    window.setTimeout(() => {
      const options = optionsRef.current;
      (last ? options[options.length - 1] : options[0])?.focus({ preventScroll: true });
    }, 0);
  };

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close(true);
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);

  // The layout switch closes the menu (public-language.js).
  useEffect(() => {
    setOpen(false);
  }, [narrow]);

  const onMenuKey = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const options = optionsRef.current.filter(Boolean) as HTMLButtonElement[];
    const index = options.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = (index + (event.key === "ArrowDown" ? 1 : options.length - 1)) % options.length;
      options[next]?.focus();
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      (event.key === "Home" ? options[0] : options[options.length - 1])?.focus();
    }
  };

  const choose = (language: (typeof LANGUAGES)[number]) => {
    if (!language.soon) {
      close(true);
      return;
    }
    toast(
      language.code === "de"
        ? t("The German version of the site follows. It is not available yet.")
        : t("The French version of the site follows. It is not available yet."),
      "ni-globe"
    );
  };

  return (
    <div
      className="language-switcher"
      onBlur={(event) => {
        if (event.relatedTarget && !rootRef.current?.contains(event.relatedTarget as Node)) close();
      }}
      ref={rootRef}
    >
      <button
        aria-controls="language-options"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={t("Language: English")}
        className="language-trigger"
        onClick={() => (open ? close() : show())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            show(event.key === "ArrowUp");
          }
        }}
        ref={triggerRef}
        type="button"
      >
        <svg aria-hidden="true" className="language-globe" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="9" />
          <ellipse cx="12" cy="12" rx="4" ry="9" />
          <path d="M3 12h18" />
        </svg>
        <span aria-hidden="true" className="language-code">
          EN
        </span>
        <svg aria-hidden="true" className="language-chevron" viewBox="0 0 12 12">
          <path d="m2.5 4.5 3.5 3.5 3.5-3.5" />
        </svg>
      </button>
      <div aria-label={t("Language")} className="language-menu" hidden={!open} id="language-options" onKeyDown={onMenuKey} role="menu">
        {LANGUAGES.map((language, index) => (
          <button
            aria-checked={!language.soon}
            aria-disabled={language.soon || undefined}
            className="language-option"
            data-language={language.code}
            key={language.code}
            onClick={() => choose(language)}
            ref={(element) => {
              optionsRef.current[index] = element;
            }}
            role="menuitemradio"
            tabIndex={-1}
            type="button"
          >
            <span lang={language.code}>{language.label}</span>
            {language.soon ? (
              <small className="language-soon">{t("Soon")}</small>
            ) : (
              <svg aria-hidden="true" className="language-check" viewBox="0 0 20 20">
                <path d="m4 10 4 4 8-8" />
              </svg>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Footer (design closing-footer) with the operator identification of U33-DEC-34 and links to the
// October pages that stay until the owner decides (U33-DEC-39: All projects, Statistics, Help).

function PublicFooter({ divider, inert, onCookieSettings }: { divider: boolean; inert: boolean; onCookieSettings: () => void }) {
  const t = useT();
  const company = siteCompany;
  return (
    <footer className="closing-footer" data-section-divider={divider ? "" : undefined} inert={inert}>
      <div className="footer-top">
        <div className="footer-brand">
          <PublicLink aria-label={t("Banxum home")} href="/">
            <img alt="Banxum" src={LOGO} width="139" />
          </PublicLink>
          <p>{t("Swiss Investment Platform")}</p>
        </div>
        <div className="footer-column">
          <h2>{t("Invest")}</h2>
          <HomeSectionLink section="opportunities">{t("Opportunities")}</HomeSectionLink>
          <HomeSectionLink section="how-it-works">{t("How it works")}</HomeSectionLink>
          <HomeSectionLink section="security">{t("Security & collateral")}</HomeSectionLink>
          <PublicLink href="/projects">{t("All projects")}</PublicLink>
          <PublicLink href="/statistics">{t("Statistics")}</PublicLink>
        </div>
        <div className="footer-column">
          <h2>{t("Banxum")}</h2>
          <PublicLink href="/about">{t("About Banxum")}</PublicLink>
          <PublicLink href="/contact">{t("Contact")}</PublicLink>
          <PublicLink href="/help">{t("Help")}</PublicLink>
        </div>
        <div className="footer-column">
          <h2>{t("Business")}</h2>
          <PublicLink href="/companies">{t("For borrowers")}</PublicLink>
          <PublicLink href="/originators">{t("For loan originators")}</PublicLink>
        </div>
      </div>
      <p className="footer-identity">
        {t("Banxum is a brand of {company}, {street}, {city} · UID {uid}", {
          company: company.name,
          street: company.street,
          city: company.city,
          uid: company.uid
        })}
      </p>
      <div className="footer-bottom">
        <span>{t("© {year} Banxum", { year: new Date().getFullYear() })}</span>
        <nav aria-label={t("Legal information")}>
          <PublicLink href="/legal/risk">{t("Risk information")}</PublicLink>
          <PublicLink href="/legal/terms">{t("Terms & conditions")}</PublicLink>
          <PublicLink href="/legal/privacy">{t("Privacy policy")}</PublicLink>
          <PublicLink href="/legal/imprint">{t("Imprint")}</PublicLink>
          <a
            className="footer-cookie-settings"
            href="#"
            onClick={(event) => {
              event.preventDefault();
              onCookieSettings();
            }}
          >
            {t("Cookie settings")}
          </a>
        </nav>
        <span>{t("Capital is at risk.")}</span>
      </div>
    </footer>
  );
}

// ---------------------------------------------------------------------------------------------
// Cookie notice (the design has none; the October notice and its stored choice, cookies.ts,
// in U33 style). Necessary cookies always, measurement only with consent, no advertising.

function CookieNotice({
  settings,
  onSaved,
  onSettings,
  onClose
}: {
  settings: boolean;
  onSaved: () => void;
  onSettings: () => void;
  onClose: () => void;
}) {
  const t = useT();
  const choice = useCookieChoice();
  const [measure, setMeasure] = useState(choice?.measure ?? false);
  useEffect(() => {
    if (settings) setMeasure(choice?.measure ?? false);
  }, [settings, choice]);
  if (choice && !settings) return null;
  const save = (value: boolean) => {
    saveCookieChoice(value);
    onSaved();
  };
  return (
    <div aria-label={t("Cookies")} aria-live="polite" className="bxp-cookie" role="dialog">
      <div className="bxp-cookie-head">
        <h2>{t("Cookies")}</h2>
        {choice ? (
          <button aria-label={t("Close")} className="bxp-cookie-close" onClick={onClose} type="button">
            <Ni glyph="cross" />
          </button>
        ) : null}
      </div>
      <p>
        {t(
          "We use necessary cookies to run the site and keep you signed in. With your consent, we also measure visits to improve the site. No advertising cookies."
        )}{" "}
        <PublicLink href="/legal/cookies">{t("Cookie policy")}</PublicLink>
      </p>
      {settings ? (
        <>
          <label className="bxp-switch">
            <input checked disabled readOnly type="checkbox" />
            <span>{t("Necessary (always on)")}</span>
          </label>
          <label className="bxp-switch">
            <input checked={measure} onChange={(event) => setMeasure(event.target.checked)} type="checkbox" />
            <span>{t("Measurement of visits")}</span>
          </label>
          <div className="bxp-cookie-actions">
            <button className="bxp-button is-primary" onClick={() => save(measure)} type="button">
              {t("Save choice")}
            </button>
          </div>
        </>
      ) : (
        <div className="bxp-cookie-actions">
          <button className="bxp-button is-primary" onClick={() => save(true)} type="button">
            {t("Accept all")}
          </button>
          <button className="bxp-button" onClick={() => save(false)} type="button">
            {t("Necessary only")}
          </button>
          <button className="bxp-button" onClick={onSettings} type="button">
            {t("Settings")}
          </button>
        </div>
      )}
    </div>
  );
}
