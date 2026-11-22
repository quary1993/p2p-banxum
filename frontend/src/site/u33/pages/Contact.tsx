// IP of Webby-Soft SRL.
/*
 * U33 Contact page (design contact.html, contact-refined.js): request a conversation (full
 * name, email, optional topic and message), sent to the enquiry endpoint (kind "contact").
 *
 * Differences with the design: the form is sent for real (consent, "sent" state with the
 * reference); the address shown is today's configured support address, not investors@banxum.ch
 * (U33-DEC-36); "will be in touch by email shortly" reads "will reply by email" (U33-DEC-35).
 */
import { useState } from "react";

import { useT } from "../../../i18n";
import { siteCompany } from "../../content";
import { useSiteTitle } from "../../context";
import { CONTACT_FORM, CONTACT_TOPICS, useEnquiryForm, type EnquirySent } from "../../pages/enquiry";
import { Consent, Field, FormAlert, Honeypot, SentState, TextArea, TextInput } from "../forms";
import { Ni, PublicLink } from "../ui";

export function Contact() {
  const t = useT();
  useSiteTitle(t("Contact"));
  const [sent, setSent] = useState<EnquirySent | null>(null);
  const [round, setRound] = useState(0);
  return (
    <div className="content-shell contact-page">
      <section aria-labelledby="contact-title" className="page-hero contact-layout">
        <div className="contact-intro">
          <h1 className="page-title" id="contact-title">
            {t("Let’s talk")}
            <br />{" "}
            {t("about investing.")}
          </h1>
          <p className="page-lead">{t("Discuss an opportunity, its collateral or how investing with Banxum works.")}</p>
          <p className="contact-no-account">{t("No account required.")}</p>
          <div aria-label={t("Banxum contact details")} className="contact-institution">
            <div className="contact-location">
              <span aria-hidden="true" className="swiss-flag" />
              <span>{t("Switzerland")}</span>
            </div>
            <p className="contact-direct-email">
              {t("Email address")}{" "}
              <a href={`mailto:${siteCompany.email}`}>
                <span>{siteCompany.email}</span>
              </a>
            </p>
          </div>
        </div>
        {sent ? (
          <div className="paper-panel contact-form">
            <SentState
              againLabel={t("Send another message")}
              onAgain={() => {
                setSent(null);
                setRound((value) => value + 1);
              }}
              sent={sent}
              title={t("Thank you. Your request has been sent.")}
            />
          </div>
        ) : (
          <ContactForm key={round} onSent={setSent} />
        )}
      </section>
    </div>
  );
}

function ContactForm({ onSent }: { onSent: (sent: EnquirySent) => void }) {
  const t = useT();
  const form = useEnquiryForm(CONTACT_FORM, onSent);
  const topic = form.values["contact-topic"] ?? "";
  return (
    <form aria-labelledby="contact-form-title" className="paper-panel contact-form" noValidate onSubmit={form.onSubmit}>
      <h2 id="contact-form-title">{t("Request a conversation")}</h2>
      <div className="form-grid">
        <Field form={form} id="contact-name" label={t("Full name")}>
          <TextInput autoComplete="name" form={form} id="contact-name" maxLength={120} />
        </Field>
        <Field error={t("Enter a valid email address.")} form={form} id="contact-email" label={t("Email address")}>
          <TextInput autoComplete="email" form={form} id="contact-email" maxLength={180} type="email" />
        </Field>
        <fieldset className="contact-topics full-span">
          <legend>
            {t("Topic")} <span className="field-optional">{t("Optional")}</span>
          </legend>
          <div className="contact-topic-options">
            {CONTACT_TOPICS.map((option) => (
              <button
                aria-pressed={topic === option}
                data-topic={option}
                key={option}
                onClick={() => form.setValue("contact-topic", topic === option ? "" : option)}
                type="button"
              >
                {t(option)}
              </button>
            ))}
          </div>
        </fieldset>
        <Field
          form={form}
          full
          id="contact-message"
          label={
            <>
              {t("Message")} <span className="field-optional">{t("Optional")}</span>
            </>
          }
        >
          <TextArea form={form} id="contact-message" maxLength={1500} placeholder={t("Add a question or a few details.")} rows={3} />
        </Field>
        <Consent form={form} id={CONTACT_FORM.consentId} />
      </div>
      <Honeypot form={form} />
      <FormAlert form={form} />
      <div className="contact-form-bottom">
        <button className="button-primary" disabled={form.pending} type="submit">
          {form.pending ? t("Sending…") : t("Request a conversation")} <Ni glyph="arrow" />
        </button>
        <p className="contact-reply">{t("A member of our team will reply by email.")}</p>
      </div>
      <div className="contact-form-meta">
        <PublicLink className="contact-privacy" href="/legal/privacy">
          {t("Privacy information")} <Ni glyph="arrow" />
        </PublicLink>
      </div>
    </form>
  );
}
