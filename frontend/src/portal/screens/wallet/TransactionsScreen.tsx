// IP of Webby-Soft SRL.
/*
 * Transactions (design #/transactions: main.tr-page.r30-transactions): search, period (preset or
 * from/to), type and currency filters, rows with amount and status, a detail dialog, the Summary of
 * the rows in view and a CSV export built in the browser from the loaded list. Data: GET
 * /investor/portal/activity/ (the latest 250 movements, the API maximum). The design's "Available
 * balance" column is left out: the API gives no balance after each movement (TODO).
 * U33-DEC-02: repayments and recoveries are credited to the Banxum balance.
 */
import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";

import { useT } from "../../../i18n";
import { useActivityData, usePortfolioData, usePrimaryOrdersData } from "../../../investorPortal/data";
import { formatDate, formatDateTime, formatMoneyLabel, formatMoneyMinor, useNumberFormat } from "../../../investorPortal/format";
import { platformTodayKey } from "../../../investorPortal/platformClock";
import { Dialog, EmptyState, NiIcon, PageHead, PortalLink } from "../../components";
import { downloadTextFile } from "./parts/downloads";
import { rich } from "./parts/rich";
import {
  inRange,
  metadataNumber,
  metadataText,
  periodRange,
  summarize,
  transactionRow,
  transactionsCsv,
  TRANSACTION_GROUPS,
  type Period,
  type TransactionGroup,
  type TransactionRow
} from "./transactionsModel";
import "./wallet.css";
import { clickOnSpace } from "../../components/keyboard";

/** The API's maximum page of activity entries. */
const ACTIVITY_LIMIT = 250;
const PAGE_SIZE = 15;

type PeriodChoice = "all" | "30" | "90" | "custom" | `y${number}`;

function choiceToPeriod(choice: PeriodChoice, custom: { from: string; to: string }): Period {
  if (choice === "30" || choice === "90") return { kind: "days", days: Number(choice) };
  if (choice === "custom") return custom.from && custom.to ? { kind: "custom", ...custom } : { kind: "all" };
  if (choice.startsWith("y")) return { kind: "year", year: Number(choice.slice(1)) };
  return { kind: "all" };
}

function AmountCell({ row }: { row: TransactionRow }) {
  const currency = row.entry.currency;
  if (!row.amountMinor || !currency) return <span className="bxm-muted">–</span>;
  const label = formatMoneyLabel(currency, row.amountMinor);
  if (row.sign === "in") return <span className="bxm-amount-in">+ {label}</span>;
  if (row.sign === "out") return <span>− {label}</span>;
  return <span className="bxm-muted">{label}</span>;
}

function TransactionDetail({ row, onClose }: { row: TransactionRow; onClose: () => void }) {
  const t = useT();
  const entry = row.entry;
  const currency = entry.currency;
  const holdings = usePortfolioData(true).data?.holdings;
  const orders = usePrimaryOrdersData().data?.orders;
  const orderId = metadataText(entry, "order_id") || (entry.activity_type === "primary_order" ? entry.id : "");
  const investmentId = row.group === "reservation"
    ? orders?.find((order) => order.id === orderId)?.id ?? ""
    : entry.loan_id ? holdings?.find((holding) => holding.loan.loan_id === entry.loan_id)?.id ?? "" : "";
  const money = (minor: number | null) => (minor === null || !currency ? null : formatMoneyLabel(currency, minor));
  const principal = metadataNumber(entry, "principal_minor");
  const interest = metadataNumber(entry, "interest_minor") ?? metadataNumber(entry, "contractual_interest_minor");
  const fee = metadataNumber(entry, "fee_minor");
  const iban = metadataText(entry, "destination_iban");
  const description = t(row.description.text, row.description.vars);
  const items: Array<[string, string | null]> = [
    [t("Date"), formatDateTime(entry.occurred_at)],
    [t("Amount"), row.amountMinor ? money(row.amountMinor) : null],
    [t("Principal"), principal !== null && (row.group === "repayment" || row.group === "recovery") ? money(principal) : null],
    [t("Interest"), interest !== null && (row.group === "repayment" || row.group === "recovery") ? money(interest) : null],
    [t("Fee"), fee ? money(fee) : null],
    [t("To"), iban || null],
    [t("Status"), t(row.status)],
    [t("Reference"), entry.id]
  ];
  const note =
    row.group === "reservation" && row.pending
      ? t("This amount is reserved from your available balance.")
      : row.group === "repayment" || row.group === "recovery"
        ? t("Credited to your Banxum balance. You can invest it again or withdraw it.")
        : (row.group === "withdrawal" || row.group === "return") && entry.status === "requested"
          ? t("The amount is set aside from your balance until the bank transfer is sent.")
          : null;
  return (
    <Dialog onClose={onClose} title={t(row.label)}>
      {description ? <p className="bxm-muted">{description}</p> : null}
      <dl className="bxm-kv wl-kv-single">
        {items.filter(([, value]) => value).map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
        ))}
      </dl>
      {note ? <p className="r75-transaction-note"><NiIcon name="info" /><span>{note}</span></p> : null}
      {investmentId ? (
        // The design's link to the investment (a holding, or the reservation of an open order).
        <PortalLink className="btn btn-outline-light mt-4" onNavigate={onClose} params={{ holdingId: investmentId }} to="investment">{t("Open investment {reference}", { reference: investmentId })}</PortalLink>
      ) : entry.loan_id ? (
        <PortalLink className="btn btn-outline-light mt-4" onNavigate={onClose} params={{ loanId: entry.loan_id }} to="loan">{t("View loan")}</PortalLink>
      ) : null}
    </Dialog>
  );
}

