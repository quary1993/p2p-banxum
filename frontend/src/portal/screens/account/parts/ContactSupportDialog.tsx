// IP of Webby-Soft SRL.
// "Contact support" (design: .modal.hp-modal.rss-contact-modal with topic, message and "Send message").
// The design's form needs a Help message endpoint (U33-DEC-35, Phase 17.2); until then the form
// prepares an email to support in the investor's mail app, and says so: nothing is "sent" here.
import { useState } from "react";

import { useT } from "../../../../i18n";
import { Dialog, NiIcon } from "../../../components";
import { SUPPORT_TOPICS, supportEmail, supportMailto } from "../accountLinks";

export function ContactSupportDialog({ onClose, topic: initialTopic, reference }: { onClose: () => void; topic?: string; reference?: string | null }) {
  const t = useT();
  const [topic, setTopic] = useState<string>(initialTopic && SUPPORT_TOPICS.includes(initialTopic as (typeof SUPPORT_TOPICS)[number]) ? initialTopic : SUPPORT_TOPICS[0]);
  const [message, setMessage] = useState("");
  const [opened, setOpened] = useState(false);
  const href = supportMailto({ subject: t(topic), body: message.trim(), reference });
  return (
    <Dialog bodyClassName="hp-modal-body" className="hp-modal rss-contact-modal" onClose={onClose} size="md" title={t("Contact support")}>
      {opened ? (
        <div className="hp-message-result" role="status">
          <NiIcon name="mail" />
          <h3>{t("Finish in your email app")}</h3>
          <p>{t("Your email app should open with your message. Send it from there; our team replies by email.")}</p>
          <p>{t("If nothing opened, write to {email}.", { email: supportEmail })}</p>
          <button className="btn btn-primary" onClick={onClose} type="button">{t("Done")}</button>
        </div>
      ) : (
        <>
          <p className="hp-modal-intro">{t("Tell us what you need help with.")}</p>
          <form onSubmit={(event) => event.preventDefault()}>
            <div className="form-group">
              <label className="form-label" htmlFor="msg-topic">{t("Topic")}</label>
              <select className="form-select" id="msg-topic" onChange={(event) => setTopic(event.target.value)} value={topic}>
                {SUPPORT_TOPICS.map((value) => <option key={value} value={value}>{t(value)}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="msg-text">{t("Message")}</label>
              <textarea aria-describedby="hp-message-note" className="form-control" id="msg-text" onChange={(event) => setMessage(event.target.value)} rows={5} value={message} />
              <p className="hp-message-note" id="hp-message-note">
                {t("Write email opens your email app with this message to {email}; you send it from there. Do not include your PIN or any confirmation code.", { email: supportEmail })}
              </p>
            </div>
            <div className="hp-modal-actions">
              <button className="btn btn-outline-light" onClick={onClose} type="button">{t("Cancel")}</button>
              <a
                aria-disabled={message.trim() ? undefined : true}
                className={`btn btn-primary ${message.trim() ? "" : "disabled"}`.trim()}
                href={message.trim() ? href : undefined}
                onClick={(event) => {
                  if (!message.trim()) {
                    event.preventDefault();
                    return;
                  }
                  setOpened(true);
                }}
              >
                {t("Write email")}
              </a>
            </div>
          </form>
        </>
      )}
    </Dialog>
  );
}
