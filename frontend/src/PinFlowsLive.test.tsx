// IP of Webby-Soft SRL.
// Real-API checks of the investor PIN (ACC-DEC-009): the PIN goes with the email code of
// every sensitive action; wrong, locked and missing PINs; the post-login "Create your
// PIN" screen; the registration step; Change PIN and Forgot PIN.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import {
  getV1AuthMeRetrieveResponseMock,
  getV1KycStatusRetrieveResponseMock,
  getV1LedgerWithdrawalRequestsCreateResponseMock
} from "./api/generated/banxumApi";
import { balancesPayload, emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";
import { enterPin, TEST_PIN } from "./test/pin";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("withdrawals", "codes", "pinSet", "pinChange", "pinResetStart", "pinResetConfirm");
});

const NEW_PIN = "730519";
const verifiedIban = {
  id: "pi1",
  currency: "CHF",
  status: "active",
  destination_iban: "CH9300762011623852957",
  destination_account_name: "Una Investor",
  is_verified_usable: true,
  verified_at: "2026-10-01T00:00:00Z",
  created_at: "2026-10-01T00:00:00Z"
};

function lender(overrides: Record<string, unknown> = {}) {
  return {
    id: "u1",
    email: "una@example.com",
    full_name: "Una Investor",
    investor_reference: "R1",
    account_type: "natural_person_lender",
    status: "active",
    phone_verified: true,
    marketing_consent: false,
    pin_set: true,
    pin_locked_until: null,
    ...overrides
  };
}

function pinStatus(overrides: Record<string, unknown> = {}) {
  return {
    pin: {
      pin_set: true,
      locked_until: null,
      attempts_left: 5,
      max_attempts: 5,
      setup_requires_email_code: true,
      reset_available: true,
      phone_last_digits: "42",
      ...overrides
    }
  };
}

function pinHandlers(status: () => ReturnType<typeof pinStatus> = () => pinStatus()) {
  return [
    http.get("*/api/v1/auth/pin/status/", () => HttpResponse.json(status())),
    http.post("*/api/v1/auth/pin/set/", async ({ request }) => {
      calls.pinSet.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(pinStatus(), { status: 201 });
    }),
    http.post("*/api/v1/auth/pin/change/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.pinChange.push(body);
      if (body.pin !== TEST_PIN) {
        return HttpResponse.json(
          { detail: "Wrong PIN. 4 attempts left before your PIN is locked.", code: "pin_invalid", attempts_left: 4 },
          { status: 400 }
        );
      }
      return HttpResponse.json(pinStatus());
    }),
    http.post("*/api/v1/auth/pin/reset/start/", () => {
      calls.pinResetStart.push({});
      return HttpResponse.json(
        { phone_challenge_id: "33333333-3333-4333-8333-333333333333", expires_at: "2026-10-16T12:10:00Z", phone_last_digits: "42" },
        { status: 202 }
      );
    }),
    http.post("*/api/v1/auth/pin/reset/confirm/", async ({ request }) => {
      calls.pinResetConfirm.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(pinStatus());
    })
  ];
}

function withdrawalHandlers(results: Array<() => Response>) {
  return [
    ...investorShellHandlers(calls, { balances: () => balancesPayload([{ currency: "CHF", investableMinor: 500_000 }], [verifiedIban]) }),
    ...pinHandlers(),
    http.post("*/api/v1/ledger/withdrawal-requests/", async ({ request }) => {
      calls.withdrawals.push((await request.json()) as Record<string, unknown>);
      const next = results.shift();
      return next ? next() : HttpResponse.json(getV1LedgerWithdrawalRequestsCreateResponseMock(), { status: 201 });
    })
  ];
}

async function openWithdrawalConfirm() {
  fireEvent.click((await screen.findAllByRole("button", { name: "Withdraw to IBAN" }, { timeout: 5000 }))[0]);
  const dialog = await screen.findByRole("dialog");
  fireEvent.change(within(dialog).getByPlaceholderText("0.00"), { target: { value: "100" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Review" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Email confirmation code" }), { target: { value: "123456" } });
  return dialog;
}

