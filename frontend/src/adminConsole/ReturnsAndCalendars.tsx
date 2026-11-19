// IP of Webby-Soft SRL.
/**
 * 18.4 finance tools: failed returns (Q02), a return account verified from a deposit (Q02.5) and the
 * CHF/EUR settlement calendars (F17). The admin console keeps its own style.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import {
  BalanceReturnFailureReasonEnum,
  useV1AdminSettlementCalendarsConfirmCreate,
  useV1AdminSettlementCalendarsDaysCreate,
  useV1AdminSettlementCalendarsDaysRemoveCreate,
  useV1AdminSettlementCalendarsRetrieve,
  useV1LedgerAdminInvestorsDepositVerificationCandidatesRetrieve,
  useV1LedgerAdminLenderDepositsVerifyAccountCreate,
  useV1LedgerAdminPayoutInstructionsList,
  useV1LedgerAdminReturnFailuresResendCreate,
  useV1LedgerAdminReturnFailuresResolveCreate,
  useV1LedgerAdminReturnFailuresRetrieve,
  useV1LedgerAdminWithdrawalRequestsReturnedCreate,
  type BalanceReturnFailure,
  type DepositVerificationCandidate,
  type SettlementCalendarDay
} from "../api/generated/banxumApi";
import { isFixturePreview } from "../investorPortal/data";
import { formatDate, formatDateTime } from "../investorPortal/format";
import { Banner, Button, Card, Chip, Empty, Field, Money } from "../investorPortal/ui";
import { withIdempotencyKey } from "./adminIdempotency";
import { useAdminBusinessDate } from "./adminBusinessDate";

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "The request failed. Check the input and try again.";
}

function maskIban(iban: string) {
  const compact = iban.replace(/\s/g, "");
  return compact.length > 8 ? `${compact.slice(0, 4)} ... ${compact.slice(-4)}` : compact;
}

const REASON_LABELS: Record<string, string> = {
  account_closed: "Account closed",
  account_unknown: "Account number unknown",
  name_mismatch: "Account holder name does not match",
  account_blocked: "Account blocked or restricted",
  bank_restriction: "Restriction at the receiving bank",
  technical: "Technical error",
  other: "Other reason"
};

// --- Failed returns ---------------------------------------------------------------------------

/** Q02: open failed returns; send again only to a corrected or newly verified account. */
export function ReturnFailuresCard() {
  const [status, setStatus] = useState<"open" | "">("open");
  const query = useV1LedgerAdminReturnFailuresRetrieve(
    { status: status || undefined, limit: 100 },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const rows = query.data?.results ?? [];
  const [selectedId, setSelectedId] = useState("");
  const selected = rows.find((row) => row.id === selectedId);
  return (
    <Card padded>
      <div className="admin-panel-head">
        <div>
          <h2>Failed returns</h2>
          <p>
            Returns that the receiving bank sent back. The money is on the investor's balance again with its original dates. The
            platform does not retry: send again only to a corrected or newly verified account.
          </p>
        </div>
        <Field label="Show">
          <select aria-label="Show" onChange={(event) => setStatus(event.target.value as "open" | "")} value={status}>
            <option value="open">Open</option>
            <option value="">All</option>
          </select>
        </Field>
      </div>
      {query.error ? <Banner tone="bad" title="Could not load failed returns">{errorMessage(query.error)}</Banner> : null}
      {rows.length ? (
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Investor</th>
                <th>Amount</th>
                <th>Account</th>
                <th>Bank reason</th>
                <th>Sent back</th>
                <th>Compliance</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className={row.id === selectedId ? "admin-selected-row" : ""} key={row.id}>
                  <td className="mono">{row.investor_user_id.slice(0, 8)}</td>
                  <td>
                    <Money amountMinor={row.amount_minor} currency={row.currency} />
                  </td>
                  <td className="mono">{maskIban(row.failed_destination_iban)}</td>
                  <td>
                    {row.reason_label}
                    {row.bank_reason_text ? <span className="muted"> · {row.bank_reason_text}</span> : null}
                  </td>
                  <td className="mono">{formatDate(row.returned_value_date)}</td>
                  <td>{row.escalated_at ? <Chip tone="warn">Since {formatDateTime(row.escalated_at)}</Chip> : <span className="muted">-</span>}</td>
                  <td>
                    <Chip tone={row.status === "open" ? "bad" : "ok"}>{row.status === "open" ? "Return failed" : "Resolved"}</Chip>
                  </td>
                  <td>{row.status === "open" ? <Button onClick={() => setSelectedId(row.id)} size="sm">Act</Button> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty icon="checkCircle" title={status === "open" ? "No open failed returns" : "No failed returns"}>
          Record a returned transfer below when the bank sends a return back.
        </Empty>
      )}
      {selected ? <ReturnFailureActions failure={selected} onDone={() => setSelectedId("")} /> : null}
    </Card>
  );
}

function ReturnFailureActions({ failure, onDone }: { failure: BalanceReturnFailure; onDone: () => void }) {
  const queryClient = useQueryClient();
  const accounts = useV1LedgerAdminPayoutInstructionsList(
    { investor_user_id: failure.investor_user_id, currency: failure.currency, state: "verified", limit: 50 },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const options = accounts.data?.results ?? [];
  const [accountId, setAccountId] = useState("");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const done = (message: string) => {
    setResult(message);
    void queryClient.invalidateQueries();
    onDone();
  };
  const resend = useV1LedgerAdminReturnFailuresResendCreate({
    mutation: { onSuccess: () => done("A new return request was created. Send the transfer before the cut-off.") }
  });
  const resolve = useV1LedgerAdminReturnFailuresResolveCreate({
    mutation: { onSuccess: () => done("The failed return is resolved.") }
  });
  return (
    <div className="admin-form-panel" style={{ marginTop: 16 }}>
      <div className="admin-context-bar">
        <strong>
          <Money amountMinor={failure.amount_minor} currency={failure.currency} />
        </strong>
        <span>Failed account {maskIban(failure.failed_destination_iban)}</span>
        <span>{failure.reason_label}</span>
      </div>
      <form
        className="admin-action-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (isFixturePreview) return setResult("Preview: the return would be sent again.");
          resend.mutate({ failureId: failure.id, data: { payout_instruction_id: accountId, note: note || undefined } });
        }}
      >
        <Field hint="Only a verified account of the investor in the same currency." label="Send again to">
          <select aria-label="Send again to" onChange={(event) => setAccountId(event.target.value)} required value={accountId}>
            <option value="">Choose an account</option>
            {options.map((account) => (
              <option key={account.id} value={account.id}>
                {maskIban(account.destination_iban)} · {account.destination_account_name}
                {account.verified_at ? ` · verified ${formatDate(account.verified_at)}` : ""}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Note">
          <textarea aria-label="Note" onChange={(event) => setNote(event.target.value)} rows={2} value={note} />
        </Field>
        <div className="row gap-8 wrap">
          <Button disabled={!accountId || resend.isPending} type="submit" variant="primary">
            Send again
          </Button>
          <Button
            disabled={!note.trim() || resolve.isPending}
            onClick={() => {
              if (isFixturePreview) return setResult("Preview: the failed return would be resolved.");
              resolve.mutate({ failureId: failure.id, data: { note } });
            }}
            variant="danger"
          >
            Resolve with the note
          </Button>
        </div>
      </form>
      {resend.error || resolve.error ? <Banner tone="bad" title="Action failed">{errorMessage(resend.error || resolve.error)}</Banner> : null}
      {result ? <Banner tone="ok" title="Done">{result}</Banner> : null}
    </div>
  );
}

/** Q02: record that the bank sent a withdrawal or return back (once per withdrawal). */
export function ReturnedTransferForm() {
  const queryClient = useQueryClient();
  const businessDate = useAdminBusinessDate();
  const [withdrawalId, setWithdrawalId] = useState("");
  const [valueDate, setValueDate] = useState(businessDate);
  const [reason, setReason] = useState<BalanceReturnFailureReasonEnum>(BalanceReturnFailureReasonEnum.account_closed);
  const [bankReason, setBankReason] = useState("");
  const [bankReference, setBankReference] = useState("");
  const [evidence, setEvidence] = useState("");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const mutation = useV1LedgerAdminWithdrawalRequestsReturnedCreate({
    mutation: {
      onSuccess: (failure) => {
        setResult(
          failure.status === "open"
            ? "Recorded. The money is back on the balance; a failed-return task is open."
            : "Recorded. The money is back on the balance and can be used again."
        );
        void queryClient.invalidateQueries();
      }
    }
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (isFixturePreview) return setResult("Preview: the returned transfer would be recorded.");
    mutation.mutate({
      withdrawalRequestId: withdrawalId.trim(),
      data: withIdempotencyKey(
        "withdrawal-returned",
        {
          returned_value_date: valueDate,
          reason_code: reason,
          bank_reason_text: bankReason || undefined,
          bank_reference: bankReference || undefined,
          evidence_reference: evidence || undefined,
          notes: notes || undefined
        },
        { withdrawalRequestId: withdrawalId.trim() }
      )
    });
  }
  return (
    <Card padded>
      <h2>Record a returned transfer</h2>
      <p>When the bank sends a sent withdrawal or return back. The cause follows the bank's answer.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <div className="admin-form-grid">
          <Field label="Withdrawal request ID">
            <input aria-label="Withdrawal request ID" onChange={(event) => setWithdrawalId(event.target.value)} required value={withdrawalId} />
          </Field>
          <Field label="Value date of the returned money">
            <input aria-label="Value date of the returned money" onChange={(event) => setValueDate(event.target.value)} required type="date" value={valueDate} />
          </Field>
          <Field label="Bank reason">
            <select aria-label="Bank reason" onChange={(event) => setReason(event.target.value as BalanceReturnFailureReasonEnum)} value={reason}>
              {Object.values(BalanceReturnFailureReasonEnum).map((value) => (
                <option key={value} value={value}>
                  {REASON_LABELS[value] ?? value}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Bank's text or code">
            <input aria-label="Bank's text or code" onChange={(event) => setBankReason(event.target.value)} value={bankReason} />
          </Field>
          <Field label="Bank reference">
            <input aria-label="Bank reference" onChange={(event) => setBankReference(event.target.value)} value={bankReference} />
          </Field>
          <Field label="Evidence reference">
            <input aria-label="Evidence reference" onChange={(event) => setEvidence(event.target.value)} value={evidence} />
          </Field>
        </div>
        <Field label="Notes">
          <textarea aria-label="Notes" onChange={(event) => setNotes(event.target.value)} rows={2} value={notes} />
        </Field>
        <Button disabled={!withdrawalId.trim() || mutation.isPending} type="submit" variant="primary">
          Record returned transfer
        </Button>
      </form>
      {mutation.error ? <Banner tone="bad" title="Could not record it">{errorMessage(mutation.error)}</Banner> : null}
      {result ? <Banner tone="ok" title="Returned transfer">{result}</Banner> : null}
    </Card>
  );
}

// --- Q02.5: verify a return account from a deposit -----------------------------------------------

export function DepositAccountVerificationCard() {
  const [investorId, setInvestorId] = useState("");
  const [lookup, setLookup] = useState("");
  const query = useV1LedgerAdminInvestorsDepositVerificationCandidatesRetrieve(lookup, {
    query: { enabled: !isFixturePreview && /^[0-9a-f-]{36}$/i.test(lookup), retry: false }
  });
  return (
    <Card padded>
      <h2>Verify a return account from a deposit</h2>
      <p>
        Compare the holder and IBAN of the incoming transfer with the investor's verified identity. A collecting or intermediary
        account, or a holder that differs or is unclear, needs a bank statement or bank confirmation first.
      </p>
      <form
        className="row gap-8 wrap"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          setLookup(investorId.trim());
        }}
      >
        <Field label="Investor ID">
          <input aria-label="Investor ID" onChange={(event) => setInvestorId(event.target.value)} value={investorId} />
        </Field>
        <Button type="submit">Show deposits</Button>
      </form>
      {query.error ? <Banner tone="bad" title="Could not load deposits">{errorMessage(query.error)}</Banner> : null}
      {query.data ? (
        <>
          <p>
            Verified identity: <strong>{query.data.verified_identity_name || "-"}</strong>
          </p>
          {query.data.results.length ? (
            query.data.results.map((deposit) => <DepositVerificationRow deposit={deposit} key={deposit.id} />)
          ) : (
            <Empty icon="checkCircle" title="No deposit to verify">Every paying account of this investor is already verified.</Empty>
          )}
        </>
      ) : null}
    </Card>
  );
}

function DepositVerificationRow({ deposit }: { deposit: DepositVerificationCandidate }) {
  const queryClient = useQueryClient();
  const [holderMatches, setHolderMatches] = useState(false);
  const [notIntermediary, setNotIntermediary] = useState(false);
  const [evidence, setEvidence] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const mutation = useV1LedgerAdminLenderDepositsVerifyAccountCreate({
    mutation: {
      onSuccess: () => {
        setResult("The account is now a verified return account of the investor.");
        void queryClient.invalidateQueries();
      }
    }
  });
  return (
    <div className="admin-form-panel" style={{ marginTop: 12 }}>
      <div className="admin-context-bar">
        <strong>{deposit.payer_name || "Unknown holder"}</strong>
        <span className="mono">{maskIban(deposit.payer_iban)}</span>
        <Money amountMinor={deposit.amount_minor} currency={deposit.currency} />
        <span>{formatDate(deposit.value_date)}</span>
      </div>
      <label className="row gap-8">
        <input checked={holderMatches} onChange={(event) => setHolderMatches(event.target.checked)} type="checkbox" />
        The holder of the transfer matches the verified identity
      </label>
      <label className="row gap-8">
        <input checked={notIntermediary} onChange={(event) => setNotIntermediary(event.target.checked)} type="checkbox" />
        Not a collecting or intermediary account
      </label>
      <Field label="Evidence reference">
        <input aria-label="Evidence reference" onChange={(event) => setEvidence(event.target.value)} value={evidence} />
      </Field>
      <Button
        disabled={!holderMatches || !notIntermediary || !evidence.trim() || mutation.isPending}
        onClick={() => {
          if (isFixturePreview) return setResult("Preview: the account would be verified.");
          mutation.mutate({
            bankOperationId: deposit.id,
            data: { holder_matches_identity: holderMatches, not_intermediary_account: notIntermediary, evidence_reference: evidence }
          });
        }}
        variant="primary"
      >
        Verify from this deposit
      </Button>
      {mutation.error ? <Banner tone="bad" title="Could not verify">{errorMessage(mutation.error)}</Banner> : null}
      {result ? <Banner tone="ok" title="Verified">{result}</Banner> : null}
    </div>
  );
}

// --- F17: settlement calendars -------------------------------------------------------------------

export function SettlementCalendarsCard() {
  const queryClient = useQueryClient();
  const businessDate = useAdminBusinessDate();
  const [currency, setCurrency] = useState<"CHF" | "EUR">("CHF");
  const [year, setYear] = useState(Number(businessDate.slice(0, 4)) || new Date().getFullYear());
  const query = useV1AdminSettlementCalendarsRetrieve({ currency, year }, { query: { enabled: !isFixturePreview, retry: false } });
  const calendar = query.data;
  const [newDate, setNewDate] = useState("");
  const [newName, setNewName] = useState("");
  const [note, setNote] = useState("");
  const [removal, setRemoval] = useState<{ day: SettlementCalendarDay; reason: string } | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const refresh = (message: string) => {
    setResult(message);
    void queryClient.invalidateQueries();
  };
  const add = useV1AdminSettlementCalendarsDaysCreate({ mutation: { onSuccess: () => refresh("The day is closed.") } });
  const remove = useV1AdminSettlementCalendarsDaysRemoveCreate({
    mutation: { onSuccess: () => { setRemoval(null); refresh("The day is open."); } }
  });
  const confirm = useV1AdminSettlementCalendarsConfirmCreate({ mutation: { onSuccess: () => refresh("The year is confirmed.") } });
  const error = query.error || add.error || remove.error || confirm.error;
  return (
    <Card padded>
      <h2>Settlement calendars</h2>
      <p>
        Closed days of the CHF (SIX SIC) and EUR (TARGET) payment systems, besides weekends. Return dates and due dates use them.
        Check each year against the bank and confirm it.
      </p>
      <div className="row gap-8 wrap">
        <Field label="Currency">
          <select aria-label="Currency" onChange={(event) => setCurrency(event.target.value as "CHF" | "EUR")} value={currency}>
            <option value="CHF">CHF (SIX SIC)</option>
            <option value="EUR">EUR (TARGET)</option>
          </select>
        </Field>
        <Field label="Year">
          <input aria-label="Year" max={2100} min={2000} onChange={(event) => setYear(Number(event.target.value))} type="number" value={year} />
        </Field>
      </div>
      {calendar ? (
        <p>
          {calendar.confirmed_at ? (
            <Chip tone="ok">Confirmed {formatDateTime(calendar.confirmed_at)}</Chip>
          ) : calendar.stored ? (
            <Chip tone="warn">Preloaded, not confirmed</Chip>
          ) : (
            <Chip tone="neutral">Not preloaded: rule days</Chip>
          )}
        </p>
      ) : null}
      {error ? <Banner tone="bad" title="Calendar action failed">{errorMessage(error)}</Banner> : null}
      {calendar?.days.length ? (
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Name</th>
                <th>Source</th>
                <th>State</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {calendar.days.map((day) => (
                <tr key={day.date}>
                  <td className="mono">{formatDate(day.date)}</td>
                  <td>{day.name}</td>
                  <td>{day.origin === "admin" ? "Added by an admin" : "Rule"}</td>
                  <td>{day.is_active ? <Chip tone="neutral">Closed</Chip> : <Chip tone="ok">Open · {day.removal_reason}</Chip>}</td>
                  <td>{day.is_active ? <Button onClick={() => setRemoval({ day, reason: "" })} size="sm">Open this day</Button> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {removal ? (
        <div className="row gap-8 wrap">
          <Field label={`Reason to open ${formatDate(removal.day.date)}`}>
            <input
              aria-label="Reason to open the day"
              onChange={(event) => setRemoval({ ...removal, reason: event.target.value })}
              value={removal.reason}
            />
          </Field>
          <Button
            disabled={!removal.reason.trim() || remove.isPending}
            onClick={() => remove.mutate({ data: { currency, date: removal.day.date, reason: removal.reason } })}
            variant="danger"
          >
            Open the day
          </Button>
        </div>
      ) : null}
      <form
        className="row gap-8 wrap"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          add.mutate({ data: { currency, date: newDate, name: newName } });
        }}
      >
        <Field label="Closed day">
          <input aria-label="Closed day" onChange={(event) => setNewDate(event.target.value)} required type="date" value={newDate} />
        </Field>
        <Field label="Name">
          <input aria-label="Name of the closed day" onChange={(event) => setNewName(event.target.value)} required value={newName} />
        </Field>
        <Button disabled={add.isPending} type="submit">
          Close this day
        </Button>
      </form>
      <div className="row gap-8 wrap">
        <Field label="Confirmation note">
          <input aria-label="Confirmation note" onChange={(event) => setNote(event.target.value)} value={note} />
        </Field>
        <Button disabled={confirm.isPending} onClick={() => confirm.mutate({ data: { currency, year, note: note || undefined } })} variant="primary">
          Confirm {currency} {year}
        </Button>
      </div>
      {result ? <Banner tone="ok" title="Settlement calendar">{result}</Banner> : null}
    </Card>
  );
}
