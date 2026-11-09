// IP of Webby-Soft SRL.
// The logic of the PIN flows (ACC-DEC-009), without markup: create, change and forgot PIN, and the
// email code each one needs. The old dialogs (pin.tsx) and the U33 screens (portal/screens/account)
// render their own fields on top of these hooks, so the API calls and the error handling live once.
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

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
import { PIN_LENGTH, pinApiError, pinWeakness } from "./pinRules";
import { usePinStatus } from "./pinState";

export function pinErrorText(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Request failed. Retry once the connection is restored.";
}

/** Seconds left until a time (ms), counting down once a second. */
export function useSecondsLeft(untilMs: number) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    setNowMs(Date.now());
    if (untilMs <= Date.now()) return undefined;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [untilMs]);
  return Math.max(0, Math.ceil((untilMs - nowMs) / 1000));
}

/** The wait of a throttled request (retry_after_seconds, or "N seconds" in the detail). */
export function retryAfter(error: unknown) {
  if (!(error instanceof ApiClientError) || !error.payload || typeof error.payload !== "object") return undefined;
  const payload = error.payload as Record<string, unknown>;
  if (typeof payload.retry_after_seconds === "number") return payload.retry_after_seconds;
  if (typeof payload.wait === "number") return payload.wait;
  const match = (typeof payload.detail === "string" ? payload.detail : "").match(/(\d+)\s+seconds?/i);
  return match ? Number.parseInt(match[1], 10) : undefined;
}

/** The email code of a sensitive action: request, resend cooldown and the button label. */
export function useFlowEmailCode(action: ActionEnum) {
  const request = useV1AuthSensitiveActionCodeRequestCreate();
  const [codeId, setCodeId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [error, setError] = useState("");
  const cooldown = useSecondsLeft(cooldownUntil);
  const send = useCallback(() => {
    setError("");
    if (isFixturePreview) {
      setCodeId("00000000-0000-0000-0000-000000000000");
      setExpiresAt(new Date(Date.now() + 10 * 60 * 1000).toISOString());
      setCooldownUntil(Date.now() + 60_000);
      return;
    }
    request.mutate(
      { data: { action } },
      {
        onSuccess: (response) => {
          setCodeId(response.code_id);
          setExpiresAt(response.expires_at);
          setCooldownUntil(Date.now() + 60_000);
        },
        onError: (mutationError) => {
          const wait = retryAfter(mutationError);
          if (wait) setCooldownUntil(Date.now() + wait * 1000);
          setError(pinErrorText(mutationError));
        }
      }
    );
  }, [action, request]);
  const label = request.isPending
    ? "Sending code..."
    : cooldown > 0
      ? codeId ? `Code sent. Send new in ${cooldown}s` : `Send new in ${cooldown}s`
      : codeId ? "Send a new email code" : "Send email code";
  return { codeId, expiresAt, send, label, cooldown, disabled: request.isPending || cooldown > 0, error, isSending: request.isPending };
}

export type FlowEmailCode = ReturnType<typeof useFlowEmailCode>;

/** Sends the email code once, as soon as the flow is active (never in preview mode). */
export function useAutoSend(send: () => void, active: boolean) {
  const sent = useRef(false);
  useEffect(() => {
    if (!active || sent.current || isFixturePreview) return;
    sent.current = true;
    send();
  }, [active, send]);
}

export function useInvalidatePinQueries() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: getV1AuthMeRetrieveQueryKey() });
    void queryClient.invalidateQueries({ queryKey: getV1AuthPinStatusRetrieveQueryKey() });
  }, [queryClient]);
}

// ---- Create -------------------------------------------------------------------------------

/** Creating the PIN; outside registration a fresh pin_setup email code is needed. */
export function useCreatePinFlow({ requiresEmailCode, onSaved }: { requiresEmailCode: boolean; onSaved: (pin: string) => void }) {
  const [pin, setPinState] = useState("");
  const [confirmation, setConfirmationState] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [confirmationError, setConfirmationError] = useState("");
  const mutation = useV1AuthPinSetCreate();
  const emailCode = useFlowEmailCode(ActionEnum.pin_setup);
  const invalidate = useInvalidatePinQueries();
  useAutoSend(emailCode.send, requiresEmailCode);
  const weakness = pin.length === PIN_LENGTH ? pinWeakness(pin) : null;
  const mismatch = confirmation.length === PIN_LENGTH && confirmation !== pin;
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
    mutation.mutate(
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
          setError(pinError?.detail ?? pinErrorText(mutationError));
        }
      }
    );
  };

  return {
    pin,
    setPin: (next: string) => {
      setPinState(next);
      setError("");
    },
    confirmation,
    setConfirmation: (next: string) => {
      setConfirmationState(next);
      setConfirmationError("");
    },
    code,
    setCode,
    emailCode,
    requiresEmailCode,
    weakness,
    mismatch,
    error,
    confirmationError,
    ready,
    saving: mutation.isPending,
    save
  };
}

// ---- Change -------------------------------------------------------------------------------

/** Changing the PIN: the current PIN, the new PIN twice and a pin_change email code. */
export function useChangePinFlow({ active = true }: { active?: boolean } = {}) {
  const [current, setCurrentState] = useState("");
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
  useAutoSend(emailCode.send, active && !done);
  const weakness = pin.length === PIN_LENGTH ? pinWeakness(pin) : null;
  const sameAsCurrent = pin.length === PIN_LENGTH && pin === current;
  const mismatch = confirmation.length === PIN_LENGTH && confirmation !== pin;
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
        setCurrent("");
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
          setError(pinError?.detail ?? pinErrorText(mutationError));
        }
      }
    );
  };

  function setCurrent(next: string) {
    setCurrentState(next);
    setCurrentError("");
  }

  return {
    current,
    setCurrent,
    pin,
    setPin,
    confirmation,
    setConfirmation,
    code,
    setCode,
    emailCode,
    weakness,
    sameAsCurrent,
    mismatch,
    currentError,
    error,
    lockedUntil,
    done,
    ready,
    saving: mutation.isPending,
    submit
  };
}

// ---- Forgot -------------------------------------------------------------------------------

/** Setting a new PIN after a forgotten one: an email code and an SMS code to the verified phone. */
export function useForgotPinFlow() {
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
  const mismatch = confirmation.length === PIN_LENGTH && confirmation !== pin;
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
        setSmsError(pinApiError(mutationError)?.detail ?? pinErrorText(mutationError));
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
          setError(pinError?.detail ?? pinErrorText(mutationError));
        }
      }
    );
  };

  const smsLabel = startMutation.isPending
    ? "Sending..."
    : smsCooldown > 0
      ? `Resend in ${smsCooldown}s`
      : challengeId ? "Resend SMS" : "Send SMS";

  return {
    started,
    start,
    lastDigits,
    resetAvailable,
    emailCode,
    code,
    setCode,
    smsCode,
    setSmsCode,
    sendSms,
    smsLabel,
    smsCooldown,
    smsSending: startMutation.isPending,
    smsSent: Boolean(challengeId),
    smsDisabled: startMutation.isPending || smsCooldown > 0,
    smsError,
    pin,
    setPin,
    confirmation,
    setConfirmation,
    weakness,
    mismatch,
    error,
    done,
    ready,
    saving: confirmMutation.isPending,
    submit
  };
}
