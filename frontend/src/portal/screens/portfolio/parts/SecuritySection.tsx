// IP of Webby-Soft SRL.
// The "Security" block of an investment or resale offer (design .p99v3-security with the r62 collateral
// group and the r68 loan-to-value comparison). One security per loan today (U33-DEC-21 adds several in
// Phase 17.4); the LTV comparison shows only when a collateral value exists. No promise of repayment
// (U33-DEC-38).
import { useId, useState } from "react";

import { useT } from "../../../../i18n";
import { formatMoneyMinor, formatRateBps, useNumberFormat } from "../../../../investorPortal/format";
import { NiIcon, PortalLink } from "../../../components";
import { securityLabel, securityValueLabel, tileIcon } from "./labels";

const WIDTH = 482;

/** Loan amount against the collateral value on one scale (design .r68-ltv). */
export function LtvFigure({ loanMinor, valueMinor, ltvBps, currency, valueLabel }: { loanMinor: number; valueMinor: number; ltvBps: number; currency: string; valueLabel: string }) {
  const t = useT();
  useNumberFormat();
  const scale = Math.max(loanMinor, valueMinor, 1);
  const loanWidth = Math.max(4, (loanMinor / scale) * WIDTH);
  const valueWidth = Math.max(4, (valueMinor / scale) * WIDTH);
  const ratioX = Math.min(loanWidth + 12, WIDTH - 90);
  const loanText = formatMoneyMinor(loanMinor, currency, 0);
  const valueText = formatMoneyMinor(valueMinor, currency, 0);
  return (
    <div
      aria-label={t("Loan amount {loan}. {valueLabel} {value}. Loan-to-value {ratio}. Both bars use the same scale.", { loan: `${currency} ${loanText}`, valueLabel, value: `${currency} ${valueText}`, ratio: formatRateBps(ltvBps) })}
      className="r68-ltv"
      role="group"
    >
      <svg aria-hidden="true" focusable="false" height="210" viewBox={`0 0 ${WIDTH} 210`}>
        <text className="r68-label" x="0" y="17">{t("Loan amount")}</text>
        <text className="r68-amount" x="0" y="51"><tspan className="r68-currency">{currency}</tspan><tspan> {loanText}</tspan></text>
        <rect className="r68-bar r68-loan" height="14" rx="5" width={loanWidth} x="0" y="71" />
        <text className="r68-ratio" textAnchor="start" x={ratioX} y="81">{formatRateBps(ltvBps)}</text>
        <text className="r68-ratio-label" textAnchor="start" x={ratioX} y="99">{t("Loan-to-value")}</text>
        <rect className="r68-bar r68-value" height="14" rx="5" width={valueWidth} x="0" y="132" />
        <text className="r68-label" x="0" y="183">{valueLabel}</text>
        <text className="r68-amount" textAnchor="end" x={WIDTH} y="187"><tspan className="r68-currency">{currency}</tspan><tspan> {valueText}</tspan></text>
      </svg>
    </div>
  );
}

export function SecuritySection({
  collateralType,
  description,
  collateralValueMinor,
  loanPrincipalMinor,
  ltvBps,
  currency,
  loanId,
  variant = "investment"
}: {
  collateralType: string;
  description: string;
  collateralValueMinor: number | null;
  loanPrincipalMinor: number | null;
  ltvBps: number | null;
  currency: string;
  loanId: string;
  /** "offer": the resale offer page's layout (section.refined-security, h2 heading, "Details" link). */
  variant?: "investment" | "offer";
}) {
  const t = useT();
  const disclosureId = useId();
  const [open, setOpen] = useState(false);
  const unsecured = /unsecured/i.test(collateralType);
  const comparable = !unsecured && ltvBps !== null && collateralValueMinor !== null && collateralValueMinor > 0 && loanPrincipalMinor !== null;
  const group = (
    <div className={`r62-collateral-group${variant === "offer" ? "" : " p99v3-collateral"}`}>
      <div className="r62-collateral-head">
        <NiIcon name={tileIcon(collateralType)} />
        <div className="r62-collateral-copy">
          {/* Design: one line naming the concrete security; the type label only when there is no description. */}
          <strong>{variant !== "offer" && description ? description : securityLabel(collateralType)}</strong>
        </div>
        {comparable ? (
          <button
            aria-controls={disclosureId}
            aria-expanded={open}
            aria-label={open ? t("Loan-to-value {ratio}. Hide comparison", { ratio: formatRateBps(ltvBps) }) : t("Loan-to-value {ratio}. Show comparison", { ratio: formatRateBps(ltvBps) })}
            className="r62-toggle"
            onClick={() => setOpen((value) => !value)}
            type="button"
          >
            <span>{t("Loan-to-value")}</span>
            <strong>{formatRateBps(ltvBps)}</strong>
            <i aria-hidden="true" className="r62-circle" />
          </button>
        ) : !unsecured && ltvBps !== null ? (
          <span className="r62-toggle u33-ltv-static">
            <span>{t("Loan-to-value")}</span>
            <strong>{formatRateBps(ltvBps)}</strong>
          </span>
        ) : null}
      </div>
      {comparable ? (
        <div aria-hidden={!open} className={`r62-disclosure${open ? " is-open" : ""}`} id={disclosureId} inert={!open}>
          <div className="r62-clip">
            <figure className="r62-figure">
              <LtvFigure currency={currency} loanMinor={loanPrincipalMinor} ltvBps={ltvBps} valueLabel={t(securityValueLabel(collateralType))} valueMinor={collateralValueMinor} />
            </figure>
          </div>
        </div>
      ) : null}
    </div>
  );
  if (variant === "offer") {
    return (
      <section className="refined-security">
        <div className="r36-security-head">
          <h2>{t("Security")}</h2>
          <PortalLink aria-label={t("Security details & documents")} className="rc-resource" params={{ loanId }} to="loan">
            {t("Details")} <NiIcon name="arrow-right" />
          </PortalLink>
        </div>
        {description ? <p>{description}</p> : null}
        <div className="rc-security-types">{group}</div>
      </section>
    );
  }
  return (
    <section className="p99v3-security">
      <div className="p99v3-security-heading">
        <h3>{t("Security")}</h3>
        <PortalLink params={{ loanId }} to="loan">
          {t("Details & documents")} <NiIcon name="arrow-right" />
        </PortalLink>
      </div>
      {group}
    </section>
  );
}
