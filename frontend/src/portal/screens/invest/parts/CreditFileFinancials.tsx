// IP of Webby-Soft SRL.
// U33-DEC-20: the credit file's Financials chapter from the structured history (design 35-credit-file
// financials): profit & loss and balance sheet by year in currency thousands, the details under "+"
// when they were recorded, the four key ratios calculated from the same figures (with their formulas),
// the borrower's existing debt at a date and the source statements. Only recorded figures are shown;
// nothing is estimated or projected. Costs are shown as negative amounts, like the statements.
import { useState, type ReactNode } from "react";

import type { MarketplaceDebtFacility, MarketplaceFinancialYear } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { formatDate, formatDecimal, formatMoneyLabel } from "../../../../investorPortal/format";
import { Dialog, NiIcon } from "../../../components";
import { ratio } from "./financialRatio";

type T = ReturnType<typeof useT>;
type Year = MarketplaceFinancialYear;
type Amount = (year: Year) => number | null | undefined;

const thousands = (minor: number | null | undefined) => (typeof minor === "number" ? formatDecimal(minor / 100 / 1000, 0) : "–");

function present(years: Year[], read: Amount) {
  return years.some((year) => typeof read(year) === "number");
}

type RowSpec = { label: string; read: Amount; negative?: boolean };

function Row({ label, years, read, negative = false, group, expanded, onToggle, child, subtotal }: { label: string; years: Year[]; read: Amount; negative?: boolean; group?: string; expanded?: boolean; onToggle?: () => void; child?: boolean; subtotal?: boolean }) {
  return (
    <tr className={[subtotal ? "r100-subtotal" : "", child ? "r100-subrow" : ""].filter(Boolean).join(" ")}>
      <th scope="row">
        {group ? (
          <button aria-expanded={Boolean(expanded)} aria-label={label} className="r100-expand" onClick={onToggle} type="button">{expanded ? "−" : "+"}</button>
        ) : (
          <span className="r100-row-indent" />
        )}
        <span>{label}</span>
      </th>
      {years.map((year) => {
        const value = read(year);
        return <td key={year.id}>{typeof value === "number" ? thousands(negative ? -value : value) : "–"}</td>;
      })}
    </tr>
  );
}

function GroupRows({ label, read, details, years, subtotal = true }: { label: string; read: Amount; details: RowSpec[]; years: Year[]; subtotal?: boolean }) {
  const [open, setOpen] = useState(false);
  const shown = details.filter((detail) => present(years, detail.read));
  return (
    <>
      <Row expanded={open} group={shown.length > 0 ? label : undefined} label={label} onToggle={() => setOpen((value) => !value)} read={read} subtotal={subtotal} years={years} />
      {open ? shown.map((detail) => <Row child key={detail.label} label={detail.label} negative={detail.negative} read={detail.read} years={years} />) : null}
    </>
  );
}

