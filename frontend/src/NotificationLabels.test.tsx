// Real-API Notifications page check (audit 2026-10-09, A-46): notices show a human topic label,
// never the raw email topic key.
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1AuthMeRetrieveResponseMock, getV1KycStatusRetrieveResponseMock } from "./api/generated/banxumApi";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

const notifications = {
  unread_count: 1,
  notifications: [
    {
      id: "11111111-1111-4111-8111-111111111111",
      notification_source: "email_delivery",
      topic: "email.deposit_reconciled",
      topic_label: "Deposit",
      status: "sent",
      title: "Deposit credited: CHF 25'000.00",
      body: "We credited CHF 25'000.00 to your BANXUM balance. Value date: 2026-10-09.",
      created_at: "2026-10-09T11:47:00Z",
      sent_at: "2026-10-09T11:47:05Z",
      unread: true,
      navigation_target: "balances",
      navigation_target_id: ""
    },
    {
      id: "22",
      notification_source: "email_outbox",
      topic: "email.withdrawal_status",
      topic_label: "Withdrawal",
      status: "pending",
      title: "Withdrawal requested: CHF 250.00",
      body: "We received your request to withdraw CHF 250.00.",
      created_at: "2026-10-09T11:40:00Z",
      sent_at: null,
      unread: false,
      navigation_target: "balances",
      navigation_target_id: ""
    }
  ]
};

test("notifications page shows topic labels, not raw topic keys", async () => {
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({
        ...getV1AuthMeRetrieveResponseMock(),
        user: {
          id: "u1",
          email: "investor@example.com",
          full_name: "Investor One",
          investor_reference: "R1",
          account_type: "investor",
          status: "active",
          phone_verified: true,
          marketing_consent: false
        }
      })
    ),
    http.get("*/api/v1/kyc/status/", () =>
      HttpResponse.json({ ...getV1KycStatusRetrieveResponseMock(), status: "approved", financial_access_allowed: true })
    ),
    http.get("*/api/v1/investor/portal/notifications/", () => HttpResponse.json(notifications))
  );
  window.history.pushState({}, "", "/notifications");
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>
  );

  const title = await screen.findByText("Deposit credited: CHF 25'000.00", {}, { timeout: 5000 });
  const row = title.closest(".notice-row") as HTMLElement;
  expect(within(row).getByText("Deposit")).toBeInTheDocument();
  expect(screen.getByText("Withdrawal")).toBeInTheDocument();
  expect(screen.queryByText(/email\.deposit_reconciled|email\.withdrawal_status/)).not.toBeInTheDocument();
});
