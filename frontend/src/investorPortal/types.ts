// "no_pin": the post-login "Create your PIN" screen (ACC-DEC-009).
export type DemoAccountState = "active" | "kyc_pending" | "frozen" | "restricted" | "no_pin";

export type RouteName =
  // The public site: "/" (home) and "site" (every other site path, in params.path and
  // params.search; see site/SitePages.tsx).
  | "public"
  | "site"
  | "login"
  | "register"
  // 18.5: the forgotten-password link and the assisted-recovery links (outside the shell).
  | "resetPassword"
  | "accountRecovery"
  | "kyc"
  | "dashboard"
  | "market"
  | "smartInvest"
  | "loan"
  | "loanSchedule"
  | "invest"
  | "portfolio"
  | "investment"
  | "secondary"
  | "balances"
  | "transactions"
  | "reports"
  | "fx"
  | "documents"
  | "notifications"
  | "settings"
  | "faq";

export interface AppRoute {
  name: RouteName;
  params?: Record<string, string>;
}

export interface InvestorProfile {
  id: string;
  name: string;
  initials: string;
  email: string;
  country: string;
  memberSince: string;
  phone: string;
}

export interface DepositInstruction {
  currency: string;
  iban: string;
  qrIban?: string;
  qrBillPayload?: string;
  bic: string;
  bank: string;
  reference: string;
}

export interface InvestorDocument {
  id: string;
  title: string;
  type: "Agreement" | "Risk" | "Assignment" | "Confirmation" | "Statement" | "Tax" | "Investment agreement" | "Transfer agreement";
  version: string;
  date: string;
  context: string;
  size: string;
  /** Acceptance category of the documents API (registration, primary_market_investment...). */
  category?: string;
  /** The investment (holding) an accepted agreement created; none while its funding is open. */
  holdingId?: string;
  /** Period of a statement or tax document (YYYY-MM-DD). */
  periodStart?: string;
  periodEnd?: string;
}

export interface NotificationItem {
  id: string;
  tone: "ok" | "warn" | "bad" | "info";
  label: string;
  title: string;
  body: string;
  time: string;
  unread: boolean;
  target?: "loan" | "holding" | "portfolio" | "balances" | "secondary_market" | "fx";
  targetId?: string;
  /** Creation time (ISO); the fixture's "today" when missing. */
  createdAt?: string;
  /** Email delivery status; "sent" when missing. */
  status?: string;
}

export interface RecoverySplit {
  loanId: string;
  totalMinor: number;
  currency: string;
  parts: Array<{ label: string; amountMinor: number }>;
}

export interface InvestorPortalFixture {
  today: string;
  profile: InvestorProfile;
  depositInstructions: DepositInstruction[];
  documents: InvestorDocument[];
  notifications: NotificationItem[];
  recoverySplit: RecoverySplit;
}
