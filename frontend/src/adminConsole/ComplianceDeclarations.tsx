/**
 * IP of Webby-Soft SRL.
 * 18.10 compliance tools (Q12, Q13): declaration reviews (the queue, the investor's file, the
 * decision, re-verification dates), staff roles (superadmin) and the proof of securities of a
 * loan (security verifier). The server checks each role; these screens only show the actions.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  useV1AdminOpsLookupsInvestorsList,
  useV1KycAdminComplianceInvestorsRetrieve,
  useV1KycAdminComplianceInvestorsReverificationCompleteCreate,
  useV1KycAdminComplianceInvestorsReverificationCreate,
  useV1KycAdminComplianceReviewsCreate,
  useV1KycAdminComplianceReviewsDecisionCreate,
  useV1KycAdminComplianceReviewsList,
  useV1KycAdminStaffRolesCreate,
  useV1LoansAdminLoansSecurityProofsList,
  useV1LoansAdminLoanDocumentsCheckCreate,
  useV1LoansAdminLoansDocumentsCreate,
  useV1LoansAdminLoansDocumentsList,
  useV1LoansAdminSecuritiesVerificationCreate,
  v1LoansAdminSecuritiesDocumentsRetrieve,
  type ComplianceReview,
  LoanDocumentUploadDocumentTypeEnum,
  type LoanDocument,
  type ProofDocument,
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
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState("");
  const decision = useV1KycAdminComplianceReviewsDecisionCreate({
    mutation: {
      onSuccess: (data) => {
        setResult(data.status === "closed" ? "The review is closed." : "The investor was asked for more information.");
        void queryClient.invalidateQueries();
        if (data.status === "closed") onDone();
      }
    }
  });
  return (
    <div className="admin-form-panel" style={{ marginTop: 16 }}>
      <InvestorFile investorId={review.investor_id} name={review.investor_name} email={review.investor_email} />
      {review.status !== "closed" ? (
        <form className="admin-action-form" onSubmit={(event: FormEvent) => { event.preventDefault(); decision.mutate({ reviewId: review.id, data: { decision: "close", note } }); }}>
          <h4>Decision</h4>
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
      {decision.error ? <Banner tone="bad" title="Action failed">{errorMessage(decision.error)}</Banner> : null}
      {result ? <Banner tone="ok" title="Done">{result}</Banner> : null}
    </div>
  );
}

/** Audit S7-5: compliance finds any investor, opens the file, a manual review and the
 * re-verification date without an existing review. */
export function InvestorComplianceCard() {
  const [search, setSearch] = useState("");
  const [chosen, setChosen] = useState<{ id: string; label: string; meta: string } | null>(null);
  const term = search.trim();
  const lookup = useV1AdminOpsLookupsInvestorsList({ q: term, limit: 10 }, { query: { enabled: !isFixturePreview && term.length >= 2, retry: false } });
  if (isFixturePreview) return null;
  const results = lookup.data ?? [];
  return (
    <Card padded>
      <h3>Investor compliance file</h3>
      <p className="muted">Find an investor by name, email or account ID. Open the file to see the declarations, open a manual review or set a re-verification date.</p>
      <Field label="Find an investor">
        <input aria-label="Find an investor" onChange={(event) => setSearch(event.target.value)} placeholder="Name, email or ID" value={search} />
      </Field>
      {lookup.error ? <Banner tone="bad" title="Could not search">{errorMessage(lookup.error)}</Banner> : null}
      {term.length >= 2 && lookup.isSuccess && !results.length ? <p className="muted">No account found.</p> : null}
      {results.length ? (
        <ul aria-label="Search results" className="admin-review-list">
          {results.map((item) => (
            <li className="admin-review-row" key={item.id}>
              <span>
                {item.label}
                <span className="muted small"> · {item.meta}</span>
              </span>
              <Button onClick={() => setChosen({ id: item.id, label: item.label, meta: item.meta })}>Open file</Button>
            </li>
          ))}
        </ul>
      ) : null}
      {chosen ? (
        <div className="admin-form-panel" style={{ marginTop: 16 }}>
          <InvestorFile investorId={chosen.id} name={chosen.label} email={chosen.meta} />
          <ManualReviewForm investorId={chosen.id} />
        </div>
      ) : null}
    </Card>
  );
}

