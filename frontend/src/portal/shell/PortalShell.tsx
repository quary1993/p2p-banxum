// IP of Webby-Soft SRL.
/*
 * The U33 investor shell (design DOM: .nk-app-root > .nk-main > .nk-sidebar + .nk-wrap > .nk-header,
 * .nk-content, .nk-footer). Data and actions come from InvestorShell (App.tsx), which keeps the
 * session, PIN, KYC and account-state gates. Screens render inside .nk-content-body.
 *
 * Folder convention of the investor area: portal/shell (this frame), portal/components (shared U33
 * building blocks, see components/index.ts), portal/screens/<area>/<Name>Screen.tsx (one screen per
 * route; App.tsx only maps routes to screens), portal/u33 (generated stylesheet, overrides, assets).
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import type { InvestorNotifications } from "../../api/generated/banxumApi";
import { useT } from "../../i18n";
import type { RouteName } from "../../investorPortal/types";
import { PortalLink } from "../components";
import { brandDisplayName } from "../brand";
import { Header } from "./Header";
import type { NavCount, NavItem } from "./nav";
import { Sidebar, type NavMarker } from "./Sidebar";
import { MOBILE_SHELL_QUERY, useMediaQuery } from "./useMediaQuery";
import type { ShellBalance, ShellProfile } from "./UserMenu";

const COMPACT_STORAGE_KEY = "banxum.sidebarCompact";

function readCompact() {
  try {
    return window.localStorage.getItem(COMPACT_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export type PortalShellProps = {
  activeRoute: RouteName;
  profile: ShellProfile;
  status: string;
  /** Available balance per currency, EUR first. */
  balances: ShellBalance[];
  counts: Partial<Record<NavCount, number>>;
  markers?: Partial<Record<RouteName, NavMarker>>;
  extraNavItems?: Partial<Record<string, NavItem[]>>;
  notifications: InvestorNotifications | undefined;
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
  addFundsDisabled: boolean;
  onAddFunds: () => void;
  onSignOut: () => void;
  signOutLabel: string;
  signOutDisabled: boolean;
  /** Banners above the screen (sign-out error, preview data, read-only view, frozen account). */
  notices?: ReactNode;
  /** Dialogs owned by the shell (Add funds, payout IBAN). */
  dialogs?: ReactNode;
  children: ReactNode;
};

export function PortalShell(props: PortalShellProps) {
  const t = useT();
  const mobile = useMediaQuery(MOBILE_SHELL_QUERY);
  const [compact, setCompact] = useState(readCompact);
  const [mobileOpen, setMobileOpen] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const toggleCompact = useCallback(() => {
    setCompact((value) => {
      try {
        window.localStorage.setItem(COMPACT_STORAGE_KEY, value ? "0" : "1");
      } catch {
        // Kept for this visit only.
      }
      return !value;
    });
  }, []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);
  const toggleMobile = useCallback(() => {
    setMobileOpen((open) => {
      if (!open) returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      return !open;
    });
  }, []);

  // The phone menu: html.mobile-menu-open (design CSS), focus inside while open, Escape closes,
  // focus returns to the menu button. Leaving the phone layout closes it.
  const menuOpen = mobile && mobileOpen;
  useEffect(() => {
    const html = document.documentElement;
    html.classList.toggle("mobile-menu-open", menuOpen);
    if (!menuOpen) return undefined;
    sidebarRef.current?.querySelector<HTMLElement>("a.nk-menu-link")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setMobileOpen(false);
        return;
      }
      if (event.key !== "Tab" || !sidebarRef.current) return;
      const focusable = Array.from(sidebarRef.current.querySelectorAll<HTMLElement>("a[href], button:not([disabled])")).filter((element) => element.offsetParent !== null || element === document.activeElement);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      html.classList.remove("mobile-menu-open");
      const target = returnFocusRef.current;
      returnFocusRef.current = null;
      if (target?.isConnected) target.focus({ preventScroll: true });
    };
  }, [menuOpen]);
  useEffect(() => {
    if (!mobile) setMobileOpen(false);
  }, [mobile]);

  const year = new Date().getFullYear();
  return (
    <div className="nk-app-root" id="bxm-app">
      <a
        className="u33-skip-link"
        href="#bxm-view"
        onClick={(event) => {
          event.preventDefault();
          const target = document.getElementById("bxm-view");
          if (!target) return;
          target.setAttribute("tabindex", "-1");
          target.focus();
        }}
      >
        {t("Skip to main content")}
      </a>
      <div className="nk-main">
        <Sidebar
          activeRoute={props.activeRoute}
          compact={compact}
          counts={props.counts}
          extraItems={props.extraNavItems}
          markers={props.markers}
          mobile={mobile}
          mobileOpen={mobileOpen}
          onCloseMobile={closeMobile}
          onNavigate={closeMobile}
          onToggleCompact={toggleCompact}
          ref={sidebarRef}
        />
        <div className="nk-wrap">
          <Header
            addFundsDisabled={props.addFundsDisabled}
            balances={props.balances}
            mobile={mobile}
            mobileOpen={mobileOpen}
            notifications={props.notifications}
            onAddFunds={props.onAddFunds}
            onMarkAllRead={props.onMarkAllRead}
            onMarkRead={props.onMarkRead}
            onNavigate={closeMobile}
            onSignOut={props.onSignOut}
            onToggleMobile={toggleMobile}
            profile={props.profile}
            signOutDisabled={props.signOutDisabled}
            signOutLabel={props.signOutLabel}
            status={props.status}
          />
          <div className="nk-content">
            <div className="container-fluid">
              <div className="nk-content-inner">
                <div className="nk-content-body ra-desktop" id="bxm-view">
                  {props.notices ? <div className="u33-shell-notices">{props.notices}</div> : null}
                  {props.children}
                </div>
              </div>
            </div>
          </div>
          <footer className="nk-footer">
            <div className="container-fluid">
              <div className="nk-footer-wrap">
                <div className="nk-footer-copyright">&copy; {year} {brandDisplayName()}</div>
                <nav aria-label={t("Legal and help")} className="nk-footer-links">
                  <ul className="nav nav-sm">
                    <li className="nav-item"><a className="nav-link" href="/legal/terms" rel="noreferrer" target="_blank">{t("Terms")}</a></li>
                    <li className="nav-item"><a className="nav-link" href="/legal/privacy" rel="noreferrer" target="_blank">{t("Privacy")}</a></li>
                    <li className="nav-item"><PortalLink className="nav-link" to="faq">{t("Help")}</PortalLink></li>
                  </ul>
                </nav>
              </div>
            </div>
          </footer>
        </div>
      </div>
      {mobile ? <button aria-label={t("Close navigation")} className="mobile-menu-shade" hidden={!mobileOpen} onClick={closeMobile} tabIndex={-1} type="button" /> : null}
      {props.dialogs}
    </div>
  );
}
