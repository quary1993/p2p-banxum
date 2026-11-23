// IP of Webby-Soft SRL.
// Sign-in (design: views.login, views.loginCode and views.forgot of the U33 prototype, in the
// create-account layout; the design's texts "Welcome back", "Email", "Log in"). 18.5 (U33-DEC-01): email and password, then the second factor: the code of
// the authenticator app or an SMS code to the verified phone (no passkeys, D-2); a recovery code
// replaces either. "Remember this browser" skips the code for 30 days (the password is still asked).
// A wrong email or password gets one answer (no account enumeration, U33-DEC-29).
// The registration link (token in the URL fragment, removed from the address bar by App, audit A-49)
// confirms the email address and continues the registration while the account has no factor.
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  useV1AuthLoginCreate,
  useV1AuthLoginResendSmsCreate,
  useV1AuthLoginVerifyCreate,
  useV1AuthPasswordForgotCreate,
  v1AuthRegisterConfirmEmailCreate,
  type UserSummary
} from "../../../../api/generated/banxumApi";
import { ApiClientError } from "../../../../api/client/httpClient";
import { clearSessionExpiredNotice, hasSessionExpiredNotice } from "../../../../api/client/sessionExpiry";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { retryAfter, useSecondsLeft } from "../../../../investorPortal/pinFlows";
import { takePendingMagicLinkToken } from "../../../../magicLinkToken";
import { brandDisplayName } from "../../../brand";
import { PortalLink, usePortalNav } from "../../../components";
import { supportMailto } from "../accountLinks";
import { AuthCard, AuthLayout, CaCodeField, CaError, CaIcon, Recipient } from "./AuthLayout";
import {
  blockedAccountStatusFromError,
  loginFlowStorageKey,
  registerFlowStorageKey,
  removeStoredObject,
  requestErrorText,
  resumedRegisterStateForUser,
  writeStoredObject
} from "./authState";
import { AuthPasswordField } from "./secondFactor";

type Mode = "password" | "code" | "forgot" | "forgotSent" | "consuming" | "blocked" | "linkExpired";
type Challenge = { id: string; method: string; phoneDigits: string };

function errorCode(error: unknown) {
  if (!(error instanceof ApiClientError) || !error.payload || typeof error.payload !== "object") return "";
  const code = (error.payload as { code?: unknown }).code;
  return typeof code === "string" ? code : "";
}

