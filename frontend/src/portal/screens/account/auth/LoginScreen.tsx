// IP of Webby-Soft SRL.
// Sign-in (design: the create-account module's "Welcome back / Send sign-in link" screen). Today's
// login is a magic link (ACC-DEC-001 until Phase 17.3 brings password + second factor, U33-DEC-01).
// The answer never says whether an account exists for the address (U33-DEC-29). The single-use token
// arrives in the URL fragment; App has already removed it from the address bar (audit A-49).
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useV1AuthMagicLinkRequestCreate, v1AuthMagicLinkConsumeCreate } from "../../../../api/generated/banxumApi";
import { ApiClientError } from "../../../../api/client/httpClient";
import { clearSessionExpiredNotice, hasSessionExpiredNotice } from "../../../../api/client/sessionExpiry";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { retryAfter, useSecondsLeft } from "../../../../investorPortal/pinFlows";
import { takePendingMagicLinkToken } from "../../../../magicLinkToken";
import { brandDisplayName } from "../../../brand";
import { PortalLink, usePortalNav } from "../../../components";
import { supportMailto } from "../accountLinks";
import { AuthCard, AuthLayout, CaError, CaIcon, Recipient } from "./AuthLayout";
import {
  blockedAccountStatusFromError,
  loginFlowStorageKey,
  readStoredObject,
  registerFlowStorageKey,
  removeStoredObject,
  requestErrorText,
  resumedRegisterStateForUser,
  writeStoredObject,
  type LoginFlowState
} from "./authState";

