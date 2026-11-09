// Account status pieces of the investor shell (audit A-20/A-21).
import { joinWithAnd, type FrozenAccount } from "./accountState";
import { formatMoneyLabel, formatRateBps } from "./format";
import { Banner, Button } from "./ui";

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
