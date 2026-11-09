// IP of Webby-Soft SRL.
// The sensitive-action confirmation of an investment (today: email code + PIN, ACC-DEC-009; U33-DEC-01
// keeps only the PIN from Phase 17.3). The logic stays in App.tsx (useSensitiveActionCode and its
// helpers, shared with withdrawals, bank accounts and resale); InvestorShell hands it to the investing
// screens as this kit, so the request, cooldown and PIN handling are the same everywhere.
import type { ActionEnum } from "../../../../api/generated/banxumApi";
import type { SensitivePin } from "../../../../investorPortal/pinState";

export type SensitiveCodeRequest = {
  codeId: string | null;
  expiresAt: string | null;
  error: string;
  isRequesting: boolean;
  resendCooldownSeconds: number;
  requestCode: () => void;
  pin: SensitivePin;
};

export type SensitiveActionKit = {
  /** Email-code request state of one action, with the PIN of the action. */
  useCode: (action: ActionEnum) => SensitiveCodeRequest;
  /** Sends the first email code once while `active` (the confirmation is open). */
  useAutoRequest: (codeRequest: Pick<SensitiveCodeRequest, "codeId" | "isRequesting" | "requestCode">, active: boolean) => void;
  /** "Send email code", "Code sent. Send new in 42s"... */
  requestLabel: (codeRequest: Pick<SensitiveCodeRequest, "codeId" | "isRequesting" | "resendCooldownSeconds">) => string;
  requestDisabled: (codeRequest: Pick<SensitiveCodeRequest, "isRequesting" | "resendCooldownSeconds">) => boolean;
};
