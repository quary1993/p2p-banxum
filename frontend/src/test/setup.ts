import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, vi } from "vitest";

import { server } from "../api/mocks/server";

beforeAll(() => {
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
