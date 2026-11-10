// IP of Webby-Soft SRL.
// Real-API interface language (U33-DEC-31): the account's language applies after sign-in, a new
// choice applies at once on the same page and is saved in the account, and a choice made before
// sign-in is saved in the account after it.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getLocale } from "./i18n";
import { chooseLanguage, hasUnsavedLanguageChoice, resetLanguageForTests } from "./i18n/language";
import { formatDate, resetNumberFormatForTests } from "./investorPortal/format";
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
  resetLanguageForTests();
});
afterEach(() => resetLanguageForTests());

const accountUser = (language: string) => ({
  id: "u1",
  email: "u1@example.com",
  full_name: "Una Investor",
  investor_reference: "R1",
  account_type: "investor",
  status: "active",
  phone_verified: true,
  marketing_consent: false,
  number_format: "european",
  language,
  pin_set: true,
  pin_locked_until: null
});

function accountHandlers(initial: string) {
  let saved = initial;
  return [
    http.get("*/api/v1/auth/me/", () => HttpResponse.json({ user: accountUser(saved), qa_controls_available: false, platform_business_date: "2026-11-10" })),
    http.patch("*/api/v1/auth/preferences/display/", async ({ request }) => {
      const body = (await request.json()) as { language: string };
      calls.displayPreferences.push(body);
      saved = body.language;
      return HttpResponse.json({ user: accountUser(saved) });
    })
  ];
}

test("U33-DEC-31: the account's language applies after sign-in, with German dates", async () => {
  // The account's handlers come first: the first matching handler answers.
  server.use(...accountHandlers("de-CH"), ...investorShellHandlers(calls));
  renderLiveApp(App, "/settings/preferences");

  expect(await screen.findByRole("combobox", { name: "Sprache" }, { timeout: 5000 })).toHaveValue("de-CH");
  expect(screen.getByRole("heading", { name: "Anzeige" })).toBeInTheDocument();
  expect(document.documentElement.lang).toBe("de-CH");
  expect(formatDate("2026-10-04T10:00:00Z")).toBe("4. Okt. 2026");
  expect(calls.displayPreferences).toEqual([]);
});

test("U33-DEC-31: a new choice applies at once on the same page and is saved in the account", async () => {
  server.use(...accountHandlers("en"), ...investorShellHandlers(calls));
  renderLiveApp(App, "/settings/preferences");

  const select = await screen.findByRole("combobox", { name: "Language" }, { timeout: 5000 });
  expect(select).toHaveValue("en");
  fireEvent.change(select, { target: { value: "de-CH" } });

  expect(await screen.findByRole("heading", { name: "Anzeige" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Sprache" })).toHaveValue("de-CH");
  await waitFor(() => expect(calls.displayPreferences).toEqual([{ language: "de-CH" }]));
  await waitFor(() => expect(hasUnsavedLanguageChoice()).toBe(false));
  expect(window.location.pathname).toBe("/settings/preferences");
});

test("U33-DEC-31: a language chosen before sign-in is saved in the account after it", async () => {
  await chooseLanguage("de-CH");
  server.use(...accountHandlers("en"), ...investorShellHandlers(calls));
  renderLiveApp(App, "/settings/preferences");

  await waitFor(() => expect(calls.displayPreferences).toEqual([{ language: "de-CH" }]), { timeout: 5000 });
  expect(await screen.findByRole("combobox", { name: "Sprache" })).toHaveValue("de-CH");
  expect(getLocale()).toBe("de-CH");
});
