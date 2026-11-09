// IP of Webby-Soft SRL.
// Profile & Settings -> Security (design: sign-in methods, recovery, signed-in devices, sign-in
// history). Today's platform, stated truthfully: sign-in with a single-use link sent to the email
// address, and the PIN with an email code for money actions (ACC-DEC-001/009). Password + second
// factor comes with Phase 17.3 (U33-DEC-01); signed-in devices and sign-in history need backend data
// (U33-DEC-25). Neither is shown until it exists.
import { useState } from "react";

import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { formatPinLockTime } from "../../../../investorPortal/pinRules";
import { Button } from "../../../components";
import { ChangePinDialog, CreatePinDialog, ForgotPinDialog } from "../parts/PinDialogs";
import { Notice, PsPanel, PsStatus, SettingsRow } from "../parts/ui";
import type { AccountData } from "./useAccountData";

export function SecurityTab({ account }: { account: AccountData }) {
  const t = useT();
  const { status, isLoading, query } = account.pin;
  const [dialog, setDialog] = useState<"create" | "change" | "forgot" | null>(null);
  const [notice, setNotice] = useState("");
  const lockedUntil = status?.locked_until ?? null;
  const close = () => setDialog(null);
  const pinStatus = !status
    ? null
    : lockedUntil
      ? <PsStatus muted>{t("Locked until {time}", { time: formatPinLockTime(lockedUntil) })}</PsStatus>
      : status.pin_set
        ? <PsStatus>{t("Set")}</PsStatus>
        : <PsStatus muted>{t("Not set")}</PsStatus>;

  return (
    <>
      <p className="ps-intro">{t("You sign in with a link sent to your email. Investments, withdrawals and bank account changes are confirmed with your PIN and a code sent to your email.")}</p>
      <PsPanel title={t("Sign-in method")}>
        <div className="ps-settings-rows">
          <SettingsRow
            description={account.email
              ? t("A single-use link is sent to {email}. Each link works once and expires after 15 minutes.", { email: account.email })
              : t("A single-use link is sent to your email address. Each link works once and expires after 15 minutes.")}
            title={t("Sign-in link by email")}
            titleExtra={<PsStatus>{t("On")}</PsStatus>}
          />
        </div>
      </PsPanel>
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
      {query.isError && !isFixturePreview && !account.readonly ? (
        <Notice action={<Button onClick={() => void query.refetch()} size="sm">{t("Retry")}</Button>} title={t("Could not load your PIN status")} tone="danger" />
      ) : null}
      {notice ? <Notice title={notice} tone="success" /> : null}
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