function ManualReviewForm({ investorId }: { investorId: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [necessary, setNecessary] = useState(true);
  const mutation = useV1KycAdminComplianceReviewsCreate({ mutation: { onSuccess: () => void queryClient.invalidateQueries() } });
  return (
    <form
      className="admin-action-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        mutation.mutate({ data: { investor_id: investorId, reason, necessary } });
      }}
    >
      <h4>Open a review</h4>
      <Field hint="Internal; recorded with your name." label="Reason for the review">
        <textarea aria-label="Reason for the review" onChange={(event) => setReason(event.target.value)} rows={2} value={reason} />
      </Field>
      <label>
        <input checked={necessary} onChange={() => setNecessary(!necessary)} type="checkbox" /> Necessary review: new investments pause until it is closed
      </label>
      <Button disabled={reason.trim().length < 5 || mutation.isPending} type="submit" variant="primary">Open the review</Button>
      {mutation.error ? <Banner tone="bad" title="Could not open the review">{errorMessage(mutation.error)}</Banner> : null}
      {mutation.data ? <Banner tone="ok" title="Review open">{mutation.data.necessary ? "New investments of this investor pause until the review is closed. An open necessary review takes the new reason." : "The review is open; investments continue."}</Banner> : null}
    </form>
  );
}

/** The investor's declarations and the re-verification date (used with or without a review). */
function InvestorFile({ investorId, name, email }: { investorId: string; name: string; email: string }) {
  const queryClient = useQueryClient();
  const file = useV1KycAdminComplianceInvestorsRetrieve(investorId, { query: { retry: false } });
  const [dueDate, setDueDate] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState("");
  const refresh = (text: string) => {
    setResult(text);
    void queryClient.invalidateQueries();
  };
  const reverify = useV1KycAdminComplianceInvestorsReverificationCreate({ mutation: { onSuccess: () => refresh("The re-verification date is set.") } });
  const complete = useV1KycAdminComplianceInvestorsReverificationCompleteCreate({ mutation: { onSuccess: () => refresh("The re-verification is done.") } });
  const latest = file.data?.declarations[0];
  const openReverification = file.data?.reverifications.find((item) => !item.completed_at && !item.replaced_at);
  const error = reverify.error || complete.error || file.error;
  return (
    <>
      <div className="admin-context-bar">
        <strong>{name}</strong>
        <span>{email}</span>
        {file.isLoading ? <span>Loading the file…</span> : latest ? <span>Declaration v{latest.version} · {formatDateTime(latest.submitted_at)}</span> : <span>No declaration</span>}
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
      {file.data ? (
        <form className="admin-action-form" onSubmit={(event: FormEvent) => { event.preventDefault(); reverify.mutate({ investorId, data: { due_date: dueDate, reason } }); }}>
          <h4>Re-verification date</h4>
          <p className="muted">{openReverification ? `Current date: ${formatDate(openReverification.due_date)} (notices sent: ${openReverification.notices_sent.join(", ") || "none"}).` : "No date set."} The investor gets notices 30 and 7 days before; after the date new investments pause.</p>
          <div className="row gap-8 wrap">
            <Field label="Date"><input aria-label="Re-verification date" onChange={(event) => setDueDate(event.target.value)} type="date" value={dueDate} /></Field>
            <Field label="Reason (internal risk)"><input aria-label="Reason" onChange={(event) => setReason(event.target.value)} value={reason} /></Field>
          </div>
          <div className="row gap-8 wrap">
            <Button disabled={!dueDate || reverify.isPending} type="submit">Set the date</Button>
            {openReverification ? <Button disabled={complete.isPending} onClick={() => complete.mutate({ investorId })}>Mark the re-verification done</Button> : null}
          </div>
        </form>
      ) : null}
      {error ? <Banner tone="bad" title="Action failed">{errorMessage(error)}</Banner> : null}
      {result ? <Banner tone="ok" title="Done">{result}</Banner> : null}
    </>
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
      <LoanDocumentsSection loanId={loanId} />
      {securities.map((security) => (
        <SecurityProofRow key={security.security_id} security={security} />
      ))}
    </section>
  );
}

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  land_register_extract: "Land register extract",
  mortgage_note_or_pledge: "Mortgage note or pledge agreement",
  guarantee_agreement: "Signed guarantee agreement",
  pledge_or_assignment_agreement: "Pledge or assignment agreement",
  third_party_debtor_notice: "Notice to the third-party debtor",
  security_transfer_agreement: "Pledge or security transfer agreement",
  asset_list: "List of the assets",
  pledge_agreement: "Pledge agreement",
  certificates_or_custody_confirmation: "Share certificates or custody confirmation",
  blocked_account_confirmation: "Blocked account confirmation",
  vehicle_registration: "Vehicle registration document",
  agreement: "The security agreement",
  other: "Other document"
};

