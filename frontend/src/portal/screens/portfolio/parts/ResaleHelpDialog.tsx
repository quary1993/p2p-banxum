// IP of Webby-Soft SRL.
// "How resale works" (design dialog .p99-help-modal with the price example). U33-DEC-06/07: the whole
// position, payments up to date, a discount or a premium of at most 2%, the seller fee of 2% of the price
// capped at 2% of the remaining investment value, shown before confirming and charged only on a sale,
// and no fee on accrued interest. The design's 1% values are 2% by decision.
import { useId, useState } from "react";

import { useT } from "../../../../i18n";
import { formatDecimal, formatMoneyMinor, useNumberFormat } from "../../../../investorPortal/format";
import { Dialog, NiIcon } from "../../../components";

const EXAMPLE_VALUE_MINOR = 100_000; // EUR 1.000, an illustration only
const MAX_PREMIUM = 2; // U33-DEC-06: a premium of at most 2%

export function ResaleHelpDialog({ onClose, buyerFeeFree }: { onClose: () => void; buyerFeeFree: boolean | null }) {
  const t = useT();
  useNumberFormat();
  const numberId = useId();
  // The price adjustment in percent: below zero a discount, above zero a premium.
  const [adjustment, setAdjustment] = useState(-1);
  const [typed, setTyped] = useState<string | null>(null);
  const clamp = (value: number) => Math.round(Math.max(-100, Math.min(MAX_PREMIUM, value)) * 10) / 10;
  const priceMinor = Math.round(EXAMPLE_VALUE_MINOR * (100 + adjustment) / 100);
  const size = Math.abs(adjustment);
  const percent = formatDecimal(size, size % 1 === 0 ? 0 : 1);
  const label = adjustment === 0
    ? t("No discount or premium")
    : adjustment < 0 ? t("{percent}% discount", { percent }) : t("{percent}% premium", { percent });
  const money = (minor: number) => formatMoneyMinor(minor, "EUR", minor % 100 === 0 ? 0 : 2);
  const difference = money(Math.abs(EXAMPLE_VALUE_MINOR - priceMinor));
  const applyTyped = (text: string) => {
    const value = Number(text.replace(",", ".").replace(/[^\d.-]/g, ""));
    if (Number.isFinite(value) && text.trim() !== "") setAdjustment(clamp(value));
    setTyped(null);
  };
  return (
    <Dialog bodyClassName="p99-help-body" className="p99-help-modal p99-simulator-modal" onClose={onClose} title={t("How resale works")}>
      <p className="p99-help-intro">
        <span className="u104-sentence">{t("Buy an existing investment from another investor.")}</span>{" "}
        <span className="u104-sentence">{t("Future loan payments go to your Banxum account.")}</span>
      </p>
      <section aria-label={t("Discount and premium example")} className="p99-simulator" data-kind={adjustment < 0 ? "discount" : adjustment > 0 ? "premium" : "neutral"}>
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
              aria-label={t("Price adjustment percentage")}
              id={numberId}
              inputMode="decimal"
              onBlur={(event) => applyTyped(event.target.value)}
              onChange={(event) => setTyped(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") applyTyped((event.target as HTMLInputElement).value);
              }}
              type="text"
              value={typed ?? (adjustment === 0 ? "0" : `${adjustment < 0 ? "-" : ""}${percent}`)}
            />
            <span>%</span>
          </label>
        </div>
        <div className="p99-range-wrap">
          <input aria-label={t("Discount or premium")} aria-valuetext={label} max={MAX_PREMIUM} min="-100" onChange={(event) => setAdjustment(clamp(Number(event.target.value)))} step="0.1" type="range" value={adjustment} />
          <i aria-hidden="true" style={{ left: `${(100 / (100 + MAX_PREMIUM)) * 100}%` }} />
        </div>
        <div className="p99-range-labels">
          <span>{t("Discount")}</span>
          <span>{t("{percent}% premium", { percent: formatDecimal(MAX_PREMIUM, 0) })}</span>
        </div>
        <div aria-atomic="true" aria-live="polite" className="p99-simulator-result" role="status">
          <span>{t("You pay")}</span>
          <strong><small>EUR</small> <output>{money(priceMinor)}</output></strong>
          <p>
            {adjustment === 0
              ? t("You pay the investment value.")
              : adjustment < 0
                ? t("The discount reduces the price by EUR {amount}.", { amount: difference })
                : t("The premium increases the price by EUR {amount}.", { amount: difference })}
          </p>
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
          <li>{t("The seller pays 2% of the selling price, capped at 2% of the remaining investment value. The exact fee is shown before the listing is confirmed and is charged only when the investment is sold.")}</li>
          <li>
            {buyerFeeFree === true
              ? t("Accrued interest is excluded from the fee. Buyers pay no fee.")
              : t("Accrued interest is excluded from the fee. Any buyer fee is shown before you confirm a purchase.")}
          </li>
          <li>{t("New listings can have a premium of up to 2%.")}</li>
          <li>{t("Paying less increases your projected return. Paying more reduces it. The loan's interest rate stays the same.")}</li>
          <li>{t("A listing is not a completed sale. A buyer must purchase the investment.")}</li>
        </ul>
      </details>
    </Dialog>
  );
}
