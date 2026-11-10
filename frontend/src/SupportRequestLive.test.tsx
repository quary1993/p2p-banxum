// IP of Webby-Soft SRL.
// Real-API Help message and account closure request (U33-DEC-35, U33-DEC-28): the portal posts to the
// support-request endpoint, shows the receipt (reference and confirmation email), and a failed send
// keeps the message and retries with the same request key.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("supportRequests");
});

function supportHandler(fail: (attempt: number) => boolean) {
  return http.post("*/api/v1/investor/portal/support-requests/", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    calls.supportRequests.push(body);
    if (fail(calls.supportRequests.length)) return HttpResponse.json({ detail: "The support mailbox is not configured." }, { status: 400 });
    const closure = body.kind === "account_closure";
    return HttpResponse.json(
      {
        reference: closure ? "CLS-2026-0001" : "SUP-2026-0007",
        kind: body.kind,
        received_at: "2026-11-10T10:00:00Z",
        context_label: "",
        receipt_email: "u1@example.com"
      },
      { status: 201 }
    );
  });
}

test("U33-DEC-35: a Help message is sent to support and the receipt shows the reference", async () => {
  server.use(...investorShellHandlers(calls), supportHandler((attempt) => attempt === 1));
  renderLiveApp(App, "/portal/help");
  const aside = await screen.findByRole("complementary", {}, { timeout: 5000 });
  fireEvent.click(within(aside).getByRole("button", { name: /^Contact support/ }));
  const dialog = screen.getByRole("dialog", { name: "Contact support" });
  fireEvent.change(within(dialog).getByLabelText("Topic"), { target: { value: "Documents or taxes" } });
  fireEvent.change(within(dialog).getByLabelText("Message"), { target: { value: "Where is my tax statement?" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Send message" }));

  // The first send fails: the message stays and can be sent again.
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("Your message was not sent: The support mailbox is not configured.");
  expect(within(dialog).getByLabelText("Message")).toHaveValue("Where is my tax statement?");
  fireEvent.click(within(dialog).getByRole("button", { name: "Try again" }));

  expect(await within(dialog).findByRole("heading", { name: "Message sent" })).toBeInTheDocument();
  expect(within(dialog).getByText("Your reference is SUP-2026-0007.")).toBeInTheDocument();
  expect(within(dialog).getByText("We sent a confirmation to u1@example.com. Our team answers by email.")).toBeInTheDocument();
  expect(calls.supportRequests).toHaveLength(2);
  expect(calls.supportRequests[1]).toMatchObject({ kind: "help", topic: "Documents or taxes", message: "Where is my tax statement?" });
  // A retry of the same message keeps its request key: the server never stores it twice.
  expect(calls.supportRequests[1].idempotency_key).toBe(calls.supportRequests[0].idempotency_key);
}, 30_000);

test("U33-DEC-28: Close account sends a request; the receipt says the account is not closed yet", async () => {
  server.use(...investorShellHandlers(calls), supportHandler(() => false));
  renderLiveApp(App, "/settings/preferences");
  fireEvent.click(await screen.findByRole("button", { name: "Close account" }, { timeout: 5000 }));
  const dialog = screen.getByRole("dialog", { name: "Request account closure" });
  fireEvent.click(within(dialog).getByRole("button", { name: "Send closure request" }));
  await waitFor(() => expect(within(dialog).getByRole("heading", { name: "Request received" })).toBeInTheDocument());
  expect(within(dialog).getByText("Your reference is CLS-2026-0001.")).toBeInTheDocument();
  expect(within(dialog).getByText(/Your account is not closed yet\./)).toBeInTheDocument();
  expect(calls.supportRequests).toEqual([expect.objectContaining({ kind: "account_closure" })]);
}, 30_000);
