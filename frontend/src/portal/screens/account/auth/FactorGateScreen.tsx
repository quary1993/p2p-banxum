// IP of Webby-Soft SRL.
// 18.5: a signed-in account without a second factor (after an assisted recovery, or an account made
// before 18.5) sets one up here before the investor area opens (design onboarding "Protect your
// account", plus the SMS choice). Then the 10 recovery codes; an SMS investor then creates the PIN
// (PIN gate), an app investor needs none (D-1).
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  getV1AuthMeRetrieveQueryKey,
  getV1AuthPinStatusRetrieveQueryKey,
  useV1AuthPhoneConfirmCreate,
  useV1AuthPhoneRequestCreate
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { retryAfter, useSecondsLeft } from "../../../../investorPortal/pinFlows";
import { AuthCard, AuthLayout, CaCodeField, CaError, CaIcon } from "./AuthLayout";
import { requestErrorText } from "./authState";
import { AuthenticatorSetup, FactorChoice, RecoveryCodesStep } from "./secondFactor";

/** SMS factor: a code to the registered mobile number verifies it. */
export function SmsFactorSetup({ onDone }: { onDone: () => void }) {
  const t = useT();
  const requestMutation = useV1AuthPhoneRequestCreate();
  const confirmMutation = useV1AuthPhoneConfirmCreate();
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const cooldown = useSecondsLeft(cooldownUntil);
  const [error, setError] = useState("");
  const send = () => {
    setError("");
    if (isFixturePreview) {
      setChallengeId("preview");
      setCooldownUntil(Date.now() + 60_000);
      return;
    }
    requestMutation.mutate(
      {},
      {
        onSuccess: (response) => {
          if (response.phone_verified) {
            onDone();
            return;
          }
          setChallengeId(response.challenge_id);
          setCooldownUntil(Date.now() + 60_000);
        },
        onError: (failure) => {
          const wait = retryAfter(failure);
          if (wait) setCooldownUntil(Date.now() + wait * 1000);
          setError(requestErrorText(failure));
        }
      }
    );
  };
  const confirm = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (code.length !== 6) {
      setError(t("Enter the six-digit SMS code."));
      return;
    }
    if (isFixturePreview) {
      onDone();
      return;
    }
    if (!challengeId) return;
    confirmMutation.mutate(
      { data: { challenge_id: challengeId, code } },
      { onSuccess: () => onDone(), onError: (failure) => setError(requestErrorText(failure)) }
    );
  };
  if (!challengeId) {
    return (
      <>
        <p className="ca-email-note">{t("We send a six-digit code to the mobile number of your account.")}</p>
        <CaError>{error || null}</CaError>
        <button className="ca-primary" disabled={requestMutation.isPending || cooldown > 0} onClick={send} type="button">
          {requestMutation.isPending ? t("Sending...") : cooldown > 0 ? t("Resend in {seconds}s", { seconds: cooldown }) : t("Send SMS code")}
          <CaIcon name="right" />
        </button>
      </>
    );
  }
  return (
    <form data-form="sms-factor" noValidate onSubmit={confirm}>
      <CaCodeField autoFocus id="factor-sms" label={t("SMS code")} onChange={(value) => { setCode(value); setError(""); }} value={code} />
      {isFixturePreview ? <p className="ca-field-note">{t("Demo: enter any 6 digits.")}</p> : null}
      <CaError>{error || null}</CaError>
      <button className="ca-primary ca-positive" disabled={confirmMutation.isPending} type="submit">
        {confirmMutation.isPending ? t("Verifying...") : t("Verify phone")}
        <CaIcon name="right" />
      </button>
      <div className="ca-action-row">
        <button className="ca-text-button" disabled={requestMutation.isPending || cooldown > 0} onClick={send} type="button">
          {cooldown > 0 ? t("Resend in {seconds}s", { seconds: cooldown }) : t("Resend code")}
        </button>
      </div>
    </form>
  );
}

export function FactorGateScreen({
  onSignOut,
  signOutError,
  signOutLabel,
  onDone
}: {
  onSignOut: () => void;
  signOutError: string;
  signOutLabel: string;
  onDone: (factor: "app" | "sms") => void;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const [factor, setFactor] = useState<"app" | "sms">("app");
  const [step, setStep] = useState<"choose" | "app" | "sms" | "codes">("choose");
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: getV1AuthMeRetrieveQueryKey() });
    void queryClient.invalidateQueries({ queryKey: getV1AuthPinStatusRetrieveQueryKey() });
  };
  const factorDone = () => setStep("codes");
  const title =
    step === "codes" ? t("Save your recovery codes") : step === "app" ? t("Protect your account") : step === "sms" ? t("Verify your mobile number") : t("Protect your account");
  const intro =
    step === "codes"
      ? t("Use one of these codes if you lose your phone. Each code works once. Store them where only you can find them.")
      : step === "app"
        ? t("Install an authenticator app, scan the code with it, then enter the 6-digit code.")
        : step === "sms"
          ? t("Your phone becomes the second factor of your account.")
          : t("Two-factor authentication is required. You need it to sign in, to invest and to change your bank account.");
  return (
    <AuthLayout>
      <AuthCard icon="shield" intro={intro} title={title}>
        {step === "choose" ? <FactorChoice onChoose={(choice) => { setFactor(choice); setStep(choice); }} phoneLabel="" /> : null}
        {step === "app" ? <AuthenticatorSetup onDone={factorDone} /> : null}
        {step === "sms" ? <SmsFactorSetup onDone={factorDone} /> : null}
        {step === "codes" ? (
          <RecoveryCodesStep
            onDone={() => {
              refresh();
              onDone(factor);
            }}
          />
        ) : null}
        {step === "app" || step === "sms" ? (
          <div className="ca-action-row">
            <button className="ca-text-button" onClick={() => setStep("choose")} type="button">{t("Choose another method")}</button>
          </div>
        ) : null}
        <div className="ca-action-row">
          <button className="ca-text-button" onClick={onSignOut} type="button">{signOutLabel}</button>
        </div>
        {signOutError ? <CaError>{t("Could not sign out: {reason}", { reason: signOutError })}</CaError> : null}
      </AuthCard>
    </AuthLayout>
  );
}
