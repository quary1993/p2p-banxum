// IP of Webby-Soft SRL.
// The investor's 6-digit PIN (ACC-DEC-009): the six-box input, the create, change and
// forgot flows, and the PIN part of every sensitive action (email code + PIN).
import { useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
  type ReactNode
} from "react";

import {
  ActionEnum,
  getV1AuthMeRetrieveQueryKey,
  getV1AuthPinStatusRetrieveQueryKey,
  useV1AuthPinChangeCreate,
  useV1AuthPinResetConfirmCreate,
  useV1AuthPinResetStartCreate,
  useV1AuthPinSetCreate,
  useV1AuthSensitiveActionCodeRequestCreate
} from "../api/generated/banxumApi";
import { ApiClientError } from "../api/client/httpClient";
import { isFixturePreview } from "./data";
import {
  PIN_LENGTH,
  formatPinLockTime,
  isRepeatedDigit,
  isStraightRun,
  pinApiError,
  pinWeakness
} from "./pinRules";
import { usePinStatus, type SensitivePin } from "./pinState";
import { Banner, Button, Chip, Field, Icon, Modal } from "./ui";

function errorText(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Request failed. Retry once the connection is restored.";
}

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
          <button aria-label={shown ? `Hide ${label}` : `Show ${label}`} aria-pressed={shown} className="pin-text-btn" disabled={disabled} onClick={() => setShown((current) => !current)} type="button">
            {shown ? "Hide" : "Show"}
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
              aria-label={`${label} digit ${index + 1} of ${PIN_LENGTH}`}
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
  const complete = pin.length === PIN_LENGTH;
  const rules = [
    { key: "length", label: "6 digits", met: complete },
    { key: "repeat", label: "Not one digit repeated, like 111111", met: complete && !isRepeatedDigit(pin) },
    { key: "run", label: "Not a straight run, like 123456 or 654321", met: complete && !isStraightRun(pin) },
    { key: "match", label: "Both entries match", met: complete && confirmation === pin }
  ];
  return (
    <div className="pin-rules">
      <div className="pin-rules-title">Your PIN</div>
      <ul aria-label="PIN rules">
        {rules.map((rule) => (
          <li className={rule.met ? "is-met" : ""} key={rule.key}>
            <span aria-hidden="true" className="pin-rule-mark">{rule.met ? <Icon name="check" size={12} /> : null}</span>
            <span>{rule.label}</span>
            <span className="sr-only">{rule.met ? " (done)" : " (not yet)"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---- Email code for the PIN flows ---------------------------------------------------------

function useSecondsLeft(untilMs: number) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    setNowMs(Date.now());
    if (untilMs <= Date.now()) return undefined;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [untilMs]);
  return Math.max(0, Math.ceil((untilMs - nowMs) / 1000));
}

function retryAfter(error: unknown) {
  if (!(error instanceof ApiClientError) || !error.payload || typeof error.payload !== "object") return undefined;
  const payload = error.payload as Record<string, unknown>;
  if (typeof payload.retry_after_seconds === "number") return payload.retry_after_seconds;
  const match = (typeof payload.detail === "string" ? payload.detail : "").match(/(\d+)\s+seconds?/i);
  return match ? Number.parseInt(match[1], 10) : undefined;
}

function useFlowEmailCode(action: ActionEnum) {
  const request = useV1AuthSensitiveActionCodeRequestCreate();
  const [codeId, setCodeId] = useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [error, setError] = useState("");
  const cooldown = useSecondsLeft(cooldownUntil);
  const send = useCallback(() => {
    setError("");
    if (isFixturePreview) {
      setCodeId("00000000-0000-0000-0000-000000000000");
      setCooldownUntil(Date.now() + 60_000);
      return;
    }
    request.mutate(
      { data: { action } },
      {
        onSuccess: (response) => {
          setCodeId(response.code_id);
          setCooldownUntil(Date.now() + 60_000);
        },
        onError: (mutationError) => {
          const wait = retryAfter(mutationError);
          if (wait) setCooldownUntil(Date.now() + wait * 1000);
          setError(errorText(mutationError));
        }
      }
    );
  }, [action, request]);
  const label = request.isPending
    ? "Sending code..."
    : cooldown > 0
      ? codeId ? `Code sent. Send new in ${cooldown}s` : `Send new in ${cooldown}s`
      : codeId ? "Send a new email code" : "Send email code";
  return { codeId, send, label, disabled: request.isPending || cooldown > 0, error, isSending: request.isPending };
}

function EmailCodeInput({
  label = "Email confirmation code",
  value,
  onChange,
  code
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  code: ReturnType<typeof useFlowEmailCode>;
}) {
  return (
    <Field error={code.error || undefined} hint={isFixturePreview ? "Demo: any 6 digits" : undefined} label={label}>
      <div className="code-request-row">
        <input
          aria-label={label}
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

function useAutoSend(send: () => void, active: boolean) {
  const sent = useRef(false);
  useEffect(() => {
    if (!active || sent.current || isFixturePreview) return;
    sent.current = true;
    send();
  }, [active, send]);
}

function useInvalidatePinQueries() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: getV1AuthMeRetrieveQueryKey() });
    void queryClient.invalidateQueries({ queryKey: getV1AuthPinStatusRetrieveQueryKey() });
  }, [queryClient]);
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
  const [pin, setPin] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [confirmationError, setConfirmationError] = useState("");
  const setMutation = useV1AuthPinSetCreate();
  const emailCode = useFlowEmailCode(ActionEnum.pin_setup);
  const invalidate = useInvalidatePinQueries();
  useAutoSend(emailCode.send, requiresEmailCode);
  const weakness = pin.length === PIN_LENGTH ? pinWeakness(pin) : null;
  const ready =
    pin.length === PIN_LENGTH &&
    !weakness &&
    confirmation === pin &&
    (!requiresEmailCode || (code.length === 6 && (isFixturePreview || Boolean(emailCode.codeId))));

  const save = () => {
    setError("");
    setConfirmationError("");
    if (weakness) {
      setError(weakness);
      return;
    }
    if (confirmation !== pin) {
      setConfirmationError("The two PINs do not match. Enter the same PIN twice.");
      return;
    }
    if (isFixturePreview) {
      onSaved(pin);
      return;
    }
    setMutation.mutate(
      {
        data: {
          new_pin: pin,
          new_pin_confirmation: confirmation,
          ...(requiresEmailCode && emailCode.codeId
            ? { sensitive_action_code_id: emailCode.codeId, sensitive_action_code: code }
            : {})
        }
      },
      {
        onSuccess: () => {
          invalidate();
          onSaved(pin);
        },
        onError: (mutationError) => {
          const pinError = pinApiError(mutationError);
          if (pinError?.code === "pin_already_set") {
            invalidate();
            onSaved(pin);
            return;
          }
          setError(pinError?.detail ?? errorText(mutationError));
        }
      }
    );
  };

  const entry = (
    <div className="pin-create-entry">
      <PinInput
        autoFocus={autoFocus}
        error={weakness ?? undefined}
        label="PIN"
        value={pin}
        onChange={(next) => {
          setPin(next);
          setError("");
        }}
      />
      <PinInput
        error={confirmationError || (confirmation.length === PIN_LENGTH && confirmation !== pin ? "The two PINs do not match." : undefined)}
        label="Repeat PIN"
        value={confirmation}
        onChange={(next) => {
          setConfirmation(next);
          setConfirmationError("");
        }}
      />
      {requiresEmailCode ? (
        <div className="pin-email-code auth-code">
          <EmailCodeInput code={emailCode} value={code} onChange={setCode} />
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
        if (ready && !setMutation.isPending) save();
      }}
    >
      <div className="pin-create-body">
        {entry}
        <PinRules confirmation={confirmation} pin={pin} />
      </div>
      {error ? <Banner tone="bad" title="Could not save your PIN">{error}</Banner> : null}
      <div className="pin-create-actions">
        <Button disabled={!ready || setMutation.isPending} size="lg" type="submit" variant="primary">
          {setMutation.isPending ? "Saving PIN..." : "Save PIN"}
        </Button>
        {footer}
      </div>
    </form>
  );
}

