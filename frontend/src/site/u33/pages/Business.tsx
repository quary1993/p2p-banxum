// IP of Webby-Soft SRL.
/*
 * U33 pages for businesses (design companies.html, originators.html, business.js): For borrowers
 * and For loan originators, with their request forms sent to the enquiry endpoint (kind
 * "company" / "originator"; one email to the team, see backend communications public_forms).
 *
 * Differences with the design: the forms are sent for real (with the consent the endpoint
 * requires and a "sent" state with the reference); "real assets" reads "collateral or
 * guarantees" (U33-DEC-38); no promise of a reply time (U33-DEC-35).
 */
import { useEffect, useState } from "react";

import { useT } from "../../../i18n";
import { useSiteTitle } from "../../context";
import {
  COMPANY_FORM,
  ENQUIRY_CURRENCIES,
  ORIGINATOR_FORM,
  ORIGINATOR_PROPOSALS,
  useEnquiryForm,
  type EnquirySent
} from "../../pages/enquiry";
import { Consent, Field, FieldError, FormAlert, Honeypot, SentState, Select, TextArea, TextInput } from "../forms";
import { scrollToSection, useNarrow } from "../hooks";
import { InPageLink, Ni, PublicLink } from "../ui";

// ---------------------------------------------------------------------------------------------
// For borrowers

const PROJECTS = [
  { purpose: "Business expansion", title: "Business expansion", text: "More capacity. More room to grow." },
  { purpose: "Machinery and equipment", title: "Machinery & equipment", text: "Productive assets for your business." },
  { purpose: "Property project", title: "Property projects", text: "Development and completion." }
];

export function Companies() {
  const t = useT();
  useSiteTitle(t("For borrowers"));
  const narrow = useNarrow();
  const [sent, setSent] = useState<EnquirySent | null>(null);
  const [round, setRound] = useState(0);
  // business.js: a project choice fills the purpose field.
  const [purpose, setPurpose] = useState<Prefill>(null);
  const formTarget = narrow ? "request-form" : "request";

  return (
    <>
      <section aria-labelledby="companies-title" className="company-hero">
        <div className="company-hero-copy">
          <p className="page-kicker">{t("FOR BORROWERS")}</p>
          <h1 id="companies-title">
            {t("Business financing.")}
            <br />{" "}
            <span>
              {t("Built around")}
              <br /> {t("your project.")}
            </span>
          </h1>
          <p className="hero-copy">
            {t("Tell us what you need to finance.")}
            <br /> {t("We assess the business and structure the loan.")}
          </p>
          <div className="hero-actions">
            <InPageLink className="button-primary" section={formTarget}>
              {t("Request financing")} <Ni glyph="arrow" />
            </InPageLink>
          </div>
          <div className="scope-line">
            <span aria-hidden="true" className="swiss-flag" />
            <span>{t("Switzerland")}</span>
          </div>
        </div>
        <aside aria-labelledby="project-title" className="project-panel">
          <div className="project-panel-heading">
            <h2 id="project-title">{t("What are you financing?")}</h2>
            <span>{t("Start with your project")}</span>
          </div>
          <div className="project-options">
            {PROJECTS.map((project, index) => (
              <InPageLink data-purpose={project.purpose} key={project.purpose} onClick={() => setPurpose((current) => ({ value: t(project.purpose), seq: (current?.seq ?? 0) + 1 }))} section={formTarget}>
                <span className="project-number">{`0${index + 1}`}</span>
                <div>
                  <strong>{t(project.title)}</strong>
                  <span>{t(project.text)}</span>
                </div>
                <Ni glyph="arrow" />
              </InPageLink>
            ))}
          </div>
          <div className="project-panel-foot">
            <span aria-hidden="true" className="asset-marker" />
            {t("Loans secured by collateral or guarantees")}
          </div>
        </aside>
      </section>
      <section aria-label={t("Why finance through Banxum")} className="value-row">
        <article>
          <span className="value-label">{t("STRUCTURE")}</span>
          <h2>
            {t("Terms shaped")}
            <br /> {t("around your business.")}
          </h2>
          <p>
            {t("Discuss the loan term and repayments")}
            <br /> {t("in the context of your project.")}
          </p>
        </article>
        <article>
          <span className="value-label">{t("ADMINISTRATION")}</span>
          <h2>
            {t("One relationship.")}
            <br /> {t("From start to finish.")}
          </h2>
          <p>
            {t("From the financing request")}
            <br /> {t("to ongoing loan administration.")}
          </p>
        </article>
        <article>
          <span className="value-label">{t("DISCRETION")}</span>
          <h2>
            {t("Your name stays")}
            <br /> {t("off the public page.")}
          </h2>
          <p>
            {t("Company identity and financial details")}
            <br /> {t("are available to verified investors.")}
          </p>
        </article>
      </section>
      <section aria-labelledby="request-title" className="request-section" id="request">
        <div className="request-context">
          <h2 id="request-title">
            {t("From your request")}
            <br />{" "}
            <span>{t("to investors.")}</span>
          </h2>
          <ol className="request-stages">
            <Stage index={1} text={t("The amount, purpose and available collateral.")} title={t("Tell us what you need")} />
            <Stage index={2} text={t("Your business, the loan terms and its security.")} title={t("We assess and structure")} />
            <Stage index={3} text={t("Selected loans are offered for funding.")} title={t("Presented to investors")} />
          </ol>
        </div>
        <div className="paper-panel business-form-panel" id="request-form">
          {sent ? (
            <SentState
              againLabel={t("Send another request")}
              onAgain={() => {
                setSent(null);
                setRound((value) => value + 1);
              }}
              sent={sent}
              title={t("Thank you. Your financing request has been sent.")}
            />
          ) : (
            <>
              <div className="business-form-heading">
                <h2>{t("Your financing request")}</h2>
                <p>{t("Start with the essentials. Documents come later.")}</p>
              </div>
              <CompanyForm key={round} onSent={setSent} purpose={purpose} />
            </>
          )}
        </div>
      </section>
    </>
  );
}

