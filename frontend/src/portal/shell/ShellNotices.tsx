// IP of Webby-Soft SRL.
/*
 * Notices above every investor screen (InvestorShell): sign-out failure, preview data, the superadmin
 * read-only view and the frozen account (PAY-DEC-022). They use the design's alert component
 * (.ov-updates > .alert, as on the Overview and Account pages); actions are the design's inline
 * alert links. Styles: portal/u33/u33-overrides.css, section 3 ("Shell notices").
 */
import type { ReactNode } from "react";

import { useT } from "../../i18n";
import { joinWithAnd, type FrozenAccount } from "../../investorPortal/accountState";
import { formatMoneyLabel } from "../../investorPortal/format";
import { NiIcon } from "../components";

export type ShellNoticeTone = "danger" | "warning" | "info";

export function ShellNotice({
  tone,
  icon,
  title,
  children,
  actions
}: {
  tone: ShellNoticeTone;
  /** Nioicon glyph name. */
  icon: string;
  title: ReactNode;
  children?: ReactNode;
  /** Inline actions (buttons with the class "alert-link"). */
  actions?: ReactNode;
}) {
  return (
    <div className={`alert alert-${tone} alert-icon u33-shell-notice`} role={tone === "danger" ? "alert" : "status"}>
      <NiIcon name={icon} />
      <strong className="bxm-signal-text">{title}</strong>
      {children ? <> {children}</> : null}
      {actions ? <span className="u33-shell-notice-actions">{actions}</span> : null}
    </div>
  );
}

/** The list of notices; renders nothing without notices. */
export function ShellNotices({ children }: { children: ReactNode[] }) {
  const t = useT();
  if (children.length === 0) return null;
  return (
    <section aria-label={t("Account notices")} className="ov-updates u33-shell-notice-list">
      {children}
    </section>
  );
}

/**
 * A blocked account (lots with `blocks_financial_actions`; no daily penalty since U33-DEC-04):
 * what is blocked and what to do. `onAddBankAccount` opens the
 * shell's bank-account dialog; `onOpenAccount` leads to the Account page.
 */
export function FrozenAccountNotice({
  account,
  fxEnabled = false,
  onAddBankAccount,
  onOpenAccount
}: {
  account: FrozenAccount;
  /** Currency exchange is off (U33-DEC-33); when an environment switches it on, it is blocked too. */
  fxEnabled?: boolean;
  onAddBankAccount?: () => void;
  onOpenAccount?: () => void;
}) {
  const t = useT();
  if (!account.frozen) return null;
  const amounts = account.amounts.map((amount) => formatMoneyLabel(amount.currency, amount.amountMinor));
  const missing = account.currenciesWithoutVerifiedIban;
  const what = amounts.length > 0 ? joinWithAnd(amounts) : t("Money on your account");
  const parts = [
    missing.length > 0
      ? t("{what} passed the 60-day holding limit, and there is no verified bank account to return it to.", { what })
      : t("{what} passed the 60-day holding limit.", { what }),
    fxEnabled ? t("Investing, currency exchange and resale are blocked.") : t("Investing and resale are blocked."),
    missing.length > 1
      ? t("To unlock them, add a bank account in your name for {currencies}. When we have verified them, we send the money to them.", { currencies: joinWithAnd(missing) })
      : missing.length === 1
        ? t("To unlock them, add a bank account in your name for {currencies}. When we have verified it, we send the money to it.", { currencies: missing[0] })
        : t("Your bank account is verified: withdraw the money now, or we send it to that account."),
    t("Your investments, documents and statements remain available.")
  ].filter(Boolean);
  return (
    <ShellNotice
      actions={
        <>
          {onAddBankAccount ? <button className="alert-link" onClick={onAddBankAccount} type="button">{t("Add a bank account")}</button> : null}
          {onOpenAccount ? <button className="alert-link" onClick={onOpenAccount} type="button">{t("Open Account")}</button> : null}
        </>
      }
      icon="lock"
      title={t("Financial actions are frozen")}
      tone="danger"
    >
      {parts.join(" ")}
    </ShellNotice>
  );
}