export function CreatePinDialog({ onClose, onSaved, intro }: { onClose: () => void; onSaved: (pin: string) => void; intro?: ReactNode }) {
  const { status } = usePinStatus();
  return (
    <Modal onClose={onClose} title="Create your PIN">
      <div className="col gap-16 pin-dialog">
        <p className="pin-dialog-intro">
          {intro ?? "You will enter it with the email code for every investment, withdrawal and bank change."}
        </p>
        <CreatePinForm requiresEmailCode={status?.setup_requires_email_code ?? true} onSaved={onSaved} />
      </div>
    </Modal>
  );
}

// ---- Change -------------------------------------------------------------------------------

export function ChangePinDialog({ onClose, onChanged, onForgot }: { onClose: () => void; onChanged: () => void; onForgot: () => void }) {
  const [current, setCurrent] = useState("");
  const [pin, setPin] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [code, setCode] = useState("");
  const [currentError, setCurrentError] = useState("");
  const [error, setError] = useState("");
  const [lockedUntil, setLockedUntil] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const mutation = useV1AuthPinChangeCreate();
  const emailCode = useFlowEmailCode(ActionEnum.pin_change);
  const invalidate = useInvalidatePinQueries();
  useAutoSend(emailCode.send, !done);
  const weakness = pin.length === PIN_LENGTH ? pinWeakness(pin) : null;
  const sameAsCurrent = pin.length === PIN_LENGTH && pin === current;
  const ready =
    current.length === PIN_LENGTH &&
    pin.length === PIN_LENGTH &&
    !weakness &&
    !sameAsCurrent &&
    confirmation === pin &&
    code.length === 6 &&
    (isFixturePreview || Boolean(emailCode.codeId)) &&
    !lockedUntil;

  const submit = () => {
    setError("");
    setCurrentError("");
    if (isFixturePreview) {
      if (pinWeakness(current)) {
        setCurrentError("Wrong PIN. 4 attempts left before your PIN is locked.");
        return;
      }
      setDone(true);
      return;
    }
    if (!emailCode.codeId) return;
    mutation.mutate(
      {
        data: {
          pin: current,
          new_pin: pin,
          new_pin_confirmation: confirmation,
          sensitive_action_code_id: emailCode.codeId,
          sensitive_action_code: code
        }
      },
      {
        onSuccess: () => {
          invalidate();
          setDone(true);
        },
        onError: (mutationError) => {
          const pinError = pinApiError(mutationError);
          if (pinError?.code === "pin_invalid") {
            setCurrent("");
            setCurrentError(pinError.detail);
            return;
          }
          if (pinError?.code === "pin_locked") {
            setLockedUntil(pinError.lockedUntil ?? "");
            invalidate();
            return;
          }
          setError(pinError?.detail ?? errorText(mutationError));
        }
      }
    );
  };

  if (done) {
    return (
      <Modal footer={<Button variant="primary" onClick={() => { onChanged(); onClose(); }}>Done</Button>} onClose={() => { onChanged(); onClose(); }} title="PIN changed">
        <Banner icon="checkCircle" tone="ok" title="Your new PIN is active">
          Use it with the email code from now on. We sent you an email about this change.
        </Banner>
      </Modal>
    );
  }

  return (
    <Modal
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ready || mutation.isPending} variant="primary" onClick={submit}>{mutation.isPending ? "Saving PIN..." : "Save new PIN"}</Button></>}
      onClose={onClose}
      title="Change PIN"
    >
      <div className="col gap-16 pin-dialog">
        {lockedUntil !== null ? (
          <PinLockedBanner lockedUntil={lockedUntil} onForgot={onForgot} />
        ) : null}
        <PinInput
          autoFocus
          error={currentError || undefined}
          label="Current PIN"
          value={current}
          onChange={(next) => {
            setCurrent(next);
            setCurrentError("");
          }}
        />
        <PinInput
          error={weakness ?? (sameAsCurrent ? "Your new PIN must be different from your current PIN." : undefined)}
          label="New PIN"
          value={pin}
          onChange={setPin}
        />
        <PinInput
          error={confirmation.length === PIN_LENGTH && confirmation !== pin ? "The two PINs do not match." : undefined}
          label="Repeat new PIN"
          value={confirmation}
          onChange={setConfirmation}
        />
        <PinRules confirmation={confirmation} pin={pin} />
        <EmailCodeInput code={emailCode} value={code} onChange={setCode} />
        {error ? <Banner tone="bad" title="Could not change your PIN">{error}</Banner> : null}
      </div>
    </Modal>
  );
}

