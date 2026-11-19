// IP of Webby-Soft SRL.
// What Profile & Settings knows about the signed-in investor, from today's API only (U33-DEC-26: no
// invented fields): /auth/me (name, email, investor reference, account type, marketing consent),
// /kyc/status (identity check, phone) and /auth/pin/status (PIN, last digits of the verified phone).
// Preview mode reads the fixture profile that App.tsx passes in.
import { useV1AuthMeRetrieve, useV1KycStatusRetrieve } from "../../../../api/generated/banxumApi";
import { readReadonlyImpersonationToken } from "../../../../api/client/impersonation";
import { isFixturePreview } from "../../../../investorPortal/data";
import { usePinStatus } from "../../../../investorPortal/pinState";

export type PreviewProfile = { name: string; email: string };

/** The investor reference shown in preview mode (format of accounts_auth.references). */
export const PREVIEW_INVESTOR_REFERENCE = "L5DEMQ8K2";

export function useAccountData(previewProfile?: PreviewProfile) {
  const readonly = Boolean(readReadonlyImpersonationToken());
  const me = useV1AuthMeRetrieve({ query: { enabled: !isFixturePreview, retry: false, staleTime: 0 } });
  const kyc = useV1KycStatusRetrieve({ query: { enabled: !isFixturePreview && !readonly, retry: false, staleTime: 0 } });
  const pin = usePinStatus(!readonly);
  const user = me.data?.user;
  return {
    readonly,
    loading: !isFixturePreview && me.isPending,
    error: !isFixturePreview && me.isError,
    name: (isFixturePreview ? previewProfile?.name : user?.full_name) ?? "",
    email: (isFixturePreview ? previewProfile?.email : user?.email) ?? "",
    reference: isFixturePreview ? PREVIEW_INVESTOR_REFERENCE : (user?.investor_reference ?? null),
    accountType: isFixturePreview ? "natural_person_lender" : (user?.account_type ?? ""),
    marketingConsent: isFixturePreview ? false : (user?.marketing_consent ?? false),
    phoneVerified: isFixturePreview ? true : (kyc.data?.phone_verified ?? user?.phone_verified),
    phoneLastDigits: pin.status?.phone_last_digits ?? "",
    kycStatus: isFixturePreview ? "approved" : kyc.data?.status,
    kycLoading: !isFixturePreview && !readonly && kyc.isPending,
    financialAccess: isFixturePreview ? true : kyc.data?.financial_access_allowed === true,
    manualReviewRequired: isFixturePreview ? false : kyc.data?.manual_review_required === true,
    // 18.3 (U33-DEC-26): verified by Didit when it provides them; never typed by the investor.
    verifiedAddress: isFixturePreview ? "" : (kyc.data?.verified_address ?? ""),
    verifiedBirthDate: isFixturePreview ? null : (kyc.data?.verified_birth_date ?? null),
    verifiedNationality: isFixturePreview ? "" : (kyc.data?.verified_nationality ?? ""),
    pin,
    user
  };
}

export type AccountData = ReturnType<typeof useAccountData>;

/** The account type as the investor reads it. */
export function investorTypeLabel(accountType: string) {
  if (accountType === "natural_person_lender") return "Individual";
  if (accountType === "legal_entity_lender_representative") return "Company representative";
  return "";
}

export type KycTone = "done" | "pending" | "action";

/**
 * The identity check status in words. The provider's flags (sanctions, PEP, adverse media, high
 * risk) are never shown to the investor: they read "In review" until compliance decides.
 */
export function kycStatusView(status: string | undefined): { label: string; description: string; tone: KycTone } {
  switch (status) {
    case "approved":
      return { label: "Approved", description: "Your identity has been verified.", tone: "done" };
    case "pending":
      return { label: "Waiting for the result", description: "Your identity check has been submitted. This page updates when the result arrives.", tone: "pending" };
    case "not_started":
      return { label: "Not started", description: "Verify your identity with Didit, our identity verification provider.", tone: "action" };
    case "expired":
      return { label: "Expired", description: "Your identity check was not completed in time. Start it again with Didit.", tone: "action" };
    case "reverification_required":
      return { label: "Verify again", description: "We need you to verify your identity again with Didit.", tone: "action" };
    case "declined":
      return { label: "Not approved", description: "Your identity check was not approved. Contact support for the next step.", tone: "action" };
    case undefined:
      return { label: "", description: "", tone: "pending" };
    default:
      return { label: "In review", description: "Our compliance team is reviewing your verification. No action is needed from you in the meantime.", tone: "pending" };
  }
}
