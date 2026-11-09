// IP of Webby-Soft SRL.
/*
 * Fields of the three U33 public forms (design business-form / contact-form markup: .field,
 * label, input), bound to the enquiry form state (pages/enquiry.ts useEnquiryForm). Additions the
 * design has no need for: the error line under an invalid field (aria-invalid,
 * aria-describedby), the consent checkbox (the endpoint requires consent), the honeypot, the
 * alert above the submit button and the "sent" state with the reference.
 */
import { useEffect, useRef, type ReactNode } from "react";

import { useT } from "../../i18n";
import type { EnquiryForm, EnquirySent } from "../pages/enquiry";
import { Ni, PublicLink } from "./ui";

function feedbackId(id: string) {
  return `${id}-feedback`;
}

function invalidProps(form: EnquiryForm, id: string) {
  return id in form.invalid ? { "aria-invalid": true as const, "aria-describedby": feedbackId(id) } : {};
}

/** The message under an invalid field: the server's, else the form's own. */
export function FieldError({ form, id, fallback }: { form: EnquiryForm; id: string; fallback: string }) {
  if (!(id in form.invalid)) return null;
  const mark = form.invalid[id];
  return (
    <p className="bxp-field-error" id={feedbackId(id)}>
      {typeof mark === "string" ? mark : fallback}
    </p>
  );
}

type FieldProps = {
  form: EnquiryForm;
  id: string;
  label: ReactNode;
  full?: boolean;
  error?: string;
  children: ReactNode;
};

/** design .field: label, control, and (ours) the error line. */
export function Field({ form, id, label, full, error, children }: FieldProps) {
  const t = useT();
  return (
    <div className={full ? "field full-span" : "field"}>
      <label htmlFor={id}>{label}</label>
      {children}
      <FieldError fallback={error ?? t("Please fill in this field.")} form={form} id={id} />
    </div>
  );
}

export function TextInput({
  form,
  id,
  type = "text",
  autoComplete,
  placeholder,
  maxLength,
  amount
}: {
  form: EnquiryForm;
  id: string;
  type?: "text" | "email";
  autoComplete?: string;
  placeholder?: string;
  maxLength?: number;
  amount?: boolean;
}) {
  return (
    <input
      autoComplete={autoComplete}
      id={id}
      inputMode={amount ? "decimal" : undefined}
      maxLength={maxLength}
      name={id}
      onBlur={amount ? () => form.formatAmount(id) : undefined}
      onChange={(event) => form.setValue(id, event.target.value)}
      placeholder={placeholder}
      type={type}
      value={form.values[id] ?? ""}
      {...invalidProps(form, id)}
    />
  );
}

export function TextArea({ form, id, rows, placeholder, maxLength }: { form: EnquiryForm; id: string; rows: number; placeholder?: string; maxLength?: number }) {
  return (
    <textarea
      id={id}
      maxLength={maxLength}
      name={id}
      onChange={(event) => form.setValue(id, event.target.value)}
      placeholder={placeholder}
      rows={rows}
      value={form.values[id] ?? ""}
      {...invalidProps(form, id)}
    />
  );
}

export function Select({
  form,
  id,
  options,
  placeholder,
  ariaLabel
}: {
  form: EnquiryForm;
  id: string;
  options: { value: string; label: string }[];
  placeholder?: string;
  ariaLabel?: string;
}) {
  return (
    <select
      aria-label={ariaLabel}
      id={id}
      name={id}
      onChange={(event) => form.setValue(id, event.target.value)}
      value={form.values[id] ?? ""}
      {...invalidProps(form, id)}
    >
      {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/** The consent the endpoint requires (U33 forms have none; the October text, U33 style). */
export function Consent({ form, id }: { form: EnquiryForm; id: string }) {
  const t = useT();
  return (
    <div className="bxp-consent full-span">
      <input
        checked={form.consent}
        id={id}
        onChange={(event) => form.setConsent(event.target.checked)}
        type="checkbox"
        {...invalidProps(form, id)}
      />
      <label htmlFor={id}>
        {t("I agree that Garanta Finanzgruppe AG processes these details to answer my request, as described in the")}{" "}
        <PublicLink href="/legal/privacy">{t("privacy policy")}</PublicLink>.
      </label>
      <FieldError fallback={t("Please confirm.")} form={form} id={id} />
    </div>
  );
}

/**
 * Honeypot: a field people never see, reach with the keyboard or hear with a screen reader.
 * Bots that fill every field fill it too; the server then answers as usual and drops the form.
 */
export function Honeypot({ form }: { form: EnquiryForm }) {
  return (
    <div aria-hidden="true" className="bxp-honeypot">
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

/** The alert above the submit button: throttled, or an error without a field to show it on. */
export function FormAlert({ form }: { form: EnquiryForm }) {
  if (!form.alert) return null;
  return (
    <p className="bxp-form-alert" role="alert">
      <Ni glyph="alert" /> {form.alert}
    </p>
  );
}

/** The form after a successful send: thanks, the reference, the reply channel, "send another". */
export function SentState({ title, sent, againLabel, onAgain }: { title: string; sent: EnquirySent; againLabel: string; onAgain: () => void }) {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
    ref.current?.scrollIntoView?.({ block: "center" });
  }, []);
  return (
    <div className="bxp-form-sent" ref={ref} role="status" tabIndex={-1}>
      <Ni className="bxp-form-sent-icon" glyph="checkCircle" />
      <h3>{title}</h3>
      <p>
        {t("Reference")} <strong>{sent.reference}</strong>. {t("A member of our team will reply by email to {email}.", { email: sent.email })}
      </p>
      <button className="bxp-button" onClick={onAgain} type="button">
        {againLabel}
      </button>
    </div>
  );
}
