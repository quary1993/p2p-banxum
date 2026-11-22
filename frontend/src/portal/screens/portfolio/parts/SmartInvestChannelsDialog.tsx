// IP of Webby-Soft SRL.
// Smart Invest notifications (design: si-notifications modal with two .si-notification-choice boxes and
// "Save preferences", with the refined presentation's title and the short labels "In the app" / "By email"). U33-DEC-30: the in-app and email match alerts have their own switches with a real
// effect; switching one off does not stop matching or service messages, and Pause stops both.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  getV1InvestorSmartInvestRetrieveQueryKey,
  useV1InvestorSmartInvestNotificationsCreate,
  type SmartInvestResponse
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { Dialog } from "../../../components";
import { errorMessage, isReadonlyView } from "./errors";

export function SmartInvestChannelsDialog({ current, onClose }: { current: SmartInvestResponse; onClose: () => void }) {
  const t = useT();
  const queryClient = useQueryClient();
  const [inApp, setInApp] = useState(current.notification_channels.in_app);
  const [email, setEmail] = useState(current.notification_channels.email);
  const [error, setError] = useState("");
  const mutation = useV1InvestorSmartInvestNotificationsCreate();
  const readonly = isReadonlyView();

  const save = async () => {
    setError("");
    if (readonly) {
      setError(t("Smart Invest cannot be changed in a read-only view."));
      return;
    }
    try {
      const response = isFixturePreview
        ? { ...current, notification_channels: { in_app: inApp, email } }
        : await mutation.mutateAsync({ data: { in_app: inApp, email } });
      queryClient.setQueryData(getV1InvestorSmartInvestRetrieveQueryKey(), response);
      onClose();
    } catch (failure) {
      setError(errorMessage(failure));
    }
  };

  return (
    <Dialog busy={mutation.isPending} onClose={onClose} size="md" title={t("Notify me about matching investment opportunities")}>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label className="si-notification-choice">
          <input checked={inApp} name="alerts" onChange={(event) => setInApp(event.target.checked)} type="checkbox" />
          {t("In the app")}
        </label>
        <label className="si-notification-choice">
          <input checked={email} name="email" onChange={(event) => setEmail(event.target.checked)} type="checkbox" />
          {t("By email")}
        </label>
        {error ? <p className="si-validation" role="alert">{error}</p> : null}
        <button className="btn btn-primary" disabled={mutation.isPending} type="submit">
          {mutation.isPending ? t("Saving...") : t("Save preferences")}
        </button>
      </form>
    </Dialog>
  );
}
