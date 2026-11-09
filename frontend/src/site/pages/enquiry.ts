// IP of Webby-Soft SRL.
/*
 * The three public forms (For borrowers, For loan originators, Contact; U33 field sets): field
 * specs, the check before sending, the request body of POST /api/v1/public/enquiries/ and the
 * reading of its errors, and the form state hook. The markup is in u33/forms.tsx and the U33
 * pages; this file holds no components (React Fast Refresh).
 *
 * Abuse guards on the client side (the server decides): a honeypot field "website" that people
 * never see or reach, and "elapsed_ms", the time from showing the form to sending it.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

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

/** The email check before sending (the server checks again). */
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
  /** The design's element id (company-name, originator-loan-type, contact-message...). */
  id: string;
  /** The contract's field name. */
  name: FieldNames[K];
  required: boolean;
  email?: boolean;
  /** Amount field: filtered while typing, formatted on blur (1,234.56). */
  amount?: boolean;
  /** Value of a new form ("EUR" for the currency select). */
  initial?: string;
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
    { id: "company-name", name: "company_name", required: true },
    { id: "company-country", name: "country", required: true },
    { id: "company-currency", name: "currency", required: true, initial: "EUR" },
    { id: "company-amount", name: "amount", required: true, amount: true },
    { id: "company-purpose", name: "purpose", required: true },
    { id: "company-collateral", name: "collateral", required: true },
    { id: "company-contact-name", name: "contact_name", required: true },
    { id: "company-email", name: "email", required: true, email: true }
  ],
  consentId: "company-consent"
};

export const ORIGINATOR_FORM: EnquiryFormSpec<"originator"> = {
  kind: "originator",
  fields: [
    { id: "originator-company", name: "company_name", required: true },
    { id: "originator-country", name: "country", required: true },
    { id: "originator-name", name: "contact_name", required: true },
    { id: "originator-email", name: "email", required: true, email: true },
    { id: "originator-loan-type", name: "proposal", required: true },
    { id: "originator-message", name: "about", required: false }
  ],
  consentId: "originator-consent"
};

export const CONTACT_FORM: EnquiryFormSpec<"contact"> = {
  kind: "contact",
  fields: [
    { id: "contact-name", name: "name", required: true },
    { id: "contact-email", name: "email", required: true, email: true },
    { id: "contact-topic", name: "topic", required: false },
    { id: "contact-message", name: "message", required: false }
  ],
  consentId: "contact-consent"
};

/** The loan currencies of the For borrowers form. */
export const ENQUIRY_CURRENCIES = ["EUR", "CHF"];

/** The proposal types of the For loan originators form (value = label, as the server lists them). */
export const ORIGINATOR_PROPOSALS = ["New loans", "Refinancing of existing loans", "Both new and existing loans"];

/** The topics of the Contact form (optional). */
export const CONTACT_TOPICS = ["How investing works", "An opportunity", "Another question"];

export type EnquiryValues = Record<string, string>;

/**
 * The check before sending: every required field filled (the consent ticked), emails in a valid
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
 * State of one form: values, the invalid marks (true: the form's own message; a string: the
 * server's message), the alert, the honeypot, and submit. onSent gets the API reference.
 */
export function useEnquiryForm<K extends EnquiryKind>(spec: EnquiryFormSpec<K>, onSent: (sent: EnquirySent) => void) {
  const submit = useEnquirySubmit();
  const [values, setValues] = useState<EnquiryValues>(() =>
    Object.fromEntries(spec.fields.map((field) => [field.id, field.initial ?? ""]))
  );
  const [consent, setConsentState] = useState(false);
  const [website, setWebsite] = useState("");
  const [invalid, setInvalid] = useState<Record<string, true | string>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const shownAt = useRef(0);

  useEffect(() => {
    shownAt.current = Date.now();
  }, []);

  const clearInvalid = useCallback(
    (id: string) =>
      setInvalid((current) => {
        if (!(id in current)) return current;
        const next = { ...current };
        delete next[id];
        return next;
      }),
    []
  );

  const focus = (id: string | undefined) => {
    if (id) document.getElementById(id)?.focus();
  };

  const amountIds = useMemo(() => new Set(spec.fields.filter((field) => field.amount).map((field) => field.id)), [spec]);
  /** An edit clears the field's invalid mark (stable, for prefills from outside the form). */
  const setValue = useCallback(
    (id: string, value: string) => {
      setValues((current) => ({ ...current, [id]: amountIds.has(id) ? cleanAmountInput(value) : value }));
      clearInvalid(id);
    },
    [amountIds, clearInvalid]
  );

  return {
    values,
    consent,
    website,
    invalid,
    alert,
    pending: submit.isPending,
    setValue,
    /** Amount fields show 1,234.56 once the visitor leaves them. */
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
