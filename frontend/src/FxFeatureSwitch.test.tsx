// IP of Webby-Soft SRL.
// Currency exchange: off by the platform setting fx.enabled (owner decision 2026-10-16), and the
// exchange screen removed from the investor area (Q25, 2026-11-13): no FX menu item and /fx shows
// the dashboard, also when the switch is on. Real-API mode: GET /api/v1/investor/portal/features/.
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1InvestorPortalDashboardRetrieveResponseMock, getV1InvestorPortalFxRetrieveResponseMock } from "./api/generated/banxumApi";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("codes");
});

function useFeatures(fxEnabled: boolean) {
  server.use(
    http.get("*/api/v1/investor/portal/features/", () => HttpResponse.json({ fx_enabled: fxEnabled })),
    http.get("*/api/v1/investor/portal/dashboard/", () => HttpResponse.json(getV1InvestorPortalDashboardRetrieveResponseMock())),
    http.get("*/api/v1/investor/portal/fx/", () =>
      HttpResponse.json({ ...getV1InvestorPortalFxRetrieveResponseMock(), quotes: [], exchanges: [] })
    ),
    http.get("*/api/v1/investor/portal/activity/", () => HttpResponse.json({ entries: [] })),
    ...investorShellHandlers(calls)
  );
}

test("FX off: no FX menu item, and /fx shows the dashboard at /dashboard", async () => {
  useFeatures(false);
  renderLiveApp(App, "/fx");

  await waitFor(() => expect(window.location.pathname).toBe("/dashboard"), { timeout: 5000 });
  const nav = await screen.findByRole("navigation", { name: "Investor portal navigation" }, { timeout: 5000 });
  expect(within(nav).getByRole("link", { name: "Account" })).toBeInTheDocument();
  expect(within(nav).queryByRole("link", { name: "Currency exchange" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Currency exchange" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Convert" })).not.toBeInTheDocument();
}, 30_000);

test("Q25: even with the FX switch on there is no exchange screen in the investor area", async () => {
  useFeatures(true);
  renderLiveApp(App, "/fx");

  await waitFor(() => expect(window.location.pathname).toBe("/dashboard"), { timeout: 5000 });
  const nav = await screen.findByRole("navigation", { name: "Investor portal navigation" }, { timeout: 5000 });
  expect(within(nav).queryByRole("link", { name: "Currency exchange" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Currency exchange" })).not.toBeInTheDocument();
}, 30_000);
