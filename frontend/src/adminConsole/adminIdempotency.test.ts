import { afterEach, expect, test, vi } from "vitest";

import { httpClient } from "../api/client/httpClient";
import { withIdempotencyKey } from "./adminIdempotency";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("an admin action keeps its key on retry and gets a new key for other values or another target (A-41)", async () => {
  const finalize = { booking_date: "2026-10-09", value_date: "2026-10-09", collection_account_identifier: "CH00", admin_notes: "" };
  const first = withIdempotencyKey("withdrawal-finalize", finalize, { withdrawalRequestId: "w1" });
  const retry = withIdempotencyKey("withdrawal-finalize", { ...finalize }, { withdrawalRequestId: "w1" });
  const otherWithdrawal = withIdempotencyKey("withdrawal-finalize", finalize, { withdrawalRequestId: "w2" });
  const otherDate = withIdempotencyKey("withdrawal-finalize", { ...finalize, value_date: "2026-10-08" }, { withdrawalRequestId: "w1" });

  expect(first).toMatchObject(finalize);
  expect(retry.idempotency_key).toBe(first.idempotency_key);
  expect(otherWithdrawal.idempotency_key).not.toBe(first.idempotency_key);
  expect(otherDate.idempotency_key).not.toBe(first.idempotency_key);

  // Once the server accepted it, the same values are a new action with a new key.
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } })));
  await httpClient({ url: "/api/v1/ledger/admin/withdrawal-requests/w1/finalize/", method: "POST", data: first });
  expect(withIdempotencyKey("withdrawal-finalize", finalize, { withdrawalRequestId: "w1" }).idempotency_key).not.toBe(first.idempotency_key);
});
