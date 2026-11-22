// IP of Webby-Soft SRL.
/*
 * The fields of today's confirmation of a money action (ACC-DEC-009, until U33-DEC-01): the email
 * code in the design's markup (label.p73-code-label + input.p73-code) and the PIN field of
 * investorPortal/pin.tsx. State and requests: ./sensitiveCode.ts.
 */
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { SensitiveFactorField } from "../../account/parts/OperationFactor";
import type { SensitiveCode } from "./sensitiveCode";

export function SensitiveFields({
  code,
  value,
  onChange,
  onContinue,
  error
}: {
  code: SensitiveCode;
  value: string;
  onChange: (value: string) => void;
  /** Runs the action again after a PIN was created from the "no PIN yet" answer. */
  onContinue?: () => void;
  error?: string;
}) {
  const t = useT();
  const message = error || code.error;
  const resendLabel = code.isRequesting
    ? t("Sending code...")
    : code.cooldown > 0
      ? t("Send a new code in {seconds}s", { seconds: code.cooldown })
      : code.codeId ? t("Send a new code") : t("Send the code");
  return (
    <div className="wl-sensitive">
      <div className="wl-code-head">
        <label className="p73-code-label" htmlFor="wl-email-code">{t("Email confirmation code")}</label>
        <button className="link wl-code-resend" disabled={code.isRequesting || code.cooldown > 0} onClick={code.requestCode} type="button">{resendLabel}</button>
      </div>
      <input
        aria-describedby="wl-code-hint wl-code-error"
        aria-invalid={message ? true : undefined}
        autoComplete="one-time-code"
        className={`form-control form-control-lg bxm-otp p73-code ${message ? "is-invalid" : ""}`.trim()}
        id="wl-email-code"
        inputMode="numeric"
        maxLength={6}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
        placeholder="000000"
        value={value}
      />
      <p className="wl-code-hint" id="wl-code-hint">
        {isFixturePreview ? t("Preview: any 6 digits work.") : t("We sent a 6-digit code to your email address.")}
      </p>
      <div className="invalid-feedback" id="wl-code-error" role="alert">{message}</div>
      <SensitiveFactorField onContinue={onContinue} pin={code.pin} />
    </div>
  );
}
