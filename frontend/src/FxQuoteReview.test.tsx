// Real-API FX review checks (audit 2026-10-09, A-64): the confirmation shows the amount in minor
// units, one rate (the quote's), a countdown from receipt using the quote's own time to live, and a
// "Refresh quote" button once it ran out; the daily limit comes from the API.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { balances, renderLiveApp, shellHandlers, summary } from "./test/liveHarness";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

const rate = 1.04;
const feeBps = 150;

function economics(sourceMinor: number) {
  const gross = Math.round(sourceMinor * rate);
  const fee = Math.round((gross * feeBps) / 10_000);
  return { gross, fee, target: gross - fee };
}

function previewPayload(source: string, target: string, sourceMinor: number) {
  const { gross, fee, target: net } = economics(sourceMinor);
  return {
    source_currency: source,
    target_currency: target,
    source_amount_minor: sourceMinor,
    provider: "mock",
    rate: rate.toFixed(12),
    previous_day_average_rate: null,
    platform_fee_bps: feeBps,
    gross_target_amount_minor: gross,
    fee_minor: fee,
    target_amount_minor: net,
    effective_net_rate: (net / sourceMinor).toFixed(12),
    limit_chf_equivalent_minor: sourceMinor,
    provider_rate_timestamp: "2026-12-10T11:00:00Z",
    sanity_metadata: {},
    previewed_at: "2026-12-10T11:00:00Z"
  };
}

test("FX review: minor-unit amount, one rate, countdown from receipt, refresh, limit from the API", async () => {
  let quotes = 0;
  server.use(
    ...shellHandlers({
      balances: () =>
        balances({
          summaries: [
            summary("CHF", { total_available_minor: 1_000_000, investable_minor: 1_000_000 }),
            summary("EUR", {})
          ]
        })
    }),
    http.get("*/api/v1/investor/portal/fx/", () =>
      HttpResponse.json({
        quotes: [],
        exchanges: [],
        terms: { daily_limit_chf_minor: 2_500_000, daily_limit_used_chf_minor: 120_000, quote_ttl_seconds: 2, platform_fee_bps: feeBps }
      })
    ),
    http.get("*/api/v1/fx/quote-preview/", ({ request }) => {
      const url = new URL(request.url);
      return HttpResponse.json(
        previewPayload(
          url.searchParams.get("source_currency") ?? "CHF",
          url.searchParams.get("target_currency") ?? "EUR",
          Number(url.searchParams.get("source_amount_minor"))
        )
      );
    }),
    http.post("*/api/v1/fx/quotes/", async ({ request }) => {
      quotes += 1;
      const body = (await request.json()) as { source_amount_minor: number };
      // Platform (QA) clock far from the browser clock: only the 2-second time to live counts.
      return HttpResponse.json({
        ...previewPayload("CHF", "EUR", body.source_amount_minor),
        id: `quote-${quotes}`,
        investor_user_id: "u1",
        provider_quote_id: `p-${quotes}`,
        issued_at: "2020-01-01T00:00:00Z",
        expires_at: "2020-01-01T00:00:02Z",
        sanity_check_passed: true,
        status: "issued",
        created_at: "2020-01-01T00:00:00Z",
        updated_at: "2020-01-01T00:00:00Z"
      });
    })
  );
  renderLiveApp(App, "/fx");

  // Daily limit and quote lock from the API, Swiss formatting.
  expect(await screen.findByText("CHF 25'000 equivalent", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByText("CHF 1'200.00")).toBeInTheDocument();
  expect(screen.getByText("2 seconds")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Amount to convert from CHF"), { target: { value: "1234.56" } });
  const { target } = economics(123_456);
  expect(target).toBe(126_468);
  await waitFor(() => expect(screen.getByRole("button", { name: "Convert" })).toBeEnabled(), { timeout: 5000 });
  const pageRate = screen.getByText(/^1 CHF = .* EUR$/, { selector: ".fx-rate-value" }).textContent;
  expect(pageRate).toBe("1 CHF = 1.0244 EUR");

  fireEvent.click(screen.getByRole("button", { name: "Convert" }));
  const dialog = await screen.findByRole("dialog", { name: "Confirm currency exchange" }, { timeout: 5000 });
  expect(within(dialog).getByText("EUR 1'264.68")).toBeInTheDocument();
  expect(within(dialog).queryByText(/1'264\.6800/)).not.toBeInTheDocument();
  expect(within(dialog).getByText("1 CHF = 1.0244 EUR")).toBeInTheDocument();
  // The countdown starts at the quote's time to live although expires_at is years in the past.
  expect(within(dialog).getByText(/0:0[12]/)).toBeInTheDocument();

  expect(await within(dialog).findByText("This quote has expired", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Confirm exchange" })).toBeDisabled();
  fireEvent.click(within(dialog).getByRole("button", { name: "Refresh quote" }));
  await waitFor(() => expect(quotes).toBe(2));
  await waitFor(() => expect(within(dialog).queryByText("This quote has expired")).not.toBeInTheDocument());
  expect(within(dialog).getByText(/0:0[12]/)).toBeInTheDocument();
}, 30_000);