function Stage({ index, title, text }: { index: number; title: string; text: string }) {
  return (
    <li>
      <span>{`0${index}`}</span>
      <div>
        <h3>{title}</h3>
        <p>{text}</p>
      </div>
    </li>
  );
}

/** A value chosen outside the form (a project or route choice), with a counter for repeats. */
type Prefill = { value: string; seq: number } | null;

function CompanyForm({ onSent, purpose }: { onSent: (sent: EnquirySent) => void; purpose: Prefill }) {
  const t = useT();
  const form = useEnquiryForm(COMPANY_FORM, onSent);
  const { setValue } = form;
  useEffect(() => {
    if (purpose) setValue("company-purpose", purpose.value);
  }, [purpose, setValue]);
  return (
    <form aria-label={t("Your financing request")} className="business-form" noValidate onSubmit={form.onSubmit}>
      <div className="form-grid">
        <Field form={form} id="company-name" label={t("Company name")}>
          <TextInput autoComplete="organization" form={form} id="company-name" maxLength={200} placeholder={t("Company name")} />
        </Field>
        <Field form={form} id="company-country" label={t("Country of registration")}>
          <TextInput autoComplete="country-name" form={form} id="company-country" maxLength={200} placeholder={t("Switzerland or an EU country")} />
        </Field>
        <div className="field">
          <label htmlFor="company-amount">{t("Amount requested")}</label>
          <div className="business-money-input">
            <Select
              ariaLabel={t("Loan currency")}
              form={form}
              id="company-currency"
              options={ENQUIRY_CURRENCIES.map((currency) => ({ value: currency, label: currency }))}
            />
            <TextInput amount form={form} id="company-amount" maxLength={40} placeholder={t("Amount")} />
          </div>
          <FieldError fallback={t("Enter the amount you would like to borrow.")} form={form} id="company-amount" />
        </div>
        <Field form={form} id="company-purpose" label={t("Purpose of financing")}>
          <TextInput form={form} id="company-purpose" maxLength={200} placeholder={t("What would the funding support?")} />
        </Field>
        <Field form={form} full id="company-collateral" label={t("Available collateral")}>
          <TextArea
            form={form}
            id="company-collateral"
            maxLength={4000}
            placeholder={t("Briefly describe the collateral or guarantees available to secure the loan.")}
            rows={2}
          />
        </Field>
        <Field form={form} id="company-contact-name" label={t("Your name")}>
          <TextInput autoComplete="name" form={form} id="company-contact-name" maxLength={200} placeholder={t("Full name")} />
        </Field>
        <Field error={t("Enter a valid email address.")} form={form} id="company-email" label={t("Email")}>
          <TextInput autoComplete="email" form={form} id="company-email" maxLength={254} placeholder={t("you@company.com")} type="email" />
        </Field>
        <Consent form={form} id={COMPANY_FORM.consentId} />
      </div>
      <Honeypot form={form} />
      <FormAlert form={form} />
      <div className="business-form-end">
        <button className="button-primary" disabled={form.pending} type="submit">
          {form.pending ? t("Sending…") : t("Send financing request")} <Ni glyph="arrow" />
        </button>
        <p className="form-note">{t("A member of our team will reply by email.")}</p>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------------------------
// For loan originators

export function Originators() {
  const t = useT();
  useSiteTitle(t("For loan originators"));
  const [sent, setSent] = useState<EnquirySent | null>(null);
  const [round, setRound] = useState(0);
  // business.js: a route's action fills the proposal type.
  const [proposal, setProposal] = useState<Prefill>(null);

  const chooseType = (value: string) => {
    setProposal((current) => ({ value, seq: (current?.seq ?? 0) + 1 }));
    scrollToSection("partnership");
  };

  return (
    <>
      <section aria-labelledby="originators-title" className="originator-hero">
        <div>
          <p className="page-kicker">{t("FOR LOAN ORIGINATORS")}</p>
          <h1 id="originators-title">
            {t("Fund new loans.")}
            <br />{" "}
            <span>{t("Refinance existing ones.")}</span>
          </h1>
          <p className="hero-copy">{t("Access investor capital for business loans secured by collateral or guarantees.")}</p>
        </div>
        <div className="originator-hero-actions">
          <InPageLink className="button-primary" section="partnership">
            {t("Propose a partnership")} <Ni glyph="arrow" />
          </InPageLink>
        </div>
      </section>
      <section aria-label={t("Two ways to work with Banxum")} className="lending-routes">
        <LendingRoute
          action={t("Propose a new loan")}
          ariaLabel={t("New loan proposal, assessment by Banxum, then investor funding if selected")}
          end={[t("Investor"), t("funding")]}
          foot={t("Before lending")}
          index="01"
          kicker={t("NEW LOANS")}
          onAction={() => chooseType(ORIGINATOR_PROPOSALS[0])}
          paper={t("LOAN PROPOSAL")}
          paperClass="new-loan"
          text={[t("Bring a financing opportunity"), t("before granting the loan.")]}
          title={[t("For the loan"), t("you want to make.")]}
        />
        <LendingRoute
          action={t("Propose an existing loan")}
          ariaLabel={t("Existing loan, assessment by Banxum, then refinancing through investors if selected")}
          end={[t("Investor"), t("refinancing")]}
          foot={t("Already granted")}
          index="02"
          kicker={t("EXISTING LOANS")}
          onAction={() => chooseType(ORIGINATOR_PROPOSALS[1])}
          paper={t("EXISTING LOAN")}
          paperClass="existing-loan"
          text={[t("Propose refinancing for a business loan"), t("you have already granted.")]}
          title={[t("For a loan"), t("already on your books.")]}
        />
      </section>
      <p className="selection-note">
        {t("Banxum assesses each opportunity before deciding what to present to investors. Financing depends on investor participation.")}
      </p>
      <section aria-labelledby="partnership-title" className="request-section originator-request" id="partnership">
        <div className="request-context">
          <h2 id="partnership-title">
            {t("Let’s discuss")}
            <br />{" "}
            <span>{t("your lending.")}</span>
          </h2>
          <ol className="request-stages">
            <Stage index={1} text={t("Your lending activity and proposed loans.")} title={t("Introduce your business")} />
            <Stage index={2} text={t("Review the opportunities and agree next steps.")} title={t("Discuss the partnership")} />
            <Stage index={3} text={t("Build the loan file for assessment and publication.")} title={t("Prepare selected opportunities")} />
          </ol>
          <PublicLink className="quiet-link cross-link" href="/companies">
            {t("Financing your own company?")} <Ni glyph="arrow" />
          </PublicLink>
        </div>
        <div className="paper-panel business-form-panel">
          {sent ? (
            <SentState
              againLabel={t("Send another request")}
              onAgain={() => {
                setSent(null);
                setRound((value) => value + 1);
              }}
              sent={sent}
              title={t("Thank you. Your partnership request has been sent.")}
            />
          ) : (
            <>
              <div className="business-form-heading">
                <h2>{t("Your partnership request")}</h2>
                <p>{t("Your company and the loans you would like to propose.")}</p>
              </div>
              <OriginatorForm key={round} onSent={setSent} proposal={proposal} />
            </>
          )}
        </div>
      </section>
    </>
  );
}

function LendingRoute({
  index,
  kicker,
  title,
  text,
  ariaLabel,
  paper,
  paperClass,
  foot,
  end,
  action,
  onAction
}: {
  index: string;
  kicker: string;
  title: [string, string];
  text: [string, string];
  ariaLabel: string;
  paper: string;
  paperClass: string;
  foot: string;
  end: [string, string];
  action: string;
  onAction: () => void;
}) {
  const t = useT();
  return (
    <article className="lending-route">
      <div className="route-top">
        <span className="route-index">{index}</span>
        <span>{kicker}</span>
      </div>
      <h2>
        {title[0]}
        <br />{" "}
        {title[1]}
      </h2>
      <p>
        {text[0]}
        <br />{" "}
        {text[1]}
      </p>
      <div aria-label={ariaLabel} className="loan-route">
        <div className={`loan-paper ${paperClass}`}>
          <span className="paper-label">{paper}</span>
          <i />
          <i />
          <i />
          <span className="paper-foot">{foot}</span>
        </div>
        <div className="route-bridge">
          <span>Banxum</span>
          <i />
          <small>{t("Assessment")}</small>
        </div>
        <div className="funding-end">
          <Ni glyph="arrow" />
          <strong>
            {end[0]}
            <br />{" "}
            {end[1]}
          </strong>
        </div>
      </div>
      <a
        className="route-action"
        href="#partnership"
        onClick={(event) => {
          event.preventDefault();
          onAction();
        }}
      >
        {action} <Ni glyph="arrow" />
      </a>
    </article>
  );
}

function OriginatorForm({ onSent, proposal }: { onSent: (sent: EnquirySent) => void; proposal: Prefill }) {
  const t = useT();
  const form = useEnquiryForm(ORIGINATOR_FORM, onSent);
  const { setValue } = form;
  useEffect(() => {
    if (proposal) setValue("originator-loan-type", proposal.value);
  }, [proposal, setValue]);
  return (
    <form aria-label={t("Your partnership request")} className="business-form" noValidate onSubmit={form.onSubmit}>
      <div className="form-grid">
        <Field form={form} id="originator-company" label={t("Company name")}>
          <TextInput autoComplete="organization" form={form} id="originator-company" maxLength={200} placeholder={t("Company name")} />
        </Field>
        <Field form={form} id="originator-country" label={t("Country of registration")}>
          <TextInput autoComplete="country-name" form={form} id="originator-country" maxLength={200} placeholder={t("Country")} />
        </Field>
        <Field form={form} id="originator-name" label={t("Your name")}>
          <TextInput autoComplete="name" form={form} id="originator-name" maxLength={200} placeholder={t("Full name")} />
        </Field>
        <Field error={t("Enter a valid email address.")} form={form} id="originator-email" label={t("Email")}>
          <TextInput autoComplete="email" form={form} id="originator-email" maxLength={254} placeholder={t("you@company.com")} type="email" />
        </Field>
        <Field error={t("Choose the type of opportunity.")} form={form} full id="originator-loan-type" label={t("What would you like to propose?")}>
          <Select
            form={form}
            id="originator-loan-type"
            options={ORIGINATOR_PROPOSALS.map((value) => ({ value, label: t(value) }))}
            placeholder={t("Select the type of opportunity")}
          />
        </Field>
        <Field
          form={form}
          full
          id="originator-message"
          label={
            <>
              {t("A short introduction")} <span className="business-optional">{t("Optional")}</span>
            </>
          }
        >
          <TextArea
            form={form}
            id="originator-message"
            maxLength={4000}
            placeholder={t("The types of business loans you work with and their collateral.")}
            rows={3}
          />
        </Field>
        <Consent form={form} id={ORIGINATOR_FORM.consentId} />
      </div>
      <Honeypot form={form} />
      <FormAlert form={form} />
      <div className="business-form-end">
        <button className="button-primary" disabled={form.pending} type="submit">
          {form.pending ? t("Sending…") : t("Propose a partnership")} <Ni glyph="arrow" />
        </button>
        <p className="form-note">{t("A member of our team will reply by email.")}</p>
      </div>
    </form>
  );
}
