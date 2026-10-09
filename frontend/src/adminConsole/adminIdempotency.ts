import { intentIdempotencyKey } from "../api/client/idempotency";

/**
 * Adds the idempotency key of one admin action (audit A-41): a retry after a timeout
 * or a double click carries the same key, so the server does the action once. The key
 * is released when the server accepts it (see httpClient); the same values later are
 * a new, deliberate action. `target` holds the path ids (withdrawal, loan, listing,
 * order), so the same body for another target gets another key.
 */
export function withIdempotencyKey<T extends object>(
  prefix: string,
  request: T,
  target: Record<string, unknown> = {}
): T & { idempotency_key: string } {
  return { ...request, idempotency_key: intentIdempotencyKey(`admin-${prefix}`, { target, request }) };
}
