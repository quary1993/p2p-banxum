// IP of Webby-Soft SRL.
// Confirmation of a resale action in U33 markup (design .bxm-code-form with .bxm-otp): today's email
// code + PIN (ACC-DEC-009, until U33-DEC-01 / Phase 17.3 moves to the PIN only). The logic is the
// platform's existing one (App.tsx useSensitiveActionCode, investorPortal/pin*): one code per action,
// a 60-second resend cooldown, the PIN boxes with the wrong-PIN, lock and "Forgot PIN?" handling.
// The create/forgot PIN dialogs are the existing old-skin dialogs, shown in a LegacyBody above the
// U33 dialog (slice S5 rebuilds them).
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { CreatePinDialog, ForgotPinDialog, PinInput } from "../../../../investorPortal/pin";
import { formatPinLockTime } from "../../../../investorPortal/pinRules";
import { LegacyBody } from "../../../shell/LegacyBody";
import { NiIcon } from "../../../components";
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
  const codeId = useId();
  const { pin } = confirmation;
  const continueRef = useRef(onContinue);
  useLayoutEffect(() => {
    continueRef.current = onContinue;
  });
  const [continueToken, setContinueToken] = useState(0);
  useEffect(() => {
    if (continueToken > 0) continueRef.current?.();
  }, [continueToken]);
  const requestLabel = confirmation.isRequesting
    ? t("Sending code...")
    : confirmation.cooldownSeconds > 0
      ? confirmation.codeId
        ? t("Code sent. Send new in {seconds}s", { seconds: confirmation.cooldownSeconds })
        : t("Send new in {seconds}s", { seconds: confirmation.cooldownSeconds })
      : confirmation.codeId
        ? t("Send a new email code")
        : t("Send email code");
  const locked = pin.lockedUntil !== null;
  const lockTime = pin.lockedUntil ? formatPinLockTime(pin.lockedUntil) : "";
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
          className="form-control form-control-lg bxm-otp s106-code"
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
        {locked ? (
          <div className="alert alert-danger alert-icon u33-confirm-lock" role="alert">
            <NiIcon name="lock-alt" />
            <div>
              <strong>{t("PIN locked")}</strong>
              <p>{lockTime ? t("Too many wrong PINs. You can try again after {time}, or set a new PIN now.", { time: lockTime }) : t("Too many wrong PINs. Try again later, or set a new PIN now.")}</p>
              <button className="link" onClick={pin.openForgot} type="button">{t("Forgot PIN?")}</button>
            </div>
          </div>
        ) : null}
        <PinInput
          aside={locked ? null : <button className="pin-text-btn" onClick={pin.openForgot} type="button">{t("Forgot PIN?")}</button>}
          disabled={locked}
          error={pin.error || undefined}
          focusSignal={pin.wrongCount}
          hint={isFixturePreview ? t("Preview: any 6 digits that are not all the same or a straight run") : t("The 6-digit PIN of your account.")}
          label="PIN"
          onChange={pin.setValue}
          value={pin.value}
        />
      </div>
      {pin.createOpen || pin.forgotOpen
        ? createPortal(
            <div className="u33-pin-dialogs">
              <LegacyBody>
                {pin.createOpen ? (
                  <CreatePinDialog
                    intro={t("You need a PIN to confirm this action. Create it now; the action continues right after.")}
                    onClose={pin.closeDialogs}
                    onSaved={(newPin) => {
                      pin.afterCreate(newPin);
                      setContinueToken((token) => token + 1);
                    }}
                  />
                ) : null}
                {pin.forgotOpen ? <ForgotPinDialog onClose={pin.closeDialogs} onReset={pin.afterReset} /> : null}
              </LegacyBody>
            </div>,
            document.body
          )
        : null}
    </div>
  );
}

