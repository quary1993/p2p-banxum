// IP of Webby-Soft SRL.
/*
 * Banxum account (design #/account: main.ap-page.r70-account), route /balances. Per currency: the
 * available balance, reserved money (primary orders allocated until funding closes), withdrawals in
 * progress, Add funds and Withdraw, and the next automatic return with its real date from the API
 * (58 days today; U33-DEC-03 changes it in Phase 17.2). Balance details lists the balance lots, the
 * reservations and the withdrawals in progress. Bank accounts live in Profile & Settings (design).
 * Today's last-day, due-back and penalty states use the design's alert component; the design has no
 * screens for them (U33-DEC-29/04, see docs/claude-design/TODO.md).
 */
import { useState, type ReactNode } from "react";

import type { BalanceLot, BalanceSummary, PendingWithdrawal, PrimaryOrderPortal } from "../../../api/generated/banxumApi";
import { readReadonlyImpersonationToken } from "../../../api/client/impersonation";
import { useT } from "../../../i18n";
import { useFrozenAccount } from "../../../investorPortal/accountState";
import { autoReturnDays } from "../../../investorPortal/balanceAgeing";
import { isFixturePreview, useBalancesData, useFxFeature, useMarketplaceLoansData, usePrimaryOrdersData } from "../../../investorPortal/data";
import { formatDate, formatMoneyLabel, formatMoneyMinor, useNumberFormat } from "../../../investorPortal/format";
import type { DemoAccountState } from "../../../investorPortal/types";
import { ButtonLink, Dialog, EmptyState, InfoTip, NiIcon, PageHead, PortalLink, StatusTag } from "../../components";
import {
  accountNotices,
  detailLots,
  isFrozenLot,
  nextReturn,
  orderedSummaries,
  pendingWithdrawalMinor,
  reservedMinor,
  reservedOrders,
  lotSourceLabel,
  type AccountNotice
} from "./accountModel";
import { AddFundsDialog } from "./AddFundsDialog";
import { maskIban } from "./parts/iban";
import { rich } from "./parts/rich";
import { WithdrawDialog } from "./WithdrawDialog";
import "./wallet.css";

type OpenDialog = { kind: "deposit" | "withdraw"; currency: string } | { kind: "rules" } | null;

function AccountNoticeAlert({
  notice,
  days,
  onWithdraw,
  onAddBankAccount
}: {
  notice: AccountNotice;
  days: number;
  onWithdraw?: (currency: string) => void;
  onAddBankAccount?: (currency: string) => void;
}) {
  const t = useT();
  const amount = formatMoneyLabel(notice.currency, notice.amountMinor);
  // Today's add-bank-account dialog when the shell offers it, else Profile & Settings.
  const addAccount = onAddBankAccount
    ? <button className="alert-link" onClick={() => onAddBankAccount(notice.currency)} type="button">{t("Add a bank account")}</button>
    : <PortalLink className="alert-link" to="settings">{t("Add a bank account")}</PortalLink>;
  if (notice.kind === "dueBackNoAccount") {
    return (
      <div className="alert alert-danger alert-icon">
        <NiIcon name="alert-circle" />
        <strong className="bxm-signal-text">{t("Add a verified bank account so we can return your money.")}</strong>{" "}
        {t("{amount} was not invested within {days} days and must go back to your bank, but there is no verified {currency} bank account.", { amount, days, currency: notice.currency })}{" "}
        {t("After 60 days (the legal limit) the money enters penalty mode.")}{" "}
        {addAccount}
      </div>
    );
  }
  if (notice.kind === "dueBack") {
    return (
      <div className="alert alert-warning alert-icon wl-alert-amber">
        <NiIcon name="undo" />
        <strong className="bxm-signal-text">{t("{amount} goes back to your bank.", { amount })}</strong>{" "}
        {t("It was not invested within {days} days. We send it to your verified bank account.", { days })}
      </div>
    );
  }
  return (
    <div className="alert alert-warning alert-icon wl-alert-amber">
      <NiIcon name="clock" />
      <strong className="bxm-signal-text">{t("Last day for {amount}.", { amount })}</strong>{" "}
      {notice.returnDate
        ? t("It can no longer be invested and goes back to your bank account on {date}. You can withdraw it until then.", { date: formatDate(notice.returnDate) })
        : t("It can no longer be invested. You can withdraw it today.")}{" "}
      {!notice.hasAccount
        ? addAccount
        : onWithdraw ? <button className="alert-link" onClick={() => onWithdraw(notice.currency)} type="button">{t("Withdraw")}</button> : null}
    </div>
  );
}

