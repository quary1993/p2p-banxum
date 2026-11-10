// IP of Webby-Soft SRL.
// The investor's 6-digit PIN (ACC-DEC-009) in the old skin: the six-box input, the create and
// forgot dialogs, and the PIN part of every sensitive action (email code + PIN). The flow logic is in
// pinFlows.ts; the U33 screens (portal/screens/account) render their own fields on the same hooks.
import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
  type ReactNode
} from "react";

import { useT } from "../i18n";
import { isFixturePreview } from "./data";
import { useCreatePinFlow, useForgotPinFlow, type FlowEmailCode } from "./pinFlows";
import { PIN_LENGTH, formatPinLockTime, isRepeatedDigit, isStraightRun } from "./pinRules";
import { usePinStatus, type SensitivePin } from "./pinState";
import { Banner, Button, Field, Icon, Modal } from "./ui";

// ---- Six-box input ------------------------------------------------------------------------

type PinInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: ReactNode;
  disabled?: boolean;
  autoFocus?: boolean;
  /** Extra content on the label row, after "Show" (for example "Forgot PIN?"). */
  aside?: ReactNode;
  /** A new value moves the focus back to the first box (after a wrong PIN). */
  focusSignal?: number;
};

/** Six square boxes for a 6-digit PIN: digits only, focus moves on, paste fills all. */
export function PinInput({ label, value, onChange, error, hint, disabled = false, autoFocus = false, aside, focusSignal = 0 }: PinInputProps) {
  const t = useT();
  const id = useId();
  const labelId = `${id}label`;
  const messageId = `${id}message`;
  const [shown, setShown] = useState(false);
  const boxes = useRef<Array<HTMLInputElement | null>>([]);
  const digits = value.replace(/\D/g, "").slice(0, PIN_LENGTH);
  // The digits as just changed, before the parent re-renders: focus moves in the same
  // event, and the focused box must not send the focus back to an older position.
  const latest = useRef(digits);
  useLayoutEffect(() => {
    latest.current = digits;
  });
  const change = (next: string) => {
    latest.current = next;
    onChange(next);
  };

  const focusBox = (index: number) => {
    const box = boxes.current[Math.max(0, Math.min(PIN_LENGTH - 1, index))];
    box?.focus();
    box?.select();
  };

  useEffect(() => {
    if (autoFocus) boxes.current[0]?.focus();
  }, [autoFocus]);
  useEffect(() => {
    if (focusSignal > 0) boxes.current[0]?.focus();
  }, [focusSignal]);

  const fillFrom = (index: number, incoming: string) => {
    const clean = incoming.replace(/\D/g, "");
    if (!clean) return;
    const next = clean.length >= PIN_LENGTH
      ? clean.slice(0, PIN_LENGTH)
      : (digits.slice(0, index) + clean + digits.slice(index + clean.length)).slice(0, PIN_LENGTH);
    change(next);
    focusBox(Math.min(next.length, PIN_LENGTH - 1));
  };

  const onBoxChange = (index: number, raw: string) => {
    // A masked box shows a dot, which is not a digit: only the new digit is left.
    let typed = raw.replace(/\D/g, "");
    if (!typed) {
      if (raw === "" && index < digits.length) change(digits.slice(0, index) + digits.slice(index + 1));
      return;
    }
    const old = digits[index] ?? "";
    if (old && typed.length === 2 && typed.includes(old)) {
      // A digit typed next to the shown one replaces it.
      typed = typed[0] === old ? typed[1] : typed[0];
    }
    if (typed.length > 1) {
      // Autofill or a paste the browser delivered as typing.
      fillFrom(index, typed);
      return;
    }
    const digit = typed;
    const position = Math.min(index, digits.length);
    const next = (digits.slice(0, position) + digit + digits.slice(position + 1)).slice(0, PIN_LENGTH);
    change(next);
    if (position < PIN_LENGTH - 1) focusBox(position + 1);
  };

  const onKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Backspace") {
      event.preventDefault();
      if (index < digits.length) {
        change(digits.slice(0, index) + digits.slice(index + 1));
        focusBox(index);
      } else if (index > 0) {
        change(digits.slice(0, index - 1));
        focusBox(index - 1);
      }
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusBox(index - 1);
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      focusBox(Math.min(index + 1, digits.length));
      return;
    }
    if (event.key.length === 1 && !/\d/.test(event.key) && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
    }
  };

  const onPaste = (index: number, event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    fillFrom(digits.length === PIN_LENGTH ? 0 : Math.min(index, digits.length), event.clipboardData.getData("text"));
  };

  return (
    <div aria-describedby={error || hint ? messageId : undefined} aria-labelledby={labelId} className={`pin-field${error ? " has-error" : ""}`} role="group">
      <div className="pin-field-head">
        <span className="pin-field-label" id={labelId}>{label}</span>
        <span className="pin-field-tools">
          <button aria-label={shown ? t("Hide {label}", { label }) : t("Show {label}", { label })} aria-pressed={shown} className="pin-text-btn" disabled={disabled} onClick={() => setShown((current) => !current)} type="button">
            {shown ? t("Hide") : t("Show")}
          </button>
          {aside}
        </span>
      </div>
      <div className="pin-boxes">
        {Array.from({ length: PIN_LENGTH }, (_, index) => {
          const digit = digits[index] ?? "";
          return (
            <input
              aria-describedby={error || hint ? messageId : undefined}
              aria-invalid={error ? true : undefined}
              aria-label={t("{label} digit {position} of {count}", { label, position: index + 1, count: PIN_LENGTH })}
              autoComplete="off"
              className={`pin-box${digit ? " is-filled" : ""}`}
              disabled={disabled}
              inputMode="numeric"
              key={index}
              maxLength={PIN_LENGTH}
              onChange={(event) => onBoxChange(index, event.target.value)}
              onFocus={(event) => {
                if (index > latest.current.length) {
                  focusBox(latest.current.length);
                  return;
                }
                event.target.select();
              }}
              onKeyDown={(event) => onKeyDown(index, event)}
              onPaste={(event) => onPaste(index, event)}
              pattern="[0-9]*"
              ref={(element) => {
                boxes.current[index] = element;
              }}
              spellCheck={false}
              type="text"
              value={digit ? (shown ? digit : "•") : ""}
            />
          );
        })}
      </div>
      {error ? (
        <p className="pin-field-error" id={messageId} role="alert">{error}</p>
      ) : hint ? (
        <p className="pin-field-hint" id={messageId}>{hint}</p>
      ) : null}
    </div>
  );
}

