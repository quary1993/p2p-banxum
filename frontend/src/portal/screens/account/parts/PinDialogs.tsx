// IP of Webby-Soft SRL.
// The PIN dialogs of Profile & Settings -> Security in U33 style (design: .modal.p73-modal with the
// large code input), on the shared flow logic of investorPortal/pinFlows.ts (ACC-DEC-009: the PIN
// goes with an email code; 18.5: a forgotten PIN is reset with the password and an SMS code).
import type { ReactNode } from "react";

import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useChangePinFlow, useCreatePinFlow, useForgotPinFlow, type FlowEmailCode } from "../../../../investorPortal/pinFlows";
import { formatPinLockTime } from "../../../../investorPortal/pinRules";
import { usePinStatus } from "../../../../investorPortal/pinState";
import { Button, Dialog, NiIcon } from "../../../components";
import { emailCodeLabel } from "./format";
import { CodeField, DialogActions, Notice, PasswordField, PinCodeField } from "./ui";

/** The success state of a dialog (design: .hp-message-result). */
export function DialogResult({ title, children, onDone }: { title: ReactNode; children: ReactNode; onDone: () => void }) {
  const t = useT();
  return (
    <div className="hp-message-result" role="status">
      <NiIcon name="check-circle" />
      <h3>{title}</h3>
      <p>{children}</p>
      <Button onClick={onDone} variant="primary">{t("Done")}</Button>
    </div>
  );
}

/** The email-code field of a PIN flow, with its send/resend button. */
export function EmailCodeField({ code, value, onChange }: { code: FlowEmailCode; value: string; onChange: (value: string) => void }) {
  const t = useT();
  return (
    <CodeField
      error={code.error || undefined}
      hint={isFixturePreview ? t("Demo: any 6 digits") : code.codeId ? t("We sent a code to your email address.") : undefined}
      label={t("Email confirmation code")}
      onChange={onChange}
      onRequest={code.send}
      requestDisabled={code.disabled}
      requestLabel={emailCodeLabel(t, code)}
      value={value}
    />
  );
}

function PinRulesNote() {
  const t = useT();
  return <p className="acc-field-hint">{t("Six digits. Not one digit repeated, like 111111, and not a straight run, like 123456 or 654321.")}</p>;
}

export function ChangePinDialog({ onClose, onChanged, onForgot }: { onClose: () => void; onChanged: () => void; onForgot: () => void }) {
  const t = useT();
  const flow = useChangePinFlow();
  const finish = () => {
    onChanged();
    onClose();
  };
  if (flow.done) {
    return (
      <Dialog className="p73-modal" onClose={finish} size="sm" title={t("PIN changed")}>
        <DialogResult onDone={finish} title={t("Your new PIN is active")}>
          {t("Use it with the email code from now on. We sent you an email about this change.")}
        </DialogResult>
      </Dialog>
    );
  }
  const lockTime = flow.lockedUntil ? formatPinLockTime(flow.lockedUntil) : "";
  return (
    <Dialog busy={flow.saving} className="p73-modal" onClose={onClose} size="sm" title={t("Change PIN")}>
      <p className="p73-intro">{t("Enter your current PIN, then your new PIN twice, and confirm with the code we send to your email.")}</p>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (flow.ready && !flow.saving) flow.submit();
        }}
      >
        {flow.lockedUntil !== null ? (
          <Notice
            action={<Button onClick={onForgot} size="sm">{t("Forgot PIN?")}</Button>}
            title={t("PIN locked")}
            tone="danger"
          >
            {lockTime
              ? t("Too many wrong PINs. You can try again after {time}, or set a new PIN now.", { time: lockTime })
              : t("Too many wrong PINs. Try again later, or set a new PIN now.")}
          </Notice>
        ) : null}
        <PinCodeField autoFocus error={flow.currentError || undefined} label={t("Current PIN")} onChange={flow.setCurrent} value={flow.current} />
        <PinCodeField
          error={flow.weakness ? t(flow.weakness) : flow.sameAsCurrent ? t("Your new PIN must be different from your current PIN.") : undefined}
          label={t("New PIN")}
          onChange={flow.setPin}
          value={flow.pin}
        />
        <PinCodeField error={flow.mismatch ? t("The two PINs do not match.") : undefined} label={t("Repeat new PIN")} onChange={flow.setConfirmation} value={flow.confirmation} />
        <PinRulesNote />
        <EmailCodeField code={flow.emailCode} onChange={flow.setCode} value={flow.code} />
        {flow.error ? <Notice title={t("Could not change your PIN")} tone="danger">{flow.error}</Notice> : null}
        <DialogActions
          onCancel={onClose}
          primaryDisabled={!flow.ready || flow.saving}
          primaryLabel={flow.saving ? t("Saving PIN...") : t("Save new PIN")}
          primaryType="submit"
        />
      </form>
    </Dialog>
  );
}

