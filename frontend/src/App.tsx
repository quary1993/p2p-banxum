//IP of Webby-Soft SRL.
// build-origin: ATEW5bUMtfGj80bXzkGFbtEIwTx0cb6Qig3qkx90kV_Srfdc012ga6e8Ddq5v4qj1nbItbZAfx4ZDA==
import { useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ComponentProps, type FormEvent, type ReactNode } from "react";
import { AdminApp } from "./adminConsole/AdminApp";
import {
  ActionEnum,
  CategoryEnum,
  DocumentKindEnum,
  InvestorDocumentDownloadRequestOutputFormatEnum,
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
  useV1InvestorSmartInvestUpdate,
  useMarketplacePrimaryOrdersBatchCreate,
  originatorClaimsLoansQuoteCreate,
  v1AuthMeRetrieve,
  useOriginatorClaimsLoansQuoteCreate,
  useOriginatorClaimsQuotesPurchaseCreate,
  v1AuthMagicLinkConsumeCreate
} from "./api/generated/banxumApi";
import { ApiClientError } from "./api/client/httpClient";
import { intentIdempotencyKey } from "./api/client/idempotency";
import {
  clearReadonlyImpersonation,
  readReadonlyImpersonationLabel,
  readReadonlyImpersonationToken
} from "./api/client/impersonation";
import {
  clearSessionExpiredNotice,
  hasSessionExpiredNotice,
  onSessionExpired
} from "./api/client/sessionExpiry";
import type {
  ActivityEntry,
  BalanceLot,
  FxQuotePreview,
  FxQuote,
  InvestorDocument,
  InvestorDocumentDownloadResponse,
  InvestorNotification,
  MarketplaceLoanDetail,
  MarketplaceLoanPreview,
  OriginatorClaimQuoteResponse,
  PayoutInstruction,
  PrimaryInvestmentOrder,
  PrimaryOrderBatchResponse,
  PublicDocumentTemplateVersion,
  SmartInvestOpportunity,
  SmartInvestResponse,
  SmartInvestRule,
  UserSummary
} from "./api/generated/banxumApi";
import {
  useActivityData,
  useBalancesData,
  useDashboardData,
  useDepositInstructionsData,
  useDocumentsData,
  useFxData,
  useFxFeature,
  useLoanDetailData,
  useMarketplaceLoansData,
  useNotificationReadActions,
  useNotificationsData,
  usePortfolioData,
  useSmartInvestData,
  isFixturePreview
} from "./investorPortal/data";
import { portalFixture } from "./investorPortal/fixtures";
import {
  FrozenAccountContext,
  frozenAccountFromBalances,
  frozenActionReason,
  payoutInstructionState,
  useFrozenAccount,
  withdrawableMinor
} from "./investorPortal/accountState";
import { FrozenAccountBanner, PendingWithdrawalsList } from "./investorPortal/AccountStatus";
import { isNotFoundError, isSignedOutError, retryTransientSessionError } from "./investorPortal/session";
import { handleTabListKeyDown, useDialog } from "./investorPortal/dialog";
import { platformTodayKey, platformTodayLocalDate, rememberPlatformBusinessDate } from "./investorPortal/platformClock";
import {
  hasSmartInvestCriteria,
  mkAnyCollateral,
  mkAnyOf,
  mkBanxumSource,
  mkCollateralMatches,
  mkDefaultFilters,
  mkEffectiveCollateral,
  mkNewLending,
  mkNoCollateral,
  mkOptionUnion,
  mkRefinancing,
  mkToggle,
  smartInvestCatalog,
  smartInvestRequestFromFilters,
  type MkFilters,
  type MkListKey
} from "./investorPortal/smartInvestCriteria";
import { onboardingStepForUser } from "./onboarding";
import { CreatePinForm, SensitivePinField, SettingsPinPanel } from "./investorPortal/pin";
import { pinApiError } from "./investorPortal/pinRules";
import { usePinStatus, useSensitivePin } from "./investorPortal/pinState";
import { SitePages } from "./site/SitePages";
import { captureMagicLinkTokenFromLocation, takePendingMagicLinkToken } from "./magicLinkToken";
import {
  formatAmountInput,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatMoneyMinor,
  formatMoneyLabel,
  formatPercent,
  formatRateBps,
  formatWholeAmount,
  daysBetweenDateKeys,
  humanizeEnum,
  isZurichWeekendAt,
  monthLabelFromKey,
  zurichMonthKey,
  parseMoneyInputToMinorUnits,
  pluralize,
  safeMetadataCategory,
  useNumberFormatScope,
  zurichDateKey
} from "./investorPortal/format";
import type { AppRoute, DemoAccountState, RouteName } from "./investorPortal/types";
import { normalizeStory, storyIsEmpty } from "./investorPortal/story";
import { StoryView } from "./investorPortal/StoryView";
import { notificationRoute } from "./investorPortal/notifications";
import { useT } from "./i18n";
import { PortalNavProvider, type PortalNav } from "./portal/components";
import { PortalShell } from "./portal/shell/PortalShell";
import { LegacyBody } from "./portal/shell/LegacyBody";
import { FX_NAV_ITEM, NAV_PARENT } from "./portal/shell/nav";
import { PreviewControls } from "./portal/shell/PreviewControls";
import { InvestmentDetailScreen } from "./portal/screens/portfolio/InvestmentDetailScreen";
import { MyInvestmentsScreen } from "./portal/screens/portfolio/MyInvestmentsScreen";
import { ResaleMarketScreen } from "./portal/screens/portfolio/ResaleMarketScreen";
import { SmartInvestScreen } from "./portal/screens/portfolio/SmartInvestScreen";
import { ReportsScreen } from "./portal/screens/wallet/ReportsScreen";
import { TransactionsScreen } from "./portal/screens/wallet/TransactionsScreen";
import { U33Skin } from "./portal/U33Skin";
import { LoanDocumentList } from "./investorPortal/LoanDocumentList";
import { currencyBalanceMinor, investAmountLimitMessage, noEligibleFundsReason } from "./investorPortal/investLimits";
import { AUTO_RETURN_AFTER_DAYS, autoReturnDays, autoReturnRuleText, lotAgeLines } from "./investorPortal/balanceAgeing";
import { isSwissInvestorLimitError, swissLoanFullForViewer } from "./investorPortal/investorLimit";
import { SwissInvestorLimitNote } from "./investorPortal/SwissInvestorLimitNote";
import {
  isUnsecuredLoan,
  loanLtvBps
} from "./investorPortal/portfolioCollateral";
import {
  Banner,
  Button,
  Card,
  Check,
  Chip,
  DeadlineMeter,
  Empty,
  Field,
  Icon,
  Modal,
  Progress,
  Rating,
  Review,
  Segmented,
  Tooltip,
  PageHead,
  UserSkin,
  type IconName
} from "./investorPortal/ui";

// Routes whose screens are rebuilt in U33 (portal/screens); every other screen body is wrapped in
// <LegacyBody> by InvestorShell until its slice replaces it. One list per slice (kept apart so the
// parallel slices do not edit the same lines).
// S2 investing (portal/screens/invest).
const U33_SCREENS_INVEST: RouteName[] = [];

// S3 portfolio, resale, Smart Invest (portal/screens/portfolio).
const U33_SCREENS_PORTFOLIO: RouteName[] = ["portfolio", "investment", "secondary", "smartInvest"];

// S4 account, transactions, reports, documents, notifications (portal/screens/wallet).
const U33_SCREENS_WALLET: RouteName[] = ["transactions", "reports"];

// S5 profile and settings, help, verification (portal/screens/account).
const U33_SCREENS_ACCOUNT: RouteName[] = [];

const U33_SCREENS = new Set<RouteName>([
  ...U33_SCREENS_INVEST,
  ...U33_SCREENS_PORTFOLIO,
  ...U33_SCREENS_WALLET,
  ...U33_SCREENS_ACCOUNT
]);
// The Reports page lists the account statements and annual tax information of Documents.
const reportDocumentKinds = ["account_statement", "annual_tax_information"];

const platformName = import.meta.env.VITE_PLATFORM_BRAND_NAME ?? "BANXUM";
const operatorName = import.meta.env.VITE_LEGAL_OPERATOR_NAME ?? "Garanta Finanzgruppe AG";
const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL ?? "support@banxum.com";
const registrationTermsVersion = import.meta.env.VITE_REGISTRATION_TERMS_VERSION ?? "registration-v1";
const registrationTermsHash =
  import.meta.env.VITE_REGISTRATION_TERMS_HASH ??
  "3b0ba70e0b1d68a6acd2135c832cf114f6db2fb5c8896625c1f28f3ba7bd8dca";

// Labels of the loan repayment types (backend loans.RepaymentType), word for word.
const repaymentTypeLabels: Record<string, string> = {
  equal_installments: "Equal installments",
  bullet_periodic_interest: "Bullet principal with periodic interest",
  amortizing_principal_interest: "Amortizing principal and interest",
  interest_only_then_bullet: "Interest-only then bullet",
  interest_only_then_amortizing: "Interest-only then amortizing"
};

function formatEnumLabel(value: string) {
  return repaymentTypeLabels[value] ?? value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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
  // True while the expired-link screen asks for an address (none known yet, or
  // "Use a different email address"); the field must stay while the user types.
  editingEmail: boolean;
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
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be full or blocked (private mode); navigation must still work.
  }
}

function removeStoredObject(key: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Nothing to remove.
  }
}

const routeNames: RouteName[] = [
  "public",
  "login",
  "register",
  "kyc",
  "dashboard",
  "market",
  "smartInvest",
  "loan",
  "loanSchedule",
  "invest",
  "portfolio",
  "investment",
  "secondary",
  "balances",
  "transactions",
  "reports",
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

// "/" restores the last in-app screen, but never a site page: the public site pages have
// their own addresses (/projects, /help...), so "/" is the home page.
function homeOrStoredRoute(): AppRoute {
  const stored = readStoredRoute();
  // Never the login or registration form either: a returning visitor whose session ended
  // sees the home page at "/" (the investor shell also falls back to it, see InvestorShell).
  return isPublicRouteName(stored.name) ? { name: "public" } : stored;
}

/** Public routes: the site and the login/registration flows. Never "the last portal page". */
function isPublicRouteName(name: RouteName) {
  return name === "public" || name === "site" || name === "login" || name === "register";
}

// The site's old FAQ address now shows Help: keep the address bar on the new path.
function canonicalSiteAddress() {
  const normalized = window.location.pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/faq") {
    window.history.replaceState(window.history.state, "", `/help${window.location.search}${window.location.hash}`);
  }
}

/**
 * The route of an address. Portal, login and registration paths have their own route names;
 * "/" is the site's home ("public") and EVERY other path belongs to the public site ("site",
 * with the path and query in params), which shows its own 404 page for unknown paths.
 */
function routeFromPathname(pathname: string, search = ""): AppRoute {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  const siteRoute: AppRoute = {
    name: "site",
    params: { path: normalized === "/faq" ? "/help" : normalized, search: search === "?" ? "" : search }
  };
  const directRoutes: Record<string, RouteName> = {
    "/": "public",
    "/login": "login",
    "/register": "register",
    "/verification": "kyc",
    "/dashboard": "dashboard",
    "/marketplace": "market",
    "/smart-invest": "smartInvest",
    "/portfolio": "portfolio",
    "/secondary-market": "secondary",
    "/balances": "balances",
    "/transactions": "transactions",
    "/reports": "reports",
    "/fx": "fx",
    "/documents": "documents",
    "/notifications": "notifications",
    "/settings": "settings",
    "/portal/help": "faq"
  };
  if (directRoutes[normalized]) return { name: directRoutes[normalized] };
  const investmentMatch = normalized.match(/^\/portfolio\/([^/]+)$/);
  if (investmentMatch) {
    try {
      return { name: "investment", params: { holdingId: decodeURIComponent(investmentMatch[1]) } };
    } catch {
      return siteRoute;
    }
  }
  const loanMatch = normalized.match(/^\/marketplace\/([^/]+)(\/schedule|\/invest)?$/);
  if (!loanMatch) return siteRoute;
  try {
    const name: RouteName = loanMatch[2] === "/schedule" ? "loanSchedule" : loanMatch[2] === "/invest" ? "invest" : "loan";
    return { name, params: { loanId: decodeURIComponent(loanMatch[1]) } };
  } catch {
    return siteRoute;
  }
}

function routePath(route: AppRoute) {
  if (route.name === "site") {
    return `${route.params?.path ?? "/"}${route.params?.search ?? ""}`;
  }
  if (route.name === "investment") {
    const path = `/portfolio/${encodeURIComponent(route.params?.holdingId ?? "")}`;
    return route.params?.section === "loan-notes" ? `${path}#loan-notes` : path;
  }
  const paths: Record<RouteName, string> = {
    public: "/",
    site: "/",
    login: "/login",
    register: "/register",
    kyc: "/verification",
    dashboard: "/dashboard",
    market: "/marketplace",
    smartInvest: "/smart-invest",
    loan: `/marketplace/${encodeURIComponent(route.params?.loanId ?? "")}`,
    loanSchedule: `/marketplace/${encodeURIComponent(route.params?.loanId ?? "")}/schedule`,
    invest: `/marketplace/${encodeURIComponent(route.params?.loanId ?? "")}/invest`,
    portfolio: "/portfolio",
    investment: `/portfolio/${encodeURIComponent(route.params?.holdingId ?? "")}`,
    secondary: "/secondary-market",
    balances: "/balances",
    transactions: "/transactions",
    reports: "/reports",
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
  // The site sets its own titles (site/SitePages.tsx).
  site: platformName,
  login: "Log in",
  register: "Register",
  kyc: "Verification",
  dashboard: "Overview",
  market: "Investment opportunities",
  smartInvest: "Smart Invest",
  loan: "Project",
  loanSchedule: "Project schedule",
  invest: "Invest",
  portfolio: "My investments",
  investment: "Investment",
  secondary: "Resale market",
  balances: "Account",
  transactions: "Transactions",
  reports: "Reports",
  fx: "Currency exchange",
  documents: "Documents",
  notifications: "Notifications",
  settings: "Profile & Settings",
  faq: "Help"
};

// The published template of a category, shown by the public site's legal page
// (site/u33/pages/Legal.tsx: /legal/registration, /legal/risk-disclosure...).
function legalDocumentPath(category: string) {
  return `/legal/${category.replace(/_/g, "-")}`;
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
    <Tooltip content={accessibleLabel} focusable={false}>
      <Button
        aria-label={accessibleLabel}
        className={`copy-id-btn${iconOnly ? " icon-only" : ""}`}
        icon="copy"
        size="sm"
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
    </Tooltip>
  );
}

