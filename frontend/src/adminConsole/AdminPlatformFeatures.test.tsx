// IP of Webby-Soft SRL.
// Real-API admin console check: the superadmin "Platform features" card switches currency
// exchange (FX) on or off with a required reason and shows the last change (2026-10-16).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { server } from "../api/mocks/server";
import type { PlatformFeatures } from "../api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let AdminApp: ComponentType;
beforeAll(async () => {
  AdminApp = (await import("./AdminApp")).AdminApp;
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

function features(enabled: boolean, change: { by: string; reason: string; version: number }): PlatformFeatures {
  return {
    features: [
      {
        key: "fx.enabled",
        title: "Currency exchange (FX)",
        description: "Investors can get FX quotes and exchange CHF and EUR.",
        enabled,
        last_change: {
          version: change.version,
          enabled,
          changed_at: "2026-10-16T15:00:00Z",
          changed_by_type: change.by ? "superadmin" : "system",
          changed_by_id: change.by ? "sa1" : "system",
          changed_by_email: change.by,
          reason: change.reason
        }
      }
    ]
  };
}

test("a superadmin switches FX on with a reason and sees the new last change", async () => {
  const posts: Array<Record<string, unknown>> = [];
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        user: {
          id: "sa1",
          email: "sa@example.com",
          full_name: "Super Admin",
          investor_reference: null,
          account_type: "superadmin",
          status: "active",
          phone_verified: false,
          marketing_consent: false
        },
        qa_controls_available: false,
        platform_business_date: "2026-10-16"
      })
    ),
    http.get("*/api/v1/admin/platform-features/", () =>
      HttpResponse.json(features(false, { by: "", reason: "Owner decision 2026-10-16: no currency exchange.", version: 1 }))
    ),
    http.post("*/api/v1/admin/platform-features/", async ({ request }) => {
      posts.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(features(true, { by: "sa@example.com", reason: "Pilot with two investors", version: 2 }));
    })
  );
  window.history.pushState({}, "", "/admin/settings");
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AdminApp />
    </QueryClientProvider>
  );

  const card = (await screen.findByRole("heading", { name: "Platform features" }, { timeout: 5000 })).closest(".card") as HTMLElement;
  const fxSwitch = await within(card).findByRole("switch", { name: "Currency exchange (FX)" });
  expect(fxSwitch).not.toBeChecked();
  expect(within(card).getByText("Off", { selector: ".chip, .chip *" })).toBeInTheDocument();
  expect(within(card).getByText(/^Off · .* · System$/)).toBeInTheDocument();
  expect(within(card).getByText("Owner decision 2026-10-16: no currency exchange.")).toBeInTheDocument();
  // Nothing to save until the switch moves.
  expect(within(card).queryByRole("button", { name: /^Switch / })).not.toBeInTheDocument();

  fireEvent.click(fxSwitch);
  const submit = within(card).getByRole("button", { name: "Switch on" });
  // The reason is required.
  expect(submit).toBeDisabled();
  fireEvent.change(within(card).getByRole("textbox", { name: "Reason for this change" }), {
    target: { value: "Pilot with two investors" }
  });
  expect(submit).toBeEnabled();
  fireEvent.click(submit);

  await waitFor(() => expect(posts).toEqual([{ key: "fx.enabled", enabled: true, reason: "Pilot with two investors" }]));
  expect(await within(card).findByText(/Currency exchange \(FX\) is now on/)).toBeInTheDocument();
  expect(within(card).getByRole("switch", { name: "Currency exchange (FX)" })).toBeChecked();
  expect(within(card).getByText(/^On · .* · sa@example\.com$/)).toBeInTheDocument();
  expect(within(card).getByText("Pilot with two investors")).toBeInTheDocument();
  expect(within(card).queryByRole("textbox", { name: "Reason for this change" })).not.toBeInTheDocument();
  expect(within(card).queryByRole("button", { name: /^Switch / })).not.toBeInTheDocument();
}, 30_000);
