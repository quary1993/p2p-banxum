// IP of Webby-Soft SRL.
/*
 * For companies: a loan from investors who see your project (design: pages_more.js
 * companies(), companyForm(), doneBox("company"), the company questions). The application is
 * sent with useEnquirySubmit (kind "company"); the done box shows the API's reference.
 */
import { useState } from "react";

import { Eyebrow, FaqList, PageHead, SiteLink } from "../components";
import { siteCompany, siteCompanyFaq } from "../content";
import { COMPANY_FORM, ENQUIRY_COUNTRIES, scrollToSection, useEnquiryForm, type EnquirySent } from "./enquiry";
import { ConsentField, DoneBox, Honeypot, SelectField, SubmitRow, TextAreaField, TextField } from "./EnquiryForm";

/** The amount note follows the country: CHF for Switzerland, EUR elsewhere. */
function currencyNote(country: string) {
  if (country === "Switzerland") return "In CHF. No loan size limits";
  if (country) return "In EUR. No loan size limits";
  return "No loan size limits";
}

function CompanyFormFields({ onSent }: { onSent: (sent: EnquirySent) => void }) {
  const form = useEnquiryForm(COMPANY_FORM, onSent);
  return (
    <form className="site-form" noValidate onSubmit={form.onSubmit}>
      <h3 className="site-h3">Apply for a loan</h3>
      <p className="site-small mb-4">About ten minutes. No commitment, and no effect on your credit rating.</p>
      <div className="row g-3">
        <TextField auto="organization" form={form} id="co-name" label="Company name" />
        <SelectField form={form} half id="co-country" label="Country of registration" options={ENQUIRY_COUNTRIES} />
        <TextField form={form} half id="co-reg" label="Company number" placeholder="CHE-123.456.789 or HRB 12345" />
        <TextField
          amount
          form={form}
          half
          id="co-amount"
          label="Amount"
          note={<span data-co-currency="">{currencyNote(form.values["co-country"])}</span>}
          placeholder="250,000.00"
        />
        <SelectField
          form={form}
          half
          id="co-term"
          label="Term"
          options={["1 month", "3 months", "6 months", "12 months", "18 months", "24 months", "36 months", "48 months", "60 months"]}
        />
        <SelectField
          form={form}
          half
          id="co-purpose"
          label="Purpose"
          options={[
            "Extension or construction",
            "Machines and equipment",
            "Real estate",
            "Stock and working capital",
            "Refinancing",
            "Other"
          ]}
        />
        <SelectField
          form={form}
          half
          id="co-security"
          label="Security you can offer"
          options={["Mortgage note", "Pledge on equipment", "Receivables", "Guarantee of the owners", "Not sure yet"]}
        />
        <TextField amount form={form} half id="co-revenue" label="Revenue last year" note="Optional" required={false} />
        <TextField form={form} half id="co-founded" label="Founded" placeholder="2015" type="number" />
        <TextAreaField
          form={form}
          id="co-about"
          label="What is the money for?"
          placeholder="Two or three sentences are enough."
          rows={4}
        />
        <TextField auto="name" form={form} half id="co-contact" label="Your name" />
        <TextField form={form} half id="co-role" label="Your role" placeholder="Owner, CFO…" />
        <TextField auto="email" error="Enter a valid email address." form={form} half id="co-email" label="Email" type="email" />
        <TextField auto="tel" form={form} half id="co-phone" label="Phone" type="tel" />
        <ConsentField form={form} id="co-consent" purpose="assess the application" />
        <SubmitRow form={form} label="Send application" />
      </div>
      <Honeypot form={form} />
    </form>
  );
}

function CompanyForm() {
  const [sent, setSent] = useState<EnquirySent | null>(null);
  if (sent) return <DoneBox kind="company" onAgain={() => setSent(null)} sent={sent} />;
  return <CompanyFormFields onSent={setSent} />;
}

export function Companies() {
  const partners = siteCompany.partners;
  return (
    <>
      <PageHead
        actions={
          <>
            <button className="btn btn-lg btn-primary" onClick={() => scrollToSection("apply")} type="button">
              Apply now
            </button>
            <SiteLink className="btn btn-lg btn-site-outline" href="/contact">
              Talk to us first
            </SiteLink>
          </>
        }
        eyebrow="For companies"
        lead="No loan size limits. Clear terms, one contact person, and an offer within about ten business days."
        title="A loan from investors who see your project"
      />
      <section className="site-section">
        <div className="site-wrap">
          <div className="site-cells">
            <div>
              <div className="site-cell-top">
                <span>01</span>
              </div>
              <h3 className="site-h3">A clear offer</h3>
              <p className="site-text">Rate and repayment plan in writing before you sign.</p>
            </div>
            <div>
              <div className="site-cell-top">
                <span>02</span>
              </div>
              <h3 className="site-h3">Repayment that fits</h3>
              <p className="site-text">
                Monthly instalments, monthly interest with the principal at the end, or everything at the end for short
                terms.
              </p>
            </div>
            <div>
              <div className="site-cell-top">
                <span>03</span>
              </div>
              <h3 className="site-h3">Your name kept private</h3>
              <p className="site-text">
                The public page shows your sector and region. Your name and figures are shown only to verified investors.
              </p>
            </div>
          </div>
        </div>
      </section>
      <section className="site-section is-paper" id="apply">
        <div className="site-wrap site-split is-5-7">
          <div className="site-sticky">
            <Eyebrow>Apply</Eyebrow>
            <h2 className="site-h2">Tell us about your project</h2>
            <p className="site-lead mt-4">
              A credit analyst answers within two business days. Prefer to talk first? Write to{" "}
              <a href={`mailto:${partners}`}>{partners}</a>.
            </p>
          </div>
          <div>
            <CompanyForm />
          </div>
        </div>
      </section>
      <section className="site-section">
        <div className="site-wrap site-split">
          <div>
            <Eyebrow>Questions</Eyebrow>
            <h2 className="site-h2">Questions from companies</h2>
          </div>
          <FaqList items={siteCompanyFaq} />
        </div>
      </section>
    </>
  );
}
