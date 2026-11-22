// IP of Webby-Soft SRL.
// Smart Invest setup and edit (design: the guided steps of #/auto-invest, .si-wizard.si-guided, U33-DEC-19).
// Steps: Currency, Interest & duration, Security (types and maximum loan-to-value), Repayments (18.3:
// No preference, Periodic repayments with interest only / principal and interest, Payment at maturity;
// U33-DEC-11 groups), Review (with borrower country, originator and the optional usual amount under
// "More preferences"). Editing starts from the saved preferences and saves at the end.
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";

import type { MarketplaceLoanPreview } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { formatDecimal, formatMoneyLabel, useNumberFormat } from "../../../investorPortal/format";
import { Dialog, InfoTip, NiIcon } from "../../components";
import { countryName } from "../invest/loanFacts";
import { SECURITY_GROUPS, securityLabel, securityPreferenceText } from "./parts/labels";
import { preferenceSummary, repaymentPreferenceText } from "./parts/smartSummary";
import { BANXUM_SOURCE, SMART_CURRENCIES, hasEffectiveCriterion, isOpenOpportunity, matchesPreferences, type SmartPreferences } from "./parts/smartInvestModel";

type StepKey = "currency" | "rates" | "security" | "repayment" | "review";
const STEPS: Array<{ key: StepKey; label: string }> = [
  { key: "currency", label: "Currency" },
  { key: "rates", label: "Interest & duration" },
  { key: "security", label: "Security" },
  { key: "repayment", label: "Repayments" },
  { key: "review", label: "Review & activate" }
];
const PERIODIC_OPTIONS = ["interest_only", "principal_and_interest"];

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
          <button aria-pressed={!limit} data-rc-range-mode="any" onClick={() => { setLimit(false); setText(null); onChange(null); }} type="button">{t("No preference")}</button>
          <button aria-controls={editorId} aria-expanded={limit} aria-pressed={limit} data-rc-range-mode="limit" onClick={() => setLimit(true)} type="button">{t("Set a limit")}</button>
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

/** Design .rs65-ltv: "Maximum loan-to-value" with No preference / Set a limit, presets and a value. */
function LtvField({ value, onChange }: { value: number | null; onChange: (value: number | null) => void }) {
  const t = useT();
  useNumberFormat();
  const editorId = useId();
  const [limit, setLimit] = useState(value !== null);
  const [text, setText] = useState<string | null>(null);
  const shown = text ?? (value === null ? "" : formatDecimal(value, Number.isInteger(value) ? 0 : 1));
  return (
    <section aria-labelledby="rs65-ltv-title" className="rs65-ltv" data-ltv-mode={limit ? "limit" : "any"}>
      <div className="rs65-ltv-heading">
        <h5 id="rs65-ltv-title">{t("Maximum loan-to-value")}</h5>
        <div aria-label={t("Loan-to-value preference")} className="rc-range-toggle" role="group">
          <button aria-pressed={!limit} onClick={() => { setLimit(false); setText(null); onChange(null); }} type="button">{t("No preference")}</button>
          <button aria-controls={editorId} aria-expanded={limit} aria-pressed={limit} onClick={() => setLimit(true)} type="button">{t("Set a limit")}</button>
        </div>
      </div>
      <div className="rs65-ltv-editor" hidden={!limit} id={editorId}>
        <div className="rs65-ltv-controls">
          <div className="rs65-ltv-input-row">
            <label htmlFor="rs65-ltv-value">{t("Loan amount up to")}</label>
            <span className="rs65-ltv-value">
              <input
                aria-label={t("Maximum loan-to-value percent")}
                id="rs65-ltv-value"
                inputMode="decimal"
                onBlur={() => setText(null)}
                onChange={(event) => {
                  setText(event.target.value);
                  const parsed = parseNumber(event.target.value);
                  onChange(parsed === null || parsed <= 0 ? null : Math.min(parsed, 100));
                }}
                placeholder="—"
                type="text"
                value={shown}
              />
              <span>%</span>
            </span>
          </div>
          <div aria-label={t("Loan-to-value limits")} className="rs65-ltv-presets" role="group">
            {[60, 70, 80].map((preset) => (
              <button aria-pressed={value === preset} key={preset} onClick={() => { setText(null); onChange(preset); }} type="button">{preset}%</button>
            ))}
          </div>
          <input
            aria-label={t("Maximum loan-to-value slider")}
            aria-valuetext={value === null ? t("No limit selected") : `${formatDecimal(value, 0)}%`}
            max={100}
            min={1}
            onChange={(event) => { setText(null); onChange(Number(event.target.value)); }}
            step={1}
            type="range"
            value={value ?? 70}
          />
        </div>
        <p className="rs65-ltv-note">{t("Only opportunities with a stated loan-to-value are shown.")}</p>
        {value === null ? <p className="rc-range-pending">{t("Enter a value or choose a limit to apply it.")}</p> : null}
      </div>
    </section>
  );
}

