//IP of Webby-Soft SRL.
// build-origin: ATEW5bUMtfGj80bXzkGFbtEIwTx0cb6Qig3qkx90kV_Srfdc012ga6e8Ddq5v4qj1nbItbZAfx4ZDA==
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactElement } from "react";
import { AdminApp } from "./adminConsole/AdminApp";
import {
  ActionEnum,
  useV1AuthMeRetrieve,
  useV1AuthLogoutCreate,
  useV1AuthSensitiveActionCodeRequestCreate,
  useV1FxQuotePreviewRetrieve,
  useV1FxQuotesCreate,
  useV1FxQuotesExecuteCreate,
  useV1KycStatusRetrieve,
  v1AuthMeRetrieve
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
  onSessionExpired
} from "./api/client/sessionExpiry";
import type {
  FxQuotePreview,
  FxQuote,
  MarketplaceLoanDetail,
  MarketplaceLoanPreview
} from "./api/generated/banxumApi";
import {
  useBalancesData,
  useFxData,
  useFxFeature,
  useMarketplaceLoansData,
  useNotificationReadActions,
  useNotificationsData,
  isFixturePreview
} from "./investorPortal/data";
import { portalFixture } from "./investorPortal/fixtures";
import {
  FrozenAccountContext,
  frozenAccountFromBalances,
  frozenActionReason,
  useFrozenAccount
} from "./investorPortal/accountState";
import { isSignedOutError, retryTransientSessionError } from "./investorPortal/session";
import {  rememberPlatformBusinessDate } from "./investorPortal/platformClock";
import { SensitivePinField } from "./investorPortal/pin";
import { useSensitivePin } from "./investorPortal/pinState";
import { SitePages } from "./site/SitePages";
import { captureMagicLinkTokenFromLocation } from "./magicLinkToken";
import {
  formatDate,
  formatDateTime,
  formatDecimal,
  formatMoneyMinor,
  formatMoneyLabel,
  formatRateBps,
  formatWholeAmount,
  isZurichWeekendAt,
  parseMoneyInputToMinorUnits,
  useNumberFormatScope
} from "./investorPortal/format";
import type { AppRoute, DemoAccountState, RouteName } from "./investorPortal/types";
import { useT } from "./i18n";
import { PortalNavProvider, type PortalNav } from "./portal/components";
import { PortalShell } from "./portal/shell/PortalShell";
import { LegacyBody } from "./portal/shell/LegacyBody";
import { FX_NAV_ITEM, NAV_PARENT } from "./portal/shell/nav";
import { PreviewControls } from "./portal/shell/PreviewControls";
import { FrozenAccountNotice, ShellNotice, ShellNotices } from "./portal/shell/ShellNotices";
import { AccountBlockedScreen } from "./portal/screens/account/AccountBlockedScreen";
import { AuthLoading } from "./portal/screens/account/auth/AuthLayout";
import { loginFlowStorageKey, registerFlowStorageKey } from "./portal/screens/account/auth/authState";
import { KycReturnScreen } from "./portal/screens/account/auth/KycReturnScreen";
import { LoginScreen } from "./portal/screens/account/auth/LoginScreen";
import { PinGateScreen } from "./portal/screens/account/auth/PinGateScreen";
import { RegisterScreen } from "./portal/screens/account/auth/RegisterScreen";
import { HelpScreen } from "./portal/screens/account/HelpScreen";
import { KycStatusScreen, VerificationLoading } from "./portal/screens/account/KycStatusScreen";
import { BankAccountDialog } from "./portal/screens/account/parts/BankAccountDialog";
import { SettingsScreen } from "./portal/screens/account/SettingsScreen";
import { isSettingsPathSegment } from "./portal/screens/account/settings/settingsTabs";
import { AccountScreen } from "./portal/screens/wallet/AccountScreen";
import { AddFundsDialog } from "./portal/screens/wallet/AddFundsDialog";
import { DocumentsScreen } from "./portal/screens/wallet/DocumentsScreen";
import { NotificationsScreen } from "./portal/screens/wallet/NotificationsScreen";
import {
  CreditFileScreen,
  InvestScreen,
  OpportunitiesScreen,
  OpportunityScreen,
  OverviewScreen,
  PastOpportunitiesScreen,
  type SensitiveActionKit
} from "./portal/screens/invest";
import { InvestmentDetailScreen } from "./portal/screens/portfolio/InvestmentDetailScreen";
import { MyInvestmentsScreen } from "./portal/screens/portfolio/MyInvestmentsScreen";
import { ResaleMarketScreen } from "./portal/screens/portfolio/ResaleMarketScreen";
import { SmartInvestScreen } from "./portal/screens/portfolio/SmartInvestScreen";
import { ReportsScreen } from "./portal/screens/wallet/ReportsScreen";
import { TransactionsScreen } from "./portal/screens/wallet/TransactionsScreen";
import { U33Skin } from "./portal/U33Skin";
import {
  Banner,
  Button,
  Card,
  Check,
  Empty,
  Field,
  Icon,
  Modal,
  Review,
  PageHead,
  UserSkin
} from "./investorPortal/ui";