test("the PIN goes with the email code; a wrong PIN shows the attempts left and keeps the code", async () => {
  server.use(
    ...withdrawalHandlers([
      () => HttpResponse.json(
        { detail: "Wrong PIN. 4 attempts left before your PIN is locked.", code: "pin_invalid", attempts_left: 4 },
        { status: 400 }
      )
    ])
  );
  renderLiveApp(App, "/balances");
  await openWithdrawalConfirm();
  const confirm = screen.getByRole("button", { name: "Confirm withdrawal" });
  // The email code alone is not enough.
  expect(confirm).toBeDisabled();
  enterPin(NEW_PIN);
  await waitFor(() => expect(confirm).toBeEnabled());
  fireEvent.click(confirm);

  expect(await screen.findByText("Wrong PIN. 4 attempts left before your PIN is locked.", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "PIN digit 1 of 6" })).toHaveValue("");
  expect(screen.getByRole("textbox", { name: "PIN digit 1 of 6" })).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByRole("textbox", { name: "Email confirmation code" })).toHaveValue("123456");
  expect(screen.getByRole("button", { name: "Confirm withdrawal" })).toBeDisabled();

  enterPin();
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findAllByText("Withdrawal requested", {}, { timeout: 5000 });
  expect(calls.withdrawals.map((body) => body.pin)).toEqual([NEW_PIN, TEST_PIN]);
  expect(calls.withdrawals[1].sensitive_action_code_id).toBe(calls.withdrawals[0].sensitive_action_code_id);
  expect(calls.withdrawals[1].sensitive_action_code).toBe("123456");
  expect(calls.codes).toEqual([{ action: "withdrawal" }]);
}, 30_000);

test("a locked PIN says until when; Forgot PIN resets it with the email and SMS codes", async () => {
  const lockedUntil = new Date(Date.now() + 30 * 60 * 1000).toISOString();
  server.use(
    ...withdrawalHandlers([
      () => HttpResponse.json(
        { detail: "Wrong PIN. Your PIN is now locked after 5 wrong attempts.", code: "pin_locked", locked_until: lockedUntil },
        { status: 423 }
      )
    ])
  );
  renderLiveApp(App, "/balances");
  await openWithdrawalConfirm();
  enterPin(NEW_PIN);
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));

  const time = new Date(lockedUntil).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" });
  expect(await screen.findByText("PIN locked", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByText(`Too many wrong PINs. You can try again after ${time}, or set a new PIN now.`)).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "PIN digit 1 of 6" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Confirm withdrawal" })).toBeDisabled();

  fireEvent.click(screen.getAllByRole("button", { name: "Forgot PIN?" })[0]);
  const forgot = await screen.findByRole("dialog", { name: "Forgot PIN" });
  expect(await within(forgot).findByText("42")).toBeInTheDocument();
  fireEvent.click(within(forgot).getByRole("button", { name: "Send the codes" }));
  await waitFor(() => expect(calls.pinResetStart).toHaveLength(1));
  await waitFor(() => expect(calls.codes).toContainEqual({ action: "pin_reset" }));
  fireEvent.change(within(forgot).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "111222" } });
  fireEvent.change(within(forgot).getByRole("textbox", { name: "SMS code" }), { target: { value: "333444" } });
  enterPin(TEST_PIN, "New PIN", forgot);
  enterPin(TEST_PIN, "Repeat new PIN", forgot);
  fireEvent.click(within(forgot).getByRole("button", { name: "Save new PIN" }));

  await screen.findByText("Your new PIN is active", {}, { timeout: 5000 });
  expect(calls.pinResetConfirm).toEqual([
    {
      sensitive_action_code_id: "22222222-2222-4222-8222-222222222222",
      sensitive_action_code: "111222",
      phone_challenge_id: "33333333-3333-4333-8333-333333333333",
      phone_code: "333444",
      new_pin: TEST_PIN,
      new_pin_confirmation: TEST_PIN
    }
  ]);
  fireEvent.click(screen.getByRole("button", { name: "Done" }));

  // Back in the withdrawal: the lock is gone and the new PIN is filled in.
  await waitFor(() => expect(screen.queryByText("PIN locked")).not.toBeInTheDocument());
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm withdrawal" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findAllByText("Withdrawal requested", {}, { timeout: 5000 });
  expect(calls.withdrawals[1].pin).toBe(TEST_PIN);
}, 40_000);

