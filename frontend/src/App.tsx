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
  getV1MarketplaceSecondaryListingsListQueryKey,
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
  useV1MarketplaceSecondaryListingsPricingPreviewRetrieve,
  useV1InvestorSmartInvestDeactivateCreate,
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
  Holding,
  InvestorDocument,
  InvestorDocumentDownloadResponse,
  InvestorNotification,
  InvestorNotifications,
  MarketplaceLoanDetail,
  MarketplaceLoanPreview,
  OriginatorClaimQuoteResponse,
  PayoutInstruction,
  PrimaryInvestmentOrder,
  PrimaryOrderBatchResponse,
  PrimaryOrderPortal,
  PublicDocumentTemplateVersion,
  PublicMarketplaceLoan,
  SecondaryMarketActivityEntryPortal,
  SecondaryMarketBuyerListing,
  SecondaryMarketInvestmentInstallment,
  SecondaryMarketListingPricingPreview,
  SecondaryMarketLoanInstallment,
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
  useLoanDetailData,
  useMarketplaceLoansData,
  useNotificationReadActions,
  useNotificationsData,
  usePortfolioData,
  usePrimaryOrdersData,
  usePublicMarketplaceLoansData,
  useSecondaryActivityData,
  useSecondaryListingDetailData,
  useSecondaryListingsData,
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
  mkListSummary,
  mkNewLending,
  mkNoCollateral,
  mkOptionUnion,
  mkRefinancing,
  mkToggle,
  smartInvestCatalog,
  smartInvestFiltersFromRule,
  smartInvestRequestFromFilters,
  type MkFilters,
  type MkListKey
} from "./investorPortal/smartInvestCriteria";
import { onboardingStepForUser } from "./onboarding";
import { captureMagicLinkTokenFromLocation, takePendingMagicLinkToken } from "./magicLinkToken";
import {
  formatDate,
  formatDateTime,
  formatMoneyMinor,
  formatMoneyLabel,
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
  zurichDateKey
} from "./investorPortal/format";
import type { AppRoute, DemoAccountState, RouteName } from "./investorPortal/types";
import { scheduleStatusTone } from "./investorPortal/scheduleStatus";
import { normalizeStory, storyIsEmpty } from "./investorPortal/story";
import { StoryView } from "./investorPortal/StoryView";
import { notificationRoute } from "./investorPortal/notifications";
import { LoanDocumentList } from "./investorPortal/LoanDocumentList";
import {
  completedHoldingLabel,
  completedHoldings,
  defaultSelectedPaymentKey,
  installmentProgress,
  isPaidScheduleRow,
  loanIsInDefault,
  scheduleRowStatus
} from "./investorPortal/holdingProgress";
import { currencyBalanceMinor, investAmountLimitMessage, noEligibleFundsReason } from "./investorPortal/investLimits";
import {
  collateralBreakdown,
  currentLoanPrincipalMinor,
  isUnsecuredHolding,
  isUnsecuredLoan,
  loanLtvBps,
  valuedSecuredHoldings,
  weightedLtvPercent
} from "./investorPortal/portfolioCollateral";
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
  Tabs,
  Tooltip,
  PageHead,
  UserSkin,
  type IconName
} from "./investorPortal/ui";

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
  "publicProjects",
  "publicFaq",
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

// "/" restores the last in-app screen, but never another public page: the
// public pages have their own addresses (/projects, /faq), so "/" is the home page.
function homeOrStoredRoute(): AppRoute {
  const stored = readStoredRoute();
  // Never the login or registration form either: a returning visitor whose session ended
  // sees the home page at "/" (the investor shell also falls back to it, see InvestorShell).
  return ["publicProjects", "publicFaq", "login", "register"].includes(stored.name) ? { name: "public" } : stored;
}

