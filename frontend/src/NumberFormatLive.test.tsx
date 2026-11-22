// IP of Webby-Soft SRL.
// Real-API number format (U33-DEC-32): the format saved in the account applies when the investor signs
// in, and a new choice in Preferences applies at once and is saved in the account.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { readNumberFormatPreference, resetNumberFormatForTests } from "./investorPortal/format";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("displayPreferences");
  window.localStorage.clear();
  resetNumberFormatForTests();
});

const accountUser = (numberFormat: string) => ({
  id: "u1",
  email: "u1@example.com",
  full_name: "Una Investor",
  investor_reference: "R1",
  account_type: "investor",
  status: "active",
  phone_verified: true,
  marketing_consent: false,
  number_format: numberFormat,
  pin_set: true,
  pin_locked_until: null,
  second_factor: "sms"
});

test("U33-DEC-32: the account's number format applies, and a new choice is saved in the account", async () => {
  let saved = "swiss";
  // The account's handlers come first: the first matching handler answers.
  server.use(
    http.get("*/api/v1/auth/me/", () => HttpResponse.json({ user: accountUser(saved), qa_controls_available: false, platform_business_date: "2026-11-10" })),
    http.patch("*/api/v1/auth/preferences/display/", async ({ request }) => {
      const body = (await request.json()) as { number_format: string };
      calls.displayPreferences.push(body);
      saved = body.number_format;
      return HttpResponse.json({ user: accountUser(saved) });
    }),
    ...investorShellHandlers(calls)
  );
  renderLiveApp(App, "/settings/preferences");

  const group = await screen.findByRole("group", { name: "Number format" }, { timeout: 5000 });
  await waitFor(() => expect(within(group).getByRole("button", { pressed: true })).toHaveAttribute("data-format", "swiss"));
  expect(readNumberFormatPreference()).toBe("swiss");

  fireEvent.click(group.querySelector('[data-format="european"]') as HTMLElement);
  await waitFor(() => expect(calls.displayPreferences).toEqual([{ number_format: "european" }]));
  expect(within(group).getByRole("button", { pressed: true })).toHaveAttribute("data-format", "european");
});
