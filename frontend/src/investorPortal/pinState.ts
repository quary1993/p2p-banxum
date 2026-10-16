// IP of Webby-Soft SRL.
// PIN state: the account's PIN status and the PIN of a sensitive action (ACC-DEC-009).
import { useCallback, useState } from "react";

import { useV1AuthPinStatusRetrieve, type PinStatus } from "../api/generated/banxumApi";
import { isFixturePreview } from "./data";
import { MAX_PIN_ATTEMPTS, PIN_LENGTH, pinApiError, pinWeakness } from "./pinRules";

const PREVIEW_LOCK_MS = 30 * 60 * 1000;

const previewStatus: PinStatus = {
  pin_set: true,
  locked_until: null,
  attempts_left: MAX_PIN_ATTEMPTS,
  max_attempts: MAX_PIN_ATTEMPTS,
  setup_requires_email_code: true,
  reset_available: true,
  phone_last_digits: "00"
};

export function usePinStatus(enabled = true) {
  const query = useV1AuthPinStatusRetrieve({
    query: { enabled: enabled && !isFixturePreview, retry: false, staleTime: 0 }
  });
  return { status: isFixturePreview ? previewStatus : query.data?.pin, isLoading: !isFixturePreview && query.isPending, query };
}

export type SensitivePin = {
  value: string;
  setValue: (value: string) => void;
  /** Six digits entered and the PIN is not locked. */
  ready: boolean;
  error: string;
  lockedUntil: string | null;
  createOpen: boolean;
  forgotOpen: boolean;
  openForgot: () => void;
  closeDialogs: () => void;
  /** Clears a lock after a forgotten-PIN reset and fills in the new PIN. */
  afterReset: (pin: string) => void;
  afterCreate: (pin: string) => void;
  /** True when the error was a PIN error; the PIN field shows it. */
  handleError: (error: unknown) => boolean;
  /** Counts wrong PINs, so the field can move the focus back to its first box. */
  wrongCount: number;
  /** Preview mode: a weak PIN counts as wrong, like the server would answer. */
  previewAccepts: () => boolean;
};

export function useSensitivePin(): SensitivePin {
  const [value, setValueState] = useState("");
  const [error, setError] = useState("");
  const [lockedUntil, setLockedUntil] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(false);
  const [previewFailures, setPreviewFailures] = useState(0);
  const [wrongCount, setWrongCount] = useState(0);
  const lockActive = lockedUntil !== null && (lockedUntil === "" || new Date(lockedUntil).getTime() > Date.now());

  const setValue = useCallback((next: string) => {
    setValueState(next);
    setError("");
  }, []);

  const handleError = useCallback((failure: unknown) => {
    const pinError = pinApiError(failure);
    if (!pinError) return false;
    if (pinError.code === "pin_invalid") {
      setValueState("");
      setError(pinError.detail);
      setWrongCount((count) => count + 1);
      return true;
    }
    if (pinError.code === "pin_locked") {
      setValueState("");
      setError("");
      setLockedUntil(pinError.lockedUntil ?? "");
      return true;
    }
    if (pinError.code === "pin_required") {
      setError("");
      setCreateOpen(true);
      return true;
    }
    return false;
  }, []);

  const previewAccepts = useCallback(() => {
    if (!isFixturePreview) return true;
    if (lockActive) return false;
    if (!pinWeakness(value)) {
      setPreviewFailures(0);
      return true;
    }
    const failures = previewFailures + 1;
    setPreviewFailures(failures >= MAX_PIN_ATTEMPTS ? 0 : failures);
    setValueState("");
    if (failures >= MAX_PIN_ATTEMPTS) {
      setLockedUntil(new Date(Date.now() + PREVIEW_LOCK_MS).toISOString());
      setError("");
      return false;
    }
    const left = MAX_PIN_ATTEMPTS - failures;
    setError(`Wrong PIN. ${left === 1 ? "1 attempt" : `${left} attempts`} left before your PIN is locked.`);
    setWrongCount((count) => count + 1);
    return false;
  }, [lockActive, previewFailures, value]);

  return {
    value,
    setValue,
    ready: value.length === PIN_LENGTH && !lockActive,
    error,
    lockedUntil: lockActive ? lockedUntil : null,
    createOpen,
    forgotOpen,
    openForgot: () => setForgotOpen(true),
    closeDialogs: () => {
      setCreateOpen(false);
      setForgotOpen(false);
    },
    afterReset: (pin: string) => {
      setForgotOpen(false);
      setLockedUntil(null);
      setPreviewFailures(0);
      setError("");
      setValueState(pin);
    },
    afterCreate: (pin: string) => {
      setCreateOpen(false);
      setError("");
      setValueState(pin);
    },
    handleError,
    previewAccepts,
    wrongCount
  };
}
