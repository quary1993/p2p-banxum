// IP of Webby-Soft SRL.
/*
 * Markup of the three public forms, ported 1:1 from the design (pages_more.js field, text,
 * select, consent, doneBox): same elements, classes, ids and texts. State and submit are in
 * enquiry.ts (useEnquiryForm). Additions the design has no need for, all invisible:
 * aria-invalid / aria-describedby on invalid fields, the honeypot, and the alert above the
 * submit button (a 429 or an error without a field to show it on).
 */
import { useEffect, useRef, type ReactNode } from "react";

import { NiIcon, SiteLink } from "../components";
import type { EnquiryForm, EnquirySent } from "./enquiry";

function feedbackId(id: string) {
  return `${id}-feedback`;
}

/** The message under an invalid field: the server's, else the design's. */
function feedbackText(form: EnquiryForm, id: string, fallback: string) {
  const mark = form.invalid[id];
  return typeof mark === "string" ? mark : fallback;
}

function invalidProps(form: EnquiryForm, id: string) {
  return id in form.invalid ? { "aria-invalid": true as const, "aria-describedby": feedbackId(id) } : {};
}

function cls(base: string, form: EnquiryForm, id: string) {
  return id in form.invalid ? `${base} is-invalid` : base;
}

/** design field(): column, label, the input, its invalid feedback and an optional note. */
function Field({
  id,
  label,
  half,
  error,
  note,
  form,
  children
}: {
  id: string;
  label: string;
  half?: boolean;
  error?: string;
  note?: ReactNode;
  form: EnquiryForm;
  children: ReactNode;
}) {
  return (
    <div className={`col-12${half ? " col-md-6" : ""}`}>
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      {children}
      <div className="invalid-feedback" id={feedbackId(id)}>
        {feedbackText(form, id, error || "Required.")}
      </div>
      {note ? <div className="form-note mt-1">{note}</div> : null}
    </div>
  );
}

/** design field() + text(): a text, email, tel, number or amount input. */
export function TextField({
  form,
  id,
  label,
  half,
  type = "text",
  auto,
  amount,
  placeholder,
  required = true,
  error,
  note
}: {
  form: EnquiryForm;
  id: string;
  label: string;
  half?: boolean;
  type?: "text" | "email" | "tel" | "number";
  auto?: string;
  amount?: boolean;
  placeholder?: string;
  required?: boolean;
  error?: string;
  note?: ReactNode;
}) {
  return (
    <Field error={error} form={form} half={half} id={id} label={label} note={note}>
      <input
        autoComplete={auto}
        className={cls(`form-control${amount ? " bxm-amount" : ""}`, form, id)}
        id={id}
        inputMode={amount ? "decimal" : undefined}
        name={id}
        onBlur={amount ? () => form.formatAmount(id) : undefined}
        onChange={(event) => form.setValue(id, event.target.value)}
        placeholder={placeholder || ""}
        required={required}
        type={type}
        value={form.values[id] ?? ""}
        {...invalidProps(form, id)}
      />
    </Field>
  );
}

