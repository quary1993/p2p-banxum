// IP of Webby-Soft SRL.
/*
 * Add funds (design #/account, data-action="deposit": .p73-modal): the bank details of the
 * investor's deposit account per currency from GET /investor/portal/deposit-instructions/, with copy
 * buttons, the Swiss QR-bill for CHF and the personal reference. No "simulate deposit" tools.
 * Texts: transfers come from a bank account in the investor's name, unclear deposits are checked by
 * hand (U33-DEC-05; not "payments from other accounts are returned"); the operator line names
 * Garanta (U33-DEC-34).
 */
import { useId, useState } from "react";

import type { DepositInstruction } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { autoReturnDays } from "../../../investorPortal/balanceAgeing";
import { useBalancesData, useDepositInstructionsData } from "../../../investorPortal/data";
import { brandDisplayName, operatorName } from "../../brand";
import { NiIcon } from "../../components";
import { CopyButton } from "./parts/CopyButton";
import { groupIban } from "./parts/iban";
import { useQrDataUrl } from "./parts/qrBill";
import { WalletDialog } from "./parts/WalletDialog";
import { currencyRank } from "./accountModel";
import "./wallet.css";

function BankRow({ label, value, copyLabel, primary = false, note, copyable = true }: { label: string; value: string; copyLabel?: string; primary?: boolean; note?: string; copyable?: boolean }) {
  return (
    <div className="p73-bank-row">
      <div>
        <label>{label}</label>
        <strong className={primary ? "p73-primary-iban" : ""}>{value}</strong>
        {note ? <small className="p79-brand-identity">{note}</small> : null}
      </div>
      {value && copyable ? <CopyButton label={copyLabel ?? label} value={value} /> : null}
    </div>
  );
}

// The design's "Download QR-bill" button (the Swiss QR code of the deposit account, as an image).
function QrBill({ payload, currency }: { payload: string; currency: string }) {
  const t = useT();
  const dataUrl = useQrDataUrl(payload);
  if (!dataUrl) return null;
  return (
    <a className="p73-download" download={`qr-bill-${currency.toLowerCase()}.png`} href={dataUrl}>
      <NiIcon name="qr" />
      <span>{t("Download QR-bill")}</span>
    </a>
  );
}

function InstructionBody({ instruction, returnDays, referenceRule, verifiedIban }: { instruction: DepositInstruction; returnDays: number; referenceRule: string; verifiedIban?: string }) {
  const t = useT();
  const brandLine = t("{brand} is a brand of {operator}.", { brand: brandDisplayName(), operator: operatorName });
  const missing = t("Not configured yet");
  // The design's transfer method: SEPA for EUR, the Swiss QR-bill for CHF when the account has one.
  const method = instruction.currency === "EUR" ? t("SEPA credit transfer") : instruction.qr_bill_payload ? t("QR-bill (QR reference)") : "";
  return (
    <>
      {instruction.is_configured ? null : (
        <div className="alert alert-danger alert-icon wl-alert" role="alert">
          <NiIcon name="alert-circle" />
          <strong className="bxm-signal-text">{t("Do not send money yet.")}</strong>{" "}
          {t("This deposit account is not fully set up. Wait until the bank details are confirmed.")}
        </div>
      )}
      <div className="p73-bank-data">
        <BankRow copyable={Boolean(instruction.account_holder_name)} copyLabel={t("beneficiary")} label={t("Beneficiary")} note={brandLine} value={instruction.account_holder_name || missing} />
        <BankRow copyable={Boolean(instruction.iban)} label={t("IBAN")} primary value={instruction.iban ? groupIban(instruction.iban) : missing} />
        {instruction.qr_iban ? <BankRow label={t("QR-IBAN")} value={groupIban(instruction.qr_iban)} /> : null}
        {instruction.bic ? <BankRow label={t("BIC")} value={instruction.bic} /> : null}
        <BankRow copyLabel={t("your personal reference")} label={t("Your personal reference")} value={instruction.payment_reference} />
      </div>
      <p className="p73-transfer-note">{t("Use your reference with every transfer so we can identify your payment.")}</p>
      {instruction.qr_bill_payload ? <QrBill currency={instruction.currency} payload={instruction.qr_bill_payload} /> : null}
      <details className="p73-more">
        <summary>{t("Transfer details")} <NiIcon name="chevron-down" /></summary>
        <div>
          <dl>
            {method ? <div><dt>{t("Method")}</dt><dd>{method}</dd></div> : null}
            {instruction.bank_name ? <div><dt>{t("Bank")}</dt><dd>{instruction.bank_name}</dd></div> : null}
            {verifiedIban ? <div><dt>{t("Your verified IBAN")}</dt><dd>{groupIban(verifiedIban)}</dd></div> : null}
          </dl>
          {/* U33-DEC-05: deposits we cannot match are checked by hand (the design returns them). */}
          <p>{t("Transfer only from your verified bank account. Deposits we cannot match to you are checked by hand before they become available.")}</p>
          {referenceRule ? <p>{referenceRule}</p> : null}
          {instruction.notes ? <p>{instruction.notes}</p> : null}
          <p>{t("Uninvested funds return after {days} days. Money held here earns no interest.", { days: returnDays })}</p>
        </div>
      </details>
    </>
  );
}

