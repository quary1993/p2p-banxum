export const READONLY_IMPERSONATION_TOKEN_STORAGE_KEY = "banxum:readonly-impersonation-token:v1";
export const READONLY_IMPERSONATION_LABEL_STORAGE_KEY = "banxum:readonly-impersonation-label:v1";
export const READONLY_IMPERSONATION_EXPIRES_STORAGE_KEY = "banxum:readonly-impersonation-expires:v1";

function storage() {
  return typeof window === "undefined" ? null : window.localStorage;
}

function fallbackSessionStorage() {
  return typeof window === "undefined" ? null : window.sessionStorage;
}

function clearStoredReadonlyImpersonation() {
  const local = storage();
  const session = fallbackSessionStorage();
  local?.removeItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY);
  local?.removeItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY);
  local?.removeItem(READONLY_IMPERSONATION_EXPIRES_STORAGE_KEY);
  session?.removeItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY);
  session?.removeItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY);
}

export function readReadonlyImpersonationToken() {
  const local = storage();
  if (!local) return "";
  const expiresAt = Number.parseInt(
    local.getItem(READONLY_IMPERSONATION_EXPIRES_STORAGE_KEY) ?? "0",
    10
  );
  if (expiresAt && expiresAt <= Date.now()) {
    clearStoredReadonlyImpersonation();
    return "";
  }
  return (
    local.getItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY) ??
    fallbackSessionStorage()?.getItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY) ??
    ""
  );
}

export function writeReadonlyImpersonation(token: string, label: string, expiresInSeconds = 30 * 60) {
  const local = storage();
  if (!local) return;
  local.setItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY, token);
  local.setItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY, label);
  local.setItem(
    READONLY_IMPERSONATION_EXPIRES_STORAGE_KEY,
    String(Date.now() + Math.max(1, expiresInSeconds) * 1000)
  );
}

export function clearReadonlyImpersonation() {
  clearStoredReadonlyImpersonation();
}

export function readReadonlyImpersonationLabel() {
  if (!readReadonlyImpersonationToken()) return "";
  return (
    storage()?.getItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY) ??
    fallbackSessionStorage()?.getItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY) ??
    ""
  );
}