/** design field() + select(): "Choose" and the options (their text is their value). */
export function SelectField({
  form,
  id,
  label,
  options,
  half
}: {
  form: EnquiryForm;
  id: string;
  label: string;
  options: string[];
  half?: boolean;
}) {
  return (
    <Field form={form} half={half} id={id} label={label}>
      <select
        className={cls("form-select", form, id)}
        id={id}
        name={id}
        onChange={(event) => form.setValue(id, event.target.value)}
        required
        value={form.values[id] ?? ""}
        {...invalidProps(form, id)}
      >
        <option value="">Choose</option>
        {options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    </Field>
  );
}

/**
 * The design's textareas: "What is the money for?" / "Anything we should know?" (optional, no
 * feedback line) and the contact message (required, "Required."). A server error on an optional
 * one is shown under it too.
 */
export function TextAreaField({
  form,
  id,
  label,
  rows,
  placeholder,
  required = false
}: {
  form: EnquiryForm;
  id: string;
  label: string;
  rows: number;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <div className="col-12">
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      <textarea
        className={cls("form-control", form, id)}
        id={id}
        onChange={(event) => form.setValue(id, event.target.value)}
        placeholder={placeholder}
        required={required}
        rows={rows}
        value={form.values[id] ?? ""}
        {...invalidProps(form, id)}
      />
      {required || typeof form.invalid[id] === "string" ? (
        <div className="invalid-feedback" id={feedbackId(id)}>
          {feedbackText(form, id, "Required.")}
        </div>
      ) : null}
    </div>
  );
}

/** design consent(): the checkbox with its text (privacy notice link) and "Please confirm.". */
export function ConsentField({ form, id, purpose }: { form: EnquiryForm; id: string; purpose: string }) {
  return (
    <div className="col-12">
      <div className="form-check">
        <input
          checked={form.consent}
          className={cls("form-check-input", form, id)}
          id={id}
          onChange={(event) => form.setConsent(event.target.checked)}
          required
          type="checkbox"
          {...invalidProps(form, id)}
        />
        <label className="form-check-label" htmlFor={id}>
          I agree that Garanta processes these details to {purpose}, as described in the{" "}
          <SiteLink href="/legal/privacy">privacy notice</SiteLink>.
        </label>
        <div className="invalid-feedback" id={feedbackId(id)}>
          {feedbackText(form, id, "Please confirm.")}
        </div>
      </div>
    </div>
  );
}

/**
 * Honeypot: a field people never see, reach with the keyboard or hear with a screen reader.
 * Bots that fill every field fill it too; the server then answers as usual and drops the form.
 */
export function Honeypot({ form }: { form: EnquiryForm }) {
  return (
    <div aria-hidden="true" className="visually-hidden">
      <input
        autoComplete="off"
        name="website"
        onChange={(event) => form.setWebsite(event.target.value)}
        tabIndex={-1}
        type="text"
        value={form.website}
      />
    </div>
  );
}

/** The submit button, with the alert above it when the form could not be sent. */
export function SubmitRow({ form, label }: { form: EnquiryForm; label: string }) {
  return (
    <>
      {form.alert ? (
        <div className="col-12">
          <div className="alert alert-danger" role="alert">
            {form.alert}
          </div>
        </div>
      ) : null}
      <div className="col-12">
        <button className="btn btn-lg btn-primary" disabled={form.pending} type="submit">
          {label}
        </button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------------------------
// Done boxes

/** The done box scrolls to the middle of the screen when it appears (design site-apply). */
function useScrollIntoView<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.scrollIntoView({ block: "center" });
  }, []);
  return ref;
}

const NEXT_STEPS: Record<"company" | "originator", [string, string][]> = {
  company: [
    ["First answer", "Within two business days, from a credit analyst, by email or phone."],
    ["Documents", "We ask for financial statements, the credit report consent and the security documents."],
    ["Offer", "Rate, fee and terms, about ten business days after we have everything."]
  ],
  originator: [
    ["Introduction call", "Within a week, with our head of partnerships."],
    ["Due diligence", "Your company, licence, loan data of the last three years and servicing."],
    ["Framework agreement", "Eligibility of claims, price, recourse and reporting."]
  ]
};

/** design doneBox(kind): For companies and For loan originators. */
export function DoneBox({ kind, sent, onAgain }: { kind: "company" | "originator"; sent: EnquirySent; onAgain: () => void }) {
  const ref = useScrollIntoView<HTMLDivElement>();
  return (
    <div className="site-form site-form-done" ref={ref} role="status">
      <NiIcon name="ni-check-circle" />
      <h3 className="site-h3">Thank you, we have your {kind === "company" ? "application" : "request"}</h3>
      <p className="site-text">
        Reference <strong>{sent.reference}</strong>. Your message was sent successfully.
      </p>
      <ol className="site-steps-list mt-4 mb-4">
        {NEXT_STEPS[kind].map(([title, text]) => (
          <li key={title}>
            <strong>{title}</strong>
            <span>{text}</span>
          </li>
        ))}
      </ol>
      <button className="btn btn-lg btn-site-outline" onClick={onAgain} type="button">
        Send another
      </button>
    </div>
  );
}

/** The contact page's done box (design contact()). */
export function ContactDoneBox({ sent, onAgain }: { sent: EnquirySent; onAgain: () => void }) {
  const ref = useScrollIntoView<HTMLDivElement>();
  return (
    <div className="site-form site-form-done" ref={ref} role="status">
      <NiIcon name="ni-check-circle" />
      <h3 className="site-h3">Thank you, we will answer soon</h3>
      <p className="site-text">
        Reference <strong>{sent.reference}</strong>. Your message was sent successfully. We usually answer within one
        business day, at {sent.email}.
      </p>
      <button className="btn btn-lg btn-site-outline" onClick={onAgain} type="button">
        Send another message
      </button>
    </div>
  );
}
