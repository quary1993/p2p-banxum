// IP of Webby-Soft SRL.
// Late and default information of an investment in the U33 presentation, from recorded data only: the
// overdue rows of the investor's schedule, the loan's days past due, the stages the team recorded and
// the next step when the team knows it (U33-DEC-22), the recorded recoveries and the public loan notes
// (the old "Loan notes"). No invented stages, next steps or dates: without recorded stages the public
// notes are shown as before. The contract termination is a separate recorded stage with its real date
// (U33-DEC-09). Banxum follows up; the investor is never
// asked to act. Recoveries are credited to the Banxum balance (U33-DEC-02); each recovery shows the
// gross, the real external costs and the net, with no Banxum recovery fee (U33-DEC-12).
import { useEffect } from "react";

import type { Holding, HoldingRecoveryStage, PublicLoanRiskNote } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { useLoanRiskNotesData } from "../../../../investorPortal/data";
import { formatDate, formatMoneyMinor, formatRateBps, useNumberFormat } from "../../../../investorPortal/format";
import { NiIcon } from "../../../components";
import { overdueRows } from "./investmentModel";

// Q16: "Recovery closed" states the result (full, partial or no recovery).
const RECOVERY_RESULT_TEXT: Record<string, string> = { full: "Full recovery", partial: "Partial recovery", none: "No recovery" };

function stageTitle(stage: { title: string; recovery_result?: string }, t: (text: string) => string) {
  const result = stage.recovery_result ? RECOVERY_RESULT_TEXT[stage.recovery_result] : "";
  return result ? `${stage.title} · ${t(result)}` : stage.title;
}

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

/** U33-DEC-22: the design's steps from recorded facts: the first missed payment, the recorded stages
 * and the next step only when it is known (with its date when known). */
function RecordedSteps({ holding, missedOn }: { holding: Holding; missedOn: string | null }) {
  const t = useT();
  const stages = holding.recovery_stages ?? [];
  const next = holding.recovery_next_step ?? null;
  return (
    <ol className="rc-steps">
      {missedOn ? (
        <li>
          <span aria-hidden="true" className="rc-step-dot done" />
          <div>
            <strong>{t("Payment missed")}</strong>
            <time dateTime={missedOn}>{formatDate(missedOn)}</time>
          </div>
          <p>{t("Your scheduled payment has not been received.")}</p>
        </li>
      ) : null}
      {stages.map((stage, index) => (
        <li key={`${stage.title}-${stage.occurred_on ?? ""}-${index}`}>
          <span aria-hidden="true" className="rc-step-dot done" />
          <div>
            <strong>{stageTitle(stage, t)}</strong>
            {stage.occurred_on ? <time dateTime={stage.occurred_on}>{formatDate(stage.occurred_on)}</time> : null}
          </div>
          {stage.investor_note ? <p>{stage.investor_note}</p> : null}
        </li>
      ))}
      {next ? (
        <li>
          <span aria-hidden="true" className="rc-step-dot next" />
          <div>
            <strong>{t("Next step · {title}", { title: next.title })}</strong>
            {next.occurred_on ? <time dateTime={next.occurred_on}>{formatDate(next.occurred_on)}</time> : null}
          </div>
          {next.investor_note ? <p>{next.investor_note}</p> : null}
        </li>
      ) : null}
    </ol>
  );
}

