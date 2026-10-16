// IP of Webby-Soft SRL.
/*
 * The three public forms (For companies, For loan originators, Contact): field specs, the
 * design's check (shell.js checkForm), the request body of POST /api/v1/public/enquiries/ and
 * the reading of its errors, and the form state hook. The markup is in EnquiryForm.tsx and the
 * pages; this file holds no components (React Fast Refresh).
 *
 * Abuse guards on the client side (the server decides): a honeypot field "website" that people
 * never see or reach, and "elapsed_ms", the time from showing the form to sending it.
 */
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  errorDetail,
  fieldErrors,
  isThrottled,
  useEnquirySubmit,
  type CompanyEnquiryFields,
  type ContactEnquiryFields,
  type EnquiryBody,
  type EnquiryKind,
  type OriginatorEnquiryFields
} from "../data";
import { ApiClientError } from "../../api/client/httpClient";
import { cleanAmountInput, num, parseAmount } from "../format";

/** The design's email check (shell.js checkForm). */
export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Shown when the server gives no message (for a 429 it always gives one). */
export const ENQUIRY_FALLBACK_ERROR = "Something went wrong. Please try again.";
export const ENQUIRY_THROTTLED_FALLBACK = "Too many messages. Please try again later or write to us by email.";

type FieldNames = {
  company: keyof CompanyEnquiryFields;
  originator: keyof OriginatorEnquiryFields;
  contact: keyof ContactEnquiryFields;
};

export type EnquiryFieldSpec<K extends EnquiryKind> = {
  /** The design's element id (co-name, or-book, ct-msg...). */
  id: string;
  /** The contract's field name. */
  name: FieldNames[K];
  required: boolean;
  email?: boolean;
  /** Amount field (design class bxm-amount): filtered while typing, formatted on blur. */
  amount?: boolean;
};

export type EnquiryFormSpec<K extends EnquiryKind> = {
  kind: K;
  /** In the order of the form (the first invalid field gets the focus). */
  fields: EnquiryFieldSpec<K>[];
  /** The consent checkbox, after every field. */
  consentId: string;
};

export const COMPANY_FORM: EnquiryFormSpec<"company"> = {
  kind: "company",
  fields: [
    { id: "co-name", name: "company_name", required: true },
    { id: "co-country", name: "country", required: true },
    { id: "co-reg", name: "company_number", required: true },
    { id: "co-amount", name: "amount", required: true, amount: true },
    { id: "co-term", name: "term", required: true },
    { id: "co-purpose", name: "purpose", required: true },
    { id: "co-security", name: "security", required: true },
    { id: "co-revenue", name: "revenue", required: false, amount: true },
    { id: "co-founded", name: "founded", required: true },
    { id: "co-about", name: "about", required: false },
    { id: "co-contact", name: "contact_name", required: true },
    { id: "co-role", name: "role", required: true },
    { id: "co-email", name: "email", required: true, email: true },
    { id: "co-phone", name: "phone", required: true }
  ],
  consentId: "co-consent"
};

export const ORIGINATOR_FORM: EnquiryFormSpec<"originator"> = {
  kind: "originator",
  fields: [
    { id: "or-name", name: "company_name", required: true },
    { id: "or-country", name: "country", required: true },
    { id: "or-licence", name: "licence", required: true },
    { id: "or-product", name: "product", required: true },
    { id: "or-book", name: "loan_book", required: true, amount: true },
    { id: "or-about", name: "about", required: false },
    { id: "or-contact", name: "contact_name", required: true },
    { id: "or-email", name: "email", required: true, email: true }
  ],
  consentId: "or-consent"
};

export const CONTACT_FORM: EnquiryFormSpec<"contact"> = {
  kind: "contact",
  fields: [
    { id: "ct-name", name: "name", required: true },
    { id: "ct-email", name: "email", required: true, email: true },
    { id: "ct-topic", name: "topic", required: true },
    { id: "ct-msg", name: "message", required: true }
  ],
  consentId: "ct-consent"
};

/** The country options of the company and loan originator forms. */
export const ENQUIRY_COUNTRIES = ["Switzerland", "Germany", "Austria", "Italy", "Romania", "France", "Other EU country"];

/** "Apply now" / "Talk to us": smooth scroll to the form section (design site-scroll). */
export function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export type EnquiryValues = Record<string, string>;

/**
 * The design's checkForm: every required field filled (the consent ticked), emails in a valid
 * format. Returns the ids of the invalid fields, in the order of the form.
 */
export function checkEnquiry<K extends EnquiryKind>(spec: EnquiryFormSpec<K>, values: EnquiryValues, consent: boolean) {
  const invalid: string[] = [];
  spec.fields.forEach((field) => {
    if (!field.required) return;
    const value = (values[field.id] ?? "").trim();
    if (!value || (field.email && !EMAIL_PATTERN.test(value))) invalid.push(field.id);
  });
  if (!consent) invalid.push(spec.consentId);
  return invalid;
}

/**
 * The request body: the design ids mapped to the contract names, values trimmed, empty
 * optional fields left out; consent (always true once the check passed), the honeypot and the
 * time since the form was shown.
 */
