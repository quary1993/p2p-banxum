// IP of Webby-Soft SRL.
// Profile & Settings -> Security: "Signed-in devices" and "Sign-in history" (design ps-device-name rows and
// .ps-history-table). U33-DEC-25: the device and browser, the approximate place (a country from the edge
// proxy, never GPS), the last activity and this device; "Sign out" ends one other session and "Sign out on
// all other devices" ends every other one, with real revocation on the server. The design has no
// "all other devices" button; the decision asks for it.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  getV1AuthSessionsRetrieveQueryKey,
  useV1AuthSessionsRetrieve,
  useV1AuthSessionsRevokeCreate,
  useV1AuthSessionsRevokeOthersCreate,
  useV1AuthSignInHistoryRetrieve,
  type SignInEvent,
  type SignInMethodEnum,
  type SignInResultEnum,
  type UserSession
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { formatDateTime } from "../../../../investorPortal/format";
import { Button, NiIcon } from "../../../components";
import { countryName } from "../../invest/loanFacts";
import { errorMessage } from "../../portfolio/parts/errors";
import { Notice, PsPanel, SettingsRow } from "../parts/ui";
import type { AccountData } from "./useAccountData";

const PREVIEW_NOW = new Date().toISOString();
const PREVIEW_SESSIONS: UserSession[] = [
  { id: "s-1", device_label: "Chrome on macOS", device_kind: "desktop", country_code: "CH", method: "password_sms", started_at: PREVIEW_NOW, last_activity_at: PREVIEW_NOW, current: true },
  { id: "s-2", device_label: "Safari on iPhone", device_kind: "mobile", country_code: "CH", method: "password_app", started_at: PREVIEW_NOW, last_activity_at: PREVIEW_NOW, current: false }
];
const PREVIEW_HISTORY: SignInEvent[] = [
  { id: "e-1", occurred_at: PREVIEW_NOW, device_label: "Chrome on macOS", device_kind: "desktop", country_code: "CH", method: "password_sms", result: "signed_in" },
  { id: "e-2", occurred_at: PREVIEW_NOW, device_label: "Safari on iPhone", device_kind: "mobile", country_code: "CH", method: "password_app", result: "signed_in" }
];

/** Design icons: ni-laptop for a computer, ni-mobile for a phone or tablet. */
function deviceIcon(kind: string) {
  return kind === "mobile" || kind === "tablet" ? "mobile" : "laptop";
}

function placeText(code: string, t: ReturnType<typeof useT>) {
  return code ? countryName(code) : t("Place not known");
}

type Translate = ReturnType<typeof useT>;

/** Audit S4-8: one label for every sign-in method of the API. The Record type makes the build fail
 *  when the backend adds a method and this map does not have it. */
function methodLabels(t: Translate): Record<SignInMethodEnum, string> {
  return {
    email_link: t("Email link"),
    registration_link: t("Registration email link"),
    password_sms: t("Password and SMS code"),
    password_app: t("Password and authenticator app"),
    password_recovery_code: t("Password and recovery code"),
    password_trusted_device: t("Password on a trusted device"),
    password_only: t("Password (second factor not set up yet)"),
    admin_password_app: t("Password and authenticator app (administrator)"),
    admin_password_code: t("Password and email code (administrator)")
  };
}

/** A failed attempt is shown in the signal colour, with its cause. */
function resultLabels(t: Translate): Record<SignInResultEnum, { label: string; failed: boolean }> {
  return {
    signed_in: { label: t("Signed in"), failed: false },
    blocked: { label: t("Account blocked"), failed: true },
    failed: { label: t("Wrong password"), failed: true },
    failed_factor: { label: t("Wrong second-factor code"), failed: true }
  };
}

// A value this build does not know (an older build against a newer server) says so plainly.
function methodText(method: string, t: Translate) {
  return (methodLabels(t) as Record<string, string | undefined>)[method] ?? t("Other sign-in method");
}

function resultText(result: string, t: Translate) {
  const known = (resultLabels(t) as Record<string, { label: string; failed: boolean } | undefined>)[result];
  if (!known) return <span className="bxm-signal-text">{t("Sign-in not completed")}</span>;
  return known.failed ? <span className="bxm-signal-text">{known.label}</span> : known.label;
}

