// IP of Webby-Soft SRL.
// 18.5 dialogs of Profile & Settings -> Security (design: .p73-modal): every security change starts
// with a fresh confirmation (the password, then the second factor or a recovery code), then the change
// itself: a new password, the authenticator app (it replaces an older app, or the SMS code and the PIN,
// D-1), or 10 new recovery codes.
import QRCode from "qrcode";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  useV1AuthSecurityAuthenticatorConfirmCreate,
  useV1AuthSecurityAuthenticatorStartCreate,
  useV1AuthSecurityConfirmResendSmsCreate,
  useV1AuthSecurityConfirmStartCreate,
  useV1AuthSecurityConfirmVerifyCreate,
  useV1AuthSecurityPasswordCreate,
  useV1AuthSecurityRecoveryCodesCreate,
  type AuthenticatorEnrollmentResponse,
  type FactorStepResponse
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { pinErrorText } from "../../../../investorPortal/pinFlows";
import { brandDisplayName } from "../../../brand";
import { Dialog } from "../../../components";
import { passwordProblem } from "../auth/authState";
import { DialogResult } from "../parts/PinDialogs";
import { CodeField, DialogActions, Notice, PasswordField } from "../parts/ui";

type Purpose = "password" | "authenticator" | "codes";

const TITLES: Record<Purpose, string> = {
  password: "Change password",
  authenticator: "Authenticator app",
  codes: "New recovery codes"
};

/** Password, then the factor (or a recovery code): answers a confirmation id valid 10 minutes. */
function ConfirmIdentity({ onConfirmed, onCancel }: { onConfirmed: (confirmationId: string) => void; onCancel: () => void }) {
  const t = useT();
  const startMutation = useV1AuthSecurityConfirmStartCreate();
  const verifyMutation = useV1AuthSecurityConfirmVerifyCreate();
  const resendMutation = useV1AuthSecurityConfirmResendSmsCreate();
  const [password, setPassword] = useState("");
  const [step, setStep] = useState<FactorStepResponse | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [error, setError] = useState("");

  const submitPassword = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (isFixturePreview) {
      setStep({ status: "factor_required", method: "app", challenge_id: "preview", phone_last_digits: "" });
      return;
    }
    startMutation.mutate(
      { data: { password } },
      { onSuccess: (response) => setStep(response), onError: (failure) => setError(pinErrorText(failure)) }
    );
  };
  const submitCode = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (isFixturePreview) {
      onConfirmed("preview");
      return;
    }
    if (!step) return;
    verifyMutation.mutate(
      { data: recovery ? { challenge_id: step.challenge_id, recovery_code: recoveryCode } : { challenge_id: step.challenge_id, code } },
      {
        onSuccess: (response) => onConfirmed(response.confirmation_id),
        onError: (failure) => {
          setCode("");
          setError(pinErrorText(failure));
        }
      }
    );
  };

  if (!step) {
    return (
      <form noValidate onSubmit={submitPassword}>
        <p className="p73-intro">{t("For your security, confirm it is you: your password, then your second factor.")}</p>
        <PasswordField autoFocus label={t("Current password")} onChange={setPassword} value={password} />
        {error ? <Notice title={error} tone="danger" /> : null}
        <DialogActions onCancel={onCancel} primaryDisabled={startMutation.isPending || (!isFixturePreview && !password)} primaryLabel={startMutation.isPending ? t("Checking...") : t("Continue")} primaryType="submit" />
      </form>
    );
  }
  const sms = step.method === "sms";
  return (
    <form noValidate onSubmit={submitCode}>
      {recovery ? (
        <div className="acc-code-field">
          <label className="p73-code-label" htmlFor="security-recovery">{t("Recovery code")}</label>
          <input autoComplete="off" className="form-control form-control-lg" id="security-recovery" maxLength={16} onChange={(event) => setRecoveryCode(event.target.value)} placeholder="XXXXX-XXXXX" value={recoveryCode} />
        </div>
      ) : (
        <CodeField
          autoFocus
          hint={isFixturePreview ? t("Demo: any 6 digits") : sms ? t("Sent by SMS to your phone number ending in {digits}.", { digits: step.phone_last_digits }) : t("The 6-digit code shown in your authenticator app.")}
          label={sms ? t("SMS code") : t("Authenticator code")}
          onChange={setCode}
          onRequest={sms ? () => resendMutation.mutate({ data: { challenge_id: step.challenge_id } }) : undefined}
          requestDisabled={resendMutation.isPending}
          requestLabel={sms ? t("Resend SMS") : undefined}
          value={code}
        />
      )}
      <button className="acc-text-button" onClick={() => setRecovery(!recovery)} type="button">
        {recovery ? t("Use the code instead") : t("Use a recovery code")}
      </button>
      {error ? <Notice title={error} tone="danger" /> : null}
      <DialogActions onCancel={onCancel} primaryDisabled={verifyMutation.isPending} primaryLabel={verifyMutation.isPending ? t("Checking...") : t("Confirm")} primaryType="submit" />
    </form>
  );
}