// Routes whose screens are rebuilt in U33 (portal/screens); every other screen body is wrapped in
// <LegacyBody> by InvestorShell until its slice replaces it. One list per slice (kept apart so the
// parallel slices do not edit the same lines).
// S2 investing (portal/screens/invest).
const U33_SCREENS_INVEST: RouteName[] = ["dashboard", "market", "loan", "loanSchedule", "invest"];
// The email code + PIN confirmation of an investment, shared with the other sensitive actions below.
const investSensitiveAction: SensitiveActionKit = {
  useCode: useSensitiveActionCode,
  useAutoRequest: useAutoRequestEmailCode,
  requestLabel: emailCodeRequestLabel,
  requestDisabled: emailCodeRequestDisabled
};

// S3 portfolio, resale, Smart Invest (portal/screens/portfolio).
const U33_SCREENS_PORTFOLIO: RouteName[] = ["portfolio", "investment", "secondary", "smartInvest"];

// S4 account, transactions, reports, documents, notifications (portal/screens/wallet).
const U33_SCREENS_WALLET: RouteName[] = ["balances", "transactions", "reports", "documents", "notifications"];

// S5 profile and settings, help, verification (portal/screens/account).
const U33_SCREENS_ACCOUNT: RouteName[] = ["settings", "faq", "kyc"];

const U33_SCREENS = new Set<RouteName>([
  ...U33_SCREENS_INVEST,
  ...U33_SCREENS_PORTFOLIO,
  ...U33_SCREENS_WALLET,
  ...U33_SCREENS_ACCOUNT
]);

const platformName = import.meta.env.VITE_PLATFORM_BRAND_NAME ?? "BANXUM";

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

const appRouteStorageKey = "banxum:app-route:v1";

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
  // Profile & Settings tabs (/settings/security...).
  const settingsMatch = normalized.match(/^\/settings\/([a-z-]+)$/);
  if (settingsMatch && isSettingsPathSegment(settingsMatch[1])) return { name: "settings", params: { tab: settingsMatch[1] } };
  // Past opportunities and the credit file are views of the marketplace and loan routes (slice S2).
  if (normalized === "/marketplace/archive") return { name: "market", params: { view: "archive" } };
  const investmentMatch = normalized.match(/^\/portfolio\/([^/]+)$/);
  if (investmentMatch) {
    try {
      return { name: "investment", params: { holdingId: decodeURIComponent(investmentMatch[1]) } };
    } catch {
      return siteRoute;
    }
  }
  const loanMatch = normalized.match(/^\/marketplace\/([^/]+)(\/schedule|\/invest|\/credit-file)?$/);
  if (!loanMatch) return siteRoute;
  try {
    const name: RouteName = loanMatch[2] === "/schedule" ? "loanSchedule" : loanMatch[2] === "/invest" ? "invest" : "loan";
    const loanId = decodeURIComponent(loanMatch[1]);
    return { name, params: loanMatch[2] === "/credit-file" ? { loanId, section: "credit-file" } : { loanId } };
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
    market: route.params?.view === "archive" ? "/marketplace/archive" : "/marketplace",
    smartInvest: "/smart-invest",
    loan: `/marketplace/${encodeURIComponent(route.params?.loanId ?? "")}${route.params?.section === "credit-file" ? "/credit-file" : ""}`,
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
    settings: route.params?.tab && isSettingsPathSegment(route.params.tab) ? `/settings/${route.params.tab}` : "/settings",
    faq: "/portal/help"
  };
  return paths[route.name];
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