test("no PIN yet: the create-PIN dialog opens and the action continues with the new PIN", async () => {
  server.use(
    ...withdrawalHandlers([
      () => HttpResponse.json({ detail: "Create your PIN first.", code: "pin_required" }, { status: 409 })
    ]),
    http.get("*/api/v1/auth/pin/status/", () => HttpResponse.json(pinStatus({ pin_set: false })))
  );
  renderLiveApp(App, "/balances");
  await openWithdrawalConfirm();
  enterPin(NEW_PIN);
  fireEvent.click(screen.getByRole("button", { name: "Confirm withdrawal" }));

  const create = await screen.findByRole("dialog", { name: "Create your PIN" }, { timeout: 5000 });
  expect(within(create).getByText(/the action continues right after/)).toBeInTheDocument();
  await waitFor(() => expect(calls.codes).toContainEqual({ action: "pin_setup" }));
  enterPin(TEST_PIN, "PIN", create);
  enterPin(TEST_PIN, "Repeat PIN", create);
  fireEvent.change(within(create).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "555666" } });
  fireEvent.click(within(create).getByRole("button", { name: "Save PIN" }));

  await screen.findAllByText("Withdrawal requested", {}, { timeout: 5000 });
  expect(calls.pinSet).toEqual([
    {
      new_pin: TEST_PIN,
      new_pin_confirmation: TEST_PIN,
      sensitive_action_code_id: "22222222-2222-4222-8222-222222222222",
      sensitive_action_code: "555666"
    }
  ]);
  expect(calls.withdrawals.map((body) => body.pin)).toEqual([NEW_PIN, TEST_PIN]);
  expect(calls.withdrawals[1].sensitive_action_code).toBe("123456");
}, 40_000);

test("after login an account without a PIN creates it before anything else", async () => {
  server.use(
    // First match wins: this account replaces the shell's default investor.
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({ ...getV1AuthMeRetrieveResponseMock(), user: lender({ pin_set: false }), qa_controls_available: false })
    ),
    ...investorShellHandlers(calls),
    ...pinHandlers(() => pinStatus({ pin_set: false }))
  );
  renderLiveApp(App, "/dashboard");

  expect(await screen.findByRole("heading", { name: "Create your PIN" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Investor portal navigation" })).not.toBeInTheDocument();
  await waitFor(() => expect(calls.codes).toEqual([{ action: "pin_setup" }]));
  const save = screen.getByRole("button", { name: "Save PIN" });
  enterPin("111111");
  expect(screen.getByText("Choose a PIN that does not repeat one digit, like 111111.")).toBeInTheDocument();
  enterPin();
  enterPin(TEST_PIN, "Repeat PIN");
  expect(save).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "777888" } });
  expect(save).toBeEnabled();
  fireEvent.click(save);

  expect(await screen.findByRole("navigation", { name: "Investor portal navigation" }, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.pinSet).toEqual([
    {
      new_pin: TEST_PIN,
      new_pin_confirmation: TEST_PIN,
      sensitive_action_code_id: "22222222-2222-4222-8222-222222222222",
      sensitive_action_code: "777888"
    }
  ]);
}, 30_000);