function routeFromPathname(pathname: string): AppRoute | null {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  const directRoutes: Record<string, RouteName> = {
    "/": "public",
    "/projects": "publicProjects",
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
  const publicProjectMatch = normalized.match(/^\/projects\/([^/]+)$/);
  if (publicProjectMatch) {
    try {
      return {
        name: "publicProjects",
        params: { loanId: decodeURIComponent(publicProjectMatch[1]) }
      };
    } catch {
      return null;
    }
  }
  const investmentMatch = normalized.match(/^\/portfolio\/([^/]+)$/);
  if (investmentMatch) {
    try {
      return { name: "investment", params: { holdingId: decodeURIComponent(investmentMatch[1]) } };
    } catch {
      return null;
    }
  }
  const loanMatch = normalized.match(/^\/marketplace\/([^/]+)(\/schedule|\/invest)?$/);
  if (!loanMatch) return null;
  try {
    const name: RouteName = loanMatch[2] === "/schedule" ? "loanSchedule" : loanMatch[2] === "/invest" ? "invest" : "loan";
    return { name, params: { loanId: decodeURIComponent(loanMatch[1]) } };
  } catch {
    return null;
  }
}

function routePath(route: AppRoute) {
  if (route.name === "publicProjects") {
    return route.params?.loanId
      ? `/projects/${encodeURIComponent(route.params.loanId)}`
      : "/projects";
  }
  const paths: Record<RouteName, string> = {
    public: "/",
    publicProjects: "/projects",
    publicFaq: "/faq",
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
  publicProjects: "Projects",
  publicFaq: "Help",
  login: "Log in",
  register: "Register",
  kyc: "Verification",
  dashboard: "Overview",
  market: "Primary market",
  smartInvest: "Smart Invest",
  loan: "Project",
  loanSchedule: "Project schedule",
  invest: "Invest",
  portfolio: "My investments",
  investment: "Investment",
  secondary: "Secondary market",
  balances: "Account",
  fx: "Currency exchange",
  documents: "Documents",
  notifications: "Notifications",
  settings: "Profile & Settings",
  faq: "Help"
};

type NavBadge = "projects" | "balances" | "notifications";
type NavLeaf = { route: RouteName; label: string; icon: IconName; badge?: NavBadge };
type NavParent = {
  key: string;
  label: string;
  icon: IconName;
  badge?: NavBadge;
  children: Array<{ route: RouteName; label: string }>;
};

const navGroups: Array<{ label: string; items: Array<NavLeaf | NavParent> }> = [
  {
    label: "Invest",
    items: [
      { route: "dashboard", label: "Overview", icon: "grid" },
      {
        key: "projects",
        label: "Projects",
        icon: "briefcase",
        badge: "projects",
        children: [
          { route: "market", label: "Primary market" },
          { route: "secondary", label: "Secondary market" }
        ]
      },
      { route: "portfolio", label: "My investments", icon: "portfolio" },
      { route: "smartInvest", label: "Smart Invest", icon: "refresh" }
    ]
  },
  {
    label: "Wallet",
    items: [
      { route: "balances", label: "Account", icon: "wallet", badge: "balances" },
      { route: "fx", label: "FX", icon: "swap" }
    ]
  },
  {
    label: "Account",
    items: [
      { route: "settings", label: "Profile & Settings", icon: "user" },
      { route: "documents", label: "Documents", icon: "docs" },
      { route: "notifications", label: "Notifications", icon: "bell", badge: "notifications" }
    ]
  }
];

// Pages that belong to a menu entry without being one themselves.
const navActiveRoute: Partial<Record<RouteName, RouteName>> = {
  loan: "market",
  loanSchedule: "market",
  invest: "market",
  investment: "portfolio",
  kyc: "settings"
};

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

// 409 from a secondary-market purchase: the listing price differs from the one
// the buyer reviewed, and nothing was charged.
function isSecondaryPriceChangedError(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 409) return false;
  const payload = error.payload as { code?: unknown } | null | undefined;
  return payload?.code === "secondary_price_changed";
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
      (!loan.funding_deadline || loan.funding_deadline < zurichDateKey(new Date(lot.withdrawal_deadline_at))) &&
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
  // A login-link token leaves the address bar before anything renders or calls the API.
  captureMagicLinkTokenFromLocation();
  const pathRoute = routeFromPathname(window.location.pathname);
  const initialRoute: AppRoute = readReadonlyImpersonationToken()
    ? pathRoute && !["public", "publicProjects", "publicFaq", "login", "register"].includes(pathRoute.name)
      ? pathRoute
      : { name: "dashboard" }
    : pathRoute?.name === "public"
      ? homeOrStoredRoute()
      : pathRoute ?? readStoredRoute();
  const [route, setRoute] = useState<AppRoute>(initialRoute);
  const [demoState, setDemoState] = useState<DemoAccountState>("active");
  // The path is state too: Back/Forward between the portal and /admin must re-render App.
  const [, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    if (window.location.pathname.startsWith("/admin")) return;
    const title = routeTitles[route.name];
    document.title = title && title !== platformName ? `${title} · ${platformName}` : platformName;
  }, [route.name]);

  useEffect(() => {
    const onPopState = () => {
      setPathname(window.location.pathname);
      // The admin console routes itself (adminConsole/adminRoute.ts); App only has to switch to it.
      if (window.location.pathname.startsWith("/admin")) return;
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
    return <UserSkin><KycReturnScreen setRoute={setRoute} /></UserSkin>;
  }

  if (window.location.pathname.startsWith("/legal/")) {
    return <UserSkin><LegalDocumentPage setRoute={setRoute} /></UserSkin>;
  }

  if (routeFromPathname(window.location.pathname) === null) {
    return <UserSkin><NotFoundPage setRoute={setRoute} /></UserSkin>;
  }

  if (route.name === "public") {
    return <UserSkin><PublicLanding setRoute={setRoute} /></UserSkin>;
  }

  if (route.name === "publicProjects") {
    return <UserSkin><PublicProjectsPage route={route} setRoute={setRoute} /></UserSkin>;
  }

  if (route.name === "publicFaq") {
    return <UserSkin><PublicFaqPage setRoute={setRoute} /></UserSkin>;
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

/* --------------------------------------------------------------------------
   Public site (logged-out pages): shell, home, projects, FAQ and legal pages.
   -------------------------------------------------------------------------- */

type SiteNavKey = "projects" | "how" | "help";

const siteHowItWorksId = "how-it-works";
function sitePrefersReducedMotion() {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function siteScrollTo(target: Element) {
  target.scrollIntoView({ behavior: sitePrefersReducedMotion() ? "auto" : "smooth", block: "start" });
}

function isPlainLeftClick(event: React.MouseEvent<HTMLAnchorElement>) {
  return !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

// Opens a section of the home page, for example "How it works", from any public page.
function goToSiteSection(setRoute: (route: AppRoute) => void, id: string) {
  const target = document.getElementById(id);
  if (target) {
    window.history.replaceState(window.history.state, "", `${window.location.pathname}#${id}`);
    siteScrollTo(target);
    return;
  }
  goTo(setRoute, "public");
  window.history.replaceState(window.history.state, "", `/#${id}`);
}

// Public preview loans arrive open and ordered by closing date (MKT-DEC-002 fields only).
function siteOpenLoans(loans: PublicMarketplaceLoan[]) {
  return loans.filter((loan) => loan.status === "open");
}

function publicLoanTypeLabel(loan: Pick<PublicMarketplaceLoan, "product_type">) {
  return loan.product_type === "originator_claim" ? "Loan Originator claim" : "Direct loan";
}

function publicLoanStatusLabel(status: string) {
  return status === "open" ? "Open for investment" : humanizeToken(status);
}

function publicCountryLabel(country: string) {
  const value = country.trim();
  if (!value) return "Not disclosed";
  if (/^[A-Za-z]{2}$/.test(value) && typeof Intl.DisplayNames === "function") {
    try {
      return new Intl.DisplayNames(["en"], { type: "region" }).of(value.toUpperCase()) ?? value;
    } catch {
      return value;
    }
  }
  return value;
}

function siteYieldRange(loans: PublicMarketplaceLoan[]) {
  if (loans.length === 0) return null;
  const values = loans.map((loan) => loan.interest_rate_bps);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  return minimum === maximum ? formatRateBps(minimum) : `${formatRateBps(minimum)} to ${formatRateBps(maximum)}`;
}

function SiteFlag({ kind, label }: { kind: "CH" | "EU"; label: string }) {
  return (
    <span aria-label={label} className="site-flag" role="img">
      {kind === "CH" ? (
        <svg height="14" viewBox="0 0 14 14" width="14">
          <rect fill="#DA291C" height="14" width="14" />
          <rect fill="#fff" height="8.4" width="2.4" x="5.8" y="2.8" />
          <rect fill="#fff" height="2.4" width="8.4" x="2.8" y="5.8" />
        </svg>
      ) : (
        <svg height="14" viewBox="0 0 20 14" width="20">
          <rect fill="#003399" height="14" width="20" />
          <circle cx="10" cy="7" fill="none" r="3.6" stroke="#ffcc00" strokeDasharray="1.2 1.6" strokeWidth="1.1" />
        </svg>
      )}
    </span>
  );
}

const siteLegalLinkLabels: Record<string, string> = {
  // The platform terms live in the published "registration" template; publishing a new version swaps the text.
  registration: "Terms and Conditions",
  primary_market_investment: "Investment terms",
  secondary_market_listing: "Seller terms",
  secondary_market_purchase: "Buyer terms",
  risk_disclosure: "Risk disclosure"
};

function SiteShell({
  active,
  children,
  setRoute
}: {
  active?: SiteNavKey;
  children: ReactNode;
  setRoute: (route: AppRoute) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [ctaVisible, setCtaVisible] = useState(false);
  const burgerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const update = () => setCtaVisible(window.scrollY > 520);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        burgerRef.current?.focus();
      }
    };
    const onResize = () => {
      if (window.innerWidth >= 1100) setMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onResize);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onResize);
    };
  }, [menuOpen]);

  const go = (name: RouteName) => {
    setMenuOpen(false);
    goTo(setRoute, name);
  };
  const navLinks: Array<{ key: SiteNavKey; label: string; href: string; open: () => void }> = [
    { key: "projects", label: "Projects", href: "/projects", open: () => go("publicProjects") },
    {
      key: "how",
      label: "How it works",
      href: `/#${siteHowItWorksId}`,
      open: () => {
        setMenuOpen(false);
        goToSiteSection(setRoute, siteHowItWorksId);
      }
    },
    { key: "help", label: "Help", href: "/faq", open: () => go("publicFaq") }
  ];
  const linkHandler = (open: () => void) => (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (!isPlainLeftClick(event)) return;
    event.preventDefault();
    open();
  };
  const renderNavLinks = () =>
    navLinks.map((link) => (
      <a
        aria-current={active === link.key ? "page" : undefined}
        className={active === link.key ? "active" : undefined}
        href={link.href}
        key={link.key}
        onClick={linkHandler(link.open)}
      >
        {link.label}
      </a>
    ));
  const ctaShown = ctaVisible && !menuOpen;

  return (
    <div className={`site ${menuOpen ? "site-menu-open" : ""}`}>
      <a
        className="site-skip"
        href="#site-main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("site-main")?.focus();
        }}
      >
        Skip to content
      </a>
      <header className="site-header">
        <div className="site-wrap site-header-inner">
          <BrandHomeLink className="site-brand" onNavigate={() => setMenuOpen(false)} setRoute={setRoute}>
            <Wordmark />
          </BrandHomeLink>
          <nav aria-label="Main" className="site-nav">
            {renderNavLinks()}
          </nav>
          <div className="site-header-actions">
            <Button className="site-btn-outline site-hide-menu" onClick={() => go("login")}>
              Log in
            </Button>
            <Button variant="primary" onClick={() => go("register")}>
              Open account
            </Button>
            <button
              aria-controls="site-menu"
              aria-expanded={menuOpen}
              aria-label="Menu"
              className="site-burger"
              onClick={() => setMenuOpen((open) => !open)}
              ref={burgerRef}
              type="button"
            >
              <Icon name={menuOpen ? "x" : "menu"} size={22} />
            </button>
          </div>
        </div>
      </header>
      {menuOpen ? (
        <div className="site-menu" id="site-menu">
          <div className="site-wrap">
            <nav aria-label="Menu" className="site-menu-nav">
              {renderNavLinks()}
            </nav>
            <div className="site-actions">
              <Button className="site-btn-outline" size="lg" onClick={() => go("login")}>
                Log in
              </Button>
              <Button size="lg" variant="primary" onClick={() => go("register")}>
                Open account
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      <main className="site-main" id="site-main" tabIndex={-1}>
        {children}
      </main>
      <SiteFooter setRoute={setRoute} />
      <div aria-hidden={!ctaShown} className={`site-mobile-cta ${ctaShown ? "is-visible" : ""}`} inert={!ctaShown}>
        <Button className="site-btn-outline" size="lg" tabIndex={ctaShown ? undefined : -1} onClick={() => go("publicProjects")}>
          Projects
        </Button>
        <Button size="lg" tabIndex={ctaShown ? undefined : -1} variant="primary" onClick={() => go("register")}>
          Open account
        </Button>
      </div>
    </div>
  );
}

function SiteFooter({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const routeLink = (name: RouteName) => (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (!isPlainLeftClick(event)) return;
    event.preventDefault();
    goTo(setRoute, name);
  };
  return (
    <footer className="site-footer">
      <div className="site-wrap">
        <div className="site-footer-grid">
          <div className="site-footer-brand">
            <BrandHomeLink setRoute={setRoute}>
              <Wordmark inverse />
            </BrandHomeLink>
            <p>
              Business loans in Switzerland and the EU/EEA, funded by individual lenders through participations in
              loan claims. {platformName} is owned and operated by {operatorName}.
            </p>
          </div>
          <div className="site-footer-col">
            <h2>Invest</h2>
            <ul>
              <li><a href="/projects" onClick={routeLink("publicProjects")}>Open projects</a></li>
              <li>
                <a
                  href={`/#${siteHowItWorksId}`}
                  onClick={(event) => {
                    if (!isPlainLeftClick(event)) return;
                    event.preventDefault();
                    goToSiteSection(setRoute, siteHowItWorksId);
                  }}
                >
                  How it works
                </a>
              </li>
              <li><a href={legalDocumentPath("risk_disclosure")}>Risk disclosure</a></li>
            </ul>
          </div>
          <div className="site-footer-col">
            <h2>Account</h2>
            <ul>
              <li><a href="/login" onClick={routeLink("login")}>Log in</a></li>
              <li><a href="/register" onClick={routeLink("register")}>Open account</a></li>
            </ul>
          </div>
          <div className="site-footer-col">
            <h2>Help</h2>
            <ul>
              <li><a href="/faq" onClick={routeLink("publicFaq")}>Help &amp; FAQ</a></li>
              <li><a href={`mailto:${supportEmail}`}>{supportEmail}</a></li>
            </ul>
          </div>
        </div>
        <div className="site-footer-legal">
          <p>
            {platformName}® is a registered trademark. The {platformName} platform is owned and operated by{" "}
            {operatorName}, a Swiss financial company with a share capital of CHF 1'100'000.00, affiliated to VQF, a
            self-regulatory organisation recognised by FINMA, and to FINOS, the Swiss financial ombudsman.{" "}
            {operatorName} is not a bank: money in a {platformName} balance is not a bank deposit and is not protected
            by the Swiss deposit insurance.
          </p>
          <p className="site-footer-risk">
            Lending to companies puts your capital at risk: a borrower can pay late or not at all, and you may not be
            able to sell your investment before it ends. Past results do not predict future results.
          </p>
        </div>
        <div className="site-footer-bottom">
          <span>© {new Date().getFullYear()} {operatorName}</span>
          <nav aria-label="Legal documents">
            {Object.keys(legalDocumentTitles).map((category) => (
              <a href={legalDocumentPath(category)} key={category} title={legalDocumentTitles[category]}>
                {siteLegalLinkLabels[category] ?? legalDocumentTitles[category]}
              </a>
            ))}
          </nav>
        </div>
      </div>
    </footer>
  );
}

function SitePlayIcon({ playing }: { playing: boolean }) {
  return playing ? (
    <svg aria-hidden="true" height="14" viewBox="0 0 14 14" width="14">
      <rect fill="currentColor" height="10" width="3" x="3" y="2" />
      <rect fill="currentColor" height="10" width="3" x="8" y="2" />
    </svg>
  ) : (
    <svg aria-hidden="true" height="14" viewBox="0 0 14 14" width="14">
      <path d="M4 2l8 5-8 5z" fill="currentColor" />
    </svg>
  );
}

function SiteProjectCarousel({
  loans,
  loading,
  failed,
  onOpen,
  onRetry,
  onSeeAll
}: {
  loans: PublicMarketplaceLoan[];
  loading: boolean;
  failed: boolean;
  onOpen: (loan: PublicMarketplaceLoan) => void;
  onRetry: () => void;
  onSeeAll: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(() => !sitePrefersReducedMotion() && typeof window.matchMedia === "function");
  const [hovered, setHovered] = useState(false);
  const count = loans.length;
  const current = count > 0 ? loans[index % count] : null;
  const position = count > 0 ? index % count : 0;

  useEffect(() => {
    if (!playing || hovered || count < 2) return undefined;
    const timer = window.setInterval(() => setIndex((value) => (value + 1) % count), 6000);
    return () => window.clearInterval(timer);
  }, [playing, hovered, count]);

  if (!current) {
    return (
      <div className="site-hero-card site-hero-card-empty">
        <div className="site-hero-card-top"><span>Open loans</span></div>
        {loading ? (
          <p>Loading the loans open for investment.</p>
        ) : failed ? (
          <>
            <p>The open loans could not be loaded right now.</p>
            <Button className="site-btn-white" onClick={onRetry}>Try again</Button>
          </>
        ) : (
          <>
            <p>No loans are open for investment right now. New loans appear here when they open.</p>
            <Button className="site-btn-white" onClick={onSeeAll}>See all projects</Button>
          </>
        )}
      </div>
    );
  }

  // Public preview fields only (plan MKT-DEC-002): borrower, amount, interest, period,
  // loan type, status, country and currency. No funding progress, deadline or minimum.
  const step = (delta: number) => {
    setPlaying(false);
    setIndex((value) => (value + delta + count) % count);
  };

  return (
    <div
      aria-label="Loans open for investment"
      aria-roledescription="carousel"
      className="site-carousel"
      onBlur={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      role="region"
    >
      <div aria-label={`${position + 1} of ${count}`} aria-roledescription="slide" role="group">
        <a
          className="site-hero-card"
          href={`/projects/${encodeURIComponent(current.loan_id)}`}
          onClick={(event) => {
            if (!isPlainLeftClick(event)) return;
            event.preventDefault();
            onOpen(current);
          }}
        >
          <div className="site-hero-card-top">
            <span className="site-live"><i aria-hidden="true" />Funding now</span>
            <span>{publicCountryLabel(current.borrower_country)}</span>
          </div>
          <h2 className="site-hero-card-title">{current.borrower_name}</h2>
          <div className="site-hero-card-place">
            {publicLoanTypeLabel(current)} · {current.currency}
            {current.is_refinancing ? " · Refinanced" : ""}
          </div>
          <div className="site-hero-rate">
            <strong>{formatRateBps(current.interest_rate_bps)}</strong>
            <span>interest a year</span>
          </div>
          <dl className="site-hero-card-facts">
            <div><dt>Term</dt><dd>{pluralize(current.term_months, "month")}</dd></div>
            <div>
              <dt>Loan amount</dt>
              <dd>{current.currency} {formatMoneyMinor(current.principal_minor, current.currency)}</dd>
            </div>
            <div><dt>Status</dt><dd>Open</dd></div>
          </dl>
        </a>
      </div>
      {count > 1 ? (
        <div className="site-carousel-nav">
          <div className="site-carousel-dots">
            {loans.map((loan, loanIndex) => (
              <button
                aria-current={loanIndex === position ? "true" : undefined}
                aria-label={`Loan ${loanIndex + 1}: ${loan.borrower_name}`}
                className={loanIndex === position ? "active" : undefined}
                key={loan.loan_id}
                onClick={() => {
                  setPlaying(false);
                  setIndex(loanIndex);
                }}
                type="button"
              />
            ))}
          </div>
          <span aria-live="polite" className="site-carousel-count">{position + 1} / {count}</span>
          <div className="site-carousel-btns">
            <button
              aria-label={playing ? "Pause" : "Play"}
              className="site-carousel-btn"
              onClick={() => setPlaying((value) => !value)}
              type="button"
            >
              <SitePlayIcon playing={playing} />
            </button>
            <button aria-label="Previous loan" className="site-carousel-btn" onClick={() => step(-1)} type="button">
              <Icon name="arrowL" size={16} />
            </button>
            <button aria-label="Next loan" className="site-carousel-btn" onClick={() => step(1)} type="button">
              <Icon name="arrowR" size={16} />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SiteProjectCard({ loan, onOpen }: { loan: PublicMarketplaceLoan; onOpen: (loan: PublicMarketplaceLoan) => void }) {
  const open = loan.status === "open";
  return (
    <article className={`site-project ${open ? "is-open" : ""}`} onClick={() => onOpen(loan)}>
      <div className="site-project-top">
        <div className="site-project-tags">
          <Chip status={loan.status} />
          {loan.is_refinancing ? <RefinancedTag /> : null}
        </div>
        <span className="site-project-country">{publicCountryLabel(loan.borrower_country)}</span>
      </div>
      <h3 className="site-project-title">{loan.borrower_name}</h3>
      <div className="site-project-place">{publicLoanTypeLabel(loan)} · {loan.currency}</div>
      <div className="site-project-rate">
        <strong>{formatRateBps(loan.interest_rate_bps)}</strong>
        <span>interest a year</span>
      </div>
      <dl className="site-project-facts">
        <div><dt>Amount</dt><dd><Money amountMinor={loan.principal_minor} currency={loan.currency} /></dd></div>
        <div><dt>Term</dt><dd>{pluralize(loan.term_months, "month")}</dd></div>
      </dl>
      <div className="site-project-foot">
        <CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" />
        <button
          aria-label={`View ${loan.borrower_name}`}
          className="site-project-open"
          onClick={(event) => {
            event.stopPropagation();
            onOpen(loan);
          }}
          type="button"
        >
          View <Icon name="chevR" size={15} />
        </button>
      </div>
    </article>
  );
}

function PublicLanding({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const loansQuery = usePublicMarketplaceLoansData();
  const loans = loansQuery.data ?? [];
  const openLoans = siteOpenLoans(loans);
  const openPreview = (loan: PublicMarketplaceLoan) => goTo(setRoute, "publicProjects", { loanId: loan.loan_id });

  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (!id) return;
    const target = document.getElementById(id);
    if (target) target.scrollIntoView({ block: "start" });
  }, []);

  return (
    <SiteShell setRoute={setRoute}>
      <section className="site-hero">
        <div className="site-wrap site-hero-grid">
          <div className="site-hero-copy">
            <span className="site-eyebrow">
              <SiteFlag kind="CH" label="Switzerland" />
              Swiss-regulated financial platform · CHF and EUR
            </span>
            <h1 className="site-display">
              <span>Your capital.</span> <span>Your choice.</span>
            </h1>
            <p className="site-lead">
              Lend to companies in Switzerland and the EU/EEA, one project at a time. You choose each loan, see its
              terms before you invest, and pay no platform fee to invest.
            </p>
            <div className="site-actions">
              <Button size="lg" variant="primary" onClick={() => goTo(setRoute, "register")}>
                Open account
              </Button>
              <Button className="site-btn-outline" size="lg" onClick={() => goTo(setRoute, "publicProjects")}>
                See open projects
              </Button>
            </div>
            <div className="site-trust">
              <span><Icon name="shield" size={15} />Regulated in Switzerland · VQF · FINOS</span>
              <span><Icon name="checkCircle" size={15} />Audited · share capital CHF 1.1 million</span>
            </div>
            <p className="site-risk-line">
              Lending to companies puts your capital at risk. Read the{" "}
              <a href={legalDocumentPath("risk_disclosure")}>risk disclosure</a>.
            </p>
          </div>
          <SiteProjectCarousel
            failed={loansQuery.isError && loans.length === 0}
            loading={loansQuery.isLoading && loans.length === 0}
            loans={openLoans.slice(0, 7)}
            onOpen={openPreview}
            onRetry={() => void loansQuery.refetch()}
            onSeeAll={() => goTo(setRoute, "publicProjects")}
          />
        </div>
      </section>
      <LandingMarketing
        loansFailed={loansQuery.isError && loans.length === 0}
        loansLoading={loansQuery.isLoading && loans.length === 0}
        onOpenLoan={openPreview}
        onRetry={() => void loansQuery.refetch()}
        openLoans={openLoans}
        setRoute={setRoute}
      />
    </SiteShell>
  );
}

function LandingMarketing({
  loansFailed,
  loansLoading,
  onOpenLoan,
  onRetry,
  openLoans,
  setRoute
}: {
  loansFailed: boolean;
  loansLoading: boolean;
  onOpenLoan: (loan: PublicMarketplaceLoan) => void;
  onRetry: () => void;
  openLoans: PublicMarketplaceLoan[];
  setRoute: (route: AppRoute) => void;
}) {
  const openCount = openLoans.length;
  const byCurrency = (["CHF", "EUR"] as const).map((currency) => {
    const currencyLoans = openLoans.filter((loan) => loan.currency === currency);
    return { currency, count: currencyLoans.length, yields: siteYieldRange(currencyLoans) };
  });

  return (
    <>
      <section className="site-section is-tint" id="fees">
        <div className="site-wrap site-split is-center">
          <div>
            <span className="site-eyebrow">Fees</span>
            <div className="site-zero">
              <strong className="site-accent">0%</strong>
              <span>platform fee when you invest</span>
            </div>
            <h2 className="site-h2">No fee to invest or to withdraw</h2>
            <p className="site-lead site-gap-top">
              Investing in a loan and withdrawing to your bank cost nothing. Fees apply only when you sell or buy on
              the secondary market or exchange currency, and you see each one before you confirm.
            </p>
          </div>
          <div className="site-box">
            <table className="site-table site-fee-table">
              <thead>
                <tr><th scope="col">For investors</th><th className="is-num" scope="col">Fee</th></tr>
              </thead>
              <tbody>
                <tr><td>Investing in a loan</td><td className="is-num">None</td></tr>
                <tr><td>Withdrawing to your bank</td><td className="is-num">None</td></tr>
                <tr>
                  <td>
                    Selling early on the secondary market
                    <span className="site-table-sub">Maker fee, paid by the seller only if the sale happens</span>
                  </td>
                  <td className="is-num">0.25% of the price</td>
                </tr>
                <tr>
                  <td>
                    Buying on the secondary market
                    <span className="site-table-sub">Taker fee, paid by the buyer</span>
                  </td>
                  <td className="is-num">Shown before you buy</td>
                </tr>
                <tr>
                  <td>
                    Exchanging CHF and EUR
                    <span className="site-table-sub">Conversion fee, included in the rate</span>
                  </td>
                  <td className="is-num">Shown before you confirm</td>
                </tr>
              </tbody>
            </table>
            <p className="site-small site-gap-top">
              Every fee that applies to an action is shown in that flow before you confirm, together with the exact
              amounts.
            </p>
          </div>
        </div>
      </section>

      <section className="site-section">
        <div className="site-wrap">
          <div className="site-section-head">
            <div>
              <span className="site-eyebrow">Open now</span>
              <h2 className="site-h2">Projects looking for investors</h2>
            </div>
            <p className="site-text">
              Every loan shows the same key facts: borrower, country, loan type, amount, interest and term. Full loan
              data, security and documents unlock after you register and verify your identity.
            </p>
          </div>
          {loansFailed ? (
            <DataErrorCard title="Could not load loan previews" onRetry={onRetry}>
              We could not reach the marketplace API. Try again, or register later when live data is available.
            </DataErrorCard>
          ) : loansLoading ? (
            <LoadingCard title="Loading loan previews">Fetching current marketplace opportunities.</LoadingCard>
          ) : openCount === 0 ? (
            <div className="site-box site-empty-note">
              No loans are open for investment right now. New loans appear here when they open.
            </div>
          ) : (
            <div className="site-projects">
              {openLoans.slice(0, 3).map((loan) => (
                <SiteProjectCard key={loan.loan_id} loan={loan} onOpen={onOpenLoan} />
              ))}
            </div>
          )}
          <div className="site-more">
            <Button className="site-btn-outline" size="lg" onClick={() => goTo(setRoute, "publicProjects")}>
              {openCount > 1 ? `All ${openCount} open projects` : openCount === 1 ? "See the open project" : "See all projects"}
            </Button>
          </div>
        </div>
      </section>

      <section className="site-cta-band" id={siteHowItWorksId}>
        <div className="site-wrap">
          <span className="site-eyebrow">How you start</span>
          <h2 className="site-display">Choose. Build. Follow.</h2>
          <ol className="site-cta-steps">
            <li>
              <small>01</small>
              <strong>Choose</strong>
              <span>
                Register online as an individual lender in Switzerland or the EU/EEA, confirm your phone and complete
                an online identity check. Then choose the loans you like: borrower, rate, term and security on one
                page.
              </span>
            </li>
            <li>
              <small>02</small>
              <strong>Build</strong>
              <span>
                Add CHF or EUR to your balance by bank transfer with your personal payment reference, then invest in
                each loan you pick, from that loan's minimum. Spread your money across borrowers, sectors and
                currencies.
              </span>
            </li>
            <li>
              <small>03</small>
              <strong>Follow</strong>
              <span>
                See every payment in your account. Principal and interest repayments are credited to your balance and
                shown in your activity. From there you invest again or withdraw to your bank.
              </span>
            </li>
          </ol>
          <div className="site-actions">
            <Button className="site-btn-white" size="lg" onClick={() => goTo(setRoute, "register")}>
              Open account
            </Button>
            <Button className="site-btn-ghost" size="lg" onClick={() => goTo(setRoute, "publicProjects")}>
              See the projects
            </Button>
          </div>
        </div>
      </section>

      <section className="site-section" id="regulated">
        <div className="site-wrap">
          <div className="site-section-head">
            <div>
              <span className="site-eyebrow">
                <SiteFlag kind="CH" label="Switzerland" />
                Regulated in Switzerland
              </span>
              <h2 className="site-h2">Swiss-regulated financial platform</h2>
            </div>
            <p className="site-text">
              {platformName}® is a registered trademark. The platform is owned and operated by {operatorName}, a Swiss
              financial company: supervised for its financial activities, answerable to an independent ombudsman,
              audited every year.
            </p>
          </div>
          <div className="site-cells">
            <div>
              <span className="site-proof-mark">VQF</span>
              <h3 className="site-h4">Member of VQF</h3>
              <p className="site-text">
                The self-regulatory organisation recognised by FINMA supervises {operatorName}'s financial activities
                and its anti-money-laundering duties.
              </p>
            </div>
            <div>
              <span className="site-proof-mark">FINOS</span>
              <h3 className="site-h4">Affiliated to FINOS</h3>
              <p className="site-text">The Swiss financial ombudsman. If you disagree with us, it mediates free of charge.</p>
            </div>
            <div>
              <span className="site-proof-mark">Audited</span>
              <h3 className="site-h4">Audited data</h3>
              <p className="site-text">
                {operatorName}'s accounts and the platform's data are audited every year by an independent auditor.
              </p>
            </div>
            <div>
              <span className="site-proof-mark">CHF 1.1m</span>
              <h3 className="site-h4">Share capital</h3>
              <p className="site-text">CHF 1'100'000.00 of share capital behind the company that runs {platformName}.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="site-section is-paper" id="currencies">
        <div className="site-wrap site-split is-center">
          <div className="site-preview" aria-label="Loans open for investment, by currency" role="region">
            <span className="site-eyebrow">Open loans today</span>
            <div className="site-wallets">
              {byCurrency.map((group) => (
                <div className="site-wallet" key={group.currency}>
                  <div className="site-wallet-head">
                    <SiteFlag kind={group.currency === "CHF" ? "CH" : "EU"} label={group.currency === "CHF" ? "Swiss franc" : "Euro"} />
                    <strong>{group.currency} loans</strong>
                  </div>
                  <div className="site-wallet-amount">{group.count} open</div>
                  <dl>
                    <div><dt>Yield a year</dt><dd>{group.yields ?? "—"}</dd></div>
                  </dl>
                </div>
              ))}
            </div>
            {openCount > 0 ? (
              <div className="site-table-scroll">
                <table className="site-table site-gap-top">
                  <thead>
                    <tr>
                      <th scope="col">Open now</th>
                      <th className="is-num" scope="col">Yield</th>
                      <th className="is-num" scope="col">Term</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openLoans.slice(0, 4).map((loan) => (
                      <tr key={loan.loan_id}>
                        <td>{loan.borrower_name}</td>
                        <td className="is-num">{formatRateBps(loan.interest_rate_bps)}</td>
                        <td className="is-num">{pluralize(loan.term_months, "month")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
          <div>
            <span className="site-eyebrow">
              <SiteFlag kind="CH" label="Swiss franc" />
              <SiteFlag kind="EU" label="Euro" />
              Multi-currency
            </span>
            <h2 className="site-h2">
              <span>CHF and EUR.</span> <span>In one place.</span>
            </h2>
            <p className="site-lead site-gap-top">
              One account with a CHF and a EUR balance: Swiss franc loans in francs, euro loans in euros. You invest
              in the currency of the loan, and you can exchange between the two.
            </p>
            <ol className="site-numbered">
              <li>
                <span className="site-numbered-index">01</span>
                <div>
                  <h3 className="site-h4">Each loan sets its minimum</h3>
                  <p>
                    Every loan shows its own minimum investment. You see it on the loan page after you open your
                    account and pass the identity check.
                  </p>
                </div>
              </li>
              <li>
                <span className="site-numbered-index">02</span>
                <div>
                  <h3 className="site-h4">Exchange between CHF and EUR</h3>
                  <p>
                    Convert available balances in your account. The conversion fee is included in the rate and shown
                    before you confirm. Exchanging does not restart the 60-day holding limit.
                  </p>
                </div>
              </li>
              <li>
                <span className="site-numbered-index">03</span>
                <div>
                  <h3 className="site-h4">A 60-day holding limit</h3>
                  <p>
                    Money you add waits in your balance until you invest it. Balances earn no interest and are not bank
                    deposits. Every amount has a 60-day holding limit, and to invest it must have enough time left to
                    cover the loan's remaining funding period.
                  </p>
                </div>
              </li>
            </ol>
            <Button className="site-gap-top" size="lg" variant="primary" onClick={() => goTo(setRoute, "register")}>
              Open account
            </Button>
          </div>
        </div>
      </section>

      <section className="site-section">
        <div className="site-wrap site-split">
          <div>
            <span className="site-eyebrow">Questions</span>
            <h2 className="site-h2">Frequently asked questions</h2>
            <p className="site-lead site-gap-top">
              Not answered here? See{" "}
              <a
                href="/faq"
                onClick={(event) => {
                  if (!isPlainLeftClick(event)) return;
                  event.preventDefault();
                  goTo(setRoute, "publicFaq");
                }}
              >
                all questions
              </a>{" "}
              or write to <a href={`mailto:${supportEmail}`}>{supportEmail}</a>.
            </p>
          </div>
          <div className="site-faq">
            <details className="site-faq-item" open>
              <summary>Is {platformName} regulated?</summary>
              <div className="site-faq-answer">
                <p>
                  Yes. {platformName}® is a registered trademark; the platform is owned and operated by {operatorName},
                  a Swiss financial company affiliated to VQF, a self-regulatory organisation recognised by FINMA, for
                  its financial activities, and to FINOS, the Swiss financial ombudsman. Its accounts are audited by an
                  independent auditor and its share capital is CHF 1'100'000.00. {operatorName} is not a bank.
                </p>
              </div>
            </details>
            <details className="site-faq-item">
              <summary>How much do I need to start?</summary>
              <div className="site-faq-answer">
                <p>
                  Each loan sets its own minimum investment, and you invest in the currency of the loan. The loan shows
                  its minimum before you invest.
                </p>
              </div>
            </details>
            <details className="site-faq-item">
              <summary>Does {platformName} charge investors fees?</summary>
              <div className="site-faq-answer">
                <p>
                  There is no platform fee to invest in a loan and no fee to withdraw to your bank. If you sell early on
                  the secondary market, the seller pays a 0.25% maker fee, only if the sale happens; the buyer pays a
                  taker fee. Exchanging currency has a conversion fee, included in the rate. Every fee is shown in the
                  flow before you confirm.
                </p>
              </div>
            </details>
            <details className="site-faq-item">
              <summary>How long can money stay uninvested?</summary>
              <div className="site-faq-answer">
                <p>
                  Every incoming amount has a 60-day holding limit. To invest, it must have enough time left to cover
                  the full remaining funding period of the loan you choose: a 30-day window needs at least 30 days of
                  holding time left. Uninvested money must be withdrawn by the holding deadline, and exchanging
                  currency does not restart this clock.
                </p>
              </div>
            </details>
            <details className="site-faq-item">
              <summary>Where do repayments go?</summary>
              <div className="site-faq-answer">
                <p>
                  Borrower repayments are distributed to current holders according to their outstanding principal.
                  Principal and interest credits appear in your balance and activity history, from where you can
                  invest again or withdraw to your bank.
                </p>
              </div>
            </details>
            <details className="site-faq-item">
              <summary>Can I lose money?</summary>
              <div className="site-faq-answer">
                <p>
                  Yes. Borrowers can pay late, pay partially, default, or become subject to recovery proceedings.
                  Collateral, guarantees or security may not fully cover losses or may take time and cost to enforce.
                </p>
              </div>
            </details>
          </div>
        </div>
      </section>
    </>
  );
}

function PublicProjectsPage({ route, setRoute }: { route: AppRoute; setRoute: (route: AppRoute) => void }) {
  const loansQuery = usePublicMarketplaceLoansData();
  const loans = loansQuery.data ?? [];
  const previewLoanId = route.params?.loanId ?? null;
  const previewLoan = loans.find((loan) => loan.loan_id === previewLoanId);
  const openPreview = (loan: PublicMarketplaceLoan) => {
    goTo(setRoute, "publicProjects", { loanId: loan.loan_id });
  };

  return (
    <SiteShell active="projects" setRoute={setRoute}>
      {previewLoan ? (
        <section className="site-section no-rule site-loan-section">
          <div className="site-wrap">
            <PublicLoanPreview
              loan={previewLoan}
              onBack={() => goTo(setRoute, "publicProjects")}
              setRoute={setRoute}
            />
          </div>
        </section>
      ) : (
        <>
          <section className="site-page-head">
            <div className="site-wrap">
              <span className="site-eyebrow">Projects</span>
              <h1 className="site-h1">Open loan opportunities</h1>
              <p className="site-lead">
                Preview current primary-market loans. Borrower documents, ratings, collateral detail and investing
                unlock after registration and identity verification.
              </p>
              <p className="site-text site-page-lede">
                Review project-specific business loans, their repayment schedules, risks, and any disclosed security
                before deciding whether to invest.
              </p>
            </div>
          </section>
          <section className="site-section no-rule site-flush-top">
            <div className="site-wrap">
              <div className="site-locked site-preview-note">
                <Icon className="site-preview-note-icon" name="lock" size={18} />
                <p>
                  <b>Preview mode.</b> You are seeing limited fields. Register as an individual lender in Switzerland
                  or the EU/EEA to see full loan data and invest.
                </p>
                <div className="site-actions">
                  <Button variant="primary" onClick={() => goTo(setRoute, "register")}>
                    Get started
                  </Button>
                  {isFixturePreview ? (
                    <Button className="site-btn-outline" onClick={() => goTo(setRoute, "dashboard")}>
                      Open dummy portal
                    </Button>
                  ) : null}
                </div>
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
                <LoansTable loans={loans} onOpen={openPreview} preview />
              )}
              <p className="site-risk-line">
                {platformName} facilitates peer-to-peer loan claim participations operated by{" "}
                {operatorName}. Investing involves risk of capital loss and is not a bank deposit,
                fund unit, trading venue, or guaranteed-return product.
              </p>
            </div>
          </section>
        </>
      )}
    </SiteShell>
  );
}

function PublicLoanPreview({
  loan,
  onBack,
  setRoute
}: {
  loan: PublicMarketplaceLoan;
  onBack: () => void;
  setRoute: (route: AppRoute) => void;
}) {
  return (
    <div className="site-loan">
      <button className="backlink site-back" onClick={onBack} type="button">
        <Icon name="arrowL" size={14} /> All loans
      </button>
      <div className="site-loan-tags">
        <Chip status={loan.status} />
        <span className="tag">{loan.currency}</span>
        <span className="tag">{publicLoanTypeLabel(loan)}</span>
        {loan.is_refinancing ? <RefinancedTag full /> : null}
      </div>
      <h1 className="site-h1">{loan.borrower_name}</h1>
      <div className="site-loan-id"><CopyIdButton ariaLabel="Copy loan ID" id={loan.loan_id} label="Copy loan ID" /></div>
      <div className="site-project-page">
        <div>
          <div className="site-loan-facts">
            <Stat amountMinor={loan.principal_minor} currency={loan.currency} label="Amount" />
            <Stat label="Interest" raw={formatRateBps(loan.interest_rate_bps)} sub="per annum" />
            <Stat label="Term" raw={`${loan.term_months} mo`} />
            <Stat label="Status" raw={publicLoanStatusLabel(loan.status)} />
            <Stat label="Borrower country" raw={publicCountryLabel(loan.borrower_country)} />
            <Stat label="Loan type" raw={loan.is_refinancing ? `${publicLoanTypeLabel(loan)}, refinancing` : publicLoanTypeLabel(loan)} />
          </div>
          <div className="site-locked site-loan-locked">
            <div className="eyebrow">Full loan data</div>
            <Banner icon="lock" tone="neutral" title="Registration required">
              Complete registration, phone verification and KYC to unlock borrower disclosures,
              collateral, documents, LTV, risk rating and investment actions.
            </Banner>
          </div>
        </div>
        <aside className="site-sticky">
          <div className="site-box is-ink-rule">
            <h2 className="site-h4">Invest with {platformName}</h2>
            <ul className="site-checks">
              <li>Individual lenders in CH and EU/EEA</li>
              <li>Minimum investment set per loan</li>
              <li>Claim participation documents</li>
            </ul>
            <Button block size="lg" variant="primary" onClick={() => goTo(setRoute, "register")}>
              Create account
            </Button>
          </div>
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
      onError: (mutationError) => setError(apiErrorMessage(mutationError))
    });
  };

  return (
    <RegisterShell onClose={() => goTo(setRoute, "public")} setRoute={setRoute} step={step}>
      {step === 0 ? (
        <>
          <PageHead
            description={<>Individual lenders only. Legal entities are onboarded by {operatorName} off-platform.</>}
            eyebrow={`Step ${step + 1} of 3`}
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
                eyebrow={`Step ${step + 1} of 3`}
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
                eyebrow={`Step ${step + 1} of 3`}
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
            eyebrow={`Step ${step + 1} of 3`}
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

const registerStepLabels = ["Account", "Email and phone", "KYC"];

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
  const [navOpen, setNavOpen] = useState(false);
  const [projectsMenuOpen, setProjectsMenuOpen] = useState(false);
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
    setNavOpen(false);
    setAddFundsOpen(false);
    setInvestLoan(null);
  };
  // Sign out fails closed (audit A-58): the portal clears its state only after the server ended
  // the session. If the call fails, the server is asked whether the session is still valid.
  const [signOutError, setSignOutError] = useState("");
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
        return <PortfolioScreen setRoute={setRoute} />;
      case "investment":
        return <InvestmentScreen holdingId={route.params?.holdingId ?? ""} setRoute={setRoute} />;
      case "secondary":
        return <SecondaryMarketScreen demoState={demoState} initialTab={route.params?.tab} />;
      case "balances":
        return <BalancesScreen demoState={demoState} />;
      case "fx":
        return <FxScreen demoState={demoState} />;
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

  // Lots on their last day (withdraw-only), past the deadline, or in penalty mode need action.
  const overdueCount = balances.lots.filter((lot) => ["withdraw_only", "overdue", "penalty_mode", "penalty"].includes(lot.bucket)).length;
  const addFundsCurrency = balances.summaries.find((summary) => summary.currency === "CHF")?.currency
    ?? balances.summaries[0]?.currency
    ?? "CHF";
  const displayRouteName = !financialAccessAllowed && !isFixturePreview ? "kyc" : route.name;
  const activeRoute = navActiveRoute[displayRouteName] ?? displayRouteName;
  const addFundsDisabled = !financialAccessAllowed || frozenAccount.frozen || readonlyImpersonation.active;
  const openProjectCount = marketplaceLoans.filter((loan) => isOpenMarketplaceLoan(loan)).length;
  const unreadCount = notifications?.unread_count ?? 0;
  const badgeFor = (badge: NavBadge | undefined) => {
    if (badge === "projects") return openProjectCount > 0 ? <span className="nav-count">{openProjectCount}</span> : null;
    if (badge === "notifications") return unreadCount > 0 ? <span className="nav-count">{unreadCount}</span> : null;
    if (badge === "balances" && (frozenAccount.frozen || overdueCount > 0)) {
      return frozenAccount.frozen
        ? <span aria-label="Account frozen" className="nav-badge bad">!</span>
        : <span aria-label={`${overdueCount} ${overdueCount === 1 ? "balance needs" : "balances need"} action`} className="nav-badge warn">{overdueCount}</span>;
    }
    return null;
  };
  const navigate = (name: RouteName) => {
    goTo(setRoute, name);
    setNavOpen(false);
  };
  const signOut = () => {
    if (readonlyImpersonation.active || isFixturePreview) {
      finishLogout();
      return;
    }
    setSignOutError("");
    logoutMutation.mutate();
  };
  const signOutLabel = readonlyImpersonation.active
    ? "Exit read-only view"
    : logoutMutation.isPending
      ? "Signing out..."
      : "Sign out";

  return (
    <UserSkin>
    <div className="app">
      <a
        className="site-skip portal-skip"
        href="#portal-content"
        onClick={(event) => {
          event.preventDefault();
          const target = document.querySelector<HTMLElement>(".app .main > main, .app .main main");
          if (!target) return;
          if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
          target.focus();
        }}
      >
        Skip to main content
      </a>
      <div className={`nav-scrim ${navOpen ? "show" : ""}`} onClick={() => setNavOpen(false)} />
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <button aria-label={`${platformName} overview`} className="sidebar-logo" onClick={() => navigate("dashboard")} type="button">
            <Wordmark compact />
          </button>
          <button aria-label="Close menu" className="icon-btn sidebar-close" onClick={() => setNavOpen(false)} type="button">
            <Icon name="arrowL" size={18} />
          </button>
        </div>
        <nav aria-label="Investor portal navigation" className="nav">
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-group-label">{group.label}</div>
              {group.items.map((item) => {
                if ("children" in item) {
                  const childActive = item.children.some((child) => child.route === activeRoute);
                  const expanded = projectsMenuOpen || childActive;
                  return (
                    <div className={`nav-parent ${childActive ? "is-active" : ""} ${expanded ? "is-open" : ""}`} key={item.key}>
                      <button
                        aria-expanded={expanded}
                        className={`nav-link nav-toggle ${childActive ? "on" : ""}`}
                        onClick={() => setProjectsMenuOpen((open) => (childActive ? true : !open))}
                        type="button"
                      >
                        <Icon name={item.icon} size={22} strokeWidth={1.5} />
                        <span className="nav-link-label">{item.label}</span>
                        {badgeFor(item.badge)}
                        <Icon className="nav-caret" name="chevR" size={16} />
                      </button>
                      {expanded ? (
                        <div className="nav-sub">
                          {item.children.map((child) => (
                            <button
                              aria-current={activeRoute === child.route ? "page" : undefined}
                              className={`nav-sublink ${activeRoute === child.route ? "on" : ""}`}
                              key={child.route}
                              onClick={() => navigate(child.route)}
                              type="button"
                            >
                              {child.label}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                }
                const isActive = activeRoute === item.route;
                return (
                  <button
                    aria-current={isActive ? "page" : undefined}
                    className={`nav-link ${isActive ? "on" : ""}`}
                    key={item.route}
                    onClick={() => navigate(item.route)}
                    type="button"
                  >
                    <Icon name={item.icon} size={22} strokeWidth={1.5} />
                    <span className="nav-link-label">{item.label}</span>
                    {badgeFor(item.badge)}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <button className={`nav-foot-link ${activeRoute === "faq" ? "on" : ""}`} onClick={() => navigate("faq")} type="button">
            <Icon name="help" size={17} />
            <span>Help</span>
          </button>
          <button className="nav-foot-link" disabled={logoutMutation.isPending} onClick={signOut} type="button">
            <Icon name="logout" size={17} />
            <span>{signOutLabel}</span>
          </button>
        </div>
      </aside>
      <div className="main">
        <header aria-label="Investor account header" className="topbar">
          <button aria-label="Menu" className="icon-btn menu-btn" onClick={() => setNavOpen((open) => !open)} type="button">
            <Icon name="menu" size={20} />
          </button>
          <button aria-label={`${platformName} overview`} className="topbar-brand" onClick={() => navigate("dashboard")} type="button">
            <Wordmark compact />
          </button>
          <div className="crumbs sr-only">{routeTitles[displayRouteName]}</div>
          <HeaderLatestProject loans={marketplaceLoans} setRoute={setRoute} />
          <div className="topbar-tools">
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
              disabled={addFundsDisabled}
              icon="plus"
              onClick={() => setAddFundsOpen(true)}
              size="sm"
            >
              <span className="topbar-add-funds-label">Add Funds</span>
            </Button>
            {isFixturePreview ? (
              <div className="state-switch">
                <span>UX state</span>
                <select className="select state-switch-select" onChange={(event) => setDemoState(event.target.value as DemoAccountState)} value={demoState}>
                  <option value="active">Active investor</option>
                  <option value="kyc_pending">KYC pending</option>
                  <option value="frozen">Day-60 freeze</option>
                  <option value="restricted">Restricted account</option>
                </select>
              </div>
            ) : null}
            <HeaderUserMenu
              addFundsDisabled={addFundsDisabled}
              financialAccessAllowed={financialAccessAllowed}
              onAddFunds={() => setAddFundsOpen(true)}
              onNavigate={navigate}
              onSignOut={signOut}
              profile={profile}
              readonly={readonlyImpersonation.active}
              signOutDisabled={logoutMutation.isPending}
              signOutLabel={signOutLabel}
              summaries={balances.summaries}
            />
            <HeaderNotificationsMenu
              notifications={notifications}
              onOpen={(target) => {
                goTo(setRoute, target.name, target.params);
                setNavOpen(false);
              }}
            />
          </div>
        </header>
        {signOutError ? (
          <div className="fixture-preview-notice">
            <Banner
              actions={<Button disabled={logoutMutation.isPending} size="sm" variant="primary" onClick={signOut}>{logoutMutation.isPending ? "Signing out..." : "Retry sign out"}</Button>}
              icon="alert"
              tone="bad"
              title="Sign out failed"
            >
              {signOutError}
            </Banner>
          </div>
        ) : null}
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
        {frozenAccount.frozen && financialAccessAllowed && !blockedAccountStatus ? (
          <div className="fixture-preview-notice frozen-account-notice">
            <FrozenAccountBanner
              account={frozenAccount}
              onAddIban={readonlyImpersonation.active ? undefined : () => setPayoutIbanOpen(true)}
              onOpenAccount={route.name === "balances" ? undefined : () => navigate("balances")}
            />
          </div>
        ) : null}
        <FrozenAccountContext.Provider value={frozenAccount}>
          {gatedScreen}
        </FrozenAccountContext.Provider>
        <footer className="portal-footer">
          <span className="portal-footer-copy">&copy; {new Date().getFullYear()} {platformName} · {operatorName}</span>
          <nav aria-label="Legal and help" className="portal-footer-links">
            <a href={legalDocumentPath("registration")} rel="noreferrer" target="_blank">Terms and Conditions</a>
            <a href={legalDocumentPath("risk_disclosure")} rel="noreferrer" target="_blank">Risk disclosure</a>
            <button onClick={() => navigate("faq")} type="button">Help</button>
          </nav>
        </footer>
      </div>
      {addFundsOpen ? (
        <DepositModal
          allowCurrencySelection
          currency={addFundsCurrency}
          onClose={() => setAddFundsOpen(false)}
        />
      ) : null}
      {payoutIbanOpen ? <PayoutIbanModal onClose={() => setPayoutIbanOpen(false)} /> : null}
    </div>
    </UserSkin>
  );
}

type ShellProfile = { initials: string; name: string; email: string };

// Closes a header menu on an outside click or Escape.
function useDismissableMenu() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return { open, setOpen, rootRef };
}

function HeaderLatestProject({ loans, setRoute }: { loans: MarketplaceLoanPreview[]; setRoute: (route: AppRoute) => void }) {
  // The list API has no publication date, so the line shows the open loan that closes last.
  const latest = loans
    .filter((loan) => isOpenMarketplaceLoan(loan))
    .reduce<MarketplaceLoanPreview | null>((current, loan) => {
      if (!current) return loan;
      return (loan.funding_deadline ?? "") > (current.funding_deadline ?? "") ? loan : current;
    }, null);
  if (!latest) return <div className="topbar-news" />;
  const meta = [
    formatRateBps(marketplaceYieldBps(latest)),
    pluralize(latest.term_months, "month"),
    latest.currency
  ].join(" · ");
  return (
    <div className="topbar-news">
      <button className="topbar-news-item" onClick={() => goTo(setRoute, "loan", { loanId: latest.loan_id })} type="button">
        <Icon name="briefcase" size={18} strokeWidth={1.5} />
        <span className="topbar-news-text">
          <b>Open now: {latest.title}</b> <span>{meta}</span>
        </span>
        <Icon name="arrowR" size={15} />
      </button>
    </div>
  );
}

function HeaderUserMenu({
  profile,
  summaries,
  financialAccessAllowed,
  readonly,
  addFundsDisabled,
  onAddFunds,
  onNavigate,
  onSignOut,
  signOutDisabled,
  signOutLabel
}: {
  profile: ShellProfile;
  summaries: Array<{ currency: string; total_available_minor: number }>;
  financialAccessAllowed: boolean;
  readonly: boolean;
  addFundsDisabled: boolean;
  onAddFunds: () => void;
  onNavigate: (route: RouteName) => void;
  onSignOut: () => void;
  signOutDisabled: boolean;
  signOutLabel: string;
}) {
  const { open, setOpen, rootRef } = useDismissableMenu();
  const status = readonly ? "Read-only view" : financialAccessAllowed ? "Verified investor" : "Verification pending";
  const go = (route: RouteName) => {
    setOpen(false);
    onNavigate(route);
  };
  return (
    <div className={`hdr-menu user-menu ${open ? "open" : ""}`} ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
        className="user-toggle"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <span className="avatar">{profile.initials}</span>
        <span className="user-toggle-info">
          <span className="user-status">{status}</span>
          <span className="user-name">{profile.name}<Icon name="chevD" size={14} /></span>
        </span>
      </button>
      {open ? (
        <div className="hdr-dropdown user-dropdown" role="menu">
          <div className="hdr-dd-inner user-card">
            <span className="avatar lg">{profile.initials}</span>
            <span className="user-card-info">
              <span className="user-card-name">{profile.name}</span>
              <span className="user-card-email">{profile.email}</span>
            </span>
          </div>
          {summaries.length > 0 ? (
            <div className="hdr-dd-inner user-balance">
              <div className="eyebrow">{platformName} account · available</div>
              {summaries.map((summary, index) => (
                <div className={index === 0 ? "user-balance-main" : "user-balance-sub"} key={summary.currency}>
                  {formatMoneyMinor(summary.total_available_minor, summary.currency)} <small>{summary.currency}</small>
                </div>
              ))}
              <button
                className="user-balance-link"
                disabled={addFundsDisabled}
                onClick={() => {
                  setOpen(false);
                  onAddFunds();
                }}
                role="menuitem"
                type="button"
              >
                Add funds <Icon name="plus" size={14} />
              </button>
            </div>
          ) : null}
          <div className="hdr-dd-inner">
            <ul className="hdr-links">
              <li><button onClick={() => go("settings")} role="menuitem" type="button"><Icon name="user" size={17} /><span>Profile &amp; Settings</span></button></li>
              <li><button onClick={() => go("balances")} role="menuitem" type="button"><Icon name="wallet" size={17} /><span>Account &amp; payout IBANs</span></button></li>
              <li><button onClick={() => go("documents")} role="menuitem" type="button"><Icon name="docs" size={17} /><span>Documents</span></button></li>
              <li><button onClick={() => go("faq")} role="menuitem" type="button"><Icon name="help" size={17} /><span>Help</span></button></li>
            </ul>
          </div>
          <div className="hdr-dd-inner">
            <ul className="hdr-links">
              <li>
                <button
                  disabled={signOutDisabled}
                  onClick={() => {
                    setOpen(false);
                    onSignOut();
                  }}
                  role="menuitem"
                  type="button"
                >
                  <Icon name="logout" size={17} />
                  <span>{signOutLabel}</span>
                </button>
              </li>
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function HeaderNotificationsMenu({
  notifications,
  onOpen
}: {
  notifications: InvestorNotifications | undefined;
  onOpen: (route: AppRoute) => void;
}) {
  const { open, setOpen, rootRef } = useDismissableMenu();
  const readActions = useNotificationReadActions();
  const unread = notifications?.unread_count ?? 0;
  const items = (notifications?.notifications ?? []).slice(0, 5);
  const openNotification = (item: InvestorNotification) => {
    if (item.unread) void readActions.markRead(item.id).catch(() => undefined);
    setOpen(false);
    onOpen(notificationRoute(item));
  };
  return (
    <div className={`hdr-menu notif-menu ${open ? "open" : ""}`} ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Notifications"
        className="icon-btn hdr-bell"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <Icon name="bell" size={20} strokeWidth={1.5} />
        {unread > 0 ? <span className="ping" /> : null}
      </button>
      {open ? (
        <div className="hdr-dropdown notif-dropdown" role="menu">
          <div className="hdr-dd-head">
            <span>Notifications{unread > 0 ? ` (${unread} new)` : ""}</span>
            {unread > 0 ? (
              <button className="notif-read-all" onClick={() => void readActions.markAllRead().catch(() => undefined)} role="menuitem" type="button">
                Mark all as read
              </button>
            ) : null}
          </div>
          <div className="hdr-dd-body">
            {items.length === 0 ? (
              <div className="notif-empty">No notifications yet.</div>
            ) : (
              items.map((item) => {
                const failed = item.status === "failed" || item.status === "dead_letter";
                return (
                  <div className={`notif-item ${item.unread ? "unread" : ""}`} key={item.id}>
                    <button className="notif-open" onClick={() => openNotification(item)} role="menuitem" type="button">
                      <span className={`notif-icon ${failed ? "late" : ""}`}><Icon name={failed ? "alert" : "bell"} size={16} /></span>
                      <span className="notif-content">
                        <span className={`notif-text ${failed ? "neg" : ""}`}>{item.title}</span>
                        <span className="notif-time">{formatDateTime(item.created_at)}</span>
                      </span>
                    </button>
                    {item.unread ? (
                      <Tooltip content="Mark as read" focusable={false}>
                        <button
                          aria-label={`Mark "${item.title}" as read`}
                          className="notif-mark"
                          onClick={() => void readActions.markRead(item.id).catch(() => undefined)}
                          role="menuitem"
                          type="button"
                        >
                          <span aria-hidden="true" className="notif-dot" />
                        </button>
                      </Tooltip>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
          <div className="hdr-dd-foot">
            <button
              onClick={() => {
                setOpen(false);
                onOpen({ name: "notifications" });
              }}
              type="button"
            >
              View all
            </button>
          </div>
        </div>
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
  const idlePct = investedMinor + notWorkingMinor > 0 ? ((notWorkingMinor / (investedMinor + notWorkingMinor)) * 100).toFixed(1) : "0.0";

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
          <DataErrorCard title="Smart Invest is temporarily unavailable" onRetry={() => void smartInvestQuery.refetch()}>
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
                <text x="800" y={chartY(pctA) + 4} textAnchor="start" fontSize="13" fontWeight="700" fill="#0a0a0a">+{pctA.toFixed(1)}%</text>
                <text x="800" y={chartY(pctB) + 4} textAnchor="start" fontSize="13" fontWeight="700" fill="#1e7a46">+{pctB.toFixed(1)}%</text>
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
      setStep("done");
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
          sensitive_action_code: code
        }
      });
      // Money moved: refresh balances, portfolio and every list, as the other flows do
      // (audit A-42 / FRONTCODE-09).
      void queryClient.invalidateQueries();
      setBatchResult(placed);
      setStep("done");
    } catch (submitError) {
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
              <button className="aa-confirm" disabled={!ack || !riskAck || code.length < 6 || busy || quotesExpired || !hasPreparedQuotes || !termsReady || (!isFixturePreview && !codeRequest.codeId)} onClick={() => void submit()} type="button">{busy ? "Placing investments..." : `Place ${selectedCount === 1 ? "1 investment" : `${selectedCount} investments`}`}</button>
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

function mkLoanKindLabel(value: string) {
  return value === mkRefinancing ? "Refinancing" : "New lending";
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
  if (filters.minRate !== null) tokens.push({ label: `${filters.minRate.toFixed(1)}% and up`, clear: () => setFlt("minRate", null) });
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
                  <span className="fs-slider-val">{filters.minRate === null ? "any rate" : `${rateValue.toFixed(1)}%`}</span>
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

function mkOriginatorLabel(source: string, originators: Array<{ id: string; name: string }>) {
  if (source === mkBanxumSource) return "BANXUM direct loans";
  return originators.find((item) => item.id === source)?.name ?? "Selected Loan Originator";
}

function smartInvestCollateralSummary(selected: string[]) {
  const collateral = mkEffectiveCollateral(selected);
  if (collateral.includes(mkAnyCollateral) && collateral.includes(mkNoCollateral)) return "With or without collateral";
  return mkListSummary(collateral.map(mkCollateralLabel), "With or without collateral");
}

function smartInvestRuleSummary(filters: MkFilters, originators: Array<{ id: string; name: string }>) {
  const rows = [
    { label: "Collateral", value: smartInvestCollateralSummary(filters.col) },
    { label: "Currency", value: mkListSummary(filters.ccy, "Any currency") },
    { label: "Minimum yield", value: filters.minRate === null ? "No minimum" : `${filters.minRate.toFixed(1)}% p.a.` },
    { label: "Maximum term", value: filters.maxTerm === null ? "Any term" : `${filters.maxTerm} months` },
    {
      label: "Source",
      value: mkListSummary(filters.orig.map((source) => mkOriginatorLabel(source, originators)), "BANXUM and all Loan Originators")
    },
    { label: "Risk rating", value: mkListSummary(filters.rating.map(mkRatingLabel), "Any rating") },
    { label: "Purpose", value: mkListSummary(filters.purpose.map(humanizeToken), "Any purpose") },
    { label: "Loan type", value: mkListSummary(filters.kind.map(mkLoanKindLabel), "Any loan type") }
  ];
  return rows;
}

type SmartInvestCheckOption = { value: string; label: string };

// One Smart Invest criterion as square checkboxes. Nothing ticked = no restriction.
function SmartInvestChecks({
  compact = false,
  idPrefix,
  label,
  onToggle,
  options,
  selected
}: {
  compact?: boolean;
  idPrefix: string;
  label: string;
  onToggle: (value: string) => void;
  options: SmartInvestCheckOption[];
  selected: string[];
}) {
  return (
    <div aria-label={label} className={`si-checks${compact ? " compact" : ""}`} role="group">
      {options.map((option) => (
        <Check checked={selected.includes(option.value)} id={`${idPrefix}-${option.value}`} key={option.value} onChange={() => onToggle(option.value)}>
          {option.label}
        </Check>
      ))}
    </div>
  );
}

// "With collateral (any type)" + each collateral type + "No collateral (unsecured)".
// While "With collateral (any type)" is ticked, every type is included and shown ticked.
function SmartInvestCollateralChecks({
  idPrefix,
  onToggle,
  selected,
  types
}: {
  idPrefix: string;
  onToggle: (value: string) => void;
  selected: string[];
  types: string[];
}) {
  const anyOn = selected.includes(mkAnyCollateral);
  return (
    <div aria-label="Collateral" className="si-col-checks" role="group">
      <Check checked={anyOn} id={`${idPrefix}-any`} onChange={() => onToggle(mkAnyCollateral)}>With collateral (any type)</Check>
      <div aria-label="Collateral types" className="si-checks si-col-types" role="group">
        {types.map((type) => (
          <Check checked={anyOn || selected.includes(type)} disabled={anyOn} id={`${idPrefix}-${type}`} key={type} onChange={() => onToggle(type)}>
            {humanizeToken(type)}
          </Check>
        ))}
      </div>
      <Check checked={selected.includes(mkNoCollateral)} id={`${idPrefix}-none`} onChange={() => onToggle(mkNoCollateral)}>No collateral (unsecured)</Check>
    </div>
  );
}

function SmartInvestMatchTable({
  matches,
  onOpen,
  plan,
  onToggle
}: {
  matches: SmartInvestOpportunity[];
  onOpen: (match: SmartInvestOpportunity) => void;
  plan: AllocPlan;
  onToggle: (loanId: string, nextUnticked: boolean) => void;
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
    <div className="smart-invest-match-table with-ticks" role="table" aria-label="Smart Invest matches">
      <div className="smart-invest-match-head" role="row">
        <span /><span>Company</span><span>Yield</span><span>Term</span><span>Collateral</span><span>Available</span><span />
      </div>
      {matches.map((match) => {
        const tickable = isOpenMarketplaceLoan(match as unknown as MarketplaceLoanPreview);
        const ticked = plan.ticked.has(match.loan_id);
        const reason = plan.blocked.get(match.loan_id);
        return (
          <div
            className="smart-invest-match-row"
            key={match.loan_id}
            onClick={() => onOpen(match)}
            role="row"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" && event.target === event.currentTarget) onOpen(match);
            }}
          >
            <span onClick={(event) => event.stopPropagation()}>
              {!tickable ? (
                <BlockedSelectionMarker label={match.title} reason="This opportunity is not currently open for investment." />
              ) : ticked ? (
                <button aria-label={`Untick ${match.title}`} className="dz-tick on" onClick={() => onToggle(match.loan_id, true)} type="button">✓</button>
              ) : reason !== undefined ? (
                <BlockedSelectionMarker label={match.title} reason={reason} />
              ) : (
                <button aria-label={`Tick ${match.title}`} className="dz-tick" onClick={() => onToggle(match.loan_id, false)} type="button" />
              )}
            </span>
            <span>
              <strong>{match.title}</strong>
              <small>{match.originator_name ? `Originated by ${match.originator_name}` : humanizeToken(match.purpose)}</small>
            </span>
            <span>{formatRateBps(match.yield_bps)}</span>
            <span>{match.term_months} mo</span>
            <span>{loanLtvBps(match) === null ? "Unsecured" : `${formatRateBps(loanLtvBps(match) ?? 0)} LTV`}</span>
            <span>{pfMoneyLabel(match.currency, match.fillable_amount_minor)}</span>
            <span aria-hidden="true">→</span>
          </div>
        );
      })}
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
  const wizardRef = useRef<HTMLElement>(null);
  const wizardDialog = useDialog({ dialogRef: wizardRef, onDismiss: onClose });
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
  const collateralTypes = mkOptionUnion(
    smartInvestCatalog.collateralTypes,
    openLoans.filter((loan) => !mkIsUnsecured(loan)).map((loan) => loan.collateral_type),
    filters.col.filter((value) => value !== mkAnyCollateral && value !== mkNoCollateral)
  );
  const currencyOptions = mkOptionUnion(smartInvestCatalog.currencies, filters.ccy).map((code) => ({ value: code, label: code }));
  return (
    <div className="ls-scrim si-wiz-scrim" role="presentation">
      <button aria-label="Close Smart Invest setup" className="ls-overlay-btn" onClick={wizardDialog.dismissFromBackdrop} tabIndex={-1} type="button" />
      <section aria-label="Smart Invest setup" aria-modal="true" className="si-wiz" ref={wizardRef} role="dialog">
        <div className="si-wiz-head">
          <div className="si-wiz-head-main">
            <div className="si-wiz-pips">
              {labels.map((label, index) => (
                <span className={index < step ? "done" : index === step ? "on" : ""} key={label} />
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
              <div className="si-wiz-cap red">Question 1 of 2</div>
              <h3>What must be behind the loan?</h3>
              <p>{securedCount} of the {openLoans.length} open today have something pledged — a mortgage, a charge over equipment, or assigned receivables. The rest rely on the borrower&apos;s promise alone, and collateral never guarantees complete recovery.</p>
              <p className="si-wiz-hint">Tick every kind you accept. Nothing ticked means with or without collateral.</p>
              <SmartInvestCollateralChecks idPrefix="si-wiz-col" onToggle={(value) => update("col", mkToggle(filters.col, value))} selected={filters.col} types={collateralTypes} />
            </>
          ) : null}
          {step === 1 ? (
            <>
              <div className="si-wiz-cap red">Question 2 of 2</div>
              <h3>Which currencies should it use?</h3>
              <p>The rule never converts funds and never combines CHF and EUR balances. A match in a currency you hold nothing of still reaches you — adding money afterwards is your call.</p>
              <p className="si-wiz-hint">Tick one or more. Nothing ticked means any currency.</p>
              <SmartInvestChecks
                idPrefix="si-wiz-ccy"
                label="Currency"
                onToggle={(value) => update("ccy", mkToggle(filters.ccy, value))}
                options={currencyOptions}
                selected={filters.ccy}
              />
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
  const frozenAccount = useFrozenAccount();
  const loansQuery = useMarketplaceLoansData();
  const updateMutation = useV1InvestorSmartInvestUpdate();
  const deactivateMutation = useV1InvestorSmartInvestDeactivateCreate();
  const [filters, setFilters] = useState<MkFilters>(mkDefaultFilters);
  const [editorOpen, setEditorOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [sheetLoanId, setSheetLoanId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [matchUnticked, setMatchUnticked] = useState<Record<string, boolean>>({});
  const [approveOpen, setApproveOpen] = useState(false);
  const balances = useBalancesData().data;
  const data = smartQuery.data;
  const rule = data?.rule;
  const active = rule?.is_active === true;
  const loans = loansQuery.data ?? [];
  const originators = Array.from(
    new Map(loans.filter((loan) => loan.originator_id && loan.originator_name).map((loan) => [loan.originator_id as string, loan.originator_name as string])).entries()
  ).map(([id, name]) => ({ id, name })).sort((left, right) => left.name.localeCompare(right.name));
  // A rule also watches future publications, so it offers the whole catalog
  // (plus any value seen on a loan or already in the rule), not only today's values.
  const ratings = mkOptionUnion(smartInvestCatalog.ratings, loans.map((loan) => loan.risk_rating), filters.rating);
  const purposes = mkOptionUnion(smartInvestCatalog.purposes, loans.map((loan) => loan.purpose), filters.purpose);
  const currencies = mkOptionUnion(smartInvestCatalog.currencies, filters.ccy);
  const collateralTypes = mkOptionUnion(
    smartInvestCatalog.collateralTypes,
    loans.filter((loan) => !mkIsUnsecured(loan)).map((loan) => loan.collateral_type),
    filters.col.filter((value) => value !== mkAnyCollateral && value !== mkNoCollateral)
  );
  const sourceOptions = [
    { value: mkBanxumSource, label: "BANXUM" },
    ...originators.map((originator) => ({ value: originator.id, label: originator.name })),
    ...filters.orig
      .filter((source) => source !== mkBanxumSource && !originators.some((originator) => originator.id === source))
      .map((source) => ({ value: source, label: "Selected Loan Originator" }))
  ];
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
              originators: [],
              collateral: [],
              currencies: [],
              risk_ratings: [],
              purposes: [],
              loan_kinds: [],
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
  const toggle = (key: MkListKey, value: string) => setFilters((current) => ({ ...current, [key]: mkToggle(current[key], value) }));
  const condMark = (selected: string[], unrestricted: string) => (
    <span className={`si-cond-mark${selected.length > 0 ? " on" : ""}`}>{selected.length > 0 ? `${selected.length} ticked` : unrestricted}</span>
  );
  const matchAllocByCcy = new Map<string, number>();
  for (const match of data.matches) {
    if (!matchAllocByCcy.has(match.currency)) {
      matchAllocByCcy.set(
        match.currency,
        balances?.summaries.find((summary) => summary.currency === match.currency)?.investable_minor ?? 0
      );
    }
  }
  const matchTickable = data.matches.filter((match) =>
    isOpenMarketplaceLoan(match as unknown as MarketplaceLoanPreview)
  ) as unknown as MarketplaceLoanPreview[];
  const matchPlan = allocationPlan(matchTickable, matchUnticked, matchAllocByCcy, balances?.lots);

  return (
    <main className="content smart-invest-page">
      <PageHead
        className="si-hero"
        description={
          <>
            <p>You decide the conditions.</p>
            <p>Nothing is ever committed without your explicit approval.</p>
          </>
        }
        title="It finds them. You approve them."
      />

      <section aria-label="Smart Invest status" className={`card si-status${active ? " active" : ""}`}>
        <div className="si-status-main">
          <h2 className="si-status-title">
            Smart Invest <span className={`si-state ${active ? "active" : "inactive"}`}>{active ? "Active" : "Not active"}</span>
          </h2>
          {active ? (
            <p className="si-active-text">The rule is watching for opportunities that meet these conditions. When a qualifying opportunity is published we notify you with the match ready to review — nothing is committed until you do.</p>
          ) : null}
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
          <div className="si-active-actions">
            <button className="si-pill-outline" onClick={() => setEditorOpen(true)} type="button">Adjust the rule</button>
            <button className="si-pill-dark" disabled={saving} onClick={() => void deactivate()} type="button">Deactivate the rule</button>
          </div>
        )}
      </section>

      {active || editorOpen ? (
        <section className="card si-conditions" id="rule-conditions">
          <button aria-expanded={editorOpen} className="si-cond-toggle" onClick={() => setEditorOpen((open) => !open || !active)} type="button">
            <h2>See your rule</h2>
            <span className="si-cond-summary">{smartInvestRuleSummary(editorOpen ? filters : smartInvestFiltersFromRule(rule), originators).slice(0, 3).map((row) => row.value).join(" · ")}</span>
            <span className="si-cond-spacer" />
            <span className={`si-cond-cta${editorOpen ? " on" : ""}`}>{editorOpen ? "Close" : "Open"} <span aria-hidden="true">{editorOpen ? "▴" : "▾"}</span></span>
          </button>
          {!editorOpen && active ? (
            <dl className="si-rule-kv">
              {smartInvestRuleSummary(smartInvestFiltersFromRule(rule), originators).map((row) => (
                <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>
              ))}
            </dl>
          ) : null}
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
                <div className="si-cond-card wide">
                  <div className="si-cond-head"><span className="si-cond-cap">Collateral</span>{condMark(filters.col, "With or without")}</div>
                  <SmartInvestCollateralChecks idPrefix="si-ed-col" onToggle={(value) => toggle("col", value)} selected={filters.col} types={collateralTypes} />
                  <div className="si-cond-note">With collateral (any type) includes every collateral type, also ones added later. Collateral can reduce loss severity, but it does not guarantee repayment or complete recovery.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-head"><span className="si-cond-cap">Which currency</span>{condMark(filters.ccy, "Any currency")}</div>
                  <SmartInvestChecks idPrefix="si-ed-ccy" label="Currency" onToggle={(value) => toggle("ccy", value)} options={currencies.map((code) => ({ value: code, label: code }))} selected={filters.ccy} />
                  <div className="si-cond-note">The rule never converts funds and never combines CHF and EUR balances.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-head"><span className="si-cond-cap">Loan type</span>{condMark(filters.kind, "Any loan type")}</div>
                  <SmartInvestChecks idPrefix="si-ed-kind" label="Loan type" onToggle={(value) => toggle("kind", value)} options={smartInvestCatalog.loanKinds.map((kind) => ({ value: kind, label: mkLoanKindLabel(kind) }))} selected={filters.kind} />
                </div>
                <div className="si-cond-card wide">
                  <div className="si-cond-head"><span className="si-cond-cap">Risk rating</span>{condMark(filters.rating, "Any rating")}</div>
                  <SmartInvestChecks compact idPrefix="si-ed-rating" label="Risk rating" onToggle={(value) => toggle("rating", value)} options={ratings.map((rating) => ({ value: rating, label: mkRatingLabel(rating) }))} selected={filters.rating} />
                  <div className="si-cond-note">The rating is arithmetic, not advice. The same facts sit on every loan&apos;s own page.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-head"><span className="si-cond-cap">Originated by</span>{condMark(filters.orig, "Any source")}</div>
                  <SmartInvestChecks idPrefix="si-ed-orig" label="Originated by" onToggle={(value) => toggle("orig", value)} options={sourceOptions} selected={filters.orig} />
                  <div className="si-cond-note">Direct loans are written by BANXUM. Purchased claims come from a named originator that keeps a slice beside you.</div>
                </div>
                <div className="si-cond-card">
                  <div className="si-cond-head"><span className="si-cond-cap">Purpose</span>{condMark(filters.purpose, "Any purpose")}</div>
                  <SmartInvestChecks idPrefix="si-ed-purpose" label="Purpose" onToggle={(value) => toggle("purpose", value)} options={purposes.map((purpose) => ({ value: purpose, label: humanizeToken(purpose) }))} selected={filters.purpose} />
                </div>
              </div>
              <p className="si-cond-intro si-cond-hint">Within one condition, tick as many options as you like: a loan qualifies if it matches any of them. Nothing ticked means no restriction.</p>
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
          <div className="smart-invest-section-title"><div><div className="eyebrow">Matched by your rule</div><h2>{data.match_count} open {data.match_count === 1 ? "opportunity" : "opportunities"}</h2></div><button className="btn" onClick={() => goTo(setRoute, "market")} type="button">Open full marketplace</button></div>
          <div className="card si-matches-card">
            <SmartInvestMatchTable
              matches={data.matches}
              onOpen={(match) => setSheetLoanId(match.loan_id)}
              onToggle={(loanId, nextUnticked) => setMatchUnticked((current) => ({ ...current, [loanId]: nextUnticked }))}
              plan={matchPlan}
            />
            {matchPlan.ticked.size > 0 || data.matches.length > 0 ? (
              <div className="aa-foot-row page">
                <span className="aa-selected">{matchPlan.ticked.size} selected</span>
                <span className="aa-foot-dots" />
                <span className="aa-committing">committing</span>
                <span className="aa-commit-total num">{allocCommitLabel(matchPlan.totals)}</span>
                <button className="si-dash-setup" disabled={matchPlan.ticked.size === 0 || frozenAccount.frozen} onClick={() => setApproveOpen(true)} type="button">Review &amp; confirm →</button>
              </div>
            ) : null}
            {frozenAccount.frozen && data.matches.length > 0 ? (
              <p className="aa-foot-note">{frozenActionReason(frozenAccount)}</p>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="card smart-invest-limitations">
        <h2>What the rule will not do</h2>
        <div>
          <p><b>01</b><strong>It does not judge a borrower.</strong> A yield above your floor is not a sign of quality. The rule matches disclosed fields only.</p>
          <p><b>02</b><strong>It never invests for you.</strong> No balance is reserved and no order is placed until you review an opportunity and complete its normal confirmation flow.</p>
          <p><b>03</b><strong>It does not guarantee availability.</strong> A match can fill, close, change status or stop accepting investments before you act.</p>
          <p><b>04</b><strong>It does not combine currencies.</strong> CHF and EUR opportunities and balances remain separate, even when your rule accepts both.</p>
        </div>
      </section>
      {approveOpen ? (
        <ApproveAllocationModal
          initialUnticked={matchUnticked}
          matches={data.matches as unknown as MarketplaceLoanPreview[]}
          onClose={() => setApproveOpen(false)}
          onDone={() => {
            setApproveOpen(false);
            void smartQuery.refetch();
            void loansQuery.refetch();
          }}
          setInvestLoan={setInvestLoan}
          setRoute={setRoute}
        />
      ) : null}
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
function plainMoneyInput(amountMinor: number, currency: string) {
  return formatMoneyMinor(amountMinor, currency).replace(/[^\d.]/g, "");
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

/** Public preview grid: project cards with only the MKT-DEC-002 fields. */
function LoansTable({ loans, onOpen }: { loans: PublicMarketplaceLoan[]; onOpen: (loan: PublicMarketplaceLoan) => void; preview?: boolean }) {
  if (loans.length === 0) {
    return (
      <div className="portal-table-empty">
        <Empty icon="market" title="No loan previews available">
          There are no published loan previews right now. Check again later or register to receive marketplace updates.
        </Empty>
      </div>
    );
  }
  return (
    <div className="site-projects loans-preview-grid">
      {loans.map((loan) => (
        <SiteProjectCard key={loan.loan_id} loan={loan} onOpen={onOpen} />
      ))}
    </div>
  );
}

function BalancesScreen({ demoState }: { demoState: DemoAccountState }) {
  const balancesQuery = useBalancesData();
  const frozenAccount = useFrozenAccount();
  const balances = balancesQuery.data;
  const [currency, setCurrency] = useState<"CHF" | "EUR">("CHF");
  const [modal, setModal] = useState<"deposit" | "withdraw" | "iban" | null>(null);
  // The account cards open the deposit and withdrawal dialogs for their own
  // currency; the page actions keep using the selected currency.
  const [modalCurrency, setModalCurrency] = useState<string>("CHF");
  const pageDescription = "Funds are non-interest-bearing and subject to a 60-day holding limit.";
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
      {readonly ? (
        <div className="col gap-12 acct-alerts">
          {readonly ? (
            <Banner icon="lock" tone="info" title="Read-only view">
              Deposits, withdrawals and payout-IBAN changes are disabled during superadmin read-only impersonation.
            </Banner>
          ) : null}
        </div>
      ) : null}

      <div className="acct-ccy-grid">
        {balances.summaries.map((item) => {
          const ccy = item.currency;
          const nextDeadline = item.next_withdrawal_deadline_at;
          return (
            <section className="card acct-ccy" key={ccy}>
              <h2 className="acct-ccy-title">{ccy} account</h2>
              <div className="acct-ccy-amount num">{ccy} {formatMoneyMinor(item.total_available_minor, ccy)}</div>
              <ul className="acct-ccy-list">
                <BucketTile label="Potentially investable" value={item.investable_minor} currency={ccy} tone="ok" sub="Depends on the loan funding window" />
                <BucketTile label="Withdraw-only" value={item.withdraw_only_minor} currency={ccy} tone="warn" sub="Day 60: can only be withdrawn, until the end of today" />
                <BucketTile label="Overdue" value={item.overdue_minor} currency={ccy} tone="warn" sub="Past the day-60 deadline" />
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
                  {nextDeadline ? <>Earliest holding deadline: <strong>{formatDate(nextDeadline)}</strong></> : "No holding deadline running."}
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
        <BalanceLotsTable lots={lots} frozen={previewFrozen} />
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
          <li>Every incoming amount has a 60-day holding limit.</li>
          <li>To invest, that amount must have enough time left to cover the loan's remaining funding period. Shorter periods can use older funds.</li>
          <li>Eligible lots are consumed oldest-first.</li>
          <li>FX conversion does not reset this limit.</li>
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

function BalanceLotsTable({ lots, frozen }: { lots: BalanceLot[]; frozen: boolean }) {
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
                    <DeadlineMeter daysUntilWithdrawal={lot.days_until_withdrawal_deadline} />
                    <div className="lot-deadline-meta">
                      <span>{lot.days_until_withdrawal_deadline > 0 ? `${lot.days_until_withdrawal_deadline}d holding time left` : lot.days_until_withdrawal_deadline === 0 ? "Day 60: last day" : "Holding deadline passed"}</span>
                      <span>{lot.days_until_withdrawal_deadline >= 0 ? `Withdraw by end of ${formatDate(lot.withdrawal_deadline_at)}` : `Deadline: ${formatDate(lot.withdrawal_deadline_at)}`}</span>
                    </div>
                  </td>
                  <td data-label="Status"><Chip status={penalty ? "penalty" : lot.bucket} /></td>
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
          <p className="acct-modal-note">The bank value date starts the new balance lot's 60-day holding period.</p>
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
          // One key per withdrawal intent: a retry after a timeout is recognised by
          // the server and not paid out twice. New amount or IBAN, new key.
          idempotency_key: intentIdempotencyKey("investor-withdrawal", {
            amount_minor: amountMinor,
            currency,
            destination_iban: selectedInstruction.destination_iban,
            destination_account_name: selectedInstruction.destination_account_name
          }),
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
  return Number.isFinite(value) && value > 0 ? value.toFixed(4) : "-";
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
                ? `Converting makes ${fxMoneyLabel(to, preview.target_amount_minor)} available in your ${to} balance. Converted money keeps the earliest deadline of the funds it came from — FX never resets the 60-day holding clock.`
                : "Converted money keeps the earliest deadline of the funds it came from — FX never resets the 60-day holding clock."}
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
      setDone(true);
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
        <SuccessState title={`${formatMoneyLabel(to, targetMinor)} credited`}>
          The new {to} lot inherits the deadline of the consumed source lots. FX does not reset the 60-day holding clock.
        </SuccessState>
      </Modal>
    );
  }
  return (
    <Modal
      busy={executeMutation.isPending}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ack || code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || executeMutation.isPending || quoteExpired || refreshing} variant="primary" onClick={executeFx}>{executeMutation.isPending ? "Executing..." : "Confirm exchange"}</Button></>}
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
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={emailCodeRequestDisabled(codeRequest)}
          requestLabel={emailCodeRequestLabel(codeRequest)}
          value={code}
          onChange={setCode}
          onRequest={codeRequest.requestCode}
        />
        <Banner tone="warn" title="Inherited ageing deadline">The target balance inherits the earliest consumed source-lot deadline. It does not start a fresh 60-day holding period.</Banner>
        <Check checked={ack} id="fx-ack" onChange={setAck}>I accept the currency-exchange terms and understand the rate, fee and inherited deadline.</Check>
        {codeRequest.error || error || (quoteExpired && refreshError) ? <Banner tone="bad" title="Could not execute FX">{codeRequest.error || error || refreshError}</Banner> : null}
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
  const [tab, setTab] = useState<"holdings" | "completed" | "activity" | "orders">("holdings");
  const [currency, setCurrency] = useState<string | null>(null);
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
  const completed = completedHoldings(portfolio.holdings);
  const currencies = pfCurrencies(active);
  const scopedCurrency = currency && currencies.includes(currency) ? currency : currencies[0] ?? "CHF";
  const scoped = active.filter((holding) => holding.currency === scopedCurrency);
  const totalMinor = scoped.reduce((sum, holding) => sum + holding.current_principal_minor, 0);

  return (
    <main className="content pf-page">
      <PageHead
        actions={currencies.length > 1 ? (
          <div aria-label="Portfolio currency" className="seg">
            {currencies.map((code) => (
              <button className={code === scopedCurrency ? "on" : ""} key={code} onClick={() => setCurrency(code)} type="button">{code}</button>
            ))}
          </div>
        ) : undefined}
        className="pf-head"
        description="Largest first, because the largest is the one that matters most if it goes wrong. Click any loan for the split, the collateral and the schedule."
        eyebrow={<>{pfLoansLabel(pfLoanCount(scoped))} · {pfMoneyLabel(scopedCurrency, totalMinor)} lent</>}
        title="Everything you own."
      />
      {scoped.length > 0 ? (
        <PfPortfolioWidgets currency={scopedCurrency} holdings={scoped} totalMinor={totalMinor} />
      ) : null}
      <div className="pf-tabs-row">
        <nav aria-label="Portfolio sections" className="tabs pf-tabs" onKeyDown={handleTabListKeyDown} role="tablist">
          <button aria-controls="pf-tab-panel" aria-selected={tab === "holdings"} className={tab === "holdings" ? "on" : ""} id="pf-tab-holdings" onClick={() => setTab("holdings")} role="tab" tabIndex={tab === "holdings" ? 0 : -1} type="button">My loans</button>
          <button aria-controls="pf-tab-panel" aria-selected={tab === "completed"} className={tab === "completed" ? "on" : ""} id="pf-tab-completed" onClick={() => setTab("completed")} role="tab" tabIndex={tab === "completed" ? 0 : -1} type="button">Completed</button>
          <button aria-controls="pf-tab-panel" aria-selected={tab === "activity"} className={tab === "activity" ? "on" : ""} id="pf-tab-activity" onClick={() => setTab("activity")} role="tab" tabIndex={tab === "activity" ? 0 : -1} type="button">Activity</button>
          <span className="pf-tab-item">
            <button aria-controls="pf-tab-panel" aria-selected={tab === "orders"} className={tab === "orders" ? "on" : ""} id="pf-tab-orders" onClick={() => setTab("orders")} role="tab" tabIndex={tab === "orders" ? 0 : -1} type="button">Orders</button>
            <PrimaryOrdersInfo orders={openOrders} />
          </span>
        </nav>
      </div>
      <div aria-labelledby={`pf-tab-${tab}`} className="pf-tab-panel" id="pf-tab-panel" role="tabpanel">
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
            <PfMyLoans
              currency={scopedCurrency}
              holdings={scoped}
              onOpen={(holding) => goTo(setRoute, "investment", { holdingId: holding.id })}
              totalMinor={totalMinor}
            />
          )
        ) : null}
        {tab === "completed" ? (
          <CompletedHoldingsTable holdings={completed} onOpen={(holding) => goTo(setRoute, "investment", { holdingId: holding.id })} />
        ) : null}
        {tab === "activity" ? <ActivityTable entries={activity.entries} /> : null}
        {tab === "orders" ? <OrdersTable onBrowse={() => goTo(setRoute, "market")} orders={orders.orders} /> : null}
      </div>
      {scoped.length > 0 ? (
        <div className="pf-howlink">
          <button onClick={() => goTo(setRoute, "faq")} type="button">
            <span className="pf-howlink-i">i</span>
            <span className="pf-howlink-text">How BANXUM loans work</span>
          </button>
        </div>
      ) : null}
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

// Design "project tile": a small black square with a white line icon, picked
// from the collateral type (or purpose) the loan already carries.
function pfTileIcon(...hints: string[]): IconName {
  const text = hints.join(" ").toLowerCase().replaceAll("_", " ");
  if (/real estate|property|immobil|hospitality|hotel/.test(text)) return "home";
  if (/receivable|invoice|factoring/.test(text)) return "doc";
  if (/solar|energy/.test(text)) return "trend";
  if (/equipment|machinery|tooling|vessel|capex/.test(text)) return "settings";
  if (/land|agricult/.test(text)) return "pin";
  if (/inventory|logistic|cargo|warehouse/.test(text)) return "briefcase";
  if (/unsecured|bridge|software/.test(text)) return "chart";
  return "building";
}

function PfTile({ hints }: { hints: string[] }) {
  return (
    <span aria-hidden="true" className="inv-tile">
      <Icon name={pfTileIcon(...hints)} size={18} />
    </span>
  );
}

/* ---- Portfolio redesign (website_redesign/portfolio.html port) ---- */

function pfActiveHoldings(holdings: Holding[]) {
  return holdings.filter((holding) => holding.status === "active" && holding.current_principal_minor > 0);
}

/** Number of distinct loans; one loan can be held in several lots (MKT-DEC-020). */
function pfLoanCount(holdings: Pick<Holding, "loan">[]) {
  return new Set(holdings.map((holding) => holding.loan.loan_id)).size;
}

function pfLoansLabel(count: number) {
  return `${count} ${count === 1 ? "loan" : "loans"}`;
}

/** Loan ids held in more than one lot: their rows show when each lot was bought. */
function pfMultiLotLoanIds(holdings: Pick<Holding, "loan">[]) {
  const counts = new Map<string, number>();
  for (const holding of holdings) counts.set(holding.loan.loan_id, (counts.get(holding.loan.loan_id) ?? 0) + 1);
  return new Set(Array.from(counts.entries()).filter(([, count]) => count > 1).map(([loanId]) => loanId));
}

function pfLotLabel(holding: Pick<Holding, "assignment_effective_at" | "source_type">) {
  const verb = holding.source_type === "secondary_market" ? "bought" : "invested";
  return `${verb} on ${formatDate(holding.assignment_effective_at)}`;
}

function pfCurrencies(holdings: Holding[]) {
  const totals = new Map<string, number>();
  for (const holding of holdings) {
    totals.set(holding.currency, (totals.get(holding.currency) ?? 0) + holding.current_principal_minor);
  }
  return Array.from(totals.entries()).sort((left, right) => right[1] - left[1]).map(([code]) => code);
}

function pfMoneyLabel(currency: string, amountMinor: number) {
  return formatMoneyLabel(currency, amountMinor);
}

function pfWholeLabel(currency: string, amountMinor: number) {
  return pfMoneyLabel(currency, amountMinor);
}

function pfDefaultInterestLabel(values: number[]) {
  const configured = values.filter((value) => value > 0);
  if (configured.length === 0) return "None";
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

// Keyed off the pledged collateral value, not the recorded type: a value of 0 means nothing is pledged.
function pfIsUnsecured(holding: Holding) {
  return isUnsecuredHolding(holding);
}

function pfHoldingCollateralLabel(holding: Holding) {
  return pfIsUnsecured(holding) ? pfCollateralShortLabels.unsecured_exception : pfCollateralLabel(holding.loan.collateral_type);
}

function pfShortDate(iso: string) {
  const date = new Date(`${iso}T00:00:00`);
  const now = platformTodayLocalDate();
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
        collateral: pfHoldingCollateralLabel(holding),
        ltvBps: loanLtvBps(holding.loan)
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
  const coverPct = weightedLtvPercent(holdings) ?? 0;

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
  const breakdown = collateralBreakdown(holdings, (holding) => pfCollateralLabel(holding.loan.collateral_type));
  const sorted = breakdown.secured;
  const unsecured = breakdown.unsecuredMinor;
  const palette = ["#0a0a0a", "#4a4a4a", "#8a8a8a"];
  const segments: { label: string; amount: number; color: string; bad?: boolean }[] = [];
  sorted.slice(0, 3).forEach(([label, amount], index) => {
    segments.push({ label: humanizeToken(label), amount, color: palette[index] });
  });
  const otherMinor = sorted.slice(3).reduce((sum, [, amount]) => sum + amount, 0);
  if (otherMinor > 0) segments.push({ label: "Other assets", amount: otherMinor, color: "#c8c8c8" });
  if (unsecured > 0) segments.push({ label: "No asset pledged", amount: unsecured, color: "#b3261e", bad: true });
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
          <text fill="#0a0a0a" fontFamily="Archivo, Helvetica, Arial, sans-serif" fontSize={center.title.length > 11 ? "12.5" : "17"} fontWeight="600" letterSpacing="-0.3" textAnchor="middle" x={size / 2} y={size / 2 - 3}>{center.title}</text>
          <text fill="#6e6e6e" fontFamily="Archivo, Helvetica, Arial, sans-serif" fontSize="9.5" fontWeight="600" letterSpacing=".02em" textAnchor="middle" x={size / 2} y={size / 2 + 12}>{center.sub}</text>
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
  if (key === "col") return pfHoldingCollateralLabel(holding);
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
  const multiLotLoanIds = pfMultiLotLoanIds(holdings);
  const [totalWhole, totalCents = "00"] = formatMoneyMinor(totalMinor, currency).split(".");

  return (
    <div className="pf-loans card">
      <div className="pf-sect-row">
        <div className="pf-sect-title">
          <h2 className="sect">My loans</h2>
          <p className="pf-sect-note">The rule under each amount is that loan's share of everything you have lent. Click any column heading to sort, or open the loan for the split, the collateral and the full schedule.</p>
        </div>
        <div className="pf-sect-tools">
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
          <div aria-label="Table view" className="seg" onKeyDown={handleTabListKeyDown} role="tablist">
            <button aria-selected={view === "focused"} className={view === "focused" ? "on" : ""} onClick={() => selectView("focused")} role="tab" tabIndex={view === "focused" ? 0 : -1} type="button">Focused</button>
            <button aria-selected={view === "detailed"} className={view === "detailed" ? "on" : ""} onClick={() => selectView("detailed")} role="tab" tabIndex={view === "detailed" ? 0 : -1} type="button">Detailed</button>
          </div>
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
          <span aria-hidden="true" className="pf-col-chev" />
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
                  <PfTile hints={[holding.loan.collateral_type, holding.loan.purpose]} />
                  <span className="pf-company-text">
                    <span className="pf-company-line">
                      <span className={`pf-company-name${late ? " late" : ""}`}>{holding.loan.borrower_name || holding.loan.loan_title}</span>
                      {late ? (
                        holding.loan.loan_status === "defaulted"
                          ? <span className="pf-tag late default">default</span>
                          : <span className="pf-tag late">late</span>
                      ) : null}
                      {listing ? <span className="pf-tag">{listingStatusLabel(listing.status)}</span> : null}
                    </span>
                    <span className="pf-company-sub">
                      {holding.loan.loan_title}
                      {multiLotLoanIds.has(holding.loan.loan_id) ? <span className="pf-lot-label"> · {pfLotLabel(holding)}</span> : null}
                    </span>
                  </span>
                </span>
                <span className="detail-col num pf-col-rate strong">{formatRateBps(holding.loan.interest_rate_bps)}</span>
                <span className="detail-col num pf-col-term mut">{holding.loan.term_months} mo</span>
                <span className="detail-col pf-col-pays mut">{pfPaysLabel(holding.loan.repayment_type)}</span>
                <span className="detail-col pf-col-collateral mut">{pfHoldingCollateralLabel(holding)}</span>
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
                <span aria-hidden="true" className="pf-col-chev"><Icon name="chevR" size={16} /></span>
              </button>
            );
          })}
        </div>
        <div className="tfoot">
          <span className="pf-tfoot-count">{pfLoansLabel(pfLoanCount(sorted))}{sorted.length > pfLoanCount(sorted) ? ` · ${sorted.length} lots` : ""}</span>
          <span className="pf-tfoot-note">The rule under each amount is that loan's share of your portfolio. Red marks a loan in arrears.</span>
          <span className="pf-tfoot-ccy">{currency}</span>
          <span className="num pf-tfoot-total">{totalWhole}</span>
          <span className="num pf-tfoot-cents">.{totalCents}</span>
          <span aria-hidden="true" className="pf-col-chev" />
        </div>
      </div>
    </div>
  );
}

function PfPortfolioWidgets({ currency, holdings, totalMinor }: { currency: string; holdings: Holding[]; totalMinor: number }) {
  const [openPanel, setOpenPanel] = useState<"cal" | "hex" | "col" | "risk" | null>(null);
  const payments = pfPayments(holdings);
  const axes = pfAxes(holdings, currency, totalMinor);
  const lowestAxis = axes.reduce((low, axis) => (axis.score < low.score ? axis : low), axes[0]);
  const segments = pfRingSegments(holdings);
  const largestSegment = segments[0];
  const securedLtvs = valuedSecuredHoldings(holdings).map((holding) => (loanLtvBps(holding.loan) ?? 0) / 100);
  const weightedLtv = weightedLtvPercent(holdings);
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
              foot={<><span className="big" style={{ color: lowestAxis.score < 50 ? "#b3261e" : "#0a0a0a" }}>{lowestAxis.score}</span><span className="note">out of 100 is your lowest of six scores · <span style={{ color: "#0a0a0a", fontWeight: 600 }}>{lowestAxis.label.toLowerCase()}</span></span></>}
              lab="Spread of portfolio"
              onToggle={() => toggle("hex")}
              open={openPanel === "hex"}
              tt="How much rests on one outcome"
            >
              <span style={{ display: "flex", justifyContent: "center", marginBottom: 10, width: "100%" }}>
                <svg height="102" shapeRendering="geometricPrecision" style={{ display: "block" }} viewBox="0 0 44 40" width="112">
                  <polygon fill="none" points="22,2 37.59,11 37.59,29 22,38 6.41,29 6.41,11" stroke="#e6e6e6" strokeWidth=".8" />
                  <polygon fill="rgba(21,23,25,.12)" points={pfHexPoints(axes.map((axis) => axis.score), 22, 20, 18)} stroke="#0a0a0a" strokeWidth="1" />
                  {(() => {
                    const index = axes.indexOf(lowestAxis);
                    const vertex = pfHexVertex(index, 22, 20, 18, lowestAxis.score);
                    return <circle cx={vertex.x.toFixed(2)} cy={vertex.y.toFixed(2)} fill="#b3261e" r="1.5" />;
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
                      <span style={{ background: segment.color, flex: "none", height: 9, width: 9 }} />
                      <span style={{ color: segment.bad ? "#b3261e" : "#2a2a2a", flex: 1 }}>{segment.label}</span>
                      <span className="num" style={{ color: segment.bad ? "#b3261e" : undefined, fontWeight: 600 }}>{totalMinor > 0 ? `${((segment.amount / totalMinor) * 100).toFixed(1)}%` : "-"}</span>
                    </span>
                  ))}
                </span>
              </span>
            </PfCard>
          </div>
          {openPanel === "col" ? <PfCollateralPanel currency={currency} holdingCount={pfLoanCount(holdings)} segments={segments} totalMinor={totalMinor} /> : null}

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
                  <span style={{ border: "1.5px solid #c8c8c8", display: "flex", flex: 1, flexDirection: "column", height: 104, justifyContent: "flex-end", overflow: "hidden" }}>
                    <span style={{ background: "#0a0a0a", display: "block", height: `${weightedLtv === null ? 0 : weightedLtv.toFixed(1)}%` }} />
                  </span>
                  <span style={{ color: "#6e6e6e", display: "flex", flex: "none", flexDirection: "column", fontSize: 10, height: 104, justifyContent: "space-between", padding: "1px 0" }}>
                    <span>valuation</span>
                    <span style={{ color: "#0a0a0a", fontWeight: 600 }}>lent</span>
                  </span>
                </span>
                <span style={{ display: "flex", flex: 1, flexDirection: "column", fontSize: 11.5, gap: 7, minWidth: 0 }}>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#2a2a2a", flex: 1 }}>Weighted LTV</span><span className="num" style={{ fontWeight: 600 }}>{weightedLtv === null ? "—" : `${weightedLtv.toFixed(1)}%`}</span></span>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#2a2a2a", flex: 1 }}>Range per project</span><span className="num" style={{ fontWeight: 600 }}>{securedLtvs.length > 0 ? `${Math.min(...securedLtvs).toFixed(0)} – ${Math.max(...securedLtvs).toFixed(0)}%` : "—"}</span></span>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#2a2a2a", flex: 1 }}>Nothing pledged</span><span className="num" style={{ color: unsecuredHoldings.length > 0 ? "#b3261e" : undefined, fontWeight: 600 }}>{pfLoanCount(unsecuredHoldings)} of {pfLoanCount(holdings)}</span></span>
                  <span style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ color: "#2a2a2a", flex: 1 }}>In arrears now</span><span className="num" style={{ color: lateHoldings.length > 0 ? "#b3261e" : undefined, fontWeight: 600 }}>{pfLoanCount(lateHoldings)} of {pfLoanCount(holdings)}</span></span>
                </span>
              </span>
            </PfCard>
          </div>
          {openPanel === "risk" ? (
            <PfProtectionPanel
              currency={currency}
              holdingCount={pfLoanCount(holdings)}
              lateCount={pfLoanCount(lateHoldings)}
              lateMinor={lateMinor}
              securedLtvs={securedLtvs}
              defaultInterestBps={defaultInterestBps}
              unsecuredCount={pfLoanCount(unsecuredHoldings)}
              unsecuredMinor={unsecuredMinor}
              weightedLtv={weightedLtv}
            />
          ) : null}
        </div>
      </div>

    </section>
  );
}

function PfCalendarCard({ currency, open, onToggle, payments }: { currency: string; open: boolean; onToggle: () => void; payments: PfPayment[] }) {
  // "This month" and "next" follow the platform business date (QA clock), not the browser clock.
  const now = platformTodayLocalDate();
  const monthPayments = payments.filter((payment) => payment.date.getFullYear() === now.getFullYear() && payment.date.getMonth() === now.getMonth());
  const paymentDays = new Set(monthPayments.map((payment) => payment.date.getDate()));
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const offset = (monthStart.getDay() + 6) % 7;
  const monthLabel = now.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
  const upcoming = payments.find((payment) => payment.date.getTime() >= new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime());
  return (
    <PfCard
      foot={<><span className="big">{paymentDays.size}</span><span className="note">payment dates in {monthLabel} · next is {upcoming ? <span style={{ color: "#0a0a0a", fontWeight: 600 }}>{pfShortDate(upcoming.iso)}, {pfMoneyLabel(currency, upcoming.amt)}</span> : "—"}</span></>}
      lab="Earnings calendar"
      onToggle={onToggle}
      open={open}
      tt="Every date you are owed money"
    >
      <span style={{ display: "grid", gap: 4, gridTemplateColumns: "repeat(7,1fr)", marginBottom: 18, width: "100%" }}>
        {Array.from({ length: 35 }, (_, cell) => {
          const day = cell - offset + 1;
          const has = day >= 1 && paymentDays.has(day);
          return <span key={cell} style={{ background: has ? "#0a0a0a" : "#e6e6e6", height: 9 }} />;
        })}
      </span>
    </PfCard>
  );
}

function PfCalendarPanel({ currency, payments }: { currency: string; payments: PfPayment[] }) {
  const [monthIndex, setMonthIndex] = useState(0);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const now = platformTodayLocalDate();
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
          <span className="cal-legend"><span style={{ background: "#1e7a46", height: 9, width: 9 }} />payday</span>
          <span className="cal-legend"><span style={{ background: "#0a0a0a", height: 2, width: 9 }} />final payment</span>
          <span className="cal-legend"><span style={{ background: "#b3261e", height: 9, width: 9 }} />late</span>
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
                      <span style={{ color: row.late ? "#b3261e" : "#0a0a0a", fontSize: 16, fontWeight: 600, letterSpacing: "-0.02em" }}>{row.name}</span>
                      <span className="grow" />
                      <span className="num" style={{ fontSize: 16, fontWeight: 600 }}>{pfMoneyLabel(currency, row.amt)}</span>
                    </div>
                  ) : null}
                  <div style={{ display: "flex", flexDirection: "column", fontSize: 13.5, marginBottom: 12 }}>
                    <div className="pf-cal-kv"><span style={{ color: "#1e7a46" }}>Interest — what you earn</span><span className="leader" /><span className="num" style={{ color: "#1e7a46", fontWeight: 600 }}>{formatMoneyMinor(row.int, currency)}</span></div>
                    <div className="pf-cal-kv"><span>Your money coming back</span><span className="leader" /><span className="num" style={{ fontWeight: 600 }}>{formatMoneyMinor(row.pri, currency)}</span></div>
                    <div className="pf-cal-kv"><span>Still outstanding</span><span className="leader" /><span className="num" style={{ fontWeight: 600 }}>{formatMoneyMinor(row.balanceAfter, currency)}</span></div>
                    <div className="pf-cal-kv"><span>Installment</span><span className="leader" /><span className="num" style={{ fontWeight: 600 }}>{row.n} of {row.term}</span></div>
                  </div>
                  <div style={{ color: "#6e6e6e", fontSize: 13, lineHeight: 1.55 }}>
                    Secured by {row.collateral === "unsecured" ? "no pledged asset" : row.collateral}.
                    {row.ltvBps !== null ? ` Lent against an independent valuation · ${formatRateBps(row.ltvBps)} of the valuation.` : ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="cal-footnote">
            <span style={{ color: "#6e6e6e", fontSize: 13.5 }}>Bars are scaled within the month, so the longest one is that month's largest payment.</span>
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
            <polygon fill="#ffffff" points={gridPoints(radius)} stroke="#c8c8c8" strokeWidth="1" />
            <polygon fill="none" points={gridPoints(radius * 0.75)} stroke="#e6e6e6" strokeWidth="1" />
            <polygon fill="none" points={gridPoints(radius * 0.5)} stroke="#e6e6e6" strokeWidth="1" />
            <polygon fill="none" points={gridPoints(radius * 0.25)} stroke="#e6e6e6" strokeWidth="1" />
            {Array.from({ length: 6 }, (_, index) => {
              const angle = -Math.PI / 2 + (index * Math.PI) / 3;
              return <line key={index} stroke="#e6e6e6" strokeWidth="1" x1={cx} x2={(cx + radius * Math.cos(angle)).toFixed(2)} y1={cy} y2={(cy + radius * Math.sin(angle)).toFixed(2)} />;
            })}
            <polygon fill="rgba(21,23,25,0.12)" points={pfHexPoints(axes.map((axis) => axis.score), cx, cy, radius)} stroke="#0a0a0a" strokeWidth="2" />
            {axes.map((axis, index) => {
              const vertex = pfHexVertex(index, cx, cy, radius, axis.score);
              return <circle cx={vertex.x.toFixed(2)} cy={vertex.y.toFixed(2)} fill={axis === lowest ? "#b3261e" : "#0a0a0a"} key={axis.label} r="4" />;
            })}
            {axes.map((axis, index) => {
              const anchor = labelAnchors[index];
              return (
                <g key={axis.label}>
                  <text fill="#0a0a0a" fontFamily="Archivo, Helvetica, Arial, sans-serif" fontSize="12" fontWeight="600" textAnchor={anchor.anchor} x={anchor.x} y={anchor.y}>{axis.label}</text>
                  <text fill={axis === lowest ? "#b3261e" : "#0a0a0a"} fontFamily="Archivo, Helvetica, Arial, sans-serif" fontSize="13" fontWeight="700" textAnchor={anchor.anchor} x={anchor.x} y={anchor.y + 16}>{axis.score}</text>
                </g>
              );
            })}
          </svg>
          <div style={{ flex: 1, minWidth: 0, paddingTop: 4 }}>
            <div className="microlabel" style={{ marginBottom: 14 }}>What each number is, and what its ends mean</div>
            <div style={{ display: "flex", flexDirection: "column", fontSize: 13 }}>
              {axes.map((axis, index) => (
                <div key={axis.label} style={{ borderBottom: index === axes.length - 1 ? "1px solid #e6e6e6" : undefined, borderTop: "1px solid #e6e6e6", padding: "9px 0" }}>
                  <div style={{ alignItems: "baseline", display: "flex" }}>
                    <span style={{ color: axis === lowest ? "#b3261e" : undefined, fontWeight: 600 }}>{axis.label}</span>
                    <span className="leader" style={{ margin: "0 8px 4px" }} />
                    <span className="num" style={{ color: axis === lowest ? "#b3261e" : undefined, fontWeight: 700 }}>{axis.score}</span>
                  </div>
                  <div style={{ color: "#6e6e6e", lineHeight: 1.5, marginTop: 3 }}>{axis.sentence}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="serif-note" style={{ borderTop: "1px solid #e6e6e6", marginTop: 26, maxWidth: 820, paddingTop: 20 }}>
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
          <div style={{ display: "flex", height: 34, marginBottom: 12, overflow: "hidden" }}>
            {segments.map((segment) => {
              const pct = totalMinor > 0 ? (segment.amount / totalMinor) * 100 : 0;
              return (
                <div key={segment.label} style={{ alignItems: "center", background: segment.color, display: "flex", padding: pct > 12 ? "0 14px" : "0 6px", width: `${pct.toFixed(1)}%` }}>
                  {pct > 18 ? <span style={{ color: "#ffffff", fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap" }}>{segment.label}</span> : null}
                  <span className="grow" />
                  {pct > 10 ? <span className="num" style={{ color: "#ffffff", fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap" }}>{pfWholeLabel(currency, segment.amount)}</span> : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="pf-collateral-ring-layout">
            <PfRing center={{ title: pfWholeLabel(currency, totalMinor), sub: `${holdingCount} loans` }} radius={60} segments={segments} size={200} stroke={34} total={totalMinor} />
            <div style={{ display: "flex", flex: 1, flexDirection: "column", fontSize: 13.5 }}>
              {segments.map((segment, index) => (
                <div key={segment.label} style={{ alignItems: "baseline", borderBottom: index === segments.length - 1 ? "1px solid #e6e6e6" : undefined, borderTop: "1px solid #e6e6e6", display: "flex", gap: 12, padding: "8px 0" }}>
                  <span style={{ background: segment.color, flex: "none", height: 11, width: 11 }} />
                  <span style={{ color: segment.bad ? "#b3261e" : undefined, fontWeight: 500 }}>{segment.label}</span>
                  <span className="leader" style={{ margin: "0 6px 4px" }} />
                  <span className="num" style={{ color: "#6e6e6e", marginRight: 14 }}>{totalMinor > 0 ? `${((segment.amount / totalMinor) * 100).toFixed(1)}%` : "-"}</span>
                  <span className="num" style={{ color: segment.bad ? "#b3261e" : undefined, fontWeight: 600 }}>{pfWholeLabel(currency, segment.amount)}</span>
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
            <div style={{ alignItems: "baseline", color: "#6e6e6e", display: "flex", fontSize: 11.5, marginBottom: 6 }}><span>Disclosed collateral valuation</span><span className="grow" /><span className="num" style={{ color: "#0a0a0a", fontWeight: 600 }}>100%</span></div>
            <div style={{ border: "1.5px solid #c8c8c8", height: 34, overflow: "hidden", position: "relative" }}>
              <div style={{ background: "#0a0a0a", bottom: 0, left: 0, position: "absolute", top: 0, width: `${weightedLtv === null ? 0 : weightedLtv.toFixed(1)}%` }} />
              <div style={{ alignItems: "center", bottom: 0, display: "flex", justifyContent: "center", left: `${weightedLtv === null ? 0 : weightedLtv.toFixed(1)}%`, position: "absolute", right: 0, top: 0 }}><span style={{ color: "#6e6e6e", fontSize: 11, fontWeight: 600 }}>headroom</span></div>
            </div>
            <div style={{ alignItems: "baseline", display: "flex", fontSize: 11.5, marginTop: 6 }}><span style={{ color: "#0a0a0a", fontWeight: 600 }}>Weighted LTV {ltvLabel}</span><span className="grow" /><span style={{ color: "#6e6e6e" }}>{weightedLtv === null ? "" : `${(100 - weightedLtv).toFixed(1)}% valuation headroom`}</span></div>
            <div style={{ color: "#6e6e6e", fontSize: 12.5, lineHeight: 1.5, marginTop: 14 }}>Weighted only across secured holdings with a disclosed LTV. Per-project disclosed LTV ranges from {securedLtvs.length > 0 ? `${Math.min(...securedLtvs).toFixed(0)}% to ${Math.max(...securedLtvs).toFixed(0)}%` : "not available"}.</div>
          </div>
          <div style={{ borderLeft: "1px solid #e6e6e6", paddingLeft: 6 }}>
            <div className="pf-risk-cap">The second is the recovery contract</div>
            <div className="pf-risk-copy">Every borrower payment follows the same non-overridable order. Garanta legal costs and the approved recovery fee are satisfied first, then penalties, contractual interest and finally principal. Recovery timing or proceeds are never guaranteed.</div>
            <div style={{ alignItems: "baseline", color: "#6e6e6e", display: "flex", fontSize: 11.5, marginBottom: 6 }}><span>Universal borrower-payment and recovery order</span></div>
            <div style={{ border: "1.5px solid #c8c8c8", display: "flex", height: 34, overflow: "hidden" }}>
              <div style={{ alignItems: "center", background: "#0a0a0a", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#ffffff", fontSize: 10.5, fontWeight: 600 }}>1</span></div>
              <div style={{ alignItems: "center", background: "#4a4a4a", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#ffffff", fontSize: 10.5, fontWeight: 600 }}>2</span></div>
              <div style={{ alignItems: "center", background: "#a5a5a5", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#0a0a0a", fontSize: 10.5, fontWeight: 600 }}>3</span></div>
              <div style={{ alignItems: "center", background: "#e6e6e6", display: "flex", justifyContent: "center", width: "25%" }}><span style={{ color: "#6e6e6e", fontSize: 10.5, fontWeight: 600 }}>4</span></div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", fontSize: 11.5, gap: 5, marginTop: 9 }}>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#0a0a0a", flex: "none", height: 9, width: 9 }} /><span style={{ color: "#2a2a2a", flex: 1 }}>Garanta legal costs and recovery fee</span></div>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#4a4a4a", flex: "none", height: 9, width: 9 }} /><span style={{ color: "#2a2a2a", flex: 1 }}>Penalty and default interest</span></div>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#a5a5a5", flex: "none", height: 9, width: 9 }} /><span style={{ color: "#2a2a2a", flex: 1 }}>Contractual interest</span></div>
              <div style={{ alignItems: "baseline", display: "flex", gap: 8 }}><span style={{ background: "#e6e6e6", border: "1px solid #c8c8c8", flex: "none", height: 9, width: 9 }} /><span style={{ color: "#2a2a2a", flex: 1 }}>Principal</span></div>
            </div>
            <div style={{ color: "#6e6e6e", fontSize: 12.5, lineHeight: 1.5, marginTop: 14 }}>Widths show sequence only, not expected amounts. Principal is never paid while an earlier tier remains due. Configured default interest across these loans is {defaultInterestLabel}.</div>
          </div>
        </div>
        <div className="pf-risk-kvs">
          <div className="kv-row"><span className="k">Configured default interest across your loans</span><span className="leader" /><span className="v">{defaultInterestLabel}</span></div>
          <div className="kv-row"><span className="k">Disclosed LTV range across your loans</span><span className="leader" /><span className="v">{rangeLabel}</span></div>
          <div className="kv-row"><span className="k">Weighted LTV across disclosed secured holdings</span><span className="leader" /><span className="v">{weightedLtv === null ? "—" : `${weightedLtv.toFixed(1)}% of valuation`}</span></div>
          <div className="kv-row"><span className="k">Loans with no asset pledged</span><span className="leader" /><span className="v">{unsecuredCount} of {holdingCount}{unsecuredCount > 0 ? ` · ${pfWholeLabel(currency, unsecuredMinor)}` : ""}</span></div>
          <div className="kv-row"><span className="k">Recovery timing</span><span className="leader" /><span className="v">Project-specific; not guaranteed</span></div>
          <div className="kv-row"><span className="k">In arrears right now</span><span className="leader" /><span className="v" style={{ color: lateCount > 0 ? "#b3261e" : undefined }}>{lateCount} of {holdingCount}{lateCount > 0 ? ` · ${pfWholeLabel(currency, lateMinor)}` : ""}</span></div>
        </div>
        <div style={{ color: "#6e6e6e", fontSize: 13, lineHeight: 1.55, maxWidth: 820 }}>Open any loan above to review its disclosed collateral, LTV, agreement terms, public risk notes and repayment schedule. These figures describe current records, not guaranteed recovery value.</div>
      </div>
    </div>
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
          <table className="pf-data-table pf-orders-table stack-on-phone">
            <thead><tr><th>Order</th><th>Loan</th><th className="num">Requested</th><th className="num">Allocated</th><th>Placed</th><th>Status</th></tr></thead>
            <tbody>
              {orders.map((order, index) => (
                <tr key={order.id}>
                  <td data-label="Order">
                    <span className="pf-order-reference">
                      <span className="pf-order-number">#{index + 1}</span>
                      <span className="mono pf-order-id">{compactOrderId(order.id)}</span>
                      <CopyIdButton ariaLabel="Copy order ID" iconOnly id={order.id} label="Copy order ID" />
                    </span>
                  </td>
                  <td data-label="Loan">
                    <span className="pf-order-loan">
                      <strong>{order.loan_title}</strong>
                      <CopyIdButton ariaLabel="Copy loan ID" iconOnly id={order.loan_id} label="Copy loan ID" />
                    </span>
                  </td>
                  <td className="num" data-label="Requested"><Money amountMinor={order.requested_amount_minor} currency={order.currency} /></td>
                  <td className="num" data-label="Allocated">{order.allocated_amount_minor > 0 ? <Money amountMinor={order.allocated_amount_minor} currency={order.currency} /> : <span className="muted">-</span>}</td>
                  <td className="mono muted" data-label="Placed">{formatDateTime(order.created_at)}</td>
                  <td data-label="Status"><Chip status={order.status} tooltip={primaryOrderStatusTooltips[order.status]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** Repaid, sold and closed holdings. They leave "My loans" but stay one click away. */
function CompletedHoldingsTable({ holdings, onOpen }: { holdings: Holding[]; onOpen: (holding: Holding) => void }) {
  return (
    <section className="pf-data-section">
      <header className="pf-data-heading">
        <h2 className="sect">Completed</h2>
        <p>Loans that are repaid, sold or closed. Open one to see its payments.</p>
      </header>
      {holdings.length === 0 ? (
        <PortfolioEmptyState icon="portfolio" title="No completed loans yet">
          Loans appear here when they are repaid, sold or closed.
        </PortfolioEmptyState>
      ) : (
        <div className="pf-data-table-wrap">
          <table className="pf-data-table pf-completed-table">
            <thead><tr><th>Loan</th><th>Result</th><th className="num">Invested</th><th className="num">Interest received</th><th>Since</th><th /></tr></thead>
            <tbody>
              {holdings.map((holding) => {
                const interestMinor = holding.received_interest_minor
                  + holding.recovered_contractual_interest_minor
                  + holding.recovered_default_interest_minor;
                return (
                  <tr key={holding.id}>
                    <td>
                      <strong>{holding.loan.loan_title}</strong>
                      <div className="muted">{holding.loan.borrower_name}</div>
                    </td>
                    <td><Chip dot={false} tone={holding.status === "transferred" ? "info" : holding.loan.loan_status === "written_off" ? "bad" : "ok"}>{completedHoldingLabel(holding)}</Chip></td>
                    <td className="num"><Money amountMinor={holding.original_principal_minor} currency={holding.currency} /></td>
                    <td className="num"><Money amountMinor={interestMinor} currency={holding.currency} /></td>
                    <td className="muted">{formatDate(holding.assignment_effective_at)}</td>
                    <td className="right">
                      <Button aria-label={`Open ${holding.loan.loan_title}`} onClick={() => onOpen(holding)} size="sm">Open</Button>
                    </td>
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
                      const tone = scheduleStatusTone(row.status);
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
                      const tone = scheduleStatusTone(row.status);
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

function HoldingDetail({ holding, setRoute }: { holding: Holding; setRoute: (route: AppRoute) => void }) {
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
  const inDefault = loanIsInDefault(loan);
  const defaultSelectedKey = defaultSelectedPaymentKey(loan, timelineRows, firstProjected?.loan_installment_id ?? null);
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
  const isPaidRow = isPaidScheduleRow;
  const progress = installmentProgress(timelineRows);
  const progressPercent = progress.total === 0 ? 0 : (progress.paid / progress.total) * 100;
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
  // LTV on the principal still owed on the whole loan (one definition, see portfolioCollateral.ts).
  const loanLtv = loanLtvBps(loan);
  const ltvPercent = loanLtv === null ? null : loanLtv / 100;
  const loanPrincipalNowMinor = currentLoanPrincipalMinor(loan) ?? loan.principal_minor;
  const futureTotals = projectedRows.reduce(
    (totals, row) => ({
      principal: totals.principal + row.projected_principal_minor,
      interest: totals.interest + row.projected_interest_minor,
      total: totals.total + row.projected_total_minor
    }),
    { principal: 0, interest: 0, total: 0 }
  );
  const selectedDate = selectedProjection?.due_date ?? selectedLoanRow?.payment_date ?? selectedLoanRow?.due_date ?? "";
  const selectedStatus = selectedProjection
    ? scheduleRowStatus(selectedProjection, loan)
    : selectedLoanRow
      ? scheduleRowStatus(selectedLoanRow, loan)
      : "unavailable";
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
    const state = isPaidRow(row) ? "paid" : row.status === "overdue" ? "overdue" : projection === firstProjected && !inDefault ? "next" : "future";
    const rowStatus = humanizeToken(scheduleRowStatus(row, loan));
    return (
      <button
        aria-label={`${formatDate(row.payment_date ?? row.due_date)}, ${rowStatus}`}
        className={`holding-v9-payment-cell ${state} ${selectedPaymentKey === key ? "selected" : ""}`}
        key={`${year}-${month}`}
        onClick={() => setSelectedPaymentKey(key)}
        title={`${row.label}: ${rowStatus}`}
        type="button"
      >
        {isPaidRow(row) ? "Paid" : row.installment_number}
      </button>
    );
  };
  const listingCopy = hasOpenListing
    ? "This position already has an open secondary-market listing."
    : listingAction.allowed
      ? "You can offer the full current claim on the secondary market."
      : listingAction.hint;
  return (
    <main className="content pf-page inv-page">
      <PageHead
        actions={
          <Button icon="calendar" onClick={() => setScheduleOpen((open) => !open)}>
            {scheduleOpen ? "Hide schedule" : "View schedule"}
          </Button>
        }
        back={{ label: "My investments", onClick: () => goTo(setRoute, "portfolio") }}
        className="inv-head"
        description={
          <div className="inv-head-sub">
            <h2 className="inv-borrower">{loan.borrower_name}</h2>
            <div className="inv-head-tags">
              <Chip status={loan.loan_status} tone={statusTone(loan.loan_status)} />
              {holding.open_secondary_listing ? <Chip status={listingStatusLabel(holding.open_secondary_listing.status)} tone={holding.open_secondary_listing.status === "active" ? "ok" : "warn"} tooltip={listingStatusTooltip(holding.open_secondary_listing.status)} /> : null}
              <Country code={loan.borrower_country} />
              <CopyIdButton ariaLabel="Copy loan ID" iconOnly id={loan.loan_id} label="Copy loan ID" />
            </div>
          </div>
        }
        title={loan.loan_title}
      />

      {impaired ? (
        <section className="banner banner-bad inv-alert">
          <Icon className="b-ico" name="alert" size={18} />
          <div className="grow">
            <div className="inv-alert-lead"><strong>{humanizeToken(loan.loan_status)}</strong>{loan.days_past_due > 0 ? ` · ${loan.days_past_due} days past due` : ""}</div>
            <p>
              {loan.default_penalty_interest_bps > 0
                ? `The loan terms specify a ${formatRateBps(loan.default_penalty_interest_bps)} annual default-interest rate. Any amount shown as received is based on recorded servicing or recovery evidence; BANXUM does not estimate accrued default interest from days past due.`
                : "This loan has no default interest rate. Late payments earn no extra interest; see the payments credited to you."}
            </p>
          </div>
        </section>
      ) : null}

      <article className="card inv-figures">
        <section className="inv-figures-top" aria-label="Position summary">
          <div className="inv-fig-group">
            <div className="inv-fig"><span>Interest received</span><strong><Money amountMinor={earnedInterestMinor} currency={currency} /></strong><small>contractual and recorded recovery interest</small></div>
            <span aria-hidden="true" className="inv-fig-plus"><Icon name="plus" size={18} /></span>
            <div className="inv-fig"><span>Projected still to earn</span><strong><Money amountMinor={projectedInterestMinor} currency={currency} /></strong><small>across {projectedRows.length} remaining payments</small></div>
          </div>
          <div className="inv-fig-group">
            <div className="inv-fig"><span>Capital returned</span><strong><Money amountMinor={capitalReturnedMinor} currency={currency} /></strong><small>{capitalReturnedPercent.toFixed(1)}% of your original claim</small></div>
            <div className="inv-fig"><span>Still owed to you</span><strong><Money amountMinor={holding.current_principal_minor} currency={currency} /></strong><small>current outstanding principal</small></div>
          </div>
        </section>
        <div className="inv-lifetime">
          Of the <strong><Money amountMinor={lifetimeInterestMinor} currency={currency} /></strong> of contractual and recorded recovery interest represented here, <strong>{receivedInterestPercent.toFixed(1)}%</strong> has been received. Future interest is projected, not guaranteed.
        </div>
        <dl className="inv-facts">
          <div><dt>Purpose</dt><dd>{humanizeToken(loan.purpose)}</dd></div>
          <div><dt>Annual yield</dt><dd>{formatRateBps(loan.yield_bps)}</dd></div>
          {loan.product_type === "originator_claim" && loan.maturity_date ? (
            <div><dt>Matures</dt><dd>{formatDate(loan.maturity_date)}</dd></div>
          ) : (
            <div><dt>Term</dt><dd>{pluralize(loan.term_months, "month")}</dd></div>
          )}
          <div><dt>Yours since</dt><dd>{formatDate(holding.assignment_effective_at)}</dd></div>
          <div><dt>Repayment</dt><dd>{formatEnumLabel(loan.repayment_type)}</dd></div>
          <div><dt>Risk rating</dt><dd><Rating value={loan.risk_rating} /></dd></div>
        </dl>
      </article>

      <section className="card inv-card inv-sell">
        <div className="card-head"><h3 className="card-title">Secondary market</h3></div>
        <div className="inv-sell-body">
          <p className="inv-sell-copy">{listingCopy}</p>
          <Tooltip
            content={!canOpenSecondaryAction ? listingAction.hint : ""}
            label={!canOpenSecondaryAction ? `${listingAction.label}. ${listingAction.hint}` : undefined}
          >
            <Button disabled={!canOpenSecondaryAction} icon="secondary" variant="primary" onClick={() => goTo(setRoute, "secondary", { tab: "sell" })}>
              {hasOpenListing ? "Manage secondary listing" : listingAction.label}
            </Button>
          </Tooltip>
        </div>
      </section>

      {scheduleOpen ? (
        <section className="card inv-card inv-schedule">
          <div className="card-head"><div><h3 className="card-title">Your future schedule</h3><div className="inv-card-sub">Current projection, schedule version {loan.schedule_version}.</div></div></div>
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
                    return <tr className="clickable" key={row.loan_installment_id} onClick={() => setSelectedPaymentKey(`projection:${row.loan_installment_id}`)}><td>{formatDate(row.due_date)}</td><td><Chip dot={false} tone={scheduleStatusTone(row.status)}>{humanizeToken(row.status)}</Chip></td><td className="num pos"><Money amountMinor={row.projected_interest_minor} currency={currency} /></td><td className="num"><Money amountMinor={row.projected_principal_minor} currency={currency} /></td><td className="num col-strong"><Money amountMinor={row.projected_total_minor} currency={currency} /></td><td className="num"><Money amountMinor={owedAfter} currency={currency} /></td></tr>;
                  })}
                </tbody>
                <tfoot className="schedule-totals"><tr><th colSpan={2}>Totals</th><th className="num"><Money amountMinor={futureTotals.interest} currency={currency} /></th><th className="num"><Money amountMinor={futureTotals.principal} currency={currency} /></th><th className="num"><Money amountMinor={futureTotals.total} currency={currency} /></th><th className="num">-</th></tr></tfoot>
              </table>
            </div>
          )}
        </section>
      ) : null}

      <section className="card inv-card inv-progress">
        <button aria-expanded={timelineOpen} className="holding-v9-progress-toggle" onClick={() => setTimelineOpen((open) => !open)} type="button">
          <span><strong>{progress.paid} of {progress.total}</strong> scheduled borrower payments recorded</span>
          <span className="inv-link">{timelineOpen ? "Hide timeline" : "Open timeline"}</span>
        </button>
        <div className="inv-progress-body">
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
        </div>
      </section>

      <section className="inv-detail-grid">
        <div className="card inv-card inv-payment">
          <div className="card-head inv-payment-head">
            <div><h3 className="card-title">Selected payment</h3><strong>{selectedDate ? formatDate(selectedDate) : "Unavailable"}</strong></div>
            <Chip dot={false} tone={scheduleStatusTone(selectedStatus)}>{humanizeToken(selectedStatus)}</Chip>
          </div>
          <div className="inv-card-body">
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
        </div>
        <div className="card inv-card inv-collateral">
          <div className="card-head"><h3 className="card-title">Collateral</h3></div>
          <div className="inv-card-body">
            <p className="holding-v9-collateral-copy">{collateralDescription}</p>
            {ltvPercent !== null && collateralValueMinor > 0 ? (
              <>
                <div aria-label={`${ltvPercent.toFixed(1)}% loan to value`} className="holding-v9-ltv-bar" role="img"><span style={{ width: `${Math.min(100, Math.max(0, ltvPercent))}%` }} /></div>
                <div className="holding-v9-ltv-label"><span><Money amountMinor={loanPrincipalNowMinor} currency={currency} /> current loan principal against <Money amountMinor={collateralValueMinor} currency={currency} /> valuation</span><strong>{formatRateBps(loanLtv ?? 0)} LTV</strong></div>
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
        </div>
      </section>

      {recoveryTotalMinor > 0 ? (
        <section className="card inv-card inv-recovery">
          <div className="card-head"><div><h3 className="card-title">Recovery credited to date</h3><div className="inv-card-sub">Recorded distributions only; no uncollected amounts are estimated.</div></div></div>
          <div className="inv-card-body">
            <Review rows={[
              { label: "Principal recovered", value: <Money amountMinor={holding.recovered_principal_minor} currency={currency} /> },
              { label: "Contractual interest recovered", value: <Money amountMinor={holding.recovered_contractual_interest_minor} currency={currency} /> },
              { label: "Default interest recovered", value: <Money amountMinor={holding.recovered_default_interest_minor} currency={currency} /> },
              { label: "Penalties recovered", value: <Money amountMinor={holding.recovered_penalties_minor} currency={currency} /> },
              { label: "Other recoveries", value: <Money amountMinor={holding.recovered_other_costs_minor} currency={currency} /> },
              { label: "Total credited recovery", value: <Money amountMinor={recoveryTotalMinor} currency={currency} />, total: true }
            ]} />
          </div>
        </section>
      ) : null}
      {holding.latest_public_note ? (
        <section className="card inv-card inv-note">
          <div className="card-head"><h3 className="card-title">Latest public note from Garanta</h3></div>
          <div className="inv-card-body"><p>{holding.latest_public_note.title}</p><small>{formatDate(holding.latest_public_note.occurred_at)}</small></div>
        </section>
      ) : null}
    </main>
  );
}

// Holding detail as a page (design: "My investments" > investment). Route: /portfolio/:holdingId.
function InvestmentScreen({ holdingId, setRoute }: { holdingId: string; setRoute: (route: AppRoute) => void }) {
  const portfolioQuery = usePortfolioData(true);
  const portfolio = portfolioQuery.data;
  if (portfolioQuery.isError && !portfolio) {
    return (
      <ScreenError title="Investment" onRetry={() => void portfolioQuery.refetch()}>
        We could not load this investment. Retry once the API connection is restored.
      </ScreenError>
    );
  }
  if (!portfolio) return <ScreenLoading title="Investment" />;
  const holding = portfolio.holdings.find((candidate) => candidate.id === holdingId);
  if (!holding) {
    return (
      <main className="content pf-page inv-page">
        <PageHead back={{ label: "My investments", onClick: () => goTo(setRoute, "portfolio") }} title="Investment not found" />
        <Card className="inv-missing">
          <Empty icon="portfolio" title="We could not find this investment">
            It is not in your portfolio. It may have been sold, or the link may be wrong.
          </Empty>
          <div className="pf-empty-action"><Button size="sm" onClick={() => goTo(setRoute, "portfolio")}>Back to My investments</Button></div>
        </Card>
      </main>
    );
  }
  return <HoldingDetail holding={holding} key={holding.id} setRoute={setRoute} />;
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
  const frozenAccount = useFrozenAccount();
  const frozen = frozenAccount.frozen || demoState === "frozen";
  const sellable = portfolio?.holdings.filter((holding) => holding.current_principal_minor > 0) ?? [];

  useEffect(() => {
    if (initialTab === "browse" || initialTab === "sell" || initialTab === "activity" || initialTab === "mine") {
      setTab(initialTab === "mine" ? "activity" : initialTab);
    }
  }, [initialTab]);

  const sellPositions = pfActiveHoldings(portfolio?.holdings ?? []);
  // Holdings already on sale are not counted as "can be listed".
  const immediatelyListableCount = sellPositions.filter((holding) => holding.loan.loan_status === "active" && !holding.open_secondary_listing).length;
  // Rule C18: late or defaulted loans cannot be listed; there is no approval request.
  const nonPerformingCount = sellPositions.filter((holding) => ["late", "defaulted"].includes(holding.loan.loan_status)).length;
  const pendingDisbursementCount = sellPositions.filter((holding) => holding.loan.loan_status === "funded").length;
  const purchaseBlockedReason = frozen
    ? `${frozenActionReason(frozenAccount)} You can still inspect every listing.`
    : isReadonlyImpersonationActive()
      ? "This is a read-only investor view. Listing details are available, but purchases are disabled."
      : "";
  const listingsLoading = listingsQuery.isPending && listingsQuery.data === undefined;
  const activityLoading = activityQuery.isPending && activityQuery.data === undefined;
  // The investor's own listings are shown as "Your listing", without Buy (audit A-35).
  const ownListingIds = new Set([
    ...listings.filter((listing) => listing.is_own_listing).map((listing) => listing.id),
    ...(portfolio?.holdings ?? []).flatMap((holding) => (holding.open_secondary_listing ? [holding.open_secondary_listing.id] : []))
  ]);
  const otherListingCount = listings.filter((listing) => !ownListingIds.has(listing.id)).length;
  const ownListingCount = listings.length - otherListingCount;

  return (
    <main className="content sm-page">
      <PageHead
        className="sm-head"
        description="Someone else lent this money and wants it back before the schedule ends. You take over their position, their collateral and their remaining term. Counterparties stay anonymous."
        eyebrow={listingsLoading ? "Loading listings" : `${otherListingCount} ${otherListingCount === 1 ? "listing" : "listings"} · sold by other investors${ownListingCount > 0 ? ` · ${ownListingCount} of yours` : ""}`}
        title="Loans other people want out of."
      />
      {frozen ? <div className="sm-alerts"><Banner icon="lock" tone="bad" title="Secondary-market actions are frozen">{frozenActionReason(frozenAccount)}</Banner></div> : null}
      <nav aria-label="Secondary market sections" className="tabs sm-tabs" onKeyDown={handleTabListKeyDown} role="tablist">
        <button aria-controls="sm-tab-panel" aria-selected={tab === "browse"} className={tab === "browse" ? "on" : ""} id="sm-tab-browse" onClick={() => setTab("browse")} role="tab" tabIndex={tab === "browse" ? 0 : -1} type="button">For sale now</button>
        <button aria-controls="sm-tab-panel" aria-selected={tab === "sell"} className={tab === "sell" ? "on" : ""} id="sm-tab-sell" onClick={() => setTab("sell")} role="tab" tabIndex={tab === "sell" ? 0 : -1} type="button">Sell a holding</button>
        <button aria-controls="sm-tab-panel" aria-selected={tab === "activity"} className={tab === "activity" ? "on" : ""} id="sm-tab-activity" onClick={() => setTab("activity")} role="tab" tabIndex={tab === "activity" ? 0 : -1} type="button">Secondary market activity</button>
      </nav>
      <div aria-labelledby={`sm-tab-${tab}`} className="sm-tab-panel" id="sm-tab-panel" role="tabpanel">
        {tab === "browse" ? (
          listingsLoading ? (
            <LoadingCard title="Loading secondary listings">Fetching current buyer-safe prices and loan context.</LoadingCard>
          ) : listingsQuery.isError && listings.length === 0 ? (
            <DataErrorCard title="Could not load secondary listings" onRetry={() => void listingsQuery.refetch()}>
              Secondary-market listings are temporarily unavailable.
            </DataErrorCard>
          ) : (
            <SmForSale
              nonPerformingCount={nonPerformingCount}
              immediatelyListableCount={immediatelyListableCount}
              listings={listings}
              ownListingIds={ownListingIds}
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
      {buy ? <BuyListingModal listing={buy} onClose={() => setBuy(null)} ownListing={ownListingIds.has(buy.id)} purchaseBlockedReason={purchaseBlockedReason} /> : null}
      {sell ? <ListHoldingModal holding={sell.holding} listing={sell.listing} onClose={() => setSell(null)} /> : null}
      {cancelListing ? <CancelSecondaryListingModal holding={cancelListing.holding} listing={cancelListing.listing} onClose={() => setCancelListing(null)} /> : null}
    </main>
  );
}

function smDiscountLabel(discountPremiumBps: number) {
  if (discountPremiumBps === 0) return { text: "par", tone: "mut" as const };
  const pct = formatRateBps(Math.abs(discountPremiumBps));
  return discountPremiumBps < 0
    ? { text: `${pct} discount`, tone: "good" as const }
    : { text: `${pct} premium`, tone: "mut" as const };
}

function SmForSale({
  nonPerformingCount,
  immediatelyListableCount,
  listings,
  ownListingIds,
  onBuy,
  onChooseLoan,
  pendingDisbursementCount,
  totalPositions
}: {
  nonPerformingCount: number;
  immediatelyListableCount: number;
  listings: SecondaryMarketBuyerListing[];
  ownListingIds: Set<string>;
  onBuy: (listing: SecondaryMarketBuyerListing) => void;
  onChooseLoan: () => void;
  pendingDisbursementCount: number;
  totalPositions: number;
}) {
  return (
    <div className="sm-forsale">
      <section className="card sm-card">
        <div className="card-head sm-card-head">
          <div>
            <h2 className="sect">For sale now</h2>
            <p className="sect-sub">A discount raises what you earn; a premium lowers it. The interest rate on the loan itself never changes — only what you paid for it.</p>
          </div>
        </div>
        {listings.length === 0 ? (
          <div className="sm-empty"><Empty icon="secondary" title="No active secondary listings">There are no buyer-visible holdings listed right now.</Empty></div>
        ) : (
          <div className="sm-table">
            <div className="sm-thead">
              <span className="sm-col-loan">Loan</span>
              <span className="sm-col-outstanding">Outstanding</span>
              <span className="sm-col-asking">Asking</span>
              <span className="sm-col-discount">Price vs par</span>
              <span className="sm-col-left">Left to run</span>
              <span className="sm-col-cost">Buyer cost</span>
              <span className="sm-col-cta" />
            </div>
            {listings.map((listing) => {
              const discount = smDiscountLabel(listing.discount_premium_bps);
              const own = ownListingIds.has(listing.id);
              return (
                <button
                  className={`sm-row${own ? " is-own" : ""}`}
                  key={listing.id}
                  onClick={() => onBuy(listing)}
                  type="button"
                >
                  <span className="sm-col-loan">
                    <PfTile hints={[listing.collateral_type, listing.loan_title]} />
                    <span className="sm-loan-text">
                      <span className="sm-loan-title">{listing.loan_title}</span>
                      <span className="num sm-loan-sub">
                        {humanizeToken(listing.collateral_type)} · {formatRateBps(listing.interest_rate_bps)} coupon
                        {listing.risk_acknowledgement_required ? <span className="sm-nonstandard"> · non-standard</span> : null}
                      </span>
                    </span>
                  </span>
                  <span className="num sm-col-outstanding" data-label="Outstanding">{pfMoneyLabel(listing.currency, listing.current_principal_minor)}</span>
                  <span className="num sm-col-asking" data-label="Asking">{pfMoneyLabel(listing.currency, listing.transfer_price_minor)}</span>
                  <span className={`num sm-col-discount ${discount.tone}`} data-label="Price vs par">{discount.text}</span>
                  <span className="num sm-col-left" data-label="Left to run">{listing.remaining_term_months} mo</span>
                  <span className="num sm-col-cost" data-label="Buyer cost">{pfMoneyLabel(listing.currency, listing.buyer_total_cost_minor)}</span>
                  <span className="sm-col-cta">{own ? <span className="sm-own-pill">Your listing</span> : <span className="sm-buy-pill">Buy</span>}</span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="card sm-card sm-explainer">
        <div className="card-head sm-card-head">
          <div>
            <h2 className="sect">Why do loans sell at a premium or a discount?</h2>
            <p className="sect-sub">The seller keeps one premium or discount percentage. Actual buyer cost also includes accrued interest and the disclosed taker fee.</p>
          </div>
        </div>
        <div className="band band-3 sm-band">
          <div className="cell">
            <div className="microlabel">At a discount</div>
            <div className="num sm-band-price">Below 100% of principal</div>
            <div className="sm-band-yield">lower transfer price</div>
            <div className="sm-band-copy">The seller wants out early — a long wait left, or collateral that resells slowly. The full amount is still owed, so the gap is yours.</div>
          </div>
          <div className="cell">
            <div className="microlabel">At par</div>
            <div className="num sm-band-price">100% of principal</div>
            <div className="sm-band-yield">same transfer price</div>
            <div className="sm-band-copy">You step in at the holding's current outstanding principal. Accrued interest and the buyer fee still form part of total cost.</div>
          </div>
          <div className="cell">
            <div className="microlabel">At a premium</div>
            <div className="num sm-band-price">Above 100% of principal</div>
            <div className="sm-band-yield">higher transfer price</div>
            <div className="sm-band-copy">The rate beats anything open today, so the seller charges for access. You take a lower yield to lock it in.</div>
          </div>
        </div>
      </section>

      <section className="card sm-card sm-selling">
        <div className="card-head sm-card-head">
          <div>
            <h2 className="sect">Selling your own</h2>
            <p className="sm-sell-note">
              {totalPositions > 0 ? (
                <>
                  <span className="sm-sell-count">{immediatelyListableCount} of your {totalPositions} {totalPositions === 1 ? "holding" : "holdings"}</span> can be listed immediately.
                  {nonPerformingCount > 0 ? ` ${nonPerformingCount} ${nonPerformingCount === 1 ? "holding is" : "holdings are"} late or in default and cannot be listed.` : ""}
                  {pendingDisbursementCount > 0 ? ` ${pendingDisbursementCount} ${pendingDisbursementCount === 1 ? "holding becomes" : "holdings become"} available after borrower disbursement.` : ""}{" "}
                </>
              ) : null}
              You set the asking price; BANXUM's maker fee comes out of what you receive, and nothing is charged if it does not sell.
            </p>
          </div>
        </div>
        <div className="sm-selling-body">
          <div className="banner banner-warn sm-caution-card">
            <Icon className="b-ico" name="alert" size={18} />
            <div className="grow">
              <p className="sm-caution-copy"><strong className="sm-caution-lead">Caution</strong> This is not a withdrawal button. There is no guaranteed buyer and no guaranteed price. If nobody wants your loan at a price you accept, you hold it to the end of its term.</p>
            </div>
            <button className="btn sm-choose-btn" onClick={onChooseLoan} type="button">Choose a loan to sell</button>
          </div>
          <p className="sm-anon-note">Buyer views never expose seller identity, seller net proceeds, maker fee, document evidence IDs, or admin fields.</p>
        </div>
      </section>
    </div>
  );
}

type OpenSecondaryListing = NonNullable<Holding["open_secondary_listing"]>;

function listingStatusLabel(status: string) {
  if (status === "active") return "Listed";
  return humanizeToken(status);
}

function listingStatusTooltip(status: string) {
  if (status === "active") {
    return "Visible to eligible buyers. Servicing changes automatically recalculate the amounts while preserving the selected premium or discount.";
  }
  return undefined;
}

// Rule C18: only loans that are paid on time can be listed. Late or defaulted loans
// cannot be listed at all; there is no listing request or approval.
function secondaryListingAction(loanStatus: string) {
  if (loanStatus === "active") {
    return { allowed: true, label: "List on secondary market", title: "Listing available", hint: "" };
  }
  if (["late", "defaulted"].includes(loanStatus)) {
    return {
      allowed: false,
      label: "List on secondary market",
      title: "Listing not available",
      hint: `This loan is ${loanStatus === "late" ? "late" : "in default"}. Loans that are late or in default cannot be listed on the secondary market.`
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
  const multiLotLoanIds = pfMultiLotLoanIds(holdings);

  return (
    <div className="portal-data-surface">
      <div className="tbl-wrap">
        <table className="tbl portal-data-table secondary-sell-table">
          <thead><tr><th>Holding</th><th>Loan status</th><th>Listing status</th><th className="num">Current principal</th><th className="num">Rate</th><th /></tr></thead>
          <tbody>{holdings.map((holding) => {
            const listing = holding.open_secondary_listing;
            const actionsDisabled = frozen || isReadonlyImpersonationActive();
            const listingAction = secondaryListingAction(holding.loan.loan_status);
            const lotMeta = multiLotLoanIds.has(holding.loan.loan_id)
              ? `${holding.loan.borrower_name} · ${pfLotLabel(holding)}`
              : holding.loan.borrower_name;
            return (
              <tr key={holding.id}>
                <td><div className="sm-holding-cell"><PfTile hints={[holding.loan.collateral_type, holding.loan.purpose]} /><EntityReference id={holding.loan.loan_id} idLabel="Copy loan ID" meta={lotMeta} title={holding.loan.loan_title} /></div></td>
                <td><Chip status={holding.loan.loan_status} tone={statusTone(holding.loan.loan_status)} /></td>
                <td>{listing ? <Chip status={listingStatusLabel(listing.status)} tone={listing.status === "active" ? "ok" : "warn"} tooltip={listingStatusTooltip(listing.status)} /> : <span className="muted">Not listed</span>}</td>
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
                        <Tooltip
                          content={!listingAction.allowed ? listingAction.hint : ""}
                          label={!listingAction.allowed ? `${listingAction.label}. ${listingAction.hint}` : undefined}
                        >
                          <Button disabled={actionsDisabled || !listingAction.allowed} size="sm" onClick={() => onSell(holding)}>{listingAction.label === "List on secondary market" ? "List" : listingAction.label}</Button>
                        </Tooltip>
                        {!listingAction.allowed ? <span className="sub">{holding.loan.loan_status === "funded" ? "Available after disbursement" : ["late", "defaulted"].includes(holding.loan.loan_status) ? "Late or in default: cannot be listed" : "Unavailable for this status"}</span> : null}
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
                  <td><div className="col gap-4"><strong>{secondaryActivityLabel(entry)}</strong>{entry.archived_at ? <span className="qa-history-note">Before QA reset</span> : null}{entry.action === "list" && entry.price_bps !== null ? <span className="sub">{priceLabel(entry.price_bps - 10000)}</span> : null}</div></td>
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

function BuyListingModal({ listing, onClose, ownListing = false, purchaseBlockedReason }: { listing: SecondaryMarketBuyerListing; onClose: () => void; ownListing?: boolean; purchaseBlockedReason: string }) {
  const queryClient = useQueryClient();
  const detailQuery = useSecondaryListingDetailData(listing.id);
  const detail = detailQuery.data;
  // Your own listing can be viewed but not bought: no terms, no code, no acceptance.
  const isOwnListing = ownListing || listing.is_own_listing || Boolean(detail?.is_own_listing);
  const [ack, setAck] = useState(false);
  const [extraAck, setExtraAck] = useState(false);
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [priceChangedMessage, setPriceChangedMessage] = useState("");
  const priceChangedRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Bring the notice and the refreshed price rows below it into view.
    if (priceChangedMessage) priceChangedRef.current?.scrollIntoView({ block: "center" });
  }, [priceChangedMessage]);
  // The acceptance evidence records the reviewed economics, so it is reused only
  // for a retry of exactly the same price; a new price needs a new acceptance.
  const [acceptance, setAcceptance] = useState<{ id: string; reviewKey: string } | null>(null);
  const [acceptanceKey, setAcceptanceKey] = useState(() => idempotencyKey("secondary-purchase-acceptance"));
  const [purchaseKey, setPurchaseKey] = useState(() => idempotencyKey("secondary-purchase"));
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const purchaseMutation = useV1MarketplaceSecondaryListingsPurchaseCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.secondary_market_purchase);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.secondary_market_purchase },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const needsExtra = detail?.risk_acknowledgement_required ?? listing.risk_acknowledgement_required;
  const submitPurchase = async () => {
    setError("");
    setPriceChangedMessage("");
    if (isOwnListing) {
      setError("This is your own listing. You cannot buy it.");
      return;
    }
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
    if (!detail) {
      setError("The current price of this listing is still loading.");
      return;
    }
    // The buyer accepts exactly the prices shown below, all taken from the fresh
    // listing detail. The server charges these values or rejects the purchase.
    const reviewed = {
      price_bps: detail.price_bps,
      current_principal_minor: detail.current_principal_minor,
      buyer_total_cost_minor: detail.buyer_total_cost_minor
    };
    const reviewKey = `${reviewed.price_bps}:${reviewed.current_principal_minor}:${reviewed.buyer_total_cost_minor}`;
    try {
      const accepted = acceptance && acceptance.reviewKey === reviewKey
        ? acceptance
        : {
            id: (await acceptanceMutation.mutateAsync({
              data: {
                category: CategoryEnum.secondary_market_purchase,
                expected_template_version_id: termsQuery.data.id,
                accepted_checkbox_labels: labels,
                context_type: "secondary_market_purchase",
                context_id: listing.id,
                data_snapshot: {
                  listing_id: listing.id,
                  currency: detail.currency,
                  price_bps: reviewed.price_bps,
                  current_principal_minor: reviewed.current_principal_minor,
                  transfer_price_minor: detail.transfer_price_minor,
                  accrued_interest_minor: detail.accrued_interest_minor,
                  taker_fee_minor: detail.taker_fee_minor,
                  buyer_total_cost_minor: reviewed.buyer_total_cost_minor
                },
                idempotency_key: `${acceptanceKey}:${reviewKey}`
              }
            })).id,
            reviewKey
          };
      setAcceptance(accepted);
      await purchaseMutation.mutateAsync({
        listingId: listing.id,
        data: {
          document_acceptance_id: accepted.id,
          risk_acknowledgement_accepted: needsExtra ? extraAck : true,
          idempotency_key: purchaseKey,
          expected_buyer_total_cost_minor: reviewed.buyer_total_cost_minor,
          expected_price_bps: reviewed.price_bps,
          expected_current_principal_minor: reviewed.current_principal_minor,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code
        }
      });
      void queryClient.invalidateQueries();
      setDone(true);
    } catch (mutationError) {
      if (isSecondaryPriceChangedError(mutationError)) {
        // Nothing was charged. Load the new price and ask the buyer to review
        // and accept it again; the entered email code stays in the field.
        setPriceChangedMessage(apiErrorMessage(mutationError));
        setAcceptance(null);
        setAcceptanceKey(idempotencyKey("secondary-purchase-acceptance"));
        setPurchaseKey(idempotencyKey("secondary-purchase"));
        setAck(false);
        setExtraAck(false);
        void detailQuery.refetch();
        void queryClient.invalidateQueries({ queryKey: getV1MarketplaceSecondaryListingsListQueryKey() });
        return;
      }
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
    <Modal xwide footer={isOwnListing ? <Button variant="ghost" onClick={onClose}>Close</Button> : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={Boolean(purchaseBlockedReason) || !ack || (needsExtra && !extraAck) || code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || detailQuery.isFetching || acceptanceMutation.isPending || purchaseMutation.isPending} variant="primary" onClick={submitPurchase}>{acceptanceMutation.isPending || purchaseMutation.isPending ? "Submitting..." : "Confirm purchase"}</Button></>} onClose={onClose} title={isOwnListing ? `Your listing: ${listing.loan_title}` : `Buy ${listing.loan_title}`}>
      <div className="col gap-16">
        {isOwnListing ? <Banner icon="lock" tone="neutral" title="This is your listing">Other investors see it with this price. You cannot buy your own listing. To change or cancel it, open Sell a holding.</Banner> : null}
        {purchaseBlockedReason && !isOwnListing ? <Banner icon="lock" tone="neutral" title="Purchase unavailable in this view">{purchaseBlockedReason}</Banner> : null}
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
          <Card padded><Stat label="LTV" raw={loanLtvBps(detail) === null ? "Not disclosed" : formatRateBps(loanLtvBps(detail) ?? 0)} /></Card>
        </div>
        {priceChangedMessage ? <div ref={priceChangedRef}><Banner tone="warn" title="Price changed">{priceChangedMessage} Nothing was charged.</Banner></div> : null}
        <Review rows={[
          { label: "Listing", value: listing.loan_title },
          { label: "Repayment type", value: formatEnumLabel(detail.repayment_type) },
          { label: "Current principal", value: `${detail.currency} ${formatMoneyMinor(detail.current_principal_minor, detail.currency)}` },
          { label: "Sale price", value: priceLabel(detail.discount_premium_bps) },
          { label: "Accrued interest to seller", value: `${detail.currency} ${formatMoneyMinor(detail.accrued_interest_minor, detail.currency)}` },
          { label: "Taker fee", value: `${detail.currency} ${formatMoneyMinor(detail.taker_fee_minor, detail.currency)}` },
          { label: "Total cost", value: `${detail.currency} ${formatMoneyMinor(detail.buyer_total_cost_minor, detail.currency)}`, total: true }
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
        {isOwnListing ? null : (
          <>
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
          </>
        )}
      </div>
    </Modal>
  );
}

// One listing confirmation attempt. The terms acceptance records the price, so the
// attempt (acceptance and keys) is replaced when the price changes or the seller goes
// back to the listing data (audit A-36).
type ListingAttempt = { priceBps: number; acceptanceKey: string; listingKey: string; acceptanceId: string | null };

function newListingAttempt(priceBps: number, isEdit: boolean): ListingAttempt {
  return {
    priceBps,
    acceptanceKey: idempotencyKey(isEdit ? "secondary-listing-edit-acceptance" : "secondary-listing-acceptance"),
    listingKey: idempotencyKey(isEdit ? "secondary-listing-edit" : "secondary-listing"),
    acceptanceId: null
  };
}

function listingPriceFromInput(value: string) {
  return Math.max(1, Number(value || 0));
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
  const [attempt, setAttempt] = useState<ListingAttempt>(() => newListingAttempt(listingPriceFromInput(String(listing?.price_bps ?? 10000)), isEdit));
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const listingMutation = useV1MarketplaceSecondaryListingsCreate();
  const editMutation = useV1MarketplaceSecondaryListingsEditCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.secondary_market_listing);
  useAutoRequestEmailCode(codeRequest, step === "verify" && !done);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.secondary_market_listing },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const price = listingPriceFromInput(priceBps);
  // Seller pricing from the server (audit A-34): transfer price, accrued interest to
  // today, the configured maker fee with its minimum, and the net proceeds. The preview
  // fixture keeps a local estimate because it has no server.
  const pricingQuery = useV1MarketplaceSecondaryListingsPricingPreviewRetrieve(
    { holding_id: holding.id, price_bps: price },
    { query: { enabled: !isFixturePreview && Number.isFinite(price) && price >= 1, retry: false, staleTime: 30_000 } }
  );
  const fixtureTransfer = Math.round((holding.current_principal_minor * price) / 10000);
  const fixtureMakerFee = Math.round(fixtureTransfer * 0.0025);
  const pricing: Pick<SecondaryMarketListingPricingPreview, "transfer_price_minor" | "accrued_interest_minor" | "maker_fee_minor" | "seller_net_proceeds_minor"> | null = isFixturePreview
    ? { transfer_price_minor: fixtureTransfer, accrued_interest_minor: 0, maker_fee_minor: fixtureMakerFee, seller_net_proceeds_minor: fixtureTransfer - fixtureMakerFee }
    : pricingQuery.data?.price_bps === price ? pricingQuery.data : null;
  const pricingValue = (minor: number | undefined) =>
    minor === undefined ? (pricingQuery.isError ? "Not available" : "Calculating...") : `${holding.currency} ${formatMoneyMinor(minor, holding.currency)}`;
  const pricingRows = [
    { label: "Transfer price", value: pricingValue(pricing?.transfer_price_minor) },
    { label: "Accrued interest to you", value: pricingValue(pricing?.accrued_interest_minor) },
    { label: "Maker fee", value: pricingValue(pricing?.maker_fee_minor) },
    { label: "Seller net proceeds", value: pricingValue(pricing?.seller_net_proceeds_minor), total: true }
  ];
  const changePrice = (value: string) => {
    setPriceBps(value);
    setAttempt(newListingAttempt(listingPriceFromInput(value), isEdit));
    // The terms are accepted for one price: a new price is accepted again.
    setAck(false);
  };
  // Rule C18: only a performing (active) loan can be listed; no approval request exists.
  const notListable = holding.loan.loan_status !== "active";
  const projectedInterestMinor = holding.investment_schedule.reduce(
    (sum, row) => sum + row.projected_interest_minor,
    0
  );
  const continueToVerification = () => {
    setError("");
    if (notListable) {
      setError(secondaryListingAction(holding.loan.loan_status).hint);
      return;
    }
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
    if (!pricing) {
      setError("The listing price is still being calculated.");
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
    // Reuse the acceptance only for a retry of exactly this price.
    let current = attempt.priceBps === price ? attempt : newListingAttempt(price, isEdit);
    try {
      const acceptance = current.acceptanceId
        ? { id: current.acceptanceId }
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
                currency: holding.currency,
                ...(pricing ? {
                  transfer_price_minor: pricing.transfer_price_minor,
                  accrued_interest_minor: pricing.accrued_interest_minor,
                  maker_fee_minor: pricing.maker_fee_minor,
                  seller_net_proceeds_minor: pricing.seller_net_proceeds_minor
                } : {})
              },
              idempotency_key: current.acceptanceKey
            }
          });
      current = { ...current, acceptanceId: acceptance.id };
      setAttempt(current);
      if (listing) {
        await editMutation.mutateAsync({
          listingId: listing.id,
          data: {
            price_bps: price,
            document_acceptance_id: acceptance.id,
            idempotency_key: current.listingKey,
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
            idempotency_key: current.listingKey,
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
    const successTitle = isEdit ? "Listing updated" : "Listing published";
    return <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={successTitle}><SuccessState title={successTitle}>{isEdit ? "Your revised price and economics are now visible to buyers anonymously." : "Your holding is visible to buyers anonymously."}</SuccessState></Modal>;
  }
  return (
    <Modal
      xwide
      footer={step === "review" ? (
        <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={notListable || !ack || !Number.isFinite(price) || price < 1 || !pricing || (!isFixturePreview && !termsQuery.data)} variant="primary" onClick={continueToVerification}>Confirm listing data</Button></>
      ) : (
        <><Button variant="ghost" onClick={() => { setError(""); setAttempt(newListingAttempt(price, isEdit)); setStep("review"); }}>Back to listing data</Button><Button disabled={code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || acceptanceMutation.isPending || listingMutation.isPending || editMutation.isPending} variant="primary" onClick={submitListing}>{acceptanceMutation.isPending || listingMutation.isPending || editMutation.isPending ? "Submitting..." : isEdit ? "Verify and update" : "Verify and publish"}</Button></>
      )}
      onClose={onClose}
      title={`${isEdit ? "Edit listing for" : "List"} ${holding.loan.loan_title}`}
    >
      {step === "review" ? (
        <div className="col gap-16">
          {notListable ? <Banner tone="bad" title="This holding cannot be listed">{secondaryListingAction(holding.loan.loan_status).hint}</Banner> : null}
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
            <input className="input mono" inputMode="numeric" onChange={(event) => changePrice(event.target.value.replace(/\D/g, ""))} value={priceBps} />
          </Field>
          <Review rows={[
            { label: "Loan", value: holding.loan.loan_title },
            { label: "Borrower", value: holding.loan.borrower_name },
            { label: "Repayment type", value: formatEnumLabel(holding.loan.repayment_type) },
            { label: "LTV", value: loanLtvBps(holding.loan) === null ? "Not disclosed" : formatRateBps(loanLtvBps(holding.loan) ?? 0) },
            { label: "Current principal", value: `${holding.currency} ${formatMoneyMinor(holding.current_principal_minor, holding.currency)}` },
            ...pricingRows
          ]} />
          <p className="muted" style={{ fontSize: 11.5 }}>Figures for a sale today. Accrued interest grows each day until the sale, so you receive it up to the sale day.</p>
          {pricingQuery.isError && !isFixturePreview ? <Banner tone="bad" title="Price not available">{apiErrorMessage(pricingQuery.error)}</Banner> : null}
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
            ...pricingRows
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
      <main className="content acct-page acct-documents">
        <PageHead description="Accepted terms, transaction evidence, statements and tax information. Self-scoped to your account." title="Documents" />
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
    <main className="content acct-page acct-documents">
      <PageHead description="Accepted document history, transaction evidence, statements and tax information. Self-scoped to your account." title="Documents" />
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

type SettingsSection = "profile" | "verification" | "payout" | "communication" | "support";

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
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={emailCodeRequestDisabled(codeRequest)}
          requestLabel={emailCodeRequestLabel(codeRequest)}
          value={code}
          onChange={setCode}
          onRequest={codeRequest.requestCode}
        />
        {codeRequest.expiresAt ? <p className="acct-modal-note">Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
        {codeRequest.error || error ? <Banner tone="bad" title="Could not submit payout IBAN">{codeRequest.error || error}</Banner> : null}
      </div>
    </Modal>
  );
}

// Account statuses that block login and financial access (set by an admin).
const blockedAccountStatuses = new Set(["restricted", "locked", "closed"]);

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
    summary: "Uninvested funds have a 60-day holding limit. Investment eligibility depends on the loan funding window.",
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
            Funds must cover the full remaining funding period of the loan you choose, within their
            original 60-day holding limit. For example, a 30-day remaining subscription window needs
            at least 30 days of holding time left; a 10-day window needs 10. Uninvested funds must be
            returned by the holding deadline. Exchanging currency does not restart this clock.
          </>
        )
      },
      {
        question: "What happens at the 60-day deadline?",
        answer: (
          <>
            The deadline date is the last day: you can withdraw until the end of that day (Europe/Zurich). From
            the next day, if a verified usable payout IBAN is on file, the system can create a forced withdrawal.
            If there is no usable IBAN, money-moving actions are blocked and the overdue balance can enter
            penalty mode. The 60-day limit cannot be extended.
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
      {
        question: "Does converting currency reset the ageing clock?",
        answer: (
          <>
            No. FX is a settlement function, not a way to restart deadlines. Converted balance inherits the
            deadlines of the funds you converted — it never receives a fresh 60-day holding period.
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

function FaqContent({ variant = "portal", footer }: { variant?: "portal" | "site"; footer?: ReactNode }) {
  const [open, setOpen] = useState("0-0");
  const site = variant === "site";
  const title = "Help & FAQ";
  const description = "Plain-English answers on onboarding, balances, orders, risk, FX, documents and the secondary market.";
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
      {faqSections.map((section, sectionIndex) => (
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

  if (!site) {
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
        {footer}
      </div>
    );
  }

  return (
    <div className="faq-v-site">
      <section className="site-page-head">
        <div className="site-wrap">
          <span className="site-eyebrow">Help</span>
          <h1 className="site-h1">{title}</h1>
          <p className="site-lead">{description}</p>
        </div>
      </section>
      <section className="site-section no-rule site-flush-top">
        <div className="site-wrap site-sidebar-layout">
          <nav aria-label="Topics" className="site-side-nav">
            <ul>
              {faqSections.map((section, sectionIndex) => (
                <li key={section.title}>
                  <a
                    href={`#${sectionId(sectionIndex)}`}
                    onClick={(event) => {
                      const target = document.getElementById(sectionId(sectionIndex));
                      if (!target) return;
                      event.preventDefault();
                      siteScrollTo(target);
                    }}
                  >
                    {section.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="faq-main">
            {intro}
            {sections}
            {risk}
            <div className="site-box is-ink-rule faq-still">
              <h2 className="site-h4">Need help?</h2>
              <p className="site-text">
                Write to <a href={`mailto:${supportEmail}`}>{supportEmail}</a>.
              </p>
              {footer}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function PublicFaqPage({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  return (
    <SiteShell active="help" setRoute={setRoute}>
      <FaqContent
        footer={
          <div className="faq-cta">
            <Button className="site-btn-outline" onClick={() => goTo(setRoute, "publicProjects")}>Back to marketplace</Button>
            <Button variant="primary" onClick={() => goTo(setRoute, "register")}>Create lender account</Button>
          </div>
        }
        variant="site"
      />
    </SiteShell>
  );
}

// Unknown address (audit A-62): a real "page not found" page that keeps the bad URL visible,
// instead of silently showing the home page or the Overview.
function NotFoundPage({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  useEffect(() => {
    document.title = `Page not found · ${platformName}`;
  }, []);
  return (
    <SiteShell setRoute={setRoute}>
      <section className="site-page-head">
        <div className="site-wrap">
          <span className="site-eyebrow">Error 404</span>
          <h1 className="site-h1">Page not found</h1>
          <p className="site-lead">
            There is no page at this address. Check the link, or go to one of the pages below.
          </p>
        </div>
      </section>
      <section className="site-section no-rule site-flush-top">
        <div className="site-wrap">
          <div className="faq-cta not-found-actions">
            <Button variant="primary" onClick={() => goTo(setRoute, "public")}>Home page</Button>
            <Button className="site-btn-outline" onClick={() => goTo(setRoute, "publicProjects")}>Projects</Button>
            <Button className="site-btn-outline" onClick={() => goTo(setRoute, "dashboard")}>My account</Button>
          </div>
        </div>
      </section>
    </SiteShell>
  );
}

// Portal Help page (design "help"): FaqContent is shared with the public FAQ,
// so it is wrapped here and left unchanged. Its own page head repeats this
// page head and is hidden inside the wrapper (see skin/account.css).
function FaqScreen() {
  return (
    <main className="content acct-page portal-help">
      <PageHead
        description="Plain-English answers on onboarding, balances, orders, risk, FX, documents and the secondary market."
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

function LegalDocumentPage({ setRoute }: { setRoute: (route: AppRoute) => void }) {
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

  const documentNav = (
    <nav aria-label="Legal documents" className="site-side-nav">
      <ul>
        {Object.keys(legalDocumentTitles).map((item) => (
          <li key={item}>
            <a
              aria-current={item === category ? "page" : undefined}
              className={item === category ? "active" : undefined}
              href={legalDocumentPath(item)}
            >
              {legalDocumentTitles[item]}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );

  return (
    <SiteShell setRoute={setRoute}>
      <div className="legal-doc">
        <section className="site-page-head">
          <div className="site-wrap">
            <span className="site-eyebrow">Legal</span>
            <h1 className="site-h1">{known ? title : "Legal documents"}</h1>
            {known ? (
              <p className="site-lead">
                The exact server-published version you accept in the platform. Values in brackets are
                filled with your transaction data at acceptance time.
              </p>
            ) : null}
          </div>
        </section>
        <section className="site-section no-rule site-flush-top">
          <div className="site-wrap site-sidebar-layout">
            {documentNav}
            {!known ? (
              <div className="site-box">
                <Empty icon="doc" title="Document not found">
                  This document address is not recognized. Open {platformName} and use the links in each flow.
                </Empty>
              </div>
            ) : (
              <div className="site-prose">
                <div className="site-doc-meta">
                  {doc ? (
                    <div className="legal-doc-meta">
                      <Chip status={`v${doc.version_number}`} tone="info" />
                      <span>hash {doc.content_hash.slice(0, 16)}</span>
                      {doc.published_at ? <span>published {formatDate(doc.published_at)}</span> : null}
                    </div>
                  ) : <span />}
                  <Button disabled={downloading || isFixturePreview} icon="doc" variant="primary" onClick={download}>
                    {downloading ? "Preparing PDF..." : "Download PDF"}
                  </Button>
                </div>
                {downloadError ? <Banner tone="bad" title="Download failed">{downloadError}</Banner> : null}
                {isFixturePreview ? (
                  <p className="site-callout">Preview mode: live document content loads from the published server template.</p>
                ) : templateQuery.isLoading ? (
                  <p className="site-callout">Loading the current published document...</p>
                ) : doc ? (
                  <>
                    <div className="legal-document-preview legal-doc-body">{renderLegalBody(doc.body)}</div>
                    {Array.isArray(doc.checkbox_labels) && doc.checkbox_labels.length > 0 ? (
                      <div className="legal-doc-acks">
                        <h2>You will be asked to confirm</h2>
                        <ul>
                          {(doc.checkbox_labels as string[]).map((label) => (
                            <li key={label}>{label}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </>
                ) : templateQuery.error instanceof ApiClientError && templateQuery.error.status === 404 ? (
                  <Banner icon="doc" tone="info" title="Not yet published">
                    The current version of this document is being prepared and will appear on this page once it is
                    published. Questions in the meantime: {supportEmail}.
                  </Banner>
                ) : (
                  <Banner tone="bad" title="Document unavailable">
                    The current published document could not be loaded. Retry, or contact {supportEmail}.
                  </Banner>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </SiteShell>
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
          idempotency_key: current.purchaseKey
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
    ? null
    : step === "confirm"
      ? <><Button onClick={() => setStep("review")}>Back</Button><Button disabled={code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || busy} variant="primary" onClick={() => void confirmPurchase()}>{busy ? "Purchasing..." : "Purchase claim"}</Button></>
      : step === "review"
        ? <><Button onClick={() => { setQuote(null); setClaimAttempt(null); setStep("amount"); }}>Reprice</Button><Button disabled={!ack1 || !ack2 || !quote} variant="primary" onClick={() => setStep("confirm")}>Continue</Button></>
        : <><Button onClick={onClose}>Cancel</Button><Button disabled={amountMinor <= 0 || Boolean(amountError) || quoteMutation.isPending} variant="primary" onClick={() => void requestQuote()}>{quoteMutation.isPending ? "Pricing..." : "Get executable quote"}</Button></>;

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
          <Banner icon="lock" tone="info" title="Confirm this claim purchase">Enter the 6-digit email confirmation code. A successful confirmation immediately assigns the claim and adds it to your portfolio.</Banner>
          <CodeRequestField hint={previewHint("Demo: any 6 digits")} label="Email confirmation code" requestDisabled={emailCodeRequestDisabled(codeRequest)} requestLabel={emailCodeRequestLabel(codeRequest)} value={code} onChange={setCode} onRequest={codeRequest.requestCode} />
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
          sensitive_action_code: code
        }
      });
      void queryClient.invalidateQueries();
      setPlacedOrder(order);
      setStep("done");
    } catch (mutationError) {
      if (isOrderNotPendingError(mutationError)) setAttempt(newPrimaryOrderAttempt(amountMinor));
      setError(apiErrorMessage(mutationError));
    }
  };

  const footer = step === "done"
    ? null
    : step === "confirm"
      ? <><Button onClick={() => setStep("review")}>Back</Button><Button disabled={code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || submitting} variant="primary" onClick={() => void confirmOrder()}>{submitting ? "Submitting..." : "Confirm order"}</Button></>
      : step === "review"
        ? <><Button onClick={backToAmount}>Back</Button><Button disabled={!ack1 || !ack2} variant="primary" onClick={() => setStep("confirm")}>Continue</Button></>
        : <><Button onClick={onClose}>Cancel</Button><Button disabled={amountMinor < loan.minimum_investment_minor || Boolean(amountError)} variant="primary" onClick={() => setStep("review")}>Review order</Button></>;

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
          <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code.</Banner>
          {!isFixturePreview && termsQuery.isError ? <Banner tone="bad" title="Investment terms unavailable">The current server-published investment terms could not be loaded.</Banner> : null}
          {!isFixturePreview && termsQuery.data ? <p className="iv-note">Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
          <CodeRequestField
            hint={previewHint("Demo: any 6 digits")}
            label="Email confirmation code"
            requestDisabled={emailCodeRequestDisabled(codeRequest)}
            requestLabel={emailCodeRequestLabel(codeRequest)}
            value={code}
            onChange={setCode}
            onRequest={codeRequest.requestCode}
          />
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

function priceLabel(discountPremiumBps: number) {
  if (discountPremiumBps === 0) return "At par";
  return discountPremiumBps < 0 ? `${formatRateBps(Math.abs(discountPremiumBps))} discount` : `${formatRateBps(discountPremiumBps)} premium`;
}
