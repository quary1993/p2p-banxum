// IP of Webby-Soft SRL.
// Small display helpers of the account screens (no components, so fast refresh keeps working).
import type { FlowEmailCode } from "../../../../investorPortal/pinFlows";
import type { t as translate } from "../../../../i18n";

/** "CH93 0076 2011 6238 5295 7": an IBAN in groups of four, as the design shows it. */
export function formatIban(iban: string) {
  return iban.replace(/\s+/g, "").replace(/(.{4})/g, "$1 ").trim();
}

/** The send/resend label of an email code, with the cooldown. */
export function emailCodeLabel(t: typeof translate, code: Pick<FlowEmailCode, "isSending" | "cooldown" | "codeId">) {
  if (code.isSending) return t("Sending code...");
  if (code.cooldown > 0) {
    return code.codeId
      ? t("Code sent. Send new in {seconds}s", { seconds: code.cooldown })
      : t("Send new in {seconds}s", { seconds: code.cooldown });
  }
  return code.codeId ? t("Send a new email code") : t("Send email code");
}

/** "your PIN" or "the code from your authenticator app" (D-1), for the dialog intros. */
export function factorPhrase(t: (text: string) => string, pin: { factor: string }) {
  return pin.factor === "app" ? t("the code from your authenticator app") : t("your PIN");
}