test("registration asks for the PIN after the phone and before identity verification", async () => {
  const user = lender({ status: "pending_kyc", pin_set: false });
  server.use(
    ...pinHandlers(() => pinStatus({ pin_set: false, setup_requires_email_code: false })),
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({ ...getV1AuthMeRetrieveResponseMock(), user, qa_controls_available: false })
    ),
    http.get("*/api/v1/kyc/status/", () =>
      HttpResponse.json({ ...getV1KycStatusRetrieveResponseMock(), status: "not_started", financial_access_allowed: false })
    )
  );
  window.localStorage.setItem(
    "banxum:register-flow:v3",
    JSON.stringify({ step: 2, email: user.email, firstName: "Una", lastName: "Investor", emailLoginSent: true })
  );
  renderLiveApp(App, "/register");

  expect(await screen.findByRole("heading", { name: "Create your PIN" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByText("Step 3 of 4")).toBeInTheDocument();
  expect(screen.getByText("You will enter it with the email code for every investment, withdrawal and bank change.")).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Registration steps" })).getByLabelText("PIN")).toHaveAttribute("aria-current", "step");
  // No email code at registration: the user just proved the email and the phone.
  expect(screen.queryByRole("textbox", { name: "Email confirmation code" })).not.toBeInTheDocument();
  const save = screen.getByRole("button", { name: "Save PIN" });
  enterPin("123456");
  expect(screen.getByText("Choose a PIN that is not a straight run of digits, like 123456 or 654321.")).toBeInTheDocument();
  enterPin();
  enterPin(NEW_PIN, "Repeat PIN");
  expect(screen.getByText("The two PINs do not match.")).toBeInTheDocument();
  expect(save).toBeDisabled();
  enterPin(TEST_PIN, "Repeat PIN");
  fireEvent.click(save);

  expect(await screen.findByRole("heading", { name: "Identity verification" }, { timeout: 5000 })).toBeInTheDocument();
  expect(calls.pinSet).toEqual([{ new_pin: TEST_PIN, new_pin_confirmation: TEST_PIN }]);
  expect(calls.codes).toEqual([]);
}, 30_000);

test("Settings: Change PIN needs the current PIN, an email code and the new PIN twice", async () => {
  server.use(
    http.get("*/api/v1/auth/me/", () =>
      HttpResponse.json({ ...getV1AuthMeRetrieveResponseMock(), user: lender(), qa_controls_available: false })
    ),
    ...investorShellHandlers(calls),
    ...pinHandlers()
  );
  renderLiveApp(App, "/settings");
  fireEvent.click(await screen.findByRole("button", { name: "PIN" }, { timeout: 5000 }));
  expect(await screen.findByText("Set")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Change PIN" }));

  const dialog = await screen.findByRole("dialog", { name: "Change PIN" });
  await waitFor(() => expect(calls.codes).toEqual([{ action: "pin_change" }]));
  enterPin(NEW_PIN, "Current PIN", dialog);
  enterPin(TEST_PIN, "New PIN", dialog);
  enterPin(TEST_PIN, "Repeat new PIN", dialog);
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Email confirmation code" }), { target: { value: "999000" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Save new PIN" }));
  expect(await within(dialog).findByText("Wrong PIN. 4 attempts left before your PIN is locked.")).toBeInTheDocument();

  enterPin(TEST_PIN, "Current PIN", dialog);
  enterPin(NEW_PIN, "New PIN", dialog);
  enterPin(NEW_PIN, "Repeat new PIN", dialog);
  fireEvent.click(within(dialog).getByRole("button", { name: "Save new PIN" }));
  await screen.findByText("Your new PIN is active", {}, { timeout: 5000 });
  expect(calls.pinChange[1]).toEqual({
    pin: TEST_PIN,
    new_pin: NEW_PIN,
    new_pin_confirmation: NEW_PIN,
    sensitive_action_code_id: "22222222-2222-4222-8222-222222222222",
    sensitive_action_code: "999000"
  });
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  expect(await screen.findByText("Your PIN was changed.")).toBeInTheDocument();
}, 30_000);
