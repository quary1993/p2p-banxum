// IP of Webby-Soft SRL.
// "Portfolio insights" of My investments (design section.mi40-insights.pi42, closed by default):
// scheduled principal and interest of the next 12 months by month, and the principal-weighted average
// interest rate. Both from the investor's projected schedule and rates in the API; one currency at a time.
import { useId, useState } from "react";

import type { Holding } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { formatDate, formatDecimal, formatMoneyMinor, formatPercent, monthLabelFromKey, useNumberFormat } from "../../../investorPortal/format";
import { platformTodayKey } from "../../../investorPortal/platformClock";
import { NiIcon } from "../../components";
import { hasProjection, investorRateBps, isOverdueRow, projectedRows, sortedCurrencies } from "./parts/investmentModel";

const CHART_WIDTH = 760;
const CHART_HEIGHT = 270;
const PLOT_LEFT = 47;
const PLOT_RIGHT = 752;
const PLOT_TOP = 25;
const PLOT_BOTTOM = 230;

function addMonths(dateKey: string, months: number) {
  const [year, month, day] = dateKey.split("-").map(Number);
  const target = new Date(Date.UTC(year, month - 1 + months, 1));
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  return `${target.getUTCFullYear()}-${String(target.getUTCMonth() + 1).padStart(2, "0")}-${String(Math.min(day, lastDay)).padStart(2, "0")}`;
}

