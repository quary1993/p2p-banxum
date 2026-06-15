const csrfSafeMethods = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

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

export const httpClient = async <T>({
  url,
  method,
  data,
  params,
  headers,
  signal
}: {
  url: string;
  method: string;
  data?: unknown;
  params?: Record<string, unknown>;
  headers?: HeadersInit;
  signal?: AbortSignal;
}): Promise<T> => {
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

  const response = await fetch(requestUrl, {
    method,
    headers: requestHeaders,
    body: data === undefined ? undefined : JSON.stringify(data),
    credentials: "same-origin",
    signal
  });

  if (!response.ok) {
    const { payload, text } = await readErrorPayload(response);
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
};
