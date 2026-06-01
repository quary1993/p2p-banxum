export const httpClient = async <T>({
  url,
  method,
  data,
  params,
  signal
}: {
  url: string;
  method: string;
  data?: unknown;
  params?: Record<string, unknown>;
  signal?: AbortSignal;
}): Promise<T> => {
  const apiBaseUrl = typeof window === "undefined" ? "http://localhost:8000" : window.location.origin;
  const requestUrl = new URL(url, apiBaseUrl);

  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      requestUrl.searchParams.set(key, String(value));
    }
  });

  const response = await fetch(requestUrl, {
    method,
    headers: {
      "Content-Type": "application/json"
    },
    body: data === undefined ? undefined : JSON.stringify(data),
    signal
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
};
