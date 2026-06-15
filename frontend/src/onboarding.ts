import type { UserSummary } from "./api/generated/banxumApi";

export function onboardingStepForUser(
  user: Pick<UserSummary, "account_type" | "status" | "phone_verified">
) {
  if (user.account_type !== "natural_person_lender" || user.status !== "pending_kyc") {
    return null;
  }
  return user.phone_verified ? 2 : 1;
}
