// IP of Webby-Soft SRL.
// Smart Invest setup and edit (design: the guided steps of #/auto-invest, .si-wizard.si-guided). Steps
// for the criteria the backend applies today: Currency, Interest & duration, Security, Review (with the
// originator under "More preferences"). The design's Repayments step, loan-to-value, country, usual
// amount and notification channels come with Phase 17.2 (U33-DEC-19); the step list is data so the
// Repayments step can be added back. Editing starts from the saved preferences and saves at the end.
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";

import type { MarketplaceLoanPreview } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { formatDecimal, useNumberFormat } from "../../../investorPortal/format";
import { InfoTip, NiIcon } from "../../components";
import { SECURITY_GROUPS, securityLabel, securityPreferenceText } from "./parts/labels";
import { BANXUM_SOURCE, SMART_CURRENCIES, hasEffectiveCriterion, isOpenOpportunity, matchesPreferences, type SmartPreferences } from "./parts/smartInvestModel";

type StepKey = "currency" | "rates" | "security" | "review";
const STEPS: Array<{ key: StepKey; label: string }> = [
  { key: "currency", label: "Currency" },
  { key: "rates", label: "Interest & duration" },
  { key: "security", label: "Security" },
  { key: "review", label: "Review & activate" }
];

const CURRENCY_NAMES: Record<string, string> = { EUR: "Euro", CHF: "Swiss franc" };