/** Re-audit (owner's choice of 2026-11-20): proof files uploaded to the loan. A Loan Originator
 * claim has no borrower record, so its proofs are uploaded here; a file counts as proof only
 * after an admin confirmed its check (security review G-1, until a scanner exists). */
function LoanDocumentsSection({ loanId }: { loanId: string }) {
  const queryClient = useQueryClient();
  const list = useV1LoansAdminLoansDocumentsList(loanId, { query: { retry: false } });
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [type, setType] = useState<string>("other");
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [checksums, setChecksums] = useState<Record<string, string>>({});
  const refresh = () => void queryClient.invalidateQueries();
  const upload = useV1LoansAdminLoansDocumentsCreate({
    mutation: {
      onSuccess: () => {
        setFile(null);
        setName("");
        refresh();
      }
    }
  });
  const check = useV1LoansAdminLoanDocumentsCheckCreate({ mutation: { onSuccess: refresh } });
  const documents: LoanDocument[] = list.data ?? [];
  return (
    <div className="admin-review-list" style={{ marginTop: 12 }}>
      <h5>Documents uploaded to this loan</h5>
      <p className="muted">PDF, PNG or JPEG, up to 20 MB. Link them to a security under Securities. A file counts as proof only after its check.</p>
      <p className="muted">
        The platform does not open a file before its check. Scan the original file on your computer with your malware scanner and read it there. Then enter its SHA-256 (on a Mac: <code>shasum -a 256 file.pdf</code>). The check is accepted only when it matches the uploaded copy.
      </p>
      {documents.length ? (
        <ul aria-label="Loan documents" className="admin-review-list">
          {documents.map((document) => (
            <li className="admin-review-row" key={document.id}>
              <span>
                {document.display_name} · {document.document_type_label}
                {document.document_date ? ` · ${formatDate(document.document_date)}` : ""}
                <span className="muted small"> · ID {document.id}</span>
              </span>
              {document.checked ? (
                <Chip tone="ok">Checked{document.checked_at ? ` ${formatDate(document.checked_at)}` : ""}</Chip>
              ) : (
                <span className="row gap-8 wrap">
                  <span className="muted small">
                    Uploaded copy SHA-256: <code>{document.checksum_sha256}</code>
                  </span>
                  <input aria-label={`SHA-256 of the scanned ${document.display_name}`} onChange={(event) => setChecksums({ ...checksums, [document.id]: event.target.value })} placeholder="SHA-256 of the scanned file" value={checksums[document.id] ?? ""} />
                  <input aria-label={`How ${document.display_name} was checked`} onChange={(event) => setNotes({ ...notes, [document.id]: event.target.value })} placeholder="How was it checked?" value={notes[document.id] ?? ""} />
                  <Button
                    disabled={(notes[document.id] ?? "").trim().length < 5 || !(checksums[document.id] ?? "").trim() || check.isPending}
                    onClick={() => check.mutate({ documentId: document.id, data: { note: notes[document.id] ?? "", checksum_sha256: (checksums[document.id] ?? "").trim() } })}
                  >
                    Confirm check
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : null}
      <form
        aria-label="Upload a loan document"
        className="admin-action-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (!file) return;
          upload.mutate({
            loanId,
            data: {
              // The schema types a binary upload as a string; the client sends it as form data.
              file: file as unknown as string,
              display_name: name,
              document_type: type as LoanDocumentUploadDocumentTypeEnum,
              document_date: date || null
            }
          });
        }}
      >
        <div className="row gap-8 wrap">
          <Field label="File">
            <input accept="application/pdf,image/png,image/jpeg" aria-label="File" onChange={(event) => setFile(event.target.files?.[0] ?? null)} type="file" />
          </Field>
          <Field label="Name">
            <input aria-label="Document name" onChange={(event) => setName(event.target.value)} value={name} />
          </Field>
          <Field label="Type">
            <select aria-label="Document type" onChange={(event) => setType(event.target.value)} value={type}>
              {Object.values(LoanDocumentUploadDocumentTypeEnum).map((value) => (
                <option key={value} value={value}>
                  {DOCUMENT_TYPE_LABELS[value] ?? value}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Document date">
            <input aria-label="Document date" onChange={(event) => setDate(event.target.value)} type="date" value={date} />
          </Field>
        </div>
        <Button disabled={!file || !name.trim() || upload.isPending} type="submit">Upload</Button>
      </form>
      {upload.error || check.error || list.error ? <Banner tone="bad" title="Document action failed">{errorMessage(upload.error || check.error || list.error)}</Banner> : null}
    </div>
  );
}

function documentLabel(document: ProofDocument) {
  if (!document.available) return `Document no longer available (${document.id})`;
  const date = document.document_date ? formatDate(document.document_date) : document.uploaded_at ? `uploaded ${formatDate(document.uploaded_at)}` : "no date";
  return `${document.title} · ${document.document_type} · ${date}${document.checked ? "" : " · waits for its check"}`;
}

async function openDocument(securityId: string, documentId: string) {
  const file = await v1LoansAdminSecuritiesDocumentsRetrieve(securityId, documentId);
  const bytes = Uint8Array.from(atob(file.content), (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: file.content_type }));
  window.open(url, "_blank", "noopener");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function SecurityProofRow({ security }: { security: SecurityProofStatus }) {
  const queryClient = useQueryClient();
  const [proofs, setProofs] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [openError, setOpenError] = useState("");
  const mutation = useV1LoansAdminSecuritiesVerificationCreate({ mutation: { onSuccess: () => void queryClient.invalidateQueries() } });
  const complete = security.required_proofs.every((proof) => proofs[proof.key]);
  const open = (documentId: string) => {
    setOpenError("");
    openDocument(security.security_id, documentId).catch((error: unknown) => setOpenError(errorMessage(error)));
  };
  return (
    <div className="admin-review-list" style={{ marginTop: 12 }}>
      <div className="admin-review-row">
        <span>{security.security_type.replace("_", " ")}</span>
        <strong>
          {security.released ? <Chip tone="info">Released</Chip> : security.verified ? <Chip tone="ok">Verified by {security.verified_by} · {security.verified_at ? formatDate(security.verified_at) : ""}</Chip> : <Chip tone="warn">{security.needs_new_verification ? "Changed: verify again" : "Not verified"}</Chip>}
        </strong>
      </div>
      {security.configuration_error ? <Banner tone="bad" title="Proof setting not valid">{security.configuration_error}</Banner> : null}
      {security.problem ? <p className="muted">Why: {security.problem}</p> : null}
      {security.documents.length ? (
        <ul aria-label="Linked documents" className="admin-review-list">
          {security.documents.map((document) => (
            <li className="admin-review-row" key={document.id}>
              <span>
                {documentLabel(document)}
                <span className="muted small"> · ID {document.id}</span>
              </span>
              {/* Re-audit 2: the server opens a file only after its check. */}
              {document.available && document.checked ? <Button onClick={() => open(document.id)}>Open</Button> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {openError ? <Banner tone="bad" title="Could not open the document">{openError}</Banner> : null}
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
                {security.documents
                  .filter((document) => document.available && document.checked)
                  .map((document) => (
                    <option key={document.id} value={document.id}>
                      {documentLabel(document)}
                    </option>
                  ))}
              </select>
            </Field>
          ))}
          <Field label="Note">
            <input aria-label="Verification note" onChange={(event) => setNote(event.target.value)} value={note} />
          </Field>
          <p className="muted">Open and check each document before you record the verification.</p>
          <Button disabled={!complete || mutation.isPending} type="submit" variant="primary">Record the verification</Button>
          {!security.document_ids.length ? <p className="muted">Link the documents to this security first (Securities).</p> : null}
        </form>
      ) : null}
      {security.history.length ? (
        <details>
          <summary>Verification history ({security.history.length})</summary>
          <ul className="admin-review-list">
            {security.history.map((item) => (
              <li key={item.verified_at}>
                <strong>{item.verifier_name}</strong> · {formatDateTime(item.verified_at)}
                {item.note ? ` · ${item.note}` : ""}
                <ul>
                  {item.proofs.map((proof) => (
                    <li key={proof.key}>
                      {proof.label}: {documentLabel(proof.document)}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {mutation.error ? <Banner tone="bad" title="Could not record the verification">{errorMessage(mutation.error)}</Banner> : null}
    </div>
  );
}
