// Real-API session checks (audit 2026-10-09, A-58/A-59, FRONTCODE-25/26, A-62):
// sign out fails closed, a failed minute re-check does not sign the investor out, "/" shows the
// public home page to a visitor whose session ended, Forward into /admin switches screens, and
// unknown addresses get a real "page not found" page.
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1AuthMeRetrieveQueryKey } from "./api/generated/banxumApi";
import { meResponse, renderLiveApp, shellHandlers } from "./test/liveHarness";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

const signedOut = () => HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 });

test("a failed sign-out keeps the investor signed in and offers Retry", async () => {
  let logoutCalls = 0;
  let sessionValid = true;
  server.use(
    ...shellHandlers({ me: () => (sessionValid ? HttpResponse.json(meResponse()) : signedOut()) }),
    http.post("*/api/v1/auth/logout/", () => {
      logoutCalls += 1;
      if (logoutCalls === 1) return HttpResponse.json({ detail: "CSRF Failed: CSRF token missing." }, { status: 403 });
      sessionValid = false;
      return new HttpResponse(null, { status: 204 });
    })
  );
  renderLiveApp(App, "/dashboard");

  fireEvent.click(await screen.findByRole("button", { name: "Sign out" }, { timeout: 5000 }));
  expect(await screen.findByText("Sign out failed", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByText("We could not sign you out. You are still signed in. Try again.")).toBeInTheDocument();
  // Still in the portal, at the same address; the public home page is not shown.
  expect(window.location.pathname).toBe("/dashboard");
  expect(screen.getByRole("navigation", { name: "Investor portal navigation" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Retry sign out" }));
  await waitFor(() => expect(window.location.pathname).toBe("/"), { timeout: 5000 });
  expect(screen.queryByRole("navigation", { name: "Investor portal navigation" })).not.toBeInTheDocument();
  expect(logoutCalls).toBe(2);
}, 30_000);

test("a 502 on the minute session re-check keeps the investor on the page", async () => {
  let meStatus = 200;
  server.use(
    ...shellHandlers({
      me: () => (meStatus === 200 ? HttpResponse.json(meResponse()) : meStatus === 403 ? signedOut() : HttpResponse.json({ detail: "Bad gateway" }, { status: meStatus }))
    })
  );
  const queryClient = renderLiveApp(App, "/dashboard");
  expect(await screen.findByRole("heading", { name: "Money working for you" }, { timeout: 5000 })).toBeInTheDocument();

  meStatus = 502;
  await act(async () => {
    await queryClient.refetchQueries({ queryKey: getV1AuthMeRetrieveQueryKey() });
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 200));
  });
  expect(screen.getByRole("heading", { name: "Money working for you" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Send magic link" })).not.toBeInTheDocument();

  // A real "signed out" answer still leads to the login form.
  meStatus = 403;
  await act(async () => {
    await queryClient.refetchQueries({ queryKey: getV1AuthMeRetrieveQueryKey() });
  });
  expect(await screen.findByRole("button", { name: "Send magic link" }, { timeout: 5000 })).toBeInTheDocument();
}, 30_000);

test("a returning visitor whose session ended sees the public home page at /", async () => {
  window.localStorage.setItem("banxum:app-route:v1", JSON.stringify({ name: "dashboard" }));
  server.use(http.get("*/api/v1/auth/me/", signedOut));
  renderLiveApp(App, "/");

  expect(await screen.findByRole("heading", { level: 1, name: /Your capital/ }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Send magic link" })).not.toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
}, 15_000);

test("browser Forward into /admin switches to the admin console", async () => {
  server.use(http.get("*/api/v1/auth/me/", signedOut));
  renderLiveApp(App, "/faq");
  await screen.findAllByRole("link", { name: "Help" }, { timeout: 5000 });

  act(() => {
    window.history.pushState({}, "", "/admin/tasks");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  expect(await screen.findByLabelText("Admin email", {}, { timeout: 5000 })).toBeInTheDocument();
});

test("an unknown address shows a page-not-found page and keeps the address", async () => {
  server.use(http.get("*/api/v1/auth/me/", signedOut));
  renderLiveApp(App, "/this-page-does-not-exist");

  expect(await screen.findByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/this-page-does-not-exist");
  fireEvent.click(screen.getByRole("button", { name: "Home page" }));
  await waitFor(() => expect(window.location.pathname).toBe("/"));
  expect(screen.queryByRole("heading", { name: "Page not found" })).not.toBeInTheDocument();
});

test("form labels are linked to their inputs on the investor and admin login screens", async () => {
  server.use(http.get("*/api/v1/auth/me/", signedOut));
  renderLiveApp(App, "/login");
  expect(await screen.findByLabelText("Email address", {}, { timeout: 5000 })).toHaveAttribute("type", "email");

  act(() => {
    window.history.pushState({}, "", "/admin");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  expect(await screen.findByLabelText("Admin email", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
});
