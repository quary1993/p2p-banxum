// IP of Webby-Soft SRL.
// State of the sign-in and registration flows that survives a reload or the magic-link round trip:
// the sessionStorage keys (App.tsx clears them on sign-out), the registration form, the
// resume step of a signed-in account that has not finished onboarding, and small request helpers.
import { ApiClientError } from "../../../../api/client/httpClient";
import type { UserSummary } from "../../../../api/generated/banxumApi";
import { onboardingStepForUser } from "../../../../onboarding";

export const loginFlowStorageKey = "banxum:login-flow:v1";
export const registerFlowStorageKey = "banxum:register-flow:v3";

// Audit S8-3: the flow state holds personal data (name, email, phone, country), so it lives in
// sessionStorage: it survives a reload of the tab and is gone when the tab closes. Values that an
// older version left in localStorage are removed on the first read.
function flowStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.sessionStorage;
}

function removeLegacy(key: string) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Storage blocked: nothing kept there either.
  }
}

export function readStoredObject<T>(key: string, fallback: T): T {
  const storage = flowStorage();
  if (!storage) return fallback;
  removeLegacy(key);
  try {
    const raw = storage.getItem(key);
    return raw ? ({ ...fallback, ...JSON.parse(raw) } as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeStoredObject(key: string, value: unknown) {
  const storage = flowStorage();
  if (!storage) return;
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be full or blocked (private mode); the flow still works for this visit.
  }
}

export function removeStoredObject(key: string) {
  const storage = flowStorage();
  if (!storage) return;
  removeLegacy(key);
  try {
    storage.removeItem(key);
  } catch {
    // Nothing to remove.
  }
}

/** Sign-out: the sign-in and registration flow state goes (audit S8-3). */
export function clearAuthFlowState() {
  removeStoredObject(loginFlowStorageKey);
  removeStoredObject(registerFlowStorageKey);
}

export type LoginFlowState = {
  email: string;
  sent: boolean;
  linkExpired: boolean;
  resendCooldownUntil: number;
  // True while the expired-link screen asks for an address (none known yet, or
  // "Use a different email address"); the field must stay while the user types.
  editingEmail: boolean;
};

export type RegisterFlowState = {
  step: number;
  firstName: string;
  lastName: string;
  email: string;
  phoneCountryCode: string;
  phoneNationalNumber: string;
  residenceCountry: string;
  terms: boolean;
  registrationAcceptedLabels: string[];
  risk: boolean;
  marketing: boolean;
  emailLoginSent: boolean;
  emailCooldownUntil: number;
  phoneChallengeId: string | null;
  phoneCooldownUntil: number;
};

/** Values the preview mode pre-fills (fixture data from App.tsx; empty in live mode). */
export type RegisterPreviewDefaults = Pick<RegisterFlowState, "firstName" | "lastName" | "email" | "phoneNationalNumber">;

export function defaultRegisterFlowState(preview?: RegisterPreviewDefaults): RegisterFlowState {
  return {
    step: 0,
    firstName: preview?.firstName ?? "",
    lastName: preview?.lastName ?? "",
    email: preview?.email ?? "",
    phoneCountryCode: "+41",
    phoneNationalNumber: preview?.phoneNationalNumber ?? "",
    residenceCountry: "Switzerland",
    terms: false,
    registrationAcceptedLabels: [],
    risk: false,
    marketing: false,
    emailLoginSent: false,
    emailCooldownUntil: 0,
    phoneChallengeId: null,
    phoneCooldownUntil: 0
  };
}

export function normalizedEmail(value: string) {
  return value.trim().toLowerCase();
}

export function e164PhoneNumber(callingCode: string, nationalNumber: string) {
  const digits = nationalNumber.replace(/\D/g, "").replace(/^0+/, "");
  return digits ? `${callingCode}${digits}` : "";
}

function splitDisplayName(fullName: string) {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return { firstName: "", lastName: "" };
  if (parts.length === 1) return { firstName: parts[0], lastName: "" };
  return { firstName: parts[0], lastName: parts.slice(1).join(" ") };
}

/** The registration state to resume for a signed-in account that has not finished onboarding. */
export function resumedRegisterStateForUser(user: UserSummary): RegisterFlowState | null {
  const nextStep = onboardingStepForUser(user);
  if (nextStep === null) return null;
  const fallback = defaultRegisterFlowState();
  const stored = readStoredObject<RegisterFlowState>(registerFlowStorageKey, fallback);
  const storedMatchesUser = normalizedEmail(stored.email) === normalizedEmail(user.email);
  const nameParts = splitDisplayName(user.full_name);
  return {
    ...fallback,
    ...(storedMatchesUser ? stored : {}),
    step: nextStep,
    firstName: storedMatchesUser && stored.firstName ? stored.firstName : nameParts.firstName,
    lastName: storedMatchesUser && stored.lastName ? stored.lastName : nameParts.lastName,
    email: user.email,
    marketing: user.marketing_consent,
    emailLoginSent: true,
    phoneChallengeId: null,
    phoneCooldownUntil: 0
  };
}

/** The magic-link consume API answers 403 { code: "account_restricted" | "account_locked" }. */
export function blockedAccountStatusFromError(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 403) return null;
  const code = (error.payload as { code?: unknown } | undefined)?.code;
  if (code === "account_restricted") return "restricted";
  if (code === "account_locked") return "locked";
  return null;
}

export type RegistrationCountry = { name: string; iso2: string; callingCode: string };

export const registrationCountries: RegistrationCountry[] = [
  { name: "Switzerland", iso2: "CH", callingCode: "+41" },
  { name: "Austria", iso2: "AT", callingCode: "+43" },
  { name: "Belgium", iso2: "BE", callingCode: "+32" },
  { name: "Bulgaria", iso2: "BG", callingCode: "+359" },
  { name: "Croatia", iso2: "HR", callingCode: "+385" },
  { name: "Cyprus", iso2: "CY", callingCode: "+357" },
  { name: "Czechia", iso2: "CZ", callingCode: "+420" },
  { name: "Denmark", iso2: "DK", callingCode: "+45" },
  { name: "Estonia", iso2: "EE", callingCode: "+372" },
  { name: "Finland", iso2: "FI", callingCode: "+358" },
  { name: "France", iso2: "FR", callingCode: "+33" },
  { name: "Germany", iso2: "DE", callingCode: "+49" },
  { name: "Greece", iso2: "GR", callingCode: "+30" },
  { name: "Hungary", iso2: "HU", callingCode: "+36" },
  { name: "Iceland", iso2: "IS", callingCode: "+354" },
  { name: "Ireland", iso2: "IE", callingCode: "+353" },
  { name: "Italy", iso2: "IT", callingCode: "+39" },
  { name: "Latvia", iso2: "LV", callingCode: "+371" },
  { name: "Liechtenstein", iso2: "LI", callingCode: "+423" },
  { name: "Lithuania", iso2: "LT", callingCode: "+370" },
  { name: "Luxembourg", iso2: "LU", callingCode: "+352" },
  { name: "Malta", iso2: "MT", callingCode: "+356" },
  { name: "Netherlands", iso2: "NL", callingCode: "+31" },
  { name: "Norway", iso2: "NO", callingCode: "+47" },
  { name: "Poland", iso2: "PL", callingCode: "+48" },
  { name: "Portugal", iso2: "PT", callingCode: "+351" },
  { name: "Romania", iso2: "RO", callingCode: "+40" },
  { name: "Slovakia", iso2: "SK", callingCode: "+421" },
  { name: "Slovenia", iso2: "SI", callingCode: "+386" },
  { name: "Spain", iso2: "ES", callingCode: "+34" },
  { name: "Sweden", iso2: "SE", callingCode: "+46" }
];

/** "Request failed..." for an unknown error, the server's message otherwise. */
export function requestErrorText(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Request failed. Retry once the connection is restored.";
}

/** NIST SP 800-63B-4 in one line, as the server checks it (passwords.py). */
export function passwordProblem(password: string, repeat: string | null, email = "") {
  if (password.length < 12) return "Use at least 12 characters.";
  if (password.length > 128) return "Use at most 128 characters.";
  if (email && password.trim().toLowerCase() === email.trim().toLowerCase()) return "Do not use your email address.";
  if (repeat !== null && repeat !== password) return "The passwords do not match.";
  return "";
}
