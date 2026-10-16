// IP of Webby-Soft SRL.
/*
 * Shell of the public site, 1:1 with the design (body.html + shell.js): header with the main
 * navigation and the language dropdown, the phone menu, the footer, the phone call-to-action
 * bar, the cookie notice and the toasts. Differences with the design, on purpose: no prototype
 * bar, "Log in" opens /login and "Open account" /register in the app, links are real paths
 * ("/projects" instead of "#/projects").
 *
 * Behaviour (as shell.js): the burger toggles body.site-menu-open and its icon, Escape and any
 * menu link close the menu, a page change closes it, scrolls to the top at once and focuses
 * <main> (not on the first load). The phone bar shows after 520 px of scrolling once the cookie
 * notice is answered and the menu is closed; body.site-has-cta is set once it is answered.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { NiIcon, SiteLink } from "./components";
import { siteCompany } from "./content";
import { SiteToastContext, useSiteNav, useSiteToast } from "./context";
import { saveCookieChoice, useCookieChoice } from "./cookies";

const LOGO = "/brand/banxum-logo.svg";
const LOGO_WHITE = "/brand/banxum-logo-white.svg";
const TOAST_MS = 3200;
const CTA_SCROLL_Y = 520;

/** Header navigation (data-nav in the design): active on the path and the pages below it. */
const MAIN_NAV = [
  { href: "/projects", label: "Projects" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/companies", label: "For companies" },
  { href: "/about", label: "About" },
  { href: "/help", label: "Help" }
];

const MENU_NAV = [
  { href: "/projects", label: "Projects" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/companies", label: "For companies" },
  { href: "/originators", label: "For loan originators" },
  { href: "/about", label: "About" },
  { href: "/statistics", label: "Statistics" },
  { href: "/help", label: "Help" }
];

type Toast = { id: number; text: string; icon: string };

export function SiteShell({ children }: { children: ReactNode }) {
  const { path, search } = useSiteNav();
  const [menuOpen, setMenuOpen] = useState(false);
  const [cookieSettings, setCookieSettings] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastSeq = useRef(0);
  const mainRef = useRef<HTMLElement>(null);
  const lastPath = useRef<string | null>(null);
  const cookieChoice = useCookieChoice();
  const answered = Boolean(cookieChoice);

  const toast = useCallback((text: string, icon = "ni-check-circle") => {
    toastSeq.current += 1;
    const id = toastSeq.current;
    setToasts((list) => [...list, { id, text, icon }]);
    window.setTimeout(() => setToasts((list) => list.filter((item) => item.id !== id)), TOAST_MS);
  }, []);

  // A new page: close the menu; a new path: to the top at once, and focus <main> after the first load.
  useLayoutEffect(() => {
    setMenuOpen(false);
    if (lastPath.current !== path) {
      // Instant: the design CSS makes scrolling smooth, which is wrong for a new page.
      window.scrollTo({ top: 0, behavior: "instant" });
      if (lastPath.current !== null) mainRef.current?.focus({ preventScroll: true });
    }
    lastPath.current = path;
  }, [path, search]);

  useEffect(() => {
    document.body.classList.toggle("site-menu-open", menuOpen);
    if (!menuOpen) return undefined;
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  useEffect(() => {
    document.body.classList.toggle("site-has-cta", answered);
  }, [answered]);

  useEffect(
    () => () => {
      document.body.classList.remove("site-menu-open", "site-has-cta");
    },
    []
  );

  useEffect(() => {
    const update = () => setScrolled(window.scrollY > CTA_SCROLL_Y);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  const ctaShown = scrolled && answered && !menuOpen;
  const isActive = (href: string) => path === href || path.startsWith(`${href}/`);

  return (
    <SiteToastContext.Provider value={toast}>
      <a
        className="visually-hidden-focusable"
        href="#site-main"
        onClick={(event) => {
          event.preventDefault();
          mainRef.current?.focus();
        }}
      >
        Skip to content
      </a>

      <header className="site-header">
        <div className="site-wrap site-header-inner">
          <SiteLink aria-label="Banxum home" className="site-brand" href="/">
            <img alt="Banxum" src={LOGO} />
          </SiteLink>
          <nav aria-label="Main" className="site-nav" id="site-nav">
            {MAIN_NAV.map((item) => (
              <SiteLink
                aria-current={isActive(item.href) ? "page" : undefined}
                className={isActive(item.href) ? "active" : undefined}
                data-nav={item.href}
                href={item.href}
                key={item.href}
              >
                {item.label}
              </SiteLink>
            ))}
          </nav>
          <div className="site-header-actions">
            <LanguageDropdown />
            <SiteLink className="btn btn-md btn-site-outline site-hide-menu" href="/login">
              Log in
            </SiteLink>
            <SiteLink className="btn btn-md btn-primary" href="/register">
              Open account
            </SiteLink>
            <button
              aria-controls="site-menu"
              aria-expanded={menuOpen}
              aria-label="Menu"
              className="site-burger"
              onClick={() => setMenuOpen((open) => !open)}
              type="button"
            >
              <NiIcon name={menuOpen ? "ni-cross" : "ni-menu"} />
            </button>
          </div>
        </div>
      </header>

      {/* Hidden while closed (CSS hides it too): its links are not reachable then. */}
      <div
        className="site-menu"
        hidden={!menuOpen}
        id="site-menu"
        onClick={(event) => {
          // The menu links point at the current page too: close the menu then.
          if ((event.target as HTMLElement).closest("a")) setMenuOpen(false);
        }}
      >
        <div className="site-wrap">
          <nav aria-label="Menu">
            {MENU_NAV.map((item) => (
              <SiteLink href={item.href} key={item.href}>
                {item.label}
              </SiteLink>
            ))}
          </nav>
          <div className="site-actions">
            <SiteLink className="btn btn-lg btn-site-outline" href="/login">
              Log in
            </SiteLink>
            <SiteLink className="btn btn-lg btn-primary" href="/register">
              Open account
            </SiteLink>
          </div>
          <div className="mt-4">
            <LanguageDropdown inMenu />
          </div>
        </div>
      </div>

      <main id="site-main" ref={mainRef} tabIndex={-1}>
        {children}
      </main>

      <SiteFooter onCookieSettings={() => setCookieSettings(true)} />

      <div aria-hidden={!ctaShown} className={`site-mobile-cta${ctaShown ? " is-visible" : ""}`} id="site-mobile-cta">
        <SiteLink className="btn btn-lg btn-site-outline" href="/projects" tabIndex={ctaShown ? undefined : -1}>
          Projects
        </SiteLink>
        <SiteLink className="btn btn-lg btn-primary" href="/register" tabIndex={ctaShown ? undefined : -1}>
          Open account
        </SiteLink>
      </div>

      <div id="site-cookie-root">
        {!answered || cookieSettings ? (
          <CookieNotice
            onSaved={() => {
              setCookieSettings(false);
              toast("Cookie choice saved.");
            }}
            onSettings={() => setCookieSettings(true)}
            settings={cookieSettings}
          />
        ) : null}
      </div>
      <div aria-live="polite" className="bxm-toasts" id="bxm-toasts">
        {toasts.map((item) => (
          <div className="bxm-toast" key={item.id}>
            <NiIcon name={item.icon} />
            <span>{item.text}</span>
          </div>
        ))}
      </div>
    </SiteToastContext.Provider>
  );
}

// ---------------------------------------------------------------------------------------------
// Language: English only for now; German and French are announced with a toast. Behaves like
// the design's Bootstrap dropdown (header: drops down to the right edge; menu: drops up).

const LANGUAGES = [
  { code: "EN", label: "English" },
  { code: "DE", label: "Deutsch" },
  { code: "FR", label: "Français" }
];

function LanguageDropdown({ inMenu = false }: { inMenu?: boolean }) {
  const toast = useSiteToast();
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(42);
  const rootRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("click", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const show = (focusFirst = false) => {
    // Popper's offset in the design: the toggle's height and 2 px.
    setOffset((toggleRef.current?.offsetHeight || 40) + 2);
    setOpen(true);
    if (focusFirst) window.setTimeout(() => menuRef.current?.querySelector("a")?.focus(), 0);
  };

  const choose = (code: string) => {
    setOpen(false);
    if (code === "EN") return;
    toast(`The ${code === "DE" ? "German" : "French"} version follows once the English texts are approved.`, "ni-globe");
  };

  const onMenuKey = (event: KeyboardEvent<HTMLUListElement>) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const items = [...(menuRef.current?.querySelectorAll("a") ?? [])];
    const index = items.indexOf(document.activeElement as HTMLAnchorElement);
    const next = event.key === "ArrowDown" ? Math.min(items.length - 1, index + 1) : Math.max(0, index - 1);
    items[next]?.focus();
  };

  const style = open
    ? inMenu
      ? { position: "absolute" as const, inset: "auto auto 0px 0px", margin: "0px", transform: `translate(0px, -${offset}px)` }
      : { position: "absolute" as const, inset: "0px 0px auto auto", margin: "0px", transform: `translate(0px, ${offset}px)` }
    : undefined;

  return (
    <div className={`dropdown site-lang ${inMenu ? "dropup" : "site-hide-menu"}`} ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="Language: English"
        className={`site-lang-toggle${open ? " show" : ""}`}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            show(true);
          }
        }}
        ref={toggleRef}
        type="button"
      >
        <NiIcon name="ni-globe" />
        <span>{inMenu ? "English" : "EN"}</span>
        <NiIcon name="ni-chevron-down" />
      </button>
      <ul
        className={`dropdown-menu${inMenu ? "" : " dropdown-menu-end"} site-lang-menu${open ? " show" : ""}`}
        data-popper-placement={open ? (inMenu ? "top-start" : "bottom-end") : undefined}
        onKeyDown={onMenuKey}
        ref={menuRef}
        style={style}
      >
        {LANGUAGES.map((language) => (
          <li key={language.code}>
            <a
              aria-current={language.code === "EN" ? "true" : undefined}
              className={language.code === "EN" ? "active" : undefined}
              href="#"
              onClick={(event) => {
                event.preventDefault();
                choose(language.code);
              }}
            >
              <span>{language.label}</span>
              {language.code === "EN" ? <NiIcon name="ni-check" /> : <small>Soon</small>}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Cookie notice: necessary cookies always, measurement only with consent, no advertising.

function CookieNotice({ settings, onSaved, onSettings }: { settings: boolean; onSaved: () => void; onSettings: () => void }) {
  const choice = useCookieChoice();
  const [measure, setMeasure] = useState(choice?.measure ?? false);
  const save = (value: boolean) => {
    saveCookieChoice(value);
    onSaved();
  };
  return (
    <div aria-label="Cookies" aria-live="polite" className="site-cookie" role="dialog">
      <h6 className="site-h4">Cookies</h6>
      <p>
        We use necessary cookies to run the site and keep you signed in. With your consent, we also measure visits to
        improve the site. No advertising cookies. <SiteLink href="/legal/cookies">Cookie policy</SiteLink>
      </p>
      {settings ? (
        <>
          <div className="form-check form-switch">
            <input checked className="form-check-input" disabled id="ck-necessary" readOnly type="checkbox" />
            <label className="form-check-label" htmlFor="ck-necessary">
              Necessary (always on)
            </label>
          </div>
          <div className="form-check form-switch mb-3">
            <input
              checked={measure}
              className="form-check-input"
              id="ck-measure"
              onChange={(event) => setMeasure(event.target.checked)}
              type="checkbox"
            />
            <label className="form-check-label" htmlFor="ck-measure">
              Measurement of visits
            </label>
          </div>
          <div className="site-actions">
            <button className="btn btn-md btn-primary" onClick={() => save(measure)} type="button">
              Save choice
            </button>
          </div>
        </>
      ) : (
        <div className="site-actions">
          <button className="btn btn-md btn-primary" onClick={() => save(true)} type="button">
            Accept all
          </button>
          <button className="btn btn-md btn-site-outline" onClick={() => save(false)} type="button">
            Necessary only
          </button>
          <button className="btn btn-md btn-site-outline" onClick={onSettings} type="button">
            Settings
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Footer

function SiteFooter({ onCookieSettings }: { onCookieSettings: () => void }) {
  const company = siteCompany.name;
  return (
    <footer className="site-footer bxm-ink">
      <div className="site-wrap">
        <div className="site-footer-grid">
          <div className="site-footer-brand">
            <SiteLink aria-label="Banxum home" href="/">
              <img alt="Banxum" src={LOGO_WHITE} />
            </SiteLink>
            <p>
              Loans to companies in Switzerland and the EU, funded by investors through the assignment of claims. Owned and
              operated by {company}.
            </p>
          </div>
          <div className="site-footer-col">
            <h6>Invest</h6>
            <ul>
              <li>
                <SiteLink href="/projects">Projects</SiteLink>
              </li>
              <li>
                <SiteLink href="/how-it-works">How it works</SiteLink>
              </li>
              <li>
                <SiteLink href="/statistics">Statistics</SiteLink>
              </li>
              <li>
                <SiteLink href="/legal/risk">Risks</SiteLink>
              </li>
            </ul>
          </div>
          <div className="site-footer-col">
            <h6>Borrow</h6>
            <ul>
              <li>
                <SiteLink href="/companies">For companies</SiteLink>
              </li>
              <li>
                <SiteLink href="/originators">For loan originators</SiteLink>
              </li>
            </ul>
          </div>
          <div className="site-footer-col">
            <h6>Company</h6>
            <ul>
              <li>
                <SiteLink href="/about">About</SiteLink>
              </li>
              <li>
                <SiteLink href="/guides">Guides</SiteLink>
              </li>
              <li>
                <SiteLink href="/contact">Contact</SiteLink>
              </li>
            </ul>
          </div>
          <div className="site-footer-col">
            <h6>Help</h6>
            <ul>
              <li>
                <SiteLink href="/help">Questions</SiteLink>
              </li>
              <li>
                <SiteLink href="/legal/complaints">Complaints</SiteLink>
              </li>
              <li>
                <a
                  href="#"
                  onClick={(event) => {
                    event.preventDefault();
                    onCookieSettings();
                  }}
                >
                  Cookie settings
                </a>
              </li>
            </ul>
          </div>
        </div>
        <div className="site-footer-legal">
          <p>
            Banxum® is a registered trademark. The Banxum platform is owned and operated by {company}, a Swiss financial
            company with a share capital of {siteCompany.capital}, affiliated to VQF, a self-regulatory organisation recognised
            by FINMA, and to FINOS, the Swiss financial ombudsman. Garanta is not a bank: money in a Banxum wallet is not a
            deposit and is not protected by the Swiss deposit insurance.
          </p>
          <p>
            Lending to companies puts your capital at risk: a borrower can pay late or not at all, and you may not be able to
            sell your investment before it ends. Past results do not predict future results.
          </p>
        </div>
        <div className="site-footer-bottom">
          <span className="site-footer-copy">
            © {new Date().getFullYear()} {company}
            <span className="site-proudly">
              <svg aria-hidden="true" height="14" viewBox="0 0 14 14" width="14">
                <rect fill="#DA291C" height="14" width="14" />
                <rect fill="#fff" height="8.4" width="2.4" x="5.8" y="2.8" />
                <rect fill="#fff" height="2.4" width="8.4" x="2.8" y="5.8" />
              </svg>
              Proudly Swiss
            </span>
          </span>
          <nav aria-label="Legal">
            <SiteLink href="/legal/terms">Terms</SiteLink>
            <SiteLink href="/legal/privacy">Privacy</SiteLink>
            <SiteLink href="/legal/cookies">Cookies</SiteLink>
            <SiteLink href="/legal/risk">Risk information</SiteLink>
            <SiteLink href="/legal/imprint">Imprint</SiteLink>
          </nav>
        </div>
      </div>
    </footer>
  );
}
