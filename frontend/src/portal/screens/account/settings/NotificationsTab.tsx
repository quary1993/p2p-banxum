// IP of Webby-Soft SRL.
// Profile & Settings -> Notifications (U33-DEC-30): the service emails that are always sent, as a
// read-only list, and the one optional switch, "News from Banxum" (today's marketing consent). No
// per-category switches and no Smart Invest channels until the notification preferences exist
// (Phase 17.2).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";

import { useV1AuthPreferencesMarketingPartialUpdate } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { brandDisplayName } from "../../../brand";
import { NiIcon, PortalLink } from "../../../components";
import { Notice, PsPanel, SettingsRow } from "../parts/ui";
import type { AccountData } from "./useAccountData";

// The design's rows and panels. Service emails show "Always on" (U33-DEC-30) where the design has
// switches; repayments are credited to the Banxum account (U33-DEC-02). The design's opportunity and
// Smart Invest alerts come with U33-DEC-17/19 (Phase 17.2).
const INVESTMENT_EMAILS: Array<{ title: string; description: string }> = [
  { title: "Repayments", description: "Repayments credited to your {brand} account." },
  { title: "Late payments", description: "Late payments and recovery updates." }
];
const ACCOUNT_EMAILS: Array<{ title: string; description: string }> = [
  { title: "Uninvested funds returning", description: "Reminders before money you have not invested goes back to your bank account." },
  { title: "Documents and statements", description: "" }
];

export function NotificationsTab({ account }: { account: AccountData }) {
  const t = useT();
  const queryClient = useQueryClient();
  const switchId = useId();
  const mutation = useV1AuthPreferencesMarketingPartialUpdate();
  const [marketing, setMarketing] = useState(account.marketingConsent);
  const [error, setError] = useState("");
  useEffect(() => setMarketing(account.marketingConsent), [account.marketingConsent]);

  const change = (next: boolean) => {
    setError("");
    setMarketing(next);
    if (isFixturePreview) return;
    mutation.mutate(
      { data: { marketing_consent: next } },
      {
        onSuccess: (response) => {
          setMarketing(response.user.marketing_consent);
          void queryClient.invalidateQueries();
        },
        onError: (mutationError) => {
          setMarketing(account.marketingConsent);
          setError(mutationError instanceof Error ? mutationError.message : t("Request failed. Retry once the connection is restored."));
        }
      }
    );
  };

  const newsTitle = t("News from {brand}", { brand: brandDisplayName() });
  return (
    <>
      <div className="ps-section-intro">
        <p>
          {account.email ? <>{t("Email notifications for")} <strong>{account.email}</strong></> : t("Email notifications")}
        </p>
        <PortalLink className="ps-text-link" to="notifications">
          {t("View notifications")}
          <NiIcon name="arrow-right" />
        </PortalLink>
      </div>
      <div className="ps-personal-grid rss-notification-settings">
        <PsPanel title={t("Investments")}>
          <div className="ps-settings-rows">
            {INVESTMENT_EMAILS.map((item) => (
              <SettingsRow actions={<span className="ps-always-on">{t("Always on")}</span>} description={t(item.description, { brand: brandDisplayName() })} key={item.title} title={t(item.title)} />
            ))}
          </div>
        </PsPanel>
        <PsPanel title={t("Account")}>
          <div className="ps-settings-rows">
            {ACCOUNT_EMAILS.map((item) => (
              <SettingsRow actions={<span className="ps-always-on">{t("Always on")}</span>} description={item.description ? t(item.description) : undefined} key={item.title} title={t(item.title)} />
            ))}
            <SettingsRow
              actions={
                <div className="custom-control custom-switch me-n2">
                  <input
                    checked={marketing}
                    className="custom-control-input"
                    disabled={account.readonly || mutation.isPending}
                    id={switchId}
                    onChange={(event) => change(event.target.checked)}
                    type="checkbox"
                  />
                  <label className="custom-control-label" htmlFor={switchId}>
                    <span className="visually-hidden">{newsTitle}</span>
                  </label>
                </div>
              }
              description={t("News and updates about {brand}. Optional; you can switch it off at any time.", { brand: brandDisplayName() })}
              title={newsTitle}
            />
            <SettingsRow actions={<span className="ps-always-on">{t("Always on")}</span>} description={t("Sign-in links, confirmation codes and changes to your account.")} title={t("Security alerts")} />
          </div>
        </PsPanel>
      </div>
      {error ? <Notice title={t("Could not update your preference")} tone="danger">{error}</Notice> : null}
    </>
  );
}
