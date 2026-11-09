// IP of Webby-Soft SRL.
// "Add a bank account" (design: .modal.p73-modal.r75-profile-modal, "New EUR bank account"), opened
// from Profile & Settings -> Bank accounts, the account menu's shell dialog and the frozen-account
// banner. Today's flow (ACC-DEC-009 / PAY-DEC-022): currency, IBAN and account holder, then the
// email code and the PIN; the new IBAN is added as "Pending verification" and becomes usable only
// after the team has verified it (U33-DEC-05: no 48-hour pause, no default-account choice yet).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ActionEnum, useV1LedgerPayoutInstructionsCreate } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useAutoSend, useFlowEmailCode, pinErrorText } from "../../../../investorPortal/pinFlows";
import { formatPinLockTime } from "../../../../investorPortal/pinRules";
import { useSensitivePin } from "../../../../investorPortal/pinState";
import { Button, Dialog, NiIcon } from "../../../components";
import { formatIban } from "./format";
import { CreatePinDialog, DialogResult, EmailCodeField, ForgotPinDialog } from "./PinDialogs";
import { DialogActions, Notice, PinCodeField } from "./ui";

const CURRENCIES = ["CHF", "EUR"] as const;

export function BankAccountDialog({
  onClose,
  currency: fixedCurrency,
  holderName = ""
}: {
  onClose: () => void;
  /** Opened for one currency (Bank accounts tab); without it the investor picks CHF or EUR. */
  currency?: string;
  /** The verified name of the investor: the account must be in this name. */
  holderName?: string;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const [step, setStep] = useState<"details" | "confirm" | "done">("details");
  const [currency, setCurrency] = useState(fixedCurrency ?? "CHF");
  const [iban, setIban] = useState("");
  const [accountName, setAccountName] = useState(holderName);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [continueToken, setContinueToken] = useState(0);
  const mutation = useV1LedgerPayoutInstructionsCreate();
  const emailCode = useFlowEmailCode(ActionEnum.bank_account_change);
  const pin = useSensitivePin();
  useAutoSend(emailCode.send, step === "confirm");
  const compactIban = iban.replace(/\s/g, "");
  const detailsValid = CURRENCIES.includes(currency as (typeof CURRENCIES)[number]) && compactIban.length >= 15 && accountName.trim().length > 1;
  const canSubmit = detailsValid && pin.ready && (isFixturePreview || (Boolean(emailCode.codeId) && code.length === 6));

  const submit = () => {
    setError("");
    if (isFixturePreview) {
      if (pin.previewAccepts()) setStep("done");
      return;
    }
    if (!emailCode.codeId) {
      setError(t("Request an email code before you add the bank account."));
      return;
    }
    mutation.mutate(
      {
        data: {
          currency,
          destination_iban: compactIban,
          destination_account_name: accountName.trim(),
          sensitive_action_code_id: emailCode.codeId,
          sensitive_action_code: code,
          pin: pin.value
        }
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setStep("done");
        },
        onError: (mutationError) => {
          if (pin.handleError(mutationError)) return;
          setError(pinErrorText(mutationError));
        }
      }
    );
  };

  // After a PIN is created from the "no PIN yet" answer, the action runs again with it.
  useEffect(() => {
    if (continueToken > 0) submit();
    // Runs once per created PIN; submit reads the current state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [continueToken]);

  const title = fixedCurrency ? t("New {currency} bank account", { currency: fixedCurrency }) : t("Add a bank account");

  if (step === "done") {
    return (
      <Dialog className="p73-modal r75-profile-modal" onClose={onClose} size="md" title={title}>
        <DialogResult onDone={onClose} title={t("Pending verification")}>
          {t("We have added your {currency} bank account. You can use it for withdrawals and returns once our team has verified it. Your verified bank accounts stay usable in the meantime.", { currency })}
        </DialogResult>
      </Dialog>
    );
  }

  const lockTime = pin.lockedUntil ? formatPinLockTime(pin.lockedUntil) : "";
  return (
    <Dialog busy={mutation.isPending} className="p73-modal r75-profile-modal" onClose={onClose} size="md" title={title}>
      {step === "details" ? (
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (detailsValid) setStep("confirm");
          }}
        >
          <p className="bxm-muted">
            {holderName
              ? t("The account must be in your name, {name}. Our team checks it before it can be used for withdrawals and returns.", { name: holderName })
              : t("The account must be in your name. Our team checks it before it can be used for withdrawals and returns.")}
          </p>
          <p className="ps-bank-change-note">
            <NiIcon name="info" />
            <span>{t("Your verified bank accounts stay usable until the new one is verified.")}</span>
          </p>
          {fixedCurrency ? null : (
            <div className="form-group">
              <label className="form-label" htmlFor="ib-currency">{t("Currency")}</label>
              <select className="form-select" id="ib-currency" onChange={(event) => setCurrency(event.target.value)} value={currency}>
                {CURRENCIES.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </div>
          )}
          <div className="form-group">
            <label className="form-label" htmlFor="ib-iban">{t("IBAN")}</label>
            <input
              autoComplete="off"
              className="form-control bxm-num"
              id="ib-iban"
              name="iban"
              onChange={(event) => setIban(event.target.value.toUpperCase())}
              placeholder={currency === "EUR" ? "DE.., AT.., FR.." : "CH.."}
              spellCheck={false}
              value={iban}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="ib-holder">{t("Account holder")}</label>
            <input className="form-control" id="ib-holder" name="holder" onChange={(event) => setAccountName(event.target.value)} value={accountName} />
          </div>
          <DialogActions onCancel={onClose} primaryDisabled={!detailsValid} primaryLabel={t("Continue")} primaryType="submit" />
        </form>
      ) : (
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit && !mutation.isPending) submit();
          }}
        >
          <p className="p73-intro">{t("Confirm with the code we send to your email and your PIN.")}</p>
          <dl className="acc-summary">
            <div><dt>{t("Currency")}</dt><dd>{currency}</dd></div>
            <div><dt>{t("IBAN")}</dt><dd><span className="bxm-iban">{formatIban(compactIban)}</span></dd></div>
            <div><dt>{t("Account holder")}</dt><dd>{accountName.trim()}</dd></div>
          </dl>
          <EmailCodeField code={emailCode} onChange={setCode} value={code} />
          {pin.lockedUntil !== null ? (
            <Notice action={<Button onClick={pin.openForgot} size="sm">{t("Forgot PIN?")}</Button>} title={t("PIN locked")} tone="danger">
              {lockTime
                ? t("Too many wrong PINs. You can try again after {time}, or set a new PIN now.", { time: lockTime })
                : t("Too many wrong PINs. Try again later, or set a new PIN now.")}
            </Notice>
          ) : null}
          <PinCodeField
            aside={pin.lockedUntil === null ? <button className="acc-text-button" onClick={pin.openForgot} type="button">{t("Forgot PIN?")}</button> : null}
            disabled={pin.lockedUntil !== null}
            error={pin.error || undefined}
            hint={isFixturePreview ? t("Demo: any 6 digits that are not all the same or a straight run") : t("The 6-digit PIN of your account.")}
            label={t("PIN")}
            onChange={pin.setValue}
            value={pin.value}
          />
          {error ? <Notice title={t("Could not add the bank account")} tone="danger">{error}</Notice> : null}
          <DialogActions
            cancelLabel={t("Back")}
            onCancel={() => setStep("details")}
            primaryDisabled={!canSubmit || mutation.isPending}
            primaryLabel={mutation.isPending ? t("Submitting...") : t("Submit for verification")}
            primaryType="submit"
          />
        </form>
      )}
      {pin.createOpen ? (
        <CreatePinDialog
          onClose={pin.closeDialogs}
          onSaved={(newPin) => {
            pin.afterCreate(newPin);
            setContinueToken((token) => token + 1);
          }}
        />
      ) : null}
      {pin.forgotOpen ? <ForgotPinDialog onClose={pin.closeDialogs} onReset={pin.afterReset} /> : null}
    </Dialog>
  );
}
