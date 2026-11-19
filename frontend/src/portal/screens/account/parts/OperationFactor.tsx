// IP of Webby-Soft SRL.
// The second factor of an operation in U33 (S7 clean-up, 18.5): the PIN (ACC-DEC-009) or, for an
// investor with an authenticator app, the app code (D-1), with the lock notice, "Forgot PIN?" and the
// "Create your PIN" dialog of an SMS investor without a PIN; after a PIN is created, the operation
// continues (``onContinue``). Replaces the old-skin SensitivePinField (investorPortal/pin.tsx).
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { useT } from "../../../../i18n";
import { formatPinLockTime } from "../../../../investorPortal/pinRules";
import type { SensitivePin } from "../../../../investorPortal/pinState";
import { CreatePinDialog, ForgotPinDialog } from "./PinDialogs";
import { OperationFactorField } from "./ui";

export function SensitiveFactorField({ pin, onContinue }: { pin: SensitivePin; onContinue?: () => void }) {
  const continueRef = useRef(onContinue);
  useLayoutEffect(() => {
    continueRef.current = onContinue;
  });
  const t = useT();
  const [continueToken, setContinueToken] = useState(0);
  useEffect(() => {
    if (continueToken > 0) continueRef.current?.();
  }, [continueToken]);
  const lockTime = pin.lockedUntil ? formatPinLockTime(pin.lockedUntil) : "";
  return (
    <div className="acc-operation-factor">
      <OperationFactorField lockTime={lockTime} pin={pin} />
      {pin.createOpen ? (
        <CreatePinDialog
          intro={t("You need a PIN to confirm this action. Create it now; the action continues right after.")}
          onClose={pin.closeDialogs}
          onSaved={(newPin) => {
            pin.afterCreate(newPin);
            setContinueToken((token) => token + 1);
          }}
        />
      ) : null}
      {pin.forgotOpen ? <ForgotPinDialog onClose={pin.closeDialogs} onReset={pin.afterReset} /> : null}
    </div>
  );
}