/** The "Sign-in history" table (design .ps-history-table). */
export function SignInHistoryTable({ events }: { events: SignInEvent[] }) {
  const t = useT();
  return (
    <table className="ps-history-table">
      <thead>
        <tr>
          <th>{t("Date")}</th>
          <th>{t("Device and place")}</th>
          <th>{t("Method")}</th>
          <th>{t("Result")}</th>
        </tr>
      </thead>
      <tbody>
        {events.map((event) => (
          <tr key={event.id}>
            <td>{formatDateTime(event.occurred_at)}</td>
            <td>{event.device_label}<small>{placeText(event.country_code, t)}</small></td>
            <td>{methodText(event.method, t)}</td>
            <td>{resultText(event.result, t)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SecurityDevices({ account }: { account: AccountData }) {
  const t = useT();
  const queryClient = useQueryClient();
  const enabled = !isFixturePreview && !account.readonly;
  const sessionsQuery = useV1AuthSessionsRetrieve({ query: { enabled, retry: false, staleTime: 0 } });
  const historyQuery = useV1AuthSignInHistoryRetrieve({ query: { enabled, retry: false, staleTime: 0 } });
  const revoke = useV1AuthSessionsRevokeCreate();
  const revokeOthers = useV1AuthSessionsRevokeOthersCreate();
  const [previewSessions, setPreviewSessions] = useState(PREVIEW_SESSIONS);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const sessions = isFixturePreview ? previewSessions : (sessionsQuery.data?.sessions ?? []);
  const history = isFixturePreview ? PREVIEW_HISTORY : (historyQuery.data?.events ?? []);
  const others = sessions.filter((session) => !session.current);
  const busy = revoke.isPending || revokeOthers.isPending;

  const refresh = () => void queryClient.invalidateQueries({ queryKey: getV1AuthSessionsRetrieveQueryKey() });
  const endOne = (session: UserSession) => {
    setError("");
    setNotice("");
    if (isFixturePreview) {
      setPreviewSessions((current) => current.filter((row) => row.id !== session.id));
      setNotice(t("{device} is signed out.", { device: session.device_label }));
      return;
    }
    revoke.mutate(
      { sessionId: session.id },
      {
        onSuccess: () => {
          setNotice(t("{device} is signed out.", { device: session.device_label }));
          refresh();
        },
        onError: (failure) => setError(errorMessage(failure))
      }
    );
  };
  const endOthers = () => {
    setError("");
    setNotice("");
    if (isFixturePreview) {
      setPreviewSessions((current) => current.filter((row) => row.current));
      setNotice(t("All other devices are signed out."));
      return;
    }
    revokeOthers.mutate(undefined, {
      onSuccess: () => {
        setNotice(t("All other devices are signed out."));
        refresh();
      },
      onError: (failure) => setError(errorMessage(failure))
    });
  };

  if (account.readonly) return null;
  return (
    <>
      <PsPanel title={t("Signed-in devices")}>
        <div className="ps-settings-rows">
          {sessions.map((session) => (
            <SettingsRow
              actions={
                session.current
                  ? <span className="ps-current-device">{t("This device")}</span>
                  : <Button disabled={busy} onClick={() => endOne(session)}>{t("Sign out")}</Button>
              }
              description={`${placeText(session.country_code, t)} · ${t("Last active {time}", { time: formatDateTime(session.last_activity_at) })}`}
              key={session.id}
              title={<span className="ps-device-name"><NiIcon name={deviceIcon(session.device_kind)} />{session.device_label}</span>}
            />
          ))}
          {others.length > 0 ? (
            <SettingsRow
              actions={<Button disabled={busy} onClick={endOthers}>{t("Sign out on all other devices")}</Button>}
              description={t("Use this if you do not recognise a device. You stay signed in here.")}
              title={t("Other devices")}
            />
          ) : null}
          {sessionsQuery.isError ? (
            <SettingsRow description={t("Your signed-in devices could not be loaded.")} title={t("Signed-in devices")} />
          ) : null}
        </div>
      </PsPanel>
      {notice ? <Notice title={notice} tone="success" /> : null}
      {error ? <Notice title={t("Could not sign out the device")} tone="danger">{error}</Notice> : null}
      <details className="ps-disclosure ps-sign-in-history">
        <summary>
          <span>
            <strong>{t("Sign-in history")}</strong>
            <small>{t("Recent access to your account")}</small>
          </span>
          <NiIcon name="chevron-down" />
        </summary>
        <div className="ps-disclosure-body">
          {history.length > 0 ? (
            <SignInHistoryTable events={history} />
          ) : (
            <p className="u33-muted">{historyQuery.isError ? t("The sign-in history could not be loaded.") : t("No sign-ins recorded yet.")}</p>
          )}
          {historyQuery.data ? <p className="u33-muted">{t("Sign-ins are kept for {days} days.", { days: historyQuery.data.retention_days })}</p> : null}
        </div>
      </details>
    </>
  );
}
