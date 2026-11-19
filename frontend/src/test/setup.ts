import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, vi } from "vitest";

import { server } from "../api/mocks/server";
import { AdminApp, SitePages } from "../lazyAreas";
import { resetNumberFormatForTests } from "../investorPortal/format";
import { resetAppearanceForTests } from "../portal/appearance";

beforeAll(async () => {
  // The lazy areas (audit G-07) render synchronously once loaded, as the tests expect.
  await Promise.all([SitePages.preload(), AdminApp.preload()]);
  Object.defineProperty(window, "scrollTo", {
    value: vi.fn(),
    writable: true
  });
  // jsdom does not implement scrollIntoView; the finance pending-work table
  // scrolls to the withdrawal execution form after "Resolve" is clicked.
  Element.prototype.scrollIntoView = vi.fn();
  server.listen({ onUnhandledRequest: "error" });
});

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  // Preferences cached by the investor area (U33): each test starts from the defaults.
  resetNumberFormatForTests();
  resetAppearanceForTests();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