function NewPassword({ confirmationId, onDone, onCancel }: { confirmationId: string; onDone: () => void; onCancel: () => void }) {
  const t = useT();
  const mutation = useV1AuthSecurityPasswordCreate();
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const problem = passwordProblem(password, repeat);
    if (problem) {
      setError(t(problem));
      return;
    }
    if (isFixturePreview) {
      onDone();
      return;
    }
    mutation.mutate({ data: { new_password: password, confirmation_id: confirmationId } }, { onSuccess: onDone, onError: (failure) => setError(pinErrorText(failure)) });
  };
  return (
    <form noValidate onSubmit={submit}>
      <PasswordField autoComplete="new-password" autoFocus hint={t("At least 12 characters. A few unrelated words are easy to remember and hard to guess.")} label={t("New password")} onChange={setPassword} value={password} />
      <PasswordField autoComplete="new-password" label={t("Repeat password")} onChange={setRepeat} value={repeat} />
      {error ? <Notice title={error} tone="danger" /> : null}
      <DialogActions onCancel={onCancel} primaryDisabled={mutation.isPending} primaryLabel={mutation.isPending ? t("Saving...") : t("Change password")} primaryType="submit" />
    </form>
  );
}

const PREVIEW_ENROLLMENT: AuthenticatorEnrollmentResponse = {
  enrollment_id: "00000000-0000-0000-0000-000000000000",
  secret: "JBSWY3DPEHPK3PXP",
  otpauth_uri: "otpauth://totp/Banxum:preview%40example.test?secret=JBSWY3DPEHPK3PXP&issuer=Banxum"
};

function NewAuthenticator({ confirmationId, onDone, onCancel }: { confirmationId: string; onDone: () => void; onCancel: () => void }) {
  const t = useT();
  const startMutation = useV1AuthSecurityAuthenticatorStartCreate();
  const confirmMutation = useV1AuthSecurityAuthenticatorConfirmCreate();
  const [enrollment, setEnrollment] = useState<AuthenticatorEnrollmentResponse | null>(isFixturePreview ? PREVIEW_ENROLLMENT : null);
  const [qr, setQr] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const started = useRef(false);
  const startMutate = startMutation.mutate;
  useEffect(() => {
    if (isFixturePreview || started.current) return;
    started.current = true;
    startMutate(undefined, { onSuccess: setEnrollment, onError: (failure) => setError(pinErrorText(failure)) });
  }, [startMutate]);
  useEffect(() => {
    if (!enrollment) return undefined;
    let mounted = true;
    QRCode.toDataURL(enrollment.otpauth_uri, { errorCorrectionLevel: "M", margin: 1, width: 180 })
      .then((next) => mounted && setQr(next))
      .catch(() => mounted && setQr(""));
    return () => {
      mounted = false;
    };
  }, [enrollment]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (isFixturePreview) {
      onDone();
      return;
    }
    if (!enrollment) return;
    confirmMutation.mutate(
      { data: { enrollment_id: enrollment.enrollment_id, code, confirmation_id: confirmationId } },
      { onSuccess: onDone, onError: (failure) => { setCode(""); setError(pinErrorText(failure)); } }
    );
  };
  return (
    <form noValidate onSubmit={submit}>
      <p className="p73-intro">{t("Scan the code with an authenticator app (for example Google Authenticator, Microsoft Authenticator or 1Password), then enter the 6-digit code. The app replaces your current second factor; investments and withdrawals then need the app code instead of a PIN.")}</p>
      <div className="acc-app-qr-row">
        {qr ? <img alt={t("QR code for your authenticator app")} height={164} src={qr} width={164} /> : <span className="acc-app-qr-wait" aria-hidden="true" />}
        <div>
          <small>{t("Or enter this key")}</small>
          <code>{(enrollment?.secret ?? "").replace(/(.{4})/g, "$1 ").trim() || "…"}</code>
        </div>
      </div>
      <CodeField autoFocus hint={isFixturePreview ? t("Demo: any 6 digits") : t("Enter the 6 digits shown in your app.")} label={t("Code from the app")} onChange={setCode} value={code} />
      {error ? <Notice title={error} tone="danger" /> : null}
      <DialogActions onCancel={onCancel} primaryDisabled={confirmMutation.isPending || code.length !== 6} primaryLabel={confirmMutation.isPending ? t("Activating...") : t("Activate")} primaryType="submit" />
    </form>
  );
}

