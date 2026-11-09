// IP of Webby-Soft SRL.
// Payment schedule of the whole portfolio (design #/investments?view=payments): the remaining payments of
// the current investments by month, overdue payments first, as a table or a calendar. Amounts are the
// investor's projected share from the API; EUR and CHF stay separate. Overdue payments are not part of
// "Interest to be received".
import { useState, type ReactNode } from "react";

import type { Holding } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { formatDate, formatMoneyMinor, monthLabelFromKey, useNumberFormat } from "../../../investorPortal/format";
import { platformTodayKey } from "../../../investorPortal/platformClock";
import { EmptyState, NiIcon, PortalLink } from "../../components";
import { addTo, nextPayment, portfolioPayments, projectedInterestMinor, sortedCurrencies, totalsList, type PortfolioPayment } from "./parts/investmentModel";
import { BackLink } from "./parts/ui";
import { useMoneyText } from "./parts/money";

/** "30 Sep" from a business date key, independent of the browser time zone. */
function dayMonth(dateKey: string) {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

function Money({ currency, amountMinor }: { currency: string; amountMinor: number }) {
  return (
    <span className="ps93-money">
      <small>{currency}</small>
      <span>{formatMoneyMinor(amountMinor, currency)}</span>
    </span>
  );
}

type Group = { key: string; late: boolean; label: string; payments: PortfolioPayment[] };

function groupPayments(payments: PortfolioPayment[]): Group[] {
  const groups: Group[] = [];
  const late = payments.filter((payment) => payment.overdue);
  if (late.length > 0) groups.push({ key: "late", late: true, label: "", payments: late });
  for (const payment of payments.filter((item) => !item.overdue)) {
    const key = payment.row.due_date.slice(0, 7);
    const group = groups.find((item) => item.key === key);
    if (group) group.payments.push(payment);
    else groups.push({ key, late: false, label: monthLabelFromKey(key, { month: "long", year: "numeric" }), payments: [payment] });
  }
  return groups;
}

export function PortfolioSchedule({ holdings, currency, currencySwitch, asOf, onBack }: { holdings: Holding[]; currency: string | null; currencySwitch: ReactNode; asOf?: string; onBack: () => void }) {
  const t = useT();
  useNumberFormat();
  const [mode, setMode] = useState<"schedule" | "calendar">("schedule");
  const scoped = holdings.filter((holding) => currency === null || holding.currency === currency);
  const payments = portfolioPayments(scoped);
  const projected = new Map<string, number>();
  for (const code of sortedCurrencies(scoped.map((holding) => holding.currency))) projected.set(code, 0);
  for (const holding of scoped) addTo(projected, holding.currency, projectedInterestMinor(holding) ?? 0);
  const nextKeys = new Set(
    scoped
      .map((holding) => {
        const row = nextPayment(holding);
        return row ? `${holding.id}:${row.loan_installment_id}` : "";
      })
      .filter(Boolean)
  );
  const earliestNext = payments.find((payment) => !payment.overdue && nextKeys.has(payment.key))?.row.due_date;
  return (
    <main aria-label={t("My investments")} className="bxm-my-investments r75c-portfolio r75c-calendar ps93-page" data-ps93-mode={mode}>
      <BackLink onClick={onBack}>{t("My investments")}</BackLink>
      <header className="r75c-head">
        <div>
          <h1>{t("Payment schedule")}</h1>
        </div>
        <div className="ps93-projection">
          <span className="ps93-projection-label">
            {t("Interest to be received")} <span className="ps93-projected">· {t("Projected")}</span>
          </span>
          <div className="ps93-projection-values">
            {totalsList(projected).map(([code, amount]) => <Money amountMinor={amount} currency={code} key={code} />)}
          </div>
        </div>
      </header>
      <section aria-labelledby="portfolio-payments-title" className="bxm-portfolio-payments card card-bordered">
        <div className="bxm-portfolio-payments-heading">
          <div>
            <h2 className="h6" id="portfolio-payments-title">{t("Payment schedule")}</h2>
            <p>{t("Upcoming payments across your portfolio · principal + interest")}</p>
          </div>
          <a
            className="link"
            href={window.location.pathname}
            onClick={(event) => {
              event.preventDefault();
              onBack();
            }}
          >
            {t("Close")} <span aria-hidden="true">×</span>
          </a>
        </div>
        <div className="bxm-portfolio-payments-content">
          <div className="ps93-toolbar">
            <div aria-label={t("Payment schedule view")} className="btn-group bxm-payment-modes mb-4" role="group">
              <button aria-controls="bxm-payment-list" aria-pressed={mode === "schedule"} className={`btn btn-sm btn-outline-light${mode === "schedule" ? " active" : ""}`} onClick={() => setMode("schedule")} type="button">{t("Schedule")}</button>
              <button aria-controls="bxm-payment-calendar" aria-pressed={mode === "calendar"} className={`btn btn-sm btn-outline-light${mode === "calendar" ? " active" : ""}`} onClick={() => setMode("calendar")} type="button">{t("Calendar")}</button>
            </div>
            {currencySwitch}
          </div>
          {payments.length === 0 ? (
            <EmptyState icon="calendar" title={t("No scheduled payments")}>
              {t("Payments of your current investments appear here. Loans in default have no scheduled payments.")}
            </EmptyState>
          ) : mode === "schedule" ? (
            <ScheduleTable earliestNext={earliestNext} nextKeys={nextKeys} payments={payments} />
          ) : (
            <PaymentCalendar asOf={asOf} payments={payments} />
          )}
        </div>
      </section>
    </main>
  );
}

function groupTotals(group: Group) {
  const totals = new Map<string, number>();
  for (const payment of group.payments) addTo(totals, payment.holding.currency, payment.row.projected_total_minor);
  return totals;
}

function ScheduleTable({ payments, nextKeys, earliestNext }: { payments: PortfolioPayment[]; nextKeys: Set<string>; earliestNext?: string }) {
  const t = useT();
  const groups = groupPayments(payments);
  const isNext = (payment: PortfolioPayment) => !payment.overdue && nextKeys.has(payment.key) && payment.row.due_date === earliestNext;
  return (
    <div id="bxm-payment-list">
      <div className="ps93-table-frame">
        <table className="ps93-table">
          <caption className="visually-hidden">{t("Upcoming and overdue payments across your investments. EUR and CHF remain separate. Late payments are not included in projected interest remaining.")}</caption>
          <colgroup>
            <col className="ps93-col-date" />
            <col className="ps93-col-investment" />
            <col className="ps93-col-number" />
            <col className="ps93-col-number" />
            <col className="ps93-col-total" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">{t("Due date")}</th>
              <th scope="col">{t("Investment")}</th>
              <th className="ps93-number" scope="col">{t("Principal")}</th>
              <th className="ps93-number ps93-interest" scope="col">{t("Interest")}</th>
              <th className="ps93-number" scope="col">{t("Total")}</th>
            </tr>
          </thead>
          {groups.map((group) => {
            const totals = groupTotals(group);
            const count = group.payments.length;
            return (
              <tbody className={`ps93-month${group.late ? " ps93-late-group" : ""}`} key={group.key}>
                <tr className="ps93-month-heading">
                  <th colSpan={5} scope="rowgroup">
                    <div className="ps93-month-heading-inner">
                      <span className="ps93-month-label">
                        {group.late ? t("Late payments") : group.label}
                        <small>{count === 1 ? t("1 payment") : t("{count} payments", { count })}</small>
                      </span>
                      <span aria-label={group.late ? t("Total overdue") : t("Monthly total")} className="ps93-month-totals">
                        <span className="ps93-month-total-label">{group.late ? t("Overdue") : t("Total payments")}</span>
                        {totalsList(totals).map(([code, amount]) => <Money amountMinor={amount} currency={code} key={code} />)}
                      </span>
                    </div>
                  </th>
                </tr>
                {group.payments.map((payment) => {
                  const { row, holding } = payment;
                  const next = isNext(payment);
                  return (
                    <tr className={`ps93-payment${payment.overdue ? " ps93-payment-late" : ""}${next ? " ps93-payment-next" : ""}`} data-payment-status={payment.overdue ? "late" : "scheduled"} key={payment.key}>
                      <td className="ps93-date">
                        <time dateTime={row.due_date}>{payment.overdue ? formatDate(row.due_date) : dayMonth(row.due_date)}</time>
                        {payment.overdue ? (
                          <small className="ps93-overdue">{row.days_past_due === 1 ? t("1 day overdue") : t("{days} days overdue", { days: row.days_past_due })}</small>
                        ) : next ? (
                          <small className="ps93-next">{t("Next payment")}</small>
                        ) : null}
                      </td>
                      <td className="ps93-investment">
                        <PortalLink params={{ holdingId: holding.id }} to="investment">{holding.loan.loan_title}</PortalLink>
                      </td>
                      <td className="ps93-number"><span className="ps93-amount">{formatMoneyMinor(row.projected_principal_minor, holding.currency)}</span></td>
                      <td className="ps93-number ps93-interest"><span className="ps93-amount">{formatMoneyMinor(row.projected_interest_minor, holding.currency)}</span></td>
                      <td className="ps93-number ps93-total"><Money amountMinor={row.projected_total_minor} currency={holding.currency} /></td>
                    </tr>
                  );
                })}
              </tbody>
            );
          })}
        </table>
      </div>
      {/* The design's mobile edition: payments by month, each opening its principal and interest. */}
      <div className="ps32-groups">
        {groups.map((group) => (
          <section className={`ps32-month${group.late ? " ps32-late" : ""}`} key={group.key}>
            <header>
              <h2>{group.late ? t("Late payments") : group.label}</h2>
              <div className="ps32-month-totals">
                {totalsList(groupTotals(group)).map(([code, amount]) => <Money amountMinor={amount} currency={code} key={code} />)}
              </div>
            </header>
            {group.payments.map((payment) => {
              const { row, holding } = payment;
              return (
                <details className="ps32-payment" key={payment.key}>
                  <summary>
                    <div className="ps32-payment-top">
                      <time dateTime={row.due_date}>{formatDate(row.due_date)}</time>
                      <Money amountMinor={row.projected_total_minor} currency={holding.currency} />
                      <NiIcon name="plus" />
                    </div>
                    <span className="ps32-project">{holding.loan.loan_title}</span>
                    {payment.overdue ? (
                      <small className="ps32-status">{row.days_past_due === 1 ? t("1 day overdue") : t("{days} days overdue", { days: row.days_past_due })}</small>
                    ) : isNext(payment) ? (
                      <small className="ps32-next">{t("Next payment")}</small>
                    ) : null}
                  </summary>
                  <div className="ps32-breakdown">
                    <dl aria-label={t("Payment breakdown")}>
                      <div>
                        <dt>{t("Principal")}</dt>
                        <dd><Money amountMinor={row.projected_principal_minor} currency={holding.currency} /></dd>
                      </div>
                      <div>
                        <dt>{t("Interest")}</dt>
                        <dd className="ps32-interest"><Money amountMinor={row.projected_interest_minor} currency={holding.currency} /></dd>
                      </div>
                    </dl>
                    <PortalLink params={{ holdingId: holding.id }} to="investment">
                      {t("View investment")} <NiIcon name="arrow-right" />
                    </PortalLink>
                  </div>
                </details>
              );
            })}
          </section>
        ))}
      </div>
    </div>
  );
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function monthKeyAdd(key: string, offset: number) {
  const [year, month] = key.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1 + offset, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

function PaymentCalendar({ payments, asOf }: { payments: PortfolioPayment[]; asOf?: string }) {
  const t = useT();
  const money = useMoneyText();
  const today = platformTodayKey(asOf);
  const months = payments.map((payment) => payment.row.due_date.slice(0, 7)).sort();
  const firstMonth = months[0] < today.slice(0, 7) ? months[0] : today.slice(0, 7);
  const lastMonth = months.at(-1) ?? firstMonth;
  const [month, setMonth] = useState(() => (months.includes(today.slice(0, 7)) || payments.some((payment) => payment.overdue) ? today.slice(0, 7) : months.find((key) => key >= today.slice(0, 7)) ?? firstMonth));
  const [selected, setSelected] = useState<string | null>(null);
  const [year, monthNumber] = month.split("-").map(Number);
  const daysInMonth = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
  const leading = (new Date(Date.UTC(year, monthNumber - 1, 1)).getUTCDay() + 6) % 7;
  const byDay = new Map<string, PortfolioPayment[]>();
  for (const payment of payments) {
    if (!payment.row.due_date.startsWith(month)) continue;
    byDay.set(payment.row.due_date, [...(byDay.get(payment.row.due_date) ?? []), payment]);
  }
  const cells: Array<string | null> = [...Array.from({ length: leading }, () => null), ...Array.from({ length: daysInMonth }, (_, index) => `${month}-${String(index + 1).padStart(2, "0")}`)];
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks = Array.from({ length: cells.length / 7 }, (_, index) => cells.slice(index * 7, index * 7 + 7));
  const monthPayments = Array.from(byDay.values()).flat();
  const scheduledTotals = new Map<string, number>();
  const overdueTotals = new Map<string, number>();
  for (const payment of monthPayments) addTo(payment.overdue ? overdueTotals : scheduledTotals, payment.holding.currency, payment.row.projected_total_minor);
  const countLine = [
    monthPayments.some((payment) => !payment.overdue)
      ? t("{count} scheduled · {amounts}", { count: monthPayments.filter((payment) => !payment.overdue).length, amounts: totalsList(scheduledTotals).map(([code, amount]) => money(code, amount)).join(" · ") })
      : "",
    monthPayments.some((payment) => payment.overdue)
      ? t("{count} overdue · {amounts}", { count: monthPayments.filter((payment) => payment.overdue).length, amounts: totalsList(overdueTotals).map(([code, amount]) => money(code, amount)).join(" · ") })
      : ""
  ].filter(Boolean).join(" | ");
  const selectedDay = selected && selected.startsWith(month) ? selected : (Array.from(byDay.keys()).sort()[0] ?? null);
  const selectedPayments = selectedDay ? byDay.get(selectedDay) ?? [] : [];
  return (
    <div className="bxm-payment-calendar" id="bxm-payment-calendar">
      <div className="bxm-calendar-heading">
        <div>
          <h3 aria-live="polite" className="title bxm-calendar-month h6">{monthLabelFromKey(month, { month: "long", year: "numeric" })}</h3>
          <p className="bxm-muted">{t("Amounts are shown in their original currency.")}</p>
        </div>
        <div aria-label={t("Change calendar month")} className="btn-group" role="group">
          <button aria-label={t("Previous month")} className="btn btn-sm btn-outline-light bxm-calendar-prev" disabled={month <= firstMonth} onClick={() => setMonth(monthKeyAdd(month, -1))} type="button"><NiIcon name="chevron-left" /></button>
          <button aria-label={t("Next month")} className="btn btn-sm btn-outline-light bxm-calendar-next" disabled={month >= lastMonth} onClick={() => setMonth(monthKeyAdd(month, 1))} type="button"><NiIcon name="chevron-right" /></button>
        </div>
      </div>
      <p className="bxm-calendar-count bxm-muted">{countLine || t("No payments this month")}</p>
      <div className="bxm-calendar-body">
        <div className="bxm-calendar-grid-wrap">
          <table className="bxm-calendar-grid">
            <caption className="visually-hidden">{t("Payment calendar for {month}", { month: monthLabelFromKey(month, { month: "long", year: "numeric" }) })}</caption>
            <thead><tr>{WEEKDAYS.map((day) => <th key={day} scope="col">{t(day)}</th>)}</tr></thead>
            <tbody>
              {weeks.map((week, index) => (
                <tr key={index}>
                  {week.map((day, dayIndex) => {
                    if (!day) return <td className="bxm-calendar-blank" key={`blank-${dayIndex}`} />;
                    const items = byDay.get(day) ?? [];
                    const late = items.some((item) => item.overdue);
                    const totals = new Map<string, number>();
                    for (const item of items) addTo(totals, item.holding.currency, item.row.projected_total_minor);
                    const amountText = totalsList(totals).map(([code, amount]) => money(code, amount)).join(" · ");
                    const classes = ["bxm-calendar-day", items.length ? "has-payments" : "", late ? "has-late" : "", day === today ? "is-today" : "", day === selectedDay ? "is-selected" : ""].filter(Boolean).join(" ");
                    return (
                      <td key={day}>
                        <button
                          aria-current={day === today ? "date" : undefined}
                          aria-label={t("{date}, {count} payments{details}", { date: formatDate(day), count: items.length, details: items.length ? `, ${amountText}${late ? `, ${t("overdue")}` : ""}` : "" })}
                          aria-pressed={day === selectedDay}
                          className={classes}
                          onClick={() => setSelected(day)}
                          type="button"
                        >
                          <span className="bxm-calendar-day-number">{Number(day.slice(8))}</span>
                          {items.length ? <span className="bxm-calendar-day-amount">{amountText}</span> : null}
                          {items.length ? <span className="bxm-calendar-day-count">{items.length === 1 ? t("1 payment") : t("{count} payments", { count: items.length })}{late ? ` · ${t("overdue")}` : ""}</span> : null}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {selectedDay ? (
          <section aria-labelledby="bxm-calendar-selected-date" aria-live="polite" className="bxm-calendar-detail">
            <div className="bxm-calendar-detail-heading">
              <h4 className="title h6" id="bxm-calendar-selected-date">{formatDate(selectedDay)}</h4>
              <span className="bxm-muted">{selectedPayments.length === 1 ? t("1 payment") : t("{count} payments", { count: selectedPayments.length })}</span>
            </div>
            {selectedPayments.map((payment) => (
              <article className="bxm-calendar-payment" key={payment.key}>
                <h5 className="title h6"><PortalLink params={{ holdingId: payment.holding.id }} to="investment">{payment.holding.loan.loan_title}</PortalLink></h5>
                <p className="bxm-calendar-payment-status bxm-muted">{payment.overdue ? t("Overdue") : t("Scheduled")}</p>
                <dl className="bxm-calendar-amounts">
                  <div><dt>{t("Principal")}</dt><dd>{money(payment.holding.currency, payment.row.projected_principal_minor)}</dd></div>
                  <div><dt>{t("Interest")}</dt><dd>{money(payment.holding.currency, payment.row.projected_interest_minor)}</dd></div>
                  <div className="bxm-calendar-total"><dt>{t("Total payment")}</dt><dd>{money(payment.holding.currency, payment.row.projected_total_minor)}</dd></div>
                </dl>
              </article>
            ))}
          </section>
        ) : null}
      </div>
    </div>
  );
}
