import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import {
  useV1LedgerAdminPayoutInstructionsRevokeCreate,
  useV1LedgerAdminPayoutInstructionsVerifyCreate,
  type AdminPayoutInstructionRow,
  type V1LedgerAdminPayoutInstructionsListState
} from "../api/generated/banxumApi";
import { ApiClientError } from "../api/client/httpClient";
import { isFixturePreview } from "../investorPortal/data";
import { formatDateTime } from "../investorPortal/format";
import { Banner, Button, Card, Chip, Empty, Field, type Tone } from "../investorPortal/ui";
import { useAdminPayoutInstructionData, useAdminPayoutInstructionsData } from "./data";

const OWNERSHIP_CONFLICT_CODE = "payout_iban_verified_for_other_investor";

const stateLabels: Record<string, string> = {
  pending: "Pending verification",
  verified: "Verified",
  revoked: "Revoked",
  rejected: "Rejected"
};

const stateTones: Record<string, Tone> = {
  pending: "warn",
  verified: "ok",
  revoked: "bad",
  rejected: "neutral"
};

const originLabels: Record<string, string> = {
  investor_request: "Investor request",
  lender_deposit: "Incoming deposit",
  admin: "Admin"
};

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "The request failed. Check the input and try again.";
}

function errorCode(error: unknown) {
  if (!(error instanceof ApiClientError)) return "";
  const payload = error.payload as { code?: unknown } | null | undefined;
  return typeof payload?.code === "string" ? payload.code : "";
}

function formatIban(iban: string) {
  return iban.replace(/\s/g, "").replace(/(.{4})/g, "$1 ").trim();
}

