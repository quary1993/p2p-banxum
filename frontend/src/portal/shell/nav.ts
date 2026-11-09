// IP of Webby-Soft SRL.
// Sidebar of the U33 investor area (design: INVEST / WALLET / ACCOUNT groups, Help at the bottom).
// Labels are English message keys (translated with t() where rendered).
import type { RouteName } from "../../investorPortal/types";

export type NavCount = "openOpportunities" | "unreadNotifications";
export type NavItem = {
  route: RouteName;
  label: string;
  /** Nioicon of the design's menu entry. */
  icon: string;
  /** data-section of the design (CSS hooks on some entries). */
  section: string;
  count?: NavCount;
};
export type NavGroup = { label: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Invest",
    items: [
      { route: "dashboard", label: "Overview", icon: "dashboard", section: "overview" },
      { route: "market", label: "Investment opportunities", icon: "briefcase", section: "projects", count: "openOpportunities" },
      { route: "secondary", label: "Resale market", icon: "exchange", section: "secondary" },
      { route: "portfolio", label: "My investments", icon: "growth", section: "investments" },
      { route: "smartInvest", label: "Smart Invest", icon: "repeat", section: "auto-invest" }
    ]
  },
  {
    label: "Wallet",
    items: [
      { route: "balances", label: "Account", icon: "wallet-alt", section: "account" },
      { route: "transactions", label: "Transactions", icon: "tranx", section: "transactions" },
      { route: "reports", label: "Reports", icon: "reports", section: "reports" }
    ]
  },
  {
    label: "Account",
    items: [
      { route: "settings", label: "Profile & Settings", icon: "user-c", section: "settings" },
      { route: "documents", label: "Documents", icon: "files", section: "documents" },
      { route: "notifications", label: "Notifications", icon: "bell", section: "notifications", count: "unreadNotifications" }
    ]
  }
];

/** Currency exchange: only when the fx.enabled platform switch is on (U33-DEC-33: off today). */
export const FX_NAV_ITEM: NavItem = { route: "fx", label: "Currency exchange", icon: "exchange", section: "fx" };

export const HELP_NAV_ITEM: NavItem = { route: "faq", label: "Help", icon: "help-alt", section: "help" };

/** Pages that belong to a menu entry without being one themselves. */
export const NAV_PARENT: Partial<Record<RouteName, RouteName>> = {
  loan: "market",
  loanSchedule: "market",
  invest: "market",
  investment: "portfolio",
  kyc: "settings"
};
