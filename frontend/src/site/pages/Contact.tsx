// IP of Webby-Soft SRL.
/*
 * Contact: talk to a person (design: pages_more.js contact()). The message is sent with
 * useEnquirySubmit (kind "contact"); the done box shows the API's reference.
 */
import { useState } from "react";

import { PageHead, SiteLink } from "../components";
import { siteCompany } from "../content";
import { CONTACT_FORM, useEnquiryForm, type EnquirySent } from "./enquiry";
import { ConsentField, ContactDoneBox, Honeypot, SelectField, SubmitRow, TextAreaField, TextField } from "./EnquiryForm";

function ContactFormFields({ onSent }: { onSent: (sent: EnquirySent) => void }) {
  const form = useEnquiryForm(CONTACT_FORM, onSent);
  return (
    <form className="site-form" noValidate onSubmit={form.onSubmit}>
      <div className="row g-3">
        <TextField auto="name" form={form} half id="ct-name" label="Your name" />
        <TextField auto="email" error="Enter a valid email address." form={form} half id="ct-email" label="Email" type="email" />
        <SelectField
          form={form}
          id="ct-topic"
          label="Topic"
          options={["Investing", "My account", "A loan for my company", "Loan originators", "Press", "Other"]}
        />
        <TextAreaField form={form} id="ct-msg" label="Message" required rows={6} />
        <div className="col-12">
          <p className="site-small mb-0">Please do not send passwords or codes. We never ask for them.</p>
        </div>
        <ConsentField form={form} id="ct-consent" purpose="answer me" />
        <SubmitRow form={form} label="Send message" />
      </div>
      <Honeypot form={form} />
    </form>
  );
}

function ContactForm() {
  const [sent, setSent] = useState<EnquirySent | null>(null);
  if (sent) return <ContactDoneBox onAgain={() => setSent(null)} sent={sent} />;
  return <ContactFormFields onSent={setSent} />;
}

export function Contact() {
  const company = siteCompany;
  return (
    <>
      <PageHead
        eyebrow="Contact"
        lead={
          <>
            Most answers are in the <SiteLink href="/help">questions</SiteLink>. For everything else, write to us.
          </>
        }
        title="Talk to a person"
      />
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap site-split is-7-5">
          <div>
            <ContactForm />
          </div>
          <div>
            <dl className="site-kv">
              <div>
                <dt>Email</dt>
                <dd>
                  <a href={`mailto:${company.email}`}>{company.email}</a>
                </dd>
              </div>
              <div>
                <dt>Companies and partners</dt>
                <dd>
                  <a href={`mailto:${company.partners}`}>{company.partners}</a>
                </dd>
              </div>
              <div>
                <dt>Phone</dt>
                <dd>{company.phone}</dd>
              </div>
              <div>
                <dt>Hours</dt>
                <dd>{company.hours}</dd>
              </div>
              <div>
                <dt>Address</dt>
                <dd>
                  {company.name}
                  <br />
                  {company.street}
                  <br />
                  {company.city}
                </dd>
              </div>
            </dl>
            <p className="site-small mt-4">
              Investors with an account can also write from the Help page of their account, so we see their investments.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
