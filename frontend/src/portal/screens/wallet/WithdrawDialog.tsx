// IP of Webby-Soft SRL.
/*
 * Withdraw (design #/account, data-action="withdraw": .p73-modal): amount within the withdrawable
 * balance, a verified bank account of the currency, review, then today's confirmation (email code +
 * PIN, ACC-DEC-009 until U33-DEC-01) and the result. Same request as before: POST
 * /ledger/withdrawal-requests/ with one idempotency key per withdrawal intent (audit A-41).
 * Texts: "usually 1–3 business days" and "No Banxum fees" (U33-DEC-35); "Verified" / "Pending
 * verification" (U33-DEC-05). Reservations are never part of the withdrawable amount.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";

import { ActionEnum, useV1LedgerWithdrawalRequestsCreate, type InvestorBalancePortal } from "../../../api/generated/banxumApi";
import { intentIdempotencyKey } from "../../../api/client/idempotency";
import { useT } from "../../../i18n";
import { payoutInstructionState, withdrawableMinor } from "../../../investorPortal/accountState";
import { isFixturePreview } from "../../../investorPortal/data";
import { formatMoneyLabel, formatMoneyMinor, parseMoneyInputToMinorUnits, useNumberFormat } from "../../../investorPortal/format";
import { NiIcon, usePortalNav } from "../../components";
import { orderedSummaries } from "./accountModel";
import { errorMessage } from "./parts/downloads";
import { groupIban } from "./parts/iban";
import { SensitiveFields } from "./parts/SensitiveConfirm";
import { sensitiveReady, useAutoRequestCode, useSensitiveCode } from "./parts/sensitiveCode";
import { WalletDialog } from "./parts/WalletDialog";
import "./wallet.css";

type Step = "form" | "confirm" | "done";

export function WithdrawDialog({
  currency: initialCurrency,
  balances,
  onAddBankAccount,
  onClose
}: {
  currency: string;
  balances: Pick<InvestorBalancePortal, "summaries" | "payout_instructions">;
  /** Today's add-bank-account dialog (shell); without it the link opens Profile & Settings. */
  onAddBankAccount?: (currency: string) => void;
  onClose: () => void;
}) {
  const t = useT();
  useNumberFormat();
  const nav = usePortalNav();
  const queryClient = useQueryClient();
  const titleId = useId();
  const summaries = orderedSummaries(balances.summaries);
  const [currency, setCurrency] = useState(summaries.some((item) => item.currency === initialCurrency) ? initialCurrency : summaries[0]?.currency ?? initialCurrency);
  const [step, setStep] = useState<Step>("form");
  const [amount, setAmount] = useState("");
  const [showAmountError, setShowAmountError] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const summary = summaries.find((item) => item.currency === currency);
  const maxMinor = withdrawableMinor(summary);
  const accounts = balances.payout_instructions.filter((instruction) => instruction.currency === currency);
  const verified = accounts.filter((instruction) => instruction.is_verified_usable);
  const [accountId, setAccountId] = useState("");
  // The default return account first (U33-DEC-05), then the other verified accounts.
  const account = verified.find((instruction) => instruction.id === accountId) ?? verified.find((instruction) => instruction.is_default_return) ?? verified[0];
  const parsed = parseMoneyInputToMinorUnits(amount, currency);
  const amountMinor = parsed.amountMinor;
  const amountError = parsed.error
    ?? (amountMinor <= 0 ? t("Enter the amount to withdraw.") : amountMinor > maxMinor ? t("You can withdraw at most {amount}.", { amount: formatMoneyLabel(currency, maxMinor) }) : undefined);
  const sensitive = useSensitiveCode(ActionEnum.withdrawal);
  useAutoRequestCode(sensitive, step === "confirm");
  const mutation = useV1LedgerWithdrawalRequestsCreate();

  const changeCurrency = (next: string) => {
    setCurrency(next);
    setAccountId("");
    setShowAmountError(false);
  };
  const review = (event: FormEvent) => {
    event.preventDefault();
    setShowAmountError(true);
    if (amountError || !account) return;
    setError("");
    setStep("confirm");
  };
  const submit = () => {
    setError("");
    if (!account) return;
    if (isFixturePreview) {
      if (sensitive.pin.previewAccepts()) setStep("done");
      return;
    }
    if (!sensitive.codeId) {
      setError(t("Ask for an email code first."));
      return;
    }
    const intent = {
      amount_minor: amountMinor,
      currency,
      destination_iban: account.destination_iban,
      destination_account_name: account.destination_account_name
    };
    mutation.mutate(
      {
        data: {
          ...intent,
          // One key per withdrawal intent: a retry after a timeout is recognised by the server and
          // not paid out twice. A new amount or account gets a new key.
          idempotency_key: intentIdempotencyKey("investor-withdrawal", intent),
          sensitive_action_code_id: sensitive.codeId,
          sensitive_action_code: code,
          pin: sensitive.pin.value
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setStep("done");
        },
        onError: (failure) => {
          if (sensitive.pin.handleError(failure)) return;
          setError(errorMessage(failure));
        }
      }
    );
  };
  const goToBankAccounts = (event: { preventDefault: () => void }) => {
    event.preventDefault();
    onClose();
    if (verified.length === 0 && onAddBankAccount) onAddBankAccount(currency);
    else nav.go("settings");
  };
  // U33-DEC-35: 1–3 business days (the design writes 1–2).
  const timing = t("Usually 1–3 business days · No Banxum fees");
  const amountLabel = formatMoneyLabel(currency, amountMinor);

  if (step === "done") {
    return (
      <WalletDialog className="p73-modal" labelledBy={titleId} onClose={onClose}>
        <div className="modal-body modal-body-md">
          <h2 id={titleId}>{t("Withdrawal requested")}</h2>
          <p className="p73-intro">{t("{amount} to your bank account ending {last}.", { amount: amountLabel, last: account?.destination_iban.replace(/\s+/g, "").slice(-4) ?? "" })}</p>
          <div className="wl-result" role="status">
            <NiIcon name="check-circle" />
            <p>{t("We have received your request. Withdrawals usually reach your bank in 1–3 business days. You get an email when the transfer is sent.")}</p>
          </div>
          <div className="p73-modal-actions">
            <button className="btn p73-next" onClick={onClose} type="button">{t("Done")}</button>
          </div>
        </div>
      </WalletDialog>
    );
  }

  if (step === "confirm" && account) {
    return (
      <WalletDialog busy={mutation.isPending} className="p73-modal" labelledBy={titleId} onClose={onClose}>
        <div className="modal-body modal-body-md">
          <h2 id={titleId}>{t("Confirm withdrawal")}</h2>
          <p className="p73-intro">{t("To your verified bank account.")}</p>
          <div className="p73-confirm-summary">
            <div className="p73-list-price">
              <span>{t("Amount to withdraw")}</span>
              <strong><small>{currency}</small>{formatMoneyMinor(amountMinor, currency)}</strong>
            </div>
            <div className="p73-confirm-bank">
              <strong>{account.destination_account_name}</strong>
              <b>{groupIban(account.destination_iban)}</b>
            </div>
          </div>
          <form
            className="bxm-code-form"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              // Submits of the PIN dialogs (create / forgot PIN) bubble here through the React tree.
              if (event.target !== event.currentTarget) return;
              if (sensitiveReady(sensitive, code) && !mutation.isPending) submit();
            }}
          >
            <SensitiveFields code={sensitive} error={error} onChange={setCode} onContinue={submit} value={code} />
            <p className="p73-confirm-note">{timing}</p>
            <div className="p73-modal-actions">
              <button className="btn p73-back" disabled={mutation.isPending} onClick={() => setStep("form")} type="button">{t("Back")}</button>
              <button className="btn p73-confirm" disabled={!sensitiveReady(sensitive, code) || mutation.isPending} type="submit">
                {mutation.isPending ? t("Sending...") : t("Confirm withdrawal")}
              </button>
            </div>
          </form>
        </div>
      </WalletDialog>
    );
  }

  const invalid = showAmountError && Boolean(amountError);
  return (
    <WalletDialog className="p73-modal" labelledBy={titleId} onClose={onClose}>
      <div className="modal-body modal-body-md">
        <h2 id={titleId}>{t("Withdraw")}</h2>
        <p className="p73-intro">{t("To your verified bank account.")}</p>
        <form noValidate onSubmit={review}>
          {summaries.length > 1 ? (
            <div aria-label={t("Currency")} className="p73-currency" role="group">
              {summaries.map((item) => (
                <button aria-pressed={item.currency === currency} className={item.currency === currency ? "active" : ""} key={item.currency} onClick={() => changeCurrency(item.currency)} type="button">
                  {item.currency}
                </button>
              ))}
            </div>
          ) : null}
          <div className="p73-amount-head">
            <label htmlFor="wl-withdraw-amount">{t("Amount to withdraw")}</label>
            <span>{t("Available {amount}", { amount: formatMoneyLabel(currency, maxMinor) })}</span>
          </div>
          <div className="p73-amount-field">
            <span>{currency}</span>
            <input
              aria-describedby="wl-withdraw-error"
              aria-invalid={invalid || undefined}
              autoComplete="off"
              className={`form-control form-control-lg bxm-amount ${invalid ? "is-invalid" : ""}`.trim()}
              data-autofocus
              id="wl-withdraw-amount"
              inputMode="decimal"
              onChange={(event) => {
                setAmount(event.target.value.replace(/[^0-9.,'’\s]/g, ""));
                setShowAmountError(false);
              }}
              placeholder={formatMoneyMinor(0, currency)}
              value={amount}
            />
            <div className="invalid-feedback" id="wl-withdraw-error">{invalid ? amountError : ""}</div>
          </div>
          <div className="p73-destination-head">
            <span>{t("To")}</span>
            <a className="link" href={nav.hrefFor("settings")} onClick={goToBankAccounts}>{verified.length > 0 ? t("Change") : t("Add a bank account")}</a>
          </div>
          {verified.length > 1 ? (
            <select aria-label={t("Bank account")} className="form-select wl-account-select" onChange={(event) => setAccountId(event.target.value)} value={account?.id ?? ""}>
              {verified.map((instruction) => (
                <option key={instruction.id} value={instruction.id}>{`${instruction.destination_account_name} · ${groupIban(instruction.destination_iban)}`}</option>
              ))}
            </select>
          ) : null}
          {account ? (
            <div className="p73-destination">
              <strong className="p73-holder">{account.destination_account_name} <NiIcon label={t("Verified")} name="check" /></strong>
              <b>{groupIban(account.destination_iban)}</b>
            </div>
          ) : (
            <div className="p73-destination wl-destination-missing" role="status">
              <strong>{t("No verified {currency} bank account yet", { currency })}</strong>
              <span>{t("Add a bank account in your name in Profile & Settings. You can withdraw once it is verified.")}</span>
              {accounts.map((instruction) => (
                <b key={instruction.id}>{`${groupIban(instruction.destination_iban)} · ${t(payoutInstructionState(instruction).label)}`}</b>
              ))}
            </div>
          )}
          <p className="p73-timing">{timing}</p>
          <div className="p73-modal-actions">
            <button className="btn p73-back" onClick={onClose} type="button">{t("Cancel")}</button>
            <button className="btn p73-next" disabled={!account} type="submit">{t("Continue")} <NiIcon name="arrow-right" /></button>
          </div>
        </form>
      </div>
    </WalletDialog>
  );
}
