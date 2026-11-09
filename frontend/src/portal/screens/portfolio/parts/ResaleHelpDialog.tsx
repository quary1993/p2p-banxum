// IP of Webby-Soft SRL.
// "How resale works" (design dialog .p99-help-modal with the price example). The texts state today's
// rules: the whole position, payments up to date, par or a discount (no premium), the seller fee shown
// before confirming and charged only on a sale, accrued interest outside the fee. The U33-DEC-06/07
// values (premium up to 2%, the capped 2% fee) come with Phase 17.2.
import { useId, useState } from "react";

import { useT } from "../../../../i18n";
import { formatDecimal, formatMoneyMinor, useNumberFormat } from "../../../../investorPortal/format";
import { Dialog, NiIcon } from "../../../components";

const EXAMPLE_VALUE_MINOR = 100_000; // EUR 1.000, an illustration only

export function ResaleHelpDialog({ onClose, buyerFeeFree }: { onClose: () => void; buyerFeeFree: boolean | null }) {
  const t = useT();
  useNumberFormat();
  const numberId = useId();
  const [discount, setDiscount] = useState(1);
  const [typed, setTyped] = useState<string | null>(null);
  const priceMinor = Math.round(EXAMPLE_VALUE_MINOR * (100 - discount) / 100);
  const label = discount === 0 ? t("No discount") : t("{percent}% discount", { percent: formatDecimal(discount, discount % 1 === 0 ? 0 : 1) });
  const money = (minor: number) => formatMoneyMinor(minor, "EUR", minor % 100 === 0 ? 0 : 2);
  const applyTyped = (text: string) => {
    const value = Number(text.replace(",", ".").replace(/[^\d.-]/g, ""));
    if (Number.isFinite(value)) setDiscount(Math.min(100, Math.max(0, Math.abs(value))));
    setTyped(null);
  };
  return (
    <Dialog bodyClassName="p99-help-body" className="p99-help-modal p99-simulator-modal" onClose={onClose} title={t("How resale works")}>
      <p className="p99-help-intro">{t("Buy an existing investment from another investor. Future loan payments go to your Banxum balance.")}</p>
      <section aria-label={t("Discount example")} className="p99-simulator">
        <div className="p99-simulator-base">
          <span>
            {t("Investment value")}
            <small>{t("Amount still to be repaid")}</small>
          </span>
          <strong><small>EUR</small> {money(EXAMPLE_VALUE_MINOR)}</strong>
        </div>
        <div className="p99-adjustment-head">
          <label htmlFor={numberId}>{t("Try a different price")}</label>
          <span className="p99-example-tag">{t("Example")}</span>
        </div>
        <div className="p99-adjustment-choice">
          <strong>{label}</strong>
          <label className="p99-percentage">
            <input
              aria-label={t("Discount percentage")}
              id={numberId}
              inputMode="decimal"
              onBlur={(event) => applyTyped(event.target.value)}
              onChange={(event) => setTyped(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") applyTyped((event.target as HTMLInputElement).value);
              }}
              type="text"
              value={typed ?? (discount === 0 ? "0" : `-${formatDecimal(discount, discount % 1 === 0 ? 0 : 1)}`)}
            />
            <span>%</span>
          </label>
        </div>
        <div className="p99-range-wrap">
          <input aria-label={t("Discount")} aria-valuetext={label} max="0" min="-100" onChange={(event) => setDiscount(Math.abs(Number(event.target.value)))} step="0.5" type="range" value={-discount} />
          <i aria-hidden="true" />
        </div>
        <div className="p99-range-labels">
          <span>{t("Discount")}</span>
          <span>{t("No premium")}</span>
        </div>
        <div aria-atomic="true" aria-live="polite" className="p99-simulator-result" role="status">
          <span>{t("You pay")}</span>
          <strong><small>EUR</small> <output>{money(priceMinor)}</output></strong>
          <p>{discount === 0 ? t("You pay the investment value.") : t("The discount reduces the price by EUR {amount}.", { amount: money(EXAMPLE_VALUE_MINOR - priceMinor) })}</p>
        </div>
      </section>
      <p className="p99-help-note p99-price-principle">
        {t("The investment value stays the same.")}
        <br />
        {t("The price you pay changes.")}
      </p>
      <details className="p99-accrued-help">
        <summary>
          {t("Accrued interest is added separately")} <span aria-hidden="true">ⓘ</span>
        </summary>
        <p>{t("Interest earned by the seller but not yet paid by the business. The buyer pays it on top of the price; no fee is charged on it.")}</p>
      </details>
      <details className="p99-trading-details">
        <summary>
          {t("Trading details")}
          <NiIcon name="chevron-down" />
        </summary>
        <ul>
          <li>{t("You buy or sell the entire listed investment.")}</li>
          <li>{t("Only investments with payments up to date can be listed.")}</li>
          <li>{t("Listings are priced at the investment value or at a discount. A premium is not possible today.")}</li>
          <li>{t("The seller pays a selling fee on the selling price. The exact fee is shown before the listing is confirmed and is charged only when the investment is sold.")}</li>
          <li>
            {buyerFeeFree === true
              ? t("Accrued interest is excluded from the fee. Buyers pay no fee.")
              : t("Accrued interest is excluded from the fee. Any buyer fee is shown before you confirm a purchase.")}
          </li>
          <li>{t("Paying less than the investment value increases your projected return. The loan's interest rate stays the same.")}</li>
          <li>{t("A listing is not a completed sale. A buyer must purchase the investment.")}</li>
        </ul>
      </details>
    </Dialog>
  );
}
