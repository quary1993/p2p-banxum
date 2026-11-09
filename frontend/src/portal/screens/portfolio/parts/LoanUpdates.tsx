// IP of Webby-Soft SRL.
// Late and default information of an investment in the U33 presentation, from today's data only: the
// overdue rows of the investor's schedule, the loan's days past due, the recorded recoveries and the
// public loan notes published by the team (the old "Loan notes"). No invented stages, next steps or
// dates (U33-DEC-22: structured recovery stages come with Phase 17.4). The contract termination is a
// separate recorded stage with its real date (U33-DEC-09). Banxum follows up; the investor is never
// asked to act. Recoveries are credited to the Banxum balance (U33-DEC-02).
import { useEffect } from "react";

import type { Holding, PublicLoanRiskNote } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { useLoanRiskNotesData } from "../../../../investorPortal/data";
import { formatDate, formatMoneyMinor, formatRateBps, useNumberFormat } from "../../../../investorPortal/format";
import { NiIcon } from "../../../components";
import { overdueRows } from "./investmentModel";

/** Public notes of a loan, newest first. */
function usePublicNotes(loanId: string) {
  const query = useLoanRiskNotesData(loanId);
  const notes = [...(query.data ?? [])]
    .filter((note) => note.visibility === "public")
    .sort((left, right) => right.occurred_at.localeCompare(left.occurred_at) || right.id.localeCompare(left.id));
  return { query, notes };
}