function ReturnLine({ summary, lots, days }: { summary: BalanceSummary; lots: BalanceLot[]; days: number }) {
  const t = useT();
  const next = nextReturn(summary, lots);
  if (!next) return <p>{t("Money that is not invested goes back to your bank account after {days} days.", { days })}</p>;
  const date = <strong>{formatDate(next.date)}</strong>;
  if (next.amountMinor === null) return <p>{rich(t("Money that is not invested returns on {date}."), { date })}</p>;
  const amount = <strong>{formatMoneyLabel(summary.currency, next.amountMinor)}</strong>;
  return next.lastDay
    ? <p>{rich(t("{amount} goes back to your bank account on {date}."), { amount, date })}</p>
    : <p>{rich(t("{amount} returns on {date} if not invested."), { amount, date })}</p>;
}

function AccountCard({
  summary,
  lots,
  orders,
  withdrawals,
  days,
  addDisabled,
  withdrawDisabled,
  onAdd,
  onWithdraw,
  onRules
}: {
  summary: BalanceSummary;
  lots: BalanceLot[];
  orders: PrimaryOrderPortal[];
  withdrawals: PendingWithdrawal[];
  days: number;
  addDisabled: boolean;
  withdrawDisabled: boolean;
  onAdd: () => void;
  onWithdraw: () => void;
  onRules: () => void;
}) {
  const t = useT();
  const currency = summary.currency;
  const reserved = reservedMinor(orders, currency);
  const pending = pendingWithdrawalMinor(withdrawals, currency);
  const headingId = `wl-account-${currency}`;
  return (
    <section aria-labelledby={headingId} className="card card-bordered ap-account">
      <div className="ap-account-body">
        <div className="ap-currency"><h2 id={headingId}>{t("{currency} account", { currency })}</h2></div>
        <div className="ap-available">
          <span>{t("Available balance")}</span>
          <div><small>{currency}</small><strong>{formatMoneyMinor(summary.total_available_minor, currency)}</strong></div>
        </div>
        <dl className="ap-breakdown">
          <div>
            <dt>
              {t("Reserved for investments")}{" "}
              <InfoTip label={t("Reserved for investments")} title={t("Reserved for investments")}>
                {t("Money reserved for investments whose funding has not closed yet. If an investment does not go ahead, the money becomes available again.")}
              </InfoTip>
            </dt>
            <dd>
              {reserved > 0
                ? <PortalLink to="portfolio">{formatMoneyLabel(currency, reserved)} <NiIcon name="chevron-right" /></PortalLink>
                : formatMoneyLabel(currency, 0)}
            </dd>
          </div>
          {pending > 0 ? (
            <div>
              <dt>
                {t("Withdrawals in progress")}{" "}
                <InfoTip label={t("Withdrawals in progress")} title={t("Withdrawals in progress")}>
                  {t("Requested withdrawals and automatic returns waiting for the bank transfer. The amount is already set aside from your balance.")}
                </InfoTip>
              </dt>
              <dd>{formatMoneyLabel(currency, pending)}</dd>
            </div>
          ) : null}
        </dl>
        <div className="ap-actions">
          <button className="btn ap-add" disabled={addDisabled} onClick={onAdd} type="button"><NiIcon name="plus" /><span>{t("Add funds")}</span></button>
          <button className="btn btn-outline-light" disabled={withdrawDisabled} onClick={onWithdraw} type="button"><NiIcon name="wallet-out" /><span>{t("Withdraw")}</span></button>
        </div>
      </div>
      <div className="ap-return">
        <NiIcon name="clock" />
        <ReturnLine days={days} lots={lots} summary={summary} />
        <button aria-label={t("About automatic returns")} className="r70-return-info" onClick={onRules} title={t("Money that is not invested goes back to your verified bank account.")} type="button">
          <NiIcon name="info" />
        </button>
      </div>
    </section>
  );
}

