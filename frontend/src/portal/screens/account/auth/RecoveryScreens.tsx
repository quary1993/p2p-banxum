// IP of Webby-Soft SRL.
// 18.5 (Q05, D4) recovery pages opened from the security emails, in the create-account layout:
// - /reset-password: the single-use link + the second factor (or a recovery code) + a new password;
// - /account-recovery: after an assisted recovery and its 24-hour notice, a new password, then a new
//   second factor (the investor is signed in to set it up);
// - /account-recovery/not-me: "This was not me" stops an assisted recovery at once.
// The token is in the fragment and leaves the address bar before any request (audit A-49).
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  v1AuthAccountRecoveryCompleteCreate,
  v1AuthAccountRecoveryNotMeCreate,
  v1AuthPasswordResetCompleteCreate,
  v1AuthPasswordResetStartCreate,
  type FactorStepResponse
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { takeSecurityLinkToken } from "../../../../magicLinkToken";
import { usePortalNav } from "../../../components";
import { supportMailto } from "../accountLinks";
import { AuthCard, AuthLayout, CaCodeField, CaError, CaIcon } from "./AuthLayout";
import { passwordFieldProblems, registerFlowStorageKey, requestErrorText, resumedRegisterStateForUser, writeStoredObject } from "./authState";
import { AuthPasswordField } from "./secondFactor";

type PasswordErrors = { password?: string; repeat?: string };

function NewPasswordFields({
  password,
  repeat,
  onPassword,
  onRepeat,
  errors = {}
}: {
  password: string;
  repeat: string;
  onPassword: (value: string) => void;
  onRepeat: (value: string) => void;
  errors?: PasswordErrors;
}) {
  const t = useT();
  return (
    <div className="ca-fields">
      <AuthPasswordField
        autoComplete="new-password"
        error={errors.password ? t(errors.password) : undefined}
        hint={t("At least 12 characters. A few unrelated words are easy to remember and hard to guess.")}
        id="new-password"
        label={t("New password")}
        onChange={onPassword}
        value={password}
      />
      <AuthPasswordField autoComplete="new-password" error={errors.repeat ? t(errors.repeat) : undefined} id="new-password-repeat" label={t("Repeat password")} onChange={onRepeat} value={repeat} />
    </div>
  );
}

/** The summary above the button names the fields with a problem ("New password: ..."). */
function passwordSummary(errors: PasswordErrors, t: (text: string) => string) {
  return [errors.password ? `${t("New password")}: ${t(errors.password)}` : "", errors.repeat ? `${t("Repeat password")}: ${t(errors.repeat)}` : ""]
    .filter(Boolean)
    .join(" ");
}

function focusPasswordField(errors: PasswordErrors) {
  const id = errors.password ? "new-password" : errors.repeat ? "new-password-repeat" : "";
  if (id) window.setTimeout(() => document.getElementById(id)?.focus(), 0);
}

function LinkNotValid({ title }: { title: string }) {
  const t = useT();
  const nav = usePortalNav();
  return (
    <AuthCard icon="mail" intro={t("This link has expired, was already used or was replaced by a newer one.")} title={title}>
      <button className="ca-primary" onClick={() => nav.go("login")} type="button">
        {t("Back to sign in")}
        <CaIcon name="right" />
      </button>
    </AuthCard>
  );
}

export function ResetPasswordScreen() {
  const t = useT();
  const nav = usePortalNav();
  const [token] = useState(() => (isFixturePreview ? "preview" : takeSecurityLinkToken("/reset-password")));
  const [step, setStep] = useState<FactorStepResponse | null>(
    isFixturePreview ? { status: "factor_required", method: "app", challenge_id: "preview", phone_last_digits: "" } : null
  );
  const [invalid, setInvalid] = useState(!token);
  const [code, setCode] = useState("");
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [passwordErrors, setPasswordErrors] = useState<PasswordErrors>({});
  const started = useRef(false);
  useEffect(() => {
    if (!token || isFixturePreview || started.current) return;
    started.current = true;
    v1AuthPasswordResetStartCreate({ token })
      .then((response) => setStep(response))
      .catch(() => setInvalid(true));
  }, [token]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const problems = passwordFieldProblems(password, repeat);
    setPasswordErrors(problems);
    if (problems.password || problems.repeat) {
      setError(passwordSummary(problems, t));
      focusPasswordField(problems);
      return;
    }
    const needsFactor = step?.status === "factor_required";
    if (needsFactor && !recoveryMode && code.length !== 6) {
      setError(t("Enter the 6-digit code."));
      return;
    }
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    if (!token) return;
    setBusy(true);
    v1AuthPasswordResetCompleteCreate({
      token,
      new_password: password,
      challenge_id: step?.challenge_id ?? "",
      ...(needsFactor ? (recoveryMode ? { recovery_code: recoveryCode } : { code }) : {})
    })
      .then(() => setDone(true))
      .catch((failure: unknown) => {
        setCode("");
        setError(requestErrorText(failure));
      })
      .finally(() => setBusy(false));
  };

  let content;
  if (invalid) {
    content = <LinkNotValid title={t("This link no longer works")} />;
  } else if (done) {
    content = (
      <AuthCard icon="checkCircle" intro={t("Your new password is active. For your security, all devices were signed out.")} success title={t("Password changed")}>
        <button className="ca-primary" onClick={() => nav.go("login")} type="button">
          {t("Sign in")}
          <CaIcon name="right" />
        </button>
      </AuthCard>
    );
  } else if (!step) {
    content = <AuthCard icon="clock" intro={t("We are checking your link.")} title={t("Reset your password")} />;
  } else {
    const sms = step.method === "sms";
    content = (
      <AuthCard
        intro={
          step.status === "factor_required"
            ? sms
              ? t("Confirm it is you with the code we sent by SMS to your phone number ending in {digits}, then choose a new password.", { digits: step.phone_last_digits })
              : t("Confirm it is you with the code from your authenticator app, then choose a new password.")
            : t("Choose a new password.")
        }
        title={t("Set a new password")}
      >
        <form data-testid="reset-password-form" noValidate onSubmit={submit}>
          {step.status === "factor_required" ? (
            recoveryMode ? (
              <div className="ca-fields">
                <div className="ca-field ca-wide">
                  <label htmlFor="reset-recovery">{t("Recovery code")}</label>
                  <input autoComplete="off" id="reset-recovery" maxLength={16} onChange={(event) => setRecoveryCode(event.target.value)} placeholder="XXXXX-XXXXX" value={recoveryCode} />
                </div>
              </div>
            ) : (
              <CaCodeField autoFocus id="reset-code" label={sms ? t("SMS code") : t("Authenticator code")} onChange={setCode} value={code} />
            )
          ) : null}
          <NewPasswordFields errors={passwordErrors} onPassword={(value) => { setPassword(value); setPasswordErrors((current) => ({ ...current, password: undefined })); }} onRepeat={(value) => { setRepeat(value); setPasswordErrors((current) => ({ ...current, repeat: undefined })); }} password={password} repeat={repeat} />
          <CaError>{error || null}</CaError>
          <button className="ca-primary" disabled={busy} type="submit">
            {busy ? t("Saving...") : t("Save new password")}
            <CaIcon name="right" />
          </button>
        </form>
        {step.status === "factor_required" ? (
          <div className="ca-action-row">
            <button className="ca-text-button" onClick={() => setRecoveryMode(!recoveryMode)} type="button">
              {recoveryMode ? t("Use the code instead") : t("Use a recovery code")}
            </button>
          </div>
        ) : null}
        <p className="ca-quiet-note">
          {t("Lost your phone and your recovery codes?")} <a href={supportMailto({ subject: t("Account recovery") })}>{t("Contact support")}</a>
        </p>
      </AuthCard>
    );
  }
  return <AuthLayout>{content}</AuthLayout>;
}

