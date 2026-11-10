// IP of Webby-Soft SRL.
// U33-DEC-20: the credit file's "Checks & updates" chapter (design 06: "File review · Recorded by
// Banxum" rows with the date, what was checked and the result; the reporting and the project updates).
// Only what the team recorded: each check with its source and date, how the loan is followed, the
// recovery stages (U33-DEC-22) and the public loan notes, newest first. No rating or opinion.
import type { MarketplaceLoanDetail } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { useLoanRiskNotesData } from "../../../../investorPortal/data";
import { formatDate } from "../../../../investorPortal/format";

function dayParts(value: string) {
  const [day, ...rest] = formatDate(value).split(" ");
  return { day, rest: rest.join(" ") };
}

export function ChecksAndUpdates({ loan }: { loan: MarketplaceLoanDetail }) {
  const t = useT();
  const checks = loan.credit_checks ?? [];
  const monitoring = loan.monitoring;
  const stages = loan.recovery_stages;
  const notesQuery = useLoanRiskNotesData(loan.loan_id);
  const notes = [...(notesQuery.data ?? [])]
    .filter((note) => note.visibility === "public")
    .sort((left, right) => right.occurred_at.localeCompare(left.occurred_at));
  const stageRows = [...(stages?.stages ?? [])].reverse();
  return (
    <>
      <div className="r100-section-head"><h3>{t("File review")}</h3><span>{t("Recorded by Banxum")}</span></div>
      {checks.length > 0 ? (
        <div className="r100-checks">
          {checks.map((check) => {
            const parts = check.checked_on ? dayParts(check.checked_on) : null;
            return (
              <div className="r100-check" key={check.id}>
                <span className="r100-check-day">{parts ? <>{parts.day}<small>{parts.rest}</small></> : null}</span>
                <span>
                  <strong>{check.name}</strong>
                  <small>{check.result}</small>
                  {check.source ? <small className="r100-check-source">{t("Source: {source}", { source: check.source })}</small> : null}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="bxm-muted">{t("No check is recorded for this loan yet.")}</p>
      )}
      {monitoring && (monitoring.frequency || monitoring.focus) ? (
        <section className="r100-reporting">
          <div className="r100-section-head"><h3>{t("Monitoring")}</h3></div>
          {monitoring.frequency ? <p><b>{t("How often")}</b> · {monitoring.frequency}</p> : null}
          {monitoring.focus ? <p><b>{t("What is followed")}</b> · {monitoring.focus}</p> : null}
        </section>
      ) : null}
      {stageRows.length > 0 || stages?.next_step ? (
        <section className="r100-file-history">
          <div className="r100-section-head"><h3>{t("Recovery stages")}</h3><span>{t("Latest first")}</span></div>
          <ol className="bxm-timeline">
            {stages?.next_step ? (
              <li className="is-current">
                <h6>{t("Next step · {title}", { title: stages.next_step.title })}</h6>
                <p>{[stages.next_step.occurred_on ? formatDate(stages.next_step.occurred_on) : "", stages.next_step.investor_note].filter(Boolean).join(" · ")}</p>
              </li>
            ) : null}
            {stageRows.map((stage, index) => (
              <li className="is-done" key={`${stage.title}-${index}`}>
                <h6>{stage.title}</h6>
                <p>{[stage.occurred_on ? formatDate(stage.occurred_on) : "", stage.investor_note].filter(Boolean).join(" · ")}</p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      <section className="r100-file-history">
        <div className="r100-section-head"><h3>{t("Project updates")}</h3><span>{t("Latest first")}</span></div>
        {notes.length > 0 ? (
          <ol className="bxm-timeline">
            {notes.map((note) => (
              <li className="is-done" key={note.id}>
                <h6>{note.title || t("Loan update")}</h6>
                <p>{formatDate(note.occurred_at)}{note.body ? ` · ${note.body}` : ""}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="bxm-muted">{notesQuery.isError ? t("The loan updates could not be loaded.") : t("No update has been published for this loan yet.")}</p>
        )}
      </section>
    </>
  );
}
