// IP of Webby-Soft SRL.
// Profile & Settings (design: main.ps-page with nav.ps-tabs; #/settings/:tab). Each tab has its own
// address (/settings/security...), so the account menu and Help can link straight to it.
import "./account.css";

import { useEffect } from "react";

import { useT } from "../../../i18n";
import { PageHead, Tabs, type TabItem } from "../../components";
import { BankAccountsTab } from "./settings/BankAccountsTab";
import { DeclarationsTab } from "./settings/DeclarationsTab";
import { NotificationsTab } from "./settings/NotificationsTab";
import { PersonalTab } from "./settings/PersonalTab";
import { PreferencesTab } from "./settings/PreferencesTab";
import { SecurityTab } from "./settings/SecurityTab";
import { settingsView, type SettingsTab } from "./settings/settingsTabs";
import { useAccountData, type PreviewProfile } from "./settings/useAccountData";

const TAB_LABELS: Array<[SettingsTab, string]> = [
  ["personal", "Personal details"],
  ["security", "account|Security"],
  ["declarations", "Declarations"],
  ["bank-accounts", "Bank accounts"],
  ["notifications", "Notifications"],
  ["preferences", "Preferences"]
];

export function SettingsScreen({ tab: tabParam, previewProfile }: { tab?: string; previewProfile?: PreviewProfile }) {
  const t = useT();
  const { tab, section } = settingsView(tabParam);
  const account = useAccountData(previewProfile);
  const items: TabItem<SettingsTab>[] = TAB_LABELS.map(([value, label]) => ({ value, label: t(label), to: "settings", params: { tab: value } }));
  // On a phone the tab bar scrolls sideways: keep the active tab in view, as the design does.
  useEffect(() => {
    const bar = document.querySelector<HTMLElement>("nav.ps-tabs");
    const active = bar?.querySelector<HTMLElement>("a.active");
    if (!bar || !active || bar.scrollWidth <= bar.clientWidth) return;
    bar.scrollLeft = Math.max(0, active.offsetLeft - bar.offsetLeft - (bar.clientWidth - active.offsetWidth) / 2);
  }, [tab]);
  return (
    <main className="ps-page" data-settings-tab={tab}>
      <PageHead title={t("Profile & Settings")} />
      <Tabs items={items} label={t("Profile and settings sections")} value={tab} variant="ps-tabs" />
      <div className="ps-content">
        {tab === "personal" ? <PersonalTab account={account} key={section ?? "personal"} section={section} /> : null}
        {tab === "security" ? <SecurityTab account={account} /> : null}
        {tab === "declarations" ? <DeclarationsTab account={account} /> : null}
        {tab === "bank-accounts" ? <BankAccountsTab account={account} /> : null}
        {tab === "notifications" ? <NotificationsTab account={account} /> : null}
        {tab === "preferences" ? <PreferencesTab account={account} /> : null}
      </div>
    </main>
  );
}
