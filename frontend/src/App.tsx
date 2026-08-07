import { useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import { useCallback, useEffect, useRef, useState, type ComponentProps, type FormEvent, type ReactNode } from "react";
import { AdminApp } from "./adminConsole/AdminApp";
import {
  ActionEnum,
  CategoryEnum,
  CollateralScopeEnum,
  CurrencyScopeEnum,
  DocumentKindEnum,
  InvestorDocumentDownloadRequestOutputFormatEnum,
  LoanKindEnum,
  OriginatorScopeEnum,
  getV1InvestorSmartInvestRetrieveQueryKey,
  useV1AuthMeRetrieve,
  useV1AuthLogoutCreate,
  useV1AuthMagicLinkRequestCreate,
  useV1AuthPhoneConfirmCreate,
  useV1AuthPhoneRequestCreate,
  useV1AuthPreferencesMarketingPartialUpdate,
  useV1AuthRegisterNaturalPersonCreate,
  useV1AuthSensitiveActionCodeRequestCreate,
  useV1DocumentsAcceptancesCreate,
  useV1DocumentsTemplatesCurrentRetrieve,
  useV1FxQuotePreviewRetrieve,
  useV1FxQuotesCreate,
  useV1FxQuotesExecuteCreate,
  useV1InvestorPortalDocumentsDownloadCreate,
  useV1KycSessionCreate,
  useV1KycStatusRetrieve,
  useV1LedgerPayoutInstructionsCreate,
  useV1LedgerWithdrawalRequestsCreate,
  useV1MarketplacePrimaryOrdersAllocateBalanceCreate,
  useV1MarketplacePrimaryOrdersCreate,
  useV1MarketplaceSecondaryListingsCreate,
  useV1MarketplaceSecondaryListingsCancelCreate,
  useV1MarketplaceSecondaryListingsEditCreate,
  useV1MarketplaceSecondaryListingsPurchaseCreate,
  useV1InvestorSmartInvestDeactivateCreate,
  useV1InvestorSmartInvestUpdate,
  useMarketplacePrimaryOrdersBatchCreate,
  useOriginatorClaimsLoansQuoteCreate,
  useOriginatorClaimsQuotesPurchaseCreate,
  v1AuthMagicLinkConsumeCreate
} from "./api/generated/banxumApi";
import { ApiClientError } from "./api/client/httpClient";
import {
  clearReadonlyImpersonation,
  readReadonlyImpersonationLabel,
  readReadonlyImpersonationToken
} from "./api/client/impersonation";
import type {
  ActivityEntry,
  BalanceLot,
  FxQuotePreview,
  FxQuote,
  Holding,
  InvestorDocument,
  InvestorDocumentDownloadResponse,
  MarketplaceLoanDetail,
  MarketplaceLoanPreview,
  OriginatorClaimQuoteResponse,
  PayoutInstruction,
  PrimaryOrderPortal,
  PublicDocumentTemplateVersion,
  SecondaryMarketActivityEntryPortal,
  SecondaryMarketBuyerListing,
  SecondaryMarketInvestmentInstallment,
  SecondaryMarketLoanInstallment,
  SmartInvestOpportunity,
  SmartInvestResponse,
  SmartInvestRule,
  SmartInvestRuleSaveRequest,
  UserSummary
} from "./api/generated/banxumApi";
import {
  useActivityData,
  useBalancesData,
  useDashboardData,
  useDepositInstructionsData,
  useDocumentsData,
  useFxData,
  useLoanDetailData,
  useMarketplaceLoansData,
  useNotificationsData,
  usePortfolioData,
  usePrimaryOrdersData,
  useSecondaryActivityData,
  useSecondaryListingDetailData,
  useSecondaryListingsData,
  useSmartInvestData,
  isFixturePreview
} from "./investorPortal/data";
import { portalFixture } from "./investorPortal/fixtures";
import { onboardingStepForUser } from "./onboarding";
import {
  formatDate,
  formatDateTime,
  formatMoneyMinor,
  formatRateBps,
  parseMoneyInputToMinorUnits,
  safeMetadataCategory,
  zurichDateKey
} from "./investorPortal/format";
import type { AppRoute, DemoAccountState, RouteName } from "./investorPortal/types";
import {
  Banner,
  Button,
  Card,
  Check,
  Chip,
  Country,
  DeadlineMeter,
  Empty,
  Field,
  Icon,
  Modal,
  Money,
  Progress,
  Rating,
  Review,
  Segmented,
  Stat,
  Tabs
} from "./investorPortal/ui";

const platformName = import.meta.env.VITE_PLATFORM_BRAND_NAME ?? "BANXUM";
const operatorName = import.meta.env.VITE_LEGAL_OPERATOR_NAME ?? "Garanta Finanzgruppe AG";
const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL ?? "support@banxum.com";
const registrationTermsVersion = import.meta.env.VITE_REGISTRATION_TERMS_VERSION ?? "registration-v1";
const registrationTermsHash =
  import.meta.env.VITE_REGISTRATION_TERMS_HASH ??
  "3b0ba70e0b1d68a6acd2135c832cf114f6db2fb5c8896625c1f28f3ba7bd8dca";

function formatEnumLabel(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const liveProfileFallback = {
  initials: "IN",
  name: "Investor account",
  email: "Live account",
  country: "Self-scoped account",
  phone: "",
  memberSince: ""
};

function displayProfile() {
  return isFixturePreview ? portalFixture.profile : liveProfileFallback;
}

function isReadonlyImpersonationActive() {
  return Boolean(readReadonlyImpersonationToken());
}

function previewHint(text: string) {
  return isFixturePreview ? text : undefined;
}

function humanizeToken(token: string) {
  const label = token.replaceAll("_", " ").trim();
  return label ? label.charAt(0).toUpperCase() + label.slice(1) : "";
}

function RefinancedTag({ full = false }: { full?: boolean }) {
  return <span className="tag">{full ? "Refinanced loan" : "Refinanced"}</span>;
}

const loginFlowStorageKey = "banxum:login-flow:v1";
const registerFlowStorageKey = "banxum:register-flow:v3";
const appRouteStorageKey = "banxum:app-route:v1";

type LoginFlowState = {
  email: string;
  sent: boolean;
  linkExpired: boolean;
  resendCooldownUntil: number;
};

type RegisterFlowState = {
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

type RegistrationCountry = {
  name: string;
  iso2: string;
  callingCode: string;
};

const registrationCountries: RegistrationCountry[] = [
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

function readStoredObject<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? ({ ...fallback, ...JSON.parse(raw) } as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStoredObject(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

function removeStoredObject(key: string) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
}

const routeNames: RouteName[] = [
  "public",
  "publicFaq",
  "login",
  "register",
  "kyc",
  "dashboard",
  "market",
  "smartInvest",
  "loan",
  "portfolio",
  "secondary",
  "balances",
  "fx",
  "documents",
  "notifications",
  "settings",
  "faq"
];

function readStoredRoute(): AppRoute {
  const storedRoute = readStoredObject<Partial<AppRoute>>(appRouteStorageKey, {});
  return storedRoute.name && routeNames.includes(storedRoute.name)
    ? { name: storedRoute.name, params: storedRoute.params }
    : { name: "public" };
}

function routeFromPathname(pathname: string): AppRoute | null {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  const directRoutes: Record<string, RouteName> = {
    "/": "public",
    "/faq": "publicFaq",
    "/help": "publicFaq",
    "/login": "login",
    "/register": "register",
    "/verification": "kyc",
    "/dashboard": "dashboard",
    "/marketplace": "market",
    "/smart-invest": "smartInvest",
    "/portfolio": "portfolio",
    "/secondary-market": "secondary",
    "/balances": "balances",
    "/fx": "fx",
    "/documents": "documents",
    "/notifications": "notifications",
    "/settings": "settings",
    "/portal/help": "faq"
  };
  if (directRoutes[normalized]) return { name: directRoutes[normalized] };
  const loanMatch = normalized.match(/^\/marketplace\/([^/]+)$/);
  if (!loanMatch) return null;
  try {
    return { name: "loan", params: { loanId: decodeURIComponent(loanMatch[1]) } };
  } catch {
    return null;
  }
}

function routePath(route: AppRoute) {
  const paths: Record<RouteName, string> = {
    public: "/",
    publicFaq: "/faq",
    login: "/login",
    register: "/register",
    kyc: "/verification",
    dashboard: "/dashboard",
    market: "/marketplace",
    smartInvest: "/smart-invest",
    loan: `/marketplace/${encodeURIComponent(route.params?.loanId ?? "")}`,
    portfolio: "/portfolio",
    secondary: "/secondary-market",
    balances: "/balances",
    fx: "/fx",
    documents: "/documents",
    notifications: "/notifications",
    settings: "/settings",
    faq: "/portal/help"
  };
  return paths[route.name];
}

function e164PhoneNumber(callingCode: string, nationalNumber: string) {
  const digits = nationalNumber.replace(/\D/g, "").replace(/^0+/, "");
  return digits ? `${callingCode}${digits}` : "";
}

function normalizedEmail(value: string) {
  return value.trim().toLowerCase();
}

function defaultRegisterFlowState(): RegisterFlowState {
  return {
    step: 0,
    firstName: isFixturePreview ? "Lukas" : "",
    lastName: isFixturePreview ? "Brunner" : "",
    email: isFixturePreview ? portalFixture.profile.email : "",
    phoneCountryCode: "+41",
    phoneNationalNumber: isFixturePreview ? "79 000 00 00" : "",
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

function splitDisplayName(fullName: string) {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return { firstName: "", lastName: "" };
  if (parts.length === 1) return { firstName: parts[0], lastName: "" };
  return { firstName: parts[0], lastName: parts.slice(1).join(" ") };
}

function resumedRegisterStateForUser(user: UserSummary): RegisterFlowState | null {
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

function resumeOnboardingForUser(user: UserSummary, setRoute: (route: AppRoute) => void) {
  const registerState = resumedRegisterStateForUser(user);
  if (!registerState) return false;
  writeStoredObject(registerFlowStorageKey, registerState);
  goTo(setRoute, "register");
  return true;
}

function retryAfterSeconds(error: unknown) {
  if (error instanceof ApiClientError && error.payload && typeof error.payload === "object") {
    const payload = error.payload as Record<string, unknown>;
    if (typeof payload.retry_after_seconds === "number") {
      return payload.retry_after_seconds;
    }
    if (typeof payload.wait === "number") {
      return payload.wait;
    }
    const detail = typeof payload.detail === "string" ? payload.detail : "";
    const match = detail.match(/(\d+)\s+seconds?/i);
    if (match) return Number.parseInt(match[1], 10);
  }
  return undefined;
}

function useSecondsUntil(untilMs: number) {
  const [nowMs, setNowMs] = useState(Date.now());
  useEffect(() => {
    if (untilMs <= Date.now()) {
      setNowMs(Date.now());
      return undefined;
    }
    setNowMs(Date.now());
    const timer = window.setInterval(() => {
      const now = Date.now();
      setNowMs(now);
      if (untilMs <= now) {
        window.clearInterval(timer);
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [untilMs]);
  return Math.max(0, Math.ceil((untilMs - nowMs) / 1000));
}

const routeTitles: Record<RouteName, string> = {
  public: platformName,
  publicFaq: "Help & FAQ",
  login: "Log in",
  register: "Register",
  kyc: "Verification",
  dashboard: "Dashboard",
  market: "Investment Opportunities",
  smartInvest: "Smart Invest",
  loan: "Investment Opportunities",
  portfolio: "My Portfolio",
  secondary: "Secondary Market",
  balances: "Balances",
  fx: "Currency Exchange",
  documents: "Documents",
  notifications: "Notifications",
  settings: "Settings",
  faq: "Help & FAQ"
};

const navGroups: Array<{
  label: string;
  items: Array<{ route: RouteName; label: string; icon: Parameters<typeof Icon>[0]["name"] }>;
}> = [
  {
    label: "Invest",
    items: [
      { route: "dashboard", label: "Dashboard", icon: "dashboard" },
      { route: "market", label: "Investment Opportunities", icon: "market" },
      { route: "smartInvest", label: "Smart Invest", icon: "trend" },
      { route: "portfolio", label: "My Portfolio", icon: "portfolio" },
      { route: "secondary", label: "Secondary Market", icon: "secondary" }
    ]
  },
  {
    label: "Money",
    items: [
      { route: "balances", label: "Balances", icon: "balance" },
      { route: "fx", label: "FX", icon: "swap" }
    ]
  },
  {
    label: "Account",
    items: [
      { route: "documents", label: "Documents", icon: "docs" },
      { route: "settings", label: "Settings", icon: "settings" },
      { route: "faq", label: "Help & FAQ", icon: "info" }
    ]
  }
];

const legalDocumentTitles: Record<string, string> = {
  registration: "Lender user agreement",
  primary_market_investment: "Investment terms and loan claim assignment",
  secondary_market_listing: "Secondary-market seller/listing terms",
  secondary_market_purchase: "Secondary-market buyer terms",
  risk_disclosure: "Generic P2P lending risk disclosure"
};

function legalDocumentPath(category: string) {
  return `/legal/${category.replace(/_/g, "-")}`;
}

function renderLegalBody(body: string): ReactNode {
  const resolved = body
    .replace(/\{\{\s*platform\.name\s*\}\}/g, platformName)
    .replace(/\{\{\s*operator\.name\s*\}\}/g, operatorName)
    .replace(/\{\{\s*platform\.support_email\s*\}\}/g, supportEmail)
    .replace(/\{\{\s*([\w.]+)\s*\}\}/g, "[$1]");
  return resolved.split(/\n\n+/).map((rawBlock, index) => {
    const block = rawBlock.trim();
    if (!block) return null;
    const heading = block.match(/^(#{1,3})\s+([\s\S]*)$/);
    if (heading) {
      const text = heading[2].trim();
      return heading[1].length === 1 ? <h2 key={index}>{text}</h2> : <h3 key={index}>{text}</h3>;
    }
    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    if (lines.length > 1 && lines.every((line) => line.startsWith("|"))) {
      const rows = lines.map((line) => line.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
      const [head, ...rest] = rows;
      return (
        <table className="legal-doc-table" key={index}>
          <thead><tr>{head.map((cell, cellIndex) => <th key={cellIndex}>{cell}</th>)}</tr></thead>
          <tbody>
            {rest
              .filter((cells) => !cells.every((cell) => /^[-\s:]*$/.test(cell)))
              .map((cells, rowIndex) => (
                <tr key={rowIndex}>{cells.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>
              ))}
          </tbody>
        </table>
      );
    }
    if (lines.length > 0 && lines.every((line) => /^[-*]\s+/.test(line))) {
      return (
        <ul key={index}>
          {lines.map((line, lineIndex) => <li key={lineIndex}>{line.replace(/^[-*]\s+/, "")}</li>)}
        </ul>
      );
    }
    return <p key={index}>{block}</p>;
  });
}

function LegalDocLink({ category, children }: { category: string; children: ReactNode }) {
  return (
    <a
      className="doc-link"
      href={legalDocumentPath(category)}
      rel="noopener noreferrer"
      target="_blank"
    >
      {children}
      <span aria-hidden="true" className="doc-link-arrow">&#8599;</span>
    </a>
  );
}

function idempotencyKey(prefix: string) {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  return `${prefix}:${random}`;
}

function apiErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Request failed. Retry once the connection is restored.";
}

function isZurichWeekend(date = new Date()) {
  try {
    const weekday = new Intl.DateTimeFormat("en-US", {
      timeZone: "Europe/Zurich",
      weekday: "short"
    }).format(date);
    return weekday === "Sat" || weekday === "Sun";
  } catch {
    return date.getDay() === 0 || date.getDay() === 6;
  }
}

function templateLabels(template: PublicDocumentTemplateVersion | undefined) {
  return Array.isArray(template?.checkbox_labels)
    ? template.checkbox_labels.filter((label): label is string => typeof label === "string")
    : [];
}

function copyTextFallback(text: string) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.left = "-9999px";
  textarea.style.position = "fixed";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function CopyIdButton({
  id,
  label = "Copy ID",
  ariaLabel,
  iconOnly = false
}: {
  id: string;
  label?: string;
  ariaLabel?: string;
  iconOnly?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const accessibleLabel = copied ? "Copied" : (ariaLabel ?? label);
  return (
    <Button
      aria-label={accessibleLabel}
      className={`copy-id-btn${iconOnly ? " icon-only" : ""}`}
      icon="copy"
      size="sm"
      title={accessibleLabel}
      variant="ghost"
      onClick={(event) => {
        event.stopPropagation();
        const done = () => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1400);
        };
        const writeClipboard = navigator.clipboard?.writeText?.bind(navigator.clipboard);
        if (writeClipboard) {
          void writeClipboard(id).then(done).catch(() => {
            copyTextFallback(id);
            done();
          });
          return;
        }
        copyTextFallback(id);
        done();
      }}
    >
      {iconOnly ? null : (copied ? "Copied" : label)}
    </Button>
  );
}

function EntityReference({
  title,
  id,
  idLabel = "Copy ID",
  meta
}: {
  title: ReactNode;
  id?: string;
  idLabel?: string;
  meta?: ReactNode;
}) {
  return (
    <div className="entity-ref">
      <div className="col-strong">{title}</div>
      {(id || meta) ? (
        <div className="entity-ref-meta">
          {meta ? <span className="sub">{meta}</span> : null}
          {id ? <CopyIdButton ariaLabel={idLabel} id={id} label={idLabel} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function useSensitiveActionCode(action: ActionEnum) {
  const requestMutation = useV1AuthSensitiveActionCodeRequestCreate();
  const [codeId, setCodeId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(0);
  const [error, setError] = useState("");
  const resendCooldownSeconds = useSecondsUntil(resendCooldownUntil);

  const requestCode = useCallback(() => {
    setError("");
    if (isFixturePreview) {
      setCodeId("00000000-0000-0000-0000-000000000000");
      setExpiresAt(new Date(Date.now() + 10 * 60 * 1000).toISOString());
      setResendCooldownUntil(Date.now() + 60_000);
      return;
    }
    requestMutation.mutate(
      { data: { action } },
      {
        onSuccess: (response) => {
          setCodeId(response.code_id);
          setExpiresAt(response.expires_at);
          setResendCooldownUntil(Date.now() + 60_000);
        },
        onError: (mutationError) => {
          const waitSeconds = retryAfterSeconds(mutationError);
          if (waitSeconds) {
            setResendCooldownUntil(Date.now() + waitSeconds * 1000);
          }
          setError(apiErrorMessage(mutationError));
        }
      }
    );
  }, [action, requestMutation]);

  return { codeId, expiresAt, error, isRequesting: requestMutation.isPending, resendCooldownSeconds, requestCode };
}

function useAutoRequestEmailCode(
  codeRequest: Pick<ReturnType<typeof useSensitiveActionCode>, "codeId" | "isRequesting" | "requestCode">,
  active: boolean
) {
  const requestedRef = useRef(false);
  useEffect(() => {
    if (!active) {
      requestedRef.current = false;
      return;
    }
    if (isFixturePreview || requestedRef.current || codeRequest.codeId || codeRequest.isRequesting) {
      return;
    }
    requestedRef.current = true;
    codeRequest.requestCode();
  }, [active, codeRequest]);
}

function CodeRequestField({
  label,
  hint,
  value,
  onChange,
  requestLabel,
  requestDisabled = false,
  onRequest,
  placeholder = "000000"
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  requestLabel?: string;
  requestDisabled?: boolean;
  onRequest?: () => void;
  placeholder?: string;
}) {
  return (
    <Field hint={hint} label={label}>
      <div className={requestLabel ? "code-request-row" : undefined}>
        <input
          aria-label={label}
          autoComplete="one-time-code"
          className="input mono"
          inputMode="numeric"
          maxLength={6}
          onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
          placeholder={placeholder}
          value={value}
        />
        {requestLabel && onRequest ? (
          <Button
            className="code-request-button"
            disabled={requestDisabled}
            variant="ghost"
            onClick={onRequest}
          >
            {requestLabel}
          </Button>
        ) : null}
      </div>
    </Field>
  );
}

function emailCodeRequestLabel(
  codeRequest: Pick<ReturnType<typeof useSensitiveActionCode>, "codeId" | "isRequesting" | "resendCooldownSeconds">
) {
  if (codeRequest.isRequesting) return "Sending code...";
  if (codeRequest.resendCooldownSeconds > 0) {
    return codeRequest.codeId
      ? `Code sent. Send new in ${codeRequest.resendCooldownSeconds}s`
      : `Send new in ${codeRequest.resendCooldownSeconds}s`;
  }
  return codeRequest.codeId ? "Send a new email code" : "Send email code";
}

function emailCodeRequestDisabled(
  codeRequest: Pick<ReturnType<typeof useSensitiveActionCode>, "isRequesting" | "resendCooldownSeconds">
) {
  return codeRequest.isRequesting || codeRequest.resendCooldownSeconds > 0;
}

function sourceLabel(sourceType: string) {
  return sourceType
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function fundingPercent(loan: Pick<MarketplaceLoanPreview, "principal_minor" | "committed_principal_minor">) {
  if (loan.principal_minor <= 0) return 0;
  return Math.round((loan.committed_principal_minor / loan.principal_minor) * 100);
}

function isOriginatorClaimLoan(
  loan: Pick<MarketplaceLoanPreview, "product_type">
) {
  return loan.product_type === "originator_claim";
}

function marketplaceYieldBps(
  loan: Pick<MarketplaceLoanPreview, "yield_bps" | "interest_rate_bps">
) {
  return loan.yield_bps || loan.interest_rate_bps;
}

function marketplaceAvailableMinor(
  loan: Pick<MarketplaceLoanPreview, "fillable_amount_minor" | "remaining_capacity_minor">
) {
  return loan.fillable_amount_minor ?? loan.remaining_capacity_minor;
}

function marketplaceClosingKey(
  loan: Pick<MarketplaceLoanPreview, "funding_deadline" | "maturity_date">
) {
  return loan.funding_deadline ?? loan.maturity_date ?? "9999-12-31";
}

function marketplaceCurrencySymbol(currency: string) {
  if (currency === "EUR") return "€";
  if (currency === "CHF") return "CHF";
  return currency;
}

function fundingDeadlineLabel(deadline: string, asOf?: string) {
  const currentKey = asOf?.slice(0, 10) || zurichDateKey(new Date());
  const deadlineTime = Date.parse(`${deadline}T00:00:00Z`);
  const currentTime = Date.parse(`${currentKey}T00:00:00Z`);
  if (!Number.isFinite(deadlineTime) || !Number.isFinite(currentTime)) return formatDate(deadline);
  const days = Math.max(0, Math.round((deadlineTime - currentTime) / 86_400_000));
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
}

function currentInvestableLotsForLoanCurrency(
  lots: BalanceLot[] | undefined,
  loan: Pick<MarketplaceLoanPreview, "currency">
) {
  return (lots ?? []).filter(
    (lot) =>
      lot.currency === loan.currency &&
      lot.status === "available" &&
      lot.bucket === "investable" &&
      lot.available_amount_minor > 0
  );
}

function sumLotAvailableMinor(lots: BalanceLot[]) {
  return lots.reduce((total, lot) => total + lot.available_amount_minor, 0);
}

function isOpenMarketplaceLoan(
  loan: Pick<
    MarketplaceLoanPreview,
    "status" | "opportunity_status" | "fillable_amount_minor" | "remaining_capacity_minor"
  >
) {
  const openStatus = ["open", "published"].includes(loan.status)
    || loan.opportunity_status === "open";
  return openStatus && marketplaceAvailableMinor(loan) > 0;
}

function statusTone(status: string) {
  if (["funded", "performing", "active", "approved"].includes(status)) return "ok" as const;
  if (["late", "overdue", "pending", "pending_allocation", "partially_allocated"].includes(status)) return "warn" as const;
  if (["default", "defaulted", "written_off", "penalty"].includes(status)) return "bad" as const;
  return "neutral" as const;
}

function goTo(setRoute: (route: AppRoute) => void, name: RouteName, params?: Record<string, string>) {
  const nextRoute = { name, params };
  writeStoredObject(appRouteStorageKey, nextRoute);
  const nextPath = routePath(nextRoute);
  if (window.location.pathname !== nextPath) {
    window.history.pushState({}, "", nextPath);
  }
  setRoute(nextRoute);
  window.scrollTo({ top: 0, behavior: "instant" });
}

function clearPortalSessionState(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.clear();
  removeStoredObject(loginFlowStorageKey);
  removeStoredObject(registerFlowStorageKey);
}

export function App() {
  const pathRoute = routeFromPathname(window.location.pathname);
  const initialRoute: AppRoute = readReadonlyImpersonationToken()
    ? pathRoute && !["public", "publicFaq", "login", "register"].includes(pathRoute.name)
      ? pathRoute
      : { name: "dashboard" }
    : pathRoute?.name === "public"
      ? readStoredRoute()
      : pathRoute ?? readStoredRoute();
  const [route, setRoute] = useState<AppRoute>(initialRoute);
  const [demoState, setDemoState] = useState<DemoAccountState>("active");

  useEffect(() => {
    const onPopState = () => {
      const nextRoute = routeFromPathname(window.location.pathname) ?? { name: "public" as const };
      writeStoredObject(appRouteStorageKey, nextRoute);
      setRoute(nextRoute);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (window.location.pathname.startsWith("/admin")) {
    return <AdminApp />;
  }

  if (window.location.pathname.startsWith("/kyc/callback")) {
    return <KycReturnScreen setRoute={setRoute} />;
  }

  if (window.location.pathname.startsWith("/legal/")) {
    return <LegalDocumentPage />;
  }

  if (route.name === "public") {
    return <PublicLanding setRoute={setRoute} />;
  }

  if (route.name === "publicFaq") {
    return <PublicFaqPage setRoute={setRoute} />;
  }

  if (route.name === "login") {
    return <LoginFlow setRoute={setRoute} />;
  }

  if (route.name === "register") {
    return <RegisterFlow setRoute={setRoute} />;
  }

  return (
    <InvestorShell
      demoState={demoState}
      route={route}
      setDemoState={setDemoState}
      setRoute={setRoute}
    />
  );
}

function Wordmark({ compact = false }: { compact?: boolean }) {
  const isBanxum = platformName.toUpperCase() === "BANXUM";
  return (
    <div className={`investor-brand ${compact ? "compact" : ""}`}>
      {isBanxum ? (
        <span className="investor-brand-art">
          <img
            alt={platformName}
            src="/brand/logo-symbol.png"
          />
        </span>
      ) : (
        <span className="investor-brand-word">
          {platformName}
        </span>
      )}
      <span className="investor-brand-operator">by {operatorName}</span>
    </div>
  );
}

function PublicLanding({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const loansQuery = useMarketplaceLoansData();
  const loans = loansQuery.data ?? [];
  const [previewLoanId, setPreviewLoanId] = useState<string | null>(null);
  const previewLoan = loans.find((loan) => loan.loan_id === previewLoanId);

  return (
    <div className="public">
      <header className="public-top">
        <Wordmark />
        <div className="grow" />
        <nav className="public-nav" aria-label="Public navigation">
          <a href="/faq" onClick={(event) => { event.preventDefault(); goTo(setRoute, "publicFaq"); }}>How it works</a>
          <a href="/faq" onClick={(event) => { event.preventDefault(); goTo(setRoute, "publicFaq"); }}>FAQ</a>
        </nav>
        <Button variant="ghost" onClick={() => goTo(setRoute, "login")}>
          Log in
        </Button>
        <Button variant="primary" onClick={() => goTo(setRoute, "register")}>
          Register
        </Button>
      </header>
      {previewLoan ? (
        <main className="public-body">
          <div className="public-mobile-links" aria-label="Public links">
            <button className="btn-link" onClick={() => goTo(setRoute, "publicFaq")} type="button">How it works</button>
            <button className="btn-link" onClick={() => goTo(setRoute, "publicFaq")} type="button">FAQ</button>
          </div>
          <PublicLoanPreview
            loan={previewLoan}
            onBack={() => setPreviewLoanId(null)}
            setRoute={setRoute}
          />
        </main>
      ) : (
        <>
          <main className="public-body landing">
            <div className="public-mobile-links" aria-label="Public links">
              <button className="btn-link" onClick={() => goTo(setRoute, "publicFaq")} type="button">How it works</button>
              <button className="btn-link" onClick={() => goTo(setRoute, "publicFaq")} type="button">FAQ</button>
            </div>
            <div className="page-head">
              <div>
                <h1>Open loan opportunities</h1>
                <div className="ph-sub">
                  Preview current primary-market loans. Borrower documents, ratings, collateral detail and
                  investing unlock after registration and identity verification.
                </div>
                <p className="lede-line">
                  Review project-specific business loans, their repayment schedules, risks, and any disclosed security before deciding whether to invest.
                </p>
              </div>
            </div>
            <div className="preview-banner">
              <Icon className="muted" name="lock" size={17} />
              <div className="grow muted-2" style={{ fontSize: 13 }}>
                <b>Preview mode.</b> You are seeing limited fields. Register as an individual lender in
                Switzerland or the EU/EEA to see full loan data and invest.
              </div>
              <Button size="sm" variant="primary" onClick={() => goTo(setRoute, "register")}>
                Get started
              </Button>
              {isFixturePreview ? (
                <Button size="sm" variant="ghost" onClick={() => goTo(setRoute, "dashboard")}>
                  Open dummy portal
                </Button>
              ) : null}
            </div>
            {loansQuery.isError && loans.length === 0 ? (
              <DataErrorCard
                title="Could not load loan previews"
                onRetry={() => void loansQuery.refetch()}
              >
                We could not reach the marketplace API. Try again, or register later when live data is available.
              </DataErrorCard>
            ) : loansQuery.isLoading && loans.length === 0 ? (
              <LoadingCard title="Loading loan previews">Fetching current marketplace opportunities.</LoadingCard>
            ) : (
              <LoansTable loans={loans} onOpen={(loan) => setPreviewLoanId(loan.loan_id)} preview />
            )}
            <p className="muted" style={{ fontSize: 11.5, marginTop: 14, maxWidth: 760 }}>
              {platformName} facilitates peer-to-peer loan claim participations operated by{" "}
              {operatorName}. Investing involves risk of capital loss and is not a bank deposit,
              fund unit, trading venue, or guaranteed-return product.
            </p>
          </main>
          <LandingMarketing setRoute={setRoute} />
        </>
      )}
    </div>
  );
}

function LandingMarketing({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const steps = [
    {
      n: "01",
      icon: "shield" as const,
      title: "We originate and vet",
      desc: `${operatorName} sources, underwrites and services business loans across Switzerland and the EU/EEA. Each published project carries its own risk, repayment, and security disclosures.`
    },
    {
      n: "02",
      icon: "market" as const,
      title: "You choose and invest",
      desc: `Browse the marketplace and buy a participation in the loan claims you pick, from CHF / EUR 1,000. Spread your capital across borrowers, sectors and currencies.`
    },
    {
      n: "03",
      icon: "trend" as const,
      title: "You earn as they repay",
      desc: `When borrowers pay, allocated interest and principal are credited to your balance. Repayments can be late or incomplete, and secondary-market liquidity is not guaranteed.`
    }
  ];

  const facts: Array<{ fig: ReactNode; k: string; d: string }> = [
    {
      fig: <>Project-specific</>,
      k: "Interest and repayment",
      d: "Rates and repayment structures are disclosed for each loan. Returns are targets, not guarantees."
    },
    {
      fig: <>1,000<span className="u"> +</span></>,
      k: "Minimum per loan",
      d: "CHF or EUR. A low entry point so you can diversify widely from the start."
    },
    {
      fig: <>Scheduled</>,
      k: "Repayment cash flow",
      d: "Every project shows its contractual schedule and repayment type before you invest."
    },
    {
      fig: <>Disclosed</>,
      k: "Security and collateral",
      d: "Collateral, guarantees, and unsecured exceptions are shown per project and never guarantee recovery."
    }
  ];

  return (
    <>
      <section className="lband surface">
        <div className="lband-inner">
          <div className="lband-eyebrow">What we do</div>
          <h2 className="lband-title">Private lending, opened up to individuals</h2>
          <p className="lband-lede">
            {platformName} lets you invest directly in business-loan claim participations — a form of private credit
            that was, until recently, the preserve of banks and institutional funds. We handle origination,
            underwriting and servicing; you choose where your money goes.
          </p>
          <div className="steps">
            {steps.map((step) => (
              <div className="step" key={step.n}>
                <div className="step-n">{step.n}</div>
                <div className="step-icon"><Icon name={step.icon} size={18} /></div>
                <h3>{step.title}</h3>
                <p>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lband dark">
        <div className="lband-inner">
          <div className="lband-eyebrow">Why investors choose private credit</div>
          <h2 className="lband-title">An income-generating asset class, beyond stocks and bonds</h2>
          <p className="lband-lede">
            Returns come from borrowers repaying real loans — driven by contractual interest, not market
            sentiment — which historically gives private credit low correlation to public equity markets
            and a steady stream of cash flow.
          </p>
          <div className="facts">
            {facts.map((fact) => (
              <div className="fact" key={fact.k}>
                <div className="fact-fig">{fact.fig}</div>
                <div className="fact-k">{fact.k}</div>
                <div className="fact-d">{fact.d}</div>
              </div>
            ))}
          </div>
          <p className="dark-caveat">
            Peer-to-peer lending carries risk: borrowers may pay late or default, collateral or guarantees
            may be absent or may not fully cover losses, capital is at risk,
            and an early exit on the secondary market is not guaranteed. Platform balances are not bank
            deposits and returns are not guaranteed.
          </p>
          <div className="dark-cta">
            <Button size="lg" variant="primary" onClick={() => goTo(setRoute, "register")}>
              Create your investor account
            </Button>
            <a href="/faq" onClick={(event) => { event.preventDefault(); goTo(setRoute, "publicFaq"); }}>Read how it works →</a>
          </div>
        </div>
      </section>
    </>
  );
}

function PublicLoanPreview({
  loan,
  onBack,
  setRoute
}: {
  loan: MarketplaceLoanPreview;
  onBack: () => void;
  setRoute: (route: AppRoute) => void;
}) {
  return (
    <div>
      <button className="backlink" onClick={onBack} type="button">
        <Icon name="arrowL" size={14} /> All loans
      </button>
      <div className="split">
        <div>
          <div className="row gap-8 wrap" style={{ marginBottom: 6 }}>
            <Chip status={loan.status} />
            <span className="tag">{loan.currency}</span>
            <span className="tag">{loan.purpose}</span>
            {loan.is_refinancing ? <RefinancedTag full /> : null}
          </div>
          <h1>{loan.title}</h1>
          <div className="ph-sub"><CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" /></div>
          <Card className="section" padded>
            <div className="grid grid-4" style={{ gap: 0 }}>
              <Stat amountMinor={loan.principal_minor} currency={loan.currency} label="Amount" />
              <Stat label="Target interest" raw={formatRateBps(loan.interest_rate_bps)} sub="per annum" />
              <Stat label="Term" raw={`${loan.term_months} mo`} />
              <Stat label="Status" raw={loan.status} />
            </div>
          </Card>
          <Card className="section" padded>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Full loan data</div>
            <Banner icon="lock" tone="neutral" title="Registration required">
              Complete registration, phone verification and KYC to unlock borrower disclosures,
              collateral, documents, LTV, risk rating and investment actions.
            </Banner>
          </Card>
        </div>
        <aside className="aside-sticky">
          <Card padded>
            <h3 style={{ fontSize: 15, marginBottom: 8 }}>Invest with {platformName}</h3>
            <div className="col gap-8 muted-2" style={{ fontSize: 13 }}>
              <span className="row gap-8"><Icon name="check" size={15} />Individual lenders in CH and EU/EEA</span>
              <span className="row gap-8"><Icon name="check" size={15} />Minimum CHF/EUR 1,000 per order</span>
              <span className="row gap-8"><Icon name="check" size={15} />Claim participation documents</span>
            </div>
            <Button block variant="primary" style={{ marginTop: 14 }} onClick={() => goTo(setRoute, "register")}>
              Create account
            </Button>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function LoginFlow({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const [initialLoginState] = useState(() =>
    readStoredObject<LoginFlowState>(loginFlowStorageKey, {
      email: "",
      sent: false,
      linkExpired: false,
      resendCooldownUntil: 0
    })
  );
  const [email, setEmail] = useState(initialLoginState.email);
  const [sent, setSent] = useState(initialLoginState.sent);
  const [linkExpired, setLinkExpired] = useState(initialLoginState.linkExpired);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(
    initialLoginState.resendCooldownUntil
  );
  const [isConsuming, setIsConsuming] = useState(false);
  const [error, setError] = useState("");
  const magicLinkRequest = useV1AuthMagicLinkRequestCreate();
  const resendCooldownSeconds = useSecondsUntil(resendCooldownUntil);

  useEffect(() => {
    writeStoredObject(loginFlowStorageKey, {
      email,
      sent,
      linkExpired,
      resendCooldownUntil
    });
  }, [email, linkExpired, resendCooldownUntil, sent]);

  const consumeAttemptedRef = useRef(false);
  const loginFlowMountedRef = useRef(false);

  useEffect(() => {
    loginFlowMountedRef.current = true;
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token || isFixturePreview) {
      return () => {
        loginFlowMountedRef.current = false;
      };
    }
    // The token is single-use: never fire a second consume request even if
    // the effect re-runs (e.g. StrictMode's development effect replay).
    if (consumeAttemptedRef.current) {
      return () => {
        loginFlowMountedRef.current = false;
      };
    }
    consumeAttemptedRef.current = true;
    setIsConsuming(true);
    void v1AuthMagicLinkConsumeCreate({ token })
      .then((response) => {
        if (!loginFlowMountedRef.current) return;
        removeStoredObject(loginFlowStorageKey);
        window.history.replaceState({}, "", "/");
        if (resumeOnboardingForUser(response.user, setRoute)) return;
        removeStoredObject(registerFlowStorageKey);
        goTo(setRoute, "dashboard");
      })
      .catch((mutationError: unknown) => {
        if (!loginFlowMountedRef.current) return;
        if (mutationError instanceof ApiClientError && mutationError.status === 400) {
          const url = new URL(window.location.href);
          url.searchParams.delete("token");
          window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
          setError("");
          setLinkExpired(true);
          return;
        }
        setError(apiErrorMessage(mutationError));
      })
      .finally(() => {
        if (loginFlowMountedRef.current) setIsConsuming(false);
      });

    return () => {
      loginFlowMountedRef.current = false;
    };
  }, [setRoute]);

  const requestMagicLink = () => {
    if (magicLinkRequest.isPending || resendCooldownSeconds > 0) return;
    setError("");
    if (isFixturePreview) {
      setSent(true);
      setLinkExpired(false);
      setResendCooldownUntil(Date.now() + 60_000);
      return;
    }
    magicLinkRequest.mutate(
      { data: { email } },
      {
        onSuccess: () => {
          setSent(true);
          setLinkExpired(false);
          setResendCooldownUntil(Date.now() + 60_000);
        },
        onError: (mutationError) => {
          const waitSeconds = retryAfterSeconds(mutationError);
          if (waitSeconds) {
            setResendCooldownUntil(Date.now() + waitSeconds * 1000);
          }
          setError(apiErrorMessage(mutationError));
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
    setResendCooldownUntil(0);
    setError("");
  };

  const resendLabel = magicLinkRequest.isPending
    ? "Sending..."
    : resendCooldownSeconds > 0
      ? `Link sent. Send new in ${resendCooldownSeconds}s`
      : "Send a new magic link";
  const resendDisabled =
    !email.includes("@") || magicLinkRequest.isPending || resendCooldownSeconds > 0;

  function submitMagicLink(event: FormEvent) {
    event.preventDefault();
    requestMagicLink();
  }

  if (isConsuming) {
    return (
      <AuthShell onClose={() => goTo(setRoute, "public")}>
        <div className="auth-card"><Empty icon="clock" title="Signing you in">Verifying your one-time login link.</Empty></div>
      </AuthShell>
    );
  }

  return (
    <AuthShell onClose={() => goTo(setRoute, "public")}>
      <div className="auth-card">
        {linkExpired ? (
          <div className="col" style={{ alignItems: "center", gap: 14, textAlign: "center" }}>
            <div className="avatar" style={{ height: 50, width: 50 }}>
              <Icon name="clock" size={22} />
            </div>
            <h2 style={{ fontSize: 18 }}>Login link expired</h2>
            <p className="muted" style={{ fontSize: 13 }}>
              This login link has expired or is no longer valid. Request a new link to continue.
            </p>
            {email ? (
              <p className="muted" style={{ fontSize: 13 }}>
                We will send the new link to <b>{email}</b>.
              </p>
            ) : (
              <div style={{ textAlign: "left", width: "100%" }}>
                <Field label="Email address">
                  <input
                    className="input"
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    type="email"
                    value={email}
                  />
                </Field>
              </div>
            )}
            {error ? <Banner tone="bad" title="Could not send a new link">{error}</Banner> : null}
            <Button block disabled={resendDisabled} variant="primary" onClick={requestMagicLink}>
              {resendLabel}
            </Button>
            {email ? (
              <Button variant="link" onClick={resetLoginFlow}>
                Use a different email address
              </Button>
            ) : null}
            <p className="muted" style={{ fontSize: 11.5 }}>
              Lost access to your email is handled through support after identity re-verification.
            </p>
          </div>
        ) : !sent ? (
          <form className="col" data-testid="login-magic-link-form" onSubmit={submitMagicLink}>
            <h2 style={{ fontSize: 19, marginBottom: 4 }}>Log in</h2>
            <p className="muted" style={{ fontSize: 13, marginBottom: 20 }}>
              We will email a secure magic link. No password is required for investor access.
            </p>
            <Field label="Email address">
              <input className="input" onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" type="email" value={email} />
            </Field>
            {error ? <Banner tone="bad" title="Could not continue">{error}</Banner> : null}
            <Button block disabled={!email.includes("@") || magicLinkRequest.isPending} style={{ marginTop: 16 }} type="submit" variant="primary">
              {magicLinkRequest.isPending ? "Sending..." : "Send magic link"}
            </Button>
            <div className="hr" style={{ margin: "18px 0" }} />
            <p className="center muted" style={{ fontSize: 12.5 }}>
              New to {platformName}? <a href="/register" onClick={(event) => { event.preventDefault(); goTo(setRoute, "register"); }}>Register as a lender</a>
            </p>
          </form>
        ) : (
          <div className="col" style={{ alignItems: "center", gap: 14, textAlign: "center" }}>
            <div className="avatar" style={{ height: 50, width: 50 }}>
              <Icon name="bell" size={22} />
            </div>
            <h2 style={{ fontSize: 18 }}>Check your inbox</h2>
            <p className="muted" style={{ fontSize: 13 }}>
              We sent a magic link to <b>{email}</b>. It expires in 15 minutes.
            </p>
            {error ? <Banner tone="bad" title="Could not send a new link">{error}</Banner> : null}
            <Button block disabled={resendDisabled} onClick={requestMagicLink}>
              {resendLabel}
            </Button>
            {isFixturePreview ? <Button block variant="primary" onClick={() => goTo(setRoute, "dashboard")}>
              Open link in demo
            </Button> : null}
            <Button variant="link" onClick={resetLoginFlow}>
              Use a different email address
            </Button>
            <p className="muted" style={{ fontSize: 11.5 }}>
              Lost access to your email is handled through support after identity re-verification.
            </p>
          </div>
        )}
      </div>
    </AuthShell>
  );
}

function KycReturnScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const authMeQuery = useV1AuthMeRetrieve({
    query: { enabled: !isFixturePreview, retry: false, staleTime: 0 }
  });
  const sessionUser = authMeQuery.data?.user;

  // The Didit redirect lands on /kyc/callback, which the SPA router does not
  // know; every exit must first restore the root path.
  const leaveTo = (name: RouteName) => {
    window.history.replaceState({}, "", "/");
    goTo(setRoute, name);
  };

  useEffect(() => {
    if (!sessionUser) return;
    // This browser holds the investor session, so verification was completed
    // on the same device: continue straight to the live verification status.
    removeStoredObject(registerFlowStorageKey);
    window.history.replaceState({}, "", "/");
    goTo(setRoute, "kyc");
  }, [sessionUser, setRoute]);

  if (!isFixturePreview && (authMeQuery.isPending || sessionUser)) {
    return (
      <AuthShell onClose={() => leaveTo("public")}>
        <div className="auth-card">
          <Empty icon="clock" title="Finishing identity verification">
            Returning you to your verification status.
          </Empty>
        </div>
      </AuthShell>
    );
  }

  // No session in this browser: the identity capture happened on a secondary
  // device (QR hand-off). The originating device keeps the session and picks
  // up the result automatically.
  return (
    <AuthShell onClose={() => leaveTo("public")}>
      <div className="auth-card">
        <div className="col" style={{ alignItems: "center", gap: 14, textAlign: "center" }}>
          <div className="avatar" style={{ height: 50, width: 50 }}>
            <Icon name="checkCircle" size={22} />
          </div>
          <h2 style={{ fontSize: 18 }}>Identity check submitted</h2>
          <p className="muted" style={{ fontSize: 13 }}>
            You can close this tab and return to the device where you started
            registration. It will continue automatically as soon as the
            verification result arrives.
          </p>
          <p className="muted" style={{ fontSize: 11.5 }}>
            Want to continue on this device instead?{" "}
            <a href="/login" onClick={(event) => { event.preventDefault(); leaveTo("login"); }}>Log in here</a>.
          </p>
        </div>
      </div>
    </AuthShell>
  );
}

function RegisterFlow({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const defaultRegisterState = defaultRegisterFlowState();
  const [initialRegisterState] = useState(() =>
    readStoredObject<RegisterFlowState>(registerFlowStorageKey, defaultRegisterState)
  );
  const [step, setStep] = useState(initialRegisterState.step);
  const [firstName, setFirstName] = useState(initialRegisterState.firstName);
  const [lastName, setLastName] = useState(initialRegisterState.lastName);
  const [email, setEmail] = useState(initialRegisterState.email);
  const [phoneCountryCode, setPhoneCountryCode] = useState(initialRegisterState.phoneCountryCode);
  const [phoneNationalNumber, setPhoneNationalNumber] = useState(initialRegisterState.phoneNationalNumber);
  const [residenceCountry, setResidenceCountry] = useState(initialRegisterState.residenceCountry);
  const [terms, setTerms] = useState(initialRegisterState.terms);
  const [registrationAcceptedLabels, setRegistrationAcceptedLabels] = useState(
    initialRegisterState.registrationAcceptedLabels
  );
  const [risk, setRisk] = useState(initialRegisterState.risk);
  const [marketing, setMarketing] = useState(initialRegisterState.marketing);
  const [emailLoginSent, setEmailLoginSent] = useState(initialRegisterState.emailLoginSent);
  const [phoneCode, setPhoneCode] = useState("");
  const [error, setError] = useState("");
  const registerMutation = useV1AuthRegisterNaturalPersonCreate();
  const registrationMagicLinkMutation = useV1AuthMagicLinkRequestCreate();
  const phoneRequestMutation = useV1AuthPhoneRequestCreate();
  const phoneConfirmMutation = useV1AuthPhoneConfirmCreate();
  const authMeQuery = useV1AuthMeRetrieve({
    query: {
      enabled: !isFixturePreview && step >= 1,
      retry: false,
      staleTime: 0
    }
  });
  const [phoneChallengeId, setPhoneChallengeId] = useState<string | null>(
    initialRegisterState.phoneChallengeId
  );
  const [phoneCooldownUntil, setPhoneCooldownUntil] = useState(initialRegisterState.phoneCooldownUntil);
  const [emailCooldownUntil, setEmailCooldownUntil] = useState(initialRegisterState.emailCooldownUntil);
  const [nowMs, setNowMs] = useState(Date.now());
  const kycSessionMutation = useV1KycSessionCreate();
  const registrationTermsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    {
      category: CategoryEnum.registration,
      template_key: "default",
      language: "en"
    },
    {
      query: {
        enabled: !isFixturePreview,
        retry: false,
        staleTime: 0
      }
    }
  );
  const riskDisclosureQuery = useV1DocumentsTemplatesCurrentRetrieve(
    {
      category: CategoryEnum.risk_disclosure,
      template_key: "default",
      language: "en"
    },
    {
      query: {
        enabled: !isFixturePreview,
        retry: false,
        staleTime: 0
      }
    }
  );
  const phoneNumber = e164PhoneNumber(phoneCountryCode, phoneNationalNumber);
  const phoneNumberLabel = phoneNumber || "your registered mobile number";
  const phoneCooldownSeconds = Math.max(0, Math.ceil((phoneCooldownUntil - nowMs) / 1000));
  const phoneRequestDisabled = phoneRequestMutation.isPending || phoneCooldownSeconds > 0;
  const emailCooldownSeconds = Math.max(0, Math.ceil((emailCooldownUntil - nowMs) / 1000));
  const registrationLabels = templateLabels(registrationTermsQuery.data);
  const riskLabels = templateLabels(riskDisclosureQuery.data);
  const allRegistrationTermsAccepted = isFixturePreview
    ? terms
    : registrationLabels.length > 0 &&
      registrationLabels.every((label) => registrationAcceptedLabels.includes(label));

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
  }, [
    email,
    emailCooldownUntil,
    emailLoginSent,
    firstName,
    lastName,
    marketing,
    phoneChallengeId,
    phoneCooldownUntil,
    phoneCountryCode,
    phoneNationalNumber,
    registrationAcceptedLabels,
    residenceCountry,
    risk,
    step,
    terms
  ]);

  useEffect(() => {
    if (phoneCooldownSeconds <= 0 && emailCooldownSeconds <= 0) return;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [emailCooldownSeconds, phoneCooldownSeconds]);

  const sessionUser = authMeQuery.data?.user;
  const hasMatchingSession =
    isFixturePreview ||
    (Boolean(sessionUser) && normalizedEmail(sessionUser?.email ?? "") === normalizedEmail(email));
  const hasDifferentSession =
    !isFixturePreview &&
    Boolean(sessionUser) &&
    normalizedEmail(sessionUser?.email ?? "") !== normalizedEmail(email);

  const kycStatusQuery = useV1KycStatusRetrieve({
    query: {
      enabled: !isFixturePreview && step === 2 && hasMatchingSession,
      retry: false,
      // Identity capture can happen on another device (QR hand-off), so keep
      // polling until the provider reports a result.
      refetchInterval: (query) => {
        const caseStatus = query.state.data?.status;
        return !caseStatus || caseStatus === "not_started" || caseStatus === "pending"
          ? 4000
          : false;
      }
    }
  });
  const kycCaseStatus = kycStatusQuery.data?.status;

  useEffect(() => {
    if (isFixturePreview || step !== 2 || !kycCaseStatus) return;
    if (kycCaseStatus === "not_started" || kycCaseStatus === "pending") return;
    // The provider produced a result: registration hand-off is complete, so
    // continue inside the account on this (already signed-in) device.
    removeStoredObject(registerFlowStorageKey);
    goTo(setRoute, kycCaseStatus === "approved" ? "dashboard" : "kyc");
  }, [kycCaseStatus, setRoute, step]);

  useEffect(() => {
    if (
      step === 1 &&
      sessionUser?.phone_verified &&
      normalizedEmail(sessionUser.email) === normalizedEmail(email)
    ) {
      setStep(2);
      setPhoneChallengeId(null);
      setPhoneCooldownUntil(0);
    }
  }, [email, sessionUser, step]);

  const requestRegistrationMagicLink = () => {
    if (!email.includes("@")) {
      setError("Enter a valid email address before requesting the sign-in link.");
      return;
    }
    setError("");
    if (isFixturePreview) {
      setEmailLoginSent(true);
      return;
    }
    registrationMagicLinkMutation.mutate(
      { data: { email } },
      {
        onSuccess: () => {
          setEmailLoginSent(true);
          setEmailCooldownUntil(Date.now() + 60_000);
          setNowMs(Date.now());
        },
        onError: (mutationError) => {
          const waitSeconds = retryAfterSeconds(mutationError);
          if (waitSeconds) {
            setEmailCooldownUntil(Date.now() + waitSeconds * 1000);
            setNowMs(Date.now());
          }
          if (waitSeconds && emailLoginSent) {
            // A link is already on its way; the button countdown tells the
            // user when resend unlocks, so no error banner is needed.
            return;
          }
          setError(apiErrorMessage(mutationError));
        }
      }
    );
  };

  const submitRegistration = () => {
    setError("");
    if (isFixturePreview) {
      setStep(1);
      setEmailLoginSent(true);
      return;
    }
    if (!registrationTermsQuery.data || registrationLabels.length === 0) {
      setError("The current lender user agreement is not available. Retry once it loads.");
      return;
    }
    if (!riskDisclosureQuery.data || riskLabels.length === 0) {
      setError("The current lender risk disclosure is not available. Retry once it loads.");
      return;
    }
    registerMutation.mutate(
      {
        data: {
          email,
          full_name: `${firstName} ${lastName}`.trim(),
          phone_number: phoneNumber,
          terms_version: registrationTermsVersion,
          terms_hash: registrationTermsHash,
          registration_document_template_version_id: registrationTermsQuery.data?.id,
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
          setStep(1);
          setPhoneCode("");
          setPhoneChallengeId(null);
          setPhoneCooldownUntil(0);
          setEmailLoginSent(response.email_login_sent);
          setEmailCooldownUntil(response.email_login_sent ? Date.now() + 60_000 : 0);
          setNowMs(Date.now());
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };

  const requestPhoneCode = () => {
    setError("");
    if (isFixturePreview) {
      setPhoneChallengeId("fixture-phone-challenge");
      setPhoneCooldownUntil(Date.now() + 60_000);
      setNowMs(Date.now());
      return;
    }
    if (!hasMatchingSession) {
      setError("Open your magic-link email in this browser before requesting the SMS code.");
      return;
    }
    phoneRequestMutation.mutate(undefined, {
      onSuccess: (response) => {
        if (response.phone_verified) {
          setStep(2);
          return;
        }
        setPhoneChallengeId(response.challenge_id);
        setPhoneCooldownUntil(Date.now() + 60_000);
        setNowMs(Date.now());
      },
      onError: (mutationError) => {
        const waitSeconds = retryAfterSeconds(mutationError);
        if (waitSeconds) {
          setPhoneCooldownUntil(Date.now() + waitSeconds * 1000);
          setNowMs(Date.now());
        }
        if (mutationError instanceof ApiClientError && mutationError.status === 403) {
          setError("Sign in with your magic-link email before requesting the SMS code.");
          return;
        }
        setError(apiErrorMessage(mutationError));
      }
    });
  };

  const confirmPhone = () => {
    setError("");
    if (isFixturePreview) {
      setStep(2);
      return;
    }
    if (!phoneChallengeId) {
      setError("Request an SMS code first.");
      return;
    }
    phoneConfirmMutation.mutate(
      { data: { challenge_id: phoneChallengeId, code: phoneCode } },
      {
        onSuccess: () => {
          setStep(2);
          setPhoneCooldownUntil(0);
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };

  const startKyc = () => {
    setError("");
    if (isFixturePreview) {
      goTo(setRoute, "kyc");
      return;
    }
    kycSessionMutation.mutate(undefined, {
      onSuccess: (response) => {
        if (response.verification_url) {
          window.location.assign(response.verification_url);
          return;
        }
        goTo(setRoute, "kyc");
      },
      onError: (mutationError) => setError(apiErrorMessage(mutationError))
    });
  };

  return (
    <AuthShell onClose={() => goTo(setRoute, "public")}>
      <div className="auth-card wide">
        <div className="auth-steps">
          {["Account", "Email and phone", "KYC"].map((label, index) => (
            <div aria-label={label} className={`s ${index < step ? "done" : index === step ? "cur" : ""}`} key={label} />
          ))}
        </div>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Step {step + 1} of 3</div>
        {step === 0 ? (
          <>
            <h2 style={{ fontSize: 19, marginBottom: 4 }}>Create your lender account</h2>
            <p className="muted" style={{ fontSize: 13, marginBottom: 18 }}>
              Individual lenders only. Legal entities are onboarded by {operatorName} off-platform.
            </p>
            <div className="grid grid-2" style={{ gap: 12, marginBottom: 12 }}>
              <Field label="First name"><input className="input" onChange={(event) => setFirstName(event.target.value)} value={firstName} /></Field>
              <Field label="Last name"><input className="input" onChange={(event) => setLastName(event.target.value)} value={lastName} /></Field>
            </div>
            <Field label="Email address"><input className="input" onChange={(event) => setEmail(event.target.value)} type="email" value={email} /></Field>
            <Field hint={phoneNumber ? `Stored as ${phoneNumber}` : "Use the mobile number you will keep available for SMS verification."} label="Mobile phone number">
              <div className="phone-number-row">
                <select
                  aria-label="Phone country prefix"
                  className="select phone-prefix-select"
                  onChange={(event) => setPhoneCountryCode(event.target.value)}
                  value={phoneCountryCode}
                >
                  {registrationCountries.map((country) => (
                    <option key={`${country.iso2}-${country.callingCode}`} value={country.callingCode}>
                      {country.iso2} {country.callingCode}
                    </option>
                  ))}
                </select>
                <input
                  className="input mono"
                  inputMode="tel"
                  onChange={(event) => setPhoneNationalNumber(event.target.value.replace(/[^\d\s().-]/g, ""))}
                  placeholder="79 000 00 00"
                  value={phoneNationalNumber}
                />
              </div>
            </Field>
            <Field label="Country of residence">
              <select className="select" onChange={(event) => setResidenceCountry(event.target.value)} value={residenceCountry}>
                {registrationCountries.map((country) => (
                  <option key={country.iso2} value={country.name}>
                    {country.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="col gap-10" style={{ marginTop: 14 }}>
              {isFixturePreview || registrationLabels.length === 0 ? (
                <Check checked={terms} id="register-terms" onChange={setTerms}>
                  I accept the{" "}
                  <LegalDocLink category="registration">
                    platform terms and registration documents
                  </LegalDocLink>
                  .
                </Check>
              ) : (
                registrationLabels.map((label, index) => (
                  <Check
                    checked={registrationAcceptedLabels.includes(label)}
                    id={`register-terms-${index}`}
                    key={label}
                    onChange={(checked) =>
                      setRegistrationAcceptedLabels((current) =>
                        checked
                          ? Array.from(new Set([...current, label]))
                          : current.filter((item) => item !== label)
                      )
                    }
                  >
                    {label} <LegalDocLink category="registration">read &amp; download</LegalDocLink>
                  </Check>
                ))
              )}
              <Check checked={risk} id="register-risk" onChange={setRisk}>
                {riskLabels.length === 1 ? riskLabels[0] : "I acknowledge the P2P lending risk disclosure."}{" "}
                <LegalDocLink category="risk_disclosure">
                  read &amp; download
                </LegalDocLink>
              </Check>
              <Check checked={marketing} id="register-marketing" onChange={setMarketing}>I agree to optional marketing communications.</Check>
            </div>
            <p className="muted" style={{ fontSize: 11.5, marginTop: 10 }}>
              Documents open in a new tab where you can read and download them.{" "}
              {!isFixturePreview && registrationTermsQuery.data ? (
                <>
                  Acceptance is recorded against server-published v
                  {registrationTermsQuery.data.version_number} (hash{" "}
                  <span className="mono">{registrationTermsQuery.data.content_hash.slice(0, 12)}</span>)
                  with timestamp and context. You can generate the accepted version from My Documents.
                </>
              ) : (
                <>Acceptance is recorded with document version, timestamp and context.</>
              )}
            </p>
            {!isFixturePreview && registrationTermsQuery.isError ? (
              <Banner tone="bad" title="Agreement unavailable">
                The current server-published lender agreement could not be loaded.
              </Banner>
            ) : null}
            {!isFixturePreview && riskDisclosureQuery.isError ? (
              <Banner tone="bad" title="Risk disclosure unavailable">
                The current server-published risk disclosure could not be loaded. Retry before registering.
              </Banner>
            ) : null}
            {error ? <Banner tone="bad" title="Could not register">{error}</Banner> : null}
            <Button block disabled={!allRegistrationTermsAccepted || !risk || !email.includes("@") || !phoneNumber || registerMutation.isPending || (!isFixturePreview && (!registrationTermsQuery.data || !riskDisclosureQuery.data))} style={{ marginTop: 16 }} variant="primary" onClick={submitRegistration}>
              {registerMutation.isPending ? "Creating account..." : "Continue"}
            </Button>
          </>
        ) : step === 1 ? (
          <>
            {!hasMatchingSession ? (
              <>
                <h2 style={{ fontSize: 19, marginBottom: 4 }}>Confirm your email</h2>
                <p className="muted" style={{ fontSize: 13, marginBottom: 18 }}>
                  We need your magic-link email opened in this browser before SMS verification.
                </p>
                {hasDifferentSession ? (
                  <Banner tone="warn" title="Different account signed in">
                    This browser is signed in as <b>{sessionUser?.email}</b>. Open the magic link
                    sent to <b>{email}</b> in this browser to continue this registration.
                  </Banner>
                ) : emailLoginSent ? (
                  <Banner tone="ok" title="Magic link sent">
                    Open the email sent to <b>{email}</b>. After sign-in, BANXUM will return you to
                    phone verification.
                  </Banner>
                ) : (
                  <Banner tone="info" title="Email confirmation required">
                    Send a secure magic link to <b>{email}</b>, then open it in this browser.
                  </Banner>
                )}
                <Button
                  block
                  disabled={
                    !email.includes("@") ||
                    registrationMagicLinkMutation.isPending ||
                    emailCooldownSeconds > 0
                  }
                  style={{ marginTop: 16 }}
                  variant="primary"
                  onClick={requestRegistrationMagicLink}
                >
                  {registrationMagicLinkMutation.isPending
                    ? "Sending..."
                    : emailCooldownSeconds > 0
                      ? emailLoginSent
                        ? `Resend in ${emailCooldownSeconds}s`
                        : `Try again in ${emailCooldownSeconds}s`
                      : emailLoginSent
                        ? "Resend magic link"
                        : "Send magic link"}
                </Button>
                {error ? <Banner tone="bad" title="Could not send magic link">{error}</Banner> : null}
              </>
            ) : (
              <>
                <h2 style={{ fontSize: 19, marginBottom: 4 }}>Verify your phone</h2>
                <p className="muted" style={{ fontSize: 13, marginBottom: 18 }}>
                  Request an SMS code for {phoneNumberLabel}. Phone verification is required before
                  financial access.
                </p>
                <CodeRequestField
                  hint={previewHint("Demo: enter any 6 digits")}
                  label="SMS code"
                  requestDisabled={phoneRequestDisabled}
                  requestLabel={
                    !isFixturePreview
                      ? phoneRequestMutation.isPending
                        ? "Sending..."
                        : phoneCooldownSeconds > 0
                          ? `Resend in ${phoneCooldownSeconds}s`
                          : phoneChallengeId
                            ? "Resend SMS"
                            : "Send SMS"
                      : undefined
                  }
                  value={phoneCode}
                  onChange={setPhoneCode}
                  onRequest={requestPhoneCode}
                />
                {error ? <Banner tone="bad" title="Could not verify phone">{error}</Banner> : null}
                <Button block disabled={phoneCode.length < 6 || (!isFixturePreview && !phoneChallengeId) || phoneConfirmMutation.isPending} style={{ marginTop: 16 }} variant="primary" onClick={confirmPhone}>
                  {phoneConfirmMutation.isPending ? "Verifying..." : "Verify phone"}
                </Button>
              </>
            )}
          </>
        ) : (
          <>
            <h2 style={{ fontSize: 19, marginBottom: 4 }}>Identity verification</h2>
            <p className="muted" style={{ fontSize: 13, marginBottom: 18 }}>
              We will redirect you to Didit for identity capture and verification. Garanta retains
              the required compliance evidence and provider references for audit and regulatory
              access. If you verify on another device (for example via QR code), this page
              continues automatically once the result arrives.
            </p>
            <KycTimeline current="pending" />
            <Banner tone="neutral" title="Provider handoff">
              Didit verifies your identity and returns provider evidence/status to {operatorName}. If
              the provider routes your case to review, financial access stays locked until Garanta
              compliance resolves it.
            </Banner>
            {error ? <Banner tone="bad" title="Could not start KYC">{error}</Banner> : null}
            <Button block disabled={kycSessionMutation.isPending} style={{ marginTop: 16 }} variant="primary" onClick={startKyc}>
              {kycSessionMutation.isPending ? "Starting Didit..." : "Start KYC"}
            </Button>
          </>
        )}
      </div>
    </AuthShell>
  );
}

function AuthShell({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="auth-wrap">
      <div className="col" style={{ gap: 20, maxWidth: 560, width: "100%" }}>
        <div className="row" style={{ justifyContent: "center" }}><Wordmark /></div>
        {children}
        <button className="btn-link center" onClick={onClose} style={{ alignSelf: "center", fontSize: 12.5 }} type="button">
          Back to investment opportunities preview
        </button>
      </div>
    </div>
  );
}

function InvestorShell({
  route,
  setRoute,
  demoState,
  setDemoState
}: {
  route: AppRoute;
  setRoute: (route: AppRoute) => void;
  demoState: DemoAccountState;
  setDemoState: (state: DemoAccountState) => void;
}) {
  const queryClient = useQueryClient();
  const [navOpen, setNavOpen] = useState(false);
  const [addFundsOpen, setAddFundsOpen] = useState(false);
  const [investState, setInvestState] = useState<{ loan: MarketplaceLoanDetail; initialAmount?: string } | null>(null);
  const investLoan = investState?.loan ?? null;
  const setInvestLoan = useCallback(
    (loan: MarketplaceLoanDetail | null, initialAmount?: string) => {
      setInvestState(loan ? { loan, initialAmount } : null);
    },
    []
  );
  const [readonlyImpersonation, setReadonlyImpersonation] = useState(() => ({
    active: isReadonlyImpersonationActive(),
    label: readReadonlyImpersonationLabel()
  }));
  const finishLogout = () => {
    clearPortalSessionState(queryClient);
    clearReadonlyImpersonation();
    setReadonlyImpersonation({ active: false, label: "" });
    goTo(setRoute, "public");
    setNavOpen(false);
    setAddFundsOpen(false);
    setInvestLoan(null);
  };
  const logoutMutation = useV1AuthLogoutCreate({
    mutation: { onSettled: finishLogout }
  });
  const authMeQuery = useV1AuthMeRetrieve({
    query: { enabled: !isFixturePreview, retry: false, staleTime: 0 }
  });
  const sessionUser = authMeQuery.data?.user;
  const hasPortalSession = isFixturePreview || Boolean(sessionUser);
  const kycGateQuery = useV1KycStatusRetrieve({
    query: {
      enabled: !isFixturePreview && hasPortalSession,
      retry: false,
      staleTime: 0,
      refetchInterval: (query) => {
        const data = query.state.data;
        if (!data?.financial_access_allowed && (data?.status === "not_started" || data?.status === "pending")) {
          return 4000;
        }
        return false;
      }
    }
  });
  const financialAccessAllowed =
    isFixturePreview || kycGateQuery.data?.financial_access_allowed === true;
  const balances = useBalancesData(financialAccessAllowed).data ?? { summaries: [], lots: [] };
  const notifications = useNotificationsData(20, financialAccessAllowed).data;
  const profile = readonlyImpersonation.active
    ? {
        initials: "RO",
        name: readonlyImpersonation.label || "Read-only user",
        email: "Superadmin read-only view",
        country: "",
        phone: "",
        memberSince: ""
      }
    : sessionUser
      ? {
          initials: sessionUser.full_name
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((part) => part[0]?.toUpperCase())
            .join("") || "IN",
          name: sessionUser.full_name,
          email: sessionUser.email,
          country: "",
          phone: "",
          memberSince: ""
        }
      : displayProfile();

  if (!isFixturePreview && authMeQuery.isPending) {
    return (
      <AuthShell onClose={() => goTo(setRoute, "public")}>
        <div className="auth-card"><ScreenLoading title="Checking your session" /></div>
      </AuthShell>
    );
  }
  if (!isFixturePreview && (!sessionUser || authMeQuery.isError)) {
    return <LoginFlow setRoute={setRoute} />;
  }
  if (!isFixturePreview && sessionUser && ["admin", "superadmin"].includes(sessionUser.account_type) && !readonlyImpersonation.active) {
    return <AdminApp />;
  }

  const screen = (() => {
    switch (route.name) {
      case "dashboard":
        return <Dashboard demoState={demoState} setInvestLoan={setInvestLoan} setRoute={setRoute} />;
      case "market":
        return <MarketplaceScreen demoState={demoState} setInvestLoan={setInvestLoan} setRoute={setRoute} />;
      case "smartInvest":
        return <SmartInvestScreen setInvestLoan={setInvestLoan} setRoute={setRoute} />;
      case "loan":
        return (
          <LoanDetailScreen
            demoState={demoState}
            loanId={route.params?.loanId ?? ""}
            setInvestLoan={setInvestLoan}
            setRoute={setRoute}
          />
        );
      case "portfolio":
        return <PortfolioScreen setRoute={setRoute} />;
      case "secondary":
        return <SecondaryMarketScreen demoState={demoState} initialTab={route.params?.tab} />;
      case "balances":
        return <BalancesScreen demoState={demoState} />;
      case "fx":
        return <FxScreen demoState={demoState} />;
      case "documents":
        return <DocumentsScreen />;
      case "notifications":
        return <NotificationsScreen />;
      case "settings":
        return <SettingsScreen setRoute={setRoute} />;
      case "kyc":
        return <KycStatusScreen setRoute={setRoute} />;
      case "faq":
        return <FaqScreen />;
      default:
        return <Dashboard demoState={demoState} setInvestLoan={setInvestLoan} setRoute={setRoute} />;
    }
  })();

  const gatedScreen =
    !isFixturePreview && hasPortalSession && !financialAccessAllowed
      ? kycGateQuery.isPending && !kycGateQuery.data
        ? <ScreenLoading title="Verification" />
        : <KycStatusScreen setRoute={setRoute} />
      : screen;

  const overdueCount = balances.lots.filter((lot) => lot.bucket === "overdue" || lot.bucket === "penalty").length;
  const addFundsCurrency = balances.summaries.find((summary) => summary.currency === "CHF")?.currency
    ?? balances.summaries[0]?.currency
    ?? "CHF";
  const displayRouteName = !financialAccessAllowed && !isFixturePreview ? "kyc" : route.name;
  const activeRoute = displayRouteName === "loan" ? "market" : displayRouteName;

  return (
    <div className="app">
      <div className={`nav-scrim ${navOpen ? "show" : ""}`} onClick={() => setNavOpen(false)} />
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="sidebar-brand"><Wordmark compact /></div>
        <nav aria-label="Investor portal navigation" className="nav">
          {navGroups.map((group) => (
            <div key={group.label}>
              <div className="nav-group-label">{group.label}</div>
              {group.items.map((item) => {
                const isActive = activeRoute === item.route;
                const showBalanceBadge = item.route === "balances" && (demoState === "frozen" || overdueCount > 0);
                return (
                  <button
                    className={`nav-link ${isActive ? "on" : ""}`}
                    key={item.route}
                    onClick={() => {
                      goTo(setRoute, item.route);
                      setNavOpen(false);
                    }}
                    type="button"
                  >
                    <Icon name={item.icon} size={17} />
                    <span className="nav-link-label">{item.label}</span>
                    {showBalanceBadge ? <span className={`nav-badge ${demoState === "frozen" ? "bad" : "warn"}`}>{demoState === "frozen" ? "!" : overdueCount}</span> : null}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="userchip" onClick={() => goTo(setRoute, "settings")}>
            <span className="avatar">{profile.initials}</span>
            <div className="grow" style={{ minWidth: 0 }}>
              <div className="col-strong" style={{ fontSize: 12.5 }}>{profile.name}</div>
              <div className="muted" style={{ fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{profile.email}</div>
            </div>
            <Icon className="faint" name="settings" size={15} />
          </div>
          <Button
            block
            disabled={logoutMutation.isPending}
            icon="logout"
            onClick={() => {
              if (readonlyImpersonation.active) {
                finishLogout();
                return;
              }
              if (isFixturePreview) {
                finishLogout();
                return;
              }
              logoutMutation.mutate();
            }}
            size="sm"
            variant="ghost"
          >
            {readonlyImpersonation.active ? "Exit read-only view" : logoutMutation.isPending ? "Signing out..." : "Sign out"}
          </Button>
        </div>
      </aside>
      <div className="main">
        <header aria-label="Investor account header" className="topbar">
          <button aria-label="Menu" className="icon-btn menu-btn" onClick={() => setNavOpen((open) => !open)} type="button">
            <Icon name="menu" size={18} />
          </button>
          <div className="crumbs"><b>{routeTitles[displayRouteName]}</b></div>
          <div className="bal-pills">
            {balances.summaries.map((summary) => (
              <div className={`bal-pill ${summary.overdue_minor > 0 || summary.penalty_mode_minor > 0 ? "flag" : ""}`} key={summary.currency}>
                <span className="bp-ccy">{summary.currency}</span>
                <span className="bp-amt">{formatMoneyMinor(summary.total_available_minor, summary.currency)}</span>
              </div>
            ))}
          </div>
          <Button
            aria-label="Add Funds"
            className="btn-green topbar-add-funds"
            disabled={!financialAccessAllowed || demoState === "frozen" || readonlyImpersonation.active}
            icon="plus"
            onClick={() => setAddFundsOpen(true)}
            size="sm"
          >
            Add Funds
          </Button>
          <button
            aria-label="Notifications"
            className="icon-btn"
            onClick={() => goTo(setRoute, "notifications")}
            type="button"
          >
            <Icon name="bell" size={17} />
            {(notifications?.unread_count ?? 0) > 0 ? <span className="ping" /> : null}
          </button>
          {isFixturePreview ? (
            <div className="state-switch">
              <span>UX state</span>
              <select className="select state-switch-select" onChange={(event) => setDemoState(event.target.value as DemoAccountState)} value={demoState}>
                <option value="active">Active investor</option>
                <option value="kyc_pending">KYC pending</option>
                <option value="frozen">Day-60 freeze</option>
              </select>
            </div>
          ) : null}
        </header>
        {isFixturePreview ? (
          <div className="fixture-preview-notice">
            <Banner icon="alert" tone="warn" title="Preview data">
              This investor portal is running with local fixture data for UX review. Balances,
              holdings, activity, FX history, and documents shown here are not real account data.
            </Banner>
          </div>
        ) : null}
        {readonlyImpersonation.active ? (
          <div className="fixture-preview-notice">
            <Banner icon="lock" tone="info" title="Superadmin read-only view">
              Viewing the portal as {readonlyImpersonation.label || "selected user"}. Mutating
              actions are disabled and generated/downloaded evidence is audited to the superadmin,
              not recorded as user activity.
            </Banner>
          </div>
        ) : null}
        {gatedScreen}
      </div>
      {addFundsOpen ? (
        <DepositModal
          allowCurrencySelection
          currency={addFundsCurrency}
          onClose={() => setAddFundsOpen(false)}
        />
      ) : null}
      {investLoan ? (
        isOriginatorClaimLoan(investLoan) ? (
          <OriginatorClaimInvestModal initialAmount={investState?.initialAmount} loan={investLoan} onClose={() => setInvestLoan(null)} />
        ) : (
          <InvestModal initialAmount={investState?.initialAmount} loan={investLoan} onClose={() => setInvestLoan(null)} />
        )
      ) : null}
    </div>
  );
}

function nextDashboardMonth(asOf: string) {
  const [year, month] = zurichDateKey(asOf).split("-").map(Number);
  const date = Number.isFinite(year) && Number.isFinite(month)
    ? new Date(Date.UTC(year, month, 1))
    : new Date();
  return {
    key: `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`,
    label: date.toLocaleDateString("en-GB", { month: "long", timeZone: "UTC" })
  };
}

function Dashboard({
  demoState,
  setRoute,
  setInvestLoan
}: {
  demoState: DemoAccountState;
  setRoute: (route: AppRoute) => void;
  setInvestLoan: (loan: MarketplaceLoanDetail | null, initialAmount?: string) => void;
}) {
  const dashboardQuery = useDashboardData();
  const balancesQuery = useBalancesData();
  const loansQuery = useMarketplaceLoansData();
  const smartInvestQuery = useSmartInvestData();
  const portfolioQuery = usePortfolioData(false);
  const [sheetLoan, setSheetLoan] = useState<MarketplaceLoanPreview | null>(null);
  const [ccyPick, setCcyPick] = useState<string | null>(null);
  const [unticked, setUnticked] = useState<Record<string, boolean>>({});
  const [closeOpen, setCloseOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const dashboard = dashboardQuery.data;
  const balances = balancesQuery.data;
  const loans = loansQuery.data ?? [];
  if ((dashboardQuery.isError && !dashboard) || (balancesQuery.isError && !balances)) {
    return (
      <ScreenError
        title="Dashboard"
        onRetry={() => {
          void dashboardQuery.refetch();
          void balancesQuery.refetch();
        }}
      >
        We could not load your investor portal data. Your financial access state and balances are
        enforced by the backend; try again when the API is reachable.
      </ScreenError>
    );
  }
  if (!dashboard || !balances) return <ScreenLoading title="Dashboard" />;

  const portfolio = portfolioQuery.data;
  const smartInvest = smartInvestQuery.data;
  const smartRuleActive = smartInvest?.rule?.is_active === true;
  const outstandingByCcy = new Map(
    dashboard.portfolio_summary.outstanding_principal_by_currency.map((amount) => [amount.currency, amount.amount_minor])
  );
  const currencies = Array.from(new Set([
    ...balances.summaries.map((summary) => summary.currency),
    ...dashboard.portfolio_summary.outstanding_principal_by_currency.filter((amount) => amount.amount_minor > 0).map((amount) => amount.currency)
  ])).sort();
  const defaultCcy = currencies.reduce(
    (best, code) => ((outstandingByCcy.get(code) ?? 0) > (outstandingByCcy.get(best) ?? 0) ? code : best),
    currencies[0] ?? "CHF"
  );
  const ccy = ccyPick && currencies.includes(ccyPick) ? ccyPick : defaultCcy;
  const summary = balances.summaries.find((item) => item.currency === ccy);
  const holdingsCcy = (portfolio?.holdings ?? []).filter(
    (holding) => holding.currency === ccy && holding.current_principal_minor > 0
  );
  const investedMinor = outstandingByCcy.get(ccy) ?? 0;
  const idleMinor = summary?.investable_minor ?? 0;
  const companies = new Set(holdingsCcy.map((holding) => holding.loan.borrower_name || holding.loan.loan_id)).size;
  const avgRateBps = investedMinor > 0
    ? Math.round(holdingsCcy.reduce((sum, holding) => sum + holding.loan.yield_bps * holding.current_principal_minor, 0) / Math.max(1, holdingsCcy.reduce((sum, holding) => sum + holding.current_principal_minor, 0)))
    : 0;
  const [investedWhole, investedCents = "00"] = formatMoneyMinor(investedMinor, ccy).split(".");
  const nextMonth = nextDashboardMonth(dashboard.as_of);
  const asOfDate = new Date(dashboard.as_of);
  const monthInfo = (offset: number) => {
    const date = new Date(asOfDate.getFullYear(), asOfDate.getMonth() + 1 + offset, 1);
    return {
      key: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`,
      label: date.toLocaleDateString("en-GB", { month: "short" }).toUpperCase()
    };
  };
  const lastDueByHolding = new Map<string, string>();
  for (const holding of holdingsCcy) {
    const last = holding.investment_schedule[holding.investment_schedule.length - 1];
    if (last) lastDueByHolding.set(holding.id, last.due_date);
  }
  const spine = Array.from({ length: 12 }, (_, offset) => {
    const info = monthInfo(offset);
    let amountMinor = 0;
    let count = 0;
    let end = false;
    for (const holding of holdingsCcy) {
      for (const installment of holding.investment_schedule) {
        if (!installment.due_date.startsWith(info.key) || installment.status === "paid") continue;
        amountMinor += installment.projected_total_minor;
        count += 1;
        if (lastDueByHolding.get(holding.id) === installment.due_date) end = true;
      }
    }
    return { ...info, amountMinor, count, end };
  });
  const spineMax = Math.max(1, ...spine.map((month) => month.amountMinor));
  const next12Minor = spine.reduce((sum, month) => sum + month.amountMinor, 0);
  const arriving = spine[0] ?? { amountMinor: 0, count: 0 };
  const realizedInterest = dashboard.portfolio_summary.realized_interest_by_currency.find((amount) => amount.currency === ccy)?.amount_minor ?? 0;
  const firstAssignment = holdingsCcy.reduce<string | null>(
    (earliest, holding) => (earliest === null || holding.assignment_effective_at < earliest ? holding.assignment_effective_at : earliest),
    null
  );
  const sinceLabel = firstAssignment
    ? new Date(firstAssignment).toLocaleDateString("en-GB", { month: "long", year: "numeric" })
    : null;
  const idlePct = investedMinor + idleMinor > 0 ? ((idleMinor / (investedMinor + idleMinor)) * 100).toFixed(1) : "0.0";

  const deskMatches = (smartInvest?.matches ?? []).filter((match) => match.currency === ccy);
  const deskTickable = deskMatches.filter((match) => match.product_type !== "originator_claim" && isOpenMarketplaceLoan(match));
  const deskTicked = deskTickable.filter((match) => !unticked[match.loan_id]);
  const deskSplit = new Map<string, number>();
  if (deskTicked.length > 0 && idleMinor > 0) {
    const per = Math.floor(idleMinor / deskTicked.length);
    for (const match of deskTicked) {
      deskSplit.set(match.loan_id, Math.max(0, Math.min(per, marketplaceAvailableMinor(match))));
    }
  }
  const deskItems = deskTicked
    .map((match) => ({ match, amountMinor: deskSplit.get(match.loan_id) ?? 0 }));
  const deskBatchReady = deskItems.length > 0 && deskItems.every(
    (item) => item.amountMinor >= item.match.minimum_investment_minor
  );
  const deskTotal = deskBatchReady
    ? deskItems.reduce((sum, item) => sum + item.amountMinor, 0)
    : 0;
  const openCcyLoans = loans.filter((loan) => isOpenMarketplaceLoan(loan) && loan.currency === ccy);
  const closingSoon = openCcyLoans
    .map((loan) => {
      const days = loan.funding_deadline
        ? Math.max(0, Math.ceil((new Date(`${loan.funding_deadline}T00:00:00`).getTime() - asOfDate.getTime()) / 86_400_000))
        : null;
      return { loan, days };
    })
    .filter((entry): entry is { loan: MarketplaceLoanPreview; days: number } => entry.days !== null && entry.days <= 7)
    .sort((left, right) => left.days - right.days);
  const bestOpenBps = openCcyLoans.reduce((max, loan) => Math.max(max, marketplaceYieldBps(loan)), 0);

  const totalBase = investedMinor + idleMinor;
  const futureInterestMinor = holdingsCcy.reduce(
    (sum, holding) => sum + holding.investment_schedule.filter((row) => row.status !== "paid").reduce((acc, row) => acc + row.projected_interest_minor, 0),
    0
  );
  const scenarioAInterest = realizedInterest + futureInterestMinor;
  const horizonMonths = Math.max(
    1,
    ...holdingsCcy.map((holding) => {
      const last = holding.investment_schedule[holding.investment_schedule.length - 1];
      if (!last) return 1;
      const lastDate = new Date(`${last.due_date}T00:00:00`);
      return (lastDate.getFullYear() - asOfDate.getFullYear()) * 12 + lastDate.getMonth() - asOfDate.getMonth();
    })
  );
  const reinvestRate = bestOpenBps / 120_000;
  let scenarioBExtra = 0;
  if (reinvestRate > 0) {
    scenarioBExtra += idleMinor * (Math.pow(1 + reinvestRate, horizonMonths) - 1);
    for (let offset = 0; offset < horizonMonths; offset += 1) {
      const info = monthInfo(offset);
      let monthPayments = 0;
      for (const holding of holdingsCcy) {
        for (const installment of holding.investment_schedule) {
          if (installment.due_date.startsWith(info.key) && installment.status !== "paid") monthPayments += installment.projected_total_minor;
        }
      }
      scenarioBExtra += monthPayments * (Math.pow(1 + reinvestRate, Math.max(0, horizonMonths - offset - 1)) - 1);
    }
  }
  const scenarioBInterest = scenarioAInterest + Math.round(scenarioBExtra);
  const pctA = totalBase > 0 ? (scenarioAInterest / totalBase) * 100 : 0;
  const pctB = totalBase > 0 ? (scenarioBInterest / totalBase) * 100 : 0;
  const pctPaid = totalBase > 0 ? (realizedInterest / totalBase) * 100 : 0;
  const chartMax = Math.max(7, Math.ceil(Math.max(pctB, pctA) / 7) * 7);
  const chartY = (pct: number) => 286 - (pct / chartMax) * 266;
  const horizonLabel = (() => {
    const date = new Date(asOfDate.getFullYear(), asOfDate.getMonth() + horizonMonths, 1);
    return date.toLocaleDateString("en-GB", { month: "short", year: "numeric" });
  })();
  const startLabel = firstAssignment
    ? new Date(firstAssignment).toLocaleDateString("en-GB", { month: "short", year: "numeric" })
    : formatDate(dashboard.as_of);
  const hasInvestments = investedMinor > 0;

  return (
    <main className="content dz-page">
      <div className="col gap-12" style={{ marginBottom: 20 }}>
        {demoState === "frozen" ? <FrozenBanner setRoute={setRoute} /> : null}
        {demoState === "kyc_pending" ? <KycBanner setRoute={setRoute} /> : null}
      </div>

      {currencies.length > 1 ? (
        <div className="dz-ccy-row">
          <div className="seg" role="tablist">
            {currencies.map((code) => (
              <button aria-selected={ccy === code} className={ccy === code ? "on" : ""} key={code} onClick={() => setCcyPick(code)} role="tab" type="button">{code}</button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="dz-hero">
        <h1>Money working for you</h1>
        <div className="dz-date">{formatDate(dashboard.as_of)}</div>
        <div className="dz-fig"><span className="dz-cur">{ccy === "EUR" ? "€" : ccy}</span><span className="dz-whole">{investedWhole}</span><span className="dz-cents">.{investedCents}</span></div>
        {hasInvestments ? (
          <>
            <div className="dz-hero-line">invested in loans to <strong>{companies === 1 ? "1 company" : `${companies} companies`}</strong></div>
            <div className="dz-hero-line">at <strong className="num">{formatRateBps(avgRateBps)}</strong> per year interest, on average</div>
          </>
        ) : (
          <div className="dz-hero-line">nothing is invested yet — your money and the open opportunities are below</div>
        )}
      </div>

      <div className="dz-band">
        <div className="dz-cell">
          <div className="dz-microlabel">Arriving in {nextMonth.label}</div>
          <div className="dz-fig-md">{pfMoneyLabel(ccy, arriving.amountMinor)}</div>
          <div className="dz-cell-sub">{portfolioQuery.isError ? "schedule temporarily unavailable" : `across ${arriving.count === 1 ? "1 payment" : `${arriving.count} payments`}`}</div>
        </div>
        <div className="dz-cell">
          <div className="dz-microlabel green">Interest paid to you so far</div>
          <div className="dz-fig-md green">{pfMoneyLabel(ccy, realizedInterest)}</div>
          <div className="dz-cell-sub">{sinceLabel ? `since ${sinceLabel}` : "no distributions yet"}</div>
        </div>
        <div className="dz-cell">
          <div className="dz-microlabel"><span className="red">Money not working</span> — just sitting</div>
          <div className="dz-fig-md">{pfMoneyLabel(ccy, idleMinor)}</div>
          <div className="dz-cell-sub">{idlePct}% of your money, earning nothing</div>
        </div>
      </div>

      <div className="dz-decisions" id="rule">
        <div className="dz-decisions-head">
          <span className="dz-decisions-cap">Waiting on your decision</span>
          <span style={{ flex: 1 }} />
          <span className="dz-serif">the clicks that bind — everything else can wait</span>
        </div>

        {smartInvestQuery.isError && !smartInvest ? (
          <DataErrorCard title="Smart Invest is temporarily unavailable" onRetry={() => void smartInvestQuery.refetch()}>
            Your dashboard is still available. Retry to load your saved rule and matching opportunities.
          </DataErrorCard>
        ) : null}

        {smartRuleActive && deskMatches.length > 0 ? (
          <div className="dz-desk">
            <div className="dz-desk-head">
              <span className="dz-desk-title">Your rule found {deskMatches.length === 1 ? "1 opportunity" : `${deskMatches.length} opportunities`}</span>
              <span className="dz-desk-sub">{pfMoneyLabel(ccy, idleMinor)} free to place · {deskTicked.length} of {deskTickable.length} ticked · nothing commits until you confirm</span>
            </div>
            <div className="dz-desk-rows">
              {deskMatches.map((match) => {
                const tickable = match.product_type !== "originator_claim" && isOpenMarketplaceLoan(match);
                const ticked = tickable && !unticked[match.loan_id];
                const amount = deskSplit.get(match.loan_id) ?? 0;
                return (
                  <div className="dz-desk-row" key={match.loan_id}>
                    {tickable ? (
                      <button aria-label={`${ticked ? "Untick" : "Tick"} ${match.title}`} className={`dz-tick${ticked ? " on" : ""}`} onClick={() => setUnticked((current) => ({ ...current, [match.loan_id]: !current[match.loan_id] }))} type="button">{ticked ? "✓" : ""}</button>
                    ) : (
                      <span className="dz-tick claim" title="Originator claims are priced per loan — open the loan to buy." />
                    )}
                    <button className="dz-desk-name" onClick={() => setSheetLoan(match)} type="button">{match.borrower_display_name || match.title}</button>
                    <span className="dz-desk-meta num">{formatRateBps(match.yield_bps)} · {match.term_months} mo · {match.originator_name || "Banxum"}{!tickable ? " · quote per loan" : ""}</span>
                    <span className="dz-leader" />
                    <span className="dz-desk-amt num">{ticked && amount > 0 ? pfMoneyLabel(ccy, amount) : "—"}</span>
                  </div>
                );
              })}
              <div className="dz-desk-foot">
                <span className="dz-desk-commit num">You commit {pfMoneyLabel(ccy, deskTotal)}</span>
                <span className="dz-desk-note">{deskBatchReady ? "nothing moves without this click" : "untick opportunities until each order reaches its minimum"}</span>
                <span style={{ flex: 1 }} />
                <button className="si-dash-setup" disabled={!deskBatchReady} onClick={() => setBatchOpen(true)} type="button">Review &amp; confirm →</button>
              </div>
            </div>
          </div>
        ) : null}

        {smartRuleActive ? (
          <div className="si-dash-rule">
            <span className="si-dash-rule-name">Investing rule</span>
            <button className="si-dash-active-chip" onClick={() => goTo(setRoute, "smartInvest")} type="button">✓ Active</button>
            <span className="si-dash-rule-sub">every new opportunity is checked against your conditions, and you approve every match</span>
            <span style={{ flex: 1 }} />
          </div>
        ) : (
          <div className="si-dash-rule">
            <span className="si-dash-rule-name">No investing rule is running</span>
            <span className="si-dash-rule-sub">a rule watches new opportunities against your conditions and asks you first — nothing commits without you</span>
            <span style={{ flex: 1 }} />
            <button className="si-dash-setup" onClick={() => goTo(setRoute, "smartInvest")} type="button">Set one up →</button>
          </div>
        )}

        {closingSoon.length > 0 ? (
          <div className="dz-close-card">
            <div className="dz-close-head">
              <span className="dz-close-title num">{closingSoon.length === 1 ? "1 opportunity closes" : `${closingSoon.length} opportunities close`} within 7 days</span>
              <span className="dz-close-near">the nearest in {closingSoon[0].days === 1 ? "1 day" : `${closingSoon[0].days} days`}</span>
              <span className="dz-close-rest">· a closed campaign does not reopen — click any for the full loan</span>
              <span style={{ flex: 1 }} />
              <span className="dz-dots">
                <span className="dz-dots-cap">today</span>
                <span className="dz-dots-row">
                  {Array.from({ length: 7 }, (_, index) => {
                    const day = index + 1;
                    const has = closingSoon.some((entry) => entry.days === day);
                    return <span className={`dz-dot${has ? (day <= 3 ? " red" : " dark") : ""}`} key={day} />;
                  })}
                </span>
                <span className="dz-dots-cap">7 d</span>
              </span>
              <button className="si-dash-setup" onClick={() => setCloseOpen((open) => !open)} type="button">{closeOpen ? "Hide ▴" : "Check ▾"}</button>
            </div>
            {closeOpen ? (
              <div className="si-dash-rows">
                {closingSoon.map((entry) => (
                  <button className="si-dash-row" key={entry.loan.loan_id} onClick={() => setSheetLoan(entry.loan)} type="button">
                    <span className="si-dash-row-name">{entry.loan.borrower_display_name || entry.loan.title}</span>
                    <span className="si-dash-row-meta">{formatRateBps(marketplaceYieldBps(entry.loan))} · {entry.loan.term_months} mo · {entry.loan.originator_name || "Banxum"}</span>
                    <span className="dz-leader" />
                    <span className={`si-dash-row-amt${entry.days <= 3 ? " red" : ""}`}>closes in {entry.days === 1 ? "1 day" : `${entry.days} days`}</span>
                    <span className="si-dash-row-go" aria-hidden="true">→</span>
                  </button>
                ))}
                <div className="si-dash-rows-foot">
                  <span>each row opens the full loan — how much you lend, if anything, is decided there</span>
                  <span style={{ flex: 1 }} />
                  <button className="fs-clear-link" onClick={() => goTo(setRoute, "market")} type="button">all opportunities →</button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="dz-income">
        <div className="dz-sect-head">
          <span className="dz-sect-sign">–</span>
          <span className="dz-sect-title">Expected income, month by month</span>
          <span style={{ flex: 1 }} />
        </div>
        <div className="dz-income-intro">
          <div>Every figure below is contracted, not forecast.</div>
          <div>Amounts in {ccy === "EUR" ? "euro" : ccy}.</div>
        </div>
        <div className="dz-spine">
          {spine.map((month, index) => (
            <div className={`dz-col${index === 0 ? " hot" : ""}`} key={month.key}>
              <span className="dz-col-amt num">{formatMoneyMinor(month.amountMinor, ccy)}</span>
              <span className={`dz-bar${month.end ? " end" : ""}`} style={{ height: `${24 + Math.round((month.amountMinor / spineMax) * 72)}px` }} />
              <span className="dz-col-m">{month.label}</span>
            </div>
          ))}
        </div>
        <div className="dz-next12">
          <span className="dz-next12-cap">Next 12 months</span>
          <span className="dz-leader" />
          <span className="dz-next12-cur">{ccy === "EUR" ? "€" : ccy}</span>
          <span className="dz-next12-val num">{formatMoneyMinor(next12Minor, ccy).split(".")[0]}</span>
          <span className="dz-next12-cents num">.{formatMoneyMinor(next12Minor, ccy).split(".")[1] ?? "00"}</span>
        </div>
        <div className="dz-income-link"><button className="fs-clear-link" onClick={() => goTo(setRoute, "portfolio")} type="button">Beyond 12 months, and the loan behind every payment, in My investments →</button></div>
        <div className="dz-income-legend"><span className="dz-legend-swatch" />Months marked with a dark line at the bottom are where one or more loans make their final repayment, so your income may decrease from then on unless you reinvest.</div>
      </div>

      <div className="dz-compare">
        <button className="dz-sect-head as-btn" onClick={() => setCompareOpen((open) => !open)} type="button">
          <span className="dz-sect-sign">{compareOpen ? "–" : "+"}</span>
          <span className="dz-sect-title">What you invested and what you earned</span>
          <span style={{ flex: 1 }} />
          <span className="dz-compare-gain num">+ {pfMoneyLabel(ccy, Math.max(0, scenarioBInterest - scenarioAInterest))} if everything were reinvested</span>
        </button>
        {compareOpen ? (
          <div className="dz-compare-body">
            <p className="dz-compare-intro">Two scenarios on the same {pfMoneyLabel(ccy, totalBase)}, from {startLabel} to the last scheduled repayment in {horizonLabel}. Totals, not a rate per year.</p>
            <div className="dz-chart-card">
              <svg viewBox="0 0 880 326" style={{ display: "block", maxWidth: "100%" }}>
                {[0, 1, 2, 3, 4].map((step) => (
                  <line key={step} x1="46" y1={20 + step * 53.2} x2="790" y2={20 + step * 53.2} stroke="#DDE3E1" strokeWidth="1" />
                ))}
                {[0, 1, 2, 3, 4].map((step) => (
                  <text key={step} x="38" y={24 + step * 53.2} textAnchor="end" fontSize="11" fill="#626B70">{Math.round(chartMax - (step * chartMax) / 5)}%</text>
                ))}
                <line x1="46" y1="286" x2="790" y2="286" stroke="#151719" strokeWidth="1" />
                <text x="38" y="290" textAnchor="end" fontSize="11" fill="#626B70">0</text>
                <polyline points={`46,286 283,${chartY(pctPaid)} 790,${chartY(pctA)}`} fill="none" stroke="#151719" strokeWidth="2.5" />
                <polyline points={`283,${chartY(pctPaid)} 790,${chartY(pctB)}`} fill="none" stroke="#1E6A4B" strokeWidth="2.5" />
                <line x1="283" y1="20" x2="283" y2="286" stroke="#C4312C" strokeWidth="1" strokeDasharray="3 3" />
                <circle cx="46" cy="286" r="4" fill="#151719" />
                <circle cx="283" cy={chartY(pctPaid)} r="4.5" fill="#C4312C" />
                <circle cx="790" cy={chartY(pctA)} r="4.5" fill="#151719" />
                <circle cx="790" cy={chartY(pctB)} r="4.5" fill="#1E6A4B" />
                <text x="46" y="303" textAnchor="start" fontSize="11" fill="#626B70">{startLabel}</text>
                <text x="283" y="303" textAnchor="middle" fontSize="11" fontWeight="600" fill="#C4312C">today</text>
                <text x="790" y="303" textAnchor="end" fontSize="11" fill="#626B70">{horizonLabel}</text>
                <text x="800" y={chartY(pctA) + 4} textAnchor="start" fontSize="13" fontWeight="700" fill="#151719">+{pctA.toFixed(1)}%</text>
                <text x="800" y={chartY(pctB) + 4} textAnchor="start" fontSize="13" fontWeight="700" fill="#1E6A4B">+{pctB.toFixed(1)}%</text>
              </svg>
              <div className="dz-chart-note">Marked points are calculated. The path between them is the shape of accrual, not a month-by-month forecast.</div>
            </div>
            <div className="dz-scenarios">
              <div className="dz-scn-head"><span style={{ flex: 1 }}>Scenario</span><span className="dz-scn-col">Capital</span><span className="dz-scn-col">Interest earned</span><span className="dz-scn-col wide">Total returned</span><span className="dz-scn-col sm">On capital</span></div>
              <div className="dz-scn-row first">
                <span className="dz-scn-name"><span className="dz-scn-line"><span className="dz-scn-swatch dark" /><strong>Nothing reinvested</strong></span><span className="dz-scn-desc">Every borrower pays on schedule and each repayment stays in your account. The {pfMoneyLabel(ccy, idleMinor)} keeps sitting there.</span></span>
                <span className="dz-scn-col num">{pfMoneyLabel(ccy, totalBase)}</span>
                <span className="dz-scn-col num green">{pfMoneyLabel(ccy, scenarioAInterest)}</span>
                <span className="dz-scn-col wide num">{pfMoneyLabel(ccy, totalBase + scenarioAInterest)}</span>
                <span className="dz-scn-col sm"><span className="dz-scn-mult num">{totalBase > 0 ? (1 + scenarioAInterest / totalBase).toFixed(2) : "1.00"}×</span><span className="dz-scn-pct num">+{pctA.toFixed(1)}%</span></span>
              </div>
              <div className="dz-scn-row">
                <span className="dz-scn-name"><span className="dz-scn-line"><span className="dz-scn-swatch green" /><strong>Everything reinvested</strong></span><span className="dz-scn-desc">{bestOpenBps > 0 ? `Every repayment is lent onward at today’s best open rate of ${formatRateBps(bestOpenBps)} the month it arrives, and the ${pfMoneyLabel(ccy, idleMinor)} is lent too.` : "No open opportunity currently supplies a reinvestment rate, so this scenario adds no assumed reinvestment return."}</span></span>
                <span className="dz-scn-col num">{pfMoneyLabel(ccy, totalBase)}</span>
                <span className="dz-scn-col num green">{pfMoneyLabel(ccy, scenarioBInterest)}</span>
                <span className="dz-scn-col wide num">{pfMoneyLabel(ccy, totalBase + scenarioBInterest)}</span>
                <span className="dz-scn-col sm"><span className="dz-scn-mult num green">{totalBase > 0 ? (1 + scenarioBInterest / totalBase).toFixed(2) : "1.00"}×</span><span className="dz-scn-pct num">+{pctB.toFixed(1)}%</span></span>
              </div>
              <div className="dz-scn-row total">
                <span style={{ flex: 1, fontWeight: 600 }}>The difference reinvesting makes</span>
                <span className="dz-scn-col dim">no extra capital</span>
                <span className="dz-scn-col num green big">{pfMoneyLabel(ccy, Math.max(0, scenarioBInterest - scenarioAInterest))}</span>
                <span className="dz-scn-col wide num dim">{pfMoneyLabel(ccy, Math.max(0, scenarioBInterest - scenarioAInterest))}</span>
                <span className="dz-scn-col sm num green">+{Math.max(0, pctB - pctA).toFixed(1)} pts</span>
              </div>
              <div className="dz-scn-note">Both scenarios hold the same {pfMoneyLabel(ccy, totalBase)} — {pfMoneyLabel(ccy, investedMinor)} lent and {pfMoneyLabel(ccy, idleMinor)} in your wallet — to the last scheduled repayment in {horizonLabel}. {pfMoneyLabel(ccy, realizedInterest)} of the interest is already paid and counted in both. The rest depends on the borrowers paying as agreed{bestOpenBps > 0 ? `, and the green scenario also assumes a loan at today’s best open rate of ${formatRateBps(bestOpenBps)} is available every time you have money to place.` : ". The green scenario currently assumes no additional return because no open reinvestment rate is available."}</div>
            </div>
          </div>
        ) : null}
      </div>

      {batchOpen && deskBatchReady ? (
        <BatchReviewModal
          currency={ccy}
          items={deskItems.map((item) => ({ loan: item.match, amountMinor: item.amountMinor }))}
          onClose={() => setBatchOpen(false)}
          onDone={() => {
            setBatchOpen(false);
            void dashboardQuery.refetch();
            void balancesQuery.refetch();
            void smartInvestQuery.refetch();
            void portfolioQuery.refetch();
          }}
        />
      ) : null}
      {sheetLoan ? (
        <MarketplaceLoanSheet
          onClose={() => setSheetLoan(null)}
          onInvest={(detail, amount) => {
            setSheetLoan(null);
            setInvestLoan(detail, amount);
          }}
          preview={sheetLoan}
          setRoute={setRoute}
        />
      ) : null}
    </main>
  );
}

function BatchReviewModal({
  currency,
  items,
  onClose,
  onDone
}: {
  currency: string;
  items: { loan: MarketplaceLoanPreview; amountMinor: number }[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [ack, setAck] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [batchKey] = useState(() => idempotencyKey("primary-batch"));
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const batchMutation = useMarketplacePrimaryOrdersBatchCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.primary_investment);
  useAutoRequestEmailCode(codeRequest, !done);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.primary_market_investment },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const totalMinor = items.reduce((sum, item) => sum + item.amountMinor, 0);
  const submit = async () => {
    setError("");
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError("Current investment terms are not available. Retry after the document template is published.");
      return;
    }
    if (!codeRequest.codeId) {
      setError("Request an email code before confirming the batch.");
      return;
    }
    try {
      const acceptance = await acceptanceMutation.mutateAsync({
        data: {
          category: CategoryEnum.primary_market_investment,
          expected_template_version_id: termsQuery.data.id,
          accepted_checkbox_labels: labels,
          context_type: "primary_order_batch",
          context_id: batchKey,
          data_snapshot: {
            currency,
            items: items.map((item) => ({ loan_id: item.loan.loan_id, amount_minor: item.amountMinor }))
          },
          idempotency_key: `${batchKey}-accept`
        }
      });
      await batchMutation.mutateAsync({
        data: {
          items: items.map((item) => ({ loan_id: item.loan.loan_id, amount_minor: item.amountMinor })),
          document_acceptance_id: acceptance.id,
          idempotency_key: batchKey,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code
        }
      });
      setDone(true);
    } catch (submitError) {
      setError(apiErrorMessage(submitError));
    }
  };
  const busy = acceptanceMutation.isPending || batchMutation.isPending;
  return (
    <Modal
      footer={done
        ? <Button variant="primary" onClick={onDone}>Done</Button>
        : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ack || code.length < 6 || busy || (!isFixturePreview && !codeRequest.codeId)} variant="primary" onClick={() => void submit()}>{busy ? "Placing orders..." : `Confirm ${items.length === 1 ? "1 order" : `${items.length} orders`}`}</Button></>}
      onClose={done ? onDone : onClose}
      title={done ? "Orders placed" : "Review & confirm"}
      wide
    >
      {done ? (
        <SuccessState title={`${pfMoneyLabel(currency, totalMinor)} committed across ${items.length === 1 ? "1 loan" : `${items.length} loans`}`}>
          Each order is created and its balance reserved. If a funding round is cancelled, the reservation returns to your account automatically.
        </SuccessState>
      ) : (
        <div className="col gap-16">
          <div className="si-dash-rows">
            {items.map((item) => (
              <div className="si-dash-row" key={item.loan.loan_id} style={{ cursor: "default" }}>
                <span className="si-dash-row-name">{item.loan.borrower_display_name || item.loan.title}</span>
                <span className="si-dash-row-meta">{formatRateBps(marketplaceYieldBps(item.loan))} · {item.loan.term_months} mo · {item.loan.originator_name || "Banxum"}</span>
                <span className="dz-leader" />
                <span className="si-dash-row-amt">{pfMoneyLabel(currency, item.amountMinor)}</span>
              </div>
            ))}
            <div className="si-dash-rows-foot">
              <span className="num" style={{ fontWeight: 600, color: "#151719" }}>You commit {pfMoneyLabel(currency, totalMinor)}</span>
              <span style={{ flex: 1 }} />
              <span>one terms acceptance and one email code cover every order in this batch</span>
            </div>
          </div>
          <Check checked={ack} id="batch-ack" onChange={setAck}>
            I accept the current primary-market investment terms for every order listed above.
          </Check>
          <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code. One code covers the whole batch.</Banner>
          <CodeRequestField
            hint={previewHint("Demo: any 6 digits")}
            label="Email confirmation code"
            requestDisabled={emailCodeRequestDisabled(codeRequest)}
            requestLabel={emailCodeRequestLabel(codeRequest)}
            value={code}
            onChange={setCode}
            onRequest={codeRequest.requestCode}
          />
          {error ? <Banner tone="bad" title="Batch not placed">{error}</Banner> : null}
        </div>
      )}
    </Modal>
  );
}

function FrozenBanner({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  return (
    <Banner
      actions={<Button size="sm" variant="primary" onClick={() => goTo(setRoute, "balances")}>Add payout IBAN</Button>}
      icon="lock"
      tone="bad"
      title="Financial actions are frozen - provide a usable payout IBAN"
    >
      A balance lot passed the 60-day regulatory deadline and no usable IBAN is on file. Investing,
      withdrawals, FX and secondary-market actions are blocked, while portfolio, documents, statements
      and notices remain available.
    </Banner>
  );
}

function KycBanner({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  return (
    <Banner
      actions={<Button size="sm" variant="primary" onClick={() => goTo(setRoute, "kyc")}>View verification status</Button>}
      icon="shield"
      tone="info"
      title="Identity verification in progress"
    >
      KYC is being reviewed. Deposits, investing, withdrawals and FX unlock once verification is approved.
    </Banner>
  );
}

type MkFilters = {
  q: string;
  minRate: number | null;
  maxTerm: number | null;
  orig: string;
  col: string;
  ccy: string;
  rating: string;
  purpose: string;
  kind: string;
};

const mkDefaultFilters: MkFilters = {
  q: "",
  minRate: null,
  maxTerm: null,
  orig: "all",
  col: "all",
  ccy: "all",
  rating: "all",
  purpose: "all",
  kind: "all"
};

const mkIsUnsecured = (loan: MarketplaceLoanPreview) => /unsecured/i.test(loan.collateral_type);
const mkYieldPct = (loan: MarketplaceLoanPreview) => marketplaceYieldBps(loan) / 100;

function mkMatches(loan: MarketplaceLoanPreview, filters: MkFilters, skip?: keyof MkFilters) {
  const haystack = `${loan.loan_id} ${loan.title} ${loan.originator_name ?? ""} ${loan.borrower_display_name ?? ""} ${loan.purpose} ${loan.collateral_type} ${loan.risk_rating}`.toLowerCase();
  const checks: [keyof MkFilters, boolean][] = [
    ["q", filters.q.trim() === "" || haystack.includes(filters.q.trim().toLowerCase())],
    ["minRate", filters.minRate === null || mkYieldPct(loan) >= filters.minRate - 0.001],
    ["maxTerm", filters.maxTerm === null || loan.term_months <= filters.maxTerm],
    ["orig", filters.orig === "all" || (filters.orig === "banxum" ? !isOriginatorClaimLoan(loan) : loan.originator_id === filters.orig)],
    [
      "col",
      filters.col === "all"
        || (filters.col === "secured"
          ? !mkIsUnsecured(loan)
          : filters.col === "unsecured"
            ? mkIsUnsecured(loan)
            : loan.collateral_type === filters.col)
    ],
    ["ccy", filters.ccy === "all" || loan.currency === filters.ccy],
    ["rating", filters.rating === "all" || loan.risk_rating === filters.rating],
    ["purpose", filters.purpose === "all" || loan.purpose === filters.purpose],
    ["kind", filters.kind === "all" || (filters.kind === "refi" ? loan.is_refinancing : !loan.is_refinancing)]
  ];
  return checks.every(([key, ok]) => key === skip || ok);
}

function hasSmartInvestCriteria(filters: MkFilters) {
  return filters.minRate !== null
    || filters.maxTerm !== null
    || filters.orig !== "all"
    || filters.col !== "all"
    || filters.ccy !== "all"
    || filters.rating !== "all"
    || filters.purpose !== "all"
    || filters.kind !== "all";
}

function smartInvestRequestFromFilters(filters: MkFilters): SmartInvestRuleSaveRequest {
  const specificOriginator = filters.orig !== "all" && filters.orig !== "banxum";
  const specificCollateral = !["all", "secured", "unsecured"].includes(filters.col);
  return {
    minimum_yield_bps: filters.minRate === null ? null : Math.round(filters.minRate * 100),
    maximum_term_months: filters.maxTerm,
    originator_scope: filters.orig === "all"
      ? OriginatorScopeEnum.all
      : filters.orig === "banxum"
        ? OriginatorScopeEnum.banxum
        : OriginatorScopeEnum.specific,
    originator_id: specificOriginator ? filters.orig : null,
    collateral_scope: specificCollateral
      ? CollateralScopeEnum.specific
      : filters.col as SmartInvestRuleSaveRequest["collateral_scope"],
    collateral_type: specificCollateral ? filters.col : "",
    currency_scope: filters.ccy as SmartInvestRuleSaveRequest["currency_scope"],
    risk_rating: filters.rating === "all" ? "" : filters.rating,
    purpose: filters.purpose === "all" ? "" : filters.purpose,
    loan_kind: filters.kind === "refi"
      ? LoanKindEnum.refinancing
      : filters.kind === "new"
        ? LoanKindEnum.new
        : LoanKindEnum.all
  };
}

function smartInvestFiltersFromRule(rule: SmartInvestRule | null | undefined): MkFilters {
  if (!rule?.is_active) return mkDefaultFilters;
  return {
    q: "",
    minRate: rule.minimum_yield_bps === null ? null : rule.minimum_yield_bps / 100,
    maxTerm: rule.maximum_term_months,
    orig: rule.originator_scope === OriginatorScopeEnum.specific
      ? rule.originator_id ?? "all"
      : rule.originator_scope,
    col: rule.collateral_scope === CollateralScopeEnum.specific
      ? rule.collateral_type
      : rule.collateral_scope,
    ccy: rule.currency_scope,
    rating: rule.risk_rating || "all",
    purpose: rule.purpose || "all",
    kind: rule.loan_kind === LoanKindEnum.refinancing ? "refi" : rule.loan_kind
  };
}

function marketplaceLoanAsSmartOpportunity(loan: MarketplaceLoanPreview): SmartInvestOpportunity {
  return {
    loan_id: loan.loan_id,
    product_type: loan.product_type,
    investment_flow: loan.investment_flow,
    title: loan.title,
    purpose: loan.purpose,
    collateral_type: loan.collateral_type,
    interest_rate_bps: loan.interest_rate_bps,
    yield_bps: loan.yield_bps,
    underlying_interest_rate_bps: loan.underlying_interest_rate_bps,
    term_months: loan.term_months,
    remaining_term_days: loan.remaining_term_days,
    risk_rating: loan.risk_rating,
    funding_deadline: loan.funding_deadline,
    maturity_date: loan.maturity_date,
    status: loan.status,
    loan_status: loan.loan_status,
    opportunity_status: loan.opportunity_status,
    currency: loan.currency,
    principal_minor: loan.principal_minor,
    committed_principal_minor: loan.committed_principal_minor,
    remaining_capacity_minor: loan.remaining_capacity_minor,
    fillable_amount_minor: loan.fillable_amount_minor,
    minimum_investment_minor: loan.minimum_investment_minor,
    ltv_bps: loan.ltv_bps,
    is_refinancing: loan.is_refinancing,
    originator_id: loan.originator_id,
    originator_name: loan.originator_name,
    borrower_display_name: loan.borrower_display_name,
    skin_in_the_game_bps: loan.skin_in_the_game_bps,
    minimum_subscription_bps: loan.minimum_subscription_bps
  };
}

function previewSmartInvestResponse(
  filters: MkFilters,
  loans: MarketplaceLoanPreview[],
  currentRule?: SmartInvestRule | null
): SmartInvestResponse {
  const request = smartInvestRequestFromFilters(filters);
  const matches = loans.filter(isOpenMarketplaceLoan).filter((loan) => mkMatches(loan, filters));
  const timestamp = new Date().toISOString();
  return {
    rule: {
      id: currentRule?.id ?? "smart-invest-rule-preview",
      is_active: true,
      revision: (currentRule?.revision ?? 0) + 1,
      minimum_yield_bps: request.minimum_yield_bps ?? null,
      maximum_term_months: request.maximum_term_months ?? null,
      originator_scope: request.originator_scope ?? OriginatorScopeEnum.all,
      originator_id: request.originator_id ?? null,
      collateral_scope: request.collateral_scope ?? CollateralScopeEnum.all,
      collateral_type: request.collateral_type ?? "",
      currency_scope: request.currency_scope ?? CurrencyScopeEnum.all,
      risk_rating: request.risk_rating ?? "",
      purpose: request.purpose ?? "",
      loan_kind: request.loan_kind ?? LoanKindEnum.all,
      activated_at: timestamp,
      deactivated_at: null,
      created_at: currentRule?.created_at ?? timestamp,
      updated_at: timestamp
    },
    match_count: matches.length,
    open_opportunity_count: loans.filter(isOpenMarketplaceLoan).length,
    matches: matches.map(marketplaceLoanAsSmartOpportunity)
  };
}

const mkSortOptions: FsSortOption[] = [
  { key: "name", label: "Company" },
  { key: "rate", label: "Yield" },
  { key: "term", label: "Term" },
  { key: "margin", label: "Collateral margin" },
  { key: "available", label: "Available to invest" },
  { key: "closing", label: "Closes" }
];

function mkSortValue(loan: MarketplaceLoanPreview, key: string): number | string {
  if (key === "name") return loan.title.toLowerCase();
  if (key === "rate") return marketplaceYieldBps(loan);
  if (key === "term") return loan.term_months;
  if (key === "margin") return loan.ltv_bps ?? 999_999;
  if (key === "available") return marketplaceAvailableMinor(loan);
  return `${Number(isOpenMarketplaceLoan(loan)) === 1 ? "0" : "1"}${marketplaceClosingKey(loan)}`;
}

function MarketplaceScreen({
  setInvestLoan,
  setRoute
}: {
  demoState: DemoAccountState;
  setInvestLoan: (loan: MarketplaceLoanDetail | null, initialAmount?: string) => void;
  setRoute: (route: AppRoute) => void;
}) {
  const queryClient = useQueryClient();
  const [sheetLoanId, setSheetLoanId] = useState<string | null>(null);
  const loansQuery = useMarketplaceLoansData();
  const balancesQuery = useBalancesData();
  const smartInvestQuery = useSmartInvestData();
  const smartInvestMutation = useV1InvestorSmartInvestUpdate();
  const loans = loansQuery.data ?? [];
  const [filters, setFilters] = useState<MkFilters>(mkDefaultFilters);
  const [panelOpen, setPanelOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"focused" | "detailed">("focused");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [capacityCurrency, setCapacityCurrency] = useState("CHF");
  const [showOrderGuide, setShowOrderGuide] = useState(false);
  const [smartInvestError, setSmartInvestError] = useState("");

  const setFlt = <K extends keyof MkFilters>(key: K, value: MkFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value }));
    if (key === "ccy" && typeof value === "string" && value !== "all") setCapacityCurrency(value);
  };
  const pickSort = (key: string) => {
    setSortDir(sortKey === key && sortDir === "asc" ? "desc" : "asc");
    setSortKey(key);
  };

  const openLoans = loans.filter(isOpenMarketplaceLoan);
  const filtered = openLoans.filter((loan) => mkMatches(loan, filters));
  const sortedLoans = [...filtered].sort((left, right) => {
    if (!sortKey) {
      const openDelta = Number(isOpenMarketplaceLoan(right)) - Number(isOpenMarketplaceLoan(left));
      return openDelta || marketplaceClosingKey(left).localeCompare(marketplaceClosingKey(right));
    }
    const x = mkSortValue(left, sortKey);
    const y = mkSortValue(right, sortKey);
    const c = typeof x === "string" ? x.localeCompare(String(y)) : x - Number(y);
    return sortDir === "asc" ? c : -c;
  });
  const openCount = openLoans.length;

  const yieldPcts = openLoans.map(mkYieldPct);
  const rateFloor = openLoans.length > 0 ? Math.floor(Math.min(...yieldPcts) * 10) / 10 : 0;
  const rateCeil = openLoans.length > 0 ? Math.ceil(Math.max(...yieldPcts) * 10) / 10 : 0;
  const termVals = Array.from(new Set(openLoans.map((loan) => loan.term_months))).sort((a, b) => a - b);
  const termCeil = termVals[termVals.length - 1] ?? 0;
  const rateValue = filters.minRate ?? rateFloor;
  const termValue = filters.maxTerm ?? termCeil;
  const rateBinCount = 20;
  const rateBins = Array.from({ length: rateBinCount }, (_, index) => {
    const lo = rateFloor + ((rateCeil - rateFloor) * index) / rateBinCount;
    const hi = rateFloor + ((rateCeil - rateFloor) * (index + 1)) / rateBinCount;
    const n = openLoans.filter((loan) => {
      const pct = mkYieldPct(loan);
      return mkMatches(loan, filters, "minRate") && pct >= lo - 0.001 && (index === rateBinCount - 1 ? pct <= hi + 0.001 : pct < hi);
    }).length;
    return { lo, n };
  });
  const rateBinMax = Math.max(1, ...rateBins.map((bin) => bin.n));
  const termBins = termVals.map((term) => ({
    term,
    n: openLoans.filter((loan) => loan.term_months === term && mkMatches(loan, filters, "maxTerm")).length
  }));
  const termBinMax = Math.max(1, ...termBins.map((bin) => bin.n));

  const originators = Array.from(
    new Map(
      openLoans
        .filter(isOriginatorClaimLoan)
        .filter((loan) => loan.originator_id && loan.originator_name)
        .map((loan) => [loan.originator_id as string, loan.originator_name as string])
    ).entries()
  ).map(([id, name]) => ({ id, name })).sort((left, right) => left.name.localeCompare(right.name));
  const collateralKinds = Array.from(
    new Set(openLoans.filter((loan) => !mkIsUnsecured(loan)).map((loan) => loan.collateral_type))
  ).sort();
  const currencies = Array.from(new Set(openLoans.map((loan) => loan.currency))).sort();
  const ratings = Array.from(new Set(openLoans.map((loan) => loan.risk_rating))).sort();
  const purposes = Array.from(new Set(openLoans.map((loan) => loan.purpose))).sort();

  const chip = (group: keyof MkFilters, value: string, label: string, predicate: (loan: MarketplaceLoanPreview) => boolean) => {
    const count = openLoans.filter((loan) => predicate(loan) && mkMatches(loan, filters, group)).length;
    const on = filters[group] === value;
    return { group, value, label, count, on };
  };
  const chipButton = (item: ReturnType<typeof chip>) => (
    <button
      aria-pressed={item.on}
      className={`fs-chip${item.on ? " on" : item.count === 0 ? " dim" : ""}`}
      key={`${String(item.group)}-${item.value}`}
      onClick={() => setFlt(item.group, (item.on ? "all" : item.value) as MkFilters[typeof item.group])}
      type="button"
    >
      {item.label}
      <span className="fs-chip-count">{item.count}</span>
    </button>
  );

  const tokens: { label: string; clear: () => void }[] = [];
  if (filters.q.trim() !== "") tokens.push({ label: `matching "${filters.q.trim()}"`, clear: () => setFlt("q", "") });
  if (filters.minRate !== null) tokens.push({ label: `${filters.minRate.toFixed(1)}% and up`, clear: () => setFlt("minRate", null) });
  if (filters.maxTerm !== null) tokens.push({ label: `up to ${filters.maxTerm} months`, clear: () => setFlt("maxTerm", null) });
  if (filters.orig !== "all") {
    const originatorName = originators.find((originator) => originator.id === filters.orig)?.name;
    tokens.push({
      label: filters.orig === "banxum" ? "from BANXUM" : `from ${originatorName ?? "selected originator"}`,
      clear: () => setFlt("orig", "all")
    });
  }
  if (filters.col !== "all") tokens.push({ label: filters.col === "secured" ? "with collateral" : filters.col === "unsecured" ? "no collateral" : humanizeToken(filters.col).toLowerCase(), clear: () => setFlt("col", "all") });
  if (filters.ccy !== "all") tokens.push({ label: filters.ccy, clear: () => setFlt("ccy", "all") });
  if (filters.rating !== "all") tokens.push({ label: `rated ${filters.rating}`, clear: () => setFlt("rating", "all") });
  if (filters.purpose !== "all") tokens.push({ label: humanizeToken(filters.purpose).toLowerCase(), clear: () => setFlt("purpose", "all") });
  if (filters.kind !== "all") tokens.push({ label: filters.kind === "refi" ? "refinancings" : "new lending", clear: () => setFlt("kind", "all") });
  const clearAllFilters = () => setFilters(mkDefaultFilters);
  const balanceSummaries = balancesQuery.data?.summaries ?? [];
  const activeCapacityCurrency = balanceSummaries.some((summary) => summary.currency === capacityCurrency)
    ? capacityCurrency
    : balanceSummaries[0]?.currency ?? capacityCurrency;
  const capacitySummary = balanceSummaries.find((summary) => summary.currency === activeCapacityCurrency);
  const hasAccountMoney = balanceSummaries.some((summary) => summary.total_available_minor > 0);
  const minimumLoan = (openLoans.length > 0 ? openLoans : loans).reduce<MarketplaceLoanPreview | undefined>(
    (lowest, loan) =>
      lowest === undefined || loan.minimum_investment_minor < lowest.minimum_investment_minor
        ? loan
        : lowest,
    undefined
  );
  const minimumCurrency = minimumLoan?.currency ?? "EUR";
  const minimumInvestmentMinor = minimumLoan?.minimum_investment_minor ?? 100000;
  const investingRuleActive = smartInvestQuery.data?.rule?.is_active === true;
  const saveSmartFilters = async () => {
    setSmartInvestError("");
    if (!hasSmartInvestCriteria(filters)) {
      setSmartInvestError("Choose at least one filter before saving a Smart Invest rule.");
      return;
    }
    if (isReadonlyImpersonationActive()) {
      setSmartInvestError("Smart Invest cannot be changed in a superadmin read-only view.");
      return;
    }
    try {
      const response = isFixturePreview
        ? previewSmartInvestResponse(filters, loans, smartInvestQuery.data?.rule)
        : await smartInvestMutation.mutateAsync({ data: smartInvestRequestFromFilters(filters) });
      queryClient.setQueryData(getV1InvestorSmartInvestRetrieveQueryKey(), response);
      setPanelOpen(false);
      goTo(setRoute, "smartInvest");
    } catch (error) {
      setSmartInvestError(apiErrorMessage(error));
    }
  };

  return (
    <main className="content marketplace-page">
      <section className="marketplace-intro">
        <div className="eyebrow">
          {openCount} open today · From {marketplaceCurrencySymbol(minimumCurrency)} {formatMoneyMinor(minimumInvestmentMinor, minimumCurrency, 0)}
        </div>
        <h1>These companies want your investment</h1>
        {hasAccountMoney ? (
          <p>Two ways to put your money to work</p>
        ) : (
          <p>
            Review each opportunity, target yield, collateral and repayment term. You decide where to
            invest; returns are not guaranteed and invested capital is at risk.
          </p>
        )}
      </section>

      <section aria-label="Investable balance" className="marketplace-capacity">
        <div className="marketplace-capacity-label">Available to commit</div>
        <div className="marketplace-capacity-amount">
          <span>{activeCapacityCurrency}</span>
          {capacitySummary ? formatMoneyMinor(capacitySummary.investable_minor, activeCapacityCurrency) : "-"}
        </div>
        <div className="marketplace-capacity-note">
          {balancesQuery.isLoading && balanceSummaries.length === 0
            ? "Loading your eligible balance..."
            : capacitySummary
              ? "available to invest"
              : "No investable balance is currently available in this currency."}
        </div>
        {balanceSummaries.length > 1 ? (
          <Segmented
            options={balanceSummaries.map((summary) => ({ value: summary.currency, label: summary.currency }))}
            value={activeCapacityCurrency}
            onChange={setCapacityCurrency}
          />
        ) : null}
        <button
          aria-label="Set your investing rule"
          className={`marketplace-investing-rule ${investingRuleActive ? "active" : "inactive"}`}
          onClick={() => goTo(setRoute, "smartInvest")}
          type="button"
        >
          <span aria-hidden="true" className="marketplace-investing-rule-dot" />
          <span className="marketplace-investing-rule-name">Investing rule</span>
          <span className="marketplace-investing-rule-state">{investingRuleActive ? "Active" : "Not active"}</span>
          <span aria-hidden="true" className="marketplace-investing-rule-arrow">→</span>
        </button>
      </section>

      <section className="marketplace-opportunities">
        <div className="marketplace-section-head">
          <div>
            <div className="eyebrow">Primary market</div>
            <h2>Open investment opportunities</h2>
          </div>
        </div>

        {tokens.length > 0 ? (
          <div className="fs-tokens">
            {tokens.map((token) => (
              <button className="fs-token" key={token.label} onClick={token.clear} type="button">
                {token.label}
                <span aria-hidden="true" className="fs-token-x">×</span>
              </button>
            ))}
            <button className="fs-clear-link" onClick={clearAllFilters} type="button">clear</button>
          </div>
        ) : null}

        <div className="fs-controls">
          <button
            aria-controls="marketplace-filter-panel"
            aria-expanded={panelOpen}
            className={`fs-pill${panelOpen || tokens.length > 0 ? " on" : ""}`}
            onClick={() => setPanelOpen((open) => !open)}
            type="button"
          >
            <span>Filter</span>
            <span aria-hidden="true" className="fs-caret">{panelOpen ? "▲" : "▼"}</span>
          </button>
          <SortControl activeKey={sortKey} dir={sortDir} onPick={pickSort} options={mkSortOptions} />
          {sortKey ? (
            <button className="fs-clear-link" onClick={() => { setSortKey(null); setSortDir("asc"); }} type="button">back to closing soonest</button>
          ) : null}
          <span className="fs-count"><strong>{filtered.length}</strong> of {openLoans.length} match</span>
          <span style={{ flex: 1 }} />
          <Segmented
            options={[{ value: "focused", label: "Focused" }, { value: "detailed", label: "Detailed" }]}
            value={viewMode}
            onChange={setViewMode}
          />
        </div>

        {panelOpen ? (
          <div className="fs-panel" id="marketplace-filter-panel">
            <div className="fs-search-row">
              <div className="fs-group-cap">Find a loan</div>
              <input
                aria-label="Search investment opportunities"
                className="fs-search-input"
                onChange={(event) => setFlt("q", event.target.value)}
                placeholder="Name, purpose, collateral or reference"
                value={filters.q}
              />
            </div>
            <div className="fs-sliders">
              <div>
                <div className="fs-slider-head">
                  <span className="fs-group-cap">
                    Pays at least
                    {filters.minRate !== null ? <button aria-label="Clear minimum rate" className="fs-group-x" onClick={() => setFlt("minRate", null)} type="button">×</button> : null}
                  </span>
                  <span className="fs-slider-val">{filters.minRate === null ? "any rate" : `${rateValue.toFixed(1)}%`}</span>
                </div>
                <div className="fs-hist">
                  {rateBins.map((bin, index) => (
                    <span
                      key={index}
                      style={{
                        height: bin.n > 0 ? `${Math.max(7, Math.round((bin.n / rateBinMax) * 100))}%` : "2px",
                        background: bin.lo >= rateValue - 0.001 && bin.n > 0 ? "#B9C0C4" : "#EDEAE2"
                      }}
                    />
                  ))}
                </div>
                <input
                  aria-label="Minimum yield"
                  className="fs-range"
                  max={rateCeil}
                  min={rateFloor}
                  onChange={(event) => setFlt("minRate", Number(event.target.value) <= rateFloor ? null : Number(event.target.value))}
                  step={0.1}
                  type="range"
                  value={rateValue}
                />
                <div className="fs-range-ends"><span>{rateFloor.toFixed(1)}%</span><span>{rateCeil.toFixed(1)}%</span></div>
              </div>
              <div>
                <div className="fs-slider-head">
                  <span className="fs-group-cap">
                    Runs no longer than
                    {filters.maxTerm !== null ? <button aria-label="Clear maximum term" className="fs-group-x" onClick={() => setFlt("maxTerm", null)} type="button">×</button> : null}
                  </span>
                  <span className="fs-slider-val">{filters.maxTerm === null ? "any term" : `${termValue} mo`}</span>
                </div>
                <div className="fs-hist wide">
                  {termBins.map((bin) => (
                    <span
                      key={bin.term}
                      style={{
                        height: bin.n > 0 ? `${Math.max(7, Math.round((bin.n / termBinMax) * 100))}%` : "2px",
                        background: bin.term <= termValue && bin.n > 0 ? "#B9C0C4" : "#EDEAE2"
                      }}
                    />
                  ))}
                </div>
                <input
                  aria-label="Maximum term"
                  className="fs-range"
                  max={termCeil}
                  min={termVals[0] ?? 0}
                  onChange={(event) => setFlt("maxTerm", Number(event.target.value) >= termCeil ? null : Number(event.target.value))}
                  step={1}
                  type="range"
                  value={termValue}
                />
                <div className="fs-range-ends"><span>{termVals[0] ?? 0} mo</span><span>{termCeil} mo</span></div>
              </div>
            </div>
            <div className="fs-groups">
              <div className="fs-group">
                <div className="fs-group-cap">
                  Originated by
                  {filters.orig !== "all" ? <button aria-label="Clear originator filter" className="fs-group-x" onClick={() => setFlt("orig", "all")} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {chipButton(chip("orig", "banxum", "BANXUM", (loan) => !isOriginatorClaimLoan(loan)))}
                  {originators.map((originator) => chipButton(chip("orig", originator.id, originator.name, (loan) => loan.originator_id === originator.id)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Collateral
                  {filters.col !== "all" ? <button aria-label="Clear collateral filter" className="fs-group-x" onClick={() => setFlt("col", "all")} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {chipButton(chip("col", "secured", "With collateral", (loan) => !mkIsUnsecured(loan)))}
                  {chipButton(chip("col", "unsecured", "No collateral", (loan) => mkIsUnsecured(loan)))}
                </div>
                {filters.col !== "unsecured" ? (
                  <div className="fs-subgroup">
                    <span className="fs-subgroup-label">of which</span>
                    <span className="fs-subgroup-body">
                      <span className="fs-chips">
                        {collateralKinds.map((kind) => chipButton(chip("col", kind, humanizeToken(kind), (loan) => loan.collateral_type === kind)))}
                      </span>
                    </span>
                  </div>
                ) : null}
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Currency
                  {filters.ccy !== "all" ? <button aria-label="Clear currency filter" className="fs-group-x" onClick={() => setFlt("ccy", "all")} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {currencies.map((code) => chipButton(chip("ccy", code, code, (loan) => loan.currency === code)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Risk rating
                  {filters.rating !== "all" ? <button aria-label="Clear rating filter" className="fs-group-x" onClick={() => setFlt("rating", "all")} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {ratings.map((rating) => chipButton(chip("rating", rating, rating, (loan) => loan.risk_rating === rating)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Purpose
                  {filters.purpose !== "all" ? <button aria-label="Clear purpose filter" className="fs-group-x" onClick={() => setFlt("purpose", "all")} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {purposes.map((purpose) => chipButton(chip("purpose", purpose, humanizeToken(purpose), (loan) => loan.purpose === purpose)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Loan type
                  {filters.kind !== "all" ? <button aria-label="Clear loan type filter" className="fs-group-x" onClick={() => setFlt("kind", "all")} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {chipButton(chip("kind", "new", "New lending", (loan) => !loan.is_refinancing))}
                  {chipButton(chip("kind", "refi", "Refinancing", (loan) => loan.is_refinancing))}
                </div>
              </div>
            </div>
            <div className="fs-panel-foot">
              <span className="fs-panel-note">
                Filters never rank or score opportunities. Without a selected sort, results stay closing soonest.
              </span>
              <button className="fs-save-rule" disabled={smartInvestMutation.isPending} onClick={() => void saveSmartFilters()} type="button">
                {smartInvestMutation.isPending ? "Saving..." : "Save Smart Filters"}
              </button>
              <button className="fs-done" onClick={() => setPanelOpen(false)} type="button">Done</button>
            </div>
            {smartInvestError ? <div className="fs-save-error" role="alert">{smartInvestError}</div> : null}
          </div>
        ) : null}

      {loansQuery.isError && loans.length === 0 ? (
        <DataErrorCard title="Could not load marketplace" onRetry={() => void loansQuery.refetch()}>
          The primary-market loan list is unavailable. Retry once the API connection is restored.
        </DataErrorCard>
      ) : loansQuery.isLoading && loans.length === 0 ? (
        <LoadingCard title="Loading marketplace">Fetching primary-market loans.</LoadingCard>
      ) : filtered.length === 0 ? (
        <div className="fs-empty">
          <div className="fs-empty-copy">
            {openLoans.length === 0
              ? "No investment opportunities are open right now. New opportunities will appear here after publication."
              : "Nothing open today matches all of that at once. Widen one of them, or set a standing rule to catch it when something does."}
          </div>
          <div className="fs-empty-actions">
            {tokens.length > 0 ? <button className="fs-empty-clear" onClick={clearAllFilters} type="button">Clear the filter</button> : null}
            <button className="fs-empty-rule" onClick={() => goTo(setRoute, "smartInvest")} type="button">Set a standing rule</button>
          </div>
        </div>
      ) : (
        <MarketplaceOpportunityList
          loans={sortedLoans}
          onOpen={(loan) => setSheetLoanId(loan.loan_id)}
          asOf={balancesQuery.data?.as_of}
          viewMode={viewMode}
          sortKey={sortKey}
          sortDir={sortDir}
          onPickSort={pickSort}
        />
      )}
      {sheetLoanId ? (() => {
        const sheetPreview = loans.find((loan) => loan.loan_id === sheetLoanId);
        if (!sheetPreview) return null;
        return (
          <MarketplaceLoanSheet
            onClose={() => setSheetLoanId(null)}
            onInvest={(detail, amount) => {
              setSheetLoanId(null);
              setInvestLoan(detail, amount);
            }}
            preview={sheetPreview}
            setRoute={setRoute}
          />
        );
      })() : null}
      <p className="marketplace-footnote">
        Direct-loan progress reflects validated allocations. Originator-claim progress reflects the
        legal claim principal already sold; quoted prices can change as interest accrues or repayments arrive.
      </p>
      </section>

      <section aria-label="How primary-market orders work" className="marketplace-process">
        <div>
          <span className="marketplace-process-number">01</span>
          <strong>Choose each opportunity</strong>
          <p>Open it to review the disclosed counterparty, yield, collateral, cash-flow schedule, documents and risks.</p>
        </div>
        <div>
          <span className="marketplace-process-number">02</span>
          <strong>Confirm the applicable investment flow</strong>
          <p>Direct-loan orders reserve eligible balance after allocation. Originator claims are priced and assigned immediately when purchased.</p>
        </div>
        <div>
          <span className="marketplace-process-number">03</span>
          <strong>Your portfolio records the legal claim</strong>
          <p>Direct-loan holdings start at funding close. An originator claim enters your portfolio as soon as the purchase settles on BANXUM.</p>
        </div>
        <button className="marketplace-process-help" onClick={() => setShowOrderGuide(true)} type="button">
          Full order explanation <Icon name="chevR" size={14} />
        </button>
      </section>

      {showOrderGuide ? (
        <Modal
          footer={<Button variant="primary" onClick={() => setShowOrderGuide(false)}>Close</Button>}
          onClose={() => setShowOrderGuide(false)}
          title="How primary-market orders work"
          wide
        >
          <div className="marketplace-order-guide">
            <div><span>1</span><p><strong>You submit an order.</strong> It records the amount you want to invest, but a pending order does not reserve loan capacity.</p></div>
            <div><span>2</span><p><strong>BANXUM validates eligible balance.</strong> Allocation is first come, first served and remains subject to your balance-lot investment window and the loan's remaining capacity.</p></div>
            <div><span>3</span><p><strong>Allocated money is reserved.</strong> If the funding round proceeds, Garanta closes it and the allocated amount becomes a loan holding in your portfolio.</p></div>
            <div><span>4</span><p><strong>If the loan does not proceed, the reservation is released.</strong> The amount returns to your platform balance and keeps its original regulatory ageing deadlines.</p></div>
          </div>
          <Banner tone="neutral" title="Minimum order">
            The launch minimum is CHF/EUR 1,000 per order. The backend confirms eligibility, capacity, terms acceptance and the fresh email code before allocation.
          </Banner>
        </Modal>
      ) : null}
    </main>
  );
}

function smartInvestRuleSummary(filters: MkFilters, originators: Array<{ id: string; name: string }>) {
  const originator = originators.find((item) => item.id === filters.orig)?.name;
  const rows = [
    {
      label: "Collateral",
      value: filters.col === "all"
        ? "Any collateral"
        : filters.col === "secured"
          ? "Collateral required"
          : filters.col === "unsecured"
            ? "No collateral required"
            : humanizeToken(filters.col)
    },
    { label: "Currency", value: filters.ccy === "all" ? "CHF and EUR" : filters.ccy },
    { label: "Minimum yield", value: filters.minRate === null ? "No minimum" : `${filters.minRate.toFixed(1)}% p.a.` },
    { label: "Maximum term", value: filters.maxTerm === null ? "Any term" : `${filters.maxTerm} months` },
    {
      label: "Source",
      value: filters.orig === "all" ? "BANXUM and all Loan Originators" : filters.orig === "banxum" ? "BANXUM direct loans" : originator ?? "Selected Loan Originator"
    },
    { label: "Risk rating", value: filters.rating === "all" ? "Any rating" : filters.rating },
    { label: "Purpose", value: filters.purpose === "all" ? "Any purpose" : humanizeToken(filters.purpose) },
    { label: "Loan type", value: filters.kind === "all" ? "New lending and refinancing" : filters.kind === "refi" ? "Refinancing" : "New lending" }
  ];
  return rows;
}

function SmartInvestMatchTable({
  matches,
  onOpen
}: {
  matches: SmartInvestOpportunity[];
  onOpen: (match: SmartInvestOpportunity) => void;
}) {
  if (matches.length === 0) {
    return (
      <div className="smart-invest-empty">
        <div>Nothing open today matches every condition in your rule.</div>
        <p>The rule remains active and will alert you when a newly published opportunity qualifies.</p>
      </div>
    );
  }
  return (
    <div className="smart-invest-match-table" role="table" aria-label="Smart Invest matches">
      <div className="smart-invest-match-head" role="row">
        <span>Company</span><span>Yield</span><span>Term</span><span>Collateral</span><span>Available</span><span />
      </div>
      {matches.map((match) => (
        <button
          className="smart-invest-match-row"
          key={match.loan_id}
          onClick={() => onOpen(match)}
          role="row"
          type="button"
        >
          <span>
            <strong>{match.borrower_display_name || match.title}</strong>
            <small>{match.originator_name ? `Originated by ${match.originator_name}` : match.purpose}</small>
          </span>
          <span>{formatRateBps(match.yield_bps)}</span>
          <span>{match.term_months} mo</span>
          <span>{match.ltv_bps === null ? "Unsecured" : `${((10_000 - match.ltv_bps) / 100).toFixed(1)}% margin`}</span>
          <span>{formatMoneyMinor(match.fillable_amount_minor, match.currency)}</span>
          <span aria-hidden="true">→</span>
        </button>
      ))}
    </div>
  );
}

function SmartInvestWizard({
  initialFilters,
  loans,
  onClose,
  onSave,
  saving
}: {
  initialFilters: MkFilters;
  loans: MarketplaceLoanPreview[];
  onClose: () => void;
  onSave: (filters: MkFilters) => Promise<void>;
  saving: boolean;
}) {
  const [step, setStep] = useState(0);
  const [filters, setFilters] = useState(initialFilters);
  const [error, setError] = useState("");
  const labels = [
    "Step 1 of 5 · what must be behind the loan",
    "Step 2 of 5 · which currency it uses",
    "Step 3 of 5 · optional, a floor on the rate",
    "Step 4 of 5 · optional, a ceiling on the term",
    "Step 5 of 5 · review your rule"
  ];
  const openLoans = loans.filter(isOpenMarketplaceLoan);
  const matchCount = openLoans.filter((loan) => mkMatches(loan, filters)).length;
  const securedCount = openLoans.filter((loan) => !mkIsUnsecured(loan)).length;
  const update = <K extends keyof MkFilters>(key: K, value: MkFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setError("");
  };
  const finish = async () => {
    if (!hasSmartInvestCriteria(filters)) {
      setError("Choose at least one condition before activating Smart Invest.");
      return;
    }
    await onSave(filters);
  };
  const optionCard = (on: boolean, title: string, note: string, go: () => void) => (
    <button className={`si-wiz-option${on ? " on" : ""}`} key={title} onClick={go} type="button">
      <strong>{title}</strong>
      <span>{note}</span>
    </button>
  );
  return (
    <div className="ls-scrim si-wiz-scrim" role="presentation">
      <button aria-label="Close Smart Invest setup" className="ls-overlay-btn" onClick={onClose} tabIndex={-1} type="button" />
      <section aria-label="Smart Invest setup" aria-modal="true" className="si-wiz" role="dialog">
        <div className="si-wiz-head">
          <div className="si-wiz-head-main">
            <div className="si-wiz-pips">
              {labels.map((label, index) => (
                <span key={label} style={{ background: index < step ? "#151719" : index === step ? "#C4312C" : "#DDE3E1" }} />
              ))}
            </div>
            <div className="si-wiz-label">{labels[step]}</div>
          </div>
          <div className="si-wiz-count">
            <div className="si-wiz-count-cap">Would qualify today</div>
            <div className="si-wiz-count-row"><span className="si-wiz-count-n">{matchCount}</span><span className="si-wiz-count-of">of {openLoans.length}</span></div>
          </div>
          <button aria-label="Close" className="ls-x" onClick={onClose} type="button">×</button>
        </div>
        <div className="si-wiz-body">
          {step === 0 ? (
            <>
              <div className="si-wiz-cap red">Question 1 of 2 · no default</div>
              <h3>Must an asset be pledged?</h3>
              <p>{securedCount} of the {openLoans.length} open today have something pledged — a mortgage, a charge over equipment, or assigned receivables. The rest rely on the borrower&apos;s promise alone, and collateral never guarantees complete recovery.</p>
              <div className="si-wiz-options">
                {optionCard(filters.col === "secured", "Required", `Only loans with a pledged asset — ${securedCount} of ${openLoans.length}.`, () => update("col", "secured"))}
                {optionCard(filters.col === "all", "Not required", `Unsecured lending is acceptable — all ${openLoans.length}.`, () => update("col", "all"))}
              </div>
            </>
          ) : null}
          {step === 1 ? (
            <>
              <div className="si-wiz-cap red">Question 2 of 2 · no default</div>
              <h3>Which currency should it use?</h3>
              <p>The rule never converts funds and never combines CHF and EUR balances. A match in a currency you hold nothing of still reaches you — adding money afterwards is your call.</p>
              <div className="si-wiz-options">
                {optionCard(filters.ccy === "CHF", "CHF only", "Match opportunities denominated in Swiss francs.", () => update("ccy", "CHF"))}
                {optionCard(filters.ccy === "EUR", "EUR only", "Match opportunities denominated in euros.", () => update("ccy", "EUR"))}
                {optionCard(filters.ccy === "all", "CHF and EUR", "Match either supported currency.", () => update("ccy", "all"))}
              </div>
            </>
          ) : null}
          {step === 2 ? (
            <>
              <div className="si-wiz-cap green">Your rule already works · everything from here is optional</div>
              <h3>A floor on the rate?</h3>
              <p>A high floor means the rule will often find nothing — and a high rate is not a sign of a better borrower, frequently the opposite.</p>
              <div className="si-wiz-value-row">
                <span className="si-wiz-value">{filters.minRate === null ? "no floor" : `${filters.minRate.toFixed(1)}%`}</span>
                <span className="si-wiz-value-note">{filters.minRate === null ? "every rate qualifies" : "anything below this is skipped"}</span>
              </div>
              <input aria-label="Minimum Smart Invest yield" className="fs-range" max="25" min="0" onChange={(event) => update("minRate", Number(event.target.value) === 0 ? null : Number(event.target.value))} step="0.1" type="range" value={filters.minRate ?? 0} />
              <div className="si-wiz-ends"><span>no floor</span><span>25%</span></div>
            </>
          ) : null}
          {step === 3 ? (
            <>
              <div className="si-wiz-cap green">Optional · step 4 of 5</div>
              <h3>A ceiling on how long?</h3>
              <p>The longer the term, the longer your capital is committed at today&apos;s rate rather than tomorrow&apos;s.</p>
              <div className="si-wiz-value-row">
                <span className="si-wiz-value">{filters.maxTerm === null ? "no ceiling" : `${filters.maxTerm} months`}</span>
                <span className="si-wiz-value-note">{filters.maxTerm === null ? "every term qualifies" : "anything longer is skipped"}</span>
              </div>
              <input aria-label="Maximum Smart Invest term" className="fs-range" max="120" min="6" onChange={(event) => update("maxTerm", Number(event.target.value) === 120 ? null : Number(event.target.value))} step="6" type="range" value={filters.maxTerm ?? 120} />
              <div className="si-wiz-ends"><span>6 months</span><span>no ceiling</span></div>
            </>
          ) : null}
          {step === 4 ? (
            <>
              <div className="si-wiz-cap">Step 5 of 5 · review</div>
              <h3>This is your rule.</h3>
              <div className="si-wiz-summary">
                {smartInvestRuleSummary(filters, []).slice(0, 4).map((row, index) => (
                  <div className="si-wiz-summary-row" key={row.label}>
                    <span className="si-wiz-summary-k">{row.label}</span>
                    <span className="si-wiz-summary-dots" />
                    <strong>{row.value}</strong>
                    <button className="fs-clear-link" onClick={() => setStep(index)} type="button">change</button>
                  </div>
                ))}
              </div>
              <div className="si-wiz-outcome">
                Smart Invest sends you a transactional alert when a newly published opportunity matches. It never places an order, reserves balance or judges whether the borrower is suitable for you.
              </div>
            </>
          ) : null}
          {error ? <div className="smart-inline-error" role="alert">{error}</div> : null}
        </div>
        <div className="si-wiz-foot">
          <button className="si-pill-outline" disabled={step === 0 || saving} onClick={() => setStep((current) => Math.max(0, current - 1))} type="button">Back</button>
          <span style={{ flex: 1 }} />
          {step >= 2 && step < 4 ? (
            <button className="fs-clear-link" onClick={() => setStep(4)} type="button">Finish now, skip the rest</button>
          ) : null}
          {step < 4 ? (
            <button className="si-pill-dark" onClick={() => setStep((current) => Math.min(4, current + 1))} type="button">Continue</button>
          ) : (
            <button className="si-pill-dark" disabled={saving} onClick={() => void finish()} type="button">{saving ? "Activating..." : "Activate the rule"}</button>
          )}
        </div>
      </section>
    </div>
  );
}

function SmartInvestScreen({
  setRoute,
  setInvestLoan
}: {
  setRoute: (route: AppRoute) => void;
  setInvestLoan: (loan: MarketplaceLoanDetail | null, initialAmount?: string) => void;
}) {
  const queryClient = useQueryClient();
  const smartQuery = useSmartInvestData();
  const loansQuery = useMarketplaceLoansData();
  const updateMutation = useV1InvestorSmartInvestUpdate();
  const deactivateMutation = useV1InvestorSmartInvestDeactivateCreate();
  const [filters, setFilters] = useState<MkFilters>(mkDefaultFilters);
  const [editorOpen, setEditorOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [sheetLoanId, setSheetLoanId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const data = smartQuery.data;
  const rule = data?.rule;
  const active = rule?.is_active === true;
  const loans = loansQuery.data ?? [];
  const originators = Array.from(
    new Map(loans.filter((loan) => loan.originator_id && loan.originator_name).map((loan) => [loan.originator_id as string, loan.originator_name as string])).entries()
  ).map(([id, name]) => ({ id, name })).sort((left, right) => left.name.localeCompare(right.name));
  const ratings = Array.from(new Set(loans.map((loan) => loan.risk_rating).filter(Boolean))).sort();
  const purposes = Array.from(new Set(loans.map((loan) => loan.purpose).filter(Boolean))).sort();
  const sheetPreview = sheetLoanId
    ? loans.find((loan) => loan.loan_id === sheetLoanId) ?? data?.matches.find((match) => match.loan_id === sheetLoanId) ?? null
    : null;

  useEffect(() => {
    if (rule?.is_active) setFilters(smartInvestFiltersFromRule(rule));
  }, [rule]);

  const save = async (nextFilters: MkFilters) => {
    setError("");
    if (!hasSmartInvestCriteria(nextFilters)) {
      setError("Choose at least one condition before activating Smart Invest.");
      return;
    }
    if (isReadonlyImpersonationActive()) {
      setError("Smart Invest cannot be changed in a superadmin read-only view.");
      return;
    }
    try {
      const response = isFixturePreview
        ? previewSmartInvestResponse(nextFilters, loans, rule)
        : await updateMutation.mutateAsync({ data: smartInvestRequestFromFilters(nextFilters) });
      queryClient.setQueryData(getV1InvestorSmartInvestRetrieveQueryKey(), response);
      setFilters(nextFilters);
      setWizardOpen(false);
      setEditorOpen(false);
    } catch (saveError) {
      setError(apiErrorMessage(saveError));
    }
  };
  const deactivate = async () => {
    setError("");
    if (isReadonlyImpersonationActive()) {
      setError("Smart Invest cannot be changed in a superadmin read-only view.");
      return;
    }
    try {
      const response = isFixturePreview
        ? {
            rule: rule ? {
              ...rule,
              is_active: false,
              revision: rule.revision + 1,
              minimum_yield_bps: null,
              maximum_term_months: null,
              originator_scope: OriginatorScopeEnum.all,
              originator_id: null,
              collateral_scope: CollateralScopeEnum.all,
              collateral_type: "",
              currency_scope: CurrencyScopeEnum.all,
              risk_rating: "",
              purpose: "",
              loan_kind: LoanKindEnum.all,
              deactivated_at: new Date().toISOString(),
              updated_at: new Date().toISOString()
            } : null,
            match_count: 0,
            open_opportunity_count: loans.filter(isOpenMarketplaceLoan).length,
            matches: []
          } satisfies SmartInvestResponse
        : await deactivateMutation.mutateAsync();
      queryClient.setQueryData(getV1InvestorSmartInvestRetrieveQueryKey(), response);
      setFilters(mkDefaultFilters);
      setEditorOpen(false);
    } catch (deactivateError) {
      setError(apiErrorMessage(deactivateError));
    }
  };

  if (smartQuery.isError && !data) {
    return <ScreenError onRetry={() => void smartQuery.refetch()} title="Smart Invest">We could not load your Smart Invest rule.</ScreenError>;
  }
  if (!data) return <ScreenLoading title="Smart Invest" />;
  const saving = updateMutation.isPending || deactivateMutation.isPending;
  const update = <K extends keyof MkFilters>(key: K, value: MkFilters[K]) => setFilters((current) => ({ ...current, [key]: value }));

  return (
    <main className="content smart-invest-page">
      <section className="si-hero">
        <div className={`si-state ${active ? "active" : "inactive"}`}>{active ? "Active" : "Not active"}</div>
        <h1>It finds them. You approve them.</h1>
        <div className="si-hero-sub">
          <div>You decide the conditions.</div>
          <div>Nothing is ever committed without your explicit approval.</div>
        </div>
        {!active ? (
          <div className="si-entry">
            <button className="si-start" onClick={() => setWizardOpen(true)} type="button">
              <span className="si-start-main">
                <span className="si-pips"><i className="on" /><i /><i /><i /><i /></span>
                <span className="si-start-cap">Five questions · 2 min</span>
                <span className="si-start-title">Walk me through it</span>
                <span className="si-start-sub">first: what must be behind the loan</span>
              </span>
              <span className="si-start-rail">Start →</span>
            </button>
            <button className="si-manual" onClick={() => setEditorOpen(true)} type="button">
              <span className="si-manual-title">Set them myself<span style={{ flex: 1 }} /><span>↓</span></span>
              <span className="si-manual-sub">all conditions below, hand-set in any order</span>
            </button>
          </div>
        ) : (
          <div className="si-active-panel">
            <div className="si-active-main">
              <div className="si-active-cap"><span className="si-dot" />Active</div>
              <div className="si-active-text">The rule is watching for opportunities that meet these conditions. When a qualifying opportunity is published we notify you with the match ready to review — nothing is committed until you do.</div>
            </div>
            <div className="si-active-actions">
              <button className="si-pill-outline" onClick={() => setEditorOpen(true)} type="button">Adjust the rule</button>
              <button className="si-pill-dark" disabled={saving} onClick={() => void deactivate()} type="button">Deactivate the rule</button>
            </div>
          </div>
        )}
      </section>

      {active || editorOpen ? (
        <section className="si-conditions" id="rule-conditions">
          <button className="si-cond-toggle" onClick={() => setEditorOpen((open) => !open || !active)} type="button">
            <h2>See your rule</h2>
            <span className="si-cond-summary">{smartInvestRuleSummary(editorOpen ? filters : smartInvestFiltersFromRule(rule), originators).slice(0, 3).map((row) => row.value).join(" · ")}</span>
            <span style={{ flex: 1 }} />
            <span className={`si-cond-cta${editorOpen ? " on" : ""}`}>{editorOpen ? "Close" : "Open"} <span aria-hidden="true">{editorOpen ? "▴" : "▾"}</span></span>
          </button>
          {editorOpen ? (
            <>
              <p className="si-cond-intro">Change any of them and the count below moves with it, against the {loans.filter(isOpenMarketplaceLoan).length} opportunities actually open right now.</p>
              <div className="si-cond-grid">
                <div className="si-cond-card">
                  <div className="si-cond-cap">Only if it pays at least</div>
                  <div className="si-cond-val">{filters.minRate === null ? "any rate" : `${filters.minRate.toFixed(1)}%`}</div>
                  <input aria-label="Minimum Smart Invest yield" className="fs-range" max="25" min="0" onChange={(event) => update("minRate", Number(event.target.value) === 0 ? null : Number(event.target.value))} step="0.1" type="range" value={filters.minRate ?? 0} />
                  <div className="si-cond-ends"><span>0% — any</span><span>25%</span></div>
                  <div className="si-cond-note">A high floor means the rule will often find nothing — and a high rate is not a sign of a better borrower, frequently the opposite.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-cap">And runs no longer than</div>
                  <div className="si-cond-val">{filters.maxTerm === null ? "any term" : `${filters.maxTerm} mo`}</div>
                  <input aria-label="Maximum Smart Invest term" className="fs-range" max="120" min="6" onChange={(event) => update("maxTerm", Number(event.target.value) === 120 ? null : Number(event.target.value))} step="6" type="range" value={filters.maxTerm ?? 120} />
                  <div className="si-cond-ends"><span>6 mo</span><span>120 mo — any</span></div>
                  <div className="si-cond-note">The longer the term, the longer your capital is committed at today&apos;s rate rather than tomorrow&apos;s.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-head"><span className="si-cond-cap">An asset must be pledged</span><span className={`si-cond-mark${filters.col !== "all" ? " on" : ""}`}>{filters.col === "all" ? "Either" : "Set"}</span></div>
                  <div className="si-cond-pills">
                    <button className={filters.col === "secured" ? "on" : ""} onClick={() => update("col", "secured")} type="button">Required</button>
                    <button className={filters.col === "unsecured" ? "on" : ""} onClick={() => update("col", "unsecured")} type="button">Unsecured only</button>
                    <button className={filters.col === "all" ? "on" : ""} onClick={() => update("col", "all")} type="button">Either</button>
                  </div>
                  <div className="si-cond-note">Collateral can reduce loss severity, but it does not guarantee repayment or complete recovery.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-head"><span className="si-cond-cap">Which currency</span><span className={`si-cond-mark${filters.ccy !== "all" ? " on" : ""}`}>{filters.ccy === "all" ? "Both" : filters.ccy}</span></div>
                  <div className="si-cond-pills">
                    <button className={filters.ccy === "CHF" ? "on" : ""} onClick={() => update("ccy", "CHF")} type="button">CHF only</button>
                    <button className={filters.ccy === "EUR" ? "on" : ""} onClick={() => update("ccy", "EUR")} type="button">EUR only</button>
                    <button className={filters.ccy === "all" ? "on" : ""} onClick={() => update("ccy", "all")} type="button">CHF and EUR</button>
                  </div>
                  <div className="si-cond-note">The rule never converts funds and never combines CHF and EUR balances.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-cap si-cond-cap-gap">Originated by</div>
                  <div className="fs-chips">
                    <button className={`fs-chip${filters.orig === "all" ? " on" : ""}`} onClick={() => update("orig", "all")} type="button">Anyone</button>
                    <button className={`fs-chip${filters.orig === "banxum" ? " on" : ""}`} onClick={() => update("orig", "banxum")} type="button">Banxum</button>
                    {originators.map((originator) => (
                      <button className={`fs-chip${filters.orig === originator.id ? " on" : ""}`} key={originator.id} onClick={() => update("orig", originator.id)} type="button">{originator.name}</button>
                    ))}
                  </div>
                  <div className="si-cond-note">Direct loans are written by Banxum. Purchased claims come from a named originator that keeps a slice beside you.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-cap si-cond-cap-gap">Risk rating</div>
                  <div className="fs-chips">
                    <button className={`fs-chip${filters.rating === "all" ? " on" : ""}`} onClick={() => update("rating", "all")} type="button">Any</button>
                    {ratings.map((rating) => (
                      <button className={`fs-chip${filters.rating === rating ? " on" : ""}`} key={rating} onClick={() => update("rating", rating)} type="button">{rating}</button>
                    ))}
                  </div>
                  <div className="si-cond-note">The rating is arithmetic, not advice. The same facts sit on every loan&apos;s own page.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-cap si-cond-cap-gap">Purpose</div>
                  <div className="fs-chips">
                    <button className={`fs-chip${filters.purpose === "all" ? " on" : ""}`} onClick={() => update("purpose", "all")} type="button">Any</button>
                    {purposes.map((purpose) => (
                      <button className={`fs-chip${filters.purpose === purpose ? " on" : ""}`} key={purpose} onClick={() => update("purpose", purpose)} type="button">{humanizeToken(purpose)}</button>
                    ))}
                  </div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-head"><span className="si-cond-cap">Loan type</span><span className={`si-cond-mark${filters.kind !== "all" ? " on" : ""}`}>{filters.kind === "all" ? "Either" : "Set"}</span></div>
                  <div className="si-cond-pills">
                    <button className={filters.kind === "new" ? "on" : ""} onClick={() => update("kind", "new")} type="button">New lending</button>
                    <button className={filters.kind === "refi" ? "on" : ""} onClick={() => update("kind", "refi")} type="button">Refinancing</button>
                    <button className={filters.kind === "all" ? "on" : ""} onClick={() => update("kind", "all")} type="button">Either</button>
                  </div>
                </div>
              </div>
              <div className="si-tally">
                <div className="si-tally-cap">What that rule does with today&apos;s {loans.filter(isOpenMarketplaceLoan).length}</div>
                <div className="si-tally-row">
                  <span className="si-tally-n">{loans.filter(isOpenMarketplaceLoan).filter((loan) => mkMatches(loan, filters)).length}</span>
                  <span className="si-tally-of">of {loans.filter(isOpenMarketplaceLoan).length} qualify</span>
                  <span style={{ flex: 1 }} />
                  <button className="fs-clear-link" onClick={() => { setEditorOpen(false); setFilters(smartInvestFiltersFromRule(rule)); }} type="button">Cancel</button>
                  <button className="si-pill-dark" disabled={saving || !hasSmartInvestCriteria(filters)} onClick={() => void save(filters)} type="button">{saving ? "Saving..." : active ? "Save the rule" : "Activate the rule"}</button>
                </div>
                <div className="si-tally-note">Every opportunity meeting all your conditions. We alert you for each new match — nothing is committed until you review it.</div>
              </div>
            </>
          ) : null}
          {error ? <div className="smart-inline-error" role="alert">{error}</div> : null}
        </section>
      ) : null}

      {active ? (
        <section className="smart-invest-matches">
          <div className="smart-invest-section-title"><div><div className="eyebrow">Matched by your rule</div><h2>{data.match_count} open {data.match_count === 1 ? "opportunity" : "opportunities"}</h2></div><button onClick={() => goTo(setRoute, "market")} type="button">Open full marketplace</button></div>
          <SmartInvestMatchTable matches={data.matches} onOpen={(match) => setSheetLoanId(match.loan_id)} />
        </section>
      ) : null}

      <section className="smart-invest-limitations">
        <h2>What the rule will not do</h2>
        <div>
          <p><b>01</b><strong>It does not judge a borrower.</strong> A yield above your floor is not a sign of quality. The rule matches disclosed fields only.</p>
          <p><b>02</b><strong>It never invests for you.</strong> No balance is reserved and no order is placed until you review an opportunity and complete its normal confirmation flow.</p>
          <p><b>03</b><strong>It does not guarantee availability.</strong> A match can fill, close, change status or stop accepting investments before you act.</p>
          <p><b>04</b><strong>It does not combine currencies.</strong> CHF and EUR opportunities and balances remain separate, even when your rule accepts both.</p>
        </div>
      </section>
      {wizardOpen ? <SmartInvestWizard initialFilters={mkDefaultFilters} loans={loans} onClose={() => setWizardOpen(false)} onSave={save} saving={saving} /> : null}
      {sheetPreview ? (
        <MarketplaceLoanSheet
          onClose={() => setSheetLoanId(null)}
          onInvest={(detail, amount) => {
            setSheetLoanId(null);
            setInvestLoan(detail, amount);
          }}
          preview={sheetPreview}
          setRoute={setRoute}
        />
      ) : null}
    </main>
  );
}

function osProjection(amountMinor: number, yieldBps: number, termMonths: number, repaymentType: string) {
  const monthlyRate = yieldBps / 120_000;
  if (repaymentType === "equal_installments" && monthlyRate > 0) {
    const payment = (amountMinor * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -termMonths));
    const total = payment * termMonths;
    return { totalMinor: Math.round(total), interestMinor: Math.round(total - amountMinor), monthlyMinor: Math.round(payment) };
  }
  const interest = amountMinor * (yieldBps / 10_000) * (termMonths / 12);
  return { totalMinor: Math.round(amountMinor + interest), interestMinor: Math.round(interest), monthlyMinor: null };
}

function MarketplaceLoanSheet({
  preview,
  onClose,
  onInvest,
  setRoute
}: {
  preview: MarketplaceLoanPreview;
  onClose: () => void;
  onInvest: (loan: MarketplaceLoanDetail, amount: string) => void;
  setRoute: (route: AppRoute) => void;
}) {
  const detailQuery = useLoanDetailData(preview.loan_id);
  const balances = useBalancesData().data;
  const portfolio = usePortfolioData(true).data;
  const [stepOpen, setStepOpen] = useState(false);
  const [amountText, setAmountText] = useState<string | null>(null);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", listener);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", listener);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const detail = detailQuery.data ?? null;
  const loan = detail ?? preview;
  const ccy = loan.currency;
  const claim = isOriginatorClaimLoan(loan);
  const yieldBps = marketplaceYieldBps(loan);
  const openLoan = isOpenMarketplaceLoan(loan);
  const ltvBps = loan.ltv_bps;
  const collateralValueMinor = detail?.collateral_value_minor ?? 0;
  const hasAsset = collateralValueMinor > 0 && ltvBps !== null && ltvBps !== undefined;
  const penaltyBps = detail?.default_penalty_interest_bps ?? 0;
  const repaymentType = detail?.repayment_type ?? "equal_installments";
  const minimumBps = loan.minimum_subscription_bps ?? 5_000;
  const pct = loan.principal_minor > 0 ? Math.round((loan.committed_principal_minor / loan.principal_minor) * 100) : 0;
  const availableMinor = marketplaceAvailableMinor(loan);
  const todayMs = Date.now();
  const daysToClose = !claim && loan.funding_deadline
    ? Math.max(0, Math.ceil((new Date(`${loan.funding_deadline}T00:00:00`).getTime() - todayMs) / 86_400_000))
    : claim && typeof loan.remaining_term_days === "number"
      ? Math.max(0, loan.remaining_term_days - 30)
      : null;
  const investableMinor = sumLotAvailableMinor(currentInvestableLotsForLoanCurrency(balances?.lots, loan));
  const commitableMinor = Math.min(investableMinor, availableMinor);
  const minInvestMinor = loan.minimum_investment_minor;
  const parsed = amountText === null ? null : parseMoneyInputToMinorUnits(amountText, ccy);
  const amountMinor = amountText === null ? Math.max(Math.min(commitableMinor, availableMinor), 0) : (parsed?.amountMinor ?? 0);
  const amountValue = amountText ?? formatMoneyMinor(amountMinor, ccy);
  const overCash = amountMinor > commitableMinor;
  const underMin = amountMinor < minInvestMinor;
  const projection = osProjection(investableMinor > 0 ? investableMinor : minInvestMinor, yieldBps, loan.term_months, repaymentType);
  const walletBase = investableMinor > 0 ? investableMinor : minInvestMinor;
  const commitProjection = osProjection(amountMinor, yieldBps, loan.term_months, repaymentType);
  const bookMinor = (portfolio?.holdings ?? [])
    .filter((holding) => holding.currency === ccy)
    .reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const originLine = claim
    ? `originated by ${loan.originator_name ?? "a loan originator"}${detail?.loan_start_date ? ` · ${new Date(`${detail.loan_start_date}T00:00:00`).toLocaleDateString("en-GB", { month: "long", year: "numeric" })}` : ""}${(loan.skin_in_the_game_bps ?? 0) > 0 ? ` · kept ${formatRateBps(loan.skin_in_the_game_bps ?? 0)}` : ""}`
    : "originated by Banxum · written when this opportunity funds";
  const borrowerLabel = loan.borrower_display_name || loan.title;
  const chain = claim
    ? `Your claim is against ${borrowerLabel}. Banxum collects it and holds the charge — ${loan.originator_name ?? "the originator"} is not in that chain${(loan.skin_in_the_game_bps ?? 0) > 0 ? `, and it kept ${formatRateBps(loan.skin_in_the_game_bps ?? 0)} of this loan, so it loses alongside you` : ""}.`
    : `We underwrote this loan ourselves and we collect it. Your claim is against ${borrowerLabel}, and Banxum holds the charge over the collateral on your behalf.`;
  const metMinimum = loan.principal_minor > 0
    && loan.committed_principal_minor * 10_000 >= loan.principal_minor * minimumBps;
  const minPct = Math.round(minimumBps / 100);
  const goDetail = () => {
    onClose();
    goTo(setRoute, "loan", { loanId: loan.loan_id });
  };
  const reviewOrder = () => {
    if (!detail || underMin || amountMinor <= 0 || overCash) return;
    onInvest(detail, formatMoneyMinor(amountMinor, ccy).replace(/[^\d.]/g, ""));
  };
  const presets: { label: string; minor: number }[] = [
    { label: "Minimum", minor: minInvestMinor },
    { label: "Half", minor: Math.max(minInvestMinor, Math.floor(commitableMinor / 2)) },
    { label: "Maximum", minor: commitableMinor }
  ];

  return (
    <div className="ls-scrim">
      <button aria-label="Dismiss" className="ls-overlay-btn" onClick={onClose} tabIndex={-1} type="button" />
      <div aria-label={loan.title} aria-modal="true" className="ls-modal" role="dialog">
        <div className="ls-scroll" style={{ opacity: stepOpen ? 0.5 : 1 }}>
          <div className="os-head">
            <div className="os-head-main">
              <div className="os-name">{loan.title}</div>
              <div className="os-origin">{originLine}</div>
            </div>
            <div className="os-stats">
              <div className="os-stat"><div className="os-stat-val">{formatRateBps(yieldBps)}</div><div className="os-stat-cap">a year</div></div>
              <div className="os-stat"><div className="os-stat-val">{loan.term_months} mo</div><div className="os-stat-cap">{pfPaysLabel(repaymentType)}</div></div>
              <div className="os-stat"><div className="os-stat-val" style={hasAsset ? undefined : { color: "#C4312C" }}>{hasAsset ? formatRateBps(ltvBps ?? 0) : "none"}</div><div className="os-stat-cap">{hasAsset ? "of valuation" : "no asset"}</div></div>
              {daysToClose !== null ? (
                <div className="os-stat"><div className="os-stat-val" style={daysToClose <= 7 ? { color: "#C4312C" } : undefined}>{daysToClose} {daysToClose === 1 ? "day" : "days"}</div><div className="os-stat-cap">to close</div></div>
              ) : null}
            </div>
            <button aria-label="Close" className="ls-x" onClick={onClose} type="button">×</button>
          </div>

          <div className="os-body">
            <div className="os-grid2">
              <div className="os-card">
                <div className="os-cap">Use of funds</div>
                <div className="os-text">{detail?.purpose_description || humanizeToken(loan.purpose)}</div>
                {hasAsset ? (
                  <div className="os-kv"><span className="os-kv-lbl">Amount lent</span><span className="os-kv-dots" /><span className="os-kv-val">{pfMoneyLabel(ccy, loan.principal_minor)}</span></div>
                ) : null}
              </div>
              <div className="os-card">
                <div className="os-cap">Collateral</div>
                <div className="os-text os-text-gap">{detail?.collateral_description || humanizeToken(loan.collateral_type)}</div>
                {hasAsset ? (
                  <>
                    <div className="os-ltv-bar"><div style={{ width: `${Math.min(100, (ltvBps ?? 0) / 100)}%` }} /></div>
                    <div className="os-trio">
                      <div><div className="os-trio-val">{pfMoneyLabel(ccy, collateralValueMinor)}</div><div className="os-stat-cap">Valuation</div></div>
                      <div><div className="os-trio-val">{pfMoneyLabel(ccy, loan.principal_minor)}</div><div className="os-stat-cap">Lent against it</div></div>
                      <div><div className="os-trio-val">{formatRateBps(ltvBps ?? 0)}</div><div className="os-stat-cap">Margin</div></div>
                    </div>
                  </>
                ) : (
                  <div className="os-none">
                    <span className="os-none-word">None</span>
                    <span className="os-none-text">Nothing is pledged. If it stops paying there is no asset to sell — only a claim against the owner.</span>
                  </div>
                )}
              </div>
            </div>

            <div className="os-card">
              <div className="os-card-head"><span className="os-cap">What your {pfMoneyLabel(ccy, walletBase)} does here</span><span className="os-over">over {loan.term_months} months</span></div>
              <div className="os-wallet">
                <div className="os-wallet-col">
                  <div className="os-wallet-cap">Illustrative — if paid as scheduled</div>
                  <div className="os-wallet-val">{pfMoneyLabel(ccy, projection.totalMinor)}</div>
                  <div className="os-wallet-sub">{pfMoneyLabel(ccy, walletBase)} your capital returning + {pfMoneyLabel(ccy, projection.interestMinor)} interest{projection.monthlyMinor ? `, arriving as ${pfMoneyLabel(ccy, projection.monthlyMinor)} a month — not in one payment` : repaymentType === "bullet_periodic_interest" ? ", interest monthly and capital at maturity" : ", paid at maturity"}</div>
                </div>
                <div className="os-wallet-col last">
                  <div className="os-wallet-cap red">If it stops paying</div>
                  <div className="os-wallet-val">{penaltyBps > 0 ? `${formatRateBps(penaltyBps)} a year` : "—"}</div>
                  <div className="os-wallet-sub">{penaltyBps > 0 ? "penalty interest accrues to you on what is outstanding" : "no penalty interest is configured for this loan"}</div>
                </div>
              </div>
            </div>

            {!claim ? (
              <div className="os-card">
                <div className="os-card-head"><span className="os-cap">Subscription window</span><span className="os-over">{loan.funding_deadline ? `closes ${formatDate(loan.funding_deadline)}` : ""}</span></div>
                <div className="os-window">
                  <div className="os-window-fill" style={{ width: `${Math.min(100, pct)}%`, background: metMinimum ? "#1E6A4B" : "#151719" }} />
                  <div className="os-window-min" style={{ left: `${Math.min(100, minPct)}%` }} />
                  <div className="os-window-knob" style={{ left: `${Math.min(100, pct)}%`, borderColor: metMinimum ? "#1E6A4B" : "#151719" }} />
                </div>
                <div className="os-window-line"><span className="os-window-sub"><strong>{pct}%</strong> subscribed · {pfMoneyLabel(ccy, availableMinor)} available</span><span className="ls-spacer" /><span className="os-window-sub">minimum {minPct}%</span></div>
                {openLoan ? (
                  metMinimum ? (
                    <div className="os-strip met">
                      <span className="os-strip-lead">Minimum reached</span>
                      <span className="os-strip-text">At the deadline, BANXUM automatically closes the loan at the subscribed amount if settlement controls complete. If a technical or accounting control blocks close, the opportunity is paused and escalated while reservations remain unchanged.</span>
                    </div>
                  ) : (
                    <div className="os-strip short">
                      <span className="os-strip-lead">{Math.max(0, minPct - pct)} points to the minimum</span>
                      <span className="os-strip-text">Every opportunity starts here. If subscriptions are still below {minPct}% at the close, no loan is made and every franc returns to your account — you are not committed to a loan that stays undersubscribed.</span>
                    </div>
                  )
                ) : null}
              </div>
            ) : (
              <div className="os-card">
                <div className="os-cap os-cap-gap">Availability</div>
                <div className="os-window plain"><div className="os-window-fill" style={{ width: `${Math.min(100, pct)}%`, background: "#151719" }} /></div>
                <div className="os-window-line"><span className="os-window-sub"><strong>{pct}%</strong> taken by other investors · {pfMoneyLabel(ccy, availableMinor)} available</span></div>
              </div>
            )}

            <div className="os-card">
              <div className="os-cap">Who you are lending to</div>
              <div className="os-text">{chain}</div>
            </div>
          </div>
        </div>

        {!stepOpen ? (
          <div className="os-invest-bar">
            <div className="os-bar-col">
              <div className="os-wallet-cap">You can commit</div>
              <div className="os-bar-row"><span className="os-bar-val">{pfMoneyLabel(ccy, commitableMinor)}</span><span className="os-bar-sub">{pfMoneyLabel(ccy, investableMinor)} not lent</span></div>
            </div>
            <div className="os-bar-col split">
              <div className="os-wallet-cap green">You would earn</div>
              <div className="os-bar-row"><span className="os-bar-val green">≈ {pfMoneyLabel(ccy, osProjection(commitableMinor, yieldBps, loan.term_months, repaymentType).interestMinor)}</span><span className="os-bar-sub">interest, over {loan.term_months} months</span></div>
            </div>
            <span className="ls-spacer" />
            {!claim && detail ? (
              <button className="os-meet-btn" onClick={goDetail} type="button">Meet the borrower →</button>
            ) : claim && detail ? (
              <button className="os-meet-btn" onClick={goDetail} type="button">The full credit file →</button>
            ) : null}
            <button className="ls-sell-btn" disabled={!openLoan || !detail || commitableMinor <= 0} onClick={() => setStepOpen(true)} title={!openLoan ? "This opportunity is not open to new investment." : commitableMinor <= 0 ? "No investable balance is available in this currency." : undefined} type="button">Invest now</button>
          </div>
        ) : (
          <div className="os-step">
            <div className="os-step-head"><span className="os-cap">How much do you want to lend</span><span className="ls-spacer" /><span className="os-over">minimum {pfMoneyLabel(ccy, minInvestMinor)} · {pfMoneyLabel(ccy, availableMinor)} available in this opportunity</span></div>
            <div className="os-step-grid">
              <div className="os-step-amount">
                <div className="os-amt-box">
                  <span className="os-amt-ccy">{ccy === "EUR" ? "€" : ccy}</span>
                  <input aria-label="Amount to invest" className="os-amt-input" inputMode="decimal" onChange={(event) => setAmountText(event.target.value)} type="text" value={amountValue} />
                </div>
                <div className="os-chips">
                  {presets.map((preset) => (
                    <button className="os-chip" key={preset.label} onClick={() => setAmountText(formatMoneyMinor(preset.minor, ccy).replace(/[^\d.]/g, ""))} type="button">{preset.label}</button>
                  ))}
                </div>
                {overCash ? <div className="os-step-note">Only {pfMoneyLabel(ccy, investableMinor)} is not lent — today's maximum here.</div> : null}
                {underMin && amountMinor > 0 ? <div className="os-step-note">The minimum in any one loan is {pfMoneyLabel(ccy, minInvestMinor)}.</div> : null}
              </div>
              <div className="os-step-mid">
                <div className="os-kv"><span className="os-kv-lbl">Scheduled — to your account</span><span className="os-kv-dots" /><span className="os-kv-val">{pfMoneyLabel(ccy, commitProjection.totalMinor)}</span></div>
                <div className="os-kv"><span className="os-kv-lbl">Of which interest</span><span className="os-kv-dots" /><span className="os-kv-val">{pfMoneyLabel(ccy, commitProjection.interestMinor)}</span></div>
              </div>
              <div className="os-step-commit">
                <div className="os-wallet-cap">You commit</div>
                <div className="os-commit-val">{pfMoneyLabel(ccy, amountMinor)}</div>
                <div className="os-commit-sub">
                  {availableMinor > 0 ? `${((amountMinor / availableMinor) * 100).toFixed(1)}% of what is available here` : ""}
                  <br />
                  {bookMinor > 0 ? `${((amountMinor / (bookMinor + amountMinor)) * 100).toFixed(1)}% of everything you have lent` : "your first loan in this currency"}
                </div>
                <button className="os-confirm" disabled={underMin || overCash || amountMinor <= 0 || !detail} onClick={reviewOrder} type="button">Review Order</button>
                <button className="os-cancel" onClick={() => { setStepOpen(false); setAmountText(null); }} type="button">Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MarketplaceOpportunityList({
  loans,
  onOpen,
  asOf,
  viewMode,
  sortKey,
  sortDir,
  onPickSort
}: {
  loans: MarketplaceLoanPreview[];
  onOpen: (loan: MarketplaceLoanPreview) => void;
  asOf?: string;
  viewMode: "focused" | "detailed";
  sortKey: string | null;
  sortDir: "asc" | "desc";
  onPickSort: (key: string) => void;
}) {
  return (
    <div className={`marketplace-list ${viewMode}`}>
      <div className="marketplace-list-head">
        <FsTh activeKey={sortKey} dir={sortDir} label="Company" onPick={onPickSort} sortKey="name" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Yield" onPick={onPickSort} sortKey="rate" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Term" onPick={onPickSort} sortKey="term" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Collateral margin" onPick={onPickSort} sortKey="margin" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Available to invest" onPick={onPickSort} sortKey="available" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Availability" onPick={onPickSort} sortKey="closing" />
      </div>
      {loans.map((loan) => {
        const fundedPercent = fundingPercent(loan);
        const originatorClaim = isOriginatorClaimLoan(loan);
        const availableMinor = marketplaceAvailableMinor(loan);
        return (
          <article className="marketplace-opportunity" key={loan.loan_id} onClick={() => onOpen(loan)}>
            <button
              aria-label={`Open ${loan.title}`}
              className="marketplace-opportunity-hit"
              onClick={(event) => {
                event.stopPropagation();
                onOpen(loan);
              }}
              type="button"
            />
            <div className="marketplace-opportunity-main">
              <div className="marketplace-opportunity-name">
                <strong>{loan.title}</strong>
                <span>
                  {originatorClaim && loan.originator_name
                    ? `${loan.originator_name} · ${loan.purpose}`
                    : loan.purpose}
                </span>
                <div className="marketplace-opportunity-tags">
                  <Rating value={loan.risk_rating} />
                  <span className="tag">{loan.currency}</span>
                  {loan.is_refinancing ? <RefinancedTag /> : null}
                  {originatorClaim ? <span className="tag">Originator claim</span> : null}
                  <Chip status={loan.status} />
                  <span className="marketplace-copy-id" onClick={(event) => event.stopPropagation()}><CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" /></span>
                </div>
              </div>
              <div className="marketplace-opportunity-rate">
                <span className="marketplace-mobile-label">Yield</span>
                <strong>{formatRateBps(marketplaceYieldBps(loan))}</strong>
                <small>per annum</small>
              </div>
              <div className="marketplace-opportunity-term">
                <span className="marketplace-mobile-label">Term</span>
                <strong>{loan.term_months}</strong>
                <small>months</small>
              </div>
              <div className="marketplace-opportunity-collateral">
                <span className="marketplace-mobile-label">Collateral margin</span>
                <strong>{loan.ltv_bps === null ? "Not disclosed" : formatRateBps(loan.ltv_bps)}</strong>
                <small>{loan.ltv_bps === null ? "No LTV" : "of valuation"}</small>
              </div>
              <div className="marketplace-opportunity-funding">
                <span className="marketplace-mobile-label">Available to invest</span>
                <div className="marketplace-funding-value">
                  <strong>{loan.currency} {formatMoneyMinor(availableMinor, loan.currency)}</strong>
                  <span>{fundedPercent}% {originatorClaim ? "claim sold" : "funded"}</span>
                </div>
                <Progress percent={fundedPercent} />
                <small>{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)} of {formatMoneyMinor(loan.principal_minor, loan.currency)} principal</small>
              </div>
              <div className="marketplace-opportunity-deadline">
                <span className="marketplace-mobile-label">{originatorClaim ? "Maturity" : "Closes in"}</span>
                <strong>
                  {originatorClaim
                    ? loan.remaining_term_days === null
                      ? "See details"
                      : `${loan.remaining_term_days} days`
                    : loan.funding_deadline
                      ? fundingDeadlineLabel(loan.funding_deadline, asOf)
                      : "-"}
                </strong>
                <small>
                  {originatorClaim
                    ? loan.maturity_date
                      ? `Matures ${formatDate(loan.maturity_date)}`
                      : "Open while performing"
                    : loan.funding_deadline
                      ? formatDate(loan.funding_deadline)
                      : "No deadline"}
                </small>
                <Icon className="marketplace-row-arrow" name="chevR" size={16} />
              </div>
            </div>
            {viewMode === "detailed" ? (
              <div className="marketplace-opportunity-details">
                <div><span>{originatorClaim ? "Current claim principal" : "Loan amount"}</span><strong>{loan.currency} {formatMoneyMinor(loan.principal_minor, loan.currency)}</strong></div>
                <div><span>{originatorClaim ? "Claim principal sold" : "Allocated"}</span><strong>{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)}</strong></div>
                <div><span>Collateral / backing</span><strong>{formatEnumLabel(loan.collateral_type)}</strong></div>
                <div><span>Risk rating</span><strong>{loan.risk_rating}</strong></div>
                <div>
                  <span>{originatorClaim ? "Underlying borrower rate" : "Allocation"}</span>
                  <strong>{originatorClaim ? formatRateBps(loan.underlying_interest_rate_bps) : "First come, first served"}</strong>
                </div>
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function LoanDetailScreen({
  loanId,
  setRoute,
  demoState,
  setInvestLoan
}: {
  loanId: string;
  setRoute: (route: AppRoute) => void;
  demoState: DemoAccountState;
  setInvestLoan: (loan: MarketplaceLoanDetail) => void;
}) {
  const loanQuery = useLoanDetailData(loanId);
  const loan = loanQuery.data;
  const [tab, setTab] = useState<"overview" | "terms" | "docs" | "risk">("overview");
  if (loanQuery.isError && !loan) {
    return (
      <ScreenError title="Loan detail" onRetry={() => void loanQuery.refetch()}>
        We could not load this loan detail. Return to the marketplace or retry after the API is reachable.
      </ScreenError>
    );
  }
  if (!loan) return <ScreenLoading title="Loan detail" />;
  const blocked = demoState !== "active";
  const originatorClaim = isOriginatorClaimLoan(loan);
  const openForInvestment = isOpenMarketplaceLoan(loan);
  const availableMinor = marketplaceAvailableMinor(loan);

  return (
    <main className="content">
      <button className="backlink" onClick={() => goTo(setRoute, "market")} type="button"><Icon name="arrowL" size={14} /> Investment Opportunities</button>
      <div className="page-head">
        <div>
          <div className="row gap-8 wrap" style={{ marginBottom: 5 }}>
            <Chip status={loan.status} />
            <Rating value={loan.risk_rating} />
            <span className="tag">{loan.currency}</span>
            {loan.is_refinancing ? <RefinancedTag full /> : null}
            {originatorClaim ? <span className="tag">Originator claim</span> : null}
          </div>
          <h1>{loan.title}</h1>
          <div className="ph-sub"><CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" /></div>
        </div>
      </div>
      <div className="split loan-detail-layout">
        <div>
          <Card padded>
            <div className="grid grid-4" style={{ gap: 0 }}>
              <Stat amountMinor={loan.principal_minor} currency={loan.currency} label={originatorClaim ? "Current principal" : "Amount"} />
              <Stat label="Yield" raw={formatRateBps(marketplaceYieldBps(loan))} sub="effective annual · ACT/365" />
              <Stat label="Term" raw={loan.remaining_term_days === null ? `${loan.term_months} mo` : `${loan.remaining_term_days} days`} sub={loan.repayment_type} />
              <Stat label={originatorClaim ? "Claim sold" : "Funded"} raw={`${fundingPercent(loan)}%`} sub={`${loan.currency} ${formatMoneyMinor(loan.committed_principal_minor, loan.currency)}`} />
            </div>
            <div style={{ marginTop: 14 }}>
              <Progress percent={fundingPercent(loan)} />
              <div className="row spread muted" style={{ fontSize: 12, marginTop: 6 }}>
                <span>{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)} {originatorClaim ? "claim principal sold" : "allocated"}</span>
                <span>
                  {originatorClaim
                    ? loan.maturity_date
                      ? `Matures ${formatDate(loan.maturity_date)}`
                      : "Maturity unavailable"
                    : loan.funding_deadline
                      ? `Closes ${formatDate(loan.funding_deadline)}`
                      : "No funding deadline"}
                </span>
              </div>
            </div>
          </Card>
          <div style={{ marginTop: 16 }}>
            <Tabs
              tabs={[
                { value: "overview", label: "Overview" },
                { value: "terms", label: "Terms & collateral" },
                { value: "docs", label: "Documents" },
                { value: "risk", label: "Risk" }
              ]}
              value={tab}
              onChange={setTab}
            />
          </div>
          <div style={{ paddingTop: 16 }}>
            {tab === "overview" ? <LoanOverview loan={loan} /> : null}
            {tab === "terms" ? <LoanTerms loan={loan} /> : null}
            {tab === "docs" ? <LoanDocuments loan={loan} /> : null}
            {tab === "risk" ? <RiskDisclosure /> : null}
          </div>
        </div>
        <aside className="aside-sticky">
          <Card padded>
            {!openForInvestment ? (
              <Empty icon="checkCircle" title="Not open for investment">
                {originatorClaim
                  ? "This originator claim is sold, on hold, repaid, late, defaulted, or within 30 days of maturity."
                  : "This loan is closed to new orders."}
              </Empty>
            ) : (
              <>
                <div className="eyebrow" style={{ marginBottom: 8 }}>{originatorClaim ? "Buy this loan claim" : "Invest in this loan"}</div>
                {originatorClaim && loan.originator_name ? <KeyValue label="Loan originator" value={loan.originator_name} /> : null}
                {originatorClaim && (loan.skin_in_the_game_bps ?? 0) > 0 ? <KeyValue label="Skin in the game" value={`${formatRateBps(loan.skin_in_the_game_bps ?? 0)} kept by the originator`} /> : null}
                <KeyValue label="Yield" value={`${formatRateBps(marketplaceYieldBps(loan))} p.a.`} />
                {originatorClaim ? <KeyValue label="Borrower coupon" value={`${formatRateBps(loan.underlying_interest_rate_bps)} p.a.`} /> : null}
                <KeyValue label="Minimum investment" value={`${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)}`} />
                <KeyValue label="Available now" value={`${loan.currency} ${formatMoneyMinor(availableMinor, loan.currency)}`} />
                <KeyValue
                  label={originatorClaim ? "Maturity" : "Closes"}
                  value={originatorClaim
                    ? loan.maturity_date ? formatDate(loan.maturity_date) : "Not available"
                    : loan.funding_deadline ? formatDate(loan.funding_deadline) : "Not available"}
                />
                {blocked || isReadonlyImpersonationActive() ? (
                  <Banner tone={demoState === "frozen" ? "bad" : "warn"} title={demoState === "frozen" ? "Financial actions frozen" : "Investing not yet available"}>
                    {isReadonlyImpersonationActive()
                      ? "Read-only impersonation cannot place orders."
                      : demoState === "frozen"
                        ? "Provide a usable payout IBAN to unlock investing."
                        : "Complete KYC verification to unlock investing."}
                  </Banner>
                ) : (
                  <Button block icon="trend" variant="primary" onClick={() => setInvestLoan(loan)}>
                    {originatorClaim ? "Review claim purchase" : "Place investment order"}
                  </Button>
                )}
                <p className="muted" style={{ fontSize: 11, lineHeight: 1.5, marginTop: 10 }}>
                  {originatorClaim
                    ? "BANXUM generates an executable quote from the remaining borrower cash flows. A confirmed purchase assigns the legal claim immediately."
                    : "Orders are intents and do not reserve capacity until funds are allocated and validated."}
                </p>
              </>
            )}
          </Card>
        </aside>
      </div>
    </main>
  );
}

type BorrowerDisclosureDocument = {
  id?: string;
  document_type?: string;
  display_name?: string;
  description?: string;
};

type BorrowerDisclosure = {
  legal_name?: string;
  year_founded?: number;
  business_classification?: string;
  registered_address?: string;
  contact_info?: string;
  country?: string;
  financials_currency?: string;
  assets_minor?: number;
  liabilities_minor?: number;
  revenue_last_year_minor?: number;
  profit_last_year_minor?: number;
  documents?: BorrowerDisclosureDocument[];
};

function borrowerDisclosureForLoan(loan: MarketplaceLoanDetail): BorrowerDisclosure {
  const raw = (loan as MarketplaceLoanDetail & { borrower_disclosure?: unknown }).borrower_disclosure;
  return raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as BorrowerDisclosure) : {};
}

function disclosureMoney(value: number | undefined, currency: string | undefined) {
  if (value === undefined || currency === undefined || currency === "") return undefined;
  return `${currency} ${formatMoneyMinor(value, currency)}`;
}

function LoanOverview({ loan }: { loan: MarketplaceLoanDetail }) {
  const borrowerDisclosure = borrowerDisclosureForLoan(loan);
  const borrowerName = borrowerDisclosure.legal_name || loan.title;
  const financialsCurrency = borrowerDisclosure.financials_currency || loan.currency;
  const borrowerRows: Array<[string, ReactNode, boolean?]> = [
    ["Legal business name", borrowerName],
    ["Business classification", borrowerDisclosure.business_classification],
    ["Country", borrowerDisclosure.country],
    ["Year founded", borrowerDisclosure.year_founded],
    ["Registered address", borrowerDisclosure.registered_address],
    ["Contact info", borrowerDisclosure.contact_info],
    ["Assets", disclosureMoney(borrowerDisclosure.assets_minor, financialsCurrency), true],
    ["Liabilities", disclosureMoney(borrowerDisclosure.liabilities_minor, financialsCurrency), true],
    ["Revenue last year", disclosureMoney(borrowerDisclosure.revenue_last_year_minor, financialsCurrency), true],
    ["Profit last year", disclosureMoney(borrowerDisclosure.profit_last_year_minor, financialsCurrency), true]
  ];

  return (
    <>
    <Card padded>
      <div className="eyebrow" style={{ marginBottom: 6 }}>Purpose</div>
      <p className="muted-2" style={{ lineHeight: 1.6, maxWidth: 680 }}>{loan.purpose_description}</p>
      <div className="hr" style={{ margin: "16px 0" }} />
      <div className="eyebrow" style={{ marginBottom: 6 }}>Borrower disclosure</div>
      <dl className="kv">
        {borrowerRows.map(([label, value, mono]) =>
          value !== undefined && value !== "" ? (
            <KeyValueRow key={label} label={label} mono={mono} value={value} />
          ) : null
        )}
      </dl>
      <p className="muted" style={{ fontSize: 11.5, lineHeight: 1.5, marginTop: 10 }}>
        Borrower optional fields are shown only when Garanta has marked the field public for this borrower.
      </p>
      <div className="hr" style={{ margin: "16px 0" }} />
      <dl className="kv">
        <KeyValueRow label="Loan reference" value={<CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" />} />
        <KeyValueRow label="Borrower" value={borrowerName} />
        {isOriginatorClaimLoan(loan) && loan.originator_name ? <KeyValueRow label="Loan originator" value={loan.originator_name} /> : null}
        {isOriginatorClaimLoan(loan) && (loan.skin_in_the_game_bps ?? 0) > 0 ? <KeyValueRow label="Skin in the game" value={`${formatRateBps(loan.skin_in_the_game_bps ?? 0)} of the outstanding principal stays with the originator`} /> : null}
        <KeyValueRow label="Currency" value={loan.currency} />
        <KeyValueRow label="Repayment type" value={loan.repayment_type} />
        <KeyValueRow label="Risk rating" value={loan.risk_rating} />
        <KeyValueRow label="Collateral type" value={loan.collateral_type} />
        {loan.ltv_bps !== null ? <KeyValueRow label="Loan-to-value" value={`${(loan.ltv_bps / 100).toFixed(1)}%`} /> : null}
      </dl>
    </Card>
    {isOriginatorClaimLoan(loan) ? <OriginatorClaimLoanSection loan={loan} /> : null}
    {loan.is_refinancing ? <OriginalLoanSection loan={loan} /> : null}
    </>
  );
}

function OriginatorClaimLoanSection({ loan }: { loan: MarketplaceLoanDetail }) {
  const schedule = loan.originator_schedule ?? [];
  const payments = loan.originator_payment_history ?? [];
  const scheduleTotals = schedule.reduce(
    (total, row) => ({
      principal: total.principal + row.principal_minor,
      interest: total.interest + row.interest_minor,
      penalty: total.penalty + row.penalty_minor,
      fee: total.fee + row.fee_minor,
      amount: total.amount + row.total_minor
    }),
    { principal: 0, interest: 0, penalty: 0, fee: 0, amount: 0 }
  );
  const paymentTotals = payments.reduce(
    (total, row) => ({
      principal: total.principal + row.principal_minor,
      interest: total.interest + row.interest_minor,
      penalty: total.penalty + row.penalty_minor,
      fee: total.fee + row.fee_minor,
      amount: total.amount + row.total_minor
    }),
    { principal: 0, interest: 0, penalty: 0, fee: 0, amount: 0 }
  );

  return (
    <Card className="section" padded>
      <div className="row gap-8 wrap" style={{ marginBottom: 6 }}>
        <div className="eyebrow">Loan-originator evidence</div>
        <span className="tag">Revision {loan.schedule_revision ?? loan.schedule_version}</span>
      </div>
      <p className="muted" style={{ fontSize: 12, lineHeight: 1.5, maxWidth: 760 }}>
        The loan originator owns the unsold claim. Your purchase assigns part of the final-borrower
        claim immediately. The yield shown by BANXUM is the effective annual ACT/365 yield priced from
        the remaining cash flows; it is distinct from the borrower coupon.
      </p>
      <dl className="kv" style={{ marginTop: 10 }}>
        <KeyValueRow label="Target investor yield" mono value={`${formatRateBps(loan.yield_bps)} p.a.`} />
        <KeyValueRow label="Underlying borrower coupon" mono value={`${formatRateBps(loan.underlying_interest_rate_bps)} p.a.`} />
        <KeyValueRow label="Current outstanding principal" mono value={`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency)}`} />
        <KeyValueRow label="Available claim principal" mono value={`${loan.currency} ${formatMoneyMinor(loan.remaining_capacity_minor, loan.currency)}`} />
        {loan.maturity_date ? <KeyValueRow label="Maturity" value={formatDate(loan.maturity_date)} /> : null}
        {loan.pricing_as_of_date ? <KeyValueRow label="Pricing data as of" value={formatDate(loan.pricing_as_of_date)} /> : null}
      </dl>
      {schedule.length > 0 ? (
        <>
          <div className="eyebrow" style={{ margin: "16px 0 8px" }}>Current full loan schedule</div>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th className="num">#</th><th>Accrual starts</th><th>Due</th><th className="num">Opening principal</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Penalty</th><th className="num">Total</th><th className="num">Outstanding after</th></tr></thead>
              <tbody>
                {schedule.map((row) => (
                  <tr key={`${row.installment_number}-${row.due_date}`}>
                    <td className="num muted">{row.installment_number}</td>
                    <td>{formatDate(row.accrual_start_date)}</td>
                    <td>{formatDate(row.due_date)}</td>
                    <td className="num">{formatMoneyMinor(row.opening_principal_minor, loan.currency)}</td>
                    <td className="num">{formatMoneyMinor(row.principal_minor, loan.currency)}</td>
                    <td className="num">{formatMoneyMinor(row.interest_minor, loan.currency)}</td>
                    <td className="num">{formatMoneyMinor(row.penalty_minor, loan.currency)}</td>
                    <td className="num col-strong">{formatMoneyMinor(row.total_minor, loan.currency)}</td>
                    <td className="num">{formatMoneyMinor(row.outstanding_after_minor, loan.currency)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="schedule-totals"><tr><th colSpan={4}>Totals</th><th className="num">{formatMoneyMinor(scheduleTotals.principal, loan.currency)}</th><th className="num">{formatMoneyMinor(scheduleTotals.interest, loan.currency)}</th><th className="num">{formatMoneyMinor(scheduleTotals.penalty, loan.currency)}</th><th className="num">{formatMoneyMinor(scheduleTotals.amount, loan.currency)}</th><th className="num">-</th></tr></tfoot>
            </table>
          </div>
        </>
      ) : null}
      {payments.length > 0 ? (
        <>
          <div className="eyebrow" style={{ margin: "16px 0 8px" }}>Historical borrower payments</div>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>Value date</th><th>Type</th><th>Reference</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Penalty</th><th className="num">Total</th><th className="num">Principal after</th></tr></thead>
              <tbody>
                {payments.map((row) => (
                  <tr key={`${row.reference}-${row.value_date}`}>
                    <td>{formatDate(row.value_date)}</td><td>{formatEnumLabel(row.payment_type)}</td><td className="mono">{row.reference}</td><td className="num">{formatMoneyMinor(row.principal_minor, loan.currency)}</td><td className="num">{formatMoneyMinor(row.interest_minor, loan.currency)}</td><td className="num">{formatMoneyMinor(row.penalty_minor, loan.currency)}</td><td className="num col-strong">{formatMoneyMinor(row.total_minor, loan.currency)}</td><td className="num">{formatMoneyMinor(row.resulting_principal_minor, loan.currency)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="schedule-totals"><tr><th colSpan={3}>Totals</th><th className="num">{formatMoneyMinor(paymentTotals.principal, loan.currency)}</th><th className="num">{formatMoneyMinor(paymentTotals.interest, loan.currency)}</th><th className="num">{formatMoneyMinor(paymentTotals.penalty, loan.currency)}</th><th className="num">{formatMoneyMinor(paymentTotals.amount, loan.currency)}</th><th className="num">-</th></tr></tfoot>
            </table>
          </div>
        </>
      ) : null}
    </Card>
  );
}

function OriginalLoanSection({ loan }: { loan: MarketplaceLoanDetail }) {
  const schedule = loan.original_loan_schedule ?? [];
  const totals = schedule.reduce(
    (acc, row) => {
      acc.principal += row.principal_minor;
      acc.interest += row.interest_minor;
      acc.total += row.total_minor;
      if (row.paid_before_publication) acc.paid += 1;
      return acc;
    },
    { principal: 0, interest: 0, total: 0, paid: 0 }
  );
  return (
    <Card className="section" padded>
      <div className="row gap-8 wrap" style={{ marginBottom: 6 }}>
        <div className="eyebrow">Original loan</div>
        <RefinancedTag full />
      </div>
      <p className="muted" style={{ fontSize: 12, lineHeight: 1.5, maxWidth: 680 }}>
        This loan refinances an existing loan of the borrower. The original loan data and repayment
        schedule below are informational only and show the loan being refinanced; investors fund the
        new loan whose terms are shown above.
      </p>
      <dl className="kv" style={{ marginTop: 10 }}>
        <KeyValueRow label="Original principal" mono value={`${loan.currency} ${formatMoneyMinor(loan.original_principal_minor, loan.currency)}`} />
        {loan.original_interest_rate_bps !== null ? <KeyValueRow label="Original interest rate" mono value={`${formatRateBps(loan.original_interest_rate_bps)} p.a.`} /> : null}
        {loan.original_term_months !== null ? <KeyValueRow label="Original term" value={`${loan.original_term_months} mo`} /> : null}
        {loan.original_repayment_type ? <KeyValueRow label="Original repayment type" value={formatEnumLabel(loan.original_repayment_type)} /> : null}
        {loan.original_interest_only_months ? <KeyValueRow label="Original interest-only period" value={`${loan.original_interest_only_months} mo`} /> : null}
        {loan.original_loan_start_date ? <KeyValueRow label="Original loan start date" value={formatDate(loan.original_loan_start_date)} /> : null}
      </dl>
      {schedule.length > 0 ? (
        <>
          <div className="eyebrow" style={{ margin: "16px 0 8px" }}>Original loan repayment schedule</div>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>Due date</th>
                  <th className="num">Principal</th>
                  <th className="num">Interest</th>
                  <th className="num">Total</th>
                  <th className="num">Outstanding after</th>
                  <th>Paid</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((row) => (
                  <tr key={row.installment_number}>
                    <td className="num muted">{row.installment_number}</td>
                    <td>{formatDate(row.due_date)}</td>
                    <td className="num">{formatMoneyMinor(row.principal_minor, loan.currency)}</td>
                    <td className="num">{formatMoneyMinor(row.interest_minor, loan.currency)}</td>
                    <td className="num col-strong">{formatMoneyMinor(row.total_minor, loan.currency)}</td>
                    <td className="num">{formatMoneyMinor(row.outstanding_after_minor, loan.currency)}</td>
                    <td>{row.paid_before_publication ? <Chip dot={false} tone="ok">Paid</Chip> : <span className="muted">-</span>}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="schedule-totals">
                <tr>
                  <th colSpan={2}>Totals</th>
                  <th className="num">{formatMoneyMinor(totals.principal, loan.currency)}</th>
                  <th className="num">{formatMoneyMinor(totals.interest, loan.currency)}</th>
                  <th className="num">{formatMoneyMinor(totals.total, loan.currency)}</th>
                  <th className="num">-</th>
                  <th>{totals.paid} paid</th>
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="muted" style={{ fontSize: 11.5, lineHeight: 1.5, marginTop: 10 }}>
            Installments marked Paid were settled by the borrower before this loan was published. The
            financed amount can be lower than the remaining outstanding of the original schedule.
          </p>
        </>
      ) : null}
    </Card>
  );
}

function LoanTerms({ loan }: { loan: MarketplaceLoanDetail }) {
  const originatorClaim = isOriginatorClaimLoan(loan);
  return (
    <Card padded>
      <dl className="kv">
        {originatorClaim && loan.originator_name ? <KeyValueRow label="Loan originator" value={loan.originator_name} /> : null}
        {originatorClaim && (loan.skin_in_the_game_bps ?? 0) > 0 ? <KeyValueRow label="Skin in the game" mono value={`${formatRateBps(loan.skin_in_the_game_bps ?? 0)} kept by the originator`} /> : null}
        <KeyValueRow label="Investor yield" mono value={`${formatRateBps(marketplaceYieldBps(loan))} p.a.`} />
        {originatorClaim ? <KeyValueRow label="Underlying borrower coupon" mono value={`${formatRateBps(loan.underlying_interest_rate_bps)} p.a.`} /> : null}
        <KeyValueRow label="Repayment type" value={loan.repayment_type} />
        <KeyValueRow label="Collateral / backing" value={loan.collateral_description} />
        {loan.collateral_value_minor > 0 ? <KeyValueRow label="Collateral value" mono value={`${loan.currency} ${formatMoneyMinor(loan.collateral_value_minor, loan.currency)}`} /> : null}
        {loan.ltv_bps !== null ? <KeyValueRow label="LTV" mono value={`${(loan.ltv_bps / 100).toFixed(1)}%`} /> : null}
        <KeyValueRow label="Primary investor fee" value="None" />
      </dl>
      {loan.ltv_bps === null ? <Banner tone="warn" title="No LTV shown">Collateral value is zero or not applicable. The platform does not show LTV for this loan.</Banner> : null}
    </Card>
  );
}

function LoanDocuments({ loan }: { loan: MarketplaceLoanDetail }) {
  const documents = borrowerDisclosureForLoan(loan).documents ?? [];
  if (documents.length === 0) {
    return (
      <Card>
        <Empty icon="doc" title="No borrower documents available">
          Investor-visible borrower documents appear here after Garanta links a clean-scanned borrower file to the loan borrower.
        </Empty>
      </Card>
    );
  }

  return (
    <Card>
      {documents.map((document, index) => (
        <div
          className="row spread"
          key={document.id ?? `${document.display_name}-${index}`}
          style={{ alignItems: "flex-start", borderBottom: index < documents.length - 1 ? "1px solid var(--line)" : 0, gap: 16, padding: "12px 16px" }}
        >
          <span className="row gap-8" style={{ alignItems: "flex-start" }}>
            <Icon className="muted" name="doc" size={16} />
            <span className="col gap-4">
              <strong>{document.display_name || "Borrower document"}</strong>
              {document.description ? <span className="muted" style={{ fontSize: 12 }}>{document.description}</span> : null}
              {document.document_type ? <span className="tag">{humanizeToken(document.document_type)}</span> : null}
            </span>
          </span>
          {document.id ? <CopyIdButton ariaLabel="Copy document ID" id={document.id} label="Copy document ID" /> : null}
        </div>
      ))}
    </Card>
  );
}

function RiskDisclosure() {
  return (
    <Card padded>
      <div className="col gap-8">
        {[
          "Loss of some or all invested capital",
          "Borrower default and delayed repayment",
          "Collateral valuation and enforcement risk",
          "Illiquidity - secondary-market exit may be unavailable or discounted",
          "No guaranteed return and no deposit protection"
        ].map((item) => (
          <div className="row gap-8" key={item} style={{ alignItems: "flex-start", fontSize: 13 }}>
            <Icon name="alert" size={15} />
            <span className="muted-2">{item}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function LoansTable({ loans, onOpen, preview = false }: { loans: MarketplaceLoanPreview[]; onOpen: (loan: MarketplaceLoanPreview) => void; preview?: boolean }) {
  if (loans.length === 0) {
    return (
      <div className="portal-table-empty">
        <Empty icon="market" title={preview ? "No loan previews available" : "No loans available"}>
          {preview
            ? "There are no published loan previews right now. Check again later or register to receive marketplace updates."
            : "There are no loans in this view right now."}
        </Empty>
      </div>
    );
  }

  return (
    <div className="portal-data-surface">
      <div className="tbl-wrap">
        <table className={`tbl portal-data-table loans-data-table ${preview ? "preview" : ""}`}>
          <thead>
            <tr>
              <th>Borrower</th>
              <th>Purpose</th>
              <th className="num">Amount</th>
              <th className="num">Yield</th>
              <th className="num">Term</th>
              {!preview ? <th>Rating</th> : null}
              {!preview ? <th className="num">Funded</th> : null}
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loans.map((loan) => (
              <tr className="clickable" key={loan.loan_id} onClick={() => onOpen(loan)}>
                <td>
                  <EntityReference
                    id={loan.loan_id}
                    idLabel="Copy loan ID"
                    title={loan.is_refinancing ? <span className="row gap-6 wrap">{loan.title}<RefinancedTag /></span> : loan.title}
                  />
                </td>
                <td>{loan.purpose}</td>
                <td className="num"><Money amountMinor={loan.principal_minor} currency={loan.currency} /></td>
                <td className="num col-strong">{formatRateBps(marketplaceYieldBps(loan))}</td>
                <td className="num">{loan.term_months} mo</td>
                {!preview ? <td><Rating value={loan.risk_rating} /></td> : null}
                {!preview ? <td className="num">{fundingPercent(loan)}%</td> : null}
                <td><Chip status={loan.status} /></td>
                <td className="right"><Icon className="faint" name="chevR" size={15} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BalancesScreen({ demoState }: { demoState: DemoAccountState }) {
  const balancesQuery = useBalancesData();
  const balances = balancesQuery.data;
  const [currency, setCurrency] = useState<"CHF" | "EUR">("CHF");
  const [modal, setModal] = useState<"deposit" | "withdraw" | "iban" | null>(null);
  if (balancesQuery.isError && !balances) {
    return (
      <ScreenError title="Balances" onRetry={() => void balancesQuery.refetch()}>
        We could not load balance lots and payout instructions. Retry once the API connection is restored.
      </ScreenError>
    );
  }
  if (!balances) return <ScreenLoading title="Balances" />;

  const summary = balances.summaries.find((item) => item.currency === currency) ?? balances.summaries[0];
  const lots = balances.lots.filter((lot) => lot.currency === currency);
  const frozen = demoState === "frozen";
  if (!summary) {
    return (
      <main className="content">
        <div className="page-head"><div><h1>Balances</h1><div className="ph-sub">Funds are non-interest-bearing and subject to 30/60-day regulatory ageing rules.</div></div></div>
        <Card><Empty icon="balance" title="No balances yet">Deposits, repayments, recoveries, FX proceeds, and sale proceeds will appear here after reconciliation.</Empty></Card>
      </main>
    );
  }

  return (
    <main className="content">
      <div className="page-head">
        <div>
          <h1>Balances</h1>
          <div className="ph-sub">Funds are non-interest-bearing and subject to 30/60-day regulatory ageing rules.</div>
        </div>
        <Segmented options={[{ value: "CHF", label: "CHF" }, { value: "EUR", label: "EUR" }]} value={currency} onChange={setCurrency} />
      </div>
      {frozen ? <div style={{ marginBottom: 18 }}><FrozenBanner setRoute={() => setModal("iban")} /></div> : null}
      {isReadonlyImpersonationActive() ? (
        <div style={{ marginBottom: 18 }}>
          <Banner icon="lock" tone="info" title="Read-only view">
            Deposits, withdrawals and payout-IBAN changes are disabled during superadmin read-only impersonation.
          </Banner>
        </div>
      ) : null}
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <BucketTile label="Investable" value={summary.investable_minor} currency={currency} tone="ok" sub="Within 30-day window" />
        <BucketTile label="Withdraw-only" value={summary.withdraw_only_minor} currency={currency} tone="warn" sub="Investment window closed" />
        <BucketTile label="Overdue" value={summary.overdue_minor} currency={currency} tone="warn" sub="Withdraw before day 60" />
        <BucketTile label="Penalty/frozen" value={frozen ? summary.overdue_minor : summary.penalty_mode_minor + summary.frozen_minor} currency={currency} tone={frozen ? "bad" : "neutral"} sub={frozen ? "IBAN required" : "None"} />
      </div>
      <div className="row gap-8 wrap" style={{ marginBottom: 20 }}>
        <Button className="btn-green" disabled={frozen || isReadonlyImpersonationActive()} icon="plus" variant="primary" onClick={() => setModal("deposit")}>Add Funds</Button>
        <Button disabled={isReadonlyImpersonationActive()} icon="download" onClick={() => setModal("withdraw")}>Withdraw</Button>
        <Button disabled={isReadonlyImpersonationActive()} icon="balance" variant="ghost" onClick={() => setModal("iban")}>Payout IBANs</Button>
      </div>
      <Card className="banner-neutral" padded>
        <div className="row gap-12" style={{ alignItems: "flex-start" }}>
          <Icon name="info" size={18} />
          <p className="muted-2" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
            Every incoming amount is a lot with its own clock. You have 30 days to invest/reinvest
            a lot and 60 days to withdraw it. Lots are consumed oldest-first. FX conversion does not
            reset the clock; converted funds inherit the source lot deadlines.
          </p>
        </div>
      </Card>
      <section className="section">
        <div className="section-head"><h2>{currency} balance lots</h2><span className="muted" style={{ fontSize: 12 }}>{lots.length} lots - FIFO consumption</span></div>
        <BalanceLotsTable lots={lots} frozen={frozen} />
      </section>
      <section className="grid grid-2 section">
        <Card padded>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Payout IBANs</div>
          {balances.payout_instructions.map((instruction) => (
            <div className="row spread" key={instruction.id} style={{ borderBottom: "1px solid var(--line)", padding: "10px 0" }}>
              <div><div className="col-strong">{instruction.destination_account_name}</div><div className="mono muted" style={{ fontSize: 12 }}>{instruction.destination_iban}</div></div>
              <div className="row gap-8"><span className="tag">{instruction.currency}</span><Chip status="verified" /></div>
            </div>
          ))}
          <Button icon="plus" size="sm" style={{ marginTop: 12 }} variant="ghost" onClick={() => setModal("iban")}>Add or update IBAN</Button>
        </Card>
        <Card><Empty icon="clock" title="No pending withdrawals">Withdrawal requests in progress will appear here.</Empty></Card>
      </section>
      {modal === "deposit" ? <DepositModal currency={currency} onClose={() => setModal(null)} /> : null}
      {modal === "withdraw" ? <WithdrawModal currency={currency} maxMinor={summary.total_available_minor - summary.penalty_mode_minor} payoutInstructions={balances.payout_instructions.filter((instruction) => instruction.currency === currency)} onClose={() => setModal(null)} /> : null}
      {modal === "iban" ? <PayoutIbanModal onClose={() => setModal(null)} /> : null}
    </main>
  );
}

function BucketTile({ label, value, currency, tone, sub }: { label: string; value: number; currency: string; tone: "ok" | "warn" | "bad" | "neutral"; sub: string }) {
  return (
    <Card padded>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ fontSize: 19 }}><span className="ccy">{currency}</span>{formatMoneyMinor(value, currency)}</div>
      <div className={`stat-sub ${tone === "bad" ? "neg" : ""}`}>{sub}</div>
    </Card>
  );
}

function BalanceLotsTable({ lots, frozen }: { lots: BalanceLot[]; frozen: boolean }) {
  if (lots.length === 0) {
    return <div className="portal-table-empty"><Empty icon="balance" title="No balance lots">Incoming deposits, repayments, recoveries, FX proceeds, or sale proceeds will appear here.</Empty></div>;
  }

  return (
    <div className="portal-data-surface">
      <div className="tbl-wrap">
        <table className="tbl portal-data-table balance-lots-table">
          <thead><tr><th>Lot</th><th>Source</th><th>Received</th><th className="num">Remaining</th><th>Age/deadline</th><th>Status</th></tr></thead>
          <tbody>
            {lots.map((lot) => {
              const penalty = frozen && lot.bucket === "overdue";
              return (
                <tr className={penalty ? "lot-penalty" : lot.bucket === "overdue" ? "lot-overdue" : ""} key={lot.id}>
                  <td><CopyIdButton ariaLabel="Copy lot ID" id={lot.id} label="Copy lot ID" /></td>
                  <td><div>{sourceLabel(lot.source_type)}</div>{lot.source_type === "fx_proceeds" ? <div className="sub">Deadline inherited from source lot</div> : null}</td>
                  <td className="mono muted" style={{ fontSize: 12 }}>{formatDate(lot.received_at)}</td>
                  <td className="num col-strong">{formatMoneyMinor(lot.available_amount_minor, lot.currency)}</td>
                  <td style={{ minWidth: 150 }}>
                    <DeadlineMeter daysUntilWithdrawal={lot.days_until_withdrawal_deadline} />
                    <div className="row spread muted" style={{ fontSize: 10.5, marginTop: 4 }}>
                      <span>{lot.days_until_investment_deadline > 0 ? `${lot.days_until_investment_deadline}d to invest` : "Invest window closed"}</span>
                      <span>{lot.days_until_withdrawal_deadline}d to withdraw</span>
                    </div>
                  </td>
                  <td><Chip status={penalty ? "penalty" : lot.bucket} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DepositModal({
  allowCurrencySelection = false,
  currency: initialCurrency,
  onClose
}: {
  allowCurrencySelection?: boolean;
  currency: string;
  onClose: () => void;
}) {
  const [currency, setCurrency] = useState(initialCurrency);
  const instructionsQuery = useDepositInstructionsData();
  const payload = instructionsQuery.data;
  if (instructionsQuery.isError && !payload) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Add Funds">
        <DataErrorCard title="Could not load funding instructions" onRetry={() => void instructionsQuery.refetch()}>
          We could not load the live bank-transfer instructions. Try again before sending funds.
        </DataErrorCard>
      </Modal>
    );
  }
  if (!payload) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Add Funds">
        <ScreenLoading title="Loading funding instructions" />
      </Modal>
    );
  }
  const selectedCurrency = allowCurrencySelection && !payload.instructions.some((item) => item.currency === currency)
    ? payload.instructions[0]?.currency ?? currency
    : currency;
  const instruction = payload.instructions.find((item) => item.currency === selectedCurrency);
  if (!instruction) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={`Add Funds · ${selectedCurrency}`}>
        <Empty icon="info" title={`No ${selectedCurrency} funding account`}>
          Garanta has not enabled bank-transfer instructions for this currency.
        </Empty>
      </Modal>
    );
  }
  return (
    <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={`Add Funds · ${selectedCurrency}`}>
      <div className="col gap-16">
        {allowCurrencySelection && payload.instructions.length > 1 ? (
          <Field label="Currency">
            <select aria-label="Currency" className="select" onChange={(event) => setCurrency(event.target.value)} value={selectedCurrency}>
              {payload.instructions.map((item) => (
                <option key={item.currency} value={item.currency}>{item.currency}</option>
              ))}
            </select>
          </Field>
        ) : null}
        <Banner tone={instruction.is_configured ? "warn" : "bad"} title={`Send ${selectedCurrency} only to this ${selectedCurrency} account`}>
          {instruction.is_configured
            ? "Matching depends on amount, currency, sender name/IBAN and the reference below."
            : "This deposit account is not fully configured yet. Do not send funds until Garanta confirms the live bank details."}
        </Banner>
        <dl className="kv">
          <KeyValueRow label="Account holder" value={instruction.account_holder_name || "Pending configuration"} />
          <KeyValueRow label="Bank" value={instruction.bank_name || "Pending configuration"} />
          <KeyValueRow label="IBAN" mono value={instruction.iban} />
          {instruction.qr_iban ? <KeyValueRow label="QR IBAN" mono value={instruction.qr_iban} /> : null}
          <KeyValueRow label="BIC/SWIFT" mono value={instruction.bic} />
        </dl>
        {instruction.qr_bill_payload ? (
          <div className="qr-instruction-panel">
            <QrBillImage payload={instruction.qr_bill_payload} />
            <div>
              <div className="eyebrow" style={{ marginBottom: 6 }}>Swiss QR-bill code</div>
              <p className="muted" style={{ fontSize: 11.5, margin: 0 }}>
                Scan this code only for {selectedCurrency} transfers. If your bank app does not carry the
                BANXUM payment reference automatically, enter the reference below unchanged.
              </p>
            </div>
          </div>
        ) : null}
        <div>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Payment reference - required</div>
          <div className="codeblock"><span>{instruction.payment_reference}</span><CopyIdButton ariaLabel="Copy payment reference" id={instruction.payment_reference} label="Copy" /></div>
          <div className="deposit-reference-guidance">
            <Icon name="info" size={16} />
            <span>
              Enter this reference unchanged in the payment details or reference field of your bank
              transfer. Missing or incorrect references may delay allocation of the funds to your
              BANXUM account.
            </span>
          </div>
          <p className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>A new balance lot is created on the bank value date and starts its 30/60-day clock.</p>
          <p className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>{payload.reference_rule}</p>
        </div>
      </div>
    </Modal>
  );
}

function QrBillImage({ payload }: { payload: string }) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    let mounted = true;
    QRCode.toDataURL(payload, {
      errorCorrectionLevel: "M",
      margin: 1,
      width: 220,
      color: {
        dark: "#1b211d",
        light: "#fffefb"
      }
    })
      .then((nextSrc) => {
        if (mounted) {
          setSrc(nextSrc);
        }
      })
      .catch(() => {
        if (mounted) {
          setSrc("");
        }
      });
    return () => {
      mounted = false;
    };
  }, [payload]);

  if (!src) {
    return <div className="qr-instruction-placeholder">QR code unavailable</div>;
  }

  return <img alt="Swiss QR-bill code for the collection account" className="qr-instruction-image" src={src} />;
}

function WithdrawModal({ currency, maxMinor, payoutInstructions, onClose }: { currency: string; maxMinor: number; payoutInstructions: PayoutInstruction[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [step, setStep] = useState<"form" | "confirm" | "done">("form");
  const [code, setCode] = useState("");
  const [selectedInstructionId, setSelectedInstructionId] = useState(payoutInstructions.find((instruction) => instruction.is_verified_usable)?.id ?? payoutInstructions[0]?.id ?? "");
  const [error, setError] = useState("");
  const codeRequest = useSensitiveActionCode(ActionEnum.withdrawal);
  useAutoRequestEmailCode(codeRequest, step === "confirm");
  const withdrawalMutation = useV1LedgerWithdrawalRequestsCreate();
  const selectedInstruction = payoutInstructions.find((instruction) => instruction.id === selectedInstructionId);
  const parsedAmount = parseMoneyInputToMinorUnits(amount, currency);
  const amountMinor = parsedAmount.amountMinor;
  const amountError =
    parsedAmount.error ?? (amountMinor > maxMinor ? `Exceeds withdrawable ${currency} balance.` : undefined);
  const valid = amountMinor > 0 && !amountError && Boolean(selectedInstruction?.is_verified_usable);

  const submitWithdrawal = () => {
    setError("");
    if (isFixturePreview) {
      setStep("done");
      return;
    }
    if (!selectedInstruction?.is_verified_usable || !codeRequest.codeId) {
      setError("Select a verified payout IBAN and request an email code first.");
      return;
    }
    withdrawalMutation.mutate(
      {
        data: {
          amount_minor: amountMinor,
          currency,
          destination_iban: selectedInstruction.destination_iban,
          destination_account_name: selectedInstruction.destination_account_name,
          idempotency_key: idempotencyKey("investor-withdrawal"),
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setStep("done");
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };

  const footer = step === "done"
    ? <Button variant="primary" onClick={onClose}>Done</Button>
    : step === "confirm"
      ? <><Button variant="ghost" onClick={() => setStep("form")}>Back</Button><Button disabled={code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || withdrawalMutation.isPending} variant="primary" onClick={submitWithdrawal}>{withdrawalMutation.isPending ? "Submitting..." : "Confirm withdrawal"}</Button></>
      : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!valid} variant="primary" onClick={() => setStep("confirm")}>Review</Button></>;

  return (
    <Modal footer={footer} onClose={onClose} title={`Withdraw ${currency}`}>
      {step === "form" ? (
        <div className="col gap-16">
          <div className="row spread"><span className="muted">Withdrawable balance</span><span className="mono col-strong">{currency} {formatMoneyMinor(maxMinor, currency)}</span></div>
          <Field error={amountError} label="Amount to withdraw">
            <div className="input-affix"><span className="prefix">{currency}</span><input className="input mono" inputMode="decimal" onChange={(event) => setAmount(event.target.value.replace(/[^0-9.]/g, ""))} placeholder="0.00" style={{ paddingLeft: 44 }} value={amount} /></div>
          </Field>
          <Field error={!selectedInstruction?.is_verified_usable ? "Add and verify a payout IBAN before withdrawing." : undefined} label="Payout IBAN">
            <select className="select" onChange={(event) => setSelectedInstructionId(event.target.value)} value={selectedInstructionId}>
              {payoutInstructions.length === 0 ? <option value="">No verified IBAN</option> : null}
              {payoutInstructions.map((instruction) => (
                <option disabled={!instruction.is_verified_usable} key={instruction.id} value={instruction.id}>
                  {instruction.destination_account_name} - {instruction.destination_iban}
                </option>
              ))}
            </select>
          </Field>
          <Banner tone="neutral" title="Operational timing">Withdrawals are processed by Garanta and usually arrive within 1-3 business days.</Banner>
        </div>
      ) : step === "confirm" ? (
        <div className="col gap-16">
          <Review rows={[{ label: "Amount", value: `${currency} ${formatMoneyMinor(amountMinor, currency)}` }, { label: "Fee", value: "None" }, { label: "You will receive", value: `${currency} ${formatMoneyMinor(amountMinor, currency)}`, total: true }]} />
          <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code.</Banner>
          <CodeRequestField
            hint={previewHint("Demo: any 6 digits")}
            label="Email confirmation code"
            requestDisabled={emailCodeRequestDisabled(codeRequest)}
            requestLabel={emailCodeRequestLabel(codeRequest)}
            value={code}
            onChange={setCode}
            onRequest={codeRequest.requestCode}
          />
          {codeRequest.expiresAt ? <p className="muted" style={{ fontSize: 11.5 }}>Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
          {codeRequest.error || error ? <Banner tone="bad" title="Could not submit withdrawal">{codeRequest.error || error}</Banner> : null}
        </div>
      ) : (
        <SuccessState title="Withdrawal requested">You will receive a confirmation email after operational processing.</SuccessState>
      )}
    </Modal>
  );
}

function FxCurrencyFlag({ currency }: { currency: "CHF" | "EUR" }) {
  return currency === "CHF" ? (
    <svg aria-hidden="true" className="fx-flag" viewBox="0 0 20 14">
      <rect fill="#d52b1e" height="14" width="20" />
      <rect fill="#fff" height="8" width="3.2" x="8.4" y="3" />
      <rect fill="#fff" height="2.8" width="8.4" x="5.8" y="5.6" />
    </svg>
  ) : (
    <svg aria-hidden="true" className="fx-flag" viewBox="0 0 20 14">
      <rect fill="#003399" height="14" width="20" />
      <circle cx="10" cy="7" fill="none" r="3.6" stroke="#ffcc00" strokeDasharray="1.2 1.6" strokeWidth="1.1" />
    </svg>
  );
}

function fxMoneyLabel(currency: string, amountMinor: number) {
  return `${currency === "EUR" ? "€" : currency} ${formatMoneyMinor(amountMinor, currency)}`;
}

function fxRateLabel(rate: string | number | null | undefined) {
  const value = Number(rate);
  return Number.isFinite(value) && value > 0 ? value.toFixed(4) : "-";
}

function fixtureFxPreview(
  sourceCurrency: "CHF" | "EUR",
  sourceAmountMinor: number,
  providerRate: number,
  feeBps: number,
  providerRateTimestamp: string
): FxQuotePreview {
  // Review-only fixture math. Live mode always uses the backend preview projection.
  const targetCurrency = sourceCurrency === "CHF" ? "EUR" : "CHF";
  const grossTargetAmountMinor = Math.round(sourceAmountMinor * providerRate);
  const feeMinor = Math.round(grossTargetAmountMinor * feeBps / 10_000);
  const targetAmountMinor = grossTargetAmountMinor - feeMinor;
  return {
    source_currency: sourceCurrency,
    target_currency: targetCurrency,
    source_amount_minor: sourceAmountMinor,
    provider: "fixture_preview",
    rate: providerRate.toFixed(12),
    previous_day_average_rate: providerRate.toFixed(12),
    platform_fee_bps: feeBps,
    gross_target_amount_minor: grossTargetAmountMinor,
    fee_minor: feeMinor,
    target_amount_minor: targetAmountMinor,
    effective_net_rate: (targetAmountMinor / sourceAmountMinor).toFixed(12),
    limit_chf_equivalent_minor: sourceCurrency === "CHF" ? sourceAmountMinor : grossTargetAmountMinor,
    provider_rate_timestamp: providerRateTimestamp,
    sanity_metadata: { fixture_preview: true },
    previewed_at: providerRateTimestamp
  };
}

function fxAvailabilityTitle(message: string) {
  if (/weekend/i.test(message)) return "FX unavailable on weekends";
  if (/market holiday/i.test(message)) return "FX unavailable on this market holiday";
  return "Current FX rate unavailable";
}

function FxScreen({ demoState }: { demoState: DemoAccountState }) {
  const fxQuery = useFxData();
  const balancesQuery = useBalancesData();
  const fx = fxQuery.data;
  const balances = balancesQuery.data;
  const [from, setFrom] = useState<"CHF" | "EUR">("CHF");
  const [amount, setAmount] = useState("");
  const [debouncedInput, setDebouncedInput] = useState({ from: "CHF" as "CHF" | "EUR", amountMinor: 0 });
  const [quoteOpen, setQuoteOpen] = useState(false);
  const [liveQuote, setLiveQuote] = useState<FxQuote | null>(null);
  const [error, setError] = useState("");
  const quoteMutation = useV1FxQuotesCreate();
  const to: "CHF" | "EUR" = from === "CHF" ? "EUR" : "CHF";
  const parsedAmount = parseMoneyInputToMinorUnits(amount, from);
  const amountMinor = parsedAmount.amountMinor;
  const availableMinor = balances?.summaries.find((summary) => summary.currency === from)?.total_available_minor ?? 0;
  const targetAvailableMinor = balances?.summaries.find((summary) => summary.currency === to)?.total_available_minor ?? 0;
  const frozen = demoState === "frozen";
  const readonly = isReadonlyImpersonationActive();
  const fxClosedForWeekend = !isFixturePreview && isZurichWeekend();
  const amountError = parsedAmount.error ?? (amountMinor > availableMinor ? `Exceeds available ${from} balance.` : undefined);
  const inputReady = amountMinor > 0 && !amountError && !frozen && !readonly && !fxClosedForWeekend;

  useEffect(() => {
    const timer = window.setTimeout(
      () => setDebouncedInput({ from, amountMinor: inputReady ? amountMinor : 0 }),
      500
    );
    return () => window.clearTimeout(timer);
  }, [amountMinor, from, inputReady]);

  const previewMatchesInput = debouncedInput.from === from && debouncedInput.amountMinor === amountMinor;
  const previewQuery = useV1FxQuotePreviewRetrieve(
    {
      source_currency: debouncedInput.from,
      target_currency: debouncedInput.from === "CHF" ? "EUR" : "CHF",
      source_amount_minor: Math.max(1, debouncedInput.amountMinor)
    },
    {
      query: {
        enabled: !isFixturePreview && inputReady && previewMatchesInput,
        retry: false,
        staleTime: 0,
        refetchOnWindowFocus: false
      }
    }
  );
  const fixtureReference = fx?.exchanges.find(
    (exchange) => exchange.source_currency === from && exchange.target_currency === to
  ) ?? fx?.exchanges.find(
    (exchange) => exchange.source_currency === to && exchange.target_currency === from
  );
  const fixtureProviderRate = fixtureReference
    ? fixtureReference.source_currency === from
      ? Number(fixtureReference.rate)
      : 1 / Number(fixtureReference.rate)
    : 0;
  const fixturePreview = isFixturePreview && inputReady && fixtureReference && fixtureProviderRate > 0
    ? fixtureFxPreview(
        from,
        amountMinor,
        fixtureProviderRate,
        fixtureReference.platform_fee_bps,
        fixtureReference.executed_at
      )
    : null;
  const queriedPreview = previewQuery.data;
  const previewCandidate = isFixturePreview ? fixturePreview : queriedPreview;
  const preview = previewCandidate
    && previewCandidate.source_currency === from
    && previewCandidate.target_currency === to
    && previewCandidate.source_amount_minor === amountMinor
      ? previewCandidate
      : null;
  const previewLoading = !isFixturePreview
    && inputReady
    && (!previewMatchesInput || previewQuery.isFetching);
  const previewError = !isFixturePreview && previewMatchesInput && previewQuery.isError
    ? apiErrorMessage(previewQuery.error)
    : "";
  const displayedError = error || previewError;

  // "Rates, net of fees" rail card: nominal 100.00-unit previews per direction,
  // mirroring the redesign's reference-rate list with live provider data.
  const nominalEnabled = !isFixturePreview && !fxClosedForWeekend;
  const nominalChfQuery = useV1FxQuotePreviewRetrieve(
    { source_currency: "CHF", target_currency: "EUR", source_amount_minor: 100_00 },
    { query: { enabled: nominalEnabled, retry: false, staleTime: 60_000, refetchOnWindowFocus: false } }
  );
  const nominalEurQuery = useV1FxQuotePreviewRetrieve(
    { source_currency: "EUR", target_currency: "CHF", source_amount_minor: 100_00 },
    { query: { enabled: nominalEnabled, retry: false, staleTime: 60_000, refetchOnWindowFocus: false } }
  );
  const fixtureNominal = (source: "CHF" | "EUR"): FxQuotePreview | null => {
    const reference = fx?.exchanges.find((exchange) => exchange.source_currency === source)
      ?? fx?.exchanges.find((exchange) => exchange.target_currency === source);
    if (!reference) return null;
    const providerRate = reference.source_currency === source
      ? Number(reference.rate)
      : 1 / Number(reference.rate);
    if (!Number.isFinite(providerRate) || providerRate <= 0) return null;
    return fixtureFxPreview(source, 100_00, providerRate, reference.platform_fee_bps, reference.executed_at);
  };
  const nominalRates = (["CHF", "EUR"] as const).map((source) => {
    const nominal = isFixturePreview
      ? fixtureNominal(source)
      : (source === "CHF" ? nominalChfQuery.data : nominalEurQuery.data) ?? null;
    return { source, target: source === "CHF" ? ("EUR" as const) : ("CHF" as const), nominal };
  });
  const nominalTimestamp = nominalRates.find((entry) => entry.nominal)?.nominal?.provider_rate_timestamp;

  const swapDirection = () => {
    setFrom(to);
    setLiveQuote(null);
    setError("");
  };
  const requestQuote = () => {
    setError("");
    if (fxClosedForWeekend) {
      setError("FX is unavailable on weekends because live FX market rates are not published. Try again after markets reopen.");
      return;
    }
    if (!preview) {
      setError("Wait for the current indicative rate before continuing.");
      return;
    }
    if (isFixturePreview) {
      setQuoteOpen(true);
      return;
    }
    quoteMutation.mutate(
      {
        data: {
          source_currency: from,
          target_currency: to,
          source_amount_minor: amountMinor,
          idempotency_key: idempotencyKey("fx-quote")
        }
      },
      {
        onSuccess: (quote) => {
          setLiveQuote(quote);
          setQuoteOpen(true);
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };
  if (balancesQuery.isError && !balances) {
    return (
      <ScreenError title="Currency & FX" onRetry={() => void balancesQuery.refetch()}>
        We could not load your available balances, so FX is unavailable.
      </ScreenError>
    );
  }
  if (!balances) return <ScreenLoading title="Currency & FX" />;

  return (
    <main className="content fx-page">
      <div className="page-head">
        <div>
          <h1>Currency exchange</h1>
          <div className="ph-sub">Convert available CHF and EUR balances. The executable rate and fee are shown before confirmation.</div>
        </div>
      </div>
      {frozen ? <Banner icon="lock" tone="bad" title="FX is frozen">Provide a usable payout IBAN to unlock currency exchange.</Banner> : null}
      {readonly ? <Banner icon="lock" tone="info" title="Read-only view">FX quote and execution are disabled during superadmin read-only impersonation.</Banner> : null}
      {fxClosedForWeekend ? (
        <Banner icon="clock" tone="warn" title="FX unavailable on weekends">
          Live FX market rates are not published on weekends, so BANXUM cannot issue executable FX quotes now. Currency exchange resumes after markets reopen.
        </Banner>
      ) : null}

      <div className="fx-desk">
        <section aria-label="Currency converter" className="fx-card">
          <div className="fx-panel">
            <div className="fx-panel-head">
              <span className="fx-cap">You send</span>
              <span className="grow" />
              <span className="num fx-balance-note">balance {fxMoneyLabel(from, availableMinor)}</span>
            </div>
            <div className="fx-panel-line">
              <input
                aria-label={`Amount to convert from ${from}`}
                className="fx-big-input num"
                disabled={frozen || fxClosedForWeekend || readonly}
                inputMode="decimal"
                onChange={(event) => {
                  setAmount(event.target.value.replace(/[^0-9.,]/g, ""));
                  setLiveQuote(null);
                  setError("");
                }}
                placeholder="0.00"
                value={amount}
              />
              <button
                aria-label={`Sending currency ${from}. Switch direction to send ${to}.`}
                className="fx-pill"
                disabled={frozen || fxClosedForWeekend || readonly}
                onClick={swapDirection}
                type="button"
              >
                <span className="fx-flag-box"><FxCurrencyFlag currency={from} /></span>
                <span>{from}</span>
                <span aria-hidden="true" className="fx-pill-caret">▼</span>
              </button>
            </div>
            {amountError ? <p className="fx-field-error">{amountError}</p> : null}
          </div>

          <div className="fx-hr">
            <button aria-label="Swap CHF and EUR" className="fx-swap" disabled={frozen || fxClosedForWeekend || readonly} onClick={swapDirection} type="button">⇅</button>
          </div>

          <div className="fx-panel receive">
            <div className="fx-panel-head">
              <span className="fx-cap">You receive</span>
              <span className="grow" />
              <span className="num fx-balance-note">balance {fxMoneyLabel(to, targetAvailableMinor)}</span>
            </div>
            <div className="fx-panel-line">
              <output aria-live="polite" className="fx-big-output num">
                {previewLoading ? "…" : preview ? formatMoneyMinor(preview.target_amount_minor, to) : "0.00"}
              </output>
              <button
                aria-label={`Receiving currency ${to}. Switch direction to receive ${from}.`}
                className="fx-pill"
                disabled={frozen || fxClosedForWeekend || readonly}
                onClick={swapDirection}
                type="button"
              >
                <span className="fx-flag-box"><FxCurrencyFlag currency={to} /></span>
                <span>{to}</span>
                <span aria-hidden="true" className="fx-pill-caret">▼</span>
              </button>
            </div>
          </div>

          <div className="fx-rate-line" aria-live="polite">
            <span className="fx-note">Rate, net of fees</span>
            <span className="leader" />
            <strong className="num fx-rate-value">{preview ? `1 ${from} = ${fxRateLabel(preview.effective_net_rate)} ${to}` : previewLoading ? "Checking current rate" : "Enter an amount"}</strong>
          </div>
          <div className="fx-cta-line">
            <span className="fx-cta-copy">
              {preview
                ? `Converting makes ${fxMoneyLabel(to, preview.target_amount_minor)} available in your ${to} balance. Converted money keeps the earliest deadline of the funds it came from — FX never resets the 30/60-day clock.`
                : "Converted money keeps the earliest deadline of the funds it came from — FX never resets the 30/60-day clock."}
            </span>
            <button
              className="fx-convert-btn"
              disabled={!preview || frozen || fxClosedForWeekend || readonly || quoteMutation.isPending}
              onClick={requestQuote}
              type="button"
            >
              {quoteMutation.isPending ? "Locking quote..." : "Convert"}
            </button>
          </div>
        </section>

        <aside className="fx-rail">
          <section className="fx-rail-card">
            <div className="fx-cap fx-rail-cap">Your balances</div>
            <div className="fx-balance-list">
              {(["CHF", "EUR"] as const).map((currency) => {
                const balance = balances.summaries.find((summary) => summary.currency === currency)?.total_available_minor ?? 0;
                return (
                  <div className={`fx-balance-row${balance === 0 ? " zero" : ""}`} key={currency}>
                    <span className="fx-flag-box"><FxCurrencyFlag currency={currency} /></span>
                    <span className="fx-balance-code">{currency}</span>
                    <span className="num fx-balance-amount">{fxMoneyLabel(currency, balance)}</span>
                  </div>
                );
              })}
            </div>
            <div className="fx-rail-foot">Money must be in a loan's currency before it can be lent. Convert it here first when it is not.</div>
          </section>
          <section className="fx-rail-card">
            <div className="fx-cap fx-rail-cap">Rates, net of fees</div>
            <div className="fx-rate-list">
              {nominalRates.map(({ source, target, nominal }) => (
                <div className="fx-rate-row" key={source}>
                  <span className="fx-flag-box"><FxCurrencyFlag currency={source} /></span>
                  <span className="fx-rate-unit">1 {source}</span>
                  <strong className="num">{nominal ? `${fxRateLabel(nominal.effective_net_rate)} ${target}` : "—"}</strong>
                </div>
              ))}
            </div>
            <div className="fx-rail-foot">
              {fxClosedForWeekend
                ? "Live rates return when FX markets reopen."
                : nominalTimestamp
                  ? `Net of fees, ${formatDateTime(nominalTimestamp)}.`
                  : "Fetching current provider rates."}
            </div>
          </section>
        </aside>
      </div>

      {displayedError ? <Banner tone="bad" title={fxAvailabilityTitle(displayedError)}>{displayedError}</Banner> : null}

      <h2 className="sect">Your conversions</h2>
      <p className="sect-sub">Every rate below is the rate you received, net of fees.</p>
      {fxQuery.isError && !fx ? (
        <DataErrorCard title="Could not load conversion history" onRetry={() => void fxQuery.refetch()}>
          The converter remains available, but historical FX activity could not be loaded.
        </DataErrorCard>
      ) : !fx ? (
        <LoadingCard title="Loading conversion history">Loading executed currency exchanges.</LoadingCard>
      ) : fx.exchanges.length === 0 ? (
        <div className="fx-history-empty"><Empty icon="swap" title="No conversions yet">Completed CHF/EUR conversions will appear here.</Empty></div>
      ) : (
        <div aria-label="Your conversions" className="rule-top fx-history" role="table">
          <div className="fx-history-row head" role="row">
            <span role="columnheader">Date</span>
            <span role="columnheader">Converted</span>
            <span role="columnheader">Rate, net of fees</span>
            <span role="columnheader">Received</span>
          </div>
          {fx.exchanges.map((exchange) => (
            <div className="fx-history-row" key={exchange.id} role="row">
              <span className="num fx-h-date" role="cell">{formatDate(exchange.executed_at)}</span>
              <span className="num fx-h-converted" role="cell">{fxMoneyLabel(exchange.source_currency, exchange.source_amount_minor)}</span>
              <span className="num fx-h-rate" role="cell">1 {exchange.source_currency} = {fxRateLabel(exchange.effective_net_rate)} {exchange.target_currency}</span>
              <strong className="num fx-h-received" role="cell">{fxMoneyLabel(exchange.target_currency, exchange.target_amount_minor)}</strong>
            </div>
          ))}
        </div>
      )}

      <div className="band band-2 fx-band">
        <div className="cell">
          <div className="microlabel">Your FX terms</div>
          <div className="kv fx-kv">
            <div className="kv-row"><span className="k">Conversion fee, in the rate</span><span className="leader" /><span className="v">{preview ? formatRateBps(preview.platform_fee_bps) : nominalRates[0].nominal ? formatRateBps(nominalRates[0].nominal.platform_fee_bps) : "Shown with each rate"}</span></div>
            <div className="kv-row"><span className="k">Daily limit</span><span className="leader" /><span className="v">CHF 100,000 equivalent</span></div>
            <div className="kv-row"><span className="k">Executable quote lock</span><span className="leader" /><span className="v">60 seconds</span></div>
          </div>
        </div>
        <div className="cell">
          <div className="microlabel red">How to avoid all of this</div>
          <div className="fx-advice">Hold an account in the currency you invest in at your own bank. Fund it once, never convert again.</div>
          <div className="fx-advice-sub">We earn less when you do this. It is still the right advice.</div>
        </div>
      </div>

      {quoteOpen && preview ? (
        <FxConfirmModal
          from={from}
          to={to}
          sourceMinor={liveQuote?.source_amount_minor ?? preview.source_amount_minor}
          feeMinor={liveQuote?.fee_minor ?? preview.fee_minor}
          targetMinor={liveQuote?.target_amount_minor ?? preview.target_amount_minor}
          rate={Number(liveQuote?.effective_net_rate ?? preview.effective_net_rate)}
          quote={liveQuote}
          onClose={() => setQuoteOpen(false)}
        />
      ) : null}
    </main>
  );
}

function FxConfirmModal({ from, to, sourceMinor, targetMinor, feeMinor, rate, quote, onClose }: { from: string; to: string; sourceMinor: number; targetMinor: number; feeMinor: number; rate: number; quote: FxQuote | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [ack, setAck] = useState(false);
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const codeRequest = useSensitiveActionCode(ActionEnum.fx);
  useAutoRequestEmailCode(codeRequest, !done);
  const executeMutation = useV1FxQuotesExecuteCreate();
  const executeFx = () => {
    setError("");
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    if (!quote || !codeRequest.codeId) {
      setError("Request an email code before confirming the executable quote.");
      return;
    }
    executeMutation.mutate(
      {
        quoteId: quote.id,
        data: {
          idempotency_key: idempotencyKey("fx-execute"),
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setDone(true);
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };
  if (done) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Exchange settled">
        <SuccessState title={`${to} ${formatMoneyMinor(targetMinor, to)} credited`}>
          The new {to} lot inherits the deadline of the consumed source lots. FX does not reset the 30/60-day timer.
        </SuccessState>
      </Modal>
    );
  }
  return (
    <Modal footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ack || code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || executeMutation.isPending} variant="primary" onClick={executeFx}>{executeMutation.isPending ? "Executing..." : "Confirm exchange"}</Button></>} onClose={onClose} title="Confirm currency exchange">
      <div className="col gap-16">
        <Banner icon="clock" tone="info" title="Executable quote locked">This quote is fixed for 60 seconds for confirmation.</Banner>
        <Review rows={[
          { label: "You exchange", value: `${from} ${formatMoneyMinor(sourceMinor, from)}` },
          { label: "Rate, net of fees", value: `1 ${from} = ${rate.toFixed(4)} ${to}` },
          { label: "Platform fee", value: `${to} ${formatMoneyMinor(feeMinor, to)}` },
          { label: "You receive", value: `${to} ${formatMoneyMinor(targetMinor, to, 4)}`, total: true }
        ]} />
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={emailCodeRequestDisabled(codeRequest)}
          requestLabel={emailCodeRequestLabel(codeRequest)}
          value={code}
          onChange={setCode}
          onRequest={codeRequest.requestCode}
        />
        {quote?.expires_at ? <p className="muted" style={{ fontSize: 11.5 }}>Quote expires {formatDateTime(quote.expires_at)}.</p> : null}
        <Banner tone="warn" title="Inherited ageing deadline">The target balance inherits the earliest consumed source-lot deadline. It does not start a fresh 30/60-day window.</Banner>
        <Check checked={ack} id="fx-ack" onChange={setAck}>I accept the currency-exchange terms and understand the rate, fee and inherited deadline.</Check>
        {codeRequest.error || error ? <Banner tone="bad" title="Could not execute FX">{codeRequest.error || error}</Banner> : null}
      </div>
    </Modal>
  );
}

function PortfolioScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const portfolioQuery = usePortfolioData(true);
  const activityQuery = useActivityData();
  const ordersQuery = usePrimaryOrdersData();
  const portfolio = portfolioQuery.data;
  const activity = activityQuery.data;
  const orders = ordersQuery.data;
  const [tab, setTab] = useState<"holdings" | "activity" | "orders">("holdings");
  const [currency, setCurrency] = useState<string | null>(null);
  const [detail, setDetail] = useState<Holding | null>(null);
  if ((portfolioQuery.isError && !portfolio) || (activityQuery.isError && !activity) || (ordersQuery.isError && !orders)) {
    return (
      <ScreenError
        title="Portfolio"
        onRetry={() => {
          void portfolioQuery.refetch();
          void activityQuery.refetch();
          void ordersQuery.refetch();
        }}
      >
        We could not load your holdings, activity, or order history. Retry once the API connection is restored.
      </ScreenError>
    );
  }
  if (!portfolio || !activity || !orders) return <ScreenLoading title="Portfolio" />;
  const openOrders = activePrimaryOrders(orders.orders);
  const active = pfActiveHoldings(portfolio.holdings);
  const currencies = pfCurrencies(active);
  const scopedCurrency = currency && currencies.includes(currency) ? currency : currencies[0] ?? "CHF";
  const scoped = active.filter((holding) => holding.currency === scopedCurrency);
  const totalMinor = scoped.reduce((sum, holding) => sum + holding.current_principal_minor, 0);

  return (
    <main className="content pf-page">
      <h1 className="sr-only">Portfolio</h1>
      <div className="pf-hero">
        <div className="eyebrow">{scoped.length} {scoped.length === 1 ? "loan" : "loans"} · {pfMoneyLabel(scopedCurrency, totalMinor)} lent</div>
        <h2>Everything you own.</h2>
        <p className="pf-lede">Largest first, because the largest is the one that matters most if it goes wrong. Click any loan for the split, the collateral and the schedule.</p>
      </div>
      <div className="pf-tabs-row">
        <nav aria-label="Portfolio sections" className="mtabs" role="tablist">
          <button aria-selected={tab === "holdings"} className={tab === "holdings" ? "on" : ""} onClick={() => setTab("holdings")} role="tab" type="button">My loans</button>
          <button aria-selected={tab === "activity"} className={tab === "activity" ? "on" : ""} onClick={() => setTab("activity")} role="tab" type="button">Activity</button>
          <span className="pf-tab-item">
            <button aria-selected={tab === "orders"} className={tab === "orders" ? "on" : ""} onClick={() => setTab("orders")} role="tab" type="button">Orders</button>
            <PrimaryOrdersInfo orders={openOrders} />
          </span>
        </nav>
        {currencies.length > 1 ? (
          <div aria-label="Portfolio currency" className="seg">
            {currencies.map((code) => (
              <button className={code === scopedCurrency ? "on" : ""} key={code} onClick={() => setCurrency(code)} type="button">{code}</button>
            ))}
          </div>
        ) : null}
      </div>
      <div>
        {tab === "holdings" ? (
          scoped.length === 0 ? (
            openOrders.length > 0 ? (
              <PendingOrdersEmptyState orders={openOrders} onViewOrders={() => setTab("orders")} />
            ) : (
              <PortfolioEmptyState
                action={<Button size="sm" onClick={() => goTo(setRoute, "market")}>Browse marketplace</Button>}
                icon="portfolio"
                title="No loan holdings yet"
              >
                Funded loan claims and settled secondary-market purchases will appear here.
              </PortfolioEmptyState>
            )
          ) : (
            <PfMyLoans currency={scopedCurrency} holdings={scoped} onOpen={setDetail} totalMinor={totalMinor} />
          )
        ) : null}
        {tab === "activity" ? <ActivityTable entries={activity.entries} /> : null}
        {tab === "orders" ? <OrdersTable onBrowse={() => goTo(setRoute, "market")} orders={orders.orders} /> : null}
      </div>
      {scoped.length > 0 ? (
        <PfPortfolioWidgets currency={scopedCurrency} holdings={scoped} setRoute={setRoute} totalMinor={totalMinor} />
      ) : null}
      {detail ? <HoldingDetail holding={detail} onClose={() => setDetail(null)} setRoute={setRoute} /> : null}
    </main>
  );
}

const openPrimaryOrderStatuses = new Set(["pending", "balance_allocated", "partially_allocated"]);

function activePrimaryOrders(orders: PrimaryOrderPortal[]) {
  return orders.filter((order) => openPrimaryOrderStatuses.has(order.status));
}

function primaryOrderDisplayAmount(order: PrimaryOrderPortal) {
  return order.allocated_amount_minor > 0 ? order.allocated_amount_minor : order.requested_amount_minor;
}

function primaryOrderTotalsByCurrency(orders: PrimaryOrderPortal[]) {
  const totals = new Map<string, number>();
  for (const order of orders) {
    totals.set(order.currency, (totals.get(order.currency) ?? 0) + primaryOrderDisplayAmount(order));
  }
  return Array.from(totals.entries()).sort(([left], [right]) => left.localeCompare(right));
}

function PrimaryOrdersInfo({ orders }: { orders: PrimaryOrderPortal[] }) {
  const [visible, setVisible] = useState(false);
  const allocatedCount = orders.filter((order) => order.allocated_amount_minor > 0).length;
  const totals = primaryOrderTotalsByCurrency(orders);
  const totalsLabel = totals
    .map(([currency, amount]) => `${currency} ${formatMoneyMinor(amount, currency)}`)
    .join(" / ");
  const tooltipId = "portfolio-primary-orders-info";
  return (
    <span
      className="pf-tab-info"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <button
        aria-describedby={visible ? tooltipId : undefined}
        aria-label="About primary orders"
        className="pf-tab-info-trigger"
        type="button"
        onBlur={() => setVisible(false)}
        onClick={() => setVisible(true)}
        onFocus={() => setVisible(true)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setVisible(false);
        }}
      >
        <Icon name="info" size={14} />
      </button>
      {visible ? (
        <span className="pf-tab-info-tooltip" id={tooltipId} role="tooltip">
          <strong>Primary orders awaiting funding close</strong>
          <span>
            Pending orders do not reserve balance. Allocated balances are reserved and become loan holdings only after Garanta closes the funding round.
          </span>
          <span>
            {orders.length > 0
              ? `${orders.length} open ${orders.length === 1 ? "order" : "orders"}${allocatedCount > 0 ? `, ${allocatedCount} with allocated balance` : ""}: ${totalsLabel}.`
              : "You have no open primary orders."}
          </span>
        </span>
      ) : null}
    </span>
  );
}

function PendingOrdersEmptyState({ orders, onViewOrders }: { orders: PrimaryOrderPortal[]; onViewOrders: () => void }) {
  return (
    <div className="pf-empty-state pf-pending-orders-empty">
      <div className="col gap-12">
        <Empty icon="portfolio" title="No loan holdings yet">
          Holdings are created only when a published loan is closed and your allocated order converts into a loan claim.
        </Empty>
        <div className="grid grid-2">
          {primaryOrderTotalsByCurrency(orders).map(([currency, amount]) => (
            <div className="stat" key={currency}>
              <div className="stat-label">Awaiting funding close</div>
              <div className="stat-value"><span className="ccy">{currency}</span>{formatMoneyMinor(amount, currency)}</div>
              <div className="stat-sub">{orders.filter((order) => order.currency === currency).length} open primary orders</div>
            </div>
          ))}
        </div>
        <div><Button size="sm" onClick={onViewOrders}>Open Orders tab</Button></div>
      </div>
    </div>
  );
}

function PortfolioEmptyState({ action, children, icon, title }: { action?: ReactNode; children: ReactNode; icon: ComponentProps<typeof Empty>["icon"]; title: string }) {
  return (
    <div className="pf-empty-state">
      <Empty icon={icon} title={title}>{children}</Empty>
      {action ? <div className="pf-empty-action">{action}</div> : null}
    </div>
  );
}

/* ---- Portfolio redesign (website_redesign/portfolio.html port) ---- */

function pfActiveHoldings(holdings: Holding[]) {
  return holdings.filter((holding) => holding.status === "active" && holding.current_principal_minor > 0);
}

function pfCurrencies(holdings: Holding[]) {
  const totals = new Map<string, number>();
  for (const holding of holdings) {
    totals.set(holding.currency, (totals.get(holding.currency) ?? 0) + holding.current_principal_minor);
  }
  return Array.from(totals.entries()).sort((left, right) => right[1] - left[1]).map(([code]) => code);
}

function pfMoneyLabel(currency: string, amountMinor: number) {
  return `${currency === "EUR" ? "€" : currency} ${formatMoneyMinor(amountMinor, currency)}`;
}

function pfWholeLabel(currency: string, amountMinor: number) {
  return pfMoneyLabel(currency, amountMinor);
}

function pfDefaultInterestLabel(values: number[]) {
  const configured = values.filter((value) => value > 0);
  if (configured.length === 0) return "Not configured";
  const minimum = Math.min(...configured);
  const maximum = Math.max(...configured);
  return minimum === maximum
    ? `${formatRateBps(minimum)} p.a.`
    : `${formatRateBps(minimum)}–${formatRateBps(maximum)} p.a.`;
}

const pfCollateralShortLabels: Record<string, string> = {
  real_estate: "property",
  corporate_guarantee: "guarantee",
  personal_guarantee: "surety",
  receivables: "receivables",
  invoices: "invoices",
  equipment: "equipment",
  inventory: "inventory",
  securities_pledge: "securities",
  cash_collateral: "cash",
  share_pledge: "shares",
  asset_backed: "assets",
  mixed_collateral: "mixed",
  unsecured_exception: "unsecured",
  other: "other"
};

function pfCollateralLabel(collateralType: string) {
  return pfCollateralShortLabels[collateralType] ?? humanizeToken(collateralType).toLowerCase();
}

function pfPaysLabel(repaymentType: string) {
  if (repaymentType === "bullet_periodic_interest") return "monthly int.";
  if (repaymentType.startsWith("interest_only")) return "interest first";
  return "monthly";
}

function pfIsLate(holding: Holding) {
  return holding.loan.loan_status === "late" || holding.loan.loan_status === "defaulted";
}

function pfIsUnsecured(holding: Holding) {
  return holding.loan.collateral_type === "unsecured_exception";
}

function pfShortDate(iso: string) {
  const date = new Date(`${iso}T00:00:00`);
  const now = new Date();
  const sameYear = date.getFullYear() === now.getFullYear();
  const label = date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return sameYear ? label : `${label} ${date.getFullYear()}`;
}

type PfPayment = {
  date: Date;
  iso: string;
  name: string;
  amt: number;
  int: number;
  pri: number;
  n: number;
  term: number;
  late: boolean;
  final: boolean;
  balanceAfter: number;
  collateral: string;
  ltvBps: number | null;
};

function pfPayments(holdings: Holding[]): PfPayment[] {
  const payments: PfPayment[] = [];
  for (const holding of holdings) {
    const rows = holding.investment_schedule.filter((row) => row.status !== "paid");
    const remainingTotal = rows.reduce((sum, row) => sum + row.projected_principal_minor, 0);
    let consumed = 0;
    for (const row of rows) {
      consumed += row.projected_principal_minor;
      payments.push({
        date: new Date(`${row.due_date}T00:00:00`),
        iso: row.due_date,
        name: holding.loan.borrower_name || holding.loan.loan_title,
        amt: row.projected_total_minor,
        int: row.projected_interest_minor,
        pri: row.projected_principal_minor,
        n: row.installment_number,
        term: holding.loan.term_months,
        late: pfIsLate(holding),
        final: row.installment_number === holding.loan.term_months,
        balanceAfter: Math.max(0, remainingTotal - consumed),
        collateral: pfCollateralLabel(holding.loan.collateral_type),
        ltvBps: holding.loan.ltv_bps
      });
    }
  }
  return payments.sort((left, right) => left.date.getTime() - right.date.getTime());
}

function pfNextPayment(holding: Holding) {
  return holding.investment_schedule.find((row) => row.status !== "paid") ?? null;
}

function pfScore(value: number, worst: number, best: number) {
  const ratio = (value - worst) / (best - worst);
  return Math.round(Math.min(1, Math.max(0, ratio)) * 100);
}

type PfAxis = { label: string; score: number; sentence: string };

function pfAxes(holdings: Holding[], currency: string, totalMinor: number): PfAxis[] {
  const share = (amount: number) => (totalMinor > 0 ? amount / totalMinor : 0);
  const largest = holdings.reduce((best, holding) => (holding.current_principal_minor > best.current_principal_minor ? holding : best), holdings[0]);
  const largestShare = share(largest.current_principal_minor);

  const byPurpose = new Map<string, number>();
  for (const holding of holdings) {
    const key = humanizeToken(holding.loan.purpose);
    byPurpose.set(key, (byPurpose.get(key) ?? 0) + holding.current_principal_minor);
  }
  const [topPurpose, topPurposeMinor] = Array.from(byPurpose.entries()).sort((a, b) => b[1] - a[1])[0];

  const secured = holdings.filter((holding) => !pfIsUnsecured(holding));
  const securedMinor = secured.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const valuedSecured = secured.filter((holding) => holding.loan.ltv_bps !== null);
  const valuedSecuredMinor = valuedSecured.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const weightedLtvBps = valuedSecuredMinor > 0
    ? valuedSecured.reduce((sum, holding) => sum + (holding.loan.ltv_bps ?? 0) * holding.current_principal_minor, 0) / valuedSecuredMinor
    : 0;
  const coverPct = weightedLtvBps / 100;

  const byCollateral = new Map<string, number>();
  for (const holding of holdings) {
    const key = pfIsUnsecured(holding) ? "no asset" : pfCollateralLabel(holding.loan.collateral_type);
    byCollateral.set(key, (byCollateral.get(key) ?? 0) + holding.current_principal_minor);
  }
  const [topCollateral, topCollateralMinor] = Array.from(byCollateral.entries()).sort((a, b) => b[1] - a[1])[0];

  const lateMinor = holdings
    .filter((holding) => pfIsLate(holding))
    .reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const currentMinor = Math.max(0, totalMinor - lateMinor);

  return [
    {
      label: "Spread across loans",
      score: pfScore(largestShare, 0.25, 0.02),
      sentence: `Your largest loan is ${largest.loan.borrower_name || largest.loan.loan_title} at ${(largestShare * 100).toFixed(1)}% of your money. Scale: 0 if one loan is over 25%, 100 if none is over 2%.`
    },
    {
      label: "Spread by purpose",
      score: pfScore(share(topPurposeMinor), 0.6, 0.2),
      sentence: `${topPurpose} is ${pfMoneyLabel(currency, topPurposeMinor)}, or ${(share(topPurposeMinor) * 100).toFixed(1)}% — your largest purpose. Scale: 0 if one purpose is over 60%, 100 if none is over 20%.`
    },
    {
      label: "Collateral cover",
      score: securedMinor > 0 ? pfScore(coverPct, 90, 40) : 0,
      sentence: securedMinor > 0
        ? `Weighted across your money, each secured loan sits at ${coverPct.toFixed(1)}% of an independent valuation. Scale: 0 at 90% of valuation, 100 at 40% or less.`
        : "No secured loans yet, so there is no valuation cover to measure."
    },
    {
      label: "With collateral",
      score: Math.round(share(securedMinor) * 100),
      sentence: `${pfMoneyLabel(currency, securedMinor)} of your ${pfMoneyLabel(currency, totalMinor)} has something pledged behind it. Scale: 0 if nothing is secured, 100 if everything is.`
    },
    {
      label: "Principal collateral",
      score: pfScore(share(topCollateralMinor), 1, 0.35),
      sentence: `${humanizeToken(topCollateral)} is ${pfMoneyLabel(currency, topCollateralMinor)}, or ${(share(topCollateralMinor) * 100).toFixed(1)}% of your money — counted by each loan's principal asset. Scale: 0 if one type is everything, 100 if none is over 35%.`
    },
    {
      label: "Current performance",
      score: Math.round(share(currentMinor) * 100),
      sentence: `${pfMoneyLabel(currency, currentMinor)} of your ${pfMoneyLabel(currency, totalMinor)} is not currently late or defaulted. Scale: 0 if all current principal is in arrears, 100 if none is.`
    }
  ];
}

function pfHexPoints(scores: number[], cx: number, cy: number, radius: number) {
  return scores
    .map((score, index) => {
      const angle = -Math.PI / 2 + (index * Math.PI) / 3;
      const r = (radius * Math.max(4, score)) / 100;
      return `${(cx + r * Math.cos(angle)).toFixed(2)},${(cy + r * Math.sin(angle)).toFixed(2)}`;
    })
    .join(" ");
}

function pfHexVertex(index: number, cx: number, cy: number, radius: number, score: number) {
  const angle = -Math.PI / 2 + (index * Math.PI) / 3;
  const r = (radius * Math.max(4, score)) / 100;
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
}

function pfRingSegments(holdings: Holding[]) {
  const byType = new Map<string, number>();
  let unsecured = 0;
  for (const holding of holdings) {
    if (pfIsUnsecured(holding)) {
      unsecured += holding.current_principal_minor;
    } else {
      const key = pfCollateralLabel(holding.loan.collateral_type);
      byType.set(key, (byType.get(key) ?? 0) + holding.current_principal_minor);
    }
  }
  const sorted = Array.from(byType.entries()).sort((a, b) => b[1] - a[1]);
  const palette = ["#151719", "#4a5257", "#8b939a"];
  const segments: { label: string; amount: number; color: string; bad?: boolean }[] = [];
  sorted.slice(0, 3).forEach(([label, amount], index) => {
    segments.push({ label: humanizeToken(label), amount, color: palette[index] });
  });
  const otherMinor = sorted.slice(3).reduce((sum, [, amount]) => sum + amount, 0);
  if (otherMinor > 0) segments.push({ label: "Other assets", amount: otherMinor, color: "#c6c3ba" });
  if (unsecured > 0) segments.push({ label: "No asset pledged", amount: unsecured, color: "#c4312c", bad: true });
  return segments;
}

function PfRing({ segments, total, radius, stroke, size, center }: { segments: { amount: number; color: string }[]; total: number; radius: number; stroke: number; size: number; center?: { title: string; sub: string } }) {
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <svg height={size} shapeRendering="geometricPrecision" style={{ display: "block", flex: "none" }} viewBox={`0 0 ${size} ${size}`} width={size}>
      <g fill="none" strokeWidth={stroke} transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        {segments.map((segment, index) => {
          const length = total > 0 ? (segment.amount / total) * circumference : 0;
          const dashOffset = -offset;
          offset += length;
          return <circle cx={size / 2} cy={size / 2} key={index} r={radius} stroke={segment.color} strokeDasharray={`${length.toFixed(2)} ${circumference.toFixed(2)}`} strokeDashoffset={dashOffset.toFixed(2)} />;
        })}
      </g>
      {center ? (
        <>
          <text fill="#151719" fontFamily="Instrument Sans, Arial, sans-serif" fontSize={center.title.length > 11 ? "12.5" : "17"} fontWeight="600" letterSpacing="-0.3" textAnchor="middle" x={size / 2} y={size / 2 - 3}>{center.title}</text>
          <text fill="#626b70" fontFamily="Instrument Sans, Arial, sans-serif" fontSize="9.5" fontWeight="600" letterSpacing=".02em" textAnchor="middle" x={size / 2} y={size / 2 + 12}>{center.sub}</text>
        </>
      ) : null}
    </svg>
  );
}

function PfCard({ lab, tt, open, onToggle, children, foot }: { lab: string; tt: string; open: boolean; onToggle: () => void; children: ReactNode; foot: ReactNode }) {
  return (
    <button aria-expanded={open} className={`card471${open ? " open" : ""}`} onClick={onToggle} type="button">
      <span className="head">
        <span style={{ flex: 1 }}><span className="lab">{lab}</span><span className="tt">{tt}</span></span>
        <span aria-hidden="true" className="sig">{open ? "−" : "+"}</span>
      </span>
      {children}
      <span className="foot">{foot}</span>
    </button>
  );
}

type FsSortOption = { key: string; label: string };

function SortControl({
  options,
  activeKey,
  dir,
  onPick,
  small
}: {
  options: FsSortOption[];
  activeKey: string | null;
  dir: "asc" | "desc";
  onPick: (key: string) => void;
  small?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const listener = (event: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", listener);
    return () => document.removeEventListener("mousedown", listener);
  }, [open]);
  return (
    <div className="fs-sort-wrap" ref={wrapRef}>
      <button aria-expanded={open} aria-haspopup="menu" className={`fs-pill${small ? " small" : ""}${open ? " on" : ""}`} onClick={() => setOpen((current) => !current)} type="button">
        <span>Sort</span>
        <span aria-hidden="true" className="fs-arrows">↑↓</span>
      </button>
      {open ? (
        <div className="fs-menu" role="menu">
          <div className="fs-menu-cap">Sort by</div>
          {options.map((option) => {
            const on = option.key === activeKey;
            return (
              <button
                className={`fs-menu-item${on ? " on" : ""}`}
                key={option.key}
                onClick={() => {
                  onPick(option.key);
                  setOpen(false);
                }}
                role="menuitem"
                type="button"
              >
                {option.label}
                {on ? <span aria-hidden="true" className="fs-menu-arrow">{dir === "asc" ? "↑" : "↓"}</span> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function FsTh({
  activeKey,
  className,
  dir,
  label,
  onPick,
  sortKey
}: {
  activeKey: string | null;
  className?: string;
  dir: "asc" | "desc";
  label: string;
  onPick: (key: string) => void;
  sortKey: string;
}) {
  const on = activeKey === sortKey;
  return (
    <button aria-label={`Sort by ${label}`} className={`fs-th${on ? " on" : ""}${className ? ` ${className}` : ""}`} onClick={() => onPick(sortKey)} type="button">
      <span className="fs-th-label">{label}</span>
      {on ? <span aria-hidden="true" className="fs-th-arrow">{dir === "asc" ? "↑" : "↓"}</span> : null}
    </button>
  );
}

const pfPaysOrder = (repaymentType: string) =>
  repaymentType === "equal_installments" ? 0 : repaymentType.startsWith("interest_only") ? 1 : repaymentType === "bullet_periodic_interest" ? 2 : 3;

const pfSortOptionsFocused: FsSortOption[] = [
  { key: "name", label: "Company" },
  { key: "share", label: "Share of portfolio" },
  { key: "amount", label: "Amount" }
];

const pfSortOptionsDetailed: FsSortOption[] = [
  { key: "name", label: "Company" },
  { key: "rate", label: "Rate" },
  { key: "term", label: "Term" },
  { key: "pays", label: "Pays" },
  { key: "col", label: "Collateral" },
  { key: "next", label: "Next payment" },
  { key: "share", label: "Share of portfolio" },
  { key: "amount", label: "Amount" }
];

function pfSortValue(holding: Holding, key: string): number | string {
  if (key === "name") return (holding.loan.borrower_name || holding.loan.loan_title).toLowerCase();
  if (key === "rate") return holding.loan.interest_rate_bps;
  if (key === "term") return holding.loan.term_months;
  if (key === "pays") return pfPaysOrder(holding.loan.repayment_type);
  if (key === "col") return pfCollateralLabel(holding.loan.collateral_type);
  if (key === "next") return pfNextPayment(holding)?.due_date ?? "9999-12-31";
  return holding.current_principal_minor;
}

function PfMyLoans({ currency, holdings, onOpen, totalMinor }: { currency: string; holdings: Holding[]; onOpen: (holding: Holding) => void; totalMinor: number }) {
  const [view, setView] = useState<"focused" | "detailed">("focused");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [dir, setDir] = useState<"asc" | "desc">("asc");
  const pick = (key: string) => {
    setDir(sortKey === key && dir === "asc" ? "desc" : "asc");
    setSortKey(key);
  };
  const selectView = (nextView: "focused" | "detailed") => {
    setView(nextView);
    if (
      nextView === "focused"
      && sortKey !== null
      && !pfSortOptionsFocused.some((option) => option.key === sortKey)
    ) {
      setSortKey(null);
      setDir("asc");
    }
  };
  const sorted = [...holdings].sort((left, right) => {
    if (!sortKey) return right.current_principal_minor - left.current_principal_minor;
    const x = pfSortValue(left, sortKey);
    const y = pfSortValue(right, sortKey);
    const c = typeof x === "string" ? x.localeCompare(String(y)) : x - Number(y);
    return dir === "asc" ? c : -c;
  });
  const largestMinor = holdings.reduce((max, holding) => Math.max(max, holding.current_principal_minor), 1);
  const [totalWhole, totalCents = "00"] = formatMoneyMinor(totalMinor, currency).split(".");

  return (
    <div className="pf-loans">
      <div className="pf-sect-row">
        <div style={{ flex: 1 }}>
          <h2 className="sect">My loans</h2>
          <p className="pf-sect-note">The rule under each amount is that loan's share of everything you have lent. Click any column heading to sort, or open the loan for the split, the collateral and the full schedule.</p>
        </div>
        {sortKey ? (
          <button className="fs-clear-link" onClick={() => { setSortKey(null); setDir("asc"); }} type="button">back to largest first</button>
        ) : null}
        <SortControl
          activeKey={sortKey}
          dir={dir}
          onPick={pick}
          options={view === "detailed" ? pfSortOptionsDetailed : pfSortOptionsFocused}
          small
        />
        <div className="seg" role="tablist">
          <button aria-selected={view === "focused"} className={view === "focused" ? "on" : ""} onClick={() => selectView("focused")} role="tab" type="button">Focused</button>
          <button aria-selected={view === "detailed"} className={view === "detailed" ? "on" : ""} onClick={() => selectView("detailed")} role="tab" type="button">Detailed</button>
        </div>
      </div>

      <div className={`pf-table ${view}`}>
        <div className="pf-thead">
          <FsTh activeKey={sortKey} className="pf-th-company" dir={dir} label="Company" onPick={pick} sortKey="name" />
          <FsTh activeKey={sortKey} className="detail-col pf-col-rate" dir={dir} label="Rate" onPick={pick} sortKey="rate" />
          <FsTh activeKey={sortKey} className="detail-col pf-col-term" dir={dir} label="Term" onPick={pick} sortKey="term" />
          <FsTh activeKey={sortKey} className="detail-col pf-col-pays" dir={dir} label="Pays" onPick={pick} sortKey="pays" />
          <FsTh activeKey={sortKey} className="detail-col pf-col-collateral" dir={dir} label="Collateral" onPick={pick} sortKey="col" />
          <FsTh activeKey={sortKey} className="detail-col pf-col-next" dir={dir} label="Next payment" onPick={pick} sortKey="next" />
          <FsTh activeKey={sortKey} className="pf-col-share" dir={dir} label="Share" onPick={pick} sortKey="share" />
          <FsTh activeKey={sortKey} className="pf-col-amount" dir={dir} label="Amount" onPick={pick} sortKey="amount" />
        </div>
        <div className="pf-tbody">
          {sorted.map((holding) => {
            const late = pfIsLate(holding);
            const next = pfNextPayment(holding);
            const shareLabel = totalMinor > 0 ? `${((holding.current_principal_minor / totalMinor) * 100).toFixed(1)}%` : "-";
            const widthPct = (holding.current_principal_minor / largestMinor) * 100;
            const listing = holding.open_secondary_listing;
            return (
              <button className="pf-row" key={holding.id} onClick={() => onOpen(holding)} type="button">
                <span className="pf-company">
                  <span className={`pf-company-name${late ? " late" : ""}`}>{holding.loan.borrower_name || holding.loan.loan_title}</span>
                  {late ? <span className="pf-tag late">late</span> : null}
                  {listing ? <span className="pf-tag">{listingStatusLabel(listing.status)}</span> : null}
                  <span className="pf-company-sub">{holding.loan.loan_title}</span>
                </span>
                <span className="detail-col num pf-col-rate strong">{formatRateBps(holding.loan.interest_rate_bps)}</span>
                <span className="detail-col num pf-col-term mut">{holding.loan.term_months} mo</span>
                <span className="detail-col pf-col-pays mut">{pfPaysLabel(holding.loan.repayment_type)}</span>
                <span className="detail-col pf-col-collateral mut">{pfCollateralLabel(holding.loan.collateral_type)}</span>
                <span className={`detail-col num pf-col-next${late ? " late" : " mut"}`}>
                  {late && holding.loan.days_past_due > 0
                    ? <>{holding.loan.days_past_due} days late{next ? <> · <b>{formatMoneyMinor(next.projected_total_minor, currency)}</b></> : null}</>
                    : next
                      ? <>{pfShortDate(next.due_date)} · <b>{formatMoneyMinor(next.projected_total_minor, currency)}</b></>
                      : "—"}
                </span>
                <span className="num pf-col-share mut">{shareLabel}</span>
                <span className="pf-col-amount">
                  <span className={`num pf-amount${late ? " late" : ""}`}>{pfWholeLabel(currency, holding.current_principal_minor)}</span>
                  <span className="pf-share-track"><span className={late ? "late" : ""} style={{ marginLeft: `${(100 - widthPct).toFixed(1)}%`, width: `${widthPct.toFixed(1)}%` }} /></span>
                </span>
              </button>
            );
          })}
        </div>
        <div className="tfoot">
          <span className="pf-tfoot-count">{sorted.length} {sorted.length === 1 ? "loan" : "loans"}</span>
          <span className="pf-tfoot-note">The rule under each amount is that loan's share of your portfolio. Red marks a loan in arrears.</span>
          <span className="pf-tfoot-ccy">{currency === "EUR" ? "€" : currency}</span>
          <span className="num pf-tfoot-total">{totalWhole}</span>
          <span className="num pf-tfoot-cents">.{totalCents}</span>
        </div>
      </div>
    </div>
  );
}

function PfPortfolioWidgets({ currency, holdings, setRoute, totalMinor }: { currency: string; holdings: Holding[]; setRoute: (route: AppRoute) => void; totalMinor: number }) {
  const [openPanel, setOpenPanel] = useState<"cal" | "hex" | "col" | "risk" | null>(null);
  const payments = pfPayments(holdings);
  const axes = pfAxes(holdings, currency, totalMinor);
  const lowestAxis = axes.reduce((low, axis) => (axis.score < low.score ? axis : low), axes[0]);
  const segments = pfRingSegments(holdings);
  const largestSegment = segments[0];
  const secured = holdings.filter((holding) => !pfIsUnsecured(holding));
  const valuedSecured = secured.filter((holding) => holding.loan.ltv_bps !== null);
  const securedLtvs = valuedSecured.map((holding) => (holding.loan.ltv_bps ?? 0) / 100);
  const valuedSecuredMinor = valuedSecured.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const weightedLtv = valuedSecuredMinor > 0
    ? valuedSecured.reduce((sum, holding) => sum + ((holding.loan.ltv_bps ?? 0) / 100) * holding.current_principal_minor, 0) / valuedSecuredMinor
    : null;
  const defaultInterestBps = holdings.map((holding) => holding.loan.default_penalty_interest_bps);
  const configuredDefaultInterestBps = defaultInterestBps.filter((value) => value > 0);
  const defaultInterestLabel = pfDefaultInterestLabel(defaultInterestBps);
  const unsecuredHoldings = holdings.filter((holding) => pfIsUnsecured(holding));
  const unsecuredMinor = unsecuredHoldings.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const lateHoldings = holdings.filter((holding) => pfIsLate(holding));
  const lateMinor = lateHoldings.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const toggle = (panel: "cal" | "hex" | "col" | "risk") => setOpenPanel((current) => (current === panel ? null : panel));

  return (
    <section aria-label="Portfolio insights" className="pf-insights">

      <div className="pf-cards">
        <div className="pf-widget-pair">
          <div className="pf-widget-card first">
            <PfCalendarCard currency={currency} open={openPanel === "cal"} onToggle={() => toggle("cal")} payments={payments} />
          </div>
          {openPanel === "cal" ? <PfCalendarPanel currency={currency} payments={payments} /> : null}

          <div className="pf-widget-card second">
            <PfCard
              foot={<><span className="big" style={{ color: lowestAxis.score < 50 ? "#c4312c" : "#151719" }}>{lowestAxis.score}</span><span className="note">is the lowest of the six · <span style={{ color: "#151719", fontWeight: 600 }}>{lowestAxis.label.toLowerCase()}</span></span></>}
              lab="Spread of portfolio"
              onToggle={() => toggle("hex")}
              open={openPanel === "hex"}
              tt="How much rests on one outcome"
            >
              <span style={{ display: "flex", justifyContent: "center", marginBottom: 10, width: "100%" }}>
                <svg height="102" shapeRendering="geometricPrecision" style={{ display: "block" }} viewBox="0 0 44 40" width="112">
                  <polygon fill="none" points="22,2 37.59,11 37.59,29 22,38 6.41,29 6.41,11" stroke="#dde3e1" strokeWidth=".8" />
                  <polygon fill="rgba(21,23,25,.12)" points={pfHexPoints(axes.map((axis) => axis.score), 22, 20, 18)} stroke="#151719" strokeWidth="1" />
                  {(() => {
                    const index = axes.indexOf(lowestAxis);
                    const vertex = pfHexVertex(index, 22, 20, 18, lowestAxis.score);
                    return <circle cx={vertex.x.toFixed(2)} cy={vertex.y.toFixed(2)} fill="#c4312c" r="1.5" />;
                  })()}
                </svg>
              </span>
            </PfCard>
          </div>
          {openPanel === "hex" ? <PfHexPanel axes={axes} /> : null}
        </div>

        <div className="pf-widget-pair">
          <div className="pf-widget-card first">
            <PfCard
              foot={<><span className="big" style={{ fontSize: 24 }}>{largestSegment ? pfWholeLabel(currency, largestSegment.amount) : "—"}</span><span className="note" style={{ fontSize: 12.5 }}>behind {largestSegment ? largestSegment.label.toLowerCase() : "nothing yet"} — your largest type</span></>}
              lab="Collateral spread"
              onToggle={() => toggle("col")}
              open={openPanel === "col"}
              tt="What stands behind your money"
            >
              <span style={{ alignItems: "center", display: "flex", gap: 22, marginBottom: 20, width: "100%" }}>
                <PfRing radius={44} segments={segments} size={120} stroke={17} total={totalMinor} />
                <span style={{ display: "flex", flex: 1, flexDirection: "column", fontSize: 11.5, gap: 6, minWidth: 0 }}>
                  {segments.map((segment) => (
                    <span key={segment.label} style={{ alignItems: "center", display: "flex", gap: 8 }}>
                      <span style={{ background: segment.color, borderRadius: 2, flex: "none", height: 9, width: 9 }} />
                      <span style={{ color: segment.bad ? "#c4312c" : "#292d30", flex: 1 }}>{segment.label}</span>
                      <span className="num" style={{ color: segment.bad ? "#c4312c" : undefined, fontWeight: 600 }}>{totalMinor > 0 ? `${((segment.amount / totalMinor) * 100).toFixed(1)}%` : "-"}</span>
                    </span>
                  ))}
                </span>
              </span>
            </PfCard>
          </div>
          {openPanel === "col" ? <PfCollateralPanel currency={currency} holdingCount={holdings.length} segments={segments} totalMinor={totalMinor} /> : null}

          <div className="pf-widget-card second">
            <PfCard
              foot={<><span className="big" style={{ fontSize: 24 }}>{defaultInterestLabel}</span><span className="note" style={{ fontSize: 12.5 }}>{configuredDefaultInterestBps.length > 0 ? "configured annual default interest, after default" : "across the loans shown"}</span></>}
              lab="If a borrower stops paying"
              onToggle={() => toggle("risk")}
              open={openPanel === "risk"}
              tt="What protects your money"
            >
              <span style={{ alignItems: "center", display: "flex", gap: 22, marginBottom: 20, width: "100%" }}>
                <span style={{ alignItems: "flex-end", display: "flex", flex: "none", gap: 9, height: 104, width: 104 }}>
                  <span style={{ border: "1.5px solid #c2bfb5", borderRadius: 3, display: "flex", flex: 1, flexDirection: "column", height: 104, justifyContent: "flex-end", overflow: "hidden" }}>
                    <span style={{ background: "#151719", display: "block", height: `${weightedLtv === null ? 0 : weightedLtv.toFixed(1)}%` }} />
                  </span>
                  <span style={{ color: "#626b70", display: "flex", flex: "none", flexDirection: "column", fontSize: 10, height: 104, justifyContent: "space-between", padding: "1px 0" }}>
                    <span>valuation</span>
                    <span style={{ color: "#151719", fontWeight: 600 }}>lent</span>
                  </span>
                </span>
                <span style={{ display: "flex", flex: 1, flexDirection: "column", fontSize: 11.5, gap: 7, minWidth: 0 }}>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#292d30", flex: 1 }}>Weighted LTV</span><span className="num" style={{ fontWeight: 600 }}>{weightedLtv === null ? "—" : `${weightedLtv.toFixed(1)}%`}</span></span>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#292d30", flex: 1 }}>Range per project</span><span className="num" style={{ fontWeight: 600 }}>{securedLtvs.length > 0 ? `${Math.min(...securedLtvs).toFixed(0)} – ${Math.max(...securedLtvs).toFixed(0)}%` : "—"}</span></span>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#292d30", flex: 1 }}>Nothing pledged</span><span className="num" style={{ color: unsecuredHoldings.length > 0 ? "#c4312c" : undefined, fontWeight: 600 }}>{unsecuredHoldings.length} of {holdings.length}</span></span>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#292d30", flex: 1 }}>In arrears now</span><span className="num" style={{ color: lateHoldings.length > 0 ? "#c4312c" : undefined, fontWeight: 600 }}>{lateHoldings.length} of {holdings.length}</span></span>
                </span>
              </span>
            </PfCard>
          </div>
          {openPanel === "risk" ? (
            <PfProtectionPanel
              currency={currency}
              holdingCount={holdings.length}
              lateCount={lateHoldings.length}
              lateMinor={lateMinor}
              securedLtvs={securedLtvs}
              defaultInterestBps={defaultInterestBps}
              unsecuredCount={unsecuredHoldings.length}
              unsecuredMinor={unsecuredMinor}
              weightedLtv={weightedLtv}
            />
          ) : null}
        </div>
      </div>

      <div className="pf-howlink">
        <button onClick={() => goTo(setRoute, "faq")} type="button">
          <span className="pf-howlink-i">i</span>
          <span className="pf-howlink-text">How BANXUM loans work</span>
        </button>
      </div>
    </section>
  );
}

function PfCalendarCard({ currency, open, onToggle, payments }: { currency: string; open: boolean; onToggle: () => void; payments: PfPayment[] }) {
  const now = new Date();
  const monthPayments = payments.filter((payment) => payment.date.getFullYear() === now.getFullYear() && payment.date.getMonth() === now.getMonth());
  const paymentDays = new Set(monthPayments.map((payment) => payment.date.getDate()));
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const offset = (monthStart.getDay() + 6) % 7;
  const monthLabel = now.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
  const upcoming = payments.find((payment) => payment.date.getTime() >= new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime());
  return (
    <PfCard
      foot={<><span className="big">{paymentDays.size}</span><span className="note">payment dates in {monthLabel} · next is {upcoming ? <span style={{ color: "#151719", fontWeight: 600 }}>{pfShortDate(upcoming.iso)}, {pfMoneyLabel(currency, upcoming.amt)}</span> : "—"}</span></>}
      lab="Earnings calendar"
      onToggle={onToggle}
      open={open}
      tt="Every date you are owed money"
    >
      <span style={{ display: "grid", gap: 4, gridTemplateColumns: "repeat(7,1fr)", marginBottom: 18, width: "100%" }}>
        {Array.from({ length: 35 }, (_, cell) => {
          const day = cell - offset + 1;
          const has = day >= 1 && paymentDays.has(day);
          return <span key={cell} style={{ background: has ? "#151719" : "#dde3e1", borderRadius: 2, height: 9 }} />;
        })}
      </span>
    </PfCard>
  );
}

function PfCalendarPanel({ currency, payments }: { currency: string; payments: PfPayment[] }) {
  const [monthIndex, setMonthIndex] = useState(0);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const now = new Date();
  const months = Array.from({ length: 12 }, (_, index) => {
    const start = new Date(now.getFullYear(), now.getMonth() + index, 1);
    const rows = payments.filter((payment) => payment.date.getFullYear() === start.getFullYear() && payment.date.getMonth() === start.getMonth());
    const byDay = new Map<number, PfPayment[]>();
    for (const row of rows) {
      const day = row.date.getDate();
      byDay.set(day, [...(byDay.get(day) ?? []), row]);
    }
    let max = 0;
    for (const group of byDay.values()) {
      const sum = group.reduce((total, row) => total + row.amt, 0);
      if (sum > max) max = sum;
    }
    return {
      start,
      short: start.toLocaleDateString("en-GB", { month: "short" }),
      full: start.toLocaleDateString("en-GB", { month: "long" }),
      year: start.getFullYear(),
      offset: (start.getDay() + 6) % 7,
      length: new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate(),
      rows,
      byDay,
      total: rows.reduce((sum, row) => sum + row.amt, 0),
      max
    };
  });
  const month = months[monthIndex];
  const selectMonth = (index: number) => { setMonthIndex(index); setSelectedDay(null); };
  const selectedGroup = selectedDay !== null ? month.byDay.get(selectedDay) ?? null : null;

  return (
    <div className="pf-panel">
      <h2 className="sect">Your earnings calendar, date by date</h2>
      <p className="sect-sub" style={{ marginBottom: 22 }}>See every day a company owes you money, for the next 12 months. Click on any day for more details.</p>
      <div className="cal-strip">
        {months.map((entry, index) => (
          <button className={index === monthIndex ? "on" : ""} key={index} onClick={() => selectMonth(index)} type="button">
            <span>{entry.short.toUpperCase()}</span>
            <span className="yr">{entry.year === now.getFullYear() ? "" : `'${String(entry.year).slice(-2)}`}</span>
          </button>
        ))}
      </div>
      <div className="cal-box">
        <div className="cal-head">
          <button className="cal-nav" disabled={monthIndex === 0} onClick={() => selectMonth(monthIndex - 1)} type="button">‹</button>
          <span className="cal-title">{month.full} {month.year}</span>
          <button className="cal-nav" disabled={monthIndex === 11} onClick={() => selectMonth(monthIndex + 1)} type="button">›</button>
          <span className="cal-meta">{month.rows.length} payments · {pfMoneyLabel(currency, month.total)}</span>
          <span className="grow" />
          <span className="cal-legend"><span style={{ background: "#1e6a4b", borderRadius: 2, height: 9, width: 9 }} />payday</span>
          <span className="cal-legend"><span style={{ background: "#151719", height: 2, width: 9 }} />final payment</span>
          <span className="cal-legend"><span style={{ background: "#c4312c", borderRadius: 2, height: 9, width: 9 }} />late</span>
        </div>
        <div className="cal-dows"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div>
        <div className="cal-grid">
          {Array.from({ length: 42 }, (_, cell) => {
            const day = cell - month.offset + 1;
            const inMonth = day >= 1 && day <= month.length;
            const group = inMonth ? month.byDay.get(day) : undefined;
            if (!inMonth) return <div className="cal-plain" key={cell} />;
            if (!group) return <div className="cal-plain" key={cell}>{day}</div>;
            const sum = group.reduce((total, row) => total + row.amt, 0);
            const isLate = group.some((row) => row.late);
            const isFinal = group.some((row) => row.final);
            const who = group.length > 1 ? `${group.length} payments` : group[0].name;
            return (
              <button
                className={`cal-cell${selectedDay === day ? " sel" : ""}${isLate ? " late" : ""}${isFinal ? " final" : ""}`}
                key={cell}
                onClick={() => setSelectedDay((current) => (current === day ? null : day))}
                type="button"
              >
                <span className="d">{day}</span>
                <span className="amt">{formatMoneyMinor(sum, currency)}</span>
                <span className="who">{who}</span>
                <span className="bar"><span style={{ width: `${month.max > 0 ? Math.round((sum / month.max) * 100) : 0}%` }} /></span>
                <span className="endline" />
              </button>
            );
          })}
        </div>
        {selectedGroup ? (
          <div className="cal-detail">
            <div style={{ alignItems: "flex-start", display: "flex", gap: 20, marginBottom: 20 }}>
              <div style={{ flex: 1 }}>
                <div className="microlabel" style={{ marginBottom: 9 }}>{selectedDay} {month.full} {month.year}</div>
                <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em" }}>
                  {selectedGroup.length > 1 ? `${selectedGroup.length} companies pay you on this day` : selectedGroup[0].name}
                </div>
              </div>
              <div style={{ alignItems: "baseline", display: "flex", flex: "none" }}>
                <span className="num" style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.05em", lineHeight: 0.9 }}>{pfMoneyLabel(currency, selectedGroup.reduce((sum, row) => sum + row.amt, 0))}</span>
              </div>
              <button className="cal-x" onClick={() => setSelectedDay(null)} type="button">×</button>
            </div>
            <div style={{ display: "grid", gap: 36, gridTemplateColumns: selectedGroup.length > 1 ? "1fr 1fr" : "1fr 1fr" }}>
              {selectedGroup.map((row, index) => (
                <div key={index}>
                  {selectedGroup.length > 1 ? (
                    <div style={{ alignItems: "baseline", display: "flex", marginBottom: 12 }}>
                      <span style={{ color: row.late ? "#c4312c" : "#151719", fontSize: 16, fontWeight: 600, letterSpacing: "-0.02em" }}>{row.name}</span>
                      <span className="grow" />
                      <span className="num" style={{ fontSize: 16, fontWeight: 600 }}>{pfMoneyLabel(currency, row.amt)}</span>
                    </div>
                  ) : null}
                  <div style={{ display: "flex", flexDirection: "column", fontSize: 13.5, marginBottom: 12 }}>
                    <div className="pf-cal-kv"><span style={{ color: "#1e6a4b" }}>Interest — what you earn</span><span className="leader" /><span className="num" style={{ color: "#1e6a4b", fontWeight: 600 }}>{formatMoneyMinor(row.int, currency)}</span></div>
                    <div className="pf-cal-kv"><span>Your money coming back</span><span className="leader" /><span className="num" style={{ fontWeight: 600 }}>{formatMoneyMinor(row.pri, currency)}</span></div>
                    <div className="pf-cal-kv"><span>Still outstanding</span><span className="leader" /><span className="num" style={{ fontWeight: 600 }}>{formatMoneyMinor(row.balanceAfter, currency)}</span></div>
                    <div className="pf-cal-kv"><span>Installment</span><span className="leader" /><span className="num" style={{ fontWeight: 600 }}>{row.n} of {row.term}</span></div>
                  </div>
                  <div style={{ color: "#626b70", fontSize: 13, lineHeight: 1.55 }}>
                    Secured by {row.collateral === "unsecured" ? "no pledged asset" : row.collateral}.
                    {row.ltvBps !== null ? ` Lent against an independent valuation · ${(row.ltvBps / 100).toFixed(0)}% of the valuation.` : ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="cal-footnote">
            <span style={{ color: "#626b70", fontSize: 13.5 }}>Bars are scaled within the month, so the longest one is that month's largest payment.</span>
            <span className="grow" />
            <span style={{ fontSize: 13.5, fontWeight: 600, marginRight: 16 }}>{month.full} in total</span>
            <span className="num" style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.03em" }}>{pfMoneyLabel(currency, month.total)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function PfHexPanel({ axes }: { axes: PfAxis[] }) {
  const cx = 220;
  const cy = 155;
  const radius = 105;
  const gridPoints = (r: number) => Array.from({ length: 6 }, (_, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI) / 3;
    return `${(cx + r * Math.cos(angle)).toFixed(2)},${(cy + r * Math.sin(angle)).toFixed(2)}`;
  }).join(" ");
  const labelAnchors: { x: number; y: number; anchor: "middle" | "start" | "end" }[] = [
    { x: 220, y: 26, anchor: "middle" },
    { x: 322, y: 96, anchor: "start" },
    { x: 322, y: 201, anchor: "start" },
    { x: 220, y: 282, anchor: "middle" },
    { x: 118, y: 201, anchor: "end" },
    { x: 118, y: 96, anchor: "end" }
  ];
  const lowest = axes.reduce((low, axis) => (axis.score < low.score ? axis : low), axes[0]);
  return (
    <div className="pf-panel">
      <h2 className="sect">How spread out your portfolio is</h2>
      <p className="sect-sub" style={{ maxWidth: 700 }}>Six measurements, each on a scale whose two ends are printed beside it. There is no total and no grade — six numbers stay six numbers, because averaging them would be an opinion about your portfolio dressed up as arithmetic.</p>
      <div className="panel-block" style={{ marginBottom: 26 }}>
        <div className="pf-hex-layout">
          <svg height="310" style={{ display: "block", flex: "none", maxWidth: "100%" }} viewBox="0 0 440 310" width="440">
            <polygon fill="#f5f3ed" points={gridPoints(radius)} stroke="#c2bfb5" strokeWidth="1" />
            <polygon fill="none" points={gridPoints(radius * 0.75)} stroke="#dde3e1" strokeWidth="1" />
            <polygon fill="none" points={gridPoints(radius * 0.5)} stroke="#dde3e1" strokeWidth="1" />
            <polygon fill="none" points={gridPoints(radius * 0.25)} stroke="#dde3e1" strokeWidth="1" />
            {Array.from({ length: 6 }, (_, index) => {
              const angle = -Math.PI / 2 + (index * Math.PI) / 3;
              return <line key={index} stroke="#dde3e1" strokeWidth="1" x1={cx} x2={(cx + radius * Math.cos(angle)).toFixed(2)} y1={cy} y2={(cy + radius * Math.sin(angle)).toFixed(2)} />;
            })}
            <polygon fill="rgba(21,23,25,0.12)" points={pfHexPoints(axes.map((axis) => axis.score), cx, cy, radius)} stroke="#151719" strokeWidth="2" />
            {axes.map((axis, index) => {
              const vertex = pfHexVertex(index, cx, cy, radius, axis.score);
              return <circle cx={vertex.x.toFixed(2)} cy={vertex.y.toFixed(2)} fill={axis === lowest ? "#c4312c" : "#151719"} key={axis.label} r="4" />;
            })}
            {axes.map((axis, index) => {
              const anchor = labelAnchors[index];
              return (
                <g key={axis.label}>
                  <text fill="#151719" fontFamily="Instrument Sans, Arial, sans-serif" fontSize="12" fontWeight="600" textAnchor={anchor.anchor} x={anchor.x} y={anchor.y}>{axis.label}</text>
                  <text fill={axis === lowest ? "#c4312c" : "#151719"} fontFamily="Instrument Sans, Arial, sans-serif" fontSize="13" fontWeight="700" textAnchor={anchor.anchor} x={anchor.x} y={anchor.y + 16}>{axis.score}</text>
                </g>
              );
            })}
          </svg>
          <div style={{ flex: 1, minWidth: 0, paddingTop: 4 }}>
            <div className="microlabel" style={{ marginBottom: 14 }}>What each number is, and what its ends mean</div>
            <div style={{ display: "flex", flexDirection: "column", fontSize: 13 }}>
              {axes.map((axis, index) => (
                <div key={axis.label} style={{ borderBottom: index === axes.length - 1 ? "1px solid #e4e1d8" : undefined, borderTop: "1px solid #e4e1d8", padding: "9px 0" }}>
                  <div style={{ alignItems: "baseline", display: "flex" }}>
                    <span style={{ color: axis === lowest ? "#c4312c" : undefined, fontWeight: 600 }}>{axis.label}</span>
                    <span className="leader" style={{ margin: "0 8px 4px" }} />
                    <span className="num" style={{ color: axis === lowest ? "#c4312c" : undefined, fontWeight: 700 }}>{axis.score}</span>
                  </div>
                  <div style={{ color: "#626b70", lineHeight: 1.5, marginTop: 3 }}>{axis.sentence}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="serif-note" style={{ borderTop: "1px solid #dde3e1", marginTop: 26, maxWidth: 820, paddingTop: 20 }}>
          <span style={{ fontSize: 17 }}>None of this knows whether a borrower will pay, whether a valuation is right, or what the franc does. A full hexagon is not a safe portfolio — it is a well-spread one.</span>
        </div>
      </div>
    </div>
  );
}

function PfCollateralPanel({ currency, holdingCount, segments, totalMinor }: { currency: string; holdingCount: number; segments: { label: string; amount: number; color: string; bad?: boolean }[]; totalMinor: number }) {
  const [view, setView] = useState<"bar" | "ring">("ring");
  return (
    <div className="pf-panel">
      <div className="pf-sect-row">
        <div style={{ flex: 1 }}>
          <h2 className="sect">What stands behind your money</h2>
          <p className="pf-sect-note">Each loan counted once, by its principal asset — so the types add up to {pfWholeLabel(currency, totalMinor)}.</p>
        </div>
        <div className="seg">
          <button className={view === "bar" ? "on" : ""} onClick={() => setView("bar")} type="button">Bar</button>
          <button className={view === "ring" ? "on" : ""} onClick={() => setView("ring")} type="button">Ring</button>
        </div>
      </div>
      <div className="panel-block" style={{ marginBottom: 26, padding: "26px 30px 24px" }}>
        {view === "bar" ? (
          <div style={{ borderRadius: 3, display: "flex", height: 34, marginBottom: 12, overflow: "hidden" }}>
            {segments.map((segment) => {
              const pct = totalMinor > 0 ? (segment.amount / totalMinor) * 100 : 0;
              return (
                <div key={segment.label} style={{ alignItems: "center", background: segment.color, display: "flex", padding: pct > 12 ? "0 14px" : "0 6px", width: `${pct.toFixed(1)}%` }}>
                  {pct > 18 ? <span style={{ color: "#f5f3ed", fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap" }}>{segment.label}</span> : null}
                  <span className="grow" />
                  {pct > 10 ? <span className="num" style={{ color: "#f5f3ed", fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap" }}>{pfWholeLabel(currency, segment.amount)}</span> : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="pf-collateral-ring-layout">
            <PfRing center={{ title: pfWholeLabel(currency, totalMinor), sub: `${holdingCount} loans` }} radius={60} segments={segments} size={200} stroke={34} total={totalMinor} />
            <div style={{ display: "flex", flex: 1, flexDirection: "column", fontSize: 13.5 }}>
              {segments.map((segment, index) => (
                <div key={segment.label} style={{ alignItems: "baseline", borderBottom: index === segments.length - 1 ? "1px solid #e4e1d8" : undefined, borderTop: "1px solid #e4e1d8", display: "flex", gap: 12, padding: "8px 0" }}>
                  <span style={{ background: segment.color, borderRadius: 2, flex: "none", height: 11, width: 11 }} />
                  <span style={{ color: segment.bad ? "#c4312c" : undefined, fontWeight: 500 }}>{segment.label}</span>
                  <span className="leader" style={{ margin: "0 6px 4px" }} />
                  <span className="num" style={{ color: "#626b70", marginRight: 14 }}>{totalMinor > 0 ? `${((segment.amount / totalMinor) * 100).toFixed(1)}%` : "-"}</span>
                  <span className="num" style={{ color: segment.bad ? "#c4312c" : undefined, fontWeight: 600 }}>{pfWholeLabel(currency, segment.amount)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function PfProtectionPanel({ currency, defaultInterestBps, holdingCount, lateCount, lateMinor, securedLtvs, unsecuredCount, unsecuredMinor, weightedLtv }: { currency: string; defaultInterestBps: number[]; holdingCount: number; lateCount: number; lateMinor: number; securedLtvs: number[]; unsecuredCount: number; unsecuredMinor: number; weightedLtv: number | null }) {
  const ltvLabel = weightedLtv === null ? "—" : `${weightedLtv.toFixed(1)}%`;
  const rangeLabel = securedLtvs.length > 0 ? `${Math.min(...securedLtvs).toFixed(0)} – ${Math.max(...securedLtvs).toFixed(0)}% of valuation` : "—";
  const defaultInterestLabel = pfDefaultInterestLabel(defaultInterestBps);
  return (
    <div className="pf-panel">
      <h2 className="sect">What protects your money</h2>
      <p className="sect-sub" style={{ maxWidth: 720 }}>Collateral and contractual recovery terms may reduce a loss, but neither guarantees repayment. Each project has its own disclosed terms and recovery evidence.</p>
      <div className="panel-block pf-risk-block">
        <div className="pf-risk-grid">
          <div style={{ paddingRight: 6 }}>
            <div className="pf-risk-cap">The first is disclosed collateral cover</div>
            <div className="pf-risk-copy">For loans with a disclosed loan-to-value ratio, BANXUM shows how much was lent relative to the stated collateral valuation. A lower LTV means more valuation headroom, but valuations and enforcement proceeds can change and may not cover the loan.</div>
            <div style={{ alignItems: "baseline", color: "#626b70", display: "flex", fontSize: 11.5, marginBottom: 6 }}><span>Disclosed collateral valuation</span><span className="grow" /><span className="num" style={{ color: "#151719", fontWeight: 600 }}>100%</span></div>
            <div style={{ border: "1.5px solid #c2bfb5", borderRadius: 3, height: 34, overflow: "hidden", position: "relative" }}>
              <div style={{ background: "#151719", bottom: 0, left: 0, position: "absolute", top: 0, width: `${weightedLtv === null ? 0 : weightedLtv.toFixed(1)}%` }} />
              <div style={{ alignItems: "center", bottom: 0, display: "flex", justifyContent: "center", left: `${weightedLtv === null ? 0 : weightedLtv.toFixed(1)}%`, position: "absolute", right: 0, top: 0 }}><span style={{ color: "#626b70", fontSize: 11, fontWeight: 600 }}>headroom</span></div>
            </div>
            <div style={{ alignItems: "baseline", display: "flex", fontSize: 11.5, marginTop: 6 }}><span style={{ color: "#151719", fontWeight: 600 }}>Weighted LTV {ltvLabel}</span><span className="grow" /><span style={{ color: "#626b70" }}>{weightedLtv === null ? "" : `${(100 - weightedLtv).toFixed(1)}% valuation headroom`}</span></div>
            <div style={{ color: "#626b70", fontSize: 12.5, lineHeight: 1.5, marginTop: 14 }}>Weighted only across secured holdings with a disclosed LTV. Per-project disclosed LTV ranges from {securedLtvs.length > 0 ? `${Math.min(...securedLtvs).toFixed(0)}% to ${Math.max(...securedLtvs).toFixed(0)}%` : "not available"}.</div>
          </div>
          <div style={{ borderLeft: "1px solid #e4e1d8", paddingLeft: 6 }}>
            <div className="pf-risk-cap">The second is the recovery contract</div>
            <div className="pf-risk-copy">Every borrower payment follows the same non-overridable order. Garanta legal costs and the approved recovery fee are satisfied first, then penalties, contractual interest and finally principal. Recovery timing or proceeds are never guaranteed.</div>
            <div style={{ alignItems: "baseline", color: "#626b70", display: "flex", fontSize: 11.5, marginBottom: 6 }}><span>Universal borrower-payment and recovery order</span></div>
            <div style={{ border: "1.5px solid #c2bfb5", borderRadius: 3, display: "flex", height: 34, overflow: "hidden" }}>
              <div style={{ alignItems: "center", background: "#151719", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#f5f3ed", fontSize: 10.5, fontWeight: 600 }}>1</span></div>
              <div style={{ alignItems: "center", background: "#4a5257", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#f5f3ed", fontSize: 10.5, fontWeight: 600 }}>2</span></div>
              <div style={{ alignItems: "center", background: "#9ca5a8", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#151719", fontSize: 10.5, fontWeight: 600 }}>3</span></div>
              <div style={{ alignItems: "center", background: "#dde3e1", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#626b70", fontSize: 10.5, fontWeight: 600 }}>4</span></div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", fontSize: 11.5, gap: 5, marginTop: 9 }}>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#151719", borderRadius: 2, flex: "none", height: 9, width: 9 }} /><span style={{ color: "#292d30", flex: 1 }}>Garanta legal costs and recovery fee</span></div>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#4a5257", borderRadius: 2, flex: "none", height: 9, width: 9 }} /><span style={{ color: "#292d30", flex: 1 }}>Penalty and default interest</span></div>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#9ca5a8", borderRadius: 2, flex: "none", height: 9, width: 9 }} /><span style={{ color: "#292d30", flex: 1 }}>Contractual interest</span></div>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#dde3e1", border: "1px solid #c2bfb5", borderRadius: 2, flex: "none", height: 9, width: 9 }} /><span style={{ color: "#292d30", flex: 1 }}>Principal</span></div>
            </div>
            <div style={{ color: "#626b70", fontSize: 12.5, lineHeight: 1.5, marginTop: 14 }}>Widths show sequence only, not expected amounts. Principal is never paid while an earlier tier remains due. Configured default interest across these loans is {defaultInterestLabel}.</div>
          </div>
        </div>
        <div className="pf-risk-kvs">
          <div className="kv-row"><span className="k">Configured default interest across your loans</span><span className="leader" /><span className="v">{defaultInterestLabel}</span></div>
          <div className="kv-row"><span className="k">Disclosed LTV range across your loans</span><span className="leader" /><span className="v">{rangeLabel}</span></div>
          <div className="kv-row"><span className="k">Weighted LTV across disclosed secured holdings</span><span className="leader" /><span className="v">{weightedLtv === null ? "—" : `${weightedLtv.toFixed(1)}% of valuation`}</span></div>
          <div className="kv-row"><span className="k">Loans with no asset pledged</span><span className="leader" /><span className="v">{unsecuredCount} of {holdingCount}{unsecuredCount > 0 ? ` · ${pfWholeLabel(currency, unsecuredMinor)}` : ""}</span></div>
          <div className="kv-row"><span className="k">Recovery timing</span><span className="leader" /><span className="v">Project-specific; not guaranteed</span></div>
          <div className="kv-row"><span className="k">In arrears right now</span><span className="leader" /><span className="v" style={{ color: lateCount > 0 ? "#c4312c" : undefined }}>{lateCount} of {holdingCount}{lateCount > 0 ? ` · ${pfWholeLabel(currency, lateMinor)}` : ""}</span></div>
        </div>
        <div style={{ color: "#626b70", fontSize: 13, lineHeight: 1.55, maxWidth: 820 }}>Open any loan above to review its disclosed collateral, LTV, agreement terms, public risk notes and repayment schedule. These figures describe current records, not guaranteed recovery value.</div>
      </div>
    </div>
  );
}

function activityCategory(entry: ActivityEntry) {
  if (entry.activity_type === "primary_order") return "order";
  if (entry.activity_type === "fx_exchange") return "fx";
  if (entry.activity_type === "withdrawal_request") return "withdrawal";
  if (entry.activity_type === "repayment_distribution") return "income";
  if (entry.activity_type === "recovery_distribution") return "recovery";
  if (entry.activity_type === "secondary_listing") return "listing";
  if (entry.activity_type === "secondary_purchase") return "purchase";
  if (entry.activity_type === "secondary_sale") return "sale";
  if (entry.activity_type.startsWith("balance_")) {
    return entry.activity_type.replace("balance_", "").replaceAll("_", " ");
  }
  return safeMetadataCategory(entry.metadata);
}

function ActivityAmount({ entry }: { entry: ActivityEntry }) {
  if (entry.amount_minor === 0 || entry.amount_minor === null) {
    return <span className="muted">-</span>;
  }
  const absoluteAmount = Math.abs(entry.amount_minor);
  const sign = entry.direction === "in" ? "+" : entry.direction === "out" ? "-" : "";
  const toneClass = entry.direction === "in" ? "pos" : entry.direction === "out" ? "neg" : "";
  return (
    <span className={`money ${toneClass}`}>
      <span className="muted">{entry.currency} </span>
      {sign}
      {formatMoneyMinor(absoluteAmount, entry.currency)}
    </span>
  );
}

function ActivityTable({ entries, dense = false }: { entries: ActivityEntry[]; dense?: boolean }) {
  return (
    <section className="pf-data-section">
      <header className="pf-data-heading">
        <h2 className="sect">Activity</h2>
        <p>Every deposit, investment, repayment, FX conversion and market event in one timeline.</p>
      </header>
      {entries.length === 0 ? (
        <PortfolioEmptyState icon="clock" title="No activity yet">
          Deposits, investments, repayments, FX, and secondary-market activity will appear here.
        </PortfolioEmptyState>
      ) : (
      <div className="pf-data-table-wrap">
        <table className={`pf-data-table pf-activity-table ${dense ? "dense" : ""}`}>
          <thead><tr><th>Date</th><th>Activity</th><th>Reference</th><th>Type</th><th className="num">Amount</th></tr></thead>
          <tbody>
            {entries.map((entry) => {
              const category = activityCategory(entry);
              return (
                <tr key={entry.id}>
                  <td className="mono muted" style={{ fontSize: 12 }}>{formatDateTime(entry.occurred_at)}</td>
                  <td className="col-strong">{entry.title}</td>
                  <td className="sub mono">{entry.loan_title || humanizeToken(entry.activity_type) || "-"}</td>
                  <td><ActivityTag category={category} /></td>
                  <td className="num"><ActivityAmount entry={entry} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}
    </section>
  );
}

function ActivityTag({ category }: { category: string }) {
  const tone = category === "income" || category === "deposit" || category === "sale" || category === "recovery" ? "ok" : category === "cost" || category === "withdrawal" || category === "purchase" ? "bad" : category === "status" || category === "order" || category === "listing" ? "warn" : "neutral";
  return <Chip dot={false} tone={tone}>{category}</Chip>;
}

const primaryOrderStatusTooltips: Record<string, string> = {
  pending: "Your order has been recorded, but no balance has been reserved yet. Allocation is first-come, first-served and depends on eligible balance and remaining loan capacity.",
  pending_allocation: "Your order has been recorded, but no balance has been reserved yet. Allocation is first-come, first-served and depends on eligible balance and remaining loan capacity.",
  partially_allocated: "Only part of the requested amount has been reserved, usually because less loan capacity remained. Only the allocated amount can become invested when funding closes.",
  balance_allocated: "The allocated amount is reserved from your balance for this loan. It becomes an investment and a portfolio holding only when the loan funding closes successfully.",
  balance_released: "Balance was previously reserved for this order, then released before funding closed. The Allocated column is historical; the released amount returned to your available balance and no holding was created.",
  closed_invested: "The loan funding closed with this order included. The allocated amount became a loan holding in your portfolio.",
  closed_not_invested: "The order closed without any balance being allocated, or no capacity remained when it was processed. No funds were reserved and no portfolio holding was created."
};

function compactOrderId(id: string) {
  const value = id.trim();
  return value.length > 8 ? `${value.slice(0, 4)}...` : value;
}

function OrdersTable({ onBrowse, orders }: { onBrowse: () => void; orders: PrimaryOrderPortal[] }) {
  return (
    <section className="pf-data-section">
      <header className="pf-data-heading">
        <h2 className="sect">Orders</h2>
        <p>Track each investment intent from submission through allocation, release, or funding close.</p>
      </header>
      {orders.length === 0 ? (
        <PortfolioEmptyState action={<Button size="sm" onClick={onBrowse}>Browse marketplace</Button>} icon="market" title="No primary orders">
          Investment intents will appear here after you place an order.
        </PortfolioEmptyState>
      ) : (
        <div className="pf-data-table-wrap">
          <table className="pf-data-table pf-orders-table">
            <thead><tr><th>Order</th><th>Loan</th><th className="num">Requested</th><th className="num">Allocated</th><th>Placed</th><th>Status</th></tr></thead>
            <tbody>
              {orders.map((order, index) => (
                <tr key={order.id}>
                  <td>
                    <span className="pf-order-reference">
                      <span className="pf-order-number">#{index + 1}</span>
                      <span className="mono pf-order-id">{compactOrderId(order.id)}</span>
                      <CopyIdButton ariaLabel="Copy order ID" iconOnly id={order.id} label="Copy order ID" />
                    </span>
                  </td>
                  <td>
                    <span className="pf-order-loan">
                      <strong>{order.loan_title}</strong>
                      <CopyIdButton ariaLabel="Copy loan ID" iconOnly id={order.loan_id} label="Copy loan ID" />
                    </span>
                  </td>
                  <td className="num"><Money amountMinor={order.requested_amount_minor} currency={order.currency} /></td>
                  <td className="num">{order.allocated_amount_minor > 0 ? <Money amountMinor={order.allocated_amount_minor} currency={order.currency} /> : <span className="muted">-</span>}</td>
                  <td className="mono muted">{formatDateTime(order.created_at)}</td>
                  <td><Chip status={order.status} tooltip={primaryOrderStatusTooltips[order.status]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function LoanSchedulePanels({
  currency,
  currentPrincipalMinor,
  investmentSchedule,
  loanSchedule,
  loanStatus,
  projectionBannerTitle = "Projection from your current holding",
  projectionDescription,
  projectionTitle = "Your investment schedule",
  scheduleVersion
}: {
  currency: string;
  currentPrincipalMinor: number;
  investmentSchedule: SecondaryMarketInvestmentInstallment[];
  loanSchedule: SecondaryMarketLoanInstallment[];
  loanStatus: string;
  projectionBannerTitle?: string;
  projectionDescription: ReactNode;
  projectionTitle?: string;
  scheduleVersion: number;
}) {
  const [scheduleTab, setScheduleTab] = useState<"investment" | "loan">("investment");
  const contractualProjectionUnavailable = ["defaulted", "written_off"].includes(loanStatus);
  const projectedTotals = investmentSchedule.reduce(
    (totals, row) => ({
      principal: totals.principal + row.projected_principal_minor,
      interest: totals.interest + row.projected_interest_minor,
      total: totals.total + row.projected_total_minor
    }),
    { principal: 0, interest: 0, total: 0 }
  );
  const fullScheduleTotals = loanSchedule.reduce(
    (totals, row) => ({
      principal: totals.principal + row.principal_minor,
      interest: totals.interest + row.interest_minor,
      total: totals.total + row.total_minor,
      paid: totals.paid + row.paid_principal_minor + row.paid_interest_minor,
      outstanding: totals.outstanding + row.outstanding_total_minor
    }),
    { principal: 0, interest: 0, total: 0, paid: 0, outstanding: 0 }
  );

  return (
    <section className="holding-schedule">
      <Tabs
        onChange={setScheduleTab}
        tabs={[
          { value: "investment", label: projectionTitle },
          { value: "loan", label: "Full loan schedule" }
        ]}
        value={scheduleTab}
      />
      {scheduleTab === "investment" ? (
        <div className="col gap-16 holding-schedule-panel" role="tabpanel">
          <div className="grid grid-3">
            <Card padded><Stat amountMinor={currentPrincipalMinor} currency={currency} label="Outstanding principal" /></Card>
            <Card padded><Stat amountMinor={projectedTotals.interest} currency={currency} label="Projected remaining interest" /></Card>
            <Card padded><Stat amountMinor={projectedTotals.total} currency={currency} label="Projected repayments" /></Card>
          </div>
          <Banner tone="neutral" title={projectionBannerTitle}>
            {projectionDescription}
          </Banner>
          {investmentSchedule.length === 0 ? (
            contractualProjectionUnavailable ? (
              <Banner tone="warn" title="Contractual projection no longer applies">
                This loan is in a non-performing or loss-resolution state, so its original contractual dates are not a reliable projection of future payments. Review public recovery updates and credited recoveries instead.
              </Banner>
            ) : currentPrincipalMinor > 0 ? (
              <Banner tone="bad" title="Investment projection unavailable">
                The current claim could not be reconciled to the active loan schedule. No estimated cash flows are shown. Contact support if this persists.
              </Banner>
            ) : (
              <Card className="section"><Empty icon="clock" title="No outstanding scheduled payments">This claim has no projected remaining contractual payments.</Empty></Card>
            )
          ) : (
            <Card className="section">
              <div className="tbl-wrap">
                <table className="tbl investment-schedule-table">
                  <thead>
                    <tr><th>#</th><th>Due date</th><th>Status</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Projected payment</th></tr>
                  </thead>
                  <tbody>
                    {investmentSchedule.map((row) => {
                      const tone = row.status === "overdue" ? "bad" : row.status === "due" ? "warn" : "neutral";
                      return (
                        <tr key={row.loan_installment_id}>
                          <td className="mono">{row.installment_number}</td>
                          <td>{formatDate(row.due_date)}</td>
                          <td><Chip dot={false} tone={tone}>{humanizeToken(row.status)}</Chip></td>
                          <td className="num"><Money amountMinor={row.projected_principal_minor} currency={currency} /></td>
                          <td className="num"><Money amountMinor={row.projected_interest_minor} currency={currency} /></td>
                          <td className="num col-strong"><Money amountMinor={row.projected_total_minor} currency={currency} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot className="schedule-totals">
                    <tr>
                      <th colSpan={3}>Totals</th>
                      <th className="num"><Money amountMinor={projectedTotals.principal} currency={currency} /></th>
                      <th className="num"><Money amountMinor={projectedTotals.interest} currency={currency} /></th>
                      <th className="num"><Money amountMinor={projectedTotals.total} currency={currency} /></th>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </Card>
          )}
        </div>
      ) : (
        <div className="col gap-16 holding-schedule-panel" role="tabpanel">
          <div className="section-head">
            <div><h2>Full loan schedule</h2><div className="ph-sub">Recorded payment history plus current future schedule, active version {scheduleVersion}.</div></div>
          </div>
          <Banner tone="neutral" title="Whole-loan borrower obligations">
            Past rows are immutable borrower payment records. Remaining rows come from the latest regenerated loan schedule. They are not the cash flows for only this claim.
          </Banner>
          {loanSchedule.length === 0 ? (
            <Card className="section"><Empty icon="clock" title="Schedule unavailable">No current repayment schedule rows are available for this loan.</Empty></Card>
          ) : (
            <Card className="section">
              <div className="tbl-wrap">
                <table className="tbl holding-schedule-table">
                  <thead>
                    <tr><th>Entry</th><th>Date</th><th>Status</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Instalment</th><th className="num">Paid</th><th className="num">Outstanding</th></tr>
                  </thead>
                  <tbody>
                    {loanSchedule.map((row) => {
                      const paidMinor = row.paid_principal_minor + row.paid_interest_minor;
                      const tone = ["paid", "paid_in_advance"].includes(row.status) ? "ok" : row.status === "overdue" ? "bad" : row.status === "due" ? "warn" : "neutral";
                      const displayDate = row.row_type === "repayment_event" && row.payment_date ? row.payment_date : row.due_date;
                      return (
                        <tr key={row.id}>
                          <td>{row.label}</td>
                          <td>{formatDate(displayDate)}</td>
                          <td><Chip dot={false} tone={tone}>{humanizeToken(row.status)}</Chip></td>
                          <td className="num"><Money amountMinor={row.principal_minor} currency={currency} /></td>
                          <td className="num"><Money amountMinor={row.interest_minor} currency={currency} /></td>
                          <td className="num col-strong"><Money amountMinor={row.total_minor} currency={currency} /></td>
                          <td className="num"><Money amountMinor={paidMinor} currency={currency} /></td>
                          <td className="num"><Money amountMinor={row.outstanding_total_minor} currency={currency} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot className="schedule-totals">
                    <tr>
                      <th colSpan={3}>Totals</th>
                      <th className="num"><Money amountMinor={fullScheduleTotals.principal} currency={currency} /></th>
                      <th className="num"><Money amountMinor={fullScheduleTotals.interest} currency={currency} /></th>
                      <th className="num"><Money amountMinor={fullScheduleTotals.total} currency={currency} /></th>
                      <th className="num"><Money amountMinor={fullScheduleTotals.paid} currency={currency} /></th>
                      <th className="num"><Money amountMinor={fullScheduleTotals.outstanding} currency={currency} /></th>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </section>
  );
}

function HoldingDetail({ holding, onClose, setRoute }: { holding: Holding; onClose: () => void; setRoute: (route: AppRoute) => void }) {
  const loan = holding.loan;
  const currency = holding.currency;
  const listingAction = secondaryListingAction(loan.loan_status);
  const hasOpenListing = holding.open_secondary_listing !== null;
  const canOpenSecondaryAction = hasOpenListing || listingAction.allowed;
  const timelineRows = [...loan.schedule].sort((left, right) => {
    const leftDate = left.payment_date ?? left.due_date;
    const rightDate = right.payment_date ?? right.due_date;
    return leftDate.localeCompare(rightDate) || left.installment_number - right.installment_number;
  });
  const projectedRows = [...holding.investment_schedule].sort(
    (left, right) => left.due_date.localeCompare(right.due_date) || left.installment_number - right.installment_number
  );
  const firstProjected = projectedRows[0];
  const defaultSelectedKey = firstProjected
    ? `projection:${firstProjected.loan_installment_id}`
    : timelineRows.length > 0
      ? `loan:${timelineRows[timelineRows.length - 1].id}`
      : "";
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [selectedPaymentKey, setSelectedPaymentKey] = useState(defaultSelectedKey);
  const selectedProjection = projectedRows.find(
    (row) => `projection:${row.loan_installment_id}` === selectedPaymentKey
  ) ?? null;
  const selectedLoanRow = selectedProjection
    ? timelineRows.find(
        (row) => row.installment_number === selectedProjection.installment_number && row.due_date === selectedProjection.due_date
      ) ?? null
    : timelineRows.find((row) => `loan:${row.id}` === selectedPaymentKey) ?? null;
  const isPaidRow = (row: (typeof timelineRows)[number]) =>
    row.is_paid || ["paid", "paid_in_advance"].includes(row.status);
  const paidRows = timelineRows.filter(isPaidRow);
  const progressPercent = timelineRows.length === 0 ? 0 : (paidRows.length / timelineRows.length) * 100;
  const years = Array.from(new Set(timelineRows.map((row) => Number((row.payment_date ?? row.due_date).slice(0, 4))))).sort();
  const selectedProjectionIndex = selectedProjection
    ? projectedRows.findIndex((row) => row.loan_installment_id === selectedProjection.loan_installment_id)
    : -1;
  const projectedBalanceAfter = selectedProjectionIndex >= 0
    ? Math.max(
        0,
        holding.current_principal_minor - projectedRows
          .slice(0, selectedProjectionIndex + 1)
          .reduce((sum, row) => sum + row.projected_principal_minor, 0)
      )
    : null;
  const selectedPrincipalMinor = selectedProjection?.projected_principal_minor ?? selectedLoanRow?.principal_minor ?? 0;
  const selectedInterestMinor = selectedProjection?.projected_interest_minor ?? selectedLoanRow?.interest_minor ?? 0;
  const selectedTotalMinor = selectedProjection?.projected_total_minor ?? selectedLoanRow?.total_minor ?? 0;
  const selectedInterestPercent = selectedTotalMinor > 0 ? (selectedInterestMinor / selectedTotalMinor) * 100 : 0;
  const earnedInterestMinor = holding.received_interest_minor
    + holding.recovered_contractual_interest_minor
    + holding.recovered_default_interest_minor;
  const projectedInterestMinor = projectedRows.reduce((sum, row) => sum + row.projected_interest_minor, 0);
  const lifetimeInterestMinor = earnedInterestMinor + projectedInterestMinor;
  const receivedInterestPercent = lifetimeInterestMinor > 0 ? (earnedInterestMinor / lifetimeInterestMinor) * 100 : 0;
  const capitalReturnedMinor = Math.max(0, holding.original_principal_minor - holding.current_principal_minor);
  const capitalReturnedPercent = holding.original_principal_minor > 0
    ? (capitalReturnedMinor / holding.original_principal_minor) * 100
    : 0;
  const recoveryTotalMinor = holding.recovered_principal_minor
    + holding.recovered_contractual_interest_minor
    + holding.recovered_default_interest_minor
    + holding.recovered_penalties_minor
    + holding.recovered_other_costs_minor;
  const impaired = ["late", "defaulted", "written_off"].includes(loan.loan_status);
  const collateralValueMinor = loan.collateral_value_minor;
  const collateralDescription = loan.collateral_description || humanizeToken(loan.collateral_type);
  const ltvPercent = loan.ltv_bps === null ? null : loan.ltv_bps / 100;
  const futureTotals = projectedRows.reduce(
    (totals, row) => ({
      principal: totals.principal + row.projected_principal_minor,
      interest: totals.interest + row.projected_interest_minor,
      total: totals.total + row.projected_total_minor
    }),
    { principal: 0, interest: 0, total: 0 }
  );
  const selectedDate = selectedProjection?.due_date ?? selectedLoanRow?.payment_date ?? selectedLoanRow?.due_date ?? "";
  const selectedStatus = selectedProjection?.status ?? selectedLoanRow?.status ?? "unavailable";
  const paymentCell = (year: number, month: number) => {
    const row = timelineRows.find((candidate) => {
      const date = candidate.payment_date ?? candidate.due_date;
      return Number(date.slice(0, 4)) === year && Number(date.slice(5, 7)) === month;
    });
    if (!row) return <span aria-hidden="true" className="holding-v9-payment-cell empty" key={`${year}-${month}`} />;
    const projection = projectedRows.find(
      (candidate) => candidate.installment_number === row.installment_number && candidate.due_date === row.due_date
    );
    const key = projection ? `projection:${projection.loan_installment_id}` : `loan:${row.id}`;
    const state = isPaidRow(row) ? "paid" : row.status === "overdue" ? "overdue" : projection === firstProjected ? "next" : "future";
    return (
      <button
        aria-label={`${formatDate(row.payment_date ?? row.due_date)}, ${humanizeToken(row.status)}`}
        className={`holding-v9-payment-cell ${state} ${selectedPaymentKey === key ? "selected" : ""}`}
        key={`${year}-${month}`}
        onClick={() => setSelectedPaymentKey(key)}
        title={`${row.label}: ${humanizeToken(row.status)}`}
        type="button"
      >
        {isPaidRow(row) ? "Paid" : row.installment_number}
      </button>
    );
  };
  return (
    <Modal
      xwide
      footer={<>
        <span className="holding-v9-footer-copy">
          {hasOpenListing
            ? "This position already has an open secondary-market listing."
            : listingAction.allowed
              ? "You can offer the full current claim on the secondary market."
              : listingAction.hint}
        </span>
        <Button variant="ghost" onClick={() => setScheduleOpen((open) => !open)}>
          {scheduleOpen ? "Hide schedule" : "View schedule"}
        </Button>
        <Button disabled={!canOpenSecondaryAction} icon="secondary" title={!canOpenSecondaryAction ? listingAction.hint : undefined} variant="primary" onClick={() => { onClose(); goTo(setRoute, "secondary", { tab: "sell" }); }}>
          {hasOpenListing ? "Manage secondary listing" : listingAction.label}
        </Button>
      </>}
      onClose={onClose}
      title={loan.loan_title}
    >
      <article className="holding-v9">
        <header className="holding-v9-intro">
          <div className="eyebrow">{humanizeToken(loan.purpose)} · yours since {formatDate(holding.assignment_effective_at)}</div>
          <div className="holding-v9-heading-row">
            <div>
              <h2>{loan.borrower_name}</h2>
              <p>{formatRateBps(loan.yield_bps)} annual yield · {humanizeToken(loan.repayment_type)} · {loan.term_months} months</p>
            </div>
            <div className="row gap-8 wrap">
              <Chip status={loan.loan_status} tone={statusTone(loan.loan_status)} />
              {holding.open_secondary_listing ? <Chip status={listingStatusLabel(holding.open_secondary_listing.status)} tone={holding.open_secondary_listing.status === "active" ? "ok" : "warn"} tooltip={listingStatusTooltip(holding.open_secondary_listing.status, loan.loan_status)} /> : null}
              <Rating value={loan.risk_rating} />
              <Country code={loan.borrower_country} />
              <CopyIdButton ariaLabel="Copy loan ID" iconOnly id={loan.loan_id} label="Copy loan ID" />
            </div>
          </div>
        </header>

        <section className="holding-v9-progress">
          <button aria-expanded={timelineOpen} className="holding-v9-progress-toggle" onClick={() => setTimelineOpen((open) => !open)} type="button">
            <span><strong>{paidRows.length} of {timelineRows.length}</strong> scheduled borrower payments recorded</span>
            <span>{timelineOpen ? "Hide timeline" : "Open timeline"}</span>
          </button>
          <div aria-label={`${progressPercent.toFixed(0)}% of scheduled payments recorded`} className="holding-v9-progress-bar" role="img">
            <span style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }} />
          </div>
          {timelineOpen ? (
            timelineRows.length === 0 ? (
              <Empty icon="clock" title="Payment timeline unavailable">No borrower schedule rows are available for this position.</Empty>
            ) : (
              <div className="holding-v9-timeline-wrap">
                <div className="holding-v9-timeline" role="group" aria-label="Borrower payment timeline">
                  <div className="holding-v9-year-label" />
                  {Array.from({ length: 12 }, (_, index) => <span className="holding-v9-month-label" key={index}>{new Date(2026, index, 1).toLocaleString("en", { month: "short" })}</span>)}
                  {years.flatMap((year) => [
                    <strong className="holding-v9-year-label" key={`${year}-label`}>{year}</strong>,
                    ...Array.from({ length: 12 }, (_, index) => paymentCell(year, index + 1))
                  ])}
                </div>
                <div className="holding-v9-legend">
                  <span><i className="paid" />Paid</span><span><i className="next" />Next</span><span><i className="future" />Future</span><span><i className="overdue" />Overdue</span>
                </div>
              </div>
            )
          ) : null}
        </section>

        <section className="holding-v9-stats" aria-label="Position summary">
          <div><span>Interest received</span><strong><Money amountMinor={earnedInterestMinor} currency={currency} /></strong><small>contractual and recorded recovery interest</small></div>
          <div><span>Projected still to earn</span><strong><Money amountMinor={projectedInterestMinor} currency={currency} /></strong><small>across {projectedRows.length} remaining payments</small></div>
          <div><span>Capital returned</span><strong><Money amountMinor={capitalReturnedMinor} currency={currency} /></strong><small>{capitalReturnedPercent.toFixed(1)}% of your original claim</small></div>
          <div><span>Still owed to you</span><strong><Money amountMinor={holding.current_principal_minor} currency={currency} /></strong><small>current outstanding principal</small></div>
        </section>
        <div className="holding-v9-lifetime">
          Of the <strong><Money amountMinor={lifetimeInterestMinor} currency={currency} /></strong> of contractual and recorded recovery interest represented here, <strong>{receivedInterestPercent.toFixed(1)}%</strong> has been received. Future interest is projected, not guaranteed.
        </div>

        {impaired ? (
          <section className="holding-v9-impaired">
            <div><strong>{humanizeToken(loan.loan_status)}</strong>{loan.days_past_due > 0 ? ` · ${loan.days_past_due} days past due` : ""}</div>
            <p>
              {loan.default_penalty_interest_bps > 0
                ? `The loan terms specify a ${formatRateBps(loan.default_penalty_interest_bps)} annual default-interest rate. Any amount shown as received is based on recorded servicing or recovery evidence; BANXUM does not estimate accrued default interest from days past due.`
                : "No non-zero default-interest rate is configured for this loan. Review recorded servicing and recovery evidence for amounts actually credited."}
            </p>
          </section>
        ) : null}

        <section className="holding-v9-detail-grid">
          <div className="holding-v9-payment-detail">
            <div className="holding-v9-section-head">
              <div><span>Selected payment</span><strong>{selectedDate ? formatDate(selectedDate) : "Unavailable"}</strong></div>
              <Chip dot={false} tone={selectedStatus === "overdue" ? "bad" : selectedStatus === "due" ? "warn" : selectedStatus === "paid" ? "ok" : "neutral"}>{humanizeToken(selectedStatus)}</Chip>
            </div>
            {selectedProjection || selectedLoanRow ? (
              <>
                <div className="holding-v9-selected-total"><Money amountMinor={selectedTotalMinor} currency={currency} /></div>
                <div className="holding-v9-split-bar"><span style={{ width: `${selectedInterestPercent}%` }} /></div>
                <Review rows={[
                  { label: selectedProjection ? "Your projected interest" : "Full-loan recorded interest", value: <Money amountMinor={selectedInterestMinor} currency={currency} /> },
                  { label: selectedProjection ? "Your projected capital" : "Full-loan recorded capital", value: <Money amountMinor={selectedPrincipalMinor} currency={currency} /> },
                  { label: selectedProjection ? "Your principal after payment" : "Investor allocation", value: projectedBalanceAfter === null ? "See credited activity" : <Money amountMinor={projectedBalanceAfter} currency={currency} /> }
                ]} />
                <p className="holding-v9-note">
                  {selectedProjection
                    ? "This is your deterministic projected share of that borrower installment. It can change after repayments in advance, recoveries, transfers, or schedule revisions."
                    : "Historical rows show the borrower payment recorded for the full loan. Your credited share remains in Activity and is not reconstructed in the browser."}
                </p>
              </>
            ) : <Empty icon="clock" title="No payment selected">Open the timeline or schedule to inspect a payment.</Empty>}
          </div>
          <div className="holding-v9-collateral">
            <div className="eyebrow">Collateral</div>
            <p className="holding-v9-collateral-copy">{collateralDescription}</p>
            {ltvPercent !== null && collateralValueMinor > 0 ? (
              <>
                <div aria-label={`${ltvPercent.toFixed(1)}% loan to value`} className="holding-v9-ltv-bar" role="img"><span style={{ width: `${Math.min(100, Math.max(0, ltvPercent))}%` }} /></div>
                <div className="holding-v9-ltv-label"><span><Money amountMinor={loan.principal_minor} currency={currency} /> current loan principal against <Money amountMinor={collateralValueMinor} currency={currency} /> valuation</span><strong>{ltvPercent.toFixed(1)}% LTV</strong></div>
              </>
            ) : <p className="muted-2">No investor-facing collateral valuation or LTV is available.</p>}
            <p className="holding-v9-note">
              Default interest, if contractually due, follows the configured annual rate of {formatRateBps(loan.default_penalty_interest_bps)}. Recoveries follow the platform waterfall and remain subject to actual collections and costs.
            </p>
            {loan.product_type === "originator_claim" && loan.originator_name && loan.skin_in_the_game_bps > 0 ? (
              <div className="holding-v9-originator">
                {loan.originator_name} must retain at least {formatRateBps(loan.skin_in_the_game_bps)} of the loan&apos;s current outstanding principal. That retained claim is not offered to investors and re-scales as principal amortizes.
              </div>
            ) : null}
          </div>
        </section>

        {recoveryTotalMinor > 0 ? (
          <section className="holding-v9-recovery">
            <div className="section-head"><div><h3>Recovery credited to date</h3><div className="ph-sub">Recorded distributions only; no uncollected amounts are estimated.</div></div></div>
            <Review rows={[
              { label: "Principal recovered", value: <Money amountMinor={holding.recovered_principal_minor} currency={currency} /> },
              { label: "Contractual interest recovered", value: <Money amountMinor={holding.recovered_contractual_interest_minor} currency={currency} /> },
              { label: "Default interest recovered", value: <Money amountMinor={holding.recovered_default_interest_minor} currency={currency} /> },
              { label: "Penalties recovered", value: <Money amountMinor={holding.recovered_penalties_minor} currency={currency} /> },
              { label: "Other recoveries", value: <Money amountMinor={holding.recovered_other_costs_minor} currency={currency} /> },
              { label: "Total credited recovery", value: <Money amountMinor={recoveryTotalMinor} currency={currency} />, total: true }
            ]} />
          </section>
        ) : null}
        {holding.latest_public_note ? <section className="holding-v9-public-note"><div className="eyebrow">Latest public note from Garanta</div><p>{holding.latest_public_note.title}</p><small>{formatDate(holding.latest_public_note.occurred_at)}</small></section> : null}

        {scheduleOpen ? (
          <section className="holding-v9-future-schedule">
            <div className="section-head"><div><h3>Your future schedule</h3><div className="ph-sub">Current projection, schedule version {loan.schedule_version}.</div></div></div>
            {projectedRows.length === 0 ? (
              <Empty icon="clock" title="No contractual projection available">
                {impaired ? "This position is in an impaired state. Review recorded recoveries rather than relying on the former contractual schedule." : "There are no remaining projected payments for this claim."}
              </Empty>
            ) : (
              <div className="tbl-wrap">
                <table className="tbl holding-v9-schedule-table">
                  <thead><tr><th>Due</th><th>Status</th><th className="num">Interest</th><th className="num">Capital</th><th className="num">Payment</th><th className="num">Owed after</th></tr></thead>
                  <tbody>
                    {projectedRows.map((row, index) => {
                      const owedAfter = Math.max(0, holding.current_principal_minor - projectedRows.slice(0, index + 1).reduce((sum, item) => sum + item.projected_principal_minor, 0));
                      return <tr className="clickable" key={row.loan_installment_id} onClick={() => setSelectedPaymentKey(`projection:${row.loan_installment_id}`)}><td>{formatDate(row.due_date)}</td><td><Chip dot={false} tone={row.status === "overdue" ? "bad" : row.status === "due" ? "warn" : "neutral"}>{humanizeToken(row.status)}</Chip></td><td className="num pos"><Money amountMinor={row.projected_interest_minor} currency={currency} /></td><td className="num"><Money amountMinor={row.projected_principal_minor} currency={currency} /></td><td className="num col-strong"><Money amountMinor={row.projected_total_minor} currency={currency} /></td><td className="num"><Money amountMinor={owedAfter} currency={currency} /></td></tr>;
                    })}
                  </tbody>
                  <tfoot className="schedule-totals"><tr><th colSpan={2}>Totals</th><th className="num"><Money amountMinor={futureTotals.interest} currency={currency} /></th><th className="num"><Money amountMinor={futureTotals.principal} currency={currency} /></th><th className="num"><Money amountMinor={futureTotals.total} currency={currency} /></th><th className="num">-</th></tr></tfoot>
                </table>
              </div>
            )}
          </section>
        ) : null}
      </article>
    </Modal>
  );
}

function SecondaryMarketScreen({ demoState, initialTab }: { demoState: DemoAccountState; initialTab?: string }) {
  const listingsQuery = useSecondaryListingsData();
  const activityQuery = useSecondaryActivityData();
  const portfolioQuery = usePortfolioData(true);
  const listings = listingsQuery.data ?? [];
  const activity = activityQuery.data;
  const portfolio = portfolioQuery.data;
  const resolvedInitialTab = initialTab === "sell" || initialTab === "activity" || initialTab === "mine" ? (initialTab === "mine" ? "activity" : initialTab) : "browse";
  const [tab, setTab] = useState<"browse" | "sell" | "activity">(resolvedInitialTab);
  const [buy, setBuy] = useState<SecondaryMarketBuyerListing | null>(null);
  const [sell, setSell] = useState<{ holding: Holding; listing: NonNullable<Holding["open_secondary_listing"]> | null } | null>(null);
  const [cancelListing, setCancelListing] = useState<{ holding: Holding; listing: NonNullable<Holding["open_secondary_listing"]> } | null>(null);
  const frozen = demoState === "frozen";
  const sellable = portfolio?.holdings.filter((holding) => holding.current_principal_minor > 0) ?? [];

  useEffect(() => {
    if (initialTab === "browse" || initialTab === "sell" || initialTab === "activity" || initialTab === "mine") {
      setTab(initialTab === "mine" ? "activity" : initialTab);
    }
  }, [initialTab]);

  const sellPositions = pfActiveHoldings(portfolio?.holdings ?? []);
  const immediatelyListableCount = sellPositions.filter((holding) => holding.loan.loan_status === "active").length;
  const approvalRequiredCount = sellPositions.filter((holding) => ["late", "defaulted"].includes(holding.loan.loan_status)).length;
  const pendingDisbursementCount = sellPositions.filter((holding) => holding.loan.loan_status === "funded").length;
  const purchaseBlockedReason = frozen
    ? "Secondary-market purchases are frozen until a usable payout IBAN is available. You can still inspect every listing."
    : isReadonlyImpersonationActive()
      ? "This is a read-only investor view. Listing details are available, but purchases are disabled."
      : "";
  const listingsLoading = listingsQuery.isPending && listingsQuery.data === undefined;
  const activityLoading = activityQuery.isPending && activityQuery.data === undefined;

  return (
    <main className="content sm-page">
      <h1 className="sr-only">Secondary market</h1>
      {frozen ? <Banner icon="lock" tone="bad" title="Secondary-market actions are frozen">Provide a usable payout IBAN to unlock buying and listing.</Banner> : null}
      <div className="sm-hero">
        <div className="eyebrow">{listingsLoading ? "Loading listings" : `${listings.length} ${listings.length === 1 ? "listing" : "listings"} · sold by other investors`}</div>
        <h2>Loans other people want out of.</h2>
        <p className="sm-lede">Someone else lent this money and wants it back before the schedule ends. You take over their position, their collateral and their remaining term. Counterparties stay anonymous.</p>
      </div>
      <nav aria-label="Secondary market sections" className="mtabs" role="tablist">
        <button aria-selected={tab === "browse"} className={tab === "browse" ? "on" : ""} onClick={() => setTab("browse")} role="tab" type="button">For sale now</button>
        <button aria-selected={tab === "sell"} className={tab === "sell" ? "on" : ""} onClick={() => setTab("sell")} role="tab" type="button">Sell a holding</button>
        <button aria-selected={tab === "activity"} className={tab === "activity" ? "on" : ""} onClick={() => setTab("activity")} role="tab" type="button">Secondary market activity</button>
      </nav>
      <div>
        {tab === "browse" ? (
          listingsLoading ? (
            <LoadingCard title="Loading secondary listings">Fetching current buyer-safe prices and loan context.</LoadingCard>
          ) : listingsQuery.isError && listings.length === 0 ? (
            <DataErrorCard title="Could not load secondary listings" onRetry={() => void listingsQuery.refetch()}>
              Secondary-market listings are temporarily unavailable.
            </DataErrorCard>
          ) : (
            <SmForSale
              approvalRequiredCount={approvalRequiredCount}
              immediatelyListableCount={immediatelyListableCount}
              listings={listings}
              onBuy={setBuy}
              onChooseLoan={() => setTab("sell")}
              pendingDisbursementCount={pendingDisbursementCount}
              totalPositions={sellPositions.length}
            />
          )
        ) : null}
        {tab === "sell" ? (
          portfolioQuery.isError && !portfolio ? (
            <DataErrorCard title="Could not load sellable holdings" onRetry={() => void portfolioQuery.refetch()}>
              Your portfolio holdings are needed before a holding can be listed.
            </DataErrorCard>
          ) : !portfolio ? (
            <LoadingCard title="Loading holdings">Fetching holdings available for listing.</LoadingCard>
          ) : (
            <SellableHoldingsTable
              frozen={frozen}
              holdings={sellable}
              onCancel={(holding, listing) => setCancelListing({ holding, listing })}
              onEdit={(holding, listing) => setSell({ holding, listing })}
              onSell={(holding) => setSell({ holding, listing: null })}
            />
          )
        ) : null}
        {tab === "activity" ? (
          activityLoading ? (
            <LoadingCard title="Loading secondary-market activity">Fetching your listings, purchases, and sales.</LoadingCard>
          ) : activityQuery.isError && !activity ? (
            <DataErrorCard title="Could not load secondary-market activity" onRetry={() => void activityQuery.refetch()}>
              Your listing, purchase, and sale history could not be loaded.
            </DataErrorCard>
          ) : (
            <SecondaryMarketActivityTable entries={activity?.entries ?? []} />
          )
        ) : null}
      </div>
      {buy ? <BuyListingModal listing={buy} onClose={() => setBuy(null)} purchaseBlockedReason={purchaseBlockedReason} /> : null}
      {sell ? <ListHoldingModal holding={sell.holding} listing={sell.listing} onClose={() => setSell(null)} /> : null}
      {cancelListing ? <CancelSecondaryListingModal holding={cancelListing.holding} listing={cancelListing.listing} onClose={() => setCancelListing(null)} /> : null}
    </main>
  );
}

function smDiscountLabel(discountPremiumBps: number) {
  if (discountPremiumBps === 0) return { text: "par", tone: "mut" as const };
  const pct = (Math.abs(discountPremiumBps) / 100).toFixed(1);
  return discountPremiumBps < 0
    ? { text: `−${pct}%`, tone: "good" as const }
    : { text: `+${pct}%`, tone: "mut" as const };
}

function SmForSale({
  approvalRequiredCount,
  immediatelyListableCount,
  listings,
  onBuy,
  onChooseLoan,
  pendingDisbursementCount,
  totalPositions
}: {
  approvalRequiredCount: number;
  immediatelyListableCount: number;
  listings: SecondaryMarketBuyerListing[];
  onBuy: (listing: SecondaryMarketBuyerListing) => void;
  onChooseLoan: () => void;
  pendingDisbursementCount: number;
  totalPositions: number;
}) {
  return (
    <div className="sm-forsale">
      <h2 className="sect">For sale now</h2>
      <p className="sect-sub" style={{ maxWidth: 680 }}>A discount raises what you earn; a premium lowers it. The interest rate on the loan itself never changes — only what you paid for it.</p>
      {listings.length === 0 ? (
        <div className="sm-empty"><Empty icon="secondary" title="No active secondary listings">There are no buyer-visible holdings listed right now.</Empty></div>
      ) : (
        <div className="rule-top sm-table">
          <div className="sm-thead">
            <span className="sm-col-loan">Loan</span>
            <span className="sm-col-outstanding">Outstanding</span>
            <span className="sm-col-asking">Asking</span>
            <span className="sm-col-discount">Discount</span>
            <span className="sm-col-left">Left to run</span>
            <span className="sm-col-cost">Buyer cost</span>
            <span className="sm-col-cta" />
          </div>
          {listings.map((listing) => {
            const discount = smDiscountLabel(listing.discount_premium_bps);
            return (
              <button
                className="sm-row"
                key={listing.id}
                onClick={() => onBuy(listing)}
                type="button"
              >
                <span className="sm-col-loan">
                  <span className="sm-loan-title">{listing.loan_title}</span>
                  <span className="num sm-loan-sub">
                    {humanizeToken(listing.collateral_type)} · {formatRateBps(listing.interest_rate_bps)} coupon
                    {listing.risk_acknowledgement_required ? <span className="sm-nonstandard"> · non-standard</span> : null}
                  </span>
                </span>
                <span className="num sm-col-outstanding">{pfMoneyLabel(listing.currency, listing.current_principal_minor)}</span>
                <span className="num sm-col-asking">{pfMoneyLabel(listing.currency, listing.transfer_price_minor)}</span>
                <span className={`num sm-col-discount ${discount.tone}`}>{discount.text}</span>
                <span className="num sm-col-left">{listing.remaining_term_months} mo</span>
                <span className="num sm-col-cost">{pfMoneyLabel(listing.currency, listing.buyer_total_cost_minor)}</span>
                <span className="sm-col-cta">details</span>
              </button>
            );
          })}
        </div>
      )}

      <h2 className="sect">Why do loans sell at a premium or a discount?</h2>
      <p className="sect-sub" style={{ maxWidth: 680 }}>The seller keeps one premium or discount percentage. Actual buyer cost also includes accrued interest and the disclosed taker fee.</p>
      <div className="band band-3 sm-band">
        <div className="cell">
          <div className="microlabel" style={{ color: "#1e6a4b", marginBottom: 14 }}>At a discount</div>
          <div className="num sm-band-price" style={{ color: "#1e6a4b" }}>Below 100% of principal</div>
          <div className="sm-band-yield" style={{ color: "#1e6a4b" }}>lower transfer price</div>
          <div className="sm-band-copy">The seller wants out early — a long wait left, or collateral that resells slowly. The full amount is still owed, so the gap is yours.</div>
        </div>
        <div className="cell">
          <div className="microlabel" style={{ marginBottom: 14 }}>At par</div>
          <div className="num sm-band-price">100% of principal</div>
          <div className="sm-band-yield">same transfer price</div>
          <div className="sm-band-copy">You step in at the holding's current outstanding principal. Accrued interest and the buyer fee still form part of total cost.</div>
        </div>
        <div className="cell">
          <div className="microlabel" style={{ marginBottom: 14 }}>At a premium</div>
          <div className="num sm-band-price">Above 100% of principal</div>
          <div className="sm-band-yield">higher transfer price</div>
          <div className="sm-band-copy">The rate beats anything open today, so the seller charges for access. You take a lower yield to lock it in.</div>
        </div>
      </div>

      <h2 className="sect">Selling your own</h2>
      <p className="sm-sell-note">
        {totalPositions > 0 ? (
          <>
            <span style={{ color: "#151719", fontWeight: 600 }}>{immediatelyListableCount} of your {totalPositions} {totalPositions === 1 ? "holding" : "holdings"}</span> can be listed immediately.
            {approvalRequiredCount > 0 ? ` ${approvalRequiredCount} non-performing ${approvalRequiredCount === 1 ? "holding can" : "holdings can"} be submitted for Garanta approval.` : ""}
            {pendingDisbursementCount > 0 ? ` ${pendingDisbursementCount} ${pendingDisbursementCount === 1 ? "holding becomes" : "holdings become"} available after borrower disbursement.` : ""}{" "}
          </>
        ) : null}
        You set the asking price; BANXUM's maker fee comes out of what you receive, and nothing is charged if it does not sell.
      </p>
      <div className="sm-caution-card">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="microlabel" style={{ color: "#c4312c", marginBottom: 11 }}>Caution</div>
          <div className="sm-caution-copy">This is not a withdrawal button. There is no guaranteed buyer and no guaranteed price. If nobody wants your loan at a price you accept, you hold it to the end of its term.</div>
        </div>
        <div style={{ flex: "none" }}>
          <button className="sm-choose-btn" onClick={onChooseLoan} type="button">Choose a loan to sell</button>
        </div>
      </div>
      <p className="sm-anon-note">Buyer views never expose seller identity, seller net proceeds, maker fee, document evidence IDs, or admin fields.</p>
    </div>
  );
}

type OpenSecondaryListing = NonNullable<Holding["open_secondary_listing"]>;

function listingStatusLabel(status: string) {
  if (status === "active") return "Listed";
  if (status === "approval_requested") return "Approval pending";
  return humanizeToken(status);
}

function listingStatusTooltip(status: string, loanStatus: string) {
  if (status === "active") {
    return "Visible to eligible buyers. Servicing changes automatically recalculate the amounts while preserving the selected premium or discount.";
  }
  if (status === "approval_requested") {
    if (["late", "defaulted"].includes(loanStatus)) {
      return "Hidden from buyers because the loan is non-performing. Garanta must review the updated status and disclosure before republishing it.";
    }
    return "Hidden from buyers until Garanta completes the required listing review.";
  }
  return undefined;
}

function secondaryListingAction(loanStatus: string) {
  if (loanStatus === "active") {
    return { allowed: true, label: "List on secondary market", title: "Listing available", hint: "" };
  }
  if (["late", "defaulted"].includes(loanStatus)) {
    return {
      allowed: true,
      label: "Request listing",
      title: "Garanta approval required",
      hint: "This non-performing holding can be submitted for review but will remain hidden until Garanta approves its disclosure."
    };
  }
  if (loanStatus === "funded") {
    return {
      allowed: false,
      label: "List on secondary market",
      title: "Listing available after borrower disbursement",
      hint: "Funding has closed, but the borrower payout is still pending. You can list this holding after disbursement moves the loan to Active."
    };
  }
  return {
    allowed: false,
    label: "List on secondary market",
    title: "Secondary-market listing unavailable",
    hint: `This holding cannot be listed while the loan status is ${humanizeToken(loanStatus).toLowerCase()}.`
  };
}

function SellableHoldingsTable({
  holdings,
  onSell,
  onEdit,
  onCancel,
  frozen
}: {
  holdings: Holding[];
  onSell: (holding: Holding) => void;
  onEdit: (holding: Holding, listing: OpenSecondaryListing) => void;
  onCancel: (holding: Holding, listing: OpenSecondaryListing) => void;
  frozen: boolean;
}) {
  if (holdings.length === 0) {
    return <div className="portal-table-empty"><Empty icon="portfolio" title="No sellable holdings">Active holdings that can be listed will appear here.</Empty></div>;
  }

  return (
    <div className="portal-data-surface">
      <div className="tbl-wrap">
        <table className="tbl portal-data-table secondary-sell-table">
          <thead><tr><th>Holding</th><th>Loan status</th><th>Listing status</th><th className="num">Current principal</th><th className="num">Rate</th><th /></tr></thead>
          <tbody>{holdings.map((holding) => {
            const listing = holding.open_secondary_listing;
            const actionsDisabled = frozen || isReadonlyImpersonationActive();
            const listingAction = secondaryListingAction(holding.loan.loan_status);
            return (
              <tr key={holding.id}>
                <td><EntityReference id={holding.loan.loan_id} idLabel="Copy loan ID" meta={holding.loan.borrower_name} title={holding.loan.loan_title} /></td>
                <td><Chip status={holding.loan.loan_status} tone={statusTone(holding.loan.loan_status)} /></td>
                <td>{listing ? <Chip status={listingStatusLabel(listing.status)} tone={listing.status === "active" ? "ok" : "warn"} tooltip={listingStatusTooltip(listing.status, holding.loan.loan_status)} /> : <span className="muted">Not listed</span>}</td>
                <td className="num"><Money amountMinor={holding.current_principal_minor} currency={holding.currency} /></td>
                <td className="num">{formatRateBps(holding.loan.interest_rate_bps)}</td>
                <td className="right">
                  <div className="row gap-8" style={{ justifyContent: "flex-end" }}>
                    {listing ? (
                      <>
                        <Button disabled={actionsDisabled} size="sm" onClick={() => onEdit(holding, listing)}>Edit</Button>
                        <Button disabled={actionsDisabled} size="sm" variant="danger" onClick={() => onCancel(holding, listing)}>Cancel</Button>
                      </>
                    ) : (
                      <div className="col gap-4" style={{ alignItems: "flex-end" }}>
                        <Button disabled={actionsDisabled || !listingAction.allowed} size="sm" title={!listingAction.allowed ? listingAction.hint : undefined} onClick={() => onSell(holding)}>{listingAction.label === "List on secondary market" ? "List" : listingAction.label}</Button>
                        {!listingAction.allowed ? <span className="sub">{holding.loan.loan_status === "funded" ? "Available after disbursement" : "Unavailable for this status"}</span> : null}
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}</tbody>
        </table>
      </div>
    </div>
  );
}

type SecondaryActivityFilter = "list" | "cancel_listing" | "sale" | "buy";

function secondaryActivityLabel(entry: SecondaryMarketActivityEntryPortal) {
  if (entry.action === "buy") return "Purchase completed";
  if (entry.action === "sale") return "Sale completed";
  if (entry.action === "cancel_listing") return "Listing cancelled";
  if (entry.event_type === "edited") return "Listing updated";
  return "Holding listed";
}

function SecondaryMarketActivityTable({ entries }: { entries: SecondaryMarketActivityEntryPortal[] }) {
  const [filters, setFilters] = useState<Record<SecondaryActivityFilter, boolean>>({
    list: false,
    cancel_listing: false,
    sale: true,
    buy: true
  });
  const visible = entries.filter((entry) => filters[entry.action as SecondaryActivityFilter] ?? false);
  const toggle = (filter: SecondaryActivityFilter, checked: boolean) => {
    setFilters((current) => ({ ...current, [filter]: checked }));
  };

  return (
    <div className="col gap-16">
      <Card padded>
        <div className="section-head compact">
          <div><h2>Activity filters</h2><div className="ph-sub">Sales and purchases are shown by default. Include listing lifecycle entries when needed.</div></div>
        </div>
        <div className="row gap-16 wrap">
          <Check checked={filters.sale} id="sm-activity-sales" onChange={(checked) => toggle("sale", checked)}>Sales</Check>
          <Check checked={filters.buy} id="sm-activity-buys" onChange={(checked) => toggle("buy", checked)}>Purchases</Check>
          <Check checked={filters.list} id="sm-activity-listings" onChange={(checked) => toggle("list", checked)}>Listings and edits</Check>
          <Check checked={filters.cancel_listing} id="sm-activity-cancellations" onChange={(checked) => toggle("cancel_listing", checked)}>Listing cancellations</Check>
        </div>
      </Card>
      {visible.length === 0 ? (
        <div className="portal-table-empty">
          <Empty icon="secondary" title={entries.length === 0 ? "No secondary-market activity" : "No activity matches these filters"}>
            {entries.length === 0 ? "Listings, purchases, sales, and cancellations will appear here." : "Select another activity type to expand the history."}
          </Empty>
        </div>
      ) : (
        <div className="portal-data-surface">
          <div className="tbl-wrap">
            <table className="tbl portal-data-table secondary-activity-table">
              <thead><tr><th>Date</th><th>Activity</th><th>Loan</th><th className="num">Principal</th><th className="num">Cash amount</th><th>State</th></tr></thead>
              <tbody>{visible.map((entry) => (
                <tr key={entry.id}>
                  <td className="mono">{formatDateTime(entry.occurred_at)}</td>
                  <td><div className="col gap-4"><strong>{secondaryActivityLabel(entry)}</strong>{entry.action === "list" && entry.price_bps !== null ? <span className="sub">{priceLabel(entry.price_bps - 10000)}</span> : null}</div></td>
                  <td><EntityReference id={entry.loan_id} idLabel="Copy loan ID" title={entry.loan_title} /></td>
                  <td className="num"><Money amountMinor={entry.principal_minor} currency={entry.currency} /></td>
                  <td className={`num ${entry.action === "sale" ? "pos" : entry.action === "buy" ? "neg" : ""}`}><Money amountMinor={entry.cash_amount_minor} currency={entry.currency} /></td>
                  <td><Chip status={entry.status} tone={statusTone(entry.status)} /></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function CancelSecondaryListingModal({
  holding,
  listing,
  onClose
}: {
  holding: Holding;
  listing: OpenSecondaryListing;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("Cancelled by investor.");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [idempotency] = useState(() => idempotencyKey("secondary-listing-cancel"));
  const mutation = useV1MarketplaceSecondaryListingsCancelCreate();
  const cancelListing = async () => {
    setError("");
    if (!reason.trim()) {
      setError("Enter a cancellation reason.");
      return;
    }
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    try {
      await mutation.mutateAsync({
        listingId: listing.id,
        data: { reason: reason.trim(), idempotency_key: idempotency }
      });
      await queryClient.invalidateQueries();
      setDone(true);
    } catch (mutationError) {
      setError(apiErrorMessage(mutationError));
    }
  };
  if (done) {
    return <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Listing cancelled"><SuccessState title="Listing cancelled">The holding is no longer visible to buyers and can be listed again.</SuccessState></Modal>;
  }
  return (
    <Modal
      footer={<><Button variant="ghost" onClick={onClose}>Keep listing</Button><Button disabled={!reason.trim() || mutation.isPending} variant="danger" onClick={cancelListing}>{mutation.isPending ? "Cancelling..." : "Cancel listing"}</Button></>}
      onClose={onClose}
      title={`Cancel ${holding.loan.loan_title} listing`}
    >
      <div className="col gap-16">
        <Banner tone="warn" title="Return this holding to your unlisted portfolio">
          Cancelling removes the open listing. It does not sell or otherwise change the underlying holding.
        </Banner>
        <Review rows={[
          { label: "Loan", value: holding.loan.loan_title },
          { label: "Listing status", value: listingStatusLabel(listing.status) },
          { label: "Current principal", value: `${holding.currency} ${formatMoneyMinor(holding.current_principal_minor, holding.currency)}` },
          { label: "Current transfer price", value: `${holding.currency} ${formatMoneyMinor(listing.transfer_price_minor, holding.currency)}` }
        ]} />
        <Field label="Cancellation reason">
          <textarea className="textarea" onChange={(event) => setReason(event.target.value)} rows={3} value={reason} />
        </Field>
        {error ? <Banner tone="bad" title="Could not cancel listing">{error}</Banner> : null}
      </div>
    </Modal>
  );
}

function BuyListingModal({ listing, onClose, purchaseBlockedReason }: { listing: SecondaryMarketBuyerListing; onClose: () => void; purchaseBlockedReason: string }) {
  const queryClient = useQueryClient();
  const detailQuery = useSecondaryListingDetailData(listing.id);
  const detail = detailQuery.data;
  const [ack, setAck] = useState(false);
  const [extraAck, setExtraAck] = useState(false);
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [acceptanceId, setAcceptanceId] = useState<string | null>(null);
  const [acceptanceKey] = useState(() => idempotencyKey("secondary-purchase-acceptance"));
  const [purchaseKey] = useState(() => idempotencyKey("secondary-purchase"));
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const purchaseMutation = useV1MarketplaceSecondaryListingsPurchaseCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.secondary_market_purchase);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.secondary_market_purchase },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const needsExtra = listing.risk_acknowledgement_required;
  const submitPurchase = async () => {
    setError("");
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError("Current secondary-market purchase terms are not available.");
      return;
    }
    if (!codeRequest.codeId) {
      setError("Request an email code before confirming the purchase.");
      return;
    }
    try {
      const acceptance = acceptanceId
        ? { id: acceptanceId }
        : await acceptanceMutation.mutateAsync({
            data: {
              category: CategoryEnum.secondary_market_purchase,
              expected_template_version_id: termsQuery.data.id,
              accepted_checkbox_labels: labels,
              context_type: "secondary_market_purchase",
              context_id: listing.id,
              data_snapshot: {
                listing_id: listing.id,
                buyer_total_cost_minor: listing.buyer_total_cost_minor,
                currency: listing.currency
              },
              idempotency_key: acceptanceKey
            }
          });
      setAcceptanceId(acceptance.id);
      await purchaseMutation.mutateAsync({
        listingId: listing.id,
        data: {
          document_acceptance_id: acceptance.id,
          risk_acknowledgement_accepted: needsExtra ? extraAck : true,
          idempotency_key: purchaseKey,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code
        }
      });
      void queryClient.invalidateQueries();
      setDone(true);
    } catch (mutationError) {
      setError(apiErrorMessage(mutationError));
    }
  };
  if (done) {
    return <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Purchase confirmed"><SuccessState title="Purchase confirmed">The holding will appear in your portfolio after settlement evidence is generated.</SuccessState></Modal>;
  }
  if (!detail) {
    return (
      <Modal xwide footer={<Button variant="ghost" onClick={onClose}>Close</Button>} onClose={onClose} title={`Buy ${listing.loan_title}`}>
        {detailQuery.isError ? (
          <DataErrorCard title="Could not load listing details" onRetry={() => void detailQuery.refetch()}>
            The loan economics and current schedules must be loaded before you can review this purchase.
          </DataErrorCard>
        ) : (
          <LoadingCard title="Loading listing details">Fetching the current loan and claim schedules.</LoadingCard>
        )}
      </Modal>
    );
  }
  const projectedInterestMinor = detail.investment_schedule.reduce(
    (sum, row) => sum + row.projected_interest_minor,
    0
  );
  return (
    <Modal xwide footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={Boolean(purchaseBlockedReason) || !ack || (needsExtra && !extraAck) || code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || acceptanceMutation.isPending || purchaseMutation.isPending} variant="primary" onClick={submitPurchase}>{acceptanceMutation.isPending || purchaseMutation.isPending ? "Submitting..." : "Confirm purchase"}</Button></>} onClose={onClose} title={`Buy ${listing.loan_title}`}>
      <div className="col gap-16">
        {purchaseBlockedReason ? <Banner icon="lock" tone="neutral" title="Purchase unavailable in this view">{purchaseBlockedReason}</Banner> : null}
        {needsExtra ? <Banner tone="bad" title="Non-standard listing - elevated risk">This listing is non-performing or otherwise non-standard. You may receive less than the principal shown, or nothing.</Banner> : null}
        <div className="row gap-8 wrap">
          <Chip status={detail.loan_status_at_listing} tone={statusTone(detail.loan_status_at_listing)} />
          <Rating value={detail.risk_rating} />
          <Country code={detail.borrower_country} />
          <CopyIdButton ariaLabel="Copy listing ID" id={detail.id} label="Copy listing ID" />
        </div>
        <div className="sub">Borrower: {detail.borrower_name} · {humanizeToken(detail.purpose)}</div>
        <div className="grid grid-4">
          <Card padded><Stat amountMinor={detail.current_principal_minor} currency={detail.currency} label="Listed principal" /></Card>
          <Card padded><Stat amountMinor={projectedInterestMinor} currency={detail.currency} label="Projected remaining interest" /></Card>
          <Card padded><Stat label="Annual interest / term" raw={`${formatRateBps(detail.interest_rate_bps)} / ${detail.term_months}mo`} /></Card>
          <Card padded><Stat label="LTV" raw={detail.ltv_bps === null ? "Not disclosed" : formatRateBps(detail.ltv_bps)} /></Card>
        </div>
        <Review rows={[
          { label: "Listing", value: listing.loan_title },
          { label: "Repayment type", value: humanizeToken(detail.repayment_type) },
          { label: "Current principal", value: `${listing.currency} ${formatMoneyMinor(listing.current_principal_minor, listing.currency)}` },
          { label: "Sale price", value: priceLabel(listing.discount_premium_bps) },
          { label: "Accrued interest to seller", value: `${listing.currency} ${formatMoneyMinor(listing.accrued_interest_minor, listing.currency)}` },
          { label: "Taker fee", value: `${listing.currency} ${formatMoneyMinor(listing.taker_fee_minor, listing.currency)}` },
          { label: "Total cost", value: `${listing.currency} ${formatMoneyMinor(listing.buyer_total_cost_minor, listing.currency)}`, total: true }
        ]} />
        {detail.public_disclosure_note ? <Banner tone="warn" title="Listing disclosure">{detail.public_disclosure_note}</Banner> : null}
        {detail.latest_public_note ? <Card padded><div className="eyebrow" style={{ marginBottom: 6 }}>Latest public loan note</div><p className="muted-2">{detail.latest_public_note.title}</p><div className="sub">{formatDate(detail.latest_public_note.occurred_at)}</div></Card> : null}
        <LoanSchedulePanels
          currency={detail.currency}
          currentPrincipalMinor={detail.current_principal_minor}
          investmentSchedule={detail.investment_schedule}
          loanSchedule={detail.loan_schedule}
          loanStatus={detail.loan_status_at_listing}
          projectionDescription={<>This is the projected share of remaining borrower payments attached to the listed claim. It is an estimate, not a guarantee, and can change after repayments in advance, recoveries, or schedule revisions.</>}
          projectionBannerTitle="Projection from the listed claim"
          projectionTitle="Listed claim projection"
          scheduleVersion={detail.schedule_version}
        />
        <Check checked={ack} id="sm-buy-ack" onChange={setAck}>
          I accept the{" "}
          <LegalDocLink category="secondary_market_purchase">
            secondary-market buyer terms and reassignment document
          </LegalDocLink>
          .
        </Check>
        {needsExtra ? <Check checked={extraAck} id="sm-extra-ack" onChange={setExtraAck}>I acknowledge this is a non-standard claim with heightened risk of partial or total loss.</Check> : null}
        {!isFixturePreview && termsQuery.data ? <p className="muted" style={{ fontSize: 11.5 }}>Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={Boolean(purchaseBlockedReason) || emailCodeRequestDisabled(codeRequest)}
          requestLabel={emailCodeRequestLabel(codeRequest)}
          value={code}
          onChange={setCode}
          onRequest={codeRequest.requestCode}
        />
        <p className="muted" style={{ fontSize: 11.5 }}>Request the email code only after you have reviewed the claim, schedules, price, and terms and intend to buy.</p>
        {codeRequest.error || error ? <Banner tone="bad" title="Could not purchase listing">{codeRequest.error || error}</Banner> : null}
      </div>
    </Modal>
  );
}

function ListHoldingModal({ holding, listing, onClose }: { holding: Holding; listing: OpenSecondaryListing | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const isEdit = listing !== null;
  const [step, setStep] = useState<"review" | "verify">("review");
  const [priceBps, setPriceBps] = useState(String(listing?.price_bps ?? 10000));
  const [ack, setAck] = useState(false);
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [acceptanceId, setAcceptanceId] = useState<string | null>(null);
  const [acceptanceKey] = useState(() => idempotencyKey(isEdit ? "secondary-listing-edit-acceptance" : "secondary-listing-acceptance"));
  const [listingKey] = useState(() => idempotencyKey(isEdit ? "secondary-listing-edit" : "secondary-listing"));
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const listingMutation = useV1MarketplaceSecondaryListingsCreate();
  const editMutation = useV1MarketplaceSecondaryListingsEditCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.secondary_market_listing);
  useAutoRequestEmailCode(codeRequest, step === "verify" && !done);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.secondary_market_listing },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const price = Math.max(1, Number(priceBps || 0));
  const transferPrice = Math.round((holding.current_principal_minor * price) / 10000);
  const makerFee = Math.round(transferPrice * 0.0025);
  const nonStandard = holding.loan.loan_status !== "active";
  const projectedInterestMinor = holding.investment_schedule.reduce(
    (sum, row) => sum + row.projected_interest_minor,
    0
  );
  const continueToVerification = () => {
    setError("");
    if (!ack) {
      setError("Accept the seller/listing terms before continuing.");
      return;
    }
    if (!Number.isFinite(price) || price < 1) {
      setError("Enter a valid sale price in basis points.");
      return;
    }
    if (!isFixturePreview && (!termsQuery.data || templateLabels(termsQuery.data).length === 0)) {
      setError("Current secondary-market listing terms are not available.");
      return;
    }
    setStep("verify");
  };
  const submitListing = async () => {
    setError("");
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError("Current secondary-market listing terms are not available.");
      return;
    }
    if (!codeRequest.codeId) {
      setError("Request an email code before publishing the listing.");
      return;
    }
    try {
      const acceptance = acceptanceId
        ? { id: acceptanceId }
        : await acceptanceMutation.mutateAsync({
            data: {
              category: CategoryEnum.secondary_market_listing,
              expected_template_version_id: termsQuery.data.id,
              accepted_checkbox_labels: labels,
              context_type: "secondary_market_listing",
              context_id: holding.id,
              data_snapshot: {
                holding_id: holding.id,
                listing_id: listing?.id ?? "",
                action: isEdit ? "edit" : "create",
                price_bps: price,
                current_principal_minor: holding.current_principal_minor,
                currency: holding.currency
              },
              idempotency_key: acceptanceKey
            }
          });
      setAcceptanceId(acceptance.id);
      if (listing) {
        await editMutation.mutateAsync({
          listingId: listing.id,
          data: {
            price_bps: price,
            document_acceptance_id: acceptance.id,
            idempotency_key: listingKey,
            sensitive_action_code_id: codeRequest.codeId,
            sensitive_action_code: code
          }
        });
      } else {
        await listingMutation.mutateAsync({
          data: {
            holding_id: holding.id,
            price_bps: price,
            document_acceptance_id: acceptance.id,
            idempotency_key: listingKey,
            sensitive_action_code_id: codeRequest.codeId,
            sensitive_action_code: code
          }
        });
      }
      void queryClient.invalidateQueries();
      setDone(true);
    } catch (mutationError) {
      setError(apiErrorMessage(mutationError));
    }
  };
  if (done) {
    const successTitle = nonStandard ? "Submitted for approval" : isEdit ? "Listing updated" : "Listing published";
    return <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={successTitle}><SuccessState title={successTitle}>{nonStandard ? "Garanta will review the revised listing before it becomes visible." : isEdit ? "Your revised price and economics are now visible to buyers anonymously." : "Your holding is visible to buyers anonymously."}</SuccessState></Modal>;
  }
  return (
    <Modal
      xwide
      footer={step === "review" ? (
        <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ack || !Number.isFinite(price) || price < 1 || (!isFixturePreview && !termsQuery.data)} variant="primary" onClick={continueToVerification}>Confirm listing data</Button></>
      ) : (
        <><Button variant="ghost" onClick={() => { setError(""); setStep("review"); }}>Back to listing data</Button><Button disabled={code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || acceptanceMutation.isPending || listingMutation.isPending || editMutation.isPending} variant="primary" onClick={submitListing}>{acceptanceMutation.isPending || listingMutation.isPending || editMutation.isPending ? "Submitting..." : nonStandard ? "Verify and submit" : isEdit ? "Verify and update" : "Verify and publish"}</Button></>
      )}
      onClose={onClose}
      title={`${isEdit ? "Edit listing for" : "List"} ${holding.loan.loan_title}`}
    >
      {step === "review" ? (
        <div className="col gap-16">
          {nonStandard ? <Banner tone="warn" title="Requires Garanta approval">Non-performing holdings require approval and status disclosure before buyers can see them.</Banner> : null}
          {isEdit ? <Banner tone="neutral" title="Editing an open listing">Changing the listing creates a new auditable revision and requires a fresh terms acceptance and email confirmation.</Banner> : null}
          <div className="row gap-8 wrap">
            <Chip status={holding.loan.loan_status} tone={statusTone(holding.loan.loan_status)} />
            <Rating value={holding.loan.risk_rating} />
            <Country code={holding.loan.borrower_country} />
            <CopyIdButton ariaLabel="Copy holding ID" id={holding.id} label="Copy holding ID" />
          </div>
          <div className="grid grid-4">
            <Card padded><Stat amountMinor={holding.original_principal_minor} currency={holding.currency} label="Originally invested" /></Card>
            <Card padded><Stat amountMinor={holding.current_principal_minor} currency={holding.currency} label="Outstanding principal" /></Card>
            <Card padded><Stat amountMinor={projectedInterestMinor} currency={holding.currency} label="Projected remaining interest" /></Card>
            <Card padded><Stat label="Annual interest / term" raw={`${formatRateBps(holding.loan.interest_rate_bps)} / ${holding.loan.term_months}mo`} /></Card>
          </div>
          <Field hint="10000 = at par, 9800 = 2% discount, 10100 = 1% premium." label="Sale price bps">
            <input className="input mono" inputMode="numeric" onChange={(event) => setPriceBps(event.target.value.replace(/\D/g, ""))} value={priceBps} />
          </Field>
          <Review rows={[
            { label: "Loan", value: holding.loan.loan_title },
            { label: "Borrower", value: holding.loan.borrower_name },
            { label: "Repayment type", value: humanizeToken(holding.loan.repayment_type) },
            { label: "LTV", value: holding.loan.ltv_bps === null ? "Not disclosed" : formatRateBps(holding.loan.ltv_bps) },
            { label: "Current principal", value: `${holding.currency} ${formatMoneyMinor(holding.current_principal_minor, holding.currency)}` },
            { label: "Transfer price", value: `${holding.currency} ${formatMoneyMinor(transferPrice, holding.currency)}` },
            { label: "Maker fee", value: `${holding.currency} ${formatMoneyMinor(makerFee, holding.currency)}` },
            { label: "Seller net proceeds", value: `${holding.currency} ${formatMoneyMinor(transferPrice - makerFee, holding.currency)}`, total: true }
          ]} />
          <Check checked={ack} id="sm-list-ack" onChange={setAck}>
            I accept the{" "}
            <LegalDocLink category="secondary_market_listing">seller/listing terms</LegalDocLink> and
            confirm I am {isEdit ? "updating the listing for" : "listing"} this entire holding.
          </Check>
          {!isFixturePreview && termsQuery.data ? <p className="muted" style={{ fontSize: 11.5 }}>Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
          <LoanSchedulePanels
            currency={holding.currency}
            currentPrincipalMinor={holding.current_principal_minor}
            investmentSchedule={holding.investment_schedule}
            loanSchedule={holding.loan.schedule}
            loanStatus={holding.loan.loan_status}
            projectionDescription={<>This is the projected share of the loan&apos;s remaining borrower payments attached to the holding you are listing. The buyer receives the claim only after a completed purchase.</>}
            projectionBannerTitle="Projection from the holding you are listing"
            projectionTitle="Listed holding projection"
            scheduleVersion={holding.loan.schedule_version}
          />
          {error ? <Banner tone="bad" title="Could not confirm listing data">{error}</Banner> : null}
        </div>
      ) : (
        <div className="col gap-16">
          <Banner icon="lock" tone="neutral" title={isEdit ? "Verify and update" : "Verify and publish"}>
            The {isEdit ? "revised listing" : "listing"} data and terms are confirmed. Enter the code sent to your email to authorize this sensitive action.
          </Banner>
          <Review rows={[
            { label: "Loan", value: holding.loan.loan_title },
            { label: "Current principal", value: `${holding.currency} ${formatMoneyMinor(holding.current_principal_minor, holding.currency)}` },
            { label: "Sale price", value: priceLabel(price - 10000) },
            { label: "Transfer price", value: `${holding.currency} ${formatMoneyMinor(transferPrice, holding.currency)}` },
            { label: "Maker fee", value: `${holding.currency} ${formatMoneyMinor(makerFee, holding.currency)}` },
            { label: "Seller net proceeds", value: `${holding.currency} ${formatMoneyMinor(transferPrice - makerFee, holding.currency)}`, total: true }
          ]} />
          <CodeRequestField
            hint={previewHint("Demo: any 6 digits")}
            label="Email confirmation code"
            requestDisabled={emailCodeRequestDisabled(codeRequest)}
            requestLabel={emailCodeRequestLabel(codeRequest)}
            value={code}
            onChange={setCode}
            onRequest={codeRequest.requestCode}
          />
          {codeRequest.error || error ? <Banner tone="bad" title={isEdit ? "Could not update listing" : "Could not list holding"}>{codeRequest.error || error}</Banner> : null}
        </div>
      )}
    </Modal>
  );
}

function DocumentsScreen() {
  const [type, setType] = useState<string>("All");
  const [error, setError] = useState("");
  const documentsQuery = useDocumentsData();
  const downloadMutation = useV1InvestorPortalDocumentsDownloadCreate();
  const documents = documentsQuery.data;
  if (documentsQuery.isError && !documents) {
    return (
      <main className="content">
        <div className="page-head"><div><h1>Documents</h1><div className="ph-sub">Accepted terms, transaction evidence, statements and tax information. Self-scoped to your account.</div></div></div>
        <DataErrorCard title="Could not load documents" onRetry={() => void documentsQuery.refetch()}>
          We could not load your self-service document list.
        </DataErrorCard>
      </main>
    );
  }
  if (!documents) return <ScreenLoading title="Documents" />;
  const rows = documents.documents.filter((document) => type === "All" || document.document_type === type);
  const types = ["All", ...Array.from(new Set(documents.documents.map((document) => document.document_type)))];
  const downloadDocument = (document: InvestorDocument, outputFormat = "pdf") => {
    setError("");
    downloadMutation.mutate(
      {
        data: {
          document_kind:
            document.document_kind === "acceptance_evidence"
              ? DocumentKindEnum.acceptance_evidence
              : document.document_kind === "annual_tax_information"
                ? DocumentKindEnum.annual_tax_information
                : DocumentKindEnum.account_statement,
          document_id: document.document_kind === "acceptance_evidence" ? document.id : undefined,
          output_format:
            outputFormat === "csv"
              ? InvestorDocumentDownloadRequestOutputFormatEnum.csv
              : outputFormat === "zip"
                ? InvestorDocumentDownloadRequestOutputFormatEnum.zip
                : InvestorDocumentDownloadRequestOutputFormatEnum.pdf,
          start_date: document.period_start,
          end_date: document.period_end
        }
      },
      {
        onSuccess: (artifact) => downloadPortalArtifact(artifact),
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };
  return (
    <main className="content">
      <div className="page-head"><div><h1>Documents</h1><div className="ph-sub">Accepted document history, transaction evidence, statements and tax information. Self-scoped to your account.</div></div></div>
      <Banner tone="neutral" title="Informational only">{documents.disclaimer}</Banner>
      {error ? <div style={{ marginTop: 12 }}><Banner tone="bad" title="Download failed">{error}</Banner></div> : null}
      <div className="toolbar" style={{ marginTop: 16 }}>
        {types.map((item) => <button className={`fchip ${type === item ? "on" : ""}`} key={item} onClick={() => setType(item)} type="button">{item}</button>)}
        <span className="results-count">{rows.length} documents</span>
      </div>
      {rows.length === 0 ? (
        <div className="portal-table-empty">
          <Empty icon="doc" title="No documents match this filter">
            Choose another document type, or return later after accepting terms or generating a statement.
          </Empty>
        </div>
      ) : (
        <div className="portal-data-surface">
          <div className="tbl-wrap">
            <table className="tbl portal-data-table documents-data-table"><thead><tr><th>Document</th><th>Type</th><th>Version</th><th>Context</th><th>Date</th><th className="num">Artifact</th><th /></tr></thead>
            <tbody>{rows.map((document) => (
              <tr key={document.id}>
                <td className="row gap-8">
                  <Icon className="muted" name="doc" size={16} />
                  <span>
                    <span className="col-strong">{document.title}</span>
                    {document.template_title ? <div className="sub">{document.template_title}</div> : null}
                  </span>
                </td>
                <td><Chip dot={false} tone={document.document_type === "Risk" ? "warn" : document.document_type === "Tax" ? "accent" : "neutral"}>{document.document_type}</Chip></td>
                <td className="mono muted">{document.version}</td>
                <td className="sub">{document.context_label}</td>
                <td className="mono muted">{formatDate(document.date)}</td>
                <td className="num muted">{document.generated_on_request ? "On request" : document.content_hash ? "Evidence" : "-"}</td>
                <td className="right">
                  <div className="row gap-6" style={{ justifyContent: "flex-end" }}>
                    {document.output_formats.includes("csv") ? <Button disabled={downloadMutation.isPending} size="sm" variant="ghost" onClick={() => downloadDocument(document, "csv")}>CSV</Button> : null}
                    {document.output_formats.includes("zip") ? <Button disabled={downloadMutation.isPending} size="sm" variant="ghost" onClick={() => downloadDocument(document, "zip")}>ZIP</Button> : null}
                    <Button disabled={downloadMutation.isPending} icon="download" size="sm" variant="ghost" onClick={() => downloadDocument(document, "pdf")}>PDF</Button>
                  </div>
                </td>
              </tr>
            ))}</tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}

function downloadPortalArtifact(artifact: InvestorDocumentDownloadResponse) {
  const bytes =
    artifact.content_encoding === "base64"
      ? Uint8Array.from(window.atob(artifact.content), (character) => character.charCodeAt(0))
      : new TextEncoder().encode(artifact.content);
  const blob = new Blob([bytes], { type: artifact.content_type });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = artifact.filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

function NotificationsScreen() {
  const notificationsQuery = useNotificationsData(100);
  const payload = notificationsQuery.data;
  if (notificationsQuery.isError && !payload) {
    return (
      <ScreenError title="Notifications" onRetry={() => void notificationsQuery.refetch()}>
        We could not load notification delivery status. Retry once the API connection is restored.
      </ScreenError>
    );
  }
  if (!payload) return <ScreenLoading title="Notifications" />;
  return (
    <main className="content">
      <div className="page-head">
        <div>
          <h1>Notifications</h1>
          <div className="ph-sub">Email delivery status, operational notices, and investor messages.</div>
        </div>
        {payload.unread_count > 0 ? <Chip tone="warn">{payload.unread_count} unread</Chip> : <Chip tone="ok">Up to date</Chip>}
      </div>
      <Card>
        {payload.notifications.length === 0 ? (
          <Empty icon="bell" title="No notifications yet">
            Emails, confirmations, balance reminders, and operational notices will appear here.
          </Empty>
        ) : (
          <div className="notice-list">
            {payload.notifications.map((notification) => (
              <div className="notice-row" key={notification.id}>
                <div className="row gap-12" style={{ alignItems: "flex-start" }}>
                  <Icon className={notification.status === "failed" || notification.status === "dead_letter" ? "neg" : "muted"} name="bell" size={17} />
                  <div className="grow">
                    <div className="row spread gap-12">
                      <div className="col-strong">{notification.title}</div>
                      <Chip status={notification.status} />
                    </div>
                    <p className="muted-2" style={{ fontSize: 12.5, lineHeight: 1.55, marginTop: 6 }}>{notification.body}</p>
                    <div className="row gap-8 wrap muted mono" style={{ fontSize: 11, marginTop: 8 }}>
                      <span>{formatDateTime(notification.created_at)}</span>
                      <span>{notification.topic}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </main>
  );
}

function kycChipTone(status: string) {
  if (status === "approved") return "ok" as const;
  if (status === "pending" || status === "not_started") return "neutral" as const;
  if (status === "manual_review" || status === "expired" || status === "reverification_required") return "warn" as const;
  return "bad" as const;
}

function SettingsScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const queryClient = useQueryClient();
  const [marketing, setMarketing] = useState(false);
  const [marketingError, setMarketingError] = useState("");
  const [showPayoutModal, setShowPayoutModal] = useState(false);
  const authMeQuery = useV1AuthMeRetrieve({
    query: { enabled: !isFixturePreview, retry: false, staleTime: 0 }
  });
  const kycStatusQuery = useV1KycStatusRetrieve({
    query: { enabled: !isFixturePreview && !isReadonlyImpersonationActive(), retry: false, staleTime: 0 }
  });
  const fixtureProfile = displayProfile();
  const account = authMeQuery.data?.user;
  const marketingMutation = useV1AuthPreferencesMarketingPartialUpdate();
  const name = isFixturePreview ? fixtureProfile.name : account?.full_name ?? "";
  const email = isFixturePreview ? fixtureProfile.email : account?.email ?? "";
  const country = isFixturePreview ? fixtureProfile.country : "";
  const memberSince = isFixturePreview ? fixtureProfile.memberSince : "";
  const phone = isFixturePreview ? fixtureProfile.phone : "";
  const kycStatus = isFixturePreview ? "approved" : kycStatusQuery.data?.status;
  const phoneVerified = isFixturePreview
    ? true
    : kycStatusQuery.data?.phone_verified ?? account?.phone_verified;
  const balances = useBalancesData();
  const payoutInstructions = balances.data?.payout_instructions ?? [];
  useEffect(() => {
    if (account) setMarketing(account.marketing_consent);
  }, [account]);

  const changeMarketingConsent = (nextValue: boolean) => {
    setMarketingError("");
    if (isFixturePreview) {
      setMarketing(nextValue);
      return;
    }
    marketingMutation.mutate(
      { data: { marketing_consent: nextValue } },
      {
        onSuccess: (response) => {
          setMarketing(response.user.marketing_consent);
          void queryClient.invalidateQueries();
        },
        onError: (mutationError) => {
          setMarketing(account?.marketing_consent ?? false);
          setMarketingError(apiErrorMessage(mutationError));
        }
      }
    );
  };
  return (
    <main className="content narrow">
      <div className="page-head"><div><h1>Settings</h1><div className="ph-sub">Profile, verification, payout accounts and preferences.</div></div></div>
      <div className="col gap-16">
        <Card><div className="card-head"><h3>Profile</h3></div><div className="card-pad"><dl className="kv">{name ? <KeyValueRow label="Name" value={name} /> : null}{email ? <KeyValueRow label="Email" mono value={email} /> : null}{country ? <KeyValueRow label="Country" value={country} /> : null}{memberSince ? <KeyValueRow label="Member since" mono value={formatDate(memberSince)} /> : null}</dl><p className="muted" style={{ fontSize: 11.5, marginTop: 12 }}>Name or email changes are handled through support after identity re-verification.</p></div></Card>
        <Card><div className="card-head"><h3>Verification</h3></div><div className="card-pad col gap-12"><div className="row spread"><span className="row gap-8"><Icon className="muted" name="shield" size={16} />Identity (KYC/AML)</span>{kycStatus ? <Chip tone={kycChipTone(kycStatus)}>{humanizeToken(kycStatus)}</Chip> : <span className="muted">-</span>}</div><div className="hr" /><div className="row spread"><span className="row gap-8"><Icon className="muted" name="phone" size={16} />{phone ? `Phone ${phone}` : "Phone"}</span>{phoneVerified === undefined ? <span className="muted">-</span> : <Chip status={phoneVerified ? "verified" : "pending"} tone={phoneVerified ? "ok" : "neutral"} />}</div></div></Card>
        <Card>
          <div className="card-head"><h3>Payout accounts</h3><Button disabled={isReadonlyImpersonationActive()} size="sm" variant="ghost" onClick={() => setShowPayoutModal(true)}>Add/update IBAN</Button></div>
          <div className="card-pad col gap-12">
            {balances.isError && !isFixturePreview ? <Banner tone="bad" title="Could not load payout accounts">Retry after signing in or when the API connection is restored.</Banner> : null}
            {payoutInstructions.length === 0 ? (
              <p className="muted" style={{ fontSize: 12 }}>No payout IBAN is on file yet. Add one so Garanta can review it for withdrawals and forced-return handling.</p>
            ) : payoutInstructions.map((instruction) => (
              <div className="row spread wrap" key={instruction.id}>
                <span>
                  <div className="col-strong mono">{instruction.destination_iban}</div>
                  <div className="sub">{instruction.currency} · {instruction.destination_account_name}</div>
                </span>
                <Chip tone={instruction.is_verified_usable ? "ok" : "warn"}>
                  {instruction.is_verified_usable ? "Verified usable" : "Pending Garanta verification"}
                </Chip>
              </div>
            ))}
            <Banner tone="info" title="Verification required">Submitting a new payout IBAN does not make it usable automatically. Garanta must verify the account before it can be used for withdrawals or forced returns.</Banner>
          </div>
        </Card>
        <Card><div className="card-head"><h3>Communication</h3></div><div className="card-pad col gap-10"><label className="row spread" style={{ cursor: isReadonlyImpersonationActive() ? "not-allowed" : "pointer" }}><span><div className="col-strong">Product updates and newsletter</div><div className="muted" style={{ fontSize: 12 }}>Transactional emails are mandatory.</div></span><input checked={marketing} disabled={isReadonlyImpersonationActive() || marketingMutation.isPending} onChange={(event) => changeMarketingConsent(event.target.checked)} type="checkbox" /></label>{marketingError ? <Banner tone="bad" title="Could not update preference">{marketingError}</Banner> : null}</div></Card>
        <Card><div className="card-head"><h3>Support & account</h3></div><div className="card-pad col gap-12"><div className="row spread"><span className="row gap-8"><Icon className="muted" name="info" size={16} />Help & FAQ</span><Button size="sm" variant="ghost" onClick={() => goTo(setRoute, "faq")}>Open</Button></div><div className="hr" /><div className="row spread"><span>Email support</span><a className="mono" href={`mailto:${supportEmail}`}>{supportEmail}</a></div></div></Card>
      </div>
      {showPayoutModal ? <PayoutIbanModal onClose={() => setShowPayoutModal(false)} /> : null}
    </main>
  );
}

function PayoutIbanModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [currency, setCurrency] = useState("CHF");
  const [iban, setIban] = useState("");
  const [accountName, setAccountName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const mutation = useV1LedgerPayoutInstructionsCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.bank_account_change);
  const hasValidPayoutDetails =
    currency.length === 3 && iban.replace(/\s/g, "").length >= 15 && accountName.trim().length > 1;
  useAutoRequestEmailCode(codeRequest, !done && hasValidPayoutDetails);
  const canSubmit = hasValidPayoutDetails && (isFixturePreview || (codeRequest.codeId && code.length >= 6));

  const submit = () => {
    setError("");
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    if (!codeRequest.codeId) {
      setError("Request an email code before submitting a payout IBAN change.");
      return;
    }
    mutation.mutate(
      {
        data: {
          currency,
          destination_iban: iban,
          destination_account_name: accountName,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setDone(true);
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };

  if (done) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Payout IBAN submitted">
        <SuccessState title="Pending Garanta verification">The payout instruction was recorded. It is not usable for withdrawals or forced returns until Garanta verifies it.</SuccessState>
      </Modal>
    );
  }

  return (
    <Modal footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!canSubmit || mutation.isPending} variant="primary" onClick={submit}>{mutation.isPending ? "Submitting..." : "Submit for verification"}</Button></>} onClose={onClose} title="Add/update payout IBAN">
      <div className="col gap-16">
        <Banner tone="warn" title="Adding payout details">A newly submitted IBAN is added to your existing payout accounts and remains unavailable until Garanta verifies it. Existing verified IBANs stay usable. The 60-day balance deadline is not extended.</Banner>
        <Field label="Currency">
          <select className="select" value={currency} onChange={(event) => setCurrency(event.target.value)}>
            <option value="CHF">CHF</option>
            <option value="EUR">EUR</option>
          </select>
        </Field>
        <Field label="IBAN">
          <input className="input mono" onChange={(event) => setIban(event.target.value.toUpperCase())} placeholder="CH..." value={iban} />
        </Field>
        <Field label="Account holder name">
          <input className="input" onChange={(event) => setAccountName(event.target.value)} placeholder={displayProfile().name} value={accountName} />
        </Field>
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={emailCodeRequestDisabled(codeRequest)}
          requestLabel={emailCodeRequestLabel(codeRequest)}
          value={code}
          onChange={setCode}
          onRequest={codeRequest.requestCode}
        />
        {codeRequest.expiresAt ? <p className="muted" style={{ fontSize: 11.5 }}>Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
        {codeRequest.error || error ? <Banner tone="bad" title="Could not submit payout IBAN">{codeRequest.error || error}</Banner> : null}
      </div>
    </Modal>
  );
}

function KycStatusScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const statusQuery = useV1KycStatusRetrieve({
    query: {
      enabled: !isFixturePreview,
      retry: false,
      // While capture is still open (possibly on another device), poll until
      // the provider reports a result.
      refetchInterval: (query) => {
        const caseStatus = query.state.data?.status;
        return caseStatus === "not_started" || caseStatus === "pending" ? 4000 : false;
      }
    }
  });
  const sessionMutation = useV1KycSessionCreate();
  const [error, setError] = useState("");
  const kycStatus = isFixturePreview ? "manual_review" : statusQuery.data?.status;
  const isApproved = kycStatus === "approved";
  const isWaitingForProvider = kycStatus === "pending";
  const canStartKyc =
    !isFixturePreview &&
    (kycStatus === "not_started" ||
      kycStatus === "expired" ||
      kycStatus === "reverification_required");

  useEffect(() => {
    if (!isFixturePreview && statusQuery.data?.financial_access_allowed) {
      goTo(setRoute, "dashboard");
    }
  }, [setRoute, statusQuery.data?.financial_access_allowed]);

  const startKyc = () => {
    setError("");
    if (isFixturePreview) return;
    sessionMutation.mutate(undefined, {
      onSuccess: (response) => {
        if (response.verification_url) {
          window.location.assign(response.verification_url);
        }
      },
      onError: (mutationError) => setError(apiErrorMessage(mutationError))
    });
  };
  const bannerTitle = isApproved
    ? "Verification approved"
    : canStartKyc
      ? "Identity verification required"
      : isWaitingForProvider
        ? "Waiting for verification result"
        : "Manual review";
  const bannerMessage = isApproved
    ? "Financial access is available if phone verification and account status are also valid."
    : canStartKyc
      ? "Start identity verification with Didit. After you finish capture, this page will wait for the provider and compliance result."
      : isWaitingForProvider
        ? `Your identity capture has been submitted. We are waiting for Didit and ${operatorName} compliance to confirm the result. This page updates automatically. If it remains here for more than a few minutes, contact ${supportEmail}.`
        : `Your case is being reviewed by ${operatorName}. Financial actions remain locked until KYC is approved. Contact ${supportEmail} if this takes longer than expected.`;

  if (!isFixturePreview && statusQuery.isPending && !statusQuery.data) {
    return <ScreenLoading title="Verification" />;
  }

  return (
    <main className="content narrow">
      <div className="page-head"><div><h1>Verification</h1><div className="ph-sub">KYC provider handoff and Garanta compliance status.</div></div></div>
      <Card padded>
        <KycTimeline current={isApproved ? "approved" : kycStatus === "not_started" ? "pending" : "manual_review"} />
        {statusQuery.isError && !isFixturePreview ? <Banner tone="bad" title="Could not load KYC status">Retry after signing in or when the API connection is restored.</Banner> : null}
        <Banner tone={isApproved ? "ok" : "info"} title={bannerTitle}>
          {bannerMessage}
        </Banner>
        {canStartKyc ? (
          <Button disabled={sessionMutation.isPending} style={{ marginTop: 16 }} variant="ghost" onClick={startKyc}>
            {sessionMutation.isPending ? "Starting Didit..." : "Start Didit verification"}
          </Button>
        ) : null}
        {error ? <Banner tone="bad" title="Could not start KYC">{error}</Banner> : null}
        {statusQuery.data?.financial_access_allowed || isFixturePreview ? (
          <Button style={{ marginTop: 16 }} variant="primary" onClick={() => goTo(setRoute, "dashboard")}>Back to dashboard</Button>
        ) : null}
      </Card>
    </main>
  );
}

function KycTimeline({ current }: { current: "pending" | "manual_review" | "approved" }) {
  const steps = [
    { key: "account", title: "Account created", desc: "Registration terms accepted." },
    { key: "phone", title: "Phone verified", desc: "SMS confirmation complete." },
    { key: "kyc", title: "Didit verification", desc: current === "approved" ? "Approved." : "Provider review in progress." },
    { key: "access", title: "Financial access", desc: "Deposits and investing unlock after approval." }
  ];
  const activeIndex = current === "approved" ? 3 : 2;
  return (
    <div className="timeline">
      {steps.map((step, index) => (
        <div className="tl-item" key={step.key}>
          <div className="tl-rail"><div className={`tl-node ${index < activeIndex ? "done" : index === activeIndex ? "cur" : ""}`}>{index < activeIndex ? "✓" : index + 1}</div>{index < steps.length - 1 ? <div className={`tl-line ${index < activeIndex ? "done" : ""}`} /> : null}</div>
          <div className="tl-content"><div className="tl-title">{step.title}</div><div className="tl-desc">{step.desc}</div></div>
        </div>
      ))}
    </div>
  );
}

type FaqSection = {
  title: string;
  summary: string;
  items: Array<{ question: string; answer: ReactNode }>;
};

const faqSections: FaqSection[] = [
  {
    title: "How BANXUM works",
    summary: "The platform connects individual lenders with project-specific business-loan opportunities.",
    items: [
      {
        question: `What is ${platformName}?`,
        answer: (
          <>
            {platformName} is a peer-to-peer lending platform operated by {operatorName}. Individual
            lenders can buy participations in loan claims originated, documented and serviced by the
            operator.
          </>
        )
      },
      {
        question: "Who are the parties in a typical loan?",
        answer: (
          <>
            A borrower receives financing, lenders fund loan-claim participations, {operatorName} operates
            the platform and servicing process, and Didit supports identity verification. The platform is
            not a bank deposit product, fund, exchange, or guaranteed-return product.
          </>
        )
      },
      {
        question: "Is every loan secured?",
        answer: (
          <>
            Security is disclosed per project. A loan may have collateral, guarantees, other security, or an
            expressly disclosed unsecured exception. Security can reduce loss risk but never guarantees repayment
            or full recovery after borrower default.
          </>
        )
      }
    ]
  },
  {
    title: "Account and verification",
    summary: "Registration, phone verification and KYC must be complete before financial access unlocks.",
    items: [
      {
        question: "Who can register online?",
        answer: (
          <>
            The online flow is for individual lenders in Switzerland and EU/EEA countries. Legal entities are
            onboarded by {operatorName} off-platform.
          </>
        )
      },
      {
        question: "Why do I need phone verification and KYC?",
        answer: (
          <>
            Phone verification confirms account contact details. KYC confirms identity and helps satisfy AML
            and investor-protection controls. Until those checks are complete, deposits and investing remain
            locked.
          </>
        )
      },
      {
        question: "What happens if KYC is under review?",
        answer: (
          <>
            Your verification screen updates automatically as soon as the provider returns a result. If the
            case is routed to manual review, financial actions stay locked until {operatorName} approves the
            account — no action is needed from you in the meantime.
          </>
        )
      }
    ]
  },
  {
    title: "Balances and deadlines",
    summary: "Operational balances are controlled by 30-day and 60-day regulatory ageing rules.",
    items: [
      {
        question: "How do I add funds?",
        answer: (
          <>
            Open Balances and choose Add Funds. You will see the collection account (IBAN) for each enabled
            currency together with your personal payment reference. Send a normal bank transfer from your own
            account in the same currency and include the reference exactly as shown — it is how your payment
            is matched to your account. Your balance is credited once {operatorName} reconciles the incoming
            payment.
          </>
        )
      },
      {
        question: "Are platform balances like a bank account?",
        answer: (
          <>
            No. Platform balances are non-interest-bearing operational funds held for investing, FX or
            withdrawal workflows. They are not bank deposits and are subject to ageing controls.
          </>
        )
      },
      {
        question: "How long can money remain uninvested?",
        answer: (
          <>
            Newly received funds are investable for 30 days. After day 30 they become withdraw-only, and by
            day 60 they must leave the platform — either through your own withdrawal or the platform's return
            process.
          </>
        )
      },
      {
        question: "What happens at the 60-day deadline?",
        answer: (
          <>
            If a verified usable payout IBAN is on file, the system can create a forced withdrawal. If there is
            no usable IBAN, money-moving actions are blocked and the overdue balance can enter penalty mode.
            The 60-day limit cannot be extended.
          </>
        )
      }
    ]
  },
  {
    title: "Investing and orders",
    summary: "Orders are intents first; they become effective only after funds are allocated.",
    items: [
      {
        question: "Does placing an order reserve loan capacity?",
        answer: (
          <>
            No. An order is an investment intent. It becomes effective only when eligible funds are allocated
            and validated on a first-come, first-served basis.
          </>
        )
      },
      {
        question: "Can an order be partially filled?",
        answer: (
          <>
            Yes. If remaining capacity is lower than your requested amount, the platform may allocate only the
            available part, subject to platform rules and available eligible balance.
          </>
        )
      },
      {
        question: "What do I agree to when investing?",
        answer: (
          <>
            Each investment requires current investment terms and risk acknowledgements. The accepted document
            version, timestamp, checkbox labels and context are recorded as immutable evidence.
          </>
        )
      },
      {
        question: "What fees do lenders pay?",
        answer: (
          <>
            Every fee that applies to an action — for example secondary-market transaction fees or the
            currency-exchange fee — is shown in that flow before you confirm, together with the exact amounts.
            Nothing is charged without being displayed first.
          </>
        )
      }
    ]
  },
  {
    title: "Repayments, portfolio and risk",
    summary: "Repayments credit lender balances; borrower delay or default can reduce expected returns.",
    items: [
      {
        question: "How do repayments reach me?",
        answer: (
          <>
            Borrower repayments are distributed to current holders according to their outstanding principal.
            Principal and interest credits appear in your balance and activity history.
          </>
        )
      },
      {
        question: "Can I lose money?",
        answer: (
          <>
            Yes. Borrowers can pay late, pay partially, default, or become subject to recovery proceedings.
            Collateral, guarantees or security may not fully cover losses or may take time and cost to enforce.
          </>
        )
      },
      {
        question: "Why do holdings sometimes show late or default status?",
        answer: (
          <>
            Loan status follows the servicing process. Late/default statuses are based on overdue installments
            and are shown so lenders can assess current risk before holding or selling.
          </>
        )
      }
    ]
  },
  {
    title: "Secondary market and FX",
    summary: "Selling and currency conversion are available only under platform controls.",
    items: [
      {
        question: "Can I sell before maturity?",
        answer: (
          <>
            You can list an entire holding on the secondary market when the platform permits it. Liquidity is
            not guaranteed, and non-performing or non-standard listings require additional acknowledgement or
            admin approval.
          </>
        )
      },
      {
        question: "Does a buyer see who the seller is?",
        answer: (
          <>
            No. Buyer-facing secondary-market views are counterparty-redacted. Buyers see loan, price, fee,
            risk and disclosure fields, not the seller identity.
          </>
        )
      },
      {
        question: "Does converting currency reset the ageing clock?",
        answer: (
          <>
            No. FX is a settlement function, not a way to restart deadlines. Converted balance inherits the
            deadlines of the funds you converted — it never receives a fresh 30/60-day timer.
          </>
        )
      }
    ]
  },
  {
    title: "Documents, reports and support",
    summary: "Accepted documents and statements remain available from the portal.",
    items: [
      {
        question: "Where can I find terms I accepted?",
        answer: (
          <>
            Open Documents in the portal. The system lists historical accepted document versions, and the full
            accepted PDF can be generated from immutable evidence when needed.
          </>
        )
      },
      {
        question: "Can I download account statements or tax documents?",
        answer: (
          <>
            Yes. Account statements and annual tax summaries can be downloaded from the Documents section once
            they are available. Every download is scoped to your own account.
          </>
        )
      },
      {
        question: "How do I contact support?",
        answer: (
          <>
            Email <a href={`mailto:${supportEmail}`}>{supportEmail}</a>. Include your investor reference if
            you have one, but do not send passwords, one-time codes or identity-document images by email unless
            support explicitly instructs you.
          </>
        )
      }
    ]
  }
];

function FaqContent() {
  const [open, setOpen] = useState("0-0");
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Help & FAQ</h1>
          <div className="ph-sub">
            Plain-English answers on onboarding, balances, orders, risk, FX, documents and the secondary market.
          </div>
        </div>
      </div>
      <div className="faq-intro">
        <div>
          <div className="eyebrow">Before investing</div>
          <h2>Know the operating rules before moving money</h2>
          <p>
            {platformName} is built for peer-to-peer business lending. These answers summarize the user-facing
            flow; the legally binding wording is the document version you accept in the platform.
          </p>
        </div>
        <div className="faq-support">
          <div className="muted">Need help?</div>
          <a className="mono" href={`mailto:${supportEmail}`}>{supportEmail}</a>
        </div>
      </div>
      <div className="faq-sections">
        {faqSections.map((section, sectionIndex) => (
          <Card key={section.title}>
            <div className="faq-section-head">
              <div>
                <h2>{section.title}</h2>
                <p>{section.summary}</p>
              </div>
            </div>
            {section.items.map((item, itemIndex) => {
              const key = `${sectionIndex}-${itemIndex}`;
              const isOpen = open === key;
              return (
                <div className="faq-row" key={item.question}>
                  <button
                    className="faq-q"
                    onClick={() => setOpen(isOpen ? "" : key)}
                    type="button"
                  >
                    <span>{item.question}</span>
                    <Icon className="muted" name={isOpen ? "chevD" : "chevR"} size={16} />
                  </button>
                  {isOpen ? <div className="faq-a">{item.answer}</div> : null}
                </div>
              );
            })}
          </Card>
        ))}
      </div>
      <Banner tone="warn" title="Risk warning">
        Investing through {platformName} involves risk of capital loss, borrower default, late payment,
        illiquidity, enforcement cost and no guaranteed return.
      </Banner>
    </>
  );
}

function PublicFaqPage({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  return (
    <div className="public">
      <header className="public-top">
        <Wordmark />
        <div className="grow" />
        <nav className="public-nav" aria-label="Public navigation">
          <a href="/" onClick={(event) => { event.preventDefault(); goTo(setRoute, "public"); }}>Investment opportunities preview</a>
          <span aria-current="page">FAQ</span>
        </nav>
        <Button variant="ghost" onClick={() => goTo(setRoute, "login")}>
          Log in
        </Button>
        <Button variant="primary" onClick={() => goTo(setRoute, "register")}>
          Register
        </Button>
      </header>
      <main className="public-body public-faq">
        <div className="public-mobile-links" aria-label="Public links">
          <button className="btn-link" onClick={() => goTo(setRoute, "public")} type="button">
            Investment opportunities preview
          </button>
          <button className="btn-link" onClick={() => goTo(setRoute, "register")} type="button">
            Register
          </button>
        </div>
        <FaqContent />
        <div className="faq-cta">
          <Button variant="ghost" onClick={() => goTo(setRoute, "public")}>Back to marketplace</Button>
          <Button variant="primary" onClick={() => goTo(setRoute, "register")}>Create lender account</Button>
        </div>
      </main>
    </div>
  );
}

function FaqScreen() {
  return (
    <main className="content narrow">
      <FaqContent />
    </main>
  );
}

function LegalDocumentPage() {
  const category = window.location.pathname
    .replace(/^\/legal\//, "")
    .replace(/\/+$/, "")
    .replace(/-/g, "_");
  const known = category in legalDocumentTitles;
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const templateQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: category as CategoryEnum, template_key: "default", language: "en" },
    { query: { enabled: !isFixturePreview && known, retry: false } }
  );
  const doc = templateQuery.data;
  const title = doc?.title ?? legalDocumentTitles[category] ?? "Document";

  const download = async () => {
    setDownloadError("");
    setDownloading(true);
    try {
      const response = await fetch(
        `/api/v1/documents/templates/current/artifact/?category=${encodeURIComponent(category)}`
      );
      if (!response.ok) throw new Error(`Download failed (${response.status}).`);
      const payload = (await response.json()) as { content: string; content_type: string; filename: string };
      const bytes = Uint8Array.from(atob(payload.content), (char) => char.charCodeAt(0));
      const blob = new Blob([bytes], { type: payload.content_type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = payload.filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="public">
      <header className="public-top">
        <Wordmark />
        <div className="grow" />
        <Button variant="ghost" onClick={() => window.location.assign("/")}>Open {platformName}</Button>
      </header>
      <main className="public-body legal-doc">
        {!known ? (
          <Card padded>
            <Empty icon="doc" title="Document not found">
              This document address is not recognized. Open {platformName} and use the links in each flow.
            </Empty>
          </Card>
        ) : (
          <>
            <div className="page-head">
              <div>
                <h1>{title}</h1>
                <div className="ph-sub">
                  The exact server-published version you accept in the platform. Values in brackets are
                  filled with your transaction data at acceptance time.
                </div>
              </div>
              <Button disabled={downloading || isFixturePreview} icon="doc" variant="primary" onClick={download}>
                {downloading ? "Preparing PDF..." : "Download PDF"}
              </Button>
            </div>
            {downloadError ? <Banner tone="bad" title="Download failed">{downloadError}</Banner> : null}
            <Card padded>
              {isFixturePreview ? (
                <p className="muted">Preview mode: live document content loads from the published server template.</p>
              ) : templateQuery.isLoading ? (
                <p className="muted">Loading the current published document...</p>
              ) : doc ? (
                <>
                  <div className="legal-doc-meta">
                    <Chip status={`v${doc.version_number}`} tone="info" />
                    <span className="muted mono">hash {doc.content_hash.slice(0, 16)}</span>
                    {doc.published_at ? (
                      <span className="muted">published {formatDate(doc.published_at)}</span>
                    ) : null}
                  </div>
                  <div className="legal-document-preview legal-doc-body">{renderLegalBody(doc.body)}</div>
                  {Array.isArray(doc.checkbox_labels) && doc.checkbox_labels.length > 0 ? (
                    <div className="legal-doc-acks">
                      <h5>You will be asked to confirm</h5>
                      <ul>
                        {(doc.checkbox_labels as string[]).map((label) => (
                          <li key={label}>{label}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </>
              ) : (
                <Banner tone="bad" title="Document unavailable">
                  The current published document could not be loaded. Retry, or contact {supportEmail}.
                </Banner>
              )}
            </Card>
          </>
        )}
      </main>
    </div>
  );
}

function OriginatorClaimInvestModal({ loan, onClose, initialAmount }: { loan: MarketplaceLoanDetail; onClose: () => void; initialAmount?: string }) {
  const queryClient = useQueryClient();
  const balances = useBalancesData().data;
  const investableLots = currentInvestableLotsForLoanCurrency(balances?.lots, loan);
  const investableBalanceMinor = sumLotAvailableMinor(investableLots);
  const maxInvest = Math.min(investableBalanceMinor, loan.fillable_amount_minor);
  const [amount, setAmount] = useState(initialAmount ?? "");
  const [step, setStep] = useState<"amount" | "review" | "confirm" | "done">("amount");
  const [ack1, setAck1] = useState(false);
  const [ack2, setAck2] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [quote, setQuote] = useState<OriginatorClaimQuoteResponse | null>(null);
  const [acceptanceId, setAcceptanceId] = useState<string | null>(null);
  const [acceptanceKey] = useState(() => idempotencyKey("originator-claim-acceptance"));
  const [purchaseKey] = useState(() => idempotencyKey("originator-claim-purchase"));
  const quoteMutation = useOriginatorClaimsLoansQuoteCreate();
  const purchaseMutation = useOriginatorClaimsQuotesPurchaseCreate();
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.primary_investment);
  useAutoRequestEmailCode(codeRequest, step === "confirm");
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.primary_market_investment },
    { query: { enabled: !isFixturePreview && step !== "amount", retry: false } }
  );
  const parsedAmount = parseMoneyInputToMinorUnits(amount, loan.currency);
  const amountMinor = parsedAmount.amountMinor;
  const amountError = parsedAmount.error
    ?? (amountMinor > 0 && amountMinor < loan.minimum_investment_minor
      ? `Minimum investment is ${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)}.`
      : amountMinor > maxInvest
        ? "Exceeds investable balance or the executable amount currently available."
        : undefined);

  const requestQuote = async () => {
    setError("");
    if (amountError || amountMinor <= 0) return;
    if (isFixturePreview) {
      const assignedPrincipal = Math.min(amountMinor, loan.remaining_capacity_minor);
      setQuote({
        quote_id: "preview-originator-quote",
        loan_id: loan.loan_id,
        currency: loan.currency,
        requested_cash_minor: amountMinor,
        executable_cash_minor: amountMinor,
        assigned_principal_minor: assignedPrincipal,
        outstanding_principal_at_pricing_minor: loan.principal_minor,
        share_ppm: loan.principal_minor > 0 ? Math.round((assignedPrincipal * 1_000_000) / loan.principal_minor) : 0,
        target_yield_bps: loan.yield_bps,
        premium_discount_minor: amountMinor - assignedPrincipal,
        rounding_remainder_minor: 0,
        entitlement_start_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
        cash_flows: (loan.originator_schedule ?? []).filter((row) => Date.parse(row.due_date) > Date.now()).map((row) => ({
          installment_number: row.installment_number,
          accrual_start_date: row.accrual_start_date,
          due_date: row.due_date,
          principal_minor: loan.principal_minor > 0 ? Math.round((row.principal_minor * assignedPrincipal) / loan.principal_minor) : 0,
          interest_minor: loan.principal_minor > 0 ? Math.round((row.interest_minor * assignedPrincipal) / loan.principal_minor) : 0,
          penalty_minor: 0,
          total_minor: loan.principal_minor > 0 ? Math.round((row.total_minor * assignedPrincipal) / loan.principal_minor) : 0,
          days_to_payment: Math.max(0, Math.ceil((Date.parse(row.due_date) - Date.now()) / 86_400_000)),
          present_value_minor: 0
        }))
      });
      setStep("review");
      return;
    }
    try {
      const nextQuote = await quoteMutation.mutateAsync({
        loanId: loan.loan_id,
        data: { requested_cash_minor: amountMinor }
      });
      setQuote(nextQuote);
      setStep("review");
    } catch (mutationError) {
      setError(apiErrorMessage(mutationError));
    }
  };

  const confirmPurchase = async () => {
    if (!quote) return;
    setError("");
    if (isFixturePreview) {
      setStep("done");
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError("Current primary-market investment terms are unavailable.");
      return;
    }
    if (!codeRequest.codeId) {
      setError("Request an email code before confirming the purchase.");
      return;
    }
    try {
      const acceptance = acceptanceId
        ? { id: acceptanceId }
        : await acceptanceMutation.mutateAsync({
            data: {
              category: CategoryEnum.primary_market_investment,
              expected_template_version_id: termsQuery.data.id,
              accepted_checkbox_labels: labels,
              context_type: "originator_claim_quote",
              context_id: quote.quote_id,
              data_snapshot: {
                loan_id: loan.loan_id,
                originator_claim_quote_id: quote.quote_id,
                requested_cash_minor: quote.requested_cash_minor,
                executable_cash_minor: quote.executable_cash_minor,
                assigned_principal_minor: quote.assigned_principal_minor,
                currency: quote.currency,
                target_yield_bps: quote.target_yield_bps
              },
              idempotency_key: acceptanceKey
            }
          });
      setAcceptanceId(acceptance.id);
      await purchaseMutation.mutateAsync({
        quoteId: quote.quote_id,
        data: {
          document_acceptance_id: acceptance.id,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          idempotency_key: purchaseKey
        }
      });
      void queryClient.invalidateQueries();
      setStep("done");
    } catch (mutationError) {
      setError(apiErrorMessage(mutationError));
    }
  };

  const busy = quoteMutation.isPending || acceptanceMutation.isPending || purchaseMutation.isPending;
  const footer = step === "done"
    ? <Button variant="primary" onClick={onClose}>Done</Button>
    : step === "confirm"
      ? <><Button variant="ghost" onClick={() => setStep("review")}>Back</Button><Button disabled={code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || busy} variant="primary" onClick={() => void confirmPurchase()}>{busy ? "Purchasing..." : "Purchase claim"}</Button></>
      : step === "review"
        ? <><Button variant="ghost" onClick={() => { setQuote(null); setStep("amount"); }}>Reprice</Button><Button disabled={!ack1 || !ack2 || !quote} variant="primary" onClick={() => setStep("confirm")}>Continue</Button></>
        : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={amountMinor <= 0 || Boolean(amountError) || quoteMutation.isPending} variant="primary" onClick={() => void requestQuote()}>{quoteMutation.isPending ? "Pricing..." : "Get executable quote"}</Button></>;

  return (
    <Modal footer={footer} onClose={onClose} title={step === "done" ? "Claim purchased" : `Buy claim - ${loan.title}`} wide>
      {step === "amount" ? (
        <div className="col gap-16">
          <Banner tone="info" title="Immediate legal assignment">
            This is an existing final-borrower loan sold by {loan.originator_name || "the loan originator"}.
            BANXUM prices the remaining cash flows to the displayed yield and assigns the purchased claim immediately.
          </Banner>
          <div className="row spread"><span className="muted">Investable {loan.currency} balance</span><span className="mono col-strong">{loan.currency} {formatMoneyMinor(investableBalanceMinor, loan.currency)}</span></div>
          {investableBalanceMinor === 0 ? <Banner tone="bad" title="No investable balance">Deposit fresh funds or use balance still inside its 30-day investment window.</Banner> : null}
          <Field error={amountError} hint={`Minimum ${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)} · up to ${loan.currency} ${formatMoneyMinor(maxInvest, loan.currency)}`} label="Cash amount to invest">
            <div className="input-affix"><span className="prefix">{loan.currency}</span><input className="input mono" inputMode="decimal" onChange={(event) => setAmount(event.target.value.replace(/[^0-9.]/g, ""))} placeholder="0.00" style={{ paddingLeft: 44 }} value={amount} /></div>
          </Field>
          <Review rows={[
            { label: "Investor yield", value: `${formatRateBps(loan.yield_bps)} effective annual · ACT/365` },
            { label: "Underlying borrower coupon", value: `${formatRateBps(loan.underlying_interest_rate_bps)} p.a.` },
            { label: "Maturity", value: loan.maturity_date ? formatDate(loan.maturity_date) : "Not available" },
            { label: "Available claim principal", value: `${loan.currency} ${formatMoneyMinor(loan.remaining_capacity_minor, loan.currency)}` }
          ]} />
          {error ? <Banner tone="bad" title="Could not price this claim">{error}</Banner> : null}
        </div>
      ) : step === "review" && quote ? (
        <div className="col gap-16">
          <Banner tone="neutral" title="Executable for five minutes">
            The cash price changes as time passes or the borrower repays. This quote expires {formatDateTime(quote.expires_at)}.
          </Banner>
          <Review rows={[
            { label: "Loan", value: loan.title },
            { label: "Loan originator", value: loan.originator_name || "Loan originator" },
            { label: "Cash consideration", value: `${quote.currency} ${formatMoneyMinor(quote.executable_cash_minor, quote.currency)}` },
            { label: "Legal principal assigned", value: `${quote.currency} ${formatMoneyMinor(quote.assigned_principal_minor, quote.currency)}` },
            { label: quote.premium_discount_minor >= 0 ? "Premium" : "Discount", value: `${quote.currency} ${formatMoneyMinor(Math.abs(quote.premium_discount_minor), quote.currency)}` },
            { label: "Target yield", value: `${formatRateBps(quote.target_yield_bps)} effective annual · ACT/365` },
            { label: "Entitlement starts", value: formatDateTime(quote.entitlement_start_at) }
          ]} />
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Your quoted cash flows</div>
            <div className="tbl-wrap">
              <table className="tbl"><thead><tr><th className="num">#</th><th>Due date</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Total</th></tr></thead><tbody>{quote.cash_flows.map((flow) => <tr key={`${flow.installment_number}-${flow.due_date}`}><td className="num muted">{flow.installment_number}</td><td>{formatDate(flow.due_date)}</td><td className="num">{formatMoneyMinor(flow.principal_minor, quote.currency)}</td><td className="num">{formatMoneyMinor(flow.interest_minor, quote.currency)}</td><td className="num col-strong">{formatMoneyMinor(flow.total_minor, quote.currency)}</td></tr>)}</tbody><tfoot className="schedule-totals"><tr><th colSpan={2}>Totals</th><th className="num">{formatMoneyMinor(quote.cash_flows.reduce((sum, row) => sum + row.principal_minor, 0), quote.currency)}</th><th className="num">{formatMoneyMinor(quote.cash_flows.reduce((sum, row) => sum + row.interest_minor, 0), quote.currency)}</th><th className="num">{formatMoneyMinor(quote.cash_flows.reduce((sum, row) => sum + row.total_minor, 0), quote.currency)}</th></tr></tfoot></table>
            </div>
          </div>
          <Check checked={ack1} id="originator-claim-ack-1" onChange={setAck1}>I accept the <LegalDocLink category="primary_market_investment">primary-market investment terms and claim assignment</LegalDocLink>.</Check>
          <Check checked={ack2} id="originator-claim-ack-2" onChange={setAck2}>I acknowledge the <LegalDocLink category="risk_disclosure">risk disclosure</LegalDocLink>, originator servicing structure and possible capital loss.</Check>
          {!isFixturePreview && termsQuery.isError ? <Banner tone="bad" title="Investment terms unavailable">The current server-published investment terms could not be loaded.</Banner> : null}
        </div>
      ) : step === "confirm" && quote ? (
        <div className="col gap-16">
          <Banner icon="lock" tone="info" title="Confirm this claim purchase">Enter the 6-digit email confirmation code. A successful confirmation immediately assigns the claim and adds it to your portfolio.</Banner>
          <Review rows={[{ label: "Cash consideration", value: `${quote.currency} ${formatMoneyMinor(quote.executable_cash_minor, quote.currency)}` }, { label: "Principal assigned", value: `${quote.currency} ${formatMoneyMinor(quote.assigned_principal_minor, quote.currency)}` }, { label: "Yield", value: formatRateBps(quote.target_yield_bps) }, { label: "Quote expires", value: formatDateTime(quote.expires_at) }]} />
          <CodeRequestField hint={previewHint("Demo: any 6 digits")} label="Email confirmation code" requestDisabled={emailCodeRequestDisabled(codeRequest)} requestLabel={emailCodeRequestLabel(codeRequest)} value={code} onChange={setCode} onRequest={codeRequest.requestCode} />
          {codeRequest.error || error ? <Banner tone="bad" title="Could not purchase claim">{codeRequest.error || error}</Banner> : null}
        </div>
      ) : (
        <SuccessState title="Claim purchased">The assigned final-borrower claim is now in your portfolio. Its immutable acceptance evidence is available in Documents.</SuccessState>
      )}
    </Modal>
  );
}

function InvestModal({ loan, onClose, initialAmount }: { loan: MarketplaceLoanDetail; onClose: () => void; initialAmount?: string }) {
  const queryClient = useQueryClient();
  const balances = useBalancesData().data;
  const investableLots = currentInvestableLotsForLoanCurrency(balances?.lots, loan);
  const investableBalanceMinor = sumLotAvailableMinor(investableLots);
  const maxInvest = Math.min(investableBalanceMinor, loan.remaining_capacity_minor);
  const [amount, setAmount] = useState(initialAmount ?? "");
  const [step, setStep] = useState<"amount" | "review" | "confirm" | "done">(initialAmount ? "review" : "amount");
  const [ack1, setAck1] = useState(false);
  const [ack2, setAck2] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [orderId, setOrderId] = useState<string | null>(null);
  const [acceptanceId, setAcceptanceId] = useState<string | null>(null);
  const [orderKey] = useState(() => idempotencyKey("primary-order"));
  const [acceptanceKey] = useState(() => idempotencyKey("primary-acceptance"));
  const [allocationKey] = useState(() => idempotencyKey("primary-allocation"));
  const orderMutation = useV1MarketplacePrimaryOrdersCreate();
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const allocateMutation = useV1MarketplacePrimaryOrdersAllocateBalanceCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.primary_investment);
  useAutoRequestEmailCode(codeRequest, step === "confirm");
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.primary_market_investment },
    { query: { enabled: !isFixturePreview && step !== "amount", retry: false } }
  );
  const parsedAmount = parseMoneyInputToMinorUnits(amount, loan.currency);
  const amountMinor = parsedAmount.amountMinor;
  const amountError =
    parsedAmount.error ??
    (amountMinor > 0 && amountMinor < loan.minimum_investment_minor
      ? `Minimum order is ${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)}.`
      : amountMinor > maxInvest
        ? "Exceeds investable balance or remaining capacity."
        : undefined);
  const footer = step === "done"
    ? <Button variant="primary" onClick={onClose}>Done</Button>
    : step === "confirm"
      ? <><Button variant="ghost" onClick={() => setStep("review")}>Back</Button><Button disabled={code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || orderMutation.isPending || acceptanceMutation.isPending || allocateMutation.isPending} variant="primary" onClick={async () => {
          setError("");
          if (isFixturePreview) {
            setStep("done");
            return;
          }
          const labels = templateLabels(termsQuery.data);
          if (!termsQuery.data || labels.length === 0) {
            setError("Current investment terms are not available. Retry after the document template is published.");
            return;
          }
          if (!codeRequest.codeId) {
            setError("Request an email code before confirming the order.");
            return;
          }
          try {
            const order = orderId
              ? { id: orderId }
              : await orderMutation.mutateAsync({
                  data: {
                    loan_id: loan.loan_id,
                    amount_minor: amountMinor,
                    idempotency_key: orderKey
                  }
                });
            const createdOrderId = order.id;
            setOrderId(createdOrderId);
            const acceptance = acceptanceId
              ? { id: acceptanceId }
              : await acceptanceMutation.mutateAsync({
                  data: {
                    category: CategoryEnum.primary_market_investment,
                    expected_template_version_id: termsQuery.data.id,
                    accepted_checkbox_labels: labels,
                    context_type: "primary_order",
                    context_id: createdOrderId,
                    data_snapshot: {
                      loan_id: loan.loan_id,
                      amount_minor: amountMinor,
                      currency: loan.currency
                    },
                    idempotency_key: acceptanceKey
                  }
                });
            setAcceptanceId(acceptance.id);
            await allocateMutation.mutateAsync({
              orderId: createdOrderId,
              data: {
                document_acceptance_id: acceptance.id,
                idempotency_key: allocationKey,
                sensitive_action_code_id: codeRequest.codeId,
                sensitive_action_code: code
              }
            });
            void queryClient.invalidateQueries();
            setStep("done");
          } catch (mutationError) {
            setError(apiErrorMessage(mutationError));
          }
        }}>{orderMutation.isPending || acceptanceMutation.isPending || allocateMutation.isPending ? "Submitting..." : "Confirm order"}</Button></>
      : step === "review"
        ? <><Button variant="ghost" onClick={() => setStep("amount")}>Back</Button><Button disabled={!ack1 || !ack2} variant="primary" onClick={() => setStep("confirm")}>Continue</Button></>
        : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={amountMinor < loan.minimum_investment_minor || Boolean(amountError)} variant="primary" onClick={() => setStep("review")}>Review order</Button></>;

  return (
    <Modal footer={footer} onClose={onClose} title={step === "done" ? "Order placed" : `Invest - ${loan.title}`}>
      {step === "amount" ? (
        <div className="col gap-16">
          <div className="row spread"><span className="muted">Investable {loan.currency} balance</span><span className="mono col-strong">{loan.currency} {formatMoneyMinor(investableBalanceMinor, loan.currency)}</span></div>
          {investableBalanceMinor === 0 ? (
            <Banner tone="bad" title="No investable balance">
              Deposit fresh funds or use balance that is still inside its 30-day investment window.
            </Banner>
          ) : null}
          <Field error={amountError} hint={`Between ${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)} and ${formatMoneyMinor(maxInvest, loan.currency)}`} label="Investment amount">
            <div className="input-affix"><span className="prefix">{loan.currency}</span><input className="input mono" inputMode="decimal" onChange={(event) => setAmount(event.target.value.replace(/[^0-9.]/g, ""))} placeholder="0.00" style={{ paddingLeft: 44 }} value={amount} /></div>
          </Field>
          <Banner tone="neutral" title="Allocation">Orders are intents only. They become effective after funds are allocated and validated, first-come first-served.</Banner>
        </div>
      ) : step === "review" ? (
        <div className="col gap-16">
          <Review rows={[{ label: "Loan", value: <span className="entity-inline"><span>{loan.title}</span><CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" /></span> }, { label: "Order amount", value: `${loan.currency} ${formatMoneyMinor(amountMinor, loan.currency)}` }, { label: "Yield", value: `${formatRateBps(marketplaceYieldBps(loan))} p.a.` }, { label: "Platform fee", value: "None" }]} />
          <Check checked={ack1} id="invest-ack-1" onChange={setAck1}>
            I accept the{" "}
            <LegalDocLink category="primary_market_investment">
              primary-market investment terms and loan claim assignment
            </LegalDocLink>
            .
          </Check>
          <Check checked={ack2} id="invest-ack-2" onChange={setAck2}>
            I acknowledge the <LegalDocLink category="risk_disclosure">risk disclosure</LegalDocLink> and
            possible capital loss.
          </Check>
          <p className="muted" style={{ fontSize: 11.5 }}>
            Documents open in a new tab where you can read and download them.{" "}
            {!isFixturePreview && termsQuery.data
              ? `Your acceptance is recorded against ${termsQuery.data.title} v${termsQuery.data.version_number}, timestamp, order amount and loan context.`
              : "Your acceptance is recorded against the exact server-published document version, timestamp, order amount and loan context."}
          </p>
          {!isFixturePreview && termsQuery.isError ? (
            <Banner tone="bad" title="Investment terms unavailable">
              The current server-published investment terms could not be loaded.
            </Banner>
          ) : null}
        </div>
      ) : step === "confirm" ? (
        <div className="col gap-16">
          <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code.</Banner>
          {!isFixturePreview && termsQuery.isError ? <Banner tone="bad" title="Investment terms unavailable">The current server-published investment terms could not be loaded.</Banner> : null}
          {!isFixturePreview && termsQuery.data ? <p className="muted" style={{ fontSize: 11.5 }}>Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
          <CodeRequestField
            hint={previewHint("Demo: any 6 digits")}
            label="Email confirmation code"
            requestDisabled={emailCodeRequestDisabled(codeRequest)}
            requestLabel={emailCodeRequestLabel(codeRequest)}
            value={code}
            onChange={setCode}
            onRequest={codeRequest.requestCode}
          />
          {codeRequest.expiresAt ? <p className="muted" style={{ fontSize: 11.5 }}>Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
          {codeRequest.error || error ? <Banner tone="bad" title="Could not place order">{codeRequest.error || error}</Banner> : null}
        </div>
      ) : (
        <SuccessState title="Order placed">Your order is pending allocation. Investment evidence will be added to Documents when generated.</SuccessState>
      )}
    </Modal>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return <div className="row spread" style={{ fontSize: 13, gap: 12, marginBottom: 8 }}><span className="muted">{label}</span><span className="mono col-strong right">{value}</span></div>;
}

function KeyValueRow({ label, value, mono = false }: { label: string; value: ReactNode; mono?: boolean }) {
  return <div className="kv-row"><dt>{label}</dt><dd className={mono ? "mono" : ""}>{value}</dd></div>;
}

function SuccessState({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="col" style={{ alignItems: "center", gap: 14, padding: "8px 0", textAlign: "center" }}>
      <div className="avatar" style={{ background: "var(--ok-bg)", borderColor: "var(--ok-line)", height: 52, width: 52 }}><Icon name="check" size={26} /></div>
      <div><h3 style={{ marginBottom: 4 }}>{title}</h3><p className="muted">{children}</p></div>
    </div>
  );
}

function LoadingCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <Card><Empty icon="clock" title={title}>{children}</Empty></Card>;
}

function DataErrorCard({
  title,
  children,
  onRetry
}: {
  title: string;
  children: React.ReactNode;
  onRetry?: () => void;
}) {
  return (
    <Card>
      <div className="state-card">
        <Empty icon="alert" title={title}>{children}</Empty>
        {onRetry ? (
          <Button icon="refresh" variant="primary" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function ScreenError({
  title,
  children,
  onRetry
}: {
  title: string;
  children: React.ReactNode;
  onRetry?: () => void;
}) {
  return (
    <main className="content">
      <div className="page-head"><h1>{title}</h1></div>
      <DataErrorCard title="Could not load this screen" onRetry={onRetry}>{children}</DataErrorCard>
    </main>
  );
}

function ScreenLoading({ title }: { title: string }) {
  return <main className="content"><div className="page-head"><h1>{title}</h1></div><LoadingCard title="Loading">Loading investor portal data.</LoadingCard></main>;
}

function priceLabel(discountPremiumBps: number) {
  if (discountPremiumBps === 0) return "At par";
  return discountPremiumBps < 0 ? `${Math.abs(discountPremiumBps / 100).toFixed(1)}% discount` : `${(discountPremiumBps / 100).toFixed(1)}% premium`;
}
