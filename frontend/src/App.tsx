//IP of Webby-Soft SRL.
// build-origin: ATEW5bUMtfGj80bXzkGFbtEIwTx0cb6Qig3qkx90kV_Srfdc012ga6e8Ddq5v4qj1nbItbZAfx4ZDA==
import { setNumberFormatPreference } from "./investorPortal/format";
import { useAccountLanguageSync } from "./investorPortal/languagePreference";
import { setInvestorScope } from "./i18n/language";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactElement } from "react";
import {
  ActionEnum,
  useV1AuthMeRetrieve,
  useV1AuthLogoutCreate,
  useV1AuthSensitiveActionCodeRequestCreate,
  useV1KycStatusRetrieve,
  v1AuthMeRetrieve
} from "./api/generated/banxumApi";
import { ApiClientError } from "./api/client/httpClient";
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
  MarketplaceLoanDetail,
  MarketplaceLoanPreview
} from "./api/generated/banxumApi";
import {
  useBalancesData,
  useMarketplaceLoansData,
  useNotificationReadActions,
  useNotificationsData,
  isFixturePreview
} from "./investorPortal/data";
import { portalFixture } from "./investorPortal/fixtures";
import {
  FrozenAccountContext,
  frozenAccountFromBalances
} from "./investorPortal/accountState";
import { isSignedOutError, retryTransientSessionError } from "./investorPortal/session";
import {  rememberPlatformBusinessDate } from "./investorPortal/platformClock";
import { useSensitivePin } from "./investorPortal/pinState";
import { AdminApp, SitePages } from "./lazyAreas";
import { captureMagicLinkTokenFromLocation } from "./magicLinkToken";
import {
  useNumberFormatScope
} from "./investorPortal/format";
import type { AppRoute, DemoAccountState, RouteName } from "./investorPortal/types";
import { useT } from "./i18n";
import { PORTAL_ADDRESS_EVENT, PortalNavProvider, type PortalNav } from "./portal/components";
import { PortalShell } from "./portal/shell/PortalShell";
import { NAV_PARENT } from "./portal/shell/nav";
import { PreviewControls } from "./portal/shell/PreviewControls";
import { FrozenAccountNotice, ShellNotice, ShellNotices } from "./portal/shell/ShellNotices";
import { AccountBlockedScreen } from "./portal/screens/account/AccountBlockedScreen";
import { AuthLoading } from "./portal/screens/account/auth/AuthLayout";
import { clearAuthFlowState } from "./portal/screens/account/auth/authState";
import { KycReturnScreen } from "./portal/screens/account/auth/KycReturnScreen";
import { LoginScreen } from "./portal/screens/account/auth/LoginScreen";
import { FactorGateScreen } from "./portal/screens/account/auth/FactorGateScreen";
import { PinGateScreen } from "./portal/screens/account/auth/PinGateScreen";
import { AccountRecoveryScreen, ResetPasswordScreen } from "./portal/screens/account/auth/RecoveryScreens";
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
  LoanOriginatorsScreen,
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
import { codeRequestBody, useOperationChange, type OperationDetails } from "./investorPortal/operationBinding";

