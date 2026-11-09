// IP of Webby-Soft SRL.
// The email code + PIN of one resale action (same behaviour as App.tsx useSensitiveActionCode).
import { useCallback, useEffect, useState } from "react";

import { useV1AuthSensitiveActionCodeRequestCreate, type ActionEnum } from "../../../../api/generated/banxumApi";
import { ApiClientError } from "../../../../api/client/httpClient";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useSensitivePin } from "../../../../investorPortal/pinState";
import { errorMessage } from "./errors";

const RESEND_COOLDOWN_MS = 60_000;

function useSecondsUntil(untilMs: number) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    setNowMs(Date.now());
    if (untilMs <= Date.now()) return undefined;
    const timer = window.setInterval(() => {
      const now = Date.now();
      setNowMs(now);
      if (untilMs <= now) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [untilMs]);
  return Math.max(0, Math.ceil((untilMs - nowMs) / 1000));
}

/** Seconds to wait before a new code, from a 429 answer (same reading as App.tsx). */
function retryAfterSeconds(error: unknown) {
  if (!(error instanceof ApiClientError) || !error.payload || typeof error.payload !== "object") return null;
  const payload = error.payload as Record<string, unknown>;
  if (typeof payload.retry_after_seconds === "number") return payload.retry_after_seconds;
  if (typeof payload.wait === "number") return payload.wait;
  const detail = typeof payload.detail === "string" ? payload.detail : "";
  const match = detail.match(/(\d+)\s+seconds?/i);
  return match ? Number.parseInt(match[1], 10) : null;
}

/** The email code of one sensitive action plus its PIN (same behaviour as App.tsx useSensitiveActionCode). */
export function useActionConfirmation(action: ActionEnum) {
  const requestMutation = useV1AuthSensitiveActionCodeRequestCreate();
  const [codeId, setCodeId] = useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [error, setError] = useState("");
  const cooldownSeconds = useSecondsUntil(cooldownUntil);
  const pin = useSensitivePin();
  const requestCode = useCallback(() => {
    setError("");
    if (isFixturePreview) {
      setCodeId("00000000-0000-0000-0000-000000000000");
      setCooldownUntil(Date.now() + RESEND_COOLDOWN_MS);
      return;
    }
    requestMutation.mutate(
      { data: { action } },
      {
        onSuccess: (response) => {
          setCodeId(response.code_id);
          setCooldownUntil(Date.now() + RESEND_COOLDOWN_MS);
        },
        onError: (mutationError) => {
          const wait = retryAfterSeconds(mutationError);
          if (wait) setCooldownUntil(Date.now() + wait * 1000);
          setError(errorMessage(mutationError));
        }
      }
    );
  }, [action, requestMutation]);
  return { codeId, error, isRequesting: requestMutation.isPending, cooldownSeconds, requestCode, pin };
}

export type ActionConfirmation = ReturnType<typeof useActionConfirmation>;

/** Code and PIN complete, and a code was requested (preview: always). */
export function confirmationReady(confirmation: ActionConfirmation, code: string) {
  return code.length === 6 && confirmation.pin.ready && (isFixturePreview || Boolean(confirmation.codeId));
}
