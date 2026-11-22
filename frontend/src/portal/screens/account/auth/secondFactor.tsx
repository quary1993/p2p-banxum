// IP of Webby-Soft SRL.
// 18.5 (U33-DEC-01, D-1): the pieces of sign-in and account protection in the create-account layout.
// - the password field with Show/Hide (design: login and signup, .u03-password-wrap);
// - the choice of the second factor: an authenticator app (design onboarding "Protect your account")
//   or an SMS code to the verified phone (the SMS choice the design lacks; Vlad, 2026-11-19);
// - the app set-up: QR code, the key to type, the first code;
// - the 10 recovery codes, shown once.
import QRCode from "qrcode";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import {
  useV1AuthSecurityAuthenticatorConfirmCreate,
  useV1AuthSecurityAuthenticatorStartCreate,
  useV1AuthSecurityRecoveryCodesCreate,
  type AuthenticatorEnrollmentResponse
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { brandDisplayName } from "../../../brand";
import { CaCodeField, CaError, CaIcon } from "./AuthLayout";
import { requestErrorText } from "./authState";

/** Email-style field with the browser's password manager attributes and Show/Hide. */
export function AuthPasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete = "current-password",
  autoFocus = false,
  hint,
  aside
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: "current-password" | "new-password";
  autoFocus?: boolean;
  hint?: ReactNode;
  aside?: ReactNode;
}) {
  const t = useT();
  const [shown, setShown] = useState(false);
  return (
    <div className="ca-field ca-wide acc-password">
      <div className="ca-pin-label">
        <label htmlFor={id}>{label}</label>
        <span className="acc-password-tools">
          <button aria-controls={id} aria-label={shown ? t("Hide password") : t("Show password")} aria-pressed={shown} onClick={() => setShown((current) => !current)} type="button">
            {shown ? t("Hide") : t("Show")}
          </button>
          {aside}
        </span>
      </div>
      <input
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        id={id}
        maxLength={128}
        name={id}
        onChange={(event) => onChange(event.target.value)}
        type={shown ? "text" : "password"}
        value={value}
      />
      {hint ? <p className="ca-field-note acc-password-hint">{hint}</p> : null}
    </div>
  );
}

/** The two second factors (D-1): the app is recommended; SMS goes to the registered mobile. */
export function FactorChoice({ phoneLabel, onChoose }: { phoneLabel: string; onChoose: (factor: "app" | "sms") => void }) {
  const t = useT();
  return (
    <div className="acc-factor-choice" role="group" aria-label={t("Second factor")}>
      <button className="acc-factor-option" onClick={() => onChoose("app")} type="button">
        <CaIcon name="shield" />
        <span>
          <strong>{t("Authenticator app")} <em>{t("Recommended")}</em></strong>
          <small>{t("Codes from an app such as Google Authenticator, Microsoft Authenticator or 1Password. You do not need a PIN.")}</small>
        </span>
        <CaIcon name="right" />
      </button>
      <button className="acc-factor-option" onClick={() => onChoose("sms")} type="button">
        <CaIcon name="phone" />
        <span>
          <strong>{t("SMS code")}</strong>
          <small>
            {phoneLabel
              ? t("A code by SMS to {phone} when you sign in. You create a 6-digit PIN for investments and withdrawals.", { phone: phoneLabel })
              : t("A code by SMS to your mobile when you sign in. You create a 6-digit PIN for investments and withdrawals.")}
          </small>
        </span>
        <CaIcon name="right" />
      </button>
    </div>
  );
}

function useQrImage(payload: string) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!payload) return undefined;
    let mounted = true;
    QRCode.toDataURL(payload, { errorCorrectionLevel: "M", margin: 1, width: 200, color: { dark: "#0a0a0a", light: "#ffffff" } })
      .then((next) => {
        if (mounted) setSrc(next);
      })
      .catch(() => {
        if (mounted) setSrc("");
      });
    return () => {
      mounted = false;
    };
  }, [payload]);
  return src;
}

const PREVIEW_ENROLLMENT: AuthenticatorEnrollmentResponse = {
  enrollment_id: "00000000-0000-0000-0000-000000000000",
  secret: "JBSWY3DPEHPK3PXP",
  otpauth_uri: "otpauth://totp/Banxum:preview%40example.test?secret=JBSWY3DPEHPK3PXP&issuer=Banxum"
};

/**
 * Design onboarding "Protect your account": scan the QR code (or type the key), then the first
 * 6-digit code activates the app. ``confirmationId`` is the fresh password + factor confirmation
 * an account with a factor needs (Security tab).
 */
