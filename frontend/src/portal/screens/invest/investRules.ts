// IP of Webby-Soft SRL.
/*
 * The amount checks and order bookkeeping of the investing screens (slice S2), with today's platform
 * rules: the minimum, the remaining capacity and the eligible balance come from the API (the Swiss
 * places rule of MKT-DEC-028 is already in the API minimum). The order, its terms acceptance and the
 * allocation record one amount, so a new amount starts a new attempt with new keys (audit A-15).
 */
import type { MarketplaceLoanDetail, PrimaryInvestmentOrder, PublicDocumentTemplateVersion } from "../../../api/generated/banxumApi";
import { ApiClientError } from "../../../api/client/httpClient";
import { t } from "../../../i18n";
import { frozenActionReason, type FrozenAccount } from "../../../investorPortal/accountState";
import { formatMoneyLabel, parseMoneyInputToMinorUnits } from "../../../investorPortal/format";
import { investAmountLimitMessage, type InvestFunds } from "../../../investorPortal/investLimits";
import { swissInvestorLimitMessage } from "../../../investorPortal/investorLimit";
import type { DemoAccountState } from "../../../investorPortal/types";
import { isReadonlyView, loanAvailableMinor, placesInfo } from "./loanFacts";

/** Why the viewer cannot start an investment, or null (read-only view, frozen account, KYC pending). */
export function investBlockedReason(demoState: DemoAccountState, frozen: FrozenAccount) {
  if (isReadonlyView()) return t("This is a read-only investor view. You can see the loan, but you cannot invest.");
  if (frozen.frozen) return frozenActionReason(frozen);
  if (demoState === "kyc_pending") return t("Complete your identity verification to invest.");
  return null;
}

export type AmountCheck =
  | { ok: true; amountMinor: number }
  | { ok: false; message: string; amountMinor: number; shortfallMinor?: number };

/** Validates an amount typed for a loan: format, then the rules of checkInvestAmountMinor. */
export function checkInvestAmount(text: string, loan: MarketplaceLoanDetail, funds: InvestFunds): AmountCheck {
  if (!text.trim()) return { ok: false, message: t("Enter an amount."), amountMinor: 0 };
  const parsed = parseMoneyInputToMinorUnits(text, loan.currency);
  if (parsed.error) return { ok: false, message: parsed.error, amountMinor: parsed.amountMinor };
  return checkInvestAmountMinor(parsed.amountMinor, loan, funds);
}

/** Validates an amount for a loan: minimum, Swiss places, remaining capacity, eligible balance. */
export function checkInvestAmountMinor(amountMinor: number, loan: MarketplaceLoanDetail, funds: InvestFunds): AmountCheck {
  if (amountMinor <= 0) return { ok: false, message: t("Enter an amount."), amountMinor };
  const places = placesInfo(loan);
  if (places?.fullForViewer) return { ok: false, message: swissInvestorLimitMessage(places.maxInvestors), amountMinor };
  if (amountMinor < loan.minimum_investment_minor) {
    return { ok: false, message: t("The minimum investment is {amount}.", { amount: formatMoneyLabel(loan.currency, loan.minimum_investment_minor) }), amountMinor };
  }
  const capacityMinor = loanAvailableMinor(loan);
  if (amountMinor > capacityMinor || amountMinor > funds.eligibleMinor) {
    // Money missing on the account (not money that is too old for this funding window): Add funds.
    if (amountMinor <= capacityMinor && funds.eligibleMinor >= funds.balanceMinor) {
      const shortfallMinor = amountMinor - funds.eligibleMinor;
      return { ok: false, message: t("Add {amount} to invest this amount.", { amount: formatMoneyLabel(loan.currency, shortfallMinor) }), amountMinor, shortfallMinor };
    }
    const message = investAmountLimitMessage({ amountMinor, capacityMinor, currency: loan.currency, funds, money: (minor) => formatMoneyLabel(loan.currency, minor) });
    return { ok: false, message: message ?? t("This amount cannot be invested in this loan."), amountMinor };
  }
  return { ok: true, amountMinor };
}

