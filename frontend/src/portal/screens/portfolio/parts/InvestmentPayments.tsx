// IP of Webby-Soft SRL.
// "Payments" of the investment page (design .r71-payments.r84-payments): interest to be received, the
// next payment and the "All payments" schedule. The API gives the investor's share of every remaining
// payment; payments already received are known as totals (principal and interest received), so they are
// one "Received to date" row, not reconstructed per payment in the browser.
import { useId, useState } from "react";

import type { Holding } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { formatDate, formatMoneyMinor, useNumberFormat } from "../../../../investorPortal/format";
import { NiIcon } from "../../../components";
import {
  hasProjection,
  holdingState,
  installmentCounts,
  interestReceivedMinor,
  isOverdueRow,
  nextPayment,
  principalAfterRows,
  principalReturnedMinor,
  projectedInterestMinor
} from "./investmentModel";
import { cadenceText } from "./labels";

export function InvestmentPayments({ holding }: { holding: Holding }) {
  const t = useT();
  useNumberFormat();
  const scheduleId = useId();
  const titleId = useId();
  const state = holdingState(holding);
  const currency = holding.currency;
  const money = (amount: number) => `${currency} ${formatMoneyMinor(amount, currency)}`;
  const projectable = hasProjection(holding);
  const [open, setOpen] = useState(false);
  const next = nextPayment(holding);
  const future = projectedInterestMinor(holding);
  const rows = principalAfterRows(holding);
  const counts = installmentCounts(holding);
  const receivedInterest = interestReceivedMinor(holding);
  const receivedPrincipal = principalReturnedMinor(holding);
  const hasReceived = receivedInterest + receivedPrincipal > 0;
  const cadence = cadenceText(holding.loan.repayment_type);
  const emptyText = state === "repaid" || state === "sold"
    ? state === "sold" ? t("No more payments. You sold this investment.") : t("All payments have been received.")
    : state === "default" || state === "writtenOff"
      ? t("No scheduled payments. This loan is in default.")
      : rows.length === 0 ? t("No scheduled payments.") : "";

  const table = (
    <div className="r50-schedule-body">
      {cadence ? <p className="r71-cadence">{cadence}</p> : null}
      <div className="ps-heading">
        <div>
          <h3 className="h6" id={titleId}>{t("Payment schedule")}</h3>
          <p>{t("All amounts relate to your investment · {currency}.", { currency })}</p>
        </div>
        {counts.total > 0 ? (
          <span className="rid-payment-count">{t("{received} of {total} payments received · {currency}", { received: counts.received, total: counts.total, currency })}</span>
        ) : null}
      </div>
      {state === "default" || state === "writtenOff" ? (
        <p className="ps-notice">{t("This loan is in default. The original payment dates no longer apply; see the recovery updates above.")}</p>
      ) : null}
      <div aria-label={t("All payments for this investment, {currency}", { currency })} className="ps-content" role="region" tabIndex={0}>
        <table className="ps-table m82-owned-schedule" data-mobile-table="true">
          <caption className="visually-hidden">{t("All payments for your investment, {currency}.", { currency })}</caption>
          <thead>
            <tr>
              <th scope="col">{t("Due date")}</th>
              <th scope="col">{t("Principal")}</th>
              <th scope="col">{t("Interest")}</th>
              <th scope="col">{t("Total")}</th>
              <th scope="col">{t("Status")}</th>
              <th scope="col"><span className="visually-hidden">{t("Payment details")}</span></th>
            </tr>
          </thead>
          <tbody>
            {hasReceived ? (
              <tr data-payment-status="paid">
                <td>
                  {t("Received to date")}
                  {counts.received > 0 ? <small>{counts.received === 1 ? t("1 payment") : t("{count} payments", { count: counts.received })}</small> : null}
                </td>
                <td data-m82-label={t("Principal")}>{formatMoneyMinor(receivedPrincipal, currency)}</td>
                <td data-m82-label={t("Interest")}>{formatMoneyMinor(receivedInterest, currency)}</td>
                <td data-m82-label={t("Total")}><strong>{formatMoneyMinor(receivedPrincipal + receivedInterest, currency)}</strong></td>
                <td><span className="ps-paid"><NiIcon name="check" />{t("Paid")}</span></td>
                <td />
              </tr>
            ) : null}
            {projectable
              ? rows.map(({ row, principalAfterMinor }) => {
                  const overdue = isOverdueRow(row);
                  const isNext = next?.loan_installment_id === row.loan_installment_id;
                  return (
                    <tr className={isNext ? "ps-next" : ""} data-payment-number={row.installment_number} data-payment-status={overdue ? "late" : "scheduled"} key={row.loan_installment_id}>
                      <td>
                        {formatDate(row.due_date)}
                        {isNext ? <small>{t("Next payment")}</small> : null}
                      </td>
                      <td data-m82-label={t("Principal")}>{formatMoneyMinor(row.projected_principal_minor, currency)}</td>
                      <td data-m82-label={t("Interest")}>{formatMoneyMinor(row.projected_interest_minor, currency)}</td>
                      <td data-m82-label={t("Total")}><strong>{formatMoneyMinor(row.projected_total_minor, currency)}</strong></td>
                      <td>
                        {overdue ? (
                          <span className="ps-overdue">{row.days_past_due === 1 ? t("Overdue · 1 day") : t("Overdue · {days} days", { days: row.days_past_due })}</span>
                        ) : row.status === "due" ? (
                          <span className="ps-scheduled">{t("Due")}</span>
                        ) : (
                          <span className="ps-scheduled">{t("Scheduled")}</span>
                        )}
                      </td>
                      <td>
                        <details className="ps-details">
                          <summary aria-label={t("Payment details for {date}", { date: formatDate(row.due_date) })}>
                            <NiIcon name="chevron-down" />
                          </summary>
                          <div>
                            <span>{t("Outstanding principal after this payment")}</span>
                            <strong>{money(principalAfterMinor)}</strong>
                          </div>
                        </details>
                      </td>
                    </tr>
                  );
                })
              : null}
          </tbody>
        </table>
      </div>
      {rows.length > 6 && projectable ? <p className="p73-schedule-foot">{t("Scroll to see all {count} payments", { count: rows.length + (hasReceived ? 1 : 0) })}</p> : null}
    </div>
  );

  if (!projectable) {
    return (
      <section className="r71-payments p73-payments">
        <h2>{t("Payments")}</h2>
        <section aria-labelledby={titleId} className="nk-block bxm-payment-schedule rid-schedule">
          <div className="card card-bordered">
            {emptyText ? <p className="ps-empty">{emptyText}</p> : null}
            {hasReceived || counts.total > 0 ? (
              <details className="ps-full r50-motion-schedule" onToggle={(event) => setOpen(event.currentTarget.open)} open={open}>
                <summary aria-expanded={open}>
                  <span className="ps-show-label">{t("View payment schedule")}</span>
                  <span className="ps-hide-label">{t("Hide payment schedule")}</span>
                  <NiIcon name="chevron-down" />
                </summary>
                {table}
              </details>
            ) : null}
          </div>
        </section>
      </section>
    );
  }

  return (
    <section className="r71-payments p73-payments r84-payments" data-r84="true">
      <header className="r84-payments-head">
        <h2>{t("Payments")}</h2>
        <button aria-controls={scheduleId} aria-expanded={open} className="r84-schedule-link" onClick={() => setOpen((value) => !value)} type="button">
          {open ? t("Hide payment schedule") : t("View payment schedule")}
          <NiIcon name={open ? "chevron-up" : "chevron-down"} />
        </button>
      </header>
      <div className="r84-payment-summary">
        <div className="r84-future">
          <span className="r84-label">{t("Interest to be received")}</span>
          <div className="r84-amount"><small>{currency}</small><strong>{formatMoneyMinor(future ?? 0, currency)}</strong></div>
          <span className="r84-projected">{t("Projected")}</span>
        </div>
        <div className="r84-next">
          <span className="r84-label">{t("Next payment")}</span>
          {next ? (
            <>
              <strong className="r84-date">{formatDate(next.due_date)}</strong>
              <span className="r84-next-amount">{money(next.projected_total_minor)}</span>
            </>
          ) : (
            <strong className="r84-date">{t("No scheduled payment")}</strong>
          )}
        </div>
      </div>
      {emptyText ? <p className="ps-empty">{emptyText}</p> : null}
      <section aria-labelledby={titleId} className="nk-block bxm-payment-schedule rid-schedule">
        <div className="card card-bordered">
          <details className="ps-full r50-motion-schedule" id={scheduleId} onToggle={(event) => setOpen(event.currentTarget.open)} open={open}>
            <summary aria-expanded={open} className="r84-native-summary">
              <span className="r71-schedule-action">
                <span className="ps-show-label">{t("View payment schedule")}</span>
                <span className="ps-hide-label">{t("Hide payment schedule")}</span>
                <NiIcon name="chevron-down" />
              </span>
            </summary>
            {table}
          </details>
        </div>
      </section>
    </section>
  );
}
