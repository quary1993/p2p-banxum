export const READONLY_IMPERSONATION_TOKEN_STORAGE_KEY = "banxum:readonly-impersonation-token:v1";
export const READONLY_IMPERSONATION_LABEL_STORAGE_KEY = "banxum:readonly-impersonation-label:v1";

export function readReadonlyImpersonationToken() {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY) ?? "";
}

export function writeReadonlyImpersonation(token: string, label: string) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY, token);
  window.sessionStorage.setItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY, label);
}

export function clearReadonlyImpersonation() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(READONLY_IMPERSONATION_TOKEN_STORAGE_KEY);
  window.sessionStorage.removeItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY);
}

export function readReadonlyImpersonationLabel() {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(READONLY_IMPERSONATION_LABEL_STORAGE_KEY) ?? "";
}