export function AddFundsDialog({ currency: initialCurrency, onClose }: { currency: string; onClose: () => void }) {
  const t = useT();
  const titleId = useId();
  const instructionsQuery = useDepositInstructionsData();
  const balances = useBalancesData().data;
  const returnDays = autoReturnDays(balances?.auto_return_after_days);
  const verifiedIbanFor = (currency: string) =>
    balances?.payout_instructions.find((item) => item.currency === currency && item.is_verified_usable)?.destination_iban;
  const [chosen, setChosen] = useState(initialCurrency);
  const payload = instructionsQuery.data;
  const instructions = [...(payload?.instructions ?? [])].sort((a, b) => currencyRank(a.currency) - currencyRank(b.currency));
  const currency = instructions.some((item) => item.currency === chosen) ? chosen : instructions[0]?.currency ?? chosen;
  const instruction = instructions.find((item) => item.currency === currency);
  return (
    <WalletDialog className="p73-modal" labelledBy={titleId} onClose={onClose}>
      <div className="modal-body modal-body-md">
        <h2 id={titleId}>{t("Add funds")}</h2>
        <p className="p73-intro">{t("Transfer from your verified bank account.")}</p>
        {instructionsQuery.isError && !payload ? (
          <div className="bxm-empty wl-dialog-state" role="alert">
            <NiIcon name="alert-circle" />
            <p>{t("We could not load the bank details. Try again before you send money.")}</p>
            <button className="btn btn-outline-light btn-sm" onClick={() => void instructionsQuery.refetch()} type="button">{t("Try again")}</button>
          </div>
        ) : !payload ? (
          <div className="bxm-empty wl-dialog-state" role="status"><NiIcon name="loader" /><p>{t("Loading the bank details...")}</p></div>
        ) : (
          <>
            {instructions.length > 1 ? (
              <div aria-label={t("Currency")} className="p73-currency" role="group">
                {instructions.map((item) => (
                  <button aria-pressed={item.currency === currency} className={item.currency === currency ? "active" : ""} key={item.currency} onClick={() => setChosen(item.currency)} type="button">
                    {item.currency}
                  </button>
                ))}
              </div>
            ) : null}
            {instruction ? (
              <InstructionBody instruction={instruction} referenceRule={payload.reference_rule} returnDays={returnDays} verifiedIban={verifiedIbanFor(instruction.currency)} />
            ) : (
              <div className="bxm-empty wl-dialog-state"><NiIcon name="info" /><p>{t("Deposits in {currency} are not open yet.", { currency })}</p></div>
            )}
          </>
        )}
      </div>
    </WalletDialog>
  );
}
