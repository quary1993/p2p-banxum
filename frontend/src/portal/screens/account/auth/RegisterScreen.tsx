// IP of Webby-Soft SRL.
// Registration (design: create-account module, steps Your details -> Email & phone -> Security PIN ->
// Identity, plus the verification states). Today's flow and checks (ACC-DEC-001/009, KYC-DEC):
// details and the server-published agreements, the magic link opened in this browser, the SMS code,
// the PIN, then Didit. Marketing consent is optional and unchecked (U33-DEC-30). Every answer is the
// same for a new address and one that already has an account (audit A-50/A-57).
import { useEffect, useState, type FormEvent } from "react";

import {
  CategoryEnum,
  useV1AuthMagicLinkRequestCreate,
  useV1AuthMeRetrieve,
  useV1AuthPhoneConfirmCreate,
  useV1AuthPhoneRequestCreate,
  useV1AuthRegisterNaturalPersonCreate,
  useV1DocumentsTemplatesCurrentRetrieve,
  useV1KycSessionCreate,
  useV1KycStatusRetrieve,
  type PublicDocumentTemplateVersion
} from "../../../../api/generated/banxumApi";
import { ApiClientError } from "../../../../api/client/httpClient";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { retryAfter, useCreatePinFlow, useSecondsLeft } from "../../../../investorPortal/pinFlows";
import { pinApiError } from "../../../../investorPortal/pinRules";
import { brandDisplayName, operatorName } from "../../../brand";
import { PortalLink, usePortalNav } from "../../../components";
import { AuthCard, AuthLayout, CaCodeField, CaDialog, CaError, CaIcon, Recipient } from "./AuthLayout";
import {
  defaultRegisterFlowState,
  e164PhoneNumber,
  normalizedEmail,
  readStoredObject,
  registerFlowStorageKey,
  registrationCountries,
  removeStoredObject,
  requestErrorText,
  writeStoredObject,
  type RegisterFlowState,
  type RegisterPreviewDefaults
} from "./authState";

const registrationTermsVersion = import.meta.env.VITE_REGISTRATION_TERMS_VERSION ?? "registration-v1";
const registrationTermsHash =
  import.meta.env.VITE_REGISTRATION_TERMS_HASH ?? "3b0ba70e0b1d68a6acd2135c832cf114f6db2fb5c8896625c1f28f3ba7bd8dca";

// KYC answers that mean "submitted, a decision is pending" (the provider's flags are never named).
const IN_REVIEW = new Set(["pending", "manual_review", "high_risk", "sanctions_hit", "pep_hit", "adverse_media_hit"]);

function templateLabels(template: PublicDocumentTemplateVersion | undefined) {
  return Array.isArray(template?.checkbox_labels)
    ? template.checkbox_labels.filter((label): label is string => typeof label === "string")
    : [];
}

function idempotencyKey(prefix: string) {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  return `${prefix}:${random}`;
}

/** A published document, opened in a new tab where it can be read and downloaded (U33-DEC-14). */
function DocumentLink({ category, children }: { category: string; children: string }) {
  return (
    <a href={`/legal/${category.replace(/_/g, "-")}`} rel="noopener noreferrer" target="_blank">{children}</a>
  );
}

function formatPhone(callingCode: string, nationalNumber: string) {
  const digits = nationalNumber.replace(/\D/g, "").replace(/^0+/, "");
  return digits ? `${callingCode} ${nationalNumber.trim().replace(/^0+/, "")}` : "";
}

function StatusDetails({ approved }: { approved: boolean }) {
  const t = useT();
  return (
    <div className="ca-status-details">
      <div className="ca-status-item"><CaIcon name="checkCircle" />{t("Email and phone verified")}</div>
      <div className="ca-status-item"><CaIcon name="checkCircle" />{t("Security PIN created")}</div>
      <div className={`ca-status-item ${approved ? "" : "ca-pending"}`.trim()}>
        <CaIcon name={approved ? "checkCircle" : "clock"} />
        {t("Identity verification")}
        <small>{approved ? t("Verified") : t("In review")}</small>
      </div>
    </div>
  );
}