export function LoginScreen() {
  const t = useT();
  const nav = usePortalNav();
  const [initial] = useState(() =>
    readStoredObject<LoginFlowState>(loginFlowStorageKey, { email: "", sent: false, linkExpired: false, resendCooldownUntil: 0, editingEmail: false })
  );
  const [email, setEmail] = useState(initial.email);
  const [sent, setSent] = useState(initial.sent);
  const [linkExpired, setLinkExpired] = useState(initial.linkExpired);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(initial.resendCooldownUntil);
  const [editingEmail, setEditingEmail] = useState(initial.editingEmail || !initial.email);
  const [focusEmailField, setFocusEmailField] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(hasSessionExpiredNotice);
  const [isConsuming, setIsConsuming] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState("");
  const magicLinkRequest = useV1AuthMagicLinkRequestCreate();
  const resendCooldownSeconds = useSecondsLeft(resendCooldownUntil);
  const navRef = useRef(nav);
  useEffect(() => {
    navRef.current = nav;
  });

  useEffect(() => {
    writeStoredObject(loginFlowStorageKey, { email, sent, linkExpired, resendCooldownUntil, editingEmail });
  }, [editingEmail, email, linkExpired, resendCooldownUntil, sent]);

  const consumeAttemptedRef = useRef(false);
  const mountedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    const token = consumeAttemptedRef.current ? null : takePendingMagicLinkToken();
    // The token is single-use: never fire a second consume request, even if the effect re-runs
    // (React StrictMode's development effect replay).
    if (!token || isFixturePreview || consumeAttemptedRef.current) {
      return () => {
        mountedRef.current = false;
      };
    }
    consumeAttemptedRef.current = true;
    setIsConsuming(true);
    void v1AuthMagicLinkConsumeCreate({ token })
      .then((response) => {
        if (!mountedRef.current) return;
        removeStoredObject(loginFlowStorageKey);
        clearSessionExpiredNotice();
        window.history.replaceState({}, "", "/");
        const resume = resumedRegisterStateForUser(response.user);
        if (resume) {
          writeStoredObject(registerFlowStorageKey, resume);
          navRef.current.go("register");
          return;
        }
        removeStoredObject(registerFlowStorageKey);
        navRef.current.go("dashboard");
      })
      .catch((mutationError: unknown) => {
        if (!mountedRef.current) return;
        const blockedStatus = blockedAccountStatusFromError(mutationError);
        if (blockedStatus || (mutationError instanceof ApiClientError && mutationError.status === 400)) {
          const url = new URL(window.location.href);
          url.searchParams.delete("token");
          window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
          setError("");
          if (blockedStatus) {
            // A valid link of a restricted or locked account: sign-in is refused, support helps.
            setBlocked(true);
            return;
          }
          setLinkExpired(true);
          return;
        }
        setError(requestErrorText(mutationError));
      })
      .finally(() => {
        if (mountedRef.current) setIsConsuming(false);
      });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const markLinkSent = () => {
    setSent(true);
    setLinkExpired(false);
    setEditingEmail(false);
    setResendCooldownUntil(Date.now() + 60_000);
    clearSessionExpiredNotice();
    setSessionExpired(false);
  };

  const requestMagicLink = () => {
    if (!email.includes("@") || magicLinkRequest.isPending || resendCooldownSeconds > 0) return;
    setError("");
    if (isFixturePreview) {
      markLinkSent();
      return;
    }
    magicLinkRequest.mutate(
      { data: { email } },
      {
        onSuccess: markLinkSent,
        onError: (mutationError) => {
          const waitSeconds = retryAfter(mutationError);
          if (waitSeconds) setResendCooldownUntil(Date.now() + waitSeconds * 1000);
          setError(requestErrorText(mutationError));
        }
      }
    );
  };

  const resetLoginFlow = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    removeStoredObject(loginFlowStorageKey);
    setEmail("");
    setSent(false);
    setLinkExpired(false);
    setEditingEmail(false);
    setResendCooldownUntil(0);
    setError("");
  };

  // On the expired-link screen: keep the screen and ask for another address.
  const switchToDifferentEmail = () => {
    setEmail("");
    setEditingEmail(true);
    setFocusEmailField(true);
    setResendCooldownUntil(0);
    setError("");
  };

  const resendLabel = magicLinkRequest.isPending
    ? t("Sending...")
    : resendCooldownSeconds > 0
      ? t("Link sent. Send new in {seconds}s", { seconds: resendCooldownSeconds })
      : t("Send a new link");
  const resendDisabled = !email.includes("@") || magicLinkRequest.isPending || resendCooldownSeconds > 0;

  function submit(event: FormEvent) {
    event.preventDefault();
    requestMagicLink();
  }

  const emailField = (autoFocus: boolean) => (
    <div className="ca-fields">
      <div className="ca-field ca-wide">
        <label htmlFor="login-email">{t("Email address")}</label>
        <input
          autoComplete="email"
          autoFocus={autoFocus}
          id="login-email"
          maxLength={120}
          name="email"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          type="email"
          value={email}
        />
      </div>
    </div>
  );

  let content;
  if (isConsuming) {
    content = <AuthCard icon="clock" intro={t("We are checking your sign-in link.")} title={t("Signing you in")} />;
  } else if (blocked) {
    content = (
      <AuthCard icon="shield" intro={t("You cannot sign in right now. Contact support for help with the next step.")} title={t("We need to review your account")}>
        <a className="ca-primary" href={supportMailto({ subject: t("Sign-in") })}>
          {t("Contact support")}
          <CaIcon name="right" />
        </a>
      </AuthCard>
    );
  } else if (linkExpired) {
    content = (
      <AuthCard icon="mail" intro={t("This sign-in link has expired or is no longer valid. Request a new link to continue.")} title={t("Your sign-in link has expired")}>
        <form data-testid="login-expired-form" noValidate onSubmit={submit}>
          {editingEmail ? emailField(focusEmailField) : <Recipient icon="mail" label={t("We will send the new link to")} value={email} />}
          <CaError>{error ? t("Could not send a new link: {reason}", { reason: error }) : null}</CaError>
          <button className="ca-primary" disabled={resendDisabled} type="submit">
            {resendLabel}
            <CaIcon name="right" />
          </button>
        </form>
        {editingEmail ? null : (
          <div className="ca-action-row">
            <button className="ca-text-button" onClick={switchToDifferentEmail} type="button">{t("Use a different email address")}</button>
          </div>
        )}
        <p className="ca-quiet-note">{t("Lost access to your email? Contact support: we verify your identity before we change anything.")}</p>
      </AuthCard>
    );
  } else if (!sent) {
    content = (
      <AuthCard intro={t("Enter your email to receive a sign-in link.")} title={t("Welcome back")}>
        <form data-testid="login-magic-link-form" noValidate onSubmit={submit}>
          {sessionExpired ? (
            <div className="ca-notice" role="status">
              <CaIcon name="clock" />
              <span><strong>{t("Your session has expired")}</strong> {t("Please sign in again to continue.")}</span>
            </div>
          ) : null}
          {emailField(false)}
          <CaError>{error ? t("Could not continue: {reason}", { reason: error }) : null}</CaError>
          <div className="acc-auth-submit">
            <button className="ca-primary" disabled={!email.includes("@") || magicLinkRequest.isPending} type="submit">
              {magicLinkRequest.isPending ? t("Sending...") : t("Send sign-in link")}
              <CaIcon name="right" />
            </button>
          </div>
        </form>
        <p className="ca-foot-link">
          {t("New to {brand}?", { brand: brandDisplayName() })}
          <PortalLink to="register">{t("Create an account")}</PortalLink>
        </p>
      </AuthCard>
    );
  } else {
    content = (
      <AuthCard icon="mail" intro={t("If an account exists for this address, a sign-in link is on its way. The link works once and expires in 15 minutes.")} title={t("Check your email")}>
        <Recipient icon="mail" label={t("Email address")} value={email} />
        <CaError>{error ? t("Could not send a new link: {reason}", { reason: error }) : null}</CaError>
        <button className="ca-secondary" disabled={resendDisabled} onClick={requestMagicLink} type="button">{resendLabel}</button>
        {isFixturePreview ? (
          <button className="ca-primary acc-auth-demo" onClick={() => nav.go("dashboard")} type="button">
            {t("Open link in demo")}
            <CaIcon name="right" />
          </button>
        ) : null}
        <div className="ca-action-row">
          <button className="ca-text-button" onClick={resetLoginFlow} type="button">{t("Use a different email address")}</button>
        </div>
        <p className="ca-quiet-note">{t("Lost access to your email? Contact support: we verify your identity before we change anything.")}</p>
      </AuthCard>
    );
  }

  return <AuthLayout>{content}</AuthLayout>;
}
