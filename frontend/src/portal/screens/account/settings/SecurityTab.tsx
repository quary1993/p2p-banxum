// IP of Webby-Soft SRL.
// Profile & Settings -> Security (design: security(): "Two-factor authentication is always on",
// the authenticator app, recovery codes, password, signed-in devices, sign-in history). 18.5
// (U33-DEC-01, D-1, D-2): no passkeys; the SMS code is shown as the factor of an SMS investor, who can
// add the app (it then replaces the SMS code and the PIN); the PIN panel is for SMS investors only.
// Remembered browsers (30 days) can be forgotten here. Signed-in devices and sign-in history
// (U33-DEC-25) are in SecurityDevices.
import { useState } from "react";

import { useV1AuthSecurityRetrieve, useV1AuthSecurityTrustedDevicesRevokeCreate, type SecurityOverview } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { formatPinLockTime } from "../../../../investorPortal/pinRules";
import { formatDate } from "../../../../investorPortal/format";
import { Button } from "../../../components";
import { ChangePinDialog, CreatePinDialog, ForgotPinDialog } from "../parts/PinDialogs";
import { Notice, PsPanel, PsStatus, SettingsRow } from "../parts/ui";
import { SecurityChangeDialog } from "./SecurityDialogs";
import { SecurityDevices } from "./SecurityDevices";
import type { AccountData } from "./useAccountData";

const PREVIEW_SECURITY: SecurityOverview = {
  second_factor: "sms",
  phone_last_digits: "00",
  authenticator_added_at: null,
  recovery_codes_remaining: 10,
  recovery_codes_issued: true,
  password_set: true,
  password_changed_at: "2025-12-10T09:30:00Z",
  trusted_devices: [],
  restriction: null
};