export function SmartInvestWizard({
  mode,
  initial,
  loans,
  originators,
  saving,
  error,
  onCancel,
  onSave
}: {
  mode: "setup" | "edit";
  initial: SmartPreferences;
  loans: MarketplaceLoanPreview[];
  originators: Array<{ id: string; name: string }>;
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
  const [matchesOpen, setMatchesOpen] = useState(false);
  const [amountText, setAmountText] = useState(initial.preferredAmount === null ? "" : formatDecimal(initial.preferredAmount, Number.isInteger(initial.preferredAmount) ? 0 : 2));
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
  };
  const reviewLabel = mode === "edit" ? t("Review & save") : t("Review & activate");
  const stepLabel = (key: StepKey, label: string) => (key === "review" ? reviewLabel : t(label));

  const next = () => {
    if (step.key === "currency" && preferences.currencies.length === 0) {
      setCurrencyError(true);
      return;
    }
    if (step.key === "review") {
      // 18.3: "No preference" everywhere is allowed; it matches every open opportunity.
      onSave(preferences);
      return;
    }
    setStepIndex((index) => Math.min(STEPS.length - 1, index + 1));
  };

  const repayment = preferences.repayment;
  const periodicSelected = PERIODIC_OPTIONS.some((option) => repayment.includes(option));
  const toggleRepayment = (option: string) => {
    update({ repayment: repayment.includes(option) ? repayment.filter((item) => item !== option) : [...repayment, option] });
  };
  // The "Periodic repayments" card ticks or clears both periodic options.
  const togglePeriodic = () => {
    update({ repayment: periodicSelected ? repayment.filter((item) => !PERIODIC_OPTIONS.includes(item)) : Array.from(new Set([...repayment, ...PERIODIC_OPTIONS])) });
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
  // Borrower countries of the open opportunities, plus a saved one that is not listed now.
  const countryValues = Array.from(new Set([...open.map((loan) => loan.borrower_country).filter(Boolean), ...preferences.countries]));
  const countryOptions = countryValues.map((value) => ({ value, label: countryName(value) })).sort((left, right) => left.label.localeCompare(right.label));
  const countryValue = preferences.countries.length === 0 ? "" : preferences.countries.length === 1 ? preferences.countries[0] : "__several__";
  const moreSummary = [
    preferences.countries.length > 0 ? preferences.countries.map(countryName).join(", ") : "",
    preferences.originators.length > 0 ? t("Originator") : "",
    preferences.preferredAmount !== null ? preferences.currencies.map((currency) => formatMoneyLabel(currency, Math.round((preferences.preferredAmount ?? 0) * 100))).join(" / ") : ""
  ].filter(Boolean);
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
        <p className="si-setup-intro">{t("Choose one or both currencies for your investments.")}</p>
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
        <LtvField onChange={(value) => update({ maxLtv: value })} value={preferences.maxLtv} />
      </>
    ),
    repayment: (
      <>
        <h4 id="si-step-heading" ref={headingRef} tabIndex={-1}>{t("Choose your repayment preferences")}</h4>
        <fieldset className="rs33-repayment-group" data-si-group="repayment">
          <legend className="visually-hidden">{t("Repayment preferences")}</legend>
          <label className={`rs33-any${repayment.length === 0 ? " is-selected" : ""}`}>
            <input checked={repayment.length === 0} onChange={() => update({ repayment: [] })} type="checkbox" />
            <span>{t("No preference")}</span>
          </label>
          <div className="rs33-repayment-cards">
            <section className={`rs33-repayment-card${periodicSelected ? " is-selected" : ""}`}>
              <label className="rs33-repayment-heading">
                <span>{t("Periodic repayments")}</span>
                <input aria-controls="rs33-periodic-options" aria-expanded={periodicSelected} checked={periodicSelected} onChange={togglePeriodic} type="checkbox" />
              </label>
              <p>{t("Receive payments during the investment term.")}</p>
              <div className="rs33-periodic-options" hidden={!periodicSelected} id="rs33-periodic-options">
                <label className="rs33-repayment-option">
                  <input checked={repayment.includes("interest_only")} name="repayment" onChange={() => toggleRepayment("interest_only")} type="checkbox" value="interest_only" />
                  <span><strong>{t("Interest only")}</strong><small>{t("Interest during the term. Your invested amount at the end.")}</small></span>
                </label>
                <label className="rs33-repayment-option">
                  <input checked={repayment.includes("principal_and_interest")} name="repayment" onChange={() => toggleRepayment("principal_and_interest")} type="checkbox" value="principal_and_interest" />
                  <span><strong>{t("Principal and interest")}</strong><small>{t("Part of your invested amount and interest with each payment.")}</small></span>
                </label>
              </div>
            </section>
            <section className={`rs33-repayment-card${repayment.includes("at_maturity") ? " is-selected" : ""}`}>
              <label className="rs33-repayment-heading">
                <span>{t("Payment at maturity")}</span>
                <input checked={repayment.includes("at_maturity")} name="repayment" onChange={() => toggleRepayment("at_maturity")} type="checkbox" value="at_maturity" />
              </label>
              <p>{t("Your invested amount and interest are paid at the end of the term.")}</p>
            </section>
          </div>
        </fieldset>
        <p className="si-setup-note rs33-periodic-note">{t("Periodic repayments may be monthly, quarterly, half-yearly or annual. The exact frequency is shown for each opportunity.")}</p>
      </>
    ),
    review: (
      <>
        <h4 id="si-step-heading" ref={headingRef} tabIndex={-1}>{mode === "edit" ? t("Review & save your preferences") : t("Review & activate Smart Invest")}</h4>
        <p className="si-setup-intro">{mode === "edit" ? t("Check your preferences before saving.") : t("Check your preferences before activating Smart Invest.")}</p>
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
            <dd>
              {t("Security type: {types}", { types: securitySummary })}
              <br />
              {preferences.maxLtv === null ? t("Loan-to-value: no preference") : t("Maximum loan-to-value {ratio}%", { ratio: formatDecimal(preferences.maxLtv, Number.isInteger(preferences.maxLtv) ? 0 : 1) })}
            </dd>
            <button aria-label={t("Edit security")} className="si-link" onClick={() => setStepIndex(2)} type="button">{t("Edit")}</button>
          </div>
          <div>
            <dt>{t("Repayments")}</dt>
            <dd>{repaymentPreferenceText(repayment)}</dd>
            <button aria-label={t("Edit repayments")} className="si-link" onClick={() => setStepIndex(3)} type="button">{t("Edit")}</button>
          </div>
        </dl>
        <div aria-atomic="true" aria-live="polite" className="r56-match-preview" role="status">
          <NiIcon name="search" />
          <div>
            <strong>{matching.length === 1 ? t("1 current opportunity matches") : t("{count} current opportunities match", { count: matching.length })}</strong>
            <p>{t("Your preferences also apply to future opportunities.")}</p>
          </div>
        </div>
        <details className="si-setup-more" open={moreSummary.length > 0 || undefined}>
          <summary>
            <NiIcon name="chevron-down" />
            {t("More preferences")}
            <small>{t("Country · Originator · Preferred amount")}</small>
          </summary>
          <div className="si-setup-grid">
            <div className="si-setup-field">
              <div className="si-select-label">
                <label htmlFor="si-country">{t("Borrower country")}</label>
              </div>
              <select
                className="form-select"
                id="si-country"
                onChange={(event) => update({ countries: event.target.value === "" ? [] : event.target.value === "__several__" ? preferences.countries : [event.target.value] })}
                value={countryValue}
              >
                <option value="">{t("No preference")}</option>
                {countryValue === "__several__" ? <option value="__several__">{t("Several countries (saved)")}</option> : null}
                {countryOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
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
          <div className="si-guided-amount">
            <label className="si-setup-label" htmlFor="si-amount">
              {t("Preferred investment amount")} <small>{t("Optional")}</small>
            </label>
            <input
              className="form-control si-setup-amount"
              id="si-amount"
              inputMode="decimal"
              name="amount"
              onBlur={() => setAmountText(preferences.preferredAmount === null ? "" : formatDecimal(preferences.preferredAmount, Number.isInteger(preferences.preferredAmount) ? 0 : 2))}
              onChange={(event) => {
                setAmountText(event.target.value);
                const parsed = parseNumber(event.target.value);
                update({ preferredAmount: parsed === null || parsed <= 0 ? null : Math.round(parsed * 100) / 100 });
              }}
              placeholder={t("Choose later")}
              type="text"
              value={amountText}
            />
            <p className="si-setup-note">
              {t("Leave blank to choose an amount for each investment.")}
              <br />
              {t("A saved amount applies separately in each selected currency.")}
            </p>
          </div>
        </details>
        {hasEffectiveCriterion(preferences) ? null : (
          <p className="si-setup-note">{t("With no preference set, every open opportunity matches.")}</p>
        )}
      </>
    )
  };

  return (
    <main className="si-page si-guided-page r31-range-simple">
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
                <button className="si94f-text-link" onClick={() => setMatchesOpen(true)} type="button">
                  {t("View matches")} <NiIcon name="arrow-right" />
                </button>
              </div>
              {/* Design: "{open} open · {soon} coming soon"; Coming soon projects come with U33-DEC-17. */}
              <span>{t("{count} open", { count: matching.length })}</span>
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
        {matchesOpen ? (
          <MatchesDialog
            editing={mode === "edit"}
            matching={matching}
            onClose={() => setMatchesOpen(false)}
            summary={preferenceSummary(preferences, originators)}
          />
        ) : null}
      </div>
    </main>
  );
}