export function idempotencyKey(prefix: string) {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  return `${prefix}:${random}`;
}

export function apiErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return t("Request failed. Retry once the connection is restored.");
}

export function templateLabels(template: PublicDocumentTemplateVersion | undefined) {
  return Array.isArray(template?.checkbox_labels)
    ? template.checkbox_labels.filter((label): label is string => typeof label === "string")
    : [];
}

/** The published legal template of a category on the public site (/legal/primary-market-investment). */
export function legalDocumentPath(category: string) {
  return `/legal/${category.replace(/_/g, "-")}`;
}

export type PrimaryOrderAttempt = {
  amountMinor: number;
  orderKey: string;
  acceptanceKey: string;
  allocationKey: string;
  orderId: string | null;
  acceptanceId: string | null;
};

export function newPrimaryOrderAttempt(amountMinor: number): PrimaryOrderAttempt {
  return {
    amountMinor,
    orderKey: idempotencyKey("primary-order"),
    acceptanceKey: idempotencyKey("primary-acceptance"),
    allocationKey: idempotencyKey("primary-allocation"),
    orderId: null,
    acceptanceId: null
  };
}

export type ClaimPurchaseAttempt = { quoteId: string; acceptanceKey: string; purchaseKey: string; acceptanceId: string | null };

/** The terms acceptance and the purchase key belong to one quote (audit A-37). */
export function newClaimPurchaseAttempt(quoteId: string): ClaimPurchaseAttempt {
  return {
    quoteId,
    acceptanceKey: idempotencyKey("originator-claim-acceptance"),
    purchaseKey: idempotencyKey("originator-claim-purchase"),
    acceptanceId: null
  };
}

/** The server closed the order before allocation; the next confirmation places a new order. */
export function isOrderNotPendingError(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 400) return false;
  const payload = error.payload as { code?: unknown } | null | undefined;
  return payload?.code === "order_not_pending";
}

export type OrderOutcome = { kind: "reserved" | "partial" | "invested" | "refused"; title: string; text: string };

/** What the server did with the order (audit A-33 / SECONDARY-06), in plain words. */
export function primaryOrderOutcome(order: PrimaryInvestmentOrder, loan: MarketplaceLoanDetail, subscription: boolean): OrderOutcome {
  const money = (minor: number) => formatMoneyLabel(loan.currency, minor);
  if (order.status === "closed_not_invested") {
    const reason = order.closed_reason.toLowerCase().includes("minimum")
      ? t("Less than the minimum order of {amount} was left in this loan.", { amount: money(loan.minimum_investment_minor) })
      : t("Other investors took the rest of this loan first.");
    return { kind: "refused", title: t("Investment not placed"), text: `${reason} ${t("Nothing was invested and no money moved.")}` };
  }
  if (order.status === "partially_allocated") {
    return {
      kind: "partial",
      title: t("Investment partly reserved"),
      text: t("Only {allocated} was left in this loan. We reserved {allocated} of the {requested} you asked for. The rest stays in your balance.", {
        allocated: money(order.allocated_amount_minor),
        requested: money(order.requested_amount_minor)
      })
    };
  }
  if (order.status === "closed_invested") {
    return { kind: "invested", title: t("Investment made"), text: t("{amount} is now invested. The funding round closed.", { amount: money(order.allocated_amount_minor) }) };
  }
  return {
    kind: "reserved",
    title: t("Investment reserved"),
    text: subscription
      ? t("{amount} of your balance is reserved for the Loan Originator funding round. It becomes an active investment automatically when funding closes. The first installment after the funding deadline belongs to the Loan Originator. If the round is cancelled, the reservation is released.", { amount: money(order.allocated_amount_minor) })
      : t("{amount} of your balance is reserved for this loan. The investment starts when funding closes. If the loan does not reach its minimum, the money goes back to your balance.", { amount: money(order.allocated_amount_minor) })
  };
}