// The email code + PIN (or authenticator code, D-1) confirmation of an investment, shared with the
// other sensitive actions (S2 investing, portal/screens/invest).
const investSensitiveAction: SensitiveActionKit = {
  useCode: useSensitiveActionCode,
  useAutoRequest: useAutoRequestEmailCode,
  requestLabel: emailCodeRequestLabel,
  requestDisabled: emailCodeRequestDisabled
};

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
  return name === "public" || name === "site" || name === "login" || name === "register" || name === "resetPassword" || name === "accountRecovery";
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
    "/reset-password": "resetPassword",
    "/account-recovery": "accountRecovery",
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
  if (normalized === "/account-recovery/not-me") return { name: "accountRecovery", params: { view: "not-me" } };
  // Profile & Settings tabs (/settings/security...).
  const settingsMatch = normalized.match(/^\/settings\/([a-z-]+)$/);
  if (settingsMatch && isSettingsPathSegment(settingsMatch[1])) return { name: "settings", params: { tab: settingsMatch[1] } };
  // Past opportunities and the credit file are views of the marketplace and loan routes (slice S2).
  if (normalized === "/marketplace/archive") return { name: "market", params: { view: "archive" } };
  // Loan originators (design #/originators): a view of the marketplace route.
  if (normalized === "/marketplace/originators") return { name: "market", params: { view: "originators" } };
  const originatorMatch = normalized.match(/^\/marketplace\/originators\/([^/]+)$/);
  if (originatorMatch) {
    try {
      return { name: "market", params: { view: "originators", originatorId: decodeURIComponent(originatorMatch[1]) } };
    } catch {
      return siteRoute;
    }
  }
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
    resetPassword: "/reset-password",
    accountRecovery: route.params?.view === "not-me" ? "/account-recovery/not-me" : "/account-recovery",
    kyc: "/verification",
    dashboard: "/dashboard",
    market: route.params?.view === "archive"
      ? "/marketplace/archive"
      : route.params?.view === "originators"
        ? `/marketplace/originators${route.params?.originatorId ? `/${encodeURIComponent(route.params.originatorId)}` : ""}`
        : "/marketplace",
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
  resetPassword: "Reset password",
  accountRecovery: "Account recovery",
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

function apiErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Request failed. Retry once the connection is restored.";
}

