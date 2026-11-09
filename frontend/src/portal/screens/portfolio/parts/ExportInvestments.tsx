// IP of Webby-Soft SRL.
// "Export" on My investments and its history (design data-action="export-investments"): downloads every
// investment as CSV (built in investmentsCsv.ts).
import type { Holding, MarketplaceLoanPreview, PrimaryOrderPortal } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { useNumberFormat } from "../../../../investorPortal/format";
import { platformTodayKey } from "../../../../investorPortal/platformClock";
import { NiIcon } from "../../../components";
import { downloadTextFile } from "../../wallet/parts/downloads";
import { investmentsCsv } from "./investmentsCsv";

export function ExportInvestmentsButton({
  holdings,
  orders,
  loansById
}: {
  holdings: Holding[];
  orders: PrimaryOrderPortal[];
  loansById: Map<string, MarketplaceLoanPreview>;
}) {
  const t = useT();
  const { format } = useNumberFormat();
  const empty = holdings.length === 0 && orders.length === 0;
  return (
    <button
      className="btn btn-outline-light"
      disabled={empty}
      onClick={() => downloadTextFile(investmentsCsv(holdings, orders, loansById, format, (text) => t(text)), `banxum-investments-${platformTodayKey()}.csv`)}
      title={t("Export all investments")}
      type="button"
    >
      <NiIcon name="download" />
      <span>{t("Export")}</span>
    </button>
  );
}