export function ForgotPinDialog({ onClose, onReset }: { onClose: () => void; onReset: (pin: string) => void }) {
  const t = useT();
  const flow = useForgotPinFlow();
  if (flow.done) {
    return (
      <Dialog className="p73-modal" onClose={() => onReset(flow.pin)} size="sm" title={t("New PIN saved")}>
        <DialogResult onDone={() => onReset(flow.pin)} title={t("Your new PIN is active")}>
          {t("Any PIN lock is lifted. We sent you an email about this change.")}
        </DialogResult>
      </Dialog>
    );
  }
  if (!flow.started) {
    return (
      <Dialog busy={flow.smsSending} className="p73-modal" onClose={onClose} size="sm" title={t("Forgot PIN")}>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (flow.resetAvailable && !flow.smsSending) flow.start();
          }}
        >
          <p className="p73-intro">
            {flow.lastDigits
              ? t("To set a new PIN, confirm it is you: your password, then a code by SMS to your phone number ending in {digits}.", { digits: flow.lastDigits })
              : t("To set a new PIN, confirm it is you: your password, then a code by SMS to your verified phone number.")}
          </p>
          {!flow.resetAvailable ? (
            <Notice title={t("No verified phone number")} tone="warning">
              {t("We cannot send an SMS code. Contact support to reset your PIN.")}
            </Notice>
          ) : (
            <PasswordField autoFocus error={flow.passwordError ? t(flow.passwordError) : undefined} label={t("Password")} onChange={flow.setPassword} value={flow.password} />
          )}
          {flow.smsError ? <Notice title={t("Could not send the SMS code")} tone="danger">{flow.smsError}</Notice> : null}
          <DialogActions
            onCancel={onClose}
            primaryDisabled={!flow.resetAvailable || flow.smsSending || (!isFixturePreview && !flow.password)}
            primaryLabel={flow.smsSending ? t("Sending...") : t("Send SMS code")}
            primaryType="submit"
          />
        </form>
      </Dialog>
    );
  }
  return (
    <Dialog busy={flow.saving} className="p73-modal" onClose={onClose} size="sm" title={t("Forgot PIN")}>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (flow.ready && !flow.saving) flow.submit();
        }}
      >
        <CodeField
          autoFocus
          error={flow.smsError || undefined}
          hint={isFixturePreview ? t("Demo: any 6 digits") : flow.lastDigits ? t("Sent to your phone number ending in {digits}.", { digits: flow.lastDigits }) : undefined}
          label={t("SMS code")}
          onChange={flow.setSmsCode}
          onRequest={flow.sendSms}
          requestDisabled={flow.smsDisabled}
          requestLabel={
            flow.smsSending
              ? t("Sending...")
              : flow.smsCooldown > 0
                ? t("Resend in {seconds}s", { seconds: flow.smsCooldown })
                : t("Resend SMS")
          }
          value={flow.smsCode}
        />
        <PinCodeField error={flow.weakness ? t(flow.weakness) : undefined} label={t("New PIN")} onChange={flow.setPin} value={flow.pin} />
        <PinCodeField error={flow.mismatch ? t("The two PINs do not match.") : undefined} label={t("Repeat new PIN")} onChange={flow.setConfirmation} value={flow.confirmation} />
        <PinRulesNote />
        {flow.error ? <Notice title={t("Could not reset your PIN")} tone="danger">{flow.error}</Notice> : null}
        <DialogActions
          onCancel={onClose}
          primaryDisabled={!flow.ready || flow.saving}
          primaryLabel={flow.saving ? t("Saving PIN...") : t("Save new PIN")}
          primaryType="submit"
        />
      </form>
    </Dialog>
  );
}

export function CreatePinDialog({ onClose, onSaved, intro }: { onClose: () => void; onSaved: (pin: string) => void; intro?: string }) {
  const t = useT();
  const { status } = usePinStatus();
  const flow = useCreatePinFlow({ requiresEmailCode: status?.setup_requires_email_code ?? true, onSaved });
  return (
    <Dialog busy={flow.saving} className="p73-modal" onClose={onClose} size="sm" title={t("Create your PIN")}>
      <p className="p73-intro">{intro ?? t("You will enter it with the email code for every investment, withdrawal and bank account change.")}</p>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (flow.ready && !flow.saving) flow.save();
        }}
      >
        <PinCodeField autoFocus error={flow.weakness ? t(flow.weakness) : undefined} label={t("PIN")} onChange={flow.setPin} value={flow.pin} />
        <PinCodeField
          error={flow.confirmationError ? t(flow.confirmationError) : flow.mismatch ? t("The two PINs do not match.") : undefined}
          label={t("Repeat PIN")}
          onChange={flow.setConfirmation}
          value={flow.confirmation}
        />
        <PinRulesNote />
        {flow.requiresEmailCode ? <EmailCodeField code={flow.emailCode} onChange={flow.setCode} value={flow.code} /> : null}
        {flow.error ? <Notice title={t("Could not save your PIN")} tone="danger">{flow.error}</Notice> : null}
        <DialogActions onCancel={onClose} primaryDisabled={!flow.ready || flow.saving} primaryLabel={flow.saving ? t("Saving PIN...") : t("Save PIN")} primaryType="submit" />
      </form>
    </Dialog>
  );
}
