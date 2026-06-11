import { afterEach, describe, expect, test, vi } from "vitest";

import { ApiClientError, httpClient } from "./httpClient";

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
});
