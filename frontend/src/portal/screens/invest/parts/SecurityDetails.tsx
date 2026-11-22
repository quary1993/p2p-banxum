// IP of Webby-Soft SRL.
// U33-DEC-21: the securities of a loan, each managed separately, with only the fields that apply.
// Design: the credit file's r100-security-block (title, facts "Owner / rights holder", "Rights &
// priority", "Status", the guarantee's "Provider / owner" and "Guarantee limit") and the opportunity's
// rc-security-type rows. A guarantee shows its scope and limit; it never has an asset value, and its
// limit is never added to an asset value. Prior-ranking debt is shown with the combined share of the
// stated value, labelled as such.
// C06 / F16: the admin chooses the main security (the summary); the loan-to-value uses the sum of the
// values that count (distinct assets with a documented valuation), and the investor sees which assets,
// with their values and valuation dates. A valuation in another currency shows its amount and rate.
import type { MarketplaceSecurity } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { formatDate, formatDecimal, formatMoneyLabel, formatPercent } from "../../../../investorPortal/format";
import { NiIcon } from "../../../components";
import { securityValueLabel } from "../../portfolio/parts/labels";
import { collateralIcon, collateralLabel } from "../loanFacts";

type T = ReturnType<typeof useT>;

/** "EUR 1.000,00 at 0,95 (2 Nov 2026)" for a valuation in another currency. */
function foreignValuationText(security: MarketplaceSecurity, t: T) {
  if (!security.valuation_currency || security.valuation_amount_minor === null) return "";
  const amount = formatMoneyLabel(security.valuation_currency, security.valuation_amount_minor);
  // The rate with its own decimals (up to 8), in the investor's number format.
  const rateValue = Number(security.valuation_fx_rate ?? "");
  const decimals = Math.min(8, (rateValue.toString().split(".")[1] ?? "").length);
  const rate = security.valuation_fx_rate && Number.isFinite(rateValue) ? formatDecimal(rateValue, decimals) : "";
  return security.valuation_fx_rate_date
    ? t("{amount} at a rate of {rate} ({date})", { amount, rate, date: formatDate(security.valuation_fx_rate_date) })
    : t("{amount} at a rate of {rate}", { amount, rate });
}

