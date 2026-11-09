// IP of Webby-Soft SRL.
// What the Account page shows, derived from the balances, primary-orders and loans APIs: the
// currency order, reserved money, withdrawals in progress, the next automatic return and today's
// account notices (last day, money due back, frozen). No amount is estimated: every figure is a
// sum of API amounts.
import type {
  BalanceLot,
  BalanceSummary,
  InvestorBalancePortal,
  PayoutInstruction,
  PendingWithdrawal,
  PrimaryOrderPortal
} from "../../../api/generated/banxumApi";

/** Orders whose allocated amount is reserved from the balance until the loan's funding closes. */
export const RESERVED_ORDER_STATUSES = new Set(["balance_allocated", "partially_allocated"]);

/** EUR first, then CHF, then any other currency (design order of the account cards). */
export function currencyRank(currency: string) {
  return currency === "EUR" ? 0 : currency === "CHF" ? 1 : 2;
}

export function orderedSummaries(summaries: BalanceSummary[]) {
  return [...summaries].sort((a, b) => currencyRank(a.currency) - currencyRank(b.currency) || a.currency.localeCompare(b.currency));
}

export function reservedOrders(orders: PrimaryOrderPortal[] | undefined) {
  return (orders ?? []).filter((order) => RESERVED_ORDER_STATUSES.has(order.status) && order.allocated_amount_minor > 0);
}

export function sumByCurrency<T>(items: T[], currency: string, pick: (item: T) => { currency: string; amountMinor: number }) {
  return items.reduce((total, item) => {
    const { currency: itemCurrency, amountMinor } = pick(item);
    return itemCurrency === currency ? total + amountMinor : total;
  }, 0);
}

export function reservedMinor(orders: PrimaryOrderPortal[], currency: string) {
  return sumByCurrency(orders, currency, (order) => ({ currency: order.currency, amountMinor: order.allocated_amount_minor }));
}

export function pendingWithdrawalMinor(withdrawals: PendingWithdrawal[], currency: string) {
  return sumByCurrency(withdrawals, currency, (withdrawal) => ({ currency: withdrawal.currency, amountMinor: withdrawal.amount_minor }));
}

export function verifiedAccounts(instructions: PayoutInstruction[], currency: string) {
  return instructions.filter((instruction) => instruction.currency === currency && instruction.is_verified_usable);
}

const PENALTY_BUCKETS = new Set(["penalty", "penalty_mode", "penalty_exhausted"]);

export function isFrozenLot(lot: Pick<BalanceLot, "bucket" | "status" | "blocks_financial_actions">) {
  return PENALTY_BUCKETS.has(lot.bucket) || lot.status === "frozen" || lot.blocks_financial_actions;
}

function liveLots(lots: BalanceLot[], currency: string) {
  return lots.filter((lot) => lot.currency === currency && lot.available_amount_minor > 0);
}

export type NextReturn = { date: string; amountMinor: number | null; lastDay: boolean };

/**
 * The next automatic return of a currency: the earliest return date of money that can still be
 * invested; when only money on its last day is left, that money's return. Without lots of the
 * currency it falls back to the summary's next_return_date (amount unknown); money already due back
 * or frozen has no upcoming return (the account notices cover it).
 */
export function nextReturn(summary: BalanceSummary, lots: BalanceLot[]): NextReturn | null {
  const live = liveLots(lots, summary.currency);
  const own = live.filter((lot) => !isFrozenLot(lot));
  for (const bucket of ["investable", "withdraw_only"]) {
    const candidates = own.filter((lot) => lot.bucket === bucket && lot.return_date);
    if (candidates.length === 0) continue;
    const date = candidates.map((lot) => lot.return_date).sort()[0];
    const amountMinor = candidates.filter((lot) => lot.return_date === date).reduce((total, lot) => total + lot.available_amount_minor, 0);
    return { date, amountMinor, lastDay: bucket === "withdraw_only" };
  }
  if (live.length > 0) return null;
  return summary.next_return_date ? { date: summary.next_return_date, amountMinor: null, lastDay: false } : null;
}

export type AccountNotice =
  | { kind: "dueBackNoAccount"; currency: string; amountMinor: number }
  | { kind: "dueBack"; currency: string; amountMinor: number }
  | { kind: "lastDay"; currency: string; amountMinor: number; returnDate: string | null };

/**
 * Today's states that need the investor (PAY-DEC-017/022, until U33-DEC-03/04): money on its last
 * day (withdraw-only), money due back to the bank, and money due back with no verified bank account
 * to send it to. The frozen state has its own banner in the shell.
 */
export function accountNotices(balances: Pick<InvestorBalancePortal, "summaries" | "lots" | "payout_instructions">): AccountNotice[] {
  const notices: AccountNotice[] = [];
  for (const summary of orderedSummaries(balances.summaries)) {
    const currency = summary.currency;
    const hasAccount = verifiedAccounts(balances.payout_instructions, currency).length > 0;
    if (summary.overdue_minor > 0) {
      notices.push({ kind: hasAccount ? "dueBack" : "dueBackNoAccount", currency, amountMinor: summary.overdue_minor });
    }
    if (summary.withdraw_only_minor > 0) {
      const lastDayLots = liveLots(balances.lots, currency).filter((lot) => lot.bucket === "withdraw_only");
      const returnDate = lastDayLots.map((lot) => lot.return_date).filter(Boolean).sort()[0] ?? null;
      notices.push({ kind: "lastDay", currency, amountMinor: summary.withdraw_only_minor, returnDate });
    }
  }
  // Money that cannot go back comes first.
  const rank = { dueBackNoAccount: 0, lastDay: 1, dueBack: 2 } as const;
  return notices.sort((a, b) => rank[a.kind] - rank[b.kind]);
}

/** Lots shown in Balance details: money still on the account, oldest first (the order lots are used). */
export function detailLots(lots: BalanceLot[]) {
  return lots
    .filter((lot) => lot.available_amount_minor > 0 || lot.penalized_amount_minor > 0)
    .sort((a, b) => a.received_at.localeCompare(b.received_at) || currencyRank(a.currency) - currencyRank(b.currency));
}

// Readable names of balance-lot sources (ledger BalanceLotSourceType), never raw keys.
const lotSourceLabels: Record<string, string> = {
  deposit: "Bank deposit",
  installment: "Loan repayment",
  repayment_principal: "Loan repayment",
  repayment_interest: "Loan repayment",
  originator_claim_repayment: "Loan Originator claim repayment",
  recovery_distribution: "Recovery payment",
  secondary_market_proceeds: "Resale proceeds",
  fx_proceeds: "Currency exchange",
  refund: "Refund",
  correction: "Balance correction",
  penalty_reversal: "Penalty refund"
};

export function lotSourceLabel(sourceType: string) {
  return lotSourceLabels[sourceType] ?? sourceType.replace(/_/g, " ").replace(/^\w/, (letter) => letter.toUpperCase());
}