function hasRecordedStages(holding: Holding) {
  return (holding.recovery_stages ?? []).length > 0 || Boolean(holding.recovery_next_step);
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
  const recorded = hasRecordedStages(holding);
  // With recorded stages every public note goes to the further steps.
  const furtherNotes = recorded ? notes : notes.slice(2);
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
        {recorded ? (
          <RecordedSteps holding={holding} missedOn={overdue[0]?.due_date ?? null} />
        ) : notes.length > 0 ? (
          <NoteSteps notes={notes.slice(0, 2)} />
        ) : (
          <NotesState empty={t("No update has been published for this loan yet.")} query={query} />
        )}
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
            {furtherNotes.length > 0 ? <NoteSteps notes={furtherNotes} /> : null}
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
  const recoveries = holding.recovery_events ?? [];
  const writtenOff = holding.loan.loan_status === "written_off";
  // U33-DEC-22: the latest recorded stage is the current stage; the next step shows only when known.
  const stages = holding.recovery_stages ?? [];
  const currentStage: HoldingRecoveryStage | null = stages.length > 0 ? stages[stages.length - 1] : null;
  const nextStep = holding.recovery_next_step ?? null;
  const historyNotes = nextStep ? notes : notes.slice(1);
  return (
    <div className="card card-bordered rid-followup r31m-default r75c-recovery" id="loan-notes">
      <div className="r75c-recovery-content">
        <div className="r75c-recovery-head">
          <h2>{writtenOff ? t("Loan written off") : t("Recovery in progress")}</h2>
          <p>{t("Banxum manages recovery. No action is needed from you.")}</p>
        </div>
        <div className="r75c-recovery-grid">
          {currentStage ? (
            <section>
              <span>{t("Current stage")}</span>
              <h3>{currentStage.title}</h3>
              <p>
                {currentStage.investor_note}{" "}
                {currentStage.occurred_on ? <time dateTime={currentStage.occurred_on}>({formatDate(currentStage.occurred_on)})</time> : null}
              </p>
            </section>
          ) : (
          <section>
            <span>{t("Current stage")}</span>
            <h3>{writtenOff ? t("Written off") : t("Default")}</h3>
            <p>
              {holding.loan.contract_terminated_on ? `${t("The loan contract was terminated on {date}.", { date: formatDate(holding.loan.contract_terminated_on) })} ` : null}
              {holding.loan.days_past_due > 0 ? t("{days} days since the first unpaid payment.", { days: holding.loan.days_past_due }) : null}{" "}
              {/* Design text adapted: recoveries go to the Banxum account, not to the IBAN (U33-DEC-02/12). */}
              {t("Recovered amounts, after real external costs such as lawyers, courts and enforcement, are credited to each investor's Banxum account in proportion to their share. Banxum takes no recovery fee.")}
            </p>
          </section>
          )}
          {nextStep ? (
            <section>
              <span>{t("Next milestone")}</span>
              <h3>{nextStep.title}</h3>
              <p>
                {nextStep.investor_note}{" "}
                {nextStep.occurred_on ? <time dateTime={nextStep.occurred_on}>({formatDate(nextStep.occurred_on)})</time> : null}
              </p>
            </section>
          ) : (
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
          )}
        </div>
        <details className="r31m-disclosure r31m-recovery-history">
          <summary>
            {t("Recovery history")}
            <NiIcon name="chevron-down" />
          </summary>
          <div>
            {stages.length > 0 || holding.loan.contract_terminated_on ? (
              <>
                <h3>{t("Stages")}</h3>
                <ol className="bxm-timeline">
                  {holding.loan.contract_terminated_on ? (
                    <li className="is-done">
                      <h6>{t("Contract terminated")}</h6>
                      <p>{formatDate(holding.loan.contract_terminated_on)}</p>
                    </li>
                  ) : null}
                  {[...stages].reverse().map((stage, index) => (
                    <li className="is-done" key={`${stage.title}-${index}`}>
                      <h6>{stageTitle(stage, t)}</h6>
                      <p>{stage.occurred_on ? formatDate(stage.occurred_on) : ""}{stage.investor_note ? ` · ${stage.investor_note}` : ""}</p>
                    </li>
                  ))}
                </ol>
              </>
            ) : null}
            {currentStage ? (
              <p className="u33-muted">{t("Recovered amounts, after real external costs such as lawyers, courts and enforcement, are credited to each investor's Banxum account in proportion to their share. Banxum takes no recovery fee.")}</p>
            ) : null}
            {historyNotes.length > 0 ? (
              <ol className="bxm-timeline">
                {historyNotes.map((note) => (
                  <li className="is-done" id={`loan-note-${note.id}`} key={note.id}>
                    <h6>{note.title || t("Loan update")}</h6>
                    <p>{formatDate(note.occurred_at)}{note.body ? ` · ${note.body}` : ""}</p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="u33-muted">{t("Earlier updates appear here.")}</p>
            )}
            {recoveries.length > 0 ? (
              <>
                <h3>{t("Recoveries")}</h3>
                <ol className="u33-recoveries">
                  {recoveries.map((recovery) => (
                    <li key={recovery.recovery_event_id}>
                      <time dateTime={recovery.value_date}>{formatDate(recovery.value_date)}</time>
                      <dl className="u33-recovered">
                        <div><dt>{t("Recovered for the whole loan")}</dt><dd>{money(recovery.gross_recovered_minor)}</dd></div>
                        <div><dt>{t("External costs deducted")}</dt><dd>{`− ${money(recovery.external_costs_minor)}`}</dd></div>
                        {recovery.recovery_fee_minor > 0 ? (
                          <div><dt>{t("Recovery fee (charged before 10 Nov 2026)")}</dt><dd>{`− ${money(recovery.recovery_fee_minor)}`}</dd></div>
                        ) : null}
                        <div><dt>{t("Net distributed to investors")}</dt><dd>{money(recovery.net_distributed_minor)}</dd></div>
                        <div className="u33-recovered-total"><dt>{t("Credited to your balance")}</dt><dd>{money(recovery.credited_to_you_minor)}</dd></div>
                      </dl>
                    </li>
                  ))}
                </ol>
              </>
            ) : null}
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
