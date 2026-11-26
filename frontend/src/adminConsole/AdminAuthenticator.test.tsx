// IP of Webby-Soft SRL.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import { renderLiveApp } from "../test/liveHarness";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");
let App: ComponentType;
beforeAll(async () => { App = (await import("../App")).App; });

test("admin setup distinguishes the email code from the app code and restarts a spent setup", async () => {
  const codes = ["email_code_invalid", "authenticator_code_invalid", "enrollment_email_exhausted"];
  server.use(
    http.get("*/api/v1/auth/me/", () => HttpResponse.json({ detail: "Sign in." }, { status: 403 })),
    http.post("*/api/v1/auth/admin/login/start/", () => HttpResponse.json({
      status: "enrollment_required", code_id: "c1", enrollment_id: "e1",
      secret: "", otpauth_uri: "", expires_at: null
    }, { status: 202 })),
    http.post("*/api/v1/auth/admin/login/enroll/", () =>
      HttpResponse.json({ code: codes.shift(), detail: "Setup code not accepted." }, { status: 400 }))
  );
  renderLiveApp(App, "/admin");
  fireEvent.change(await screen.findByLabelText("Admin email", {}, { timeout: 5000 }), { target: { value: "admin@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "test-only password" } });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  const email = await screen.findByLabelText(/^Email code/, {}, { timeout: 5000 });
  const app = screen.getByLabelText(/^Code from the app/);
  const submit = screen.getByRole("button", { name: "Activate and open admin console" });
  const type = (input: HTMLElement, value: string) => fireEvent.change(input, { target: { value } });
  expect(email).toHaveAttribute("autocomplete", "one-time-code");
  expect(app).not.toHaveAttribute("autocomplete", "one-time-code");
  type(email, "123456");
  type(app, "045678");
  fireEvent.click(submit);
  await waitFor(() => expect(email).toHaveFocus());
  expect(email).toHaveValue("");
  expect(app).toHaveValue("");
  type(email, "234567");
  type(app, "045678");
  fireEvent.click(submit);
  await waitFor(() => expect(app).toHaveFocus());
  expect(email).toHaveValue("234567");
  expect(app).toHaveValue("");
  type(app, "045679");
  fireEvent.click(submit);
  const restart = await screen.findByRole("button", { name: "Restart setup" });
  expect(screen.queryByText("Or enter this key")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Activate and open admin console" })).not.toBeInTheDocument();
  fireEvent.click(restart);
  expect(screen.getByLabelText("Password")).toHaveValue("");
  expect(screen.queryByText("Setup code not accepted.")).not.toBeInTheDocument();
});
