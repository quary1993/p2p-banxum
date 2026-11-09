// IP of Webby-Soft SRL.
// Profile & Settings -> Bank accounts (design: .ps-bank-grid, one .ps-panel.ps-bank per account).
// Today's payout IBANs per currency with "Verified" / "Pending verification" (U33-DEC-05). Adding an
// account uses today's email code + PIN flow; a new IBAN never replaces a verified one by itself.
// Repayments are credited to the Banxum balance, not to these accounts (U33-DEC-02). No default
// return account and no 48-hour pause (Phase 17.2, U33-DEC-05).
import { useState } from "react";

import type { PayoutInstruction } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview, useBalancesData } from "../../../../investorPortal/data";
import { formatDate } from "../../../../investorPortal/format";
import { brandDisplayName } from "../../../brand";
import { Button, NiIcon, PortalLink } from "../../../components";
import { BankAccountDialog } from "../parts/BankAccountDialog";
import { formatIban } from "../parts/format";
import { Notice, PsPanel, PsStatus } from "../parts/ui";
import type { AccountData } from "./useAccountData";

const CURRENCIES = ["CHF", "EUR"];

function BankPanel({ instruction }: { instruction: PayoutInstruction }) {
  const t = useT();
  return (
    <PsPanel className="ps-bank" title={t("{currency} account", { currency: instruction.currency })}>
      <div className="ps-panel-body">
        {/* Design: bank name, IBAN and account holder. The platform does not store the bank name. */}
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
        <div className="ps-bank-footer">
          {instruction.is_verified_usable ? (
            <PsStatus>{instruction.verified_at ? t("Verified · {date}", { date: formatDate(instruction.verified_at) }) : t("Verified")}</PsStatus>
          ) : (
            <PsStatus muted>{t("Pending verification")}</PsStatus>
          )}
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
          {instructions.map((instruction) => <BankPanel instruction={instruction} key={instruction.id} />)}
          {missing.map((currency) => (
            <EmptyBankPanel currency={currency} disabled={account.readonly} key={currency} onAdd={() => setDialog({ currency })} />
          ))}
        </div>
      )}
      <div className="acc-bank-actions">
        <p className="ps-bank-notice">
          <NiIcon name="info" />
          <span>{t("A new bank account shows Pending verification until our team has verified it; you cannot use it for withdrawals before. Your verified accounts stay usable meanwhile.")}</span>
        </p>
        <Button disabled={account.readonly} icon="plus" onClick={() => setDialog({})}>{t("Add a bank account")}</Button>
      </div>
      {dialog ? <BankAccountDialog currency={dialog.currency} holderName={account.name} onClose={() => setDialog(null)} /> : null}
    </>
  );
}