function BlockedSelectionMarker({ label, reason }: { label: string; reason: string }) {
  return (
    <Tooltip content={reason} label={`${label} cannot be selected. ${reason}`}>
      <span aria-hidden="true" className="dz-tick blocked" />
    </Tooltip>
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
  // Every sensitive action needs the PIN with the email code (ACC-DEC-009).
  const pin = useSensitivePin();

  return { codeId, expiresAt, error, isRequesting: requestMutation.isPending, resendCooldownSeconds, requestCode, pin };
}

// The email code and the PIN of a sensitive action, side by side in every flow. After a
// PIN is created from the "no PIN yet" answer, onContinue runs the action again.
function SensitiveActionFields({
  codeRequest,
  code,
  onCodeChange,
  onContinue,
  requestDisabled = false
}: {
  codeRequest: ReturnType<typeof useSensitiveActionCode>;
  code: string;
  onCodeChange: (value: string) => void;
  onContinue?: () => void;
  requestDisabled?: boolean;
}) {
  return (
    <div className="sensitive-confirm">
      <CodeRequestField
        hint={previewHint("Demo: any 6 digits")}
        label="Email confirmation code"
        requestDisabled={requestDisabled || emailCodeRequestDisabled(codeRequest)}
        requestLabel={emailCodeRequestLabel(codeRequest)}
        value={code}
        onChange={onCodeChange}
        onRequest={codeRequest.requestCode}
      />
      <SensitivePinField onContinue={onContinue} pin={codeRequest.pin} />
    </div>
  );
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

// Readable names of balance-lot sources (ledger BalanceLotSourceType), never raw keys.
const lotSourceLabels: Record<string, string> = {
  deposit: "Bank deposit",
  installment: "Loan repayment",
  originator_claim_repayment: "Loan Originator claim repayment",
  recovery_distribution: "Recovery payment",
  secondary_market_proceeds: "Secondary-market sale",
  fx_proceeds: "Currency exchange (FX)",
  refund: "Refund",
  correction: "Balance correction",
  penalty_reversal: "Penalty refund"
};

function sourceLabel(sourceType: string) {
  return lotSourceLabels[sourceType] ?? humanizeEnum(sourceType);
}

// Activity lines for balance credits carry the raw lot source in their type ("balance_fx_proceeds").
function activityTitle(entry: Pick<ActivityEntry, "activity_type" | "title" | "metadata">) {
  if (entry.activity_type === "withdrawal_request" && (entry.metadata as { is_forced?: unknown } | null)?.is_forced === true) {
    // The server names forced returns; older entries fall back to a fixed label.
    return entry.title.startsWith("Forced return") ? entry.title : "Forced return to your bank account";
  }
  // A penalty charge is a debit with its own server title, not a balance source.
  if (entry.activity_type === "balance_penalty_charge") return entry.title;
  if (entry.activity_type.startsWith("balance_") && entry.title !== "QA opening balance") {
    return sourceLabel(entry.activity_type.slice("balance_".length));
  }
  return entry.title;
}

function activityReference(entry: Pick<ActivityEntry, "activity_type" | "loan_title">) {
  if (entry.loan_title) return entry.loan_title;
  if (entry.activity_type.startsWith("balance_")) return "Account balance";
  return humanizeToken(entry.activity_type) || "-";
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

function usesImmediateClaimAssignment(
  loan: Pick<MarketplaceLoanPreview, "investment_flow">
) {
  return loan.investment_flow === "immediate_claim_assignment";
}

function usesOriginatorSubscription(
  loan: Pick<MarketplaceLoanPreview, "product_type" | "investment_flow">
) {
  return isOriginatorClaimLoan(loan) && loan.investment_flow === "primary_order";
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

// Money labels use the ISO currency code everywhere ("EUR 250.00"), never a symbol.
function marketplaceCurrencySymbol(currency: string) {
  return currency;
}

function fundingDaysRemaining(deadline: string, asOf?: string) {
  // Europe/Zurich business date of the platform clock (as_of), never the browser's date.
  const currentKey = platformTodayKey(asOf);
  const deadlineTime = Date.parse(`${deadline}T00:00:00Z`);
  const currentTime = Date.parse(`${currentKey}T00:00:00Z`);
  if (!Number.isFinite(deadlineTime) || !Number.isFinite(currentTime)) return null;
  return Math.max(0, Math.round((deadlineTime - currentTime) / 86_400_000));
}

function fundingDeadlineLabel(deadline: string, asOf?: string) {
  const days = fundingDaysRemaining(deadline, asOf);
  if (days === null) return formatDate(deadline);
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
}

function currentInvestableLotsForLoanCurrency(
  lots: BalanceLot[] | undefined,
  loan: Pick<MarketplaceLoanPreview, "currency" | "funding_deadline">
) {
  return (lots ?? []).filter(
    (lot) =>
      lot.currency === loan.currency &&
      lot.status === "available" &&
      lot.bucket === "investable" &&
      // The whole funding window must end before the lot's last day (day 58), when it can only be withdrawn.
      (!loan.funding_deadline || loan.funding_deadline < lot.last_day) &&
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

function goTo(setRoute: (route: AppRoute) => void, name: RouteName, params?: Record<string, string>) {
  const nextRoute = { name, params };
  writeStoredObject(appRouteStorageKey, nextRoute);
  const nextPath = routePath(nextRoute);
  if (`${window.location.pathname}${window.location.hash}` !== nextPath) {
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

// In-app navigation from the public site (site/SitePages.tsx navigate()): site paths change the
// address and the route without touching the stored portal route; /login and /register go
// through goTo like the rest of the app.
function goToSitePath(setRoute: (route: AppRoute) => void, href: string, options?: { replace?: boolean }) {
  const url = new URL(href, window.location.origin);
  const route = routeFromPathname(url.pathname, url.search);
  if (route.name !== "public" && route.name !== "site") {
    goTo(setRoute, route.name, route.params);
    return;
  }
  const nextAddress = `${routePath(route)}${url.hash}`;
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== nextAddress) {
    if (options?.replace) window.history.replaceState(window.history.state, "", nextAddress);
    else window.history.pushState({}, "", nextAddress);
  }
  setRoute(route);
}

export function App() {
  // A login-link token leaves the address bar before anything renders or calls the API.
  captureMagicLinkTokenFromLocation();
  const pathRoute = routeFromPathname(window.location.pathname, window.location.search);
  const initialRoute: AppRoute = readReadonlyImpersonationToken()
    ? !isPublicRouteName(pathRoute.name)
      ? pathRoute
      : { name: "dashboard" }
    : pathRoute.name === "public"
      ? homeOrStoredRoute()
      : pathRoute;
  const [route, setRoute] = useState<AppRoute>(initialRoute);
  const [demoState, setDemoState] = useState<DemoAccountState>("active");
  // The path is state too: Back/Forward between the portal and /admin must re-render App.
  const [, setPathname] = useState(() => window.location.pathname);
  const navigateSite = useCallback(
    (href: string, options?: { replace?: boolean }) => goToSitePath(setRoute, href, options),
    []
  );

  useLayoutEffect(() => {
    canonicalSiteAddress();
  }, []);

  useEffect(() => {
    if (window.location.pathname.startsWith("/admin")) return;
    // The public site sets its own titles ("Projects · Banxum").
    if (route.name === "public" || route.name === "site") return;
    const title = routeTitles[route.name];
    document.title = title && title !== platformName ? `${title} · ${platformName}` : platformName;
  }, [route.name]);

  useEffect(() => {
    const onPopState = () => {
      setPathname(window.location.pathname);
      // The admin console routes itself (adminConsole/adminRoute.ts); App only has to switch to it.
      if (window.location.pathname.startsWith("/admin")) return;
      canonicalSiteAddress();
      const nextRoute = routeFromPathname(window.location.pathname, window.location.search);
      if (nextRoute.name !== "site") writeStoredObject(appRouteStorageKey, nextRoute);
      setRoute(nextRoute);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (window.location.pathname.startsWith("/admin")) {
    return <AdminApp />;
  }

  if (window.location.pathname.startsWith("/kyc/callback")) {
    return <UserSkin><KycReturnScreen setRoute={setRoute} /></UserSkin>;
  }

  // The public site (logged-out pages): its own router, which picks the skin and shell per page
  // (U33 pages html.bxp, the October pages html.bxs).
  if (route.name === "public" || route.name === "site") {
    return (
      <SitePages
        navigate={navigateSite}
        path={route.name === "public" ? "/" : route.params?.path ?? "/"}
        search={route.name === "public" ? "" : route.params?.search ?? ""}
      />
    );
  }

  if (route.name === "login") {
    return <UserSkin><LoginFlow setRoute={setRoute} /></UserSkin>;
  }

  if (route.name === "register") {
    return <UserSkin><RegisterFlow setRoute={setRoute} /></UserSkin>;
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

function Wordmark({ compact = false, inverse = false }: { compact?: boolean; inverse?: boolean }) {
  const isBanxum = platformName.toUpperCase() === "BANXUM";
  return (
    <span className={`investor-brand bxm-wordmark ${compact ? "compact" : ""} ${inverse ? "inverse" : ""}`}>
      {isBanxum ? (
        <img
          alt={platformName}
          className="bxm-wordmark-img"
          src={inverse ? "/brand/banxum-logo-white.svg" : "/brand/banxum-logo.svg"}
        />
      ) : (
        <span className="investor-brand-word">
          {platformName}
        </span>
      )}
    </span>
  );
}

// The logo leads to the main page: the Overview for a signed-in investor, the
// public home page otherwise. "Signed in" comes from the shared /auth/me query.
function BrandHomeLink({
  children,
  className,
  onNavigate,
  setRoute
}: {
  children: ReactNode;
  className?: string;
  onNavigate?: () => void;
  setRoute: (route: AppRoute) => void;
}) {
  // Read the session the page already has. Never refetch a failed check on mount: the login
  // screen shows this link too, and a refetch there resets the portal's session gate, which
  // then remounts the login screen and this link in a loop (audit A-03).
  const authMeQuery = useV1AuthMeRetrieve({
    query: {
      enabled: !isFixturePreview,
      retry: false,
      retryOnMount: false,
      refetchOnMount: false,
      refetchOnWindowFocus: false,
      staleTime: 60_000
    }
  });
  const user = authMeQuery.data?.user;
  const signedIn = Boolean(user) && !["admin", "superadmin"].includes(user?.account_type ?? "");
  const target: RouteName = signedIn ? "dashboard" : "public";
  return (
    <a
      aria-label={signedIn ? `${platformName} overview` : `${platformName} home`}
      className={className}
      href={routePath({ name: target })}
      onClick={(event) => {
        if (!isPlainLeftClick(event)) return;
        event.preventDefault();
        onNavigate?.();
        goTo(setRoute, target);
      }}
    >
      {children}
    </a>
  );
}

// A plain left click (no new tab, no modifier): the only click the app handles itself.
function isPlainLeftClick(event: React.MouseEvent<HTMLAnchorElement>) {
  return !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

function LoginFlow({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const [initialLoginState] = useState(() =>
    readStoredObject<LoginFlowState>(loginFlowStorageKey, {
      email: "",
      sent: false,
      linkExpired: false,
      resendCooldownUntil: 0,
      editingEmail: false
    })
  );
  const [email, setEmail] = useState(initialLoginState.email);
  const [sent, setSent] = useState(initialLoginState.sent);
  const [linkExpired, setLinkExpired] = useState(initialLoginState.linkExpired);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(
    initialLoginState.resendCooldownUntil
  );
  const [editingEmail, setEditingEmail] = useState(
    initialLoginState.editingEmail || !initialLoginState.email
  );
  const [focusEmailField, setFocusEmailField] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(hasSessionExpiredNotice);
  const [isConsuming, setIsConsuming] = useState(false);
  const [blockedAccountStatus, setBlockedAccountStatus] = useState<string | null>(null);
  const [error, setError] = useState("");
  const magicLinkRequest = useV1AuthMagicLinkRequestCreate();
  const resendCooldownSeconds = useSecondsUntil(resendCooldownUntil);

  useEffect(() => {
    writeStoredObject(loginFlowStorageKey, {
      email,
      sent,
      linkExpired,
      resendCooldownUntil,
      editingEmail
    });
  }, [editingEmail, email, linkExpired, resendCooldownUntil, sent]);

  const consumeAttemptedRef = useRef(false);
  const loginFlowMountedRef = useRef(false);

  useEffect(() => {
    loginFlowMountedRef.current = true;
    // The token arrives in the URL fragment (/login#token=...) or, in older emails, the
    // query; App has already removed it from the address bar (audit A-49).
    const token = consumeAttemptedRef.current ? null : takePendingMagicLinkToken();
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
        clearSessionExpiredNotice();
        window.history.replaceState({}, "", "/");
        if (resumeOnboardingForUser(response.user, setRoute)) return;
        removeStoredObject(registerFlowStorageKey);
        goTo(setRoute, "dashboard");
      })
      .catch((mutationError: unknown) => {
        if (!loginFlowMountedRef.current) return;
        const blockedStatus = blockedAccountStatusFromError(mutationError);
        if (blockedStatus || (mutationError instanceof ApiClientError && mutationError.status === 400)) {
          const url = new URL(window.location.href);
          url.searchParams.delete("token");
          window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
          setError("");
          if (blockedStatus) {
            // A valid link of a restricted or locked account: say why login is refused.
            setBlockedAccountStatus(blockedStatus);
            return;
          }
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
      <AuthShell onClose={() => goTo(setRoute, "public")} setRoute={setRoute}>
        <div className="auth-card"><Empty icon="clock" title="Signing you in">Verifying your one-time login link.</Empty></div>
      </AuthShell>
    );
  }

  if (blockedAccountStatus) {
    const statusWord = blockedAccountStatus === "locked" ? "locked" : "restricted";
    return (
      <AuthShell onClose={() => goTo(setRoute, "public")} setRoute={setRoute}>
        <div className="auth-card">
          <div className="auth-form">
            <AuthStatusIcon name="lock" />
            <div className="auth-head">
              <h2>Your account is {statusWord}</h2>
              <p>
                You cannot log in while your account is {statusWord}. Please contact support at{" "}
                <a href={`mailto:${supportEmail}`}>{supportEmail}</a> for further details.
              </p>
            </div>
            <a className="btn btn-primary btn-lg btn-block" href={`mailto:${supportEmail}`}>
              Contact support
            </a>
          </div>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell onClose={() => goTo(setRoute, "public")} setRoute={setRoute}>
      <div className="auth-card">
        {linkExpired ? (
          <form className="auth-form" data-testid="login-expired-form" onSubmit={submitMagicLink}>
            <AuthStatusIcon name="clock" />
            <div className="auth-head">
              <h2>Login link expired</h2>
              <p>
                This login link has expired or is no longer valid. Request a new link to continue.
              </p>
              {editingEmail ? null : (
                <p>
                  We will send the new link to <b>{email}</b>.
                </p>
              )}
            </div>
            {editingEmail ? (
              <Field label="Email address">
                <input
                  autoFocus={focusEmailField}
                  className="input"
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@example.com"
                  type="email"
                  value={email}
                />
              </Field>
            ) : null}
            {error ? <Banner tone="bad" title="Could not send a new link">{error}</Banner> : null}
            <Button block disabled={resendDisabled} size="lg" type="submit" variant="primary">
              {resendLabel}
            </Button>
            {editingEmail ? null : (
              <div className="auth-alt">
                <Button variant="link" onClick={switchToDifferentEmail}>
                  Use a different email address
                </Button>
              </div>
            )}
            <p className="auth-note">
              Lost access to your email is handled through support after identity re-verification.
            </p>
          </form>
        ) : !sent ? (
          <form className="auth-form" data-testid="login-magic-link-form" onSubmit={submitMagicLink}>
            <div className="auth-head">
              <h2>Log in</h2>
              <p>
                We will email a secure magic link. No password is required for investor access.
              </p>
            </div>
            {sessionExpired ? (
              <Banner icon="clock" tone="warn" title="Your session has expired">
                Please log in again to continue.
              </Banner>
            ) : null}
            <Field label="Email address">
              <input className="input" onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" type="email" value={email} />
            </Field>
            {error ? <Banner tone="bad" title="Could not continue">{error}</Banner> : null}
            <Button block disabled={!email.includes("@") || magicLinkRequest.isPending} size="lg" type="submit" variant="primary">
              {magicLinkRequest.isPending ? "Sending..." : "Send magic link"}
            </Button>
            <p className="auth-alt">
              New to {platformName}? <a href="/register" onClick={(event) => { event.preventDefault(); goTo(setRoute, "register"); }}>Register as a lender</a>
            </p>
          </form>
        ) : (
          <div className="auth-form">
            <AuthStatusIcon name="bell" />
            <div className="auth-head">
              <h2>Check your inbox</h2>
              <p>
                We sent a magic link to <b>{email}</b>. It expires in 15 minutes.
              </p>
            </div>
            {error ? <Banner tone="bad" title="Could not send a new link">{error}</Banner> : null}
            <div className="auth-actions">
              <Button block disabled={resendDisabled} size="lg" onClick={requestMagicLink}>
                {resendLabel}
              </Button>
              {isFixturePreview ? <Button block size="lg" variant="primary" onClick={() => goTo(setRoute, "dashboard")}>
                Open link in demo
              </Button> : null}
            </div>
            <div className="auth-alt">
              <Button variant="link" onClick={resetLoginFlow}>
                Use a different email address
              </Button>
            </div>
            <p className="auth-note">
              Lost access to your email is handled through support after identity re-verification.
            </p>
          </div>
        )}
      </div>
    </AuthShell>
  );
}

// The magic-link consume API answers 403 { code: "account_restricted" | "account_locked" }
// when a valid link belongs to an account an admin has blocked.
function blockedAccountStatusFromError(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 403) return null;
  const code = (error.payload as { code?: unknown } | undefined)?.code;
  if (code === "account_restricted") return "restricted";
  if (code === "account_locked") return "locked";
  return null;
}

function AuthStatusIcon({ name }: { name: IconName }) {
  return (
    <div aria-hidden="true" className="auth-status-icon">
      <Icon name={name} size={20} />
    </div>
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
      <AuthShell onClose={() => leaveTo("public")} setRoute={setRoute}>
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
    <AuthShell onClose={() => leaveTo("public")} setRoute={setRoute}>
      <div className="auth-card">
        <div className="auth-form">
          <AuthStatusIcon name="checkCircle" />
          <div className="auth-head">
            <h2>Identity check submitted</h2>
            <p>
              You can close this tab and return to the device where you started
              registration. It will continue automatically as soon as the
              verification result arrives.
            </p>
          </div>
          <p className="auth-alt is-start">
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
      enabled: !isFixturePreview && step === 3 && hasMatchingSession,
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
    if (isFixturePreview || step !== 3 || !kycCaseStatus) return;
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
    // The PIN step (ACC-DEC-009) is done once the account has a PIN.
    if (
      step === 2 &&
      sessionUser?.pin_set === true &&
      normalizedEmail(sessionUser.email) === normalizedEmail(email)
    ) {
      setStep(3);
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
    // Send the number typed at registration: the signed-in owner may correct an
    // unverified number this way (a repeated registration never changes stored data).
    phoneRequestMutation.mutate(phoneNumber ? { data: { phone_number: phoneNumber } } : {}, {
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
      onError: (mutationError) => {
        // Identity verification needs the PIN first (ACC-DEC-009): back to the PIN step.
        if (pinApiError(mutationError)?.code === "pin_required") {
          setStep(2);
          return;
        }
        setError(apiErrorMessage(mutationError));
      }
    });
  };

  return (
    <RegisterShell onClose={() => goTo(setRoute, "public")} setRoute={setRoute} step={step}>
      {step === 0 ? (
        <>
          <PageHead
            description={<>Individual lenders only. Legal entities are onboarded by {operatorName} off-platform.</>}
            eyebrow={`Step ${step + 1} of ${registerStepLabels.length}`}
            title="Create your lender account"
          />
          <div className="card auth-onb-card">
            <div className="auth-onb-grid">
              <Field label="First name"><input className="input" onChange={(event) => setFirstName(event.target.value)} value={firstName} /></Field>
              <Field label="Last name"><input className="input" onChange={(event) => setLastName(event.target.value)} value={lastName} /></Field>
              <div className="auth-onb-span">
                <Field label="Email address"><input className="input" onChange={(event) => setEmail(event.target.value)} type="email" value={email} /></Field>
              </div>
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
            </div>
            <div className="auth-consents">
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
            <p className="auth-note">
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
            <div className="auth-onb-actions">
              <Button disabled={!allRegistrationTermsAccepted || !risk || !email.includes("@") || !phoneNumber || registerMutation.isPending || (!isFixturePreview && (!registrationTermsQuery.data || !riskDisclosureQuery.data))} size="lg" variant="primary" onClick={submitRegistration}>
                {registerMutation.isPending ? "Creating account..." : "Continue"}
              </Button>
            </div>
          </div>
        </>
      ) : step === 1 ? (
        <>
          {!hasMatchingSession ? (
            <>
              <PageHead
                description="We need your magic-link email opened in this browser before SMS verification."
                eyebrow={`Step ${step + 1} of ${registerStepLabels.length}`}
                title="Confirm your email"
              />
              <div className="card auth-onb-card">
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
                <div className="auth-onb-actions">
                  <Button
                    disabled={
                      !email.includes("@") ||
                      registrationMagicLinkMutation.isPending ||
                      emailCooldownSeconds > 0
                    }
                    size="lg"
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
                </div>
                {error ? <Banner tone="bad" title="Could not send magic link">{error}</Banner> : null}
              </div>
            </>
          ) : (
            <>
              <PageHead
                description={
                  <>
                    Request an SMS code for {phoneNumberLabel}. Phone verification is required before
                    financial access.
                  </>
                }
                eyebrow={`Step ${step + 1} of ${registerStepLabels.length}`}
                title="Verify your phone"
              />
              <div className="card auth-onb-card">
                <div className="auth-code">
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
                </div>
                {error ? <Banner tone="bad" title="Could not verify phone">{error}</Banner> : null}
                <div className="auth-onb-actions">
                  <Button disabled={phoneCode.length < 6 || (!isFixturePreview && !phoneChallengeId) || phoneConfirmMutation.isPending} size="lg" variant="primary" onClick={confirmPhone}>
                    {phoneConfirmMutation.isPending ? "Verifying..." : "Verify phone"}
                  </Button>
                </div>
              </div>
            </>
          )}
        </>
      ) : step === 2 ? (
        <>
          <PageHead
            description="You will enter it with the email code for every investment, withdrawal and bank change."
            eyebrow={`Step ${step + 1} of ${registerStepLabels.length}`}
            title="Create your PIN"
          />
          <div className="card auth-onb-card">
            <CreatePinForm layout="split" requiresEmailCode={false} onSaved={() => setStep(3)} />
          </div>
        </>
      ) : (
        <>
          <PageHead
            description={
              <>
                We will redirect you to Didit for identity capture and verification. Garanta retains
                the required compliance evidence and provider references for audit and regulatory
                access. If you verify on another device (for example via QR code), this page
                continues automatically once the result arrives.
              </>
            }
            eyebrow={`Step ${step + 1} of ${registerStepLabels.length}`}
            title="Identity verification"
          />
          <div className="card auth-onb-card">
            <KycTimeline current="pending" />
            <Banner tone="neutral" title="Provider handoff">
              Didit verifies your identity and returns provider evidence/status to {operatorName}. If
              the provider routes your case to review, financial access stays locked until Garanta
              compliance resolves it.
            </Banner>
            {error ? <Banner tone="bad" title="Could not start KYC">{error}</Banner> : null}
            <div className="auth-onb-actions">
              <Button disabled={kycSessionMutation.isPending} size="lg" variant="primary" onClick={startKyc}>
                {kycSessionMutation.isPending ? "Starting Didit..." : "Start KYC"}
              </Button>
            </div>
          </div>
        </>
      )}
    </RegisterShell>
  );
}

const registerStepLabels = ["Account", "Email and phone", "PIN", "KYC"];

// Registration uses the onboarding layout: a slim top bar, the numbered step
// bar and a centred column with the step content.
function RegisterShell({
  step,
  onClose,
  setRoute,
  children
}: {
  step: number;
  onClose: () => void;
  setRoute: (route: AppRoute) => void;
  children: ReactNode;
}) {
  return (
    <div className="auth-wrap auth-onb">
      <header className="auth-onb-head">
        <BrandHomeLink className="auth-brand-link" setRoute={setRoute}>
          <Wordmark />
        </BrandHomeLink>
        <button className="auth-onb-exit" onClick={onClose} type="button">
          <Icon name="arrowL" size={16} />
          <span>Back to investment opportunities preview</span>
        </button>
      </header>
      <div className="auth-onb-body">
        <ol aria-label="Registration steps" className="auth-stepbar">
          {registerStepLabels.map((label, index) => (
            <li
              aria-current={index === step ? "step" : undefined}
              aria-label={label}
              className={`auth-stepbar-item ${index < step ? "is-done" : index === step ? "is-current" : ""}`}
              key={label}
            >
              <span className="auth-stepbar-index">{String(index + 1).padStart(2, "0")}</span>
              <span className="auth-stepbar-label">{label}</span>
            </li>
          ))}
        </ol>
        {children}
      </div>
    </div>
  );
}

// Short public claim for the dark side panel, taken from the public landing copy.
const authClaim =
  "Review project-specific business loans, their repayment schedules, risks, and any disclosed security before deciding whether to invest.";

// Sign-in and status screens use the split layout: a dark panel with the logo
// and claim on wide screens, and the form panel on the right.
function AuthShell({
  children,
  onClose,
  setRoute
}: {
  children: React.ReactNode;
  onClose: () => void;
  setRoute: (route: AppRoute) => void;
}) {
  return (
    <div className="auth-wrap auth-split">
      <aside className="auth-aside">
        <span className="auth-aside-label">Investor area</span>
        <div className="auth-aside-brand">
          <BrandHomeLink className="auth-brand-link" setRoute={setRoute}>
            <Wordmark inverse />
          </BrandHomeLink>
          <p className="auth-claim">{authClaim}</p>
        </div>
      </aside>
      <div className="auth-main">
        <div className="auth-panel">
          <div className="auth-mobile-brand">
            <BrandHomeLink className="auth-brand-link" setRoute={setRoute}>
              <Wordmark />
            </BrandHomeLink>
          </div>
          {children}
        </div>
        <p className="auth-foot">
          <button className="btn-link" onClick={onClose} type="button">
            Back to investment opportunities preview
          </button>
          <span aria-hidden="true" className="auth-foot-sep">·</span>
          <span>{operatorName}</span>
        </p>
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
  const t = useT();
  // U33-DEC-32: the investor's number format applies while the investor area is mounted.
  useNumberFormatScope();
  const notificationReadActions = useNotificationReadActions();
  const [addFundsOpen, setAddFundsOpen] = useState(false);
  const [payoutIbanOpen, setPayoutIbanOpen] = useState(false);
  // Investing is a page (/marketplace/:loanId/invest); callers hand over the loan and an optional amount.
  const setInvestLoan = useCallback(
    (loan: MarketplaceLoanDetail | null, initialAmount?: string) => {
      if (!loan) return;
      goTo(setRoute, "invest", { loanId: loan.loan_id, ...(initialAmount ? { amount: initialAmount } : {}) });
    },
    [setRoute]
  );
  const [readonlyImpersonation, setReadonlyImpersonation] = useState(() => ({
    active: isReadonlyImpersonationActive(),
    label: readReadonlyImpersonationLabel()
  }));
  const finishLogout = () => {
    clearPortalSessionState(queryClient);
    clearReadonlyImpersonation();
    clearSessionExpiredNotice();
    setReadonlyImpersonation({ active: false, label: "" });
    goTo(setRoute, "public");
    setAddFundsOpen(false);
    setInvestLoan(null);
  };
  // Sign out fails closed (audit A-58): the portal clears its state only after the server ended
  // the session. If the call fails, the server is asked whether the session is still valid.
  const [signOutError, setSignOutError] = useState("");
  // Set once the post-login "Create your PIN" screen saved a PIN, before /auth/me says so.
  const [pinJustCreated, setPinJustCreated] = useState(false);
  const logoutMutation = useV1AuthLogoutCreate({
    mutation: {
      onSuccess: () => {
        setSignOutError("");
        finishLogout();
      },
      onError: async () => {
        try {
          const current = await v1AuthMeRetrieve();
          if (current?.user) {
            setSignOutError("We could not sign you out. You are still signed in. Try again.");
          } else {
            finishLogout();
          }
        } catch (checkError) {
          if (isSignedOutError(checkError)) finishLogout();
          else setSignOutError("We could not sign you out. You may still be signed in. Try again.");
        }
      }
    }
  });
  // Re-checked every minute so an expired session or an account restricted by an
  // admin is noticed even while the investor stays on one screen. Only 401/403 mean
  // "signed out" (audit A-59); other failures keep the cached session and retry.
  const authMeQuery = useV1AuthMeRetrieve({
    query: {
      enabled: !isFixturePreview,
      retry: retryTransientSessionError,
      retryDelay: (attempt) => Math.min(2_000 * 2 ** attempt, 15_000),
      staleTime: 0,
      refetchInterval: (query) =>
        query.state.data?.user && !isSignedOutError(query.state.error) ? 60_000 : false
    }
  });
  // Show "Checking your session" only before the first answer. A later re-check of a failed
  // session must keep the login form mounted, so typed input is not lost.
  const firstSessionCheck =
    authMeQuery.isPending && authMeQuery.dataUpdatedAt === 0 && authMeQuery.errorUpdatedAt === 0;
  // The backend ends sessions a fixed time after login; any API call then
  // answers 401 session_expired. Leave the portal for the login screen, which
  // explains what happened.
  useEffect(
    () =>
      onSessionExpired(() => {
        if (isReadonlyImpersonationActive()) {
          clearReadonlyImpersonation();
          queryClient.clear();
          window.location.assign("/admin");
          return;
        }
        clearPortalSessionState(queryClient);
        goTo(setRoute, "login");
      }),
    [queryClient, setRoute]
  );
  const sessionUser = isSignedOutError(authMeQuery.error) ? undefined : authMeQuery.data?.user;
  // Screens without an as_of of their own use the platform (QA) business date, not the browser's.
  rememberPlatformBusinessDate(authMeQuery.data?.platform_business_date);
  const hasPortalSession = isFixturePreview || Boolean(sessionUser);
  // Signed out at "/" (a returning visitor whose last screen was in the portal): "/" is the
  // public home page, not the login form (FRONTCODE-26).
  const signedOutAtHome =
    !isFixturePreview && !firstSessionCheck && !sessionUser && window.location.pathname === "/";
  // Switch before paint: App then shows the home page itself, so it mounts only once.
  useLayoutEffect(() => {
    if (!signedOutAtHome) return;
    writeStoredObject(appRouteStorageKey, { name: "public" });
    setRoute({ name: "public" });
  }, [setRoute, signedOutAtHome]);
  // Signed in at "/": show the screen's own address, so reload and sharing work.
  const routeAddress = routePath(route);
  useEffect(() => {
    if (sessionUser && window.location.pathname === "/" && routeAddress !== "/") {
      window.history.replaceState({}, "", routeAddress);
    }
  }, [routeAddress, sessionUser]);
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
  // Currency exchange can be switched off (platform setting fx.enabled, owner decision
  // 2026-10-16): no FX menu item, and /fx shows the dashboard instead.
  const fxFeature = useFxFeature();
  const fxRouteUnavailable = route.name === "fx" && fxFeature.known && !fxFeature.enabled;
  useEffect(() => {
    if (!fxRouteUnavailable) return;
    const dashboardRoute: AppRoute = { name: "dashboard" };
    writeStoredObject(appRouteStorageKey, dashboardRoute);
    window.history.replaceState({}, "", routePath(dashboardRoute));
    setRoute(dashboardRoute);
  }, [fxRouteUnavailable, setRoute]);
  const balancesData = useBalancesData(financialAccessAllowed).data;
  const balances = balancesData ?? { summaries: [], lots: [] };
  // Day-60 penalty mode (PAY-DEC-022) from the live balances; the preview switch only drives fixtures.
  const frozenAccount = frozenAccountFromBalances(
    financialAccessAllowed ? balancesData : undefined,
    isFixturePreview && demoState === "frozen"
  );
  const notifications = useNotificationsData(20, financialAccessAllowed).data;
  const marketplaceLoans = useMarketplaceLoansData(financialAccessAllowed).data ?? [];
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

  if (!isFixturePreview && firstSessionCheck) {
    return (
      <UserSkin>
        <AuthShell onClose={() => goTo(setRoute, "public")} setRoute={setRoute}>
          <div className="auth-card"><ScreenLoading title="Checking your session" /></div>
        </AuthShell>
      </UserSkin>
    );
  }
  if (signedOutAtHome) {
    // The layout effect above switches to the public route before this is painted.
    return null;
  }
  if (!isFixturePreview && !sessionUser) {
    return <UserSkin><LoginFlow setRoute={setRoute} /></UserSkin>;
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
        return <SmartInvestScreen />;
      case "loan":
        return (
          <LoanDetailScreen
            demoState={demoState}
            loanId={route.params?.loanId ?? ""}
            setInvestLoan={setInvestLoan}
            setRoute={setRoute}
          />
        );
      case "loanSchedule":
        return (
          <LoanScheduleScreen
            demoState={demoState}
            loanId={route.params?.loanId ?? ""}
            setInvestLoan={setInvestLoan}
            setRoute={setRoute}
          />
        );
      case "invest":
        return (
          <InvestScreen
            initialAmount={route.params?.amount}
            loanId={route.params?.loanId ?? ""}
            setRoute={setRoute}
          />
        );
      case "portfolio":
        return <MyInvestmentsScreen />;
      case "investment":
        return <InvestmentDetailScreen focusSection={route.params?.section} holdingId={route.params?.holdingId ?? ""} />;
      case "secondary":
        return <ResaleMarketScreen initialTab={route.params?.tab} />;
      case "balances":
        return <BalancesScreen demoState={demoState} />;
      case "transactions":
        return <TransactionsScreen><ActivityPanel /></TransactionsScreen>;
      case "reports":
        return <ReportsScreen><DocumentsScreen embedded kinds={reportDocumentKinds} /></ReportsScreen>;
      case "fx":
        if (fxFeature.enabled) return <FxScreen demoState={demoState} />;
        return fxFeature.known
          ? <Dashboard demoState={demoState} setInvestLoan={setInvestLoan} setRoute={setRoute} />
          : <ScreenLoading title="Currency exchange" />;
      case "documents":
        return <DocumentsScreen />;
      case "notifications":
        return <NotificationsScreen setRoute={setRoute} />;
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

  const blockedAccountStatus = isFixturePreview
    ? demoState === "restricted" ? "restricted" : null
    : sessionUser && !readonlyImpersonation.active && blockedAccountStatuses.has(sessionUser.status)
      ? sessionUser.status
      : null;
  const gatedScreen = blockedAccountStatus
    ? <AccountBlockedScreen status={blockedAccountStatus} />
    : !isFixturePreview && hasPortalSession && !financialAccessAllowed
      ? kycGateQuery.isPending && kycGateQuery.dataUpdatedAt === 0 && kycGateQuery.errorUpdatedAt === 0
        // Loading only before the first answer: a re-check after an error must not unmount
        // the status screen, whose own lookup would then restart the check in a loop.
        ? <ScreenLoading title="Verification" />
        : <KycStatusScreen setRoute={setRoute} />
      : screen;

  // Lots on their last day (withdraw-only), due back to the bank, or in penalty mode need action.
  const overdueCount = balances.lots.filter((lot) => ["withdraw_only", "overdue", "penalty_mode", "penalty"].includes(lot.bucket)).length;
  const addFundsCurrency = balances.summaries.find((summary) => summary.currency === "CHF")?.currency
    ?? balances.summaries[0]?.currency
    ?? "CHF";
  const displayRouteName = !financialAccessAllowed && !isFixturePreview ? "kyc" : route.name;
  const activeRoute = NAV_PARENT[displayRouteName] ?? displayRouteName;
  const addFundsDisabled = !financialAccessAllowed || frozenAccount.frozen || readonlyImpersonation.active;
  const openProjectCount = marketplaceLoans.filter((loan) => isOpenMarketplaceLoan(loan)).length;
  const unreadCount = notifications?.unread_count ?? 0;
  // The Account entry keeps today's alert marker: money that must go back, or a frozen account.
  const accountMarker = frozenAccount.frozen
    ? { text: "!", label: t("Account frozen") }
    : overdueCount > 0
      ? { text: String(overdueCount), label: overdueCount === 1 ? t("1 balance needs action") : t("{count} balances need action", { count: overdueCount }) }
      : undefined;
  // Available balance per currency, EUR first then CHF (design header order).
  const shellBalances = [...balances.summaries]
    .sort((a, b) => (a.currency === b.currency ? 0 : a.currency === "EUR" ? -1 : b.currency === "EUR" ? 1 : a.currency.localeCompare(b.currency)))
    .map((summary) => ({ currency: summary.currency, availableMinor: summary.total_available_minor }));
  const signOut = () => {
    if (readonlyImpersonation.active || isFixturePreview) {
      finishLogout();
      return;
    }
    setSignOutError("");
    logoutMutation.mutate();
  };
  const signOutLabel = readonlyImpersonation.active
    ? t("Exit read-only view")
    : logoutMutation.isPending
      ? t("Signing out...")
      : t("Sign out");

  // ACC-DEC-009: an investor without a PIN creates one before anything else.
  const needsPin = isFixturePreview
    ? demoState === "no_pin"
    : Boolean(sessionUser) &&
      !readonlyImpersonation.active &&
      !pinJustCreated &&
      sessionUser?.pin_set === false &&
      lenderAccountTypes.has(sessionUser.account_type) &&
      !blockedAccountStatuses.has(sessionUser.status);
  if (needsPin) {
    return (
      <PinGateScreen
        onCreated={() => {
          if (isFixturePreview) setDemoState("active");
          setPinJustCreated(true);
        }}
        onSignOut={signOut}
        setRoute={setRoute}
        signOutError={signOutError}
        signOutLabel={signOutLabel}
      />
    );
  }

  const portalNav: PortalNav = {
    hrefFor: (name, params) => routePath({ name, params }),
    go: (name, params) => goTo(setRoute, name, params),
    route
  };
  const status = readonlyImpersonation.active
    ? t("Read-only view")
    : financialAccessAllowed
      ? t("Verified investor")
      : t("Verification pending");
  // Rebuilt U33 screens bring their own layout; every other screen body stays in the old skin.
  const isU33Screen = gatedScreen === screen && U33_SCREENS.has(route.name);
  const notices = [
    signOutError ? (
      <Banner
        actions={<Button disabled={logoutMutation.isPending} size="sm" variant="primary" onClick={signOut}>{logoutMutation.isPending ? "Signing out..." : "Retry sign out"}</Button>}
        icon="alert"
        key="sign-out"
        tone="bad"
        title="Sign out failed"
      >
        {signOutError}
      </Banner>
    ) : null,
    isFixturePreview ? (
      <Banner icon="alert" key="preview" tone="warn" title="Preview data">
        This investor portal is running with local fixture data for UX review. Balances,
        holdings, activity, FX history, and documents shown here are not real account data.
      </Banner>
    ) : null,
    readonlyImpersonation.active ? (
      <Banner icon="lock" key="read-only" tone="info" title="Superadmin read-only view">
        Viewing the portal as {readonlyImpersonation.label || "selected user"}. Mutating
        actions are disabled and generated/downloaded evidence is audited to the superadmin,
        not recorded as user activity.
      </Banner>
    ) : null,
    frozenAccount.frozen && financialAccessAllowed && !blockedAccountStatus ? (
      <div className="frozen-account-notice" key="frozen">
        <FrozenAccountBanner
          account={frozenAccount}
          onAddIban={readonlyImpersonation.active ? undefined : () => setPayoutIbanOpen(true)}
          onOpenAccount={route.name === "balances" ? undefined : () => goTo(setRoute, "balances")}
        />
      </div>
    ) : null
  ].filter(Boolean);

  return (
    <UserSkin>
      <U33Skin>
        <PortalNavProvider value={portalNav}>
          <PortalShell
            activeRoute={activeRoute}
            addFundsDisabled={addFundsDisabled}
            balances={shellBalances}
            counts={{ openOpportunities: openProjectCount, unreadNotifications: unreadCount }}
            dialogs={addFundsOpen || payoutIbanOpen ? (
              <LegacyBody>
                {addFundsOpen ? (
                  <DepositModal
                    allowCurrencySelection
                    currency={addFundsCurrency}
                    onClose={() => setAddFundsOpen(false)}
                  />
                ) : null}
                {payoutIbanOpen ? <PayoutIbanModal onClose={() => setPayoutIbanOpen(false)} /> : null}
              </LegacyBody>
            ) : null}
            extraNavItems={fxFeature.enabled ? { Wallet: [FX_NAV_ITEM] } : undefined}
            markers={accountMarker ? { balances: accountMarker } : undefined}
            notices={notices.length > 0 ? <LegacyBody><div className="col gap-12">{notices}</div></LegacyBody> : null}
            notifications={notifications}
            onAddFunds={() => setAddFundsOpen(true)}
            onMarkAllRead={() => void notificationReadActions.markAllRead().catch(() => undefined)}
            onMarkRead={(id) => void notificationReadActions.markRead(id).catch(() => undefined)}
            onSignOut={signOut}
            profile={profile}
            signOutDisabled={logoutMutation.isPending}
            signOutLabel={signOutLabel}
            status={status}
          >
            <FrozenAccountContext.Provider value={frozenAccount}>
              {isU33Screen ? gatedScreen : <LegacyBody>{gatedScreen}</LegacyBody>}
            </FrozenAccountContext.Provider>
          </PortalShell>
          {isFixturePreview ? <PreviewControls onStateChange={setDemoState} state={demoState} /> : null}
        </PortalNavProvider>
      </U33Skin>
    </UserSkin>
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
  const frozenAccount = useFrozenAccount();
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
  // Free to place in new loans (investable lots only).
  const idleMinor = summary?.investable_minor ?? 0;
  // "Money not working" is everything on the account: investable, last-day, overdue and frozen money.
  const notWorkingMinor = summary?.total_available_minor ?? 0;
  const frozenMinor = (summary?.penalty_mode_minor ?? 0) + (summary?.frozen_minor ?? 0);
  const companies = new Set(holdingsCcy.map((holding) => holding.loan.borrower_name || holding.loan.loan_id)).size;
  const avgRateBps = investedMinor > 0
    ? Math.round(holdingsCcy.reduce((sum, holding) => sum + holding.loan.yield_bps * holding.current_principal_minor, 0) / Math.max(1, holdingsCcy.reduce((sum, holding) => sum + holding.current_principal_minor, 0)))
    : 0;
  const [investedWhole, investedCents = "00"] = formatMoneyMinor(investedMinor, ccy).split(".");
  const nextMonth = nextDashboardMonth(dashboard.as_of);
  // Months and days count on the Europe/Zurich calendar of the platform time (as_of), so a
  // browser in another time zone groups payments under the same months as the labels.
  const todayKey = zurichDateKey(dashboard.as_of);
  const monthInfo = (offset: number) => {
    const key = zurichMonthKey(todayKey, 1 + offset);
    return {
      key,
      label: monthLabelFromKey(key, { month: "short" }).toUpperCase()
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
    ? new Date(firstAssignment).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "Europe/Zurich" })
    : null;
  const idlePct = investedMinor + notWorkingMinor > 0 ? formatDecimal(((notWorkingMinor / (investedMinor + notWorkingMinor)) * 100), 1) : formatDecimal(0, 1);

  const deskMatches = (smartInvest?.matches ?? []).filter((match) => match.currency === ccy);
  const deskTickable = deskMatches.filter(isOpenMarketplaceLoan);
  const deskPlan = allocationPlan(deskTickable, unticked, new Map([[ccy, idleMinor]]), balances.lots);
  const deskTicked = deskTickable.filter((match) => deskPlan.ticked.has(match.loan_id));
  const deskAffordableIds = new Set(deskTicked.map((match) => match.loan_id));
  const deskUnaffordable = (match: MarketplaceLoanPreview) =>
    !deskAffordableIds.has(match.loan_id) && !unticked[match.loan_id];
  const deskSplit = deskPlan.split;
  // The select-all toggle covers the rows a click can tick; rows whose eligible sources cannot reach the
  // minimum keep their blocked marker either way.
  const deskSelectable = deskTickable.filter(
    (match) => sumLotAvailableMinor(currentInvestableLotsForLoanCurrency(balances.lots, match)) >= match.minimum_investment_minor
  );
  const deskAllUnticked = deskSelectable.length > 0 && deskSelectable.every((match) => unticked[match.loan_id]);
  const toggleDeskSelection = () => {
    if (deskAllUnticked) {
      setUnticked({});
      return;
    }
    setUnticked((current) => ({ ...current, ...Object.fromEntries(deskSelectable.map((match) => [match.loan_id, true])) }));
  };
  const deskItems = deskTicked
    .map((match) => ({ match, amountMinor: deskSplit.get(match.loan_id) ?? 0 }));
  const deskBatchReady = deskItems.length > 0 && !frozenAccount.frozen;
  const deskTotal = deskItems.reduce((sum, item) => sum + item.amountMinor, 0);
  const openCcyLoans = loans.filter((loan) => isOpenMarketplaceLoan(loan) && loan.currency === ccy);
  const closingSoon = openCcyLoans
    .map((loan) => {
      const days = loan.funding_deadline
        ? Math.max(0, daysBetweenDateKeys(todayKey, loan.funding_deadline) ?? 0)
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
      const [lastYear, lastMonth] = last.due_date.split("-").map(Number);
      const [todayYear, todayMonth] = todayKey.split("-").map(Number);
      return (lastYear - todayYear) * 12 + lastMonth - todayMonth;
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
  const horizonLabel = monthLabelFromKey(zurichMonthKey(todayKey, horizonMonths), { month: "short", year: "numeric" });
  const startLabel = firstAssignment
    ? new Date(firstAssignment).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "Europe/Zurich" })
    : formatDate(dashboard.as_of);
  const hasInvestments = investedMinor > 0;

  return (
    <main className="content dz-page">
      <PageHead
        actions={
          <>
            {currencies.length > 1 ? (
              <div aria-label="Display currency" className="seg" onKeyDown={handleTabListKeyDown} role="tablist">
                {currencies.map((code) => (
                  <button aria-selected={ccy === code} className={ccy === code ? "on" : ""} key={code} onClick={() => setCcyPick(code)} role="tab" tabIndex={ccy === code ? 0 : -1} type="button">{code}</button>
                ))}
              </div>
            ) : null}
            <Button icon="briefcase" onClick={() => goTo(setRoute, "market")} variant="primary">Browse projects</Button>
          </>
        }
        description={<>Your investments in {ccy} on {formatDate(dashboard.as_of)}.</>}
        title="Money working for you"
      />
      {demoState === "kyc_pending" ? (
        <div className="col gap-12 dz-alerts">
          <KycBanner setRoute={setRoute} />
        </div>
      ) : null}

      <div className="dz-stats">
        <div className="card dz-stat dz-hero">
          <div className="dz-stat-title">Invested in loans</div>
          <div className="dz-fig num">
            <span className="dz-cur dz-cur-lead">{ccy}</span>
            <span className="dz-whole">{investedWhole}</span><span className="dz-cents">.{investedCents}</span>
          </div>
          {hasInvestments ? (
            <div className="dz-stat-lines">
              <div className="dz-hero-line">invested in loans to <strong>{companies === 1 ? "1 company" : `${companies} companies`}</strong></div>
              <div className="dz-hero-line">at <strong className="num">{formatRateBps(avgRateBps)}</strong> per year interest, on average</div>
            </div>
          ) : (
            <div className="dz-stat-lines">
              <div className="dz-hero-line">nothing is invested yet — your money and the open opportunities are below</div>
            </div>
          )}
        </div>
        <div className="card dz-stat dz-cell">
          <div className="dz-stat-title dz-microlabel">Arriving in {nextMonth.label}</div>
          <div className="dz-fig-md num">{pfMoneyLabel(ccy, arriving.amountMinor)}</div>
          <div className="dz-cell-sub">{portfolioQuery.isError ? "schedule temporarily unavailable" : `across ${arriving.count === 1 ? "1 payment" : `${arriving.count} payments`}`}</div>
        </div>
        <div className="card dz-stat dz-cell">
          <div className="dz-stat-title dz-microlabel">Interest paid to you so far</div>
          <div className="dz-fig-md green num">{pfMoneyLabel(ccy, realizedInterest)}</div>
          <div className="dz-cell-sub">{sinceLabel ? `since ${sinceLabel}` : "no distributions yet"}</div>
        </div>
        <div className="card dz-stat dz-cell">
          <div className="dz-stat-title dz-microlabel"><span className="red">Money not working</span> — just sitting</div>
          <div className="dz-fig-md num">{pfMoneyLabel(ccy, notWorkingMinor)}</div>
          <div className="dz-cell-sub">{idlePct}% of your money, earning nothing</div>
          {frozenMinor > 0 ? (
            <div className="dz-cell-sub red">of which {pfMoneyLabel(ccy, frozenMinor)} frozen, with a daily penalty</div>
          ) : null}
        </div>
      </div>

      <div className="dz-decisions" id="rule">
        <div className="dz-decisions-head">
          <span className="dz-decisions-cap">Waiting on your decision</span>
          <span style={{ flex: 1 }} />
          <span className="dz-serif">the clicks that bind — everything else can wait</span>
        </div>

        {smartInvestQuery.isError && !smartInvest ? (
          <DataErrorCard title="Smart-Invest is temporarily unavailable" onRetry={() => void smartInvestQuery.refetch()}>
            Your dashboard is still available. Retry to load your saved rule and matching opportunities.
          </DataErrorCard>
        ) : null}

        {smartRuleActive && deskMatches.length > 0 ? (
          <div className="dz-desk">
            <div className="dz-desk-head">
              <span className="dz-desk-title">Your rule found {deskMatches.length === 1 ? "1 opportunity" : `${deskMatches.length} opportunities`}</span>
              <span className="dz-desk-sub">{pfMoneyLabel(ccy, idleMinor)} free to place · {deskTicked.length} of {deskTickable.length} ticked · nothing commits until you confirm</span>
              {deskSelectable.length > 0 ? (
                <Button className="dz-desk-toggle" onClick={toggleDeskSelection} size="sm" variant="ghost">
                  {deskAllUnticked ? "Select all" : "Unselect all"}
                </Button>
              ) : null}
            </div>
            <div className="dz-desk-rows">
              {deskMatches.map((match) => {
                const tickable = isOpenMarketplaceLoan(match);
                const unaffordable = tickable && deskUnaffordable(match);
                const ticked = tickable && deskAffordableIds.has(match.loan_id);
                const amount = deskSplit.get(match.loan_id) ?? 0;
                const affordNote = deskPlan.blocked.get(match.loan_id) ?? (idleMinor <= 0
                  ? `You have no investable ${ccy} balance, so nothing can be committed to this loan yet.`
                  : `Splitting your ${pfMoneyLabel(ccy, idleMinor)} across the ticked loans leaves less than this loan's minimum investment of ${pfMoneyLabel(ccy, match.minimum_investment_minor)}.`);
                return (
                  <div className="dz-desk-row" key={match.loan_id}>
                    {!tickable ? (
                      <BlockedSelectionMarker label={match.title} reason="This opportunity is not currently open for investment." />
                    ) : unaffordable ? (
                      <BlockedSelectionMarker label={match.title} reason={affordNote} />
                    ) : (
                      <button aria-label={`${ticked ? "Untick" : "Tick"} ${match.title}`} className={`dz-tick${ticked ? " on" : ""}`} onClick={() => setUnticked((current) => ({ ...current, [match.loan_id]: !current[match.loan_id] }))} type="button">{ticked ? "✓" : ""}</button>
                    )}
                    <button className="dz-desk-name" onClick={() => setSheetLoan(match)} type="button">{match.title}</button>
                    <span className="dz-desk-meta num">{formatRateBps(match.yield_bps)} · {match.term_months} mo · {match.originator_name || platformName}</span>
                    <span className="dz-leader" />
                    {unaffordable ? (
                      <Tooltip content={affordNote} label={`Below minimum. ${affordNote}`}>
                        <span className="dz-desk-amt num">below minimum</span>
                      </Tooltip>
                    ) : <span className="dz-desk-amt num">{ticked && amount > 0 ? pfMoneyLabel(ccy, amount) : "—"}</span>}
                  </div>
                );
              })}
              <div className="dz-desk-foot">
                <span className="dz-desk-commit num">You commit {pfMoneyLabel(ccy, deskTotal)}</span>
                <span className="dz-desk-note">{frozenAccount.frozen ? frozenActionReason(frozenAccount) : deskBatchReady ? "nothing moves without this click" : deskAllUnticked ? "tick the opportunities you want to invest in" : "untick opportunities until each order reaches its minimum"}</span>
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
              <button aria-controls="dz-closing-rows" aria-expanded={closeOpen} className="si-dash-setup" onClick={() => setCloseOpen((open) => !open)} type="button">{closeOpen ? "Hide" : "Check"} <span aria-hidden="true">{closeOpen ? "▴" : "▾"}</span></button>
            </div>
            {closeOpen ? (
              <div className="si-dash-rows" id="dz-closing-rows">
                {closingSoon.map((entry) => (
                  <button className="si-dash-row" key={entry.loan.loan_id} onClick={() => setSheetLoan(entry.loan)} type="button">
                    <span className="si-dash-row-name">{entry.loan.title}</span>
                    <span className="si-dash-row-meta">{formatRateBps(marketplaceYieldBps(entry.loan))} · {entry.loan.term_months} mo · {entry.loan.originator_name || platformName}</span>
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
          <span className="dz-next12-cur">{ccy}</span>
          <span className="dz-next12-val num">{formatMoneyMinor(next12Minor, ccy).split(".")[0]}</span>
          <span className="dz-next12-cents num">.{formatMoneyMinor(next12Minor, ccy).split(".")[1] ?? "00"}</span>
        </div>
        <div className="dz-income-link"><button className="fs-clear-link" onClick={() => goTo(setRoute, "portfolio")} type="button">Beyond 12 months, and the loan behind every payment, in My investments →</button></div>
        <div className="dz-income-legend"><span className="dz-legend-swatch" />Months marked with a dark line at the bottom are where one or more loans make their final repayment, so your income may decrease from then on unless you reinvest.</div>
      </div>

      <div className="dz-compare">
        <button aria-controls="dz-compare-body" aria-expanded={compareOpen} className="dz-sect-head as-btn" onClick={() => setCompareOpen((open) => !open)} type="button">
          <span aria-hidden="true" className="dz-sect-sign">{compareOpen ? "–" : "+"}</span>
          <span className="dz-sect-title">What you invested and what you earned</span>
          <span style={{ flex: 1 }} />
          <span className="dz-compare-gain num">+ {pfMoneyLabel(ccy, Math.max(0, scenarioBInterest - scenarioAInterest))} if everything were reinvested</span>
        </button>
        {compareOpen ? (
          <div className="dz-compare-body" id="dz-compare-body">
            <p className="dz-compare-intro">Two scenarios on the same {pfMoneyLabel(ccy, totalBase)}, from {startLabel} to the last scheduled repayment in {horizonLabel}. Totals, not a rate per year.</p>
            <div className="dz-chart-card">
              <svg viewBox="0 0 880 326" style={{ display: "block", maxWidth: "100%" }}>
                {[0, 1, 2, 3, 4].map((step) => (
                  <line key={step} x1="46" y1={20 + step * 53.2} x2="790" y2={20 + step * 53.2} stroke="#e6e6e6" strokeWidth="1" />
                ))}
                {[0, 1, 2, 3, 4].map((step) => (
                  <text key={step} x="38" y={24 + step * 53.2} textAnchor="end" fontSize="11" fill="#6e6e6e">{Math.round(chartMax - (step * chartMax) / 5)}%</text>
                ))}
                <line x1="46" y1="286" x2="790" y2="286" stroke="#0a0a0a" strokeWidth="1" />
                <text x="38" y="290" textAnchor="end" fontSize="11" fill="#6e6e6e">0</text>
                <polyline points={`46,286 283,${chartY(pctPaid)} 790,${chartY(pctA)}`} fill="none" stroke="#0a0a0a" strokeWidth="2.5" />
                <polyline points={`283,${chartY(pctPaid)} 790,${chartY(pctB)}`} fill="none" stroke="#1e7a46" strokeWidth="2.5" />
                <line x1="283" y1="20" x2="283" y2="286" stroke="#b3261e" strokeWidth="1" strokeDasharray="3 3" />
                <circle cx="46" cy="286" r="4" fill="#0a0a0a" />
                <circle cx="283" cy={chartY(pctPaid)} r="4.5" fill="#b3261e" />
                <circle cx="790" cy={chartY(pctA)} r="4.5" fill="#0a0a0a" />
                <circle cx="790" cy={chartY(pctB)} r="4.5" fill="#1e7a46" />
                <text x="46" y="303" textAnchor="start" fontSize="11" fill="#6e6e6e">{startLabel}</text>
                <text x="283" y="303" textAnchor="middle" fontSize="11" fontWeight="600" fill="#b3261e">today</text>
                <text x="790" y="303" textAnchor="end" fontSize="11" fill="#6e6e6e">{horizonLabel}</text>
                <text x="800" y={chartY(pctA) + 4} textAnchor="start" fontSize="13" fontWeight="700" fill="#0a0a0a">+{formatPercent(pctA, 1)}</text>
                <text x="800" y={chartY(pctB) + 4} textAnchor="start" fontSize="13" fontWeight="700" fill="#1e7a46">+{formatPercent(pctB, 1)}</text>
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
                <span className="dz-scn-col sm"><span className="dz-scn-mult num">{totalBase > 0 ? formatDecimal((1 + scenarioAInterest / totalBase), 2) : formatDecimal(1, 2)}×</span><span className="dz-scn-pct num">+{formatPercent(pctA, 1)}</span></span>
              </div>
              <div className="dz-scn-row">
                <span className="dz-scn-name"><span className="dz-scn-line"><span className="dz-scn-swatch green" /><strong>Everything reinvested</strong></span><span className="dz-scn-desc">{bestOpenBps > 0 ? `Every repayment is lent onward at today’s best open rate of ${formatRateBps(bestOpenBps)} the month it arrives, and the ${pfMoneyLabel(ccy, idleMinor)} is lent too.` : "No open opportunity currently supplies a reinvestment rate, so this scenario adds no assumed reinvestment return."}</span></span>
                <span className="dz-scn-col num">{pfMoneyLabel(ccy, totalBase)}</span>
                <span className="dz-scn-col num green">{pfMoneyLabel(ccy, scenarioBInterest)}</span>
                <span className="dz-scn-col wide num">{pfMoneyLabel(ccy, totalBase + scenarioBInterest)}</span>
                <span className="dz-scn-col sm"><span className="dz-scn-mult num green">{totalBase > 0 ? formatDecimal((1 + scenarioBInterest / totalBase), 2) : formatDecimal(1, 2)}×</span><span className="dz-scn-pct num">+{formatPercent(pctB, 1)}</span></span>
              </div>
              <div className="dz-scn-row total">
                <span style={{ flex: 1, fontWeight: 600 }}>The difference reinvesting makes</span>
                <span className="dz-scn-col dim">no extra capital</span>
                <span className="dz-scn-col num green big">{pfMoneyLabel(ccy, Math.max(0, scenarioBInterest - scenarioAInterest))}</span>
                <span className="dz-scn-col wide num dim">{pfMoneyLabel(ccy, Math.max(0, scenarioBInterest - scenarioAInterest))}</span>
                <span className="dz-scn-col sm num green">+{formatDecimal(Math.max(0, pctB - pctA), 1)} pts</span>
              </div>
              <div className="dz-scn-note">Both scenarios hold the same {pfMoneyLabel(ccy, totalBase)} — {pfMoneyLabel(ccy, investedMinor)} lent and {pfMoneyLabel(ccy, idleMinor)} in your wallet — to the last scheduled repayment in {horizonLabel}. {pfMoneyLabel(ccy, realizedInterest)} of the interest is already paid and counted in both. The rest depends on the borrowers paying as agreed{bestOpenBps > 0 ? `, and the green scenario also assumes a loan at today’s best open rate of ${formatRateBps(bestOpenBps)} is available every time you have money to place.` : ". The green scenario currently assumes no additional return because no open reinvestment rate is available."}</div>
            </div>
          </div>
        ) : null}
      </div>

      {batchOpen ? (
        <ApproveAllocationModal
          initialUnticked={unticked}
          matches={deskMatches as unknown as MarketplaceLoanPreview[]}
          onClose={() => setBatchOpen(false)}
          onDone={() => {
            setBatchOpen(false);
            void dashboardQuery.refetch();
            void balancesQuery.refetch();
            void smartInvestQuery.refetch();
            void portfolioQuery.refetch();
          }}
          setInvestLoan={setInvestLoan}
          setRoute={setRoute}
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

type AllocMatch = MarketplaceLoanPreview;

type AllocPlan = {
  ticked: Set<string>;
  split: Map<string, number>;
  blocked: Map<string, string>;
  totals: Map<string, number>;
};

type BatchPreparedQuote = Pick<
  OriginatorClaimQuoteResponse,
  | "quote_id"
  | "loan_id"
  | "currency"
  | "requested_cash_minor"
  | "executable_cash_minor"
  | "assigned_principal_minor"
  | "target_yield_bps"
  | "rounding_remainder_minor"
  | "entitlement_start_at"
  | "expires_at"
>;

// A quote's time to live (expires_at − entitlement_start_at, both on the platform clock). The
// countdown runs from when the browser received the quotes, so a browser clock that differs from
// the platform (QA) clock cannot expire them early or keep them alive (FRONTCODE-15).
function batchQuoteLifetimeMs(quote: Pick<BatchPreparedQuote, "entitlement_start_at" | "expires_at">) {
  const lifetime = Date.parse(quote.expires_at) - Date.parse(quote.entitlement_start_at);
  return Number.isFinite(lifetime) && lifetime > 0 ? lifetime : 0;
}

function allocationPlan(
  matches: AllocMatch[],
  untickedIds: Record<string, boolean>,
  allocByCcy: Map<string, number>,
  lots: BalanceLot[] | undefined
): AllocPlan {
  const ticked = new Set<string>();
  const split = new Map<string, number>();
  const blocked = new Map<string, string>();
  const totals = new Map<string, number>();
  const currencies = Array.from(new Set(matches.map((match) => match.currency)));
  for (const currency of currencies) {
    const alloc = allocByCcy.get(currency) ?? 0;
    const pool = matches.filter((match) => match.currency === currency);
    const splitSources = (selected: AllocMatch[]) => {
      const remaining = new Map((lots ?? []).map((lot) => [lot.id, lot.available_amount_minor]));
      const amounts = new Map<string, number>();
      const per = selected.length > 0 ? Math.floor(alloc / selected.length) : 0;
      // Long windows have fewer eligible sources; allocate those first, as on the server.
      const ordered = [...selected].sort((a, b) =>
        (b.funding_deadline ?? "").localeCompare(a.funding_deadline ?? "") || a.loan_id.localeCompare(b.loan_id)
      );
      for (const match of ordered) {
        let needed = Math.min(per, marketplaceAvailableMinor(match));
        let assigned = 0;
        const eligible = currentInvestableLotsForLoanCurrency(lots, match).sort((a, b) =>
          a.received_at.localeCompare(b.received_at) || a.id.localeCompare(b.id)
        );
        for (const lot of eligible) {
          const amount = Math.min(needed, remaining.get(lot.id) ?? 0);
          remaining.set(lot.id, (remaining.get(lot.id) ?? 0) - amount);
          needed -= amount;
          assigned += amount;
        }
        amounts.set(match.loan_id, assigned);
      }
      return amounts;
    };
    let selected = alloc > 0 ? pool.filter((match) => !untickedIds[match.loan_id]) : [];
    for (;;) {
      if (selected.length === 0) break;
      const amounts = splitSources(selected);
      const affordable = selected.filter(
        (match) => (amounts.get(match.loan_id) ?? 0) >= match.minimum_investment_minor
      );
      if (affordable.length === selected.length) break;
      selected = affordable;
    }
    let total = 0;
    const amounts = splitSources(selected);
    for (const match of selected) {
      const amount = amounts.get(match.loan_id) ?? 0;
      ticked.add(match.loan_id);
      split.set(match.loan_id, amount);
      total += amount;
    }
    totals.set(currency, total);
    for (const match of pool) {
      if (ticked.has(match.loan_id)) continue;
      if (marketplaceAvailableMinor(match) < match.minimum_investment_minor) {
        blocked.set(match.loan_id,
          `This opportunity has only ${pfMoneyLabel(currency, marketplaceAvailableMinor(match))} left, less than its minimum investment of ${pfMoneyLabel(currency, match.minimum_investment_minor)}.`
        );
        continue;
      }
      if (sumLotAvailableMinor(currentInvestableLotsForLoanCurrency(lots, match)) < match.minimum_investment_minor) {
        blocked.set(match.loan_id,
          currencyBalanceMinor(lots, currency) < match.minimum_investment_minor
            ? `Your ${currency} balance is below this loan's minimum investment of ${pfMoneyLabel(currency, match.minimum_investment_minor)}.`
            : `Your eligible ${currency} sources cannot cover this loan's remaining funding period at its minimum investment. Use newer funds or choose a shorter funding window.`
        );
        continue;
      }
      if (untickedIds[match.loan_id]) {
        // Manually unticked: disabled only if re-ticking could never reach its minimum.
        const withIt = [...selected, match];
        let test = withIt;
        for (;;) {
          if (test.length === 0) break;
          const testAmounts = splitSources(test);
          const ok = test.filter(
            (candidate) => (testAmounts.get(candidate.loan_id) ?? 0) >= candidate.minimum_investment_minor
          );
          if (ok.length === test.length) break;
          test = ok;
        }
        if (!test.some((candidate) => candidate.loan_id === match.loan_id)) {
          blocked.set(
            match.loan_id,
            alloc <= 0
              ? `You are allocating no ${currency}, so nothing can be committed to this loan.`
              : `Splitting ${pfMoneyLabel(currency, alloc)} across the ticked loans would leave less than this loan's minimum investment of ${pfMoneyLabel(currency, match.minimum_investment_minor)}.`
          );
        }
      } else {
        blocked.set(
          match.loan_id,
          alloc <= 0
            ? `You are allocating no ${currency}, so nothing can be committed to this loan.`
            : `Splitting ${pfMoneyLabel(currency, alloc)} across the ticked loans leaves less than this loan's minimum investment of ${pfMoneyLabel(currency, match.minimum_investment_minor)}.`
        );
      }
    }
  }
  return { ticked, split, blocked, totals };
}

function allocCommitLabel(totals: Map<string, number>) {
  const parts = Array.from(totals.entries())
    .filter(([, amount]) => amount > 0)
    .map(([currency, amount]) => pfMoneyLabel(currency, amount));
  return parts.length > 0 ? parts.join(" + ") : "—";
}

function ApproveAllocationModal({
  matches,
  initialUnticked,
  onClose,
  onDone,
  setRoute,
  setInvestLoan
}: {
  matches: AllocMatch[];
  initialUnticked: Record<string, boolean>;
  onClose: () => void;
  onDone: () => void;
  setRoute: (route: AppRoute) => void;
  setInvestLoan: (loan: MarketplaceLoanDetail | null, initialAmount?: string) => void;
}) {
  const queryClient = useQueryClient();
  const balances = useBalancesData().data;
  const tickable = matches.filter(isOpenMarketplaceLoan);
  const currencies = Array.from(new Set(tickable.map((match) => match.currency))).sort();
  const investableByCcy = new Map(
    currencies.map((currency) => [
      currency,
      balances?.summaries.find((summary) => summary.currency === currency)?.investable_minor ?? 0
    ])
  );
  const [unticked, setUnticked] = useState<Record<string, boolean>>(initialUnticked);
  const [allocText, setAllocText] = useState<Record<string, string>>({});
  const [step, setStep] = useState<"allocate" | "confirm" | "done">("allocate");
  const [ack, setAck] = useState(false);
  // The same risk acknowledgement as a single investment (audit A-31 / JOURNEY-12).
  const [riskAck, setRiskAck] = useState(false);
  const [batchResult, setBatchResult] = useState<PrimaryOrderBatchResponse | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [sheetLoan, setSheetLoan] = useState<AllocMatch | null>(null);
  const [preparedQuotes, setPreparedQuotes] = useState<Record<string, BatchPreparedQuote>>({});
  const [preparingQuotes, setPreparingQuotes] = useState(false);
  const [quoteClock, setQuoteClock] = useState(() => Date.now());
  const [quotesReceivedAt, setQuotesReceivedAt] = useState(0);
  const [batchKey] = useState(() => idempotencyKey("primary-batch"));
  const [acceptanceKey, setAcceptanceKey] = useState(() => idempotencyKey("primary-batch-accept"));
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const batchMutation = useMarketplacePrimaryOrdersBatchCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.primary_investment);
  useAutoRequestEmailCode(codeRequest, step === "confirm");
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.primary_market_investment },
    { query: { enabled: !isFixturePreview && step === "confirm", retry: false } }
  );
  const busy = preparingQuotes || acceptanceMutation.isPending || batchMutation.isPending;
  const termsLabels = templateLabels(termsQuery.data);
  const termsReady = isFixturePreview || Boolean(termsQuery.data && termsLabels.length > 0);
  // Escape, Tab and focus follow the shared dialog rules; the loan sheet opened from here is the
  // top-most dialog while it is open, so Escape closes only that sheet.
  const approveRef = useRef<HTMLDivElement>(null);
  useDialog({
    dialogRef: approveRef,
    onDismiss: () => (step === "done" ? onDone() : onClose()),
    busy
  });
  useEffect(() => {
    if (step !== "confirm" || Object.keys(preparedQuotes).length === 0) return undefined;
    setQuoteClock(Date.now());
    const timer = window.setInterval(() => setQuoteClock(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [preparedQuotes, step]);

  const allocByCcy = new Map<string, number>();
  const allocationIssues = new Map<string, string>();
  for (const currency of currencies) {
    const investable = investableByCcy.get(currency) ?? 0;
    const raw = allocText[currency];
    if (raw === undefined) {
      allocByCcy.set(currency, investable);
    } else {
      const parsed = parseMoneyInputToMinorUnits(raw, currency);
      if (parsed.error) allocationIssues.set(currency, parsed.error);
      else if (parsed.amountMinor <= 0) allocationIssues.set(currency, "Enter an amount greater than zero.");
      else if (parsed.amountMinor > investable) {
        allocationIssues.set(
          currency,
          `The allocation exceeds your investable balance of ${pfMoneyLabel(currency, investable)}.`
        );
      }
      allocByCcy.set(currency, Math.min(investable, Math.max(0, parsed.amountMinor)));
    }
  }
  const plan = allocationPlan(tickable, unticked, allocByCcy, balances?.lots);
  const items = tickable
    .filter((match) => plan.ticked.has(match.loan_id))
    .map((match) => ({ match, amountMinor: plan.split.get(match.loan_id) ?? 0 }));
  const reviewItems = items.map((item) => ({
    ...item,
    amountMinor:
      usesImmediateClaimAssignment(item.match)
        ? preparedQuotes[item.match.loan_id]?.executable_cash_minor ?? item.amountMinor
        : item.amountMinor,
    quote: preparedQuotes[item.match.loan_id]
  }));
  const reviewTotals = new Map<string, number>();
  for (const item of reviewItems) {
    reviewTotals.set(
      item.match.currency,
      (reviewTotals.get(item.match.currency) ?? 0) + item.amountMinor
    );
  }
  const selectedCount = items.length;
  const immediateClaimCount = items.filter((item) => usesImmediateClaimAssignment(item.match)).length;
  // After placing, count from the server's orders: a round can close (and invest) at once.
  const reservedOrderCount = batchResult
    ? batchResult.orders.filter((order) => order.status === "balance_allocated" || order.status === "partially_allocated").length
    : selectedCount - immediateClaimCount;
  const investedOrderCount = batchResult ? batchResult.orders.filter((order) => order.status === "closed_invested").length : 0;
  const quoteExpiryMs = quotesReceivedAt + Math.min(
    ...Object.values(preparedQuotes).map((quote) => batchQuoteLifetimeMs(quote))
  );
  const hasPreparedQuotes = immediateClaimCount === Object.keys(preparedQuotes).length;
  const quotesExpired = immediateClaimCount > 0 && (!Number.isFinite(quoteExpiryMs) || quoteExpiryMs <= quoteClock);
  const quoteSecondsRemaining = Number.isFinite(quoteExpiryMs)
    ? Math.max(0, Math.ceil((quoteExpiryMs - quoteClock) / 1_000))
    : 0;

  const prepareReview = async () => {
    setError("");
    setPreparingQuotes(true);
    try {
      const claimItems = items.filter((item) => usesImmediateClaimAssignment(item.match));
      const quotes = await Promise.all(
        claimItems.map(async (item) => {
          if (isFixturePreview) {
            return {
              quote_id: `preview-${item.match.loan_id}`,
              loan_id: item.match.loan_id,
              currency: item.match.currency,
              requested_cash_minor: item.amountMinor,
              executable_cash_minor: item.amountMinor,
              assigned_principal_minor: item.amountMinor,
              target_yield_bps: marketplaceYieldBps(item.match),
              rounding_remainder_minor: 0,
              entitlement_start_at: new Date().toISOString(),
              expires_at: new Date(Date.now() + 5 * 60_000).toISOString()
            } satisfies BatchPreparedQuote;
          }
          return originatorClaimsLoansQuoteCreate(item.match.loan_id, {
            requested_cash_minor: item.amountMinor
          });
        })
      );
      const nextQuotes = Object.fromEntries(quotes.map((quote) => [quote.loan_id, quote]));
      setPreparedQuotes(nextQuotes);
      setQuotesReceivedAt(Date.now());
      setAcceptanceKey(idempotencyKey("primary-batch-accept"));
      setAck(false);
      setRiskAck(false);
      setCode("");
      setQuoteClock(Date.now());
      setStep("confirm");
    } catch (quoteError) {
      setError(
        `Prices could not be prepared. No money moved. ${apiErrorMessage(quoteError)}`
      );
    } finally {
      setPreparingQuotes(false);
    }
  };

  const submit = async () => {
    setError("");
    if (!ack || !riskAck) {
      setError("Accept the investment terms and the risk disclosure first.");
      return;
    }
    if (isFixturePreview) {
      if (codeRequest.pin.previewAccepts()) setStep("done");
      return;
    }
    if (!termsQuery.data || termsLabels.length === 0) {
      setError("Current investment terms are not available. Retry after the document template is published.");
      return;
    }
    if (!codeRequest.codeId) {
      setError("Request an email code before confirming the batch.");
      return;
    }
    if (!hasPreparedQuotes) {
      setError("One or more originator-claim prices are missing. Refresh prices and review again.");
      return;
    }
    if (quotesExpired) {
      setError("One or more originator-claim prices expired. Refresh prices before confirming.");
      return;
    }
    try {
      const acceptance = await acceptanceMutation.mutateAsync({
        data: {
          category: CategoryEnum.primary_market_investment,
          expected_template_version_id: termsQuery.data.id,
          accepted_checkbox_labels: termsLabels,
          context_type: "primary_order_batch",
          context_id: batchKey,
          data_snapshot: {
            items: reviewItems.map((item) => ({
              loan_id: item.match.loan_id,
              amount_minor: item.amountMinor,
              currency: item.match.currency,
              ...(item.quote ? { quote_id: item.quote.quote_id } : {})
            }))
          },
          idempotency_key: acceptanceKey
        }
      });
      const placed = await batchMutation.mutateAsync({
        data: {
          items: reviewItems.map((item) => ({
            loan_id: item.match.loan_id,
            amount_minor: item.amountMinor,
            ...(item.quote ? { quote_id: item.quote.quote_id } : {})
          })),
          document_acceptance_id: acceptance.id,
          idempotency_key: batchKey,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          pin: codeRequest.pin.value
        }
      });
      // Money moved: refresh balances, portfolio and every list, as the other flows do
      // (audit A-42 / FRONTCODE-09).
      void queryClient.invalidateQueries();
      setBatchResult(placed);
      setStep("done");
    } catch (submitError) {
      if (codeRequest.pin.handleError(submitError)) return;
      setError(apiErrorMessage(submitError));
    }
  };
  const dismiss = () => {
    if (busy) return;
    if (step === "done") onDone();
    else onClose();
  };

  return (
    <div className="ls-scrim">
      <button aria-label="Dismiss" className="ls-overlay-btn" disabled={busy} onClick={dismiss} tabIndex={-1} type="button" />
      <div aria-label="Approve this allocation." aria-modal="true" className="ls-modal aa-modal" ref={approveRef} role="dialog">
        <div className="ls-scroll aa-scroll">
          {step === "done" ? (
            <div className="aa-done">
              <div className="aa-eyebrow">Investments confirmed</div>
              <h2 className="aa-title">Every selected investment is in.</h2>
              <p className="aa-done-text">
                {allocCommitLabel(reviewTotals)} committed across {selectedCount === 1 ? "1 loan" : `${selectedCount} loans`}.
                {reservedOrderCount > 0 ? ` ${reservedOrderCount === 1 ? "One order reserves" : `${reservedOrderCount} orders reserve`} balance until the applicable funding round closes.` : ""}
                {investedOrderCount > 0 ? ` ${investedOrderCount === 1 ? "One funding round" : `${investedOrderCount} funding rounds`} closed at once, so ${investedOrderCount === 1 ? "that investment is" : "those investments are"} already active.` : ""}
                {immediateClaimCount > 0 ? ` ${immediateClaimCount === 1 ? "One legacy Loan Originator claim was" : `${immediateClaimCount} legacy Loan Originator claims were`} purchased immediately at the reviewed prices.` : ""}
              </p>
            </div>
          ) : step === "confirm" ? (
            <div className="aa-body">
              <div className="aa-eyebrow">Approve the allocation</div>
              <h2 className="aa-title">One code covers every investment.</h2>
              <div className="si-dash-rows aa-review-rows">
                {reviewItems.map((item) => (
                  <div className="si-dash-row" key={item.match.loan_id} style={{ cursor: "default" }}>
                    <span className="si-dash-row-name">{item.match.title}</span>
                    <span className="si-dash-row-meta">
                      {formatRateBps(marketplaceYieldBps(item.match))} · {item.match.term_months} mo · {item.match.originator_name || platformName}
                      {item.quote ? ` · assigned principal ${pfMoneyLabel(item.match.currency, item.quote.assigned_principal_minor)}` : " · reserved until funding close"}
                    </span>
                    <span className="dz-leader" />
                    <span className="si-dash-row-amt">{pfMoneyLabel(item.match.currency, item.amountMinor)}</span>
                  </div>
                ))}
                <div className="si-dash-rows-foot">
                  <span className="num" style={{ fontWeight: 600, color: "#0a0a0a" }}>You commit {allocCommitLabel(reviewTotals)}</span>
                  <span style={{ flex: 1 }} />
                  <span>one terms acceptance and one email code cover every investment in this batch</span>
                </div>
              </div>
              {immediateClaimCount > 0 ? (
                <Banner tone={quotesExpired ? "bad" : "info"} title={quotesExpired ? "Quoted prices expired" : "Loan Originator prices locked"}>
                  {quotesExpired
                    ? "Refresh prices and review the updated cash and assigned-principal amounts before confirming."
                    : `The ${immediateClaimCount === 1 ? "legacy claim price is" : "legacy claim prices are"} executable for ${Math.floor(quoteSecondsRemaining / 60)}:${String(quoteSecondsRemaining % 60).padStart(2, "0")}. Minor-unit rounding not used by a quote remains in your balance.`}
                  <div style={{ marginTop: 10 }}>
                    <button className="aa-link" disabled={busy} onClick={() => void prepareReview()} type="button">
                      {preparingQuotes ? "Refreshing prices..." : "Refresh prices"}
                    </button>
                  </div>
                </Banner>
              ) : null}
              <Check checked={ack} id="aa-ack" onChange={setAck}>
                I accept the current <LegalDocLink category="primary_market_investment">primary-market investment terms</LegalDocLink> for every investment listed above.
              </Check>
              <Check checked={riskAck} id="aa-risk-ack" onChange={setRiskAck}>
                I acknowledge the <LegalDocLink category="risk_disclosure">risk disclosure</LegalDocLink> and possible capital loss.
              </Check>
              {!isFixturePreview && termsQuery.isLoading ? <p className="muted">Loading the current published terms...</p> : null}
              {!isFixturePreview && !termsQuery.isLoading && !termsReady ? (
                <Banner tone="bad" title="Investment terms unavailable">The current server-published investment terms could not be loaded. No order can be placed until a current version is available.</Banner>
              ) : null}
              {!isFixturePreview && termsQuery.data ? <p className="muted" style={{ fontSize: 11.5 }}>Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
              <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code and your PIN. One code covers the whole batch.</Banner>
              <SensitiveActionFields code={code} codeRequest={codeRequest} onCodeChange={setCode} onContinue={() => void submit()} />
              {error ? <Banner tone="bad" title="Batch not placed">{error}</Banner> : null}
            </div>
          ) : (
            <div className="aa-body">
              <div className="aa-eyebrow">Approve the allocation</div>
              <h2 className="aa-title">Approve this allocation.</h2>
              <div className="aa-intro">
                {tickable.length === 1 ? "1 opportunity meets" : `${tickable.length} opportunities meet`} your conditions today{selectedCount === tickable.length ? ", and every one is ticked" : ""}. Untick anything you would rather skip — your capital is split equally between whatever stays ticked, so unticking one gives the others more. Legacy immediate-assignment prices are locked on the next step; funding-round opportunities reserve at par. The small i opens any loan in full — your ticks keep waiting underneath.
              </div>
              <div className="aa-list-head">
                <span className="aa-list-cap">Today&apos;s allocation</span>
                <span style={{ flex: 1 }} />
                <button className="aa-link" onClick={() => setUnticked({})} type="button">all</button>
                <button className="aa-link" onClick={() => setUnticked(Object.fromEntries(tickable.map((match) => [match.loan_id, true])))} type="button">none</button>
              </div>
              {currencies.map((currency) => (
                <div className="aa-alloc-row" key={currency}>
                  <span className="aa-alloc-cap">Allocating{currencies.length > 1 ? ` · ${currency}` : ""}</span>
                  <div className="aa-alloc-box">
                    <span className="aa-alloc-cur">{currency}</span>
                    <input
                      aria-label={`Amount to allocate in ${currency}`}
                      className="aa-alloc-input"
                      inputMode="decimal"
                      onChange={(event) => setAllocText((current) => ({ ...current, [currency]: event.target.value }))}
                      type="text"
                      value={allocText[currency] ?? formatMoneyMinor(allocByCcy.get(currency) ?? 0, currency).replace(/[^\d.]/g, "")}
                    />
                  </div>
                  <button className="aa-chip" onClick={() => setAllocText((current) => ({ ...current, [currency]: formatMoneyMinor(investableByCcy.get(currency) ?? 0, currency).replace(/[^\d.]/g, "") }))} type="button">
                    My balance · {pfMoneyLabel(currency, investableByCcy.get(currency) ?? 0)}
                  </button>
                  {allocationIssues.has(currency) || (investableByCcy.get(currency) ?? 0) <= 0 ? (
                    <button className="aa-chip add" onClick={() => { onClose(); goTo(setRoute, "balances"); }} type="button">Add money →</button>
                  ) : null}
                  {allocationIssues.has(currency) ? <span className="aa-alloc-error" role="alert">{allocationIssues.get(currency)}</span> : null}
                </div>
              ))}
              <div className="aa-rows">
                {tickable.map((match) => {
                  const ticked = plan.ticked.has(match.loan_id);
                  const reason = plan.blocked.get(match.loan_id);
                  const blockedNow = reason !== undefined;
                  const amount = plan.split.get(match.loan_id) ?? 0;
                  const days = match.funding_deadline
                    ? fundingDaysRemaining(match.funding_deadline, balances?.as_of)
                    : null;
                  return (
                    <div className="aa-row" key={match.loan_id}>
                      {ticked ? (
                        <button aria-label={`Untick ${match.title}`} className="dz-tick on" onClick={() => setUnticked((current) => ({ ...current, [match.loan_id]: true }))} type="button">✓</button>
                      ) : blockedNow ? (
                        <BlockedSelectionMarker label={match.title} reason={reason} />
                      ) : (
                        <button aria-label={`Tick ${match.title}`} className="dz-tick" onClick={() => setUnticked((current) => ({ ...current, [match.loan_id]: false }))} type="button" />
                      )}
                      <span className="aa-row-main">
                        <span className="aa-row-name">
                          {match.title}
                          <button aria-label={`Open ${match.title} in full`} className="aa-info" onClick={() => setSheetLoan(match)} type="button">i</button>
                        </span>
                        <span className="aa-row-meta num">{formatRateBps(marketplaceYieldBps(match))} · {match.term_months} mo · {match.originator_name || platformName}{days !== null ? ` · closes in ${days === 1 ? "1 day" : `${days} days`}` : ""}</span>
                      </span>
                      {blockedNow && !ticked ? (
                        <Tooltip content={reason} label={`Below minimum. ${reason}`}>
                          <span className="aa-row-amt num">below minimum</span>
                        </Tooltip>
                      ) : <span className="aa-row-amt num">{ticked && amount > 0 ? pfMoneyLabel(match.currency, amount) : "—"}</span>}
                    </div>
                  );
                })}
              </div>
              <div className="aa-foot-row">
                <span className="aa-selected">{selectedCount} selected</span>
                <span className="aa-foot-dots" />
                <span className="aa-committing">committing</span>
                <span className="aa-commit-total num">{allocCommitLabel(plan.totals)}</span>
              </div>
              {error ? <div className="smart-inline-error" role="alert">{error}</div> : null}
            </div>
          )}
        </div>
        <div className="aa-actions">
          {step === "done" ? (
            <button className="aa-confirm" onClick={onDone} type="button">Done</button>
          ) : step === "confirm" ? (
            <>
              <button className="aa-confirm" disabled={!ack || !riskAck || code.length < 6 || !codeRequest.pin.ready || busy || quotesExpired || !hasPreparedQuotes || !termsReady || (!isFixturePreview && !codeRequest.codeId)} onClick={() => void submit()} type="button">{busy ? "Placing investments..." : `Place ${selectedCount === 1 ? "1 investment" : `${selectedCount} investments`}`}</button>
              <button className="aa-cancel" disabled={busy} onClick={() => { setStep("allocate"); setPreparedQuotes({}); setError(""); }} type="button">Back</button>
            </>
          ) : (
            <>
              <button className="aa-confirm" disabled={selectedCount === 0 || allocationIssues.size > 0 || preparingQuotes} onClick={() => void prepareReview()} type="button">{preparingQuotes ? "Preparing prices..." : `Confirm ${selectedCount}`}</button>
              <button className="aa-cancel" onClick={onClose} type="button">Cancel</button>
            </>
          )}
        </div>
      </div>
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
    </div>
  );
}

function KycBanner({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const fxEnabled = useFxFeature().enabled;
  return (
    <Banner
      actions={<Button size="sm" variant="primary" onClick={() => goTo(setRoute, "kyc")}>View verification status</Button>}
      icon="shield"
      tone="info"
      title="Identity verification in progress"
    >
      KYC is being reviewed. Deposits, investing{fxEnabled ? ", withdrawals and FX unlock" : " and withdrawals unlock"} once verification
      is approved.
    </Banner>
  );
}

// The shared "unsecured" rule (portfolioCollateral.ts), also used by the portfolio widgets.
const mkIsUnsecured = (loan: MarketplaceLoanPreview) => isUnsecuredLoan(loan);
const mkYieldPct = (loan: MarketplaceLoanPreview) => marketplaceYieldBps(loan) / 100;

// Same semantics as the backend rule: conditions combine with AND, the values
// ticked inside one condition with OR, and an empty list does not restrict.
function mkMatches(loan: MarketplaceLoanPreview, filters: MkFilters, skip?: keyof MkFilters) {
  const haystack = `${loan.loan_id} ${loan.title} ${loan.originator_name ?? ""} ${loan.borrower_display_name ?? ""} ${loan.purpose} ${loan.collateral_type} ${loan.risk_rating}`.toLowerCase();
  const checks: [keyof MkFilters, boolean][] = [
    ["q", filters.q.trim() === "" || haystack.includes(filters.q.trim().toLowerCase())],
    ["minRate", filters.minRate === null || mkYieldPct(loan) >= filters.minRate - 0.001],
    ["maxTerm", filters.maxTerm === null || loan.term_months <= filters.maxTerm],
    ["orig", mkAnyOf(filters.orig, isOriginatorClaimLoan(loan) ? loan.originator_id ?? "" : mkBanxumSource)],
    ["col", mkCollateralMatches(filters.col, { unsecured: mkIsUnsecured(loan), collateralType: loan.collateral_type })],
    ["ccy", mkAnyOf(filters.ccy, loan.currency)],
    ["rating", mkAnyOf(filters.rating, loan.risk_rating)],
    ["purpose", mkAnyOf(filters.purpose, loan.purpose)],
    ["kind", mkAnyOf(filters.kind, loan.is_refinancing ? mkRefinancing : mkNewLending)]
  ];
  return checks.every(([key, ok]) => key === skip || ok);
}

function mkCollateralLabel(value: string) {
  if (value === mkAnyCollateral) return "With collateral (any type)";
  if (value === mkNoCollateral) return "No collateral";
  return humanizeToken(value);
}

function mkRatingLabel(value: string) {
  return value === "unrated" ? "Unrated" : value;
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
      originators: request.originators ?? [],
      collateral: request.collateral ?? [],
      currencies: request.currencies ?? [],
      risk_ratings: request.risk_ratings ?? [],
      purposes: request.purposes ?? [],
      loan_kinds: request.loan_kinds ?? [],
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
  { key: "rating", label: "Rating" },
  { key: "rate", label: "Yield" },
  { key: "term", label: "Term" },
  { key: "margin", label: "LTV" },
  { key: "available", label: "Available to invest" },
  { key: "closing", label: "Closes" }
];

function mkSortValue(loan: MarketplaceLoanPreview, key: string): number | string {
  if (key === "name") return loan.title.toLowerCase();
  if (key === "rating") return loan.risk_rating;
  if (key === "rate") return marketplaceYieldBps(loan);
  if (key === "term") return loan.term_months;
  if (key === "margin") return loanLtvBps(loan) ?? 999_999;
  if (key === "available") return marketplaceAvailableMinor(loan);
  return `${Number(isOpenMarketplaceLoan(loan)) === 1 ? "0" : "1"}${marketplaceClosingKey(loan)}`;
}

// The primary market opens in the Cards layout; the List layout is the sortable
// table. The choice is a per-browser convenience only.
type MkLayout = "cards" | "list";
const mkLayoutStorageKey = "banxum:marketplace-layout:v1";

function readMarketplaceLayout(): MkLayout {
  try {
    return window.localStorage.getItem(mkLayoutStorageKey) === "list" ? "list" : "cards";
  } catch {
    return "cards";
  }
}

function writeMarketplaceLayout(layout: MkLayout) {
  try {
    window.localStorage.setItem(mkLayoutStorageKey, layout);
  } catch {
    // Storage can be unavailable (private mode); the choice then lasts for this visit.
  }
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
  const [layout, setLayout] = useState<MkLayout>(readMarketplaceLayout);
  const pickLayout = (next: MkLayout) => {
    setLayout(next);
    writeMarketplaceLayout(next);
  };
  const [viewMode, setViewMode] = useState<"focused" | "detailed">("focused");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [capacityCurrency, setCapacityCurrency] = useState("CHF");
  const [showOrderGuide, setShowOrderGuide] = useState(false);
  const [smartInvestError, setSmartInvestError] = useState("");

  const setFlt = <K extends keyof MkFilters>(key: K, value: MkFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };
  const toggleFlt = (key: MkListKey, value: string) => {
    setFilters((current) => ({ ...current, [key]: mkToggle(current[key], value) }));
    if (key === "ccy" && !filters.ccy.includes(value)) setCapacityCurrency(value);
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
  // Rating-scale order (AAA first), not alphabetical.
  const ratings = mkOptionUnion(
    smartInvestCatalog.ratings.filter((rating) => openLoans.some((loan) => loan.risk_rating === rating)),
    Array.from(new Set(openLoans.map((loan) => loan.risk_rating))).sort()
  );
  const purposes = Array.from(new Set(openLoans.map((loan) => loan.purpose))).sort();

  // Multi-select toggle chips: every chip ticked in one group widens that group.
  const anyCollateralOn = filters.col.includes(mkAnyCollateral);
  const chip = (group: MkListKey, value: string, label: string, predicate: (loan: MarketplaceLoanPreview) => boolean) => {
    const count = openLoans.filter((loan) => predicate(loan) && mkMatches(loan, filters, group)).length;
    // "With collateral (any type)" already includes each collateral type: shown ticked, not clickable.
    const implied = group === "col" && anyCollateralOn && value !== mkAnyCollateral && value !== mkNoCollateral;
    const on = implied || filters[group].includes(value);
    return { group, value, label, count, on, implied };
  };
  const chipButton = (item: ReturnType<typeof chip>) => (
    <button
      aria-pressed={item.on}
      className={`fs-chip${item.on ? " on" : item.count === 0 ? " dim" : ""}${item.implied ? " implied" : ""}`}
      disabled={item.implied}
      key={`${item.group}-${item.value}`}
      onClick={() => toggleFlt(item.group, item.value)}
      title={item.implied ? "Included in With collateral (any type)" : undefined}
      type="button"
    >
      {item.label}
      <span className="fs-chip-count">{item.count}</span>
    </button>
  );
  const anyLabel = (selected: string[], unrestricted: string) =>
    selected.length === 0 ? <span className="fs-group-any">{unrestricted}</span> : null;

  const tokens: { label: string; clear: () => void }[] = [];
  if (filters.q.trim() !== "") tokens.push({ label: `matching "${filters.q.trim()}"`, clear: () => setFlt("q", "") });
  if (filters.minRate !== null) tokens.push({ label: `${formatPercent(filters.minRate, 1)} and up`, clear: () => setFlt("minRate", null) });
  if (filters.maxTerm !== null) tokens.push({ label: `up to ${filters.maxTerm} months`, clear: () => setFlt("maxTerm", null) });
  const listToken = (key: MkListKey, value: string, label: string) => {
    tokens.push({ label, clear: () => setFilters((current) => ({ ...current, [key]: current[key].filter((item) => item !== value) })) });
  };
  for (const source of filters.orig) {
    const originatorName = originators.find((originator) => originator.id === source)?.name;
    listToken("orig", source, source === mkBanxumSource ? "from BANXUM" : `from ${originatorName ?? "selected originator"}`);
  }
  for (const value of mkEffectiveCollateral(filters.col)) listToken("col", value, mkCollateralLabel(value).toLowerCase());
  for (const code of filters.ccy) listToken("ccy", code, code);
  for (const rating of filters.rating) listToken("rating", rating, `rated ${mkRatingLabel(rating)}`);
  for (const purpose of filters.purpose) listToken("purpose", purpose, humanizeToken(purpose).toLowerCase());
  for (const kind of filters.kind) listToken("kind", kind, kind === mkRefinancing ? "refinancings" : "new lending");
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
      setSmartInvestError("Choose at least one filter before saving a Smart-Invest rule.");
      return;
    }
    if (isReadonlyImpersonationActive()) {
      setSmartInvestError("Smart-Invest cannot be changed in a superadmin read-only view.");
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
      <PageHead
        actions={
          <div aria-label="View" className="seg mk-layout-switch" role="group">
            <button aria-pressed={layout === "cards"} className={layout === "cards" ? "on" : ""} onClick={() => pickLayout("cards")} type="button">
              <Icon name="grid" size={15} />
              Cards
            </button>
            <button aria-pressed={layout === "list"} className={layout === "list" ? "on" : ""} onClick={() => pickLayout("list")} type="button">
              <Icon name="list" size={15} />
              List
            </button>
          </div>
        }
        className="marketplace-intro"
        description={hasAccountMoney ? (
          "Two ways to put your money to work"
        ) : (
          <>
            Review each opportunity, target yield, collateral and repayment term. You decide where to
            invest; returns are not guaranteed and invested capital is at risk.
          </>
        )}
        eyebrow={loansQuery.isError && loans.length === 0
          ? <>Projects could not be loaded</>
          : loansQuery.isPending && loans.length === 0
            ? <>Loading projects</>
            : openCount === 0
              ? <>Nothing open today</>
              : <>{openCount} open today · From {marketplaceCurrencySymbol(minimumCurrency)} {formatMoneyMinor(minimumInvestmentMinor, minimumCurrency, 0)}</>}
        title="These companies want your investment"
      />

      <section aria-label="Investable balance" className="card marketplace-capacity">
        <div className="marketplace-capacity-figure">
          <div className="marketplace-capacity-label">Available to commit</div>
          <div className="marketplace-capacity-amount num">
            {capacitySummary ? formatMoneyMinor(capacitySummary.investable_minor, activeCapacityCurrency) : "-"}
            <span>{activeCapacityCurrency}</span>
          </div>
        </div>
        <div className="marketplace-capacity-note">
          {balancesQuery.isLoading && balanceSummaries.length === 0
            ? "Loading your eligible balance..."
            : capacitySummary
              ? "available to invest"
              : "No investable balance is currently available in this currency."}
        </div>
        <div className="marketplace-capacity-tools">
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
            <span className="marketplace-investing-rule-name">Investing rule</span>
            <span className="marketplace-investing-rule-state">{investingRuleActive ? "Active" : "Not active"}</span>
            <Icon className="marketplace-investing-rule-arrow" name="arrowR" size={15} />
          </button>
        </div>
      </section>

      <section className="marketplace-opportunities">
        <div className="card mk-toolbar">
          <div className="marketplace-section-head">
            <div>
              <div className="eyebrow">Primary market</div>
              <h2>Open investment opportunities</h2>
            </div>
          </div>

          <div className="mk-toolbar-body">
            <div className="fs-controls">
              <button
                aria-controls="marketplace-filter-panel"
                aria-expanded={panelOpen}
                className={`fs-pill${panelOpen || tokens.length > 0 ? " on" : ""}`}
                onClick={() => setPanelOpen((open) => !open)}
                type="button"
              >
                <Icon name="filter" size={14} />
                <span>Filter</span>
                <span aria-hidden="true" className="fs-caret">{panelOpen ? "▲" : "▼"}</span>
              </button>
              <SortControl activeKey={sortKey} dir={sortDir} onPick={pickSort} options={mkSortOptions} />
              {sortKey ? (
                <button className="fs-clear-link" onClick={() => { setSortKey(null); setSortDir("asc"); }} type="button">back to closing soonest</button>
              ) : null}
              <span className="fs-count"><strong>{filtered.length}</strong> of {openLoans.length} match</span>
              <span className="fs-controls-spacer" />
              {layout === "list" ? (
                <Segmented
                  options={[{ value: "focused", label: "Focused" }, { value: "detailed", label: "Detailed" }]}
                  value={viewMode}
                  onChange={setViewMode}
                />
              ) : null}
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
                  <span className="fs-slider-val">{filters.minRate === null ? "any rate" : `${formatPercent(rateValue, 1)}`}</span>
                </div>
                <div className="fs-hist">
                  {rateBins.map((bin, index) => (
                    <span
                      key={index}
                      style={{
                        height: bin.n > 0 ? `${Math.max(7, Math.round((bin.n / rateBinMax) * 100))}%` : "2px",
                        background: bin.lo >= rateValue - 0.001 && bin.n > 0 ? "#b5b5b5" : "#ededed"
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
                <div className="fs-range-ends"><span>{formatPercent(rateFloor, 1)}</span><span>{formatPercent(rateCeil, 1)}</span></div>
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
                        background: bin.term <= termValue && bin.n > 0 ? "#b5b5b5" : "#ededed"
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
                  {anyLabel(filters.orig, "any source")}
                  {filters.orig.length > 0 ? <button aria-label="Clear originator filter" className="fs-group-x" onClick={() => setFlt("orig", [])} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {chipButton(chip("orig", mkBanxumSource, "BANXUM", (loan) => !isOriginatorClaimLoan(loan)))}
                  {originators.map((originator) => chipButton(chip("orig", originator.id, originator.name, (loan) => loan.originator_id === originator.id)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Collateral
                  {anyLabel(filters.col, "with or without")}
                  {filters.col.length > 0 ? <button aria-label="Clear collateral filter" className="fs-group-x" onClick={() => setFlt("col", [])} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {chipButton(chip("col", mkAnyCollateral, "With collateral (any type)", (loan) => !mkIsUnsecured(loan)))}
                  {chipButton(chip("col", mkNoCollateral, "No collateral", (loan) => mkIsUnsecured(loan)))}
                </div>
                {collateralKinds.length > 0 ? (
                  <div className="fs-subgroup">
                    <span className="fs-subgroup-label">or only</span>
                    <span className="fs-subgroup-body">
                      <span className="fs-chips">
                        {collateralKinds.map((kind) => chipButton(chip("col", kind, humanizeToken(kind), (loan) => !mkIsUnsecured(loan) && loan.collateral_type === kind)))}
                      </span>
                    </span>
                  </div>
                ) : null}
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Currency
                  {anyLabel(filters.ccy, "any currency")}
                  {filters.ccy.length > 0 ? <button aria-label="Clear currency filter" className="fs-group-x" onClick={() => setFlt("ccy", [])} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {currencies.map((code) => chipButton(chip("ccy", code, code, (loan) => loan.currency === code)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Risk rating
                  {anyLabel(filters.rating, "any rating")}
                  {filters.rating.length > 0 ? <button aria-label="Clear rating filter" className="fs-group-x" onClick={() => setFlt("rating", [])} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {ratings.map((rating) => chipButton(chip("rating", rating, mkRatingLabel(rating), (loan) => loan.risk_rating === rating)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Purpose
                  {anyLabel(filters.purpose, "any purpose")}
                  {filters.purpose.length > 0 ? <button aria-label="Clear purpose filter" className="fs-group-x" onClick={() => setFlt("purpose", [])} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {purposes.map((purpose) => chipButton(chip("purpose", purpose, humanizeToken(purpose), (loan) => loan.purpose === purpose)))}
                </div>
              </div>
              <div className="fs-group">
                <div className="fs-group-cap">
                  Loan type
                  {anyLabel(filters.kind, "any loan type")}
                  {filters.kind.length > 0 ? <button aria-label="Clear loan type filter" className="fs-group-x" onClick={() => setFlt("kind", [])} type="button">×</button> : null}
                </div>
                <div className="fs-chips">
                  {chipButton(chip("kind", mkNewLending, "New lending", (loan) => !loan.is_refinancing))}
                  {chipButton(chip("kind", mkRefinancing, "Refinancing", (loan) => loan.is_refinancing))}
                </div>
              </div>
            </div>
            <p className="fs-panel-hint">Pick several options in one group to see loans that match any of them.</p>
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
        </div>

      {loansQuery.isError && loans.length === 0 ? (
        <DataErrorCard title="Could not load marketplace" onRetry={() => void loansQuery.refetch()}>
          The primary-market loan list is unavailable. Retry once the API connection is restored.
        </DataErrorCard>
      ) : loansQuery.isLoading && loans.length === 0 ? (
        <LoadingCard title="Loading marketplace">Fetching primary-market loans.</LoadingCard>
      ) : filtered.length === 0 ? (
        <div className="card fs-empty">
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
      ) : layout === "cards" ? (
        <MarketplaceOpportunityCards
          asOf={balancesQuery.data?.as_of}
          loans={sortedLoans}
          onOpen={(loan) => setSheetLoanId(loan.loan_id)}
        />
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
        Funding-round progress reflects validated balance reservations. Legacy immediate-assignment
        claim progress reflects principal already sold; only those legacy prices can change before purchase.
      </p>
      </section>

      <section aria-label="How primary-market orders work" className="card marketplace-process">
        <div>
          <span className="marketplace-process-number">01</span>
          <strong>Choose each opportunity</strong>
          <p>Open it to review the disclosed counterparty, yield, collateral, cash-flow schedule, documents and risks.</p>
        </div>
        <div>
          <span className="marketplace-process-number">02</span>
          <strong>Confirm the applicable investment flow</strong>
          <p>Current opportunities reserve eligible balance during funding. A Loan Originator subscription buys principal at par and activates automatically when funding closes.</p>
        </div>
        <div>
          <span className="marketplace-process-number">03</span>
          <strong>Your portfolio records the legal claim</strong>
          <p>Holdings start at funding close. For Loan Originator loans, the first post-funding installment belongs entirely to the LO; investors participate in subsequent installments.</p>
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
            <div><span>3</span><p><strong>Allocated money is reserved until funding closes.</strong> Direct and Loan Originator orders become holdings at funding close. The LO's boundary installment is excluded from investor payments.</p></div>
            <div><span>4</span><p><strong>If the funding round is cancelled, the reservation is released.</strong> The amount returns to your platform balance and keeps its original regulatory ageing deadlines. An operational close failure keeps funds reserved while BANXUM resolves it.</p></div>
          </div>
          <Banner tone="neutral" title="Minimum order">
            The launch minimum is CHF/EUR 1,000 per order. The backend confirms eligibility, capacity, terms acceptance and the fresh email code before allocation.
          </Banner>
        </Modal>
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

type InvestorScheduleRow = {
  installment: number;
  dueDate: string;
  principalMinor: number;
  interestMinor: number;
  penaltyMinor: number;
  totalMinor: number;
  owedAfterMinor: number;
};

type InvestorScheduleProjection = {
  basis: "direct" | "subscription" | "quoted" | "unavailable";
  rows: InvestorScheduleRow[];
  principalMinor: number;
  interestMinor: number;
  penaltyMinor: number;
  totalMinor: number;
};

// Mirrors the backend entitlement math: a fixed proportional share of each
// contracted installment. Direct loans allocate principal and interest by the
// investor's share of the financeable principal; v2 originator subscriptions
// entitle only rows after the boundary installment, with the declared interest
// and penalty participation applied on top of the proportional share.
function investorScheduleProjection(
  detail: MarketplaceLoanDetail,
  amountMinor: number
): InvestorScheduleProjection {
  const empty = (basis: InvestorScheduleProjection["basis"]): InvestorScheduleProjection => ({
    basis,
    rows: [],
    principalMinor: 0,
    interestMinor: 0,
    penaltyMinor: 0,
    totalMinor: 0
  });
  if (amountMinor <= 0) return empty("unavailable");
  if (usesImmediateClaimAssignment(detail)) return empty("quoted");
  const subscription = usesOriginatorSubscription(detail);
  const boundaryDate = detail.entitlement_start_date ?? null;
  const source: { installment: number; dueDate: string; opening: number; principal: number; interest: number; penalty: number }[] = subscription
    ? (detail.originator_schedule ?? [])
        .filter((row) => !boundaryDate || row.due_date > boundaryDate)
        .map((row) => ({
          installment: row.installment_number,
          dueDate: row.due_date,
          opening: Math.max(1, row.opening_principal_minor),
          principal: row.principal_minor,
          interest: row.interest_minor,
          penalty: row.penalty_minor
        }))
    : (detail.loan_schedule ?? []).filter((row) => row.row_type !== "repayment_event").map((row) => ({
        installment: row.installment_number,
        dueDate: row.due_date,
        opening: Math.max(1, detail.principal_minor),
        principal: row.principal_minor,
        interest: row.interest_minor,
        penalty: 0
      }));
  if (source.length === 0) return empty("unavailable");
  const interestParticipation = subscription ? (detail.investor_interest_participation_bps ?? 0) : 10_000;
  const penaltyParticipation = subscription ? (detail.investor_penalty_participation_bps ?? 0) : 10_000;
  const rows: InvestorScheduleRow[] = [];
  let remaining = amountMinor;
  let totalInterest = 0;
  let totalPenalty = 0;
  source.forEach((row, index) => {
    // For direct loans the share of the financeable principal is constant; for
    // subscriptions the share of each row's opening principal stays constant as
    // both the loan and the holding amortise proportionally.
    const sharePrincipal = BigInt(subscription ? remaining : amountMinor);
    const denominator = BigInt(row.opening) * 10_000n;
    const proportional = (component: number, participation = 10_000) => {
      const numerator = BigInt(component) * sharePrincipal * BigInt(participation);
      return Number((numerator * 2n + denominator) / (denominator * 2n));
    };
    const principalPart = index === source.length - 1
      ? remaining
      : Math.min(remaining, proportional(row.principal));
    const interestPart = proportional(row.interest, interestParticipation);
    const penaltyPart = proportional(row.penalty, penaltyParticipation);
    remaining -= principalPart;
    totalInterest += interestPart;
    totalPenalty += penaltyPart;
    rows.push({
      installment: row.installment,
      dueDate: row.dueDate,
      principalMinor: principalPart,
      interestMinor: interestPart,
      penaltyMinor: penaltyPart,
      totalMinor: principalPart + interestPart + penaltyPart,
      owedAfterMinor: Math.max(0, remaining)
    });
  });
  return {
    basis: subscription ? "subscription" : "direct",
    rows,
    principalMinor: amountMinor,
    interestMinor: totalInterest,
    penaltyMinor: totalPenalty,
    totalMinor: amountMinor + totalInterest + totalPenalty
  };
}

function marketplaceProjection(
  detail: MarketplaceLoanDetail | null,
  amountMinor: number,
  yieldBps: number,
  termMonths: number,
  repaymentType: string
) {
  if (detail) {
    const projection = investorScheduleProjection(detail, amountMinor);
    if (projection.rows.length > 0) {
      return {
        totalMinor: projection.totalMinor,
        interestMinor: projection.interestMinor,
        monthlyMinor: repaymentType === "equal_installments" ? projection.rows[0].totalMinor : null
      };
    }
    if (projection.basis === "subscription") {
      return { totalMinor: amountMinor, interestMinor: 0, monthlyMinor: null };
    }
  }
  return osProjection(amountMinor, yieldBps, termMonths, repaymentType);
}

/** An amount as a plain input value ("5000.00"), without thousands separators. */
// An amount written back into an amount field: no grouping, the investor's decimal sign (U33-DEC-32).
function plainMoneyInput(amountMinor: number, currency: string) {
  return formatAmountInput(amountMinor, currency);
}

/** How the money comes back, for the sheet's projection line. */
function repaymentPatternText(repaymentType: string) {
  if (repaymentType === "bullet_periodic_interest" || repaymentType === "interest_only_then_bullet") {
    return ", interest monthly and capital at maturity";
  }
  if (repaymentType === "interest_only_then_amortizing") {
    return ", interest only at first, then capital and interest every month";
  }
  if (repaymentType === "amortizing_principal_interest" || repaymentType === "equal_installments") {
    return ", capital and interest every month";
  }
  return ", as the loan schedule says";
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
  const [calcOpen, setCalcOpen] = useState(false);
  const [calcText, setCalcText] = useState("");
  const [calcError, setCalcError] = useState("");
  const [calcResult, setCalcResult] = useState<InvestorScheduleProjection | null>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const sheetDialog = useDialog({ dialogRef: sheetRef, onDismiss: onClose });

  const detail = detailQuery.data ?? null;
  const loan = detail ?? preview;
  const ccy = loan.currency;
  const claim = isOriginatorClaimLoan(loan);
  const subscriptionClaim = usesOriginatorSubscription(loan);
  const immediateClaim = usesImmediateClaimAssignment(loan);
  const yieldBps = marketplaceYieldBps(loan);
  const openLoan = isOpenMarketplaceLoan(loan);
  const collateralLoan = { ...loan, collateral_value_minor: detail?.collateral_value_minor };
  const ltvBps = loanLtvBps(collateralLoan);
  const collateralValueMinor = detail?.collateral_value_minor ?? 0;
  const hasAsset = !isUnsecuredLoan(collateralLoan) && ltvBps !== null;
  const penaltyBps = detail?.default_penalty_interest_bps ?? 0;
  const repaymentType = detail?.repayment_type ?? "equal_installments";
  const minimumBps = loan.minimum_subscription_bps ?? 5_000;
  const pct = loan.principal_minor > 0 ? Math.round((loan.committed_principal_minor / loan.principal_minor) * 100) : 0;
  const availableMinor = marketplaceAvailableMinor(loan);
  const daysToClose = loan.funding_deadline
    ? fundingDaysRemaining(loan.funding_deadline, balances?.as_of)
    : immediateClaim && typeof loan.remaining_term_days === "number"
      ? Math.max(0, loan.remaining_term_days - 30)
      : null;
  const investableMinor = sumLotAvailableMinor(currentInvestableLotsForLoanCurrency(balances?.lots, loan));
  const commitableMinor = Math.min(investableMinor, availableMinor);
  const funds = { balanceMinor: currencyBalanceMinor(balances?.lots, ccy), eligibleMinor: investableMinor };
  const fundsBlock = noEligibleFundsReason(ccy, funds);
  const limitMessage = (value: number) =>
    investAmountLimitMessage({ amountMinor: value, capacityMinor: availableMinor, currency: ccy, funds, money: (minor) => pfMoneyLabel(ccy, minor) });
  const minInvestMinor = loan.minimum_investment_minor;
  const parsed = amountText === null ? null : parseMoneyInputToMinorUnits(amountText, ccy);
  const amountMinor = amountText === null ? Math.max(Math.min(commitableMinor, availableMinor), 0) : (parsed?.amountMinor ?? 0);
  // Pre-fill a plain number ("5000.00"): an edited "5’000’000.00" was hard to correct.
  const amountValue = amountText ?? plainMoneyInput(amountMinor, ccy);
  const overCash = amountMinor > commitableMinor;
  const underMin = amountMinor < minInvestMinor;
  // Project what can really be lent here: the balance, capped by what the loan still
  // takes (audit A-39 / JOURNEY-05), not the whole wallet.
  const walletBase = commitableMinor >= minInvestMinor ? commitableMinor : minInvestMinor;
  const projection = marketplaceProjection(detail, walletBase, yieldBps, loan.term_months, repaymentType);
  const commitProjection = marketplaceProjection(detail, amountMinor, yieldBps, loan.term_months, repaymentType);
  const bookMinor = (portfolio?.holdings ?? [])
    .filter((holding) => holding.currency === ccy)
    .reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const originLine = claim
    ? `originated by ${loan.originator_name ?? "a loan originator"}${subscriptionClaim && loan.funding_deadline ? ` · funding closes ${formatDate(loan.funding_deadline)}` : detail?.loan_start_date ? ` · ${new Date(`${detail.loan_start_date}T00:00:00`).toLocaleDateString("en-GB", { month: "long", year: "numeric" })}` : ""}${(loan.skin_in_the_game_bps ?? 0) > 0 ? ` · kept ${formatRateBps(loan.skin_in_the_game_bps ?? 0)}` : ""}`
    : "originated by Banxum · written when this opportunity funds";
  // The claim is against the borrower, never the loan title. Direct loans name the
  // borrower in the disclosure; the preview may not have it yet.
  const borrowerLabel = loan.borrower_display_name
    || (detail ? borrowerDisclosureForLoan(detail).legal_name : undefined)
    || "the borrower";
  const chain = claim
    ? `${subscriptionClaim ? "After activation, your" : "Your"} claim is against ${borrowerLabel}. Banxum collects it and holds the charge — ${loan.originator_name ?? "the originator"} is not in that chain${(loan.skin_in_the_game_bps ?? 0) > 0 ? `, and it keeps ${formatRateBps(loan.skin_in_the_game_bps ?? 0)} of the outstanding principal, so it loses alongside you` : ""}.`
    : `We underwrote this loan ourselves and we collect it. Your claim is against ${borrowerLabel}, and Banxum holds the charge over the collateral on your behalf.`;
  const metMinimum = !subscriptionClaim && loan.principal_minor > 0
    && loan.committed_principal_minor * 10_000 >= loan.principal_minor * minimumBps;
  const minPct = Math.round(minimumBps / 100);
  const goDetail = () => {
    onClose();
    goTo(setRoute, "loan", { loanId: loan.loan_id });
  };
  const goSchedule = () => {
    onClose();
    goTo(setRoute, "loanSchedule", { loanId: loan.loan_id });
  };
  const reviewOrder = () => {
    if (!detail || underMin || amountMinor <= 0 || overCash) return;
    onInvest(detail, plainMoneyInput(amountMinor, ccy));
  };
  const presets: { label: string; minor: number }[] = [
    { label: "Minimum", minor: minInvestMinor },
    { label: "Half", minor: Math.max(minInvestMinor, Math.floor(commitableMinor / 2)) },
    { label: "Maximum", minor: commitableMinor }
  ];

  return (
    <div className="ls-scrim os-scrim">
      <button aria-label="Dismiss" className="ls-overlay-btn" onClick={sheetDialog.dismissFromBackdrop} tabIndex={-1} type="button" />
      <div aria-label={loan.title} aria-modal="true" className="ls-modal os-sheet" ref={sheetRef} role="dialog">
        <div className="ls-scroll" style={{ opacity: stepOpen ? 0.5 : 1 }}>
          <div className="os-head">
            <div className="os-head-main">
              <div className="os-name">{loan.title}</div>
              <div className="os-origin">{originLine}</div>
            </div>
            <div className="os-stats">
              <div className="os-stat"><div className="os-stat-val">{formatRateBps(yieldBps)}</div><div className="os-stat-cap">{subscriptionClaim ? "nominal investor rate" : "a year"}</div></div>
              <div className="os-stat"><div className="os-stat-val">{loan.term_months} mo</div><div className="os-stat-cap">{subscriptionClaim ? "remaining schedule" : pfPaysLabel(repaymentType)}</div></div>
              <div className="os-stat"><div className="os-stat-val" style={hasAsset ? undefined : { color: "#b3261e" }}>{hasAsset ? formatRateBps(ltvBps ?? 0) : "none"}</div><div className="os-stat-cap">{hasAsset ? "of valuation" : "no asset"}</div></div>
              {daysToClose !== null ? (
                <div className="os-stat"><div className="os-stat-val" style={daysToClose <= 7 ? { color: "#b3261e" } : undefined}>{daysToClose} {daysToClose === 1 ? "day" : "days"}</div><div className="os-stat-cap">to close</div></div>
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
                      <div><div className="os-trio-val">{formatRateBps(ltvBps ?? 0)}</div><div className="os-stat-cap">LTV</div></div>
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
              <div className="os-card-head"><span className="os-cap">What your {pfMoneyLabel(ccy, walletBase)} does here</span><span className="os-over">over {pluralize(loan.term_months, "month")}</span></div>
              <div className="os-wallet">
                <div className="os-wallet-col">
                  <div className="os-wallet-cap">Illustrative — if paid as scheduled</div>
                  <div className="os-wallet-val">{pfMoneyLabel(ccy, projection.totalMinor)}</div>
                  <div className="os-wallet-sub">{pfMoneyLabel(ccy, walletBase)} your capital returning + {pfMoneyLabel(ccy, projection.interestMinor)} interest{subscriptionClaim ? ", based on the imported remaining loan schedule and your declared component participation" : projection.monthlyMinor ? `, arriving as ${pfMoneyLabel(ccy, projection.monthlyMinor)} a month — not in one payment` : repaymentPatternText(repaymentType)}</div>
                </div>
                <div className="os-wallet-col last">
                  <div className="os-wallet-cap red">If it stops paying</div>
                  <div className="os-wallet-val">{penaltyBps > 0 ? `${formatRateBps(penaltyBps)} a year` : "—"}</div>
                  <div className="os-wallet-sub">{penaltyBps > 0 ? "penalty interest accrues to you on what is outstanding" : "no penalty interest is configured for this loan"}</div>
                </div>
              </div>
            </div>

            {subscriptionClaim ? (
              <div className="os-card">
                <div className="os-cap">Loan Originator subscription terms</div>
                <div className="os-text">
                  Every {ccy} 1.00 reserved buys {ccy} 1.00 of post-boundary principal at funding close.
                  No investor interest accrues during funding. The first installment after the funding
                  deadline belongs entirely to the Loan Originator. Your holding activates automatically
                  at funding close; investor entitlements cover only installments after that boundary date.
                </div>
                <div className="os-kv"><span className="os-kv-lbl">Underlying borrower coupon</span><span className="os-kv-dots" /><span className="os-kv-val">{formatRateBps(loan.underlying_interest_rate_bps)}</span></div>
                <div className="os-kv"><span className="os-kv-lbl">Your share of attributable interest</span><span className="os-kv-dots" /><span className="os-kv-val">{formatRateBps(loan.investor_interest_participation_bps ?? 0)}</span></div>
                <div className="os-kv"><span className="os-kv-lbl">Your share of attributable penalties</span><span className="os-kv-dots" /><span className="os-kv-val">{formatRateBps(loan.investor_penalty_participation_bps ?? 0)}</span></div>
                {loan.entitlement_start_date ? <div className="os-kv"><span className="os-kv-lbl">Boundary installment due</span><span className="os-kv-dots" /><span className="os-kv-val">{formatDate(loan.entitlement_start_date)}</span></div> : null}
              </div>
            ) : null}

            {!claim ? (
              <div className="os-card">
                <div className="os-card-head"><span className="os-cap">Subscription window</span><span className="os-over">{loan.funding_deadline ? `closes ${formatDate(loan.funding_deadline)}` : ""}</span></div>
                <div className="os-window">
                  <div className="os-window-fill" style={{ width: `${Math.min(100, pct)}%`, background: metMinimum ? "#1e7a46" : "#0a0a0a" }} />
                  <div className="os-window-min" style={{ left: `${Math.min(100, minPct)}%` }} />
                  <div className="os-window-knob" style={{ left: `${Math.min(100, pct)}%`, borderColor: metMinimum ? "#1e7a46" : "#0a0a0a" }} />
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
            ) : subscriptionClaim ? (
              <div className="os-card">
                <div className="os-card-head"><span className="os-cap">Funding round</span><span className="os-over">{loan.funding_deadline ? `closes ${formatDate(loan.funding_deadline)}` : ""}</span></div>
                <div className="os-window plain"><div className="os-window-fill" style={{ width: `${Math.min(100, pct)}%`, background: "#1e7a46" }} /></div>
                <div className="os-window-line"><span className="os-window-sub"><strong>{pct}%</strong> reserved · {pfMoneyLabel(ccy, availableMinor)} available at par</span></div>
                <div className="os-strip met">
                  <span className="os-strip-lead">Reserved, then activated</span>
                  <span className="os-strip-text">Your money becomes an active investment automatically when this round closes. The boundary installment belongs entirely to the LO; your schedule starts afterward. If the round is cancelled before close, your reserved balance returns with its original ageing dates.</span>
                </div>
              </div>
            ) : (
              <div className="os-card">
                <div className="os-cap os-cap-gap">Availability</div>
                <div className="os-window plain"><div className="os-window-fill" style={{ width: `${Math.min(100, pct)}%`, background: "#0a0a0a" }} /></div>
                <div className="os-window-line"><span className="os-window-sub"><strong>{pct}%</strong> taken by other investors · {pfMoneyLabel(ccy, availableMinor)} available</span></div>
              </div>
            )}

            <div className="os-card os-calc">
              <button aria-expanded={calcOpen} className="os-calc-toggle" onClick={() => setCalcOpen((open) => !open)} type="button">
                <span className="os-cap">Investment schedule calculator</span>
                <span className="os-calc-hint">how a given amount comes back to you, installment by installment</span>
                <span className="ls-spacer" />
                <span className="os-over">{calcOpen ? "Hide" : "Show"} <span aria-hidden="true">{calcOpen ? "▴" : "▾"}</span></span>
              </button>
              {calcOpen ? (
                <div className="os-calc-body">
                  {detail && usesImmediateClaimAssignment(detail) ? (
                    <div className="os-note">This claim is priced by an executable quote at its target yield, so the exact schedule is fixed only when you review a purchase — the quote shows every installment you would receive.</div>
                  ) : (
                    <>
                      <form
                        className="os-calc-row"
                        onSubmit={(event) => {
                          event.preventDefault();
                          setCalcError("");
                          setCalcResult(null);
                          if (!detail) {
                            setCalcError("The loan schedule is still loading.");
                            return;
                          }
                          const parsed = parseMoneyInputToMinorUnits(calcText, ccy);
                          const value = parsed.amountMinor;
                          if (parsed.error || value <= 0) {
                            setCalcError(parsed.error ?? "Enter a valid amount.");
                            return;
                          }
                          if (value < minInvestMinor) {
                            setCalcError(`The minimum in any one loan is ${pfMoneyLabel(ccy, minInvestMinor)}.`);
                            return;
                          }
                          const overLimit = limitMessage(value);
                          if (overLimit) {
                            setCalcError(overLimit);
                            return;
                          }
                          const projection = investorScheduleProjection(detail, value);
                          if (projection.rows.length === 0) {
                            setCalcError("No contracted schedule is available for this loan yet.");
                            return;
                          }
                          setCalcResult(projection);
                        }}
                      >
                        <div className="os-amt-box os-amt-box-sm">
                          <span className="os-amt-ccy">{ccy}</span>
                          <input aria-label="Amount to calculate" className="os-amt-input os-amt-input-sm" inputMode="decimal" onChange={(event) => setCalcText(event.target.value)} placeholder={formatMoneyMinor(minInvestMinor, ccy).replace(/[^\d.]/g, "")} type="text" value={calcText} />
                        </div>
                        <button className="si-pill-dark os-calc-btn" type="submit">Calculate</button>
                        <span className="os-over os-calc-limits">minimum {pfMoneyLabel(ccy, minInvestMinor)} · up to {pfMoneyLabel(ccy, Math.min(availableMinor, investableMinor))} today</span>
                      </form>
                      {calcError ? <div className="os-step-note os-calc-error" role="alert">{calcError}</div> : null}
                      {calcResult ? (
                        <div className={`os-calc-result ${calcResult.penaltyMinor > 0 ? "has-penalty" : ""}`}>
                          <div className="ls-th">
                            <span className="ls-td-due">Due</span>
                            <span className="ls-td-cap">Capital</span>
                            <span className="ls-td-int">Interest</span>
                            {calcResult.penaltyMinor > 0 ? <span className="ls-td-cap">Penalty</span> : null}
                            <span className="ls-td-amt">Payment</span>
                            <span className="ls-td-bal">Owed after</span>
                          </div>
                          {calcResult.rows.map((row) => (
                            <div className="ls-tr" key={row.installment}>
                              <span className="ls-td-due">{pfShortDate(row.dueDate)}</span>
                              <span className="ls-td-cap">{formatMoneyMinor(row.principalMinor, ccy)}</span>
                              <span className="ls-td-int">{formatMoneyMinor(row.interestMinor, ccy)}</span>
                              {calcResult.penaltyMinor > 0 ? <span className="ls-td-cap">{formatMoneyMinor(row.penaltyMinor, ccy)}</span> : null}
                              <span className="ls-td-amt">{formatMoneyMinor(row.totalMinor, ccy)}</span>
                              <span className="ls-td-bal">{formatMoneyMinor(row.owedAfterMinor, ccy)}</span>
                            </div>
                          ))}
                          <div className="ls-tr os-calc-total">
                            <span className="ls-td-due">{calcResult.rows.length} payments</span>
                            <span className="ls-td-cap">{formatMoneyMinor(calcResult.principalMinor, ccy)}</span>
                            <span className="ls-td-int">{formatMoneyMinor(calcResult.interestMinor, ccy)}</span>
                            {calcResult.penaltyMinor > 0 ? <span className="ls-td-cap">{formatMoneyMinor(calcResult.penaltyMinor, ccy)}</span> : null}
                            <span className="ls-td-amt">{formatMoneyMinor(calcResult.totalMinor, ccy)}</span>
                            <span className="ls-td-bal">—</span>
                          </div>
                          <div className="ls-sched-note">
                            {calcResult.basis === "subscription"
                              ? `Only installments after the boundary installment${detail?.entitlement_start_date ? ` (${formatDate(detail.entitlement_start_date)})` : ""} count. Capital is your proportional share of each installment; interest counts ${formatRateBps(detail?.investor_interest_participation_bps ?? 0)} and penalties ${formatRateBps(detail?.investor_penalty_participation_bps ?? 0)} of the amount attributable to your share. No interest accrues during funding, and the boundary installment belongs to the Loan Originator.`
                              : "Indicative share of the current schedule, assuming the campaign funds in full. At a partial close the schedule and your share are recalculated. Actual distributions may differ by rounding; repayments are not guaranteed."}
                          </div>
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
              ) : null}
            </div>

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
              {openLoan && fundsBlock ? (
                <div className="os-bar-reason">
                  <span>{fundsBlock.title}</span>
                  <Tooltip content={fundsBlock.detail} label={fundsBlock.detail}>
                    <span aria-hidden="true" className="os-bar-reason-i">i</span>
                  </Tooltip>
                </div>
              ) : null}
            </div>
            <div className="os-bar-col split">
              <div className="os-wallet-cap green">You would earn</div>
              <div className="os-bar-row"><span className="os-bar-val green">≈ {pfMoneyLabel(ccy, marketplaceProjection(detail, commitableMinor, yieldBps, loan.term_months, repaymentType).interestMinor)}</span><span className="os-bar-sub">interest, over the remaining schedule</span></div>
            </div>
            <div className="os-bar-actions">
              {detail ? (
                <div className="os-bar-links">
                  <button className="os-meet-btn" onClick={goDetail} type="button">{claim ? "Meet the originator" : "Meet the borrower"} →</button>
                  <button className="os-meet-btn" onClick={goSchedule} type="button">Loan schedule →</button>
                </div>
              ) : null}
              <button className="ls-sell-btn" disabled={!openLoan || !detail || commitableMinor <= 0} onClick={() => setStepOpen(true)} title={!openLoan ? "This opportunity is not open to new investment." : commitableMinor <= 0 && fundsBlock ? `${fundsBlock.title} ${fundsBlock.detail}` : undefined} type="button">Invest now</button>
            </div>
          </div>
        ) : (
          <div className="os-step">
            <div className="os-step-head"><span className="os-cap">How much do you want to lend</span><span className="ls-spacer" /><span className="os-over">minimum {pfMoneyLabel(ccy, minInvestMinor)} · {pfMoneyLabel(ccy, availableMinor)} available in this opportunity</span></div>
            <div className="os-step-grid">
              <div className="os-step-amount">
                <div className="os-amt-box">
                  <span className="os-amt-ccy">{ccy}</span>
                  <input aria-label="Amount to invest" className="os-amt-input" inputMode="decimal" onChange={(event) => setAmountText(event.target.value)} type="text" value={amountValue} />
                </div>
                <div className="os-chips">
                  {presets.map((preset) => (
                    <button className="os-chip" key={preset.label} onClick={() => setAmountText(plainMoneyInput(preset.minor, ccy))} type="button">{preset.label}</button>
                  ))}
                </div>
                {parsed?.error ? <div className="os-step-note" role="alert">{parsed.error}</div> : null}
                {overCash ? <div className="os-step-note">{limitMessage(amountMinor)}</div> : null}
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
                  {availableMinor > 0 ? `${formatPercent(((amountMinor / availableMinor) * 100), 1)} of what is available here` : ""}
                  <br />
                  {bookMinor > 0 ? `${formatPercent(((amountMinor / (bookMinor + amountMinor)) * 100), 1)} of everything you have lent` : "your first loan in this currency"}
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

// What the listing says about when an opportunity closes (or matures), shared by
// the List rows and the Cards so both layouts read the same.
function marketplaceClosingInfo(loan: MarketplaceLoanPreview, asOf?: string) {
  const originatorClaim = isOriginatorClaimLoan(loan);
  const subscriptionClaim = usesOriginatorSubscription(loan);
  const label = subscriptionClaim || !originatorClaim ? "Closes in" : "Maturity";
  const value = subscriptionClaim
    ? loan.funding_deadline
      ? fundingDeadlineLabel(loan.funding_deadline, asOf)
      : "See details"
    : originatorClaim
      ? loan.remaining_term_days === null
        ? "See details"
        : `${loan.remaining_term_days} days`
      : loan.funding_deadline
        ? fundingDeadlineLabel(loan.funding_deadline, asOf)
        : "-";
  const note = subscriptionClaim
    ? loan.funding_deadline
      ? formatDate(loan.funding_deadline)
      : "Funding deadline unavailable"
    : originatorClaim
      ? loan.maturity_date
        ? `Matures ${formatDate(loan.maturity_date)}`
        : "Open while performing"
      : loan.funding_deadline
        ? formatDate(loan.funding_deadline)
        : "No deadline";
  return { label, value, note };
}

function marketplaceFundedWord(loan: MarketplaceLoanPreview) {
  return usesOriginatorSubscription(loan) ? "reserved" : isOriginatorClaimLoan(loan) ? "claim sold" : "funded";
}

function MarketplaceOpportunityCards({
  loans,
  onOpen,
  asOf
}: {
  loans: MarketplaceLoanPreview[];
  onOpen: (loan: MarketplaceLoanPreview) => void;
  asOf?: string;
}) {
  return (
    <div className="mk-cards">
      {loans.map((loan) => {
        const fundedPercent = fundingPercent(loan);
        const originatorClaim = isOriginatorClaimLoan(loan);
        const availableMinor = marketplaceAvailableMinor(loan);
        const closing = marketplaceClosingInfo(loan, asOf);
        const principalDecimals = loan.principal_minor % 100 === 0 ? 0 : 2;
        return (
          <article className="card mk-card" key={loan.loan_id}>
            <div className="mk-card-head">
              <span aria-hidden="true" className="mk-card-tile">
                <Icon name={originatorClaim ? "doc" : "briefcase"} size={20} />
              </span>
              <div className="mk-card-info">
                <h3 className="mk-card-title">
                  <button onClick={() => onOpen(loan)} type="button">{loan.title}</button>
                </h3>
                <div className="mk-card-sub">
                  {originatorClaim && loan.originator_name ? `${loan.originator_name} · ${humanizeToken(loan.purpose)}` : humanizeToken(loan.purpose)}
                </div>
              </div>
              <span className="mk-card-copy">
                <CopyIdButton ariaLabel="Copy loan ID" iconOnly id={loan.loan_id} label="Copy loan ID" />
              </span>
            </div>
            <div className="mk-card-tags">
              {isOpenMarketplaceLoan(loan) ? <Chip status="open" /> : <Chip status={loan.status} />}
              {loan.is_refinancing ? <RefinancedTag /> : null}
              <span className="tag">Risk {loan.risk_rating}</span>
            </div>
            <dl className="mk-card-figures">
              <div><dt>Interest p.a.</dt><dd className="num">{formatRateBps(marketplaceYieldBps(loan))}</dd></div>
              <div><dt>Term</dt><dd className="num">{loan.term_months} mo</dd></div>
              <div>
                <dt>Amount</dt>
                <dd className="num"><span className="mk-card-ccy">{loan.currency}</span> {formatMoneyMinor(loan.principal_minor, loan.currency, principalDecimals)}</dd>
              </div>
            </dl>
            <div className="mk-card-progress">
              <div className="mk-card-row">
                <span><strong className="num">{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)}</strong> {marketplaceFundedWord(loan)}</span>
                <strong className="num">{fundedPercent}%</strong>
              </div>
              <Progress percent={fundedPercent} />
              <div className="mk-card-row">
                <span>Available to invest <strong className="num">{loan.currency} {formatMoneyMinor(availableMinor, loan.currency)}</strong></span>
                <span className="num">Min. {loan.currency} {formatMoneyMinor(loan.minimum_investment_minor, loan.currency)}</span>
              </div>
            </div>
            <div className="mk-card-foot">
              <span className="mk-card-when">
                <Icon name="clock" size={15} />
                <span>
                  {closing.label === "Closes in" && closing.value === "Today" ? (
                    <strong>Closes today</strong>
                  ) : (
                    <>
                      <span className="mk-card-when-label">{closing.label}</span>{" "}
                      <strong>{closing.value}</strong>
                    </>
                  )}{" "}
                  <span className="mk-card-when-note">· {closing.note}</span>
                </span>
              </span>
              <button aria-label={`Invest in ${loan.title}`} className="btn btn-sm btn-primary mk-card-go" onClick={() => onOpen(loan)} type="button">Invest</button>
            </div>
          </article>
        );
      })}
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
        <FsTh activeKey={sortKey} dir={sortDir} label="Rating" onPick={onPickSort} sortKey="rating" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Yield" onPick={onPickSort} sortKey="rate" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Term" onPick={onPickSort} sortKey="term" />
        <FsTh activeKey={sortKey} dir={sortDir} label="LTV" onPick={onPickSort} sortKey="margin" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Available to invest" onPick={onPickSort} sortKey="available" />
        <FsTh activeKey={sortKey} dir={sortDir} label="Availability" onPick={onPickSort} sortKey="closing" />
      </div>
      {loans.map((loan) => {
        const fundedPercent = fundingPercent(loan);
        const originatorClaim = isOriginatorClaimLoan(loan);
        const subscriptionClaim = usesOriginatorSubscription(loan);
        const availableMinor = marketplaceAvailableMinor(loan);
        const closing = marketplaceClosingInfo(loan, asOf);
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
                <strong>
                  {loan.title}
                  <span className="marketplace-copy-id" onClick={(event) => event.stopPropagation()}><CopyIdButton ariaLabel="Copy loan ID" iconOnly id={loan.loan_id} label="Copy loan ID" /></span>
                </strong>
                <span>
                  {originatorClaim && loan.originator_name
                    ? `${loan.originator_name} · ${humanizeToken(loan.purpose)}`
                    : humanizeToken(loan.purpose)}
                  {loan.is_refinancing ? <> <RefinancedTag /></> : null}
                </span>
              </div>
              <div className="marketplace-opportunity-rating">
                <span className="marketplace-mobile-label">Rating</span>
                <strong>{loan.risk_rating}</strong>
              </div>
              <div className="marketplace-opportunity-rate">
                <span className="marketplace-mobile-label">Yield</span>
                <strong>{formatRateBps(marketplaceYieldBps(loan))}</strong>
                <small>per annum</small>
              </div>
              <div className="marketplace-opportunity-term">
                <span className="marketplace-mobile-label">Term</span>
                <strong>{loan.term_months}</strong>
                <small>{loan.term_months === 1 ? "month" : "months"}</small>
              </div>
              <div className="marketplace-opportunity-collateral">
                <span className="marketplace-mobile-label">LTV</span>
                <strong>{loanLtvBps(loan) === null ? "Not disclosed" : formatRateBps(loanLtvBps(loan) ?? 0)}</strong>
                <small>{loanLtvBps(loan) === null ? "No LTV" : "of valuation"}</small>
              </div>
              <div className="marketplace-opportunity-funding">
                <span className="marketplace-mobile-label">Available to invest</span>
                <div className="marketplace-funding-value">
                  <strong>{loan.currency} {formatMoneyMinor(availableMinor, loan.currency)}</strong>
                  <span>{fundedPercent}% {subscriptionClaim ? "reserved" : originatorClaim ? "claim sold" : "funded"}</span>
                </div>
                <Progress percent={fundedPercent} />
                <small>{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)} of {formatMoneyMinor(loan.principal_minor, loan.currency)} {subscriptionClaim ? "reserved" : "principal"}</small>
              </div>
              <div className="marketplace-opportunity-deadline">
                <span className="marketplace-mobile-label">{closing.label}</span>
                <strong>{closing.value}</strong>
                <small>{closing.note}</small>
                <Icon className="marketplace-row-arrow" name="chevR" size={16} />
              </div>
            </div>
            {viewMode === "detailed" ? (
              <div className="marketplace-opportunity-details">
                <div><span>{originatorClaim ? "Post-boundary principal" : "Loan amount"}</span><strong>{loan.currency} {formatMoneyMinor(loan.principal_minor, loan.currency)}</strong></div>
                <div><span>{subscriptionClaim ? "Principal reserved" : originatorClaim ? "Claim principal sold" : "Allocated"}</span><strong>{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)}</strong></div>
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

type LoanPageKind = "story" | "schedule";

function loanCounterpartyLabel(loan: MarketplaceLoanDetail) {
  return isOriginatorClaimLoan(loan) ? "Meet the originator" : "Meet the borrower";
}

function loanStorySubjectName(loan: MarketplaceLoanDetail) {
  if (isOriginatorClaimLoan(loan)) return loan.originator_name || "the loan originator";
  return borrowerDisclosureForLoan(loan).legal_name || loan.title;
}

function loanClosesRow(loan: MarketplaceLoanDetail): [string, string] {
  const subscriptionClaim = usesOriginatorSubscription(loan);
  const originatorClaim = isOriginatorClaimLoan(loan);
  if (subscriptionClaim || !originatorClaim) {
    // A loan that no longer takes orders says its funding closed, not that it "closes".
    return [isOpenMarketplaceLoan(loan) ? "Closes" : "Funding closed", loan.funding_deadline ? formatDate(loan.funding_deadline) : "Not available"];
  }
  return ["Maturity", loan.maturity_date ? formatDate(loan.maturity_date) : "Not available"];
}

/** Whether the current viewer can start an order on this loan from the loan pages. */
function loanInvestBlocked(demoState: DemoAccountState, frozen = false) {
  return frozen || demoState !== "active" || isReadonlyImpersonationActive();
}

function loanDaysLeftLabel(days: number) {
  return days === 1 ? "1 day left" : `${days} days left`;
}

/**
 * The key facts shared by both loan pages (design: project facts card). Three big figures and the
 * funding progress on top, then the loan facts as a key/value grid.
 */
function LoanFactsCard({ loan }: { loan: MarketplaceLoanDetail }) {
  const originatorClaim = isOriginatorClaimLoan(loan);
  const subscriptionClaim = usesOriginatorSubscription(loan);
  const disclosure = borrowerDisclosureForLoan(loan);
  const availableMinor = marketplaceAvailableMinor(loan);
  const asOf = useBalancesData().data?.as_of;
  const [closesLabel, closesValue] = loanClosesRow(loan);
  const borrowerName = originatorClaim
    ? loan.borrower_display_name || disclosure.legal_name || "Undisclosed final borrower"
    : disclosure.legal_name || loan.title;
  const rows: Array<[string, ReactNode, boolean?]> = [
    ["Borrower", borrowerName],
    ...(originatorClaim && loan.originator_name ? [["Loan originator", loan.originator_name] as [string, ReactNode]] : []),
    ...(originatorClaim && (loan.skin_in_the_game_bps ?? 0) > 0
      ? [["Skin in the game", `${formatRateBps(loan.skin_in_the_game_bps ?? 0)} of the outstanding principal stays with the originator`] as [string, ReactNode]]
      : []),
    [subscriptionClaim ? "Nominal investor interest rate" : "Investor yield", `${formatRateBps(marketplaceYieldBps(loan))} p.a.`, true],
    ...(originatorClaim ? [["Borrower coupon", `${formatRateBps(loan.underlying_interest_rate_bps)} p.a.`, true] as [string, ReactNode, boolean]] : []),
    ["Loan-to-value", loanLtvBps(loan) !== null ? formatRateBps(loanLtvBps(loan) ?? 0) : "Not shown (no collateral value)", true],
    ["Collateral", loan.collateral_value_minor > 0 ? `${humanizeToken(loan.collateral_type)} · ${loan.currency} ${formatMoneyMinor(loan.collateral_value_minor, loan.currency)}` : humanizeToken(loan.collateral_type)],
    ["Collateral / backing", loan.collateral_description],
    ...(subscriptionClaim ? [
      ["Investor interest participation", formatRateBps(loan.investor_interest_participation_bps ?? 0), true] as [string, ReactNode, boolean],
      ["Investor penalty participation", formatRateBps(loan.investor_penalty_participation_bps ?? 0), true] as [string, ReactNode, boolean],
      ["Boundary installment due", loan.entitlement_start_date ? formatDate(loan.entitlement_start_date) : "Not available"] as [string, ReactNode]
    ] : []),
    ["Purpose", loan.purpose_description || humanizeToken(loan.purpose)],
    ["Risk rating", <Rating key="rating" value={loan.risk_rating} />],
    ["Repayment type", formatEnumLabel(loan.repayment_type)],
    ["Minimum investment", `${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)}`, true],
    ["Available now", `${loan.currency} ${formatMoneyMinor(availableMinor, loan.currency)}`, true],
    [closesLabel, closesValue]
  ];
  const percent = fundingPercent(loan);
  const daysLeft = closesLabel === "Closes" && loan.funding_deadline && isOpenMarketplaceLoan(loan)
    ? fundingDaysRemaining(loan.funding_deadline, asOf)
    : null;
  const [termValue, termUnit] = loan.remaining_term_days === null
    ? [loan.term_months, "mo"]
    : [loan.remaining_term_days, "days"];

  return (
    <Card className="lp-facts-card">
      <div className="lp-figures">
        <div className="lp-figs">
          <div className="lp-fig">
            <div className="lp-fig-num">{formatRateBps(marketplaceYieldBps(loan))}</div>
            <div className="lp-fig-label">Yield</div>
            <div className="lp-fig-sub">{subscriptionClaim ? "nominal rate after boundary" : originatorClaim ? "effective annual · ACT/365" : "nominal annual rate"}</div>
          </div>
          <div className="lp-fig">
            <div className="lp-fig-num">{termValue} <small>{termUnit}</small></div>
            <div className="lp-fig-label">Term</div>
            <div className="lp-fig-sub">{formatEnumLabel(loan.repayment_type)}</div>
          </div>
          <div className="lp-fig">
            <div className="lp-fig-num">{formatMoneyMinor(loan.principal_minor, loan.currency)} <small>{loan.currency}</small></div>
            <div className="lp-fig-label">{originatorClaim ? "Current principal" : "Amount"}</div>
          </div>
        </div>
        <div className="lp-funding">
          <div className="lp-funding-row">
            <span><strong>{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)}</strong> {subscriptionClaim ? "reserved" : originatorClaim ? "claim principal sold" : "allocated"}</span>
            <span className="lp-funding-pct">{subscriptionClaim ? "Reserved" : originatorClaim ? "Claim sold" : "Funded"} <strong>{percent}%</strong></span>
          </div>
          <Progress percent={percent} />
          <div className="lp-funding-row">
            <span>{closesLabel === "Closes" ? `Closes ${closesValue}` : `Matures ${closesValue}`}</span>
            {daysLeft !== null ? <span>{loanDaysLeftLabel(daysLeft)}</span> : null}
          </div>
        </div>
      </div>
      <div className="lp-facts-wrap">
        <div className="eyebrow lp-facts-title">Key facts</div>
        <dl className="kv lp-facts">
          {rows.map(([label, value, mono]) =>
            value !== undefined && value !== "" ? <KeyValueRow key={label} label={label} mono={mono} value={value} /> : null
          )}
        </dl>
      </div>
      {loan.investor_summary ? <p className="lp-summary">{loan.investor_summary}</p> : null}
    </Card>
  );
}

/** Card of the loan pages' main column: a head with a title (and optional tags) above the content. */
function LoanCard({ title, tags, className = "", children }: { title: string; tags?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <Card className={`lp-card ${className}`}>
      <div className="lp-card-head">
        <h2>{title}</h2>
        {tags ? <div className="lp-card-tags">{tags}</div> : null}
      </div>
      {children}
    </Card>
  );
}

/** Admin-entered borrower disclosure (design: "Borrower" card). Absent optional fields stay hidden. */
function LoanBorrowerCard({ loan }: { loan: MarketplaceLoanDetail }) {
  const disclosure = borrowerDisclosureForLoan(loan);
  const financialsCurrency = disclosure.financials_currency || loan.currency;
  const rows: Array<[string, ReactNode, boolean?]> = [
    ...(disclosure.country ? [["Country", disclosure.country] as [string, ReactNode]] : []),
    ...(disclosure.year_founded ? [["Year founded", String(disclosure.year_founded)] as [string, ReactNode]] : []),
    ...(disclosure.business_classification ? [["Business", disclosure.business_classification] as [string, ReactNode]] : []),
    ...(disclosure.registered_address ? [["Registered address", disclosure.registered_address] as [string, ReactNode]] : []),
    ...(disclosure.contact_info ? [["Contact info", disclosure.contact_info] as [string, ReactNode]] : []),
    ...(disclosure.assets_minor !== undefined ? [["Assets", disclosureMoney(disclosure.assets_minor, financialsCurrency), true] as [string, ReactNode, boolean]] : []),
    ...(disclosure.liabilities_minor !== undefined ? [["Liabilities", disclosureMoney(disclosure.liabilities_minor, financialsCurrency), true] as [string, ReactNode, boolean]] : []),
    ...(disclosure.revenue_last_year_minor !== undefined ? [["Revenue last year", disclosureMoney(disclosure.revenue_last_year_minor, financialsCurrency), true] as [string, ReactNode, boolean]] : []),
    ...(disclosure.profit_last_year_minor !== undefined ? [["Profit last year", disclosureMoney(disclosure.profit_last_year_minor, financialsCurrency), true] as [string, ReactNode, boolean]] : [])
  ];
  const visible = rows.filter(([, value]) => value !== undefined && value !== "");
  if (visible.length === 0) return null;
  return (
    <LoanCard title="Borrower details">
      <div className="lp-card-body">
        <dl className="kv lp-kv">
          {visible.map(([label, value, mono]) => <KeyValueRow key={label} label={label} mono={mono} value={value} />)}
        </dl>
      </div>
    </LoanCard>
  );
}

/** Borrower documents disclosed by the admin (design: "Documents" card). Each one downloads. */
function LoanDocumentsCard({ loan }: { loan: MarketplaceLoanDetail }) {
  const documents = borrowerDisclosureForLoan(loan).documents ?? [];
  if (documents.length === 0) return null;
  return (
    <LoanCard title="Documents">
      <LoanDocumentList disabled={isFixturePreview} documents={documents} humanize={humanizeToken} loanId={loan.loan_id} />
    </LoanCard>
  );
}

/** Design "Invest in this loan" card: key/value rows, then a grey footer with the note and the action. */
function LoanInvestAside({
  loan,
  demoState,
  setInvestLoan
}: {
  loan: MarketplaceLoanDetail;
  demoState: DemoAccountState;
  setInvestLoan: (loan: MarketplaceLoanDetail) => void;
}) {
  const frozenAccount = useFrozenAccount();
  const frozen = frozenAccount.frozen;
  const blocked = loanInvestBlocked(demoState, frozen);
  const originatorClaim = isOriginatorClaimLoan(loan);
  const subscriptionClaim = usesOriginatorSubscription(loan);
  const openForInvestment = isOpenMarketplaceLoan(loan);
  const availableMinor = marketplaceAvailableMinor(loan);
  const [closesLabel, closesValue] = loanClosesRow(loan);
  const balances = useBalancesData(!blocked).data;
  // Say up front when the investor's own funds cannot be used here (none, or too old for this funding window).
  const fundsBlock = balances
    ? noEligibleFundsReason(loan.currency, {
        balanceMinor: currencyBalanceMinor(balances.lots, loan.currency),
        eligibleMinor: sumLotAvailableMinor(currentInvestableLotsForLoanCurrency(balances.lots, loan))
      })
    : null;
  return (
    <aside className="aside-sticky lp-aside">
      <Card className="lp-aside-card">
        {!openForInvestment ? (
          <div className="lp-aside-sec">
            <Empty icon="checkCircle" title="Not open for investment">
              {originatorClaim
                ? "This originator claim is sold, on hold, repaid, late, defaulted, or within 30 days of maturity."
                : "This loan is closed to new orders."}
            </Empty>
          </div>
        ) : (
          <>
            <div className="lp-aside-sec">
              <h2 className="lp-aside-title">{subscriptionClaim ? "Subscribe at par" : originatorClaim ? "Buy this loan claim" : "Invest in this loan"}</h2>
              <div className="lp-aside-list">
                {originatorClaim && loan.originator_name ? <KeyValue label="Loan originator" value={loan.originator_name} /> : null}
                {originatorClaim && (loan.skin_in_the_game_bps ?? 0) > 0 ? <KeyValue label="Skin in the game" value={`${formatRateBps(loan.skin_in_the_game_bps ?? 0)} kept by the originator`} /> : null}
                <KeyValue label="Yield" value={`${formatRateBps(marketplaceYieldBps(loan))} p.a.`} />
                {originatorClaim ? <KeyValue label="Borrower coupon" value={`${formatRateBps(loan.underlying_interest_rate_bps)} p.a.`} /> : null}
                <KeyValue label="Minimum investment" value={`${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)}`} />
                <KeyValue label="Available now" value={`${loan.currency} ${formatMoneyMinor(availableMinor, loan.currency)}`} />
                <KeyValue label={closesLabel} value={closesValue} />
              </div>
            </div>
            {blocked ? (
              <div className="lp-aside-sec">
                <Banner tone={frozen ? "bad" : "warn"} title={frozen ? "Financial actions frozen" : "Investing not yet available"}>
                  {isReadonlyImpersonationActive()
                    ? "Read-only impersonation cannot place orders."
                    : frozen
                      ? frozenActionReason(frozenAccount)
                      : "Complete KYC verification to unlock investing."}
                </Banner>
              </div>
            ) : fundsBlock ? (
              <div className="lp-aside-sec">
                <Banner tone="warn" title={fundsBlock.title}>{fundsBlock.detail}</Banner>
              </div>
            ) : null}
            <div className="lp-aside-foot">
              <p className="lp-aside-note">
                {subscriptionClaim
                  ? "The order reserves balance at par and becomes a holding automatically at funding close. No interest accrues during funding; the boundary installment belongs entirely to the LO."
                  : originatorClaim
                  ? "BANXUM generates an executable quote from the remaining borrower cash flows. A confirmed purchase assigns the legal claim immediately."
                  : "Orders are intents and do not reserve capacity until funds are allocated and validated."}
              </p>
              {blocked ? null : (
                <Button icon="trend" size="lg" variant="primary" onClick={() => setInvestLoan(loan)}>
                  {usesImmediateClaimAssignment(loan) ? "Review claim purchase" : "Invest now"}
                </Button>
              )}
            </div>
          </>
        )}
      </Card>
    </aside>
  );
}

/**
 * Shared frame of the two loan pages (design: project page): page head with the tile, tags and the
 * Invest pill, the facts card, the page switch, then the main column next to the invest card.
 */
function LoanPageFrame({
  loanId,
  page,
  setRoute,
  demoState,
  setInvestLoan,
  children
}: {
  loanId: string;
  page: LoanPageKind;
  setRoute: (route: AppRoute) => void;
  demoState: DemoAccountState;
  setInvestLoan: (loan: MarketplaceLoanDetail) => void;
  children: (loan: MarketplaceLoanDetail) => ReactNode;
}) {
  const loanQuery = useLoanDetailData(loanId);
  const frozenAccount = useFrozenAccount();
  const loan = loanQuery.data;
  const title = page === "story" ? loanCounterpartyLabel : () => "Loan schedule & payments";
  if (loanQuery.isError && !loan) {
    return isNotFoundError(loanQuery.error) ? (
      <LoanNotFound setRoute={setRoute} title="Loan detail" />
    ) : (
      <ScreenError title="Loan detail" onRetry={() => void loanQuery.refetch()}>
        We could not load this loan detail. Return to the marketplace or retry after the API is reachable.
      </ScreenError>
    );
  }
  if (!loan) return <ScreenLoading title="Loan detail" />;
  const originatorClaim = isOriginatorClaimLoan(loan);
  const canInvest = isOpenMarketplaceLoan(loan) && !loanInvestBlocked(demoState, frozenAccount.frozen);

  return (
    <main className="content lp-page">
      <PageHead
        actions={canInvest ? <Button icon="trend" variant="primary" onClick={() => setInvestLoan(loan)}>Invest</Button> : undefined}
        back={{ label: "Primary market", onClick: () => goTo(setRoute, "market") }}
        className="lp-head"
        description={
          <span className="lp-meta">
            <span className="lp-eyebrow">{title(loan)}</span>
            {/* A published loan with nothing left to fill is not "Open" (it waits for its close). */}
            <Chip status={["open", "published"].includes(loan.status) && !isOpenMarketplaceLoan(loan) ? "funded" : loan.status} />
            <Rating value={loan.risk_rating} />
            <span className="tag">{loan.currency}</span>
            {loan.is_refinancing ? <RefinancedTag full /> : null}
            {originatorClaim ? <span className="tag">Originator claim</span> : null}
            <CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" />
          </span>
        }
        title={
          <span className="lp-title">
            <span aria-hidden="true" className="lp-tile"><Icon name="building" size={26} strokeWidth={1.5} /></span>
            <span>{loan.title}</span>
          </span>
        }
      />
      <LoanFactsCard loan={loan} />
      <nav aria-label="Loan pages" className="lp-switch">
        <button aria-current={page === "story" ? "page" : undefined} className={`lp-switch-btn ${page === "story" ? "on" : ""}`} onClick={() => goTo(setRoute, "loan", { loanId: loan.loan_id })} type="button">{loanCounterpartyLabel(loan)}</button>
        <button aria-current={page === "schedule" ? "page" : undefined} className={`lp-switch-btn ${page === "schedule" ? "on" : ""}`} onClick={() => goTo(setRoute, "loanSchedule", { loanId: loan.loan_id })} type="button">Loan schedule & payments</button>
      </nav>
      <div className="split loan-detail-layout">
        <div className="lp-main">
          {children(loan)}
          <LoanBorrowerCard loan={loan} />
          <LoanDocumentsCard loan={loan} />
        </div>
        <LoanInvestAside demoState={demoState} loan={loan} setInvestLoan={setInvestLoan} />
      </div>
    </main>
  );
}

/** "Meet the borrower" (direct loans) / "Meet the originator" (originator claims): key facts + the admin-authored story. */
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
  return (
    <LoanPageFrame demoState={demoState} loanId={loanId} page="story" setInvestLoan={setInvestLoan} setRoute={setRoute}>
      {(loan) => {
        const story = normalizeStory((loan as MarketplaceLoanDetail & { story?: unknown }).story);
        const subject = loanStorySubjectName(loan);
        const originatorClaim = isOriginatorClaimLoan(loan);
        return (
          <LoanCard className="lp-story-card" title={originatorClaim ? "About the loan originator" : "About the borrower"}>
            <div className="lp-card-body">
              {storyIsEmpty(story) ? (
                <Empty icon="doc" title={`No story published yet for ${subject}`}>
                  {originatorClaim
                    ? "BANXUM has not published a profile of this loan originator yet."
                    : "BANXUM has not published a profile of this borrower yet."}
                </Empty>
              ) : (
                <StoryView story={story} />
              )}
              {!storyIsEmpty(story) ? <p className="lp-story-note">
                Published by BANXUM from {originatorClaim ? "the loan originator's" : "the borrower's"} material. Investment terms and risk disclosures apply; repayments are not guaranteed.
              </p> : null}
            </div>
          </LoanCard>
        );
      }}
    </LoanPageFrame>
  );
}

function DirectLoanScheduleSection({ loan }: { loan: MarketplaceLoanDetail }) {
  const schedule = loan.loan_schedule ?? [];
  const hasPayments = schedule.some((row) => row.row_type === "repayment_event");
  const totals = schedule.reduce(
    (acc, row) => {
      acc.principal += row.principal_minor;
      acc.interest += row.interest_minor;
      acc.total += row.total_minor;
      return acc;
    },
    { principal: 0, interest: 0, total: 0 }
  );
  return (
    <LoanCard tags={<span className="tag">Version {loan.schedule_version}</span>} title="Contracted repayment schedule">
      <div className="lp-card-body">
        <p className="lp-card-text">
          The borrower's full schedule on the published principal, {formatEnumLabel(loan.repayment_type).toLowerCase()} at {formatRateBps(loan.interest_rate_bps)} p.a.
          {loan.first_payment_date ? ` First payment ${formatDate(loan.first_payment_date)}.` : ""} {isOpenMarketplaceLoan(loan) ? "If the campaign closes at its minimum, the loan is made on the smaller principal and this schedule is regenerated." : "Recorded payments are followed by the remaining schedule."} Your share follows your share of the principal.
        </p>
      </div>
      {schedule.length > 0 ? (
        <div className="tbl-wrap lp-table">
          <table className="tbl">
            <thead><tr><th>Installment / payment</th><th>Date</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Total</th><th className="num">Outstanding after</th><th>Status</th></tr></thead>
            <tbody>
              {schedule.map((row) => (
                <tr key={row.id ?? row.installment_number}>
                  <td>{row.label ?? row.installment_number}</td>
                  <td>{formatDate(row.payment_date ?? row.due_date)}</td>
                  <td className="num">{formatMoneyMinor(row.principal_minor, loan.currency)}</td>
                  <td className="num">{formatMoneyMinor(row.interest_minor, loan.currency)}</td>
                  <td className="num col-strong">{formatMoneyMinor(row.total_minor, loan.currency)}</td>
                  <td className="num">{formatMoneyMinor(row.outstanding_after_minor, loan.currency)}</td>
                  <td>{humanizeToken(row.status ?? "upcoming")}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="schedule-totals">
              <tr>
                <th colSpan={2}>Totals · {schedule.length} payments</th>
                <th className="num">{formatMoneyMinor(totals.principal, loan.currency)}</th>
                <th className="num">{formatMoneyMinor(totals.interest, loan.currency)}</th>
                <th className="num">{formatMoneyMinor(totals.total, loan.currency)}</th>
                <th className="num">-</th>
                <th />
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <Empty icon="doc" title="Schedule not available yet">The contracted schedule appears once the loan is published with its installments.</Empty>
      )}
      {!hasPayments ? (
        <div className="lp-card-sub">
          <div className="eyebrow lp-subhead">Payment history</div>
          <Empty icon="checkCircle" title="No borrower payments yet">
            {isOpenMarketplaceLoan(loan)
              ? "This loan is still funding. Borrower payments are listed here once the first installment is collected."
              : "No borrower payments have been recorded for this loan."}
          </Empty>
        </div>
      ) : null}
    </LoanCard>
  );
}

/** Loan schedule & payment history page: the contracted schedule and what the borrower has paid, nothing else. */
function LoanScheduleScreen({
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
  return (
    <LoanPageFrame demoState={demoState} loanId={loanId} page="schedule" setInvestLoan={setInvestLoan} setRoute={setRoute}>
      {(loan) => (
        <>
          {isOriginatorClaimLoan(loan) ? <OriginatorClaimLoanSection loan={loan} /> : <DirectLoanScheduleSection loan={loan} />}
          {loan.is_refinancing ? <OriginalLoanSection loan={loan} /> : null}
        </>
      )}
    </LoanPageFrame>
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

function OriginatorClaimLoanSection({ loan }: { loan: MarketplaceLoanDetail }) {
  const subscriptionClaim = usesOriginatorSubscription(loan);
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
    <LoanCard tags={<span className="tag">Revision {loan.schedule_revision ?? loan.schedule_version}</span>} title="Loan-originator evidence">
      <div className="lp-card-body">
        <p className="lp-card-text">
          {subscriptionClaim
            ? "The Loan Originator retains the unsold principal. Your order reserves cash at par during funding and activates automatically at funding close. The first post-funding installment belongs entirely to the LO. You participate in subsequent payments under the declared interest and penalty percentages."
            : "The Loan Originator owns the unsold claim. A legacy purchase assigns part of the final-borrower claim immediately. The yield shown by BANXUM is the effective annual ACT/365 yield priced from the remaining cash flows; it is distinct from the borrower coupon."}
        </p>
        <dl className="kv lp-kv">
          <KeyValueRow label={subscriptionClaim ? "Nominal investor interest rate" : "Target investor yield"} mono value={`${formatRateBps(loan.yield_bps)} p.a.`} />
          <KeyValueRow label="Underlying borrower coupon" mono value={`${formatRateBps(loan.underlying_interest_rate_bps)} p.a.`} />
          {subscriptionClaim ? <KeyValueRow label="Investor interest participation" mono value={formatRateBps(loan.investor_interest_participation_bps ?? 0)} /> : null}
          {subscriptionClaim ? <KeyValueRow label="Investor penalty participation" mono value={formatRateBps(loan.investor_penalty_participation_bps ?? 0)} /> : null}
          {subscriptionClaim && loan.funding_deadline ? <KeyValueRow label="Funding deadline" value={formatDate(loan.funding_deadline)} /> : null}
          {subscriptionClaim && loan.entitlement_start_date ? <KeyValueRow label="Boundary installment due" value={formatDate(loan.entitlement_start_date)} /> : null}
          <KeyValueRow label={subscriptionClaim ? "Post-boundary principal" : "Current outstanding principal"} mono value={`${loan.currency} ${formatMoneyMinor(loan.principal_minor, loan.currency)}`} />
          <KeyValueRow label={subscriptionClaim ? "Available at par" : "Available claim principal"} mono value={`${loan.currency} ${formatMoneyMinor(loan.remaining_capacity_minor, loan.currency)}`} />
          {loan.maturity_date ? <KeyValueRow label="Maturity" value={formatDate(loan.maturity_date)} /> : null}
          {!subscriptionClaim && loan.pricing_as_of_date ? <KeyValueRow label="Pricing data as of" value={formatDate(loan.pricing_as_of_date)} /> : null}
        </dl>
        {subscriptionClaim ? (
          <Banner tone="info" title="No funding-period interest">
            The boundary installment is excluded from investor entitlement. For subsequent installments, principal
            follows the imported loan schedule; interest and penalties are distributed using the declared
            participation percentages. Unsold rights remain with the Loan Originator.
          </Banner>
        ) : null}
      </div>
      {schedule.length > 0 ? (
        <div className="lp-card-sub">
          <div className="eyebrow lp-subhead">Current full loan schedule</div>
          <div className="tbl-wrap lp-table">
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
        </div>
      ) : null}
      {payments.length > 0 ? (
        <div className="lp-card-sub">
          <div className="eyebrow lp-subhead">Historical borrower payments</div>
          <div className="tbl-wrap lp-table">
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
        </div>
      ) : null}
    </LoanCard>
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
    <LoanCard tags={<RefinancedTag full />} title="Original loan">
      <div className="lp-card-body">
        <p className="lp-card-text">
          This loan refinances an existing loan of the borrower. The original loan data and repayment
          schedule below are informational only and show the loan being refinanced; investors fund the
          new loan whose terms are shown above.
        </p>
        <dl className="kv lp-kv">
          <KeyValueRow label="Original principal" mono value={`${loan.currency} ${formatMoneyMinor(loan.original_principal_minor, loan.currency)}`} />
          {loan.original_interest_rate_bps !== null ? <KeyValueRow label="Original interest rate" mono value={`${formatRateBps(loan.original_interest_rate_bps)} p.a.`} /> : null}
          {loan.original_term_months !== null ? <KeyValueRow label="Original term" value={`${loan.original_term_months} mo`} /> : null}
          {loan.original_repayment_type ? <KeyValueRow label="Original repayment type" value={formatEnumLabel(loan.original_repayment_type)} /> : null}
          {loan.original_interest_only_months ? <KeyValueRow label="Original interest-only period" value={`${loan.original_interest_only_months} mo`} /> : null}
          {loan.original_loan_start_date ? <KeyValueRow label="Original loan start date" value={formatDate(loan.original_loan_start_date)} /> : null}
        </dl>
      </div>
      {schedule.length > 0 ? (
        <div className="lp-card-sub">
          <div className="eyebrow lp-subhead">Original loan repayment schedule</div>
          <div className="tbl-wrap lp-table">
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
          <p className="lp-card-note">
            Installments marked Paid were settled by the borrower before this loan was published. The
            financed amount can be lower than the remaining outstanding of the original schedule.
          </p>
        </div>
      ) : null}
    </LoanCard>
  );
}

function BalancesScreen({ demoState }: { demoState: DemoAccountState }) {
  const balancesQuery = useBalancesData();
  const fxFeature = useFxFeature();
  const frozenAccount = useFrozenAccount();
  const balances = balancesQuery.data;
  const [currency, setCurrency] = useState<"CHF" | "EUR">("CHF");
  const [modal, setModal] = useState<"deposit" | "withdraw" | "iban" | null>(null);
  // The account cards open the deposit and withdrawal dialogs for their own
  // currency; the page actions keep using the selected currency.
  const [modalCurrency, setModalCurrency] = useState<string>("CHF");
  const returnDays = autoReturnDays(balancesQuery.data?.auto_return_after_days);
  const pageDescription = `Funds are non-interest-bearing. ${autoReturnRuleText(returnDays)}`;
  if (balancesQuery.isError && !balances) {
    return (
      <ScreenError title="Account" onRetry={() => void balancesQuery.refetch()}>
        We could not load balance lots and payout instructions. Retry once the API connection is restored.
      </ScreenError>
    );
  }
  if (!balances) return <ScreenLoading title="Account" />;

  const summary = balances.summaries.find((item) => item.currency === currency) ?? balances.summaries[0];
  const lots = balances.lots.filter((lot) => lot.currency === currency);
  const frozen = frozenAccount.frozen;
  // The fixture preview's "Day-60 freeze" shows the overdue lots as frozen; live data has its own bucket.
  const previewFrozen = isFixturePreview && demoState === "frozen";
  const readonly = isReadonlyImpersonationActive();
  // Withdrawals go only to an IBAN Garanta has verified for that currency.
  const verifiedIbanCurrencies = new Set(
    balances.payout_instructions.filter((instruction) => instruction.is_verified_usable).map((instruction) => instruction.currency)
  );
  const withdrawBlockedReason = (forCurrency: string) =>
    verifiedIbanCurrencies.has(forCurrency) ? "" : `No verified payout IBAN for ${forCurrency} yet. Garanta must verify an IBAN before you can withdraw.`;
  // Money due back to the bank that cannot go back: there is no verified IBAN in its currency.
  const returnBlocked = balances.summaries.filter((item) => item.overdue_minor > 0 && !verifiedIbanCurrencies.has(item.currency));
  if (!summary) {
    return (
      <main className="content acct-page acct-balances">
        <PageHead description={pageDescription} title="Account" />
        <Card><Empty icon="balance" title="No balances yet">Deposits, repayments, recoveries, FX proceeds, and sale proceeds will appear here after reconciliation.</Empty></Card>
      </main>
    );
  }
  const openModal = (kind: "deposit" | "withdraw" | "iban", forCurrency: string = currency) => {
    setModalCurrency(forCurrency);
    setModal(kind);
  };
  const modalSummary = balances.summaries.find((item) => item.currency === modalCurrency) ?? summary;

  return (
    <main className="content acct-page acct-balances">
      <PageHead
        actions={
          <>
            <Segmented options={[{ value: "CHF", label: "CHF" }, { value: "EUR", label: "EUR" }]} value={currency} onChange={setCurrency} />
            <Button className="btn-green" disabled={frozen || readonly} icon="plus" variant="primary" onClick={() => openModal("deposit")}>Add Funds</Button>
            <Button disabled={readonly} icon="download" onClick={() => openModal("withdraw")}>Withdraw</Button>
            <Button disabled={readonly} icon="balance" variant="ghost" onClick={() => openModal("iban")}>Payout IBANs</Button>
          </>
        }
        description={pageDescription}
        title="Account"
      />
      {readonly || returnBlocked.length > 0 ? (
        <div className="col gap-12 acct-alerts">
          {readonly ? (
            <Banner icon="lock" tone="info" title="Read-only view">
              Deposits, withdrawals and payout-IBAN changes are disabled during superadmin read-only impersonation.
            </Banner>
          ) : null}
          {returnBlocked.map((item) => (
            <Banner
              actions={readonly ? undefined : <Button size="sm" variant="primary" onClick={() => openModal("iban", item.currency)}>Add payout IBAN</Button>}
              key={item.currency}
              tone="warn"
              title="Add a verified bank account so we can return your money"
            >
              {formatMoneyLabel(item.currency, item.overdue_minor)} was not invested within {returnDays} days and must go back to your bank,
              but there is no verified {item.currency} payout IBAN. Add one in your name: when Garanta has verified it, we send the money there.
              After 60 days (the legal limit) the money enters penalty mode.
            </Banner>
          ))}
        </div>
      ) : null}

      <div className="acct-ccy-grid">
        {balances.summaries.map((item) => {
          const ccy = item.currency;
          const nextReturn = item.next_return_date;
          return (
            <section className="card acct-ccy" key={ccy}>
              <h2 className="acct-ccy-title">{ccy} account</h2>
              <div className="acct-ccy-amount num">{ccy} {formatMoneyMinor(item.total_available_minor, ccy)}</div>
              <ul className="acct-ccy-list">
                <BucketTile label="Potentially investable" value={item.investable_minor} currency={ccy} tone="ok" sub="Depends on the loan funding window" />
                <BucketTile label="Withdraw-only" value={item.withdraw_only_minor} currency={ccy} tone="warn" sub={`Day ${returnDays}: last day, can only be withdrawn today`} />
                <BucketTile label="Due back to your bank" value={item.overdue_minor} currency={ccy} tone="warn" sub={`Not invested within ${returnDays} days`} />
                {/* Blocked balance only. Penalties already charged are no longer in the balance; they are listed in the lots view. */}
                <BucketTile
                  label="Frozen"
                  value={previewFrozen ? item.overdue_minor : item.penalty_mode_minor + item.frozen_minor}
                  currency={ccy}
                  tone={previewFrozen || item.penalty_mode_minor + item.frozen_minor > 0 ? "bad" : "neutral"}
                  sub={previewFrozen
                    ? "IBAN required"
                    : item.penalty_mode_minor > 0
                      ? `Penalty ${formatRateBps(balances.penalty_bps_per_day ?? 0)} a day until withdrawn`
                      : item.frozen_minor > 0 ? "Blocked until withdrawn" : "None"}
                />
                <li className="acct-ccy-row total">
                  <span className="acct-ccy-label">On the account</span>
                  <span className="acct-ccy-value num">{formatMoneyMinor(item.total_available_minor, ccy)}</span>
                </li>
              </ul>
              <div className="acct-ccy-cta">
                <Button block className="btn-green" disabled={frozen || readonly} size="lg" variant="primary" onClick={() => openModal("deposit", ccy)}>Add {ccy}</Button>
                <Button block className="acct-ccy-withdraw" disabled={readonly} variant="ghost" onClick={() => openModal("withdraw", ccy)}>Withdraw to IBAN</Button>
                {withdrawBlockedReason(ccy) ? <p className="acct-ccy-note acct-ccy-blocked">{withdrawBlockedReason(ccy)}</p> : null}
                <p className="acct-ccy-note">
                  {nextReturn ? <>Goes back to your bank on <strong>{formatDate(nextReturn)}</strong> if not invested</> : "No money waiting to go back to your bank."}
                </p>
              </div>
            </section>
          );
        })}
      </div>

      <section className="card acct-lots-card">
        <div className="card-head">
          <h2>{currency} balance lots</h2>
          <span className="acct-card-meta">{pluralize(lots.length, "lot")} · used oldest first</span>
        </div>
        {summary.penalty_charged_minor > 0 ? (
          <div className="acct-penalty-line">
            <span>Penalty charged</span>
            <span className="acct-penalty-value num">{currency} {formatMoneyMinor(summary.penalty_charged_minor, currency)}</span>
            <span className="acct-penalty-note">
              Balance-ageing penalty for funds held past day 60, taken from the lots below. It is already deducted and not part of any balance shown.
            </span>
          </div>
        ) : null}
        <BalanceLotsTable lots={lots} frozen={previewFrozen} returnDays={returnDays} />
      </section>

      <div className="acct-two">
        <section className="card acct-iban-card">
          <div className="card-head">
            <h2>Payout IBANs</h2>
            <Button disabled={readonly} icon="plus" size="sm" onClick={() => openModal("iban")}>Add or update IBAN</Button>
          </div>
          <div className="acct-rows">
            {balances.payout_instructions.map((instruction) => (
              <div className="acct-row" key={instruction.id}>
                <div className="acct-row-text">
                  <div className="acct-row-title">{instruction.destination_account_name}</div>
                  <div className="acct-iban num">{instruction.destination_iban}</div>
                </div>
                <div className="acct-row-actions">
                  <span className="tag">{instruction.currency}</span>
                  {(() => {
                    const state = payoutInstructionState(instruction);
                    return <Chip status={state.key} tone={state.tone}>{state.label}</Chip>;
                  })()}
                </div>
              </div>
            ))}
          </div>
        </section>
        <section className="card acct-pending-card">
          <div className="card-head"><h2>Pending withdrawals</h2></div>
          <PendingWithdrawalsList withdrawals={balances.pending_withdrawals ?? []} />
        </section>
      </div>

      <section className="card acct-rules">
        <div className="card-head"><h2>Rules for your money</h2></div>
        <ul className="acct-rules-list">
          <li>{autoReturnRuleText(returnDays)} We send it to your verified payout IBAN.</li>
          <li>To invest, that amount must have enough time left to cover the loan's remaining funding period. Shorter periods can use older funds.</li>
          <li>Eligible lots are consumed oldest-first.</li>
          {fxFeature.enabled ? <li>FX conversion does not restart this count.</li> : null}
          <li>Without a verified payout IBAN we cannot return the money. After 60 days (the legal limit) it enters penalty mode.</li>
        </ul>
      </section>
      {modal === "deposit" ? <DepositModal currency={modalCurrency} onClose={() => setModal(null)} /> : null}
      {modal === "withdraw" ? <WithdrawModal currency={modalCurrency} maxMinor={withdrawableMinor(modalSummary)} payoutInstructions={balances.payout_instructions.filter((instruction) => instruction.currency === modalCurrency)} onClose={() => setModal(null)} /> : null}
      {modal === "iban" ? <PayoutIbanModal onClose={() => setModal(null)} /> : null}
    </main>
  );
}

// One line of a currency account card (design "nk-iv-wg2-list").
function BucketTile({ label, value, currency, tone, sub }: { label: string; value: number; currency: string; tone: "ok" | "warn" | "bad" | "neutral"; sub: string }) {
  return (
    <li className={`acct-ccy-row tone-${tone}`}>
      <span className="acct-ccy-label">
        {label}
        <span className={`acct-ccy-sub${tone === "bad" ? " neg" : ""}`}>{sub}</span>
      </span>
      <span className="acct-ccy-value num">{formatMoneyMinor(value, currency)}</span>
    </li>
  );
}

function BalanceLotsTable({ lots, frozen, returnDays }: { lots: BalanceLot[]; frozen: boolean; returnDays: number }) {
  if (lots.length === 0) {
    return <div className="portal-table-empty"><Empty icon="balance" title="No balance lots">Incoming deposits, repayments, recoveries, FX proceeds, or sale proceeds will appear here.</Empty></div>;
  }
  const showPenalty = lots.some((lot) => lot.penalized_amount_minor > 0);

  return (
    <div className="portal-data-surface">
      <div className="tbl-wrap">
        <table className="tbl portal-data-table balance-lots-table stack-on-phone">
          <thead><tr><th>Lot</th><th>Source</th><th>Received</th><th className="num">Remaining</th>{showPenalty ? <th className="num">Penalty charged</th> : null}<th>Age/deadline</th><th>Status</th></tr></thead>
          <tbody>
            {lots.map((lot) => {
              const penalty = frozen && lot.bucket === "overdue";
              const age = lotAgeLines(lot, returnDays);
              return (
                <tr className={penalty ? "lot-penalty" : lot.bucket === "overdue" ? "lot-overdue" : ""} key={lot.id}>
                  <td data-label="Lot"><CopyIdButton ariaLabel="Copy lot ID" id={lot.id} label="Copy lot ID" /></td>
                  <td data-label="Source"><div>{sourceLabel(lot.source_type)}</div>{lot.source_type === "fx_proceeds" ? <div className="sub">Deadline inherited from source lot</div> : null}</td>
                  <td className="lot-received" data-label="Received">{formatDate(lot.received_at)}</td>
                  <td className="num lot-remaining" data-label="Remaining">{formatMoneyMinor(lot.available_amount_minor, lot.currency)}</td>
                  {showPenalty ? (
                    <td className={`num lot-penalty-charged${lot.penalized_amount_minor > 0 ? " has-penalty" : ""}`} data-label="Penalty charged">{lot.penalized_amount_minor > 0 ? formatMoneyMinor(lot.penalized_amount_minor, lot.currency) : "-"}</td>
                  ) : null}
                  <td className="lot-deadline" data-label="Age / deadline">
                    <DeadlineMeter daysLeft={lot.days_until_last_day} totalDays={returnDays} />
                    <div className="lot-deadline-meta">
                      <span>{age.status}</span>
                      <span>{age.detail}</span>
                    </div>
                  </td>
                  <td data-label="Status"><Chip status={penalty ? "penalty" : lot.bucket}>{!penalty && lot.bucket === "overdue" ? "Due back" : undefined}</Chip></td>
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
      <div className="col gap-16 acct-modal deposit-modal">
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
        <dl className="acct-copy-list">
          <DepositDetailRow copyLabel="Copy account holder" copyValue={instruction.account_holder_name} label="Account holder" value={instruction.account_holder_name || "Pending configuration"} />
          <DepositDetailRow label="Bank" value={instruction.bank_name || "Pending configuration"} />
          <DepositDetailRow copyLabel="Copy IBAN" copyValue={instruction.iban} label="IBAN" value={instruction.iban} />
          {instruction.qr_iban ? <DepositDetailRow copyLabel="Copy QR IBAN" copyValue={instruction.qr_iban} label="QR IBAN" value={instruction.qr_iban} /> : null}
          <DepositDetailRow copyLabel="Copy BIC/SWIFT" copyValue={instruction.bic} label="BIC/SWIFT" value={instruction.bic} />
        </dl>
        {instruction.qr_bill_payload ? (
          <div className="qr-instruction-panel">
            <QrBillImage payload={instruction.qr_bill_payload} />
            <div>
              <div className="eyebrow">Swiss QR-bill code</div>
              <p className="qr-instruction-copy">
                Scan this code only for {selectedCurrency} transfers. If your bank app does not carry the
                BANXUM payment reference automatically, enter the reference below unchanged.
              </p>
            </div>
          </div>
        ) : null}
        <div className="deposit-reference">
          <div className="acct-copy is-key">
            <div className="acct-copy-label">Payment reference - required</div>
            <div className="acct-copy-value num">{instruction.payment_reference}</div>
            <div className="acct-copy-action"><CopyIdButton ariaLabel="Copy payment reference" id={instruction.payment_reference} label="Copy" /></div>
          </div>
          <div className="deposit-reference-guidance">
            <Icon name="info" size={16} />
            <span>
              Enter this reference unchanged in the payment details or reference field of your bank
              transfer. Missing or incorrect references may delay allocation of the funds to your
              BANXUM account.
            </span>
          </div>
          <p className="acct-modal-note">The bank value date starts the new balance lot's count: what is not invested goes back to your bank after {AUTO_RETURN_AFTER_DAYS} days.</p>
          <p className="acct-modal-note">{payload.reference_rule}</p>
        </div>
      </div>
    </Modal>
  );
}

// A label/value row with an optional copy button (design "How to add funds").
function DepositDetailRow({ label, value, copyValue, copyLabel }: { label: string; value: ReactNode; copyValue?: string | null; copyLabel?: string }) {
  return (
    <div className="acct-copy">
      <dt className="acct-copy-label">{label}</dt>
      <dd className="acct-copy-value num">{value}</dd>
      {copyValue ? (
        <dd className="acct-copy-action"><CopyIdButton ariaLabel={copyLabel ?? `Copy ${label}`} iconOnly id={copyValue} label={copyLabel ?? `Copy ${label}`} /></dd>
      ) : null}
    </div>
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
        dark: "#0a0a0a",
        light: "#ffffff"
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

function formatIbanGroups(iban: string) {
  return iban.replace(/\s/g, "").replace(/(.{4})/g, "$1 ").trim();
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
      if (codeRequest.pin.previewAccepts()) setStep("done");
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
          // One key per withdrawal intent: a retry after a timeout is recognised by
          // the server and not paid out twice. New amount or IBAN, new key.
          idempotency_key: intentIdempotencyKey("investor-withdrawal", {
            amount_minor: amountMinor,
            currency,
            destination_iban: selectedInstruction.destination_iban,
            destination_account_name: selectedInstruction.destination_account_name
          }),
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          pin: codeRequest.pin.value
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setStep("done");
        },
        onError: (mutationError) => {
          if (codeRequest.pin.handleError(mutationError)) return;
          setError(apiErrorMessage(mutationError));
        }
      }
    );
  };

  const footer = step === "done"
    ? <Button variant="primary" onClick={onClose}>Done</Button>
    : step === "confirm"
      ? <><Button variant="ghost" onClick={() => setStep("form")}>Back</Button><Button disabled={code.length < 6 || !codeRequest.pin.ready || (!isFixturePreview && !codeRequest.codeId) || withdrawalMutation.isPending} variant="primary" onClick={submitWithdrawal}>{withdrawalMutation.isPending ? "Submitting..." : "Confirm withdrawal"}</Button></>
      : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!valid} variant="primary" onClick={() => setStep("confirm")}>Review</Button></>;

  return (
    <Modal footer={footer} onClose={onClose} title={`Withdraw ${currency}`}>
      {step === "form" ? (
        <div className="col gap-16 acct-modal">
          <div className="acct-modal-figure"><span className="acct-modal-figure-label">Withdrawable balance</span><span className="acct-modal-figure-value num">{currency} {formatMoneyMinor(maxMinor, currency)}</span></div>
          <Field error={amountError} label="Amount to withdraw">
            <div className="input-affix"><span className="prefix">{currency}</span><input className="input mono" inputMode="decimal" onChange={(event) => setAmount(event.target.value.replace(/[^0-9.,'\u2019\s]/g, ""))} placeholder="0.00" style={{ paddingLeft: 60 }} value={amount} /></div>
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
        <div className="col gap-16 acct-modal">
          <Review rows={[{ label: "Amount", value: `${currency} ${formatMoneyMinor(amountMinor, currency)}` }, { label: "To IBAN", value: selectedInstruction ? formatIbanGroups(selectedInstruction.destination_iban) : "-" }, { label: "Account name", value: selectedInstruction?.destination_account_name || "-" }, { label: "Fee", value: "None" }, { label: "You will receive", value: `${currency} ${formatMoneyMinor(amountMinor, currency)}`, total: true }]} />
          <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code and your PIN.</Banner>
          <SensitiveActionFields code={code} codeRequest={codeRequest} onCodeChange={setCode} onContinue={submitWithdrawal} />
          {codeRequest.expiresAt ? <p className="acct-modal-note">Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
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
  return formatMoneyLabel(currency, amountMinor);
}

function fxRateLabel(rate: string | number | null | undefined) {
  const value = Number(rate);
  return Number.isFinite(value) && value > 0 ? formatDecimal(value, 4) : "-";
}

// The quoted rate net of the platform fee, shown the same way on the page, in the rate list and in
// the confirmation. (The amount-based effective rate differs in the 4th decimal through rounding.)
function fxNetRateLabel(quote: Pick<FxQuotePreview, "rate" | "platform_fee_bps"> | null | undefined) {
  if (!quote) return "-";
  return fxRateLabel(Number(quote.rate) * ((10_000 - quote.platform_fee_bps) / 10_000));
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
  const frozenAccount = useFrozenAccount();
  const fx = fxQuery.data;
  const balances = balancesQuery.data;
  const [from, setFrom] = useState<"CHF" | "EUR">("CHF");
  const [amount, setAmount] = useState("");
  const [debouncedInput, setDebouncedInput] = useState({ from: "CHF" as "CHF" | "EUR", amountMinor: 0 });
  const [quoteOpen, setQuoteOpen] = useState(false);
  const [liveQuote, setLiveQuote] = useState<FxQuote | null>(null);
  // Browser time when the quote arrived: the countdown runs from here for the quote's time to live.
  const [quoteReceivedAt, setQuoteReceivedAt] = useState(0);
  const [error, setError] = useState("");
  const quoteMutation = useV1FxQuotesCreate();
  const to: "CHF" | "EUR" = from === "CHF" ? "EUR" : "CHF";
  const parsedAmount = parseMoneyInputToMinorUnits(amount, from);
  const amountMinor = parsedAmount.amountMinor;
  const availableMinor = balances?.summaries.find((summary) => summary.currency === from)?.total_available_minor ?? 0;
  const targetAvailableMinor = balances?.summaries.find((summary) => summary.currency === to)?.total_available_minor ?? 0;
  const frozen = frozenAccount.frozen || demoState === "frozen";
  const readonly = isReadonlyImpersonationActive();
  // Weekends follow the platform clock (balances.as_of, Europe/Zurich), not the browser's date.
  const fxClosedForWeekend = !isFixturePreview && Boolean(balances?.as_of) && isZurichWeekendAt(balances?.as_of ?? "");
  const fxTerms = fx?.terms;
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
  const requestQuote = (afterQuote?: () => void) => {
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
          setQuoteReceivedAt(Date.now());
          setQuoteOpen(true);
          afterQuote?.();
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
    <main className="content fx-page acct-page">
      <PageHead
        description="Convert available CHF and EUR balances. The executable rate and fee are shown before confirmation."
        title="Currency exchange"
      />
      {frozen || readonly || fxClosedForWeekend ? (
        <div className="col gap-12 acct-alerts">
          {frozen ? <Banner icon="lock" tone="bad" title="FX is frozen">{frozenActionReason(frozenAccount)}</Banner> : null}
          {readonly ? <Banner icon="lock" tone="info" title="Read-only view">FX quote and execution are disabled during superadmin read-only impersonation.</Banner> : null}
          {fxClosedForWeekend ? (
            <Banner icon="clock" tone="warn" title="FX unavailable on weekends">
              Live FX market rates are not published on weekends, so BANXUM cannot issue executable FX quotes now. Currency exchange resumes after markets reopen.
            </Banner>
          ) : null}
        </div>
      ) : null}

      <div className="fx-desk">
        <section aria-label="Currency converter" className="card fx-card">
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
            <strong className="num fx-rate-value">{preview ? `1 ${from} = ${fxNetRateLabel(preview)} ${to}` : previewLoading ? "Checking current rate" : "Enter an amount"}</strong>
          </div>
          <div className="fx-cta-line">
            <span className="fx-cta-copy">
              {preview
                ? `Converting makes ${fxMoneyLabel(to, preview.target_amount_minor)} available in your ${to} balance. Converted money keeps the earliest deadline of the funds it came from — FX never resets the holding clock.`
                : "Converted money keeps the earliest deadline of the funds it came from — FX never resets the holding clock."}
            </span>
            <button
              className="fx-convert-btn"
              disabled={!preview || frozen || fxClosedForWeekend || readonly || quoteMutation.isPending}
              onClick={() => requestQuote()}
              type="button"
            >
              {quoteMutation.isPending ? "Locking quote..." : "Convert"}
            </button>
          </div>
        </section>

        <aside className="fx-rail">
          <section className="card fx-rail-card">
            <div className="card-head"><h2 className="fx-cap fx-rail-cap">Your balances</h2></div>
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
          <section className="card fx-rail-card">
            <div className="card-head"><h2 className="fx-cap fx-rail-cap">Rates, net of fees</h2></div>
            <div className="fx-rate-list">
              {nominalRates.map(({ source, target, nominal }) => (
                <div className="fx-rate-row" key={source}>
                  <span className="fx-flag-box"><FxCurrencyFlag currency={source} /></span>
                  <span className="fx-rate-unit">1 {source}</span>
                  <strong className="num">{nominal ? `${fxNetRateLabel(nominal)} ${target}` : "—"}</strong>
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

      {displayedError ? <div className="fx-error"><Banner tone="bad" title={fxAvailabilityTitle(displayedError)}>{displayedError}</Banner></div> : null}

      <section className="card fx-history-card">
        <div className="card-head">
          <div>
            <h2 className="sect">Your conversions</h2>
            <p className="sect-sub">Every rate below is the rate you received, net of fees.</p>
          </div>
        </div>
        {fxQuery.isError && !fx ? (
          <DataErrorCard title="Could not load conversion history" onRetry={() => void fxQuery.refetch()}>
            The converter remains available, but historical FX activity could not be loaded.
          </DataErrorCard>
        ) : !fx ? (
          <LoadingCard title="Loading conversion history">Loading executed currency exchanges.</LoadingCard>
        ) : fx.exchanges.length === 0 ? (
          <div className="fx-history-empty"><Empty icon="swap" title="No conversions yet">Completed CHF/EUR conversions will appear here.</Empty></div>
        ) : (
          <div aria-label="Your conversions" className="fx-history" role="table">
            <div className="fx-history-row head" role="row">
              <span role="columnheader">Date</span>
              <span role="columnheader">Converted</span>
              <span role="columnheader">Rate, net of fees</span>
              <span role="columnheader">Received</span>
            </div>
            {fx.exchanges.map((exchange) => (
              <div className="fx-history-row" key={exchange.id} role="row">
                <span className="num fx-h-date" role="cell">{formatDate(exchange.executed_at)}{exchange.archived_at ? <span className="qa-history-note">Before QA reset</span> : null}</span>
                <span className="num fx-h-converted" role="cell">{fxMoneyLabel(exchange.source_currency, exchange.source_amount_minor)}</span>
                <span className="num fx-h-rate" role="cell">1 {exchange.source_currency} = {fxRateLabel(exchange.effective_net_rate)} {exchange.target_currency}</span>
                <strong className="num fx-h-received" role="cell">{fxMoneyLabel(exchange.target_currency, exchange.target_amount_minor)}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="fx-band">
        <section className="card fx-terms-card">
          <div className="card-head"><h2 className="microlabel">Your FX terms</h2></div>
          <div className="kv fx-kv">
            <div className="kv-row"><span className="k">Conversion fee, in the rate</span><span className="leader" /><span className="v">{preview ? formatRateBps(preview.platform_fee_bps) : nominalRates[0].nominal ? formatRateBps(nominalRates[0].nominal.platform_fee_bps) : "Shown with each rate"}</span></div>
            <div className="kv-row"><span className="k">Daily limit</span><span className="leader" /><span className="v">{fxTerms && fxTerms.daily_limit_chf_minor > 0 ? `${formatWholeAmount("CHF", fxTerms.daily_limit_chf_minor)} equivalent` : "Shown with each quote"}</span></div>
            {fxTerms && fxTerms.daily_limit_chf_minor > 0 ? (
              <div className="kv-row"><span className="k">Used today</span><span className="leader" /><span className="v num">{formatMoneyLabel("CHF", fxTerms.daily_limit_used_chf_minor)}</span></div>
            ) : null}
            <div className="kv-row"><span className="k">Executable quote lock</span><span className="leader" /><span className="v">{fxTerms && fxTerms.quote_ttl_seconds > 0 ? `${fxTerms.quote_ttl_seconds} seconds` : "Shown with each quote"}</span></div>
          </div>
        </section>
        <section className="card fx-advice-card">
          <div className="card-head"><h2 className="microlabel">How to avoid all of this</h2></div>
          <div className="fx-advice-body">
            <div className="fx-advice">Hold an account in the currency you invest in at your own bank. Fund it once, never convert again.</div>
            <div className="fx-advice-sub">We earn less when you do this. It is still the right advice.</div>
          </div>
        </section>
      </div>

      {quoteOpen && preview ? (
        <FxConfirmModal
          from={from}
          to={to}
          sourceMinor={liveQuote?.source_amount_minor ?? preview.source_amount_minor}
          feeMinor={liveQuote?.fee_minor ?? preview.fee_minor}
          targetMinor={liveQuote?.target_amount_minor ?? preview.target_amount_minor}
          rate={fxNetRateLabel(liveQuote ?? preview)}
          quote={liveQuote}
          quoteReceivedAt={quoteReceivedAt}
          quoteTtlSeconds={fxTerms?.quote_ttl_seconds}
          refreshing={quoteMutation.isPending}
          refreshError={error}
          onRefreshQuote={() => requestQuote()}
          onClose={() => setQuoteOpen(false)}
        />
      ) : null}
    </main>
  );
}

/** Seconds left on a quote, counted from when the browser received it (not browser clock vs server time). */
function quoteSecondsLeft(quote: Pick<FxQuote, "issued_at" | "expires_at"> | null, receivedAtMs: number, nowMs: number, fallbackTtlSeconds?: number) {
  if (!quote || receivedAtMs <= 0) return null;
  const ttlMs = Date.parse(quote.expires_at) - Date.parse(quote.issued_at);
  const lifetimeMs = Number.isFinite(ttlMs) && ttlMs > 0 ? ttlMs : (fallbackTtlSeconds ?? 0) * 1000;
  if (lifetimeMs <= 0) return null;
  return Math.max(0, Math.ceil((receivedAtMs + lifetimeMs - nowMs) / 1000));
}

function formatCountdown(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function FxConfirmModal({
  from,
  to,
  sourceMinor,
  targetMinor,
  feeMinor,
  rate,
  quote,
  quoteReceivedAt = 0,
  quoteTtlSeconds,
  refreshing = false,
  refreshError = "",
  onRefreshQuote,
  onClose
}: {
  from: string;
  to: string;
  sourceMinor: number;
  targetMinor: number;
  feeMinor: number;
  rate: string;
  quote: FxQuote | null;
  quoteReceivedAt?: number;
  quoteTtlSeconds?: number;
  refreshing?: boolean;
  refreshError?: string;
  onRefreshQuote?: () => void;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [ack, setAck] = useState(false);
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const codeRequest = useSensitiveActionCode(ActionEnum.fx);
  useAutoRequestEmailCode(codeRequest, !done);
  const executeMutation = useV1FxQuotesExecuteCreate();
  const secondsLeft = quoteSecondsLeft(quote, quoteReceivedAt, nowMs, quoteTtlSeconds);
  const quoteExpired = secondsLeft !== null && secondsLeft <= 0;
  const quoteId = quote?.id;
  useEffect(() => {
    // A new quote (refresh) restarts the countdown and asks for the terms again.
    setNowMs(Date.now());
    setAck(false);
    setError("");
    if (done || !quoteId) return undefined;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [done, quoteId]);
  const executeFx = () => {
    setError("");
    if (isFixturePreview) {
      if (codeRequest.pin.previewAccepts()) setDone(true);
      return;
    }
    if (!quote || !codeRequest.codeId) {
      setError("Request an email code before confirming the executable quote.");
      return;
    }
    if (quoteExpired) {
      setError("This quote has expired. Refresh the quote to get a new rate.");
      return;
    }
    executeMutation.mutate(
      {
        quoteId: quote.id,
        data: {
          // One key per quote: a retry of the same quote is not executed twice.
          idempotency_key: intentIdempotencyKey("fx-execute", { quote_id: quote.id }),
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          pin: codeRequest.pin.value
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setDone(true);
        },
        onError: (mutationError) => {
          if (codeRequest.pin.handleError(mutationError)) return;
          setError(apiErrorMessage(mutationError));
        }
      }
    );
  };
  if (done) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Exchange settled">
        <SuccessState title={`${formatMoneyLabel(to, targetMinor)} credited`}>
          The new {to} lot inherits the deadline of the consumed source lots. FX does not reset the holding clock.
        </SuccessState>
      </Modal>
    );
  }
  return (
    <Modal
      busy={executeMutation.isPending}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ack || code.length < 6 || !codeRequest.pin.ready || (!isFixturePreview && !codeRequest.codeId) || executeMutation.isPending || quoteExpired || refreshing} variant="primary" onClick={executeFx}>{executeMutation.isPending ? "Executing..." : "Confirm exchange"}</Button></>}
      onClose={onClose}
      title="Confirm currency exchange"
    >
      <div className="col gap-16 acct-modal">
        {quoteExpired ? (
          <Banner
            actions={onRefreshQuote ? <Button disabled={refreshing} size="sm" variant="primary" onClick={onRefreshQuote}>{refreshing ? "Refreshing..." : "Refresh quote"}</Button> : undefined}
            icon="clock"
            tone="warn"
            title="This quote has expired"
          >
            Get a new quote to see the current rate. Nothing was exchanged.
          </Banner>
        ) : (
          <Banner icon="clock" tone="info" title="Executable quote locked">
            {secondsLeft !== null
              ? <>This rate is fixed for <strong aria-live="off" className="num fx-quote-countdown">{formatCountdown(secondsLeft)}</strong>. Confirm before it runs out.</>
              : "This rate is fixed for a short time. Confirm before it runs out."}
          </Banner>
        )}
        <Review rows={[
          { label: "You exchange", value: formatMoneyLabel(from, sourceMinor) },
          { label: "Rate, net of fees", value: `1 ${from} = ${rate} ${to}` },
          { label: "Fee, included in the rate", value: formatMoneyLabel(to, feeMinor) },
          { label: "You receive", value: formatMoneyLabel(to, targetMinor), total: true }
        ]} />
        <SensitiveActionFields code={code} codeRequest={codeRequest} onCodeChange={setCode} onContinue={executeFx} />
        <Banner tone="warn" title="Inherited ageing deadline">The target balance inherits the earliest consumed source-lot deadline. It does not start a fresh holding period.</Banner>
        <Check checked={ack} id="fx-ack" onChange={setAck}>I accept the currency-exchange terms and understand the rate, fee and inherited deadline.</Check>
        {codeRequest.error || error || (quoteExpired && refreshError) ? <Banner tone="bad" title="Could not execute FX">{codeRequest.error || error || refreshError}</Banner> : null}
      </div>
    </Modal>
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

function pfMoneyLabel(currency: string, amountMinor: number) {
  return formatMoneyLabel(currency, amountMinor);
}

function pfPaysLabel(repaymentType: string) {
  if (repaymentType === "bullet_periodic_interest") return "monthly int.";
  if (repaymentType.startsWith("interest_only")) return "interest first";
  return "monthly";
}

function pfShortDate(iso: string) {
  const date = new Date(`${iso}T00:00:00`);
  const now = platformTodayLocalDate();
  const sameYear = date.getFullYear() === now.getFullYear();
  const label = date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return sameYear ? label : `${label} ${date.getFullYear()}`;
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
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const listener = (event: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", listener);
    // Keyboard users land on the current sort option (or the first one).
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') ?? []);
    (items.find((item) => item.getAttribute("aria-checked") === "true") ?? items[0])?.focus();
    return () => document.removeEventListener("mousedown", listener);
  }, [open]);
  const activeLabel = options.find((option) => option.key === activeKey)?.label;
  const sortStateId = useId();
  // Menu keys: arrows move, Home/End jump, Escape or Tab closes and returns to the Sort button.
  const onMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="menuitemradio"]'));
    const index = items.findIndex((item) => item === document.activeElement);
    if (event.key === "Escape" || event.key === "Tab") {
      if (event.key === "Escape") event.preventDefault();
      setOpen(false);
      buttonRef.current?.focus();
      return;
    }
    const next = event.key === "ArrowDown" ? (index + 1) % items.length
      : event.key === "ArrowUp" ? (index - 1 + items.length) % items.length
        : event.key === "Home" ? 0
          : event.key === "End" ? items.length - 1 : -1;
    if (next < 0 || items.length === 0) return;
    event.preventDefault();
    items[next].focus();
  };
  return (
    <div className="fs-sort-wrap" ref={wrapRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-describedby={activeLabel ? sortStateId : undefined}
        className={`fs-pill${small ? " small" : ""}${open ? " on" : ""}`}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
        ref={buttonRef}
        type="button"
      >
        <span>Sort</span>
        <span aria-hidden="true" className="fs-arrows">↑↓</span>
      </button>
      {activeLabel ? <span className="sr-only" id={sortStateId}>Sorted by {activeLabel}, {dir === "asc" ? "ascending" : "descending"}</span> : null}
      {open ? (
        <div aria-label="Sort by" className="fs-menu" onKeyDown={onMenuKeyDown} ref={menuRef} role="menu">
          <div aria-hidden="true" className="fs-menu-cap">Sort by</div>
          {options.map((option) => {
            const on = option.key === activeKey;
            return (
              <button
                aria-checked={on}
                className={`fs-menu-item${on ? " on" : ""}`}
                key={option.key}
                onClick={() => {
                  onPick(option.key);
                  setOpen(false);
                  buttonRef.current?.focus();
                }}
                role="menuitemradio"
                tabIndex={-1}
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

function activityCategory(entry: ActivityEntry) {
  if (entry.activity_type === "primary_order") return "order";
  if (entry.activity_type === "fx_exchange") return "fx";
  if (entry.activity_type === "balance_penalty_charge") return "penalty";
  if (entry.activity_type === "withdrawal_request" && safeMetadataFlag(entry.metadata, "is_forced")) return "forced return";
  if (entry.activity_type === "withdrawal_request") return "withdrawal";
  if (entry.activity_type === "withdrawal_cancellation") return "withdrawal reversal";
  if (entry.activity_type === "repayment_distribution") return "income";
  if (entry.activity_type === "recovery_distribution") return "recovery";
  if (entry.activity_type === "secondary_listing") return "listing";
  if (entry.activity_type === "secondary_purchase") return "purchase";
  if (entry.activity_type === "secondary_sale") return "sale";
  if (entry.activity_type.startsWith("balance_")) {
    return sourceLabel(entry.activity_type.slice("balance_".length)).toLowerCase();
  }
  return safeMetadataCategory(entry.metadata);
}

// "email.magic_link_requested" -> "Magic link requested".
// "3" -> "v3"; generated statements ("reporting-v2") -> "v2".
function documentVersionLabel(version: string) {
  if (/^\d+$/.test(version)) return `v${version}`;
  const suffix = version.match(/-v(\d+)$/);
  return suffix ? `v${suffix[1]}` : version;
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

// Body of the Transactions page until slice S4 rebuilds it: today's activity list.
function ActivityPanel() {
  const activityQuery = useActivityData();
  const activity = activityQuery.data;
  if (activityQuery.isError && !activity) {
    return (
      <DataErrorCard title="Could not load transactions" onRetry={() => void activityQuery.refetch()}>
        We could not load your account activity.
      </DataErrorCard>
    );
  }
  if (!activity) return <ScreenLoading title="Transactions" />;
  // The portfolio page's "Activity" list, in its own page context.
  return (
    <div className="content pf-page">
      <ActivityTable entries={activity.entries} />
    </div>
  );
}

function ActivityTable({ entries, dense = false }: { entries: ActivityEntry[]; dense?: boolean }) {
  const fxEnabled = useFxFeature().enabled;
  return (
    <section className="pf-data-section">
      <header className="pf-data-heading">
        <h2 className="sect">Activity</h2>
        <p>Every deposit, investment, repayment, {fxEnabled ? "FX conversion " : ""}and market event in one timeline.</p>
      </header>
      {entries.length === 0 ? (
        <PortfolioEmptyState icon="clock" title="No activity yet">
          Deposits, investments, repayments, FX, and secondary-market activity will appear here.
        </PortfolioEmptyState>
      ) : (
      <div className="pf-data-table-wrap">
        <table className={`pf-data-table pf-activity-table stack-on-phone ${dense ? "dense" : ""}`}>
          <thead><tr><th>Date</th><th>Activity</th><th>Reference</th><th>Type</th><th className="num">Amount</th></tr></thead>
          <tbody>
            {entries.map((entry) => {
              const category = activityCategory(entry);
              return (
                <tr key={entry.id}>
                  <td className="mono muted" data-label="Date" style={{ fontSize: 12 }}>{formatDateTime(entry.occurred_at)}</td>
                  <td className="col-strong" data-label="Activity">
                    {activityTitle(entry)}
                    <ActivityStatusTag entry={entry} />
                    {entry.archived_at ? <span className="qa-history-note">Before QA reset</span> : null}
                  </td>
                  <td className="sub mono" data-label="Reference">{activityReference(entry)}</td>
                  <td data-label="Type"><ActivityTag category={category} /></td>
                  <td className="num" data-label="Amount"><ActivityAmount entry={entry} /></td>
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

const withdrawalActivityStatus: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral"; tooltip: string }> = {
  requested: { label: "Pending", tone: "warn", tooltip: "Requested and waiting for bank execution. The amount is already set aside from your balance." },
  finalized: { label: "Finalized", tone: "ok", tooltip: "Paid out to your verified IBAN." },
  cancelled: { label: "Cancelled", tone: "bad", tooltip: "Not paid out. The amount was returned to your balance (see the matching reversal line)." },
  returned: { label: "Returned to balance", tone: "ok", tooltip: "The cancelled withdrawal amount is available in your balance again." }
};

// Withdrawals show their outcome next to the title, so a cancelled request is not mistaken for a payout.
function ActivityStatusTag({ entry }: { entry: ActivityEntry }) {
  if (entry.activity_type !== "withdrawal_request" && entry.activity_type !== "withdrawal_cancellation") return null;
  const status = withdrawalActivityStatus[entry.status];
  if (!status) return null;
  return (
    <span className="activity-status-tag">
      <Chip tone={status.tone} tooltip={status.tooltip}>{status.label}</Chip>
    </span>
  );
}

function safeMetadataFlag(metadata: unknown, key: string) {
  return Boolean(metadata && typeof metadata === "object" && !Array.isArray(metadata) && (metadata as Record<string, unknown>)[key] === true);
}

function ActivityTag({ category }: { category: string }) {
  const tone = category === "income" || category === "deposit" || category === "sale" || category === "recovery" || category === "withdrawal reversal" ? "ok" : category === "cost" || category === "withdrawal" || category === "forced return" || category === "penalty" || category === "purchase" ? "bad" : category === "status" || category === "order" || category === "listing" ? "warn" : "neutral";
  return <Chip dot={false} tone={tone}>{category}</Chip>;
}

// `embedded`: the list without its page frame (the Reports page shows its own U33 head);
// `kinds`: only these document kinds (account_statement, annual_tax_information, acceptance_evidence).
function DocumentsScreen({ embedded = false, kinds }: { embedded?: boolean; kinds?: string[] } = {}) {
  const [type, setType] = useState<string>("All");
  const [error, setError] = useState("");
  const documentsQuery = useDocumentsData();
  const downloadMutation = useV1InvestorPortalDocumentsDownloadCreate();
  const documents = documentsQuery.data;
  const Frame = embedded ? "div" : "main";
  const frameClass = embedded ? "acct-page acct-documents" : "content acct-page acct-documents";
  if (documentsQuery.isError && !documents) {
    return (
      <Frame className={frameClass}>
        {embedded ? null : <PageHead description="Accepted terms, transaction evidence, statements and tax information. Self-scoped to your account." title="Documents" />}
        <DataErrorCard title="Could not load documents" onRetry={() => void documentsQuery.refetch()}>
          We could not load your self-service document list.
        </DataErrorCard>
      </Frame>
    );
  }
  if (!documents) return <ScreenLoading title={embedded ? "Reports" : "Documents"} />;
  const listed = kinds ? documents.documents.filter((document) => kinds.includes(document.document_kind)) : documents.documents;
  const rows = listed.filter((document) => type === "All" || document.document_type === type);
  const types = ["All", ...Array.from(new Set(listed.map((document) => document.document_type)))];
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
    <Frame className={frameClass}>
      {embedded ? null : <PageHead description="Accepted document history, transaction evidence, statements and tax information. Self-scoped to your account." title="Documents" />}
      <div className="col gap-12 acct-alerts">
        <Banner tone="neutral" title="Informational only">{documents.disclaimer}</Banner>
        {error ? <Banner tone="bad" title="Download failed">{error}</Banner> : null}
      </div>
      <div className="doc-filter-bar">
        <div aria-label="Document type" className="tabs doc-type-tabs" role="group">
          {types.map((item) => <button aria-pressed={type === item} className={type === item ? "on" : ""} key={item} onClick={() => setType(item)} type="button">{item}</button>)}
        </div>
        <span className="results-count">{pluralize(rows.length, "document")}</span>
      </div>
      <section className="card acct-table-card">
        {rows.length === 0 ? (
          <div className="portal-table-empty">
            <Empty icon="doc" title="No documents match this filter">
              Choose another document type, or return later after accepting terms or generating a statement.
            </Empty>
          </div>
        ) : (
          <div className="portal-data-surface">
            <div className="tbl-wrap">
              <table className="tbl portal-data-table documents-data-table stack-on-phone"><thead><tr><th>Document</th><th>Type</th><th>Version</th><th>Context</th><th>Date</th><th className="num">Artifact</th><th /></tr></thead>
              <tbody>{rows.map((document) => (
                <tr key={document.id}>
                  <td data-label="Document">
                    <div className="doc-title-cell">
                      <Icon className="doc-title-icon" name="doc" size={16} />
                      <span>
                        <span className="doc-title">{document.title}</span>
                        {document.template_title ? <span className="sub">{document.template_title}</span> : null}
                      </span>
                    </div>
                  </td>
                  <td data-label="Type"><Chip dot={false} tone={document.document_type === "Risk" ? "warn" : "neutral"}>{document.document_type}</Chip></td>
                  <td className="doc-muted" data-label="Version">{documentVersionLabel(document.version)}</td>
                  <td className="doc-muted doc-context" data-label="Context">{document.context_label}</td>
                  <td className="doc-muted doc-date" data-label="Date">{formatDate(document.date)}</td>
                  <td className="num doc-muted" data-label="Artifact">{document.generated_on_request ? "On request" : document.content_hash ? "Evidence" : "-"}</td>
                  <td className="right doc-downloads-cell">
                    <div className="doc-downloads">
                      {document.output_formats.includes("csv") ? <Button disabled={downloadMutation.isPending} size="sm" onClick={() => downloadDocument(document, "csv")}>CSV</Button> : null}
                      {document.output_formats.includes("zip") ? <Button disabled={downloadMutation.isPending} size="sm" onClick={() => downloadDocument(document, "zip")}>ZIP</Button> : null}
                      <Button disabled={downloadMutation.isPending} icon="download" size="sm" onClick={() => downloadDocument(document, "pdf")}>PDF</Button>
                    </div>
                  </td>
                </tr>
              ))}</tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </Frame>
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

function NotificationsScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const notificationsQuery = useNotificationsData(100);
  const readActions = useNotificationReadActions();
  const payload = notificationsQuery.data;
  if (notificationsQuery.isError && !payload) {
    return (
      <ScreenError title="Notifications" onRetry={() => void notificationsQuery.refetch()}>
        We could not load notification delivery status. Retry once the API connection is restored.
      </ScreenError>
    );
  }
  if (!payload) return <ScreenLoading title="Notifications" />;
  const openNotification = (notification: InvestorNotification) => {
    if (notification.unread) void readActions.markRead(notification.id).catch(() => undefined);
    const target = notificationRoute(notification);
    if (target.name !== "notifications") goTo(setRoute, target.name, target.params);
  };
  return (
    <main className="content acct-page acct-notifications">
      <PageHead
        actions={
          <>
            {payload.unread_count > 0 ? <Chip tone="warn">{payload.unread_count} unread</Chip> : <Chip tone="ok">Up to date</Chip>}
            <Button disabled={payload.unread_count === 0} icon="check" onClick={() => void readActions.markAllRead().catch(() => undefined)} size="sm">
              Mark all as read
            </Button>
          </>
        }
        description="Email delivery status, operational notices, and investor messages. Open a notice to go to the loan, holding or balance it is about."
        title="Notifications"
      />
      <Card>
        {payload.notifications.length === 0 ? (
          <Empty icon="bell" title="No notifications yet">
            Emails, confirmations, balance reminders, and operational notices will appear here.
          </Empty>
        ) : (
          <div className="notice-list">
            {payload.notifications.map((notification) => {
              const failed = notification.status === "failed" || notification.status === "dead_letter";
              const hasTarget = notificationRoute(notification).name !== "notifications";
              return (
                <div className={`notice-row${failed ? " is-failed" : ""}${notification.unread ? " is-unread" : ""}`} key={notification.id}>
                  <span className="notice-icon"><Icon className={failed ? "neg" : "muted"} name="bell" size={17} /></span>
                  <div className="notice-content">
                    {hasTarget ? (
                      <button className="notice-title notice-open" onClick={() => openNotification(notification)} type="button">
                        {notification.title}
                        <Icon name="arrowR" size={14} />
                      </button>
                    ) : (
                      <div className="notice-title">{notification.title}</div>
                    )}
                    <p className="notice-body">{notification.body}</p>
                    <div className="notice-meta">
                      <span>{formatDateTime(notification.created_at)}</span>
                      <span>{notification.topic_label}</span>
                    </div>
                  </div>
                  <div className="notice-status">
                    {notification.unread ? <Chip dot tone="info">Unread</Chip> : null}
                    <Chip status={notification.status} />
                    {notification.unread ? (
                      <Button aria-label={`Mark "${notification.title}" as read`} onClick={() => void readActions.markRead(notification.id).catch(() => undefined)} size="sm" variant="ghost">
                        Mark as read
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
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

type SettingsSection = "profile" | "verification" | "pin" | "payout" | "communication" | "support";

function SettingsScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const queryClient = useQueryClient();
  const [section, setSection] = useState<SettingsSection>("profile");
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
  const readonly = isReadonlyImpersonationActive();
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || fixtureProfile.initials;
  const summaries = balances.data?.summaries ?? [];
  const identityRows = [
    name ? { label: "Name", value: name } : null,
    country ? { label: "Country", value: country } : null,
    memberSince ? { label: "Member since", value: formatDate(memberSince) } : null
  ].filter((row): row is { label: string; value: string } => row !== null);
  const sections: Array<{ key: SettingsSection; label: string; icon: IconName; description: string }> = [
    { key: "profile", label: "Profile", icon: "user", description: "The details of your investor account." },
    { key: "verification", label: "Verification", icon: "shield", description: "Identity and phone checks for your account." },
    { key: "pin", label: "PIN", icon: "lock", description: "Your 6-digit PIN confirms investments, withdrawals and bank changes with the email code." },
    { key: "payout", label: "Payout accounts", icon: "building", description: "Bank accounts in your name for withdrawals and forced returns." },
    { key: "communication", label: "Communication", icon: "mail", description: "Choose the optional emails you receive." },
    { key: "support", label: "Support & account", icon: "help", description: "Answers to common questions and how to reach support." }
  ];
  const current = sections.find((item) => item.key === section) ?? sections[0];

  return (
    <main className="content acct-page acct-settings">
      <PageHead description="Profile, verification, payout accounts and preferences." title="Profile & Settings" />
      <div className="card acct-settings-card">
        <aside className="acct-settings-aside">
          <div className="acct-settings-user">
            <span aria-hidden="true" className="acct-settings-avatar">{initials}</span>
            <div className="acct-settings-who">
              {name ? <div className="acct-settings-name">{name}</div> : null}
              {email ? <div className="acct-settings-email">{email}</div> : null}
            </div>
          </div>
          {summaries.length > 0 ? (
            <div className="acct-settings-balance">
              <div className="bxm-label">Account balance</div>
              {summaries.map((item, index) => (
                <div className={index === 0 ? "acct-settings-balance-main num" : "acct-settings-balance-sub num"} key={item.currency}>
                  {formatMoneyMinor(item.total_available_minor, item.currency)} <span className="acct-settings-ccy">{item.currency}</span>
                </div>
              ))}
            </div>
          ) : null}
          <nav aria-label="Settings sections" className="acct-settings-menu">
            {sections.map((item) => (
              <button
                aria-current={section === item.key ? "true" : undefined}
                className={section === item.key ? "on" : ""}
                key={item.key}
                onClick={() => {
                  setSection(item.key);
                  // On narrow screens the section opens below the menu; bring it into view.
                  if (window.matchMedia?.("(max-width: 991px)").matches) {
                    document.getElementById("acct-settings-title")?.scrollIntoView?.({ block: "start", behavior: "smooth" });
                  }
                }}
                type="button"
              >
                <Icon className="acct-settings-menu-icon" name={item.icon} size={17} />
                <span>{item.label}</span>
                <Icon className="acct-settings-menu-chev" name="chevR" size={15} />
              </button>
            ))}
          </nav>
        </aside>

        <section aria-labelledby="acct-settings-title" className="acct-settings-main">
          <div className="acct-settings-head">
            <div>
              <h2 id="acct-settings-title">{current.label}</h2>
              <p>{current.description}</p>
            </div>
            {section === "payout" ? (
              <Button disabled={readonly} size="sm" onClick={() => setShowPayoutModal(true)}>Add/update IBAN</Button>
            ) : null}
          </div>

          {section === "profile" ? (
            <>
              {identityRows.length > 0 ? (
                <div className="acct-data-group">
                  <div className="acct-data-head">Identity</div>
                  <dl className="acct-data-list">
                    {identityRows.map((row) => (
                      <div className="acct-data-item" key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>
                    ))}
                  </dl>
                </div>
              ) : null}
              {email ? (
                <div className="acct-data-group">
                  <div className="acct-data-head">Contact</div>
                  <dl className="acct-data-list">
                    <div className="acct-data-item"><dt>Email</dt><dd>{email}</dd></div>
                  </dl>
                </div>
              ) : null}
              <p className="acct-settings-note">Name or email changes are handled through support after identity re-verification.</p>
            </>
          ) : null}

          {section === "verification" ? (
            <div className="acct-box">
              <div className="acct-row">
                <div className="acct-row-text"><Icon className="acct-row-icon" name="shield" size={16} /><span className="acct-row-title">Identity (KYC/AML)</span></div>
                <div className="acct-row-actions">{kycStatus ? <Chip tone={kycChipTone(kycStatus)}>{humanizeToken(kycStatus)}</Chip> : <span className="muted">-</span>}</div>
              </div>
              <div className="acct-row">
                <div className="acct-row-text"><Icon className="acct-row-icon" name="phone" size={16} /><span className="acct-row-title">{phone ? `Phone ${phone}` : "Phone"}</span></div>
                <div className="acct-row-actions">{phoneVerified === undefined ? <span className="muted">-</span> : <Chip status={phoneVerified ? "verified" : "pending"} tone={phoneVerified ? "ok" : "neutral"} />}</div>
              </div>
            </div>
          ) : null}

          {section === "pin" ? <SettingsPinPanel readonly={readonly} /> : null}

          {section === "payout" ? (
            <div className="col gap-16">
              {balances.isError && !isFixturePreview ? <Banner tone="bad" title="Could not load payout accounts">Retry after signing in or when the API connection is restored.</Banner> : null}
              {payoutInstructions.length === 0 ? (
                <p className="acct-settings-note">No payout IBAN is on file yet. Add one so Garanta can review it for withdrawals and forced-return handling.</p>
              ) : (
                <div className="acct-box">
                  {payoutInstructions.map((instruction) => (
                    <div className="acct-row" key={instruction.id}>
                      <div className="acct-row-text">
                        <span>
                          <span className="acct-iban num">{instruction.destination_iban}</span>
                          <span className="acct-row-sub">{instruction.currency} · {instruction.destination_account_name}</span>
                        </span>
                      </div>
                      <div className="acct-row-actions">
                        <Chip tone={instruction.is_verified_usable ? "ok" : "warn"}>
                          {instruction.is_verified_usable ? "Verified usable" : "Pending Garanta verification"}
                        </Chip>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <Banner tone="info" title="Verification required">Submitting a new payout IBAN does not make it usable automatically. Garanta must verify the account before it can be used for withdrawals or forced returns.</Banner>
            </div>
          ) : null}

          {section === "communication" ? (
            <div className="col gap-16">
              <div className="acct-box">
                <label className="acct-row acct-toggle-row" style={{ cursor: readonly ? "not-allowed" : "pointer" }}>
                  <span className="acct-row-text">
                    <span>
                      <span className="acct-row-title">Product updates and newsletter</span>
                      <span className="acct-row-sub">Transactional emails are mandatory.</span>
                    </span>
                  </span>
                  <span className="acct-row-actions">
                    <input checked={marketing} className="acct-checkbox" disabled={readonly || marketingMutation.isPending} onChange={(event) => changeMarketingConsent(event.target.checked)} type="checkbox" />
                  </span>
                </label>
              </div>
              {marketingError ? <Banner tone="bad" title="Could not update preference">{marketingError}</Banner> : null}
            </div>
          ) : null}

          {section === "support" ? (
            <div className="acct-box">
              <div className="acct-row">
                <div className="acct-row-text"><Icon className="acct-row-icon" name="info" size={16} /><span className="acct-row-title">Help & FAQ</span></div>
                <div className="acct-row-actions"><Button size="sm" onClick={() => goTo(setRoute, "faq")}>Open</Button></div>
              </div>
              <div className="acct-row">
                <div className="acct-row-text"><Icon className="acct-row-icon" name="mail" size={16} /><span className="acct-row-title">Email support</span></div>
                <div className="acct-row-actions"><a className="acct-mail" href={`mailto:${supportEmail}`}>{supportEmail}</a></div>
              </div>
            </div>
          ) : null}
        </section>
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
  const canSubmit = hasValidPayoutDetails && codeRequest.pin.ready && (isFixturePreview || (codeRequest.codeId && code.length >= 6));

  const submit = () => {
    setError("");
    if (isFixturePreview) {
      if (codeRequest.pin.previewAccepts()) setDone(true);
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
          sensitive_action_code: code,
          pin: codeRequest.pin.value
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setDone(true);
        },
        onError: (mutationError) => {
          if (codeRequest.pin.handleError(mutationError)) return;
          setError(apiErrorMessage(mutationError));
        }
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
      <div className="col gap-16 acct-modal">
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
        <SensitiveActionFields code={code} codeRequest={codeRequest} onCodeChange={setCode} onContinue={submit} />
        {codeRequest.expiresAt ? <p className="acct-modal-note">Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
        {codeRequest.error || error ? <Banner tone="bad" title="Could not submit payout IBAN">{codeRequest.error || error}</Banner> : null}
      </div>
    </Modal>
  );
}

// Account statuses that block login and financial access (set by an admin).
const blockedAccountStatuses = new Set(["restricted", "locked", "closed"]);
const lenderAccountTypes = new Set(["natural_person_lender", "legal_entity_lender_representative"]);

// After login, an account without a PIN (every account created before ACC-DEC-009)
// creates it here before the portal opens. Outside registration this needs an email code.
function PinGateScreen({
  onCreated,
  onSignOut,
  setRoute,
  signOutError,
  signOutLabel
}: {
  onCreated: () => void;
  onSignOut: () => void;
  setRoute: (route: AppRoute) => void;
  signOutError: string;
  signOutLabel: string;
}) {
  const { status, isLoading, query } = usePinStatus();
  return (
    <UserSkin>
      <AuthShell onClose={() => goTo(setRoute, "public")} setRoute={setRoute}>
        <div className="auth-card">
          <div className="auth-form pin-gate">
            <AuthStatusIcon name="lock" />
            <div className="auth-head">
              <h2>Create your PIN</h2>
              <p>
                Before you continue: you will enter this 6-digit PIN with the email code for every
                investment, withdrawal and bank change.
              </p>
            </div>
            {isLoading ? (
              <ScreenLoading title="Loading" />
            ) : query.isError && !isFixturePreview ? (
              <Banner actions={<Button size="sm" onClick={() => void query.refetch()}>Retry</Button>} tone="bad" title="Could not load your account">
                Check your connection and try again.
              </Banner>
            ) : (
              <CreatePinForm
                footer={<Button variant="link" onClick={onSignOut}>{signOutLabel}</Button>}
                requiresEmailCode={status?.setup_requires_email_code ?? true}
                onSaved={onCreated}
              />
            )}
            {signOutError ? <Banner tone="bad" title="Could not sign out">{signOutError}</Banner> : null}
          </div>
        </div>
      </AuthShell>
    </UserSkin>
  );
}

function AccountBlockedScreen({ status }: { status: string }) {
  const statusWord = status === "locked" ? "locked" : status === "closed" ? "closed" : "restricted";
  const supportLink = <a href={`mailto:${supportEmail}`}>{supportEmail}</a>;
  return (
    <main className="content narrow acct-page acct-blocked">
      <PageHead description="Your balances, investments and loans are not available right now." title="Account access" />
      <section aria-label="Account status" className="card acct-blocked-card">
        <Banner icon="lock" tone="bad" title={`Your account is ${statusWord}`}>
          {statusWord === "closed" ? (
            <>This account has been closed. If you have questions, contact support at {supportLink}.</>
          ) : (
            <>
              You cannot view or move money while your account is {statusWord}. Please contact support at{" "}
              {supportLink} for further details.
            </>
          )}
        </Banner>
        <div className="acct-blocked-actions">
          <a className="btn btn-primary" href={`mailto:${supportEmail}`}>
            <Icon name="mail" size={15} />
            Contact support
          </a>
        </div>
      </section>
    </main>
  );
}

function KycStatusScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const statusQuery = useV1KycStatusRetrieve({
    query: {
      enabled: !isFixturePreview,
      retry: false,
      // The portal gate already asked; never re-run a failed lookup just because this screen mounted.
      retryOnMount: false,
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
  // A case that waits for an admin decision cannot be restarted by the investor; re-verification
  // is open only when an admin requested it (the case is then no longer flagged for review).
  const canStartKyc =
    !isFixturePreview &&
    !statusQuery.data?.manual_review_required &&
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
        : "Verification under review";
  const bannerMessage = isApproved
    ? "Financial access is available if phone verification and account status are also valid."
    : canStartKyc
      ? "Start identity verification with Didit. After you finish capture, this page will wait for the provider and compliance result."
      : isWaitingForProvider
        ? `Your identity capture has been submitted. We are waiting for Didit and ${operatorName} compliance to confirm the result. This page updates automatically. If it remains here for more than a few minutes, contact ${supportEmail}.`
        : `Your verification is under review. We will contact you. Financial actions stay locked until ${operatorName} completes the review. Contact ${supportEmail} with any questions.`;

  if (!isFixturePreview && statusQuery.isPending && statusQuery.dataUpdatedAt === 0 && statusQuery.errorUpdatedAt === 0) {
    return <ScreenLoading title="Verification" />;
  }

  return (
    <main className="content narrow acct-page acct-kyc">
      <PageHead description="KYC provider handoff and Garanta compliance status." title="Verification" />
      <section aria-labelledby="acct-kyc-status" className="card acct-kyc-card">
        <h2 className="bxm-label acct-group-label" id="acct-kyc-status">Status</h2>
        <div className="acct-box acct-kyc-steps">
          <KycTimeline current={isApproved ? "approved" : kycStatus === "not_started" ? "pending" : "manual_review"} />
        </div>
        <div className="col gap-12 acct-kyc-notes">
          {statusQuery.isError && !isFixturePreview ? (
            <Banner tone="bad" title="Could not load KYC status">
              The verification service did not answer.{" "}
              <button className="btn btn-sm" disabled={statusQuery.isFetching} onClick={() => void statusQuery.refetch()} type="button">
                Retry
              </button>
            </Banner>
          ) : null}
          <Banner tone={isApproved ? "ok" : "info"} title={bannerTitle}>
            {bannerMessage}
          </Banner>
        </div>
        {canStartKyc || statusQuery.data?.financial_access_allowed || isFixturePreview ? (
          <div className="acct-kyc-actions">
            {canStartKyc ? (
              <Button disabled={sessionMutation.isPending} onClick={startKyc}>
                {sessionMutation.isPending ? "Starting Didit..." : "Start Didit verification"}
              </Button>
            ) : null}
            {statusQuery.data?.financial_access_allowed || isFixturePreview ? (
              <Button variant="primary" onClick={() => goTo(setRoute, "dashboard")}>Back to dashboard</Button>
            ) : null}
          </div>
        ) : null}
        {error ? <div className="acct-kyc-error"><Banner tone="bad" title="Could not start KYC">{error}</Banner></div> : null}
      </section>
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

// Texts that offer currency exchange follow the FX switch (fx.enabled, owner decision 2026-10-16).
function faqSections(fxEnabled: boolean): FaqSection[] {
  return [
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
    summary: `${autoReturnRuleText()} Investment eligibility depends on the loan funding window.`,
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
            Up to {AUTO_RETURN_AFTER_DAYS} days. Money that is not invested goes back to your bank automatically
            after {AUTO_RETURN_AFTER_DAYS} days. To invest, the money must cover the full remaining funding period
            of the loan you choose within those days. For example, a 30-day remaining subscription window needs
            at least 30 days of holding time left; a 10-day window needs 10. Exchanging currency does not restart
            this count.
          </>
        )
      },
      {
        question: `What happens after ${AUTO_RETURN_AFTER_DAYS} days?`,
        answer: (
          <>
            Day {AUTO_RETURN_AFTER_DAYS} is the last day: you can withdraw the money until the end of that day
            (Europe/Zurich), but you can no longer invest{fxEnabled ? " or exchange" : ""} it. The next day we send it back
            automatically to your verified payout IBAN. If there is no verified IBAN, the money stays on your
            balance and we ask you to add one. Money may not stay longer than 60 days, the legal limit: after
            day 60 it enters penalty mode and money-moving actions are blocked until a verified IBAN is on file.
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
            Every fee that applies to an action — for example the secondary-market seller fee
            {fxEnabled ? " or the currency-exchange fee" : ""} — is shown in that flow before you confirm, together
            with the exact amounts.
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
    title: fxEnabled ? "Secondary market and FX" : "Secondary market",
    summary: fxEnabled
      ? "Selling and currency conversion are available only under platform controls."
      : "Selling is available only under platform controls.",
    items: [
      {
        question: "Can I sell before maturity?",
        answer: (
          <>
            You can list an entire holding on the secondary market when the loan is paid on time. Liquidity is
            not guaranteed. Loans that are late or in default cannot be listed, and an open listing is cancelled
            when its loan becomes late or defaulted.
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
      ...(fxEnabled
        ? [
          {
            question: "Does converting currency reset the ageing clock?",
            answer: (
              <>
                No. FX is a settlement function, not a way to restart deadlines. Converted balance inherits the
                deadlines of the funds you converted — it never receives a fresh holding period.
              </>
            )
          }
          ]
        : []),
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
}

// Questions of the portal Help page (FaqScreen).
function FaqContent() {
  const [open, setOpen] = useState("0-0");
  const fxEnabled = useFxFeature().enabled;
  const faqTopics = faqSections(fxEnabled);
  const title = "Help & FAQ";
  const description = `Plain-English answers on onboarding, balances, orders, risk, ${fxEnabled ? "FX, " : ""}documents and the secondary market.`;
  const sectionId = (index: number) => `faq-topic-${index + 1}`;

  const intro = (
    <div className="faq-intro">
      <div>
        <div className="eyebrow">Before investing</div>
        <h2>Know the operating rules before moving money</h2>
        <p>
          {platformName} is built for peer-to-peer business lending. These answers summarize the user-facing
          flow; the legally binding wording is the document version you accept in the platform.
        </p>
      </div>
    </div>
  );

  const support = (
    <div className="faq-support">
      <div className="faq-support-title">Need help?</div>
      <a href={`mailto:${supportEmail}`}>{supportEmail}</a>
    </div>
  );

  const sections = (
    <div className="faq-sections">
      {faqTopics.map((section, sectionIndex) => (
        <section aria-labelledby={`${sectionId(sectionIndex)}-title`} className="faq-section" id={sectionId(sectionIndex)} key={section.title}>
          <div className="faq-section-head">
            <h2 id={`${sectionId(sectionIndex)}-title`}>{section.title}</h2>
            <p>{section.summary}</p>
          </div>
          <div className="faq-rows">
            {section.items.map((item, itemIndex) => {
              const key = `${sectionIndex}-${itemIndex}`;
              const isOpen = open === key;
              const answerId = `faq-answer-${key}`;
              return (
                <div className={`faq-row ${isOpen ? "open" : ""}`} key={item.question}>
                  <button
                    aria-controls={isOpen ? answerId : undefined}
                    aria-expanded={isOpen}
                    className="faq-q"
                    onClick={() => setOpen(isOpen ? "" : key)}
                    type="button"
                  >
                    <span>{item.question}</span>
                    <Icon className="faq-q-icon" name={isOpen ? "minus" : "plus"} size={18} />
                  </button>
                  {isOpen ? <div className="faq-a" id={answerId}>{item.answer}</div> : null}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );

  const risk = (
    <Banner tone="warn" title="Risk warning">
      Investing through {platformName} involves risk of capital loss, borrower default, late payment,
      illiquidity, enforcement cost and no guaranteed return.
    </Banner>
  );

  return (
    <div className="faq-v-portal">
      <PageHead description={description} title={title} />
      <div className="faq-layout">
        <div className="faq-main">
          {intro}
          {sections}
          {risk}
        </div>
        <aside className="faq-aside">{support}</aside>
      </div>
    </div>
  );
}

// Portal Help page (design "help"): FaqContent is wrapped here and left unchanged. Its own
// page head repeats this page head and is hidden inside the wrapper (see skin/account.css).
function FaqScreen() {
  const fxEnabled = useFxFeature().enabled;
  return (
    <main className="content acct-page portal-help">
      <PageHead
        description={`Plain-English answers on onboarding, balances, orders, risk, ${fxEnabled ? "FX, " : ""}documents and the secondary market.`}
        title="Help"
      />
      <div className="portal-help-grid">
        <section aria-labelledby="portal-help-questions" className="card portal-help-faq">
          <div className="card-head"><h2 id="portal-help-questions">Questions</h2></div>
          <div className="portal-help-faq-body">
            <FaqContent />
          </div>
        </section>
        <aside className="portal-help-aside">
          <section aria-labelledby="portal-help-contact" className="card portal-help-contact">
            <div className="card-head"><h2 id="portal-help-contact">Contact us</h2></div>
            <dl className="portal-help-kv">
              <div><dt>Email</dt><dd><a href={`mailto:${supportEmail}`}>{supportEmail}</a></dd></div>
              <div><dt>Operator</dt><dd>{operatorName}</dd></div>
            </dl>
          </section>
        </aside>
      </div>
    </main>
  );
}

type InvestStep = "amount" | "review" | "confirm" | "done";

const investStepLabels = ["Amount", "Review and sign", "Done"];

/** Numbered step bar of the invest page. Review and the email confirmation both belong to step 02. */
function InvestStepBar({ step }: { step: InvestStep }) {
  const current = step === "amount" ? 0 : step === "done" ? 2 : 1;
  return (
    <ol aria-label="Investment steps" className="iv-steps">
      {investStepLabels.map((label, index) => (
        <li
          aria-current={index === current ? "step" : undefined}
          className={`iv-step${index < current ? " is-done" : ""}${index === current ? " is-current" : ""}`}
          key={label}
        >
          <span className="iv-step-index">{String(index + 1).padStart(2, "0")}</span>
          <span className="iv-step-label">{label}</span>
        </li>
      ))}
    </ol>
  );
}

/**
 * Page frame of the invest flow (design: project > Invest): page head, step bar, alerts, the form on
 * the left and the "Your investment" summary card with the actions in its grey footer on the right.
 */
function InvestPageFrame({
  loan,
  title,
  step,
  onBack,
  alerts,
  summary,
  footer,
  children
}: {
  loan: MarketplaceLoanDetail;
  title: string;
  step: InvestStep;
  onBack: () => void;
  alerts?: ReactNode;
  summary: Array<ComponentProps<typeof Review>["rows"]>;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const counterparty = isOriginatorClaimLoan(loan) ? loan.originator_name : borrowerDisclosureForLoan(loan).legal_name;
  return (
    <main className="content iv-page">
      <PageHead
        back={{ label: loan.title, onClick: onBack }}
        description={counterparty && counterparty !== loan.title ? `${loan.title} · ${counterparty}` : loan.title}
        title={title}
      />
      <InvestStepBar step={step} />
      {alerts ? <div className="iv-alerts">{alerts}</div> : null}
      <div className="iv-grid">
        <div className="iv-main">{children}</div>
        <aside className="card iv-summary">
          {summary.filter((rows) => rows.length > 0).map((rows, index) => (
            <div className="iv-summary-sec" key={index}>
              {index === 0 ? <h2 className="iv-summary-title">Your investment</h2> : null}
              <Review rows={rows} />
            </div>
          ))}
          {footer ? <div className="iv-summary-foot">{footer}</div> : null}
        </aside>
      </div>
    </main>
  );
}

/** The loan being invested in (design: chosen project tile at the top of the amount form). */
function InvestLoanChip({ loan }: { loan: MarketplaceLoanDetail }) {
  const term = loan.remaining_term_days === null ? `${loan.term_months} mo` : `${loan.remaining_term_days} days`;
  return (
    <div className="iv-chosen">
      <span aria-hidden="true" className="iv-chosen-icon"><Icon name="building" size={26} strokeWidth={1.4} /></span>
      <span className="iv-chosen-info">
        <span className="iv-chosen-name">{loan.title}</span>
        <span className="iv-chosen-text">
          {formatRateBps(marketplaceYieldBps(loan))} p.a. · {term} · {loan.currency} {formatMoneyMinor(marketplaceAvailableMinor(loan), loan.currency)} available now
        </span>
      </span>
    </div>
  );
}

/** Large pill amount input with the currency on the right (design: invest amount field). */
function InvestAmountInput({ currency, label, value, onChange }: { currency: string; label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="iv-amount">
      <input
        aria-label={label}
        className="input mono iv-amount-input"
        inputMode="decimal"
        // Keep the decimal comma and the thousands separators the app prints (' ’ and
        // spaces); the parser reads them and shows an error for anything ambiguous.
        onChange={(event) => onChange(event.target.value.replace(/[^0-9.,'\u2019\s]/g, ""))}
        placeholder="0.00"
        value={value}
      />
      <span aria-hidden="true" className="iv-amount-ccy">{currency}</span>
    </div>
  );
}

/** Where the money comes from (design: "Paid from" block). */
function InvestPaidFrom({ currency, investableBalanceMinor }: { currency: string; investableBalanceMinor: number }) {
  return (
    <div className="iv-field">
      <div className="iv-label">Paid from</div>
      <div className="iv-chosen">
        <span aria-hidden="true" className="iv-chosen-icon"><Icon name="wallet" size={26} strokeWidth={1.4} /></span>
        <span className="iv-chosen-info">
          <span className="iv-chosen-name">Investable {currency} balance</span>
          <span className="iv-chosen-text mono">{currency} {formatMoneyMinor(investableBalanceMinor, currency)}</span>
        </span>
      </div>
    </div>
  );
}

/** Result of the invest page with the ways onward ("refused": nothing was invested). */
function InvestDone({
  title,
  children,
  onBackToLoan,
  setRoute,
  outcome = "success"
}: {
  title: string;
  children: ReactNode;
  onBackToLoan: () => void;
  setRoute: (route: AppRoute) => void;
  outcome?: "success" | "refused";
}) {
  return (
    <div className="card iv-card iv-done">
      {outcome === "refused"
        ? <Banner tone="bad" title={title}>{children}</Banner>
        : <SuccessState title={title}>{children}</SuccessState>}
      <div className="iv-actions">
        <Button variant="primary" onClick={() => goTo(setRoute, "portfolio")}>My investments</Button>
        <Button onClick={onBackToLoan}>Back to the loan</Button>
        <Button onClick={() => goTo(setRoute, "market")}>Primary market</Button>
      </div>
    </div>
  );
}

type ClaimPurchaseAttempt = { quoteId: string; acceptanceKey: string; purchaseKey: string; acceptanceId: string | null };

function newClaimPurchaseAttempt(quoteId: string): ClaimPurchaseAttempt {
  return {
    quoteId,
    acceptanceKey: idempotencyKey("originator-claim-acceptance"),
    purchaseKey: idempotencyKey("originator-claim-purchase"),
    acceptanceId: null
  };
}

/** Legacy originator-claim purchase (immediate assignment): amount, executable quote, email code, done. */
function OriginatorClaimInvestFlow({
  loan,
  onClose,
  initialAmount,
  setRoute
}: {
  loan: MarketplaceLoanDetail;
  onClose: () => void;
  initialAmount?: string;
  setRoute: (route: AppRoute) => void;
}) {
  const queryClient = useQueryClient();
  const balances = useBalancesData().data;
  const investableLots = currentInvestableLotsForLoanCurrency(balances?.lots, loan);
  const investableBalanceMinor = sumLotAvailableMinor(investableLots);
  const maxInvest = Math.min(investableBalanceMinor, loan.fillable_amount_minor);
  const funds = { balanceMinor: currencyBalanceMinor(balances?.lots, loan.currency), eligibleMinor: investableBalanceMinor };
  const fundsBlock = noEligibleFundsReason(loan.currency, funds);
  const [amount, setAmount] = useState(initialAmount ?? "");
  const [step, setStep] = useState<InvestStep>("amount");
  const [ack1, setAck1] = useState(false);
  const [ack2, setAck2] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [quote, setQuote] = useState<OriginatorClaimQuoteResponse | null>(null);
  // The terms acceptance and the purchase key belong to one quote: a new quote (Reprice,
  // new amount) needs a new acceptance and a new key (audit A-37).
  const [claimAttempt, setClaimAttempt] = useState<ClaimPurchaseAttempt | null>(null);
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
      : investAmountLimitMessage({
          amountMinor,
          capacityMinor: loan.fillable_amount_minor,
          currency: loan.currency,
          funds,
          money: (minor) => `${loan.currency} ${formatMoneyMinor(minor, loan.currency)}`
        }) ?? undefined);

  const applyQuote = (nextQuote: OriginatorClaimQuoteResponse) => {
    setQuote(nextQuote);
    setClaimAttempt(newClaimPurchaseAttempt(nextQuote.quote_id));
    // New economics: the investor reviews and accepts them again.
    setAck1(false);
    setAck2(false);
    setStep("review");
  };

  const requestQuote = async () => {
    setError("");
    if (amountError || amountMinor <= 0) return;
    if (isFixturePreview) {
      const assignedPrincipal = Math.min(amountMinor, loan.remaining_capacity_minor);
      applyQuote({
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
      return;
    }
    try {
      const nextQuote = await quoteMutation.mutateAsync({
        loanId: loan.loan_id,
        data: { requested_cash_minor: amountMinor }
      });
      applyQuote(nextQuote);
    } catch (mutationError) {
      // A Swiss-borrower claim with no place left: reload the places.
      if (isSwissInvestorLimitError(mutationError)) void queryClient.invalidateQueries();
      setError(apiErrorMessage(mutationError));
    }
  };

  const confirmPurchase = async () => {
    if (!quote) return;
    setError("");
    if (isFixturePreview) {
      if (codeRequest.pin.previewAccepts()) setStep("done");
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
    let current = claimAttempt?.quoteId === quote.quote_id ? claimAttempt : newClaimPurchaseAttempt(quote.quote_id);
    try {
      const acceptance = current.acceptanceId
        ? { id: current.acceptanceId }
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
              idempotency_key: current.acceptanceKey
            }
          });
      current = { ...current, acceptanceId: acceptance.id };
      setClaimAttempt(current);
      await purchaseMutation.mutateAsync({
        quoteId: quote.quote_id,
        data: {
          document_acceptance_id: acceptance.id,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          pin: codeRequest.pin.value,
          idempotency_key: current.purchaseKey
        }
      });
      void queryClient.invalidateQueries();
      setStep("done");
    } catch (mutationError) {
      if (codeRequest.pin.handleError(mutationError)) return;
      if (isSwissInvestorLimitError(mutationError)) void queryClient.invalidateQueries();
      setError(apiErrorMessage(mutationError));
    }
  };

  const busy = quoteMutation.isPending || acceptanceMutation.isPending || purchaseMutation.isPending;
  const footer = step === "done"
    ? null
    : step === "confirm"
      ? <><Button onClick={() => setStep("review")}>Back</Button><Button disabled={code.length < 6 || !codeRequest.pin.ready || (!isFixturePreview && !codeRequest.codeId) || busy} variant="primary" onClick={() => void confirmPurchase()}>{busy ? "Purchasing..." : "Purchase claim"}</Button></>
      : step === "review"
        ? <><Button onClick={() => { setQuote(null); setClaimAttempt(null); setStep("amount"); }}>Reprice</Button><Button disabled={!ack1 || !ack2 || !quote} variant="primary" onClick={() => setStep("confirm")}>Continue</Button></>
        : <><Button onClick={onClose}>Cancel</Button><Button disabled={amountMinor <= 0 || Boolean(amountError) || quoteMutation.isPending || swissLoanFullForViewer(loan)} variant="primary" onClick={() => void requestQuote()}>{quoteMutation.isPending ? "Pricing..." : "Get executable quote"}</Button></>;

  const amountRows = [
    { label: "Investor yield", value: `${formatRateBps(loan.yield_bps)} effective annual · ACT/365` },
    { label: "Underlying borrower coupon", value: `${formatRateBps(loan.underlying_interest_rate_bps)} p.a.` },
    { label: "Maturity", value: loan.maturity_date ? formatDate(loan.maturity_date) : "Not available" },
    { label: "Available claim principal", value: `${loan.currency} ${formatMoneyMinor(loan.remaining_capacity_minor, loan.currency)}` }
  ];
  // Summary card: the claim details first, then the amounts (design: overview, then amount rows).
  const quoteRows = quote ? [
    [
      { label: "Loan", value: loan.title },
      { label: "Loan originator", value: loan.originator_name || "Loan originator" },
      { label: "Target yield", value: `${formatRateBps(quote.target_yield_bps)} effective annual · ACT/365` },
      { label: "Entitlement starts", value: formatDateTime(quote.entitlement_start_at) }
    ],
    [
      { label: "Cash consideration", value: `${quote.currency} ${formatMoneyMinor(quote.executable_cash_minor, quote.currency)}` },
      { label: "Legal principal assigned", value: `${quote.currency} ${formatMoneyMinor(quote.assigned_principal_minor, quote.currency)}` },
      { label: quote.premium_discount_minor >= 0 ? "Premium" : "Discount", value: `${quote.currency} ${formatMoneyMinor(Math.abs(quote.premium_discount_minor), quote.currency)}` }
    ]
  ] : [];
  const confirmRows = quote ? [
    [
      { label: "Yield", value: formatRateBps(quote.target_yield_bps) },
      { label: "Quote expires", value: formatDateTime(quote.expires_at) }
    ],
    [
      { label: "Cash consideration", value: `${quote.currency} ${formatMoneyMinor(quote.executable_cash_minor, quote.currency)}` },
      { label: "Principal assigned", value: `${quote.currency} ${formatMoneyMinor(quote.assigned_principal_minor, quote.currency)}` }
    ]
  ] : [];
  const summaryRows = step === "amount" || !quote ? [amountRows] : step === "confirm" ? confirmRows : quoteRows;

  return (
    <InvestPageFrame
      alerts={step === "amount" && fundsBlock
        ? <Banner tone="bad" title={fundsBlock.title}>{fundsBlock.detail}</Banner>
        : undefined}
      footer={footer}
      loan={loan}
      onBack={onClose}
      step={step}
      summary={summaryRows}
      title="Buy claim"
    >
      {step === "amount" ? (
        <div className="iv-form">
          <Banner tone="info" title="Immediate legal assignment">
            This is an existing final-borrower loan sold by {loan.originator_name || "the loan originator"}.
            BANXUM prices the remaining cash flows to the displayed yield and assigns the purchased claim immediately.
          </Banner>
          <InvestLoanChip loan={loan} />
          <Field error={amountError} hint={`Minimum ${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)} · up to ${loan.currency} ${formatMoneyMinor(maxInvest, loan.currency)}`} label="Cash amount to invest">
            <InvestAmountInput currency={loan.currency} label="Cash amount to invest" value={amount} onChange={setAmount} />
          </Field>
          <SwissInvestorLimitNote loan={loan} />
          <InvestPaidFrom currency={loan.currency} investableBalanceMinor={investableBalanceMinor} />
          {error ? <Banner tone="bad" title="Could not price this claim">{error}</Banner> : null}
        </div>
      ) : step === "review" && quote ? (
        <div className="iv-form">
          <Banner tone="neutral" title="Executable for five minutes">
            The cash price changes as time passes or the borrower repays. This quote expires {formatDateTime(quote.expires_at)}.
          </Banner>
          <div className="card iv-card iv-flows">
            <div className="eyebrow iv-card-cap">Your quoted cash flows</div>
            <div className="tbl-wrap">
              <table className="tbl"><thead><tr><th className="num">#</th><th>Due date</th><th className="num">Principal</th><th className="num">Interest</th><th className="num">Total</th></tr></thead><tbody>{quote.cash_flows.map((flow) => <tr key={`${flow.installment_number}-${flow.due_date}`}><td className="num muted">{flow.installment_number}</td><td>{formatDate(flow.due_date)}</td><td className="num">{formatMoneyMinor(flow.principal_minor, quote.currency)}</td><td className="num">{formatMoneyMinor(flow.interest_minor, quote.currency)}</td><td className="num col-strong">{formatMoneyMinor(flow.total_minor, quote.currency)}</td></tr>)}</tbody><tfoot className="schedule-totals"><tr><th colSpan={2}>Totals</th><th className="num">{formatMoneyMinor(quote.cash_flows.reduce((sum, row) => sum + row.principal_minor, 0), quote.currency)}</th><th className="num">{formatMoneyMinor(quote.cash_flows.reduce((sum, row) => sum + row.interest_minor, 0), quote.currency)}</th><th className="num">{formatMoneyMinor(quote.cash_flows.reduce((sum, row) => sum + row.total_minor, 0), quote.currency)}</th></tr></tfoot></table>
            </div>
          </div>
          <div className="card iv-card iv-sign">
            <Check checked={ack1} id="originator-claim-ack-1" onChange={setAck1}>I accept the <LegalDocLink category="primary_market_investment">primary-market investment terms and claim assignment</LegalDocLink>.</Check>
            <Check checked={ack2} id="originator-claim-ack-2" onChange={setAck2}>I acknowledge the <LegalDocLink category="risk_disclosure">risk disclosure</LegalDocLink>, originator servicing structure and possible capital loss.</Check>
            {!isFixturePreview && termsQuery.isError ? <Banner tone="bad" title="Investment terms unavailable">The current server-published investment terms could not be loaded.</Banner> : null}
          </div>
        </div>
      ) : step === "confirm" && quote ? (
        <div className="card iv-card iv-form">
          <Banner icon="lock" tone="info" title="Confirm this claim purchase">Enter the 6-digit email confirmation code and your PIN. A successful confirmation immediately assigns the claim and adds it to your portfolio.</Banner>
          <SensitiveActionFields code={code} codeRequest={codeRequest} onCodeChange={setCode} onContinue={() => void confirmPurchase()} />
          {codeRequest.error || error ? <Banner tone="bad" title="Could not purchase claim">{codeRequest.error || error}</Banner> : null}
        </div>
      ) : (
        <InvestDone setRoute={setRoute} title="Claim purchased" onBackToLoan={onClose}>
          The assigned final-borrower claim is now in your portfolio. Its immutable acceptance evidence is available in Documents.
        </InvestDone>
      )}
    </InvestPageFrame>
  );
}

// Invest flow as a page (design: project > Invest). Route: /marketplace/:loanId/invest.
function InvestScreen({ loanId, initialAmount, setRoute }: { loanId: string; initialAmount?: string; setRoute: (route: AppRoute) => void }) {
  const loanQuery = useLoanDetailData(loanId);
  const frozenAccount = useFrozenAccount();
  const loan = loanQuery.data;
  if (loanQuery.isError && !loan) {
    return isNotFoundError(loanQuery.error) ? (
      <LoanNotFound setRoute={setRoute} title="Invest" />
    ) : (
      <ScreenError title="Invest" onRetry={() => void loanQuery.refetch()}>
        We could not load this loan detail. Return to the marketplace or retry after the API is reachable.
      </ScreenError>
    );
  }
  if (!loan) return <ScreenLoading title="Invest" />;
  const backToLoan = () => goTo(setRoute, "loan", { loanId: loan.loan_id });
  // A closed loan is handled in InvestEntry when the page opens (JOURNEY-09, FRONTCODE-24):
  // a loan that fills while the investor is here keeps the flow, so the result shows.
  if (frozenAccount.frozen) {
    // Penalty mode blocks new orders (PAY-DEC-022): say so before any code is sent.
    return (
      <main className="content">
        <PageHead back={{ label: "Back to the loan", onClick: backToLoan }} title="Invest" />
        <Banner icon="lock" tone="bad" title="Financial actions frozen">{frozenActionReason(frozenAccount)}</Banner>
      </main>
    );
  }
  // A new loan or a new handed-over amount starts a fresh flow (new idempotency keys).
  const flowKey = `${loan.loan_id}:${initialAmount ?? ""}`;
  return <InvestEntry initialAmount={initialAmount} key={flowKey} loan={loan} onClose={backToLoan} setRoute={setRoute} />;
}

/** Why this invest page cannot take an order (closed loan, read-only view), or null. */
function investUnavailableReason(loan: MarketplaceLoanDetail) {
  if (isReadonlyImpersonationActive()) {
    return { title: "Read-only view", detail: "This is a read-only investor view. You can see the loan, but you cannot invest." };
  }
  if (!isOpenMarketplaceLoan(loan)) {
    return { title: "This loan is not open for investment", detail: "It is closed or fully funded. You can still read the loan page and its payments, or choose another loan on the primary market." };
  }
  return null;
}

// Decides once, when the page opens, whether the invest flow may start (FRONTCODE-24):
// a closed loan or the read-only view shows a notice and no email code is sent. A loan
// that fills while the investor is on the page keeps the flow, so the result shows.
function InvestEntry({
  loan,
  initialAmount,
  onClose,
  setRoute
}: {
  loan: MarketplaceLoanDetail;
  initialAmount?: string;
  onClose: () => void;
  setRoute: (route: AppRoute) => void;
}) {
  const [unavailable] = useState(() => investUnavailableReason(loan));
  if (unavailable) {
    return (
      <main className="content iv-page">
        <PageHead back={{ label: loan.title, onClick: onClose }} description={loan.title} title="Invest" />
        <div className="card iv-card iv-done">
          <Banner tone="neutral" title={unavailable.title}>{unavailable.detail}</Banner>
          <div className="iv-actions">
            <Button variant="primary" onClick={() => goTo(setRoute, "market")}>Primary market</Button>
            <Button onClick={onClose}>Back to the loan</Button>
          </div>
        </div>
      </main>
    );
  }
  return usesImmediateClaimAssignment(loan) ? (
    <OriginatorClaimInvestFlow initialAmount={initialAmount} loan={loan} onClose={onClose} setRoute={setRoute} />
  ) : (
    <InvestFlow initialAmount={initialAmount} loan={loan} onClose={onClose} setRoute={setRoute} />
  );
}

// One confirmation attempt of a primary order. The order, its terms acceptance and the
// allocation all record one amount, so the attempt (with its keys) is replaced whenever
// the amount changes or the investor goes back to the amount step (audit A-15).
type PrimaryOrderAttempt = {
  amountMinor: number;
  orderKey: string;
  acceptanceKey: string;
  allocationKey: string;
  orderId: string | null;
  acceptanceId: string | null;
};

function newPrimaryOrderAttempt(amountMinor: number): PrimaryOrderAttempt {
  return {
    amountMinor,
    orderKey: idempotencyKey("primary-order"),
    acceptanceKey: idempotencyKey("primary-acceptance"),
    allocationKey: idempotencyKey("primary-allocation"),
    orderId: null,
    acceptanceId: null
  };
}

// The server closed the order before allocation (for example a newer order replaced
// it). Nothing was invested; the next confirmation places a new order.
function isOrderNotPendingError(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 400) return false;
  const payload = error.payload as { code?: unknown } | null | undefined;
  return payload?.code === "order_not_pending";
}

/** Plain-English result of an allocated primary order, from the server's order. */
function primaryOrderOutcome(
  order: PrimaryInvestmentOrder,
  loan: MarketplaceLoanDetail,
  subscriptionClaim: boolean,
  money: (minor: number) => string
): { title: string; text: string; status: string; refused: boolean } {
  if (order.status === "closed_not_invested") {
    const reason = order.closed_reason.toLowerCase().includes("minimum")
      ? `Less than the minimum order of ${money(loan.minimum_investment_minor)} was left in this loan.`
      : "Other investors took the rest of this loan first.";
    return { title: "Order not placed", text: `${reason} Nothing was invested and no money moved.`, status: "Not invested", refused: true };
  }
  if (order.status === "partially_allocated") {
    return {
      title: "Order partly placed",
      text: `Only ${money(order.allocated_amount_minor)} was left in this loan. We reserved ${money(order.allocated_amount_minor)} of the ${money(order.requested_amount_minor)} you asked for. The rest stays in your balance.`,
      status: "Partly allocated",
      refused: false
    };
  }
  if (order.status === "closed_invested") {
    return {
      title: "Investment made",
      text: `${money(order.allocated_amount_minor)} is now invested. The funding round closed.`,
      status: "Invested",
      refused: false
    };
  }
  return {
    title: "Order placed",
    text: subscriptionClaim
      ? `${money(order.allocated_amount_minor)} of your balance is reserved for the Loan Originator funding round. It becomes an active holding automatically at funding close. The boundary installment belongs entirely to the LO. Reservations are returned if the round is cancelled before close.`
      : `${money(order.allocated_amount_minor)} of your balance is reserved for this loan. The investment starts when funding closes. If the loan does not reach its minimum, the money goes back to your balance.`,
    status: "Reserved until funding closes",
    refused: false
  };
}

/** Primary-market order (direct loans and Loan Originator subscriptions): amount, review, email code, done. */
function InvestFlow({
  loan,
  onClose,
  initialAmount,
  setRoute
}: {
  loan: MarketplaceLoanDetail;
  onClose: () => void;
  initialAmount?: string;
  setRoute: (route: AppRoute) => void;
}) {
  const queryClient = useQueryClient();
  const subscriptionClaim = usesOriginatorSubscription(loan);
  const balances = useBalancesData().data;
  const investableLots = currentInvestableLotsForLoanCurrency(balances?.lots, loan);
  const investableBalanceMinor = sumLotAvailableMinor(investableLots);
  const maxInvest = Math.min(investableBalanceMinor, loan.remaining_capacity_minor);
  const funds = { balanceMinor: currencyBalanceMinor(balances?.lots, loan.currency), eligibleMinor: investableBalanceMinor };
  const fundsBlock = noEligibleFundsReason(loan.currency, funds);
  const [amount, setAmount] = useState(initialAmount ?? "");
  const [step, setStep] = useState<InvestStep>(initialAmount ? "review" : "amount");
  const [ack1, setAck1] = useState(false);
  const [ack2, setAck2] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState<PrimaryOrderAttempt>(() =>
    newPrimaryOrderAttempt(parseMoneyInputToMinorUnits(initialAmount ?? "", loan.currency).amountMinor)
  );
  // The order as the server returned it after allocation: the done screen shows it.
  const [placedOrder, setPlacedOrder] = useState<PrimaryInvestmentOrder | null>(null);
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
      : investAmountLimitMessage({
          amountMinor,
          capacityMinor: loan.remaining_capacity_minor,
          currency: loan.currency,
          funds,
          money: (minor) => `${loan.currency} ${formatMoneyMinor(minor, loan.currency)}`
        }) ?? undefined);
  const submitting = orderMutation.isPending || acceptanceMutation.isPending || allocateMutation.isPending;
  const money = (minor: number) => `${loan.currency} ${formatMoneyMinor(minor, loan.currency)}`;

  // A new amount, or a return to the amount step, drops the cached order and terms
  // acceptance: they recorded the old amount. New keys go with them.
  const changeAmount = (value: string) => {
    setAmount(value);
    setAttempt(newPrimaryOrderAttempt(parseMoneyInputToMinorUnits(value, loan.currency).amountMinor));
    // The terms are accepted for the order amount: a new amount is accepted again.
    setAck1(false);
    setAck2(false);
  };
  const backToAmount = () => {
    setError("");
    setAttempt(newPrimaryOrderAttempt(amountMinor));
    setStep("amount");
  };

  const confirmOrder = async () => {
    setError("");
    if (isFixturePreview) {
      if (codeRequest.pin.previewAccepts()) setStep("done");
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
    // Reuse the order and acceptance only for a retry of exactly this amount.
    let current = attempt.amountMinor === amountMinor ? attempt : newPrimaryOrderAttempt(amountMinor);
    try {
      const orderId = current.orderId ?? (await orderMutation.mutateAsync({
        data: {
          loan_id: loan.loan_id,
          amount_minor: amountMinor,
          idempotency_key: current.orderKey
        }
      })).id;
      current = { ...current, orderId };
      setAttempt(current);
      const acceptanceId = current.acceptanceId ?? (await acceptanceMutation.mutateAsync({
        data: {
          category: CategoryEnum.primary_market_investment,
          expected_template_version_id: termsQuery.data.id,
          accepted_checkbox_labels: labels,
          context_type: "primary_order",
          context_id: orderId,
          data_snapshot: {
            loan_id: loan.loan_id,
            amount_minor: amountMinor,
            currency: loan.currency
          },
          idempotency_key: current.acceptanceKey
        }
      })).id;
      current = { ...current, acceptanceId };
      setAttempt(current);
      const order = await allocateMutation.mutateAsync({
        orderId,
        data: {
          document_acceptance_id: acceptanceId,
          idempotency_key: current.allocationKey,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          pin: codeRequest.pin.value
        }
      });
      void queryClient.invalidateQueries();
      setPlacedOrder(order);
      setStep("done");
    } catch (mutationError) {
      if (codeRequest.pin.handleError(mutationError)) return;
      if (isOrderNotPendingError(mutationError)) setAttempt(newPrimaryOrderAttempt(amountMinor));
      // The last place of a Swiss-borrower loan went to someone else: reload the places.
      if (isSwissInvestorLimitError(mutationError)) void queryClient.invalidateQueries();
      setError(apiErrorMessage(mutationError));
    }
  };

  const footer = step === "done"
    ? null
    : step === "confirm"
      ? <><Button onClick={() => setStep("review")}>Back</Button><Button disabled={code.length < 6 || !codeRequest.pin.ready || (!isFixturePreview && !codeRequest.codeId) || submitting} variant="primary" onClick={() => void confirmOrder()}>{submitting ? "Submitting..." : "Confirm order"}</Button></>
      : step === "review"
        ? <><Button onClick={backToAmount}>Back</Button><Button disabled={!ack1 || !ack2} variant="primary" onClick={() => setStep("confirm")}>Continue</Button></>
        : <><Button onClick={onClose}>Cancel</Button><Button disabled={amountMinor < loan.minimum_investment_minor || Boolean(amountError) || swissLoanFullForViewer(loan)} variant="primary" onClick={() => setStep("review")}>Review order</Button></>;

  // What the server did with the order (audit A-33 / SECONDARY-06): allocated in full,
  // partly allocated, or closed with nothing invested.
  const outcome = placedOrder ? primaryOrderOutcome(placedOrder, loan, subscriptionClaim, money) : null;

  // Summary card: the loan terms first, then the amounts (design: overview, then amount and fees).
  const orderRows = [
    [
      { label: "Loan", value: <span className="entity-inline"><span>{loan.title}</span><CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" /></span> },
      ...(subscriptionClaim && loan.originator_name ? [{ label: "Loan Originator", value: loan.originator_name }] : []),
      { label: subscriptionClaim ? "Nominal investor interest rate" : "Yield", value: `${formatRateBps(marketplaceYieldBps(loan))} p.a.` },
      ...(subscriptionClaim ? [
        { label: "Underlying borrower coupon", value: `${formatRateBps(loan.underlying_interest_rate_bps)} p.a.` },
        { label: "Interest participation", value: formatRateBps(loan.investor_interest_participation_bps ?? 0) },
        { label: "Penalty participation", value: formatRateBps(loan.investor_penalty_participation_bps ?? 0) },
        { label: "Funding closes", value: loan.funding_deadline ? formatDate(loan.funding_deadline) : "Not available" },
        { label: "Boundary installment", value: loan.entitlement_start_date ? formatDate(loan.entitlement_start_date) : "Not available" }
      ] : [])
    ],
    placedOrder ? [
      { label: "Order amount", value: money(placedOrder.requested_amount_minor) },
      { label: subscriptionClaim ? "Principal acquired at funding close" : "Investment amount", value: money(placedOrder.allocated_amount_minor) },
      { label: "Status", value: outcome?.status ?? humanizeToken(placedOrder.status) },
      { label: "Platform fee", value: "None" }
    ] : [
      { label: "Order amount", value: money(amountMinor) },
      { label: subscriptionClaim ? "Principal acquired at funding close" : "Investment amount", value: money(amountMinor) },
      { label: "Platform fee", value: "None" }
    ]
  ];

  return (
    <InvestPageFrame
      alerts={step === "amount" && fundsBlock ? (
        <Banner tone="bad" title={fundsBlock.title}>{fundsBlock.detail}</Banner>
      ) : undefined}
      footer={footer}
      loan={loan}
      onBack={onClose}
      step={step}
      summary={orderRows}
      title="Invest"
    >
      {step === "amount" ? (
        <div className="iv-form">
          <InvestLoanChip loan={loan} />
          <Field error={amountError} hint={`Between ${loan.currency} ${formatMoneyMinor(loan.minimum_investment_minor, loan.currency)} and ${formatMoneyMinor(maxInvest, loan.currency)}`} label="Investment amount">
            <InvestAmountInput currency={loan.currency} label="Investment amount" value={amount} onChange={changeAmount} />
          </Field>
          <SwissInvestorLimitNote loan={loan} />
          <InvestPaidFrom currency={loan.currency} investableBalanceMinor={investableBalanceMinor} />
          <Banner tone="neutral" title={subscriptionClaim ? "Subscription at par" : "Allocation"}>
            {subscriptionClaim
              ? `Every ${loan.currency} 1.00 buys ${loan.currency} 1.00 of post-boundary principal when funding closes. Holdings activate automatically. No interest accrues during funding, and the boundary installment belongs entirely to the Loan Originator.`
              : "Orders are intents only. They become effective after funds are allocated and validated, first-come first-served."}
          </Banner>
        </div>
      ) : step === "review" ? (
        <div className="card iv-card iv-sign">
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
          <p className="iv-note">
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
        <div className="card iv-card iv-form">
          <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code and your PIN.</Banner>
          {!isFixturePreview && termsQuery.isError ? <Banner tone="bad" title="Investment terms unavailable">The current server-published investment terms could not be loaded.</Banner> : null}
          {!isFixturePreview && termsQuery.data ? <p className="iv-note">Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
          <SensitiveActionFields code={code} codeRequest={codeRequest} onCodeChange={setCode} onContinue={() => void confirmOrder()} />
          {codeRequest.expiresAt ? <p className="iv-note">Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
          {codeRequest.error || error ? <Banner tone="bad" title="Could not place order">{codeRequest.error || error}</Banner> : null}
        </div>
      ) : (
        <InvestDone outcome={outcome?.refused ? "refused" : "success"} setRoute={setRoute} title={outcome?.title ?? "Order placed"} onBackToLoan={onClose}>
          {outcome?.text ?? (subscriptionClaim
            ? "Your balance is reserved for the Loan Originator funding round and becomes an active holding automatically at funding close. The boundary installment belongs entirely to the LO. Reservations are returned if the round is cancelled before close."
            : "Your balance is reserved for this loan. The investment starts when funding closes.")}
        </InvestDone>
      )}
    </InvestPageFrame>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return <div className="lp-kv-line"><span className="lp-kv-k">{label}</span><span className="lp-kv-v">{value}</span></div>;
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

function LoanNotFound({ title, setRoute }: { title: string; setRoute: (route: AppRoute) => void }) {
  return (
    <main className="content">
      <div className="page-head"><h1>{title}</h1></div>
      <Card padded>
        <Empty icon="search" title="Loan not found">
          This loan does not exist, or it is no longer shown to investors.
        </Empty>
        <div className="row gap-8" style={{ justifyContent: "center", marginTop: 12 }}>
          <Button variant="primary" onClick={() => goTo(setRoute, "market")}>Go to the primary market</Button>
        </div>
      </Card>
    </main>
  );
}

function ScreenLoading({ title }: { title: string }) {
  return <main className="content"><div className="page-head"><h1>{title}</h1></div><LoadingCard title="Loading">Loading investor portal data.</LoadingCard></main>;
}