export function RegisterScreen({ previewDefaults }: { previewDefaults?: RegisterPreviewDefaults }) {
  const t = useT();
  const nav = usePortalNav();
  const brand = brandDisplayName();
  const [initial] = useState(() => readStoredObject<RegisterFlowState>(registerFlowStorageKey, defaultRegisterFlowState(previewDefaults)));
  const [step, setStep] = useState(initial.step);
  const [firstName, setFirstName] = useState(initial.firstName);
  const [lastName, setLastName] = useState(initial.lastName);
  const [email, setEmail] = useState(initial.email);
  const [phoneCountryCode, setPhoneCountryCode] = useState(initial.phoneCountryCode);
  const [phoneNationalNumber, setPhoneNationalNumber] = useState(initial.phoneNationalNumber);
  const [residenceCountry, setResidenceCountry] = useState(initial.residenceCountry);
  const [terms, setTerms] = useState(initial.terms);
  const [registrationAcceptedLabels, setRegistrationAcceptedLabels] = useState(initial.registrationAcceptedLabels);
  const [risk, setRisk] = useState(initial.risk);
  const [marketing, setMarketing] = useState(initial.marketing);
  const [emailLoginSent, setEmailLoginSent] = useState(initial.emailLoginSent);
  const [emailCooldownUntil, setEmailCooldownUntil] = useState(initial.emailCooldownUntil);
  const [phoneChallengeId, setPhoneChallengeId] = useState<string | null>(initial.phoneChallengeId);
  const [phoneCooldownUntil, setPhoneCooldownUntil] = useState(initial.phoneCooldownUntil);
  const [phoneCode, setPhoneCode] = useState("");
  const [editingPhone, setEditingPhone] = useState(false);
  const [companyOpen, setCompanyOpen] = useState(false);
  const [error, setError] = useState("");
  // Preview mode only: the Didit hand-off and result are simulated on this screen.
  const [previewKyc, setPreviewKyc] = useState<"not_started" | "pending" | "approved">("not_started");
  const registerMutation = useV1AuthRegisterNaturalPersonCreate();
  const magicLinkMutation = useV1AuthMagicLinkRequestCreate();
  const phoneRequestMutation = useV1AuthPhoneRequestCreate();
  const phoneConfirmMutation = useV1AuthPhoneConfirmCreate();
  const kycSessionMutation = useV1KycSessionCreate();
  const authMeQuery = useV1AuthMeRetrieve({ query: { enabled: !isFixturePreview && step >= 1, retry: false, staleTime: 0 } });
  const templateQuery = { enabled: !isFixturePreview, retry: false, staleTime: 0 } as const;
  const registrationTermsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.registration, template_key: "default", language: "en" },
    { query: templateQuery }
  );
  const riskDisclosureQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.risk_disclosure, template_key: "default", language: "en" },
    { query: templateQuery }
  );
  const phoneNumber = e164PhoneNumber(phoneCountryCode, phoneNationalNumber);
  const phoneCooldownSeconds = useSecondsLeft(phoneCooldownUntil);
  const emailCooldownSeconds = useSecondsLeft(emailCooldownUntil);
  const registrationLabels = templateLabels(registrationTermsQuery.data);
  const riskLabels = templateLabels(riskDisclosureQuery.data);
  const allRegistrationTermsAccepted = isFixturePreview || registrationLabels.length === 0
    ? terms
    : registrationLabels.every((label) => registrationAcceptedLabels.includes(label));

  useEffect(() => {
    writeStoredObject(registerFlowStorageKey, {
      step,
      firstName,
      lastName,
      email,
      phoneCountryCode,
      phoneNationalNumber,
      residenceCountry,
      terms,
      registrationAcceptedLabels,
      risk,
      marketing,
      emailLoginSent,
      emailCooldownUntil,
      phoneChallengeId,
      phoneCooldownUntil
    } satisfies RegisterFlowState);
  }, [email, emailCooldownUntil, emailLoginSent, firstName, lastName, marketing, phoneChallengeId, phoneCooldownUntil, phoneCountryCode, phoneNationalNumber, registrationAcceptedLabels, residenceCountry, risk, step, terms]);

  const sessionUser = authMeQuery.data?.user;
  const hasMatchingSession = isFixturePreview || (Boolean(sessionUser) && normalizedEmail(sessionUser?.email ?? "") === normalizedEmail(email));
  const hasDifferentSession = !isFixturePreview && Boolean(sessionUser) && normalizedEmail(sessionUser?.email ?? "") !== normalizedEmail(email);

  const kycStatusQuery = useV1KycStatusRetrieve({
    query: {
      enabled: !isFixturePreview && step === 3 && hasMatchingSession,
      retry: false,
      // Identity capture can happen on another device (QR hand-off): poll until a result arrives.
      refetchInterval: (query) => {
        const caseStatus = query.state.data?.status;
        return !caseStatus || caseStatus === "not_started" || caseStatus === "pending" ? 4000 : false;
      }
    }
  });
  const kycStatus = isFixturePreview ? previewKyc : kycStatusQuery.data?.status;

  useEffect(() => {
    if (isFixturePreview || step !== 3 || !kycStatus) return;
    // A refused check continues in the account, where Verification explains the next step.
    if (kycStatus === "declined") {
      removeStoredObject(registerFlowStorageKey);
      nav.go("kyc");
    }
    // nav changes identity on every App render; the status decides.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kycStatus, step]);

  useEffect(() => {
    if (step === 1 && sessionUser?.phone_verified && normalizedEmail(sessionUser.email) === normalizedEmail(email)) {
      setStep(2);
      setPhoneChallengeId(null);
      setPhoneCooldownUntil(0);
    }
    // The PIN step (ACC-DEC-009) is done once the account has a PIN.
    if (step === 2 && sessionUser?.pin_set === true && normalizedEmail(sessionUser.email) === normalizedEmail(email)) {
      setStep(3);
    }
  }, [email, sessionUser, step]);

  const goToStep = (next: number) => {
    setError("");
    setStep(next);
  };

  // ---- Step 1: details and agreements --------------------------------------------------------

  const submitDetails = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!firstName.trim() || !lastName.trim() || !allRegistrationTermsAccepted || !risk) {
      setError(t("Complete your details and accept the required agreements."));
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError(t("Enter a valid email address."));
      return;
    }
    if (!phoneNumber || phoneNumber.replace(/\D/g, "").length < 6) {
      setError(t("Enter a valid mobile number."));
      return;
    }
    if (isFixturePreview) {
      goToStep(1);
      setEmailLoginSent(true);
      return;
    }
    if (!registrationTermsQuery.data || registrationLabels.length === 0) {
      setError(t("The current lender user agreement is not available. Retry once it loads."));
      return;
    }
    if (!riskDisclosureQuery.data || riskLabels.length === 0) {
      setError(t("The current lender risk disclosure is not available. Retry once it loads."));
      return;
    }
    registerMutation.mutate(
      {
        data: {
          email: email.trim(),
          full_name: `${firstName} ${lastName}`.trim(),
          phone_number: phoneNumber,
          terms_version: registrationTermsVersion,
          terms_hash: registrationTermsHash,
          registration_document_template_version_id: registrationTermsQuery.data.id,
          accepted_checkbox_labels: registrationLabels,
          document_idempotency_key: idempotencyKey("registration-document"),
          risk_document_template_version_id: riskDisclosureQuery.data.id,
          accepted_risk_checkbox_labels: riskLabels,
          risk_document_idempotency_key: idempotencyKey("registration-risk-disclosure"),
          marketing_consent: marketing
        }
      },
      {
        onSuccess: (response) => {
          goToStep(1);
          setPhoneCode("");
          setPhoneChallengeId(null);
          setPhoneCooldownUntil(0);
          setEmailLoginSent(response.email_login_sent);
          setEmailCooldownUntil(response.email_login_sent ? Date.now() + 60_000 : 0);
        },
        onError: (mutationError) => setError(requestErrorText(mutationError))
      }
    );
  };

  // ---- Step 2: email link, then the SMS code ----------------------------------------------

  const requestRegistrationMagicLink = () => {
    setError("");
    if (isFixturePreview) {
      setEmailLoginSent(true);
      return;
    }
    magicLinkMutation.mutate(
      { data: { email: email.trim() } },
      {
        onSuccess: () => {
          setEmailLoginSent(true);
          setEmailCooldownUntil(Date.now() + 60_000);
        },
        onError: (mutationError) => {
          const waitSeconds = retryAfter(mutationError);
          if (waitSeconds) setEmailCooldownUntil(Date.now() + waitSeconds * 1000);
          // A link is already on its way: the button countdown says when resend unlocks.
          if (waitSeconds && emailLoginSent) return;
          setError(requestErrorText(mutationError));
        }
      }
    );
  };

  const requestPhoneCode = () => {
    setError("");
    if (isFixturePreview) {
      setPhoneChallengeId("fixture-phone-challenge");
      setPhoneCooldownUntil(Date.now() + 60_000);
      setEditingPhone(false);
      return;
    }
    if (!hasMatchingSession) {
      setError(t("Open the sign-in link from your email in this browser before you request the SMS code."));
      return;
    }
    // The number typed at registration: the signed-in owner may correct an unverified number this
    // way (a repeated registration never changes stored data).
    phoneRequestMutation.mutate(phoneNumber ? { data: { phone_number: phoneNumber } } : {}, {
      onSuccess: (response) => {
        setEditingPhone(false);
        if (response.phone_verified) {
          goToStep(2);
          return;
        }
        setPhoneChallengeId(response.challenge_id);
        setPhoneCooldownUntil(Date.now() + 60_000);
      },
      onError: (mutationError) => {
        const waitSeconds = retryAfter(mutationError);
        if (waitSeconds) setPhoneCooldownUntil(Date.now() + waitSeconds * 1000);
        if (mutationError instanceof ApiClientError && mutationError.status === 403) {
          setError(t("Open the sign-in link from your email before you request the SMS code."));
          return;
        }
        setError(requestErrorText(mutationError));
      }
    });
  };

  const confirmPhone = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (phoneCode.length < 6) {
      setError(t("Enter the six-digit SMS code."));
      return;
    }
    if (isFixturePreview) {
      goToStep(2);
      return;
    }
    if (!phoneChallengeId) {
      setError(t("Request an SMS code first."));
      return;
    }
    phoneConfirmMutation.mutate(
      { data: { challenge_id: phoneChallengeId, code: phoneCode } },
      {
        onSuccess: () => {
          goToStep(2);
          setPhoneCooldownUntil(0);
        },
        onError: (mutationError) => setError(requestErrorText(mutationError))
      }
    );
  };

  // ---- Step 3: PIN -------------------------------------------------------------------------

  // No email code at registration: the investor has just proved the email and the phone.
  const pinFlow = useCreatePinFlow({ requiresEmailCode: false, onSaved: () => goToStep(3) });

  // ---- Step 4: Didit -----------------------------------------------------------------------

  const startKyc = () => {
    setError("");
    if (isFixturePreview) {
      setPreviewKyc("pending");
      return;
    }
    kycSessionMutation.mutate(undefined, {
      onSuccess: (response) => {
        if (response.verification_url) {
          window.location.assign(response.verification_url);
          return;
        }
        nav.go("kyc");
      },
      onError: (mutationError) => {
        // Identity verification needs the PIN first (ACC-DEC-009): back to the PIN step.
        if (pinApiError(mutationError)?.code === "pin_required") {
          goToStep(2);
          return;
        }
        setError(requestErrorText(mutationError));
      }
    });
  };

  const openAccount = () => {
    removeStoredObject(registerFlowStorageKey);
    nav.go("dashboard");
  };

  const phoneLabel = formatPhone(phoneCountryCode, phoneNationalNumber) || t("Your registered mobile number");
  const phoneEditor = (
    <div className="ca-fields acc-phone-edit">
      <div className="ca-field ca-phone-field ca-wide">
        <label htmlFor="register-phone-edit">{t("Mobile number")}</label>
        <div className="ca-phone-input">
          <select aria-label={t("Country prefix")} onChange={(event) => setPhoneCountryCode(event.target.value)} value={phoneCountryCode}>
            {registrationCountries.map((country) => <option key={`${country.iso2}-${country.callingCode}`} value={country.callingCode}>{country.iso2} {country.callingCode}</option>)}
          </select>
          <input autoComplete="tel-national" id="register-phone-edit" inputMode="tel" maxLength={24} onChange={(event) => setPhoneNationalNumber(event.target.value.replace(/[^\d\s().-]/g, ""))} placeholder="79 000 00 00" type="tel" value={phoneNationalNumber} />
        </div>
      </div>
    </div>
  );
  const phoneRecipient = editingPhone ? phoneEditor : (
    <Recipient
      action={<button className="ca-text-button" onClick={() => setEditingPhone(true)} type="button">{t("Change")}</button>}
      icon="phone"
      label={t("Your mobile")}
      value={phoneLabel}
    />
  );

  let content;
  let journeyStep = step;
  let journeyDone = false;
  if (step === 0) {
    content = (
      <AuthCard
        intro={<>{t("For individual investors.")} <a href="#" onClick={(event) => { event.preventDefault(); setCompanyOpen(true); }}>{t("Investing as a company?")}</a></>}
        title={t("Create your account")}
        wide
      >
        <form data-form="details" noValidate onSubmit={submitDetails}>
          <div className="ca-fields">
            <div className="ca-field">
              <label htmlFor="register-first">{t("First name")}</label>
              <input autoComplete="given-name" id="register-first" maxLength={120} onChange={(event) => setFirstName(event.target.value)} value={firstName} />
            </div>
            <div className="ca-field">
              <label htmlFor="register-last">{t("Last name")}</label>
              <input autoComplete="family-name" id="register-last" maxLength={120} onChange={(event) => setLastName(event.target.value)} value={lastName} />
            </div>
            <div className="ca-field ca-wide">
              <label htmlFor="register-email">{t("Email address")}</label>
              <input autoComplete="email" id="register-email" maxLength={120} onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
            </div>
            <div className="ca-field ca-phone-field">
              <label htmlFor="register-phone">{t("Mobile number")}</label>
              <div className="ca-phone-input">
                <select aria-label={t("Country prefix")} onChange={(event) => setPhoneCountryCode(event.target.value)} value={phoneCountryCode}>
                  {registrationCountries.map((country) => <option key={`${country.iso2}-${country.callingCode}`} value={country.callingCode}>{country.iso2} {country.callingCode}</option>)}
                </select>
                <input autoComplete="tel-national" id="register-phone" inputMode="tel" maxLength={24} onChange={(event) => setPhoneNationalNumber(event.target.value.replace(/[^\d\s().-]/g, ""))} placeholder="79 000 00 00" type="tel" value={phoneNationalNumber} />
              </div>
            </div>
            <div className="ca-field ca-country-field">
              <label htmlFor="register-country">{t("Country of residence")}</label>
              <select autoComplete="country" id="register-country" onChange={(event) => setResidenceCountry(event.target.value)} value={residenceCountry}>
                {registrationCountries.map((country) => <option key={country.iso2} value={country.name}>{t(country.name)}</option>)}
              </select>
            </div>
          </div>
          <div className="ca-agreements">
            {isFixturePreview || registrationLabels.length === 0 ? (
              <label className="ca-checkbox">
                <input checked={terms} onChange={(event) => setTerms(event.target.checked)} type="checkbox" />
                <span>
                  {t("I have read, understood and accept the")} <DocumentLink category="registration">{t("General Terms and Conditions / User Agreement")}</DocumentLink>
                  {t(", including its integral annexes.")}
                </span>
              </label>
            ) : (
              registrationLabels.map((label) => (
                <label className="ca-checkbox" key={label}>
                  <input
                    checked={registrationAcceptedLabels.includes(label)}
                    onChange={(event) =>
                      setRegistrationAcceptedLabels((current) => (event.target.checked ? Array.from(new Set([...current, label])) : current.filter((item) => item !== label)))
                    }
                    type="checkbox"
                  />
                  <span>{label} <DocumentLink category="registration">{t("Read the document")}</DocumentLink></span>
                </label>
              ))
            )}
            <label className="ca-checkbox">
              <input checked={risk} onChange={(event) => setRisk(event.target.checked)} type="checkbox" />
              <span>
                {riskLabels.length === 1 ? <>{riskLabels[0]} <DocumentLink category="risk_disclosure">{t("Read the risk disclosure")}</DocumentLink></> : (
                  <>{t("I acknowledge the")} <DocumentLink category="risk_disclosure">{t("risk disclosure")}</DocumentLink>{t(" and possible capital loss.")}</>
                )}
              </span>
            </label>
            <label className="ca-checkbox ca-optional">
              <input checked={marketing} onChange={(event) => setMarketing(event.target.checked)} type="checkbox" />
              <span>{t("I agree to optional marketing communications.")}</span>
            </label>
          </div>
          {!isFixturePreview && registrationTermsQuery.isError ? <CaError>{t("The current lender user agreement could not be loaded. Retry before registering.")}</CaError> : null}
          {!isFixturePreview && riskDisclosureQuery.isError ? <CaError>{t("The current lender risk disclosure could not be loaded. Retry before registering.")}</CaError> : null}
          <CaError>{error || null}</CaError>
          <button
            className="ca-primary"
            disabled={registerMutation.isPending || (!isFixturePreview && (!registrationTermsQuery.data || !riskDisclosureQuery.data))}
            type="submit"
          >
            {registerMutation.isPending ? t("Creating account...") : t("Continue")}
            <CaIcon name="right" />
          </button>
        </form>
        <p className="ca-foot-link">
          {t("Already have an account?")}
          <PortalLink to="login">{t("Log in")}</PortalLink>
        </p>
        <p className="ca-quiet-note">{t("Your acceptance is recorded with the document version, the time and the context. You find the accepted versions in Documents.")}</p>
      </AuthCard>
    );
  } else if (step === 1 && !hasMatchingSession) {
    content = (
      <AuthCard icon="mail" intro={t("Open the link in your email to continue.")} title={t("Check your email")}>
        {hasDifferentSession ? (
          <CaError>{t("This browser is signed in as {current}. Open the link sent to {email} in this browser to continue this registration.", { current: sessionUser?.email ?? "", email })}</CaError>
        ) : null}
        <Recipient icon="mail" label={emailLoginSent ? t("Link sent to") : t("Email address")} value={email} />
        <p className="ca-email-note">{t("Use this browser to continue where you left off.")}</p>
        <CaError>{error || null}</CaError>
        <button className="ca-secondary" disabled={!email.includes("@") || magicLinkMutation.isPending || emailCooldownSeconds > 0} onClick={requestRegistrationMagicLink} type="button">
          {magicLinkMutation.isPending
            ? t("Sending...")
            : emailCooldownSeconds > 0
              ? t("Resend in {seconds}s", { seconds: emailCooldownSeconds })
              : emailLoginSent ? t("Resend link") : t("Send link")}
        </button>
        <div className="ca-action-row">
          <button className="ca-text-button" onClick={() => goToStep(0)} type="button">{t("Wrong email address?")}</button>
        </div>
        <div className="ca-waiting"><CaIcon name="clock" />{t("Waiting for email confirmation")}</div>
      </AuthCard>
    );
  } else if (step === 1 && !phoneChallengeId) {
    content = (
      <AuthCard icon="phone" intro={t("We will send a six-digit code to your mobile.")} title={t("Verify your mobile number")}>
        {phoneRecipient}
        <CaError>{error || null}</CaError>
        <button className="ca-primary" disabled={phoneRequestMutation.isPending || phoneCooldownSeconds > 0 || !phoneNumber} onClick={requestPhoneCode} type="button">
          {phoneRequestMutation.isPending
            ? t("Sending...")
            : phoneCooldownSeconds > 0 ? t("Resend in {seconds}s", { seconds: phoneCooldownSeconds }) : t("Send SMS code")}
          <CaIcon name="right" />
        </button>
        <p className="ca-quiet-note"><CaIcon name="check" /> {t("Email verified")}</p>
      </AuthCard>
    );
  } else if (step === 1) {
    content = (
      <AuthCard icon="phone" intro={t("Enter the six-digit code sent to your mobile.")} title={t("Enter your SMS code")}>
        {phoneRecipient}
        <form data-form="sms" noValidate onSubmit={confirmPhone}>
          <CaCodeField autoFocus id="register-sms" label={t("SMS code")} onChange={(value) => { setPhoneCode(value); setError(""); }} value={phoneCode} />
          {isFixturePreview ? <p className="ca-field-note">{t("Demo: enter any 6 digits.")}</p> : null}
          <CaError>{error || null}</CaError>
          <button className="ca-primary ca-positive" disabled={phoneConfirmMutation.isPending} type="submit">
            {phoneConfirmMutation.isPending ? t("Verifying...") : t("Verify phone")}
            <CaIcon name="right" />
          </button>
        </form>
        <div className="ca-action-row">
          <button className="ca-text-button" disabled={phoneRequestMutation.isPending || phoneCooldownSeconds > 0} onClick={requestPhoneCode} type="button">
            {phoneCooldownSeconds > 0 ? t("Resend in {seconds}s", { seconds: phoneCooldownSeconds }) : t("Resend code")}
          </button>
        </div>
      </AuthCard>
    );
  } else if (step === 2) {
    const pinError = pinFlow.weakness ?? (pinFlow.confirmationError || (pinFlow.mismatch ? "The two PINs do not match." : "")) ?? "";
    content = (
      <AuthCard icon="lock" intro={t("Use your PIN and an email code to confirm investments, withdrawals and bank account changes.")} title={t("Create your security PIN")}>
        <form
          data-form="pin"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (pinFlow.ready && !pinFlow.saving) pinFlow.save();
          }}
        >
          <CaCodeField autoFocus id="register-pin" label={t("6-digit PIN")} masked onChange={pinFlow.setPin} value={pinFlow.pin} />
          <CaCodeField id="register-pin-repeat" label={t("Confirm PIN")} masked onChange={pinFlow.setConfirmation} value={pinFlow.confirmation} />
          <p className="ca-field-note">{t("Avoid repeated digits or simple sequences.")}</p>
          <CaError>{pinError ? t(pinError) : pinFlow.error ? t("Could not save your PIN: {reason}", { reason: pinFlow.error }) : null}</CaError>
          <button className="ca-primary ca-positive" disabled={!pinFlow.ready || pinFlow.saving} type="submit">
            {pinFlow.saving ? t("Saving PIN...") : t("Save PIN & continue")}
            <CaIcon name="right" />
          </button>
        </form>
      </AuthCard>
    );
  } else if (kycStatus === "approved") {
    journeyDone = true;
    content = (
      <AuthCard icon="checkCircle" intro={t("Your identity has been verified. You can now open your investor account.")} success title={t("Your account is ready")}>
        <StatusDetails approved />
        <button className="ca-primary" onClick={openAccount} type="button">
          {t("Open my account")}
          <CaIcon name="right" />
        </button>
        <p className="ca-quiet-note">{t("You review and confirm each investment yourself.")}</p>
      </AuthCard>
    );
  } else if (kycStatus && IN_REVIEW.has(kycStatus)) {
    content = (
      <AuthCard icon="clock" intro={t("Your identity check has been submitted. This page updates when the review is complete.")} title={t("Your verification is in review")}>
        <StatusDetails approved={false} />
        <p className="ca-email-note">{t("You can invest once verification is approved. {operator} retains the required compliance evidence and the provider's references.", { operator: operatorName })}</p>
        <button
          className="ca-secondary"
          disabled={!isFixturePreview && kycStatusQuery.isFetching}
          onClick={() => (isFixturePreview ? setPreviewKyc("approved") : void kycStatusQuery.refetch())}
          type="button"
        >
          {t("Check status")}
        </button>
      </AuthCard>
    );
  } else {
    journeyStep = 3;
    const interrupted = kycStatus === "expired" || kycStatus === "reverification_required";
    content = (
      <AuthCard
        icon="user"
        intro={interrupted ? t("Your verification is not complete. Continue with Didit to finish this step.") : t("Continue with Didit, our identity verification provider.")}
        title={interrupted ? t("Continue your identity verification") : t("Verify your identity")}
      >
        <ul className="ca-kyc-list">
          <li><CaIcon name="document" /><span>{t("Have your identity document ready")}</span></li>
          <li><CaIcon name="user" /><span>{t("Follow the identity and selfie checks")}</span></li>
          <li>
            <CaIcon name="phone" />
            <span>
              {t("Use this device or continue on your phone")}
              <small className="ca-subline">{t("Didit lets you switch devices; this page continues by itself when the result arrives.")}</small>
            </span>
          </li>
        </ul>
        <CaError>{error || null}</CaError>
        <button className="ca-primary" disabled={kycSessionMutation.isPending} onClick={startKyc} type="button">
          {kycSessionMutation.isPending ? t("Starting Didit...") : interrupted ? t("Continue verification") : t("Continue to identity verification")}
          <CaIcon name="right" />
        </button>
        <p className="ca-quiet-note">
          {t("You will return to {brand} after verification. {operator} retains the required compliance evidence and the provider's references.", { brand, operator: operatorName })}
        </p>
      </AuthCard>
    );
  }

  return (
    <AuthLayout step={journeyStep} stepsDone={journeyDone}>
      {content}
      {companyOpen ? (
        <CaDialog onClose={() => setCompanyOpen(false)} title={t("Investing as a company?")}>
          <p>{t("Online registration is for individual investors. Companies are onboarded by {operator} separately; contact us to discuss investing as a company.", { operator: operatorName })}</p>
          <p><a href="/contact" rel="noopener" target="_blank">{t("Open contact page")}</a></p>
        </CaDialog>
      ) : null}
    </AuthLayout>
  );
}
