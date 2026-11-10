// IP of Webby-Soft SRL.
// Real-API signed-in devices and sign-in history (U33-DEC-25): the list comes from the server, "Sign out"
// ends that session there, and the history shows the device, the place, the method and the result.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("revokes", "revokeOthers");
});

const sessions = [
  { id: "11111111-1111-4111-8111-111111111111", device_label: "Chrome on macOS", device_kind: "desktop", country_code: "CH", method: "email_link", started_at: "2026-11-10T08:00:00Z", last_activity_at: "2026-11-10T09:00:00Z", current: true },
  { id: "22222222-2222-4222-8222-222222222222", device_label: "Safari on iPhone", device_kind: "mobile", country_code: "", method: "email_link", started_at: "2026-11-09T18:00:00Z", last_activity_at: "2026-11-09T19:00:00Z", current: false }
];

test("U33-DEC-25: the investor sees the signed-in devices and signs one out on the server", async () => {
  let current = sessions;
  server.use(
    ...investorShellHandlers(calls),
    http.get("*/api/v1/auth/pin/status/", () => HttpResponse.json({ pin_set: true, locked_until: null, phone_last_digits: "12" })),
    http.get("*/api/v1/auth/sessions/", () => HttpResponse.json({ sessions: current })),
    http.get("*/api/v1/auth/sign-in-history/", () =>
      HttpResponse.json({
        retention_days: 365,
        events: [
          { id: "e1", occurred_at: "2026-11-10T08:00:00Z", device_label: "Chrome on macOS", device_kind: "desktop", country_code: "CH", method: "email_link", result: "signed_in" },
          { id: "e2", occurred_at: "2026-11-08T08:00:00Z", device_label: "Firefox on Windows", device_kind: "desktop", country_code: "", method: "email_link", result: "blocked" }
        ]
      })
    ),
    http.post("*/api/v1/auth/sessions/:sessionId/revoke/", ({ params }) => {
      calls.revokes.push({ id: String(params.sessionId) });
      current = sessions.filter((session) => session.id !== params.sessionId);
      return new HttpResponse(null, { status: 204 });
    })
  );
  renderLiveApp(App, "/settings/security");
  const signOut = await screen.findByRole("button", { name: "Sign out" }, { timeout: 5000 });
  expect(screen.getByText("This device")).toBeInTheDocument();
  expect(screen.getByText(/^Place not known · Last active /)).toBeInTheDocument();
  const table = screen.getByRole("table");
  expect(within(table).getByText("Account blocked")).toBeInTheDocument();
  expect(within(table).getAllByText("Switzerland").length).toBeGreaterThan(0);
  expect(screen.getByText("Sign-ins are kept for 365 days.")).toBeInTheDocument();

  fireEvent.click(signOut);
  await waitFor(() => expect(calls.revokes).toEqual([{ id: "22222222-2222-4222-8222-222222222222" }]));
  expect(await screen.findByText("Safari on iPhone is signed out.")).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument());
}, 30_000);
