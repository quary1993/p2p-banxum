// Real-API session gate checks (audit 2026-10-09, A-03): a logged-out visit to a portal
// URL must settle on the login form. The logo link's own session lookup once reset the
// gate's check, so the page swapped between "Checking your session" and the login form
// forever and called /auth/me dozens of times a second. The verification (KYC) gate had the
// same pattern when its status lookup failed.
import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1AuthMeRetrieveResponseMock } from "./api/generated/banxumApi";

// Leave fixture preview mode so the gate talks to the (mocked) API.
vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

function renderLoggedOutAt(path: string) {
  let meCalls = 0;
  server.use(
    http.get("*/api/v1/auth/me/", () => {
      meCalls += 1;
      return HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 });
    })
  );
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
  return { meCalls: () => meCalls };
}

test("a logged-out deep link settles on the login form without polling the session", async () => {
  const session = renderLoggedOutAt("/portfolio");

  expect(await screen.findByRole("button", { name: "Send magic link" })).toBeInTheDocument();
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 600));
  });

  expect(screen.getByRole("button", { name: "Send magic link" })).toBeInTheDocument();
  expect(screen.queryByText("Checking your session")).not.toBeInTheDocument();
  expect(session.meCalls()).toBeLessThanOrEqual(2);
});

test("typed login email survives a later session re-check", async () => {
  renderLoggedOutAt("/dashboard");

  await screen.findByRole("button", { name: "Send magic link" });
  const email = screen.getByPlaceholderText("you@example.com") as HTMLInputElement;
  fireEvent.change(email, { target: { value: "investor@example.com" } });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 300));
  });

  expect((screen.getByPlaceholderText("you@example.com") as HTMLInputElement).value).toBe("investor@example.com");
});

test("a failing verification status lookup settles on the status screen with Retry", async () => {
  let kycCalls = 0;
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        ...getV1AuthMeRetrieveResponseMock(),
        user: {
          id: "u1",
          email: "investor@example.com",
          full_name: "Una Investor",
          investor_reference: "R1",
          account_type: "natural_person_lender",
          status: "pending_kyc",
          phone_verified: true,
          marketing_consent: false
        }
      })
    ),
    http.get("*/api/v1/kyc/status/", () => {
      kycCalls += 1;
      return HttpResponse.json({ detail: "Service unavailable" }, { status: 503 });
    })
  );
  window.history.pushState({}, "", "/dashboard");
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>
  );

  expect(await screen.findByText("Could not load KYC status")).toBeInTheDocument();
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 600));
  });

  expect(screen.getByText("Could not load KYC status")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  expect(kycCalls).toBeLessThanOrEqual(2);
});
