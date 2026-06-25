import { useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AdminApp } from "./adminConsole/AdminApp";
import {
  ActionEnum,
  CategoryEnum,
  DocumentKindEnum,
  InvestorDocumentDownloadRequestOutputFormatEnum,
  useV1AuthMeRetrieve,
  useV1AuthLogoutCreate,
  useV1AuthMagicLinkConsumeCreate,
  useV1AuthMagicLinkRequestCreate,
  useV1AuthPhoneConfirmCreate,
  useV1AuthPhoneRequestCreate,
  useV1AuthRegisterNaturalPersonCreate,
  useV1AuthSensitiveActionCodeRequestCreate,
  useV1DocumentsAcceptancesCreate,
  useV1DocumentsTemplatesCurrentRetrieve,
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
  useV1MarketplaceSecondaryListingsPurchaseCreate
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
  BalanceSummary,
  FxQuote,
  Holding,
  InvestorDocument,
  InvestorDocumentDownloadResponse,
  MarketplaceLoanDetail,
  MarketplaceLoanPreview,
  PayoutInstruction,
  PrimaryOrderPortal,
  PublicDocumentTemplateVersion,
  SecondaryListingPortal,
  SecondaryMarketBuyerListing,
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
  useSecondaryListingsData,
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
  safeMetadataCategory
} from "./investorPortal/format";
import type { AppRoute, DemoAccountState, RouteName } from "./investorPortal/types";
import {
  Banner,
  BarBreakdown,
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

const loginFlowStorageKey = "banxum:login-flow:v1";
const registerFlowStorageKey = "banxum:register-flow:v3";
const appRouteStorageKey = "banxum:app-route:v1";

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
  "login",
  "register",
  "kyc",
  "dashboard",
  "market",
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

const routeTitles: Record<RouteName, string> = {
  public: platformName,
  login: "Log in",
  register: "Register",
  kyc: "Verification",
  dashboard: "Dashboard",
  market: "Marketplace",
  loan: "Marketplace",
  portfolio: "Portfolio",
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
      { route: "market", label: "Marketplace", icon: "market" },
      { route: "portfolio", label: "Portfolio", icon: "portfolio" },
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
      { route: "notifications", label: "Notifications", icon: "bell" },
      { route: "settings", label: "Settings", icon: "settings" },
      { route: "faq", label: "Help & FAQ", icon: "info" }
    ]
  }
];

const riskText =
  `I understand that investing through ${platformName} involves lending-related risks. I may lose some or all of the amount invested. Borrowers may pay late, pay only part of the expected amount, or default. Collateral, guarantees or security may not fully cover losses and may take time and cost to enforce. Expected returns are not guaranteed, past performance and risk ratings do not guarantee future results, and secondary-market sale may be unavailable or only possible at a lower price.`;

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

