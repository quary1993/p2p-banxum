//IP of Webby-Soft SRL.
// build-origin: ATEW5bUMtfGj80bXzkGFbtEIwTx0cb6Qig3qkx90kV_Srfdc012ga6e8Ddq5v4qj1nbItbZAfx4ZDA==
import { idempotencyKeyFromBody, releaseIdempotencyKey } from "./idempotency";
import { readReadonlyImpersonationToken } from "./impersonation";
import { isSessionExpiredPayload, reportSessionExpired } from "./sessionExpiry";

const csrfSafeMethods = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

/** Shown when no answer came back (offline, timeout, dropped connection). */
export const NETWORK_ERROR_MESSAGE =
  "No answer from the server. Check your internet connection and try again.";
/** Status of an ApiClientError when the request got no HTTP answer. */
export const NETWORK_ERROR_STATUS = 0;

function isAbortError(error: unknown) {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as { name?: unknown }).name === "AbortError"
  );
}

export class ApiClientError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

function readCookie(name: string) {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

function stringifyApiValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(stringifyApiValue).join(" ");
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).map(stringifyApiValue).join(" ");
  }
  if (value === undefined || value === null) return "";
  return String(value);
}

function apiErrorMessage(status: number, payload: unknown, fallbackText: string) {
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const detail = stringifyApiValue(record.detail).trim();
    if (detail) return detail;

    const fieldErrors = Object.entries(record)
      .map(([field, value]) => {
        const message = stringifyApiValue(value).trim();
        return message ? `${field.replaceAll("_", " ")}: ${message}` : "";
      })
      .filter(Boolean);
    if (fieldErrors.length) return fieldErrors.join(" ");
  }

  const fallback = fallbackText.trim();
  return fallback || `API request failed: ${status}`;
}

async function readErrorPayload(response: Response): Promise<{ payload: unknown; text: string }> {
  const text = await response.text();
  const contentType = response.headers.get("Content-Type") ?? "";
  if (text && contentType.toLowerCase().includes("application/json")) {
    try {
      return { payload: JSON.parse(text), text };
    } catch {
      return { payload: undefined, text };
    }
  }
  return { payload: undefined, text };
}

type LegacyHttpClientRequest = {
  url: string;
  method: string;
  data?: unknown;
  params?: Record<string, unknown>;
  headers?: HeadersInit;
  signal?: AbortSignal;
};

export function httpClient<T>(request: LegacyHttpClientRequest): Promise<T>;
export function httpClient<T>(url: string, options?: RequestInit): Promise<T>;
export async function httpClient<T>(requestOrUrl: LegacyHttpClientRequest | string, options?: RequestInit): Promise<T> {
  const legacyRequest = typeof requestOrUrl === "string" ? undefined : requestOrUrl;
  const url = typeof requestOrUrl === "string" ? requestOrUrl : requestOrUrl.url;
  const method = legacyRequest?.method ?? options?.method ?? "GET";
  const data = legacyRequest?.data;
  const params = legacyRequest?.params;
  const headers = legacyRequest?.headers ?? options?.headers;
  const signal = legacyRequest?.signal ?? options?.signal ?? undefined;
  const body = legacyRequest ? (data === undefined ? undefined : JSON.stringify(data)) : options?.body;

  const apiBaseUrl = typeof window === "undefined" ? "http://localhost:8000" : window.location.origin;
  const requestUrl = new URL(url, apiBaseUrl);

  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      requestUrl.searchParams.set(key, String(value));
    }
  });

  const requestHeaders = new Headers(headers);
  if (data !== undefined && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (!csrfSafeMethods.has(method.toUpperCase()) && !requestHeaders.has("X-CSRFToken")) {
    const csrfToken = readCookie("csrftoken");
    if (csrfToken) {
      requestHeaders.set("X-CSRFToken", decodeURIComponent(csrfToken));
    }
  }

  const readonlyImpersonationToken =
    typeof window !== "undefined" && window.location.pathname.startsWith("/admin")
      ? ""
      : readReadonlyImpersonationToken();
  if (readonlyImpersonationToken && !requestHeaders.has("X-BANXUM-Impersonate")) {
    requestHeaders.set("X-BANXUM-Impersonate", readonlyImpersonationToken);
  }

  let response: Response;
  try {
    response = await fetch(requestUrl, {
      ...options,
      method,
      headers: requestHeaders,
      body,
      credentials: "same-origin",
      signal
    });
  } catch (fetchError) {
    if (isAbortError(fetchError)) throw fetchError;
    // "Failed to fetch" and similar browser texts mean nothing to users. The request
    // may still have reached the server: a retry with the same idempotency key is safe.
    throw new ApiClientError(NETWORK_ERROR_STATUS, NETWORK_ERROR_MESSAGE, null);
  }

  if (response.ok && !csrfSafeMethods.has(method.toUpperCase())) {
    // The server accepted this intent; the same values again are a new action.
    const acceptedKey = idempotencyKeyFromBody(body);
    if (acceptedKey) releaseIdempotencyKey(acceptedKey);
  }

  if (!response.ok) {
    const { payload, text } = await readErrorPayload(response);
    if (isSessionExpiredPayload(response.status, payload)) {
      reportSessionExpired();
    }
    throw new ApiClientError(response.status, apiErrorMessage(response.status, payload, text), payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const responseText = await response.text();
  if (!responseText) {
    return undefined as T;
  }
  const responseContentType = response.headers.get("Content-Type") ?? "";
  if (responseContentType.toLowerCase().includes("application/json")) {
    return JSON.parse(responseText) as T;
  }
  return responseText as T;
}
