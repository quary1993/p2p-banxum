// IP of Webby-Soft SRL.
// Sidebar of the U33 shell (design: .nk-sidebar.r75-sidebar): logo, collapse toggle, grouped menu with
// counts, identity block (U33-DEC-34) and Help. On phones it is the off-canvas menu (html.mobile-menu-open).
import { forwardRef } from "react";

import { useT } from "../../i18n";
import type { RouteName } from "../../investorPortal/types";
import { NiIcon, PortalLink } from "../components";
import { brandDisplayName, isBanxumBrand, operatorName } from "../brand";
import { HELP_NAV_ITEM, NAV_GROUPS, type NavCount, type NavItem } from "./nav";

/** A marker on a menu entry that needs attention (text shown, label read by screen readers). */
export type NavMarker = { text: string; label: string };

export type SidebarProps = {
  activeRoute: RouteName;
  counts: Partial<Record<NavCount, number>>;
  markers?: Partial<Record<RouteName, NavMarker>>;
  /** Extra items per group label (Currency exchange when switched on). */
  extraItems?: Partial<Record<string, NavItem[]>>;
  compact: boolean;
  onToggleCompact: () => void;
  mobile: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onNavigate: () => void;
};

function MenuLink({ item, active, count, marker, onNavigate }: { item: NavItem; active: boolean; count?: number; marker?: NavMarker; onNavigate: () => void }) {
  const t = useT();
  return (
    <li className={`nk-menu-item ${active ? "active current-page" : ""}`.trim()} data-section={item.section}>
      <PortalLink aria-current={active ? "page" : undefined} className="nk-menu-link" onNavigate={onNavigate} to={item.route}>
        <span className="nk-menu-icon"><NiIcon name={item.icon} /></span>
        <span className="nk-menu-text">{t(item.label)}</span>
        {count ? <span className="nk-menu-badge">{count}</span> : null}
        {marker ? <span aria-label={marker.label} className="nk-menu-badge u33-menu-alert" role="img">{marker.text}</span> : null}
      </PortalLink>
    </li>
  );
}

export const Sidebar = forwardRef<HTMLDivElement, SidebarProps>(function Sidebar(
  { activeRoute, counts, markers, extraItems, compact, onToggleCompact, mobile, mobileOpen, onCloseMobile, onNavigate },
  ref
) {
  const t = useT();
  const brand = brandDisplayName();
  return (
    <div
      className={`nk-sidebar nk-sidebar-fixed r75-sidebar ${compact && !mobile ? "is-compact" : ""} ${mobile ? "nk-sidebar-mobile" : ""}`.replace(/\s+/g, " ").trim()}
      data-content="sidebarMenu"
      inert={mobile && !mobileOpen ? true : undefined}
      ref={ref}
    >
      <div className="nk-sidebar-element nk-sidebar-head">
        <div className="nk-sidebar-brand">
          <PortalLink aria-label={t("{brand} overview", { brand })} className="logo-link nk-sidebar-logo bxm-logo bxm-logo-md" onNavigate={onNavigate} to="dashboard">
            {isBanxumBrand() ? (
              <>
                <img alt={brand} className="bxm-logo-full" src="/brand/banxum-logo.svg" />
                <span className="bxm-logo-symbol"><img alt={brand} src="/brand/banxum-symbol.svg" /><span aria-hidden="true" className="bxm-symbol-r">®</span></span>
              </>
            ) : (
              <span className="bxm-logo-text">{brand}</span>
            )}
          </PortalLink>
        </div>
        <div className="nk-menu-trigger me-n2">
          <a
            aria-expanded={!compact}
            aria-label={compact ? t("Expand the menu") : t("Collapse the menu")}
            className="nk-quick-nav-icon bxm-compact-toggle d-none d-xl-inline-flex"
            href="#"
            onClick={(event) => {
              event.preventDefault();
              onToggleCompact();
            }}
            role="button"
            title={compact ? t("Expand the menu") : t("Collapse the menu")}
          >
            <NiIcon name="menu" />
          </a>
        </div>
        {mobile ? (
          <button aria-label={t("Close navigation")} className="mobile-menu-close" onClick={onCloseMobile} type="button">
            <NiIcon name="cross" />
          </button>
        ) : null}
      </div>
      <div className="nk-sidebar-element">
        <div className="nk-sidebar-body">
          <div className="nk-sidebar-content">
            <nav aria-label={t("Investor portal navigation")} className="nk-sidebar-menu">
              <ul className="nk-menu" id="bxm-menu">
                {NAV_GROUPS.map((group) => (
                  <MenuGroup activeRoute={activeRoute} counts={counts} extra={extraItems?.[group.label] ?? []} items={group.items} key={group.label} label={group.label} markers={markers} onNavigate={onNavigate} />
                ))}
              </ul>
            </nav>
          </div>
        </div>
      </div>
      <div className="nk-sidebar-footer">
        {/* U33-DEC-34: the brand plus a discreet operator line; address/UID stay in the legal area. */}
        <div className="refined-operator"><strong>{brand}</strong><span>{t("A brand of {operator}", { operator: operatorName })}</span></div>
        <ul className="nk-menu nk-menu-footer">
          <MenuLink active={activeRoute === HELP_NAV_ITEM.route} item={HELP_NAV_ITEM} onNavigate={onNavigate} />
        </ul>
      </div>
    </div>
  );
});

function MenuGroup({ label, items, extra, activeRoute, counts, markers, onNavigate }: { label: string; items: NavItem[]; extra: NavItem[]; activeRoute: RouteName; counts: Partial<Record<NavCount, number>>; markers?: Partial<Record<RouteName, NavMarker>>; onNavigate: () => void }) {
  const t = useT();
  return (
    <>
      <li className="nk-menu-heading"><h6 className="overline-title text-primary-alt">{t(label)}</h6></li>
      {[...items, ...extra].map((item) => (
        <MenuLink active={activeRoute === item.route} count={item.count ? counts[item.count] : undefined} item={item} key={item.route} marker={markers?.[item.route]} onNavigate={onNavigate} />
      ))}
    </>
  );
}
