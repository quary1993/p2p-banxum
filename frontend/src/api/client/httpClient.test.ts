import { afterEach, describe, expect, test, vi } from "vitest";

import { ApiClientError, NETWORK_ERROR_MESSAGE, httpClient } from "./httpClient";
import { intentIdempotencyKey } from "./idempotency";
import { hasSessionExpiredNotice, onSessionExpired } from "./sessionExpiry";

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "csrftoken=; Max-Age=0";
});

function mockJsonResponse() {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastFetchInit(fetchMock: ReturnType<typeof mockJsonResponse>) {
  const [, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
  return init;
}

describe("httpClient", () => {
  test("adds Django CSRF token for unsafe same-origin requests", async () => {
    document.cookie = "csrftoken=token%20123";
    const fetchMock = mockJsonResponse();

    await httpClient({
      url: "/api/v1/example/",
      method: "POST",
      data: { amount: 100 }
    });

    const init = lastFetchInit(fetchMock);
    const headers = init?.headers as Headers;
    expect(headers.get("X-CSRFToken")).toBe("token 123");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  test("supports the generated fetch mutator signature", async () => {
    document.cookie = "csrftoken=generated-token";
    const fetchMock = mockJsonResponse();

    await httpClient("/api/v1/example/?currency=CHF", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount_minor: 100 })
    });

    const [url] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    const init = lastFetchInit(fetchMock);
    const headers = init.headers as Headers;
    expect(url.pathname).toBe("/api/v1/example/");
    expect(url.searchParams.get("currency")).toBe("CHF");
    expect(init.body).toBe('{"amount_minor":100}');
    expect(headers.get("X-CSRFToken")).toBe("generated-token");
  });

  test("does not add CSRF header to safe read requests", async () => {
    document.cookie = "csrftoken=token%20123";
    const fetchMock = mockJsonResponse();

    await httpClient({
      url: "/api/v1/example/",
      method: "GET"
    });

    const init = lastFetchInit(fetchMock);
    const headers = init?.headers as Headers;
    expect(headers.get("X-CSRFToken")).toBeNull();
    expect(headers.get("Content-Type")).toBeNull();
  });

  test("throws parsed API detail for JSON error responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Phone number is required." }), {
            headers: { "Content-Type": "application/json" },
            status: 400
          })
      )
    );

    await expect(
      httpClient({
        url: "/api/v1/auth/phone/request/",
        method: "POST"
      })
    ).rejects.toMatchObject({
      name: "ApiClientError",
      message: "Phone number is required.",
      status: 400
    } satisfies Partial<ApiClientError>);
  });

  test("returns undefined for successful empty responses", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 202 })));

    await expect(
      httpClient<void>({
        url: "/api/v1/auth/magic-link/request/",
        method: "POST",
        data: { email: "investor@example.test" }
      })
    ).resolves.toBeUndefined();
  });

  test("reports an expired session once the API answers 401 session_expired", async () => {
    const listener = vi.fn();
    const unsubscribe = onSessionExpired(listener);
    const respond = (status: number, body: Record<string, string>) =>
      vi.stubGlobal(
        "fetch",
        vi.fn(
          async () =>
            new Response(JSON.stringify(body), {
              headers: { "Content-Type": "application/json" },
              status
            })
        )
      );
    try {
      respond(403, { detail: "Authentication credentials were not provided." });
      await expect(httpClient({ url: "/api/v1/auth/me/", method: "GET" })).rejects.toMatchObject({ status: 403 });
      expect(listener).not.toHaveBeenCalled();
      expect(hasSessionExpiredNotice()).toBe(false);

      respond(401, { detail: "Your session has expired. Please log in again.", code: "session_expired" });
      await expect(httpClient({ url: "/api/v1/auth/me/", method: "GET" })).rejects.toMatchObject({
        status: 401,
        message: "Your session has expired. Please log in again."
      });
      expect(listener).toHaveBeenCalledTimes(1);
      expect(hasSessionExpiredNotice()).toBe(true);
    } finally {
      unsubscribe();
    }
  });

  test("normalizes field validation errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ phone_number: ["Enter a valid phone number."] }), {
            headers: { "Content-Type": "application/json" },
            status: 400
          })
      )
    );

    await expect(
      httpClient({
        url: "/api/v1/auth/register/",
        method: "POST"
      })
    ).rejects.toMatchObject({
      message: "phone number: Enter a valid phone number."
    });
  });

  test("a network failure gives a clear message, not the browser's 'Failed to fetch'", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));

    const failure = httpClient({ url: "/api/v1/ledger/withdrawal-requests/", method: "POST", data: {} });

    await expect(failure).rejects.toBeInstanceOf(ApiClientError);
    await expect(failure).rejects.toMatchObject({ status: 0, message: NETWORK_ERROR_MESSAGE });
  });

  test("an aborted request still rejects with the abort error", async () => {
    const abort = new DOMException("The operation was aborted.", "AbortError");
    vi.stubGlobal("fetch", vi.fn(async () => { throw abort; }));

    await expect(httpClient({ url: "/api/v1/auth/me/", method: "GET" })).rejects.toBe(abort);
  });

  test("an intent keeps its idempotency key until the server accepts it (A-41)", async () => {
    const intent = { amount_minor: 10_000, currency: "CHF", destination_iban: "CH93" };
    const first = intentIdempotencyKey("investor-withdrawal", intent);
    expect(intentIdempotencyKey("investor-withdrawal", { ...intent })).toBe(first);
    expect(intentIdempotencyKey("investor-withdrawal", { ...intent, amount_minor: 20_000 })).not.toBe(first);

    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    await expect(
      httpClient({ url: "/api/v1/ledger/withdrawal-requests/", method: "POST", data: { ...intent, idempotency_key: first } })
    ).rejects.toMatchObject({ status: 0 });
    // A timeout is not an answer: the retry must carry the same key.
    expect(intentIdempotencyKey("investor-withdrawal", intent)).toBe(first);

    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ id: "w1" }), {
      headers: { "Content-Type": "application/json" },
      status: 201
    })));
    await httpClient({ url: "/api/v1/ledger/withdrawal-requests/", method: "POST", data: { ...intent, idempotency_key: first } });
    // Accepted: the same values again are a new withdrawal with a new key.
    expect(intentIdempotencyKey("investor-withdrawal", intent)).not.toBe(first);
  });
});
