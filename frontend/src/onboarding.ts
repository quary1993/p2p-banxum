import type { UserSummary } from "./api/generated/banxumApi";

// Registration steps (18.5): 0 details and password, 1 email, 2 security (second factor, recovery
// codes and, for SMS, the PIN of ACC-DEC-009), 3 identity (KYC). A signed-in account has already
// confirmed its email (the registration link, or the password sign-in that needs it).
export function onboardingStepForUser(
  user: Pick<UserSummary, "account_type" | "status"> & Partial<Pick<UserSummary, "pin_set" | "second_factor" | "phone_verified">>
) {
  if (user.account_type !== "natural_person_lender" || user.status !== "pending_kyc") {
    return null;
  }
  const factor = user.second_factor ?? (user.phone_verified ? "sms" : "");
  if (!factor) return 2;
  if (factor === "sms" && user.pin_set === false) return 2;
  return 3;
}
