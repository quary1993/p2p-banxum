// Session checks for the investor shell (audit A-58/A-59).
// Only an answer that says "not signed in" ends the session view: 401 (including
// `session_expired`) or 403. A 5xx, a timeout or a network error says nothing about the
// session, so the shell keeps the cached session and checks again quietly.
import { ApiClientError } from "../api/client/httpClient";

export function isSignedOutError(error: unknown) {
  return error instanceof ApiClientError && (error.status === 401 || error.status === 403);
}

/** React Query retry rule for the session lookup: retry transient failures, never "signed out". */
export function retryTransientSessionError(failureCount: number, error: unknown) {
  return !isSignedOutError(error) && failureCount < 2;
}

export function isNotFoundError(error: unknown) {
  return error instanceof ApiClientError && (error.status === 404 || error.status === 400);
}
