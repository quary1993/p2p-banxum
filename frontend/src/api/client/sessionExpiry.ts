// The backend ends investor and admin sessions a fixed time after login and answers
// the next API call with 401 { code: "session_expired" }. The HTTP client reports it
// here; the investor shell and the admin console listen, return to their login
// screen, and show the notice kept in sessionStorage (it survives the redirect).

export const SESSION_EXPIRED_CODE = "session_expired";
export const SESSION_EXPIRED_NOTICE_STORAGE_KEY = "banxum:session-expired:v1";

type SessionExpiredListener = () => void;

const listeners = new Set<SessionExpiredListener>();

function noticeStorage() {
  return typeof window === "undefined" ? null : window.sessionStorage;
}

export function isSessionExpiredPayload(status: number, payload: unknown) {
  return (
    status === 401 &&
    Boolean(payload) &&
    typeof payload === "object" &&
    (payload as Record<string, unknown>).code === SESSION_EXPIRED_CODE
  );
}

export function reportSessionExpired() {
  try {
    noticeStorage()?.setItem(SESSION_EXPIRED_NOTICE_STORAGE_KEY, "1");
  } catch {
    // Storage can be unavailable (private mode); the redirect still happens.
  }
  listeners.forEach((listener) => listener());
}

export function onSessionExpired(listener: SessionExpiredListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function hasSessionExpiredNotice() {
  try {
    return noticeStorage()?.getItem(SESSION_EXPIRED_NOTICE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function clearSessionExpiredNotice() {
  try {
    noticeStorage()?.removeItem(SESSION_EXPIRED_NOTICE_STORAGE_KEY);
  } catch {
    // Nothing to clear.
  }
}