function addDays(dateKey: string, days: number) {
  const date = new Date(`${dateKey}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** A rounded axis step for the largest bar (minor units). */
function niceStep(maxMinor: number) {
  const target = Math.max(1, maxMinor / 3);
  const power = 10 ** Math.floor(Math.log10(target));
  const factor = [1, 2, 2.5, 5, 10].find((candidate) => candidate * power >= target) ?? 10;
  return factor * power;
}

export function PortfolioInsights({ holdings, asOf }: { holdings: Holding[]; asOf?: string }) {
  const t = useT();
  useNumberFormat();
  const chartsId = useId();
  const periodId = useId();
  const rateId = useId();
  const [open, setOpen] = useState(false);
  const [periodInfo, setPeriodInfo] = useState(false);
  const [rateInfo, setRateInfo] = useState(false);
  const projectable = holdings.filter(hasProjection);
  const currencies = sortedCurrencies(projectable.map((holding) => holding.currency));
  const [chosen, setChosen] = useState<string | null>(null);
  const currency = chosen && currencies.includes(chosen) ? chosen : currencies[0];
  if (!currency) return null;
  const scoped = projectable.filter((holding) => holding.currency === currency);

  const today = platformTodayKey(asOf);
  const end = addMonths(today, 12);
  const monthKeys = Array.from({ length: 13 }, (_, index) => addMonths(`${today.slice(0, 7)}-01`, index).slice(0, 7));
  const buckets = new Map(monthKeys.map((key) => [key, { principal: 0, interest: 0 }]));
  let principalTotal = 0;
  let interestTotal = 0;
  for (const holding of scoped) {
    for (const row of projectedRows(holding)) {
      if (isOverdueRow(row) || row.due_date <= today || row.due_date > end) continue;
      const bucket = buckets.get(row.due_date.slice(0, 7));
      if (!bucket) continue;
      bucket.principal += row.projected_principal_minor;
      bucket.interest += row.projected_interest_minor;
      principalTotal += row.projected_principal_minor;
      interestTotal += row.projected_interest_minor;
    }
  }
  const outstanding = scoped.reduce((sum, holding) => sum + holding.current_principal_minor, 0);
  const maxBar = Math.max(1, ...Array.from(buckets.values()).map((bucket) => bucket.principal + bucket.interest));
  const step = niceStep(maxBar);
  const axisMax = Math.max(step, Math.ceil(maxBar / step) * step);
  const ticks = Array.from({ length: Math.round(axisMax / step) + 1 }, (_, index) => index * step);
  const y = (minor: number) => PLOT_BOTTOM - (minor / axisMax) * (PLOT_BOTTOM - PLOT_TOP);
  const slot = (PLOT_RIGHT - PLOT_LEFT) / monthKeys.length;
  const tickLabel = (minor: number) => {
    const units = minor / 100;
    return units >= 1000 ? `${formatDecimal(units / 1000, units % 1000 === 0 ? 0 : 1)}k` : formatDecimal(units, 0);
  };
  const labelThreshold = maxBar * 0.25;

  const rated = scoped.filter((holding) => holding.current_principal_minor > 0);
  const weightedBps = outstanding > 0 ? rated.reduce((sum, holding) => sum + investorRateBps(holding.loan) * holding.current_principal_minor, 0) / outstanding : null;
  const rates = rated.map((holding) => investorRateBps(holding.loan));

  return (
    <section className="mi40-insights pi42">
      <div className="mi40-section-head">
        <button aria-controls={chartsId} aria-expanded={open} className="mi40-insights-toggle" onClick={() => setOpen((value) => !value)} type="button">
          <span>
            <strong>{t("Portfolio insights")}</strong>
            <small>{t("Your scheduled payments and interest rates")}</small>
          </span>
          <NiIcon name="chevron-down" />
        </button>
        {currencies.length > 1 ? (
          <div aria-label={t("Portfolio insights currency")} className="mi40-insight-currency" hidden={!open} role="group">
            {currencies.map((code) => (
              <button aria-pressed={code === currency} className={code === currency ? "active" : undefined} key={code} onClick={() => setChosen(code)} type="button">{code}</button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="mi40-charts" hidden={!open} id={chartsId}>
        {open ? (
          <div className="pi42-grid">
            <section className="pi42-payments">
              <div className="pi42-panel-title">
                <div>
                  <h3>{t("Scheduled payments")}</h3>
                  <p>{t("Next 12 months")}</p>
                </div>
                <button aria-controls={periodId} aria-expanded={periodInfo} aria-label={t("About the scheduled payment period")} className="pi42-info pi42-period-info" onClick={() => setPeriodInfo((value) => !value)} type="button">
                  <NiIcon name="info" />
                </button>
              </div>
              <p className="pi42-period-explanation" hidden={!periodInfo} id={periodId}>
                {t("{from} – {to}. Scheduled payments for existing active and late investments. Overdue payments, funding reservations and recoveries are not included.", { from: formatDate(addDays(today, 1)), to: formatDate(end) })}
              </p>
              <div className="pi42-figures">
                <div>
                  <span>{t("Scheduled interest")}</span>
                  <strong className="pi42-interest"><small>{currency}</small> {formatMoneyMinor(interestTotal, currency)}</strong>
                </div>
                <div>
                  <span>{t("Scheduled principal repayments")}</span>
                  <strong><small>{currency}</small> {formatMoneyMinor(principalTotal, currency)}</strong>
                </div>
              </div>
              {outstanding > 0 ? (
                <div className="pi42-capital-note">
                  <strong>{formatPercent((principalTotal / outstanding) * 100, 1)}</strong> {t("of your outstanding principal scheduled for repayment")}
                </div>
              ) : null}
              <div className="pi42-legend">
                <span><i />{t("Principal")}</span>
                <span><i />{t("Interest")}</span>
                <small>{currency}</small>
              </div>
              <div className="pi42-chart">
                <svg aria-label={t("Scheduled principal and interest by month, {currency}", { currency })} role="img" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}>
                  {ticks.map((tick) => (
                    <g key={tick}>
                      <line stroke="#e2e5e8" strokeWidth="1" x1={PLOT_LEFT} x2={PLOT_RIGHT} y1={y(tick)} y2={y(tick)} />
                      <text fill="#87909a" fontSize="11" textAnchor="end" x={PLOT_LEFT - 12} y={y(tick) + 4}>{tickLabel(tick)}</text>
                    </g>
                  ))}
                  {monthKeys.map((key, index) => {
                    const bucket = buckets.get(key) ?? { principal: 0, interest: 0 };
                    const x = PLOT_LEFT + slot * index + (slot - 24) / 2;
                    const principalTop = y(bucket.principal);
                    const interestTop = y(bucket.principal + bucket.interest);
                    const total = bucket.principal + bucket.interest;
                    const [year] = key.split("-");
                    const showYear = index === 0 || key.endsWith("-01") || index === monthKeys.length - 1;
                    return (
                      <g key={key}>
                        <title>{t("{month}: Principal {principal}; interest {interest}", { month: monthLabelFromKey(key, { month: "long", year: "numeric" }), principal: `${currency} ${formatMoneyMinor(bucket.principal, currency)}`, interest: `${currency} ${formatMoneyMinor(bucket.interest, currency)}` })}</title>
                        <rect fill="#b4bbc3" height={PLOT_BOTTOM - principalTop} rx="2" width="24" x={x} y={principalTop} />
                        <rect fill="#1c7946" height={principalTop - interestTop} rx="1" width="24" x={x} y={interestTop} />
                        {total > labelThreshold ? (
                          <text fill="#525b64" fontSize="11" fontWeight="500" textAnchor="middle" x={x + 12} y={interestTop - 9}>{formatMoneyMinor(total, currency)}</text>
                        ) : null}
                        <text fill="#747b84" fontSize="11" textAnchor="middle" x={x + 12} y="251">{monthLabelFromKey(key, { month: "short" })}</text>
                        {showYear ? <text fill="#9aa0a7" fontSize="10" textAnchor="middle" x={x + 12} y="267">{year}</text> : null}
                      </g>
                    );
                  })}
                </svg>
              </div>
            </section>
            <section className="pi42-rates">
              <div className="pi42-panel-title">
                <div>
                  <h3>{t("Portfolio interest")}</h3>
                  <p>{rated.length === 1 ? t("{currency} · 1 investment in repayment", { currency }) : t("{currency} · {count} investments in repayment", { currency, count: rated.length })}</p>
                </div>
                <button aria-controls={rateId} aria-expanded={rateInfo} aria-label={t("How the average interest rate is calculated")} className="pi42-info pi42-rate-info" onClick={() => setRateInfo((value) => !value)} type="button">
                  <NiIcon name="info" />
                </button>
              </div>
              {weightedBps !== null ? (
                <>
                  <div className="pi42-rate-main">
                    <span>{t("Average annual interest rate")}</span>
                    <strong>{formatDecimal(weightedBps / 100, 2)} <small>%</small></strong>
                  </div>
                  <div className="pi42-rate-range">
                    <div><span>{t("Lowest rate")}</span><strong>{formatDecimal(Math.min(...rates) / 100, 1)} <small>%</small></strong></div>
                    <div><span>{t("Highest rate")}</span><strong>{formatDecimal(Math.max(...rates) / 100, 1)} <small>%</small></strong></div>
                  </div>
                </>
              ) : null}
              <p className="pi42-rate-note">{t("Weighted by outstanding principal.")}</p>
              <p className="pi42-rate-explanation" hidden={!rateInfo} id={rateId}>
                {t("Loans with more outstanding principal have more weight in this average. Includes loans on schedule or with late payments; excludes reservations and loans in recovery. This is not your realised return.")}
              </p>
            </section>
          </div>
        ) : null}
      </div>
    </section>
  );
}