export function SecurityTab({ account }: { account: AccountData }) {
  const t = useT();
  const { status, isLoading, query } = account.pin;
  const securityQuery = useV1AuthSecurityRetrieve({ query: { enabled: !isFixturePreview && !account.readonly, retry: false, staleTime: 0 } });
  const revokeMutation = useV1AuthSecurityTrustedDevicesRevokeCreate();
  const security = isFixturePreview ? PREVIEW_SECURITY : securityQuery.data;
  const [dialog, setDialog] = useState<"create" | "change" | "forgot" | null>(null);
  const [change, setChange] = useState<"password" | "authenticator" | "codes" | null>(null);
  const [notice, setNotice] = useState("");
  const lockedUntil = status?.locked_until ?? null;
  const factor = security?.second_factor ?? status?.second_factor ?? "";
  const close = () => setDialog(null);
  const pinStatus = !status
    ? null
    : lockedUntil
      ? <PsStatus muted>{t("Locked until {time}", { time: formatPinLockTime(lockedUntil) })}</PsStatus>
      : status.pin_set
        ? <PsStatus>{t("Set")}</PsStatus>
        : <PsStatus muted>{t("Not set")}</PsStatus>;
  const disabled = account.readonly || !security;

  return (
    <>
      <p className="ps-intro">{t("Two-factor authentication is always on. You need it to sign in, to invest and to change your bank account.")}</p>
      {security?.restriction ? (
        <Notice title={t("Bank account changes paused until {date}", { date: formatDate(security.restriction.ends_at) })} tone="warning">
          {t("After the recovery of your account you cannot add a bank account or change your default return account for 72 hours. Withdrawals to your verified accounts still work.")}
        </Notice>
      ) : null}
      <PsPanel title={t("Two-factor authentication")}>
        <div className="ps-settings-rows">
          <SettingsRow
            actions={<Button disabled={disabled} onClick={() => setChange("authenticator")} variant={factor === "app" ? "secondary" : "primary"}>{factor === "app" ? t("Replace") : t("Set up")}</Button>}
            description={factor === "app"
              ? t("Codes from an app such as Google Authenticator, Microsoft Authenticator or 1Password. You type the code when you sign in and to confirm investments and withdrawals.")
              : t("Add an app such as Google Authenticator, Microsoft Authenticator or 1Password. It then replaces the SMS code and the PIN.")}
            note={factor === "app" && security?.authenticator_added_at ? t("Added {date}", { date: formatDate(security.authenticator_added_at) }) : undefined}
            title={t("Authenticator app")}
            titleExtra={factor === "app" ? <PsStatus>{t("On")}</PsStatus> : <PsStatus muted>{t("Off")}</PsStatus>}
          />
          {factor === "sms" ? (
            <SettingsRow
              description={security?.phone_last_digits
                ? t("A code by SMS to your phone number ending in {digits} when you sign in.", { digits: security.phone_last_digits })
                : t("A code by SMS to your verified phone when you sign in.")}
              title={t("SMS code")}
              titleExtra={<PsStatus>{t("On")}</PsStatus>}
            />
          ) : null}
          <SettingsRow
            actions={<Button disabled={disabled || !factor} onClick={() => setChange("codes")}>{t("New codes")}</Button>}
            description={t("Use one if you lose your phone. Each code works once.")}
            note={security ? t("{count} of 10 left", { count: security.recovery_codes_remaining }) : undefined}
            title={t("Recovery codes")}
          />
        </div>
      </PsPanel>
      <PsPanel title={t("Password")}>
        <div className="ps-settings-rows">
          <SettingsRow
            actions={<Button disabled={disabled} onClick={() => setChange("password")}>{t("Change password")}</Button>}
            description={t("At least 12 characters. Changing it signs you out on other devices.")}
            note={security?.password_changed_at ? t("Last changed {date}", { date: formatDate(security.password_changed_at) }) : undefined}
            title={t("Password")}
          />
        </div>
      </PsPanel>
      {security && security.trusted_devices.length ? (
        <PsPanel title={t("Remembered browsers")}>
          <div className="ps-settings-rows">
            {security.trusted_devices.map((device) => (
              <SettingsRow
                actions={
                  <Button
                    disabled={account.readonly || revokeMutation.isPending}
                    onClick={() => revokeMutation.mutate({ deviceId: device.id }, { onSuccess: () => void securityQuery.refetch() })}
                  >
                    {t("Forget")}
                  </Button>
                }
                description={t("Signs in without the code until {date}. The password is still asked.", { date: formatDate(device.expires_at) })}
                key={device.id}
                title={device.device_label}
              />
            ))}
          </div>
        </PsPanel>
      ) : null}
      {factor === "sms" ? (
        <PsPanel title={t("PIN")}>
          <div className="ps-settings-rows">
            <SettingsRow
              actions={
                <>
                  {status && !status.pin_set ? (
                    <Button disabled={account.readonly} onClick={() => setDialog("create")} variant="primary">{t("Create PIN")}</Button>
                  ) : (
                    <Button disabled={account.readonly || !status || Boolean(lockedUntil)} onClick={() => setDialog("change")}>{t("Change PIN")}</Button>
                  )}
                  <Button disabled={account.readonly || !status} onClick={() => setDialog("forgot")}>{t("Forgot PIN?")}</Button>
                </>
              }
              description={t("Needed with the email code for every investment, withdrawal and bank account change.")}
              note={isLoading ? t("Loading...") : undefined}
              title={t("PIN")}
              titleExtra={pinStatus}
            />
            <SettingsRow
              description={t("We never ask for your PIN by email, SMS or phone. Do not share it with anyone, including our team.")}
              title={t("Keep your PIN private")}
            />
          </div>
        </PsPanel>
      ) : null}
      <SecurityDevices account={account} />
      {(query.isError || securityQuery.isError) && !isFixturePreview && !account.readonly ? (
        <Notice
          action={<Button onClick={() => { void query.refetch(); void securityQuery.refetch(); }} size="sm">{t("Retry")}</Button>}
          title={t("Could not load your security settings")}
          tone="danger"
        />
      ) : null}
      {notice ? <Notice title={notice} tone="success" /> : null}
      {change ? <SecurityChangeDialog onChanged={setNotice} onClose={() => setChange(null)} purpose={change} /> : null}
      {dialog === "create" ? (
        <CreatePinDialog onClose={close} onSaved={() => { close(); setNotice(t("Your PIN is saved.")); }} />
      ) : null}
      {dialog === "change" ? (
        <ChangePinDialog onChanged={() => setNotice(t("Your PIN was changed."))} onClose={close} onForgot={() => setDialog("forgot")} />
      ) : null}
      {dialog === "forgot" ? (
        <ForgotPinDialog onClose={close} onReset={() => { close(); setNotice(t("Your new PIN is saved.")); }} />
      ) : null}
    </>
  );
}
