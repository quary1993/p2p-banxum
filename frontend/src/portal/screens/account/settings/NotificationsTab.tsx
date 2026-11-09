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

const SERVICE_EMAILS: Array<{ title: string; description: string }> = [
  { title: "Investments and repayments", description: "Confirmations of your investments, and repayments credited to your {brand} balance." },
  { title: "Late payments and recoveries", description: "When a payment is late, and updates on recovery." },
  { title: "Documents and statements", description: "When a document or statement is ready for you." },
  { title: "Money going back to your bank", description: "Reminders before money you have not invested goes back to your bank account." },
  { title: "Security", description: "Sign-in links, confirmation codes and changes to your account." }
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
        <PsPanel title={t("Always sent")}>
          <div className="ps-settings-rows">
            {SERVICE_EMAILS.map((item) => (
              <SettingsRow actions={<span className="ps-always-on">{t("Always on")}</span>} description={t(item.description, { brand: brandDisplayName() })} key={item.title} title={t(item.title)} />
            ))}
          </div>
        </PsPanel>
        <PsPanel title={t("Optional")}>
          <div className="ps-settings-rows">
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
          </div>
        </PsPanel>
      </div>
      {error ? <Notice title={t("Could not update your preference")} tone="danger">{error}</Notice> : null}
    </>
  );
}
