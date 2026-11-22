// IP of Webby-Soft SRL.
// Payment schedule table of the investing screens (design: .pd-schedule-table > table.table.bxm-table):
// due date, principal, interest, total; the full loan on the opportunity page, the investor's share on
// Review & sign, the quoted cash flows of a legacy claim purchase.
import { useT } from "../../../../i18n";
import { formatDate, formatMoneyLabel, useNumberFormat } from "../../../../investorPortal/format";

export type ScheduleTableRow = { key: string; dueDate: string; principalMinor: number; interestMinor: number; totalMinor: number };

export function ScheduleTable({ rows, currency, label }: { rows: ScheduleTableRow[]; currency: string; label: string }) {
  const t = useT();
  useNumberFormat();
  return (
    <div aria-label={label} className="pd-schedule-table" role="region" tabIndex={0}>
      <table className="table bxm-table">
        <thead>
          <tr>
            <th scope="col">{t("Due")}</th>
            <th className="text-end" scope="col">{t("Principal")}</th>
            <th className="text-end" scope="col">{t("Interest")}</th>
            <th className="text-end" scope="col">{t("Total")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>{formatDate(row.dueDate)}</td>
              <td className="text-end">{formatMoneyLabel(currency, row.principalMinor)}</td>
              <td className="text-end">{formatMoneyLabel(currency, row.interestMinor)}</td>
              <td className="text-end">{formatMoneyLabel(currency, row.totalMinor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
