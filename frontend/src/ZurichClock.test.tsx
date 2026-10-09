// Browser clock and time zone (audit 2026-10-09, A-66). These run with the browser in a time zone
// far from Zurich: business dates, months and due times must follow Europe/Zurich and the platform
// clock, not the browser.
import { act, fireEvent, screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterAll, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  daysBetweenDateKeys,
  isZurichWeekendAt,
  monthLabelFromKey,
  zurichDateKey,
  zurichDateTimeInputToIso,
  zurichDateTimeInputValue,
  zurichMonthKey
} from "./investorPortal/format";
import { platformTodayKey, platformTodayLocalDate, rememberPlatformBusinessDate } from "./investorPortal/platformClock";
import { renderLiveApp } from "./test/liveHarness";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
const originalTimeZone = process.env.TZ;
beforeAll(async () => {
  App = (await import("./App")).App;
});
afterAll(() => {
  process.env.TZ = originalTimeZone;
});

describe.each(["America/New_York", "Pacific/Auckland"])("browser in %s", (timeZone) => {
  beforeEach(() => {
    process.env.TZ = timeZone;
  });

  test("an admin due time keeps its Zurich wall time through repeated saves", () => {
    let stored = "2026-10-09T14:00:00+02:00";
    for (let save = 0; save < 3; save += 1) {
      const shown = zurichDateTimeInputValue(stored);
      expect(shown).toBe("2026-10-09T14:00");
      stored = zurichDateTimeInputToIso(shown);
    }
    expect(stored).toBe("2026-10-09T12:00:00.000Z");
    // Winter time (UTC+1).
    expect(zurichDateTimeInputToIso("2026-12-01T09:15")).toBe("2026-12-01T08:15:00.000Z");
  });

  test("months, days and weekends follow the Zurich calendar", () => {
    // 31 Oct 23:30 UTC is already 1 November in Zurich.
    expect(zurichDateKey("2026-10-31T23:30:00Z")).toBe("2026-11-01");
    expect(zurichMonthKey("2026-10-31T23:30:00Z")).toBe("2026-11");
    expect(zurichMonthKey("2026-10-31T23:30:00Z", 1)).toBe("2026-12");
    expect(monthLabelFromKey("2026-12")).toBe("December");
    expect(daysBetweenDateKeys("2026-10-09", "2026-10-23")).toBe(14);
    // Friday 23:30 UTC is Saturday in Zurich; Sunday 22:30 UTC is Sunday 23:30 in Zurich.
    expect(isZurichWeekendAt("2026-10-09T22:30:00Z")).toBe(true);
    expect(isZurichWeekendAt("2026-10-09T21:30:00Z")).toBe(false);
    expect(isZurichWeekendAt("2026-10-11T22:30:00Z")).toBe(false);
  });

  test("screens without their own as_of use the remembered platform date", () => {
    rememberPlatformBusinessDate("2026-11-30");
    expect(platformTodayKey()).toBe("2026-11-30");
    const today = platformTodayLocalDate();
    expect([today.getFullYear(), today.getMonth() + 1, today.getDate()]).toEqual([2026, 11, 30]);
    // An explicit platform as_of wins, on the Zurich calendar.
    expect(platformTodayKey("2026-12-09T23:30:00Z")).toBe("2026-12-10");
  });
});

const adminUser = {
  id: "a1",
  email: "admin@example.com",
  full_name: "Ada Admin",
  investor_reference: null,
  account_type: "admin",
  status: "active",
  phone_verified: true,
  marketing_consent: false
};