// ---- Forgot -------------------------------------------------------------------------------

export function ForgotPinDialog({ onClose, onReset }: { onClose: () => void; onReset: (pin: string) => void }) {
  const { status } = usePinStatus();
  const [started, setStarted] = useState(false);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [smsCooldownUntil, setSmsCooldownUntil] = useState(0);
  const smsCooldown = useSecondsLeft(smsCooldownUntil);
  const [code, setCode] = useState("");
  const [smsCode, setSmsCode] = useState("");
  const [pin, setPin] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [smsError, setSmsError] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const emailCode = useFlowEmailCode(ActionEnum.pin_reset);
  const startMutation = useV1AuthPinResetStartCreate();
  const confirmMutation = useV1AuthPinResetConfirmCreate();
  const invalidate = useInvalidatePinQueries();
  const lastDigits = status?.phone_last_digits ?? "";
  const resetAvailable = status ? status.reset_available : true;
  const weakness = pin.length === PIN_LENGTH ? pinWeakness(pin) : null;
  const ready =
    code.length === 6 &&
    smsCode.length === 6 &&
    pin.length === PIN_LENGTH &&
    !weakness &&
    confirmation === pin &&
    (isFixturePreview || (Boolean(emailCode.codeId) && Boolean(challengeId)));

  const sendSms = () => {
    setSmsError("");
    if (isFixturePreview) {
      setChallengeId("fixture-pin-reset");
      setSmsCooldownUntil(Date.now() + 60_000);
      return;
    }
    startMutation.mutate(undefined, {
      onSuccess: (response) => {
        setChallengeId(response.phone_challenge_id);
        setSmsCooldownUntil(Date.now() + 60_000);
      },
      onError: (mutationError) => {
        const wait = retryAfter(mutationError);
        if (wait) setSmsCooldownUntil(Date.now() + wait * 1000);
        setSmsError(pinApiError(mutationError)?.detail ?? errorText(mutationError));
      }
    });
  };

  const start = () => {
    setStarted(true);
    emailCode.send();
    sendSms();
  };

  const submit = () => {
    setError("");
    setSmsError("");
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    if (!emailCode.codeId || !challengeId) return;
    confirmMutation.mutate(
      {
        data: {
          sensitive_action_code_id: emailCode.codeId,
          sensitive_action_code: code,
          phone_challenge_id: challengeId,
          phone_code: smsCode,
          new_pin: pin,
          new_pin_confirmation: confirmation
        }
      },
      {
        onSuccess: () => {
          invalidate();
          setDone(true);
        },
        onError: (mutationError) => {
          const pinError = pinApiError(mutationError);
          if (pinError?.code === "phone_code_invalid" || pinError?.code === "phone_code_attempts_exceeded") {
            setSmsError(pinError.detail);
            return;
          }
          setError(pinError?.detail ?? errorText(mutationError));
        }
      }
    );
  };

  if (done) {
    return (
      <Modal footer={<Button variant="primary" onClick={() => onReset(pin)}>Done</Button>} onClose={() => onReset(pin)} title="New PIN saved">
        <Banner icon="checkCircle" tone="ok" title="Your new PIN is active">
          Any PIN lock is lifted. We sent you an email about this change.
        </Banner>
      </Modal>
    );
  }

  if (!started) {
    return (
      <Modal
        footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!resetAvailable} variant="primary" onClick={start}>Send the codes</Button></>}
        onClose={onClose}
        title="Forgot PIN"
      >
        <div className="col gap-16 pin-dialog">
          <p className="pin-dialog-intro">
            To set a new PIN, confirm it is you with two codes: one by email and one by SMS
            {lastDigits ? <> to your phone number ending in <b>{lastDigits}</b></> : " to your verified phone number"}.
          </p>
          {!resetAvailable ? (
            <Banner tone="warn" title="No verified phone number">
              We cannot send an SMS code. Contact support to reset your PIN.
            </Banner>
          ) : null}
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ready || confirmMutation.isPending} variant="primary" onClick={submit}>{confirmMutation.isPending ? "Saving PIN..." : "Save new PIN"}</Button></>}
      onClose={onClose}
      title="Forgot PIN"
    >
      <div className="col gap-16 pin-dialog">
        <EmailCodeInput code={emailCode} value={code} onChange={setCode} />
        <Field error={smsError || undefined} hint={isFixturePreview ? "Demo: any 6 digits" : lastDigits ? `Sent to your phone number ending in ${lastDigits}.` : undefined} label="SMS code">
          <div className="code-request-row">
            <input
              aria-label="SMS code"
              autoComplete="one-time-code"
              className="input mono"
              inputMode="numeric"
              maxLength={6}
              onChange={(event) => setSmsCode(event.target.value.replace(/\D/g, ""))}
              placeholder="000000"
              value={smsCode}
            />
            <Button className="code-request-button" disabled={startMutation.isPending || smsCooldown > 0} variant="ghost" onClick={sendSms}>
              {startMutation.isPending ? "Sending..." : smsCooldown > 0 ? `Resend in ${smsCooldown}s` : challengeId ? "Resend SMS" : "Send SMS"}
            </Button>
          </div>
        </Field>
        <PinInput error={weakness ?? undefined} label="New PIN" value={pin} onChange={setPin} />
        <PinInput
          error={confirmation.length === PIN_LENGTH && confirmation !== pin ? "The two PINs do not match." : undefined}
          label="Repeat new PIN"
          value={confirmation}
          onChange={setConfirmation}
        />
        <PinRules confirmation={confirmation} pin={pin} />
        {error ? <Banner tone="bad" title="Could not reset your PIN">{error}</Banner> : null}
      </div>
    </Modal>
  );
}