function lotStatus(lot: BalanceLot, previewFrozen: boolean): { label: string; tone: "late" | "default" } | null {
  if (isFrozenLot(lot) || (previewFrozen && lot.bucket === "overdue")) {
    return { label: lot.bucket === "penalty_exhausted" ? "Used up by penalty" : lot.status === "frozen" && !lot.bucket.startsWith("penalty") ? "Frozen" : "Frozen, penalty charged", tone: "default" };
  }
  if (lot.bucket === "overdue") return { label: "Due back", tone: "late" };
  if (lot.bucket === "withdraw_only") return { label: "Last day", tone: "late" };
  return null;
}

function BalanceDetails({
  lots,
  orders,
  withdrawals,
  summaries,
  loanDeadlines,
  previewFrozen,
  onRules
}: {
  lots: BalanceLot[];
  orders: PrimaryOrderPortal[];
  withdrawals: PendingWithdrawal[];
  summaries: BalanceSummary[];
  loanDeadlines: Map<string, string>;
  previewFrozen: boolean;
  onRules: () => void;
}) {
  const t = useT();
  const rows = detailLots(lots);
  const showPenalty = rows.some((lot) => lot.penalized_amount_minor > 0);
  const penaltyCharged = summaries.filter((summary) => summary.penalty_charged_minor > 0);
  const empty = rows.length === 0 && orders.length === 0 && withdrawals.length === 0;
  return (
    <details className="card card-bordered ap-details p73-balance">
      <summary><span><strong>{t("Balance details")}</strong></span><NiIcon name="chevron-down" /></summary>
      <div className="ap-details-body">
        {empty ? <div className="bxm-empty"><NiIcon name="wallet" /><p>{t("No money on your account yet.")}</p></div> : null}
        {rows.length > 0 ? (
          <table className="p73-balance-table m82-balance-records" data-mobile-table="true">
            <thead>
              <tr>
                <th scope="col">{t("Received")}</th>
                <th scope="col">{t("Available")}</th>
                {showPenalty ? <th scope="col">{t("Penalty charged")}</th> : null}
                <th scope="col">
                  {t("Return date")}{" "}
                  <button aria-label={t("About automatic returns")} className="p73-inline-info" onClick={onRules} type="button"><NiIcon name="info" /></button>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((lot) => {
                const status = lotStatus(lot, previewFrozen);
                return (
                  <tr key={lot.id}>
                    <td data-m82-label={t("Received")}>{formatDate(lot.received_at)}<span className="wl-lot-source">{t(lotSourceLabel(lot.source_type))}</span></td>
                    <td className={lot.available_amount_minor === 0 ? "p73-zero" : ""} data-m82-label={t("Available")}><small>{lot.currency}</small><strong>{formatMoneyMinor(lot.available_amount_minor, lot.currency)}</strong></td>
                    {showPenalty ? (
                      <td className={lot.penalized_amount_minor === 0 ? "p73-zero" : ""} data-m82-label={t("Penalty charged")}><small>{lot.currency}</small><span>{formatMoneyMinor(lot.penalized_amount_minor, lot.currency)}</span></td>
                    ) : null}
                    <td data-m82-label={t("Return date")}>
                      {lot.bucket === "overdue" ? t("Due since {date}", { date: formatDate(lot.return_date) }) : formatDate(lot.return_date)}
                      {status ? <StatusTag className="wl-lot-tag" tone={status.tone}>{t(status.label)}</StatusTag> : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : null}
        {penaltyCharged.map((summary) => (
          <p className="wl-penalty-note" key={summary.currency}>
            {t("Penalty charged so far: {amount}. It is already deducted and not part of any balance shown.", { amount: formatMoneyLabel(summary.currency, summary.penalty_charged_minor) })}
          </p>
        ))}
        {orders.length > 0 ? (
          <div className="p73-reservations">
            <h3>{t("Investment reservations")}</h3>
            {orders.map((order) => {
              const deadline = loanDeadlines.get(order.loan_id);
              return (
                <PortalLink className="p73-reservation-row" key={order.id} params={{ loanId: order.loan_id }} to="loan">
                  <span className="p73-reservation-icon"><NiIcon name="briefcase" /></span>
                  <span className="p73-reservation-copy">
                    <strong>{order.loan_title}</strong>
                    <span>
                      {deadline
                        ? t("Funding closes {date}", { date: formatDate(deadline) })
                        : t("Reserved on {date}", { date: formatDate(order.allocated_at ?? order.created_at) })}
                    </span>
                  </span>
                  <strong>{formatMoneyLabel(order.currency, order.allocated_amount_minor)}</strong>
                  <NiIcon name="chevron-right" />
                </PortalLink>
              );
            })}
          </div>
        ) : null}
        {withdrawals.length > 0 ? (
          <div className="p73-reservations">
            <h3>{t("Withdrawals in progress")}</h3>
            <ul aria-label={t("Withdrawals in progress")} className="wl-plain-list">
              {withdrawals.map((withdrawal) => (
                <li className="p73-reservation-row wl-withdrawal-row" key={withdrawal.id}>
                  <span className="p73-reservation-icon"><NiIcon name={withdrawal.is_forced ? "undo" : "wallet-out"} /></span>
                  <span className="p73-reservation-copy">
                    <strong>
                      {withdrawal.is_forced
                        ? t("Automatic return to {iban}", { iban: maskIban(withdrawal.destination_iban) })
                        : t("Withdrawal to {iban}", { iban: maskIban(withdrawal.destination_iban) })}
                    </strong>
                    <span>{t("Requested {date} · Waiting for the bank transfer", { date: formatDate(withdrawal.requested_at) })}</span>
                  </span>
                  <strong>{formatMoneyLabel(withdrawal.currency, withdrawal.amount_minor)}</strong>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </details>
  );
}

export function AccountRulesDialog({ days, fxEnabled, onClose }: { days: number; fxEnabled: boolean; onClose: () => void }) {
  const t = useT();
  return (
    <Dialog onClose={onClose} title={t("How your account works")}>
      <ul className="bxm-rules mt-3">
        <li>{t("Your Banxum account holds money for investment. Money that is not invested earns no interest and goes back automatically to your verified bank account (IBAN) after {days} days.", { days })}</li>
        <li>{t("To invest, the money must have enough time left to cover the loan's remaining funding period. The oldest money is used first.")}</li>
        {fxEnabled ? <li>{t("A currency exchange does not restart this count.")}</li> : null}
        <li>{t("Loan repayments and recoveries are credited to your Banxum balance. You can invest them again or withdraw them.")}</li>
        <li>{t("Transfers must come from and go to bank accounts in your name.")}</li>
        <li>{t("Withdrawals usually reach your bank in 1–3 business days. There is no Banxum fee.")}</li>
        <li>{t("Without a verified bank account we cannot return the money. After 60 days (the legal limit) it enters penalty mode.")}</li>
      </ul>
      <p className="wl-rules-link"><PortalLink className="link" onNavigate={onClose} to="settings">{t("Manage your bank accounts in Profile & Settings")}</PortalLink></p>
    </Dialog>
  );
}

function ScreenFrame({ actions, children }: { actions?: ReactNode; children: ReactNode }) {
  const t = useT();
  return (
    <main className="ap-page r70-account">
      <PageHead actions={actions} title={t("Banxum account")} />
      {children}
    </main>
  );
}

export function AccountScreen({
  demoState,
  onAddBankAccount
}: {
  demoState: DemoAccountState;
  /** Opens today's add-bank-account dialog of the shell (PayoutIbanModal; S5's BankAccountDialog after the merge). */
  onAddBankAccount?: (currency: string) => void;
}) {
  const t = useT();
  useNumberFormat();
  const balancesQuery = useBalancesData();
  const ordersQuery = usePrimaryOrdersData();
  const loansQuery = useMarketplaceLoansData();
  const fxEnabled = useFxFeature().enabled;
  const frozen = useFrozenAccount().frozen;
  const readonly = Boolean(readReadonlyImpersonationToken());
  const [dialog, setDialog] = useState<OpenDialog>(null);
  const balances = balancesQuery.data;
  const viewTransactions = <ButtonLink className="ap-transactions" icon="tranx" to="transactions">{t("View transactions")}</ButtonLink>;

  if (!balances) {
    return (
      <ScreenFrame actions={viewTransactions}>
        {balancesQuery.isError ? (
          <EmptyState
            actions={<button className="btn btn-outline-light" onClick={() => void balancesQuery.refetch()} type="button">{t("Try again")}</button>}
            icon="alert-circle"
            title={t("We could not load your account")}
          >
            {t("Your balances are not available right now. Try again in a moment.")}
          </EmptyState>
        ) : (
          <div className="bxm-empty" role="status"><NiIcon name="loader" /><p>{t("Loading your account...")}</p></div>
        )}
      </ScreenFrame>
    );
  }

  const days = autoReturnDays(balances.auto_return_after_days);
  const summaries = orderedSummaries(balances.summaries);
  const orders = reservedOrders(ordersQuery.data?.orders);
  const withdrawals = balances.pending_withdrawals ?? [];
  const notices = accountNotices(balances);
  const loanDeadlines = new Map((loansQuery.data ?? []).filter((loan) => loan.funding_deadline).map((loan) => [loan.loan_id, loan.funding_deadline as string]));
  const previewFrozen = isFixturePreview && demoState === "frozen";
  const openWithdraw = readonly ? undefined : (currency: string) => setDialog({ kind: "withdraw", currency });
  const openRules = () => setDialog({ kind: "rules" });
  const addBankAccount = readonly || !onAddBankAccount ? undefined : onAddBankAccount;

  return (
    <ScreenFrame actions={viewTransactions}>
      {notices.length > 0 ? (
        <section aria-label={t("Account notices")} className="ov-updates ap-alerts">
          {notices.map((notice) => <AccountNoticeAlert days={days} key={`${notice.kind}-${notice.currency}`} notice={notice} onAddBankAccount={addBankAccount} onWithdraw={openWithdraw} />)}
        </section>
      ) : null}
      {summaries.length === 0 ? (
        <EmptyState
          actions={<button className="btn ap-add" disabled={frozen || readonly} onClick={() => setDialog({ kind: "deposit", currency: "EUR" })} type="button"><NiIcon name="plus" /><span>{t("Add funds")}</span></button>}
          icon="wallet"
          title={t("No balances yet")}
        >
          {t("Deposits, repayments, recoveries and sale proceeds appear here once they are booked.")}
        </EmptyState>
      ) : (
        <div className="ap-accounts">
          {summaries.map((summary) => (
            <AccountCard
              addDisabled={frozen || readonly}
              days={days}
              key={summary.currency}
              lots={balances.lots}
              onAdd={() => setDialog({ kind: "deposit", currency: summary.currency })}
              onRules={openRules}
              onWithdraw={() => setDialog({ kind: "withdraw", currency: summary.currency })}
              orders={orders}
              summary={summary}
              withdrawDisabled={readonly}
              withdrawals={withdrawals}
            />
          ))}
        </div>
      )}
      <BalanceDetails
        loanDeadlines={loanDeadlines}
        lots={balances.lots}
        onRules={openRules}
        orders={orders}
        previewFrozen={previewFrozen}
        summaries={summaries}
        withdrawals={withdrawals}
      />
      <div className="ap-foot">
        <button className="ap-how btn btn-outline-light" onClick={openRules} type="button"><NiIcon name="info" /><span>{t("How your account works")}</span></button>
        <span>{t("Money held here does not earn interest.")}</span>
      </div>
      {dialog?.kind === "deposit" ? <AddFundsDialog currency={dialog.currency} onClose={() => setDialog(null)} /> : null}
      {dialog?.kind === "withdraw" ? <WithdrawDialog balances={balances} currency={dialog.currency} onAddBankAccount={addBankAccount} onClose={() => setDialog(null)} /> : null}
      {dialog?.kind === "rules" ? <AccountRulesDialog days={days} fxEnabled={fxEnabled} onClose={() => setDialog(null)} /> : null}
    </ScreenFrame>
  );
}