export function LoginScreen() {
  const t = useT();
  const nav = usePortalNav();
  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [code, setCode] = useState("");
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [trustDevice, setTrustDevice] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(hasSessionExpiredNotice);
  const [resendUntil, setResendUntil] = useState(0);
  const [error, setError] = useState("");
  const loginMutation = useV1AuthLoginCreate();
  const verifyMutation = useV1AuthLoginVerifyCreate();
  const resendMutation = useV1AuthLoginResendSmsCreate();
  const forgotMutation = useV1AuthPasswordForgotCreate();
  const resendSeconds = useSecondsLeft(resendUntil);
  const navRef = useRef(nav);
  useEffect(() => {
    navRef.current = nav;
  });

  /** Signed in: the registration continues where it stopped, otherwise the Overview. */
  const continueAs = (user: UserSummary | null | undefined) => {
    removeStoredObject(loginFlowStorageKey);
    clearSessionExpiredNotice();
    const resume = user ? resumedRegisterStateForUser(user) : null;
    if (resume) {
      writeStoredObject(registerFlowStorageKey, resume);
      navRef.current.go("register");
      return;
    }
    removeStoredObject(registerFlowStorageKey);
    navRef.current.go("dashboard");
  };
  const continueRef = useRef(continueAs);
  useEffect(() => {
    continueRef.current = continueAs;
  });

  // The registration link: single use, so one request even when the effect runs twice (StrictMode).
  const consumeAttemptedRef = useRef(false);
  useEffect(() => {
    let mounted = true;
    const token = consumeAttemptedRef.current ? null : takePendingMagicLinkToken();
    if (!token || isFixturePreview) return () => {
      mounted = false;
    };
    consumeAttemptedRef.current = true;
    setMode("consuming");
    void v1AuthRegisterConfirmEmailCreate({ token })
      .then((response) => {
        if (!mounted) return;
        window.history.replaceState({}, "", "/");
        continueRef.current(response.user);
      })
      .catch((failure: unknown) => {
        if (!mounted) return;
        if (blockedAccountStatusFromError(failure)) {
          setMode("blocked");
          return;
        }
        setMode("linkExpired");
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleSignInError = (failure: unknown) => {
    if (blockedAccountStatusFromError(failure)) {
      setMode("blocked");
      return;
    }
    const wait = retryAfter(failure);
    if (errorCode(failure) === "email_not_confirmed") {
      setError(t("Confirm your email address first: open the link we sent you. We sent the link again."));
      return;
    }
    setError(wait ? t("Too many attempts. Try again in {seconds} seconds.", { seconds: wait }) : requestErrorText(failure));
  };

  const submitPassword = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!email.includes("@") || !password) {
      setError(t("Enter your email address and your password."));
      return;
    }
    if (isFixturePreview) {
      setChallenge({ id: "preview", method: "sms", phoneDigits: "00" });
      setMode("code");
      return;
    }
    loginMutation.mutate(
      { data: { email: email.trim(), password } },
      {
        onSuccess: (response) => {
          setPassword("");
          setSessionExpired(false);
          if (response.status === "factor_required") {
            setChallenge({ id: response.challenge_id, method: response.method, phoneDigits: response.phone_last_digits });
            setCode("");
            setRecoveryMode(false);
            setRecoveryCode("");
            if (response.method === "sms") setResendUntil(Date.now() + 60_000);
            setMode("code");
            return;
          }
          continueRef.current(response.user);
        },
        onError: handleSignInError
      }
    );
  };

  const submitCode = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!recoveryMode && code.length !== 6) {
      setError(t("Enter the 6-digit code."));
      return;
    }
    if (recoveryMode && recoveryCode.replace(/[^a-z0-9]/gi, "").length !== 10) {
      setError(t("Enter one of your recovery codes."));
      return;
    }
    if (isFixturePreview) {
      continueRef.current(null);
      return;
    }
    if (!challenge) return;
    verifyMutation.mutate(
      {
        data: recoveryMode
          ? { challenge_id: challenge.id, recovery_code: recoveryCode, trust_device: trustDevice }
          : { challenge_id: challenge.id, code, trust_device: trustDevice }
      },
      {
        onSuccess: (response) => continueRef.current(response.user),
        onError: (failure) => {
          setCode("");
          if (["challenge_expired", "challenge_attempts"].includes(errorCode(failure)) || (failure instanceof ApiClientError && failure.status === 429)) {
            setMode("password");
            setChallenge(null);
          }
          handleSignInError(failure);
        }
      }
    );
  };

  const resendSms = () => {
    if (!challenge || resendSeconds > 0) return;
    setError("");
    resendMutation.mutate(
      { data: { challenge_id: challenge.id } },
      {
        onSuccess: () => setResendUntil(Date.now() + 60_000),
        onError: (failure) => {
          const wait = retryAfter(failure);
          if (wait) setResendUntil(Date.now() + wait * 1000);
          setError(requestErrorText(failure));
        }
      }
    );
  };

  const submitForgot = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!email.includes("@")) {
      setError(t("Enter a valid email address."));
      return;
    }
    if (isFixturePreview) {
      setMode("forgotSent");
      return;
    }
    forgotMutation.mutate(
      { data: { email: email.trim() } },
      {
        onSuccess: () => setMode("forgotSent"),
        onError: (failure) => setError(requestErrorText(failure))
      }
    );
  };

  const backToSignIn = () => {
    setMode("password");
    setChallenge(null);
    setCode("");
    setRecoveryCode("");
    setRecoveryMode(false);
    setError("");
  };

  let content;
  if (mode === "consuming") {
    content = <AuthCard icon="clock" intro={t("We are checking your link.")} title={t("Signing you in")} />;
  } else if (mode === "blocked") {
    content = (
      <AuthCard icon="shield" intro={t("You cannot sign in right now. Contact support for help with the next step.")} title={t("We need to review your account")}>
        <a className="ca-primary" href={supportMailto({ subject: t("Sign-in") })}>
          {t("Contact support")}
          <CaIcon name="right" />
        </a>
      </AuthCard>
    );
  } else if (mode === "linkExpired") {
    content = (
      <AuthCard icon="mail" intro={t("This link has expired or was already used. Sign in with your email address and password: if your email is not confirmed yet, we send a new link.")} title={t("This link no longer works")}>
        <button className="ca-primary" onClick={backToSignIn} type="button">
          {t("Sign in")}
          <CaIcon name="right" />
        </button>
      </AuthCard>
    );
  } else if (mode === "forgot") {
    content = (
      <AuthCard intro={t("We send a link to your email address if it belongs to an account.")} title={t("Reset your password")}>
        <form data-testid="forgot-password-form" noValidate onSubmit={submitForgot}>
          <div className="ca-fields">
            <div className="ca-field ca-wide">
              <label htmlFor="forgot-email">{t("Email address")}</label>
              <input autoComplete="email" autoFocus id="forgot-email" maxLength={120} onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
            </div>
          </div>
          <CaError>{error || null}</CaError>
          <div className="acc-auth-submit">
            <button className="ca-primary" disabled={forgotMutation.isPending} type="submit">
              {forgotMutation.isPending ? t("Sending...") : t("Send link")}
              <CaIcon name="right" />
            </button>
          </div>
        </form>
        <div className="ca-action-row">
          <button className="ca-text-button" onClick={backToSignIn} type="button">{t("Back to sign in")}</button>
        </div>
      </AuthCard>
    );
  } else if (mode === "forgotSent") {
    content = (
      <AuthCard icon="mail" intro={t("If the address belongs to an account, the link is on its way. It works once and for 30 minutes. You also need your second factor.")} title={t("Check your email")}>
        <Recipient icon="mail" label={t("Email address")} value={email} />
        <div className="ca-action-row">
          <button className="ca-text-button" onClick={backToSignIn} type="button">{t("Back to sign in")}</button>
        </div>
      </AuthCard>
    );
  } else if (mode === "code" && challenge) {
    const sms = challenge.method === "sms";
    content = (
      <AuthCard
        intro={
          recoveryMode
            ? t("Enter one of the 10 recovery codes you saved. Each code works once.")
            : sms
              ? challenge.phoneDigits
                ? t("Enter the 6-digit code we sent by SMS to your phone number ending in {digits}.", { digits: challenge.phoneDigits })
                : t("Enter the 6-digit code we sent by SMS to your phone.")
              : t("Enter the 6-digit code from your authenticator app.")
        }
        title={t("Two-factor authentication")}
      >
        <form data-testid="login-code-form" noValidate onSubmit={submitCode}>
          {recoveryMode ? (
            <div className="ca-fields">
              <div className="ca-field ca-wide">
                <label htmlFor="login-recovery">{t("Recovery code")}</label>
                <input autoComplete="off" autoFocus id="login-recovery" maxLength={16} onChange={(event) => setRecoveryCode(event.target.value)} placeholder="XXXXX-XXXXX" value={recoveryCode} />
              </div>
            </div>
          ) : (
            <>
              <CaCodeField autoFocus id="login-code" label={sms ? t("SMS code") : t("Authenticator code")} onChange={(value) => { setCode(value); setError(""); }} value={code} />
              <p className="ca-field-note">{isFixturePreview ? t("Demo: any 6 digits work.") : sms ? t("The code works for 10 minutes.") : t("Enter the 6 digits shown in your app.")}</p>
            </>
          )}
          <label className="ca-checkbox acc-trust">
            <input checked={trustDevice} onChange={(event) => setTrustDevice(event.target.checked)} type="checkbox" />
            <span>{t("Remember this browser for 30 days. Use this only on your own device: you still enter your password.")}</span>
          </label>
          <CaError>{error || null}</CaError>
          <button className="ca-primary" disabled={verifyMutation.isPending} type="submit">
            {verifyMutation.isPending ? t("Checking...") : t("Continue")}
            <CaIcon name="right" />
          </button>
        </form>
        <div className="ca-action-row">
          <button className="ca-text-button" onClick={() => { setRecoveryMode(!recoveryMode); setError(""); }} type="button">
            {recoveryMode ? t("Use the code instead") : t("Use a recovery code")}
          </button>
          {sms && !recoveryMode ? (
            <button className="ca-text-button" disabled={resendMutation.isPending || resendSeconds > 0} onClick={resendSms} type="button">
              {resendSeconds > 0 ? t("Resend in {seconds}s", { seconds: resendSeconds }) : t("Resend SMS")}
            </button>
          ) : null}
          <button className="ca-text-button" onClick={backToSignIn} type="button">{t("Back")}</button>
        </div>
        <p className="ca-quiet-note">{t("Lost your phone and your recovery codes? Contact support: we verify your identity before we change anything.")}</p>
      </AuthCard>
    );
  } else {
    content = (
      <AuthCard title={t("Welcome back")}>
        <form data-testid="login-password-form" noValidate onSubmit={submitPassword}>
          {sessionExpired ? (
            <div className="ca-notice" role="status">
              <CaIcon name="clock" />
              <span><strong>{t("Your session has expired")}</strong> {t("Please sign in again to continue.")}</span>
            </div>
          ) : null}
          <div className="ca-fields">
            <div className="ca-field ca-wide">
              <label htmlFor="login-email">{t("Email")}</label>
              <input autoComplete="username" id="login-email" maxLength={120} name="email" onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" type="email" value={email} />
            </div>
            <AuthPasswordField
              aside={<button onClick={() => { setMode("forgot"); setError(""); }} type="button">{t("Forgot password?")}</button>}
              id="login-password"
              label={t("Password")}
              onChange={setPassword}
              value={password}
            />
          </div>
          <CaError>{error ? t("Could not sign in: {reason}", { reason: error }) : null}</CaError>
          <div className="acc-auth-submit">
            <button className="ca-primary" disabled={loginMutation.isPending} type="submit">
              {loginMutation.isPending ? t("Logging in...") : t("Log in")}
              <CaIcon name="right" />
            </button>
          </div>
        </form>
        <p className="ca-foot-link">
          {t("New to {brand}?", { brand: brandDisplayName() })}{" "}
          <PortalLink to="register">{t("Create an account")}</PortalLink>
        </p>
      </AuthCard>
    );
  }

  return <AuthLayout>{content}</AuthLayout>;
}
