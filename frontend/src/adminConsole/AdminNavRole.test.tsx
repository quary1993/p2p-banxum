// Real-API admin console check (audit 2026-10-09, SECURITY-06): "Superadmin settings"
// holds superadmin-only actions, so a regular admin does not see it.
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let AdminApp: ComponentType;
beforeAll(async () => {
  AdminApp = (await import("./AdminApp")).AdminApp;
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

function renderAdminAs(accountType: "admin" | "superadmin", path = "/admin") {
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        user: {
          id: "a1",
          email: `${accountType}@example.com`,
          full_name: "Ops",
          investor_reference: null,
          account_type: accountType,
          status: "active",
          phone_verified: false,
          marketing_consent: false
        },
        qa_controls_available: false,
        platform_business_date: "2026-10-09"
      })
    )
  );
  window.history.pushState({}, "", path);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AdminApp />
    </QueryClientProvider>
  );
}

test("a regular admin does not see superadmin settings", async () => {
  renderAdminAs("admin", "/admin/settings");

  const nav = await screen.findByRole("complementary", { name: "Admin console navigation" });
  expect(within(nav).getByRole("button", { name: "Daily dashboard" })).toBeInTheDocument();
  expect(within(nav).queryByRole("button", { name: "Superadmin settings" })).not.toBeInTheDocument();
  // A direct link to the section goes back to the dashboard.
  await vi.waitFor(() => expect(window.location.pathname).toBe("/admin"));
});

test("a superadmin sees superadmin settings", async () => {
  renderAdminAs("superadmin");

  const nav = await screen.findByRole("complementary", { name: "Admin console navigation" });
  expect(within(nav).getByRole("button", { name: "Superadmin settings" })).toBeInTheDocument();
});