/** "View matches" (design .si94f-modal): the opportunities that match the preferences being edited. */
function MatchesDialog({ matching, summary, editing, onClose }: { matching: MarketplaceLoanPreview[]; summary: string; editing: boolean; onClose: () => void }) {
  const t = useT();
  return (
    <Dialog bodyClassName="si94f-dialog" className="si94f-modal" onClose={onClose} size="lg" title={t("Matching opportunities")}>
      <header>
        <div>
          <p>
            <span>{matching.length === 1 ? t("1 opportunity") : t("{count} opportunities", { count: matching.length })}</span> · <span>{t("{count} open", { count: matching.length })}</span>
          </p>
        </div>
      </header>
      <div className="si94f-filter-summary">
        {summary.split(" · ").flatMap((part, index) => (index === 0 ? [<span key={index}>{part}</span>] : [" · ", <span key={index}>{part}</span>]))}
      </div>
      <div className="si94f-results">
        <div className="si94f-result-head">
          <span>{t("Opportunity")}</span>
          <span>{t("Annual interest")}</span>
          <span>{t("Term")}</span>
        </div>
        {matching.map((loan) => (
          <div className="si94f-result" key={loan.loan_id}>
            <div>
              <strong>{loan.title}</strong>
              <span>{loan.currency}</span>
            </div>
            <b>{formatDecimal((loan.yield_bps || loan.interest_rate_bps) / 100, 1)}%</b>
            <div className="si94f-result-term">{loan.term_months}<span>{t("months")}</span></div>
          </div>
        ))}
      </div>
      <footer>
        <span>{editing ? t("These changes are not saved.") : t("Your preferences are not activated.")}</span>
        <button className="btn si94f-button" onClick={onClose} type="button">
          {t("Back to preferences")} <NiIcon name="arrow-right" />
        </button>
      </footer>
    </Dialog>
  );
}
