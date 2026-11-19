/**
 * IP of Webby-Soft SRL.
 * 18.10 compliance tools (Q12, Q13): declaration reviews (the queue, the investor's file, the
 * decision, re-verification dates), staff roles (superadmin) and the proof of securities of a
 * loan (security verifier). The server checks each role; these screens only show the actions.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  useV1KycAdminComplianceInvestorsRetrieve,
  useV1KycAdminComplianceInvestorsReverificationCompleteCreate,
  useV1KycAdminComplianceInvestorsReverificationCreate,
  useV1KycAdminComplianceReviewsDecisionCreate,
  useV1KycAdminComplianceReviewsList,
  useV1KycAdminStaffRolesCreate,
  useV1LoansAdminLoansSecurityProofsList,
  useV1LoansAdminSecuritiesVerificationCreate,
  type ComplianceReview,
  type SecurityProofStatus
} from "../api/generated/banxumApi";
import { isFixturePreview } from "../investorPortal/data";
import { formatDate, formatDateTime } from "../investorPortal/format";
import { Banner, Button, Card, Chip, Empty, Field } from "../investorPortal/ui";

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "The request failed. Check the input and try again.";
}

const SOURCE_LABELS: Record<string, string> = {
  salary: "Salary",
  savings: "Savings",
  sale_of_property: "Sale of property",
  inheritance: "Inheritance",
  business_income: "Business income",
  dividends: "Dividends",
  investment_income: "Investment income",
  rent: "Rent",
  other: "Other"
};

export function DeclarationReviewsCard() {
  const [filter, setFilter] = useState<"open" | "closed">("open");
  const query = useV1KycAdminComplianceReviewsList({ status: filter }, { query: { enabled: !isFixturePreview, retry: false } });
  const reviews = query.data ?? [];
  const [selected, setSelected] = useState<ComplianceReview | null>(null);
  if (isFixturePreview) return <Banner tone="info" title="Declaration reviews">Shown with live data only.</Banner>;
  return (
    <Card padded>
      <div className="row between gap-8 wrap">
        <div>
          <h3>Declaration reviews</h3>
          <p className="muted">Reviews opened by the investors' declarations (Q12) or by compliance. A necessary open review pauses new investments; it is not a refusal.</p>
        </div>
        <select aria-label="Show reviews" onChange={(event) => setFilter(event.target.value as "open" | "closed")} value={filter}>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
        </select>
      </div>
      {query.error ? <Banner tone="bad" title="Could not load the reviews">{errorMessage(query.error)}</Banner> : null}
      {reviews.length ? (
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Investor</th>
                <th>Reasons</th>
                <th>Status</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((review) => (
                <tr aria-selected={selected?.id === review.id} className="clickable" key={review.id} onClick={() => setSelected(review)}>
                  <td>
                    {review.investor_name}
                    <div className="muted small">{review.investor_email}</div>
                  </td>
                  <td>{review.trigger_labels.join("; ") || review.opened_reason}</td>
                  <td>
                    <Chip tone={review.status === "closed" ? "ok" : review.status === "more_information" ? "warn" : "info"}>{review.status.replace("_", " ")}</Chip>
                  </td>
                  <td>{formatDate(review.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title={filter === "open" ? "No open review" : "No closed review"}>Reviews appear here when an investor's answers need one.</Empty>
      )}
      {selected ? <ReviewFile onDone={() => setSelected(null)} review={selected} /> : null}
    </Card>
  );
}

function ReviewFile({ review, onDone }: { review: ComplianceReview; onDone: () => void }) {
  const queryClient = useQueryClient();
  const file = useV1KycAdminComplianceInvestorsRetrieve(review.investor_id, { query: { retry: false } });
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState("");
  const refresh = (text: string) => {
    setResult(text);
    void queryClient.invalidateQueries();
  };
  const decision = useV1KycAdminComplianceReviewsDecisionCreate({ mutation: { onSuccess: (data) => { refresh(data.status === "closed" ? "The review is closed." : "The investor was asked for more information."); if (data.status === "closed") onDone(); } } });
  const reverify = useV1KycAdminComplianceInvestorsReverificationCreate({ mutation: { onSuccess: () => refresh("The re-verification date is set.") } });
  const complete = useV1KycAdminComplianceInvestorsReverificationCompleteCreate({ mutation: { onSuccess: () => refresh("The re-verification is done.") } });
  const latest = file.data?.declarations[0];
  const openReverification = file.data?.reverifications.find((item) => !item.completed_at && !item.replaced_at);
  const error = decision.error || reverify.error || complete.error || file.error;
  return (
    <div className="admin-form-panel" style={{ marginTop: 16 }}>
      <div className="admin-context-bar">
        <strong>{review.investor_name}</strong>
        <span>{review.investor_email}</span>
        {latest ? <span>Declaration v{latest.version} · {formatDateTime(latest.submitted_at)}</span> : <span>No declaration</span>}
      </div>
      {latest ? (
        <dl className="admin-review-list">
          <div className="admin-review-row"><span>Beneficial owner</span><strong>{latest.beneficial_owner_is_self ? "The investor" : latest.beneficial_owner_name}</strong></div>
          <div className="admin-review-row"><span>Sources of funds</span><strong>{latest.sources_of_funds.map((key) => SOURCE_LABELS[key] ?? key).join(", ")}{latest.savings_origin ? ` (savings: ${latest.savings_origin})` : ""}{latest.source_other_text ? ` (other: ${latest.source_other_text})` : ""}</strong></div>
          <div className="admin-review-row"><span>PEP</span><strong>{latest.pep_status}{latest.pep_person ? ` · ${latest.pep_person}, ${latest.pep_relation}, ${latest.pep_function}, ${latest.pep_country}` : ""}</strong></div>
          <div className="admin-review-row"><span>Yearly volume</span><strong>{latest.yearly_volume_band}</strong></div>
          {latest.subject_type === "company" ? <div className="admin-review-row"><span>Company</span><strong>{Object.values(latest.company_details).join(" · ")}</strong></div> : null}
        </dl>
      ) : null}
      {review.status !== "closed" ? (
        <form className="admin-action-form" onSubmit={(event: FormEvent) => { event.preventDefault(); decision.mutate({ reviewId: review.id, data: { decision: "close", note } }); }}>
          <Field label="Outcome (recorded with your name)">
            <textarea aria-label="Outcome" onChange={(event) => setNote(event.target.value)} rows={2} value={note} />
          </Field>
          <Field hint="Sent to the investor by email." label="Message to the investor">
            <textarea aria-label="Message to the investor" onChange={(event) => setMessage(event.target.value)} rows={2} value={message} />
          </Field>
          <div className="row gap-8 wrap">
            <Button disabled={note.trim().length < 5 || decision.isPending} type="submit" variant="primary">Close the review</Button>
            <Button disabled={message.trim().length < 5 || decision.isPending} onClick={() => decision.mutate({ reviewId: review.id, data: { decision: "more_information", investor_message: message } })}>Ask for more information</Button>
          </div>
        </form>
      ) : <p className="muted">Closed {review.closed_at ? formatDateTime(review.closed_at) : ""}: {review.outcome_note}</p>}
      <form className="admin-action-form" onSubmit={(event: FormEvent) => { event.preventDefault(); reverify.mutate({ investorId: review.investor_id, data: { due_date: dueDate, reason } }); }}>
        <h4>Re-verification date</h4>
        <p className="muted">{openReverification ? `Current date: ${formatDate(openReverification.due_date)} (notices sent: ${openReverification.notices_sent.join(", ") || "none"}).` : "No date set."} The investor gets notices 30 and 7 days before; after the date new investments pause.</p>
        <div className="row gap-8 wrap">
          <Field label="Date"><input aria-label="Re-verification date" onChange={(event) => setDueDate(event.target.value)} type="date" value={dueDate} /></Field>
          <Field label="Reason (internal risk)"><input aria-label="Reason" onChange={(event) => setReason(event.target.value)} value={reason} /></Field>
        </div>
        <div className="row gap-8 wrap">
          <Button disabled={!dueDate || reverify.isPending} type="submit">Set the date</Button>
          {openReverification ? <Button disabled={complete.isPending} onClick={() => complete.mutate({ investorId: review.investor_id })}>Mark the re-verification done</Button> : null}
        </div>
      </form>
      {error ? <Banner tone="bad" title="Action failed">{errorMessage(error)}</Banner> : null}
      {result ? <Banner tone="ok" title="Done">{result}</Banner> : null}
    </div>
  );
}

const ROLE_LABELS: Array<[string, string]> = [
  ["compliance", "Compliance"],
  ["compliance_deputy", "Compliance deputy"],
  ["security_verifier", "Security verifier"],
  ["security_verifier_deputy", "Security verifier deputy"]
];

export function StaffRolesCard() {
  const [userId, setUserId] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const mutation = useV1KycAdminStaffRolesCreate();
  if (isFixturePreview) return null;
  return (
    <Card padded>
      <h3>Staff roles</h3>
      <p className="muted">A superadmin grants the compliance and security verifier roles (and their deputies) to admin accounts. Each change is audited.</p>
      <form
        className="admin-action-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          mutation.mutate({ userId: userId.trim(), data: { roles: roles as never } });
        }}
      >
        <Field hint="The admin account's ID (Users > account)." label="Admin account ID">
          <input aria-label="Admin account ID" onChange={(event) => setUserId(event.target.value)} value={userId} />
        </Field>
        <div className="row gap-8 wrap">
          {ROLE_LABELS.map(([key, text]) => (
            <label key={key}>
              <input checked={roles.includes(key)} onChange={() => setRoles(roles.includes(key) ? roles.filter((item) => item !== key) : [...roles, key])} type="checkbox" /> {text}
            </label>
          ))}
        </div>
        <Button disabled={!userId.trim() || mutation.isPending} type="submit" variant="primary">Save roles</Button>
      </form>
      {mutation.error ? <Banner tone="bad" title="Could not save the roles">{errorMessage(mutation.error)}</Banner> : null}
      {mutation.data ? <Banner tone="ok" title="Roles saved">{mutation.data.roles.length ? mutation.data.roles.join(", ") : "No role"}</Banner> : null}
    </Card>
  );
}

export function SecurityProofsPanel({ loanId }: { loanId: string }) {
  const query = useV1LoansAdminLoansSecurityProofsList(loanId, { query: { enabled: !isFixturePreview, retry: false } });
  if (isFixturePreview) return <Banner tone="info" title="Proof of securities">Shown with live data only.</Banner>;
  const securities = query.data ?? [];
  return (
    <section aria-label="Proof of securities" className="admin-form-panel">
      <h4>Proof of securities</h4>
      <p className="muted">Publication needs, for each security that is not released, one linked document per required proof and a verification by a security verifier. An essential change needs a new verification.</p>
      {query.error ? <Banner tone="bad" title="Could not load the proofs">{errorMessage(query.error)}</Banner> : null}
      {securities.map((security) => (
        <SecurityProofRow key={security.security_id} security={security} />
      ))}
    </section>
  );
}

function SecurityProofRow({ security }: { security: SecurityProofStatus }) {
  const queryClient = useQueryClient();
  const [proofs, setProofs] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const mutation = useV1LoansAdminSecuritiesVerificationCreate({ mutation: { onSuccess: () => void queryClient.invalidateQueries() } });
  const complete = security.required_proofs.every((proof) => proofs[proof.key]);
  return (
    <div className="admin-review-list" style={{ marginTop: 12 }}>
      <div className="admin-review-row">
        <span>{security.security_type.replace("_", " ")}</span>
        <strong>
          {security.released ? <Chip tone="info">Released</Chip> : security.verified ? <Chip tone="ok">Verified by {security.verified_by} · {security.verified_at ? formatDate(security.verified_at) : ""}</Chip> : <Chip tone="warn">{security.needs_new_verification ? "Changed: verify again" : "Not verified"}</Chip>}
        </strong>
      </div>
      {!security.released && !security.verified ? (
        <form
          className="admin-action-form"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            mutation.mutate({ securityId: security.security_id, data: { proofs, note } });
          }}
        >
          {security.required_proofs.map((proof) => (
            <Field key={proof.key} label={proof.label}>
              <select aria-label={proof.label} onChange={(event) => setProofs({ ...proofs, [proof.key]: event.target.value })} value={proofs[proof.key] ?? ""}>
                <option value="">Choose a linked document</option>
                {security.document_ids.map((documentId) => (
                  <option key={documentId} value={documentId}>
                    {documentId.slice(0, 8)}
                  </option>
                ))}
              </select>
            </Field>
          ))}
          <Field label="Note">
            <input aria-label="Verification note" onChange={(event) => setNote(event.target.value)} value={note} />
          </Field>
          <Button disabled={!complete || mutation.isPending} type="submit" variant="primary">Record the verification</Button>
          {!security.document_ids.length ? <p className="muted">Link the documents to this security first (Securities).</p> : null}
        </form>
      ) : null}
      {mutation.error ? <Banner tone="bad" title="Could not record the verification">{errorMessage(mutation.error)}</Banner> : null}
    </div>
  );
}
