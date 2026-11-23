// IP of Webby-Soft SRL.
// Profile & Settings -> Bank accounts (design: .ps-bank-grid, one .ps-panel.ps-bank per account).
// U33-DEC-05: several accounts in the investor's name, "Verified" / "Pending verification" shown
// separately, and one default return account per currency (the account money going back to the
// bank is sent to). Adding an account ("Change" in the design) and choosing the return account
// use the email code + PIN; a new IBAN never replaces a verified one by itself. Repayments are
// credited to the Banxum balance, not to these accounts (U33-DEC-02). No 48-hour pause.
import { useState } from "react";

import type { PayoutInstruction } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview, useBalancesData } from "../../../../investorPortal/data";
import { formatDate } from "../../../../investorPortal/format";
import { brandDisplayName } from "../../../brand";
import { Button, NiIcon, PortalLink } from "../../../components";
import { BankAccountDialog } from "../parts/BankAccountDialog";
import { DefaultReturnAccountDialog } from "../parts/DefaultReturnAccountDialog";
import { formatIban } from "../parts/format";
import { Notice, PsPanel, PsStatus } from "../parts/ui";
import type { AccountData } from "./useAccountData";

/** The design's order: EUR, then CHF (as everywhere in the investor area). */
const CURRENCIES = ["EUR", "CHF"];

function BankPanel({ instruction, readonly, onChange, onUseForReturns }: { instruction: PayoutInstruction; readonly: boolean; onChange: () => void; onUseForReturns: () => void }) {
  const t = useT();
  const verified = instruction.verification_status === "verified";
  return (
    <PsPanel className="ps-bank" title={t("{currency} account", { currency: instruction.currency })}>
      <div className="ps-panel-body">
        {/* Design: bank name (ps-bank-title), IBAN and account holder. 18.3: the bank name comes from
            the SIX bank master for CH and LI IBANs, else the investor typed it; left out when unknown. */}
        {instruction.bank_name ? (
          <div className="ps-bank-title">
            <span className="ps-bank-icon"><NiIcon name="building" /></span>
            <strong>{instruction.bank_name}</strong>
          </div>
        ) : null}
        <dl className="ps-bank-facts">
          <div>
            <dt>{t("IBAN")}</dt>
            <dd><span className="bxm-iban">{formatIban(instruction.destination_iban)}</span></dd>
          </div>
          <div>
            <dt>{t("Account holder")}</dt>
            <dd>{instruction.destination_account_name}</dd>
          </div>
        </dl>
        {instruction.is_default_return ? (
          <p className="ps-panel-note">{t("Money that goes back to your bank in {currency} is sent to this account.", { currency: instruction.currency })}</p>
        ) : null}
        <div className="ps-bank-footer">
          {verified ? (
            <PsStatus>{instruction.verified_at ? t("Verified · {date}", { date: formatDate(instruction.verified_at) }) : t("Verified")}</PsStatus>
          ) : (
            <PsStatus muted>{t("Pending verification")}</PsStatus>
          )}
          <span className="acc-bank-buttons">
            {verified && !instruction.is_default_return ? (
              <Button disabled={readonly} onClick={onUseForReturns} size="sm">{t("Use for returns")}</Button>
            ) : null}
            <Button aria-label={t("Change {currency} bank account", { currency: instruction.currency })} disabled={readonly} onClick={onChange} size="sm">{t("Change")}</Button>
          </span>
        </div>
      </div>
    </PsPanel>
  );
}

function EmptyBankPanel({ currency, disabled, onAdd }: { currency: string; disabled: boolean; onAdd: () => void }) {
  const t = useT();
  return (
    <PsPanel className="ps-bank acc-bank-empty" title={t("{currency} account", { currency })}>
      <div className="ps-panel-body">
        <p className="ps-panel-note">{t("No {currency} bank account yet. Add one in your name to withdraw {currency} and to receive money that goes back to your bank.", { currency })}</p>
        <div className="ps-bank-footer">
          <span />
          <Button disabled={disabled} onClick={onAdd}>{t("Add {currency} account", { currency })}</Button>
        </div>
      </div>
    </PsPanel>
  );
}

export function BankAccountsTab({ account }: { account: AccountData }) {
  const t = useT();
  const balances = useBalancesData();
  const [dialog, setDialog] = useState<{ currency?: string } | null>(null);
  const [returnAccount, setReturnAccount] = useState<PayoutInstruction | null>(null);
  const instructions = [...(balances.data?.payout_instructions ?? [])].sort(
    (a, b) => CURRENCIES.indexOf(a.currency) - CURRENCIES.indexOf(b.currency) || a.created_at.localeCompare(b.created_at)
  );
  const missing = CURRENCIES.filter((currency) => !instructions.some((instruction) => instruction.currency === currency));
  const loading = !isFixturePreview && balances.isPending;

  return (
    <>
      <div className="ps-section-intro">
        <p>{t("Bank accounts in your name, for withdrawals and for money that goes back to your bank. Repayments are credited to your {brand} balance.", { brand: brandDisplayName() })}</p>
        <PortalLink className="ps-text-link" to="balances">
          {t("{brand} account", { brand: brandDisplayName() })}
          <NiIcon name="arrow-right" />
        </PortalLink>
      </div>
      {balances.isError && !isFixturePreview ? (
        <Notice action={<Button onClick={() => void balances.refetch()} size="sm">{t("Retry")}</Button>} title={t("Could not load your bank accounts")} tone="danger">
          {t("Check your connection and try again.")}
        </Notice>
      ) : loading ? (
        <p className="ps-intro" role="status">{t("Loading your bank accounts...")}</p>
      ) : (
        <div className="ps-bank-grid">
          {/* Currency by currency: its accounts, or the empty panel when it has none. */}
          {CURRENCIES.flatMap((currency) =>
            missing.includes(currency)
              ? [<EmptyBankPanel currency={currency} disabled={account.readonly} key={currency} onAdd={() => setDialog({ currency })} />]
              : instructions.filter((instruction) => instruction.currency === currency).map((instruction) => (
                  <BankPanel
                    instruction={instruction}
                    key={instruction.id}
                    onChange={() => setDialog({ currency: instruction.currency })}
                    onUseForReturns={() => setReturnAccount(instruction)}
                    readonly={account.readonly}
                  />
                ))
          )}
          {instructions.filter((instruction) => !CURRENCIES.includes(instruction.currency)).map((instruction) => (
            <BankPanel
              instruction={instruction}
              key={instruction.id}
              onChange={() => setDialog({ currency: instruction.currency })}
              onUseForReturns={() => setReturnAccount(instruction)}
              readonly={account.readonly}
            />
          ))}
        </div>
      )}
      <div className="acc-bank-actions">
        <p className="ps-bank-notice">
          <NiIcon name="info" />
          <span>{t("A new bank account shows Pending verification until our team has verified it; you cannot use it for withdrawals before. Your verified accounts stay usable meanwhile. Money that goes back to your bank is sent to your return account in that currency.")}</span>
        </p>
        <Button disabled={account.readonly} icon="plus" onClick={() => setDialog({})}>{t("Add a bank account")}</Button>
      </div>
      {dialog ? <BankAccountDialog currency={dialog.currency} holderName={account.name} onClose={() => setDialog(null)} /> : null}
      {returnAccount ? <DefaultReturnAccountDialog instruction={returnAccount} onClose={() => setReturnAccount(null)} /> : null}
    </>
  );
}
