// IP of Webby-Soft SRL.
// After sign-in, an account without a PIN (every account created before ACC-DEC-009) creates it here
// before the investor area opens (design: the create-account module's PIN screen). Outside
// registration the PIN needs a fresh email code. Password + second factor for existing accounts comes
// with Phase 17.3 (U33-DEC-29 "Security for existing accounts").
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useCreatePinFlow } from "../../../../investorPortal/pinFlows";
import { usePinStatus } from "../../../../investorPortal/pinState";
import { emailCodeLabel } from "../parts/format";
import { AuthCard, AuthLayout, CaCodeField, CaError, CaIcon } from "./AuthLayout";

function PinGateForm({ requiresEmailCode, onCreated }: { requiresEmailCode: boolean; onCreated: () => void }) {
  const t = useT();
  const flow = useCreatePinFlow({ requiresEmailCode, onSaved: onCreated });
  const pinError = flow.weakness ?? (flow.confirmationError || (flow.mismatch ? "The two PINs do not match." : ""));
  return (
    <form
      data-form="pin"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (flow.ready && !flow.saving) flow.save();
      }}
    >
      <CaCodeField autoFocus id="gate-pin" label={t("6-digit PIN")} masked onChange={flow.setPin} value={flow.pin} />
      <CaCodeField id="gate-pin-repeat" label={t("Confirm PIN")} masked onChange={flow.setConfirmation} value={flow.confirmation} />
      <p className="ca-field-note">{t("Avoid repeated digits or simple sequences.")}</p>
      {requiresEmailCode ? (
        <div className="ca-fields acc-email-code">
          <div className="ca-field ca-wide">
            <div className="acc-ca-label-row">
              <label htmlFor="gate-email-code">{t("Email confirmation code")}</label>
              <button className="ca-text-button" disabled={flow.emailCode.disabled} onClick={flow.emailCode.send} type="button">{emailCodeLabel(t, flow.emailCode)}</button>
            </div>
            <input
              autoComplete="one-time-code"
              id="gate-email-code"
              inputMode="numeric"
              maxLength={6}
              onChange={(event) => flow.setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              value={flow.code}
            />
            {isFixturePreview ? <p className="ca-field-note">{t("Demo: any 6 digits")}</p> : null}
          </div>
        </div>
      ) : null}
      <CaError>
        {pinError
          ? t(pinError)
          : flow.emailCode.error
            ? t("Could not send the email code: {reason}", { reason: flow.emailCode.error })
            : flow.error ? t("Could not save your PIN: {reason}", { reason: flow.error }) : null}
      </CaError>
      <button className="ca-primary ca-positive" disabled={!flow.ready || flow.saving} type="submit">
        {flow.saving ? t("Saving PIN...") : t("Save PIN & continue")}
        <CaIcon name="right" />
      </button>
    </form>
  );
}

export function PinGateScreen({
  onCreated,
  onSignOut,
  signOutError,
  signOutLabel
}: {
  onCreated: () => void;
  onSignOut: () => void;
  signOutError: string;
  signOutLabel: string;
}) {
  const t = useT();
  const { status, isLoading, query } = usePinStatus();
  return (
    <AuthLayout>
      <AuthCard
        icon="lock"
        intro={t("Before you continue: you will enter this PIN with an email code for every investment, withdrawal and bank account change.")}
        title={t("Create your security PIN")}
      >
        {isLoading ? (
          <p className="ca-email-note" role="status">{t("Loading...")}</p>
        ) : query.isError && !isFixturePreview ? (
          <>
            <CaError>{t("Could not load your account. Check your connection and try again.")}</CaError>
            <button className="ca-secondary" onClick={() => void query.refetch()} type="button">{t("Retry")}</button>
          </>
        ) : (
          <PinGateForm onCreated={onCreated} requiresEmailCode={status?.setup_requires_email_code ?? true} />
        )}
        <div className="ca-action-row">
          <button className="ca-text-button" onClick={onSignOut} type="button">{signOutLabel}</button>
        </div>
        {signOutError ? <CaError>{t("Could not sign out: {reason}", { reason: signOutError })}</CaError> : null}
      </AuthCard>
    </AuthLayout>
  );
}