/** Verify (with evidence), reject or revoke one payout IBAN. Used by the queue and by tasks. */
export function PayoutInstructionActions({
  instruction,
  onDone
}: {
  instruction: AdminPayoutInstructionRow;
  /** Called with the result message; the row may leave the current list afterwards. */
  onDone?: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const [evidence, setEvidence] = useState("");
  const [confirmedName, setConfirmedName] = useState("");
  const [notes, setNotes] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const done = (message: string) => {
    setResult(message);
    void queryClient.invalidateQueries();
    onDone?.(message);
  };
  const verify = useV1LedgerAdminPayoutInstructionsVerifyCreate({
    mutation: { onSuccess: () => done("IBAN verified. The investor can now use it for withdrawals.") }
  });
  const revoke = useV1LedgerAdminPayoutInstructionsRevokeCreate({
    mutation: {
      onSuccess: (response) =>
        done(
          response.action === "rejected"
            ? "IBAN request rejected. The investor was told by email."
            : `IBAN revoked. The investor was told by email.${
                response.flagged_withdrawal_request_ids.length
                  ? ` ${response.flagged_withdrawal_request_ids.length} open withdrawal(s) to this IBAN are stopped: cancel them in Withdrawals.`
                  : ""
              }`
        )
    }
  });
  const pending = instruction.state === "pending";
  const verified = instruction.state === "verified";
  const ownershipConflict = errorCode(verify.error) === OWNERSHIP_CONFLICT_CODE;
  const needsOverride = instruction.other_investor_count > 0 || ownershipConflict;

  function submitVerify(event: FormEvent) {
    event.preventDefault();
    if (isFixturePreview) {
      setResult("Preview: the IBAN would be verified with this evidence.");
      return;
    }
    verify.mutate({
      instructionId: instruction.id,
      data: {
        evidence_reference: evidence,
        notes: notes || undefined,
        destination_account_name: confirmedName || undefined,
        other_investor_override_reason: overrideReason || undefined
      }
    });
  }

  function submitRevoke(event: FormEvent) {
    event.preventDefault();
    if (isFixturePreview) {
      setResult(`Preview: the IBAN would be ${pending ? "rejected" : "revoked"}.`);
      return;
    }
    revoke.mutate({ instructionId: instruction.id, data: { reason } });
  }

  return (
    <div className="col gap-12" data-testid="payout-iban-actions">
      <div className="admin-detail-grid">
        <Row label="Investor" value={`${instruction.investor_name || instruction.investor_email} (${instruction.investor_reference || instruction.investor_email || instruction.investor_user_id})`} />
        <Row label="Currency" value={instruction.currency} />
        <Row label="IBAN" value={<span className="mono">{formatIban(instruction.destination_iban)}</span>} />
        <Row label="Account name" value={instruction.destination_account_name || "-"} />
        <Row label="Status" value={<Chip status={instruction.state} tone={stateTones[instruction.state] ?? "neutral"}>{stateLabels[instruction.state] ?? instruction.state}</Chip>} />
        <Row label="Came from" value={originLabels[instruction.origin] ?? instruction.origin} />
        {instruction.evidence_reference ? <Row label="Evidence" value={instruction.evidence_reference} /> : null}
        {instruction.revocation_reason ? <Row label="Reason" value={instruction.revocation_reason} /> : null}
      </div>
      {instruction.other_investor_count > 0 && (pending || verified) ? (
        <Banner tone="warn" title="IBAN used by another investor">
          This IBAN is a verified payout account of {instruction.other_investor_count} other investor(s). Check who owns the account.
        </Banner>
      ) : null}
      {pending ? (
        <form className="admin-action-form" onSubmit={submitVerify}>
          <Field hint="Where the ownership proof is kept: bank letter, statement, ticket." label="Evidence reference">
            <input aria-label="Evidence reference" onChange={(event) => setEvidence(event.target.value)} required value={evidence} />
          </Field>
          <Field hint="Optional. Only if the evidence shows a different account holder name." label="Confirmed account name">
            <input aria-label="Confirmed account name" onChange={(event) => setConfirmedName(event.target.value)} placeholder={instruction.destination_account_name} value={confirmedName} />
          </Field>
          {needsOverride ? (
            <Field hint="Required because the IBAN belongs to another investor." label="Override reason">
              <textarea aria-label="Override reason" onChange={(event) => setOverrideReason(event.target.value)} required rows={2} value={overrideReason} />
            </Field>
          ) : null}
          <Field label="Notes">
            <textarea aria-label="Verification notes" onChange={(event) => setNotes(event.target.value)} rows={2} value={notes} />
          </Field>
          {verify.error ? <Banner tone="bad" title="Could not verify the IBAN">{errorMessage(verify.error)}</Banner> : null}
          <div className="row gap-8 wrap">
            <Button disabled={verify.isPending || !evidence.trim()} type="submit" variant="primary">Verify IBAN</Button>
          </div>
        </form>
      ) : null}
      {pending || verified ? (
        <form className="admin-action-form" onSubmit={submitRevoke}>
          <Field
            hint={
              pending
                ? "The request is closed. The investor gets a notice that the IBAN was not verified. This reason stays internal."
                : "The IBAN leaves the investor's withdrawal choices and forced returns. Open withdrawals to it are stopped. The investor gets a notice. This reason stays internal."
            }
            label={pending ? "Reject reason" : "Revoke reason"}
          >
            <textarea aria-label={pending ? "Reject reason" : "Revoke reason"} onChange={(event) => setReason(event.target.value)} required rows={2} value={reason} />
          </Field>
          {revoke.error ? <Banner tone="bad" title="Could not change the IBAN">{errorMessage(revoke.error)}</Banner> : null}
          <div className="row gap-8 wrap">
            <Button disabled={revoke.isPending || !reason.trim()} type="submit" variant="danger">
              {pending ? "Reject request" : "Revoke IBAN"}
            </Button>
          </div>
        </form>
      ) : null}
      {result && !onDone ? <Banner tone={isFixturePreview ? "info" : "ok"} title="Done">{result}</Banner> : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="admin-review-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

/** Payout IBAN queue: pending investor requests first; also verified, revoked and rejected. */
export function PayoutIbanQueue() {
  const [state, setState] = useState<V1LedgerAdminPayoutInstructionsListState | "">("pending");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const listQuery = useAdminPayoutInstructionsData({
    state: state || undefined,
    q: search.trim() || undefined,
    limit: 50
  });
  const rows = listQuery.data?.results ?? [];
  const selected = rows.find((row) => row.id === selectedId) ?? null;

  return (
    <Card padded>
      <h2>IBAN verification</h2>
      <p>
        Investors add payout IBANs in the portal. Verify a request only with evidence of ownership.
        Revoke an IBAN that may no longer be used.
      </p>
      <div className="row gap-8 wrap" style={{ marginBottom: 12 }}>
        <select aria-label="Filter payout IBANs by status" onChange={(event) => { setState(event.target.value as V1LedgerAdminPayoutInstructionsListState | ""); setSelectedId(""); }} value={state}>
          <option value="pending">Pending verification</option>
          <option value="verified">Verified</option>
          <option value="revoked">Revoked</option>
          <option value="rejected">Rejected</option>
          <option value="">All</option>
        </select>
        <input aria-label="Search payout IBANs" onChange={(event) => setSearch(event.target.value)} placeholder="Investor, email, reference or IBAN" value={search} />
      </div>
      {listQuery.error ? <Banner tone="bad" title="Could not load payout IBANs">{errorMessage(listQuery.error)}</Banner> : null}
      {notice ? <Banner tone={isFixturePreview ? "info" : "ok"} title="Done">{notice}</Banner> : null}
      {rows.length ? (
        <div className="table-wrap admin-table-wrap">
          <table aria-label="Payout IBANs" className="admin-table">
            <thead>
              <tr>
                <th>Investor</th>
                <th>IBAN</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className={row.id === selectedId ? "admin-selected-row" : ""} key={row.id} onClick={() => { setSelectedId(row.id); setNotice(null); }}>
                  <td>
                    <div className="col gap-4">
                      <strong>{row.investor_name || row.investor_email}</strong>
                      <span className="mono muted">{row.investor_reference || row.investor_email}</span>
                    </div>
                  </td>
                  <td>
                    <div className="col gap-4">
                      <span className="mono">{row.currency} · {formatIban(row.destination_iban)}</span>
                      <span className="muted">{row.destination_account_name}</span>
                    </div>
                  </td>
                  <td>
                    <div className="col gap-4">
                      <div className="row gap-4 wrap">
                        <Chip status={row.state} tone={stateTones[row.state] ?? "neutral"}>{stateLabels[row.state] ?? row.state}</Chip>
                        {row.other_investor_count > 0 && row.state !== "revoked" && row.state !== "rejected" ? <Chip dot={false} tone="warn">Other investor</Chip> : null}
                      </div>
                      <span className="muted">{originLabels[row.origin] ?? row.origin} · {formatDateTime(row.updated_at)}</span>
                    </div>
                  </td>
                  <td><Button onClick={(event) => { event.stopPropagation(); setSelectedId(row.id); setNotice(null); }} size="sm">Open</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty icon="checkCircle" title={state === "pending" ? "No IBAN waits for verification" : "No payout IBANs match"}>
          {state === "pending" ? "New investor IBAN requests appear here and in Tasks." : "Change the filter or the search."}
        </Empty>
      )}
      {selected ? (
        <div className="admin-form-panel" style={{ marginTop: 16 }}>
          <PayoutInstructionActions
            instruction={selected}
            key={selected.id}
            onDone={(message) => {
              // The row may leave this filtered list, so keep the result above the table.
              setNotice(message);
              if (!isFixturePreview) setSelectedId("");
              void listQuery.refetch();
            }}
          />
        </div>
      ) : null}
    </Card>
  );
}

/** Task drawer block for "IBAN verification" tasks: verify or reject from the task. */
export function PayoutInstructionTaskBlock({ instructionId }: { instructionId: string }) {
  const query = useAdminPayoutInstructionData(instructionId, true);
  const instruction = query.data;
  const [notice, setNotice] = useState<string | null>(null);
  if (query.error) {
    return <Banner tone="bad" title="Could not load the IBAN request">{errorMessage(query.error)}</Banner>;
  }
  if (!instruction) return <p className="muted">Loading the IBAN request...</p>;
  return (
    <div className="admin-drawer-action">
      <h4>{instruction.state === "pending" ? "Verify or reject this IBAN" : "Payout IBAN"}</h4>
      {instruction.state === "pending" ? (
        <p className="muted">This task closes when the IBAN is verified or rejected.</p>
      ) : null}
      {notice ? <Banner tone={isFixturePreview ? "info" : "ok"} title="Done">{notice}</Banner> : null}
      <PayoutInstructionActions
        instruction={instruction}
        key={`${instruction.id}:${instruction.state}`}
        onDone={(message) => {
          setNotice(message);
          void query.refetch();
        }}
      />
    </div>
  );
}
