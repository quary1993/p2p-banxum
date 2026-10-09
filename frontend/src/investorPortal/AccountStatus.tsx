// Account status pieces shared by the investor shell and the Account page (audit A-20/A-21).
import type { PendingWithdrawal } from "../api/generated/banxumApi";
import { joinWithAnd, type FrozenAccount } from "./accountState";
import { formatDate, formatMoneyLabel, formatRateBps } from "./format";
import { Banner, Button, Chip, Empty } from "./ui";

/**
 * The blocking banner of PAY-DEC-022: what is frozen, the daily penalty, and what to do.
 * `onAddIban` opens the payout-IBAN dialog; `onOpenAccount` leads to the Account page.
 */
export function FrozenAccountBanner({
  account,
  onAddIban,
  onOpenAccount
}: {
  account: FrozenAccount;
  onAddIban?: () => void;
  onOpenAccount?: () => void;
}) {
  if (!account.frozen) return null;
  const amounts = account.amounts.map((amount) => formatMoneyLabel(amount.currency, amount.amountMinor));
  const missing = account.currenciesWithoutVerifiedIban;
  const what = amounts.length > 0 ? joinWithAnd(amounts) : "Money on your account";
  const penalty = account.penaltyBpsPerDay > 0
    ? ` A penalty of ${formatRateBps(account.penaltyBpsPerDay)} of this money is taken every day until it leaves your account.`
    : "";
  const todo = missing.length > 0
    ? missing.length > 1
      ? ` To unlock them, add a payout IBAN for ${joinWithAnd(missing)}. When Garanta has verified them, we send the money to them.`
      : ` To unlock them, add a payout IBAN for ${joinWithAnd(missing)}. When Garanta has verified it, we send the money to it.`
    : " Your payout IBAN is verified: withdraw the money now, or Garanta sends it to that IBAN.";
  return (
    <Banner
      actions={
        <>
          {onAddIban ? <Button size="sm" variant="primary" onClick={onAddIban}>Add payout IBAN</Button> : null}
          {onOpenAccount ? <Button size="sm" variant="ghost" onClick={onOpenAccount}>Open Account</Button> : null}
        </>
      }
      icon="lock"
      tone="bad"
      title="Financial actions are frozen"
    >
      {what} passed the 60-day holding limit{missing.length > 0 ? ", and there is no verified payout IBAN to return it to" : ""}.{penalty}
      {" "}Investing, currency exchange and secondary-market trades are blocked.{todo} Your portfolio, documents,
      statements and notices remain available.
    </Banner>
  );
}

/** Requested withdrawals waiting for the bank transfer; forced returns are labelled. */
export function PendingWithdrawalsList({ withdrawals }: { withdrawals: PendingWithdrawal[] }) {
  if (withdrawals.length === 0) {
    return <Empty icon="clock" title="No pending withdrawals">Withdrawal requests in progress will appear here.</Empty>;
  }
  return (
    <ul aria-label="Pending withdrawals" className="acct-rows acct-pending-list">
      {withdrawals.map((withdrawal) => (
        <li className="acct-row" key={withdrawal.id}>
          <div className="acct-row-text">
            <div className="acct-row-title num">{formatMoneyLabel(withdrawal.currency, withdrawal.amount_minor)}</div>
            <div className="acct-iban num">To {withdrawal.destination_iban}</div>
            <div className="acct-row-sub">
              {withdrawal.is_forced
                ? `Forced return of money past the 60-day limit, ${formatDate(withdrawal.requested_at)}`
                : `Requested ${formatDate(withdrawal.requested_at)}`}
            </div>
          </div>
          <div className="acct-row-actions">
            {withdrawal.is_forced ? <Chip tone="warn">Forced return</Chip> : null}
            <Chip tone="warn">Waiting for bank transfer</Chip>
          </div>
        </li>
      ))}
    </ul>
  );
}