function Table({ years, ratios = false, children }: { years: Year[]; ratios?: boolean; children: ReactNode }) {
  const t = useT();
  return (
    <div className="r100-table-scroll">
      <table className={`r100-table r100-financial-table${ratios ? " r100-ratio-table" : ""}`}>
        <thead>
          <tr>
            <th scope="col">{ratios ? t("Indicator") : <span className="visually-hidden">{t("Measure")}</span>}</th>
            {years.map((year) => <th key={year.id} scope="col">{year.year}</th>)}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function liabilities(year: Year) {
  return typeof year.total_assets_minor === "number" && typeof year.equity_minor === "number" ? year.total_assets_minor - year.equity_minor : null;
}

function DebtFacilities({ facilities, t }: { facilities: MarketplaceDebtFacility[]; t: T }) {
  const asAt = facilities[0]?.as_at;
  return (
    <section aria-labelledby="r100-debt-title" className="r100-financial-card">
      <div className="r100-table-heading"><h3 id="r100-debt-title">{t("Existing debt")}</h3>{asAt ? <span>{t("At {date}", { date: formatDate(asAt) })}</span> : null}</div>
      <div className="r100-table-scroll">
        <table className="r100-table r100-debt-table">
          <thead>
            <tr><th scope="col">{t("Facility")}</th><th scope="col">{t("Balance")}</th><th scope="col">{t("Due within a year")}</th><th scope="col">{t("Due later")}</th><th scope="col">{t("Security")}</th></tr>
          </thead>
          <tbody>
            {facilities.map((facility) => (
              <tr key={facility.id}>
                <th scope="row">{facility.facility_type}</th>
                <td>{formatMoneyLabel(facility.currency, facility.balance_minor)}</td>
                <td>{facility.current_portion_minor !== null ? formatMoneyLabel(facility.currency, facility.current_portion_minor) : "–"}</td>
                <td>{facility.non_current_portion_minor !== null ? formatMoneyLabel(facility.currency, facility.non_current_portion_minor) : "–"}</td>
                <td>{facility.security_description || "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="bxm-muted small">{t("Existing debt is separate from the amount offered through this investment.")}</p>
    </section>
  );
}

export function FinancialStatements({ years, facilities, company, currency }: { years: Year[]; facilities: MarketplaceDebtFacility[]; company: string; currency: string }) {
  const t = useT();
  const [formulasOpen, setFormulasOpen] = useState(false);
  const sorted = [...years].sort((left, right) => left.year - right.year);
  const withInterest = present(sorted, (year) => year.interest_expense_minor);
  const source = [...sorted].reverse().find((year) => year.source_document)?.source_document;
  const yearCurrency = sorted[sorted.length - 1]?.currency || currency;
  return (
    <>
      <div className="r100-financial-context">
        <span>{[company, sorted.length > 1 ? `${sorted[0].year}–${sorted[sorted.length - 1].year}` : String(sorted[0]?.year ?? "")].filter(Boolean).join(" · ")}</span>
        <span><span>{t("Historical")}</span> · {yearCurrency} <span>{t("thousands")}</span></span>
      </div>
      <section aria-labelledby="r100-pl-title" className="r100-financial-card">
        <div className="r100-table-heading"><h3 id="r100-pl-title">{t("Profit & loss")}</h3><span>{t("Financial year")}</span></div>
        <Table years={sorted}>
          <Row label={t("Revenue")} read={(year) => year.revenue_minor} years={sorted} />
          <GroupRows
            details={[
              { label: t("Materials & purchased services"), read: (year) => year.materials_costs_minor, negative: true },
              { label: t("Staff costs"), read: (year) => year.staff_costs_minor, negative: true },
              { label: t("Other operating costs"), read: (year) => year.other_operating_costs_minor, negative: true },
              { label: t("Depreciation"), read: (year) => year.depreciation_minor, negative: true }
            ]}
            label={t("Operating profit")}
            read={(year) => year.operating_profit_minor}
            years={sorted}
          />
          <GroupRows
            details={[
              { label: t("Interest expense"), read: (year) => year.interest_expense_minor, negative: true },
              { label: t("Profit before tax"), read: (year) => year.profit_before_tax_minor },
              { label: t("Income tax"), read: (year) => year.income_tax_minor, negative: true }
            ]}
            label={t("Net profit")}
            read={(year) => year.net_profit_minor}
            years={sorted}
          />
        </Table>
      </section>
      <section aria-labelledby="r100-bs-title" className="r100-financial-card">
        <div className="r100-table-heading"><h3 id="r100-bs-title">{t("Balance sheet")}</h3><span>{t("At year-end")}</span></div>
        <Table years={sorted}>
          <GroupRows
            details={[
              { label: t("Current assets"), read: (year) => year.current_assets_minor },
              { label: t("Cash"), read: (year) => year.cash_minor },
              { label: t("Trade receivables"), read: (year) => year.trade_receivables_minor },
              { label: t("Inventories"), read: (year) => year.inventories_minor },
              { label: t("Other current assets"), read: (year) => year.other_current_assets_minor },
              { label: t("Property, plant & equipment"), read: (year) => year.property_plant_equipment_minor },
              { label: t("Other non-current assets"), read: (year) => year.other_non_current_assets_minor }
            ]}
            label={t("Total assets")}
            read={(year) => year.total_assets_minor}
            years={sorted}
          />
          <GroupRows
            details={[
              { label: t("Trade payables"), read: (year) => year.trade_payables_minor },
              { label: t("Other operating liabilities"), read: (year) => year.other_operating_liabilities_minor }
            ]}
            label={t("Total liabilities")}
            read={liabilities}
            years={sorted}
          />
          <GroupRows
            details={[
              { label: t("Current financial debt"), read: (year) => year.current_financial_debt_minor },
              { label: t("Non-current financial debt"), read: (year) => year.non_current_financial_debt_minor }
            ]}
            label={t("Of which financial debt")}
            read={(year) => year.financial_debt_minor}
            subtotal={false}
            years={sorted}
          />
          <Row label={t("Equity")} read={(year) => year.equity_minor} subtotal years={sorted} />
        </Table>
      </section>
      <section aria-labelledby="r100-ratios-title" className="r100-financial-card">
        <div className="r100-table-heading">
          <h3 id="r100-ratios-title">{t("Key ratios")}</h3>
          <button aria-label={t("Ratio formulas")} className="r100-info" onClick={() => setFormulasOpen(true)} type="button"><NiIcon name="info" /></button>
        </div>
        <Table ratios years={sorted}>
          <tr><th scope="row"><span className="r100-row-indent" /><span>{t("Equity / total assets")}</span></th>{sorted.map((year) => <td key={year.id}>{ratio(year.equity_minor, year.total_assets_minor, "%")}</td>)}</tr>
          <tr><th scope="row"><span className="r100-row-indent" /><span>{t("Financial debt / equity")}</span></th>{sorted.map((year) => <td key={year.id}>{ratio(year.financial_debt_minor, year.equity_minor, "×")}</td>)}</tr>
          <tr><th scope="row"><span className="r100-row-indent" /><span>{t("Operating margin")}</span></th>{sorted.map((year) => <td key={year.id}>{ratio(year.operating_profit_minor, year.revenue_minor, "%")}</td>)}</tr>
          {withInterest ? <tr><th scope="row"><span className="r100-row-indent" /><span>{t("Interest coverage")}</span></th>{sorted.map((year) => <td key={year.id}>{ratio(year.operating_profit_minor, year.interest_expense_minor, "×", { absolute: true })}</td>)}</tr> : null}
        </Table>
      </section>
      {facilities.length > 0 ? <DebtFacilities facilities={facilities} t={t} /> : null}
      {source ? <div className="r100-financial-source"><span className="r100-link"><NiIcon name="file-text" /> {source.display_name}</span></div> : null}
      <p className="bxm-muted small">{t("Historical figures from the borrower's financial statements. They are not audited by Banxum and do not predict future results.")}</p>
      {formulasOpen ? (
        <Dialog onClose={() => setFormulasOpen(false)} size="md" title={t("Key ratios")}>
          <p><b>{t("Equity / total assets")}</b><br /><span>{t("Equity ÷ total assets × 100.")}</span></p>
          <p><b>{t("Financial debt / equity")}</b><br /><span>{t("Financial debt ÷ equity.")}</span></p>
          <p><b>{t("Operating margin")}</b><br /><span>{t("Operating profit ÷ revenue × 100.")}</span></p>
          {withInterest ? <p><b>{t("Interest coverage")}</b><br /><span>{t("Operating profit ÷ interest expense (as a positive amount).")}</span></p> : null}
          <p>{t("Calculated for each historical year. Financial debt excludes trade and other operating liabilities.")}</p>
          <p>{t("n/a: a figure is missing or the divisor is zero or negative.")}</p>
        </Dialog>
      ) : null}
    </>
  );
}
