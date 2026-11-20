// IP of Webby-Soft SRL.
// Audit S4-8: the sign-in history names every sign-in method and every result of the API. No method
// falls back to a general label.
import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { SignInMethodEnum, SignInResultEnum, type SignInEvent } from "../../../../api/generated/banxumApi";
import { SignInHistoryTable } from "./SecurityDevices";

const event: SignInEvent = {
  id: "e-1",
  occurred_at: "2026-11-20T09:00:00Z",
  device_label: "Chrome on macOS",
  device_kind: "desktop",
  country_code: "CH",
  method: "password_sms",
  result: "signed_in"
};

const METHOD_LABELS: Record<SignInMethodEnum, string> = {
  email_link: "Email link",
  registration_link: "Registration email link",
  password_sms: "Password and SMS code",
  password_app: "Password and authenticator app",
  password_recovery_code: "Password and recovery code",
  password_trusted_device: "Password on a trusted device",
  password_only: "Password (second factor not set up yet)",
  admin_password_app: "Password and authenticator app (administrator)",
  admin_password_code: "Password and email code (administrator)"
};

const RESULT_LABELS: Record<SignInResultEnum, string> = {
  signed_in: "Signed in",
  blocked: "Account blocked",
  failed: "Wrong password",
  failed_factor: "Wrong second-factor code"
};

describe("sign-in history", () => {
  test.each(Object.values(SignInMethodEnum))("the method %s has its own label", (method) => {
    render(<SignInHistoryTable events={[{ ...event, method }]} />);

    expect(screen.getByRole("cell", { name: METHOD_LABELS[method] })).toBeInTheDocument();
    expect(screen.queryByText("Other sign-in method")).not.toBeInTheDocument();
    expect(screen.queryByText("Earlier sign-in")).not.toBeInTheDocument();
  });

  test("every method has a different label", () => {
    expect(new Set(Object.values(METHOD_LABELS)).size).toBe(Object.values(SignInMethodEnum).length);
  });

  test.each(Object.values(SignInResultEnum))("the result %s has its own label", (result) => {
    render(<SignInHistoryTable events={[{ ...event, result }]} />);

    const cell = screen.getByText(RESULT_LABELS[result]);
    expect(cell).toBeInTheDocument();
    // Only a successful sign-in is plain text; every failure has the signal colour.
    expect(cell.classList.contains("bxm-signal-text")).toBe(result !== "signed_in");
  });

  test("a wrong second-factor code is not shown as a wrong password", () => {
    render(<SignInHistoryTable events={[{ ...event, result: "failed_factor" }]} />);

    expect(screen.queryByText("Wrong password")).not.toBeInTheDocument();
  });
});
