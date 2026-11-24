// IP of Webby-Soft SRL.
// Real-API checks of 18.5 (U33-DEC-01, Q05, D-1): password + second factor sign-in with
// "Remember this browser", the forgotten-password link page, "This was not me", and the factor gate
// of a signed-in account without a factor (after an assisted recovery). No real data or secrets.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1AuthMeRetrieveResponseMock } from "./api/generated/banxumApi";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("logins", "verifies", "resetStarts", "resetCompletes", "notMe", "enrollStarts", "enrollConfirms", "recoveryCodes");
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

const PASSWORD = "quiet-harbour-lantern-47";

function investor(overrides: Record<string, unknown> = {}) {
  return {
    id: "u1",
    email: "una@example.com",
    full_name: "Una Investor",
    investor_reference: "R1",
    account_type: "natural_person_lender",
    status: "active",
    phone_verified: true,
    marketing_consent: false,
    number_format: "european",
    language: "en",
    pin_set: true,
    pin_locked_until: null,
    second_factor: "sms",
    ...overrides
  };
}

test("sign-in: the password, then the SMS code; the browser can be remembered for 30 days", async () => {
  let signedIn = false;
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      signedIn
        ? HttpResponse.json({ ...getV1AuthMeRetrieveResponseMock(), user: investor(), qa_controls_available: false })
        : HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 })
    ),
    http.post("*/api/v1/auth/login/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.logins.push(body);
      if (body.password !== PASSWORD) {
        return HttpResponse.json({ detail: "The email address or the password is wrong.", code: "invalid_credentials" }, { status: 400 });
      }
      return HttpResponse.json({ status: "factor_required", method: "sms", challenge_id: "11111111-1111-4111-8111-111111111111", phone_last_digits: "42", user: null });
    }),
    http.post("*/api/v1/auth/login/verify/", async ({ request }) => {
      calls.verifies.push((await request.json()) as Record<string, unknown>);
      signedIn = true;
      return HttpResponse.json({ user: investor() });
    }),
    ...investorShellHandlers(calls)
  );
  renderLiveApp(App, "/login");

  fireEvent.change(await screen.findByPlaceholderText("you@example.com", {}, { timeout: 5000 }), { target: { value: "una@example.com" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong-password-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  expect(await screen.findByText(/The email address or the password is wrong/)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Password"), { target: { value: PASSWORD } });
  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  expect(await screen.findByText("Enter the 6-digit code we sent by SMS to your phone number ending in 42.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("SMS code"), { target: { value: "482913" } });
  fireEvent.click(screen.getByRole("checkbox", { name: /Remember this browser for 30 days/ }));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  await waitFor(() => expect(window.location.pathname).toBe("/dashboard"), { timeout: 5000 });
  expect(calls.logins).toEqual([
    { email: "una@example.com", password: "wrong-password-1" },
    { email: "una@example.com", password: PASSWORD }
  ]);
  expect(calls.verifies).toEqual([{ challenge_id: "11111111-1111-4111-8111-111111111111", code: "482913", trust_device: true }]);
  // The password never stays in the browser's storage.
  expect(JSON.stringify(window.localStorage)).not.toContain(PASSWORD);
}, 30_000);

test("the forgotten-password link asks for the second factor and a new password, and keeps the token out of the address bar", async () => {
  server.use(
    http.get("*/api/v1/auth/me/", () => HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 })),
    http.post("*/api/v1/auth/password/reset/start/", async ({ request }) => {
      calls.resetStarts.push({ ...((await request.json()) as Record<string, unknown>), addressBar: window.location.href });
      return HttpResponse.json({ status: "factor_required", method: "app", challenge_id: "22222222-2222-4222-8222-222222222222", phone_last_digits: "" });
    }),
    http.post("*/api/v1/auth/password/reset/complete/", async ({ request }) => {
      calls.resetCompletes.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ status: "password_reset" });
    })
  );
  renderLiveApp(App, "/reset-password#token=reset-token-123");

  expect(await screen.findByRole("heading", { name: "Set a new password" }, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.resetStarts).toHaveLength(1);
  expect(calls.resetStarts[0].token).toBe("reset-token-123");
  expect(String(calls.resetStarts[0].addressBar)).not.toContain("reset-token-123");
  fireEvent.change(screen.getByLabelText("Authenticator code"), { target: { value: "135790" } });
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: "short" } });
  fireEvent.change(screen.getByLabelText("Repeat password"), { target: { value: "short" } });
  fireEvent.click(screen.getByRole("button", { name: "Save new password" }));
  expect(screen.getByText("Use at least 12 characters.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: PASSWORD } });
  fireEvent.change(screen.getByLabelText("Repeat password"), { target: { value: PASSWORD } });
  fireEvent.click(screen.getByRole("button", { name: "Save new password" }));

  expect(await screen.findByRole("heading", { name: "Password changed" })).toBeInTheDocument();
  expect(calls.resetCompletes).toEqual([
    { token: "reset-token-123", new_password: PASSWORD, challenge_id: "22222222-2222-4222-8222-222222222222", code: "135790" }
  ]);
}, 30_000);

