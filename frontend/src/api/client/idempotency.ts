// Idempotency keys per intent (QA audit 2026-10-09, A-41).
//
// A money action keeps one idempotency key for as long as the user retries the
// same intent (same amount, destination, quote, ...). When a request times out
// after the server committed it, the retry carries the same key, so the server
// returns the original result instead of doing the action twice. A new key is
// made only when the intent changes, or after the server accepted the request
// (then the same values again are a new, deliberate action).

const keysByIntent = new Map<string, string>();

function randomPart() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
}

/** A new key for one attempt. Prefer `intentIdempotencyKey` for money actions. */
export function newIdempotencyKey(prefix: string) {
  return `${prefix}:${randomPart()}`;
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0));
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

/**
 * The key for this intent: the same key for every retry of the same values, until
 * the server accepts a request with it. `intent` must not contain values that
 * change on a retry (the email code, for example).
 */
export function intentIdempotencyKey(prefix: string, intent: unknown) {
  const fingerprint = `${prefix}|${stableJson(intent)}`;
  const existing = keysByIntent.get(fingerprint);
  if (existing) return existing;
  const key = newIdempotencyKey(prefix);
  keysByIntent.set(fingerprint, key);
  return key;
}

/** Forget a key after the server accepted it (called by the HTTP client). */
export function releaseIdempotencyKey(key: string) {
  for (const [fingerprint, value] of keysByIntent) {
    if (value === key) keysByIntent.delete(fingerprint);
  }
}

/** The idempotency key of a JSON request body, if it has one. */
export function idempotencyKeyFromBody(body: unknown): string | undefined {
  if (typeof body !== "string" || !body.includes("idempotency_key")) return undefined;
  try {
    const parsed = JSON.parse(body) as { idempotency_key?: unknown };
    return typeof parsed?.idempotency_key === "string" ? parsed.idempotency_key : undefined;
  } catch {
    return undefined;
  }
}
