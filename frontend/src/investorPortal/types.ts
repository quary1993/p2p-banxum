export type DemoAccountState = "active" | "kyc_pending" | "frozen" | "restricted";

export type RouteName =
  | "public"
  | "publicProjects"
  | "publicFaq"
  | "login"
  | "register"
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
  type: "Agreement" | "Risk" | "Assignment" | "Confirmation" | "Statement" | "Tax";
  version: string;
  date: string;
  context: string;
  size: string;
}

export interface NotificationItem {
  id: string;
  tone: "ok" | "warn" | "bad" | "info";
  title: string;
  body: string;
  time: string;
  unread: boolean;
  target?: "loan" | "holding" | "portfolio" | "balances" | "secondary_market" | "fx";
  targetId?: string;
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
