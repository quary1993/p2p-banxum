// IP of Webby-Soft SRL.
// PIN rules and PIN error answers (ACC-DEC-009), shared by the PIN screens and state.
import { ApiClientError } from "../api/client/httpClient";

export const PIN_LENGTH = 6;
export const MAX_PIN_ATTEMPTS = 5;

// ---- Rules (the same as accounts_auth.pin_services.pin_weakness) ---------------------------

export function pinWeakness(pin: string): string | null {
  if (!/^\d{6}$/.test(pin)) return "Your PIN must be exactly 6 digits.";
  if (new Set(pin).size === 1) return "Choose a PIN that does not repeat one digit, like 111111.";
  const steps = new Set(Array.from(pin.slice(1)).map((digit, index) => Number(digit) - Number(pin[index])));
  if (steps.size === 1 && (steps.has(1) || steps.has(-1))) {
    return "Choose a PIN that is not a straight run of digits, like 123456 or 654321.";
  }
  return null;
}

export function isRepeatedDigit(pin: string) {
  return pin.length === PIN_LENGTH && new Set(pin).size === 1;
}

export function isStraightRun(pin: string) {
  if (pin.length !== PIN_LENGTH) return false;
  const steps = new Set(Array.from(pin.slice(1)).map((digit, index) => Number(digit) - Number(pin[index])));
  return steps.size === 1 && (steps.has(1) || steps.has(-1));
}

/** "14:35", Zurich time like every other time in the investor area. */
export function formatPinLockTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" });
}

// ---- API errors ---------------------------------------------------------------------------

export type PinApiError = {
  code: string;
  detail: string;
  attemptsLeft?: number;
  lockedUntil?: string;
};

/** The error body of a PIN check or PIN flow (``{detail, code, ...}``), or null. */
export function pinApiError(error: unknown): PinApiError | null {
  if (!(error instanceof ApiClientError) || !error.payload || typeof error.payload !== "object") return null;
  const payload = error.payload as Record<string, unknown>;
  if (typeof payload.code !== "string") return null;
  return {
    code: payload.code,
    detail: typeof payload.detail === "string" ? payload.detail : error.message,
    attemptsLeft: typeof payload.attempts_left === "number" ? payload.attempts_left : undefined,
    lockedUntil: typeof payload.locked_until === "string" ? payload.locked_until : undefined
  };
}