function NewRecoveryCodes({ confirmationId, onDone }: { confirmationId: string; onDone: () => void }) {
  const t = useT();
  const mutation = useV1AuthSecurityRecoveryCodesCreate();
  const [codes, setCodes] = useState<string[]>(isFixturePreview ? ["K7Q2M-9XH4T", "P3V8N-2LW6R", "B5J9C-7ZD3F", "H2M6T-4QX8K", "R9W3L-6NB2V", "D4F7Y-8KC5P", "T6X2Q-3MJ9H", "N8C4R-5VL7W", "F3K9B-2TD6M", "W7H5P-9QN3X"] : []);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const requested = useRef(false);
  const mutate = mutation.mutate;
  useEffect(() => {
    if (isFixturePreview || requested.current) return;
    requested.current = true;
    mutate({ data: { confirmation_id: confirmationId } }, { onSuccess: (response) => setCodes(response.codes), onError: (failure) => setError(pinErrorText(failure)) });
  }, [confirmationId, mutate]);
  const download = () => {
    const text = `${t("{brand} recovery codes", { brand: brandDisplayName() })}\n${t("Each code works once.")}\n\n${codes.join("\n")}\n`;
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "banxum-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div>
      <p className="p73-intro">{t("Your older codes no longer work. Store these where only you can find them; you will not see them again.")}</p>
      {codes.length ? (
        <ol className="acc-recovery-grid" aria-label={t("Recovery codes")}>
          {codes.map((code) => <li key={code}><code>{code}</code></li>)}
        </ol>
      ) : null}
      {error ? <Notice title={error} tone="danger" /> : null}
      {codes.length ? (
        <>
          <button className="acc-text-button" onClick={download} type="button">{t("Download")}</button>
          <label className="acc-check">
            <input checked={saved} onChange={(event) => setSaved(event.target.checked)} type="checkbox" />
            <span>{t("I saved these codes in a safe place.")}</span>
          </label>
          <DialogActions onPrimary={onDone} primaryDisabled={!saved} primaryLabel={t("Done")} />
        </>
      ) : null}
    </div>
  );
}

export function SecurityChangeDialog({ purpose, onClose, onChanged }: { purpose: Purpose; onClose: () => void; onChanged: (message: string) => void }) {
  const t = useT();
  const queryClient = useQueryClient();
  const [confirmationId, setConfirmationId] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const finish = (message: string) => {
    void queryClient.invalidateQueries();
    onChanged(message);
    setDone(true);
  };
  return (
    <Dialog className="p73-modal" onClose={onClose} size="sm" title={t(TITLES[purpose])}>
      {done ? (
        <DialogResult onDone={onClose} title={t("Saved")}>
          {purpose === "password"
            ? t("Your new password is active. Other devices were signed out.")
            : purpose === "authenticator"
              ? t("Your authenticator app is active. You type its code when you sign in and to confirm investments and withdrawals. Other devices were signed out.")
              : t("Your new recovery codes are active.")}
        </DialogResult>
      ) : !confirmationId ? (
        <ConfirmIdentity onCancel={onClose} onConfirmed={setConfirmationId} />
      ) : purpose === "password" ? (
        <NewPassword confirmationId={confirmationId} onCancel={onClose} onDone={() => finish(t("Your password was changed."))} />
      ) : purpose === "authenticator" ? (
        <NewAuthenticator confirmationId={confirmationId} onCancel={onClose} onDone={() => finish(t("Your authenticator app is set up."))} />
      ) : (
        <NewRecoveryCodes confirmationId={confirmationId} onDone={() => finish(t("Your new recovery codes are saved."))} />
      )}
    </Dialog>
  );
}