test("admin forms opened right after login use the platform business date, not the browser date", async () => {
  process.env.TZ = "America/New_York";
  let signedIn = false;
  server.use(
    http.get("*/api/v1/auth/me/", async () => {
      if (!signedIn) return HttpResponse.json({ detail: "Authentication credentials were not provided." }, { status: 403 });
      await delay(300);
      return HttpResponse.json({ user: adminUser, qa_controls_available: true, platform_business_date: "2026-09-09" });
    }),
    http.post("*/api/v1/auth/admin/login/start/", () =>
      HttpResponse.json({ code_id: "55555555-5555-4555-8555-555555555555", expires_at: "2026-09-09T11:57:00Z" })
    ),
    http.post("*/api/v1/auth/admin/login/confirm/", () => {
      signedIn = true;
      return HttpResponse.json({ user: adminUser });
    })
  );
  renderLiveApp(App, "/admin/finance");

  fireEvent.change(await screen.findByLabelText("Admin email", {}, { timeout: 5000 }), { target: { value: "admin@example.com" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Send email code" }));
  fireEvent.change(await screen.findByPlaceholderText("000000"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Open admin console" }));
  // Right after login the session (with the platform date) is still loading: no form yet.
  expect(await screen.findByText("Loading the platform date")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Lender deposit" })).not.toBeInTheDocument();
  const heading = await screen.findByRole("heading", { name: "Lender deposit" }, { timeout: 5000 });
  const form = within(heading.closest("form") ?? (heading.parentElement as HTMLElement));
  expect((form.getByLabelText("Booking date") as HTMLInputElement).value).toBe("2026-09-09");
  expect((form.getByLabelText("Value date") as HTMLInputElement).value).toBe("2026-09-09");
}, 20_000);

test("saving a task's status does not resend (and so cannot move) its due time", async () => {
  process.env.TZ = "America/New_York";
  const patches: Array<Record<string, unknown>> = [];
  const task = {
    id: "77777777-7777-4777-8777-777777777777",
    task_type: "manual_review",
    title: "Check the payout IBAN",
    priority: "normal",
    status: "open",
    assigned_admin_id: null,
    created_by_id: "a1",
    due_at: "2026-10-09T14:00:00+02:00",
    notes: "",
    related_object_type: "",
    related_object_id: "",
    completed_at: null,
    completion_note: "",
    is_terminal: false,
    created_at: "2026-10-01T10:00:00Z",
    updated_at: "2026-10-01T10:00:00Z"
  };
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({ user: adminUser, qa_controls_available: false, platform_business_date: "2026-10-09" })
    ),
    http.get("*/api/v1/admin-ops/tasks/", () => HttpResponse.json([task])),
    http.get(`*/api/v1/admin-ops/tasks/${task.id}/events/`, () => HttpResponse.json([])),
    http.patch(`*/api/v1/admin-ops/tasks/${task.id}/`, async ({ request }) => {
      patches.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ ...task, status: "in_progress" });
    })
  );
  renderLiveApp(App, `/admin/tasks/${task.id}`);

  const drawer = await screen.findByRole("dialog", { name: task.title }, { timeout: 5000 });
  // Shown as the Zurich wall time although the browser is in New York.
  expect((within(drawer).getByLabelText("Due at") as HTMLInputElement).value).toBe("2026-10-09T14:00");
  fireEvent.change(within(drawer).getByLabelText("Status"), { target: { value: "in_progress" } });
  await act(async () => {
    fireEvent.click(within(drawer).getByRole("button", { name: /^Save/ }));
    await new Promise((resolve) => setTimeout(resolve, 200));
  });
  expect(patches).toHaveLength(1);
  expect(patches[0]).not.toHaveProperty("due_at");
  expect(patches[0].status).toBe("in_progress");

  // Changing the due time sends the Zurich wall time as an exact instant.
  fireEvent.change(within(drawer).getByLabelText("Due at"), { target: { value: "2026-10-12T09:30" } });
  await act(async () => {
    fireEvent.click(within(drawer).getByRole("button", { name: /^Save/ }));
    await new Promise((resolve) => setTimeout(resolve, 200));
  });
  expect(patches[1].due_at).toBe("2026-10-12T07:30:00.000Z");
}, 20_000);