export function buildEnquiryBody<K extends EnquiryKind>(
  spec: EnquiryFormSpec<K>,
  values: EnquiryValues,
  guards: { website: string; elapsedMs: number }
): EnquiryBody {
  const fields: Record<string, string> = {};
  spec.fields.forEach((field) => {
    const value = (values[field.id] ?? "").trim();
    if (value || field.required) fields[field.name] = value;
  });
  // The spec names exactly the contract's fields of its kind (typed by EnquiryFieldSpec<K>).
  return {
    kind: spec.kind,
    fields,
    consent: true,
    website: guards.website,
    elapsed_ms: Math.max(0, Math.round(guards.elapsedMs))
  } as unknown as EnquiryBody;
}

export type EnquiryErrors = {
  /** Field id -> the server's message. */
  fields: Record<string, string>;
  /** Message for the alert above the submit button (throttled, or no field to show it on). */
  alert: string | null;
};

/**
 * Reads an error of POST /public/enquiries/: field errors (400 { fields: { name: [...] } },
 * consent at the top level) go to their inputs; a 429 and anything else go to the alert.
 */
export function readEnquiryErrors<K extends EnquiryKind>(spec: EnquiryFormSpec<K>, error: unknown): EnquiryErrors {
  if (isThrottled(error)) return { fields: {}, alert: errorDetail(error, ENQUIRY_THROTTLED_FALLBACK) };
  const byName = fieldErrors(error);
  const fields: Record<string, string> = {};
  spec.fields.forEach((field) => {
    const messages = byName[field.name];
    if (messages?.length) fields[field.id] = messages[0];
  });
  const consent = topLevelMessage(error, "consent") ?? byName.consent?.[0];
  if (consent) fields[spec.consentId] = consent;
  if (Object.keys(fields).length) return { fields, alert: null };
  return { fields: {}, alert: errorDetail(error, ENQUIRY_FALLBACK_ERROR) };
}

function topLevelMessage(error: unknown, key: string): string | null {
  if (!(error instanceof ApiClientError) || error.status !== 400 || !error.payload || typeof error.payload !== "object") {
    return null;
  }
  const value = (error.payload as Record<string, unknown>)[key];
  if (Array.isArray(value) && value.length) return String(value[0]);
  if (typeof value === "string" && value) return value;
  return null;
}

/** What the done box shows. */
export type EnquirySent = { reference: string; email: string };

/**
 * State of one form: values, the design's invalid marks (true: the design's message; a string:
 * the server's message), the alert, the honeypot, and submit. onSent gets the API reference.
 */
export function useEnquiryForm<K extends EnquiryKind>(spec: EnquiryFormSpec<K>, onSent: (sent: EnquirySent) => void) {
  const submit = useEnquirySubmit();
  const [values, setValues] = useState<EnquiryValues>(() => Object.fromEntries(spec.fields.map((field) => [field.id, ""])));
  const [consent, setConsentState] = useState(false);
  const [website, setWebsite] = useState("");
  const [invalid, setInvalid] = useState<Record<string, true | string>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const shownAt = useRef(0);

  useEffect(() => {
    shownAt.current = Date.now();
  }, []);

  const clearInvalid = (id: string) =>
    setInvalid((current) => {
      if (!(id in current)) return current;
      const next = { ...current };
      delete next[id];
      return next;
    });

  const focus = (id: string | undefined) => {
    if (id) document.getElementById(id)?.focus();
  };

  const amountIds = new Set(spec.fields.filter((field) => field.amount).map((field) => field.id));

  return {
    values,
    consent,
    website,
    invalid,
    alert,
    pending: submit.isPending,
    /** The design's input handler: an edit clears the field's invalid mark. */
    setValue(id: string, value: string) {
      setValues((current) => ({ ...current, [id]: amountIds.has(id) ? cleanAmountInput(value) : value }));
      clearInvalid(id);
    },
    /** Amount fields show 1,234.56 once the visitor leaves them (core.js focusout). */
    formatAmount(id: string) {
      const parsed = parseAmount(values[id]);
      if (!Number.isNaN(parsed)) setValues((current) => ({ ...current, [id]: num(parsed) }));
    },
    setConsent(checked: boolean) {
      setConsentState(checked);
      clearInvalid(spec.consentId);
    },
    setWebsite,
    onSubmit(event: FormEvent<HTMLFormElement>) {
      event.preventDefault();
      if (submit.isPending) return;
      const failed = checkEnquiry(spec, values, consent);
      setInvalid(Object.fromEntries(failed.map((id) => [id, true as const])));
      setAlert(null);
      if (failed.length) {
        focus(failed[0]);
        return;
      }
      const email = (values[spec.fields.find((field) => field.email)?.id ?? ""] ?? "").trim();
      const body = buildEnquiryBody(spec, values, { website, elapsedMs: Date.now() - shownAt.current });
      submit.mutate(body, {
        onSuccess: (response) => onSent({ reference: response.reference, email }),
        onError: (error) => {
          const errors = readEnquiryErrors(spec, error);
          setInvalid(errors.fields);
          setAlert(errors.alert);
          const ids = [...spec.fields.map((field) => field.id), spec.consentId];
          focus(ids.find((id) => id in errors.fields));
        }
      });
    }
  };
}

export type EnquiryForm = ReturnType<typeof useEnquiryForm>;
