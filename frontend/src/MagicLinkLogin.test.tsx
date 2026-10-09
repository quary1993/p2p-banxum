// Real-API login-link checks (audit 2026-10-09, A-49). The login email now carries the
// token in the URL fragment (/login#token=...). The token must leave the address bar
// before the first API call, so it never reaches access logs or a Referer header, and
// older ?token= links keep working.
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

afterEach(() => {
  server.events.removeAllListeners();
  window.history.pushState({}, "", "/");
});

const signedInUser = {
  id: "u1",
  email: "investor@example.com",
  full_name: "Una Investor",
  investor_reference: "R1",
  account_type: "natural_person_lender",
  status: "pending_kyc",
  phone_verified: false,
  marketing_consent: false
};

function renderLoginLink(path: string) {
  const consumed: string[] = [];
  const addressBarAtRequest: string[] = [];
  server.events.on("request:start", () => {
    addressBarAtRequest.push(window.location.href);
  });
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 })
    ),
    http.post("*/api/v1/auth/magic-link/consume/", async ({ request }) => {
      const body = (await request.json()) as { token: string };
      consumed.push(body.token);
      return HttpResponse.json({ user: signedInUser });
    })
  );
  window.history.pushState({}, "", path);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>
  );
  return { consumed, addressBarAtRequest };
}

test("a fragment login link signs in and never shows the token to the network", async () => {
  const token = "fragment-token-123";
  const session = renderLoginLink(`/login#token=${token}`);

  await waitFor(() => expect(session.consumed).toEqual([token]));
  expect(session.addressBarAtRequest.length).toBeGreaterThan(0);
  for (const href of session.addressBarAtRequest) {
    expect(href).not.toContain(token);
  }
  expect(window.location.href).not.toContain(token);
});

test("an older ?token= link still signs in once and leaves the address bar", async () => {
  const token = "query-token-456";
  const session = renderLoginLink(`/login?token=${token}`);

  await waitFor(() => expect(session.consumed).toEqual([token]));
  for (const href of session.addressBarAtRequest) {
    expect(href).not.toContain(token);
  }
  expect(window.location.href).not.toContain(token);
});

test("the page tells the browser not to send referrers", async () => {
  const html = await import("../index.html?raw");
  expect(html.default).toContain('<meta name="referrer" content="no-referrer" />');
});
