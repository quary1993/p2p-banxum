// IP of Webby-Soft SRL.
// The sensitive-action confirmation of an investment: email code + PIN (ACC-DEC-009), or email code +
// authenticator code for an investor with the app (D-1, 18.5). The logic stays in App.tsx (useSensitiveActionCode and its
// helpers, shared with withdrawals, bank accounts and resale); InvestorShell hands it to the investing
// screens as this kit, so the request, cooldown and PIN handling are the same everywhere.
import type { ActionEnum } from "../../../../api/generated/banxumApi";
import type { OperationDetails } from "../../../../investorPortal/operationBinding";
import type { SensitivePin } from "../../../../investorPortal/pinState";

export type SensitiveCodeRequest = {
  codeId: string | null;
  expiresAt: string | null;
  error: string;
  /** What the email code confirms, as the email shows it (18.5). */
  summary: string;
  isRequesting: boolean;
  resendCooldownSeconds: number;
  requestCode: () => void;
  pin: SensitivePin;
};

export type SensitiveActionKit = {
  /**
   * Email-code request state of one action, with the PIN (or authenticator code, D-1) of the
   * action. 18.5: the code is requested with the operation details and confirms only them.
   */
  useCode: (action: ActionEnum, operation?: OperationDetails | null) => SensitiveCodeRequest;
  /** Sends the first email code once while `active` (the confirmation is open). */
  useAutoRequest: (codeRequest: Pick<SensitiveCodeRequest, "codeId" | "isRequesting" | "requestCode">, active: boolean) => void;
  /** "Send email code", "Code sent. Send new in 42s"... */
  requestLabel: (codeRequest: Pick<SensitiveCodeRequest, "codeId" | "isRequesting" | "resendCooldownSeconds">) => string;
  requestDisabled: (codeRequest: Pick<SensitiveCodeRequest, "isRequesting" | "resendCooldownSeconds">) => boolean;
};