function useSensitiveActionCode(action: ActionEnum, operation?: OperationDetails | null) {
  const requestMutation = useV1AuthSensitiveActionCodeRequestCreate();
  const [codeId, setCodeId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(0);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState("");
  const resendCooldownSeconds = useSecondsUntil(resendCooldownUntil);
  // 18.5: the code confirms only these operation details; changed details need a new code.
  useOperationChange(operation, () => {
    setCodeId(null);
    setSummary("");
    setResendCooldownUntil(0);
  });
  const bodyKey = JSON.stringify(codeRequestBody(action, operation));

  const requestCode = useCallback(() => {
    setError("");
    if (isFixturePreview) {
      setCodeId("00000000-0000-0000-0000-000000000000");
      setExpiresAt(new Date(Date.now() + 10 * 60 * 1000).toISOString());
      setResendCooldownUntil(Date.now() + 60_000);
      return;
    }
    requestMutation.mutate(
      { data: JSON.parse(bodyKey) as ReturnType<typeof codeRequestBody<ActionEnum>> },
      {
        onSuccess: (response) => {
          setCodeId(response.code_id);
          setExpiresAt(response.expires_at);
          setSummary(response.operation_summary ?? "");
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
  }, [bodyKey, requestMutation]);
  // Every sensitive action needs the PIN (or the authenticator code, D-1) with the email code.
  const pin = useSensitivePin();

  return { codeId, expiresAt, summary, error, isRequesting: requestMutation.isPending, resendCooldownSeconds, requestCode, pin };
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
  // The whole address counts: a menu click from /portfolio?view=history must leave History.
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== nextPath) {
    window.history.pushState({}, "", nextPath);
    window.dispatchEvent(new Event(PORTAL_ADDRESS_EVENT));
  }
  setRoute(nextRoute);
  window.scrollTo({ top: 0, behavior: "instant" });
}

function clearPortalSessionState(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.clear();
  clearAuthFlowState();
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

  // U33-DEC-31: the investor area (sign-in, registration, portal) uses the chosen language; the public
  // site and the admin console stay English for now. App re-renders everything when it changes.
  useT();
  const investorArea = !window.location.pathname.startsWith("/admin") && route.name !== "public" && route.name !== "site";
  useLayoutEffect(() => {
    void setInvestorScope(investorArea);
  }, [investorArea]);

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

  // 18.5: the security email links (forgotten password, assisted recovery).
  if (route.name === "resetPassword") {
    return <PortalNavProvider value={authNavFor(route, setRoute)}><ResetPasswordScreen /></PortalNavProvider>;
  }
  if (route.name === "accountRecovery") {
    return (
      <PortalNavProvider value={authNavFor(route, setRoute)}>
        <AccountRecoveryScreen notMe={route.params?.view === "not-me"} />
      </PortalNavProvider>
    );
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
  // 18.5: the factor set up at the factor gate ("app" needs no PIN), before /auth/me reloads.
  const [factorJustSetUp, setFactorJustSetUp] = useState<"" | "app" | "sms">("");
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
  // U33-DEC-32: the number format saved in the account applies on every device.
  const accountNumberFormat = sessionUser?.number_format;
  useEffect(() => {
    if (accountNumberFormat === "european" || accountNumberFormat === "swiss") setNumberFormatPreference(accountNumberFormat);
  }, [accountNumberFormat]);
  // U33-DEC-31: the language saved in the account applies on every device.
  useAccountLanguageSync(sessionUser?.language, { canSave: Boolean(sessionUser) && !readonlyImpersonation.active });
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
  // Q25 (2026-11-13): the currency exchange screen is removed from the investor area (the backend
  // function stays, switched off); an old /fx address shows the dashboard.
  const fxRouteUnavailable = route.name === "fx";
  useEffect(() => {
    if (!fxRouteUnavailable) return;
    const dashboardRoute: AppRoute = { name: "dashboard" };
    writeStoredObject(appRouteStorageKey, dashboardRoute);
    window.history.replaceState({}, "", routePath(dashboardRoute));
    setRoute(dashboardRoute);
  }, [fxRouteUnavailable, setRoute]);
  const balancesData = useBalancesData(financialAccessAllowed).data;
  const balances = balancesData ?? { summaries: [], lots: [] };
  // A blocked account from the live balances (no penalty mode since U33-DEC-04); the preview switch only drives fixtures.
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
          : route.params?.view === "originators"
            ? <LoanOriginatorsScreen key={route.params?.originatorId ?? "all"} originatorId={route.params?.originatorId} />
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
        return <OverviewScreen demoState={demoState} investorName={profile.name} />;
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

  // Lots on their last day (withdraw-only) or due back to the bank need action (older penalty-mode lots too).
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

  // 18.5: an investor without a second factor sets one up before anything else (after an assisted
  // recovery, or an account from before 18.5).
  const needsFactor =
    !isFixturePreview &&
    Boolean(sessionUser) &&
    !readonlyImpersonation.active &&
    !factorJustSetUp &&
    sessionUser?.second_factor === "" &&
    lenderAccountTypes.has(sessionUser.account_type) &&
    !blockedAccountStatuses.has(sessionUser.status);
  if (needsFactor) {
    return (
      <PortalNavProvider value={authNavFor(route, setRoute)}>
        <FactorGateScreen onDone={setFactorJustSetUp} onSignOut={signOut} signOutError={signOutError} signOutLabel={signOutLabel} />
      </PortalNavProvider>
    );
  }

  // ACC-DEC-009: an SMS investor without a PIN creates one before anything else. D-1: an investor
  // with an authenticator app has no PIN.
  const needsPin = isFixturePreview
    ? demoState === "no_pin"
    : Boolean(sessionUser) &&
      !readonlyImpersonation.active &&
      !pinJustCreated &&
      sessionUser?.pin_set === false &&
      sessionUser?.second_factor !== "app" &&
      factorJustSetUp !== "app" &&
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
        fxEnabled={false}
        key="frozen"
        onAddBankAccount={readonlyImpersonation.active ? undefined : () => openBankAccountDialog()}
        onOpenAccount={route.name === "balances" ? undefined : () => goTo(setRoute, "balances")}
      />
    ) : null
  ].filter((notice): notice is ReactElement => Boolean(notice));

  return (
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
            {gatedScreen}
          </FrozenAccountContext.Provider>
        </PortalShell>
        {isFixturePreview ? <PreviewControls onStateChange={setDemoState} state={demoState} /> : null}
      </PortalNavProvider>
    </U33Skin>
  );
}

const blockedAccountStatuses = new Set(["restricted", "locked", "closed"]);
const lenderAccountTypes = new Set(["natural_person_lender", "legal_entity_lender_representative"]);