test('"This was not me" stops an assisted recovery', async () => {
  server.use(
    http.get("*/api/v1/auth/me/", () => HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 })),
    http.post("*/api/v1/auth/account-recovery/not-me/", async ({ request }) => {
      calls.notMe.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ status: "recovery_stopped" });
    })
  );
  renderLiveApp(App, "/account-recovery/not-me#token=dispute-token-9");

  expect(await screen.findByRole("heading", { name: "Recovery stopped" }, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.notMe).toEqual([{ token: "dispute-token-9" }]);
}, 20_000);

test("an account without a second factor sets up the app and saves its recovery codes before anything else", async () => {
  let factor = "";
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({ ...getV1AuthMeRetrieveResponseMock(), user: investor({ second_factor: factor, phone_verified: false, pin_set: false }), qa_controls_available: false })
    ),
    http.post("*/api/v1/auth/security/authenticator/start/", () => {
      calls.enrollStarts.push({});
      return HttpResponse.json({
        enrollment_id: "33333333-3333-4333-8333-333333333333",
        secret: "JBSWY3DPEHPK3PXP",
        otpauth_uri: "otpauth://totp/Banxum:una%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=Banxum"
      });
    }),
    http.post("*/api/v1/auth/security/authenticator/confirm/", async ({ request }) => {
      calls.enrollConfirms.push((await request.json()) as Record<string, unknown>);
      factor = "app";
      return HttpResponse.json({});
    }),
    http.post("*/api/v1/auth/security/recovery-codes/", async ({ request }) => {
      calls.recoveryCodes.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ codes: Array.from({ length: 10 }, (_, index) => `ABCDE-${String(index).padStart(5, "0")}`) });
    }),
    http.get("*/api/v1/auth/pin/status/", () =>
      HttpResponse.json({ pin: { pin_set: false, locked_until: null, attempts_left: 5, max_attempts: 5, setup_requires_email_code: true, reset_available: false, phone_last_digits: "", second_factor: factor } })
    ),
    ...investorShellHandlers(calls)
  );
  renderLiveApp(App, "/dashboard");

  expect(await screen.findByRole("heading", { name: "Protect your account" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Investor portal navigation" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Authenticator app/ }));
  expect(await screen.findByText("JBSW Y3DP EHPK 3PXP")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Code from the app"), { target: { value: "246801" } });
  fireEvent.click(screen.getByRole("button", { name: "Activate" }));

  expect(await screen.findByRole("heading", { name: "Save your recovery codes" })).toBeInTheDocument();
  const list = await screen.findByRole("list", { name: "Recovery codes" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(10);
  fireEvent.click(screen.getByRole("checkbox", { name: /I saved these codes/ }));
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  // D-1: an app investor creates no PIN; the portal opens.
  expect(await screen.findByRole("navigation", { name: "Investor portal navigation" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Create your security PIN" })).not.toBeInTheDocument();
  expect(calls.enrollConfirms).toEqual([{ enrollment_id: "33333333-3333-4333-8333-333333333333", code: "246801", confirmation_id: null }]);
  expect(calls.recoveryCodes).toEqual([{ confirmation_id: null }]);
}, 30_000);
