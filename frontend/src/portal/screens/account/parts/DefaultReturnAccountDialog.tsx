// IP of Webby-Soft SRL.
// "Use for returns" (U33-DEC-05): the investor makes a verified bank account the default return
// account of its currency, the account money going back to the bank is sent to. Confirmed like
// adding an account: the bank-account email code and the PIN. There is no waiting period; the
// change is announced by a notice.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ActionEnum, useV1LedgerPayoutInstructionsDefaultCreate, type PayoutInstruction } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useAutoSend, useFlowEmailCode, pinErrorText } from "../../../../investorPortal/pinFlows";
import { formatPinLockTime } from "../../../../investorPortal/pinRules";
import { useSensitivePin } from "../../../../investorPortal/pinState";
import { Button, Dialog } from "../../../components";
import { formatIban } from "./format";
import { CreatePinDialog, DialogResult, EmailCodeField, ForgotPinDialog } from "./PinDialogs";
import { DialogActions, Notice, PinCodeField } from "./ui";

export function DefaultReturnAccountDialog({ instruction, onClose }: { instruction: PayoutInstruction; onClose: () => void }) {
  const t = useT();
  const queryClient = useQueryClient();
  const [done, setDone] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [continueToken, setContinueToken] = useState(0);
  const mutation = useV1LedgerPayoutInstructionsDefaultCreate();
  const emailCode = useFlowEmailCode(ActionEnum.bank_account_change);
  const pin = useSensitivePin();
  useAutoSend(emailCode.send, !done);
  const canSubmit = pin.ready && (isFixturePreview || (Boolean(emailCode.codeId) && code.length === 6));
  const title = t("Use for {currency} returns", { currency: instruction.currency });

  const submit = () => {
    setError("");
    if (isFixturePreview) {
      if (pin.previewAccepts()) setDone(true);
      return;
    }
    if (!emailCode.codeId) {
      setError(t("Request an email code before you change the return account."));
      return;
    }
    mutation.mutate(
      { instructionId: instruction.id, data: { sensitive_action_code_id: emailCode.codeId, sensitive_action_code: code, pin: pin.value } },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries();
          setDone(true);
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

  if (done) {
    return (
      <Dialog className="p73-modal r75-profile-modal" onClose={onClose} size="md" title={title}>
        <DialogResult onDone={onClose} title={t("Return account changed")}>
          {t("When we send {currency} back to your bank, we now use the account ending {last}.", { currency: instruction.currency, last: instruction.destination_iban.replace(/\s+/g, "").slice(-4) })}
        </DialogResult>
      </Dialog>
    );
  }

  const lockTime = pin.lockedUntil ? formatPinLockTime(pin.lockedUntil) : "";
  return (
    <Dialog busy={mutation.isPending} className="p73-modal r75-profile-modal" onClose={onClose} size="md" title={title}>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit && !mutation.isPending) submit();
        }}
      >
        <p className="p73-intro">{t("Money that goes back to your bank in {currency} is sent to this account. Confirm with the code we send to your email and your PIN.", { currency: instruction.currency })}</p>
        <dl className="acc-summary">
          <div><dt>{t("IBAN")}</dt><dd><span className="bxm-iban">{formatIban(instruction.destination_iban)}</span></dd></div>
          <div><dt>{t("Account holder")}</dt><dd>{instruction.destination_account_name}</dd></div>
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
        {error ? <Notice title={t("Could not change the return account")} tone="danger">{error}</Notice> : null}
        <DialogActions
          onCancel={onClose}
          primaryDisabled={!canSubmit || mutation.isPending}
          primaryLabel={mutation.isPending ? t("Submitting...") : t("Confirm")}
          primaryType="submit"
        />
      </form>
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
