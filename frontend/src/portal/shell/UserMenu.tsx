// IP of Webby-Soft SRL.
// Account dropdown of the U33 header (design: #bxm-user-dropdown): user card, available balances with
// "Add funds", Profile & Settings, Help, Language (English only until Phase 17.8), Sign out.
import { useT } from "../../i18n";
import { Dropdown, MoneyAmount, NiIcon, PortalLink } from "../components";
import { brandDisplayName } from "../brand";

export type ShellBalance = { currency: string; availableMinor: number };
export type ShellProfile = { initials: string; name: string; email: string };

export function UserMenu({
  profile,
  status,
  balances,
  addFundsDisabled,
  onAddFunds,
  onSignOut,
  signOutLabel,
  signOutDisabled
}: {
  profile: ShellProfile;
  /** "Verified investor", "Verification pending" or "Read-only view". */
  status: string;
  balances: ShellBalance[];
  addFundsDisabled: boolean;
  onAddFunds: () => void;
  onSignOut: () => void;
  signOutLabel: string;
  signOutDisabled: boolean;
}) {
  const t = useT();
  const [first, ...others] = balances;
  return (
    <Dropdown
      className="user-dropdown"
      id="bxm-user-dropdown"
      menuClassName="dropdown-menu-s1"
      toggle={
        <div className="user-toggle">
          <div className="user-avatar sm"><span>{profile.initials}</span></div>
          <div className="user-info d-none d-md-block">
            <div className="user-status">{status}</div>
            <div className="user-name dropdown-indicator">{profile.name}</div>
          </div>
        </div>
      }
      toggleLabel={t("Account menu")}
    >
      {(close) => (
        <>
          <div className="dropdown-inner user-card-wrap bg-lighter d-none d-md-block">
            <div className="user-card">
              <div className="user-avatar"><span>{profile.initials}</span></div>
              <div className="user-info">
                <span className="lead-text">{profile.name}</span>
                <span className="sub-text">{profile.email}</span>
              </div>
            </div>
          </div>
          {first ? (
            <div className="dropdown-inner user-account-info">
              <h6 className="overline-title-alt">{t("{brand} account · available", { brand: brandDisplayName() })}</h6>
              <MoneyAmount amountMinor={first.availableMinor} as="div" className="user-balance" currency={first.currency} currencyAs="small" />
              {others.map((balance) => (
                <MoneyAmount amountMinor={balance.availableMinor} as="div" className="user-balance-sub" currency={balance.currency} key={balance.currency} />
              ))}
              <a
                aria-disabled={addFundsDisabled || undefined}
                className={`link ${addFundsDisabled ? "disabled" : ""}`.trim()}
                href="#"
                onClick={(event) => {
                  event.preventDefault();
                  if (addFundsDisabled) return;
                  close();
                  onAddFunds();
                }}
                role="button"
              >
                <span>{t("Add funds")}</span> <NiIcon name="wallet-in" />
              </a>
            </div>
          ) : null}
          <div className="dropdown-inner">
            <ul className="link-list">
              <li><PortalLink onNavigate={close} to="settings"><NiIcon name="user-alt" /><span>{t("Profile & Settings")}</span></PortalLink></li>
              <li><PortalLink onNavigate={close} to="faq"><NiIcon name="help-alt" /><span>{t("Help")}</span></PortalLink></li>
              <li className="p30-language">
                {/* One language until Phase 17.8 adds de-CH: shown, not selectable. */}
                <button aria-disabled="true" className="p30-language-toggle" disabled type="button">
                  <NiIcon name="globe" />
                  <span className="p30-language-label">{t("Language")}</span>
                  <span className="p30-language-current">English</span>
                </button>
              </li>
            </ul>
          </div>
          <div className="dropdown-inner">
            <ul className="link-list">
              <li>
                <a
                  aria-disabled={signOutDisabled || undefined}
                  href="#"
                  onClick={(event) => {
                    event.preventDefault();
                    if (signOutDisabled) return;
                    close();
                    onSignOut();
                  }}
                  role="button"
                >
                  <NiIcon name="signout" />
                  <span>{signOutLabel}</span>
                </a>
              </li>
            </ul>
          </div>
        </>
      )}
    </Dropdown>
  );
}