// ---- Rules checklist ----------------------------------------------------------------------

export function PinRules({ pin, confirmation }: { pin: string; confirmation: string }) {
  const t = useT();
  const complete = pin.length === PIN_LENGTH;
  const rules = [
    { key: "length", label: t("6 digits"), met: complete },
    { key: "repeat", label: t("Not one digit repeated, like 111111"), met: complete && !isRepeatedDigit(pin) },
    { key: "run", label: t("Not a straight run, like 123456 or 654321"), met: complete && !isStraightRun(pin) },
    { key: "match", label: t("Both entries match"), met: complete && confirmation === pin }
  ];
  return (
    <div className="pin-rules">
      <div className="pin-rules-title">{t("Your PIN")}</div>
      <ul aria-label={t("PIN rules")}>
        {rules.map((rule) => (
          <li className={rule.met ? "is-met" : ""} key={rule.key}>
            <span aria-hidden="true" className="pin-rule-mark">{rule.met ? <Icon name="check" size={12} /> : null}</span>
            <span>{rule.label}</span>
            <span className="sr-only">{rule.met ? ` (${t("done")})` : ` (${t("not yet")})`}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---- Email code for the PIN flows ---------------------------------------------------------

function EmailCodeInput({
  label,
  value,
  onChange,
  code
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  code: FlowEmailCode;
}) {
  const t = useT();
  const fieldLabel = label ?? t("Email confirmation code");
  return (
    <Field error={code.error || undefined} hint={isFixturePreview ? t("Demo: any 6 digits") : undefined} label={fieldLabel}>
      <div className="code-request-row">
        <input
          aria-label={fieldLabel}
          autoComplete="one-time-code"
          className="input mono"
          inputMode="numeric"
          maxLength={6}
          onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
          placeholder="000000"
          value={value}
        />
        <Button className="code-request-button" disabled={code.disabled} variant="ghost" onClick={code.send}>
          {code.label}
        </Button>
      </div>
    </Field>
  );
}

// ---- Create -------------------------------------------------------------------------------

type CreatePinFormProps = {
  /** True outside registration: a fresh pin_setup email code is needed. */
  requiresEmailCode: boolean;
  onSaved: (pin: string) => void;
  /** Wide layout: entry on the left, rules on the right (registration and the post-login screen). */
  layout?: "split" | "stacked";
  autoFocus?: boolean;
  footer?: ReactNode;
};

export function CreatePinForm({ requiresEmailCode, onSaved, layout = "stacked", autoFocus = true, footer }: CreatePinFormProps) {
  const t = useT();
  const flow = useCreatePinFlow({ requiresEmailCode, onSaved });
  const { pin, confirmation, code, weakness, error, confirmationError, ready } = flow;
  const save = flow.save;

  const entry = (
    <div className="pin-create-entry">
      <PinInput
        autoFocus={autoFocus}
        error={weakness ?? undefined}
        label={t("PIN")}
        value={pin}
        onChange={flow.setPin}
      />
      <PinInput
        error={confirmationError || (flow.mismatch ? t("The two PINs do not match.") : undefined)}
        label={t("Repeat PIN")}
        value={confirmation}
        onChange={flow.setConfirmation}
      />
      {requiresEmailCode ? (
        <div className="pin-email-code auth-code">
          <EmailCodeInput code={flow.emailCode} value={code} onChange={flow.setCode} />
        </div>
      ) : null}
    </div>
  );

  return (
    <form
      className={`pin-create pin-create-${layout}`}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (ready && !flow.saving) save();
      }}
    >
      <div className="pin-create-body">
        {entry}
        <PinRules confirmation={confirmation} pin={pin} />
      </div>
      {error ? <Banner tone="bad" title={t("Could not save your PIN")}>{error}</Banner> : null}
      <div className="pin-create-actions">
        <Button disabled={!ready || flow.saving} size="lg" type="submit" variant="primary">
          {flow.saving ? t("Saving PIN...") : t("Save PIN")}
        </Button>
        {footer}
      </div>
    </form>
  );
}

export function CreatePinDialog({ onClose, onSaved, intro }: { onClose: () => void; onSaved: (pin: string) => void; intro?: ReactNode }) {
  const t = useT();
  const { status } = usePinStatus();
  return (
    <Modal onClose={onClose} title={t("Create your PIN")}>
      <div className="col gap-16 pin-dialog">
        <p className="pin-dialog-intro">
          {intro ?? t("You will enter it with the email code for every investment, withdrawal and bank change.")}
        </p>
        <CreatePinForm requiresEmailCode={status?.setup_requires_email_code ?? true} onSaved={onSaved} />
      </div>
    </Modal>
  );
}

// ---- Forgot -------------------------------------------------------------------------------

export function ForgotPinDialog({ onClose, onReset }: { onClose: () => void; onReset: (pin: string) => void }) {
  const t = useT();
  const flow = useForgotPinFlow();
  const { started, start, lastDigits, resetAvailable, code, smsCode, pin, confirmation, weakness, error, done, ready } = flow;

  if (done) {
    return (
      <Modal footer={<Button variant="primary" onClick={() => onReset(pin)}>{t("Done")}</Button>} onClose={() => onReset(pin)} title={t("New PIN saved")}>
        <Banner icon="checkCircle" tone="ok" title={t("Your new PIN is active")}>
          {t("Any PIN lock is lifted. We sent you an email about this change.")}
        </Banner>
      </Modal>
    );
  }

  if (!started) {
    return (
      <Modal
        footer={<><Button variant="ghost" onClick={onClose}>{t("Cancel")}</Button><Button disabled={!resetAvailable} variant="primary" onClick={start}>{t("Send the codes")}</Button></>}
        onClose={onClose}
        title={t("Forgot PIN")}
      >
        <div className="col gap-16 pin-dialog">
          <p className="pin-dialog-intro">
            {lastDigits
              ? t("To set a new PIN, confirm it is you with two codes: one by email and one by SMS to your phone number ending in {digits}.", { digits: lastDigits })
              : t("To set a new PIN, confirm it is you with two codes: one by email and one by SMS to your verified phone number.")}
          </p>
          {!resetAvailable ? (
            <Banner tone="warn" title={t("No verified phone number")}>
              {t("We cannot send an SMS code. Contact support to reset your PIN.")}
            </Banner>
          ) : null}
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      footer={<><Button variant="ghost" onClick={onClose}>{t("Cancel")}</Button><Button disabled={!ready || flow.saving} variant="primary" onClick={flow.submit}>{flow.saving ? t("Saving PIN...") : t("Save new PIN")}</Button></>}
      onClose={onClose}
      title={t("Forgot PIN")}
    >
      <div className="col gap-16 pin-dialog">
        <EmailCodeInput code={flow.emailCode} value={code} onChange={flow.setCode} />
        <Field error={flow.smsError || undefined} hint={isFixturePreview ? t("Demo: any 6 digits") : lastDigits ? t("Sent to your phone number ending in {digits}.", { digits: lastDigits }) : undefined} label={t("SMS code")}>
          <div className="code-request-row">
            <input
              aria-label={t("SMS code")}
              autoComplete="one-time-code"
              className="input mono"
              inputMode="numeric"
              maxLength={6}
              onChange={(event) => flow.setSmsCode(event.target.value.replace(/\D/g, ""))}
              placeholder="000000"
              value={smsCode}
            />
            <Button className="code-request-button" disabled={flow.smsDisabled} variant="ghost" onClick={flow.sendSms}>
              {flow.smsLabel}
            </Button>
          </div>
        </Field>
        <PinInput error={weakness ?? undefined} label={t("New PIN")} value={pin} onChange={flow.setPin} />
        <PinInput
          error={flow.mismatch ? t("The two PINs do not match.") : undefined}
          label={t("Repeat new PIN")}
          value={confirmation}
          onChange={flow.setConfirmation}
        />
        <PinRules confirmation={confirmation} pin={pin} />
        {error ? <Banner tone="bad" title={t("Could not reset your PIN")}>{error}</Banner> : null}
      </div>
    </Modal>
  );
}

// ---- The PIN of a sensitive action --------------------------------------------------------

function PinLockedBanner({ lockedUntil, onForgot }: { lockedUntil: string; onForgot: () => void }) {
  const t = useT();
  const time = lockedUntil ? formatPinLockTime(lockedUntil) : "";
  return (
    <Banner
      actions={<Button size="sm" onClick={onForgot}>{t("Forgot PIN?")}</Button>}
      icon="lock"
      tone="bad"
      title={t("PIN locked")}
    >
      {time
        ? t("Too many wrong PINs. You can try again after {time}, or set a new PIN now.", { time })
        : t("Too many wrong PINs. Try again later, or set a new PIN now.")}
    </Banner>
  );
}

/**
 * The PIN boxes next to the email code of a sensitive action, with the wrong-PIN line,
 * the lock notice with "Forgot PIN?", and the create-PIN dialog for an account without
 * a PIN. After the PIN is created the action continues (``onContinue``).
 */
export function SensitivePinField({ pin, onContinue }: { pin: SensitivePin; onContinue?: () => void }) {
  const t = useT();
  const continueRef = useRef(onContinue);
  useLayoutEffect(() => {
    continueRef.current = onContinue;
  });
  const [continueToken, setContinueToken] = useState(0);
  useEffect(() => {
    if (continueToken > 0) continueRef.current?.();
  }, [continueToken]);

  return (
    <div className="pin-sensitive">
      {pin.lockedUntil !== null ? <PinLockedBanner lockedUntil={pin.lockedUntil} onForgot={pin.openForgot} /> : null}
      <PinInput
        aside={pin.lockedUntil === null ? <button className="pin-text-btn" onClick={pin.openForgot} type="button">{t("Forgot PIN?")}</button> : null}
        disabled={pin.lockedUntil !== null}
        error={pin.error || undefined}
        focusSignal={pin.wrongCount}
        hint={isFixturePreview ? t("Demo: any 6 digits that are not all the same or a straight run") : t("The 6-digit PIN of your account.")}
        label={t("PIN")}
        value={pin.value}
        onChange={pin.setValue}
      />
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
    </div>
  );
}
