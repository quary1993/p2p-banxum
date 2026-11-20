// IP of Webby-Soft SRL.
// Audit S8-1 and S8-3: the privacy notice and the cookie policy say what the code does. The cookie
// policy names every browser storage key; measurement is described as not active.
import { expect, test } from "vitest";

import { SESSION_EXPIRED_NOTICE_STORAGE_KEY } from "../api/client/sessionExpiry";
import { LANGUAGE_STORAGE_KEY } from "../i18n/language";
import { loginFlowStorageKey, registerFlowStorageKey } from "../portal/screens/account/auth/authState";
import { siteLegal } from "./content";
import { SITE_COOKIES_KEY } from "./cookies";

function body(id: string) {
  const doc = siteLegal.find((item) => item.id === id);
  if (!doc || !("body" in doc) || typeof doc.body !== "string") throw new Error(`No legal text ${id}`);
  return doc.body;
}

test("the cookie policy names the storage keys the code uses", () => {
  const cookies = body("cookies");
  for (const key of [
    SITE_COOKIES_KEY,
    LANGUAGE_STORAGE_KEY,
    loginFlowStorageKey,
    registerFlowStorageKey,
    SESSION_EXPIRED_NOTICE_STORAGE_KEY,
    "banxum:app-route:v1",
    "banxum:marketplace-layout:v1",
    "bxm-site-newsletter",
    "bxm-site-project-filters",
    "sessionid",
    "csrftoken",
    "banxum_device",
    "banxum_trusted"
  ]) {
    expect(cookies).toContain(key);
  }
  expect(cookies).not.toContain("_ga");
  expect(cookies).toContain("Measurement (not active)");
});

test("the privacy notice names where the IP address is kept in clear and what is deleted", () => {
  const privacy = body("privacy");
  expect(privacy).toContain("IP address in clear");
  expect(privacy).toContain("record of each document you accept");
  expect(privacy).toContain("Sign-in history and ended sessions: after 365 days");
  expect(privacy).toContain("have no automatic deletion yet");
  expect(privacy).not.toMatch(/Google \(Google Analytics\) for the measurement/);
});
