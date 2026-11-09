// IP of Webby-Soft SRL.
// Small U33 building blocks of the portfolio area (slice S3). Shared primitives come from
// portal/components; these are portfolio-specific and may be merged into components later.
import type { ReactNode } from "react";

import { useT } from "../../../../i18n";
import { formatMoneyMinor, useNumberFormat } from "../../../../investorPortal/format";
import type { RouteName } from "../../../../investorPortal/types";
import { Button, EmptyState, NiIcon, PageHead, PortalLink } from "../../../components";
import { tileIcon } from "./labels";

/** The black project tile with a line icon (design .bxm-project-tile / .mi40-tile). */
export function ProjectTile({ collateralType, className = "bxm-project-tile", as: Tag = "div" }: { collateralType: string; className?: string; as?: "div" | "span" }) {
  return (
    <Tag aria-hidden="true" className={className}>
      <NiIcon name={tileIcon(collateralType)} />
    </Tag>
  );
}

/** "EUR" + amount as the design writes summary figures: <span>EUR</span><strong>537,51</strong>. */
export function CurrencyFigure({ currency, amountMinor, codeAs: Code = "span", valueAs: Value = "strong", className }: { currency: string; amountMinor: number; codeAs?: "span" | "small"; valueAs?: "strong" | "span"; className?: string }) {
  useNumberFormat();
  return (
    <div className={className}>
      <Code>{currency}</Code>
      <Value>{formatMoneyMinor(amountMinor, currency)}</Value>
    </div>
  );
}

/** A labelled native select (design label.bxm-mi-filter / .mi64-sort-label / .rs-sort). */
export function SelectFilter<V extends string>({
  label,
  ariaLabel,
  value,
  options,
  onChange,
  className,
  selectClassName = "form-select"
}: {
  label: string;
  ariaLabel?: string;
  value: V;
  options: Array<{ value: V; label: string; disabled?: boolean }>;
  onChange: (value: V) => void;
  className: string;
  selectClassName?: string;
}) {
  return (
    <label className={className}>
      {label}
      <select aria-label={ariaLabel ?? label} className={selectClassName} onChange={(event) => onChange(event.target.value as V)} value={value}>
        {options.map((option) => (
          <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

/** The back link above a sub-page (design a.r75c-back / a.back-to). */
export function BackLink({ to, onClick, children, className = "r75c-back" }: { to?: RouteName; onClick?: () => void; children: ReactNode; className?: string }) {
  if (onClick) {
    return (
      <a
        className={className}
        href={window.location.pathname}
        onClick={(event) => {
          event.preventDefault();
          onClick();
        }}
      >
        <NiIcon name="arrow-left" />
        {className === "back-to" ? <span>{children}</span> : children}
      </a>
    );
  }
  return (
    <PortalLink className={className} to={to ?? "portfolio"}>
      <NiIcon name="arrow-left" />
      {className === "back-to" ? <span>{children}</span> : children}
    </PortalLink>
  );
}

/** Loading state of a portfolio page: the page head and a quiet line. */
export function PageLoading({ title, className }: { title: string; className: string }) {
  const t = useT();
  return (
    <main aria-busy="true" className={className}>
      <PageHead title={title} />
      <div className="card card-bordered u33-state-card">
        <div className="card-inner">
          <p className="u33-muted" role="status">{t("Loading...")}</p>
        </div>
      </div>
    </main>
  );
}

/** Error state of a portfolio page with a retry. */
export function PageError({ title, className, message, onRetry }: { title: string; className: string; message: string; onRetry: () => void }) {
  const t = useT();
  return (
    <main className={className}>
      <PageHead title={title} />
      <div className="card card-bordered u33-state-card">
        <EmptyState actions={<Button onClick={onRetry} variant="secondary">{t("Retry")}</Button>} icon="alert-circle" title={t("We could not load this page")}>
          {message}
        </EmptyState>
      </div>
    </main>
  );
}
