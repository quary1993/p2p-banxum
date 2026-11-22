// IP of Webby-Soft SRL.
// Building blocks of Review & sign (design #/projects/:id/invest?step=review): the step bar, the page
// frame, the editable amount, the two acceptances (U33-DEC-14), the confirmation dialog with today's
// email code + PIN (ACC-DEC-009; U33-DEC-01 keeps only the PIN from Phase 17.3) and the result.
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import type { MarketplaceLoanDetail } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { HelpWithThisStep } from "../../account/parts/HelpWithThisStep";
import { isFixturePreview, useBalancesData } from "../../../../investorPortal/data";
import { formatDate, formatDateTime, formatMoneyLabel, formatMoneyMinor, useNumberFormat } from "../../../../investorPortal/format";
import { SensitiveFactorField } from "../../account/parts/OperationFactor";
import { Dialog, NiIcon, PortalLink } from "../../../components";
import { legalDocumentPath } from "../investRules";
import { borrowerName, projectIcon, repaymentText } from "../loanFacts";
import type { SensitiveActionKit, SensitiveCodeRequest } from "./sensitiveAction";

export function InvestSteps({ current, lastLabel }: { current: 2 | 3; lastLabel: string }) {
  const t = useT();
  const step = (index: number, label: string) => {
    const done = index < current || (current === 3 && index === 3);
    const active = index === current;
    return (
      <span aria-current={active ? "step" : undefined} className={`ip-step${active ? " is-active" : ""}${done && !active ? " rp-complete" : ""}`}>
        <b>{done ? <NiIcon name="check" /> : index}</b>
        {label}
      </span>
    );
  };
  return (
    <nav aria-label={t("Investment progress")} className="ip-steps">
      {step(1, t("Amount"))}
      <span className="ip-step-line" />
      {step(2, t("Review & sign"))}
      <span className="ip-step-line" />
      {step(3, lastLabel)}
    </nav>
  );
}

/** Page frame: back link, heading with steps, project header, the two columns, help and risk line. */
export function ReviewFrame({
  loan,
  lastStepLabel,
  onSubmit,
  summary,
  agreement,
  amountMinor = null
}: {
  loan: MarketplaceLoanDetail;
  lastStepLabel: string;
  onSubmit: (event: FormEvent) => void;
  summary: ReactNode;
  agreement: ReactNode;
  /** 18.3: the amount under review, for "Help with this step". */
  amountMinor?: number | null;
}) {
  const t = useT();
  const company = borrowerName(loan);
  return (
    <main className="bxm-invest-desktop ip-page rp-page rl29-review">
      <PortalLink className="ip-back" params={{ loanId: loan.loan_id }} to="loan"><NiIcon name="arrow-left" />{t("Back to opportunity")}</PortalLink>
      <div className="ip-heading">
        <h1>{t("Review & sign")}</h1>
        <InvestSteps current={2} lastLabel={lastStepLabel} />
      </div>
      <section aria-label={t("Review your investment")} className="ip-panel">
        <header className="ip-project">
          <span className="ip-project-icon"><NiIcon name={projectIcon(loan)} /></span>
          <div className="rp-project-name">
            <h2>{loan.title}</h2>
            {company && company !== loan.title ? <p>{company}</p> : loan.originator_name ? <p>{loan.originator_name}</p> : null}
          </div>
          <div className="rp-project-links">
            <PortalLink className="rp-view-details" params={{ loanId: loan.loan_id }} to="loan">{t("View details")} <NiIcon name="arrow-up-right" /></PortalLink>
            <PortalLink params={{ loanId: loan.loan_id, section: "credit-file" }} to="loan">{t("Credit file")} <NiIcon name="arrow-up-right" /></PortalLink>
          </div>
        </header>
        <form className="ip-grid rp-grid" noValidate onSubmit={onSubmit}>
          <aside className="ip-summary rp-summary">{summary}</aside>
          <section className="rp-agreement-side">{agreement}</section>
        </form>
        <div className="rl29-help">
          {/* 18.3: help for this step with its live values (design r34-invest-help, "Reviewing and signing"). */}
          <HelpWithThisStep
            context={loan.title}
            items={[
              {
                question: t("What am I confirming?"),
                answer: t("The purchase agreement for {amount} in {project}. Review the agreement and each acknowledgement before you confirm.", {
                  amount: amountMinor ? formatMoneyLabel(loan.currency, amountMinor) : t("your chosen amount"),
                  project: loan.title
                })
              },
              { question: t("When are funds reserved?"), answer: t("Only after you accept the acknowledgements and confirm with your codes.") },
              { question: t("Can I still change the amount?"), answer: t("Yes. Select Change beside your investment amount before you confirm.") }
            ]}
            title={t("Reviewing and signing")}
          />
        </div>
      </section>
      <p className="ip-bottom"><NiIcon name="info" />{t("Repayments are not guaranteed. You may lose part or all of your investment.")}</p>
    </main>
  );
}

