// IP of Webby-Soft SRL.
// Confirmation of a resale action in U33 markup (design .bxm-code-form with .bxm-otp): the email code
// (bound to the operation, 18.5) + the PIN (ACC-DEC-009) or the authenticator code (D-1). One code per
// action, a 60-second resend cooldown; the second factor with its wrong-code, lock, "Forgot PIN?" and
// "Create your PIN" handling is the shared U33 SensitiveFactorField (S7: no old-skin dialogs left).
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { SensitiveFactorField } from "../../account/parts/OperationFactor";
import type { ActionConfirmation } from "./confirmation";

/**
 * The email code field (with its send/resend link) and the PIN boxes. After a PIN is created from the
 * "no PIN yet" answer, `onContinue` runs the action again.
 */
export function ConfirmFields({
  confirmation,
  code,
  onCodeChange,
  onContinue,
  requestDisabled = false
}: {
  confirmation: ActionConfirmation;
  code: string;
  onCodeChange: (value: string) => void;
  onContinue?: () => void;
  requestDisabled?: boolean;
}) {
  const t = useT();
  // The design styles the code field by its id (.s106-modal #bxm-code); one confirmation is open at a time.
  const codeId = "bxm-code";
  const { pin } = confirmation;
  const requestLabel = confirmation.isRequesting
    ? t("Sending code...")
    : confirmation.cooldownSeconds > 0
      ? confirmation.codeId
        ? t("Code sent. Send new in {seconds}s", { seconds: confirmation.cooldownSeconds })
        : t("Send new in {seconds}s", { seconds: confirmation.cooldownSeconds })
      : confirmation.codeId
        ? t("Send a new email code")
        : t("Send email code");
  return (
    <div className="bxm-code-form u33-confirm">
      <div className="u33-confirm-code">
        <div className="u33-confirm-head">
          <label className="s106-code-label" htmlFor={codeId}>{t("Email confirmation code")}</label>
          <button
            className="link u33-confirm-send"
            disabled={requestDisabled || confirmation.isRequesting || confirmation.cooldownSeconds > 0}
            onClick={confirmation.requestCode}
            type="button"
          >
            {requestLabel}
          </button>
        </div>
        <input
          aria-label={t("Email confirmation code")}
          autoComplete="one-time-code"
          className="form-control form-control-lg bxm-otp p73-code s106-code"
          id={codeId}
          inputMode="numeric"
          maxLength={6}
          onChange={(event) => onCodeChange(event.target.value.replace(/\D/g, ""))}
          placeholder="000000"
          value={code}
        />
        {isFixturePreview ? <p className="u33-confirm-hint">{t("Preview: any 6 digits")}</p> : null}
      </div>
      <div className="u33-confirm-pin">
        <SensitiveFactorField onContinue={onContinue} pin={pin} />
      </div>
    </div>
  );
}