export function AccountRecoveryScreen({ notMe = false }: { notMe?: boolean }) {
  const t = useT();
  const nav = usePortalNav();
  const [token] = useState(() => (isFixturePreview ? "preview" : takeSecurityLinkToken(notMe ? "/account-recovery/not-me" : "/account-recovery")));
  const [state, setState] = useState<"form" | "stopping" | "stopped" | "invalid">(token ? (notMe ? "stopping" : "form") : "invalid");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [passwordErrors, setPasswordErrors] = useState<PasswordErrors>({});
  const started = useRef(false);
  useEffect(() => {
    if (!notMe || !token || started.current) return;
    started.current = true;
    if (isFixturePreview) {
      setState("stopped");
      return;
    }
    v1AuthAccountRecoveryNotMeCreate({ token })
      .then(() => setState("stopped"))
      .catch(() => setState("invalid"));
  }, [notMe, token]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const problems = passwordFieldProblems(password, repeat);
    setPasswordErrors(problems);
    if (problems.password || problems.repeat) {
      setError(passwordSummary(problems, t));
      focusPasswordField(problems);
      return;
    }
    if (isFixturePreview) {
      nav.go("dashboard");
      return;
    }
    if (!token) return;
    setBusy(true);
    v1AuthAccountRecoveryCompleteCreate({ token, new_password: password })
      .then((response) => {
        window.history.replaceState({}, "", "/");
        const resume = resumedRegisterStateForUser(response.user);
        if (resume) {
          writeStoredObject(registerFlowStorageKey, resume);
          nav.go("register");
          return;
        }
        // The investor portal asks for the new second factor before anything else.
        nav.go("dashboard");
      })
      .catch((failure: unknown) => setError(requestErrorText(failure)))
      .finally(() => setBusy(false));
  };

  let content;
  if (state === "invalid") {
    content = <LinkNotValid title={t("This link no longer works")} />;
  } else if (state === "stopping") {
    content = <AuthCard icon="clock" intro={t("One moment, please.")} title={t("Stopping the recovery")} />;
  } else if (state === "stopped") {
    content = (
      <AuthCard icon="shield" intro={t("We stopped the recovery of your account. Our support team will contact you. Nothing else changed in your account.")} title={t("Recovery stopped")}>
        <a className="ca-secondary" href={supportMailto({ subject: t("Account recovery stopped") })}>{t("Contact support")}</a>
      </AuthCard>
    );
  } else {
    content = (
      <AuthCard intro={t("Choose a new password. Then you set up your new second factor.")} title={t("Finish the recovery of your account")}>
        <form data-testid="account-recovery-form" noValidate onSubmit={submit}>
          <NewPasswordFields errors={passwordErrors} onPassword={(value) => { setPassword(value); setPasswordErrors((current) => ({ ...current, password: undefined })); }} onRepeat={(value) => { setRepeat(value); setPasswordErrors((current) => ({ ...current, repeat: undefined })); }} password={password} repeat={repeat} />
          <CaError>{error || null}</CaError>
          <button className="ca-primary" disabled={busy} type="submit">
            {busy ? t("Saving...") : t("Continue")}
            <CaIcon name="right" />
          </button>
        </form>
        <p className="ca-quiet-note">{t("For 72 hours after the recovery you cannot add a bank account or change your default return account. Withdrawals to your verified accounts still work.")}</p>
      </AuthCard>
    );
  }
  return <AuthLayout>{content}</AuthLayout>;
}
