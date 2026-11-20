// IP of Webby-Soft SRL.
// Profile & Settings -> Declarations (18.10, Q12, U33-DEC-27): the investor's declarations
// (beneficial owner, sources of funds, PEP, expected yearly volume; company version), the review
// state and the re-verification date. Each submission is a new version; some answers open a
// compliance review, which pauses new investments until it is closed (not a refusal).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState, type FormEvent } from "react";

import {
  getV1KycDeclarationsRetrieveQueryKey,
  useV1KycDeclarationsCreate,
  useV1KycDeclarationsRetrieve,
  type Declaration
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { formatDate } from "../../../../investorPortal/format";
import { Notice, PsPanel, SettingsRow } from "../parts/ui";
import type { AccountData } from "./useAccountData";

const SOURCES: Array<[string, string]> = [
  ["salary", "Salary"],
  ["savings", "Savings"],
  ["sale_of_property", "Sale of property"],
  ["inheritance", "Inheritance"],
  ["business_income", "Business income"],
  ["dividends", "Dividends"],
  ["investment_income", "Investment income"],
  ["rent", "Rent"],
  ["other", "Other"]
];
const BANDS: Array<[string, string]> = [
  ["under_10k", "Under 10,000"],
  ["10k_50k", "10,000 - 50,000"],
  ["50k_250k", "50,000 - 250,000"],
  ["over_250k", "Over 250,000"]
];
const PEP: Array<[string, string]> = [
  ["no", "No"],
  ["yes", "Yes"],
  ["not_sure", "Not sure"]
];

type FormState = {
  subject_type: "person" | "company";
  beneficial_owner_is_self: boolean;
  beneficial_owner_name: string;
  sources_of_funds: string[];
  savings_origin: string;
  source_other_text: string;
  pep_status: string;
  pep_person: string;
  pep_relation: string;
  pep_function: string;
  pep_country: string;
  yearly_volume_band: string;
  company_name: string;
  representative_name: string;
  representative_authority: string;
  controlling_persons: string;
};

function initialForm(declaration?: Declaration | null, subject?: "person" | "company"): FormState {
  const company = (declaration?.company_details ?? {}) as Record<string, string>;
  return {
    // Audit S7-1: the subject follows the account type (sent by the server), not a choice.
    subject_type: subject ?? (declaration?.subject_type === "company" ? "company" : "person"),
    beneficial_owner_is_self: declaration ? declaration.beneficial_owner_is_self : true,
    beneficial_owner_name: declaration?.beneficial_owner_name ?? "",
    sources_of_funds: declaration?.sources_of_funds ?? [],
    savings_origin: declaration?.savings_origin ?? "",
    source_other_text: declaration?.source_other_text ?? "",
    pep_status: declaration?.pep_status ?? "",
    pep_person: declaration?.pep_person ?? "",
    pep_relation: declaration?.pep_relation ?? "",
    pep_function: declaration?.pep_function ?? "",
    pep_country: declaration?.pep_country ?? "",
    yearly_volume_band: declaration?.yearly_volume_band ?? "",
    company_name: company.company_name ?? "",
    representative_name: company.representative_name ?? "",
    representative_authority: company.representative_authority ?? "",
    controlling_persons: company.controlling_persons ?? ""
  };
}

function label(options: Array<[string, string]>, value: string) {
  return options.find(([key]) => key === value)?.[1] ?? value;
}

export function DeclarationsTab({ account }: { account: AccountData }) {
  const t = useT();
  const queryClient = useQueryClient();
  const formId = useId();
  const status = useV1KycDeclarationsRetrieve({ query: { enabled: !isFixturePreview && !account.readonly } });
  const mutation = useV1KycDeclarationsCreate();
  const current = status.data?.declaration ?? null;
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<FormState>(() => initialForm(null));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (status.data) setForm(initialForm(status.data.declaration, status.data.declaration_subject));
  }, [status.data]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((previous) => ({ ...previous, [key]: value }));
  const toggleSource = (key: string) =>
    set("sources_of_funds", form.sources_of_funds.includes(key) ? form.sources_of_funds.filter((item) => item !== key) : [...form.sources_of_funds, key]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSaved(false);
    mutation.mutate(
      {
        data: {
          subject_type: form.subject_type,
          beneficial_owner_is_self: form.beneficial_owner_is_self,
          beneficial_owner_name: form.beneficial_owner_name,
          sources_of_funds: form.sources_of_funds as never,
          savings_origin: form.savings_origin,
          source_other_text: form.source_other_text,
          pep_status: form.pep_status as never,
          pep_person: form.pep_person,
          pep_relation: form.pep_relation,
          pep_function: form.pep_function,
          pep_country: form.pep_country,
          yearly_volume_band: form.yearly_volume_band as never,
          company_details:
            form.subject_type === "company"
              ? {
                  company_name: form.company_name,
                  representative_name: form.representative_name,
                  representative_authority: form.representative_authority,
                  controlling_persons: form.controlling_persons
                }
              : {}
        }
      },
      {
        onSuccess: (response) => {
          queryClient.setQueryData(getV1KycDeclarationsRetrieveQueryKey(), response);
          setEditing(false);
          setSaved(true);
        },
        onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : t("Request failed. Retry once the connection is restored."))
      }
    );
  };

  if (isFixturePreview || account.readonly) {
    return <Notice title={t("Declarations")}>{t("Your declarations are shown with live data only.")}</Notice>;
  }
  if (status.isLoading) return <p className="bxm-muted">{t("Loading...")}</p>;
  const data = status.data;
  const showForm = editing || !current;

  return (
    <div className="ps-stack">
      {data?.review_open ? (
        <Notice title={t("Compliance review in progress")} tone="warning">
          {data.review_message || t("Our compliance team is reviewing your declarations. New investments are paused until the review is closed. Your account, documents and investments stay available.")}
        </Notice>
      ) : null}
      {!current ? (
        <Notice title={t("Complete your declarations")} tone="info">
          {t("We need these answers before your next investment. They take about two minutes.")}
        </Notice>
      ) : null}
      {data?.reverification_due_date ? (
        <Notice title={t("Re-verification")} tone={data.investment_block === "reverification_due" ? "danger" : "info"}>
          {t("Please update your details and declarations by {date}.", { date: formatDate(data.reverification_due_date) })}
        </Notice>
      ) : null}
      {saved ? <Notice tone="success">{t("Your declarations are saved.")}</Notice> : null}

      {current && !showForm ? (
        <PsPanel title={t("Your declarations")} status={<span className="bxm-row-note">{t("Version {n} · {date}", { n: current.version, date: formatDate(current.submitted_at) })}</span>}>
          <SettingsRow title={t("Beneficial owner of the funds")} description={current.beneficial_owner_is_self ? t("I am the beneficial owner") : current.beneficial_owner_name} />
          <SettingsRow title={t("Sources of funds")} description={current.sources_of_funds.map((key) => t(label(SOURCES, key))).join(", ")} />
          <SettingsRow title={t("Politically exposed person")} description={t(label(PEP, current.pep_status))} />
          <SettingsRow title={t("Expected yearly investment volume")} description={t(label(BANDS, current.yearly_volume_band))} />
          <div className="card-inner">
            <button className="btn btn-outline-primary" onClick={() => setEditing(true)} type="button">
              {t("Update declarations")}
            </button>
          </div>
        </PsPanel>
      ) : null}

      {showForm ? (
        <PsPanel title={current ? t("Update your declarations") : t("Your declarations")}>
          <form aria-label={t("Declarations")} className="card-inner u33-declarations-form" id={formId} onSubmit={submit}>
            <fieldset className="mb-3">
              <legend className="form-label">{t("Who invests?")}</legend>
              <p className="u33-muted mb-0">{form.subject_type === "company" ? t("A company invests (company account).") : t("I invest as a private person (private account).")}</p>
            </fieldset>
            {form.subject_type === "company" ? (
              <div className="row g-2 mb-3">
                {(
                  [
                    ["company_name", "Company name"],
                    ["representative_name", "Representative"],
                    ["representative_authority", "Representative's authority"],
                    ["controlling_persons", "Controlling persons"]
                  ] as const
                ).map(([key, text]) => (
                  <label className="col-md-6" key={key}>
                    <span className="form-label">{t(text)}</span>
                    <input className="form-control" onChange={(event) => set(key, event.target.value)} value={form[key]} />
                  </label>
                ))}
              </div>
            ) : null}
            <fieldset className="mb-3">
              <legend className="form-label">{t("Are you the beneficial owner of the funds you invest?")}</legend>
              {[true, false].map((value) => (
                <label className="form-check form-check-inline" key={String(value)}>
                  <input checked={form.beneficial_owner_is_self === value} className="form-check-input" name="beneficial_owner" onChange={() => set("beneficial_owner_is_self", value)} type="radio" />
                  <span className="form-check-label">{value ? t("Yes") : t("No")}</span>
                </label>
              ))}
              {!form.beneficial_owner_is_self ? (
                <label className="d-block mt-2">
                  <span className="form-label">{t("Name of the beneficial owner")}</span>
                  <input className="form-control" onChange={(event) => set("beneficial_owner_name", event.target.value)} value={form.beneficial_owner_name} />
                </label>
              ) : null}
            </fieldset>
            <fieldset className="mb-3">
              <legend className="form-label">{t("Where does the money come from? (choose all that apply)")}</legend>
              {SOURCES.map(([key, text]) => (
                <label className="form-check" key={key}>
                  <input checked={form.sources_of_funds.includes(key)} className="form-check-input" onChange={() => toggleSource(key)} type="checkbox" />
                  <span className="form-check-label">{t(text)}</span>
                </label>
              ))}
              {form.sources_of_funds.includes("savings") ? (
                <label className="d-block mt-2">
                  <span className="form-label">{t("Where do the savings come from?")}</span>
                  <input className="form-control" onChange={(event) => set("savings_origin", event.target.value)} value={form.savings_origin} />
                </label>
              ) : null}
              {form.sources_of_funds.includes("other") ? (
                <label className="d-block mt-2">
                  <span className="form-label">{t("Explain the other source")}</span>
                  <input className="form-control" onChange={(event) => set("source_other_text", event.target.value)} value={form.source_other_text} />
                </label>
              ) : null}
            </fieldset>
            <fieldset className="mb-3">
              <legend className="form-label">{t("Are you, a close family member or a close associate a politically exposed person?")}</legend>
              {PEP.map(([key, text]) => (
                <label className="form-check form-check-inline" key={key}>
                  <input checked={form.pep_status === key} className="form-check-input" name="pep_status" onChange={() => set("pep_status", key)} type="radio" />
                  <span className="form-check-label">{t(text)}</span>
                </label>
              ))}
              {form.pep_status === "yes" ? (
                <div className="row g-2 mt-1">
                  {(
                    [
                      ["pep_person", "Person"],
                      ["pep_relation", "Relation to you"],
                      ["pep_function", "Function"],
                      ["pep_country", "Country"]
                    ] as const
                  ).map(([key, text]) => (
                    <label className="col-md-6" key={key}>
                      <span className="form-label">{t(text)}</span>
                      <input className="form-control" onChange={(event) => set(key, event.target.value)} value={form[key]} />
                    </label>
                  ))}
                </div>
              ) : null}
            </fieldset>
            <label className="d-block mb-3">
              <span className="form-label">{t("Expected yearly investment volume")}</span>
              <select className="form-select" onChange={(event) => set("yearly_volume_band", event.target.value)} value={form.yearly_volume_band}>
                <option value="">{t("Choose")}</option>
                {BANDS.map(([key, text]) => (
                  <option key={key} value={key}>
                    {t(text)}
                  </option>
                ))}
              </select>
            </label>
            {error ? (
              <p className="text-danger" role="alert">
                {error}
              </p>
            ) : null}
            <div className="d-flex gap-2">
              <button className="btn btn-primary" disabled={mutation.isPending} type="submit">
                {t("Save declarations")}
              </button>
              {current ? (
                <button className="btn btn-outline-light" onClick={() => setEditing(false)} type="button">
                  {t("Cancel")}
                </button>
              ) : null}
            </div>
          </form>
        </PsPanel>
      ) : null}
    </div>
  );
}