function parseNumber(text: string) {
  const value = Number(text.trim().replace(/['’\s]/g, "").replace(",", "."));
  return text.trim() === "" || !Number.isFinite(value) ? null : value;
}

function RangeField({
  field,
  label,
  context,
  unsetTitle,
  unsetNote,
  prefix,
  unit,
  presets,
  presetLabel,
  min,
  max,
  step,
  decimals,
  value,
  onChange
}: {
  field: string;
  label: string;
  context: string;
  unsetTitle: string;
  unsetNote: string;
  prefix: string;
  unit: string;
  presets: number[];
  presetLabel: (value: number) => string;
  min: number;
  max: number;
  step: number;
  decimals: number;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const t = useT();
  useNumberFormat();
  const inputId = useId();
  const titleId = useId();
  const editorId = useId();
  const [limit, setLimit] = useState(value !== null);
  const [text, setText] = useState<string | null>(null);
  const top = Math.max(max, value ?? 0);
  const fill = value === null ? 0 : ((value - min) / (top - min)) * 100;
  const shown = text ?? (value === null ? "" : formatDecimal(value, decimals));
  return (
    <div className="si-range-field rc-smart-range" data-field={field} style={{ "--rc-range-fill": `${fill}%` } as CSSProperties}>
      <div className="si-range-heading">
        <label htmlFor={inputId} id={titleId}>{label}</label>
        <div aria-labelledby={titleId} className="rc-range-toggle" role="group">
          <button aria-pressed={!limit} onClick={() => { setLimit(false); setText(null); onChange(null); }} type="button">{t("No preference")}</button>
          <button aria-controls={editorId} aria-expanded={limit} aria-pressed={limit} onClick={() => setLimit(true)} type="button">{t("Set a limit")}</button>
        </div>
      </div>
      {context ? <p className="si94f-range-context">{context}</p> : null}
      <div className="rc-range-unset" hidden={limit}>
        <NiIcon name="minus-circle" />
        <div>
          {unsetTitle}
          <small>{unsetNote}</small>
        </div>
      </div>
      <div className="rc-range-editor" hidden={!limit} id={editorId}>
        <div className="rc-range-input-row">
          <span>{prefix}</span>
          <div aria-label={label} className="si94f-presets" role="group">
            {presets.map((preset) => (
              <button aria-label={presetLabel(preset)} aria-pressed={value === preset} key={preset} onClick={() => { setText(null); onChange(preset); }} type="button">
                {field === "minRate" ? `${preset}%+` : preset}
              </button>
            ))}
          </div>
          <label className="si-range-value">
            <input
              aria-label={`${label} ${unit}`}
              className="form-control"
              id={inputId}
              inputMode="decimal"
              onBlur={() => setText(null)}
              onChange={(event) => {
                setText(event.target.value);
                const parsed = parseNumber(event.target.value);
                onChange(parsed === null ? null : Math.min(Math.max(parsed, min), field === "minRate" ? 100 : 1200));
              }}
              placeholder="—"
              type="text"
              value={shown}
            />
            <span>{unit}</span>
          </label>
        </div>
        <input
          aria-label={label}
          aria-valuetext={value === null ? t("No preference") : `${formatDecimal(value, decimals)} ${unit}`}
          max={top}
          min={min}
          onChange={(event) => { setText(null); onChange(Number(event.target.value)); }}
          step={step}
          type="range"
          value={value ?? min}
        />
        <div className="si-range-foot">
          <span>{field === "minRate" ? `${formatDecimal(min, 0)}%` : t("1 month")}</span>
          <span>{field === "minRate" ? `${formatDecimal(top, 0)}%` : t("{count} months", { count: top })}</span>
        </div>
        {value === null ? <p className="rc-range-pending">{t("Enter a value or move the slider to apply a limit.")}</p> : null}
      </div>
    </div>
  );
}

export function SmartInvestWizard({
  mode,
  initial,
  loans,
  originators,
  retired,
  saving,
  error,
  onCancel,
  onSave
}: {
  mode: "setup" | "edit";
  initial: SmartPreferences;
  loans: MarketplaceLoanPreview[];
  originators: Array<{ id: string; name: string }>;
  /** Criteria of the saved rule that saving removes (risk ratings, purposes, loan kinds). */
  retired: string[];
  saving: boolean;
  error: string;
  onCancel: () => void;
  onSave: (preferences: SmartPreferences) => void;
}) {
  const t = useT();
  useNumberFormat();
  const [stepIndex, setStepIndex] = useState(0);
  const [preferences, setPreferences] = useState<SmartPreferences>(initial);
  const [currencyError, setCurrencyError] = useState(false);
  const [criterionError, setCriterionError] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);
  const step = STEPS[stepIndex];
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [stepIndex]);

  const open = loans.filter(isOpenOpportunity);
  const matching = open.filter((loan) => matchesPreferences(loan, preferences));
  const yields = open.map((loan) => (loan.yield_bps || loan.interest_rate_bps) / 100);
  const terms = open.map((loan) => loan.term_months);
  const update = (patch: Partial<SmartPreferences>) => {
    setPreferences((current) => ({ ...current, ...patch }));
    setCriterionError(false);
  };
  const reviewLabel = mode === "edit" ? t("Review & save") : t("Review & activate");
  const stepLabel = (key: StepKey, label: string) => (key === "review" ? reviewLabel : t(label));

  const next = () => {
    if (step.key === "currency" && preferences.currencies.length === 0) {
      setCurrencyError(true);
      return;
    }
    if (step.key === "review") {
      if (!hasEffectiveCriterion(preferences)) {
        setCriterionError(true);
        return;
      }
      onSave(preferences);
      return;
    }
    setStepIndex((index) => Math.min(STEPS.length - 1, index + 1));
  };

  const security = preferences.security;
  const toggleSecurity = (type: string) => {
    const current = security ?? [];
    const nextList = current.includes(type) ? current.filter((item) => item !== type) : [...current, type];
    update({ security: nextList.length === 0 ? null : nextList });
  };
  const toggleGroup = (types: string[]) => {
    const current = security ?? [];
    const all = types.every((type) => current.includes(type));
    const nextList = all ? current.filter((type) => !types.includes(type)) : Array.from(new Set([...current, ...types]));
    update({ security: nextList.length === 0 ? null : nextList });
  };

  const currencySummary = preferences.currencies.length === SMART_CURRENCIES.length ? SMART_CURRENCIES.join(" · ") : preferences.currencies.join(" · ");
  const securitySummary = security === null ? t("no preference") : securityPreferenceText(security);
  const originatorValue = preferences.originators.length === 0 ? "" : preferences.originators.length === 1 ? preferences.originators[0] : "__several__";
  const originatorOptions = [
    { value: BANXUM_SOURCE, label: t("Banxum (direct loans)") },
    ...originators.map((originator) => ({ value: originator.id, label: originator.name })),
    ...preferences.originators
      .filter((id) => id !== BANXUM_SOURCE && !originators.some((originator) => originator.id === id))
      .map((id) => ({ value: id, label: t("Originator saved in your preferences") }))
  ];

  const body: Record<StepKey, ReactNode> = {
    currency: (
      <>
        <h4 id="si-step-heading" ref={headingRef} tabIndex={-1}>{t("Choose your currencies")}</h4>
        <p className="si-setup-intro">{t("Choose one or both currencies for your investments. EUR and CHF stay separate; nothing is converted.")}</p>
        <fieldset className="si-guided-currencies si-setup-field">
          <legend className="visually-hidden">{t("Currencies")}</legend>
          <div>
            {SMART_CURRENCIES.map((code) => (
              <label className="si-currency-card" key={code}>
                <input
                  checked={preferences.currencies.includes(code)}
                  name="currencies"
                  onChange={() => {
                    setCurrencyError(false);
                    update({ currencies: preferences.currencies.includes(code) ? preferences.currencies.filter((item) => item !== code) : [...preferences.currencies, code] });
                  }}
                  type="checkbox"
                  value={code}
                />
                <span>
                  <strong>{code}</strong>
                  <small>{t(CURRENCY_NAMES[code] ?? code)}</small>
                  <NiIcon name="check" />
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        {currencyError ? <p className="si-validation" role="alert">{t("Choose at least one currency.")}</p> : null}
      </>
    ),
    rates: (
      <>
        <h4 id="si-step-heading" ref={headingRef} tabIndex={-1}>{t("Set your interest and duration preferences")}</h4>
        <p className="si-setup-intro">{t("Leave either as No preference if you do not wish to set a limit.")}</p>
        <div className="si-guided-ranges">
          <RangeField
            context={yields.length ? t("Current opportunities · {range}", { range: `${formatDecimal(Math.min(...yields), 1)}–${formatDecimal(Math.max(...yields), 1)}%` }) : ""}
            decimals={1}
            field="minRate"
            label={t("Minimum annual interest rate")}
            max={15}
            min={0}
            onChange={(value) => update({ minRate: value === 0 ? null : value })}
            prefix={t("At least")}
            presetLabel={(value) => t("Minimum interest {value} percent", { value })}
            presets={[6, 7, 8]}
            step={0.1}
            unit="%"
            unsetNote={t("No minimum rate applied.")}
            unsetTitle={t("Any interest rate")}
            value={preferences.minRate}
          />
          <RangeField
            context={terms.length ? t("Current opportunities · {range}", { range: `${Math.min(...terms)}–${Math.max(...terms)} ${t("months")}` }) : ""}
            decimals={0}
            field="maxTerm"
            label={t("Maximum investment duration")}
            max={Math.max(60, ...terms)}
            min={1}
            onChange={(value) => update({ maxTerm: value === null ? null : Math.max(1, Math.round(value)) })}
            prefix={t("Up to")}
            presetLabel={(value) => t("Up to {value} months", { value })}
            presets={[12, 24, 36, 48, 60]}
            step={1}
            unit={t("months")}
            unsetNote={t("No maximum duration applied.")}
            unsetTitle={t("Any duration")}
            value={preferences.maxTerm}
          />
        </div>
        <p className="si-setup-note r31-slider-hint">{t("Move a slider or enter a value to set a limit.")}</p>
      </>
    ),
    security: (
      <>
        <h4 id="si-step-heading" ref={headingRef} tabIndex={-1}>{t("Choose your security preferences")}</h4>
        <fieldset className="rs65-security">
          <legend className="si-setup-label">{t("Security type")}</legend>
          <label className={`rs33-any${security === null ? " is-selected" : ""}`}>
            <input checked={security === null} onChange={() => update({ security: null })} type="checkbox" />
            <span>{t("No preference")}</span>
          </label>
          <div className="rs65-security-grid">
            {SECURITY_GROUPS.map((group) => {
              const selected = group.types.filter((type) => security?.includes(type));
              return (
                <section className="rs65-security-card" data-security-category={group.key} key={group.key}>
                  <label className="rs65-category-title">
                    <span>{t(group.label)}</span>
                    <input
                      aria-label={t("Select all: {group}", { group: t(group.label) })}
                      checked={selected.length === group.types.length}
                      onChange={() => toggleGroup(group.types)}
                      ref={(element) => {
                        if (element) element.indeterminate = selected.length > 0 && selected.length < group.types.length;
                      }}
                      type="checkbox"
                    />
                  </label>
                  <div className="rs65-security-options">
                    {group.types.map((type) => (
                      <label key={type}>
                        <input checked={security?.includes(type) ?? false} name="collateral" onChange={() => toggleSecurity(type)} type="checkbox" value={type} />
                        <span>{securityLabel(type)}</span>
                      </label>
                    ))}
                    {group.key === "other" && security?.includes("unsecured") ? (
                      <label>
                        <input checked name="collateral" onChange={() => toggleSecurity("unsecured")} type="checkbox" value="unsecured" />
                        <span>{t("No collateral (older loans)")}</span>
                      </label>
                    ) : null}
                  </div>
                </section>
              );
            })}
          </div>
          <p className="si-setup-note r53-security-rule">{t("An opportunity needs to match at least one selected security type. Every new loan is secured by collateral or guarantees.")}</p>
        </fieldset>
      </>
    ),
    review: (
      <>
        <h4 id="si-step-heading" ref={headingRef} tabIndex={-1}>{mode === "edit" ? t("Review & save your preferences") : t("Review & activate Smart Invest")}</h4>
        <p className="si-setup-intro">{mode === "edit" ? t("Check your preferences before saving them.") : t("Check your preferences before activating Smart Invest.")}</p>
        {retired.length > 0 ? (
          <div className="alert alert-warning alert-icon u33-retired-criteria" role="status">
            <NiIcon name="alert-circle" />
            {t("Your saved preferences also include risk rating, purpose or loan type. Smart Invest no longer uses them: saving your preferences removes them.")}
          </div>
        ) : null}
        <dl className="rs33-review">
          <div>
            <dt>{t("Currencies")}</dt>
            <dd>{currencySummary}</dd>
            <button aria-label={t("Edit currencies")} className="si-link" onClick={() => setStepIndex(0)} type="button">{t("Edit")}</button>
          </div>
          <div>
            <dt>{t("Interest & duration")}</dt>
            <dd>
              {preferences.minRate === null ? t("Interest rate: no preference") : t("Interest rate: at least {rate}%", { rate: formatDecimal(preferences.minRate, 1) })}
              <br />
              {preferences.maxTerm === null ? t("Term: no preference") : t("Term: up to {count} months", { count: preferences.maxTerm })}
            </dd>
            <button aria-label={t("Edit interest & duration")} className="si-link" onClick={() => setStepIndex(1)} type="button">{t("Edit")}</button>
          </div>
          <div>
            <dt>{t("Security")}</dt>
            <dd>{t("Security type: {types}", { types: securitySummary })}</dd>
            <button aria-label={t("Edit security")} className="si-link" onClick={() => setStepIndex(2)} type="button">{t("Edit")}</button>
          </div>
        </dl>
        <div aria-atomic="true" aria-live="polite" className="r56-match-preview" role="status">
          <NiIcon name="search" />
          <div>
            <strong>{matching.length === 1 ? t("1 current opportunity matches") : t("{count} current opportunities match", { count: matching.length })}</strong>
            <p>{t("Your preferences also apply to future opportunities.")}</p>
          </div>
        </div>
        <details className="si-setup-more" open={preferences.originators.length > 0 || undefined}>
          <summary>
            <NiIcon name="chevron-down" />
            {t("More preferences")}
            <small>{t("Originator")}</small>
          </summary>
          <div className="si-setup-grid">
            <div className="si-setup-field">
              <div className="si-select-label">
                <label htmlFor="si-originator">{t("Originator")}</label>
                <InfoTip label={t("Originator")} title={t("Originator")}>
                  {t("The company that granted the loan and offers part of it on Banxum. Banxum's own loans are direct loans.")}
                </InfoTip>
              </div>
              <select
                className="form-select"
                id="si-originator"
                onChange={(event) => update({ originators: event.target.value === "" ? [] : event.target.value === "__several__" ? preferences.originators : [event.target.value] })}
                value={originatorValue}
              >
                <option value="">{t("No preference")}</option>
                {originatorValue === "__several__" ? <option value="__several__">{t("Several originators (saved)")}</option> : null}
                {originatorOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
          </div>
        </details>
        {criterionError ? (
          <p className="si-validation" role="alert">
            {t("Set at least one preference that limits the matches: one currency only, a minimum interest rate, a maximum duration, a security type or an originator.")}
          </p>
        ) : null}
      </>
    )
  };

  return (
    <main className="si-page si-guided-page">
      <div className="nk-block-head nk-block-head-sm">
        <div className="nk-block-between g-3">
          <div className="nk-block-head-content">
            <h1 className="nk-block-title page-title">{mode === "edit" ? t("Edit Smart Invest") : t("Set up Smart Invest")}</h1>
          </div>
        </div>
      </div>
      <div className={`card card-bordered si-wizard si-setup si-guided rs33-guided${mode === "edit" ? " rs33-edit" : ""}`} data-step={stepIndex + 1}>
        <form
          className="r75c-guided-form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            next();
          }}
        >
          <div className="si-guided-label">
            <span>{t("Step {current} of {total}", { current: stepIndex + 1, total: STEPS.length })}</span>
            {stepIndex > 0 ? <button className="si-link" onClick={onCancel} type="button">{t("Cancel")}</button> : null}
          </div>
          <ol aria-label={t("Smart Invest setup")} className="si-setup-progress">
            {STEPS.map((item, index) => {
              const state = index < stepIndex ? "is-done" : index === stepIndex ? "is-current" : "";
              const content = (
                <>
                  <span aria-hidden="true">{index < stepIndex ? <NiIcon name="check" /> : index + 1}</span>
                  <b className="u33-step-name">{stepLabel(item.key, item.label)}</b>
                </>
              );
              return (
                <li aria-current={mode === "setup" && index === stepIndex ? "step" : undefined} className={state} key={item.key}>
                  {mode === "edit" ? (
                    <button aria-current={index === stepIndex ? "step" : undefined} className="rs33-edit-step" onClick={() => setStepIndex(index)} type="button">{content}</button>
                  ) : content}
                </li>
              );
            })}
          </ol>
          <div className="si-setup-body">{body[step.key]}</div>
          <div className="si-setup-foot si94-footer r75c-fixed-controls">
            <div aria-atomic="true" aria-live="polite" className="si94-match-count" role="status">
              <div className="si94f-count-title">
                <strong>{matching.length === 1 ? t("1 matching opportunity") : t("{count} matching opportunities", { count: matching.length })}</strong>
              </div>
              <span>{t("{count} open now", { count: open.length })}</span>
            </div>
            {step.key === "review" ? <p className="si-setup-final-note">{t("No money is invested or reserved when you activate Smart Invest. You confirm each investment.")}</p> : null}
            <div className="si-setup-actions">
              <button className="si-link" disabled={saving} onClick={stepIndex === 0 ? onCancel : () => setStepIndex(stepIndex - 1)} type="button">
                {stepIndex === 0 ? t("Cancel") : t("Back")}
              </button>
              <button className="btn si-setup-primary" disabled={saving} type="submit">
                {step.key === "review" ? (saving ? t("Saving...") : mode === "edit" ? t("Save preferences") : t("Activate Smart Invest")) : t("Continue")}
                <NiIcon name="arrow-right" />
              </button>
            </div>
          </div>
          {error ? <p className="si-validation u33-save-error" role="alert">{error}</p> : null}
        </form>
      </div>
    </main>
  );
}
