// IP of Webby-Soft SRL.
/*
 * For loan originators: fund part of your loan book with investors (design: pages_more.js
 * originators(), originatorForm(), doneBox("originator")). The request is sent with
 * useEnquirySubmit (kind "originator").
 *
 * Partners come from usePublicOriginators(). The API has no city and no business text, so a
 * partner reads "<Country> · partner since <Month Year>" and "<N> claims funded.". Without
 * partners (none yet, still loading, or the call failed) the "Our partners" column is left out.
 */
import { useState, type CSSProperties } from "react";

import { Eyebrow, PageHead } from "../components";
import { siteCompany } from "../content";
import { usePublicOriginators } from "../data";
import { monthYear } from "../format";
import { countryName } from "../projects";
import { ENQUIRY_COUNTRIES, ORIGINATOR_FORM, scrollToSection, useEnquiryForm, type EnquirySent } from "./enquiry";
import { ConsentField, DoneBox, Honeypot, SelectField, SubmitRow, TextAreaField, TextField } from "./EnquiryForm";

function OriginatorFormFields({ onSent }: { onSent: (sent: EnquirySent) => void }) {
  const form = useEnquiryForm(ORIGINATOR_FORM, onSent);
  return (
    <form className="site-form" noValidate onSubmit={form.onSubmit}>
      <h3 className="site-h3">Talk to us</h3>
      <p className="site-small mb-4">Tell us about your company and your loans. We answer within a week.</p>
      <div className="row g-3">
        <TextField auto="organization" form={form} id="or-name" label="Company name" />
        <SelectField form={form} half id="or-country" label="Country" options={ENQUIRY_COUNTRIES} />
        <TextField form={form} half id="or-licence" label="Licence or registration" placeholder="Authority and number" />
        <SelectField
          form={form}
          half
          id="or-product"
          label="What you finance"
          options={["Leasing", "Invoices (factoring)", "Business loans", "Real estate loans", "Other"]}
        />
        <TextField
          amount
          form={form}
          half
          id="or-book"
          label="Loan book"
          note="Amount outstanding, in CHF or EUR"
          placeholder="10,000,000.00"
        />
        <TextAreaField form={form} id="or-about" label="Anything we should know?" rows={4} />
        <TextField auto="name" form={form} half id="or-contact" label="Your name" />
        <TextField auto="email" error="Enter a valid email address." form={form} half id="or-email" label="Email" type="email" />
        <ConsentField form={form} id="or-consent" purpose="answer my request" />
        <SubmitRow form={form} label="Send" />
      </div>
      <Honeypot form={form} />
    </form>
  );
}

function OriginatorForm() {
  const [sent, setSent] = useState<EnquirySent | null>(null);
  if (sent) return <DoneBox kind="originator" onAgain={() => setSent(null)} sent={sent} />;
  return <OriginatorFormFields onSent={setSent} />;
}

function Partners() {
  const { data } = usePublicOriginators();
  if (!data?.length) return null;
  return (
    <div>
      <Eyebrow>Our partners</Eyebrow>
      <div className="site-cells is-2" style={{ "--site-cols": 1 } as CSSProperties}>
        {data.map((partner) => (
          <div key={partner.id}>
            <h3 className="site-h4">{partner.name}</h3>
            <p className="site-small mb-2">
              {countryName(partner.country)} · partner since {monthYear(partner.partner_since)}
            </p>
            <p className="site-text mb-0">{partner.claims_funded} claims funded.</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Originators() {
  const partners = siteCompany.partners;
  return (
    <>
      <PageHead
        actions={
          <button className="btn btn-lg btn-primary" onClick={() => scrollToSection("talk")} type="button">
            Talk to us
          </button>
        }
        eyebrow="For loan originators"
        lead="Leasing, factoring and lending companies assign claims to Garanta, which offers shares of them to investors on Banxum. You keep your customers and the servicing."
        title="Fund part of your loan book with investors"
      />
      <section className="site-section">
        <div className="site-wrap site-split">
          <div>
            <Eyebrow>How it works</Eyebrow>
            <h2 className="site-h2">A framework agreement, then claim by claim</h2>
          </div>
          <ol className="site-steps-list">
            <li>
              <strong>Due diligence</strong>
              <span>Your company, licence, loan data of the last three years, losses and recoveries, servicing.</span>
            </li>
            <li>
              <strong>Framework agreement</strong>
              <span>Which claims are eligible, the price, recourse for claims that are not valid, reporting.</span>
            </li>
            <li>
              <strong>You propose claims</strong>
              <span>We check each one and list it with the same facts as any project.</span>
            </li>
            <li>
              <strong>Investors fund</strong>
              <span>Garanta buys the claim and pays you the price when it is fully funded.</span>
            </li>
            <li>
              <strong>You keep servicing</strong>
              <span>Your customer pays you as before; you pass the payments to Garanta for the investors.</span>
            </li>
          </ol>
        </div>
      </section>
      <section className="site-section">
        <div className="site-wrap site-split">
          <div>
            <Eyebrow>What we look for</Eyebrow>
            <ul className="site-checks">
              <li>A licensed or registered lender in Switzerland or the EU</li>
              <li>At least three years of lending, with loan-level data</li>
              <li>Audited financial statements</li>
              <li>A share of each loan kept on your own book</li>
              <li>Recourse for claims that turn out not to be valid</li>
            </ul>
          </div>
          <Partners />
        </div>
      </section>
      <section className="site-section is-paper" id="talk">
        <div className="site-wrap site-split">
          <div>
            <Eyebrow>Contact</Eyebrow>
            <h2 className="site-h2">Talk to our partnerships team</h2>
            <p className="site-lead mt-4">
              Or write to <a href={`mailto:${partners}`}>{partners}</a>.
            </p>
          </div>
          <div>
            <OriginatorForm />
          </div>
        </div>
      </section>
    </>
  );
}