/** Scrolls to the updates when the page was opened from a notification (/portfolio/:id#loan-notes). */
function useFocusUpdates(focus: boolean, ready: boolean) {
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (!ready || (!focus && hash !== "loan-notes" && !hash.startsWith("loan-note-"))) return;
    const timer = window.setTimeout(() => {
      const target = document.getElementById(hash.startsWith("loan-note-") ? hash : "loan-notes");
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [focus, ready]);
}

function NoteSteps({ notes }: { notes: PublicLoanRiskNote[] }) {
  const t = useT();
  return (
    <ol className="rc-steps">
      {notes.map((note) => (
        <li id={`loan-note-${note.id}`} key={note.id}>
          <span aria-hidden="true" className="rc-step-dot done" />
          <div>
            <strong>{note.title || t("Loan update")}</strong>
            <time dateTime={note.occurred_at}>{formatDate(note.occurred_at)}</time>
          </div>
          {note.body ? <p>{note.body}</p> : null}
        </li>
      ))}
    </ol>
  );
}

function NotesState({ query, empty }: { query: ReturnType<typeof usePublicNotes>["query"]; empty: string }) {
  const t = useT();
  if (query.isError) {
    return (
      <p className="u33-muted">
        {t("The loan updates could not be loaded.")} <button className="link" onClick={() => void query.refetch()} type="button">{t("Retry")}</button>
      </p>
    );
  }
  if (query.isLoading) return <p aria-live="polite" className="u33-muted">{t("Loading updates...")}</p>;
  return <p className="u33-muted">{empty}</p>;
}

function DefaultInterestNote({ holding }: { holding: Holding }) {
  const t = useT();
  const rate = holding.loan.default_penalty_interest_bps;
  return (
    <p className="u33-muted">
      {rate > 0
        ? t("The loan terms set default interest of {rate} a year. Amounts are shown only once received; Banxum does not estimate default interest from the days overdue.", { rate: formatRateBps(rate) })
        : t("This loan has no default interest. Late payments do not earn extra interest.")}
    </p>
  );
}

/** Late payment: the overdue amount, the public updates and the missed payments (design .rc-payment-update). */
export function LatePaymentUpdate({ holding, focus }: { holding: Holding; focus: boolean }) {
  const t = useT();
  useNumberFormat();
  const { query, notes } = usePublicNotes(holding.loan.loan_id);
  useFocusUpdates(focus, !query.isLoading);
  const overdue = overdueRows(holding);
  const overdueMinor = overdue.reduce((sum, row) => sum + row.projected_total_minor, 0);
  const onlyInterest = overdue.every((row) => row.projected_principal_minor === 0);
  return (
    <div className="card card-bordered rc-payment-update rid-followup r31m-late" id="loan-notes">
      <header className="rc-payment-head">
        <h2>{t("Payment update")}</h2>
        <p className="r31m-followup-note">{t("Banxum, as collection agent, is following up for all investors.")}</p>
      </header>
      <div className="rc-payment-body">
        <div className="rc-payment-amount">
          {overdue.length > 0 ? (
            <div>
              <small>{onlyInterest ? t("Overdue interest") : t("Overdue payment")}</small>
              <strong><span>{holding.currency}</span> {formatMoneyMinor(overdueMinor, holding.currency)}</strong>
            </div>
          ) : null}
          <div className="rc-due">
            <small>{overdue.length > 0 ? t("Payment due") : t("Days overdue")}</small>
            <b>{overdue.length > 0 ? formatDate(overdue[0].due_date) : holding.loan.days_past_due}</b>
          </div>
        </div>
        {notes.length > 0 ? <NoteSteps notes={notes.slice(0, 2)} /> : <NotesState empty={t("No update has been published for this loan yet.")} query={query} />}
      </div>
      <details className="rc-further">
        <summary>
          {t("Payment schedule & further steps")}
          <NiIcon name="chevron-down" />
        </summary>
        <div>
          <section className="r31m-payment-history">
            <h3>{t("Payment history")}</h3>
            {overdue.length > 0 ? (
              <ol className="rc-steps">
                {overdue.map((row) => (
                  <li key={row.loan_installment_id}>
                    <span aria-hidden="true" className="rc-step-dot done" />
                    <div>
                      <strong>{t("Payment missed")}</strong>
                      <time dateTime={row.due_date}>{formatDate(row.due_date)}</time>
                    </div>
                    <p>{t("Your scheduled payment of {amount} has not been received.", { amount: `${holding.currency} ${formatMoneyMinor(row.projected_total_minor, holding.currency)}` })}</p>
                  </li>
                ))}
                {holding.loan.contract_terminated_on ? (
                  <li>
                    <span aria-hidden="true" className="rc-step-dot done" />
                    <div>
                      <strong>{t("Contract terminated")}</strong>
                      <time dateTime={holding.loan.contract_terminated_on}>{formatDate(holding.loan.contract_terminated_on)}</time>
                    </div>
                    <p>{t("The loan contract was terminated.")}</p>
                  </li>
                ) : null}
              </ol>
            ) : (
              <p className="u33-muted">{t("The borrower is {days} days late. The overdue amounts are shown once the schedule is updated.", { days: holding.loan.days_past_due })}</p>
            )}
            {notes.length > 2 ? <NoteSteps notes={notes.slice(2)} /> : null}
          </section>
          <h3>{t("Default interest")}</h3>
          <DefaultInterestNote holding={holding} />
        </div>
      </details>
    </div>
  );
}

/** Loan in default: recovery information (design .r75c-recovery), without invented stages. */
export function RecoveryUpdate({ holding, focus }: { holding: Holding; focus: boolean }) {
  const t = useT();
  useNumberFormat();
  const { query, notes } = usePublicNotes(holding.loan.loan_id);
  useFocusUpdates(focus, !query.isLoading);
  const latest = notes[0];
  const money = (amount: number) => `${holding.currency} ${formatMoneyMinor(amount, holding.currency)}`;
  const recovered = [
    { label: t("Principal recovered"), amount: holding.recovered_principal_minor },
    { label: t("Interest recovered"), amount: holding.recovered_contractual_interest_minor },
    { label: t("Default interest recovered"), amount: holding.recovered_default_interest_minor },
    { label: t("Penalties recovered"), amount: holding.recovered_penalties_minor },
    { label: t("Other recoveries"), amount: holding.recovered_other_costs_minor }
  ];
  const recoveredTotal = recovered.reduce((sum, item) => sum + item.amount, 0);
  const writtenOff = holding.loan.loan_status === "written_off";
  return (
    <div className="card card-bordered rid-followup r31m-default r75c-recovery" id="loan-notes">
      <div className="r75c-recovery-content">
        <div className="r75c-recovery-head">
          <h2>{writtenOff ? t("Loan written off") : t("Recovery in progress")}</h2>
          <p>{t("Banxum manages recovery. No action is needed from you.")}</p>
        </div>
        <div className="r75c-recovery-grid">
          <section>
            <span>{t("Current stage")}</span>
            <h3>{writtenOff ? t("Written off") : t("Default")}</h3>
            <p>
              {holding.loan.contract_terminated_on ? `${t("The loan contract was terminated on {date}.", { date: formatDate(holding.loan.contract_terminated_on) })} ` : null}
              {holding.loan.days_past_due > 0 ? t("{days} days since the first unpaid payment.", { days: holding.loan.days_past_due }) : null}{" "}
              {/* Design text adapted: recoveries go to the Banxum account, not to the IBAN (U33-DEC-02/12). */}
              {t("Recovered amounts, after the costs of enforcement, are credited to each investor's Banxum account in proportion to their share.")}
            </p>
          </section>
          <section>
            <span>{t("Latest update")}</span>
            {latest ? (
              <>
                <h3>{latest.title || t("Loan update")}</h3>
                <p>{latest.body} <time dateTime={latest.occurred_at}>({formatDate(latest.occurred_at)})</time></p>
              </>
            ) : (
              <NotesState empty={t("No update has been published for this loan yet. You are informed when there is one.")} query={query} />
            )}
          </section>
        </div>
        <details className="r31m-disclosure r31m-recovery-history">
          <summary>
            {t("Recovery history")}
            <NiIcon name="chevron-down" />
          </summary>
          <div>
            {notes.length > 1 ? (
              <ol className="bxm-timeline">
                {notes.slice(1).map((note) => (
                  <li className="is-done" id={`loan-note-${note.id}`} key={note.id}>
                    <h6>{note.title || t("Loan update")}</h6>
                    <p>{formatDate(note.occurred_at)}{note.body ? ` · ${note.body}` : ""}</p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="u33-muted">{t("Earlier updates appear here.")}</p>
            )}
            <h3>{t("Recovered to date")}</h3>
            {recoveredTotal > 0 ? (
              <dl className="u33-recovered">
                {recovered.filter((item) => item.amount > 0).map((item) => (
                  <div key={item.label}><dt>{item.label}</dt><dd>{money(item.amount)}</dd></div>
                ))}
                <div className="u33-recovered-total"><dt>{t("Total credited to your balance")}</dt><dd>{money(recoveredTotal)}</dd></div>
              </dl>
            ) : (
              <p className="u33-muted">{t("Nothing has been recovered yet.")}</p>
            )}
            <h3>{t("Default interest")}</h3>
            <DefaultInterestNote holding={holding} />
          </div>
        </details>
      </div>
    </div>
  );
}

/** Public updates of a performing loan, when the team published any (the old "Loan notes"). */
export function LoanNotes({ loanId, focus }: { loanId: string; focus: boolean }) {
  const t = useT();
  const { query, notes } = usePublicNotes(loanId);
  useFocusUpdates(focus, !query.isLoading);
  if (notes.length === 0 && !query.isError) return null;
  return (
    <details className="r71-documents u33-loan-notes" id="loan-notes" open={focus || undefined}>
      <summary>
        {t("Loan updates")} <span className="u33-count">{notes.length}</span>
        <NiIcon name="chevron-down" />
      </summary>
      <div className="r71-document-body">
        {notes.length > 0 ? <NoteSteps notes={notes} /> : <NotesState empty="" query={query} />}
      </div>
    </details>
  );
}
