// IP of Webby-Soft SRL.
// Account dropdown of the U33 header (design: #bxm-user-dropdown): user card, available balances with
// "Add funds", the Profile & Settings pages (Personal information, Security, Bank accounts,
// Preferences), Language (English / Deutsch, U33-DEC-31), Sign out. Help is in the sidebar footer.
import { useState } from "react";

import { useT } from "../../i18n";
import { INTERFACE_LANGUAGES, usePreferredLanguage } from "../../i18n/language";
import { useSetInterfaceLanguage } from "../../investorPortal/languagePreference";
import { Dropdown, MoneyAmount, NiIcon, PortalLink } from "../components";
import { brandDisplayName } from "../brand";
import { clickOnSpace } from "../components/keyboard";

export type ShellBalance = { currency: string; availableMinor: number };

// The design's account-menu entries: Profile & Settings tabs (/settings/<tab>), with its icons.
const SETTINGS_ENTRIES: Array<[string, string, string]> = [
  ["personal", "user-alt", "Personal information"],
  ["security", "lock-alt", "account|Security"],
  ["bank-accounts", "building", "Bank accounts"],
  ["preferences", "setting", "Preferences"]
];
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
  const language = usePreferredLanguage();
  const setLanguage = useSetInterfaceLanguage();
  const [languageOpen, setLanguageOpen] = useState(false);
  const current = INTERFACE_LANGUAGES.find((option) => option.value === language) ?? INTERFACE_LANGUAGES[0];
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
                onKeyDown={clickOnSpace}
                role="button"
              >
                <span>{t("Add funds")}</span> <NiIcon name="wallet-in" />
              </a>
            </div>
          ) : null}
          <div className="dropdown-inner">
            <ul className="link-list">
              {SETTINGS_ENTRIES.map(([tab, icon, label]) => (
                <li key={tab}><PortalLink onNavigate={close} params={{ tab }} to="settings"><NiIcon name={icon} /><span>{t(label)}</span></PortalLink></li>
              ))}
              <li className="p30-language">
                <button
                  aria-controls="p30-language-options"
                  aria-expanded={languageOpen}
                  className="p30-language-toggle"
                  onClick={() => setLanguageOpen((open) => !open)}
                  type="button"
                >
                  <NiIcon name="globe" />
                  <span className="p30-language-label">{t("Language")}</span>
                  <span className="p30-language-current">{current.label}</span>
                  <NiIcon className="p30-language-chevron" name="chevron-down" />
                </button>
                <div aria-label={t("Language")} className="p30-language-options" hidden={!languageOpen} id="p30-language-options" role="group">
                  {INTERFACE_LANGUAGES.map((option) => (
                    <button
                      aria-pressed={option.value === language}
                      data-p30-language={option.value}
                      key={option.value}
                      lang={option.value}
                      onClick={() => {
                        setLanguage(option.value);
                        setLanguageOpen(false);
                      }}
                      type="button"
                    >
                      <span>{option.label}</span>
                      <NiIcon name="check" />
                    </button>
                  ))}
                </div>
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
                  onKeyDown={clickOnSpace}
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