/** F16: the assets whose values make the loan-to-value, when there are several (or not only the main). */
export function LtvAssets({ counted, main, currency }: { counted: MarketplaceSecurity[]; main?: MarketplaceSecurity; currency: string }) {
  const t = useT();
  if (counted.length === 0 || (counted.length === 1 && counted[0] === main)) return null;
  return (
    <div className="u33-ltv-assets">
      <p className="bxm-muted small">{t("The loan-to-value uses the sum of these values:")}</p>
      <ul>
        {counted.map((security) => (
          <li key={security.id}>
            <strong>{collateralLabel(security.security_type)}</strong>
            <span>{formatMoneyLabel(currency, security.value_minor ?? 0)}</span>
            {security.valuation_date ? <small>{t("Assessed {date}", { date: formatDate(security.valuation_date) })}</small> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function securityStatusLabel(status: string, t: T) {
  if (status === "in_place") return t("In place");
  if (status === "pending") return t("Being put in place");
  if (status === "released") return t("Released");
  return "";
}

function securityRankLabel(rank: number | null | undefined, t: T) {
  if (!rank) return "";
  return rank === 1 ? t("First rank") : t("Rank {rank}", { rank });
}

/** "Including prior debt, total secured borrowing is 72.4% of the stated value." */
function combinedShare(security: MarketplaceSecurity, loanMinor: number) {
  if (!security.prior_ranking_debt_minor || !security.value_minor) return null;
  return ((security.prior_ranking_debt_minor + loanMinor) / security.value_minor) * 100;
}

function Facts({ rows }: { rows: [string, string][] }) {
  const shown = rows.filter(([, value]) => value);
  if (shown.length === 0) return null;
  return (
    <dl className="r100-security-facts r100-security-record">
      {shown.map(([label, value]) => (
        <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
      ))}
    </dl>
  );
}

/** The record facts of one security (owner, rank, status, valuation or guarantee limit). */
export function SecurityFacts({ security, currency, loanMinor, withValue = true }: { security: MarketplaceSecurity; currency: string; loanMinor: number; withValue?: boolean }) {
  const t = useT();
  if (security.is_guarantee) {
    return (
      <Facts
        rows={[
          [t("Provider / owner"), security.holder_name],
          [t("Guarantee limit"), security.undertaking_limit_minor !== null ? formatMoneyLabel(currency, security.undertaking_limit_minor) : ""],
          [t("Status"), securityStatusLabel(security.status, t)]
        ]}
      />
    );
  }
  const share = combinedShare(security, loanMinor);
  return (
    <>
      <Facts
        rows={[
          [t(securityValueLabel(security.security_type)), withValue && security.value_minor !== null ? formatMoneyLabel(currency, security.value_minor) : ""],
          [t("Assessment date"), security.valuation_date ? formatDate(security.valuation_date) : ""],
          [t("Valuation basis"), security.valuation_source],
          [t("Prepared by"), security.appraiser],
          [t("Owner / rights holder"), security.holder_name],
          [t("Rights & priority"), securityRankLabel(security.rank, t)],
          [t("Status"), securityStatusLabel(security.status, t)],
          [t("Prior-ranking debt"), security.prior_ranking_debt_minor ? formatMoneyLabel(currency, security.prior_ranking_debt_minor) : ""],
          [t("Valuation in {currency}", { currency: security.valuation_currency }), foreignValuationText(security, t)],
          [t("In the loan-to-value"), withValue && security.value_minor !== null && security.status !== "released" ? (security.counts_in_ltv ? t("Yes") : t("No")) : ""]
        ]}
      />
      {share !== null ? (
        <p className="bxm-muted small">{t("Including prior debt, total secured borrowing is {share} of the stated value.", { share: formatPercent(share, 1) })}</p>
      ) : null}
    </>
  );
}

/** Scope, insurance and records of one security, when recorded. */
export function SecurityNotes({ security }: { security: MarketplaceSecurity }) {
  const t = useT();
  return (
    <>
      {security.undertaking_scope ? <><h4>{t("Scope")}</h4><p>{security.undertaking_scope}</p></> : null}
      {security.insurance ? <><h4>{t("Insurance")}</h4><p>{security.insurance}</p></> : null}
      {security.documents.length > 0 ? <p className="bxm-muted small">{t("Records: {names}", { names: security.documents.map((document) => document.display_name).join(", ") })}</p> : null}
    </>
  );
}

/** A credit file block for a security other than the main one (design: r100-security-block r100-guarantee). */
export function AdditionalSecurityBlock({ security, currency, loanMinor }: { security: MarketplaceSecurity; currency: string; loanMinor: number }) {
  return (
    <section className={`r100-security-block${security.is_guarantee ? " r100-guarantee" : ""}`}>
      <div className="r100-security-title">
        <span className="r100-symbol"><NiIcon name={collateralIcon(security.security_type)} /></span>
        <div>
          <h3>{collateralLabel(security.security_type)}</h3>
          {security.description && security.description !== security.security_type ? <p>{security.description}</p> : null}
        </div>
      </div>
      <SecurityFacts currency={currency} loanMinor={loanMinor} security={security} />
      <SecurityNotes security={security} />
    </section>
  );
}

/** An opportunity row for a security other than the main one (design: rc-security-type). */
export function SecurityTypeRow({ security, currency }: { security: MarketplaceSecurity; currency: string }) {
  const t = useT();
  const detail = security.is_guarantee
    ? [security.holder_name, security.undertaking_limit_minor !== null ? t("Limit {amount}", { amount: formatMoneyLabel(currency, security.undertaking_limit_minor) }) : ""].filter(Boolean).join(" · ")
    : security.description && security.description !== security.security_type ? security.description : "";
  const status = security.status === "released" ? securityStatusLabel(security.status, t) : "";
  return (
    <div className="rc-security-type">
      <NiIcon name={collateralIcon(security.security_type)} />
      <strong>{collateralLabel(security.security_type)}</strong>
      {detail || status ? <span>{[detail, status].filter(Boolean).join(" · ")}</span> : null}
    </div>
  );
}