function marketplaceAvailableMinor(
  loan: Pick<MarketplaceLoanPreview, "fillable_amount_minor" | "remaining_capacity_minor">
) {
  return loan.fillable_amount_minor ?? loan.remaining_capacity_minor;
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
    return <PortalNavProvider value={authNavFor(route, setRoute)}><KycReturnScreen /></PortalNavProvider>;
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

  // Sign-in and registration (S5): U33 auth layout, outside the investor shell.
  if (route.name === "login") {
    return <PortalNavProvider value={authNavFor(route, setRoute)}><LoginScreen /></PortalNavProvider>;
  }

  if (route.name === "register") {
    return (
      <PortalNavProvider value={authNavFor(route, setRoute)}>
        <RegisterScreen
          previewDefaults={isFixturePreview ? { firstName: "Lukas", lastName: "Brunner", email: portalFixture.profile.email, phoneNationalNumber: "79 000 00 00" } : undefined}
        />
      </PortalNavProvider>
    );
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

/** Navigation for the screens outside the investor shell (sign-in, registration, PIN gate, Didit return). */
function authNavFor(route: AppRoute, setRoute: (route: AppRoute) => void): PortalNav {
  return {
    hrefFor: (name, params) => routePath({ name, params }),
    go: (name, params) => goTo(setRoute, name, params),
    route
  };
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
  // Currency of the bank account being added (the Account page knows it; the frozen-account banner does not).
  const [bankAccountCurrency, setBankAccountCurrency] = useState<string | undefined>(undefined);
  const openBankAccountDialog = useCallback((currency?: string) => {
    setBankAccountCurrency(currency);
    setPayoutIbanOpen(true);
  }, []);
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
    return <PortalNavProvider value={authNavFor(route, setRoute)}><AuthLoading title={t("Checking your session")} /></PortalNavProvider>;
  }
  if (signedOutAtHome) {
    // The layout effect above switches to the public route before this is painted.
    return null;
  }
  if (!isFixturePreview && !sessionUser) {
    return <PortalNavProvider value={authNavFor(route, setRoute)}><LoginScreen /></PortalNavProvider>;
  }
  if (!isFixturePreview && sessionUser && ["admin", "superadmin"].includes(sessionUser.account_type) && !readonlyImpersonation.active) {
    return <AdminApp />;
  }

  const screen = (() => {
    switch (route.name) {
      case "dashboard":
        return <OverviewScreen demoState={demoState} investorName={profile.name} />;
      case "market":
        return route.params?.view === "archive"
          ? <PastOpportunitiesScreen />
          : <OpportunitiesScreen initialMatchesOnly={route.params?.matches === "1"} key={route.params?.matches ?? "all"} />;
      case "smartInvest":
        return <SmartInvestScreen />;
      case "loan":
        return route.params?.section === "credit-file" ? (
          <CreditFileScreen initialChapter={route.params?.chapter} key={`${route.params?.loanId}:${route.params?.chapter ?? ""}`} loanId={route.params?.loanId ?? ""} />
        ) : (
          <OpportunityScreen
            demoState={demoState}
            fromArchive={route.params?.from === "archive"}
            loanId={route.params?.loanId ?? ""}
            onAddFunds={() => setAddFundsOpen(true)}
          />
        );
      case "loanSchedule":
        // The old schedule page: the opportunity page with its payment schedule open.
        return <OpportunityScreen demoState={demoState} loanId={route.params?.loanId ?? ""} onAddFunds={() => setAddFundsOpen(true)} scheduleOpen />;
      case "invest":
        return (
          <InvestScreen
            demoState={demoState}
            initialAmount={route.params?.amount}
            loanId={route.params?.loanId ?? ""}
            onAddFunds={() => setAddFundsOpen(true)}
            sensitiveAction={investSensitiveAction}
          />
        );
      case "portfolio":
        return <MyInvestmentsScreen />;
      case "investment":
        return <InvestmentDetailScreen focusSection={route.params?.section} holdingId={route.params?.holdingId ?? ""} />;
      case "secondary":
        return <ResaleMarketScreen initialTab={route.params?.tab} />;
      case "balances":
        // Adding a bank account opens the shell's bank-account dialog for that currency.
        return <AccountScreen demoState={demoState} onAddBankAccount={openBankAccountDialog} />;
      case "transactions":
        return <TransactionsScreen />;
      case "reports":
        return <ReportsScreen />;
      case "fx":
        if (fxFeature.enabled) return <FxScreen demoState={demoState} />;
        return fxFeature.known
          ? <OverviewScreen demoState={demoState} investorName={profile.name} />
          : <ScreenLoading title="Currency exchange" />;
      case "documents":
        return <DocumentsScreen />;
      case "notifications":
        return <NotificationsScreen />;
      case "settings":
        return <SettingsScreen previewProfile={isFixturePreview ? displayProfile() : undefined} tab={route.params?.tab} />;
      case "kyc":
        return <KycStatusScreen />;
      case "faq":
        return <HelpScreen />;
      default:
        return <OverviewScreen demoState={demoState} investorName={profile.name} />;
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
        ? <VerificationLoading />
        : <KycStatusScreen />
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
      <PortalNavProvider value={authNavFor(route, setRoute)}>
        <PinGateScreen
          onCreated={() => {
            if (isFixturePreview) setDemoState("active");
            setPinJustCreated(true);
          }}
          onSignOut={signOut}
          signOutError={signOutError}
          signOutLabel={signOutLabel}
        />
      </PortalNavProvider>
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
  // The gate screens (account access, verification) are U33 screens of S5.
  const isU33Screen = gatedScreen !== screen || U33_SCREENS.has(route.name);
  const notices = [
    signOutError ? (
      <ShellNotice
        actions={
          <button className="alert-link" disabled={logoutMutation.isPending} onClick={signOut} type="button">
            {logoutMutation.isPending ? t("Signing out...") : t("Retry sign out")}
          </button>
        }
        icon="alert-circle"
        key="sign-out"
        title={t("Sign out failed")}
        tone="danger"
      >
        {signOutError}
      </ShellNotice>
    ) : null,
    isFixturePreview ? (
      <ShellNotice icon="alert" key="preview" title={t("Preview data")} tone="warning">
        {t("This investor portal is running with local fixture data for UX review. Balances, holdings, activity and documents shown here are not real account data.")}
      </ShellNotice>
    ) : null,
    readonlyImpersonation.active ? (
      <ShellNotice icon="eye" key="read-only" title={t("Superadmin read-only view")} tone="info">
        {t("Viewing the portal as {name}. Actions that change data are disabled, and generated or downloaded evidence is audited to the superadmin, not recorded as user activity.", { name: readonlyImpersonation.label || t("selected user") })}
      </ShellNotice>
    ) : null,
    frozenAccount.frozen && financialAccessAllowed && !blockedAccountStatus ? (
      <FrozenAccountNotice
        account={frozenAccount}
        fxEnabled={fxFeature.enabled}
        key="frozen"
        onAddBankAccount={readonlyImpersonation.active ? undefined : () => openBankAccountDialog()}
        onOpenAccount={route.name === "balances" ? undefined : () => goTo(setRoute, "balances")}
      />
    ) : null
  ].filter((notice): notice is ReactElement => Boolean(notice));

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
              <>
                {addFundsOpen ? (
                  <AddFundsDialog currency={addFundsCurrency} onClose={() => setAddFundsOpen(false)} />
                ) : null}
                {payoutIbanOpen ? (
                  <BankAccountDialog
                    currency={bankAccountCurrency}
                    holderName={readonlyImpersonation.active ? "" : profile.name}
                    onClose={() => setPayoutIbanOpen(false)}
                  />
                ) : null}
              </>
            ) : null}
            extraNavItems={fxFeature.enabled ? { Wallet: [FX_NAV_ITEM] } : undefined}
            markers={accountMarker ? { balances: accountMarker } : undefined}
            notices={notices.length > 0 ? <ShellNotices>{notices}</ShellNotices> : null}
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

// Account statuses that block login and financial access (set by an admin).
const blockedAccountStatuses = new Set(["restricted", "locked", "closed"]);
const lenderAccountTypes = new Set(["natural_person_lender", "legal_entity_lender_representative"]);

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
