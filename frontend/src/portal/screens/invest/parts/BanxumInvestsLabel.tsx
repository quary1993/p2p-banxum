// IP of Webby-Soft SRL.
// Q04 (2026-11-13): the design's co-investment label (u102-co-label with its "i") as "Banxum invests",
// without an amount or a percentage. Shown only when a Garanta account has a confirmed reservation or
// holds a participation in the loan; same terms as the other investors (U33-DEC-15).
import { useT } from "../../../../i18n";
import { InfoTip } from "../../../components";

export function BanxumInvestsLabel() {
  const t = useT();
  return (
    <span className="u102-co-label">
      <span>{t("Banxum invests")}</span>
      <InfoTip label={t("Banxum invests")} title={t("Banxum invests")}>
        {t("Banxum invests its own money in this loan, on the same terms as the other investors. It has no priority and no obligation to cover losses.")}
      </InfoTip>
    </span>
  );
}
