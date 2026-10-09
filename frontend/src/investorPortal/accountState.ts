// Account state derived from the live balances API (audit A-20/A-21). The day-60 "frozen" state
// (penalty mode, PAY-DEC-022) used to exist only in the fixture preview; it now comes from
// `has_penalty_mode_balance` and the lots' `blocks_financial_actions`.
import { createContext, useContext } from "react";

import type { BalanceSummary, InvestorBalancePortal, PayoutInstruction } from "../api/generated/banxumApi";

export type FrozenAccount = {
  /** Investing, FX and secondary-market actions are blocked until the money is returned. */
  frozen: boolean;
  /** Money in penalty mode per currency. */
  amounts: Array<{ currency: string; amountMinor: number }>;
  /** Daily penalty on that money, in basis points. */
  penaltyBpsPerDay: number;
  /** Currencies of the frozen money that have no verified payout IBAN yet. */
  currenciesWithoutVerifiedIban: string[];
};

export const notFrozenAccount: FrozenAccount = {
  frozen: false,
  amounts: [],
  penaltyBpsPerDay: 0,
  currenciesWithoutVerifiedIban: []
};

type BalancesLike = Partial<
  Pick<
    InvestorBalancePortal,
    "summaries" | "lots" | "payout_instructions" | "has_penalty_mode_balance" | "penalty_bps_per_day"
  >
>;

/**
 * The frozen state of the investor. `previewFrozen` keeps the fixture preview's "Day-60 freeze"
 * switch working; live data never depends on it.
 */
export function frozenAccountFromBalances(balances: BalancesLike | undefined, previewFrozen = false): FrozenAccount {
  if (!balances) return notFrozenAccount;
  const summaries = balances.summaries ?? [];
  const lots = balances.lots ?? [];
  const live = Boolean(balances.has_penalty_mode_balance) || lots.some((lot) => lot.blocks_financial_actions);
  if (!live && !previewFrozen) return notFrozenAccount;
  const amounts = summaries
    .map((summary) => ({
      currency: summary.currency,
      amountMinor: live ? summary.penalty_mode_minor : summary.overdue_minor + summary.penalty_mode_minor
    }))
    .filter((amount) => amount.amountMinor > 0);
  // Lots can block before the summary is refreshed; fall back to the lots themselves.
  const fromLots = lots
    .filter((lot) => lot.blocks_financial_actions && !amounts.some((amount) => amount.currency === lot.currency))
    .reduce<Map<string, number>>((byCurrency, lot) => {
      byCurrency.set(lot.currency, (byCurrency.get(lot.currency) ?? 0) + lot.available_amount_minor);
      return byCurrency;
    }, new Map());
  fromLots.forEach((amountMinor, currency) => amounts.push({ currency, amountMinor }));
  amounts.sort((left, right) => left.currency.localeCompare(right.currency));
  const verified = new Set(
    (balances.payout_instructions ?? [])
      .filter((instruction) => instruction.is_verified_usable)
      .map((instruction) => instruction.currency)
  );
  return {
    frozen: true,
    amounts,
    penaltyBpsPerDay: balances.penalty_bps_per_day ?? 0,
    currenciesWithoutVerifiedIban: amounts.map((amount) => amount.currency).filter((currency) => !verified.has(currency))
  };
}

export const FrozenAccountContext = createContext<FrozenAccount>(notFrozenAccount);

export function useFrozenAccount() {
  return useContext(FrozenAccountContext);
}

/**
 * The amount a voluntary withdrawal can take: everything on the account except lots with the
 * status "frozen", which the ledger never releases for withdrawals. Penalty-mode money can and
 * should be withdrawn (to a verified IBAN).
 */
export function withdrawableMinor(summary: Pick<BalanceSummary, "total_available_minor" | "frozen_minor"> | undefined) {
  if (!summary) return 0;
  return Math.max(0, summary.total_available_minor - summary.frozen_minor);
}

export type PayoutInstructionState = {
  key: "verified" | "pending_verification" | "revoked" | "rejected" | "disabled";
  label: string;
  tone: "ok" | "warn" | "bad" | "neutral";
};

/** Verification state of a payout IBAN as the investor should read it. */
export function payoutInstructionState(instruction: Pick<PayoutInstruction, "is_verified_usable" | "status">): PayoutInstructionState {
  const status = String(instruction.status ?? "").toLowerCase();
  if (status === "revoked") return { key: "revoked", label: "Revoked", tone: "bad" };
  if (status === "rejected") return { key: "rejected", label: "Rejected", tone: "bad" };
  if (status === "disabled") return { key: "disabled", label: "Not in use", tone: "neutral" };
  if (instruction.is_verified_usable) return { key: "verified", label: "Verified", tone: "ok" };
  return { key: "pending_verification", label: "Pending verification", tone: "warn" };
}

export function joinWithAnd(items: string[]) {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** Short reason shown next to a money action that the frozen state blocks. */
export function frozenActionReason(account: FrozenAccount) {
  return account.currenciesWithoutVerifiedIban.length > 0
    ? `Your account is frozen. Add a payout IBAN for ${joinWithAnd(account.currenciesWithoutVerifiedIban)} first.`
    : "Your account is frozen until the overdue money is withdrawn.";
}