export function AuthenticatorSetup({
  confirmationId,
  onDone,
  submitLabel
}: {
  confirmationId?: string;
  onDone: () => void;
  submitLabel?: string;
}) {
  const t = useT();
  const startMutation = useV1AuthSecurityAuthenticatorStartCreate();
  const confirmMutation = useV1AuthSecurityAuthenticatorConfirmCreate();
  const [enrollment, setEnrollment] = useState<AuthenticatorEnrollmentResponse | null>(isFixturePreview ? PREVIEW_ENROLLMENT : null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const started = useRef(false);
  const startMutate = startMutation.mutate;
  useEffect(() => {
    if (isFixturePreview || started.current) return;
    started.current = true;
    startMutate(undefined, {
      onSuccess: (response) => setEnrollment(response),
      onError: (failure) => setError(requestErrorText(failure))
    });
  }, [startMutate]);
  const qr = useQrImage(enrollment?.otpauth_uri ?? "");
  const key = (enrollment?.secret ?? "").replace(/(.{4})/g, "$1 ").trim();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (code.length !== 6) {
      setError(t("Enter the 6 digits shown in your app."));
      return;
    }
    if (isFixturePreview) {
      onDone();
      return;
    }
    if (!enrollment) return;
    confirmMutation.mutate(
      { data: { enrollment_id: enrollment.enrollment_id, code, confirmation_id: confirmationId ?? null } },
      {
        onSuccess: () => onDone(),
        onError: (failure) => {
          setCode("");
          setError(requestErrorText(failure));
        }
      }
    );
  };

  return (
    <form className="acc-app-setup" data-form="authenticator" noValidate onSubmit={submit}>
      <div className="acc-app-qr">
        {qr ? <img alt={t("QR code for your authenticator app")} height={164} src={qr} width={164} /> : <span className="acc-app-qr-wait" aria-hidden="true" />}
        <div>
          <small>{t("Or enter this key")}</small>
          <code className="acc-app-key">{key || "…"}</code>
          {enrollment?.otpauth_uri ? (
            <a className="acc-app-open" href={enrollment.otpauth_uri}>{t("Open in an authenticator app on this device")}</a>
          ) : null}
        </div>
      </div>
      <CaCodeField autoFocus id="authenticator-code" label={t("Code from the app")} onChange={(value) => { setCode(value); setError(""); }} value={code} />
      <p className="ca-field-note">{isFixturePreview ? t("Demo: any 6 digits work.") : t("Enter the 6 digits shown in your app.")}</p>
      <CaError>{error || null}</CaError>
      <button className="ca-primary" disabled={confirmMutation.isPending || (!isFixturePreview && !enrollment)} type="submit">
        {confirmMutation.isPending ? t("Activating...") : submitLabel ?? t("Activate")}
        <CaIcon name="right" />
      </button>
    </form>
  );
}

function previewCodes() {
  return ["K7Q2M-9XH4T", "P3V8N-2LW6R", "B5J9C-7ZD3F", "H2M6T-4QX8K", "R9W3L-6NB2V", "D4F7Y-8KC5P", "T6X2Q-3MJ9H", "N8C4R-5VL7W", "F3K9B-2TD6M", "W7H5P-9QN3X"];
}

/**
 * The 10 recovery codes, shown once (design Security: "Use one if you lose your phone. Each code
 * works once."). The first set needs no confirmation; a new set (Security tab) passes one.
 */
export function RecoveryCodesStep({ confirmationId, onDone, doneLabel }: { confirmationId?: string; onDone: () => void; doneLabel?: string }) {
  const t = useT();
  const mutation = useV1AuthSecurityRecoveryCodesCreate();
  const [codes, setCodes] = useState<string[]>(isFixturePreview ? previewCodes() : []);
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const requested = useRef(false);
  const mutate = mutation.mutate;
  useEffect(() => {
    if (isFixturePreview || requested.current) return;
    requested.current = true;
    mutate(
      { data: { confirmation_id: confirmationId ?? null } },
      {
        onSuccess: (response) => setCodes(response.codes),
        onError: (failure) => setError(requestErrorText(failure))
      }
    );
  }, [confirmationId, mutate]);
  const text = `${t("{brand} recovery codes", { brand: brandDisplayName() })}\n${t("Each code works once.")}\n\n${codes.join("\n")}\n`;
  const download = () => {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "banxum-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  };
  const copy = () => {
    void navigator.clipboard?.writeText(text).then(() => setCopied(true)).catch(() => setCopied(false));
  };
  return (
    <div className="acc-recovery-codes">
      {codes.length ? (
        <ol className="acc-recovery-list" aria-label={t("Recovery codes")}>
          {codes.map((code) => <li key={code}><code>{code}</code></li>)}
        </ol>
      ) : (
        <p className="ca-email-note" role="status">{mutation.isPending ? t("Creating your codes...") : null}</p>
      )}
      <CaError>{error || null}</CaError>
      {codes.length ? (
        <>
          <div className="acc-recovery-actions">
            <button className="ca-secondary" onClick={download} type="button">{t("Download")}</button>
            <button className="ca-secondary" onClick={copy} type="button">{copied ? t("Copied") : t("Copy")}</button>
          </div>
          <label className="ca-checkbox acc-recovery-saved">
            <input checked={saved} onChange={(event) => setSaved(event.target.checked)} type="checkbox" />
            <span>{t("I saved these codes in a safe place. I will not see them again.")}</span>
          </label>
          <button className="ca-primary" disabled={!saved} onClick={onDone} type="button">
            {doneLabel ?? t("Continue")}
            <CaIcon name="right" />
          </button>
        </>
      ) : null}
    </div>
  );
}
