// IP of Webby-Soft SRL.
// Header of the U33 shell (design: .nk-header.is-light): mobile menu button and logo, available balance
// per currency (EUR then CHF, each a link to Account), account dropdown and notifications bell.
import type { InvestorNotifications } from "../../api/generated/banxumApi";
import { useT } from "../../i18n";
import { formatMoneyLabel } from "../../investorPortal/format";
import { NiIcon, PortalLink } from "../components";
import { brandDisplayName, isBanxumBrand } from "../brand";
import { NotificationsMenu } from "./NotificationsMenu";
import { UserMenu, type ShellBalance, type ShellProfile } from "./UserMenu";

export type HeaderProps = {
  profile: ShellProfile;
  status: string;
  balances: ShellBalance[];
  notifications: InvestorNotifications | undefined;
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
  addFundsDisabled: boolean;
  onAddFunds: () => void;
  onSignOut: () => void;
  signOutLabel: string;
  signOutDisabled: boolean;
  mobile: boolean;
  mobileOpen: boolean;
  onToggleMobile: () => void;
  onNavigate: () => void;
};

export function Header(props: HeaderProps) {
  const t = useT();
  const brand = brandDisplayName();
  return (
    <header aria-label={t("Investor account header")} className="nk-header nk-header-fixed is-light">
      <div className="container-fluid">
        <div className="nk-header-wrap">
          {props.mobile ? (
            <button aria-expanded={props.mobileOpen} aria-label={t("Open navigation")} className="mobile-menu-toggle" onClick={props.onToggleMobile} type="button">
              <NiIcon name="menu" />
            </button>
          ) : null}
          <div className="nk-header-brand d-xl-none">
            <PortalLink aria-label={t("{brand} overview", { brand })} className="logo-link bxm-logo bxm-logo-bar" onNavigate={props.onNavigate} to="dashboard">
              {isBanxumBrand() ? <img alt={brand} src="/brand/banxum-logo-bar.svg" /> : <span className="bxm-logo-text">{brand}</span>}
            </PortalLink>
          </div>
          <div className="nk-header-news d-none d-xl-block bxm-account-shortcut" id="bxm-header-news">
            {props.balances.length > 0 ? (
              <div aria-label={t("Available balance")} className="r65-balances" role="group">
                <span>{t("Available balance")}</span>
                {props.balances.map((balance) => {
                  const label = formatMoneyLabel(balance.currency, balance.availableMinor);
                  return (
                    <PortalLink aria-label={t("{amount}, view {currency} account", { amount: label, currency: balance.currency })} key={balance.currency} onNavigate={props.onNavigate} to="balances">
                      <strong>{label}</strong>
                      <NiIcon name="chevron-right" />
                    </PortalLink>
                  );
                })}
              </div>
            ) : null}
          </div>
          <div className="nk-header-tools">
            <ul className="nk-quick-nav">
              <UserMenu
                addFundsDisabled={props.addFundsDisabled}
                balances={props.balances}
                onAddFunds={props.onAddFunds}
                onSignOut={props.onSignOut}
                profile={props.profile}
                signOutDisabled={props.signOutDisabled}
                signOutLabel={props.signOutLabel}
                status={props.status}
              />
              <NotificationsMenu notifications={props.notifications} onMarkAllRead={props.onMarkAllRead} onMarkRead={props.onMarkRead} />
            </ul>
          </div>
        </div>
      </div>
    </header>
  );
}
