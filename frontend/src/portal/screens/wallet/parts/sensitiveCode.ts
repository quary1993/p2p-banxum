// IP of Webby-Soft SRL.
/*
 * Today's confirmation of a money action (ACC-DEC-009, until U33-DEC-01 lands in Phase 17.3): a
 * 6-digit code sent by email plus the investor's PIN. Same requests and rules as App.tsx
 * useSensitiveActionCode / useAutoRequestEmailCode (code request with a resend cooldown, the PIN
 * state of investorPortal/pinState.ts). Kept here because screens cannot import App.tsx; the main
 * session merges it with the other slices' copies.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { useV1AuthSensitiveActionCodeRequestCreate, type ActionEnum } from "../../../../api/generated/banxumApi";
import { ApiClientError } from "../../../../api/client/httpClient";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useSensitivePin } from "../../../../investorPortal/pinState";
import { errorMessage } from "./downloads";

const RESEND_COOLDOWN_MS = 60_000;

function retryAfterSeconds(error: unknown) {
  if (!(error instanceof ApiClientError) || !error.payload || typeof error.payload !== "object") return undefined;
  const payload = error.payload as Record<string, unknown>;
  if (typeof payload.retry_after_seconds === "number") return payload.retry_after_seconds;
  if (typeof payload.wait === "number") return payload.wait;
  const match = (typeof payload.detail === "string" ? payload.detail : "").match(/(\d+)\s+seconds?/i);
  return match ? Number.parseInt(match[1], 10) : undefined;
}

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

/** The email code of one sensitive action and the PIN that goes with it. */
export function useSensitiveCode(action: ActionEnum) {
  const { mutate, isPending } = useV1AuthSensitiveActionCodeRequestCreate();
  const [codeId, setCodeId] = useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [error, setError] = useState("");
  const cooldown = useSecondsLeft(cooldownUntil);
  const pin = useSensitivePin();
  const requestCode = useCallback(() => {
    setError("");
    if (isFixturePreview) {
      setCodeId("00000000-0000-0000-0000-000000000000");
      setCooldownUntil(Date.now() + RESEND_COOLDOWN_MS);
      return;
    }
    mutate(
      { data: { action } },
      {
        onSuccess: (response) => {
          setCodeId(response.code_id);
          setCooldownUntil(Date.now() + RESEND_COOLDOWN_MS);
        },
        onError: (failure) => {
          const wait = retryAfterSeconds(failure);
          if (wait) setCooldownUntil(Date.now() + wait * 1000);
          setError(errorMessage(failure));
        }
      }
    );
  }, [action, mutate]);
  return { codeId, error, isRequesting: isPending, cooldown, requestCode, pin };
}

export type SensitiveCode = ReturnType<typeof useSensitiveCode>;

/** Sends the email code once when the confirmation step opens (live mode only). */
export function useAutoRequestCode(code: Pick<SensitiveCode, "codeId" | "isRequesting" | "requestCode">, active: boolean) {
  const requested = useRef(false);
  const { codeId, isRequesting, requestCode } = code;
  useEffect(() => {
    if (!active) {
      requested.current = false;
      return;
    }
    if (isFixturePreview || requested.current || codeId || isRequesting) return;
    requested.current = true;
    requestCode();
  }, [active, codeId, isRequesting, requestCode]);
}

/** True when the code and the PIN are complete and the action may be sent. */
export function sensitiveReady(code: SensitiveCode, value: string) {
  return value.length === 6 && code.pin.ready && (isFixturePreview || Boolean(code.codeId));
}