export function TransactionsScreen() {
  const t = useT();
  const { format } = useNumberFormat();
  const activityQuery = useActivityData(ACTIVITY_LIMIT);
  const entries = activityQuery.data?.entries;
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState<TransactionGroup | "">("");
  const [currency, setCurrency] = useState<"" | string>("");
  const [choice, setChoice] = useState<PeriodChoice>("all");
  const [draft, setDraft] = useState({ from: "", to: "" });
  const [custom, setCustom] = useState({ from: "", to: "" });
  const [rangeError, setRangeError] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [shown, setShown] = useState(PAGE_SIZE);
  const [selected, setSelected] = useState<TransactionRow | null>(null);

  // Most recent first (the API's order; kept when entries share a time).
  const rows = useMemo(
    () => (entries ?? []).map(transactionRow).sort((a, b) => b.entry.occurred_at.localeCompare(a.entry.occurred_at)),
    [entries]
  );
  const years = useMemo(() => [...new Set(rows.map((row) => Number(row.dateKey.slice(0, 4))).filter(Boolean))].sort((a, b) => b - a), [rows]);
  const currencies = useMemo(() => [...new Set(rows.map((row) => row.entry.currency).filter(Boolean))].sort((a, b) => (a === "EUR" ? -1 : b === "EUR" ? 1 : a.localeCompare(b))), [rows]);
  const groups = TRANSACTION_GROUPS.filter((item) => rows.some((row) => row.group === item.value));
  const period = choiceToPeriod(choice, custom);
  const range = periodRange(period, platformTodayKey());
  const query = search.trim().toLowerCase();
  const filtered = rows.filter((row) => {
    if (group && row.group !== group) return false;
    if (currency && row.entry.currency !== currency) return false;
    if (!inRange(row.dateKey, range)) return false;
    if (!query) return true;
    const haystack = [t(row.label), t(row.status), t(row.description.text, row.description.vars), row.entry.title, row.entry.id, formatMoneyMinor(row.amountMinor, row.entry.currency || "CHF")]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
  const visible = filtered.slice(0, shown);
  const summary = summarize(filtered);
  const resetPaging = () => setShown(PAGE_SIZE);

  const applyRange = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.from || !draft.to || draft.from > draft.to) {
      setRangeError(true);
      return;
    }
    setRangeError(false);
    setCustom(draft);
    resetPaging();
  };
  const rangeLabel = period.kind === "custom"
    ? t("{from} to {to}", { from: formatDate(period.from), to: formatDate(period.to) })
    : t("All time");
  const exportCsv = () => {
    const csv = transactionsCsv(filtered, format, (text, vars) => t(text, vars), formatDateTime);
    downloadTextFile(csv, `banxum-transactions-${platformTodayKey()}.csv`);
  };
  const openOnKey = (event: KeyboardEvent<HTMLTableRowElement>, row: TransactionRow) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setSelected(row);
    }
  };

  const head = (
    <PageHead
      actions={
        <button className="btn btn-outline-light" disabled={filtered.length === 0} onClick={exportCsv} type="button">
          <NiIcon name="download" /><span>{t("Export CSV")}</span>
        </button>
      }
      // U33-DEC-02: repayments are credited to the Banxum account, not paid to the bank account.
      subtitle={t("Movements on your Banxum account and repayments credited to it.")}
      title={t("Transactions")}
    />
  );

  if (!entries) {
    return (
      <main className="tr-page r30-transactions">
        {head}
        {activityQuery.isError ? (
          <EmptyState
            actions={<button className="btn btn-outline-light" onClick={() => void activityQuery.refetch()} type="button">{t("Try again")}</button>}
            icon="alert-circle"
            title={t("We could not load your transactions")}
          >
            {t("Your account movements are not available right now. Try again in a moment.")}
          </EmptyState>
        ) : (
          <div className="bxm-empty" role="status"><NiIcon name="loader" /><p>{t("Loading transactions...")}</p></div>
        )}
      </main>
    );
  }

  return (
    <main className="tr-page r30-transactions">
      {head}
      <div className="tr-toolbar">
        <div className="tr-search">
          <NiIcon name="search" />
          <input
            aria-label={t("Search transactions")}
            className="form-control"
            id="tr-search"
            onChange={(event) => {
              setSearch(event.target.value);
              resetPaging();
            }}
            placeholder={t("Search transactions")}
            type="search"
            value={search}
          />
        </div>
        <div className="r30-period-control">
          <label htmlFor="tr-period">{t("Period")}</label>
          <select
            className="form-select tr-period"
            id="tr-period"
            onChange={(event) => {
              setChoice(event.target.value as PeriodChoice);
              setRangeError(false);
              resetPaging();
            }}
            value={choice}
          >
            <option value="all">{t("All time")}</option>
            <option value="30">{t("Last 30 days")}</option>
            <option value="90">{t("Last 90 days")}</option>
            {years.map((year) => <option key={year} value={`y${year}`}>{year}</option>)}
            <option value="custom">{t("Custom dates")}</option>
          </select>
        </div>
        <select
          aria-label={t("Transaction type")}
          className="form-select tr-type"
          onChange={(event) => {
            setGroup(event.target.value as TransactionGroup | "");
            resetPaging();
          }}
          value={group}
        >
          <option value="">{t("All types")}</option>
          {groups.map((item) => <option key={item.value} value={item.value}>{t(item.label)}</option>)}
        </select>
        <div aria-label={t("Currency")} className="bxm-seg" role="group">
          {["", ...currencies].map((value) => (
            <a
              aria-pressed={currency === value}
              className={currency === value ? "active" : ""}
              href="#"
              key={value || "all"}
              onClick={(event) => {
                event.preventDefault();
                setCurrency(value);
                resetPaging();
              }}
              onKeyDown={clickOnSpace}
              role="button"
            >
              {value || t("All")}
            </a>
          ))}
        </div>
      </div>
      {choice === "custom" ? (
        <form className="r30-date-range" noValidate onSubmit={applyRange}>
          <div className="r30-date-field">
            <label htmlFor="tr-from">{t("From")}</label>
            <input aria-describedby="tr-date-error" aria-invalid={rangeError} className="form-control" id="tr-from" onChange={(event) => setDraft({ ...draft, from: event.target.value })} required type="date" value={draft.from} />
          </div>
          <div className="r30-date-field">
            <label htmlFor="tr-to">{t("date|To")}</label>
            <input aria-describedby="tr-date-error" aria-invalid={rangeError} className="form-control" id="tr-to" onChange={(event) => setDraft({ ...draft, to: event.target.value })} required type="date" value={draft.to} />
          </div>
          <button className="btn btn-outline-light" type="submit">{t("Apply")}</button>
          <span className="r30-range-label">{t("Current view: {range}", { range: rangeLabel })}</span>
          <p className="r30-range-error" hidden={!rangeError} id="tr-date-error" role="alert">{t("Choose a start and end date. From must be on or before To.")}</p>
        </form>
      ) : null}
      <div className="tr-meta">
        <span>{rich(t("{count} · Most recent first"), { count: <strong>{filtered.length === 1 ? t("1 transaction") : t("{count} transactions", { count: filtered.length })}</strong> })}</span>
        <button aria-controls="tr-totals" aria-expanded={summaryOpen} className="tr-link" onClick={() => setSummaryOpen((open) => !open)} type="button">
          {t("Summary")} <NiIcon name="chevron-down" />
        </button>
      </div>
      <div className="tr-summary" hidden={!summaryOpen} id="tr-totals">
        <div className="tr-summary-grid">
          {summary.length === 0 ? <p className="wl-summary-empty">{t("No movements in this view.")}</p> : null}
          {summary.map((item) => (
            <section key={item.currency}>
              <h3>{item.currency} <span>{t("in this view")}</span></h3>
              <dl>
                <div><dt>{t("Deposited")}</dt><dd>{formatMoneyMinor(item.deposited, item.currency)}</dd></div>
                <div><dt>{t("Invested")}</dt><dd>{formatMoneyMinor(item.invested, item.currency)}</dd></div>
                <div><dt>{t("Repaid to Banxum account")}</dt><dd>{formatMoneyMinor(item.credited, item.currency)}</dd></div>
                <div><dt>{t("Withdrawn")}</dt><dd>{formatMoneyMinor(item.withdrawn, item.currency)}</dd></div>
              </dl>
            </section>
          ))}
        </div>
      </div>
      {filtered.length === 0 ? (
        <div className="bxm-empty">
          <NiIcon name="tranx" />
          <p>{rows.length === 0 ? t("No transactions yet. Deposits, investments and repayments will appear here.") : t("No transactions for these filters.")}</p>
        </div>
      ) : (
        <table className="tr-table r30-transactions-table r31m-transactions-table mobile-records m82-compact-records" data-mobile-table="true">
          <colgroup><col style={{ width: "58%" }} /><col style={{ width: "18%" }} /><col style={{ width: "20%" }} /><col style={{ width: "4%" }} /></colgroup>
          <thead>
            <tr><th>{t("Transaction")}</th><th>{t("Date")}</th><th className="tr-right">{t("Amount")}</th><th><span className="visually-hidden">{t("Details")}</span></th></tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const description = t(row.description.text, row.description.vars);
              return (
                <tr
                  aria-label={[t(row.label), description, formatDate(row.entry.occurred_at)].filter(Boolean).join(" · ")}
                  data-action="tx"
                  key={row.entry.id}
                  onClick={() => setSelected(row)}
                  onKeyDown={(event) => openOnKey(event, row)}
                  role="button"
                  tabIndex={0}
                >
                  <td data-mobile-label={t("Transaction")}>
                    <div className="tr-item">
                      <span className="tr-icon"><NiIcon name={row.icon} /></span>
                      <div>
                        <strong>{t(row.label)}</strong>
                        <span className={`tr-status r31m-status ${row.pending ? "tr-reserved" : ""}`.trim()}>{row.pending ? <i /> : null}{t(row.status)}</span>
                        {description ? <small>{description}</small> : null}
                        {/* Activity kept from before a QA environment reset stays visible and is marked. */}
                        {row.entry.archived_at ? <small className="wl-qa-note">{t("Before QA reset")}</small> : null}
                      </div>
                    </div>
                  </td>
                  <td className="tr-date" data-mobile-label={t("Date")}>{formatDate(row.entry.occurred_at)}</td>
                  <td className="tr-right tr-amount" data-mobile-label={t("Amount")}><AmountCell row={row} /></td>
                  <td className="tr-arrow" data-mobile-label={t("Details")}><NiIcon name="chevron-right" /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {filtered.length > 0 ? (
        <div className="tr-table-footer">
          <span>{t("Showing {shown} of {total}", { shown: visible.length, total: filtered.length })}</span>
          {visible.length < filtered.length ? (
            <button className="btn btn-outline-light btn-sm" onClick={() => setShown((count) => count + PAGE_SIZE)} type="button">
              {t("Show more")} <NiIcon name="chevron-down" />
            </button>
          ) : null}
        </div>
      ) : null}
      {entries.length >= ACTIVITY_LIMIT ? (
        <p className="wl-list-note">{t("This list shows your latest {count} movements. Older movements are in your account statements under Reports.", { count: ACTIVITY_LIMIT })}</p>
      ) : null}
      {selected ? <TransactionDetail onClose={() => setSelected(null)} row={selected} /> : null}
    </main>
  );
}