/**
 * The amount on Review & sign: editable in place. Enter or leaving the field checks and applies the
 * new amount; Escape restores the applied one. `onApply` returns an error message, or null when the
 * amount was applied.
 */
export function ReviewAmount({
  currency,
  appliedMinor,
  onApply,
  onCancel,
  error,
  status,
  action
}: {
  currency: string;
  appliedMinor: number | null;
  onApply: (text: string) => void;
  /** Escape: the applied amount stays; its error, if any, is cleared. */
  onCancel: () => void;
  error: string;
  status: string;
  action?: ReactNode;
}) {
  const t = useT();
  useNumberFormat();
  const applied = appliedMinor === null ? "" : formatMoneyMinor(appliedMinor, currency);
  const [draft, setDraft] = useState(applied);
  const inputRef = useRef<HTMLInputElement>(null);
  const skipBlur = useRef(false);
  useEffect(() => {
    setDraft(applied);
  }, [applied]);
  useEffect(() => {
    if (appliedMinor === null) inputRef.current?.focus();
    // Only on the first render: an empty amount asks for one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const apply = () => {
    if (draft.trim() === applied.trim() && !error) return;
    onApply(draft);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      apply();
    } else if (event.key === "Escape") {
      event.preventDefault();
      skipBlur.current = true;
      setDraft(applied);
      onCancel();
      inputRef.current?.blur();
    }
  };
  return (
    <>
      <div className="rp-amount-head">
        <label htmlFor="review-amount-input" id="review-amount-label">{t("Your investment amount")}</label>
      </div>
      <div className={`rp-amount ra28-value${error ? " has-error" : ""}`}>
        <span>{currency}</span>
        <input
          aria-describedby="ra28-error"
          aria-invalid={error ? true : undefined}
          aria-labelledby="review-amount-label"
          autoComplete="off"
          id="review-amount-input"
          inputMode="decimal"
          onBlur={() => {
            if (skipBlur.current) {
              skipBlur.current = false;
              return;
            }
            apply();
          }}
          onChange={(event) => setDraft(event.target.value.replace(/[^0-9.,'’\s]/g, ""))}
          onKeyDown={onKeyDown}
          placeholder={t("Enter an amount")}
          ref={inputRef}
          type="text"
          value={draft}
        />
        <label htmlFor="review-amount-input">
          <NiIcon name="edit" />
          <span className="ra28-sr">{t("Edit investment amount")}</span>
        </label>
      </div>
      <p aria-live="polite" className="ra28-error" id="ra28-error">{error}</p>
      {action ? <div className="u33-invest-amount-action">{action}</div> : null}
      <span className="ra28-sr ra28-status" role="status">{status}</span>
    </>
  );
}

/** The two acceptances of U33-DEC-14, unchecked by default; the documents open before confirmation. */
export function Acceptances({
  terms,
  risks,
  onTerms,
  onRisks,
  disabled,
  templateNote,
  termsLabel
}: {
  terms: boolean;
  risks: boolean;
  onTerms: (value: boolean) => void;
  onRisks: (value: boolean) => void;
  disabled?: boolean;
  templateNote?: string;
  termsLabel: string;
}) {
  const t = useT();
  return (
    <div className="rp-consents">
      <h3>{t("Before you sign")}</h3>
      <div className="custom-control custom-checkbox mb-2">
        <input checked={terms} className="custom-control-input" disabled={disabled} id="ack-terms" onChange={(event) => onTerms(event.target.checked)} type="checkbox" />
        <label className="custom-control-label" htmlFor="ack-terms">{termsLabel}</label>
      </div>
      <div className="rd98-links">
        <a href={legalDocumentPath("primary_market_investment")} rel="noopener noreferrer" target="_blank">
          <span>{t("Investment terms")}</span><NiIcon name="arrow-up-right" />
        </a>
      </div>
      <div className="custom-control custom-checkbox mb-2">
        <input checked={risks} className="custom-control-input" disabled={disabled} id="ack-risks" onChange={(event) => onRisks(event.target.checked)} type="checkbox" />
        <label className="custom-control-label" htmlFor="ack-risks">
          {t("I have read the risk information and understand that I can lose part or all of this amount.")}
        </label>
      </div>
      <div className="rd98-links">
        <a href={legalDocumentPath("risk_disclosure")} rel="noopener noreferrer" target="_blank">
          <span>{t("Risk information")}</span><NiIcon name="arrow-up-right" />
        </a>
      </div>
      <p className="u33-invest-record">
        {templateNote ?? t("Documents open in a new tab. Your acceptance is recorded with the document version, the time, the amount and the loan.")}
      </p>
    </div>
  );
}

/** "No investment fees" and the green confirm button (design: .rl29-sign-actions). */
export function SignActions({ label, disabled, extra }: { label: string; disabled: boolean; extra?: ReactNode }) {
  const t = useT();
  return (
    <div className="rl29-sign-actions">
      {extra}
      <div className="rl29-no-fees"><NiIcon name="check" /><span>{t("No investment fees")}</span></div>
      <button className="ip-continue" disabled={disabled} type="submit"><NiIcon name="lock-alt" />{label}</button>
    </div>
  );
}

/** Confirmation dialog (design: .p73-modal) with today's email code and PIN. */
export function ConfirmDialog({
  loan,
  amountMinor,
  amountLabel,
  title,
  intro,
  note,
  confirmLabel,
  busyLabel,
  kit,
  codeRequest,
  code,
  onCode,
  busy,
  error,
  onConfirm,
  onClose
}: {
  loan: MarketplaceLoanDetail;
  amountMinor: number;
  amountLabel: string;
  title: string;
  intro: string;
  note: string;
  confirmLabel: string;
  busyLabel: string;
  kit: SensitiveActionKit;
  codeRequest: SensitiveCodeRequest;
  code: string;
  onCode: (value: string) => void;
  busy: boolean;
  error: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const t = useT();
  const company = borrowerName(loan);
  const ready = code.length === 6 && codeRequest.pin.ready && (isFixturePreview || Boolean(codeRequest.codeId)) && !busy;
  const message = codeRequest.error || error;
  return (
    <Dialog busy={busy} className="p73-modal" onClose={onClose} size="sm" title={title}>
      <p className="p73-intro">{intro}</p>
      <div className="p73-confirm-summary">
        <div className="p73-confirm-project">
          <span className="p73-project-icon"><NiIcon name={projectIcon(loan)} /></span>
          <div>
            <strong>{loan.title}</strong>
            {company && company !== loan.title ? <small>{company}</small> : null}
          </div>
        </div>
        <div className="p73-list-price">
          <span>{amountLabel}</span>
          <strong className="p73-full-amount">{formatMoneyLabel(loan.currency, amountMinor)}</strong>
        </div>
      </div>
      <form
        className="bxm-code-form"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onConfirm();
        }}
      >
        <div className="u33-invest-code-head">
          <label className="p73-code-label" htmlFor="p73-email-code">{t("Email confirmation code")}</label>
          <button className="link u33-invest-code-request" disabled={kit.requestDisabled(codeRequest)} onClick={codeRequest.requestCode} type="button">
            {kit.requestLabel(codeRequest)}
          </button>
        </div>
        <input
          aria-describedby="p73-code-help"
          autoComplete="one-time-code"
          className="form-control form-control-lg bxm-otp p73-code"
          id="p73-email-code"
          inputMode="numeric"
          maxLength={6}
          onChange={(event) => onCode(event.target.value.replace(/\D/g, ""))}
          placeholder="000000"
          value={code}
        />
        <p className="u33-invest-code-help" id="p73-code-help">
          {isFixturePreview
            ? t("Demo: any 6 digits")
            : codeRequest.expiresAt
              ? t("We sent a 6-digit code to your email. It expires {time}.", { time: formatDateTime(codeRequest.expiresAt) })
              : t("We send a 6-digit code to your email.")}
        </p>
        <div className="u33-invest-pin">
          <SensitiveFactorField onContinue={onConfirm} pin={codeRequest.pin} />
        </div>
        {message ? <div className="alert alert-danger u33-invest-confirm-error" role="alert">{message}</div> : null}
        <p className="p73-confirm-note">{note}</p>
        <div className="p73-modal-actions">
          <button className="btn p73-back" disabled={busy} onClick={onClose} type="button">{t("Cancel")}</button>
          <button className="btn p73-confirm" disabled={!ready} type="submit">{busy ? busyLabel : confirmLabel}</button>
        </div>
      </form>
    </Dialog>
  );
}

/** Result page (design: main.l8-reserved): reserved, partly reserved, invested, purchased or refused. */
export function ResultPage({
  loan,
  title,
  text,
  refused,
  amountLabel,
  amountMinor,
  reference,
  lastStepLabel,
  showNext
}: {
  loan: MarketplaceLoanDetail;
  title: string;
  text: string;
  refused: boolean;
  amountLabel: string;
  amountMinor: number;
  reference?: string;
  lastStepLabel: string;
  showNext: boolean;
}) {
  const t = useT();
  useNumberFormat();
  const balances = useBalancesData().data;
  const company = borrowerName(loan);
  const available = balances?.summaries.find((summary) => summary.currency === loan.currency)?.total_available_minor;
  return (
    <main className="bxm-invest-desktop ip-page l8-reserved r50-reservation">
      <div className="ip-heading l8-done-heading">
        <div className="l8-confirm-title">
          {refused ? null : <span className="l8-check"><NiIcon name="check" /></span>}
          <h1>{title}</h1>
        </div>
        <InvestSteps current={3} lastLabel={lastStepLabel} />
      </div>
      <section className="ip-panel">
        <header className="ip-project">
          <span className="ip-project-icon"><NiIcon name={projectIcon(loan)} /></span>
          <div>
            <h2>{loan.title}</h2>
            {company && company !== loan.title ? <p>{company}</p> : null}
          </div>
          {reference ? <span className="l8-reference">{reference}</span> : null}
        </header>
        <div className="l8-reserved-hero">
          <div>
            <span className="l8-label">{amountLabel}</span>
            <div className="l8-reserved-amount"><span>{loan.currency}</span> <strong>{formatMoneyMinor(amountMinor, loan.currency)}</strong></div>
            <p>{text}</p>
          </div>
          {typeof available === "number" ? (
            <div className="l8-available">
              <span className="l8-label">{t("Available balance")}</span>
              <strong>{formatMoneyLabel(loan.currency, available)}</strong>
              <PortalLink to="balances">{t("View account")} <NiIcon name="arrow-right" /></PortalLink>
            </div>
          ) : null}
        </div>
        {showNext ? (
          <section className="l8-next">
            <h2>{t("What happens next")}</h2>
            <div className="l8-next-grid">
              {loan.funding_deadline ? (
                <div>
                  <span className="l8-next-label">{t("Funding closes")}</span>
                  <h3>{formatDate(loan.funding_deadline)}</h3>
                  <p>{t("Your reservation becomes an investment when funding closes.")}</p>
                </div>
              ) : null}
              <div>
                <span className="l8-next-label">{t("Repayments")}</span>
                <h3>{repaymentText(loan.repayment_type) || t("As the loan schedule says")}</h3>
                <p>{t("Payments follow your loan schedule and are credited to your Banxum balance.")}</p>
              </div>
            </div>
            <p className="l8-release">{t("If the funding round does not reach its minimum or is cancelled, your reserved funds become available again.")}</p>
          </section>
        ) : null}
        <footer className="l8-done-actions">
          <PortalLink className="btn btn-primary" to="portfolio">{t("My investments")} <NiIcon name="arrow-right" /></PortalLink>
          {refused ? null : <PortalLink className="l8-document-link" to="documents"><NiIcon name="file-text" />{t("Your accepted terms in Documents")}</PortalLink>}
          <PortalLink className="l8-op-link" to="market">{t("View opportunities")} <NiIcon name="arrow-right" /></PortalLink>
        </footer>
      </section>
    </main>
  );
}
