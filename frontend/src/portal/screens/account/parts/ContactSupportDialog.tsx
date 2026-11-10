// IP of Webby-Soft SRL.
// "Contact support" (design: .modal.hp-modal.rss-contact-modal with topic, message and "Send message").
// U33-DEC-35: the form is sent by email to the support mailbox (no ticket system). The investor sees
// a real receipt: the reference and the confirmation email; an error keeps the message so it can be
// sent again (the same request key, so a retry never sends it twice). The design's "We answer within
// one business day" is left out until the support times are confirmed.
import { useState } from "react";

import { useV1InvestorPortalSupportRequestsCreate, type InvestorSupportRequestReceipt } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { Dialog, NiIcon } from "../../../components";
import { errorMessage, idempotencyKey } from "../../portfolio/parts/errors";
import { SUPPORT_TOPICS, supportEmail } from "../accountLinks";

export function ContactSupportDialog({ onClose, topic: initialTopic }: { onClose: () => void; topic?: string }) {
  const t = useT();
  const [topic, setTopic] = useState<string>(initialTopic && SUPPORT_TOPICS.includes(initialTopic as (typeof SUPPORT_TOPICS)[number]) ? initialTopic : SUPPORT_TOPICS[0]);
  const [message, setMessage] = useState("");
  const [requestKey, setRequestKey] = useState(() => idempotencyKey("support-help"));
  const [receipt, setReceipt] = useState<InvestorSupportRequestReceipt | null>(null);
  const [previewSent, setPreviewSent] = useState(false);
  const mutation = useV1InvestorPortalSupportRequestsCreate();
  const canSend = message.trim().length > 0 && !mutation.isPending;

  // A changed message after a failure is a new message: it gets a new request key.
  const edit = (update: () => void) => {
    update();
    if (mutation.isError) {
      mutation.reset();
      setRequestKey(idempotencyKey("support-help"));
    }
  };

  const send = () => {
    if (!canSend) return;
    if (isFixturePreview) {
      setPreviewSent(true);
      return;
    }
    mutation.mutate(
      { data: { kind: "help", idempotency_key: requestKey, topic, message: message.trim() } },
      { onSuccess: (result) => setReceipt(result) }
    );
  };

  if (receipt || previewSent) {
    return (
      <Dialog bodyClassName="hp-modal-body" className="hp-modal rss-contact-modal" onClose={onClose} size="md" title={t("Contact support")}>
        <div className="hp-message-result" role="status">
          <NiIcon name="mail" />
          <h3>{t("Message sent")}</h3>
          {receipt ? (
            <>
              <p>{t("Your reference is {reference}.", { reference: receipt.reference })}</p>
              <p>{t("We sent a confirmation to {email}. Our team answers by email.", { email: receipt.receipt_email })}</p>
            </>
          ) : (
            <p>{t("Demo: nothing was sent.")}</p>
          )}
          <button className="btn btn-primary" onClick={onClose} type="button">{t("Done")}</button>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog bodyClassName="hp-modal-body" busy={mutation.isPending} className="hp-modal rss-contact-modal" onClose={onClose} size="md" title={t("Contact support")}>
      <p className="hp-modal-intro">{t("Tell us what you need help with.")}</p>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <div className="form-group">
          <label className="form-label" htmlFor="msg-topic">{t("Topic")}</label>
          <select className="form-select" id="msg-topic" onChange={(event) => edit(() => setTopic(event.target.value))} value={topic}>
            {SUPPORT_TOPICS.map((value) => <option key={value} value={value}>{t(value)}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="msg-text">{t("Message")}</label>
          <textarea
            aria-describedby="hp-message-note"
            className="form-control"
            id="msg-text"
            maxLength={4000}
            onChange={(event) => {
              const value = event.target.value;
              edit(() => setMessage(value));
            }}
            required
            rows={5}
            value={message}
          />
          <p className="hp-message-note" id="hp-message-note">{t("Do not include your PIN or any confirmation code.")}</p>
        </div>
        {mutation.isError ? (
          <p className="hp-message-error" role="alert">
            {t("Your message was not sent: {reason}", { reason: errorMessage(mutation.error) })} {t("Try again, or write to {email}.", { email: supportEmail })}
          </p>
        ) : null}
        <div className="hp-modal-actions">
          <button className="btn btn-outline-light" onClick={onClose} type="button">{t("Cancel")}</button>
          <button className="btn btn-primary" disabled={!canSend} type="submit">
            {mutation.isPending ? t("Sending...") : mutation.isError ? t("Try again") : t("Send message")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
