// IP of Webby-Soft SRL.
// Loan-to-value comparison (design: .r68-ltv): the loan amount and the collateral value as two bars on
// one scale, with the ratio, for the first security (U33-DEC-21: the other securities are listed after it;
// prior-ranking debt is stated in the credit file with the combined share, not drawn here).
import { useLayoutEffect, useRef, useState } from "react";

import { useT } from "../../../../i18n";
import { formatMoneyMinor, formatPercent, useNumberFormat } from "../../../../investorPortal/format";

export function LtvFigure({
  loanMinor,
  valueMinor,
  currency,
  ltvBps,
  valueLabel
}: {
  loanMinor: number;
  valueMinor: number;
  currency: string;
  ltvBps: number;
  valueLabel: string;
}) {
  const t = useT();
  useNumberFormat();
  const boxRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(480);
  useLayoutEffect(() => {
    const box = boxRef.current;
    if (!box) return undefined;
    const measure = () => {
      const next = Math.round(box.getBoundingClientRect().width);
      if (next > 0) setWidth(next);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    return () => observer.disconnect();
  }, []);
  const ratio = Math.min(1, loanMinor / Math.max(1, valueMinor));
  const loanWidth = Math.max(8, width * ratio);
  const gradientId = `u33-ltv-${Math.round(ltvBps)}-${Math.round(width)}`;
  const loanText = formatMoneyMinor(loanMinor, currency, 0);
  const valueText = formatMoneyMinor(valueMinor, currency, 0);
  const ratioText = formatPercent(ltvBps / 100, 0);
  return (
    <div
      aria-label={t("Loan amount {loan}. {valueLabel} {value}. Loan-to-value {ratio}. Both bars use the same scale.", {
        loan: `${currency} ${loanText}`,
        valueLabel,
        value: `${currency} ${valueText}`,
        ratio: ratioText
      })}
      className="r68-ltv"
      ref={boxRef}
      role="group"
    >
      <svg aria-hidden="true" focusable="false" height="210" viewBox={`0 0 ${width} 210`}>
        <defs>
          <linearGradient id={gradientId} x1="0" x2="1" y1="0" y2=".6">
            <stop stopColor="#3e4a54" />
            <stop offset="1" stopColor="#202b35" />
          </linearGradient>
        </defs>
        <text className="r68-label" x="0" y="17">{t("Loan amount")}</text>
        <text className="r68-amount" x="0" y="51"><tspan className="r68-currency">{currency} </tspan><tspan>{loanText}</tspan></text>
        <rect className="r68-bar r68-loan" height="14" rx="5" width={loanWidth} x="0" y="71" />
        <path className="r68-guide" d={`M${loanWidth} 85V132`} stroke="#b3bdc5" strokeDasharray="2 4" strokeWidth="1" />
        <text className="r68-ratio" textAnchor="start" x={Math.min(loanWidth + 12, width - 90)} y="81">{ratioText}</text>
        <text className="r68-ratio-label" textAnchor="start" x={Math.min(loanWidth + 12, width - 90)} y="99">{t("Loan-to-value")}</text>
        <rect className="r68-bar r68-value" fill={`url(#${gradientId})`} height="14" rx="5" width={width} x="0" y="132" />
        <text className="r68-label" x="0" y="183">{valueLabel}</text>
        <text className="r68-amount" textAnchor="end" x={width} y="187"><tspan className="r68-currency">{currency} </tspan><tspan>{valueText}</tspan></text>
        <text className="r68-full" textAnchor="end" x={width - 12} y="143">100%</text>
      </svg>
    </div>
  );
}