// ---- The PIN of a sensitive action --------------------------------------------------------

function PinLockedBanner({ lockedUntil, onForgot }: { lockedUntil: string; onForgot: () => void }) {
  const time = lockedUntil ? formatPinLockTime(lockedUntil) : "";
  return (
    <Banner
      actions={<Button size="sm" onClick={onForgot}>Forgot PIN?</Button>}
      icon="lock"
      tone="bad"
      title="PIN locked"
    >
      {time
        ? `Too many wrong PINs. You can try again after ${time}, or set a new PIN now.`
        : "Too many wrong PINs. Try again later, or set a new PIN now."}
    </Banner>
  );
}

/**
 * The PIN boxes next to the email code of a sensitive action, with the wrong-PIN line,
 * the lock notice with "Forgot PIN?", and the create-PIN dialog for an account without
 * a PIN. After the PIN is created the action continues (``onContinue``).
 */
export function SensitivePinField({ pin, onContinue }: { pin: SensitivePin; onContinue?: () => void }) {
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
        aside={pin.lockedUntil === null ? <button className="pin-text-btn" onClick={pin.openForgot} type="button">Forgot PIN?</button> : null}
        disabled={pin.lockedUntil !== null}
        error={pin.error || undefined}
        focusSignal={pin.wrongCount}
        hint={isFixturePreview ? "Demo: any 6 digits that are not all the same or a straight run" : "The 6-digit PIN of your account."}
        label="PIN"
        value={pin.value}
        onChange={pin.setValue}
      />
      {pin.createOpen ? (
        <CreatePinDialog
          intro="You need a PIN to confirm this action. Create it now; the action continues right after."
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

// ---- Settings -----------------------------------------------------------------------------

export function SettingsPinPanel({ readonly = false }: { readonly?: boolean }) {
  const { status, isLoading, query } = usePinStatus(!readonly);
  const [dialog, setDialog] = useState<"create" | "change" | "forgot" | null>(null);
  const [notice, setNotice] = useState("");
  const lockedUntil = status?.locked_until ?? null;
  const chip = !status
    ? null
    : lockedUntil
      ? <Chip tone="bad">{`Locked until ${formatPinLockTime(lockedUntil)}`}</Chip>
      : status.pin_set
        ? <Chip tone="ok">Set</Chip>
        : <Chip tone="warn">Not set</Chip>;
  const close = () => setDialog(null);
  return (
    <div className="col gap-16">
      <div className="acct-box">
        <div className="acct-row">
          <div className="acct-row-text">
            <Icon className="acct-row-icon" name="lock" size={16} />
            <span>
              <span className="acct-row-title">PIN</span>
              <span className="acct-row-sub">Needed with the email code for every investment, withdrawal and bank change.</span>
            </span>
          </div>
          <div className="acct-row-actions">{isLoading ? <span className="muted">-</span> : chip}</div>
        </div>
        <div className="acct-row pin-settings-actions">
          {status && !status.pin_set ? (
            <Button disabled={readonly} size="sm" variant="primary" onClick={() => setDialog("create")}>Create PIN</Button>
          ) : (
            <Button disabled={readonly || !status || Boolean(lockedUntil)} size="sm" onClick={() => setDialog("change")}>Change PIN</Button>
          )}
          <Button disabled={readonly || !status} size="sm" variant="ghost" onClick={() => setDialog("forgot")}>Forgot PIN?</Button>
        </div>
      </div>
      {query.isError && !isFixturePreview ? <Banner tone="bad" title="Could not load your PIN status">Reload the page to try again.</Banner> : null}
      {notice ? <Banner tone="ok" title={notice} /> : null}
      <p className="acct-settings-note">{"We never ask for your PIN by email, SMS or phone. Do not share it with anyone."}</p>
      {dialog === "create" ? (
        <CreatePinDialog onClose={close} onSaved={() => { close(); setNotice("Your PIN is saved."); }} />
      ) : null}
      {dialog === "change" ? (
        <ChangePinDialog onChanged={() => setNotice("Your PIN was changed.")} onClose={close} onForgot={() => setDialog("forgot")} />
      ) : null}
      {dialog === "forgot" ? (
        <ForgotPinDialog onClose={close} onReset={() => { close(); setNotice("Your new PIN is saved."); }} />
      ) : null}
    </div>
  );
}
