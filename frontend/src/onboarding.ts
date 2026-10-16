import type { UserSummary } from "./api/generated/banxumApi";

// Registration steps: 0 account, 1 email and phone, 2 PIN (ACC-DEC-009), 3 KYC.
export function onboardingStepForUser(
  user: Pick<UserSummary, "account_type" | "status" | "phone_verified"> &
    Partial<Pick<UserSummary, "pin_set">>
) {
  if (user.account_type !== "natural_person_lender" || user.status !== "pending_kyc") {
    return null;
  }
  if (!user.phone_verified) return 1;
  return user.pin_set === false ? 2 : 3;
}