function useSensitiveActionCode(action: ActionEnum) {
  const requestMutation = useV1AuthSensitiveActionCodeRequestCreate();
  const [codeId, setCodeId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [error, setError] = useState("");

  const requestCode = useCallback(() => {
    setError("");
    if (isFixturePreview) {
      setCodeId("00000000-0000-0000-0000-000000000000");
      setExpiresAt(new Date(Date.now() + 10 * 60 * 1000).toISOString());
      return;
    }
    requestMutation.mutate(
      { data: { action } },
      {
        onSuccess: (response) => {
          setCodeId(response.code_id);
          setExpiresAt(response.expires_at);
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  }, [action, requestMutation]);

  return { codeId, expiresAt, error, isRequesting: requestMutation.isPending, requestCode };
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
  codeRequest: Pick<ReturnType<typeof useSensitiveActionCode>, "codeId" | "isRequesting">
) {
  if (codeRequest.isRequesting) return "Sending code...";
  return codeRequest.codeId ? "Send a new email code" : "Send email code";
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

function currentInvestableLotsForLoanCurrency(lots: BalanceLot[] | undefined, loan: MarketplaceLoanDetail) {
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

function isOpenMarketplaceLoan(loan: Pick<MarketplaceLoanPreview, "status" | "remaining_capacity_minor">) {
  return ["open", "published"].includes(loan.status) && loan.remaining_capacity_minor > 0;
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
  setRoute(nextRoute);
  window.scrollTo({ top: 0, behavior: "instant" });
}

function clearPortalSessionState(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.clear();
  removeStoredObject(loginFlowStorageKey);
  removeStoredObject(registerFlowStorageKey);
}

export function App() {
  const initialRoute: AppRoute = readReadonlyImpersonationToken()
    ? { name: "dashboard" }
    : window.location.pathname.startsWith("/login")
      ? { name: "login" }
      : readStoredRoute();
  const [route, setRoute] = useState<AppRoute>(initialRoute);
  const [demoState, setDemoState] = useState<DemoAccountState>("active");

  if (window.location.pathname.startsWith("/admin")) {
    return <AdminApp />;
  }

  if (window.location.pathname.startsWith("/kyc/callback")) {
    return <KycReturnScreen setRoute={setRoute} />;
  }

  if (route.name === "public") {
    return <PublicLanding setRoute={setRoute} />;
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
  return (
    <div className="brand" style={{ padding: 0 }}>
      <span className="brand-mark">{platformName.slice(0, 1)}</span>
      <div className="col" style={{ gap: 0 }}>
        <span className="brand-name" style={compact ? { fontSize: 14 } : undefined}>
          {platformName}
        </span>
        <span className="brand-sub">by {operatorName}</span>
      </div>
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
          <a onClick={() => goTo(setRoute, "faq")}>How it works</a>
          <a onClick={() => goTo(setRoute, "faq")}>FAQ</a>
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
            <button className="btn-link" onClick={() => goTo(setRoute, "faq")} type="button">How it works</button>
            <button className="btn-link" onClick={() => goTo(setRoute, "faq")} type="button">FAQ</button>
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
              <button className="btn-link" onClick={() => goTo(setRoute, "faq")} type="button">How it works</button>
              <button className="btn-link" onClick={() => goTo(setRoute, "faq")} type="button">FAQ</button>
            </div>
            <div className="page-head">
              <div>
                <h1>Open loan opportunities</h1>
                <div className="ph-sub">
                  Preview current primary-market loans. Borrower documents, ratings, collateral detail and
                  investing unlock after registration and identity verification.
                </div>
                <p className="lede-line">
                  Put your capital to work: fund highly collateralised, secured loans and earn monthly interest.
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
      desc: `${operatorName} sources, underwrites and services business loans across Switzerland and the EU/EEA. Every loan is risk-rated, secured by collateral, and fully documented.`
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
      desc: `Interest and principal land in your balance on schedule. Reinvest into new loans, exchange currency, sell early on the secondary market, or withdraw to your bank.`
    }
  ];

  const facts: Array<{ fig: ReactNode; k: string; d: string }> = [
    {
      fig: <>8–18<span className="u">%</span></>,
      k: "Target annual interest",
      d: "Target range across loans on the platform. Returns are targets, not guarantees."
    },
    {
      fig: <>1,000<span className="u"> +</span></>,
      k: "Minimum per loan",
      d: "CHF or EUR. A low entry point so you can diversify widely from the start."
    },
    {
      fig: <>Monthly</>,
      k: "Repayment cash flow",
      d: "Most loans repay interest and principal on a schedule — income before maturity, not only at the end."
    },
    {
      fig: <>10<span className="u">/10</span></>,
      k: "Secured by collateral",
      d: "Every loan is backed by real assets — no unsecured lending on the platform."
    },
    {
      fig: <>{"≤ 63"}<span className="u">%</span></>,
      k: "Conservative loan-to-value",
      d: "Pledged collateral comfortably exceeds every loan, cushioning against loss for lower risk."
    }
  ];

  return (
    <>
      <section className="lband surface">
        <div className="lband-inner">
          <div className="lband-eyebrow">What we do</div>
          <h2 className="lband-title">Private lending, opened up to individuals</h2>
          <p className="lband-lede">
            {platformName} lets you invest directly in secured business loans — a form of private credit
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
            Across 10 loans in 6 countries on the platform today. Peer-to-peer lending carries risk:
            borrowers may pay late or default, collateral may not fully cover losses, capital is at risk,
            and an early exit on the secondary market is not guaranteed. Platform balances are not bank
            deposits and returns are not guaranteed.
          </p>
          <div className="dark-cta">
            <Button size="lg" variant="primary" onClick={() => goTo(setRoute, "register")}>
              Create your investor account
            </Button>
            <a onClick={() => goTo(setRoute, "faq")}>Read how it works →</a>
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
          </div>
          <h1>{loan.title}</h1>
          <div className="ph-sub mono">{loan.loan_id}</div>
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
    readStoredObject(loginFlowStorageKey, { email: "", sent: false })
  );
  const [email, setEmail] = useState(initialLoginState.email);
  const [sent, setSent] = useState(initialLoginState.sent);
  const [error, setError] = useState("");
  const magicLinkRequest = useV1AuthMagicLinkRequestCreate();
  const magicLinkConsume = useV1AuthMagicLinkConsumeCreate();

  useEffect(() => {
    writeStoredObject(loginFlowStorageKey, { email, sent });
  }, [email, sent]);

  const consumeAttemptedRef = useRef(false);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token || isFixturePreview) return;
    // The token is single-use: never fire a second consume request even if
    // the effect re-runs (e.g. StrictMode double-mount in development).
    if (consumeAttemptedRef.current) return;
    consumeAttemptedRef.current = true;
    magicLinkConsume.mutate(
      { data: { token } },
      {
        onSuccess: (response) => {
          removeStoredObject(loginFlowStorageKey);
          window.history.replaceState({}, "", "/");
          if (resumeOnboardingForUser(response.user, setRoute)) return;
          removeStoredObject(registerFlowStorageKey);
          goTo(setRoute, "dashboard");
        },
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
    // The generated mutation object is intentionally omitted to avoid
    // re-consuming the one-time token after React Query state changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setRoute]);

  const requestMagicLink = () => {
    setError("");
    if (isFixturePreview) {
      setSent(true);
      return;
    }
    magicLinkRequest.mutate(
      { data: { email } },
      {
        onSuccess: () => setSent(true),
        onError: (mutationError) => setError(apiErrorMessage(mutationError))
      }
    );
  };

  function submitMagicLink(event: FormEvent) {
    event.preventDefault();
    requestMagicLink();
  }

  if (magicLinkConsume.isPending) {
    return (
      <AuthShell onClose={() => goTo(setRoute, "public")}>
        <div className="auth-card"><Empty icon="clock" title="Signing you in">Verifying your one-time login link.</Empty></div>
      </AuthShell>
    );
  }

  return (
    <AuthShell onClose={() => goTo(setRoute, "public")}>
      <div className="auth-card">
        {!sent ? (
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
              New to {platformName}? <a onClick={() => goTo(setRoute, "register")}>Register as a lender</a>
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
            {isFixturePreview ? <Button block variant="primary" onClick={() => goTo(setRoute, "dashboard")}>
              Open link in demo
            </Button> : null}
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
            <a onClick={() => leaveTo("login")}>Log in here</a>.
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
  const phoneNumber = e164PhoneNumber(phoneCountryCode, phoneNationalNumber);
  const phoneNumberLabel = phoneNumber || "your registered mobile number";
  const phoneCooldownSeconds = Math.max(0, Math.ceil((phoneCooldownUntil - nowMs) / 1000));
  const phoneRequestDisabled = phoneRequestMutation.isPending || phoneCooldownSeconds > 0;
  const emailCooldownSeconds = Math.max(0, Math.ceil((emailCooldownUntil - nowMs) / 1000));
  const registrationLabels = templateLabels(registrationTermsQuery.data);
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
            <div className="legal" style={{ margin: "14px 0 12px" }}>
              <h5>
                {isFixturePreview
                  ? "Platform Terms of Use - v4.2"
                  : registrationTermsQuery.data?.title ?? "Lender user agreement"}
              </h5>
              {isFixturePreview ? (
                <p>
                  By registering you enter into the {platformName} platform terms operated by{" "}
                  {operatorName}. Platform balances are non-interest-bearing and subject to regulatory
                  ageing limits. The 60-day holding limit cannot be extended.
                </p>
              ) : registrationTermsQuery.isLoading ? (
                <p className="muted">Loading the current server-published lender agreement...</p>
              ) : registrationTermsQuery.data ? (
                <>
                  <p className="muted">
                    Server-published v{registrationTermsQuery.data.version_number}. Hash{" "}
                    <span className="mono">{registrationTermsQuery.data.content_hash.slice(0, 12)}</span>.
                    Acceptance records a versioned PDF snapshot and emails a copy to you.
                  </p>
                  <div
                    aria-label="Current lender user agreement"
                    className="legal-document-preview"
                  >
                    {registrationTermsQuery.data.body}
                  </div>
                </>
              ) : (
                <p className="muted">
                  The current server-published lender agreement could not be loaded. Retry before
                  registering.
                </p>
              )}
              <p className="muted">Server-versioned clickwrap. Acceptance is recorded with document version, timestamp and context.</p>
            </div>
            <div className="col gap-10">
              {isFixturePreview || registrationLabels.length === 0 ? (
                <Check checked={terms} id="register-terms" onChange={setTerms}>I accept the platform terms and registration documents.</Check>
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
                    {label}
                  </Check>
                ))
              )}
              <Check checked={risk} id="register-risk" onChange={setRisk}>I acknowledge the generic P2P lending risk disclosure.</Check>
              <Check checked={marketing} id="register-marketing" onChange={setMarketing}>I agree to optional marketing communications.</Check>
            </div>
            {!isFixturePreview && registrationTermsQuery.isError ? (
              <Banner tone="bad" title="Agreement unavailable">
                The current server-published lender agreement could not be loaded.
              </Banner>
            ) : null}
            {error ? <Banner tone="bad" title="Could not register">{error}</Banner> : null}
            <Button block disabled={!allRegistrationTermsAccepted || !risk || !email.includes("@") || !phoneNumber || registerMutation.isPending || (!isFixturePreview && !registrationTermsQuery.data)} style={{ marginTop: 16 }} variant="primary" onClick={submitRegistration}>
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
          Back to marketplace preview
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
  const [investLoan, setInvestLoan] = useState<MarketplaceLoanDetail | null>(null);
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
    setInvestLoan(null);
  };
  const logoutMutation = useV1AuthLogoutCreate({
    mutation: { onSettled: finishLogout }
  });
  const kycGateQuery = useV1KycStatusRetrieve({
    query: {
      enabled: !isFixturePreview && !readonlyImpersonation.active,
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
    isFixturePreview || readonlyImpersonation.active || kycGateQuery.data?.financial_access_allowed === true;
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
    : displayProfile();

  const screen = (() => {
    switch (route.name) {
      case "dashboard":
        return <Dashboard demoState={demoState} setRoute={setRoute} />;
      case "market":
        return <MarketplaceScreen demoState={demoState} setInvestLoan={setInvestLoan} setRoute={setRoute} />;
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
        return <SecondaryMarketScreen demoState={demoState} />;
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
        return <Dashboard demoState={demoState} setRoute={setRoute} />;
    }
  })();

  const gatedScreen =
    !isFixturePreview && !financialAccessAllowed
      ? kycGateQuery.isPending && !kycGateQuery.data
        ? <ScreenLoading title="Verification" />
        : <KycStatusScreen setRoute={setRoute} />
      : screen;

  const overdueCount = balances.lots.filter((lot) => lot.bucket === "overdue" || lot.bucket === "penalty").length;
  const displayRouteName = !financialAccessAllowed && !isFixturePreview ? "kyc" : route.name;
  const activeRoute = displayRouteName === "loan" ? "market" : displayRouteName;

  return (
    <div className="app">
      <div className={`nav-scrim ${navOpen ? "show" : ""}`} onClick={() => setNavOpen(false)} />
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="brand">
          <span className="brand-mark">{platformName.slice(0, 1)}</span>
          <div className="col" style={{ gap: 0 }}>
            <span className="brand-name">{platformName}</span>
            <span className="brand-sub">{operatorName}</span>
          </div>
        </div>
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
                    {item.label}
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
        <header className="topbar">
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
              <select onChange={(event) => setDemoState(event.target.value as DemoAccountState)} value={demoState}>
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
      {investLoan ? <InvestModal loan={investLoan} onClose={() => setInvestLoan(null)} /> : null}
    </div>
  );
}

function Dashboard({ demoState, setRoute }: { demoState: DemoAccountState; setRoute: (route: AppRoute) => void }) {
  const dashboardQuery = useDashboardData();
  const balancesQuery = useBalancesData();
  const loansQuery = useMarketplaceLoansData();
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

  const openLoans = loans.filter(isOpenMarketplaceLoan).slice(0, 4);
  const firstName = displayProfile().name.split(" ")[0] || "Investor";

  return (
    <main className="content">
      <div className="page-head">
        <div>
          <h1>Welcome back, {firstName}</h1>
          <div className="ph-sub">Account overview - {formatDate(dashboard.as_of)} - Europe/Zurich</div>
        </div>
        <div className="page-actions">
          <Button icon="wallet" onClick={() => goTo(setRoute, "balances")}>Deposit</Button>
          <Button icon="market" variant="primary" onClick={() => goTo(setRoute, "market")}>Browse loans</Button>
        </div>
      </div>

      <div className="col gap-12" style={{ marginBottom: 20 }}>
        {demoState === "frozen" ? <FrozenBanner setRoute={setRoute} /> : null}
        {demoState === "kyc_pending" ? <KycBanner setRoute={setRoute} /> : null}
        {demoState === "active" ? <AgeingAlerts balances={balances.summaries} setRoute={setRoute} /> : null}
      </div>

      <div className="grid-stat" style={{ marginBottom: 20 }}>
        <Stat amountMinor={sumAmounts(dashboard.portfolio_summary.outstanding_principal_by_currency)} currency="CHF" label="Outstanding principal" sub={`${dashboard.portfolio_summary.active_holding_count} active holdings`} />
        <Stat amountMinor={sumAmounts(dashboard.portfolio_summary.realized_interest_by_currency)} currency="CHF" label="Interest received" sub="lifetime distributions" />
        <Stat amountMinor={sumAmounts(dashboard.portfolio_summary.late_or_defaulted_exposure_by_currency)} currency="CHF" label="Late/default principal" sub="watch status updates" />
        <Stat label="Weighted yield" raw="7.6%" sub="display projection" />
      </div>

      <div className="dash-split">
        <section>
          <div className="section-head"><h2>Balances</h2><a onClick={() => goTo(setRoute, "balances")}>Manage</a></div>
          <div className="grid grid-2">
            {balances.summaries.map((summary) => <BalanceCard key={summary.currency} summary={summary} setRoute={setRoute} frozen={demoState === "frozen"} />)}
          </div>
        </section>
        <section>
          <div className="section-head"><h2>Required actions</h2></div>
          <Card>
            {dashboard.pending_actions.map((action, index) => (
              <ActionRow action={action} key={`${action.type}-${index}`} setRoute={setRoute} last={index === dashboard.pending_actions.length - 1} />
            ))}
          </Card>
        </section>
      </div>

      <section className="section">
        <div className="section-head"><h2>Open opportunities</h2><a onClick={() => goTo(setRoute, "market")}>All loans</a></div>
        {loansQuery.isError && loans.length === 0 ? (
          <DataErrorCard title="Could not load opportunities" onRetry={() => void loansQuery.refetch()}>
            Your balances and portfolio loaded, but marketplace data is temporarily unavailable.
          </DataErrorCard>
        ) : (
          <LoansTable loans={openLoans} onOpen={(loan) => goTo(setRoute, "loan", { loanId: loan.loan_id })} />
        )}
      </section>

      <section className="section">
        <div className="section-head"><h2>Recent activity</h2><a onClick={() => goTo(setRoute, "portfolio")}>Full history</a></div>
        <ActivityTable entries={dashboard.recent_activity.slice(0, 6)} dense />
      </section>
    </main>
  );
}

function AgeingAlerts({ balances, setRoute }: { balances: BalanceSummary[]; setRoute: (route: AppRoute) => void }) {
  const overdue = balances.filter((summary) => summary.overdue_minor > 0 || summary.withdraw_only_minor > 0);
  if (overdue.length === 0) return null;

  return (
    <Banner
      actions={
        <>
          <Button size="sm" onClick={() => goTo(setRoute, "balances")}>Review balances</Button>
          <Button size="sm" variant="ghost" onClick={() => goTo(setRoute, "balances")}>Withdraw funds</Button>
        </>
      }
      tone="warn"
      title="Balance ageing - action needed"
    >
      Some balance lots are withdraw-only or approaching the 60-day regulatory deadline. {operatorName} cannot extend the 60-day limit.
    </Banner>
  );
}

function FrozenBanner({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  return (
    <Banner
      actions={<Button size="sm" variant="danger" onClick={() => goTo(setRoute, "balances")}>Add payout IBAN</Button>}
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

function BalanceCard({ summary, setRoute, frozen }: { summary: BalanceSummary; setRoute: (route: AppRoute) => void; frozen: boolean }) {
  return (
    <Card padded>
      <div className="row spread" style={{ marginBottom: 12 }}>
        <div className="row gap-8"><span className="brand-name" style={{ fontSize: 13 }}>{summary.currency}</span><span className="muted">balance</span></div>
        <span className="stat-value" style={{ fontSize: 18 }}>{formatMoneyMinor(summary.total_available_minor, summary.currency)}</span>
      </div>
      <BalanceRow currency={summary.currency} label="Investable" tone="ok" value={summary.investable_minor} />
      <BalanceRow currency={summary.currency} label="Withdraw-only" tone="warn" value={summary.withdraw_only_minor} />
      <BalanceRow currency={summary.currency} label="Overdue" tone="warn" value={summary.overdue_minor} />
      <BalanceRow currency={summary.currency} label="Penalty mode" tone="bad" value={summary.penalty_mode_minor + summary.frozen_minor} />
      <div className="row gap-8" style={{ marginTop: 14 }}>
        <Button block disabled={frozen} size="sm" onClick={() => goTo(setRoute, "balances")}>Deposit</Button>
        <Button block size="sm" variant="ghost" onClick={() => goTo(setRoute, "balances")}>Withdraw</Button>
      </div>
    </Card>
  );
}

function BalanceRow({ label, value, tone, currency }: { label: string; value: number; tone: "ok" | "warn" | "bad"; currency: string }) {
  return (
    <div className="row spread" style={{ fontSize: 12.5, marginTop: 7 }}>
      <span className="row gap-6">
        <span style={{ background: `var(--${tone})`, borderRadius: "50%", height: 7, width: 7 }} />
        {label}
      </span>
      <span className="mono">{formatMoneyMinor(value, currency)}</span>
    </div>
  );
}

function ActionRow({
  action,
  setRoute,
  last
}: {
  action: { type: string; severity: string; message: string };
  setRoute: (route: AppRoute) => void;
  last: boolean;
}) {
  const route = action.type.includes("balance") ? "balances" : "portfolio";
  return (
    <div className="row gap-12" style={{ alignItems: "flex-start", borderBottom: last ? 0 : "1px solid var(--line)", padding: "13px 16px" }}>
      <Icon name={action.severity === "bad" ? "alert" : "clock"} size={17} />
      <div className="grow">
        <div className="col-strong">{action.type.replaceAll("_", " ")}</div>
        <div className="muted" style={{ fontSize: 12 }}>{action.message}</div>
      </div>
      <Button size="sm" variant="ghost" onClick={() => goTo(setRoute, route)}>View</Button>
    </div>
  );
}

function MarketplaceScreen({
  setRoute
}: {
  demoState: DemoAccountState;
  setInvestLoan: (loan: MarketplaceLoanDetail) => void;
  setRoute: (route: AppRoute) => void;
}) {
  const loansQuery = useMarketplaceLoansData();
  const loans = loansQuery.data ?? [];
  const [query, setQuery] = useState("");
  const [currency, setCurrency] = useState("all");
  const [availability, setAvailability] = useState<"open" | "all">("open");

  const filtered = loans.filter((loan) => {
    const matchesSearch = `${loan.loan_id} ${loan.title}`.toLowerCase().includes(query.toLowerCase());
    const matchesCurrency = currency === "all" || loan.currency === currency;
    const matchesAvailability = availability === "all" || isOpenMarketplaceLoan(loan);
    return matchesSearch && matchesCurrency && matchesAvailability;
  });

  return (
    <main className="content">
      <div className="page-head">
        <div>
          <h1>Marketplace</h1>
          <div className="ph-sub">Primary-market loan claims open for investment. Minimum CHF/EUR 1,000 per order.</div>
        </div>
        <Segmented options={[{ value: "open", label: "Open" }, { value: "all", label: "All" }]} value={availability} onChange={setAvailability} />
      </div>
      <div className="toolbar">
        <div className="search">
          <Icon name="search" size={15} />
          <input className="input" onChange={(event) => setQuery(event.target.value)} placeholder="Search borrower or loan ID" value={query} />
        </div>
        <select className="select filter-select" onChange={(event) => setCurrency(event.target.value)} value={currency}>
          <option value="all">All currencies</option>
          <option value="CHF">CHF</option>
          <option value="EUR">EUR</option>
        </select>
        <span className="results-count">{filtered.length} loans</span>
      </div>
      {loansQuery.isError && loans.length === 0 ? (
        <DataErrorCard title="Could not load marketplace" onRetry={() => void loansQuery.refetch()}>
          The primary-market loan list is unavailable. Retry once the API connection is restored.
        </DataErrorCard>
      ) : loansQuery.isLoading && loans.length === 0 ? (
        <LoadingCard title="Loading marketplace">Fetching primary-market loans.</LoadingCard>
      ) : filtered.length === 0 ? (
        <Card><Empty icon="search" title="No loans match these filters">Try widening the currency or availability filters.</Empty></Card>
      ) : (
        <LoansTable loans={filtered} onOpen={(loan) => goTo(setRoute, "loan", { loanId: loan.loan_id })} />
      )}
      <p className="muted" style={{ fontSize: 11.5, marginTop: 14, maxWidth: 760 }}>
        Funding progress reflects validated allocations only. Pending orders do not reserve capacity.
      </p>
    </main>
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

  return (
    <main className="content">
      <button className="backlink" onClick={() => goTo(setRoute, "market")} type="button"><Icon name="arrowL" size={14} /> Marketplace</button>
      <div className="page-head">
        <div>
          <div className="row gap-8 wrap" style={{ marginBottom: 5 }}>
            <Chip status={loan.status} />
            <Rating value={loan.risk_rating} />
            <span className="tag">{loan.currency}</span>
          </div>
          <h1>{loan.title}</h1>
          <div className="ph-sub mono">{loan.loan_id}</div>
        </div>
      </div>
      <div className="split">
        <div>
          <Card padded>
            <div className="grid grid-4" style={{ gap: 0 }}>
              <Stat amountMinor={loan.principal_minor} currency={loan.currency} label="Amount" />
              <Stat label="Target interest" raw={formatRateBps(loan.interest_rate_bps)} sub="per annum" />
              <Stat label="Term" raw={`${loan.term_months} mo`} sub={loan.repayment_type} />
              <Stat label="Funded" raw={`${fundingPercent(loan)}%`} sub={`${loan.currency} ${formatMoneyMinor(loan.committed_principal_minor, loan.currency)}`} />
            </div>
            <div style={{ marginTop: 14 }}>
              <Progress percent={fundingPercent(loan)} />
              <div className="row spread muted" style={{ fontSize: 12, marginTop: 6 }}>
                <span>{loan.currency} {formatMoneyMinor(loan.committed_principal_minor, loan.currency)} allocated</span>
                <span>Closes {formatDate(loan.funding_deadline)}</span>
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
            {tab === "docs" ? <LoanDocuments /> : null}
            {tab === "risk" ? <RiskDisclosure /> : null}
          </div>
        </div>
        <aside className="aside-sticky">
          <Card padded>
            {loan.status === "funded" ? (
              <Empty icon="checkCircle" title="Fully funded">This loan is closed to new orders.</Empty>
            ) : (
              <>
                <div className="eyebrow" style={{ marginBottom: 8 }}>Invest in this loan</div>
                <KeyValue label="Target interest" value={`${formatRateBps(loan.interest_rate_bps)} p.a.`} />
                <KeyValue label="Minimum order" value={`${loan.currency} 1,000`} />
                <KeyValue label="Remaining" value={`${loan.currency} ${formatMoneyMinor(loan.remaining_capacity_minor, loan.currency)}`} />
                <KeyValue label="Closes" value={formatDate(loan.funding_deadline)} />
                {blocked || isReadonlyImpersonationActive() ? (
                  <Banner tone={demoState === "frozen" ? "bad" : "warn"} title={demoState === "frozen" ? "Financial actions frozen" : "Investing not yet available"}>
                    {isReadonlyImpersonationActive()
                      ? "Read-only impersonation cannot place orders."
                      : demoState === "frozen"
                        ? "Provide a usable payout IBAN to unlock investing."
                        : "Complete KYC verification to unlock investing."}
                  </Banner>
                ) : (
                  <Button block icon="trend" variant="primary" onClick={() => setInvestLoan(loan)}>Place investment order</Button>
                )}
                <p className="muted" style={{ fontSize: 11, lineHeight: 1.5, marginTop: 10 }}>
                  Orders are intents and do not reserve capacity until funds are allocated and validated.
                </p>
              </>
            )}
          </Card>
        </aside>
      </div>
    </main>
  );
}

function LoanOverview({ loan }: { loan: MarketplaceLoanDetail }) {
  return (
    <Card padded>
      <div className="eyebrow" style={{ marginBottom: 6 }}>Purpose</div>
      <p className="muted-2" style={{ lineHeight: 1.6, maxWidth: 680 }}>{loan.purpose_description}</p>
      <div className="hr" style={{ margin: "16px 0" }} />
      <dl className="kv">
        <KeyValueRow label="Loan ID" mono value={loan.loan_id} />
        <KeyValueRow label="Borrower" value={loan.title} />
        <KeyValueRow label="Currency" value={loan.currency} />
        <KeyValueRow label="Repayment type" value={loan.repayment_type} />
        <KeyValueRow label="Risk rating" value={loan.risk_rating} />
        <KeyValueRow label="Collateral type" value={loan.collateral_type} />
        {loan.ltv_bps !== null ? <KeyValueRow label="Loan-to-value" value={`${(loan.ltv_bps / 100).toFixed(1)}%`} /> : null}
      </dl>
    </Card>
  );
}

function LoanTerms({ loan }: { loan: MarketplaceLoanDetail }) {
  return (
    <Card padded>
      <dl className="kv">
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

function LoanDocuments() {
  return (
    <Card>
      {["Borrower presentation", "Borrower financial summary", "Loan claim assignment template", "Risk disclosure"].map((title, index) => (
        <div className="row spread" key={title} style={{ borderBottom: index < 3 ? "1px solid var(--line)" : 0, padding: "12px 16px" }}>
          <span className="row gap-8"><Icon className="muted" name="doc" size={16} />{title}</span>
          <Button icon="download" size="sm" variant="ghost">PDF</Button>
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
      <Card>
        <Empty icon="market" title={preview ? "No loan previews available" : "No loans available"}>
          {preview
            ? "There are no published loan previews right now. Check again later or register to receive marketplace updates."
            : "There are no loans in this view right now."}
        </Empty>
      </Card>
    );
  }

  return (
    <Card>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Borrower</th>
              <th>Purpose</th>
              <th className="num">Amount</th>
              <th className="num">Interest</th>
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
                <td><div className="col-strong">{loan.title}</div><div className="sub mono">{loan.loan_id}</div></td>
                <td>{loan.purpose}</td>
                <td className="num"><Money amountMinor={loan.principal_minor} currency={loan.currency} /></td>
                <td className="num col-strong">{formatRateBps(loan.interest_rate_bps)}</td>
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
    </Card>
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
        <Button disabled={frozen || isReadonlyImpersonationActive()} icon="plus" variant="primary" onClick={() => setModal("deposit")}>Deposit funds</Button>
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
      {modal === "iban" ? <IbanModal onClose={() => setModal(null)} /> : null}
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
    return <Card><Empty icon="balance" title="No balance lots">Incoming deposits, repayments, recoveries, FX proceeds, or sale proceeds will appear here.</Empty></Card>;
  }

  return (
    <Card>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>Lot</th><th>Source</th><th>Received</th><th className="num">Remaining</th><th>Age/deadline</th><th>Status</th></tr></thead>
          <tbody>
            {lots.map((lot) => {
              const penalty = frozen && lot.bucket === "overdue";
              return (
                <tr className={penalty ? "lot-penalty" : lot.bucket === "overdue" ? "lot-overdue" : ""} key={lot.id}>
                  <td className="mono col-strong">{lot.id}</td>
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
    </Card>
  );
}

function DepositModal({ currency, onClose }: { currency: string; onClose: () => void }) {
  const instructionsQuery = useDepositInstructionsData();
  const payload = instructionsQuery.data;
  if (instructionsQuery.isError && !payload) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={`Deposit ${currency}`}>
        <DataErrorCard title="Could not load deposit instructions" onRetry={() => void instructionsQuery.refetch()}>
          We could not load the live deposit instructions. Try again before sending funds.
        </DataErrorCard>
      </Modal>
    );
  }
  if (!payload) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={`Deposit ${currency}`}>
        <ScreenLoading title="Deposit instructions" />
      </Modal>
    );
  }
  const instruction = payload.instructions.find((item) => item.currency === currency);
  if (!instruction) {
    return (
      <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={`Deposit ${currency}`}>
        <Empty icon="info" title={`No ${currency} deposit account`}>
          Garanta has not enabled deposit instructions for this currency.
        </Empty>
      </Modal>
    );
  }
  return (
    <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={`Deposit ${currency}`}>
      <div className="col gap-16">
        <Banner tone={instruction.is_configured ? "warn" : "bad"} title={`Send ${currency} only to this ${currency} account`}>
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
                Scan this code only for {currency} deposits. If your bank app does not carry the
                BANXUM payment reference automatically, enter the reference below unchanged.
              </p>
            </div>
          </div>
        ) : null}
        <div>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Payment reference - required</div>
          <div className="codeblock"><span>{instruction.payment_reference}</span><Button icon="copy" size="sm" variant="ghost">Copy</Button></div>
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
            requestDisabled={codeRequest.isRequesting}
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

function IbanModal({ onClose }: { onClose: () => void }) {
  const profile = displayProfile();
  return (
    <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title="Payout bank accounts">
      <div className="col gap-16">
        <Banner tone="neutral" title="Verification required">New payout accounts are checked before first use. Changing payout details requires a fresh email confirmation code.</Banner>
        <Field label="IBAN"><input className="input mono" placeholder="CH.. / DE.." /></Field>
        <Field label="Account name"><input className="input" placeholder={profile.name} /></Field>
      </div>
    </Modal>
  );
}

function FxScreen({ demoState }: { demoState: DemoAccountState }) {
  const fxQuery = useFxData();
  const balancesQuery = useBalancesData();
  const fx = fxQuery.data;
  const balances = balancesQuery.data;
  const [from, setFrom] = useState<"CHF" | "EUR">("CHF");
  const [amount, setAmount] = useState("");
  const [quoteOpen, setQuoteOpen] = useState(false);
  const [liveQuote, setLiveQuote] = useState<FxQuote | null>(null);
  const [error, setError] = useState("");
  const quoteMutation = useV1FxQuotesCreate();
  const to = from === "CHF" ? "EUR" : "CHF";
  const rate = from === "CHF" ? 1.0432 : 0.9586;
  const parsedAmount = parseMoneyInputToMinorUnits(amount, from);
  const amountMinor = parsedAmount.amountMinor;
  const availableMinor = balances?.summaries.find((summary) => summary.currency === from)?.total_available_minor ?? 0;
  const feeMinor = Math.round(amountMinor * 0.015);
  const targetMinor = Math.round((amountMinor - feeMinor) * rate);
  const frozen = demoState === "frozen";
  const amountError =
    parsedAmount.error ?? (amountMinor > availableMinor ? `Exceeds available ${from} balance.` : undefined);
  const requestQuote = () => {
    setError("");
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
      <ScreenError title="Currency exchange" onRetry={() => void balancesQuery.refetch()}>
        We could not load your available balances, so FX is unavailable.
      </ScreenError>
    );
  }
  if (!balances) return <ScreenLoading title="Currency exchange" />;

  return (
    <main className="content narrow">
      <div className="page-head"><div><h1>Currency exchange</h1><div className="ph-sub">Auxiliary settlement function, not trading or speculation.</div></div></div>
      {frozen ? <Banner icon="lock" tone="bad" title="FX is frozen">Provide a usable payout IBAN to unlock currency exchange.</Banner> : null}
      {isReadonlyImpersonationActive() ? <Banner icon="lock" tone="info" title="Read-only view">FX quote and execution are disabled during superadmin read-only impersonation.</Banner> : null}
      <div className="grid grid-2 section">
        <Card padded>
          <div className="row spread" style={{ marginBottom: 14 }}><span className="eyebrow">Exchange</span><span className="muted">Fee 1.5%</span></div>
          <div className="col gap-10">
            <Field error={amountError} hint={`Available ${from}: ${formatMoneyMinor(availableMinor, from)}`} label="From">
              <div className="input-affix"><span className="prefix">{from}</span><input className="input mono" disabled={frozen || isReadonlyImpersonationActive()} inputMode="decimal" onChange={(event) => setAmount(event.target.value.replace(/[^0-9.]/g, ""))} placeholder="0.00" style={{ paddingLeft: 44 }} value={amount} /></div>
            </Field>
            <button aria-label="Swap direction" className="icon-btn" disabled={frozen || isReadonlyImpersonationActive()} onClick={() => { setFrom(to); setLiveQuote(null); }} type="button"><Icon name="swap" size={16} /></button>
            <Field label="To estimated">
              <div className="input-affix"><span className="prefix">{to}</span><input className="input mono" readOnly style={{ background: "var(--surface-2)", paddingLeft: 44 }} value={amountMinor > 0 && !parsedAmount.error ? formatMoneyMinor(targetMinor, to) : ""} /></div>
            </Field>
          </div>
          <Review rows={[{ label: "Indicative rate", value: `${from}/${to} ${rate.toFixed(4)}` }, { label: "Platform fee", value: `${from} ${formatMoneyMinor(feeMinor, from)}` }]} />
          {error ? <Banner tone="bad" title="Could not quote FX">{error}</Banner> : null}
          <Button block disabled={frozen || isReadonlyImpersonationActive() || amountMinor <= 0 || Boolean(amountError) || quoteMutation.isPending} style={{ marginTop: 14 }} variant="primary" onClick={requestQuote}>{quoteMutation.isPending ? "Quoting..." : "Review exchange"}</Button>
        </Card>
        <Card padded>
          <div className="eyebrow" style={{ marginBottom: 10 }}>How FX works here</div>
          <div className="col gap-8 muted-2" style={{ fontSize: 12.5 }}>
            <span><b>Instant internal settlement.</b> Target currency credits immediately after confirmed quote.</span>
            <span><b>No fresh ageing clock.</b> Converted funds inherit source-lot deadlines.</span>
            <span><b>1-minute quote lock.</b> Refresh after expiry.</span>
            <span><b>Daily limit.</b> CHF 100,000 equivalent per investor per day.</span>
          </div>
        </Card>
      </div>
      <section className="section">
        <div className="section-head"><h2>Exchange history</h2></div>
        {fxQuery.isError && !fx ? (
          <DataErrorCard title="Could not load exchange history" onRetry={() => void fxQuery.refetch()}>
            Your quote form is available, but historical FX activity could not be loaded.
          </DataErrorCard>
        ) : (
        <Card>
          <div className="tbl-wrap">
            <table className="tbl dense"><thead><tr><th>Reference</th><th>Date</th><th>Pair</th><th className="num">Debited</th><th className="num">Credited</th><th>Status</th></tr></thead>
              <tbody>{(fx?.exchanges ?? []).map((exchange) => <tr key={exchange.id}><td className="mono col-strong">{exchange.id}</td><td className="mono muted">{formatDate(exchange.executed_at)}</td><td>{exchange.source_currency}/{exchange.target_currency}</td><td className="num">{exchange.source_currency} {formatMoneyMinor(exchange.source_amount_minor, exchange.source_currency)}</td><td className="num">{exchange.target_currency} {formatMoneyMinor(exchange.target_amount_minor, exchange.target_currency)}</td><td><Chip status={exchange.status} /></td></tr>)}</tbody>
            </table>
          </div>
        </Card>
        )}
      </section>
      {quoteOpen ? <FxConfirmModal from={from} to={to} sourceMinor={liveQuote?.source_amount_minor ?? amountMinor} feeMinor={liveQuote?.fee_minor ?? feeMinor} targetMinor={liveQuote?.target_amount_minor ?? targetMinor} rate={Number(liveQuote?.rate ?? rate)} quote={liveQuote} onClose={() => setQuoteOpen(false)} /> : null}
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
          { label: `Rate ${from}/${to}`, value: rate.toFixed(4) },
          { label: "Platform fee", value: `${from} ${formatMoneyMinor(feeMinor, from)}` },
          { label: "You receive", value: `${to} ${formatMoneyMinor(targetMinor, to, 4)}`, total: true }
        ]} />
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={codeRequest.isRequesting}
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
  const [tab, setTab] = useState<"holdings" | "exposure" | "activity" | "orders">("holdings");
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

  return (
    <main className="content">
      <div className="page-head"><div><h1>Portfolio</h1><div className="ph-sub">Your loan claim holdings, exposure and transaction history.</div></div></div>
      <div className="grid-stat" style={{ marginBottom: 20 }}>
        <Stat amountMinor={sumAmounts(portfolio.summary.original_principal_by_currency)} currency="CHF" label="Invested principal" sub="lifetime" />
        <Stat amountMinor={sumAmounts(portfolio.summary.outstanding_principal_by_currency)} currency="CHF" label="Outstanding principal" sub={`${portfolio.summary.active_holding_count} active holdings`} />
        <Stat amountMinor={sumAmounts(portfolio.summary.realized_interest_by_currency)} currency="CHF" label="Interest received" sub="lifetime" />
        <Stat label="Weighted yield" raw="7.6%" sub="projection" />
      </div>
      {openOrders.length > 0 ? <PendingOrdersNotice orders={openOrders} onViewOrders={() => setTab("orders")} /> : null}
      <Tabs tabs={[{ value: "holdings", label: "Holdings" }, { value: "exposure", label: "Exposure" }, { value: "activity", label: "Activity" }, { value: "orders", label: "Orders" }]} value={tab} onChange={setTab} />
      <div style={{ paddingTop: 18 }}>
        {tab === "holdings" ? <HoldingsTable holdings={portfolio.holdings} pendingOrders={openOrders} onOpen={setDetail} onViewOrders={() => setTab("orders")} /> : null}
        {tab === "exposure" ? <ExposurePanel pendingOrders={openOrders} portfolio={portfolio} onViewOrders={() => setTab("orders")} /> : null}
        {tab === "activity" ? <ActivityTable entries={activity.entries} /> : null}
        {tab === "orders" ? <OrdersTable orders={orders.orders} /> : null}
      </div>
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

function PendingOrdersNotice({ orders, onViewOrders }: { orders: PrimaryOrderPortal[]; onViewOrders: () => void }) {
  const allocatedCount = orders.filter((order) => order.allocated_amount_minor > 0).length;
  const totals = primaryOrderTotalsByCurrency(orders);
  return (
    <div style={{ marginBottom: 16 }}>
      <Banner
        actions={<Button size="sm" onClick={onViewOrders}>View orders</Button>}
        tone="info"
        title="Primary orders awaiting funding close"
      >
        {allocatedCount > 0
          ? "Allocated order balances are reserved for published loans. They become portfolio holdings only after Garanta closes the loan funding round."
          : "Your primary orders are still waiting for balance allocation. They are not portfolio holdings yet."}{" "}
        {totals.map(([currency, amount]) => `${currency} ${formatMoneyMinor(amount, currency)}`).join(" / ")} is currently open in primary orders.
      </Banner>
    </div>
  );
}

function PendingOrdersEmptyState({ orders, onViewOrders }: { orders: PrimaryOrderPortal[]; onViewOrders: () => void }) {
  return (
    <Card padded>
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
    </Card>
  );
}

function HoldingsTable({
  holdings,
  pendingOrders,
  onOpen,
  onViewOrders
}: {
  holdings: Holding[];
  pendingOrders: PrimaryOrderPortal[];
  onOpen: (holding: Holding) => void;
  onViewOrders: () => void;
}) {
  if (holdings.length === 0) {
    if (pendingOrders.length > 0) {
      return <PendingOrdersEmptyState orders={pendingOrders} onViewOrders={onViewOrders} />;
    }
    return <Card><Empty icon="portfolio" title="No holdings yet">Funded loan claims and settled secondary-market purchases will appear here.</Empty></Card>;
  }

  return (
    <Card>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>Borrower</th><th>Status</th><th className="num">Invested</th><th className="num">Outstanding</th><th className="num">Interest received</th><th className="num">Rate</th><th className="num">DPD</th><th /></tr></thead>
          <tbody>
            {holdings.map((holding) => (
              <tr className="clickable" key={holding.id} onClick={() => onOpen(holding)}>
                <td><div className="col-strong">{holding.loan.borrower_name}</div><div className="sub mono">{holding.loan.loan_id}</div></td>
                <td><Chip status={holding.loan.loan_status} tone={statusTone(holding.loan.loan_status)} /></td>
                <td className="num"><Money amountMinor={holding.original_principal_minor} currency={holding.currency} /></td>
                <td className="num col-strong">{formatMoneyMinor(holding.current_principal_minor, holding.currency)}</td>
                <td className="num pos">+{formatMoneyMinor(holding.received_interest_minor, holding.currency)}</td>
                <td className="num">{formatRateBps(holding.loan.interest_rate_bps)}</td>
                <td className="num">{holding.loan.days_past_due > 0 ? <span className="neg col-strong">{holding.loan.days_past_due}</span> : <span className="muted">0</span>}</td>
                <td className="right"><Icon className="faint" name="chevR" size={15} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function hasExposure(portfolio: NonNullable<ReturnType<typeof usePortfolioData>["data"]>) {
  return (
    portfolio.exposure.by_loan_status.length > 0 ||
    portfolio.exposure.by_risk_rating.length > 0 ||
    portfolio.exposure.by_borrower.length > 0 ||
    portfolio.exposure.by_country.length > 0 ||
    portfolio.exposure.by_purpose.length > 0 ||
    portfolio.exposure.by_collateral_type.length > 0 ||
    portfolio.exposure.by_maturity.length > 0
  );
}

function ExposurePanel({
  portfolio,
  pendingOrders,
  onViewOrders
}: {
  portfolio: ReturnType<typeof usePortfolioData>["data"];
  pendingOrders: PrimaryOrderPortal[];
  onViewOrders: () => void;
}) {
  if (!portfolio) return null;
  if (!hasExposure(portfolio)) {
    return (
      <Card padded>
        <div className="col gap-12">
          <Empty icon="trend" title="No funded exposure yet">
            Exposure is calculated only from active loan holdings. Allocated primary orders are shown separately until funding closes.
          </Empty>
          {pendingOrders.length > 0 ? (
            <>
              <div className="grid grid-2">
                {primaryOrderTotalsByCurrency(pendingOrders).map(([currency, amount]) => (
                  <div className="stat" key={currency}>
                    <div className="stat-label">Allocated / pending orders</div>
                    <div className="stat-value"><span className="ccy">{currency}</span>{formatMoneyMinor(amount, currency)}</div>
                    <div className="stat-sub">Not yet exposure</div>
                  </div>
                ))}
              </div>
              <div><Button size="sm" onClick={onViewOrders}>View order pipeline</Button></div>
            </>
          ) : null}
        </div>
      </Card>
    );
  }
  const statusData = portfolio.exposure.by_loan_status.map((bucket) => ({ label: bucket.name, value: bucket.outstanding_principal_minor }));
  const ratingData = portfolio.exposure.by_risk_rating.map((bucket) => ({ label: bucket.name, value: bucket.outstanding_principal_minor }));
  return (
    <div className="col gap-16">
      <Banner tone="neutral" title="Exposure is informational">{platformName} shows concentration metrics but does not enforce hard concentration limits at launch.</Banner>
      <div className="grid grid-2">
        <Card padded><div className="eyebrow" style={{ marginBottom: 14 }}>By status</div><BarBreakdown data={statusData} /></Card>
        <Card padded><div className="eyebrow" style={{ marginBottom: 14 }}>By risk rating</div><BarBreakdown data={ratingData} /></Card>
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
  if (entries.length === 0) {
    return <Card><Empty icon="clock" title="No activity yet">Deposits, investments, repayments, FX, and secondary-market activity will appear here.</Empty></Card>;
  }

  return (
    <Card>
      <div className="tbl-wrap">
        <table className={`tbl ${dense ? "dense" : ""}`}>
          <thead><tr><th>Date</th><th>Activity</th><th>Reference</th><th>Type</th><th className="num">Amount</th></tr></thead>
          <tbody>
            {entries.map((entry) => {
              const category = activityCategory(entry);
              return (
                <tr key={entry.id}>
                  <td className="mono muted" style={{ fontSize: 12 }}>{formatDateTime(entry.occurred_at)}</td>
                  <td className="col-strong">{entry.title}</td>
                  <td className="sub mono">{entry.loan_title || entry.activity_type}</td>
                  <td><ActivityTag category={category} /></td>
                  <td className="num"><ActivityAmount entry={entry} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ActivityTag({ category }: { category: string }) {
  const tone = category === "income" || category === "deposit" || category === "sale" || category === "recovery" ? "ok" : category === "cost" || category === "withdrawal" || category === "purchase" ? "bad" : category === "status" || category === "order" || category === "listing" ? "warn" : "neutral";
  return <Chip dot={false} tone={tone}>{category}</Chip>;
}

function OrdersTable({ orders }: { orders: PrimaryOrderPortal[] }) {
  return (
    <div>
      <Banner tone="neutral" title="Orders are intents">Pending orders do not reserve loan capacity until funds are allocated and validated, first-come first-served.</Banner>
      {orders.length === 0 ? (
        <Card className="section"><Empty icon="market" title="No primary orders">Investment intents will appear here after you place an order.</Empty></Card>
      ) : (
      <Card className="section">
        <div className="tbl-wrap">
          <table className="tbl">
            <thead><tr><th>Order</th><th>Loan</th><th className="num">Requested</th><th className="num">Allocated</th><th>Placed</th><th>Status</th></tr></thead>
            <tbody>{orders.map((order) => <tr key={order.id}><td className="mono col-strong">{order.id}</td><td><div className="col-strong">{order.loan_title}</div><div className="sub mono">{order.loan_id}</div></td><td className="num"><Money amountMinor={order.requested_amount_minor} currency={order.currency} /></td><td className="num">{order.allocated_amount_minor > 0 ? <Money amountMinor={order.allocated_amount_minor} currency={order.currency} /> : <span className="muted">-</span>}</td><td className="mono muted">{formatDateTime(order.created_at)}</td><td><Chip status={order.status} /></td></tr>)}</tbody>
          </table>
        </div>
      </Card>
      )}
    </div>
  );
}

function HoldingDetail({ holding, onClose, setRoute }: { holding: Holding; onClose: () => void; setRoute: (route: AppRoute) => void }) {
  const impaired = ["late", "defaulted"].includes(holding.loan.loan_status);
  return (
    <Modal drawer footer={<><Button variant="ghost" onClick={onClose}>Close</Button><Button disabled={holding.loan.loan_status !== "funded"} icon="secondary" variant="primary" onClick={() => { onClose(); goTo(setRoute, "secondary"); }}>List on secondary market</Button></>} onClose={onClose} title={holding.loan.borrower_name}>
      <div className="col gap-16">
        <div className="row gap-8 wrap"><Chip status={holding.loan.loan_status} tone={statusTone(holding.loan.loan_status)} /><Rating value={holding.loan.risk_rating} /><Country code={holding.loan.borrower_country} /><span className="tag">{holding.loan.loan_id}</span></div>
        {impaired ? <Banner tone="warn" title={`${holding.loan.loan_status.replaceAll("_", " ")} - ${holding.loan.days_past_due} DPD`}>This position is not a normal live loan. Review public notes and recovery updates before taking action.</Banner> : null}
        <div className="grid grid-2">
          <Card padded><Stat amountMinor={holding.original_principal_minor} currency={holding.currency} label="Invested" /></Card>
          <Card padded><Stat amountMinor={holding.current_principal_minor} currency={holding.currency} label="Outstanding" /></Card>
          <Card padded><Stat amountMinor={holding.received_interest_minor} currency={holding.currency} label="Interest received" /></Card>
          <Card padded><Stat label="Rate / term" raw={`${formatRateBps(holding.loan.interest_rate_bps)} / ${holding.loan.term_months}mo`} /></Card>
        </div>
        {holding.latest_public_note ? <Card padded><div className="eyebrow" style={{ marginBottom: 6 }}>Public note from Garanta</div><p className="muted-2">{holding.latest_public_note.title}</p><div className="sub">{formatDate(holding.latest_public_note.occurred_at)}</div></Card> : null}
        {holding.loan.loan_status === "defaulted" ? <RecoverySplitView /> : null}
      </div>
    </Modal>
  );
}

function RecoverySplitView() {
  if (!isFixturePreview) {
    return (
      <Card padded>
        <Empty icon="info" title="Recovery split API pending">
          Recovery distribution detail will come from the servicing report endpoints.
        </Empty>
      </Card>
    );
  }

  return (
    <div>
      <div className="eyebrow" style={{ marginBottom: 8 }}>Recovery distribution</div>
      <Review rows={[
        ...portalFixture.recoverySplit.parts.map((part) => ({ label: part.label, value: `${portalFixture.recoverySplit.currency} ${formatMoneyMinor(part.amountMinor, portalFixture.recoverySplit.currency)}`, tone: part.amountMinor < 0 ? "bad" as const : undefined })),
        { label: "Credited to you", value: `${portalFixture.recoverySplit.currency} ${formatMoneyMinor(portalFixture.recoverySplit.totalMinor, portalFixture.recoverySplit.currency)}`, total: true }
      ]} />
    </div>
  );
}

function SecondaryMarketScreen({ demoState }: { demoState: DemoAccountState }) {
  const listingsQuery = useSecondaryListingsData();
  const activityQuery = useSecondaryActivityData();
  const portfolioQuery = usePortfolioData(true);
  const listings = listingsQuery.data ?? [];
  const activity = activityQuery.data;
  const portfolio = portfolioQuery.data;
  const [tab, setTab] = useState<"browse" | "sell" | "mine">("browse");
  const [buy, setBuy] = useState<SecondaryMarketBuyerListing | null>(null);
  const [sell, setSell] = useState<Holding | null>(null);
  const frozen = demoState === "frozen";
  const sellable = portfolio?.holdings.filter((holding) => holding.current_principal_minor > 0) ?? [];

  return (
    <main className="content">
      <div className="page-head"><div><h1>Secondary market</h1><div className="ph-sub">Bulletin-board transfer of whole loan claim holdings. Counterparties are anonymous.</div></div></div>
      {frozen ? <Banner icon="lock" tone="bad" title="Secondary-market actions are frozen">Provide a usable payout IBAN to unlock buying and listing.</Banner> : null}
      <Banner tone="neutral" title="How it works">Sellers list an entire holding at a discount or premium. Accrued interest to settlement belongs to the seller; future interest belongs to the buyer.</Banner>
      <div style={{ marginTop: 16 }}><Tabs tabs={[{ value: "browse", label: "Browse listings" }, { value: "sell", label: "Sell a holding" }, { value: "mine", label: "My listings" }]} value={tab} onChange={setTab} /></div>
      <div style={{ paddingTop: 18 }}>
        {tab === "browse" ? (
          listingsQuery.isError && listings.length === 0 ? (
            <DataErrorCard title="Could not load secondary listings" onRetry={() => void listingsQuery.refetch()}>
              Secondary-market listings are temporarily unavailable.
            </DataErrorCard>
          ) : (
            <BuyerListingsTable frozen={frozen} listings={listings} onBuy={setBuy} />
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
            <SellableHoldingsTable frozen={frozen} holdings={sellable} onSell={setSell} />
          )
        ) : null}
        {tab === "mine" ? (
          activityQuery.isError && !activity ? (
            <DataErrorCard title="Could not load your listings" onRetry={() => void activityQuery.refetch()}>
              Your seller-side secondary-market activity could not be loaded.
            </DataErrorCard>
          ) : (
            <MyListingsTable listings={activity?.listings ?? []} />
          )
        ) : null}
      </div>
      {buy ? <BuyListingModal listing={buy} onClose={() => setBuy(null)} /> : null}
      {sell ? <ListHoldingModal holding={sell} onClose={() => setSell(null)} /> : null}
    </main>
  );
}

function BuyerListingsTable({ listings, onBuy, frozen }: { listings: SecondaryMarketBuyerListing[]; onBuy: (listing: SecondaryMarketBuyerListing) => void; frozen: boolean }) {
  if (listings.length === 0) {
    return <Card><Empty icon="secondary" title="No active secondary listings">There are no buyer-visible holdings listed right now.</Empty></Card>;
  }

  return (
    <Card>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>Listing</th><th>Status</th><th className="num">Principal</th><th className="num">Price</th><th className="num">Accrued</th><th className="num">Total cost</th><th className="num">DPD</th><th /></tr></thead>
          <tbody>
            {listings.map((listing) => (
              <tr className="clickable" key={listing.id} onClick={() => !frozen && !isReadonlyImpersonationActive() && onBuy(listing)}>
                <td><div className="col-strong">{listing.loan_title}</div><div className="sub mono">{listing.id}</div></td>
                <td><div className="row gap-6 wrap"><Chip status={listing.loan_status_at_listing} tone={statusTone(listing.loan_status_at_listing)} />{listing.risk_acknowledgement_required ? <Chip square tone="warn">Non-standard</Chip> : null}</div></td>
                <td className="num"><Money amountMinor={listing.current_principal_minor} currency={listing.currency} /></td>
                <td className="num">{priceLabel(listing.discount_premium_bps)}</td>
                <td className="num">{formatMoneyMinor(listing.accrued_interest_minor, listing.currency)}</td>
                <td className="num col-strong"><Money amountMinor={listing.buyer_total_cost_minor} currency={listing.currency} /></td>
                <td className="num">{listing.days_past_due > 0 ? <span className="neg col-strong">{listing.days_past_due}</span> : "0"}</td>
                <td className="right"><Icon className="faint" name="chevR" size={15} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ fontSize: 11.5, margin: "12px 16px 16px" }}>Buyer views never expose seller identity, seller net proceeds, maker fee, document evidence IDs, or admin fields.</p>
    </Card>
  );
}

function SellableHoldingsTable({ holdings, onSell, frozen }: { holdings: Holding[]; onSell: (holding: Holding) => void; frozen: boolean }) {
  if (holdings.length === 0) {
    return <Card><Empty icon="portfolio" title="No sellable holdings">Active holdings that can be listed will appear here.</Empty></Card>;
  }

  return (
    <Card>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>Holding</th><th>Status</th><th className="num">Current principal</th><th className="num">Rate</th><th /></tr></thead>
          <tbody>{holdings.map((holding) => <tr key={holding.id}><td><div className="col-strong">{holding.loan.borrower_name}</div><div className="sub mono">{holding.loan.loan_id}</div></td><td><Chip status={holding.loan.loan_status} tone={statusTone(holding.loan.loan_status)} /></td><td className="num"><Money amountMinor={holding.current_principal_minor} currency={holding.currency} /></td><td className="num">{formatRateBps(holding.loan.interest_rate_bps)}</td><td className="right"><Button disabled={frozen || isReadonlyImpersonationActive()} size="sm" onClick={() => onSell(holding)}>{holding.loan.loan_status === "funded" ? "List" : "Request listing"}</Button></td></tr>)}</tbody>
        </table>
      </div>
    </Card>
  );
}

function MyListingsTable({ listings }: { listings: SecondaryListingPortal[] }) {
  if (listings.length === 0) {
    return <Card><Empty icon="secondary" title="No listings yet">Your seller-side secondary-market listings will appear here.</Empty></Card>;
  }

  return (
    <Card>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>Listing</th><th className="num">Principal</th><th className="num">Seller net</th><th>State</th></tr></thead>
          <tbody>{listings.map((listing) => <tr key={listing.id}><td><div className="col-strong">{listing.loan_title}</div><div className="sub mono">{listing.id}</div></td><td className="num"><Money amountMinor={listing.current_principal_minor} currency={listing.currency} /></td><td className="num"><Money amountMinor={listing.seller_net_proceeds_minor} currency={listing.currency} /></td><td><Chip status={listing.status} /></td></tr>)}</tbody>
        </table>
      </div>
    </Card>
  );
}

function BuyListingModal({ listing, onClose }: { listing: SecondaryMarketBuyerListing; onClose: () => void }) {
  const queryClient = useQueryClient();
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
  useAutoRequestEmailCode(codeRequest, !done);
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
  return (
    <Modal wide footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ack || (needsExtra && !extraAck) || code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || acceptanceMutation.isPending || purchaseMutation.isPending} variant="primary" onClick={submitPurchase}>{acceptanceMutation.isPending || purchaseMutation.isPending ? "Submitting..." : "Confirm purchase"}</Button></>} onClose={onClose} title={`Buy listing ${listing.id}`}>
      <div className="col gap-16">
        {needsExtra ? <Banner tone="bad" title="Non-standard listing - elevated risk">This listing is non-performing or otherwise non-standard. You may receive less than the principal shown, or nothing.</Banner> : null}
        <Review rows={[
          { label: "Current principal", value: `${listing.currency} ${formatMoneyMinor(listing.current_principal_minor, listing.currency)}` },
          { label: "Sale price", value: priceLabel(listing.discount_premium_bps) },
          { label: "Accrued interest to seller", value: `${listing.currency} ${formatMoneyMinor(listing.accrued_interest_minor, listing.currency)}` },
          { label: "Taker fee", value: `${listing.currency} ${formatMoneyMinor(listing.taker_fee_minor, listing.currency)}` },
          { label: "Total cost", value: `${listing.currency} ${formatMoneyMinor(listing.buyer_total_cost_minor, listing.currency)}`, total: true }
        ]} />
        <Check checked={ack} id="sm-buy-ack" onChange={setAck}>I accept the secondary-market buyer terms and reassignment document.</Check>
        {needsExtra ? <Check checked={extraAck} id="sm-extra-ack" onChange={setExtraAck}>I acknowledge this is a non-standard claim with heightened risk of partial or total loss.</Check> : null}
        {!isFixturePreview && termsQuery.data ? <p className="muted" style={{ fontSize: 11.5 }}>Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={codeRequest.isRequesting}
          requestLabel={emailCodeRequestLabel(codeRequest)}
          value={code}
          onChange={setCode}
          onRequest={codeRequest.requestCode}
        />
        {codeRequest.error || error ? <Banner tone="bad" title="Could not purchase listing">{codeRequest.error || error}</Banner> : null}
      </div>
    </Modal>
  );
}

function ListHoldingModal({ holding, onClose }: { holding: Holding; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [priceBps, setPriceBps] = useState("10000");
  const [ack, setAck] = useState(false);
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [acceptanceId, setAcceptanceId] = useState<string | null>(null);
  const [acceptanceKey] = useState(() => idempotencyKey("secondary-listing-acceptance"));
  const [listingKey] = useState(() => idempotencyKey("secondary-listing"));
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const listingMutation = useV1MarketplaceSecondaryListingsCreate();
  const codeRequest = useSensitiveActionCode(ActionEnum.secondary_market_listing);
  useAutoRequestEmailCode(codeRequest, !done);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.secondary_market_listing },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const price = Math.max(1, Number(priceBps || 0));
  const transferPrice = Math.round((holding.current_principal_minor * price) / 10000);
  const makerFee = Math.round(transferPrice * 0.0025);
  const nonStandard = holding.loan.loan_status !== "funded";
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
                price_bps: price,
                current_principal_minor: holding.current_principal_minor,
                currency: holding.currency
              },
              idempotency_key: acceptanceKey
            }
          });
      setAcceptanceId(acceptance.id);
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
      void queryClient.invalidateQueries();
      setDone(true);
    } catch (mutationError) {
      setError(apiErrorMessage(mutationError));
    }
  };
  if (done) {
    return <Modal footer={<Button variant="primary" onClick={onClose}>Done</Button>} onClose={onClose} title={nonStandard ? "Submitted for approval" : "Listing published"}><SuccessState title={nonStandard ? "Submitted for approval" : "Listing published"}>{nonStandard ? "Garanta will review the listing disclosure before it becomes visible." : "Your holding is visible to buyers anonymously."}</SuccessState></Modal>;
  }
  return (
    <Modal footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!ack || code.length < 6 || (!isFixturePreview && !codeRequest.codeId) || acceptanceMutation.isPending || listingMutation.isPending} variant="primary" onClick={submitListing}>{acceptanceMutation.isPending || listingMutation.isPending ? "Submitting..." : nonStandard ? "Submit for approval" : "Publish listing"}</Button></>} onClose={onClose} title={`List ${holding.loan.loan_id}`}>
      <div className="col gap-16">
        {nonStandard ? <Banner tone="warn" title="Requires Garanta approval">Non-performing holdings require approval and status disclosure before buyers can see them.</Banner> : null}
        <Field hint="10000 = at par, 9800 = 2% discount, 10100 = 1% premium." label="Sale price bps">
          <input className="input mono" inputMode="numeric" onChange={(event) => setPriceBps(event.target.value.replace(/\D/g, ""))} value={priceBps} />
        </Field>
        <Review rows={[
          { label: "Current principal", value: `${holding.currency} ${formatMoneyMinor(holding.current_principal_minor, holding.currency)}` },
          { label: "Transfer price", value: `${holding.currency} ${formatMoneyMinor(transferPrice, holding.currency)}` },
          { label: "Maker fee", value: `${holding.currency} ${formatMoneyMinor(makerFee, holding.currency)}` },
          { label: "Seller net proceeds", value: `${holding.currency} ${formatMoneyMinor(transferPrice - makerFee, holding.currency)}`, total: true }
        ]} />
        <Check checked={ack} id="sm-list-ack" onChange={setAck}>I accept the seller/listing terms and confirm I am listing this entire holding.</Check>
        {!isFixturePreview && termsQuery.data ? <p className="muted" style={{ fontSize: 11.5 }}>Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
        <CodeRequestField
          hint={previewHint("Demo: any 6 digits")}
          label="Email confirmation code"
          requestDisabled={codeRequest.isRequesting}
          requestLabel={emailCodeRequestLabel(codeRequest)}
          value={code}
          onChange={setCode}
          onRequest={codeRequest.requestCode}
        />
        {codeRequest.error || error ? <Banner tone="bad" title="Could not list holding">{codeRequest.error || error}</Banner> : null}
      </div>
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
      <div className="page-head"><div><h1>Documents</h1><div className="ph-sub">Accepted terms, transaction evidence, statements and tax information. Self-scoped to your account.</div></div></div>
      <Banner tone="neutral" title="Informational only">{documents.disclaimer}</Banner>
      {error ? <div style={{ marginTop: 12 }}><Banner tone="bad" title="Download failed">{error}</Banner></div> : null}
      <div className="toolbar" style={{ marginTop: 16 }}>
        {types.map((item) => <button className={`fchip ${type === item ? "on" : ""}`} key={item} onClick={() => setType(item)} type="button">{item}</button>)}
        <span className="results-count">{rows.length} documents</span>
      </div>
      <Card>
        <div className="tbl-wrap">
          <table className="tbl"><thead><tr><th>Document</th><th>Type</th><th>Version</th><th>Context</th><th>Date</th><th className="num">Size</th><th /></tr></thead>
            <tbody>{rows.map((document) => (
              <tr key={document.id}>
                <td className="row gap-8"><Icon className="muted" name="doc" size={16} /><span className="col-strong">{document.title}</span></td>
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
      </Card>
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

function SettingsScreen({ setRoute }: { setRoute: (route: AppRoute) => void }) {
  const [marketing, setMarketing] = useState(false);
  const [showPayoutModal, setShowPayoutModal] = useState(false);
  const profile = displayProfile();
  const balances = useBalancesData();
  const payoutInstructions = balances.data?.payout_instructions ?? [];
  return (
    <main className="content narrow">
      <div className="page-head"><div><h1>Settings</h1><div className="ph-sub">Profile, verification, payout accounts and preferences.</div></div></div>
      <div className="col gap-16">
        <Card><div className="card-head"><h3>Profile</h3></div><div className="card-pad"><dl className="kv"><KeyValueRow label="Name" value={profile.name} /><KeyValueRow label="Email" mono value={profile.email} /><KeyValueRow label="Country" value={profile.country} />{profile.memberSince ? <KeyValueRow label="Member since" mono value={formatDate(profile.memberSince)} /> : null}</dl><p className="muted" style={{ fontSize: 11.5, marginTop: 12 }}>Name or email changes are handled through support after identity re-verification.</p></div></Card>
        <Card><div className="card-head"><h3>Verification</h3></div><div className="card-pad col gap-12"><div className="row spread"><span className="row gap-8"><Icon className="muted" name="shield" size={16} />Identity (KYC/AML)</span><Chip status={isFixturePreview ? "approved" : "backend required"} tone={isFixturePreview ? "ok" : "neutral"} /></div><div className="hr" /><div className="row spread"><span className="row gap-8"><Icon className="muted" name="phone" size={16} />Phone {profile.phone || "backend required"}</span><Chip status={isFixturePreview ? "verified" : "backend required"} tone={isFixturePreview ? "ok" : "neutral"} /></div></div></Card>
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
        <Card><div className="card-head"><h3>Communication</h3></div><div className="card-pad"><label className="row spread" style={{ cursor: "pointer" }}><span><div className="col-strong">Product updates and newsletter</div><div className="muted" style={{ fontSize: 12 }}>Transactional emails are mandatory.</div></span><input checked={marketing} onChange={(event) => setMarketing(event.target.checked)} type="checkbox" /></label></div></Card>
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
        <Banner tone="warn" title="Changing payout details">A newly submitted IBAN replaces the previous active payout instruction and remains pending until Garanta verifies it. The 60-day balance deadline is not extended.</Banner>
        <Field label="Currency">
          <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
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
          requestDisabled={codeRequest.isRequesting}
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

function FaqScreen() {
  const [open, setOpen] = useState(0);
  const faqs = [
    ["Are platform balances like a bank account?", "No. Balances are non-interest-bearing operational funds, not bank deposits, and are subject to regulatory ageing limits."],
    ["What happens at the 60-day deadline?", "If a usable payout IBAN is on file, Garanta may initiate forced withdrawal. If not, money-moving actions freeze until one is provided. The 60-day limit cannot be extended."],
    ["Does converting currency reset the clock?", "No. FX is a settlement function. Converted funds inherit source-lot deadlines."],
    ["Is an investment order guaranteed to be filled?", "No. Orders are intents and are filled first-come, first-served only when funds are allocated and validated."],
    ["Can I sell before maturity?", "You can list an entire holding on the secondary market. Liquidity is not guaranteed and non-performing listings require approval and extra acknowledgement."]
  ];
  return (
    <main className="content narrow">
      <div className="page-head"><div><h1>Help & FAQ</h1><div className="ph-sub">Plain-English answers on balances, orders, risk, FX and secondary market.</div></div></div>
      <Card>
        {faqs.map(([question, answer], index) => (
          <div key={question} style={{ borderBottom: index < faqs.length - 1 ? "1px solid var(--line)" : 0 }}>
            <button className="row spread" onClick={() => setOpen(open === index ? -1 : index)} style={{ background: "none", border: 0, cursor: "pointer", padding: "15px 18px", textAlign: "left", width: "100%" }} type="button">
              <span className="col-strong">{question}</span><Icon className="muted" name={open === index ? "chevD" : "chevR"} size={16} />
            </button>
            {open === index ? <div style={{ padding: "0 18px 16px" }}><p className="muted-2" style={{ fontSize: 13, lineHeight: 1.6 }}>{answer}</p></div> : null}
          </div>
        ))}
      </Card>
      <Banner tone="warn" title="Risk warning">Investing through {platformName} involves risk of loss, borrower default, illiquidity and no guaranteed return.</Banner>
    </main>
  );
}

function InvestModal({ loan, onClose }: { loan: MarketplaceLoanDetail; onClose: () => void }) {
  const queryClient = useQueryClient();
  const balances = useBalancesData().data;
  const investableLots = currentInvestableLotsForLoanCurrency(balances?.lots, loan);
  const investableBalanceMinor = sumLotAvailableMinor(investableLots);
  const maxInvest = Math.min(investableBalanceMinor, loan.remaining_capacity_minor);
  const [amount, setAmount] = useState("");
  const [step, setStep] = useState<"amount" | "review" | "confirm" | "done">("amount");
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
    (amountMinor > 0 && amountMinor < 100000
      ? "Minimum order is 1,000."
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
        : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={amountMinor < 100000 || Boolean(amountError)} variant="primary" onClick={() => setStep("review")}>Review order</Button></>;

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
          <Field error={amountError} hint={`Between ${loan.currency} 1,000 and ${formatMoneyMinor(maxInvest, loan.currency)}`} label="Investment amount">
            <div className="input-affix"><span className="prefix">{loan.currency}</span><input className="input mono" inputMode="decimal" onChange={(event) => setAmount(event.target.value.replace(/[^0-9.]/g, ""))} placeholder="0.00" style={{ paddingLeft: 44 }} value={amount} /></div>
          </Field>
          <Banner tone="neutral" title="Allocation">Orders are intents only. They become effective after funds are allocated and validated, first-come first-served.</Banner>
        </div>
      ) : step === "review" ? (
        <div className="col gap-16">
          <Review rows={[{ label: "Loan", value: `${loan.loan_id} - ${loan.title}` }, { label: "Order amount", value: `${loan.currency} ${formatMoneyMinor(amountMinor, loan.currency)}` }, { label: "Target interest", value: `${formatRateBps(loan.interest_rate_bps)} p.a.` }, { label: "Platform fee", value: "None" }]} />
          <div className="legal"><h5>Generic P2P lending risk acknowledgement</h5><p>{riskText}</p></div>
          <Check checked={ack1} id="invest-ack-1" onChange={setAck1}>I accept the primary-market investment terms and loan claim assignment.</Check>
          <Check checked={ack2} id="invest-ack-2" onChange={setAck2}>I acknowledge the risk disclosure and possible capital loss.</Check>
        </div>
      ) : step === "confirm" ? (
        <div className="col gap-16">
          <Banner icon="lock" tone="info" title="Confirm a sensitive action">Enter the 6-digit email confirmation code.</Banner>
          {!isFixturePreview && termsQuery.isError ? <Banner tone="bad" title="Investment terms unavailable">The current server-published investment terms could not be loaded.</Banner> : null}
          {!isFixturePreview && termsQuery.data ? <p className="muted" style={{ fontSize: 11.5 }}>Accepting {termsQuery.data.title} v{termsQuery.data.version_number}.</p> : null}
          <CodeRequestField
            hint={previewHint("Demo: any 6 digits")}
            label="Email confirmation code"
            requestDisabled={codeRequest.isRequesting}
            requestLabel={emailCodeRequestLabel(codeRequest)}
            value={code}
            onChange={setCode}
            onRequest={codeRequest.requestCode}
          />
          {codeRequest.expiresAt ? <p className="muted" style={{ fontSize: 11.5 }}>Code expires {formatDateTime(codeRequest.expiresAt)}.</p> : null}
          {codeRequest.error || error ? <Banner tone="bad" title="Could not place order">{codeRequest.error || error}</Banner> : null}
        </div>
      ) : (
        <SuccessState title="Order placed">Your order is pending allocation. Documents will be emailed and added to Documents when generated.</SuccessState>
      )}
    </Modal>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return <div className="row spread" style={{ fontSize: 13, gap: 12, marginBottom: 8 }}><span className="muted">{label}</span><span className="mono col-strong right">{value}</span></div>;
}

function KeyValueRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
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

function sumAmounts(amounts: Array<{ amount_minor: number }>) {
  return amounts.reduce((sum, item) => sum + item.amount_minor, 0);
}
